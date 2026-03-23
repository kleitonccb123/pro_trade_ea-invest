"""
RiskManager - Camada 6

Valida risco ANTES de colocar ordens.

Responsabilidades:
- Limite de alavancagem por usuário
- Limite de tamanho de posição
- Limite de perda máxima por trade
- Kill-switch automático
- Validação de colateral
- Max drawdown
- Cooldown pós-loss
- Limite por símbolo
"""

from __future__ import annotations

import logging
import asyncio
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Optional, Tuple, Dict

if TYPE_CHECKING:
    from app.services.ea_controller import EAController

logger = logging.getLogger(__name__)


class RiskConfig:
    """Configuração de risco por usuário/estratégia."""

    def __init__(
        self,
        max_leverage: float = 10.0,
        max_position_size: Decimal = Decimal("100_000"),
        max_loss_per_trade: Decimal = Decimal("1_000"),
        max_daily_loss: Decimal = Decimal("5_000"),
        max_drawdown_pct: float = 20.0,          # % do balanço inicial
        max_open_positions: int = 10,
        max_position_per_symbol: int = 1,        # posições simultâneas por símbolo
        cooldown_after_loss_s: float = 60.0,     # segundos de pausa após loss
        kill_switch_on_daily_loss: bool = True,  # para todos os bots se atingir limite
    ):
        self.max_leverage = max_leverage
        self.max_position_size = max_position_size
        self.max_loss_per_trade = max_loss_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_drawdown_pct = max_drawdown_pct
        self.max_open_positions = max_open_positions
        self.max_position_per_symbol = max_position_per_symbol
        self.cooldown_after_loss_s = cooldown_after_loss_s
        self.kill_switch_on_daily_loss = kill_switch_on_daily_loss


class RiskManager:
    """
    Valida risco de ordens e rastreia estado de perda/drawdown/cooldown.

    Funcionalidades novas:
    - Cooldown automático após loss (bloqueia novas ordens por N segundos)
    - Controle de max drawdown percentual
    - Limite de posições abertas por símbolo
    - Kill-switch quando perda diária é atingida
    """

    def __init__(self, risk_config: Optional[RiskConfig] = None):
        self.config = risk_config or RiskConfig()

        # Estado rastreado em memória por user_id
        self._cooldown_until: Dict[str, datetime] = {}         # user_id → tempo fim cooldown
        self._peak_balance: Dict[str, Decimal] = {}            # user_id → balanço máximo histórico
        self._open_positions: Dict[str, Dict[str, int]] = {}   # user_id → {symbol → count}
        self._kill_switched: set = set()                       # user_ids com kill-switch ativo

        logger.info("✅ RiskManager inicializado")

    # ─────────────────────────────── COOLDOWN ───────────────────────────────

    def register_loss(self, user_id: str) -> None:
        """Registra loss e inicia período de cooldown para o usuário."""
        cooldown_end = datetime.now(timezone.utc) + timedelta(
            seconds=self.config.cooldown_after_loss_s
        )
        self._cooldown_until[user_id] = cooldown_end
        logger.warning(
            f"⏸ Cooldown ativado para user={user_id} "
            f"até {cooldown_end.isoformat()} "
            f"({self.config.cooldown_after_loss_s}s)"
        )

    def is_in_cooldown(self, user_id: str) -> bool:
        """Retorna True se o usuário ainda está em período de cooldown."""
        until = self._cooldown_until.get(user_id)
        if until and datetime.now(timezone.utc) < until:
            return True
        # Limpa entrada expirada
        if user_id in self._cooldown_until:
            del self._cooldown_until[user_id]
        return False

    # ─────────────────────────────── DRAWDOWN ───────────────────────────────

    def update_peak_balance(self, user_id: str, current_balance: Decimal) -> None:
        """Atualiza pico de balanço para cálculo de drawdown."""
        peak = self._peak_balance.get(user_id, Decimal("0"))
        if current_balance > peak:
            self._peak_balance[user_id] = current_balance

    def check_drawdown(self, user_id: str, current_balance: Decimal) -> Tuple[bool, Optional[str]]:
        """Retorna (is_ok, error) baseado em max drawdown percentual."""
        self.update_peak_balance(user_id, current_balance)
        peak = self._peak_balance.get(user_id, current_balance)

        if peak <= Decimal("0"):
            return True, None

        drawdown_pct = float((peak - current_balance) / peak * 100)
        if drawdown_pct >= self.config.max_drawdown_pct:
            msg = (
                f"Drawdown {drawdown_pct:.1f}% excede limite "
                f"{self.config.max_drawdown_pct}%"
            )
            logger.error(f"❌ {msg}")
            return False, msg
        return True, None

    # ────────────────────────────── KILL-SWITCH ─────────────────────────────

    def activate_kill_switch(self, user_id: str) -> None:
        """Para todas as operações do usuário."""
        self._kill_switched.add(user_id)
        logger.error(f"🔴 KILL-SWITCH ativado para user={user_id}")

    def deactivate_kill_switch(self, user_id: str) -> None:
        """Reativa operações (ação manual do admin)."""
        self._kill_switched.discard(user_id)
        logger.info(f"🟢 Kill-switch desativado para user={user_id}")

    def is_kill_switched(self, user_id: str) -> bool:
        return user_id in self._kill_switched

    async def trigger_kill_switch(
        self,
        user_id: str,
        reason: str,
        ea_controller: "EAController",  # type: ignore[name-defined]
    ) -> None:
        """
        Aciona kill switch via SaaS: bloqueia EA imediatamente e muda o
        estado do StrategyManager para CLOSING_POSITIONS.

        Fluxo (DOC-STRAT-08 §8.3):
          1. Marca user_id como kill-switched em memória
          2. Grava emergency_stop no control.json do EA (EAController)
          3. Persiste novo estado CLOSING_POSITIONS via _StateStore

        Args:
            user_id:       ID do usuário no backend
            reason:        Motivo do acionamento (para audit log)
            ea_controller: Instância de EAController já configurada para o EA
        """
        # Imports diferidos para evitar importações circulares
        from app.services.strategy_manager import _StateStore, StrategyState  # noqa: PLC0415

        # 1. Marca kill-switch em memória
        self._kill_switched.add(user_id)

        # 2. Atualiza arquivo de controle do EA imediatamente
        ea_controller.emergency_stop()

        # 3. Muda estado do StrategyManager para CLOSING_POSITIONS
        await _StateStore.save(user_id, {
            "state":       StrategyState.CLOSING_POSITIONS,
            "kill_reason": reason,
        })

        logger.critical(
            f"🚨 KILL SWITCH ativado para user={user_id} | reason={reason}"
        )

    # ────────────────────────────── POSIÇÕES ────────────────────────────────

    def register_open_position(self, user_id: str, symbol: str) -> None:
        positions = self._open_positions.setdefault(user_id, {})
        positions[symbol] = positions.get(symbol, 0) + 1

    def close_position(self, user_id: str, symbol: str) -> None:
        positions = self._open_positions.get(user_id, {})
        if symbol in positions:
            positions[symbol] = max(0, positions[symbol] - 1)

    def open_position_count(self, user_id: str, symbol: Optional[str] = None) -> int:
        positions = self._open_positions.get(user_id, {})
        if symbol:
            return positions.get(symbol, 0)
        return sum(positions.values())

    # ─────────────────────────── VALIDAÇÃO COMPLETA ─────────────────────────

    async def validate_order(
        self,
        user_id: str,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        stop_loss: Optional[Decimal] = None,
        account_balance: Optional[Decimal] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida se ordem pode ser colocada.

        Returns:
            (is_valid, error_message)
        """

        # 0. Kill-switch
        if self.is_kill_switched(user_id):
            return False, "Kill-switch ativo. Operações suspensas."

        # 0b. Cooldown
        if self.is_in_cooldown(user_id):
            until = self._cooldown_until[user_id]
            remaining = (until - datetime.now(timezone.utc)).seconds
            return False, f"Cooldown ativo ({remaining}s restantes)"

        # 1. Tamanho da posição
        position_value = size * price
        if position_value > self.config.max_position_size:
            error = (
                f"Posição ${position_value:.2f} excede limite "
                f"${self.config.max_position_size}"
            )
            logger.warning(f"⚠️ {error}")
            return False, error

        # 2. Risco máximo por trade (com stop-loss)
        if stop_loss:
            loss_per_unit = abs(price - stop_loss)
            total_loss = loss_per_unit * size

            if total_loss > self.config.max_loss_per_trade:
                error = (
                    f"Risco ${total_loss:.2f} excede limite "
                    f"${self.config.max_loss_per_trade}"
                )
                logger.warning(f"⚠️ {error}")
                return False, error

        # 3. Alavancagem
        if account_balance and account_balance > 0:
            leverage = position_value / account_balance
            if leverage > self.config.max_leverage:
                error = f"Alavancagem {leverage:.1f}x excede {self.config.max_leverage}x"
                logger.warning(f"⚠️ {error}")
                return False, error

        # 4. Limite de posições por símbolo
        sym_count = self.open_position_count(user_id, symbol)
        if sym_count >= self.config.max_position_per_symbol:
            error = (
                f"Já há {sym_count} posição(ões) abertas em {symbol}. "
                f"Limite: {self.config.max_position_per_symbol}"
            )
            logger.warning(f"⚠️ {error}")
            return False, error

        # 5. Total de posições abertas
        total_count = self.open_position_count(user_id)
        if total_count >= self.config.max_open_positions:
            error = f"Limite de {self.config.max_open_positions} posições abertas atingido"
            logger.warning(f"⚠️ {error}")
            return False, error

        # 6. Drawdown
        if account_balance:
            ok, err = self.check_drawdown(user_id, account_balance)
            if not ok:
                return False, err

        # 7. Sanidade
        if size <= Decimal("0"):
            return False, "Tamanho deve ser > 0"
        if price <= Decimal("0"):
            return False, "Preço deve ser > 0"

        logger.info(f"✅ Ordem validada: {side} {size} {symbol} @ ${price}")
        return True, None

    async def check_daily_loss(
        self,
        user_id: str,
        realized_pnl_today: Decimal,
    ) -> bool:
        """Verifica perda máxima diária. Aciona kill-switch se necessário."""
        if realized_pnl_today < -self.config.max_daily_loss:
            logger.error(
                f"❌ Perda diária ${abs(realized_pnl_today):.2f} "
                f"excede limite ${self.config.max_daily_loss}"
            )
            if self.config.kill_switch_on_daily_loss:
                self.activate_kill_switch(user_id)
            return False
        return True

    async def get_available_risk(
        self,
        user_id: str,
        account_balance: Decimal,
        realized_pnl_today: Decimal,
    ) -> Decimal:
        """Calcula quanto de risco ainda está disponível."""
        daily_loss_remaining = self.config.max_daily_loss + realized_pnl_today
        if account_balance <= 0:
            return Decimal("0")
        account_risk = account_balance / Decimal(str(self.config.max_leverage))
        return min(daily_loss_remaining, account_risk)

    def update_config(self, config: RiskConfig):
        """Atualiza configuração de risco em runtime."""
        self.config = config
        logger.info("✅ Configuração de risco atualizada")


# Instância global
risk_manager = RiskManager()


def init_risk_manager(risk_config: Optional[RiskConfig] = None):
    global risk_manager
    risk_manager = RiskManager(risk_config)
    return risk_manager


def get_risk_manager() -> RiskManager:
    """Get the global RiskManager instance."""
    global risk_manager
    if risk_manager is None:
        risk_manager = RiskManager()
    return risk_manager
