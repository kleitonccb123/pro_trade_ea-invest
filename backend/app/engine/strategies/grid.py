"""
Grid Trading Strategy — divide price range into N levels, buy low / sell high.

Each level is a price band. When price drops into a buy-band and no open
position exists, generate a buy signal. When price rises into a sell-band
and a position is open, generate a sell signal.

Config keys:
  grid_upper       — upper bound of grid (required)
  grid_lower       — lower bound of grid (required)
  grid_levels      — number of grid levels (default: 10)
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.engine.strategies.base import Candle, StrategyBase, TradingSignal

logger = logging.getLogger("engine.strategies.grid")

MINIMUM_CANDLES = 1  # Grid only needs current price


class GridStrategy(StrategyBase):
    """
    Stateful grid strategy.  The worker can only track ONE open position at a
    time (the caller — BotWorker — handles position state).
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.upper: float = float(config.get("grid_upper", 0))
        self.lower: float = float(config.get("grid_lower", 0))
        self.levels: int = max(2, int(config.get("grid_levels", 10)))
        self._levels_list: List[float] = self._build_levels()

        # Internal state
        self._last_zone: Optional[int] = None  # index of zone where we bought

        logger.debug(
            f"GridStrategy — range=[{self.lower}, {self.upper}] "
            f"levels={self.levels} step≈{self._step():.4f}"
        )

    def _build_levels(self) -> List[float]:
        if self.upper <= self.lower or self.levels < 2:
            return []
        step = (self.upper - self.lower) / self.levels
        return [self.lower + i * step for i in range(self.levels + 1)]

    def _step(self) -> float:
        if len(self._levels_list) < 2:
            return 0
        return self._levels_list[1] - self._levels_list[0]

    def _price_zone(self, price: float) -> Optional[int]:
        """Return the grid zone index (0 = lowest) for the given price."""
        for i in range(len(self._levels_list) - 1):
            if self._levels_list[i] <= price < self._levels_list[i + 1]:
                return i
        return None

    async def calculate(
        self, candles: List[Candle], current_price: float
    ) -> TradingSignal:
        if not self._levels_list or self.upper <= self.lower:
            return self._hold("grid_nao_configurado")

        if current_price < self.lower or current_price > self.upper:
            return self._hold("preco_fora_do_grid")

        zone = self._price_zone(current_price)
        if zone is None:
            return self._hold("zona_invalida")

        metadata = {
            "grid_zone": zone,
            "grid_total": self.levels,
            "level_low": round(self._levels_list[zone], 6),
            "level_high": round(self._levels_list[zone + 1], 6),
        }

        # Buy at lower zones (below midpoint) — entry
        mid_zone = self.levels // 2
        if zone < mid_zone and self._last_zone is None:
            self._last_zone = zone
            return TradingSignal(
                action="buy",
                reason=f"grid_zona_{zone}_compra",
                confidence=round(1.0 - zone / self.levels, 3),
                metadata=metadata,
            )

        # Sell at higher zones — exit
        if zone > mid_zone and self._last_zone is not None and zone > self._last_zone:
            self._last_zone = None
            return TradingSignal(
                action="sell",
                reason=f"grid_zona_{zone}_venda",
                confidence=round(zone / self.levels, 3),
                metadata=metadata,
            )

        return self._hold(f"grid_aguardando_zona_{zone}")
