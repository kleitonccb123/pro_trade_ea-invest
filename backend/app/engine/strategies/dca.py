"""
DCA (Dollar-Cost Averaging) Strategy.

Buys at fixed time intervals regardless of price.
Sells when profit target or stop-loss is reached.

Config keys:
  dca_interval_hours  — hours between buys (default: 24)
  dca_profit_target   — profit % to trigger sell (default: 5.0)
  dca_stop_loss       — loss % to trigger sell (default: 15.0)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.engine.strategies.base import Candle, StrategyBase, TradingSignal

logger = logging.getLogger("engine.strategies.dca")

MINIMUM_CANDLES = 1


class DCAStrategy(StrategyBase):
    """Time-based DCA with profit-target/stop-loss exit."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.interval_hours: float = float(config.get("dca_interval_hours", 24))
        self.profit_target_pct: float = float(config.get("dca_profit_target", 5.0))
        self.stop_loss_pct: float = float(config.get("dca_stop_loss", 15.0))

        # Internal state
        self._last_buy_time: Optional[datetime] = None
        self._avg_entry_price: Optional[float] = None

    async def calculate(
        self, candles: List[Candle], current_price: float
    ) -> TradingSignal:
        now = datetime.now(timezone.utc)
        metadata = {
            "interval_hours": self.interval_hours,
            "avg_entry": self._avg_entry_price,
        }

        # ── Exit conditions (if we have an average entry price) ─────────────
        if self._avg_entry_price and self._avg_entry_price > 0:
            pnl_pct = (current_price - self._avg_entry_price) / self._avg_entry_price * 100
            metadata["pnl_pct"] = round(pnl_pct, 3)

            if pnl_pct >= self.profit_target_pct:
                self._avg_entry_price = None
                self._last_buy_time = None
                return TradingSignal(
                    action="sell",
                    reason=f"dca_alvo_lucro_{pnl_pct:.2f}pct",
                    confidence=1.0,
                    metadata=metadata,
                )

            if pnl_pct <= -self.stop_loss_pct:
                self._avg_entry_price = None
                self._last_buy_time = None
                return TradingSignal(
                    action="sell",
                    reason=f"dca_stop_loss_{pnl_pct:.2f}pct",
                    confidence=1.0,
                    metadata=metadata,
                )

        # ── Entry condition: time elapsed ────────────────────────────────────
        interval_delta = timedelta(hours=self.interval_hours)
        if self._last_buy_time is None or (now - self._last_buy_time) >= interval_delta:
            self._last_buy_time = now
            # Update running average entry price
            if self._avg_entry_price is None:
                self._avg_entry_price = current_price
            else:
                # Simple average of two entries (simplified 2-order DCA)
                self._avg_entry_price = (self._avg_entry_price + current_price) / 2
            metadata["avg_entry"] = round(self._avg_entry_price, 4)
            return TradingSignal(
                action="buy",
                reason=f"dca_aporte_periodico",
                confidence=0.8,
                metadata=metadata,
            )

        next_buy = self._last_buy_time + interval_delta
        wait_h = round((next_buy - now).total_seconds() / 3600, 1)
        return self._hold(f"dca_aguardando_{wait_h}h")
