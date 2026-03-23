"""
Integration Tests — EA Monitor Endpoints  (PEND-13)
=====================================================

Tests:
  POST  /ea/connect
  GET   /ea/accounts
  GET   /ea/{account_id}/positions
  POST  /ea/{account_id}/update   (EA push, authenticated by X-EA-Key)
  DELETE /ea/{account_id}
  WS    /ws/ea/{account_id}       (JWT auth via ?token=)
"""

import json
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

os.environ.setdefault("APP_MODE", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-ea-monitor")
os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_app():
    from app.main import app
    return app


def _make_token(user_id: str = "user_ea_001") -> str:
    """Return a valid JWT signed with the test secret."""
    from jose import jwt as jose_jwt
    return jose_jwt.encode(
        {"sub": user_id, "type": "access"},
        "test-secret-for-ea-monitor",
        algorithm="HS256",
    )


def _auth_headers(user_id: str = "user_ea_001") -> dict:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _mock_user(user_id: str = "user_ea_001"):
    return {
        "id": user_id,
        "email": "ea@test.com",
        "name": "EA Tester",
        "is_active": True,
        "hashed_password": "x",
        "plan": "PRO+",
    }


# ── POST /ea/connect ──────────────────────────────────────────────────────────

class TestEAConnect:
    """POST /api/ea/connect"""

    async def test_connect_success(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user())
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/ea/connect",
                    json={
                        "account_id": "1234567",
                        "account_name": "IC Markets Demo",
                        "server": "ICMarkets-Demo01",
                        "broker": "IC Markets",
                    },
                    headers=_auth_headers(),
                )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["account_id"] == "1234567"
        assert "api_key" in data
        assert len(data["api_key"]) >= 16

    async def test_connect_missing_account_id(self):
        app = _make_app()

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user())
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/ea/connect",
                    json={},  # missing required account_id
                    headers=_auth_headers(),
                )

        assert resp.status_code == 422  # Unprocessable Entity

    async def test_connect_unauthenticated(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/ea/connect",
                json={"account_id": "1234567"},
            )

        assert resp.status_code in (401, 403)


# ── GET /ea/accounts ─────────────────────────────────────────────────────────

class TestEAAccounts:
    """GET /api/ea/accounts"""

    async def test_list_accounts_empty(self):
        app = _make_app()

        # Clear any in-memory registry that might have been populated by earlier tests
        import app.ea_monitor.router as ea_router
        ea_router._registry.clear()

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user("user_new_001"))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/ea/accounts", headers=_auth_headers("user_new_001"))

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_accounts_after_connect(self):
        app = _make_app()
        user_id = "user_ea_list_001"

        import app.ea_monitor.router as ea_router
        # Seed registry directly
        ea_router._registry["9999001"] = {
            "owner_user_id": user_id,
            "api_key": "testkey123",
            "account_name": "Test Account",
            "server": "Server1",
            "broker": "Broker1",
            "last_seen": None,
            "balance": 10000.0,
            "equity": 10050.0,
            "positions": [],
            "telemetry": {},
        }

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/ea/accounts", headers=_auth_headers(user_id))

        # cleanup
        ea_router._registry.pop("9999001", None)

        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) == 1
        assert accounts[0]["account_id"] == "9999001"


# ── GET /ea/{account_id}/positions ───────────────────────────────────────────

class TestEAPositions:
    """GET /api/ea/{account_id}/positions"""

    async def test_positions_not_found(self):
        app = _make_app()

        import app.ea_monitor.router as ea_router
        ea_router._registry.pop("nonexistent_acct", None)

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user())
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(
                    "/api/ea/nonexistent_acct/positions", headers=_auth_headers()
                )

        assert resp.status_code == 404

    async def test_positions_success(self):
        app = _make_app()
        user_id = "user_pos_001"

        import app.ea_monitor.router as ea_router
        sample_positions = [
            {
                "id": 1001,
                "symbol": "EURUSD",
                "type": "BUY",
                "volume": 0.1,
                "open_price": 1.0850,
                "current_price": 1.0870,
                "sl": 1.0800,
                "tp": 1.0950,
                "profit": 20.0,
                "swap": -0.5,
                "open_time": "2026-03-12T09:00:00Z",
            }
        ]
        ea_router._registry["7777001"] = {
            "owner_user_id": user_id,
            "api_key": "poskey456",
            "account_name": "Pos Account",
            "server": "SrvA",
            "broker": "BrkA",
            "last_seen": "2026-03-12T10:00:00Z",
            "balance": 5000.0,
            "equity": 5020.0,
            "positions": sample_positions,
            "telemetry": {},
        }

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(
                    "/api/ea/7777001/positions", headers=_auth_headers(user_id)
                )

        ea_router._registry.pop("7777001", None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] == "7777001"
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "EURUSD"


# ── POST /ea/{account_id}/update (EA push) ───────────────────────────────────

class TestEAUpdate:
    """POST /api/ea/{account_id}/update — authenticated by X-EA-Key header"""

    async def test_update_success(self):
        app = _make_app()

        import app.ea_monitor.router as ea_router
        ea_router._registry["8888001"] = {
            "owner_user_id": "userX",
            "api_key": "secret_ea_key_abc",
            "account_name": "Update Account",
            "server": "SrvB",
            "broker": "BrkB",
            "last_seen": None,
            "balance": 0.0,
            "equity": 0.0,
            "positions": [],
            "telemetry": {},
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/ea/8888001/update",
                headers={"X-EA-Key": "secret_ea_key_abc"},
                json={
                    "balance": 12500.0,
                    "equity": 12550.0,
                    "positions": [],
                    "telemetry": {
                        "strategy_id": "EURUSD_M15",
                        "open_positions": 0,
                        "open_orders": 0,
                        "unrealized_pnl": 0,
                        "realized_pnl_today": 50.0,
                        "account_balance": 12500.0,
                        "account_equity": 12550.0,
                        "heartbeat": "2026-03-12T10:05:00Z",
                    },
                },
            )

        ea_router._registry.pop("8888001", None)

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_update_wrong_key(self):
        app = _make_app()

        import app.ea_monitor.router as ea_router
        ea_router._registry["8888002"] = {
            "owner_user_id": "userY",
            "api_key": "correct_key",
            "account_name": "Acct",
            "server": "S",
            "broker": "B",
            "last_seen": None,
            "balance": 0.0,
            "equity": 0.0,
            "positions": [],
            "telemetry": {},
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/ea/8888002/update",
                headers={"X-EA-Key": "WRONG_KEY"},
                json={"balance": 100.0, "equity": 100.0, "positions": [], "telemetry": {}},
            )

        ea_router._registry.pop("8888002", None)

        assert resp.status_code == 403

    async def test_update_account_not_found(self):
        app = _make_app()

        import app.ea_monitor.router as ea_router
        ea_router._registry.pop("missing_acct", None)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/ea/missing_acct/update",
                headers={"X-EA-Key": "any"},
                json={"balance": 0.0, "equity": 0.0, "positions": [], "telemetry": {}},
            )

        assert resp.status_code == 404


# ── DELETE /ea/{account_id} ───────────────────────────────────────────────────

class TestEADelete:
    """DELETE /api/ea/{account_id}"""

    async def test_delete_own_account(self):
        app = _make_app()
        user_id = "user_del_001"

        import app.ea_monitor.router as ea_router
        ea_router._registry["del_acct_1"] = {
            "owner_user_id": user_id,
            "api_key": "del_key",
            "account_name": "Delete Me",
            "server": "S",
            "broker": "B",
            "last_seen": None,
            "balance": 0.0,
            "equity": 0.0,
            "positions": [],
            "telemetry": {},
        }

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.delete(
                    "/api/ea/del_acct_1", headers=_auth_headers(user_id)
                )

        assert resp.status_code == 200
        assert "del_acct_1" not in ea_router._registry

    async def test_delete_others_account_forbidden(self):
        app = _make_app()

        import app.ea_monitor.router as ea_router
        ea_router._registry["del_acct_2"] = {
            "owner_user_id": "other_user",
            "api_key": "k",
            "account_name": "N",
            "server": "S",
            "broker": "B",
            "last_seen": None,
            "balance": 0.0,
            "equity": 0.0,
            "positions": [],
            "telemetry": {},
        }

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user("attacker_user"))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.ea_monitor.router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.delete(
                    "/api/ea/del_acct_2", headers=_auth_headers("attacker_user")
                )

        # cleanup
        ea_router._registry.pop("del_acct_2", None)

        assert resp.status_code == 403
