"""
PositionTracker — Breakeven + Trailing por Candle

Equivale a ManagePositionStops() do MT5:
    1. Quando posição avança X pontos → mover SL para preço de entrada (breakeven)
    2. Após breakeven → trailing stop no mínimo/máximo do candle anterior

Estado por ticket persistido em memória (dict).
O EA runner chama update() em cada tick.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Coroutine, Dict, Optional, Set

from .config import EAConfig
from .indicators import Candle

logger = logging.getLogger(__name__)

# Tipo de callback para modificar SL/TP de uma ordem/posição
ModifyCallback = Callable[
    [str, Optional[float], Optional[float]],  # (order_id_or_symbol, sl, tp)
    Coroutine[Any, Any, bool]
]


@dataclass
class TrackedPosition:
    """Estado de breakeven/trailing para uma posição."""
    order_id: str
    side: str                     # "buy" | "sell"
    open_price: float
    sl: float
    tp: float
    breakeven_activated: bool = False
    last_trailing_bar_time: int = 0  # timestamp do último candle que moveu o SL


class PositionTracker:
    """
    Rastreia estado de breakeven/trailing para todas as posições abertas do EA.

    Uso:
        tracker.register(order_id, side, open_price, sl, tp)
        await tracker.update(positions_snapshot, last_closed_candle, bid, ask, modify_fn)
        tracker.remove(order_id)
    """

    def __init__(self, config: EAConfig):
        self.cfg = config
        self._positions: Dict[str, TrackedPosition] = {}

    # ── Registro ─────────────────────────────────────────────────────────────

    def register(
        self,
        order_id: str,
        side: str,
        open_price: float,
        sl: float = 0.0,
        tp: float = 0.0,
    ) -> None:
        """Registra nova posição para rastreamento."""
        if order_id not in self._positions:
            self._positions[order_id] = TrackedPosition(
                order_id=order_id,
                side=side,
                open_price=open_price,
                sl=sl,
                tp=tp,
            )
            if self.cfg.debug:
                logger.debug("[PositionTracker] Registrado: %s %s @ %.5f", order_id, side, open_price)

    def remove(self, order_id: str) -> None:
        """Remove posição do rastreamento (fechada)."""
        if order_id in self._positions:
            del self._positions[order_id]
            if self.cfg.debug:
                logger.debug("[PositionTracker] Removido: %s", order_id)

    def remove_closed(self, active_order_ids: Set[str]) -> None:
        """Remove posições que não estão mais na lista de ativas."""
        to_remove = [oid for oid in self._positions if oid not in active_order_ids]
        for oid in to_remove:
            self.remove(oid)

    def update_sl(self, order_id: str, sl: float) -> None:
        """Atualiza SL conhecido localmente após modificação."""
        pos = self._positions.get(order_id)
        if pos:
            pos.sl = sl

    def update_tp(self, order_id: str, tp: float) -> None:
        pos = self._positions.get(order_id)
        if pos:
            pos.tp = tp

    # ── Cálculo de breakeven ──────────────────────────────────────────────────

    def _breakeven_triggered(
        self, pos: TrackedPosition, bid: float, ask: float
    ) -> bool:
        """
        Retorna True se a posição avançou o suficiente para ativar breakeven.
        Equivale ao cálculo diffPoints >= BreakevenActivatePoints do MT5.
        """
        tick = float(self.cfg.price_tick)
        if tick <= 0:
            return False

        bp = self.cfg.breakeven_activate_points

        if pos.side == "buy":
            diff_points = (bid - pos.open_price) / tick
        else:
            diff_points = (pos.open_price - ask) / tick

        return diff_points >= bp

    def _should_move_sl(
        self, pos: TrackedPosition, new_sl: float
    ) -> bool:
        """
        Verifica se o novo SL representa um avanço mínimo (MinMovePoints).
        Para BUY: novo SL > SL atual + mínimo.
        Para SELL: novo SL < SL atual - mínimo.
        """
        tick = float(self.cfg.price_tick)
        min_move = self.cfg.min_move_points * tick

        if pos.sl <= 0:
            return True  # sem SL atual, qualquer valor é válido

        if pos.side == "buy":
            return new_sl > pos.sl + min_move
        else:
            return new_sl < pos.sl - min_move

    # ── Update principal ──────────────────────────────────────────────────────

    async def update(
        self,
        bid: float,
        ask: float,
        last_closed_candle: Optional[Candle],
        current_bar_time: int,
        modify_fn: ModifyCallback,
    ) -> None:
        """
        Verifica cada posição registrada e aplica breakeven/trailing.

        Deve ser chamado em cada tick ou a cada nova barra.
        `modify_fn(order_id, new_sl, new_tp)` → modifica a ordem na exchange.
        """
        if not self._positions:
            return

        for order_id, pos in list(self._positions.items()):
            try:
                await self._process_position(
                    pos, bid, ask, last_closed_candle, current_bar_time, modify_fn
                )
            except Exception as exc:
                logger.warning("[PositionTracker] Erro ao processar %s: %s", order_id, exc)

    async def _process_position(
        self,
        pos: TrackedPosition,
        bid: float,
        ask: float,
        last_closed_candle: Optional[Candle],
        current_bar_time: int,
        modify_fn: ModifyCallback,
    ) -> None:
        tick = float(self.cfg.price_tick)

        # 1) Ativar breakeven
        if not pos.breakeven_activated:
            if self._breakeven_triggered(pos, bid, ask):
                # SL = preço de entrada (breakeven exato)
                new_sl = round(pos.open_price, 8)
                if self._should_move_sl(pos, new_sl):
                    ok = await modify_fn(pos.order_id, new_sl, pos.tp if pos.tp > 0 else None)
                    if ok:
                        pos.sl = new_sl
                        pos.breakeven_activated = True
                        pos.last_trailing_bar_time = current_bar_time
                        if self.cfg.debug:
                            logger.debug(
                                "[PositionTracker] Breakeven ativado %s — SL=%.8f",
                                pos.order_id, new_sl
                            )
            return

        # 2) Trailing por candle (após breakeven)
        if not self.cfg.use_trailing_candle:
            return

        if last_closed_candle is None:
            return

        # Evitar múltiplas modificações no mesmo candle
        if pos.last_trailing_bar_time == last_closed_candle.timestamp:
            return

        # Novo SL = min/max do candle anterior
        if pos.side == "buy":
            new_sl = last_closed_candle.low
        else:
            new_sl = last_closed_candle.high

        new_sl = round(new_sl, 8)

        # SL só pode avançar (nunca retroceder)
        if pos.sl > 0:
            if pos.side == "buy":
                # Para BUY: SL deve estar acima do preço de entrada (para trailing conservador)
                if new_sl <= pos.sl + self.cfg.min_move_points * tick:
                    return  # não avançou o suficiente
            else:
                if new_sl >= pos.sl - self.cfg.min_move_points * tick:
                    return

        # Verificar que o novo SL é favorável em relação ao preço de entrada
        if pos.side == "buy" and new_sl < pos.open_price:
            return  # não mover abaixo do breakeven
        if pos.side == "sell" and new_sl > pos.open_price:
            return

        ok = await modify_fn(pos.order_id, new_sl, pos.tp if pos.tp > 0 else None)
        if ok:
            pos.sl = new_sl
            pos.last_trailing_bar_time = last_closed_candle.timestamp
            if self.cfg.debug:
                logger.debug(
                    "[PositionTracker] Trailing %s — SL=%.8f (candle bar=%d)",
                    pos.order_id, new_sl, last_closed_candle.timestamp
                )
