"""
Unit Tests — Auth Service
==========================

Tests for JWT creation, token decoding, blacklist, and password hashing.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from app.auth import service as auth_service
from app.core.config import settings


# ── Token creation ────────────────────────────────────────────────────────────

class TestCreateAccessToken:
    def test_creates_valid_jwt(self):
        token = auth_service.create_access_token(subject="user123")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_token_contains_subject(self):
        token = auth_service.create_access_token(subject="user123")
        payload = auth_service.decode_token(token)
        assert payload["sub"] == "user123"

    def test_custom_expire_minutes(self):
        token = auth_service.create_access_token(subject="user123", expire_minutes=1)
        payload = auth_service.decode_token(token)
        exp = datetime.utcfromtimestamp(payload["exp"])
        # Should expire ~1 minute from now (with tolerance)
        assert (exp - datetime.utcnow()).total_seconds() < 120

    def test_scope_included_when_provided(self):
        token = auth_service.create_access_token(subject="user123", scope="admin")
        payload = auth_service.decode_token(token)
        assert payload["scope"] == "admin"

    def test_scope_absent_when_not_provided(self):
        token = auth_service.create_access_token(subject="user123")
        payload = auth_service.decode_token(token)
        assert "scope" not in payload


class TestCreateRefreshToken:
    def test_creates_valid_jwt(self):
        token = auth_service.create_refresh_token(subject="user123")
        payload = auth_service.decode_token(token)
        assert payload["sub"] == "user123"

    def test_refresh_token_has_longer_expiry(self):
        access = auth_service.create_access_token(subject="u1")
        refresh = auth_service.create_refresh_token(subject="u1")
        a_payload = auth_service.decode_token(access)
        r_payload = auth_service.decode_token(refresh)
        assert r_payload["exp"] > a_payload["exp"]


# ── Token decoding ────────────────────────────────────────────────────────────

class TestDecodeToken:
    def test_decodes_valid_token(self):
        token = auth_service.create_access_token(subject="abc")
        payload = auth_service.decode_token(token)
        assert payload["sub"] == "abc"
        assert "exp" in payload

    def test_rejects_tampered_token(self):
        token = auth_service.create_access_token(subject="abc")
        tampered = token[:-4] + "XXXX"
        from jose import JWTError
        with pytest.raises(JWTError):
            auth_service.decode_token(tampered)

    def test_rejects_expired_token(self):
        from jose import jwt, JWTError
        payload = {"sub": "abc", "exp": datetime.utcnow() - timedelta(hours=1)}
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.algorithm)
        with pytest.raises(JWTError):
            auth_service.decode_token(token)

    def test_rejects_wrong_secret(self):
        from jose import jwt, JWTError
        payload = {"sub": "abc", "exp": datetime.utcnow() + timedelta(hours=1)}
        token = jwt.encode(payload, "wrong-secret", algorithm=settings.algorithm)
        with pytest.raises(JWTError):
            auth_service.decode_token(token)


# ── Token blacklist (in-memory fallback) ──────────────────────────────────────

class TestTokenBlacklist:
    async def test_token_not_blacklisted_initially(self):
        result = await auth_service.is_blacklisted("some-token-xyz")
        assert result is False

    async def test_add_and_check_blacklist(self):
        await auth_service.add_to_blacklist("revoked-token-1", expire_seconds=300)
        assert await auth_service.is_blacklisted("revoked-token-1") is True

    async def test_different_token_not_blacklisted(self):
        await auth_service.add_to_blacklist("revoked-token-2", expire_seconds=300)
        assert await auth_service.is_blacklisted("other-token") is False


# ── Password hashing ─────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_and_verify(self):
        from app.core.security import get_password_hash, verify_password
        hashed = get_password_hash("MyP@ssw0rd!")
        assert verify_password("MyP@ssw0rd!", hashed) is True

    def test_wrong_password_fails(self):
        from app.core.security import get_password_hash, verify_password
        hashed = get_password_hash("MyP@ssw0rd!")
        assert verify_password("WrongPass1!", hashed) is False

    def test_hash_is_not_plaintext(self):
        from app.core.security import get_password_hash
        hashed = get_password_hash("Secret123!")
        assert hashed != "Secret123!"
        assert len(hashed) > 20

    def test_different_hashes_for_same_password(self):
        from app.core.security import get_password_hash
        h1 = get_password_hash("Same@Pass1")
        h2 = get_password_hash("Same@Pass1")
        # bcrypt salts should produce different hashes
        assert h1 != h2
