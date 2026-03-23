"""
Integration Tests — LGPD Endpoints
====================================

Tests DELETE /api/lgpd/account and GET /api/lgpd/export.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from httpx import ASGITransport, AsyncClient


TEST_USER_ID = "665f0c0a1234567890abcdef"


class _ChainableCursor:
    """Mock cursor supporting find().sort().skip().limit().to_list() chains."""

    def __init__(self, data=None):
        self._data = data or []

    def sort(self, *a, **kw):
        return self

    def skip(self, n):
        return self

    def limit(self, n):
        return self

    async def to_list(self, length=None):
        return self._data


def _mock_current_user():
    """Simulated dependency return value."""
    from app.core.security import get_password_hash
    return {
        "_id": TEST_USER_ID,
        "id": TEST_USER_ID,
        "email": "lgpd@test.com",
        "name": "LGPD User",
        "hashed_password": get_password_hash("StrongP@ss1"),
        "is_active": True,
        "plan": "free",
    }


def _make_app_with_user():
    """Build app with get_current_user overridden."""
    import os
    os.environ.setdefault("APP_MODE", "dev")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")

    from app.main import app
    from app.auth.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    return app


class TestDeleteAccount:
    """DELETE /api/lgpd/account"""

    async def test_delete_account_success(self):
        app = _make_app_with_user()

        mock_db = MagicMock()
        for coll_name in ["users", "bots", "admin_audit_log"]:
            coll = AsyncMock()
            coll.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            coll.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
            coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id="audit_id"))
            setattr(mock_db, coll_name, coll)

        with patch("app.auth.lgpd_router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.request(
                    "DELETE",
                    "/api/lgpd/account",
                    json={"password": "StrongP@ss1", "reason": "Testing LGPD"},
                )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert "grace_period_days" in data

        # Cleanup
        app.dependency_overrides.clear()

    async def test_delete_account_wrong_password(self):
        app = _make_app_with_user()

        mock_db = MagicMock()
        mock_db.users = AsyncMock()

        with patch("app.auth.lgpd_router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.request(
                    "DELETE",
                    "/api/lgpd/account",
                    json={"password": "WrongPassword1!", "reason": ""},
                )

        assert resp.status_code == 403, resp.text
        app.dependency_overrides.clear()


class TestExportData:
    """GET /api/lgpd/export"""

    async def test_export_returns_user_data(self):
        app = _make_app_with_user()

        from bson import ObjectId

        mock_db = MagicMock()

        # users.find_one — async
        user_doc = {
            "_id": ObjectId(TEST_USER_ID),
            "email": "lgpd@test.com",
            "name": "LGPD User",
            "is_active": True,
        }
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=user_doc)
        mock_db.users = mock_users

        # Collections using find().to_list() or find().sort().to_list()
        for coll_name in ["bots", "bot_trades", "notifications", "strategies"]:
            mock_coll = MagicMock()
            mock_coll.find = MagicMock(return_value=_ChainableCursor([]))
            setattr(mock_db, coll_name, mock_coll)

        # Collections using find_one (async)
        for coll_name in ["game_profiles", "affiliates"]:
            mock_coll = AsyncMock()
            mock_coll.find_one = AsyncMock(return_value=None)
            setattr(mock_db, coll_name, mock_coll)

        with patch("app.auth.lgpd_router.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/api/lgpd/export")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert "data" in data
        app.dependency_overrides.clear()
