"""
Integration Tests — Auth Endpoints
====================================

Tests register, login, refresh, logout endpoints via HTTPX AsyncClient.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Build a patched app suitable for testing auth endpoints."""
    import os
    os.environ.setdefault("APP_MODE", "dev")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")

    from app.core.database import MockDatabase
    from app.main import app
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegisterEndpoint:
    """POST /api/auth/register"""

    async def test_register_success(self):
        app = _make_app()

        mock_db = MagicMock()
        # users collection
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=None)  # no existing user
        mock_users.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="new_id_123")
        )
        mock_db.__getitem__ = lambda self, k: mock_users if k == "users" else AsyncMock()
        mock_db.users = mock_users

        # Gamification profiles
        mock_gp = AsyncMock()
        mock_gp.find_one = AsyncMock(return_value=None)
        mock_gp.insert_one = AsyncMock(return_value=MagicMock(inserted_id="gp_id"))
        mock_db.game_profiles = mock_gp

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.auth.router.check_rate_limit_async",
                   new_callable=AsyncMock, return_value=(True, {})), \
             patch("app.gamification.service.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post("/api/auth/register", json={
                    "email": "newuser@test.com",
                    "password": "StrongP@ss1",
                    "name": "New User",
                })

            assert resp.status_code in (201, 200), resp.text

    async def test_register_weak_password(self):
        app = _make_app()

        with patch("app.auth.router.check_rate_limit_async",
                   new_callable=AsyncMock, return_value=(True, {})):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post("/api/auth/register", json={
                    "email": "weak@test.com",
                    "password": "123",
                    "name": "Weak",
                })

            # Should be rejected by password validation
            assert resp.status_code in (400, 422), resp.text

    async def test_register_invalid_email(self):
        app = _make_app()

        with patch("app.auth.router.check_rate_limit_async",
                   new_callable=AsyncMock, return_value=(True, {})):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post("/api/auth/register", json={
                    "email": "not-an-email",
                    "password": "StrongP@ss1",
                    "name": "Bad Email",
                })

            assert resp.status_code in (400, 422), resp.text

    async def test_register_rate_limited(self):
        app = _make_app()

        with patch("app.auth.router.check_rate_limit_async",
                   new_callable=AsyncMock,
                   return_value=(False, {"reset_in_seconds": 3600})):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post("/api/auth/register", json={
                    "email": "rate@test.com",
                    "password": "StrongP@ss1",
                    "name": "Rate Limited",
                })

            assert resp.status_code == 429


class TestLoginEndpoint:
    """POST /api/auth/login"""

    async def test_login_missing_fields(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/api/auth/login", json={})

        assert resp.status_code == 422  # Pydantic validation error

    async def test_login_invalid_email_format(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/api/auth/login", json={
                "email": "invalid-email",
                "password": "test123",
            })

        # Pydantic EmailStr will reject this
        assert resp.status_code in (400, 422), resp.text


class TestTokenRefresh:
    """POST /api/auth/refresh"""

    async def test_refresh_no_cookie(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/api/auth/refresh")

        # 403 = CSRF middleware blocks, 401/400/422 = auth/validation error
        assert resp.status_code in (401, 400, 403, 422), resp.text


class TestLogout:
    """POST /api/auth/logout"""

    async def test_logout_no_token(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            resp = await ac.post("/api/auth/logout")

        # 403 = CSRF middleware blocks, 401/200 = auth/success
        assert resp.status_code in (401, 200, 403), resp.text
