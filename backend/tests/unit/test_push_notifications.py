"""
Unit Tests — Push Notification Sending (_send_push_notification)
================================================================

Tests the pywebpush integration, email fallback, and stale subscription cleanup.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.notifications.service import NotificationService


@pytest.fixture
def svc():
    return NotificationService()


@pytest.fixture
def sample_notification():
    return {
        "_id": "abc123",
        "title": "Price Alert",
        "message": "BTC reached $70,000",
        "type": "price_alert",
        "data": {"symbol": "BTCUSDT"},
    }


@pytest.fixture
def sample_prefs():
    return {
        "push_subscription": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2w...",
                "auth": "tBHItJI5svbpC7htE...",
            },
        },
        "push_enabled": True,
        "email_enabled": True,
        "email_address": "test@example.com",
    }


class TestSendPushNotification:
    """Tests for NotificationService._send_push_notification"""

    async def test_no_subscription_falls_back_to_email(self, svc, sample_notification):
        """When user has no push subscription, fallback to email."""
        prefs_no_sub = {"push_subscription": None}

        with patch.object(svc, "_send_email_notification", new_callable=AsyncMock) as mock_email:
            await svc._send_push_notification("user1", sample_notification, prefs_no_sub)
            mock_email.assert_awaited_once_with("user1", sample_notification, prefs_no_sub)

    async def test_empty_endpoint_falls_back_to_email(self, svc, sample_notification):
        """When subscription has empty endpoint, fallback to email."""
        prefs_empty = {"push_subscription": {"endpoint": "", "keys": {}}}

        with patch.object(svc, "_send_email_notification", new_callable=AsyncMock) as mock_email:
            await svc._send_push_notification("user1", sample_notification, prefs_empty)
            mock_email.assert_awaited_once()

    async def test_no_vapid_keys_falls_back_to_email(self, svc, sample_notification, sample_prefs):
        """When VAPID private key is missing, fallback to email."""
        mock_settings = MagicMock()
        mock_settings.vapid_private_key = ""
        mock_settings.vapid_claims_email = "mailto:admin@example.com"

        with (
            patch("app.notifications.service.get_db"),
            patch.object(svc, "_send_email_notification", new_callable=AsyncMock) as mock_email,
            patch("app.core.config.settings", mock_settings),
        ):
            await svc._send_push_notification("user1", sample_notification, sample_prefs)
            mock_email.assert_awaited_once()

    async def test_successful_push_delivery(self, svc, sample_notification, sample_prefs):
        """When everything is configured, webpush is called and email is NOT called."""
        mock_settings = MagicMock()
        mock_settings.vapid_private_key = "-----BEGIN EC PRIVATE KEY-----\nfake\n-----END EC PRIVATE KEY-----"
        mock_settings.vapid_claims_email = "mailto:admin@example.com"

        with (
            patch("app.core.config.settings", mock_settings),
            patch("pywebpush.webpush") as mock_webpush,
            patch.object(svc, "_send_email_notification", new_callable=AsyncMock) as mock_email,
        ):
            await svc._send_push_notification("user1", sample_notification, sample_prefs)

            mock_webpush.assert_called_once()
            call_kwargs = mock_webpush.call_args
            assert call_kwargs[1]["subscription_info"] == sample_prefs["push_subscription"]
            assert call_kwargs[1]["vapid_private_key"] == mock_settings.vapid_private_key
            mock_email.assert_not_awaited()

    async def test_push_failure_falls_back_to_email(self, svc, sample_notification, sample_prefs):
        """When webpush raises an exception, fallback to email."""
        mock_settings = MagicMock()
        mock_settings.vapid_private_key = "-----BEGIN EC PRIVATE KEY-----\nfake\n-----END EC PRIVATE KEY-----"
        mock_settings.vapid_claims_email = "mailto:admin@example.com"

        with (
            patch("app.core.config.settings", mock_settings),
            patch("pywebpush.webpush", side_effect=Exception("Connection refused")),
            patch.object(svc, "_send_email_notification", new_callable=AsyncMock) as mock_email,
            patch("app.notifications.service.get_db") as mock_get_db,
        ):
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            await svc._send_push_notification("user1", sample_notification, sample_prefs)
            mock_email.assert_awaited_once()

    async def test_expired_subscription_410_cleans_up(self, svc, sample_notification, sample_prefs):
        """When push returns 410 (Gone), subscription is cleared from DB."""
        mock_settings = MagicMock()
        mock_settings.vapid_private_key = "-----BEGIN EC PRIVATE KEY-----\nfake\n-----END EC PRIVATE KEY-----"
        mock_settings.vapid_claims_email = "mailto:admin@example.com"

        mock_db_collection = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_db_collection)

        with (
            patch("app.core.config.settings", mock_settings),
            patch("pywebpush.webpush", side_effect=Exception("410 Gone")),
            patch("app.notifications.service.get_db", return_value=mock_db),
            patch.object(svc, "_send_email_notification", new_callable=AsyncMock) as mock_email,
        ):
            await svc._send_push_notification("user1", sample_notification, sample_prefs)

            # Should have tried to clear subscription
            mock_db_collection.update_one.assert_awaited_once_with(
                {"user_id": "user1"},
                {"$set": {"push_subscription": None, "push_enabled": False}},
            )
            # Should still fallback to email
            mock_email.assert_awaited_once()

    async def test_expired_subscription_404_cleans_up(self, svc, sample_notification, sample_prefs):
        """When push returns 404, subscription is also cleared."""
        mock_settings = MagicMock()
        mock_settings.vapid_private_key = "-----BEGIN EC PRIVATE KEY-----\nfake\n-----END EC PRIVATE KEY-----"
        mock_settings.vapid_claims_email = "mailto:admin@example.com"

        mock_db_collection = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_db_collection)

        with (
            patch("app.core.config.settings", mock_settings),
            patch("pywebpush.webpush", side_effect=Exception("404 not found")),
            patch("app.notifications.service.get_db", return_value=mock_db),
            patch.object(svc, "_send_email_notification", new_callable=AsyncMock),
        ):
            await svc._send_push_notification("user1", sample_notification, sample_prefs)

            mock_db_collection.update_one.assert_awaited_once()

    async def test_none_prefs_falls_back_to_email(self, svc, sample_notification):
        """When prefs is None, fallback to email."""
        with patch.object(svc, "_send_email_notification", new_callable=AsyncMock) as mock_email:
            await svc._send_push_notification("user1", sample_notification, None)
            mock_email.assert_awaited_once()

    async def test_push_payload_contains_correct_fields(self, svc, sample_notification, sample_prefs):
        """Verify the JSON payload sent to webpush has correct structure."""
        import json

        mock_settings = MagicMock()
        mock_settings.vapid_private_key = "-----BEGIN EC PRIVATE KEY-----\nfake\n-----END EC PRIVATE KEY-----"
        mock_settings.vapid_claims_email = "mailto:admin@example.com"

        with (
            patch("app.core.config.settings", mock_settings),
            patch("pywebpush.webpush") as mock_webpush,
            patch.object(svc, "_send_email_notification", new_callable=AsyncMock),
        ):
            await svc._send_push_notification("user1", sample_notification, sample_prefs)

            payload_str = mock_webpush.call_args[1]["data"]
            payload = json.loads(payload_str)

            assert payload["title"] == "Price Alert"
            assert payload["body"] == "BTC reached $70,000"
            assert payload["tag"] == "price_alert"
            assert payload["data"]["notification_id"] == "abc123"
            assert payload["data"]["symbol"] == "BTCUSDT"
            assert payload["icon"] == "/favicon.ico"
