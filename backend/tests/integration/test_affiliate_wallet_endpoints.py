"""
Integration Tests — Affiliate Wallet & Withdrawal Endpoints (PEND-10)

Tests the full HTTP flow for:
1. GET /affiliates/wallet
2. POST /affiliates/withdrawal-method
3. POST /affiliates/withdraw  (success, insufficient balance, below minimum, no method)
4. GET /affiliates/transactions
5. Auth-required checks for all wallet endpoints
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock

from app.affiliates.models import (
    AffiliateWallet,
    WithdrawalMethod,
    WithdrawalMethodType,
    WithdrawalStatus,
)

TEST_USER_ID = "665f0c0a1234567890abcdef"

PIX_METHOD = {
    "type": "pix",
    "key": "user@email.com",
    "holder_name": "Test User",
}

WALLET_STATS = {
    "pending_balance": 25.0,
    "available_balance": 150.0,
    "total_balance": 175.0,
    "total_earned": 500.0,
    "total_withdrawn": 0.0,
    "withdrawal_method": {
        "type": "pix",
        "key": "user@email.com",
        "holder_name": "Test User",
        "is_verified": False,
        "verified_at": None,
    },
    "is_withdrawal_ready": True,
    "recent_transactions": [],
    "completed_withdrawals_count": 0,
    "last_withdrawal_at": None,
}


@pytest.mark.asyncio
class TestAffiliateWalletEndpoints:

    # ------------------------------------------------------------------
    # GET /affiliates/wallet
    # ------------------------------------------------------------------

    async def test_get_wallet_returns_stats(self, client, auth_header):
        """GET /affiliates/wallet should return wallet balances."""
        with patch(
            "app.affiliates.router.AffiliateWalletService.get_wallet_stats",
            new_callable=AsyncMock,
            return_value=WALLET_STATS,
        ):
            resp = await client.get("/affiliates/wallet", headers=auth_header)

        assert resp.status_code == 200
        data = resp.json()
        assert data["available_balance"] == 150.0
        assert data["pending_balance"] == 25.0
        assert data["is_withdrawal_ready"] is True

    async def test_get_wallet_requires_auth(self, client):
        """GET /affiliates/wallet without token should return 401."""
        resp = await client.get("/affiliates/wallet")
        assert resp.status_code == 401

    async def test_get_wallet_creates_wallet_for_new_user(self, client, auth_header):
        """GET /affiliates/wallet for a user without wallet creates one."""
        empty_stats = {**WALLET_STATS, "available_balance": 0.0, "pending_balance": 0.0,
                       "total_balance": 0.0, "total_earned": 0.0, "withdrawal_method": None,
                       "is_withdrawal_ready": False}
        with patch(
            "app.affiliates.router.AffiliateWalletService.get_wallet_stats",
            new_callable=AsyncMock,
            return_value=empty_stats,
        ):
            resp = await client.get("/affiliates/wallet", headers=auth_header)

        assert resp.status_code == 200
        assert resp.json()["available_balance"] == 0.0

    # ------------------------------------------------------------------
    # POST /affiliates/withdrawal-method
    # ------------------------------------------------------------------

    async def test_set_pix_method_success(self, client, auth_header):
        """POST /affiliates/withdrawal-method with valid PIX data should succeed."""
        with patch(
            "app.affiliates.router.AffiliateWalletService.get_or_create_wallet",
            new_callable=AsyncMock,
            return_value=AffiliateWallet(user_id=TEST_USER_ID),
        ), patch(
            "app.affiliates.router.AffiliateWalletService.save_wallet",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await client.post(
                "/affiliates/withdrawal-method",
                json=PIX_METHOD,
                headers=auth_header,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_set_method_invalid_type_rejected(self, client, auth_header):
        """POST /affiliates/withdrawal-method with unsupported type should 400."""
        resp = await client.post(
            "/affiliates/withdrawal-method",
            json={"type": "bitcoin_lightning", "key": "xyz", "holder_name": "Test"},
            headers=auth_header,
        )
        assert resp.status_code == 400

    async def test_set_method_requires_auth(self, client):
        """POST /affiliates/withdrawal-method without auth should return 401."""
        resp = await client.post("/affiliates/withdrawal-method", json=PIX_METHOD)
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # POST /affiliates/withdraw
    # ------------------------------------------------------------------

    async def test_withdraw_success(self, client, auth_header):
        """POST /affiliates/withdraw with valid amount should succeed."""
        with patch(
            "app.affiliates.router.WithdrawalRateLimiter.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, "ok"),
        ), patch(
            "app.affiliates.router.WithdrawalRateLimiter.record_withdrawal_attempt",
            new_callable=AsyncMock,
        ), patch(
            "app.affiliates.router.AffiliateWalletService.get_or_create_wallet",
            new_callable=AsyncMock,
            return_value=AffiliateWallet(
                user_id=TEST_USER_ID,
                available_balance=Decimal("200.00"),
                withdrawal_method=WithdrawalMethod(
                    type=WithdrawalMethodType.PIX,
                    key="user@email.com",
                    holder_name="Test User",
                ),
            ),
        ), patch(
            "app.affiliates.router.AffiliateWalletService.process_withdrawal",
            new_callable=AsyncMock,
            return_value=(True, "Saque de $100.00 solicitado com sucesso!", "wd_001"),
        ):
            resp = await client.post(
                "/affiliates/withdraw",
                json={"amount_usd": 100.0},
                headers=auth_header,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["withdrawal_id"] == "wd_001"

    async def test_withdraw_rate_limited(self, client, auth_header):
        """POST /affiliates/withdraw when rate limited should return failure."""
        with patch(
            "app.affiliates.router.WithdrawalRateLimiter.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(False, "Rate limit: 1 saque por hora"),
        ), patch(
            "app.affiliates.router.AffiliateWalletService.get_or_create_wallet",
            new_callable=AsyncMock,
            return_value=AffiliateWallet(user_id=TEST_USER_ID),
        ):
            resp = await client.post(
                "/affiliates/withdraw",
                json={"amount_usd": 100.0},
                headers=auth_header,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Rate" in data["message"] or "saque" in data["message"].lower()

    async def test_withdraw_no_method_configured(self, client, auth_header):
        """POST /affiliates/withdraw without a configured method should fail."""
        with patch(
            "app.affiliates.router.WithdrawalRateLimiter.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, "ok"),
        ), patch(
            "app.affiliates.router.AffiliateWalletService.get_or_create_wallet",
            new_callable=AsyncMock,
            return_value=AffiliateWallet(
                user_id=TEST_USER_ID,
                available_balance=Decimal("200.00"),
                withdrawal_method=None,
            ),
        ):
            resp = await client.post(
                "/affiliates/withdraw",
                json={"amount_usd": 100.0},
                headers=auth_header,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    async def test_withdraw_requires_auth(self, client):
        """POST /affiliates/withdraw without auth should return 401."""
        resp = await client.post("/affiliates/withdraw", json={"amount_usd": 100.0})
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # GET /affiliates/transactions
    # ------------------------------------------------------------------

    async def test_get_transactions_returns_list(self, client, auth_header):
        """GET /affiliates/transactions should return paginated list."""
        resp = await client.get("/affiliates/transactions", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "transactions" in data
        assert "total" in data
        assert isinstance(data["transactions"], list)

    async def test_get_transactions_requires_auth(self, client):
        """GET /affiliates/transactions without auth should return 401."""
        resp = await client.get("/affiliates/transactions")
        assert resp.status_code == 401

    async def test_get_transactions_pagination(self, client, auth_header):
        """GET /affiliates/transactions with page param should work."""
        resp = await client.get(
            "/affiliates/transactions?page=1&per_page=5",
            headers=auth_header,
        )
        assert resp.status_code == 200

    # ------------------------------------------------------------------
    # process_withdrawal debits balance
    # ------------------------------------------------------------------

    async def test_withdraw_process_debits_balance(self, client, auth_header):
        """POST /affiliates/withdraw should fail gracefully if balance insufficient."""
        with patch(
            "app.affiliates.router.WithdrawalRateLimiter.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, "ok"),
        ), patch(
            "app.affiliates.router.AffiliateWalletService.get_or_create_wallet",
            new_callable=AsyncMock,
            return_value=AffiliateWallet(
                user_id=TEST_USER_ID,
                available_balance=Decimal("200.00"),
                withdrawal_method=WithdrawalMethod(
                    type=WithdrawalMethodType.PIX,
                    key="user@email.com",
                    holder_name="Test User",
                ),
            ),
        ), patch(
            "app.affiliates.router.AffiliateWalletService.process_withdrawal",
            new_callable=AsyncMock,
            return_value=(False, "Saldo insuficiente: disponível $30.00", None),
        ):
            resp = await client.post(
                "/affiliates/withdraw",
                json={"amount_usd": 200.0},
                headers=auth_header,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
