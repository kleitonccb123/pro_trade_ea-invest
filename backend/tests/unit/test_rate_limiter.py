"""
Unit Tests — Rate Limiter
==========================

Tests in-memory rate limiter and async variant.
"""

import pytest
from unittest.mock import patch

from app.core.rate_limiter import check_rate_limit, check_rate_limit_async


class TestCheckRateLimit:
    def test_first_request_allowed(self):
        allowed, info = check_rate_limit("test-ip-1", max_requests=5, window_seconds=60)
        assert allowed is True

    def test_within_limit(self):
        for _ in range(4):
            check_rate_limit("test-ip-2", max_requests=5, window_seconds=60)
        allowed, info = check_rate_limit("test-ip-2", max_requests=5, window_seconds=60)
        assert allowed is True

    def test_exceeds_limit(self):
        for _ in range(5):
            check_rate_limit("test-ip-3", max_requests=5, window_seconds=60)
        allowed, info = check_rate_limit("test-ip-3", max_requests=5, window_seconds=60)
        assert allowed is False
        assert "reset_in_seconds" in info


class TestCheckRateLimitAsync:
    async def test_first_request_allowed(self):
        allowed, info = await check_rate_limit_async("async-ip-1", max_requests=5, window_seconds=60)
        assert allowed is True

    async def test_exceeds_limit(self):
        for _ in range(5):
            await check_rate_limit_async("async-ip-2", max_requests=5, window_seconds=60)
        allowed, info = await check_rate_limit_async("async-ip-2", max_requests=5, window_seconds=60)
        assert allowed is False
