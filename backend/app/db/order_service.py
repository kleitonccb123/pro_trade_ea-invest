"""
Order Service - CRUD and execution for trading orders.

Integrates with RiskManager (validation) and OrderManager (execution).
"""

from typing import List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from bson import ObjectId
import logging
from uuid import uuid4

from app.db.models import Order, OrderStatus, OrderSide, OrderType, Trade, OrderExecution
from app.trading.risk_manager import get_risk_manager, RiskConfig
from app.trading.order_manager import get_order_manager, OrderRequest, OrderExecutionStatus

logger = logging.getLogger(__name__)


class OrderService:
    """Database service for order operations."""
    
    def __init__(self, orders_collection, trades_collection):
        """
        Initialize order service.
        
        Args:
            orders_collection: MongoDB collection for orders
            trades_collection: MongoDB collection for trades/fills
        """
        self.orders_db = orders_collection
        self.trades_db = trades_collection
    
    async def create_order(
        self,
        user_id: str,
        bot_id: str,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        size: Decimal,
        price: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Order:
        """
        Create order in database (before execution).
        
        Args:
            user_id: User ID
            bot_id: Bot ID submitting order
            symbol: Trading symbol
            side: BUY or SELL
            order_type: MARKET or LIMIT
            size: Order size
            price: Limit price (required for limit orders)
            take_profit: Optional TP price
            stop_loss: Optional SL price
            
        Returns:
            Created Order object with _id
        """
        # Generate client_oid for idempotency
        client_oid = str(uuid4())
        
        order = Order(
            user_id=user_id,
            bot_id=ObjectId(bot_id),
            symbol=symbol,
            side=side,
            order_type=order_type,
            size=size,
            price=price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            client_oid=client_oid,
            status=OrderStatus.PENDING,
        )
        
        result = await self.orders_db.insert_one(
            order.model_dump(by_alias=True, exclude_none=True)
        )
        
        order.id = result.inserted_id
        
        logger.info(
            f"✅ Order created: {symbol} {side.value} {size} "
            f"(bot: {bot_id}, oid: {client_oid})"
        )
        
        return order
    
    async def validate_and_execute_order(
        self,
        order_id: str,
        user_id: str,
        current_price: Decimal,
        account_balance: Decimal,
    ) -> Tuple[bool, Optional[str], Optional[Order]]:
        """
        Validate order against risk params and execute if valid.
        
        Performs:
        1. Get Order from DB
        2. Validate with RiskManager
        3. If valid, execute with OrderManager
        4. Update order status in DB
        
        Args:
            order_id: Order ID in database
            user_id: User ID (ownership check)
            current_price: Current market price
            account_balance: User's available balance
            
        Returns:
            Tuple: (success: bool, error_message: Optional[str], order: Optional[Order])
        """
        # Get order from DB
        order_doc = await self.orders_db.find_one({
            "_id": ObjectId(order_id),
            "user_id": user_id
        })
        
        if not order_doc:
            return False, "Order not found", None
        
        order = Order.model_validate(order_doc)
        
        # Validate with RiskManager
        risk_manager = get_risk_manager()
        risk_config = RiskConfig()  # Use defaults for now
        
        is_valid, error_msg = await risk_manager.validate_order(
            user_id=user_id,
            symbol=order.symbol,
            side=order.side.value,
            size=order.size,
            price=order.price or current_price,
            stop_loss=order.stop_loss,
            account_balance=account_balance,
            risk_config=risk_config,
        )
        
        if not is_valid:
            # Update order status to REJECTED
            await self.orders_db.update_one(
                {"_id": ObjectId(order_id)},
                {
                    "$set": {
                        "status": OrderStatus.REJECTED.value,
                        "error_message": error_msg,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )
            
            logger.warning(f"❌ Order {order_id} rejected: {error_msg}")
            return False, error_msg, order
        
        # Execute order with OrderManager
        try:
            order_manager = get_order_manager()
            
            # Create OrderRequest for execution
            order_request = OrderRequest(
                order_id=order.client_oid,  # Use client_oid for idempotence
                symbol=order.symbol,
                side=order.side.value.upper(),
                size=order.size,
                order_type=order.order_type.value,
                price=order.price,
                take_profit=order.take_profit,
                stop_loss=order.stop_loss,
            )
            
            # Execute
            result = await order_manager.execute_order(order_request)
            
            # Update order in DB with exchange details
            update_data = {
                "exchange_order_id": result.exchange_order_id,
                "status": OrderStatus.OPEN.value if result.status == OrderExecutionStatus.EXECUTED else OrderStatus.FAILED.value,
                "updated_at": datetime.utcnow(),
            }
            
            if result.error:
                update_data["error_message"] = result.error
                update_data["last_error"] = result.error
                update_data["retry_count"] = order.retry_count + 1
            
            await self.orders_db.update_one(
                {"_id": ObjectId(order_id)},
                {"$set": update_data}
            )
            
            logger.info(f"✅ Order {order_id} executed: {result.exchange_order_id}")
            
            return True, None, order
            
        except Exception as e:
            error_msg = str(e)
            
            # Update order status
            await self.orders_db.update_one(
                {"_id": ObjectId(order_id)},
                {
                    "$set": {
                        "status": OrderStatus.FAILED.value,
                        "error_message": error_msg,
                        "last_error": error_msg,
                        "retry_count": order.retry_count + 1,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )
            
            logger.error(f"❌ Order execution failed: {error_msg}")
            return False, error_msg, order
    
    async def get_order(self, order_id: str, user_id: str) -> Optional[Order]:
        """
        Get order by ID with ownership check.
        
        Args:
            order_id: Order ID
            user_id: User ID
            
        Returns:
            Order object or None
        """
        doc = await self.orders_db.find_one({
            "_id": ObjectId(order_id),
            "user_id": user_id
        })
        
        if not doc:
            return None
        
        return Order.model_validate(doc)
    
    async def list_orders(
        self,
        user_id: str,
        bot_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """
        List user's orders with optional filters.
        
        Args:
            user_id: User ID
            bot_id: Optional bot filter
            status: Optional status filter
            limit: Max results
            
        Returns:
            List of Order objects
        """
        query = {"user_id": user_id}
        
        if bot_id:
            query["bot_id"] = ObjectId(bot_id)
        
        if status:
            query["status"] = status
        
        docs = await self.orders_db.find(query).sort("created_at", -1).limit(limit).to_list(length=None)
        
        return [Order.model_validate(doc) for doc in docs]
    
    async def cancel_order(self, order_id: str, user_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID
            user_id: User ID
            
        Returns:
            True if cancelled, False if not found or not cancellable
        """
        order = await self.get_order(order_id, user_id)
        
        if not order:
            return False
        
        # Can only cancel PENDING or OPEN orders
        if order.status not in [OrderStatus.PENDING, OrderStatus.OPEN]:
            logger.warning(f"Cannot cancel order {order_id} with status {order.status}")
            return False
        
        # TODO: Call exchange API to cancel order if it has exchange_order_id
        
        result = await self.orders_db.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$set": {
                    "status": OrderStatus.CANCELLED.value,
                    "cancelled_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Order {order_id} cancelled")
            return True
        
        return False
    
    async def record_execution(
        self,
        order_id: str,
        exchange_trade_id: str,
        filled_size: Decimal,
        fill_price: Decimal,
        fee: Decimal,
        fee_currency: str = "USDT",
    ) -> Optional[Trade]:
        """
        Record a trade execution (fill) for an order.
        
        Args:
            order_id: Order ID
            exchange_trade_id: Exchange trade ID
            filled_size: Amount filled
            fill_price: Fill price
            fee: Fee amount
            fee_currency: Fee currency
            
        Returns:
            Created Trade object
        """
        order = await self.orders_db.find_one({"_id": ObjectId(order_id)})
        
        if not order:
            return None
        
        order = Order.model_validate(order)
        
        # Create trade record
        trade = Trade(
            user_id=order.user_id,
            bot_id=order.bot_id,
            order_id=order.id,
            position_id=order.associated_position_id,
            symbol=order.symbol,
            side=order.side,
            size=filled_size,
            price=fill_price,
            fee=fee,
            fee_currency=fee_currency,
            exchange_trade_id=exchange_trade_id,
            exchange_order_id=order.exchange_order_id or "",
        )
        
        result = await self.trades_db.insert_one(
            trade.model_dump(by_alias=True, exclude_none=True)
        )
        
        trade.id = result.inserted_id
        
        # Update order execution record
        new_total_filled = order.filled_size + filled_size
        new_average_price = (
            (order.average_fill_price * order.filled_size + fill_price * filled_size) / new_total_filled
            if new_total_filled > 0 else fill_price
        )
        
        await self.orders_db.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$inc": {"filled_size": str(filled_size), "total_fee": str(fee)},
                "$set": {
                    "average_fill_price": str(new_average_price),
                    "status": OrderStatus.FILLED.value if new_total_filled >= order.size else OrderStatus.PARTIALLY_FILLED.value,
                    "executed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        logger.info(f"✅ Trade recorded: {exchange_trade_id} ({filled_size} @ {fill_price})")
        
        return trade


# Global instance
_service: Optional[OrderService] = None


def init_order_service(orders_collection, trades_collection) -> OrderService:
    """Initialize global order service."""
    global _service
    _service = OrderService(orders_collection, trades_collection)
    logger.info("✅ Order service initialized")
    return _service


def get_order_service() -> OrderService:
    """Get global order service."""
    global _service
    if _service is None:
        raise RuntimeError("Order service not initialized. Call init_order_service() first")
    return _service
