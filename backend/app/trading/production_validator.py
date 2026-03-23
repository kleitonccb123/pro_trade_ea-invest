"""
KuCoin Production Validation — PEND-03

Provides:
  1. Sandbox ↔ Production mode switching with explicit env control
  2. Connectivity health check (public + private endpoints)
  3. Latency monitoring per-call with running statistics
  4. Trade audit integration — logs every order lifecycle event
  5. Engine health router with circuit breaker + latency metrics
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("trading.production_validator")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Latency Monitor — tracks per-endpoint call latencies
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LatencyRecord:
    endpoint: str
    latency_ms: float
    success: bool
    timestamp: float = field(default_factory=time.monotonic)


class LatencyMonitor:
    """
    Sliding-window latency tracker for exchange API calls.

    Stores up to ``max_records`` most recent calls per endpoint
    and exposes min/max/avg/p95/p99 statistics.
    """

    def __init__(self, max_records: int = 500) -> None:
        self._max = max_records
        self._records: Dict[str, Deque[LatencyRecord]] = {}
        self._global: Deque[LatencyRecord] = deque(maxlen=max_records)

    def record(self, endpoint: str, latency_ms: float, success: bool) -> None:
        if endpoint not in self._records:
            self._records[endpoint] = deque(maxlen=self._max)
        rec = LatencyRecord(endpoint=endpoint, latency_ms=latency_ms, success=success)
        self._records[endpoint].append(rec)
        self._global.append(rec)

    def stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        records = list(self._records.get(endpoint, [])) if endpoint else list(self._global)
        if not records:
            return {
                "count": 0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "avg_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "error_rate_pct": 0.0,
            }
        latencies = sorted(r.latency_ms for r in records)
        n = len(latencies)
        errors = sum(1 for r in records if not r.success)
        return {
            "count": n,
            "min_ms": round(latencies[0], 2),
            "max_ms": round(latencies[-1], 2),
            "avg_ms": round(sum(latencies) / n, 2),
            "p95_ms": round(latencies[int(n * 0.95)] if n > 1 else latencies[0], 2),
            "p99_ms": round(latencies[int(n * 0.99)] if n > 1 else latencies[0], 2),
            "error_rate_pct": round((errors / n) * 100, 2) if n else 0.0,
        }

    def all_endpoint_stats(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for ep in self._records:
            result[ep] = self.stats(ep)
        result["_global"] = self.stats()
        return result


# Global singleton
_latency_monitor = LatencyMonitor()


def get_latency_monitor() -> LatencyMonitor:
    return _latency_monitor


# ─────────────────────────────────────────────────────────────────────────────
# 2. Instrumented REST client wrapper — records latency automatically
# ─────────────────────────────────────────────────────────────────────────────

async def timed_request(coro, endpoint: str, monitor: Optional[LatencyMonitor] = None):
    """Execute an awaitable and record its latency."""
    mon = monitor or _latency_monitor
    t0 = time.perf_counter()
    success = True
    try:
        result = await coro
        return result
    except Exception:
        success = False
        raise
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        mon.record(endpoint, elapsed_ms, success)


# ─────────────────────────────────────────────────────────────────────────────
# 3. KuCoin Connectivity Checker
# ─────────────────────────────────────────────────────────────────────────────

class KuCoinConnectivityChecker:
    """
    Validates KuCoin API connectivity for both sandbox and production.

    Usage:
        checker = KuCoinConnectivityChecker(rest_client)
        report = await checker.full_check()
    """

    def __init__(self, rest_client) -> None:
        self._client = rest_client

    async def check_public(self) -> Dict[str, Any]:
        """Test public endpoints (no auth required)."""
        results: Dict[str, Any] = {}

        # 1. Server time
        t0 = time.perf_counter()
        try:
            data = await self._client.request(
                "GET", "/api/v1/timestamp", authenticated=False,
            )
            latency = (time.perf_counter() - t0) * 1000
            server_ts = data if isinstance(data, (int, float)) else 0
            results["server_time"] = {
                "ok": True,
                "latency_ms": round(latency, 2),
                "server_timestamp": server_ts,
            }
        except Exception as exc:
            results["server_time"] = {"ok": False, "error": str(exc)}

        # 2. Ticker
        t0 = time.perf_counter()
        try:
            ticker = await self._client.get_ticker("BTC-USDT")
            latency = (time.perf_counter() - t0) * 1000
            results["ticker"] = {
                "ok": True,
                "latency_ms": round(latency, 2),
                "last_price": ticker.get("last") or ticker.get("lastTradedPrice"),
            }
        except Exception as exc:
            results["ticker"] = {"ok": False, "error": str(exc)}

        return results

    async def check_private(self) -> Dict[str, Any]:
        """Test private endpoints (requires valid API credentials)."""
        results: Dict[str, Any] = {}

        # 1. Account balances
        t0 = time.perf_counter()
        try:
            balances = await self._client.get_account_balances()
            latency = (time.perf_counter() - t0) * 1000
            results["account_balances"] = {
                "ok": True,
                "latency_ms": round(latency, 2),
                "account_count": len(balances) if isinstance(balances, list) else 0,
            }
        except Exception as exc:
            results["account_balances"] = {"ok": False, "error": str(exc)}

        # 2. Open orders (read-only, safe check)
        t0 = time.perf_counter()
        try:
            orders = await self._client.get_open_orders()
            latency = (time.perf_counter() - t0) * 1000
            results["open_orders"] = {
                "ok": True,
                "latency_ms": round(latency, 2),
                "order_count": len(orders) if isinstance(orders, list) else 0,
            }
        except Exception as exc:
            results["open_orders"] = {"ok": False, "error": str(exc)}

        return results

    async def full_check(self) -> Dict[str, Any]:
        """Run both public and private connectivity checks."""
        is_sandbox = self._client.base_url != "https://api.kucoin.com"
        public = await self.check_public()
        private = await self.check_private()
        all_ok = all(
            v.get("ok", False)
            for section in (public, private)
            for v in section.values()
        )
        return {
            "mode": "sandbox" if is_sandbox else "production",
            "base_url": self._client.base_url,
            "overall_ok": all_ok,
            "public": public,
            "private": private,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Trade Audit Logger — structured per-trade lifecycle events
# ─────────────────────────────────────────────────────────────────────────────

class TradeAuditLogger:
    """
    Logs every order lifecycle event into the ``trade_audit_log`` collection.

    Events: ORDER_INTENT, ORDER_SENT, ORDER_FILLED, ORDER_CANCELLED,
            ORDER_ERROR, POSITION_OPENED, POSITION_CLOSED, STOP_ORDER_PLACED,
            STOP_ORDER_CANCELLED.

    Each document is immutable (insert-only) for audit compliance.
    """

    COLLECTION = "trade_audit_log"

    def __init__(self, db=None):
        self._db = db

    def _get_db(self):
        if self._db is not None:
            return self._db
        from app.core.database import get_db
        return get_db()

    async def log(
        self,
        event_type: str,
        user_id: str,
        bot_id: Optional[str] = None,
        order_id: Optional[str] = None,
        client_oid: Optional[str] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        amount: Optional[float] = None,
        price: Optional[float] = None,
        fee: Optional[float] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert an immutable audit record. Returns the inserted _id as string."""
        db = self._get_db()
        doc = {
            "event_type": event_type,
            "user_id": user_id,
            "bot_id": bot_id,
            "order_id": order_id,
            "client_oid": client_oid,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "fee": fee,
            "latency_ms": latency_ms,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc),
        }
        result = await db[self.COLLECTION].insert_one(doc)
        logger.info(
            "AUDIT [%s] user=%s bot=%s order=%s symbol=%s side=%s",
            event_type, user_id, bot_id, order_id, symbol, side,
        )
        return str(result.inserted_id)

    async def get_user_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        bot_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        db = self._get_db()
        query: Dict[str, Any] = {"user_id": user_id}
        if event_type:
            query["event_type"] = event_type
        if bot_id:
            query["bot_id"] = bot_id
        cursor = db[self.COLLECTION].find(query).sort("timestamp", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def get_order_trail(self, order_id: str) -> List[Dict[str, Any]]:
        """Full lifecycle trail for a single order."""
        db = self._get_db()
        cursor = (
            db[self.COLLECTION]
            .find({"order_id": order_id})
            .sort("timestamp", 1)
        )
        docs = await cursor.to_list(length=50)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs


# Global singleton
_trade_audit = TradeAuditLogger()


def get_trade_audit() -> TradeAuditLogger:
    return _trade_audit
