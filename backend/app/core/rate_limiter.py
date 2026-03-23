"""
Rate Limiter - In-Memory Token Bucket Implementation
Prevents brute force attacks without external dependencies
"""

import time
import logging
from typing import Dict, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter using token bucket algorithm.
    
    Features:
    - Time-based bucketing (no external dependencies)
    - Per-IP address limiting
    - Configurable request limits and time windows
    """

    def __init__(self):
        # Format: {ip_address: (tokens, last_reset_time)}
        self._buckets: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, time.time()))

    def is_allowed(
        self,
        identifier: str,
        max_requests: int = 5,
        window_seconds: int = 900  # 15 minutes default
    ) -> Tuple[bool, Dict]:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (usually IP address)
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds

        Returns:
            (allowed: bool, info: dict with remaining_requests, reset_time)
        """
        current_time = time.time()
        tokens, last_reset = self._buckets[identifier]

        # Check if window has expired
        time_since_reset = current_time - last_reset
        if time_since_reset >= window_seconds:
            # Reset bucket
            tokens = 0
            last_reset = current_time
            self._buckets[identifier] = (tokens, last_reset)

        # Calculate remaining tokens
        allowed = tokens < max_requests

        if allowed:
            # Consume one token
            tokens += 1
            self._buckets[identifier] = (tokens, last_reset)

        # Calculate reset time
        time_until_reset = max(0, window_seconds - time_since_reset)

        info = {
            "allowed": allowed,
            "remaining_requests": max(0, max_requests - tokens),
            "reset_in_seconds": int(time_until_reset),
            "limit": max_requests,
        }

        return allowed, info

    def cleanup_expired(self, max_age_seconds: int = 86400):
        """
        Remove expired entries (older than max_age_seconds).
        Call this periodically to prevent memory leaks.
        """
        current_time = time.time()
        expired = [
            key for key, (_, last_reset) in self._buckets.items()
            if current_time - last_reset > max_age_seconds
        ]
        for key in expired:
            del self._buckets[key]
        if expired:
            logger.debug(f"[♻️] Cleaned up {len(expired)} expired rate limit entries")


# Global rate limiter instance
_rate_limiter = RateLimiter()


def check_rate_limit(
    identifier: str,
    max_requests: int = 5,
    window_seconds: int = 900
) -> Tuple[bool, Dict]:
    """
    Check if request is allowed.

    Usage in route:
        allowed, info = check_rate_limit(
            identifier=request.client.host,
            max_requests=5,
            window_seconds=900
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {info['reset_in_seconds']} seconds"
            )
    """
    return _rate_limiter.is_allowed(identifier, max_requests, window_seconds)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


async def check_rate_limit_async(
    identifier: str,
    max_requests: int = 5,
    window_seconds: int = 900,
) -> Tuple[bool, Dict]:
    """
    Async rate limiter that uses Redis when available, falling back to in-memory.

    Redis strategy: INCR + EXPIRE (atomic counter per sliding window).
    """
    try:
        from app.core.config import settings as _cfg
        if _cfg.redis_url:
            import redis.asyncio as _aioredis
            _r = _aioredis.from_url(_cfg.redis_url, decode_responses=True)
            key = f"rate_limit:{identifier}"
            current = await _r.incr(key)
            if current == 1:
                await _r.expire(key, window_seconds)
            ttl = await _r.ttl(key)
            await _r.aclose()
            allowed = current <= max_requests
            return allowed, {
                "allowed": allowed,
                "remaining_requests": max(0, max_requests - current),
                "reset_in_seconds": max(0, ttl),
                "limit": max_requests,
            }
    except Exception:
        pass  # Fall through to in-memory
    return check_rate_limit(identifier, max_requests, window_seconds)


async def start_cleanup_scheduler() -> None:
    """
    Background task that periodically removes expired in-memory rate limit entries.
    Call once at startup via asyncio.create_task(start_cleanup_scheduler()).
    """
    import asyncio
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            _rate_limiter.cleanup_expired()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("[rate_limiter] Cleanup error: %s", exc)
