"""
Combined Strategy — requires RSI AND MACD confirmation before signalling.

Buy  only when:  RSI < oversold  AND  MACD bullish crossover
Sell only when:  RSI > overbought  AND  MACD bearish crossover

This double-confirmation approach reduces false positives.
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd
import ta

from app.engine.strategies.base import Candle, StrategyBase, TradingSignal

logger = logging.getLogger("engine.strategies.combined")

MINIMUM_CANDLES = 60


class CombinedStrategy(StrategyBase):
    """RSI + MACD confirmation strategy."""

    def __init__(self, config: dict):
        super().__init__(config)
        # RSI params
        self.rsi_period: int = int(config.get("rsi_period", 14))
        self.oversold: float = float(config.get("rsi_oversold", 35.0))
        self.overbought: float = float(config.get("rsi_overbought", 65.0))
        # MACD params
        self.fast: int = int(config.get("macd_fast", 12))
        self.slow: int = int(config.get("macd_slow", 26))
        self.signal: int = int(config.get("macd_signal", 9))

    async def calculate(
        self, candles: List[Candle], current_price: float
    ) -> TradingSignal:
        if not self._enough_data(candles, MINIMUM_CANDLES):
            return self._hold("dados_insuficientes")

        closes = pd.Series(self._closes(candles))

        # ── RSI ───────────────────────────────────────────────────────────
        rsi_series = ta.momentum.RSIIndicator(close=closes, window=self.rsi_period).rsi()
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

        # ── MACD ──────────────────────────────────────────────────────────
        macd_ind = ta.trend.MACD(
            close=closes,
            window_fast=self.fast,
            window_slow=self.slow,
            window_sign=self.signal,
        )
        macd_line = macd_ind.macd()
        signal_line = macd_ind.macd_signal()

        if len(macd_line) < 2:
            return self._hold("macd_insuficiente")

        macd_now = float(macd_line.iloc[-1])
        macd_prev = float(macd_line.iloc[-2])
        sig_now = float(signal_line.iloc[-1])
        sig_prev = float(signal_line.iloc[-2])

        macd_bullish = macd_prev < sig_prev and macd_now > sig_now
        macd_bearish = macd_prev > sig_prev and macd_now < sig_now

        metadata = {
            "rsi": round(rsi, 2),
            "macd": round(macd_now, 6),
            "macd_signal": round(sig_now, 6),
            "histogram": round(macd_now - sig_now, 6),
        }

        # ── Double confirmation ───────────────────────────────────────────
        if rsi < self.oversold and macd_bullish:
            return TradingSignal(
                action="buy",
                reason=f"combined_compra_rsi{rsi:.1f}_macd_alta",
                confidence=round(
                    (self.oversold - rsi) / self.oversold * 0.5 + 0.5, 3
                ),
                metadata=metadata,
            )

        if rsi > self.overbought and macd_bearish:
            return TradingSignal(
                action="sell",
                reason=f"combined_venda_rsi{rsi:.1f}_macd_baixa",
                confidence=round(
                    (rsi - self.overbought) / (100 - self.overbought) * 0.5 + 0.5, 3
                ),
                metadata=metadata,
            )

        reasons = []
        if rsi < self.oversold:
            reasons.append(f"rsi_ok({rsi:.0f})")
        if macd_bullish:
            reasons.append("macd_bullish")
        return self._hold("aguardando_confirmacao" + (":"+",".join(reasons) if reasons else ""))
