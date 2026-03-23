"""
PositionRiskManager — DOC-07 §7

Gerencia TRÊS camadas de proteção durante a vida de uma posição aberta:

  Nível 1 — Saída de posição (por trade)
    • Stop-loss percentual
    • Take-profit percentual
    • Trailing stop
    • Tempo máximo de holding

  Nível 2 — Sessão do bot (por bot/dia)
    • Daily drawdown percentual sobre capital inicial
    • Perdas consecutivas (circuit-breaker)
    • Burst de erros (N erros em janela de T segundos)

  Nível 3 — Delegado ao KillSwitchService
    • Kill de usuário
    • Kill global de plataforma

Este manager é SÍNCRONO para Nível 1 (hot-path no loop de tick) e
ASSÍNCRONO para Nível 2/3 (chamadas periódicas ou pós-trade).

Uso:
    from app.risk.manager import PositionRiskManager, RiskConfig, StopReason

    cfg = RiskConfig(
        stop_loss_pct=2.5,
        take_profit_pct=5.0,
        trailing_stop=True,
        max_holding_hours=24.0,
        max_daily_drawdown_pct=10.0,
        max_consecutive_losses=5,
        max_error_burst=10,
        error_burst_window_seconds=300,
    )
    rm = PositionRiskManager(bot_id="abc", config=cfg)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


# ─── StopReason ──────────────────────────────────────────────────────────────

class StopReason(str, Enum):
    """Motivos padronizados para stop/encerramento de posição ou bot."""
    STOP_LOSS           = "stop_loss"
    TAKE_PROFIT         = "take_profit"
    TRAILING_STOP       = "trailing_stop"
    MAX_HOLDING_TIME    = "max_holding_time"
    DAILY_DRAWDOWN      = "daily_drawdown"
    CONSECUTIVE_LOSSES  = "consecutive_losses"
    ERROR_BURST         = "error_burst"
    EXCHANGE_OFFLINE    = "exchange_offline"
    MANUAL_STOP         = "manual_stop"
    EMERGENCY_KILL      = "emergency_kill"


# ─── RiskConfig ──────────────────────────────────────────────────────────────

@dataclass
class RiskConfig:
    """
    Configuração completa de risco para um bot.
    Pode ser construída a partir do dict de configuração do bot.

    Todos os campos têm defaults conservadores.
    """
    # Nível 1 — Saída de posição
    stop_loss_pct: float            = 2.5     # % de queda desde entrada → vender
    take_profit_pct: float          = 5.0     # % de alta desde entrada → vender
    trailing_stop: bool             = False   # trailing em vez de stop fixo
    trailing_stop_pct: float        = 2.5     # queda desde pico → trailing trigger
    max_holding_hours: float        = 0.0     # 0 = desabilitado

    # Nível 2 — Sessão
    max_daily_drawdown_pct: float   = 10.0   # % sobre capital inicial do dia
    max_consecutive_losses: int     = 5      # perdas seguidas → fechar bot
    max_error_burst: int            = 10     # N erros em burst_window_seconds → fechar
    error_burst_window_seconds: int = 300    # janela de tempo para burst (5 min)

    @classmethod
    def from_dict(cls, d: dict) -> "RiskConfig":
        """Constrói a partir do dict de configuração do bot (campos extras são ignorados)."""
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid})


# ─── PositionRiskManager ─────────────────────────────────────────────────────

class PositionRiskManager:
    """
    Gerenciador de risco em processo por bot.

    Uma instância por BotWorker. Sem dependências externas (sem Redis, sem DB).
    Toda a persistência é responsabilidade do BotWorker.
    """

    def __init__(self, bot_id: str, config: RiskConfig) -> None:
        self.bot_id = bot_id
        self.cfg    = config

        # ── Nível 1: estado da posição atual ─────────────────────────────
        self._peak_price: Optional[float]      = None  # para trailing stop
        self._position_entry_price: Optional[float] = None

        # ── Nível 2: estado da sessão ─────────────────────────────────────
        self._session_start   = datetime.now(timezone.utc)
        self._initial_capital = 0.0        # capital inicial do dia (set externamente)
        self._session_pnl     = 0.0        # PnL acumulado da sessão
        self._consecutive_losses: int = 0  # perdas consecutivas
        self._error_timestamps: List[float] = []  # timestamps de erros recentes

    # ── API pública — Nível 1: verificação de exit por posição ────────────

    def check_position_exit(
        self,
        entry_price: float,
        current_price: float,
        entry_timestamp: Optional[datetime] = None,
    ) -> Optional[StopReason]:
        """
        Verifica se a posição aberta deve ser fechada.

        Retorna StopReason se deve sair, None caso contrário.
        Chamado a cada tick de preço (hot-path — deve ser rápido).
        """
        if current_price <= 0 or entry_price <= 0:
            return None

        gain_pct = (current_price - entry_price) / entry_price * 100.0
        loss_pct = -gain_pct  # positivo quando em perda

        # Take-profit
        if gain_pct >= self.cfg.take_profit_pct:
            logger.debug(
                "PositionRiskManager[%s]: TAKE_PROFIT gain=%.2f%% >= %.2f%%",
                self.bot_id[:8], gain_pct, self.cfg.take_profit_pct,
            )
            self._reset_trailing()
            return StopReason.TAKE_PROFIT

        # Trailing stop (tem precedência sobre stop fixo quando habilitado)
        if self.cfg.trailing_stop:
            ts_reason = self._check_trailing(entry_price, current_price)
            if ts_reason:
                return ts_reason
        else:
            # Stop fixo apenas quando trailing está desabilitado
            if loss_pct >= self.cfg.stop_loss_pct:
                logger.debug(
                    "PositionRiskManager[%s]: STOP_LOSS loss=%.2f%% >= %.2f%%",
                    self.bot_id[:8], loss_pct, self.cfg.stop_loss_pct,
                )
                self._reset_trailing()
                return StopReason.STOP_LOSS

        # Tempo máximo de holding
        if self.cfg.max_holding_hours > 0 and entry_timestamp is not None:
            now = datetime.now(timezone.utc)
            # Normaliza tz
            ts = entry_timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            held_hours = (now - ts).total_seconds() / 3600.0
            if held_hours >= self.cfg.max_holding_hours:
                logger.info(
                    "PositionRiskManager[%s]: MAX_HOLDING_TIME held=%.2fh >= %.2fh",
                    self.bot_id[:8], held_hours, self.cfg.max_holding_hours,
                )
                return StopReason.MAX_HOLDING_TIME

        return None

    # ── API pública — Nível 2: estado da sessão ───────────────────────────

    def set_initial_capital(self, capital_usdt: float) -> None:
        """Define o capital inicial do dia (para cálculo de daily drawdown %)."""
        self._initial_capital = capital_usdt

    def record_trade_result(self, pnl_net: float) -> Optional[StopReason]:
        """
        Registra resultado de um trade fechado.

        Atualiza PnL de sessão e contagem de perdas consecutivas.
        Retorna StopReason se algum limite foi atingido, None caso contrário.
        Chamado pelo BotWorker imediatamente após fechar posição.
        """
        self._session_pnl += pnl_net

        if pnl_net < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        logger.debug(
            "PositionRiskManager[%s]: trade pnl=%+.4f session_pnl=%+.4f consecutive=%d",
            self.bot_id[:8], pnl_net, self._session_pnl, self._consecutive_losses,
        )

        # Verificar daily drawdown
        if self._initial_capital > 0:
            drawdown_pct = (-self._session_pnl / self._initial_capital) * 100.0
            if drawdown_pct >= self.cfg.max_daily_drawdown_pct:
                logger.warning(
                    "PositionRiskManager[%s]: DAILY_DRAWDOWN %.2f%% >= %.2f%%",
                    self.bot_id[:8], drawdown_pct, self.cfg.max_daily_drawdown_pct,
                )
                return StopReason.DAILY_DRAWDOWN

        # Verificar perdas consecutivas
        if (
            self.cfg.max_consecutive_losses > 0
            and self._consecutive_losses >= self.cfg.max_consecutive_losses
        ):
            logger.warning(
                "PositionRiskManager[%s]: CONSECUTIVE_LOSSES %d >= %d",
                self.bot_id[:8], self._consecutive_losses, self.cfg.max_consecutive_losses,
            )
            return StopReason.CONSECUTIVE_LOSSES

        return None

    def record_error(self) -> Optional[StopReason]:
        """
        Registra um erro de execução.

        Mantém timestamps de erros na janela configurada.
        Retorna StopReason.ERROR_BURST se o limite de erros foi atingido.
        Chamado pelo BotWorker no bloco except de cada ciclo.
        """
        now = time.monotonic()
        window = float(self.cfg.error_burst_window_seconds)

        # Purga timestamps fora da janela
        self._error_timestamps = [
            t for t in self._error_timestamps if (now - t) <= window
        ]
        self._error_timestamps.append(now)

        if len(self._error_timestamps) >= self.cfg.max_error_burst:
            logger.error(
                "PositionRiskManager[%s]: ERROR_BURST %d erros em %.0fs",
                self.bot_id[:8], len(self._error_timestamps), window,
            )
            return StopReason.ERROR_BURST

        return None

    # ── Consultas de estado ───────────────────────────────────────────────

    @property
    def session_pnl(self) -> float:
        return self._session_pnl

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def recent_error_count(self) -> int:
        now = time.monotonic()
        window = float(self.cfg.error_burst_window_seconds)
        return sum(1 for t in self._error_timestamps if (now - t) <= window)

    def reset_session(self) -> None:
        """Reseta o estado de sessão (chamado no início de cada dia UTC)."""
        self._session_pnl         = 0.0
        self._consecutive_losses  = 0
        self._error_timestamps    = []
        self._session_start       = datetime.now(timezone.utc)

    # ── Privados: trailing stop ────────────────────────────────────────────

    def _check_trailing(
        self,
        entry_price: float,
        current_price: float,
    ) -> Optional[StopReason]:
        # Atualiza pico
        if self._peak_price is None or current_price > self._peak_price:
            self._peak_price = current_price

        # O trailing só se ativa depois de um movimento favorável
        if self._peak_price <= entry_price:
            return None

        drop_from_peak_pct = (self._peak_price - current_price) / self._peak_price * 100.0
        if drop_from_peak_pct >= self.cfg.trailing_stop_pct:
            logger.info(
                "PositionRiskManager[%s]: TRAILING_STOP peak=%.4f current=%.4f drop=%.2f%%",
                self.bot_id[:8], self._peak_price, current_price, drop_from_peak_pct,
            )
            self._reset_trailing()
            return StopReason.TRAILING_STOP

        return None

    def _reset_trailing(self) -> None:
        self._peak_price = None
