"""
RSI Strategy — signal based on Relative Strength Index.

Default:  Buy when RSI < oversold (30), Sell when RSI > overbought (70).
Optional: Volume confirmation filter.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np
import pandas as pd
import ta

from app.engine.strategies.base import Candle, StrategyBase, TradingSignal

logger = logging.getLogger("engine.strategies.rsi")

MINIMUM_CANDLES = 30


class RSIStrategy(StrategyBase):
    """RSI mean-reversion strategy."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.rsi_period: int = int(config.get("rsi_period", 14))
        self.oversold: float = float(config.get("rsi_oversold", 30.0))
        self.overbought: float = float(config.get("rsi_overbought", 70.0))
        self.volume_filter: bool = bool(config.get("volume_filter", False))

    async def calculate(
        self, candles: List[Candle], current_price: float
    ) -> TradingSignal:
        if not self._enough_data(candles, MINIMUM_CANDLES):
            return self._hold("dados_insuficientes")

        closes = pd.Series(self._closes(candles))
        rsi_series = ta.momentum.RSIIndicator(close=closes, window=self.rsi_period).rsi()

        if rsi_series.empty:
            return self._hold("rsi_vazio")

        rsi = float(rsi_series.iloc[-1])
        metadata = {"rsi": round(rsi, 2), "pair": self.pair}

        # Optional volume filter — current volume above 20-period average
        if self.volume_filter:
            vols = pd.Series(self._volumes(candles))
            avg_vol = float(vols.tail(20).mean())
            current_vol = float(vols.iloc[-1])
            metadata["volume_ratio"] = round(current_vol / avg_vol, 3) if avg_vol else 0
            if current_vol < avg_vol * 0.8:
                logger.debug(f"RSI={rsi:.1f} — volume insuficiente, ignorando sinal")
                return self._hold("volume_baixo")

        if rsi < self.oversold:
            return TradingSignal(
                action="buy",
                reason=f"rsi_sobrevendido_{rsi:.1f}",
                confidence=round((self.oversold - rsi) / self.oversold, 3),
                metadata=metadata,
            )

        if rsi > self.overbought:
            return TradingSignal(
                action="sell",
                reason=f"rsi_sobrecomprado_{rsi:.1f}",
                confidence=round((rsi - self.overbought) / (100 - self.overbought), 3),
                metadata=metadata,
            )

        return self._hold(f"rsi_neutro_{rsi:.1f}")
