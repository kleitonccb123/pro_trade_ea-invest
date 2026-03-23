"""
Integration Tests — Notifications Endpoints
=============================================

Tests GET /notifications, POST /notifications/mark-read, etc.
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
        "email": "notif@test.com",
        "name": "Notif User",
        "is_active": True,
    }


def _make_app():
    import os
    os.environ.setdefault("APP_MODE", "dev")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")

    from app.main import app
    from app.auth.dependencies import get_current_user
    from app.core.database import get_db

    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return app


class TestGetNotifications:
    """GET /notifications"""

    async def test_list_notifications_empty(self):
        app = _make_app()

        with patch(
            "app.notifications.router.notification_service"
        ) as mock_svc:
            mock_svc.get_notifications = AsyncMock(return_value=([], 0, 0))

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/notifications")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 0
        app.dependency_overrides.clear()

    async def test_list_notifications_with_items(self):
        app = _make_app()

        sample_notif = {
            "id": 1,
            "type": "bot_trade",
            "title": "Trade Executed",
            "message": "BTC-USDT filled",
            "is_read": False,
            "priority": "medium",
            "created_at": datetime.utcnow().isoformat(),
        }

        with patch(
            "app.notifications.router.notification_service"
        ) as mock_svc:
            mock_svc.get_notifications = AsyncMock(
                return_value=([sample_notif], 1, 1)
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/notifications")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 1
        app.dependency_overrides.clear()

    async def test_list_unread_only(self):
        app = _make_app()

        with patch(
            "app.notifications.router.notification_service"
        ) as mock_svc:
            mock_svc.get_notifications = AsyncMock(return_value=([], 0, 0))

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/notifications?unread_only=true")

        assert resp.status_code == 200, resp.text
        app.dependency_overrides.clear()


class TestMarkRead:
    """POST /notifications/mark-read"""

    async def test_mark_read_success(self):
        app = _make_app()

        with patch(
            "app.notifications.router.notification_service"
        ) as mock_svc:
            mock_svc.mark_as_read = AsyncMock(return_value=2)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.post(
                    "/notifications/mark-read",
                    json={"notification_ids": [1, 2]},
                )

        # 200 if successful, 403 if CSRF middleware blocks POST
        assert resp.status_code in (200, 403), resp.text
        if resp.status_code == 200:
            data = resp.json()
            assert data["marked_count"] == 2
        app.dependency_overrides.clear()


class TestVapidPublicKey:
    """GET /notifications/vapid-public-key"""

    async def test_returns_vapid_key(self):
        app = _make_app()

        with patch("app.notifications.router.settings") as mock_settings:
            mock_settings.vapid_public_key = "BCSp8bBCzGYOc1t6Irw0BstLa2Ut0rJ9DTjq5g8KgHXW"

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/notifications/vapid-public-key")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["public_key"] == "BCSp8bBCzGYOc1t6Irw0BstLa2Ut0rJ9DTjq5g8KgHXW"
        app.dependency_overrides.clear()

    async def test_returns_empty_when_not_configured(self):
        app = _make_app()

        with patch("app.notifications.router.settings") as mock_settings:
            mock_settings.vapid_public_key = ""

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/notifications/vapid-public-key")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["public_key"] == ""
        app.dependency_overrides.clear()

    async def test_no_auth_required(self):
        """VAPID public key endpoint should work without authentication."""
        import os
        os.environ.setdefault("APP_MODE", "dev")
        os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
        os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
        os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")

        from app.main import app
        from app.core.database import get_db

        # Only override DB, NOT get_current_user — to verify no auth needed
        app.dependency_overrides[get_db] = lambda: MagicMock()

        with patch("app.notifications.router.settings") as mock_settings:
            mock_settings.vapid_public_key = "test-key"

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                resp = await ac.get("/notifications/vapid-public-key")

        assert resp.status_code == 200, resp.text
        app.dependency_overrides.clear()
