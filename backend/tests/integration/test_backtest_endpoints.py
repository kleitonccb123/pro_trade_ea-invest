"""
Integration tests for backtest API endpoints.

Tests:
- GET  /api/backtest/symbols  — list available symbols
- POST /api/backtest/run      — run a backtest (mocked klines)
- GET  /api/backtest/{id}     — get result
- GET  /api/backtest/strategy/{id} — list history
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tests.conftest import TEST_USER_ID


@pytest.mark.integration
class TestBacktestEndpoints:

    async def test_list_symbols(self, client, auth_header):
        resp = await client.get("/api/backtest/symbols", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "symbols" in data
        assert "BTC-USDT" in data["symbols"]
        assert len(data["symbols"]) >= 10

    async def test_run_backtest_no_strategy(self, client, auth_header):
        """Should 404 when strategy doesn't exist."""
        resp = await client.post("/api/backtest/run", headers=auth_header, json={
            "strategy_id": "000000000000000000000000",
            "symbol": "BTC-USDT",
            "start_date": "2025-01-01",
            "end_date": "2025-09-01",
            "initial_capital": 1000,
            "short_period": 9,
            "long_period": 21,
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
        })
        assert resp.status_code in (404, 403)

    async def test_run_backtest_invalid_symbol(self, client, auth_header):
        """Should 400 for unsupported symbol."""
        resp = await client.post("/api/backtest/run", headers=auth_header, json={
            "strategy_id": "000000000000000000000000",
            "symbol": "FAKE-COIN",
            "start_date": "2025-01-01",
            "end_date": "2025-09-01",
            "initial_capital": 1000,
            "short_period": 9,
            "long_period": 21,
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
        })
        assert resp.status_code == 400

    async def test_run_backtest_invalid_periods(self, client, auth_header):
        """short_period >= long_period should be rejected."""
        resp = await client.post("/api/backtest/run", headers=auth_header, json={
            "strategy_id": "000000000000000000000000",
            "symbol": "BTC-USDT",
            "start_date": "2025-01-01",
            "end_date": "2025-09-01",
            "initial_capital": 1000,
            "short_period": 30,
            "long_period": 10,
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
        })
        assert resp.status_code == 400

    async def test_get_nonexistent_result(self, client, auth_header):
        """GET /api/backtest/<fake-id> should 404."""
        resp = await client.get("/api/backtest/nonexistent-id-123", headers=auth_header)
        assert resp.status_code == 404

    async def test_list_strategy_history_empty(self, client, auth_header):
        """GET /api/backtest/strategy/<id> should return empty list."""
        resp = await client.get("/api/backtest/strategy/000000000000000000000000", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
