"""
Integration Tests — Analytics Endpoints
=========================================

Tests GET /analytics/dashboard/summary and GET /analytics/export/csv.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from httpx import ASGITransport, AsyncClient


TEST_USER_ID = "665f0c0a1234567890abcdef"


def _mock_current_user():
    return {
        "_id": TEST_USER_ID,
        "id": TEST_USER_ID,
        "email": "analytics@test.com",
        "name": "Analytics User",
        "is_active": True,
        "plan": "free",
    }


def _make_app():
    import os
    os.environ.setdefault("APP_MODE", "dev")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")

    from app.main import app
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    return app


class TestDashboardSummary:
    """GET /analytics/dashboard/summary"""

    async def test_summary_returns_defaults_when_no_trades(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_col.find = MagicMock(return_value=mock_cursor)
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.service.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/dashboard/summary")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total_pnl" in data
        assert "win_rate" in data
        assert "num_trades" in data
        app.dependency_overrides.clear()

    async def test_summary_with_trades(self):
        app = _make_app()

        trades = [
            {"user_id": TEST_USER_ID, "pnl": 100.0, "timestamp": datetime.utcnow().isoformat()},
            {"user_id": TEST_USER_ID, "pnl": -30.0, "timestamp": datetime.utcnow().isoformat()},
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=trades)
        mock_col.find = MagicMock(return_value=mock_cursor)
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.service.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/dashboard/summary")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["num_trades"] == 2
        assert data["total_pnl"] == 70.0
        app.dependency_overrides.clear()


class TestCSVExport:
    """GET /analytics/export/csv"""

    async def test_csv_export_empty(self):
        app = _make_app()

        class _ChainableCursor:
            def sort(self, *a, **kw): return self
            def skip(self, n): return self
            def limit(self, n): return self
            async def to_list(self, length=None): return []

        mock_db = MagicMock()
        # CSV export uses db.bot_trades.find(query).sort(...).to_list(...)
        mock_coll = MagicMock()
        mock_coll.find = MagicMock(return_value=_ChainableCursor())
        mock_db.bot_trades = mock_coll

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/csv")

        assert resp.status_code == 200, resp.text
        assert "text/csv" in resp.headers.get("content-type", "")
        app.dependency_overrides.clear()


# ===================================================================
# PEND-06: Advanced Performance Dashboard endpoints
# ===================================================================


class _ChainableCursorAM:
    """Mock cursor supporting find().to_list() for advanced metrics tests."""

    def __init__(self, data=None):
        self._data = data or []

    def sort(self, *a, **kw):
        return self

    async def to_list(self, length=None):
        return self._data


class TestAdvancedMetrics:
    """GET /analytics/advanced-metrics"""

    async def test_advanced_metrics_empty_trades(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/advanced-metrics")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["num_trades"] == 0
        assert data["total_pnl"] == 0.0
        assert data["sharpe_ratio"] == 0.0
        assert data["equity_curve"] == []
        app.dependency_overrides.clear()

    async def test_advanced_metrics_with_trades(self):
        app = _make_app()

        trades = [
            {
                "user_id": TEST_USER_ID,
                "pnl": 200.0,
                "timestamp": datetime(2025, 5, 20, 10, 0),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": -80.0,
                "timestamp": datetime(2025, 5, 22, 14, 0),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": 150.0,
                "timestamp": datetime(2025, 5, 25, 9, 0),
                "symbol": "ETH-USDT",
                "instance_id": "bot-2",
            },
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/advanced-metrics")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["num_trades"] == 3
        assert data["total_pnl"] == 270.0
        assert len(data["equity_curve"]) == 3
        assert data["sharpe_ratio"] != 0.0
        app.dependency_overrides.clear()

    async def test_advanced_metrics_with_symbol_filter(self):
        app = _make_app()

        trades = [
            {
                "user_id": TEST_USER_ID,
                "pnl": 100.0,
                "timestamp": datetime(2025, 5, 20),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": 50.0,
                "timestamp": datetime(2025, 5, 22),
                "symbol": "ETH-USDT",
                "instance_id": "bot-2",
            },
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/advanced-metrics?symbol=BTC-USDT")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["num_trades"] == 1
        assert data["total_pnl"] == 100.0
        app.dependency_overrides.clear()

    async def test_advanced_metrics_invalid_date(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/advanced-metrics?start_date=not-a-date")

        assert resp.status_code == 400, resp.text
        app.dependency_overrides.clear()

    async def test_advanced_metrics_requires_auth(self):
        """Without auth override, endpoint should reject."""
        import os
        os.environ.setdefault("APP_MODE", "dev")
        os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
        os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
        os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")

        from app.main import app
        # No dependency override → auth required
        app.dependency_overrides.clear()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.get("/analytics/advanced-metrics")

        assert resp.status_code in (401, 403), resp.text


class TestBotComparison:
    """GET /analytics/bot-comparison"""

    async def test_bot_comparison_empty(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/bot-comparison")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0
        app.dependency_overrides.clear()

    async def test_bot_comparison_with_trades(self):
        app = _make_app()

        trades = [
            {
                "user_id": TEST_USER_ID,
                "pnl": 300.0,
                "timestamp": datetime(2025, 5, 20),
                "symbol": "BTC-USDT",
                "instance_id": "bot-A",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": -50.0,
                "timestamp": datetime(2025, 5, 22),
                "symbol": "BTC-USDT",
                "instance_id": "bot-A",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": 100.0,
                "timestamp": datetime(2025, 5, 23),
                "symbol": "ETH-USDT",
                "instance_id": "bot-B",
            },
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/bot-comparison")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 2
        # Sorted by total_pnl desc → bot-A (250) > bot-B (100)
        assert data[0]["bot_id"] == "bot-A"
        assert data[0]["total_pnl"] == 250.0
        assert data[1]["bot_id"] == "bot-B"
        assert data[1]["total_pnl"] == 100.0
        # Each item has expected fields
        assert "sharpe_ratio" in data[0]
        assert "win_rate" in data[0]
        assert "symbol" in data[0]
        app.dependency_overrides.clear()

    async def test_bot_comparison_with_date_filter(self):
        app = _make_app()

        trades = [
            {
                "user_id": TEST_USER_ID,
                "pnl": 100.0,
                "timestamp": datetime(2025, 5, 10),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": 200.0,
                "timestamp": datetime(2025, 5, 25),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
            },
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/bot-comparison?start_date=2025-05-20")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["total_pnl"] == 200.0
        app.dependency_overrides.clear()


# ── PDF Export ───────────────────────────────────────────────────────────────


class TestExportPDF:
    """GET /analytics/export/pdf"""

    def _sample_trades(self):
        return [
            {
                "user_id": TEST_USER_ID,
                "pnl": 150.0,
                "timestamp": datetime(2025, 5, 10),
                "created_at": datetime(2025, 5, 10),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
                "side": "buy",
                "amount": 0.5,
                "price": 60000.0,
                "exit_price": 60300.0,
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": -50.0,
                "timestamp": datetime(2025, 5, 15),
                "created_at": datetime(2025, 5, 15),
                "symbol": "ETH-USDT",
                "instance_id": "bot-2",
                "side": "sell",
                "amount": 2.0,
                "price": 3000.0,
                "exit_price": 2975.0,
            },
        ]

    async def test_export_pdf_success(self):
        app = _make_app()
        trades = self._sample_trades()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/pdf")

        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"
        app.dependency_overrides.clear()

    async def test_export_pdf_with_filters(self):
        app = _make_app()
        trades = self._sample_trades()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get(
                    "/analytics/export/pdf?start_date=2025-05-12&symbol=ETH-USDT"
                )

        assert resp.status_code == 200, resp.text
        assert resp.content[:5] == b"%PDF-"
        app.dependency_overrides.clear()

    async def test_export_pdf_empty_trades(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/pdf")

        assert resp.status_code == 200, resp.text
        assert resp.content[:5] == b"%PDF-"
        app.dependency_overrides.clear()

    async def test_export_pdf_content_disposition(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/pdf")

        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".pdf" in cd
        app.dependency_overrides.clear()


class TestExportFiscalPDF:
    """GET /analytics/export/pdf/fiscal"""

    def _fiscal_trades(self):
        return [
            {
                "user_id": TEST_USER_ID,
                "pnl": 300.0,
                "created_at": datetime(2025, 3, 15),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": -80.0,
                "created_at": datetime(2025, 6, 20),
                "symbol": "ETH-USDT",
                "instance_id": "bot-2",
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": 120.0,
                "created_at": datetime(2025, 6, 25),
                "symbol": "BTC-USDT",
                "instance_id": "bot-1",
            },
        ]

    async def test_fiscal_pdf_success(self):
        app = _make_app()
        trades = self._fiscal_trades()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/pdf/fiscal?year=2025")

        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"
        app.dependency_overrides.clear()

    async def test_fiscal_pdf_default_year(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/pdf/fiscal")

        assert resp.status_code == 200, resp.text
        assert resp.content[:5] == b"%PDF-"
        app.dependency_overrides.clear()

    async def test_fiscal_pdf_empty_trades(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/pdf/fiscal?year=2024")

        assert resp.status_code == 200, resp.text
        assert resp.content[:5] == b"%PDF-"
        app.dependency_overrides.clear()

    async def test_fiscal_pdf_content_disposition(self):
        app = _make_app()
        trades = self._fiscal_trades()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/export/pdf/fiscal?year=2025")

        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".pdf" in cd
        assert "2025" in cd
        app.dependency_overrides.clear()


# ── PEND-12: by-strategy ──────────────────────────────────────────────────────

class TestByStrategyEndpoint:
    """GET /analytics/by-strategy"""

    async def test_empty_trades_returns_empty_list(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/by-strategy")

        assert resp.status_code == 200, resp.text
        assert resp.json() == []
        app.dependency_overrides.clear()

    async def test_returns_strategy_metrics(self):
        app = _make_app()

        trades = [
            {
                "user_id": TEST_USER_ID,
                "pnl": 100.0,
                "strategy_name": "scalp",
                "bot_id": "bot1",
                "timestamp": datetime(2024, 1, 15, 10, 0),
            },
            {
                "user_id": TEST_USER_ID,
                "pnl": -20.0,
                "strategy_name": "scalp",
                "bot_id": "bot1",
                "timestamp": datetime(2024, 1, 16, 14, 0),
            },
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/by-strategy")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["strategy_name"] == "scalp"
        assert data[0]["num_trades"] == 2
        assert data[0]["total_pnl"] == pytest.approx(80.0)
        assert "bot1" in data[0]["bot_ids"]
        app.dependency_overrides.clear()

    async def test_multiple_strategies_sorted_by_pnl(self):
        app = _make_app()

        trades = [
            {"user_id": TEST_USER_ID, "pnl": 5.0, "strategy_name": "low", "timestamp": datetime(2024, 1, 1)},
            {"user_id": TEST_USER_ID, "pnl": 200.0, "strategy_name": "high", "timestamp": datetime(2024, 1, 2)},
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/by-strategy")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data[0]["strategy_name"] == "high"  # sorted desc by total_pnl
        app.dependency_overrides.clear()

    async def test_requires_authentication(self):
        from app.main import app as raw_app
        raw_app.dependency_overrides.clear()

        async with AsyncClient(
            transport=ASGITransport(app=raw_app),
            base_url="http://test",
        ) as ac:
            resp = await ac.get("/analytics/by-strategy")

        assert resp.status_code == 401


# ── PEND-12: heatmap ───────────────────────────────────────────────────────────

class TestHeatmapEndpoint:
    """GET /analytics/heatmap"""

    async def test_empty_trades_returns_168_cells(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/heatmap")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["cells"]) == 168
        assert data["days"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        assert len(data["hours"]) == 24
        app.dependency_overrides.clear()

    async def test_heatmap_cell_contains_correct_avg_pnl(self):
        app = _make_app()

        # 2024-01-15 = Monday (weekday=0), hour=9
        trades = [
            {"user_id": TEST_USER_ID, "pnl": 40.0, "timestamp": datetime(2024, 1, 15, 9, 0)},
            {"user_id": TEST_USER_ID, "pnl": 60.0, "timestamp": datetime(2024, 1, 15, 9, 0)},
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/heatmap")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        cell = next(c for c in data["cells"] if c["day"] == 0 and c["hour"] == 9)
        assert cell["avg_pnl"] == pytest.approx(50.0)
        assert cell["count"] == 2
        app.dependency_overrides.clear()

    async def test_heatmap_requires_authentication(self):
        from app.main import app as raw_app
        raw_app.dependency_overrides.clear()

        async with AsyncClient(
            transport=ASGITransport(app=raw_app),
            base_url="http://test",
        ) as ac:
            resp = await ac.get("/analytics/heatmap")

        assert resp.status_code == 401


# ── PEND-12: correlation ──────────────────────────────────────────────────────

class TestCorrelationEndpoint:
    """GET /analytics/correlation"""

    async def test_empty_trades_returns_empty_matrix(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM([]))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/correlation")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["bots"] == []
        assert data["matrix"] == []
        app.dependency_overrides.clear()

    async def test_two_bots_returns_2x2_matrix(self):
        app = _make_app()

        trades = [
            {"user_id": TEST_USER_ID, "pnl": 10.0, "bot_id": "b1", "timestamp": datetime(2024, 1, 1)},
            {"user_id": TEST_USER_ID, "pnl": 10.0, "bot_id": "b2", "timestamp": datetime(2024, 1, 1)},
            {"user_id": TEST_USER_ID, "pnl": 20.0, "bot_id": "b1", "timestamp": datetime(2024, 1, 2)},
            {"user_id": TEST_USER_ID, "pnl": 20.0, "bot_id": "b2", "timestamp": datetime(2024, 1, 2)},
        ]

        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.find = MagicMock(return_value=_ChainableCursorAM(trades))
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/analytics/correlation")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["bots"]) == 2
        assert len(data["matrix"]) == 2
        assert len(data["matrix"][0]) == 2
        # Identical series → off-diagonal should be 1.0
        b1i = data["bots"].index("b1")
        b2i = data["bots"].index("b2")
        assert data["matrix"][b1i][b1i] == pytest.approx(1.0)
        assert data["matrix"][b1i][b2i] == pytest.approx(1.0)
        app.dependency_overrides.clear()

    async def test_correlation_requires_authentication(self):
        from app.main import app as raw_app
        raw_app.dependency_overrides.clear()

        async with AsyncClient(
            transport=ASGITransport(app=raw_app),
            base_url="http://test",
        ) as ac:
            resp = await ac.get("/analytics/correlation")

        assert resp.status_code == 401
