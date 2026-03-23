"""
Integration Tests — 2FA Endpoints
====================================

Tests the full HTTP flow for:
1. POST /auth/2fa/setup
2. POST /auth/2fa/confirm
3. GET /auth/2fa/status
4. POST /auth/2fa/complete (login with 2FA)
5. POST /auth/2fa/backup-codes (regenerate)
6. POST /auth/2fa/disable
7. Session invalidation on 2FA toggle
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.auth.two_factor import TOTP, TwoFactorSetup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TEST_USER_ID = "665f0c0a1234567890abcdef"
TEST_USER_EMAIL = "test@cryptotradehub.com"


@pytest.fixture()
def two_fa_mocks():
    """Configure mocks for 2FA service methods."""
    backup_codes = [f"ABCD-{i:04d}" for i in range(10)]
    secret = TOTP.generate_secret()
    
    setup_return = TwoFactorSetup(
        secret=secret,
        provisioning_uri=f"otpauth://totp/CryptoTradeHub:{TEST_USER_EMAIL}?secret={secret}",
        backup_codes=backup_codes,
    )
    
    return {
        "secret": secret,
        "backup_codes": backup_codes,
        "setup_return": setup_return,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestTwoFactorEndpoints:
    """Integration tests for 2FA API endpoints."""

    async def test_setup_2fa(self, client, auth_header, two_fa_mocks):
        """POST /auth/2fa/setup should return secret and backup codes."""
        with patch(
            "app.auth.two_factor_router.two_factor_service.setup_2fa",
            new_callable=AsyncMock,
            return_value=two_fa_mocks["setup_return"],
        ):
            resp = await client.post("/api/auth/2fa/setup", headers=auth_header)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "backup_codes" in data
        assert len(data["backup_codes"]) == 10

    async def test_confirm_2fa_valid_code(self, client, auth_header):
        """POST /auth/2fa/confirm with valid code should enable 2FA."""
        with patch(
            "app.auth.two_factor_router.two_factor_service.confirm_setup",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "app.auth.two_factor_router.session_manager.revoke_all_sessions",
            new_callable=AsyncMock,
            return_value=0,
        ):
            resp = await client.post(
                "/api/auth/2fa/confirm",
                headers=auth_header,
                json={"code": "123456"},
            )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_confirm_2fa_invalid_code(self, client, auth_header):
        """POST /auth/2fa/confirm with invalid code should fail."""
        with patch(
            "app.auth.two_factor_router.two_factor_service.confirm_setup",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = await client.post(
                "/api/auth/2fa/confirm",
                headers=auth_header,
                json={"code": "000000"},
            )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    async def test_2fa_status(self, client, auth_header):
        """GET /auth/2fa/status should return enabled status."""
        with patch(
            "app.auth.two_factor_router.two_factor_service.get_2fa_status",
            new_callable=AsyncMock,
            return_value={
                "enabled": True,
                "setup_started": True,
                "backup_codes_remaining": 8,
                "last_verification": None,
            },
        ):
            resp = await client.get("/api/auth/2fa/status", headers=auth_header)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    async def test_complete_2fa_login_with_totp(self, client, two_fa_mocks):
        """POST /auth/2fa/complete should exchange pending_token + code for access token."""
        from app.auth.service import create_access_token
        pending_token = create_access_token(subject=TEST_USER_ID, scope="2fa_pending", expire_minutes=5)
        
        with patch(
            "app.auth.two_factor_router.two_factor_service.verify",
            new_callable=AsyncMock,
            return_value=(True, "Código verificado"),
        ):
            resp = await client.post(
                "/api/auth/2fa/complete",
                json={"pending_token": pending_token, "code": "123456"},
            )
        
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_complete_2fa_login_with_backup_code(self, client, two_fa_mocks):
        """POST /auth/2fa/complete with backup code should work."""
        from app.auth.service import create_access_token
        pending_token = create_access_token(subject=TEST_USER_ID, scope="2fa_pending", expire_minutes=5)
        
        with patch(
            "app.auth.two_factor_router.two_factor_service.verify",
            new_callable=AsyncMock,
            return_value=(True, "Backup code usado"),
        ):
            resp = await client.post(
                "/api/auth/2fa/complete",
                json={"pending_token": pending_token, "code": "ABCD-0001"},
            )
        
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_regenerate_backup_codes(self, client, auth_header, two_fa_mocks):
        """POST /auth/2fa/backup-codes should return new codes."""
        new_codes = [f"NEWC-{i:04d}" for i in range(10)]
        
        with patch(
            "app.auth.two_factor_router.two_factor_service.regenerate_backup_codes",
            new_callable=AsyncMock,
            return_value=(True, new_codes),
        ):
            resp = await client.post(
                "/api/auth/2fa/backup-codes",
                headers=auth_header,
                json={"code": "123456"},
            )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["backup_codes"]) == 10

    async def test_disable_2fa_with_session_invalidation(self, client, auth_header):
        """POST /auth/2fa/disable should disable 2FA and invalidate sessions."""
        with patch(
            "app.auth.two_factor_router.two_factor_service.disable_2fa",
            new_callable=AsyncMock,
            return_value=(True, "2FA desativado com sucesso"),
        ), patch(
            "app.auth.two_factor_router.session_manager.revoke_all_sessions",
            new_callable=AsyncMock,
            return_value=3,
        ) as mock_revoke:
            resp = await client.post(
                "/api/auth/2fa/disable",
                headers=auth_header,
                json={"code": "123456"},
            )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # Verify session invalidation was called
        mock_revoke.assert_called_once()

    async def test_setup_requires_auth(self, client):
        """2FA setup without auth should return 401."""
        resp = await client.post("/api/auth/2fa/setup")
        assert resp.status_code in (401, 403)

    async def test_status_requires_auth(self, client):
        """2FA status without auth should return 401."""
        resp = await client.get("/api/auth/2fa/status")
        assert resp.status_code in (401, 403)
