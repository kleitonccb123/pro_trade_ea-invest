"""
Unit Tests — Circuit Breaker (ExchangeHealthMonitor)

Tests:
  - State transitions: CLOSED → OPEN → HALF_OPEN → CLOSED
  - Consecutive failure threshold
  - Error rate window threshold
  - Timeout transition (OPEN → HALF_OPEN)
  - Guard decorator
  - Status reporting
"""

import time
from unittest.mock import patch

import pytest

from app.trading.circuit_breaker import (
    CircuitOpenError,
    CircuitState,
    ExchangeHealthMonitor,
    init_circuit_breaker,
    get_circuit_breaker,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_monitor(**kwargs) -> ExchangeHealthMonitor:
    defaults = dict(failure_threshold=3, success_threshold=2, timeout_s=5.0, error_rate_pct=60.0, window_s=30.0)
    defaults.update(kwargs)
    return ExchangeHealthMonitor(**defaults)


# ── Tests: Initial State ────────────────────────────────────────────────────

class TestInitialState:

    def test_starts_closed(self):
        m = _make_monitor()
        assert m.state == CircuitState.CLOSED

    def test_is_open_false_initially(self):
        m = _make_monitor()
        assert m.is_open is False

    def test_status_dict(self):
        m = _make_monitor()
        s = m.status()
        assert s["state"] == "closed"
        assert s["consecutive_fails"] == 0


# ── Tests: Failure Threshold ────────────────────────────────────────────────

class TestFailureThreshold:

    def test_stays_closed_under_threshold(self):
        # error_rate_pct=101 disables rate-based trigger, testing only consecutive threshold
        m = _make_monitor(failure_threshold=3, error_rate_pct=101.0)
        m.record_failure(RuntimeError("err1"))
        m.record_failure(RuntimeError("err2"))
        assert m.state == CircuitState.CLOSED

    def test_opens_at_threshold(self):
        m = _make_monitor(failure_threshold=3)
        for i in range(3):
            m.record_failure(RuntimeError(f"err{i}"))
        assert m.state == CircuitState.OPEN

    def test_pre_request_raises_when_open(self):
        m = _make_monitor(failure_threshold=2)
        m.record_failure(RuntimeError("a"))
        m.record_failure(RuntimeError("b"))
        with pytest.raises(CircuitOpenError):
            m.pre_request()

    def test_success_resets_consecutive_fails(self):
        # error_rate_pct=101 disables rate-based trigger
        m = _make_monitor(failure_threshold=3, error_rate_pct=101.0)
        m.record_failure(RuntimeError("a"))
        m.record_failure(RuntimeError("b"))
        m.record_success()  # reset
        m.record_failure(RuntimeError("c"))
        # Only 1 consecutive failure now, not 3
        assert m.state == CircuitState.CLOSED


# ── Tests: Error Rate Window ────────────────────────────────────────────────

class TestErrorRateWindow:

    def test_opens_on_high_error_rate(self):
        m = _make_monitor(failure_threshold=100, error_rate_pct=60.0, window_s=60.0)
        # 4 failures + 1 success = 80% error rate > 60%
        m.record_success()
        for _ in range(4):
            m.record_failure(RuntimeError("x"))
        assert m.state == CircuitState.OPEN

    def test_stays_closed_on_low_error_rate(self):
        m = _make_monitor(failure_threshold=100, error_rate_pct=60.0)
        # 2 failures + 3 success = 40% error rate < 60%
        m.record_success()
        m.record_success()
        m.record_success()
        m.record_failure(RuntimeError("x"))
        m.record_failure(RuntimeError("y"))
        assert m.state == CircuitState.CLOSED


# ── Tests: Timeout Transition ───────────────────────────────────────────────

class TestTimeoutTransition:

    def test_open_to_half_open_after_timeout(self):
        m = _make_monitor(failure_threshold=2, timeout_s=0.1)
        m.record_failure(RuntimeError("a"))
        m.record_failure(RuntimeError("b"))
        assert m.state == CircuitState.OPEN
        time.sleep(0.15)
        # Accessing .state triggers _check_timeout
        assert m.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_after_successes(self):
        m = _make_monitor(failure_threshold=2, success_threshold=2, timeout_s=0.1)
        m.record_failure(RuntimeError("a"))
        m.record_failure(RuntimeError("b"))
        time.sleep(0.15)
        assert m.state == CircuitState.HALF_OPEN
        m.record_success()
        m.record_success()
        assert m.state == CircuitState.CLOSED

    def test_half_open_back_to_open_on_failure(self):
        m = _make_monitor(failure_threshold=2, timeout_s=0.1)
        m.record_failure(RuntimeError("a"))
        m.record_failure(RuntimeError("b"))
        time.sleep(0.15)
        assert m.state == CircuitState.HALF_OPEN
        # Fail while in HALF_OPEN — should go back to OPEN
        # The record_failure triggers consecutive threshold again
        m.record_failure(RuntimeError("c"))
        m.record_failure(RuntimeError("d"))
        assert m.state == CircuitState.OPEN


# ── Tests: Guard Decorator ──────────────────────────────────────────────────

class TestGuardDecorator:

    @pytest.mark.asyncio
    async def test_guard_records_success(self):
        m = _make_monitor()

        async def ok_fn():
            return 42

        wrapped = m.guard(ok_fn)
        result = await wrapped()
        assert result == 42
        assert m.status()["window_size"] == 1

    @pytest.mark.asyncio
    async def test_guard_records_failure(self):
        m = _make_monitor()

        async def fail_fn():
            raise ValueError("boom")

        wrapped = m.guard(fail_fn)
        with pytest.raises(ValueError, match="boom"):
            await wrapped()
        assert m.status()["consecutive_fails"] == 1

    @pytest.mark.asyncio
    async def test_guard_raises_circuit_open(self):
        m = _make_monitor(failure_threshold=1)
        m.record_failure(RuntimeError("x"))

        async def never_called():
            return "should not get here"

        wrapped = m.guard(never_called)
        with pytest.raises(CircuitOpenError):
            await wrapped()


# ── Tests: Global Singleton ─────────────────────────────────────────────────

class TestGlobalSingleton:

    def test_init_and_get(self):
        cb = init_circuit_breaker(failure_threshold=10, timeout_s=30)
        assert get_circuit_breaker() is cb

    def test_get_returns_none_without_init(self):
        # Reset global (careful: this modifies module state)
        import app.trading.circuit_breaker as mod
        old = mod._circuit_breaker
        mod._circuit_breaker = None
        assert get_circuit_breaker() is None
        mod._circuit_breaker = old


# ── Tests: Core Resilience CircuitBreaker ────────────────────────────────────

class TestCoreCircuitBreaker:

    @pytest.mark.asyncio
    async def test_decorator_pattern(self):
        from app.core.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitOpenError as CoreOpenError

        cb = CircuitBreaker("test_core_cb", CircuitBreakerConfig(failure_threshold=2, timeout=0.1))

        call_count = 0

        @cb
        async def flaky():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("down")

        # 2 failures should open
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await flaky()
        assert call_count == 2

        # Now should be OPEN
        with pytest.raises(CoreOpenError):
            await flaky()
        assert call_count == 2  # was not called

    @pytest.mark.asyncio
    async def test_recovery_via_success(self):
        from app.core.resilience import CircuitBreaker, CircuitBreakerConfig

        cb = CircuitBreaker("test_recover_cb", CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout=0.1,
        ))

        @cb
        async def will_fail():
            raise ConnectionError("err")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await will_fail()

        import asyncio
        await asyncio.sleep(0.15)

        # Now HALF_OPEN — next call should succeed
        @cb
        async def will_succeed():
            return "ok"

        result = await will_succeed()
        assert result == "ok"

    def test_get_all_stats(self):
        from app.core.resilience import CircuitBreaker
        stats = CircuitBreaker.get_all_stats()
        assert isinstance(stats, dict)
