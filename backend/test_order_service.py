"""
Unit Tests for OrderService
============================

Tests the complete OrderService functionality including:
- Order creation
- Order validation and execution (integrating RiskManager + OrderManager)
- Order retrieval and listing
- Order cancellation
- Trade execution recording
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.db.order_service import OrderService
from app.db.models import OrderStatus, OrderSide, OrderType, Order
from app.trading.order_manager import OrderExecutionStatus


class TestOrderServiceCreate:
    """Test order creation functionality."""
    
    @pytest.mark.asyncio
    async def test_create_order_basic(self, sample_order_data, mock_orders_collection, mock_trades_collection):
        """Test creating a basic order."""
        mock_orders_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        service = OrderService(mock_orders_collection, mock_trades_collection)
        
        order = await service.create_order(**sample_order_data)
        
        assert order is not None
        assert order.user_id == "test_user_123"
        assert order.status == OrderStatus.PENDING
        assert order.client_oid is not None  # UUID should be generated
        mock_orders_collection.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_order_generates_client_oid(self, sample_order_data, mock_orders_collection, mock_trades_collection):
        """Test that client_oid is generated for idempotency."""
        mock_orders_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        service = OrderService(mock_orders_collection, mock_trades_collection)
        
        # Remove client_oid to test generation
        sample_order_data.pop("client_oid")
        order = await service.create_order(**sample_order_data)
        
        # Verify client_oid was generated
        assert order.client_oid is not None
        assert len(order.client_oid) > 0


class TestOrderServiceValidateAndExecute:
    """Test order validation and execution flow (RiskManager + OrderManager integration)."""
    
    @pytest.mark.asyncio
    async def test_validate_and_execute_success(self, sample_order_data, mock_orders_collection, mock_trades_collection):
        """Test successful order validation and execution."""
        order_id = ObjectId()
        
        # Mock order retrieval
        mock_orders_collection.find_one = AsyncMock(
            return_value={**sample_order_data, "_id": order_id}
        )
        # Mock order update
        mock_orders_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        
        # Mock RiskManager and OrderManager
        with patch('app.db.order_service.get_risk_manager') as mock_get_risk_mgr, \
             patch('app.db.order_service.get_order_manager') as mock_get_order_mgr:
            
            # RiskManager returns valid
            mock_risk_mgr = AsyncMock()
            mock_risk_mgr.validate_order = AsyncMock(return_value=(True, None))
            mock_get_risk_mgr.return_value = mock_risk_mgr
            
            # OrderManager executes successfully
            mock_order_mgr = AsyncMock()
            mock_order_mgr.execute_order = AsyncMock(
                return_value=OrderResult(
                    status=FASE1OrderStatus.EXECUTED,
                    exchange_order_id="kucoin_12345",
                    filled_size=Decimal("0.01"),
                    filled_price=Decimal("45010"),
                    error=None
                )
            )
            mock_get_order_mgr.return_value = mock_order_mgr
            
            # Execute
            is_valid, error, order = await service.validate_and_execute_order(
                order_id=str(order_id),
                user_id="test_user_123",
                current_price=Decimal("45000"),
                account_balance=Decimal("10000")
            )
            
            # Verify
            assert is_valid is True
            assert error is None
            assert order is not None
            assert order.exchange_order_id == "kucoin_12345"
            # Verify RiskManager was called
            mock_risk_mgr.validate_order.assert_called_once()
            # Verify OrderManager was called
            mock_order_mgr.execute_order.assert_called_once()
            # Verify order was updated to OPEN status
            mock_orders_collection.update_one.assert_called()
    
    @pytest.mark.asyncio
    async def test_validate_fails_insufficient_balance(self, sample_order_data, mock_orders_collection, mock_trades_collection):
        """Test order rejected by RiskManager (insufficient balance)."""
        order_id = ObjectId()
        
        mock_orders_collection.find_one = AsyncMock(
            return_value={**sample_order_data, "_id": order_id}
        )
        mock_orders_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        
        with patch('app.db.order_service.get_risk_manager') as mock_get_risk_mgr:
            # RiskManager rejects order
            mock_risk_mgr = AsyncMock()
            mock_risk_mgr.validate_order = AsyncMock(
                return_value=(False, "Insufficient balance")
            )
            mock_get_risk_mgr.return_value = mock_risk_mgr
            
            is_valid, error, order = await service.validate_and_execute_order(
                order_id=str(order_id),
                user_id="test_user_123",
                current_price=Decimal("45000"),
                account_balance=Decimal("100")  # Very small balance
            )
            
            # Verify
            assert is_valid is False
            assert "Insufficient balance" in error
            # Verify order status was set to REJECTED
            call_args = mock_orders_collection.update_one.call_args[0]
            update_doc = call_args[1]["$set"]
            assert update_doc["status"] == OrderStatus.REJECTED.value
    
    @pytest.mark.asyncio
    async def test_validate_and_execute_order_manager_fails(self, sample_order_data, mock_orders_collection, mock_trades_collection):
        """Test order execution fails in OrderManager."""
        order_id = ObjectId()
        
        mock_orders_collection.find_one = AsyncMock(
            return_value={**sample_order_data, "_id": order_id}
        )
        mock_orders_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        
        with patch('app.db.order_service.get_risk_manager') as mock_get_risk_mgr, \
             patch('app.db.order_service.get_order_manager') as mock_get_order_mgr:
            
            # RiskManager approves
            mock_risk_mgr = AsyncMock()
            mock_risk_mgr.validate_order = AsyncMock(return_value=(True, None))
            mock_get_risk_mgr.return_value = mock_risk_mgr
            
            # OrderManager fails
            mock_order_mgr = AsyncMock()
            mock_order_mgr.execute_order = AsyncMock(
                return_value=OrderResult(
                    status=FASE1OrderStatus.FAILED,
                    exchange_order_id=None,
                    filled_size=Decimal("0"),
                    filled_price=Decimal("0"),
                    error="KuCoin API error: 429 Too Many Requests"
                )
            )
            mock_get_order_mgr.return_value = mock_order_mgr
            
            is_valid, error, order = await service.validate_and_execute_order(
                order_id=str(order_id),
                user_id="test_user_123",
                current_price=Decimal("45000"),
                account_balance=Decimal("10000")
            )
            
            assert is_valid is False
            assert "KuCoin API error" in error


class TestOrderServiceRetrieval:
    """Test order retrieval and listing."""
    
    @pytest.mark.asyncio
    async def test_get_order_success(self, sample_order, mock_orders_collection, mock_trades_collection):
        """Test retrieving an existing order."""
        order_id = ObjectId()
        mock_orders_collection.find_one = AsyncMock(return_value=sample_order.model_dump())
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        result = await service.get_order(str(order_id), "test_user_123")
        
        assert result is not None
        # Verify ownership check
        call_args = mock_orders_collection.find_one.call_args[0][0]
        assert call_args["user_id"] == "test_user_123"
    
    @pytest.mark.asyncio
    async def test_get_order_not_found(self, mock_orders_collection, mock_trades_collection):
        """Test retrieving a non-existent order."""
        mock_orders_collection.find_one = AsyncMock(return_value=None)
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        result = await service.get_order("nonexistent_id", "test_user_123")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_orders_for_user(self, sample_order_data, mock_orders_collection, mock_trades_collection):
        """Test listing all orders for a user."""
        order1 = sample_order_data.copy()
        order2 = sample_order_data.copy()
        order2["symbol"] = "ETH-USDT"
        
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([order1, order2])
        mock_orders_collection.find = MagicMock(return_value=mock_cursor)
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        result = await service.list_orders(
            user_id="test_user_123",
            bot_id=None,
            status=None,
            limit=20
        )
        
        # Verify query filters by user_id
        call_args = mock_orders_collection.find.call_args[0][0]
        assert call_args["user_id"] == "test_user_123"
    
    @pytest.mark.asyncio
    async def test_list_orders_with_filters(self, mock_orders_collection, mock_trades_collection):
        """Test listing orders with bot_id and status filters."""
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([])
        mock_orders_collection.find = MagicMock(return_value=mock_cursor)
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        await service.list_orders(
            user_id="test_user_123",
            bot_id="bot_123",
            status=OrderStatus.OPEN
        )
        
        # Verify query includes all filters
        call_args = mock_orders_collection.find.call_args[0][0]
        assert call_args["user_id"] == "test_user_123"
        assert call_args["bot_id"] == "bot_123"
        assert call_args["status"] == OrderStatus.OPEN.value


class TestOrderServiceCancellation:
    """Test order cancellation."""
    
    @pytest.mark.asyncio
    async def test_cancel_order_success(self, mock_orders_collection, mock_trades_collection):
        """Test canceling a pending order."""
        # Mock find_one to return an open order
        mock_orders_collection.find_one = AsyncMock(
            return_value={"status": OrderStatus.OPEN.value}
        )
        # Mock update
        mock_orders_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        success = await service.cancel_order("order_123", "test_user_123")
        
        assert success is True
        # Verify status was updated to CANCELLED
        call_args = mock_orders_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        assert update_doc["status"] == OrderStatus.CANCELLED.value
    
    @pytest.mark.asyncio
    async def test_cancel_order_already_filled(self, mock_orders_collection, mock_trades_collection):
        """Test that filled orders cannot be canceled."""
        mock_orders_collection.find_one = AsyncMock(
            return_value={"status": OrderStatus.FILLED.value}
        )
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        success = await service.cancel_order("order_123", "test_user_123")
        
        assert success is False
        # Verify no update was attempted
        mock_orders_collection.update_one.assert_not_called()


class TestOrderServiceExecution:
    """Test trade execution recording."""
    
    @pytest.mark.asyncio
    async def test_record_execution_single_fill(self, mock_orders_collection, mock_trades_collection):
        """Test recording a single trade fill."""
        order_id = ObjectId()
        
        # Mock find_one to return order
        mock_orders_collection.find_one = AsyncMock(
            return_value={
                "_id": order_id,
                "filled_size": Decimal("0"),
                "average_fill_price": Decimal("0"),
                "total_fee": Decimal("0"),
                "status": OrderStatus.OPEN.value
            }
        )
        # Mock update
        mock_orders_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        # Mock trade insert
        mock_trades_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        
        success = await service.record_execution(
            order_id=str(order_id),
            user_id="test_user_123",
            exchange_trade_id="kucoin_trade_12345",
            filled_size=Decimal("0.01"),
            filled_price=Decimal("45010"),
            fee=Decimal("0.00015")
        )
        
        assert success is True
        # Verify trade was recorded
        mock_trades_collection.insert_one.assert_called_once()
        # Verify order was updated atomically
        mock_orders_collection.update_one.assert_called()
    
    @pytest.mark.asyncio
    async def test_record_execution_multiple_fills(self, mock_orders_collection, mock_trades_collection):
        """Test recording multiple trade fills (partial fills)."""
        order_id = ObjectId()
        
        # First fill
        mock_orders_collection.find_one = AsyncMock(
            return_value={
                "_id": order_id,
                "filled_size": Decimal("0"),
                "average_fill_price": Decimal("0"),
                "total_fee": Decimal("0")
            }
        )
        mock_orders_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        mock_trades_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        
        # Record first fill
        success1 = await service.record_execution(
            order_id=str(order_id),
            user_id="test_user_123",
            exchange_trade_id="kucoin_trade_1",
            filled_size=Decimal("0.005"),
            filled_price=Decimal("45010"),
            fee=Decimal("0.000075")
        )
        
        # Update for second fill
        mock_orders_collection.find_one = AsyncMock(
            return_value={
                "_id": order_id,
                "filled_size": Decimal("0.005"),
                "average_fill_price": Decimal("45010"),
                "total_fee": Decimal("0.000075")
            }
        )
        
        # Record second fill
        success2 = await service.record_execution(
            order_id=str(order_id),
            user_id="test_user_123",
            exchange_trade_id="kucoin_trade_2",
            filled_size=Decimal("0.005"),
            filled_price=Decimal("45020"),
            fee=Decimal("0.000075")
        )
        
        assert success1 is True
        assert success2 is True
        # Verify both trades were recorded
        assert mock_trades_collection.insert_one.call_count == 2


class TestOrderServiceOwnershipValidation:
    """Test ownership validation in order operations."""
    
    @pytest.mark.asyncio
    async def test_get_order_ownership_check(self, mock_orders_collection, mock_trades_collection):
        """Test that order retrieval checks user ownership."""
        mock_orders_collection.find_one = AsyncMock(return_value=None)
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        result = await service.get_order("order_123", "other_user")
        
        # Verify user_id was included in query
        call_args = mock_orders_collection.find_one.call_args[0][0]
        assert call_args["user_id"] == "other_user"
    
    @pytest.mark.asyncio
    async def test_cancel_order_ownership_check(self, mock_orders_collection, mock_trades_collection):
        """Test that order cancellation checks user ownership."""
        mock_orders_collection.find_one = AsyncMock(return_value=None)
        
        service = OrderService(mock_orders_collection, mock_trades_collection)
        success = await service.cancel_order("order_123", "test_user_123")
        
        assert success is False
