"""
Database Fixtures & Test Data
==============================

Provides reusable test fixtures for testing Bot, Order, and Position services.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from bson import ObjectId
from typing import Dict, Any

from app.db.models import (
    BotStatus, OrderStatus, OrderSide, OrderType, PositionStatus,
    Bot, Order, Position, Trade
)


# ============================================
# BOT FIXTURES
# ============================================

@pytest.fixture
def sample_bot_data() -> Dict[str, Any]:
    """Minimal bot creation data (without auto-initialized fields)."""
    return {
        "user_id": "test_user_123",
        "name": "Test Bot",
        "exchange": "kucoin",
        "account_id": "test_account_123",
        "symbol": "BTC-USDT",
        "strategy_type": "dca",
        "config": {
            "strategy_type": "dca",
            "fast_ma": 20,
            "slow_ma": 50,
            "custom": {"interval": "1h", "amount": 100}
        },
        "risk_config": {
            "max_position_size": Decimal("1"),
            "leverage": 1,
            "stop_loss_percent": Decimal("5")
        },
    }


@pytest.fixture
def sample_bot_full_data() -> Dict[str, Any]:
    """Full bot data including auto-initialized fields."""
    data = sample_bot_data()
    data.update({
        "status": BotStatus.STOPPED,
        "enabled": True,
        "trades_count": 0,
        "total_pnl": Decimal("0"),
        "win_rate": Decimal("0"),
    })
    return data


@pytest.fixture
def sample_bot(sample_bot_full_data) -> Bot:
    """Create a sample bot instance."""
    return Bot(**sample_bot_full_data)


@pytest.fixture
def sample_running_bot(sample_bot_full_data) -> Bot:
    """Create a running bot instance."""
    data = sample_bot_full_data.copy()
    data["status"] = BotStatus.RUNNING
    data["started_at"] = datetime.now()
    return Bot(**data)


@pytest.fixture
def sample_bot_with_stats(sample_bot_full_data) -> Bot:
    """Create a bot with trading statistics."""
    data = sample_bot_full_data.copy()
    data["trades_count"] = 42
    data["total_pnl"] = Decimal("1234.56")
    data["win_rate"] = Decimal("0.67")
    return Bot(**data)


# ============================================
# ORDER FIXTURES
# ============================================

@pytest.fixture
def sample_order_data() -> Dict[str, Any]:
    """Minimal order data for testing."""
    return {
        "user_id": "test_user_123",
        "bot_id": "test_bot_123",
        "symbol": "BTC-USDT",
        "side": OrderSide.BUY,
        "type": OrderType.LIMIT,
        "size": Decimal("0.01"),
        "price": Decimal("45000"),
        "take_profit": Decimal("50000"),
        "stop_loss": Decimal("40000"),
        "status": OrderStatus.PENDING,
        "filled_size": Decimal("0"),
        "average_fill_price": Decimal("0"),
        "total_fee": Decimal("0"),
        "exchange_order_id": None,
        "client_oid": "test_client_oid_123",
        "executions": [],
        "retry_count": 0,
    }


@pytest.fixture
def sample_order(sample_order_data) -> Order:
    """Create a sample order instance."""
    return Order(**sample_order_data)


@pytest.fixture
def sample_open_order(sample_order_data) -> Order:
    """Create an open order (executed on exchange)."""
    data = sample_order_data.copy()
    data["status"] = OrderStatus.OPEN
    data["exchange_order_id"] = "kucoin_order_12345"
    return Order(**data)


@pytest.fixture
def sample_filled_order(sample_order_data) -> Order:
    """Create a completely filled order."""
    data = sample_order_data.copy()
    data["status"] = OrderStatus.FILLED
    data["exchange_order_id"] = "kucoin_order_12345"
    data["filled_size"] = Decimal("0.01")
    data["average_fill_price"] = Decimal("45010")
    data["total_fee"] = Decimal("0.00015")
    return Order(**data)


@pytest.fixture
def sample_partially_filled_order(sample_order_data) -> Order:
    """Create a partially filled order."""
    data = sample_order_data.copy()
    data["status"] = OrderStatus.FILLED  # 50% filled
    data["exchange_order_id"] = "kucoin_order_12345"
    data["filled_size"] = Decimal("0.005")
    data["average_fill_price"] = Decimal("45010")
    data["total_fee"] = Decimal("0.000075")
    return Order(**data)


@pytest.fixture
def sample_rejected_order(sample_order_data) -> Order:
    """Create a rejected order (failed validation)."""
    data = sample_order_data.copy()
    data["status"] = OrderStatus.REJECTED
    data["error_message"] = "Insufficient balance"
    return Order(**data)


# ============================================
# POSITION FIXTURES
# ============================================

@pytest.fixture
def sample_position_data() -> Dict[str, Any]:
    """Minimal position data for testing."""
    return {
        "user_id": "test_user_123",
        "bot_id": "test_bot_123",
        "symbol": "BTC-USDT",
        "side": OrderSide.BUY,
        "size": Decimal("0.01"),
        "entry_price": Decimal("45000"),
        "entry_cost": Decimal("450"),
        "entry_order_id": "order_123",
        "exit_order_id": None,
        "status": PositionStatus.OPEN,
        "current_price": Decimal("45000"),
        "unrealized_pnl": Decimal("0"),
        "unrealized_pnl_percent": Decimal("0"),
        "realized_pnl": Decimal("0"),
        "take_profit_price": Decimal("50000"),
        "stop_loss_price": Decimal("40000"),
    }


@pytest.fixture
def sample_position(sample_position_data) -> Position:
    """Create a sample position instance."""
    return Position(**sample_position_data)


@pytest.fixture
def sample_profitable_position(sample_position_data) -> Position:
    """Create a profitable open position."""
    data = sample_position_data.copy()
    data["current_price"] = Decimal("48000")
    data["unrealized_pnl"] = Decimal("300")  # (48000 - 45000) * 0.01
    data["unrealized_pnl_percent"] = Decimal("6.67")
    return Position(**data)


@pytest.fixture
def sample_losing_position(sample_position_data) -> Position:
    """Create a losing open position."""
    data = sample_position_data.copy()
    data["current_price"] = Decimal("42000")
    data["unrealized_pnl"] = Decimal("-300")  # (42000 - 45000) * 0.01
    data["unrealized_pnl_percent"] = Decimal("-6.67")
    return Position(**data)


@pytest.fixture
def sample_closed_position(sample_position_data) -> Position:
    """Create a closed position with realized PnL."""
    data = sample_position_data.copy()
    data["status"] = PositionStatus.CLOSED
    data["exit_order_id"] = "exit_order_123"
    data["current_price"] = Decimal("48000")
    data["unrealized_pnl"] = Decimal("0")  # No unrealized PnL for closed
    data["realized_pnl"] = Decimal("300")  # (48000 - 45000) * 0.01
    data["closed_at"] = datetime.now()
    return Position(**data)


@pytest.fixture
def sample_short_position(sample_position_data) -> Position:
    """Create a short position (sell-first)."""
    data = sample_position_data.copy()
    data["side"] = OrderSide.SELL
    data["entry_price"] = Decimal("45000")
    data["current_price"] = Decimal("44000")
    # For SHORT: profit = (entry - current) * size
    data["unrealized_pnl"] = Decimal("10")  # (45000 - 44000) * 0.01
    data["unrealized_pnl_percent"] = Decimal("0.22")
    return Position(**data)


# ============================================
# TRADE FIXTURES
# ============================================

@pytest.fixture
def sample_trade_data() -> Dict[str, Any]:
    """Minimal trade data for testing."""
    return {
        "user_id": "test_user_123",
        "order_id": "order_123",
        "symbol": "BTC-USDT",
        "side": OrderSide.BUY,
        "filled_size": Decimal("0.01"),
        "filled_price": Decimal("45010"),
        "fee": Decimal("0.00015"),
        "exchange_trade_id": "kucoin_trade_12345",
    }


@pytest.fixture
def sample_trade(sample_trade_data) -> Trade:
    """Create a sample trade instance."""
    return Trade(**sample_trade_data)


# ============================================
# MULTI-ORDER TEST SCENARIOS
# ============================================

@pytest.fixture
def sample_multi_order_scenario() -> Dict[str, Any]:
    """Create a multi-order scenario for integration testing."""
    return {
        "user_id": "test_user_123",
        "bot_id": "test_bot_123",
        "orders": [
            {
                "symbol": "BTC-USDT",
                "side": OrderSide.BUY,
                "type": OrderType.LIMIT,
                "size": Decimal("0.01"),
                "price": Decimal("45000"),
            },
            {
                "symbol": "ETH-USDT",
                "side": OrderSide.BUY,
                "type": OrderType.LIMIT,
                "size": Decimal("0.5"),
                "price": Decimal("2500"),
            },
            {
                "symbol": "BTC-USDT",
                "side": OrderSide.SELL,
                "type": OrderType.MARKET,
                "size": Decimal("0.01"),
                "price": None,
            },
        ]
    }


# ============================================
# DATABASE MOCK FIXTURES
# ============================================

@pytest.fixture
def mock_bots_collection():
    """Mock MongoDB bots collection."""
    from unittest.mock import AsyncMock
    collection = AsyncMock()
    collection.insert_one = AsyncMock(return_value=type('obj', (object,), {'inserted_id': ObjectId()})())
    collection.find_one = AsyncMock(return_value=None)
    collection.update_one = AsyncMock(return_value=type('obj', (object,), {'modified_count': 1})())
    collection.delete_one = AsyncMock(return_value=type('obj', (object,), {'deleted_count': 1})())
    collection.find = AsyncMock(return_value=AsyncMock(__aiter__=AsyncMock(return_value=AsyncMock())))
    return collection


@pytest.fixture
def mock_orders_collection():
    """Mock MongoDB orders collection."""
    from unittest.mock import AsyncMock
    collection = AsyncMock()
    collection.insert_one = AsyncMock(return_value=type('obj', (object,), {'inserted_id': ObjectId()})())
    collection.find_one = AsyncMock(return_value=None)
    collection.update_one = AsyncMock(return_value=type('obj', (object,), {'modified_count': 1})())
    collection.delete_one = AsyncMock(return_value=type('obj', (object,), {'deleted_count': 1})())
    collection.find = AsyncMock(return_value=AsyncMock(__aiter__=AsyncMock(return_value=AsyncMock())))
    return collection


@pytest.fixture
def mock_positions_collection():
    """Mock MongoDB positions collection."""
    from unittest.mock import AsyncMock
    collection = AsyncMock()
    collection.insert_one = AsyncMock(return_value=type('obj', (object,), {'inserted_id': ObjectId()})())
    collection.find_one = AsyncMock(return_value=None)
    collection.update_one = AsyncMock(return_value=type('obj', (object,), {'modified_count': 1})())
    collection.delete_one = AsyncMock(return_value=type('obj', (object,), {'deleted_count': 1})())
    collection.find = AsyncMock(return_value=AsyncMock(__aiter__=AsyncMock(return_value=AsyncMock())))
    return collection


@pytest.fixture
def mock_trades_collection():
    """Mock MongoDB trades collection."""
    from unittest.mock import AsyncMock
    collection = AsyncMock()
    collection.insert_one = AsyncMock(return_value=type('obj', (object,), {'inserted_id': ObjectId()})())
    collection.find = AsyncMock(return_value=AsyncMock(__aiter__=AsyncMock(return_value=AsyncMock())))
    return collection
