"""
KuCoin sliding-window rate limiter — DOC_04 §3.

Each endpoint category has its own token bucket.
acquire() must be awaited before every REST request.

Official KuCoin limits (spot, as of 2025):
  market data  → 30 req / 10 s
  order place  → 45 req / 10 s
  order cancel → 60 req / 10 s
  account      → 20 req / 10 s
  other        → 20 req / 10 s
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("kucoin.ratelimit")


@dataclass
class RateLimitBucket:
    """
    Sliding-window rate-limit bucket.

    Thread-safe via asyncio.Lock — suitable for use within a single event loop.
    """

    max_requests: int
    window_seconds: int
    timestamps: deque = field(default_factory=deque)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> None:
        """
        Wait until a request slot is available and claim it.

        Implements a sliding window: only timestamps within the last
        `window_seconds` are counted.
        """
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds

            # Drop expired timestamps
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()

            if len(self.timestamps) >= self.max_requests:
                # Oldest timestamp + window = when the next slot opens
                wait_until = self.timestamps[0] + self.window_seconds
                wait_time = wait_until - time.monotonic()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Re-clean after sleeping
                    cutoff = time.monotonic() - self.window_seconds
                    while self.timestamps and self.timestamps[0] < cutoff:
                        self.timestamps.popleft()

            self.timestamps.append(time.monotonic())


# ── Gateway rate-limit state (DOC-K02) ───────────────────────────────────────

@dataclass
class GatewayRateLimitState:
    """
    Estado real do rate limit conforme informado pelos headers da KuCoin.

    Headers esperados em cada resposta:
      gw-ratelimit-limit:     total de pontos disponíveis na janela
      gw-ratelimit-remaining: pontos restantes NESTE momento
      gw-ratelimit-reset:     timestamp Unix (ms) quando os pontos resetam
    """
    limit: int = 2000
    remaining: int = 2000
    reset_at_ms: int = 0          # timestamp ms quando reseta
    last_updated: float = 0.0     # monotonic time da última atualização
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def update_from_headers(self, headers: dict) -> None:
        """Atualiza estado com headers da resposta."""
        raw_limit     = headers.get("gw-ratelimit-limit")
        raw_remaining = headers.get("gw-ratelimit-remaining")
        raw_reset     = headers.get("gw-ratelimit-reset")

        if raw_limit is not None:
            try:
                self.limit = int(raw_limit)
            except (ValueError, TypeError):
                pass

        if raw_remaining is not None:
            try:
                self.remaining = int(raw_remaining)
            except (ValueError, TypeError):
                pass

        if raw_reset is not None:
            try:
                self.reset_at_ms = int(raw_reset)
            except (ValueError, TypeError):
                pass

        self.last_updated = time.monotonic()

        if self.remaining < 100:
            logger.warning(
                "⚠️  gw-ratelimit-remaining=%d (limit=%d). "
                "Aplicando throttle preventivo.",
                self.remaining, self.limit,
            )

    def seconds_until_reset(self) -> float:
        """Segundos até o próximo reset do gateway."""
        if not self.reset_at_ms:
            return 0.0
        reset_ts = self.reset_at_ms / 1000.0
        return max(0.0, reset_ts - time.time())

    def usage_pct(self) -> float:
        """Percentual de uso (0.0 a 1.0)."""
        if self.limit == 0:
            return 1.0
        return 1.0 - (self.remaining / self.limit)


# ── Per-category buckets (module-level singletons) ────────────────────────────

KUCOIN_RATE_LIMITS: Dict[str, RateLimitBucket] = {
    "market_data": RateLimitBucket(max_requests=30, window_seconds=10),
    "order_place":  RateLimitBucket(max_requests=45, window_seconds=10),
    "order_cancel": RateLimitBucket(max_requests=60, window_seconds=10),
    "account":      RateLimitBucket(max_requests=20, window_seconds=10),
    "order_list":   RateLimitBucket(max_requests=30, window_seconds=10),
    "default":      RateLimitBucket(max_requests=20, window_seconds=10),
}

# Prefix → category mapping (longest prefix wins)
ENDPOINT_CATEGORY_MAP: Dict[str, str] = {
    "/api/v1/market/candles":              "market_data",
    "/api/v1/market/orderbook":            "market_data",
    "/api/v1/market/stats":                "market_data",
    "/api/v1/market/":                     "market_data",
    "/api/v1/orders/cancel":               "order_cancel",
    "/api/v1/orders":                      "order_place",
    "/api/v1/hf/orders":                   "order_place",
    "/api/v1/accounts":                    "account",
    "/api/v2/accounts":                    "account",
}


class KuCoinRateLimiter:
    """Static interface for per-endpoint rate limiting."""

    @staticmethod
    async def acquire(endpoint: str) -> None:
        """
        Acquire a slot for the given endpoint path.
        Blocks if the category bucket is exhausted.
        """
        # Sort by length descending to match most-specific prefix first
        category = "default"
        for prefix in sorted(ENDPOINT_CATEGORY_MAP, key=len, reverse=True):
            if endpoint.startswith(prefix):
                category = ENDPOINT_CATEGORY_MAP[prefix]
                break
        await KUCOIN_RATE_LIMITS[category].acquire()
