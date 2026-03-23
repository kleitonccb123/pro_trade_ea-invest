"""
Bot Repository - MongoDB Implementation with Motor

This module provides async database operations for Bot documents.
Handles bot configurations, instances, and trading history.

Collections:
- bots: Bot configurations/templates
- bot_instances: Running bot instances
- bot_trades: Trade history for bots

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from enum import Enum

from app.core.database import get_db

logger = logging.getLogger(__name__)


class BotState(str, Enum):
    """Bot instance states."""
    idle = "idle"
    running = "running"
    paused = "paused"
    stopped = "stopped"
    error = "error"


class BotRepository:
    """
    Repository for Bot CRUD operations in MongoDB.
    
    Manages:
    - Bot templates/configurations
    - Bot instances (running bots)
    - Trade history
    """
    
    COLLECTION_BOTS = "bots"
    COLLECTION_INSTANCES = "bot_instances"
    COLLECTION_TRADES = "bot_trades"
    
    # ==================== BOT TEMPLATES ====================
    
    @classmethod
    def _get_bots_collection(cls):
        """Get the bots collection."""
        db = get_db()
        return db[cls.COLLECTION_BOTS]
    
    @classmethod
    def _get_instances_collection(cls):
        """Get the bot_instances collection."""
        db = get_db()
        return db[cls.COLLECTION_INSTANCES]
    
    @classmethod
    def _get_trades_collection(cls):
        """Get the bot_trades collection."""
        db = get_db()
        return db[cls.COLLECTION_TRADES]
    
    @classmethod
    async def create_bot(
        cls,
        user_id: str | ObjectId,
        name: str,
        symbol: str,
        strategy: str = "default",
        config: Dict = None,
        **extra_fields
    ) -> Dict[str, Any]:
        """
        Create a new bot configuration.
        
        Args:
            user_id: Owner's user ID
            name: Bot display name
            symbol: Trading pair (e.g., "BTC/USDT")
            strategy: Strategy name/type
            config: Strategy configuration
            extra_fields: Additional fields
            
        Returns:
            Created bot document
        """
        collection = cls._get_bots_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        now = datetime.utcnow()
        bot_doc = {
            "user_id": user_id,
            "name": name,
            "symbol": symbol,
            "strategy": strategy,
            "config": config or {},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            # Statistics
            "total_trades": 0,
            "total_profit": 0.0,
            "win_rate": 0.0,
            **extra_fields
        }
        
        result = await collection.insert_one(bot_doc)
        bot_doc["_id"] = result.inserted_id
        
        logger.info(f"? Created bot: {name} ({symbol})")
        return bot_doc
    
    @classmethod
    async def find_bot_by_id(cls, bot_id: str | ObjectId) -> Optional[Dict[str, Any]]:
        """Find bot by ID."""
        collection = cls._get_bots_collection()
        
        if isinstance(bot_id, str):
            try:
                bot_id = ObjectId(bot_id)
            except Exception:
                return None
        
        return await collection.find_one({"_id": bot_id})
    
    @classmethod
    async def find_user_bots(
        cls,
        user_id: str | ObjectId,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Find all bots owned by a user."""
        collection = cls._get_bots_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        query = {"user_id": user_id}
        if active_only:
            query["is_active"] = True
        
        cursor = collection.find(query).sort("created_at", -1)
        return await cursor.to_list(length=100)
    
    @classmethod
    async def find_all_bots(
        cls,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find all bots with pagination."""
        collection = cls._get_bots_collection()
        cursor = collection.find().skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
    
    @classmethod
    async def update_bot(
        cls,
        bot_id: str | ObjectId,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update bot configuration."""
        collection = cls._get_bots_collection()
        
        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)
        
        updates["updated_at"] = datetime.utcnow()
        
        result = await collection.find_one_and_update(
            {"_id": bot_id},
            {"$set": updates},
            return_document=True
        )
        return result
    
    @classmethod
    async def delete_bot(cls, bot_id: str | ObjectId) -> bool:
        """Delete bot by ID."""
        collection = cls._get_bots_collection()
        
        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)
        
        result = await collection.delete_one({"_id": bot_id})
        return result.deleted_count > 0
    
    # ==================== BOT INSTANCES ====================
    
    @classmethod
    async def create_instance(
        cls,
        bot_id: str | ObjectId,
        user_id: str | ObjectId,
        exchange: str = "binance",
        is_live: bool = False,
        initial_balance: float = 10000.0,
        **extra_fields
    ) -> Dict[str, Any]:
        """
        Create a new bot instance (running bot).
        
        Args:
            bot_id: Parent bot configuration ID
            user_id: Owner's user ID
            exchange: Exchange to trade on
            is_live: True for real trading, False for simulation
            initial_balance: Starting balance (for simulation)
            extra_fields: Additional fields
            
        Returns:
            Created instance document
        """
        collection = cls._get_instances_collection()
        
        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        now = datetime.utcnow()
        instance_doc = {
            "bot_id": bot_id,
            "user_id": user_id,
            "exchange": exchange,
            "is_live": is_live,
            "state": BotState.idle.value,
            "initial_balance": initial_balance,
            "current_balance": initial_balance,
            "total_pnl": 0.0,
            "total_pnl_percent": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "max_drawdown": 0.0,
            "created_at": now,
            "started_at": None,
            "stopped_at": None,
            "last_trade_at": None,
            "error_message": None,
            **extra_fields
        }
        
        result = await collection.insert_one(instance_doc)
        instance_doc["_id"] = result.inserted_id
        
        logger.info(f"? Created bot instance: {result.inserted_id}")
        return instance_doc
    
    @classmethod
    async def find_instance_by_id(
        cls,
        instance_id: str | ObjectId
    ) -> Optional[Dict[str, Any]]:
        """Find bot instance by ID."""
        collection = cls._get_instances_collection()
        
        if isinstance(instance_id, str):
            try:
                instance_id = ObjectId(instance_id)
            except Exception:
                return None
        
        return await collection.find_one({"_id": instance_id})
    
    @classmethod
    async def find_user_instances(
        cls,
        user_id: str | ObjectId,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Find all instances for a user."""
        collection = cls._get_instances_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        query = {"user_id": user_id}
        if active_only:
            query["state"] = {"$in": [BotState.running.value, BotState.paused.value]}
        
        cursor = collection.find(query).sort("created_at", -1)
        return await cursor.to_list(length=100)
    
    @classmethod
    async def find_running_instances(cls) -> List[Dict[str, Any]]:
        """Find all currently running instances."""
        collection = cls._get_instances_collection()
        cursor = collection.find({"state": BotState.running.value})
        return await cursor.to_list(length=1000)
    
    @classmethod
    async def update_instance_state(
        cls,
        instance_id: str | ObjectId,
        state: BotState | str,
        error_message: str = None
    ) -> Optional[Dict[str, Any]]:
        """Update instance state."""
        collection = cls._get_instances_collection()
        
        if isinstance(instance_id, str):
            instance_id = ObjectId(instance_id)
        
        if isinstance(state, BotState):
            state = state.value
        
        updates = {"state": state}
        
        if state == BotState.running.value:
            updates["started_at"] = datetime.utcnow()
            updates["error_message"] = None
        elif state == BotState.stopped.value:
            updates["stopped_at"] = datetime.utcnow()
        elif state == BotState.error.value:
            updates["error_message"] = error_message
        
        return await collection.find_one_and_update(
            {"_id": instance_id},
            {"$set": updates},
            return_document=True
        )
    
    @classmethod
    async def update_instance_stats(
        cls,
        instance_id: str | ObjectId,
        balance: float,
        pnl: float,
        total_trades: int,
        winning_trades: int,
        max_drawdown: float = None
    ) -> Optional[Dict[str, Any]]:
        """Update instance trading statistics."""
        collection = cls._get_instances_collection()
        
        if isinstance(instance_id, str):
            instance_id = ObjectId(instance_id)
        
        # Get instance to calculate PnL percent
        instance = await cls.find_instance_by_id(instance_id)
        if not instance:
            return None
        
        initial_balance = instance.get("initial_balance", 10000)
        pnl_percent = ((balance - initial_balance) / initial_balance) * 100 if initial_balance > 0 else 0
        
        updates = {
            "current_balance": balance,
            "total_pnl": pnl,
            "total_pnl_percent": pnl_percent,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "last_trade_at": datetime.utcnow(),
        }
        
        if max_drawdown is not None:
            updates["max_drawdown"] = max_drawdown
        
        return await collection.find_one_and_update(
            {"_id": instance_id},
            {"$set": updates},
            return_document=True
        )
    
    # ==================== BOT TRADES ====================
    
    @classmethod
    async def record_trade(
        cls,
        instance_id: str | ObjectId,
        user_id: str | ObjectId,
        symbol: str,
        side: str,  # "buy" or "sell"
        quantity: float,
        price: float,
        pnl: float = 0.0,
        is_simulated: bool = True,
        **extra_fields
    ) -> Dict[str, Any]:
        """
        Record a trade executed by a bot.
        
        Args:
            instance_id: Bot instance that made the trade
            user_id: User who owns the bot
            symbol: Trading pair
            side: "buy" or "sell"
            quantity: Amount traded
            price: Execution price
            pnl: Profit/loss from trade (for closing trades)
            is_simulated: True if simulation, False if real
            extra_fields: Additional trade data
            
        Returns:
            Created trade document
        """
        collection = cls._get_trades_collection()
        
        if isinstance(instance_id, str):
            instance_id = ObjectId(instance_id)
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        trade_doc = {
            "instance_id": instance_id,
            "user_id": user_id,
            "symbol": symbol,
            "side": side.lower(),
            "quantity": quantity,
            "price": price,
            "value": quantity * price,
            "pnl": pnl,
            "is_simulated": is_simulated,
            "timestamp": datetime.utcnow(),
            **extra_fields
        }
        
        result = await collection.insert_one(trade_doc)
        trade_doc["_id"] = result.inserted_id
        
        logger.info(f"? Recorded trade: {side} {quantity} {symbol} @ {price}")
        return trade_doc
    
    @classmethod
    async def find_instance_trades(
        cls,
        instance_id: str | ObjectId,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find trades for a specific bot instance."""
        collection = cls._get_trades_collection()
        
        if isinstance(instance_id, str):
            instance_id = ObjectId(instance_id)
        
        cursor = collection.find({"instance_id": instance_id}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    @classmethod
    async def find_user_trades(
        cls,
        user_id: str | ObjectId,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find all trades for a user across all bots."""
        collection = cls._get_trades_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        cursor = collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    @classmethod
    async def get_instance_stats(cls, instance_id: str | ObjectId) -> Dict[str, Any]:
        """Calculate trading statistics for an instance."""
        collection = cls._get_trades_collection()
        
        if isinstance(instance_id, str):
            instance_id = ObjectId(instance_id)
        
        trades = await cls.find_instance_trades(instance_id, limit=10000)
        
        if not trades:
            return {
                "total_trades": 0,
                "total_pnl": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }
        
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) < 0]
        
        return {
            "total_trades": len(trades),
            "total_pnl": total_pnl,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": len(wins) / len(trades) * 100 if trades else 0,
            "avg_win": sum(t["pnl"] for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t["pnl"] for t in losses) / len(losses) if losses else 0,
        }
    
    # ==================== HELPER METHODS FOR WEBSOCKET ====================
    
    @classmethod
    async def get_latest_instance(cls, bot_id: str | ObjectId) -> Optional[Dict[str, Any]]:
        """
        Get the latest/most recent instance for a bot.
        
        Used by WebSocket PnL updates to get current bot state.
        
        Args:
            bot_id: Bot ID (can be int-like string or ObjectId string)
            
        Returns:
            Most recent instance document or None
        """
        collection = cls._get_instances_collection()
        
        # Try to handle both integer-like IDs and ObjectIds
        query = None
        
        if isinstance(bot_id, str):
            # Try as ObjectId first
            try:
                obj_id = ObjectId(bot_id)
                query = {"bot_id": obj_id}
            except Exception:
                # Try as integer bot_id stored differently
                try:
                    query = {"bot_id": int(bot_id)}
                except ValueError:
                    # Use as string
                    query = {"bot_id": bot_id}
        elif isinstance(bot_id, ObjectId):
            query = {"bot_id": bot_id}
        else:
            query = {"bot_id": bot_id}
        
        # Get the most recent instance
        cursor = collection.find(query).sort("created_at", -1).limit(1)
        instances = await cursor.to_list(length=1)
        
        return instances[0] if instances else None
    
    @classmethod
    async def get_instance_trades(
        cls,
        instance_id: str | ObjectId,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Alias for find_instance_trades for WebSocket compatibility.
        """
        return await cls.find_instance_trades(instance_id, limit)
    
    # ==================== INDEXES ====================
    
    @classmethod
    async def ensure_indexes(cls) -> None:
        """Create necessary indexes for bot collections."""
        db = await get_db()
        
        try:
            # Bots collection indexes
            bots = db[cls.COLLECTION_BOTS]
            await bots.create_index("user_id")
            await bots.create_index("symbol")
            await bots.create_index("is_active")
            
            # Instances collection indexes
            instances = db[cls.COLLECTION_INSTANCES]
            await instances.create_index("bot_id")
            await instances.create_index("user_id")
            await instances.create_index("state")
            await instances.create_index([("user_id", 1), ("state", 1)])
            
            # Trades collection indexes
            trades = db[cls.COLLECTION_TRADES]
            await trades.create_index("instance_id")
            await trades.create_index("user_id")
            await trades.create_index("timestamp")
            await trades.create_index([("instance_id", 1), ("timestamp", -1)])
            
            logger.info("? Created indexes for bot collections")
        except Exception as e:
            logger.warning(f"??  Could not create indexes: {e}")


# Convenience instance
bot_repository = BotRepository()

# Alias for easier import
BotsRepository = BotRepository
