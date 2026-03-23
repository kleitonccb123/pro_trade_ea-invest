"""
Scalping Strategy — Bollinger Bands + RSI for quick entries/exits.

Typical hold time: 1-15 minutes.
Uses tight profit targets and stop-losses for small, frequent wins.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np
import pandas as pd
import ta

from app.engine.strategies.base import Candle, StrategyBase, TradingSignal

logger = logging.getLogger("engine.strategies.scalping")

MINIMUM_CANDLES = 25


class ScalpingStrategy(StrategyBase):
    """Scalping: small profits on small price changes using BB + RSI."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bb_period: int = int(config.get("bb_period", 20))
        self.bb_std: float = float(config.get("bb_std", 2.0))
        self.rsi_period: int = int(config.get("rsi_period", 7))
        self.rsi_oversold: float = float(config.get("rsi_oversold", 30.0))
        self.rsi_overbought: float = float(config.get("rsi_overbought", 70.0))
        self.profit_target_pct: float = float(config.get("profit_target_pct", 0.3))
        self.stop_loss_pct: float = float(config.get("stop_loss_pct", 0.15))
        self.volume_filter: bool = bool(config.get("volume_filter", True))

    async def calculate(
        self, candles: List[Candle], current_price: float
    ) -> TradingSignal:
        if not self._enough_data(candles, MINIMUM_CANDLES):
            return self._hold("dados_insuficientes")

        closes = pd.Series(self._closes(candles))

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            close=closes, window=self.bb_period, window_dev=self.bb_std
        )
        upper_band = float(bb.bollinger_hband().iloc[-1])
        lower_band = float(bb.bollinger_lband().iloc[-1])
        mid_band = float(bb.bollinger_mavg().iloc[-1])

        # RSI (fast, 7 periods)
        rsi_indicator = ta.momentum.RSIIndicator(close=closes, window=self.rsi_period)
        rsi_series = rsi_indicator.rsi()
        if rsi_series.empty:
            return self._hold("rsi_vazio")
        rsi = float(rsi_series.iloc[-1])

        metadata = {
            "rsi": round(rsi, 2),
            "upper_band": round(upper_band, 4),
            "lower_band": round(lower_band, 4),
            "mid_band": round(mid_band, 4),
            "current_price": current_price,
            "pair": self.pair,
            "profit_target_pct": self.profit_target_pct,
            "stop_loss_pct": self.stop_loss_pct,
        }

        # Optional volume filter — current volume above 20-period average
        if self.volume_filter:
            vols = pd.Series(self._volumes(candles))
            avg_vol = float(vols.tail(20).mean())
            current_vol = float(vols.iloc[-1])
            metadata["volume_ratio"] = round(current_vol / avg_vol, 3) if avg_vol else 0
            if avg_vol > 0 and current_vol < avg_vol * 0.7:
                logger.debug(
                    f"Scalping RSI={rsi:.1f} — volume too low ({current_vol:.0f} < {avg_vol * 0.7:.0f})"
                )
                return self._hold("volume_baixo")

        # BUY signal: price at or below lower Bollinger Band + RSI oversold
        if current_price <= lower_band and rsi < self.rsi_oversold:
            confidence = min(
                ((self.rsi_oversold - rsi) / self.rsi_oversold) * 0.5
                + ((lower_band - current_price) / lower_band) * 0.5,
                1.0,
            )
            metadata["target"] = round(mid_band, 4)
            metadata["reason"] = "price_at_lower_bb_oversold"
            return TradingSignal(
                action="buy",
                reason=f"scalp_buy_rsi_{rsi:.1f}_bb_lower",
                confidence=round(max(confidence, 0.55), 3),
                metadata=metadata,
            )

        # SELL signal: price at or above upper Bollinger Band + RSI overbought
        if current_price >= upper_band and rsi > self.rsi_overbought:
            confidence = min(
                ((rsi - self.rsi_overbought) / (100 - self.rsi_overbought)) * 0.5
                + ((current_price - upper_band) / upper_band) * 0.5,
                1.0,
            )
            metadata["reason"] = "price_at_upper_bb_overbought"
            return TradingSignal(
                action="sell",
                reason=f"scalp_sell_rsi_{rsi:.1f}_bb_upper",
                confidence=round(max(confidence, 0.55), 3),
                metadata=metadata,
            )

        return self._hold(f"scalp_neutro_rsi_{rsi:.1f}")
