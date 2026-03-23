"""
Unit Tests — Helpers & Utilities
=================================

Tests for centralized helper functions like email validation,
get_user_id extraction patterns, and settings validators.
"""

import pytest

from app.auth.router import validate_email_format


class TestEmailValidation:
    @pytest.mark.parametrize("email", [
        "user@example.com",
        "user+tag@domain.co.uk",
        "first.last@sub.domain.org",
        "test123@gmail.com",
    ])
    def test_valid_emails(self, email):
        assert validate_email_format(email) is True

    @pytest.mark.parametrize("email", [
        "",
        "not-an-email",
        "@domain.com",
        "user@",
        "user@.com",
        "a" * 255 + "@test.com",  # exceeds 254 char limit
    ])
    def test_invalid_emails(self, email):
        assert validate_email_format(email) is False

    def test_none_email(self):
        assert validate_email_format(None) is False


class TestGetUserIdPatterns:
    """Test the pattern used across routers to extract user_id from current_user."""

    def test_extract_from_id_key(self):
        user = {"id": "abc123", "_id": "xyz789"}
        user_id = str(user.get("id") or user.get("_id"))
        assert user_id == "abc123"

    def test_extract_from_underscore_id(self):
        user = {"_id": "xyz789"}
        user_id = str(user.get("id") or user.get("_id"))
        assert user_id == "xyz789"

    def test_fallback_none(self):
        user = {}
        user_id = user.get("id") or user.get("_id")
        assert user_id is None


class TestSettingsDefaults:
    """Ensure settings have sensible defaults for dev mode."""

    def test_algorithm_is_hs256(self):
        from app.core.config import settings
        assert settings.algorithm == "HS256"

    def test_access_token_expire_positive(self):
        from app.core.config import settings
        assert settings.access_token_expire_minutes > 0

    def test_refresh_token_longer_than_access(self):
        from app.core.config import settings
        assert settings.refresh_token_expire_minutes > settings.access_token_expire_minutes
