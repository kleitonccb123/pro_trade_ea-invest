"""
Unit Tests — Billing Service (PEND-04)

Covers:
  - Invoice generation
  - User invoice listing
  - Subscription cancellation
  - Revenue metrics computation
  - Active subscriber listing
  - Billing events listing
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers — chainable cursor mock
# ---------------------------------------------------------------------------

class _ChainableCursor:
    """Mimics a Motor cursor with sort/skip/limit/to_list chaining."""

    def __init__(self, docs: list):
        self._docs = list(docs)

    def sort(self, *_a, **_kw):
        return self

    def skip(self, n: int):
        self._docs = self._docs[n:]
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return self._docs[:length] if length else self._docs


def _make_collection(docs=None):
    """Build an AsyncMock collection backed by a doc list."""
    docs = docs or []
    col = AsyncMock()
    col.find = MagicMock(return_value=_ChainableCursor(docs))
    col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="inv_001"))
    col.update_one = AsyncMock()
    col.count_documents = AsyncMock(return_value=0)
    col.aggregate = MagicMock(return_value=_ChainableCursor([]))
    return col


def _make_db():
    db = MagicMock()
    db.invoices = _make_collection()
    db.licenses = _make_collection()
    db.license_audit = _make_collection()
    db.webhook_events = _make_collection()
    return db


# ===================================================================
# Invoice Tests
# ===================================================================

class TestGenerateInvoice:
    async def test_creates_invoice_doc(self):
        from app.billing.service import generate_invoice_from_event

        db = _make_db()
        result = await generate_invoice_from_event(
            db,
            user_id="u1",
            sale_id="PP-123",
            payload={
                "sale_amount": "97.00",
                "payment_method": "credit_card",
                "product_name": "Plano Pro Mensal",
                "subscription_id": "SUB-1",
                "customer_email": "user@test.com",
            },
        )
        assert result == "inv_001"
        db.invoices.insert_one.assert_awaited_once()
        doc = db.invoices.insert_one.call_args[0][0]
        assert doc["user_id"] == "u1"
        assert doc["sale_id"] == "PP-123"
        assert doc["amount"] == 97.0
        assert doc["status"] == "paid"

    async def test_handles_invalid_amount(self):
        from app.billing.service import generate_invoice_from_event

        db = _make_db()
        await generate_invoice_from_event(db, "u1", "PP-X", {"sale_amount": "invalid"})
        doc = db.invoices.insert_one.call_args[0][0]
        assert doc["amount"] == 0.0

    async def test_handles_missing_amount(self):
        from app.billing.service import generate_invoice_from_event

        db = _make_db()
        await generate_invoice_from_event(db, "u1", "PP-Y", {})
        doc = db.invoices.insert_one.call_args[0][0]
        assert doc["amount"] == 0.0


class TestGetUserInvoices:
    async def test_returns_invoices(self):
        from app.billing.service import get_user_invoices

        inv = {"sale_id": "PP-1", "amount": 50.0, "status": "paid"}
        db = _make_db()
        db.invoices.find = MagicMock(return_value=_ChainableCursor([inv]))

        result = await get_user_invoices(db, "u1", limit=10)
        assert len(result) == 1
        assert result[0]["sale_id"] == "PP-1"

    async def test_empty_list(self):
        from app.billing.service import get_user_invoices

        db = _make_db()
        result = await get_user_invoices(db, "u1")
        assert result == []


# ===================================================================
# Cancel Subscription
# ===================================================================

class TestCancelSubscription:
    async def test_creates_grace_period(self):
        from app.billing.service import cancel_subscription

        db = _make_db()
        result = await cancel_subscription(db, "u1", "user_request")

        assert result["canceled"] is True
        assert "grace_until" in result
        db.licenses.update_one.assert_awaited_once()
        db.license_audit.insert_one.assert_awaited_once()

        # Check audit event
        audit_doc = db.license_audit.insert_one.call_args[0][0]
        assert audit_doc["event"] == "cancel_requested"
        assert audit_doc["user_id"] == "u1"

    async def test_custom_reason(self):
        from app.billing.service import cancel_subscription

        db = _make_db()
        result = await cancel_subscription(db, "u1", "too_expensive")
        audit_doc = db.license_audit.insert_one.call_args[0][0]
        assert audit_doc["context"]["reason"] == "too_expensive"


# ===================================================================
# Revenue Metrics
# ===================================================================

class TestComputeRevenueMetrics:
    async def test_empty_database(self):
        from app.billing.service import compute_revenue_metrics

        db = _make_db()
        db.licenses.count_documents = AsyncMock(return_value=0)
        db.license_audit.count_documents = AsyncMock(return_value=0)

        metrics = await compute_revenue_metrics(db)
        assert metrics["mrr"] == 0.0
        assert metrics["active_subscribers"] == 0
        assert metrics["churned_30d"] == 0
        assert metrics["churn_rate"] == 0.0
        assert metrics["total_revenue"] == 0.0
        assert metrics["arpu"] == 0.0

    async def test_with_active_subscribers(self):
        from app.billing.service import compute_revenue_metrics

        db = _make_db()
        db.licenses.count_documents = AsyncMock(return_value=10)
        db.license_audit.count_documents = AsyncMock(return_value=2)
        db.invoices.aggregate = MagicMock(side_effect=[
            _ChainableCursor([{"_id": None, "total": 5000.0, "count": 50}]),
            _ChainableCursor([{"_id": None, "total": 1200.0}]),
        ])

        metrics = await compute_revenue_metrics(db)
        assert metrics["active_subscribers"] == 10
        assert metrics["churned_30d"] == 2
        assert metrics["churn_rate"] == round(2 / 12, 4)
        assert metrics["mrr"] == 1200.0
        assert metrics["total_revenue"] == 5000.0
        assert metrics["revenue_30d"] == 1200.0
        assert metrics["arpu"] == 500.0  # 5000 / 10
        assert metrics["total_invoices"] == 50


# ===================================================================
# List Active Subscribers
# ===================================================================

class TestListActiveSubscribers:
    async def test_returns_subscribers(self):
        from app.billing.service import list_active_subscribers

        sub = {"user_id": "u1", "plan": "pro", "activated_at": datetime.now(timezone.utc)}
        db = _make_db()
        db.licenses.find = MagicMock(return_value=_ChainableCursor([sub]))

        result = await list_active_subscribers(db, skip=0, limit=10)
        assert len(result) == 1

    async def test_empty(self):
        from app.billing.service import list_active_subscribers

        db = _make_db()
        result = await list_active_subscribers(db)
        assert result == []


# ===================================================================
# List Billing Events
# ===================================================================

class TestListBillingEvents:
    async def test_returns_events(self):
        from app.billing.service import list_billing_events

        evt = {"sale_id": "PP-1", "event_type": "approved", "processed_at": datetime.now(timezone.utc)}
        db = _make_db()
        db.webhook_events.find = MagicMock(return_value=_ChainableCursor([evt]))

        result = await list_billing_events(db, limit=10)
        assert len(result) == 1
        assert result[0]["sale_id"] == "PP-1"

    async def test_empty(self):
        from app.billing.service import list_billing_events

        db = _make_db()
        result = await list_billing_events(db)
        assert result == []
