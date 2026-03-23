"""
DailyController — Controle de metas e limites financeiros diários

Equivale a:
    CheckDailyStops()    → meta diária + limite de perda (por dia)
    CheckEmergencyStop() → drawdown de emergência (% do capital inicial)
    GetDailyProfit()     → P&L realizado no dia atual

Estado:
    - Bloqueia novas entradas quando o limite é atingido
    - Reseta automaticamente no novo dia
    - Permite reativação manual se os valores foram ajustados

Contabilidade:
    O P&L do dia é obtido do histórico de operações fechadas via
    KuCoin API (equivale ao HistorySelect + HistoryDealGetDouble do MT5).
    O lado não-realizado é incluído nos cálculos de emergência.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from .config import EAConfig

logger = logging.getLogger(__name__)


@dataclass
class DailyState:
    """Estado diário do controlador financeiro."""
    trade_date: date = field(default_factory=lambda: date.today())
    daily_profit: float = 0.0         # P&L realizado do dia
    is_daily_blocked: bool = False     # bloqueado por meta/limite
    is_emergency_blocked: bool = False # bloqueado por drawdown de emergência
    initial_equity: float = 0.0       # equity ao iniciar o EA (para drawdown %)

    # Valores na hora do bloqueio (para validação de reativação)
    blocked_daily_target: float = 0.0
    blocked_loss_limit: float = 0.0

    # Runtime mutável (pode ser ajustado via painel sem reiniciar)
    runtime_daily_target: float = 0.0
    runtime_loss_limit: float = 0.0


class DailyController:
    """
    Controla limites financeiros diários e de emergência.

    Uso:
        ctrl = DailyController(config)
        ctrl.initialize(initial_equity=10_000.0)

        # A cada tick (throttled):
        ctrl.update_daily_profit(realized_pnl_today)
        ctrl.check_daily_stops(on_limit_reached_fn)
        ctrl.check_emergency_stop(current_equity, on_emergency_fn)

        # Para verificar se pode operar:
        if ctrl.can_trade:
            ...

        # Reativação manual via painel:
        ctrl.try_reactivate(new_target, new_limit)
    """

    def __init__(self, config: EAConfig):
        self.cfg = config
        self._state = DailyState(
            runtime_daily_target=config.daily_target_usd,
            runtime_loss_limit=config.daily_loss_limit_usd,
        )

    # ── Inicialização ─────────────────────────────────────────────────────────

    def initialize(self, initial_equity: float) -> None:
        """Deve ser chamado no início do EA com o equity atual."""
        self._state.initial_equity = initial_equity
        self._state.trade_date = date.today()
        if self.cfg.debug:
            logger.debug(
                "[DailyController] Iniciado — equity=%.2f target=%.2f limit=%.2f",
                initial_equity,
                self._state.runtime_daily_target,
                self._state.runtime_loss_limit,
            )

    # ── Estado ───────────────────────────────────────────────────────────────

    @property
    def can_trade(self) -> bool:
        """True se EA pode abrir novas posições (sem bloqueios)."""
        return (
            self.cfg.active
            and not self._state.is_daily_blocked
            and not self._state.is_emergency_blocked
        )

    @property
    def is_daily_blocked(self) -> bool:
        return self._state.is_daily_blocked

    @property
    def is_emergency_blocked(self) -> bool:
        return self._state.is_emergency_blocked

    @property
    def daily_profit(self) -> float:
        return self._state.daily_profit

    @property
    def initial_equity(self) -> float:
        return self._state.initial_equity

    def status_text(self) -> str:
        if not self.cfg.active:
            return "DESATIVADO"
        if self._state.is_emergency_blocked:
            return "BLOQUEADO (Emergência)"
        if self._state.is_daily_blocked:
            return "BLOQUEADO (Stop diário)"
        return "ATIVO"

    # ── Reset de novo dia ─────────────────────────────────────────────────────

    def _check_new_day(self) -> None:
        """Reseta bloqueio diário quando o dia muda (equivale ao reset do MT5)."""
        today = date.today()
        if today != self._state.trade_date:
            if self.cfg.debug:
                logger.debug("[DailyController] Novo dia — resetando bloqueio diário")
            self._state.trade_date = today
            self._state.is_daily_blocked = False
            self._state.daily_profit = 0.0

    # ── Atualizar P&L ─────────────────────────────────────────────────────────

    def update_daily_profit(self, realized_pnl: float) -> None:
        """
        Recebe o P&L realizado do dia (somado externamente das ordens fechadas).
        Equivale ao GetDailyProfit() + HistorySelect do MT5.
        """
        self._state.daily_profit = realized_pnl

    # ── Verificar stops diários ───────────────────────────────────────────────

    def check_daily_stops(self, on_limit_fn=None) -> bool:
        """
        Verifica meta diária e limite de perda.

        Retorna True se algum bloqueio foi ativado nesta chamada.
        Chama on_limit_fn() se fornecido (ex: fechar todas as posições).
        """
        self._check_new_day()

        if self._state.is_daily_blocked:
            return False

        profit = self._state.daily_profit
        target = self._state.runtime_daily_target
        limit = self._state.runtime_loss_limit

        triggered = False

        if target > 0 and profit >= target:
            logger.info(
                "[DailyController] META DIÁRIA ATINGIDA — P&L=%.2f >= target=%.2f",
                profit, target
            )
            self._state.is_daily_blocked = True
            self._state.blocked_daily_target = target
            self._state.blocked_loss_limit = limit
            triggered = True

        elif limit > 0 and profit <= -limit:
            logger.info(
                "[DailyController] LIMITE DE PERDA ATINGIDO — P&L=%.2f <= -%.2f",
                profit, limit
            )
            self._state.is_daily_blocked = True
            self._state.blocked_daily_target = target
            self._state.blocked_loss_limit = limit
            triggered = True

        if triggered and on_limit_fn:
            on_limit_fn()

        return triggered

    # ── Drawdown de emergência ────────────────────────────────────────────────

    def check_emergency_stop(self, current_equity: float, on_emergency_fn=None) -> bool:
        """
        Verifica se o drawdown percentual ultrapassou o limite de emergência.

        drawdown% = (initial_equity - current_equity) / initial_equity × 100
        """
        if self._state.is_emergency_blocked:
            return False

        if self._state.initial_equity <= 0:
            return False

        pct = self.cfg.emergency_drawdown_pct
        if pct <= 0:
            return False

        drawdown_pct = (
            (self._state.initial_equity - current_equity)
            / self._state.initial_equity
        ) * 100.0

        if drawdown_pct >= pct:
            logger.warning(
                "[DailyController] EMERGÊNCIA — Drawdown %.1f%% >= limite %.1f%%",
                drawdown_pct, pct
            )
            self._state.is_emergency_blocked = True
            if on_emergency_fn:
                on_emergency_fn()
            return True

        return False

    # ── Reativação manual ─────────────────────────────────────────────────────

    def try_reactivate(self, new_target: float, new_limit: float) -> bool:
        """
        Permite reativação do EA após bloqueio diário SE os valores foram alterados.
        Equivale ao BTN_REACTIVATE do MT5.

        Retorna True se reativado com sucesso.
        """
        if not self._state.is_daily_blocked:
            return False

        if (new_target != self._state.blocked_daily_target
                or new_limit != self._state.blocked_loss_limit):
            self._state.is_daily_blocked = False
            self._state.runtime_daily_target = new_target
            self._state.runtime_loss_limit = new_limit
            logger.info(
                "[DailyController] EA REATIVADO — target=%.2f limit=%.2f",
                new_target, new_limit
            )
            return True

        logger.warning(
            "[DailyController] Reativação negada — valores não alterados "
            "(target=%.2f limit=%.2f)",
            new_target, new_limit
        )
        return False

    def adjust_target(self, delta: float) -> None:
        """Ajuste de meta diária em tempo real (equivale a BTN_TP_INC/DEC do MT5)."""
        self._state.runtime_daily_target = max(0.0, self._state.runtime_daily_target + delta)
        if self.cfg.debug:
            logger.debug("[DailyController] MetaDiaria ajustada → %.2f", self._state.runtime_daily_target)

    def adjust_limit(self, delta: float) -> None:
        """Ajuste de limite de perda em tempo real (equivale a BTN_SL_INC/DEC do MT5)."""
        self._state.runtime_loss_limit = max(0.0, self._state.runtime_loss_limit + delta)
        if self.cfg.debug:
            logger.debug("[DailyController] LimitePerda ajustado → %.2f", self._state.runtime_loss_limit)

    def get_summary(self) -> dict:
        return {
            "can_trade": self.can_trade,
            "status": self.status_text(),
            "daily_profit": round(self._state.daily_profit, 2),
            "daily_target": self._state.runtime_daily_target,
            "daily_loss_limit": self._state.runtime_loss_limit,
            "is_daily_blocked": self._state.is_daily_blocked,
            "is_emergency_blocked": self._state.is_emergency_blocked,
            "initial_equity": self._state.initial_equity,
            "trade_date": str(self._state.trade_date),
        }
