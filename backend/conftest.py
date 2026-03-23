"""
Pytest Configuration and Global Fixtures
==========================================

This file is automatically loaded by pytest and makes all fixtures available to all tests.
"""

import pytest
from test_fixtures import (
    # Bot fixtures
    sample_bot_data,
    sample_bot,
    sample_running_bot,
    sample_bot_with_stats,
    # Order fixtures
    sample_order_data,
    sample_order,
    sample_open_order,
    sample_filled_order,
    sample_partially_filled_order,
    sample_rejected_order,
    # Position fixtures
    sample_position_data,
    sample_position,
    sample_profitable_position,
    sample_losing_position,
    sample_closed_position,
    sample_short_position,
    # Trade fixtures
    sample_trade_data,
    sample_trade,
    # Scenario fixtures
    sample_multi_order_scenario,
    # Mock collection fixtures
    mock_bots_collection,
    mock_orders_collection,
    mock_positions_collection,
    mock_trades_collection,
)


# Re-export all fixtures so pytest can discover them
__all__ = [
    # Bot fixtures
    "sample_bot_data",
    "sample_bot",
    "sample_running_bot",
    "sample_bot_with_stats",
    # Order fixtures
    "sample_order_data",
    "sample_order",
    "sample_open_order",
    "sample_filled_order",
    "sample_partially_filled_order",
    "sample_rejected_order",
    # Position fixtures
    "sample_position_data",
    "sample_position",
    "sample_profitable_position",
    "sample_losing_position",
    "sample_closed_position",
    "sample_short_position",
    # Trade fixtures
    "sample_trade_data",
    "sample_trade",
    # Scenario fixtures
    "sample_multi_order_scenario",
    # Mock collection fixtures
    "mock_bots_collection",
    "mock_orders_collection",
    "mock_positions_collection",
    "mock_trades_collection",
]


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "mongodb_url": "mongodb://localhost:27017",
        "database_name": "test_trading_db",
        "test_user_id": "test_user_123",
        "test_bot_id": "test_bot_123",
    }


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (requires pytest-asyncio)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
