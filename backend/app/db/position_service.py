"""
Position Service - Manage open trading positions and calculate PnL.

Handles position lifecycle from opening to closing.
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from bson import ObjectId
import logging

from app.db.models import Position, PositionStatus, OrderSide

logger = logging.getLogger(__name__)


class PositionService:
    """Database service for position operations."""
    
    def __init__(self, positions_collection):
        """
        Initialize position service.
        
        Args:
            positions_collection: MongoDB collection for positions
        """
        self.db = positions_collection
    
    async def open_position(
        self,
        user_id: str,
        bot_id: str,
        symbol: str,
        side: OrderSide,
        size: Decimal,
        entry_price: Decimal,
        entry_order_id: str,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Position:
        """
        Open new trading position.
        
        Args:
            user_id: User ID
            bot_id: Bot ID
            symbol: Trading symbol
            side: LONG (BUY) or SHORT (SELL)
            size: Position size
            entry_price: Entry price
            entry_order_id: Order ID that opened position
            take_profit: Target profit price
            stop_loss: Risk limit price
            
        Returns:
            Created Position object
        """
        position = Position(
            user_id=user_id,
            bot_id=ObjectId(bot_id),
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            entry_cost=size * entry_price,
            entry_order_id=ObjectId(entry_order_id),
            status=PositionStatus.OPEN,
            take_profit_price=take_profit,
            stop_loss_price=stop_loss,
        )
        
        result = await self.db.insert_one(
            position.model_dump(by_alias=True, exclude_none=True)
        )
        
        position.id = result.inserted_id
        
        logger.info(
            f"✅ Position opened: {symbol} {side.value} {size} @ {entry_price} "
            f"(cost: {size * entry_price}, user: {user_id})"
        )
        
        return position
    
    async def get_position(self, position_id: str, user_id: str) -> Optional[Position]:
        """
        Get position by ID with ownership check.
        
        Args:
            position_id: Position ID
            user_id: User ID
            
        Returns:
            Position object or None
        """
        doc = await self.db.find_one({
            "_id": ObjectId(position_id),
            "user_id": user_id
        })
        
        if not doc:
            return None
        
        return Position.model_validate(doc)
    
    async def list_open_positions(
        self,
        user_id: str,
        bot_id: Optional[str] = None,
    ) -> List[Position]:
        """
        List all open positions for user.
        
        Args:
            user_id: User ID
            bot_id: Optional bot filter
            
        Returns:
            List of open Position objects
        """
        query = {
            "user_id": user_id,
            "status": {"$in": [PositionStatus.OPENING.value, PositionStatus.OPEN.value]}
        }
        
        if bot_id:
            query["bot_id"] = ObjectId(bot_id)
        
        docs = await self.db.find(query).to_list(length=None)
        
        return [Position.model_validate(doc) for doc in docs]
    
    async def update_position_price(
        self,
        position_id: str,
        current_price: Decimal,
    ) -> Optional[Position]:
        """
        Update position with latest market price and calculate unrealized PnL.
        
        Args:
            position_id: Position ID
            current_price: Current market price
            
        Returns:
            Updated Position object
        """
        position_doc = await self.db.find_one({"_id": ObjectId(position_id)})
        
        if not position_doc:
            return None
        
        position = Position.model_validate(position_doc)
        
        # Calculate unrealized PnL
        if position.side == OrderSide.BUY:
            # Long position: profit if price goes up
            pnl = (current_price - position.entry_price) * position.size
            pnl_percent = ((current_price - position.entry_price) / position.entry_price) * Decimal("100")
        else:
            # Short position: profit if price goes down
            pnl = (position.entry_price - current_price) * position.size
            pnl_percent = ((position.entry_price - current_price) / position.entry_price) * Decimal("100")
        
        # Update in DB
        result = await self.db.find_one_and_update(
            {"_id": ObjectId(position_id)},
            {
                "$set": {
                    "current_price": str(current_price),
                    "unrealized_pnl": str(pnl),
                    "unrealized_pnl_percent": str(pnl_percent),
                    "last_price_update": datetime.utcnow(),
                }
            },
            return_document=True
        )
        
        if result:
            return Position.model_validate(result)
        
        return None
    
    async def close_position(
        self,
        position_id: str,
        exit_price: Decimal,
        exit_order_id: str,
    ) -> Optional[Position]:
        """
        Close position and calculate realized PnL.
        
        Args:
            position_id: Position ID
            exit_price: Price at which position was closed
            exit_order_id: Order ID that closed position
            
        Returns:
            Updated Position object with realized PnL
        """
        position_doc = await self.db.find_one({"_id": ObjectId(position_id)})
        
        if not position_doc:
            return None
        
        position = Position.model_validate(position_doc)
        
        # Calculate realized PnL
        if position.side == OrderSide.BUY:
            # Bought at entry_price, sold at exit_price
            realized_pnl = (exit_price - position.entry_price) * position.size
        else:
            # Sold at entry_price, bought back at exit_price
            realized_pnl = (position.entry_price - exit_price) * position.size
        
        # Update in DB
        result = await self.db.find_one_and_update(
            {"_id": ObjectId(position_id)},
            {
                "$set": {
                    "status": PositionStatus.CLOSED.value,
                    "exit_order_id": ObjectId(exit_order_id),
                    "closed_at": datetime.utcnow(),
                    "realized_pnl": str(realized_pnl),
                }
            },
            return_document=True
        )
        
        if result:
            logger.info(f"✅ Position {position_id} closed with PnL: {realized_pnl}")
            return Position.model_validate(result)
        
        return None
    
    async def get_portfolio_summary(self, user_id: str) -> dict:
        """
        Get summary of all open positions for portfolio view.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with summary: total_positions, total_exposure, total_pnl, etc
        """
        positions = await self.list_open_positions(user_id)
        
        if not positions:
            return {
                "total_positions": 0,
                "total_exposure": Decimal("0"),
                "total_unrealized_pnl": Decimal("0"),
                "total_unrealized_pnl_percent": Decimal("0"),
                "positions": []
            }
        
        total_exposure = Decimal("0")
        total_pnl = Decimal("0")
        
        for pos in positions:
            exposure = pos.size * (pos.current_price or pos.entry_price)
            total_exposure += exposure
            
            if pos.unrealized_pnl:
                total_pnl += Decimal(pos.unrealized_pnl)
        
        # Calculate weighted average return
        avg_return = (total_pnl / total_exposure * Decimal("100")) if total_exposure > 0 else Decimal("0")
        
        return {
            "total_positions": len(positions),
            "total_exposure": str(total_exposure),
            "total_unrealized_pnl": str(total_pnl),
            "total_unrealized_pnl_percent": str(avg_return),
            "positions": [
                {
                    "id": str(pos.id),
                    "symbol": pos.symbol,
                    "side": pos.side.value,
                    "size": str(pos.size),
                    "entry_price": str(pos.entry_price),
                    "current_price": str(pos.current_price or pos.entry_price),
                    "unrealized_pnl": str(pos.unrealized_pnl or Decimal("0")),
                    "unrealized_pnl_percent": str(pos.unrealized_pnl_percent or Decimal("0")),
                }
                for pos in positions
            ]
        }


# Global instance
_service: Optional[PositionService] = None


def init_position_service(positions_collection) -> PositionService:
    """Initialize global position service."""
    global _service
    _service = PositionService(positions_collection)
    logger.info("✅ Position service initialized")
    return _service


def get_position_service() -> PositionService:
    """Get global position service."""
    global _service
    if _service is None:
        raise RuntimeError("Position service not initialized. Call init_position_service() first")
    return _service
