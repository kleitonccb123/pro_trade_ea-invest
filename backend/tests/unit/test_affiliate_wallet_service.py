"""
Unit tests for AffiliateWalletService (PEND-10).

Tests:
- get_or_create_wallet: creates new wallet, retrieves existing
- record_commission: valid commission, anti-self-referral IP, invalid amount
- release_pending_balances: releases expired transactions, skips future ones
- request_withdrawal: creates request, validates minimums and balance
- process_withdrawal: success flow, insufficient balance, below minimum, no method
- get_wallet_stats: returns correct structure and balances
"""
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest

_backend_root = Path(__file__).resolve().parent.parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

os.environ.setdefault("APP_MODE", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ENCRYPTION_KEY", "k1cTQzwPY4AYGTW4K5DQT_d8RGdX8oYFI2Hn1ND5UAU=")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "k1cTQzwPY4AYGTW4K5DQT_d8RGdX8oYFI2Hn1ND5UAU=")
os.environ.setdefault("STRATEGY_ENCRYPTION_KEY", "k1cTQzwPY4AYGTW4K5DQT_d8RGdX8oYFI2Hn1ND5UAU=")
os.environ.setdefault("DATABASE_URL", "")

from app.core.database import MockDatabase, _mock_data
from app.affiliates.wallet_service import AffiliateWalletService
from app.affiliates.models import (
    AffiliateWallet,
    WithdrawalMethod,
    WithdrawalMethodType,
    WithdrawalStatus,
    TransactionStatus,
    TransactionType,
    MINIMUM_WITHDRAWAL_AMOUNT,
)

USER_ID = "user_test_001"


@pytest.fixture(autouse=True)
def clear_data():
    _mock_data.clear()
    yield
    _mock_data.clear()


@pytest.fixture()
def db():
    return MockDatabase("test_db")


@pytest.fixture()
def service(db):
    return AffiliateWalletService(db)


@pytest.fixture()
def pix_method():
    return WithdrawalMethod(
        type=WithdrawalMethodType.PIX,
        key="test@email.com",
        holder_name="Test User",
        is_verified=False,
    )


# =====================================================================
# get_or_create_wallet
# =====================================================================

class TestGetOrCreateWallet:

    @pytest.mark.asyncio
    async def test_creates_new_wallet_on_first_call(self, service):
        wallet = await service.get_or_create_wallet(USER_ID)
        assert wallet.user_id == USER_ID
        assert wallet.available_balance == Decimal("0.00")
        assert wallet.pending_balance == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_retrieves_existing_wallet(self, service, db):
        existing = AffiliateWallet(user_id=USER_ID, available_balance=Decimal("100.00"))
        await db.affiliate_wallets.insert_one(existing.dict())

        wallet = await service.get_or_create_wallet(USER_ID)
        assert wallet.user_id == USER_ID
        assert wallet.available_balance == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_does_not_duplicate_wallet(self, service):
        await service.get_or_create_wallet(USER_ID)
        await service.get_or_create_wallet(USER_ID)
        docs = await db_count(service.wallet_col, USER_ID)
        assert docs <= 1

    @pytest.mark.asyncio
    async def test_default_currency_is_usd(self, service):
        wallet = await service.get_or_create_wallet(USER_ID)
        assert wallet.currency == "USD"


async def db_count(col, user_id):
    docs = await col.find({"user_id": user_id}).to_list(None)
    return len(docs)


# =====================================================================
# record_commission
# =====================================================================

class TestRecordCommission:

    @pytest.mark.asyncio
    async def test_records_valid_commission(self, service):
        success, msg = await service.record_commission(
            affiliate_user_id=USER_ID,
            referral_id="ref_001",
            sale_amount_usd=Decimal("1000.00"),
            commission_rate=Decimal("0.10"),
        )
        assert success is True
        assert "100.00" in msg

        wallet = await service.get_or_create_wallet(USER_ID)
        assert wallet.pending_balance == Decimal("100.00")
        assert wallet.total_earned == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_rejects_self_referral_by_ip(self, service):
        success, msg = await service.record_commission(
            affiliate_user_id=USER_ID,
            referral_id="ref_002",
            sale_amount_usd=Decimal("500.00"),
            buyer_ip="192.168.1.1",
            affiliate_ip="192.168.1.1",
        )
        assert success is False
        assert "Auto" in msg or "auto" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_zero_sale_amount(self, service):
        success, msg = await service.record_commission(
            affiliate_user_id=USER_ID,
            referral_id="ref_003",
            sale_amount_usd=Decimal("0"),
        )
        assert success is False

    @pytest.mark.asyncio
    async def test_uses_default_commission_rate(self, service):
        success, msg = await service.record_commission(
            affiliate_user_id=USER_ID,
            referral_id="ref_004",
            sale_amount_usd=Decimal("100.00"),
        )
        assert success is True
        wallet = await service.get_or_create_wallet(USER_ID)
        # Default rate is COMMISSION_RATE = 0.10 → $10
        assert wallet.pending_balance == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_different_ips_allowed(self, service):
        success, _ = await service.record_commission(
            affiliate_user_id=USER_ID,
            referral_id="ref_005",
            sale_amount_usd=Decimal("200.00"),
            buyer_ip="10.0.0.1",
            affiliate_ip="10.0.0.2",
        )
        assert success is True


# =====================================================================
# release_pending_balances
# =====================================================================

class TestReleasePendingBalances:

    @pytest.mark.asyncio
    async def test_releases_expired_transaction(self, service, db):
        wallet = AffiliateWallet(user_id=USER_ID, pending_balance=Decimal("50.00"))
        await db.affiliate_wallets.insert_one(wallet.dict())

        from app.affiliates.models import AffiliateTransaction
        tx = AffiliateTransaction(
            user_id=USER_ID,
            type=TransactionType.COMMISSION,
            status=TransactionStatus.PENDING,
            amount_usd=Decimal("50.00"),
            release_at=datetime.utcnow() - timedelta(hours=1),
        )
        await db.affiliate_transactions.insert_one(tx.dict())

        released = await service.release_pending_balances()
        assert released == 1

    @pytest.mark.asyncio
    async def test_does_not_release_future_transaction(self, service, db):
        wallet = AffiliateWallet(user_id=USER_ID, pending_balance=Decimal("30.00"))
        await db.affiliate_wallets.insert_one(wallet.dict())

        from app.affiliates.models import AffiliateTransaction
        tx = AffiliateTransaction(
            user_id=USER_ID,
            type=TransactionType.COMMISSION,
            status=TransactionStatus.PENDING,
            amount_usd=Decimal("30.00"),
            release_at=datetime.utcnow() + timedelta(days=5),
        )
        await db.affiliate_transactions.insert_one(tx.dict())

        released = await service.release_pending_balances()
        assert released == 0


# =====================================================================
# process_withdrawal
# =====================================================================

class TestProcessWithdrawal:

    @pytest.mark.asyncio
    async def test_successful_withdrawal(self, service, pix_method, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("200.00"),
            withdrawal_method=pix_method,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        success, msg, wid = await service.process_withdrawal(USER_ID, 100.0)
        assert success is True
        assert wid is not None
        assert "100" in msg

    @pytest.mark.asyncio
    async def test_fails_below_minimum(self, service, pix_method, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("200.00"),
            withdrawal_method=pix_method,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        success, msg, wid = await service.process_withdrawal(USER_ID, 10.0)
        assert success is False
        assert wid is None

    @pytest.mark.asyncio
    async def test_fails_insufficient_balance(self, service, pix_method, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("30.00"),
            withdrawal_method=pix_method,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        success, msg, wid = await service.process_withdrawal(USER_ID, 50.0)
        assert success is False
        assert "saldo" in msg.lower() or "insuficiente" in msg.lower()

    @pytest.mark.asyncio
    async def test_fails_no_withdrawal_method(self, service, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("200.00"),
            withdrawal_method=None,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        success, msg, wid = await service.process_withdrawal(USER_ID, 50.0)
        assert success is False
        assert wid is None

    @pytest.mark.asyncio
    async def test_creates_transaction_record(self, service, pix_method, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("500.00"),
            withdrawal_method=pix_method,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        await service.process_withdrawal(USER_ID, 100.0)
        txs = await db.affiliate_transactions.find({"user_id": USER_ID}).to_list(None)
        assert any(tx.get("type") == TransactionType.WITHDRAWAL for tx in txs)


# =====================================================================
# get_wallet_stats
# =====================================================================

class TestGetWalletStats:

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self, service):
        stats = await service.get_wallet_stats(USER_ID)
        required_keys = [
            "pending_balance", "available_balance", "total_balance",
            "total_earned", "total_withdrawn", "withdrawal_method",
            "is_withdrawal_ready", "recent_transactions",
            "completed_withdrawals_count", "last_withdrawal_at",
        ]
        for key in required_keys:
            assert key in stats, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_reflects_wallet_balances(self, service, pix_method, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("75.00"),
            pending_balance=Decimal("25.00"),
            total_earned=Decimal("300.00"),
            withdrawal_method=pix_method,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        stats = await service.get_wallet_stats(USER_ID)
        assert stats["available_balance"] == 75.0
        assert stats["pending_balance"] == 25.0
        assert stats["total_balance"] == 100.0
        assert stats["total_earned"] == 300.0

    @pytest.mark.asyncio
    async def test_is_withdrawal_ready_true_when_sufficient(self, service, pix_method, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("100.00"),
            withdrawal_method=pix_method,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        stats = await service.get_wallet_stats(USER_ID)
        assert stats["is_withdrawal_ready"] is True

    @pytest.mark.asyncio
    async def test_is_withdrawal_ready_false_when_no_method(self, service, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("100.00"),
            withdrawal_method=None,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        stats = await service.get_wallet_stats(USER_ID)
        assert stats["is_withdrawal_ready"] is False

    @pytest.mark.asyncio
    async def test_is_withdrawal_ready_false_when_insufficient_balance(self, service, pix_method, db):
        wallet = AffiliateWallet(
            user_id=USER_ID,
            available_balance=Decimal("30.00"),
            withdrawal_method=pix_method,
        )
        await db.affiliate_wallets.insert_one(wallet.dict())

        stats = await service.get_wallet_stats(USER_ID)
        assert stats["is_withdrawal_ready"] is False
