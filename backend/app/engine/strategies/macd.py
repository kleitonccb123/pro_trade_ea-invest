"""
MACD Strategy — signal from MACD line crossing Signal line.

Buy  when MACD crosses above Signal (bullish crossover).
Sell when MACD crosses below Signal (bearish crossover).
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd
import ta

from app.engine.strategies.base import Candle, StrategyBase, TradingSignal

logger = logging.getLogger("engine.strategies.macd")

MINIMUM_CANDLES = 60


class MACDStrategy(StrategyBase):
    """MACD crossover strategy."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.fast: int = int(config.get("macd_fast", 12))
        self.slow: int = int(config.get("macd_slow", 26))
        self.signal: int = int(config.get("macd_signal", 9))

    async def calculate(
        self, candles: List[Candle], current_price: float
    ) -> TradingSignal:
        if not self._enough_data(candles, MINIMUM_CANDLES):
            return self._hold("dados_insuficientes")

        closes = pd.Series(self._closes(candles))
        macd_indicator = ta.trend.MACD(
            close=closes,
            window_fast=self.fast,
            window_slow=self.slow,
            window_sign=self.signal,
        )

        macd_line = macd_indicator.macd()
        signal_line = macd_indicator.macd_signal()

        if len(macd_line) < 2 or len(signal_line) < 2:
            return self._hold("macd_vazio")

        macd_now = float(macd_line.iloc[-1])
        macd_prev = float(macd_line.iloc[-2])
        signal_now = float(signal_line.iloc[-1])
        signal_prev = float(signal_line.iloc[-2])

        histogram = macd_now - signal_now
        metadata = {
            "macd": round(macd_now, 6),
            "signal": round(signal_now, 6),
            "histogram": round(histogram, 6),
        }

        # Bullish crossover: MACD was below signal, now above
        bullish = macd_prev < signal_prev and macd_now > signal_now
        # Bearish crossover: MACD was above signal, now below
        bearish = macd_prev > signal_prev and macd_now < signal_now

        if bullish:
            return TradingSignal(
                action="buy",
                reason="macd_cruzamento_alta",
                confidence=min(abs(histogram) * 10, 1.0),
                metadata=metadata,
            )

        if bearish:
            return TradingSignal(
                action="sell",
                reason="macd_cruzamento_baixa",
                confidence=min(abs(histogram) * 10, 1.0),
                metadata=metadata,
            )

        return self._hold(f"macd_sem_cruzamento")
