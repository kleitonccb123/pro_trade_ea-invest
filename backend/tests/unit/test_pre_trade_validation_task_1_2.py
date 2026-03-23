"""
Unit Tests for Task 1.2 — Pre-Trade Validation Expansion

Tests for the validate_order_executable function and helper functions.

Coverage:
- validate_order_executable: main validation function
- get_quote_currency: currency pair parsing
- get_base_currency: currency pair parsing
- get_last_price: price fetching
- Edge cases: insufficient balance, kill-switch, cooldown, etc.

Author: Crypto Trade Hub
"""

import pytest
import logging
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.trading.pre_trade_validation import (
    validate_order_executable,
    get_quote_currency,
    get_base_currency,
    get_last_price,
)

logger = logging.getLogger(__name__)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_credentials():
    """Mock encrypted credentials."""
    return {
        "_id": "cred_123",
        "user_id": "user_123",
        "exchange": "kucoin",
        "api_key_encrypted": "encrypted_key",
        "api_secret_encrypted": "encrypted_secret",
        "passphrase_encrypted": "encrypted_passphrase",
        "is_testnet": True,
    }


@pytest.fixture
def mock_balance_data():
    """Mock balance data from exchange."""
    return {
        "BTC": {"available": Decimal("0.5"), "locked": Decimal("0.1")},
        "USDT": {"available": Decimal("10000"), "locked": Decimal("1000")},
        "ETH": {"available": Decimal("5"), "locked": Decimal("0.5")},
    }


@pytest.fixture
def mock_market_info():
    """Mock market info."""
    from app.trading.pre_trade_validation import MarketInfo
    
    return MarketInfo(
        symbol="BTC-USDT",
        base_currency="BTC",
        quote_currency="USDT",
        min_order_size=Decimal("0.0001"),
        max_order_size=Decimal("100"),
        min_notional=Decimal("10"),
        price_precision=8,
        quantity_precision=8,
        tick_size=Decimal("0.00000001"),
        step_size=Decimal("0.00000001"),
    )


@pytest.fixture
def mock_kucoin_client(mock_balance_data, mock_market_info):
    """Mock KuCoin client."""
    client = AsyncMock()
    client.get_account_balance = AsyncMock(return_value=mock_balance_data)
    client.exchange = AsyncMock()
    client.exchange.fetch_ticker = AsyncMock(
        return_value={"last": Decimal("42000")}
    )
    return client


@pytest.fixture
def mock_risk_manager():
    """Mock RiskManager."""
    manager = MagicMock()
    manager._kill_switched = set()
    manager.is_in_cooldown = MagicMock(return_value=False)
    manager.config = MagicMock()
    manager.config.max_open_positions = 10
    return manager


# ==================== HELPER FUNCTION TESTS ====================

class TestGetQuoteCurrency:
    """Tests for get_quote_currency helper."""
    
    def test_slash_separator(self):
        """Test quote currency extraction with / separator."""
        assert get_quote_currency("BTC/USDT") == "USDT"
        assert get_quote_currency("ETH/USD") == "USD"
        assert get_quote_currency("ADA/USDT") == "USDT"
    
    def test_dash_separator(self):
        """Test quote currency extraction with - separator."""
        assert get_quote_currency("BTC-USDT") == "USDT"
        assert get_quote_currency("ETH-USD") == "USD"
    
    def test_underscore_separator(self):
        """Test quote currency extraction with _ separator."""
        assert get_quote_currency("BTC_USDT") == "USDT"
        assert get_quote_currency("ETH_USD") == "USD"
    
    def test_no_separator(self):
        """Test quote currency extraction without separator."""
        # Fallback: last 4 characters
        assert get_quote_currency("BTCUSDT") == "USDT"
    
    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert get_quote_currency("btc/usdt") == "USDT"
        assert get_quote_currency("ETH/usd") == "USD"


class TestGetBaseCurrency:
    """Tests for get_base_currency helper."""
    
    def test_slash_separator(self):
        """Test base currency extraction with / separator."""
        assert get_base_currency("BTC/USDT") == "BTC"
        assert get_base_currency("ETH/USD") == "ETH"
        assert get_base_currency("ADA/USDT") == "ADA"
    
    def test_dash_separator(self):
        """Test base currency extraction with - separator."""
        assert get_base_currency("BTC-USDT") == "BTC"
        assert get_base_currency("ETH-USD") == "ETH"
    
    def test_underscore_separator(self):
        """Test base currency extraction with _ separator."""
        assert get_base_currency("BTC_USDT") == "BTC"
        assert get_base_currency("ETH_USD") == "ETH"
    
    def test_no_separator(self):
        """Test base currency extraction without separator."""
        # Fallback: first 3-4 characters
        assert get_base_currency("BTCUSDT") == "BTC"
    
    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert get_base_currency("btc/usdt") == "BTC"
        assert get_base_currency("ETH/usd") == "ETH"


@pytest.mark.asyncio
class TestGetLastPrice:
    """Tests for get_last_price helper."""
    
    async def test_fetch_price_success(self):
        """Test successful price fetch."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={"last": 42000.50}
        )
        
        price = await get_last_price("BTC-USDT", mock_exchange)
        
        assert price == Decimal("42000.50")
        mock_exchange.fetch_ticker.assert_called_once_with("BTC-USDT")
    
    async def test_fetch_price_no_exchange(self):
        """Test price fetch without exchange (returns 0)."""
        price = await get_last_price("BTC-USDT", exchange=None)
        
        assert price == Decimal("0")
    
    async def test_fetch_price_error(self):
        """Test price fetch error handling."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ticker = AsyncMock(side_effect=Exception("API Error"))
        
        price = await get_last_price("BTC-USDT", mock_exchange)
        
        # Should return 0 on error
        assert price == Decimal("0")


# ==================== VALIDATE_ORDER_EXECUTABLE TESTS ====================

@pytest.mark.asyncio
class TestValidateOrderExecutable:
    """Tests for validate_order_executable main function."""
    
    async def test_validate_order_buy_success(self, mock_credentials, mock_balance_data, mock_market_info, mock_kucoin_client):
        """Test successful BUY order validation."""
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            # Setup mocks
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=False)
            mock_risk_mgr.return_value._kill_switched = set()
            
            # Execute
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="BUY",
                quantity=Decimal("0.1"),
                current_price=Decimal("42000")
            )
            
            # Verify
            assert is_valid is True
            assert error is None
    
    async def test_validate_order_sell_success(self, mock_credentials, mock_balance_data, mock_market_info, mock_kucoin_client):
        """Test successful SELL order validation."""
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            # Setup mocks
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=False)
            mock_risk_mgr.return_value._kill_switched = set()
            
            # Execute
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="SELL",
                quantity=Decimal("0.1"),
                current_price=Decimal("42000")
            )
            
            # Verify
            assert is_valid is True
            assert error is None
    
    async def test_no_credentials(self):
        """Test validation fails when no credentials found."""
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo:
            mock_cred_repo.get_credentials = AsyncMock(return_value=None)
            
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="BUY",
                quantity=Decimal("0.1"),
                current_price=Decimal("42000")
            )
            
            assert is_valid is False
            assert "credenciais" in error.lower()
    
    async def test_insufficient_balance_buy(self, mock_credentials, mock_market_info, mock_kucoin_client):
        """Test BUY fails with insufficient USDT balance."""
        # Modify balance to have insufficient USDT
        mock_kucoin_client.get_account_balance = AsyncMock(
            return_value={
                "BTC": {"available": Decimal("0.5"), "locked": Decimal("0.1")},
                "USDT": {"available": Decimal("100"), "locked": Decimal("100")},  # Only 100 USDT, but need ~4200
            }
        )
        
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=False)
            mock_risk_mgr.return_value._kill_switched = set()
            
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="BUY",
                quantity=Decimal("0.1"),
                current_price=Decimal("42000")
            )
            
            assert is_valid is False
            assert "saldo insuficiente" in error.lower()
    
    async def test_insufficient_balance_sell(self, mock_credentials, mock_market_info, mock_kucoin_client):
        """Test SELL fails with insufficient BTC balance."""
        # Modify balance to have insufficient BTC
        mock_kucoin_client.get_account_balance = AsyncMock(
            return_value={
                "BTC": {"available": Decimal("0.05"), "locked": Decimal("0")},  # Only 0.05, need 0.1
                "USDT": {"available": Decimal("50000"), "locked": Decimal("0")},
            }
        )
        
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=False)
            mock_risk_mgr.return_value._kill_switched = set()
            
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="SELL",
                quantity=Decimal("0.1"),
                current_price=Decimal("42000")
            )
            
            assert is_valid is False
            assert "saldo insuficiente" in error.lower()
    
    async def test_quantity_below_minimum(self, mock_credentials, mock_balance_data, mock_market_info, mock_kucoin_client):
        """Test validation fails when quantity below minimum."""
        # Modify market info to have higher minimum
        mock_market_info.min_order_size = Decimal("0.5")
        
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=False)
            mock_risk_mgr.return_value._kill_switched = set()
            
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="BUY",
                quantity=Decimal("0.1"),  # Below 0.5 minimum
                current_price=Decimal("42000")
            )
            
            assert is_valid is False
            assert "m?nimo" in error.lower() or "minimo" in error.lower()
    
    async def test_kill_switch_active(self, mock_credentials, mock_balance_data, mock_market_info, mock_kucoin_client):
        """Test validation fails when kill-switch is active."""
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=False)
            mock_risk_mgr.return_value._kill_switched = {"user_123"}  # Kill-switch active
            
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="BUY",
                quantity=Decimal("0.1"),
                current_price=Decimal("42000")
            )
            
            assert is_valid is False
            assert "kill-switch" in error.lower()
    
    async def test_cooldown_active(self, mock_credentials, mock_balance_data, mock_market_info, mock_kucoin_client):
        """Test validation fails when cooldown is active."""
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=True)  # Cooldown active
            mock_risk_mgr.return_value._kill_switched = set()
            
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="BUY",
                quantity=Decimal("0.1"),
                current_price=Decimal("42000")
            )
            
            assert is_valid is False
            assert "cooldown" in error.lower()
    
    async def test_notional_too_small(self, mock_credentials, mock_balance_data, mock_market_info, mock_kucoin_client):
        """Test validation fails when notional value is too small."""
        # Modify market info to have higher minimum notional
        mock_market_info.min_notional = Decimal("1000")
        
        with patch("app.trading.pre_trade_validation.CredentialsRepository") as mock_cred_repo, \
             patch("app.trading.pre_trade_validation.KuCoinClient") as mock_client_class, \
             patch("app.trading.pre_trade_validation.get_market_info_from_ccxt") as mock_get_market, \
             patch("app.trading.pre_trade_validation.RiskManager") as mock_risk_mgr:
            
            mock_cred_repo.get_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_class.return_value = mock_kucoin_client
            mock_get_market.return_value = mock_market_info
            mock_risk_mgr.return_value.is_in_cooldown = MagicMock(return_value=False)
            mock_risk_mgr.return_value._kill_switched = set()
            
            is_valid, error = await validate_order_executable(
                user_id="user_123",
                symbol="BTC-USDT",
                side="BUY",
                quantity=Decimal("0.001"),  # 0.001 * 42000 = 42 (below 1000 min)
                current_price=Decimal("42000")
            )
            
            assert is_valid is False
            assert "notional" in error.lower() or "valor" in error.lower()


# ==================== INTEGRATION TESTS ====================

@pytest.mark.asyncio
class TestValidateOrderExecutableIntegration:
    """Integration tests with real KuCoin API (requires credentials)."""
    
    async def test_validate_order_with_real_exchange(self):
        """
        Integration test with real KuCoin exchange.
        REQUIRES: Environment variables set
        - KUCOIN_TESTNET_API_KEY
        - KUCOIN_TESTNET_API_SECRET
        - KUCOIN_TESTNET_API_PASSPHRASE
        """
        import os
        
        api_key = os.getenv("KUCOIN_TESTNET_API_KEY")
        if not api_key:
            pytest.skip("KUCOIN_TESTNET_API_KEY not set")
        
        # TODO: Implement real integration test
        # This would require setting up credentials in MongoDB first
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
