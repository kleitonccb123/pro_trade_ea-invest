"""
Base Strategy — TradingSignal dataclass + abstract StrategyBase.

All concrete strategies inherit StrategyBase and implement `calculate()`.

Candle format (from KuCoinClient.get_candles):
    [timestamp, open, close, high, low, volume, turnover]  — all floats
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Literal, Optional

logger = logging.getLogger("engine.strategies")

# Each element: [ts, open, close, high, low, volume, turnover]
Candle = List[float]


@dataclass
class TradingSignal:
    action: Literal["buy", "sell", "hold"] = "hold"
    reason: str = ""
    confidence: float = 0.0         # 0.0 – 1.0
    metadata: dict = field(default_factory=dict)


class StrategyBase(ABC):
    """
    Abstract base for all trading strategies.

    Subclasses receive the full bot `config` dict and must implement
    `calculate(candles, current_price)` which returns a TradingSignal.
    """

    def __init__(self, config: dict):
        self.config = config
        self.pair: str = config.get("pair", "BTC-USDT")
        self.timeframe: str = config.get("timeframe", "1h")

    @abstractmethod
    async def calculate(
        self, candles: List[Candle], current_price: float
    ) -> TradingSignal:
        """
        Analyse `candles` and `current_price` and return a trading decision.

        Args:
            candles:       List of OHLCV arrays, oldest first.
            current_price: Latest market price (from WebSocket tick).

        Returns:
            TradingSignal with action="buy"|"sell"|"hold".
        """

    # ── Utility helpers available to all subclasses ──────────────────────────

    def _closes(self, candles: List[Candle]) -> List[float]:
        """Return closing prices as a flat list (index 2 per KuCoin format)."""
        return [c[2] for c in candles]

    def _highs(self, candles: List[Candle]) -> List[float]:
        return [c[3] for c in candles]

    def _lows(self, candles: List[Candle]) -> List[float]:
        return [c[4] for c in candles]

    def _volumes(self, candles: List[Candle]) -> List[float]:
        return [c[5] for c in candles]

    def _enough_data(self, candles: List[Candle], minimum: int) -> bool:
        if len(candles) < minimum:
            logger.debug(
                f"{self.__class__.__name__} — dados insuficientes "
                f"({len(candles)}/{minimum} velas)"
            )
            return False
        return True

    def _hold(self, reason: str = "sem_sinal") -> TradingSignal:
        return TradingSignal(action="hold", reason=reason)
