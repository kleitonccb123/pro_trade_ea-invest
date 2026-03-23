"""
Unit Tests — Production Validator (Latency Monitor, Trade Audit, Connectivity)

Tests:
  - LatencyMonitor: record, stats, percentiles, error rate, multi-endpoint
  - TradeAuditLogger: log events, query by user, query by order
  - KuCoinConnectivityChecker: public/private checks with mocks
  - timed_request helper
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.trading.production_validator import (
    KuCoinConnectivityChecker,
    LatencyMonitor,
    LatencyRecord,
    TradeAuditLogger,
    get_latency_monitor,
    get_trade_audit,
    timed_request,
)


# ── LatencyMonitor ───────────────────────────────────────────────────────────

class TestLatencyMonitor:

    def test_empty_stats(self):
        m = LatencyMonitor()
        s = m.stats()
        assert s["count"] == 0
        assert s["avg_ms"] == 0.0

    def test_single_record(self):
        m = LatencyMonitor()
        m.record("GET /ticker", 50.0, True)
        s = m.stats("GET /ticker")
        assert s["count"] == 1
        assert s["min_ms"] == 50.0
        assert s["max_ms"] == 50.0
        assert s["avg_ms"] == 50.0
        assert s["error_rate_pct"] == 0.0

    def test_multiple_records(self):
        m = LatencyMonitor()
        m.record("GET /ticker", 10.0, True)
        m.record("GET /ticker", 30.0, True)
        m.record("GET /ticker", 20.0, True)
        s = m.stats("GET /ticker")
        assert s["count"] == 3
        assert s["min_ms"] == 10.0
        assert s["max_ms"] == 30.0
        assert s["avg_ms"] == 20.0

    def test_error_rate(self):
        m = LatencyMonitor()
        m.record("POST /orders", 100.0, True)
        m.record("POST /orders", 200.0, False)
        m.record("POST /orders", 150.0, True)
        m.record("POST /orders", 300.0, False)
        s = m.stats("POST /orders")
        assert s["error_rate_pct"] == 50.0

    def test_percentiles(self):
        m = LatencyMonitor()
        # Insert 100 records with increasing latency
        for i in range(1, 101):
            m.record("GET /test", float(i), True)
        s = m.stats("GET /test")
        # int(100*0.95)=95 -> sorted[95]=96, int(100*0.99)=99 -> sorted[99]=100
        assert s["p95_ms"] == 96.0
        assert s["p99_ms"] == 100.0

    def test_multi_endpoint_stats(self):
        m = LatencyMonitor()
        m.record("GET /a", 10.0, True)
        m.record("GET /b", 20.0, True)
        all_stats = m.all_endpoint_stats()
        assert "GET /a" in all_stats
        assert "GET /b" in all_stats
        assert "_global" in all_stats
        assert all_stats["_global"]["count"] == 2

    def test_max_records_limit(self):
        m = LatencyMonitor(max_records=5)
        for i in range(10):
            m.record("ep", float(i), True)
        s = m.stats("ep")
        assert s["count"] == 5  # only last 5 kept

    def test_global_singleton(self):
        mon = get_latency_monitor()
        assert isinstance(mon, LatencyMonitor)


# ── timed_request ────────────────────────────────────────────────────────────

class TestTimedRequest:

    @pytest.mark.asyncio
    async def test_records_success(self):
        m = LatencyMonitor()

        async def slow_call():
            await asyncio.sleep(0.01)
            return "ok"

        result = await timed_request(slow_call(), "test_ep", monitor=m)
        assert result == "ok"
        s = m.stats("test_ep")
        assert s["count"] == 1
        assert s["error_rate_pct"] == 0.0
        assert s["min_ms"] > 0

    @pytest.mark.asyncio
    async def test_records_failure(self):
        m = LatencyMonitor()

        async def fail_call():
            raise ConnectionError("timeout")

        with pytest.raises(ConnectionError):
            await timed_request(fail_call(), "test_ep", monitor=m)
        s = m.stats("test_ep")
        assert s["count"] == 1
        assert s["error_rate_pct"] == 100.0


# ── TradeAuditLogger ────────────────────────────────────────────────────────

class _ChainableCursor:
    """Test helper — mimics Motor cursor with chaining."""

    def __init__(self, docs):
        self._docs = docs
        self._sort_key = None
        self._sort_dir = 1
        self._limit = None

    def sort(self, key, direction=1):
        self._sort_key = key
        self._sort_dir = direction
        return self

    def limit(self, n):
        self._limit = n
        return self

    async def to_list(self, length=None):
        docs = list(self._docs)
        if self._sort_key:
            docs.sort(key=lambda d: d.get(self._sort_key, ""), reverse=self._sort_dir == -1)
        if self._limit:
            docs = docs[: self._limit]
        return docs


class TestTradeAuditLogger:

    @pytest.mark.asyncio
    async def test_log_event(self):
        mock_col = AsyncMock()
        mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc123"))
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        audit = TradeAuditLogger(db=mock_db)
        result = await audit.log(
            event_type="ORDER_SENT",
            user_id="u1",
            bot_id="b1",
            order_id="ord1",
            symbol="BTC-USDT",
            side="buy",
            amount=0.01,
            price=50000.0,
        )
        assert result == "abc123"
        mock_col.insert_one.assert_called_once()
        doc = mock_col.insert_one.call_args[0][0]
        assert doc["event_type"] == "ORDER_SENT"
        assert doc["user_id"] == "u1"
        assert doc["symbol"] == "BTC-USDT"

    @pytest.mark.asyncio
    async def test_get_user_events(self):
        docs = [
            {"_id": "a1", "event_type": "ORDER_SENT", "user_id": "u1", "timestamp": datetime(2026, 1, 1)},
            {"_id": "a2", "event_type": "ORDER_FILLED", "user_id": "u1", "timestamp": datetime(2026, 1, 2)},
        ]

        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursor(docs))
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        audit = TradeAuditLogger(db=mock_db)
        events = await audit.get_user_events("u1", limit=10)
        assert len(events) == 2
        assert events[0]["_id"] == "a2"  # sorted desc by timestamp

    @pytest.mark.asyncio
    async def test_get_user_events_with_filter(self):
        docs = [
            {"_id": "a1", "event_type": "ORDER_SENT", "user_id": "u1", "bot_id": "b1", "timestamp": datetime(2026, 1, 1)},
        ]

        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursor(docs))
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        audit = TradeAuditLogger(db=mock_db)
        events = await audit.get_user_events("u1", event_type="ORDER_SENT", bot_id="b1")
        query = mock_col.find.call_args[0][0]
        assert query["event_type"] == "ORDER_SENT"
        assert query["bot_id"] == "b1"

    @pytest.mark.asyncio
    async def test_get_order_trail(self):
        docs = [
            {"_id": "a1", "order_id": "ord1", "event_type": "ORDER_INTENT", "timestamp": datetime(2026, 1, 1, 0, 0)},
            {"_id": "a2", "order_id": "ord1", "event_type": "ORDER_SENT", "timestamp": datetime(2026, 1, 1, 0, 1)},
            {"_id": "a3", "order_id": "ord1", "event_type": "ORDER_FILLED", "timestamp": datetime(2026, 1, 1, 0, 2)},
        ]

        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursor(docs))
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        audit = TradeAuditLogger(db=mock_db)
        trail = await audit.get_order_trail("ord1")
        assert len(trail) == 3
        # sorted ascending by timestamp
        assert trail[0]["event_type"] == "ORDER_INTENT"
        assert trail[2]["event_type"] == "ORDER_FILLED"

    def test_global_singleton(self):
        audit = get_trade_audit()
        assert isinstance(audit, TradeAuditLogger)


# ── KuCoinConnectivityChecker ────────────────────────────────────────────────

class TestConnectivityChecker:

    @pytest.mark.asyncio
    async def test_public_check_success(self):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=1709900000000)
        mock_client.get_ticker = AsyncMock(return_value={"lastTradedPrice": "65000.0"})
        mock_client.base_url = "https://openapi-sandbox.kucoin.com"

        checker = KuCoinConnectivityChecker(mock_client)
        result = await checker.check_public()
        assert result["server_time"]["ok"] is True
        assert result["ticker"]["ok"] is True
        assert result["ticker"]["last_price"] == "65000.0"

    @pytest.mark.asyncio
    async def test_public_check_failure(self):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=ConnectionError("network"))
        mock_client.get_ticker = AsyncMock(side_effect=ConnectionError("network"))
        mock_client.base_url = "https://api.kucoin.com"

        checker = KuCoinConnectivityChecker(mock_client)
        result = await checker.check_public()
        assert result["server_time"]["ok"] is False
        assert result["ticker"]["ok"] is False

    @pytest.mark.asyncio
    async def test_private_check_success(self):
        mock_client = AsyncMock()
        mock_client.get_account_balances = AsyncMock(return_value=[{"currency": "USDT", "available": "1000"}])
        mock_client.get_open_orders = AsyncMock(return_value=[])
        mock_client.base_url = "https://openapi-sandbox.kucoin.com"

        checker = KuCoinConnectivityChecker(mock_client)
        result = await checker.check_private()
        assert result["account_balances"]["ok"] is True
        assert result["account_balances"]["account_count"] == 1
        assert result["open_orders"]["ok"] is True

    @pytest.mark.asyncio
    async def test_full_check(self):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=1709900000000)
        mock_client.get_ticker = AsyncMock(return_value={"lastTradedPrice": "65000.0"})
        mock_client.get_account_balances = AsyncMock(return_value=[])
        mock_client.get_open_orders = AsyncMock(return_value=[])
        mock_client.base_url = "https://openapi-sandbox.kucoin.com"

        checker = KuCoinConnectivityChecker(mock_client)
        result = await checker.full_check()
        assert result["mode"] == "sandbox"
        assert result["overall_ok"] is True
        assert "checked_at" in result

    @pytest.mark.asyncio
    async def test_full_check_partial_failure(self):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=1709900000000)
        mock_client.get_ticker = AsyncMock(return_value={"lastTradedPrice": "65000.0"})
        mock_client.get_account_balances = AsyncMock(side_effect=Exception("auth error"))
        mock_client.get_open_orders = AsyncMock(return_value=[])
        mock_client.base_url = "https://api.kucoin.com"

        checker = KuCoinConnectivityChecker(mock_client)
        result = await checker.full_check()
        assert result["mode"] == "production"
        assert result["overall_ok"] is False
