"""
ScalperModule — Entradas scalper dentro do candle seguinte a um candle de força

Equivale ao bloco de scalper do OnTick() do MT5:
    - Ativa quando o candle anterior foi de força na direção da tendência
    - Abre 1 operação por vez dentro do candle atual
    - Só reabre após a anterior ser fechada + intervalo mínimo
    - Verifica se o preço ainda está a favor da EMA antes de abrir

Ciclo de vida por candle:
    Nova barra → verifica candle anterior de força → ativa scalper para este candle
    Scalper tenta entrar (verificando preço vs EMA)
    Operação aberta → aguarda fechamento
    Fechamento detectado → aguarda intervalo → nova tentativa
    Próxima barra → desativa scalper (candle expirou)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from .config import EAConfig
from .signal_generator import Direction

logger = logging.getLogger(__name__)

# Tipo de callback para abrir ordem
OpenOrderCallback = Callable[
    [str, str, Any],  # (direction, symbol, volume)
    Coroutine[Any, Any, Optional[str]]  # retorna order_id ou None
]


class ScalperState(str, Enum):
    IDLE         = "idle"          # inativo
    WAITING      = "waiting"       # aguardando entrada (candle ativo)
    HAS_TRADE    = "has_trade"     # operação aberta
    COOLDOWN     = "cooldown"      # aguardando intervalo após fechamento


@dataclass
class ScalperContext:
    """Estado do scalper para a barra atual."""
    active: bool = False
    direction: Direction = Direction.NONE
    bar_timestamp: int = 0        # timestamp da barra onde escalper está ativo
    has_active_trade: bool = False
    last_close_monotonic: float = 0.0


class ScalperModule:
    """
    Gerencia a lógica de entradas scalper.

    Uso pelo EA runner:
        # Na nova barra:
        scalper.on_new_bar(direction, was_force_candle, current_bar_ts)

        # Em cada tick:
        await scalper.tick(ema_value, bid, ask, has_open_pos, can_trade, open_fn, volume)

        # Quando posição fechada:
        scalper.on_position_closed()
    """

    def __init__(self, config: EAConfig):
        self.cfg = config
        self._ctx = ScalperContext()

    @property
    def is_active(self) -> bool:
        return self._ctx.active

    @property
    def state(self) -> ScalperState:
        if not self._ctx.active:
            return ScalperState.IDLE
        if self._ctx.has_active_trade:
            return ScalperState.HAS_TRADE
        if self._ctx.last_close_monotonic > 0:
            elapsed = time.monotonic() - self._ctx.last_close_monotonic
            if elapsed < max(1, self.cfg.scalper_interval_s):
                return ScalperState.COOLDOWN
        return ScalperState.WAITING

    # ── Controle de barra ────────────────────────────────────────────────────

    def on_new_bar(
        self,
        direction: Direction,
        was_force_candle: bool,
        current_bar_timestamp: int,
    ) -> None:
        """
        Chamado quando nova barra é detectada.
        Ativa ou desativa o scalper conforme condições.
        """
        if not self.cfg.use_scalper:
            return

        if was_force_candle and direction in (Direction.BUY, Direction.SELL):
            self._ctx.active = True
            self._ctx.direction = direction
            self._ctx.bar_timestamp = current_bar_timestamp
            self._ctx.has_active_trade = False
            self._ctx.last_close_monotonic = 0.0
            if self.cfg.debug:
                logger.debug(
                    "[Scalper] Ativado para barra %d —Dir=%s",
                    current_bar_timestamp, direction.value
                )
        else:
            self._deactivate("condições não atendidas na nova barra")

    def check_bar_expiry(self, current_bar_timestamp: int) -> None:
        """
        Desativa scalper se a barra atual mudou (expirou a janela).
        Deve ser chamado no início de cada tick.
        """
        if self._ctx.active and current_bar_timestamp != self._ctx.bar_timestamp:
            self._deactivate(f"barra expirou (era {self._ctx.bar_timestamp}, agora {current_bar_timestamp})")

    def _deactivate(self, reason: str = "") -> None:
        if self._ctx.active and self.cfg.debug:
            logger.debug("[Scalper] Desativado — %s", reason)
        self._ctx.active = False
        self._ctx.direction = Direction.NONE
        self._ctx.has_active_trade = False
        self._ctx.last_close_monotonic = 0.0

    # ── Detecção de fechamento ───────────────────────────────────────────────

    def on_position_closed(self) -> None:
        """
        Chamado quando a posição scalper é detectada como fechada.
        Inicia período de cooldown antes da próxima entrada.
        """
        if self._ctx.has_active_trade:
            self._ctx.has_active_trade = False
            self._ctx.last_close_monotonic = time.monotonic()
            if self.cfg.debug:
                logger.debug(
                    "[Scalper] Operação fechada — aguardando %ds antes de nova entrada",
                    self.cfg.scalper_interval_s
                )

    # ── Tick principal ───────────────────────────────────────────────────────

    async def tick(
        self,
        ema_value: Optional[float],
        bid: float,
        ask: float,
        has_open_positions: bool,
        can_trade: bool,
        open_order_fn: OpenOrderCallback,
        volume: Any,
    ) -> None:
        """
        Lógica do scalper executada em cada tick.

        Condições para abrir nova entrada:
        1. Scalper ativo e sem posição aberta pelo EA
        2. Intervalo pós-fechamento cumprido
        3. Preço ainda está a favor da EMA
        4. EA pode operar (sem bloqueios de risco/gestão)
        """
        if not self._ctx.active or not self.cfg.use_scalper:
            return

        # Detectar fechamento da operação scalper
        if self._ctx.has_active_trade and not has_open_positions:
            self.on_position_closed()

        # Verificar se pode tentar nova entrada
        if not can_trade:
            return
        if has_open_positions:
            return
        if self._ctx.has_active_trade:
            return

        # Verificar cooldown
        if self._ctx.last_close_monotonic > 0:
            elapsed = time.monotonic() - self._ctx.last_close_monotonic
            if elapsed < max(1, self.cfg.scalper_interval_s):
                return

        # Verificar preço vs EMA (filtro essencial do scalper)
        if ema_value is None:
            return

        direction = self._ctx.direction
        price_ok = False
        if direction == Direction.BUY and bid > ema_value:
            price_ok = True
        elif direction == Direction.SELL and ask < ema_value:
            price_ok = True

        if not price_ok:
            if self.cfg.debug:
                logger.debug(
                    "[Scalper] SKIP — preço não está a favor da EMA (dir=%s bid=%.5f ask=%.5f ema=%.5f)",
                    direction.value, bid, ask, ema_value
                )
            return

        # Abrir posição
        if self.cfg.debug:
            logger.debug(
                "[Scalper] Abrindo %s — vol=%s",
                direction.value, volume
            )

        order_id = await open_order_fn(direction.value, self.cfg.symbol, volume)
        if order_id:
            self._ctx.has_active_trade = True
            self._ctx.last_close_monotonic = 0.0
