from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any


class MarketMode:
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"


def generate_candles(count: int = 200, start_price: float = 100.0, mode: str = MarketMode.SIDEWAYS) -> List[Dict[str, Any]]:
    """Generate a list of synthetic candles.

    Each candle: {open, high, low, close, volume, timestamp}
    Mode affects drift.
    """
    candles: List[Dict[str, Any]] = []
    price = start_price
    ts = datetime.utcnow() - timedelta(minutes=count)
    for _ in range(count):
        drift = 0.0
        if mode == MarketMode.BULL:
            drift = random.uniform(0.0, 0.5)
        elif mode == MarketMode.BEAR:
            drift = random.uniform(-0.5, 0.0)
        else:
            drift = random.uniform(-0.2, 0.2)

        change = drift + random.uniform(-0.8, 0.8)
        open_p = price
        close_p = max(0.01, price + change)
        high_p = max(open_p, close_p) + random.uniform(0, 0.5)
        low_p = min(open_p, close_p) - random.uniform(0, 0.5)
        volume = random.uniform(1, 100)
        candles.append({
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume,
            "timestamp": ts,
        })
        price = close_p
        ts = ts + timedelta(minutes=1)
    return candles
