"""
Unit Tests for PositionService
==============================

Tests the complete PositionService functionality including:
- Position opening
- Position retrieval and listing
- Real-time PnL calculation
- Position closing with realized PnL
- Portfolio summary aggregation
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.db.position_service import PositionService
from app.db.models import PositionStatus, OrderSide, Position


class TestPositionServiceOpen:
    """Test position opening functionality."""
    
    @pytest.mark.asyncio
    async def test_open_position_long(self, sample_position_data, mock_positions_collection):
        """Test opening a long position."""
        mock_positions_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        service = PositionService(mock_positions_collection)
        
        position = await service.open_position(**sample_position_data)
        
        assert position is not None
        assert position.side == OrderSide.BUY
        assert position.status == PositionStatus.OPEN
        assert position.entry_price == Decimal("45000")
        assert position.entry_cost == Decimal("450")  # 0.01 * 45000
    
    @pytest.mark.asyncio
    async def test_open_position_short(self, sample_position_data, mock_positions_collection):
        """Test opening a short position."""
        sample_position_data["side"] = OrderSide.SELL
        
        mock_positions_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        service = PositionService(mock_positions_collection)
        
        position = await service.open_position(**sample_position_data)
        
        assert position.side == OrderSide.SELL
        assert position.status == PositionStatus.OPEN


class TestPositionServiceRetrieval:
    """Test position retrieval and listing."""
    
    @pytest.mark.asyncio
    async def test_get_position_success(self, sample_position, mock_positions_collection):
        """Test retrieving an existing position."""
        position_id = ObjectId()
        mock_positions_collection.find_one = AsyncMock(
            return_value=sample_position.model_dump()
        )
        
        service = PositionService(mock_positions_collection)
        result = await service.get_position(str(position_id), "test_user_123")
        
        assert result is not None
        # Verify ownership check
        call_args = mock_positions_collection.find_one.call_args[0][0]
        assert call_args["user_id"] == "test_user_123"
    
    @pytest.mark.asyncio
    async def test_get_position_not_found(self, mock_positions_collection):
        """Test retrieving a non-existent position."""
        mock_positions_collection.find_one = AsyncMock(return_value=None)
        
        service = PositionService(mock_positions_collection)
        result = await service.get_position("nonexistent_id", "test_user_123")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_open_positions_for_user(self, sample_position_data, mock_positions_collection):
        """Test listing open positions for a user."""
        pos1 = sample_position_data.copy()
        pos2 = sample_position_data.copy()
        pos2["symbol"] = "ETH-USDT"
        
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([pos1, pos2])
        mock_positions_collection.find = MagicMock(return_value=mock_cursor)
        
        service = PositionService(mock_positions_collection)
        result = await service.list_open_positions("test_user_123")
        
        # Verify query filters by user_id and open status
        call_args = mock_positions_collection.find.call_args[0][0]
        assert call_args["user_id"] == "test_user_123"
        # Status should filter for OPENING or OPEN
        assert "$in" in call_args.get("status", {}) or call_args.get("status") is not None
    
    @pytest.mark.asyncio
    async def test_list_positions_filtered_by_bot(self, mock_positions_collection):
        """Test listing positions filtered by bot_id."""
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([])
        mock_positions_collection.find = MagicMock(return_value=mock_cursor)
        
        service = PositionService(mock_positions_collection)
        await service.list_open_positions("test_user_123", bot_id="bot_123")
        
        # Verify bot_id filter is included
        call_args = mock_positions_collection.find.call_args[0][0]
        assert call_args["bot_id"] == "bot_123"


class TestPositionServicePnL:
    """Test PnL calculation in positions."""
    
    @pytest.mark.asyncio
    async def test_update_position_price_profitable_long(self, sample_position_data, mock_positions_collection):
        """Test updating position price with profit (long position)."""
        position_id = ObjectId()
        sample_position_data["current_price"] = Decimal("45000")
        
        mock_positions_collection.find_one = AsyncMock(
            return_value={**sample_position_data, "_id": position_id}
        )
        mock_positions_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = PositionService(mock_positions_collection)
        
        # Update to higher price (profit)
        success = await service.update_position_price(
            str(position_id),
            "test_user_123",
            Decimal("48000")  # +$45/0.01 = +$300 profit
        )
        
        assert success is True
        # Verify PnL was calculated correctly
        call_args = mock_positions_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        # For LONG: PnL = (current - entry) * size = (48000 - 45000) * 0.01 = 300
        assert update_doc["unrealized_pnl"] == Decimal("300")
    
    @pytest.mark.asyncio
    async def test_update_position_price_losing_long(self, sample_position_data, mock_positions_collection):
        """Test updating position price with loss (long position)."""
        position_id = ObjectId()
        
        mock_positions_collection.find_one = AsyncMock(
            return_value={**sample_position_data, "_id": position_id}
        )
        mock_positions_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = PositionService(mock_positions_collection)
        
        # Update to lower price (loss)
        success = await service.update_position_price(
            str(position_id),
            "test_user_123",
            Decimal("42000")  # -$30,000 = -$300 loss
        )
        
        assert success is True
        # Verify negative PnL
        call_args = mock_positions_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        # For LONG: PnL = (42000 - 45000) * 0.01 = -300
        assert update_doc["unrealized_pnl"] == Decimal("-300")
    
    @pytest.mark.asyncio
    async def test_update_position_price_profitable_short(self, sample_position_data, mock_positions_collection):
        """Test updating position price with profit (short position)."""
        position_id = ObjectId()
        sample_position_data["side"] = OrderSide.SELL
        sample_position_data["entry_price"] = Decimal("45000")
        
        mock_positions_collection.find_one = AsyncMock(
            return_value={**sample_position_data, "_id": position_id}
        )
        mock_positions_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = PositionService(mock_positions_collection)
        
        # Update to lower price (profit for short)
        success = await service.update_position_price(
            str(position_id),
            "test_user_123",
            Decimal("42000")  # Short profit, price went down
        )
        
        assert success is True
        # Verify positive PnL for short
        call_args = mock_positions_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        # For SHORT: PnL = (entry - current) * size = (45000 - 42000) * 0.01 = 300
        assert update_doc["unrealized_pnl"] == Decimal("300")
    
    @pytest.mark.asyncio
    async def test_update_position_price_at_stop_loss(self, sample_position_data, mock_positions_collection):
        """Test updating position price at stop loss level."""
        position_id = ObjectId()
        sample_position_data["stop_loss_price"] = Decimal("40000")
        
        mock_positions_collection.find_one = AsyncMock(
            return_value={**sample_position_data, "_id": position_id}
        )
        mock_positions_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = PositionService(mock_positions_collection)
        
        success = await service.update_position_price(
            str(position_id),
            "test_user_123",
            Decimal("40000")  # At stop loss
        )
        
        assert success is True
        # Verify stop loss was reached
        call_args = mock_positions_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        assert update_doc["unrealized_pnl"] == Decimal("-500")  # (40000-45000)*0.01


class TestPositionServiceClose:
    """Test position closing with realized PnL."""
    
    @pytest.mark.asyncio
    async def test_close_position_with_profit(self, mock_positions_collection):
        """Test closing a profitable position."""
        position_id = ObjectId()
        exit_price = Decimal("48000")
        
        # Mock find_one to return open position
        mock_positions_collection.find_one = AsyncMock(
            return_value={
                "_id": position_id,
                "status": PositionStatus.OPEN.value,
                "entry_price": Decimal("45000"),
                "size": Decimal("0.01"),
                "side": OrderSide.BUY.value
            }
        )
        # Mock update
        mock_positions_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = PositionService(mock_positions_collection)
        
        success = await service.close_position(
            str(position_id),
            "test_user_123",
            exit_price=exit_price,
            exit_order_id="exit_order_123"
        )
        
        assert success is True
        # Verify realized PnL was calculated
        call_args = mock_positions_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        # For LONG: realized_pnl = (48000 - 45000) * 0.01 = 300
        assert update_doc["realized_pnl"] == Decimal("300")
        assert update_doc["status"] == PositionStatus.CLOSED.value
        assert update_doc["exit_order_id"] == "exit_order_123"
    
    @pytest.mark.asyncio
    async def test_close_position_with_loss(self, mock_positions_collection):
        """Test closing a losing position."""
        position_id = ObjectId()
        
        mock_positions_collection.find_one = AsyncMock(
            return_value={
                "_id": position_id,
                "status": PositionStatus.OPEN.value,
                "entry_price": Decimal("45000"),
                "size": Decimal("0.01"),
                "side": OrderSide.BUY.value
            }
        )
        mock_positions_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = PositionService(mock_positions_collection)
        
        success = await service.close_position(
            str(position_id),
            "test_user_123",
            exit_price=Decimal("42000"),
            exit_order_id="exit_order_123"
        )
        
        assert success is True
        # Verify negative realized PnL
        call_args = mock_positions_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        # For LONG: realized_pnl = (42000 - 45000) * 0.01 = -300
        assert update_doc["realized_pnl"] == Decimal("-300")
    
    @pytest.mark.asyncio
    async def test_close_position_already_closed(self, mock_positions_collection):
        """Test that already closed positions cannot be closed again."""
        mock_positions_collection.find_one = AsyncMock(
            return_value={"status": PositionStatus.CLOSED.value}
        )
        
        service = PositionService(mock_positions_collection)
        
        success = await service.close_position(
            "position_123",
            "test_user_123",
            exit_price=Decimal("48000"),
            exit_order_id="exit_order_123"
        )
        
        assert success is False
        # Verify no update was attempted
        mock_positions_collection.update_one.assert_not_called()


class TestPositionServicePortfolio:
    """Test portfolio summary aggregation."""
    
    @pytest.mark.asyncio
    async def test_get_portfolio_summary_single_position(self, sample_profitable_position, mock_positions_collection):
        """Test portfolio summary with single position."""
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([sample_profitable_position.model_dump()])
        mock_positions_collection.find = MagicMock(return_value=mock_cursor)
        
        service = PositionService(mock_positions_collection)
        summary = await service.get_portfolio_summary("test_user_123")
        
        assert summary is not None
        assert summary["total_positions"] == 1
        assert summary["total_unrealized_pnl"] == Decimal("300")
        # Verify aggregation statistics
        assert "total_exposure" in summary
        assert "weighted_return" in summary
    
    @pytest.mark.asyncio
    async def test_get_portfolio_summary_multiple_positions(self, sample_position_data, mock_positions_collection):
        """Test portfolio summary with multiple positions."""
        pos1 = sample_position_data.copy()
        pos1["unrealized_pnl"] = Decimal("300")  # Profitable
        
        pos2 = sample_position_data.copy()
        pos2["symbol"] = "ETH-USDT"
        pos2["unrealized_pnl"] = Decimal("-100")  # Losing
        
        pos3 = sample_position_data.copy()
        pos3["symbol"] = "BNB-USDT"
        pos3["unrealized_pnl"] = Decimal("50")
        
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([pos1, pos2, pos3])
        mock_positions_collection.find = MagicMock(return_value=mock_cursor)
        
        service = PositionService(mock_positions_collection)
        summary = await service.get_portfolio_summary("test_user_123")
        
        assert summary["total_positions"] == 3
        assert summary["total_unrealized_pnl"] == Decimal("250")  # 300 - 100 + 50
    
    @pytest.mark.asyncio
    async def test_get_portfolio_summary_no_positions(self, mock_positions_collection):
        """Test portfolio summary with no open positions."""
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([])
        mock_positions_collection.find = MagicMock(return_value=mock_cursor)
        
        service = PositionService(mock_positions_collection)
        summary = await service.get_portfolio_summary("test_user_123")
        
        assert summary["total_positions"] == 0
        assert summary["total_unrealized_pnl"] == Decimal("0")


class TestPositionServiceOwnershipValidation:
    """Test ownership validation in position operations."""
    
    @pytest.mark.asyncio
    async def test_get_position_ownership_check(self, mock_positions_collection):
        """Test that position retrieval checks user ownership."""
        mock_positions_collection.find_one = AsyncMock(return_value=None)
        
        service = PositionService(mock_positions_collection)
        result = await service.get_position("position_123", "test_user_123")
        
        # Verify user_id was included in query
        call_args = mock_positions_collection.find_one.call_args[0][0]
        assert call_args["user_id"] == "test_user_123"
    
    @pytest.mark.asyncio
    async def test_list_positions_per_user_isolation(self, mock_positions_collection):
        """Test that listing positions only returns user's own positions."""
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([])
        mock_positions_collection.find = MagicMock(return_value=mock_cursor)
        
        service = PositionService(mock_positions_collection)
        await service.list_open_positions("user_123")
        
        # Verify user_id filter is strict
        call_args = mock_positions_collection.find.call_args[0][0]
        assert call_args["user_id"] == "user_123"


class TestPositionServiceIntegration:
    """Integration tests for position workflows."""
    
    @pytest.mark.asyncio
    async def test_full_position_lifecycle(self, sample_position_data, mock_positions_collection):
        """Test complete position lifecycle: open → price updates → close."""
        position_id = ObjectId()
        
        # Open
        mock_positions_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=position_id)
        )
        service = PositionService(mock_positions_collection)
        position = await service.open_position(**sample_position_data)
        assert position is not None
        
        # Update price with profit
        mock_positions_collection.find_one = AsyncMock(
            return_value={
                **sample_position_data,
                "_id": position_id,
                "status": PositionStatus.OPEN.value,
                "current_price": Decimal("45000")
            }
        )
        mock_positions_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        await service.update_position_price(
            str(position_id),
            "test_user_123",
            Decimal("48000")
        )
        
        # Close position
        mock_positions_collection.find_one = AsyncMock(
            return_value={
                **sample_position_data,
                "_id": position_id,
                "status": PositionStatus.OPEN.value,
                "entry_price": Decimal("45000")
            }
        )
        
        success = await service.close_position(
            str(position_id),
            "test_user_123",
            exit_price=Decimal("48000"),
            exit_order_id="exit_order_123"
        )
        
        assert success is True
