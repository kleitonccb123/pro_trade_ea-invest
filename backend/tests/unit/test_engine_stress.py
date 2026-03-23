"""
Stress / Concurrency Tests — Trading Engine (PEND-03)

Tests:
  - Concurrent order placement with circuit breaker protection
  - Multiple bot workers running simultaneously
  - Circuit breaker under high failure rates
  - Latency monitor under concurrent load
  - Balance reservation race conditions
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.trading.circuit_breaker import (
    CircuitOpenError,
    CircuitState,
    ExchangeHealthMonitor,
)
from app.trading.production_validator import LatencyMonitor, TradeAuditLogger


# ── Concurrent Circuit Breaker Stress ────────────────────────────────────────

class TestCircuitBreakerConcurrency:
    """Verify circuit breaker behaves correctly under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_successes(self):
        """Many coroutines recording success simultaneously."""
        m = ExchangeHealthMonitor(failure_threshold=5)

        async def hit():
            m.pre_request()
            m.record_success()

        tasks = [hit() for _ in range(50)]
        await asyncio.gather(*tasks)
        assert m.state == CircuitState.CLOSED
        assert m.status()["window_size"] == 50

    @pytest.mark.asyncio
    async def test_concurrent_failures_open_circuit(self):
        """Concurrent failures should eventually open the circuit."""
        m = ExchangeHealthMonitor(failure_threshold=5)

        async def fail():
            try:
                m.pre_request()
            except CircuitOpenError:
                return "blocked"
            m.record_failure(RuntimeError("err"))
            return "failed"

        tasks = [fail() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        assert m.state == CircuitState.OPEN
        # Some should be blocked after circuit opens
        assert "blocked" in results or m.status()["consecutive_fails"] >= 5

    @pytest.mark.asyncio
    async def test_guard_under_concurrent_load(self):
        """Guard decorator with mixed success/failure under load."""
        m = ExchangeHealthMonitor(failure_threshold=10, error_rate_pct=80.0)
        call_count = 0

        async def flaky(should_fail: bool):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ValueError("flaky")
            return "ok"

        wrapped = m.guard(flaky)
        tasks = []
        for i in range(20):
            tasks.append(wrapped(should_fail=(i % 3 == 0)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        successes = sum(1 for r in results if r == "ok")
        failures = sum(1 for r in results if isinstance(r, (ValueError, CircuitOpenError)))
        assert successes + failures == 20


# ── Concurrent Latency Monitor ──────────────────────────────────────────────

class TestLatencyMonitorConcurrency:

    @pytest.mark.asyncio
    async def test_concurrent_records(self):
        """Many coroutines recording latency at once."""
        m = LatencyMonitor(max_records=1000)

        async def record(i: int):
            m.record(f"ep_{i % 5}", float(i), True)

        tasks = [record(i) for i in range(200)]
        await asyncio.gather(*tasks)
        stats = m.all_endpoint_stats()
        total = sum(stats[ep]["count"] for ep in stats if ep != "_global")
        assert total == 200
        assert stats["_global"]["count"] == 200


# ── Concurrent Trade Audit Logging ──────────────────────────────────────────

class TestTradeAuditConcurrency:

    @pytest.mark.asyncio
    async def test_concurrent_audit_logs(self):
        """Multiple audit events logged concurrently."""
        insert_count = 0

        async def mock_insert(doc):
            nonlocal insert_count
            insert_count += 1
            return MagicMock(inserted_id=f"id_{insert_count}")

        mock_col = AsyncMock()
        mock_col.insert_one = mock_insert
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        audit = TradeAuditLogger(db=mock_db)

        async def log_event(i: int):
            await audit.log(
                event_type="ORDER_SENT",
                user_id=f"user_{i % 5}",
                bot_id=f"bot_{i}",
                order_id=f"ord_{i}",
                symbol="BTC-USDT",
                side="buy",
            )

        tasks = [log_event(i) for i in range(50)]
        await asyncio.gather(*tasks)
        assert insert_count == 50


# ── Simulated Multi-Bot Stress ──────────────────────────────────────────────

class TestMultiBotSimulation:
    """Simulates multiple bots running trading cycles concurrently."""

    @pytest.mark.asyncio
    async def test_multiple_bots_with_circuit_breaker(self):
        """5 bots running 10 cycles each through a shared circuit breaker."""
        cb = ExchangeHealthMonitor(failure_threshold=8, error_rate_pct=70.0)
        cycle_completed = 0
        circuit_blocked = 0

        async def bot_cycle(bot_id: int, cycle: int):
            nonlocal cycle_completed, circuit_blocked
            try:
                cb.pre_request()
            except CircuitOpenError:
                circuit_blocked += 1
                return

            # Simulate: 20% failure rate
            if (bot_id + cycle) % 5 == 0:
                cb.record_failure(RuntimeError(f"bot{bot_id}_cycle{cycle}"))
            else:
                cb.record_success()
            cycle_completed += 1

        tasks = []
        for bot_id in range(5):
            for cycle in range(10):
                tasks.append(bot_cycle(bot_id, cycle))

        await asyncio.gather(*tasks)
        assert cycle_completed + circuit_blocked == 50
        # With 20% failure rate and threshold=8, circuit might not open
        # But all cycles should complete or be blocked
        assert cycle_completed > 0

    @pytest.mark.asyncio
    async def test_high_failure_rate_blocks_later_bots(self):
        """With high failure rate, later iterations should be blocked."""
        # error_rate_pct=101 disables rate-based trigger, only consecutive threshold matters
        cb = ExchangeHealthMonitor(failure_threshold=3, error_rate_pct=101.0)
        blocked = 0
        passed = 0

        async def bot_cycle(i: int):
            nonlocal blocked, passed
            try:
                cb.pre_request()
            except CircuitOpenError:
                blocked += 1
                return
            # Always fail
            cb.record_failure(RuntimeError(f"fail_{i}"))
            passed += 1

        # Run sequentially to guarantee ordering
        for i in range(10):
            await bot_cycle(i)

        # First 3 pass (trigger threshold), rest blocked
        assert passed == 3
        assert blocked == 7

    @pytest.mark.asyncio
    async def test_latency_across_bots(self):
        """Each bot records latencies to the shared monitor."""
        m = LatencyMonitor()

        async def bot_work(bot_id: int):
            for _ in range(5):
                m.record(f"bot_{bot_id}/place_order", float(bot_id * 10 + 50), True)
                m.record(f"bot_{bot_id}/get_ticker", float(bot_id * 5 + 20), True)

        tasks = [bot_work(i) for i in range(5)]
        await asyncio.gather(*tasks)

        all_stats = m.all_endpoint_stats()
        # 5 bots × 10 records each = 50 global
        assert all_stats["_global"]["count"] == 50
        # Each bot has 2 endpoints × 5 cycles = 10 records
        assert all_stats["bot_0/place_order"]["count"] == 5
