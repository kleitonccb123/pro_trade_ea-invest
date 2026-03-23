"""
Integration Tests — Billing Management Endpoints (PEND-04)

Tests the expanded billing router:
  POST /api/billing/cancel
  GET  /api/billing/invoices
  GET  /api/admin/billing/metrics
  GET  /api/admin/billing/subscribers
  GET  /api/admin/billing/events
"""

import pytest
from tests.conftest import TEST_USER_ID


# ===================================================================
# Cancel Subscription
# ===================================================================

class TestCancelSubscription:
    async def test_cancel_requires_auth(self, client):
        resp = await client.post("/api/billing/cancel", json={"reason": "test"})
        assert resp.status_code in (401, 403)

    async def test_cancel_free_user_returns_400(self, client, auth_header):
        resp = await client.post(
            "/api/billing/cancel",
            json={"reason": "test"},
            headers=auth_header,
        )
        assert resp.status_code == 400


# ===================================================================
# Invoices
# ===================================================================

class TestInvoices:
    async def test_invoices_returns_200(self, client, auth_header):
        resp = await client.get("/api/billing/invoices", headers=auth_header)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_invoices_requires_auth(self, client):
        resp = await client.get("/api/billing/invoices")
        assert resp.status_code in (401, 403)


# ===================================================================
# Admin Billing Metrics
# ===================================================================

class TestAdminMetrics:
    async def test_metrics_requires_admin(self, client, auth_header):
        """Non-admin user gets 403."""
        resp = await client.get("/api/admin/billing/metrics", headers=auth_header)
        assert resp.status_code == 403

    async def test_subscribers_requires_admin(self, client, auth_header):
        resp = await client.get("/api/admin/billing/subscribers", headers=auth_header)
        assert resp.status_code == 403

    async def test_events_requires_admin(self, client, auth_header):
        resp = await client.get("/api/admin/billing/events", headers=auth_header)
        assert resp.status_code == 403
