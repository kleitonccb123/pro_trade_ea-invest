# Strategies Repository - Motor/MongoDB implementation
import logging
from datetime import datetime
from bson import ObjectId
from app.core.database import get_db

logger = logging.getLogger(__name__)


class StrategyRepository:

    def __init__(self, session=None):
        self.db = get_db()

    async def create_strategy(self, user_id: str, data: dict) -> dict:
        data["user_id"] = user_id
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        result = await self.db["strategies"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data

    async def get_strategies(self, user_id: str, skip: int = 0, limit: int = 50) -> list:
        cursor = self.db["strategies"].find({"user_id": user_id}).skip(skip).limit(limit).sort("created_at", -1)
        strategies = []
        async for s in cursor:
            s["_id"] = str(s["_id"])
            strategies.append(s)
        return strategies

    async def delete_strategy(self, user_id: str, strategy_id: str) -> bool:
        try:
            obj_id = ObjectId(strategy_id)
        except Exception:
            obj_id = strategy_id
        result = await self.db["strategies"].delete_one({"_id": obj_id, "user_id": user_id})
        return result.deleted_count > 0

    async def create_bot_instance(self, data: dict) -> dict:
        data["created_at"] = datetime.utcnow()
        data["started_at"] = datetime.utcnow()
        data["status"] = data.get("status", "created")
        result = await self.db["bot_instances"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data

    async def delete_bot_instances(self, user_id: str, bot_id: str) -> int:
        try:
            obj_id = ObjectId(bot_id)
        except Exception:
            obj_id = bot_id
        result = await self.db["bot_instances"].delete_many({"bot_id": obj_id, "user_id": user_id})
        return result.deleted_count

    async def get_bot_instances(self, user_id: str, bot_id: str = None, limit: int = 100) -> list:
        query = {"user_id": user_id}
        if bot_id:
            query["bot_id"] = bot_id
        cursor = self.db["bot_instances"].find(query).sort("started_at", -1).limit(limit)
        instances = []
        async for inst in cursor:
            inst["_id"] = str(inst["_id"])
            instances.append(inst)
        return instances

    async def update_bot_instance(self, instance_id: str, data: dict) -> bool:
        try:
            obj_id = ObjectId(instance_id)
        except Exception:
            obj_id = instance_id
        data["updated_at"] = datetime.utcnow()
        result = await self.db["bot_instances"].update_one({"_id": obj_id}, {"$set": data})
        return result.modified_count > 0

    async def create_trade(self, data: dict) -> dict:
        data["created_at"] = datetime.utcnow()
        result = await self.db["trades"].insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data

    async def get_trades(self, user_id: str, bot_id: str = None, skip: int = 0, limit: int = 50) -> list:
        query = {"user_id": user_id}
        if bot_id:
            query["bot_id"] = bot_id
        cursor = self.db["trades"].find(query).skip(skip).limit(limit).sort("created_at", -1)
        trades = []
        async for t in cursor:
            t["_id"] = str(t["_id"])
            trades.append(t)
        return trades

    async def get_trades_count(self, user_id: str, bot_id: str = None) -> int:
        query = {"user_id": user_id}
        if bot_id:
            query["bot_id"] = bot_id
        return await self.db["trades"].count_documents(query)

    async def get_trades_stats(self, user_id: str, bot_id: str = None) -> dict:
        query = {"user_id": user_id}
        if bot_id:
            query["bot_id"] = bot_id
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": None,
                "total_trades": {"$sum": 1},
                "total_pnl": {"$sum": {"$ifNull": ["$pnl", 0]}},
                "total_volume": {"$sum": {"$ifNull": ["$volume", 0]}},
                "win_count": {"$sum": {"$cond": [{"$gt": [{"$ifNull": ["$pnl", 0]}, 0]}, 1, 0]}},
                "loss_count": {"$sum": {"$cond": [{"$lt": [{"$ifNull": ["$pnl", 0]}, 0]}, 1, 0]}},
            }}
        ]
        result = await self.db["trades"].aggregate(pipeline).to_list(1)
        if result:
            stats = result[0]
            stats.pop("_id", None)
            total = stats.get("total_trades", 0)
            stats["win_rate"] = (stats.get("win_count", 0) / total * 100) if total > 0 else 0
            return stats
        return {"total_trades": 0, "total_pnl": 0, "total_volume": 0, "win_count": 0, "loss_count": 0, "win_rate": 0}

    async def update_trade(self, trade_id: str, data: dict) -> bool:
        try:
            obj_id = ObjectId(trade_id)
        except Exception:
            obj_id = trade_id
        data["updated_at"] = datetime.utcnow()
        result = await self.db["trades"].update_one({"_id": obj_id}, {"$set": data})
        return result.modified_count > 0



