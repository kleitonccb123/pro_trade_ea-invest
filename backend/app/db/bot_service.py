"""
Bot Service - CRUD operations for trading bots.

Manages bot creation, updates, and state transitions.
"""

from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.db.models import Bot, BotStatus

logger = logging.getLogger(__name__)


class BotService:
    """Database service for bot operations."""
    
    def __init__(self, db_collection):
        """
        Initialize bot service.
        
        Args:
            db_collection: MongoDB collection for bots
        """
        self.db = db_collection
    
    async def create_bot(
        self,
        user_id: str,
        name: str,
        exchange: str,
        account_id: str,
        symbol: str,
        strategy_type: str,
        config: dict,
        risk_config: Optional[dict] = None,
    ) -> Bot:
        """
        Create new trading bot.
        
        Args:
            user_id: User ID
            name: Bot name
            exchange: Exchange (kucoin, binance)
            account_id: Exchange account ID
            symbol: Trading symbol (BTC-USDT)
            strategy_type: Strategy name (sma_crossover, etc)
            config: Strategy configuration dict
            risk_config: Risk management settings
            
        Returns:
            Created Bot object with _id set
        """
        bot = Bot(
            user_id=user_id,
            name=name,
            exchange=exchange,
            account_id=account_id,
            symbol=symbol,
            strategy_type=strategy_type,
            config=config,
            risk_config=risk_config or {},
        )
        
        result = await self.db.insert_one(bot.model_dump(by_alias=True, exclude_none=True))
        bot.id = result.inserted_id
        
        logger.info(f"✅ Bot '{name}' created for user {user_id} (id: {result.inserted_id})")
        
        return bot
    
    async def get_bot(self, bot_id: str, user_id: str) -> Optional[Bot]:
        """
        Get bot by ID (with ownership check).
        
        Args:
            bot_id: Bot ID
            user_id: User ID (for ownership verification)
            
        Returns:
            Bot object or None if not found
        """
        doc = await self.db.find_one({
            "_id": ObjectId(bot_id),
            "user_id": user_id
        })
        
        if not doc:
            logger.warning(f"Bot {bot_id} not found for user {user_id}")
            return None
        
        return Bot.model_validate(doc)
    
    async def list_bots(self, user_id: str, status: Optional[str] = None) -> List[Bot]:
        """
        List all bots for user.
        
        Args:
            user_id: User ID
            status: Optional status filter (running, stopped, etc)
            
        Returns:
            List of Bot objects
        """
        query = {"user_id": user_id}
        
        if status:
            query["status"] = status
        
        docs = await self.db.find(query).to_list(length=None)
        
        return [Bot.model_validate(doc) for doc in docs]
    
    async def update_bot_status(
        self,
        bot_id: str,
        status: BotStatus,
        error_message: Optional[str] = None,
    ) -> Optional[Bot]:
        """
        Update bot status (RUNNING, STOPPED, ERROR, etc).
        
        Args:
            bot_id: Bot ID
            status: New status
            error_message: Optional error message for ERROR status
            
        Returns:
            Updated Bot object or None if not found
        """
        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow(),
        }
        
        # Add timestamp based on status
        if status == BotStatus.RUNNING:
            update_data["started_at"] = datetime.utcnow()
        elif status == BotStatus.STOPPED:
            update_data["stopped_at"] = datetime.utcnow()
        
        # Add error if provided
        if error_message:
            update_data["error_message"] = error_message
        
        result = await self.db.find_one_and_update(
            {"_id": ObjectId(bot_id)},
            {"$set": update_data},
            return_document=True
        )
        
        if not result:
            logger.warning(f"Bot {bot_id} not found for status update")
            return None
        
        logger.info(f"✅ Bot {bot_id} status updated to {status}")
        
        return Bot.model_validate(result)
    
    async def update_bot_statistics(
        self,
        bot_id: str,
        trades_count: int,
        total_pnl,
        win_rate,
    ) -> Optional[Bot]:
        """
        Update bot trading statistics.
        
        Args:
            bot_id: Bot ID
            trades_count: Total number of trades executed
            total_pnl: Total profit/loss (Decimal)
            win_rate: Win rate percentage (Decimal)
            
        Returns:
            Updated Bot object
        """
        result = await self.db.find_one_and_update(
            {"_id": ObjectId(bot_id)},
            {
                "$set": {
                    "trades_count": trades_count,
                    "total_pnl": str(total_pnl),
                    "win_rate": str(win_rate),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True
        )
        
        if not result:
            return None
        
        return Bot.model_validate(result)
    
    async def update_bot_config(
        self,
        bot_id: str,
        config: dict,
    ) -> Optional[Bot]:
        """
        Update bot strategy configuration.
        
        Cannot update while bot is running.
        
        Args:
            bot_id: Bot ID
            config: New configuration dict
            
        Returns:
            Updated Bot object
        """
        # Get current bot to check status
        bot_doc = await self.db.find_one({"_id": ObjectId(bot_id)})
        
        if not bot_doc:
            return None
        
        bot = Bot.model_validate(bot_doc)
        
        if bot.status == BotStatus.RUNNING:
            logger.warning(f"Cannot update config for running bot {bot_id}")
            raise ValueError("Cannot update configuration while bot is running")
        
        result = await self.db.find_one_and_update(
            {"_id": ObjectId(bot_id)},
            {
                "$set": {
                    "config": config,
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True
        )
        
        return Bot.model_validate(result) if result else None
    
    async def delete_bot(self, bot_id: str, user_id: str) -> bool:
        """
        Delete bot (only if stopped).
        
        Args:
            bot_id: Bot ID
            user_id: User ID
            
        Returns:
            True if deleted, False if not found or still running
        """
        # Check bot status
        bot = await self.get_bot(bot_id, user_id)
        
        if not bot:
            return False
        
        if bot.status == BotStatus.RUNNING:
            logger.warning(f"Cannot delete running bot {bot_id}")
            raise ValueError("Cannot delete bot while it is running")
        
        result = await self.db.delete_one({
            "_id": ObjectId(bot_id),
            "user_id": user_id
        })
        
        if result.deleted_count > 0:
            logger.info(f"✅ Bot {bot_id} deleted")
            return True
        
        return False


# Global instance
_service: Optional[BotService] = None


def init_bot_service(db_collection) -> BotService:
    """Initialize global bot service."""
    global _service
    _service = BotService(db_collection)
    logger.info("✅ Bot service initialized")
    return _service


def get_bot_service() -> BotService:
    """Get global bot service."""
    global _service
    if _service is None:
        raise RuntimeError("Bot service not initialized. Call init_bot_service() first")
    return _service
