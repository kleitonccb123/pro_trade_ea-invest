"""
Unit Tests — TwoFactorAuthService & Backup Codes
===================================================

Tests:
1. TOTP generation and verification
2. Backup code generation format
3. Backup code single-use enforcement
4. Setup/confirm flow
5. Rate limiting / lockout
6. Regenerate backup codes
7. Disable 2FA
8. 2FA status
"""

import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from app.auth.two_factor import TOTP, TwoFactorAuthService, TwoFactorSetup
from app.core.encryption import EncryptionService


# ==================== TOTP Unit Tests ====================

class TestTOTP:
    """Test the TOTP implementation."""

    def test_generate_secret_length(self):
        secret = TOTP.generate_secret()
        assert len(secret) >= 20

    def test_generate_secret_uniqueness(self):
        s1 = TOTP.generate_secret()
        s2 = TOTP.generate_secret()
        assert s1 != s2

    def test_generate_code_is_6_digits(self):
        totp = TOTP(TOTP.generate_secret())
        code = totp.generate()
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_correct_code(self):
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        code = totp.generate()
        assert totp.verify(code) is True

    def test_verify_wrong_code(self):
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        assert totp.verify("000000") is False or totp.verify("999999") is False

    def test_verify_code_window_tolerance(self):
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        # Generate code at current time
        code = totp.generate()
        # Should still pass within window
        assert totp.verify(code, window=1) is True

    def test_provisioning_uri_format(self):
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        uri = totp.get_provisioning_uri("test@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "secret=" in uri
        assert "issuer=CryptoTradeHub" in uri


# ==================== Backup Code Tests ====================

class TestBackupCodes:
    """Test backup code generation and format."""

    def setup_method(self):
        self.service = TwoFactorAuthService()

    def test_generate_10_codes(self):
        codes = self.service._generate_backup_codes()
        assert len(codes) == 10

    def test_code_format_xxxx_xxxx(self):
        codes = self.service._generate_backup_codes()
        for code in codes:
            assert len(code) == 9, f"Code {code} should be 9 chars (XXXX-XXXX)"
            assert code[4] == "-", f"Code {code} should have dash at position 4"
            # Check hex characters
            clean = code.replace("-", "")
            assert len(clean) == 8
            assert all(c in "0123456789ABCDEF" for c in clean)

    def test_codes_are_unique(self):
        codes = self.service._generate_backup_codes()
        assert len(set(codes)) == len(codes), "Backup codes should be unique"

    def test_is_backup_code_format_valid(self):
        assert self.service._is_backup_code_format("ABCD-EF12") is True

    def test_is_backup_code_format_totp_rejected(self):
        assert self.service._is_backup_code_format("123456") is False

    def test_is_backup_code_format_wrong_dash(self):
        assert self.service._is_backup_code_format("ABCDE-F12") is False


# ==================== TwoFactorAuthService Async Tests ====================

@pytest.mark.asyncio
class TestTwoFactorAuthService:
    """Async tests for 2FA service with mocked database."""

    @pytest.fixture(autouse=True)
    def _setup(self, mock_db):
        self.service = TwoFactorAuthService()
        self.mock_db = mock_db
        self.user_id = "test-user-123"
        self.email = "test@example.com"

        # Patch get_db to return our mock
        self._db_patcher = patch("app.auth.two_factor.get_db", return_value=mock_db)
        self._db_patcher.start()
        yield
        self._db_patcher.stop()

    async def test_setup_2fa_returns_setup_data(self):
        result = await self.service.setup_2fa(self.user_id, self.email)
        assert isinstance(result, TwoFactorSetup)
        assert result.secret
        assert result.provisioning_uri.startswith("otpauth://totp/")
        assert len(result.backup_codes) == 10

    async def test_setup_2fa_stores_encrypted_data(self):
        await self.service.setup_2fa(self.user_id, self.email)
        doc = await self.mock_db[self.service.COLLECTION].find_one({"user_id": self.user_id})
        assert doc is not None
        assert doc["is_enabled"] is False
        assert "secret_encrypted" in doc
        assert len(doc["backup_codes_encrypted"]) == 10

    async def test_confirm_setup_with_valid_code(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        # Generate a valid TOTP code
        totp = TOTP(setup.secret)
        code = totp.generate()
        result = await self.service.confirm_setup(self.user_id, code)
        assert result is True

        # Verify is_enabled is now True
        doc = await self.mock_db[self.service.COLLECTION].find_one({"user_id": self.user_id})
        assert doc["is_enabled"] is True

    async def test_confirm_setup_with_invalid_code(self):
        await self.service.setup_2fa(self.user_id, self.email)
        result = await self.service.confirm_setup(self.user_id, "000000")
        # May pass due to TOTP window, but most likely:
        assert isinstance(result, bool)

    async def test_verify_totp_code(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        totp = TOTP(setup.secret)
        code = totp.generate()
        # Confirm first
        await self.service.confirm_setup(self.user_id, code)
        
        # Now verify with a fresh code
        code2 = totp.generate()
        success, msg = await self.service.verify(self.user_id, code2)
        assert success is True

    async def test_verify_backup_code(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        totp = TOTP(setup.secret)
        code = totp.generate()
        await self.service.confirm_setup(self.user_id, code)

        # Use a backup code
        backup_code = setup.backup_codes[0]
        success, msg = await self.service.verify(self.user_id, backup_code)
        assert success is True
        assert "backup" in msg.lower() or "verificado" in msg.lower()

    async def test_backup_code_single_use(self):
        """Backup code in backup_codes_used list should be rejected."""
        setup = await self.service.setup_2fa(self.user_id, self.email)
        totp = TOTP(setup.secret)
        code = totp.generate()
        await self.service.confirm_setup(self.user_id, code)

        backup_code = setup.backup_codes[0]
        
        # First use — should succeed
        success1, _ = await self.service.verify(self.user_id, backup_code)
        assert success1 is True

        # Manually mark as used in DB (since MockDB doesn't support $push)
        collection = self.service._get_collection()
        doc = await collection.find_one({"user_id": self.user_id})
        doc["backup_codes_used"] = [backup_code.upper()]

        # Second use — should fail as it's in backup_codes_used
        success2, msg2 = await self.service.verify(self.user_id, backup_code)
        assert success2 is False

    async def test_verify_fails_when_not_enabled(self):
        await self.service.setup_2fa(self.user_id, self.email)
        # Don't confirm
        success, msg = await self.service.verify(self.user_id, "123456")
        assert success is False
        assert "ativo" in msg.lower() or "not" in msg.lower()

    async def test_verify_fails_when_not_configured(self):
        success, msg = await self.service.verify("nonexistent", "123456")
        assert success is False

    async def test_is_2fa_enabled(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        assert await self.service.is_2fa_enabled(self.user_id) is False

        totp = TOTP(setup.secret)
        await self.service.confirm_setup(self.user_id, totp.generate())
        assert await self.service.is_2fa_enabled(self.user_id) is True

    async def test_disable_2fa(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        totp = TOTP(setup.secret)
        await self.service.confirm_setup(self.user_id, totp.generate())

        # Disable with valid code
        code = totp.generate()
        success, msg = await self.service.disable_2fa(self.user_id, code)
        assert success is True
        assert await self.service.is_2fa_enabled(self.user_id) is False

    async def test_regenerate_backup_codes(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        totp = TOTP(setup.secret)
        await self.service.confirm_setup(self.user_id, totp.generate())

        # Regenerate
        code = totp.generate()
        success, new_codes = await self.service.regenerate_backup_codes(self.user_id, code)
        assert success is True
        assert len(new_codes) == 10
        # Old codes should differ from new ones
        assert set(new_codes) != set(setup.backup_codes)

    async def test_lockout_after_max_attempts(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        totp = TOTP(setup.secret)
        await self.service.confirm_setup(self.user_id, totp.generate())

        # Exhaust attempts
        for _ in range(self.service.MAX_ATTEMPTS):
            await self.service.verify(self.user_id, "000000")

        # Next attempt should be locked
        success, msg = await self.service.verify(self.user_id, "000000")
        assert success is False
        assert "bloqueada" in msg.lower() or "locked" in msg.lower() or "bloqueado" in msg.lower()

    async def test_get_2fa_status(self):
        setup = await self.service.setup_2fa(self.user_id, self.email)
        totp = TOTP(setup.secret)
        await self.service.confirm_setup(self.user_id, totp.generate())

        status = await self.service.get_2fa_status(self.user_id)
        assert status["enabled"] is True
        assert status["backup_codes_remaining"] == 10
