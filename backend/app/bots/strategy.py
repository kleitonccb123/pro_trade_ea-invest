from __future__ import annotations

from typing import List, Dict, Any
import logging

from app.bots.strategy_base import Strategy, Signal

logger = logging.getLogger(__name__)


class StrategyRSIEMA(Strategy):
    """RSI + EMA strategy that implements the `Strategy` interface.

    It expects candles as list of dicts with `close` values and returns Signal.BUY/SELL/HOLD.
    """

    def __init__(self, rsi_period: int = 14, ema_period: int = 21):
        self.rsi_period = rsi_period
        self.ema_period = ema_period

    def _closes(self, candles: List[Dict[str, Any]]) -> List[float]:
        return [c["close"] for c in candles]

    def _ema(self, prices: List[float], period: int) -> List[float]:
        if not prices or period <= 0:
            return []
        emas = []
        k = 2 / (period + 1)
        ema_prev = prices[0]
        for p in prices:
            ema_prev = (p - ema_prev) * k + ema_prev
            emas.append(ema_prev)
        return emas

    def _rsi(self, prices: List[float], period: int) -> List[float]:
        if len(prices) < period + 1:
            return []
        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        rsis = []
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        rs = avg_gain / (avg_loss if avg_loss != 0 else 1e-8)
        rsis.append(100 - (100 / (1 + rs)))
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            rs = avg_gain / (avg_loss if avg_loss != 0 else 1e-8)
            rsis.append(100 - (100 / (1 + rs)))
        return rsis

    def on_candles(self, candles: List[Dict[str, Any]]) -> Signal:
        closes = self._closes(candles)
        if len(closes) < max(self.rsi_period + 1, self.ema_period + 1):
            return Signal.HOLD
        emas = self._ema(closes, self.ema_period)
        rsis = self._rsi(closes, self.rsi_period)
        if not emas or not rsis:
            return Signal.HOLD

        last_price = closes[-1]
        last_ema = emas[-1]
        last_rsi = rsis[-1]

        logger.debug("RSI=%s EMA=%s PRICE=%s", last_rsi, last_ema, last_price)

        if last_price > last_ema and last_rsi < 35:
            return Signal.BUY
        if last_price < last_ema and last_rsi > 65:
            return Signal.SELL
        return Signal.HOLD
