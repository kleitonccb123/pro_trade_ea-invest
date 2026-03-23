"""
Integration Tests — Engine Health Endpoints (PEND-03)

Tests:
  GET /api/engine/health
  GET /api/engine/latency
  GET /api/engine/circuit-breaker
  GET /api/engine/audit/{bot_id}
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture()
async def ac(app, auth_header):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.headers.update(auth_header)
        yield c


class TestEngineHealth:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, ac: AsyncClient):
        r = await ac.get("/api/engine/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "degraded", "unhealthy")
        assert "uptime_s" in body
        assert body["mode"] in ("sandbox", "production")

    @pytest.mark.asyncio
    async def test_health_unauthenticated(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/engine/health")
            assert r.status_code in (401, 403)


class TestEngineLatency:

    @pytest.mark.asyncio
    async def test_latency_returns_200(self, ac: AsyncClient):
        r = await ac.get("/api/engine/latency")
        assert r.status_code == 200
        body = r.json()
        assert "_global" in body

    @pytest.mark.asyncio
    async def test_latency_with_endpoint_filter(self, ac: AsyncClient):
        r = await ac.get("/api/engine/latency", params={"endpoint": "GET /test"})
        assert r.status_code == 200
        body = r.json()
        assert "count" in body


class TestCircuitBreakerEndpoint:

    @pytest.mark.asyncio
    async def test_circuit_breaker_returns_200(self, ac: AsyncClient):
        r = await ac.get("/api/engine/circuit-breaker")
        assert r.status_code == 200
        body = r.json()
        # Should have at least the resilience_breakers key
        assert "resilience_breakers" in body


class TestAuditEndpoint:

    @pytest.mark.asyncio
    async def test_audit_trail_empty(self, ac: AsyncClient):
        r = await ac.get("/api/engine/audit/nonexistent_bot_id")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 0

    @pytest.mark.asyncio
    async def test_order_trail_empty(self, ac: AsyncClient):
        r = await ac.get("/api/engine/audit/order/nonexistent_order_id")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 0
