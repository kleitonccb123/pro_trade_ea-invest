"""
BotInstanceRepository — data access layer for the trading engine collections.

All methods are static; the DB handle is obtained per-call via get_db()
so the module is safe to import in both API and engine processes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from app.core.database import get_db
from app.engine.models import (
    BotMetrics,
    BotStatus,
    BotTrade,
    UserBotInstance,
)

logger = logging.getLogger("engine.repository")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BotInstanceRepository:
    """CRUD + business helpers for `user_bot_instances`."""

    # ── Create ────────────────────────────────────────────────────────────────

    @staticmethod
    async def create(instance: UserBotInstance) -> str:
        """Insert a new bot instance. Returns the string _id."""
        db = get_db()
        doc = instance.to_mongo()
        doc["started_at"] = _utcnow()
        doc["created_at"] = _utcnow()
        doc["updated_at"] = _utcnow()
        result = await db["user_bot_instances"].insert_one(doc)
        return str(result.inserted_id)

    # ── Read ──────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_by_id(bot_id: str) -> Optional[dict]:
        db = get_db()
        return await db["user_bot_instances"].find_one({"_id": ObjectId(bot_id)})

    @staticmethod
    async def get_active_by_user(user_id: str) -> List[dict]:
        db = get_db()
        cursor = db["user_bot_instances"].find(
            {"user_id": user_id, "status": {"$in": ["running", "paused", "pending"]}}
        )
        return await cursor.to_list(length=None)

    @staticmethod
    async def get_all_running() -> List[dict]:
        """Used by orchestrator on startup to restore active bots."""
        db = get_db()
        cursor = db["user_bot_instances"].find({"status": "running"})
        return await cursor.to_list(length=None)

    @staticmethod
    async def get_by_user_and_robot(user_id: str, robot_id: str) -> Optional[dict]:
        db = get_db()
        return await db["user_bot_instances"].find_one(
            {"user_id": user_id, "robot_id": robot_id}
        )

    # ── Update ────────────────────────────────────────────────────────────────

    @staticmethod
    async def update_status(bot_id: str, status: BotStatus, **kwargs) -> None:
        db = get_db()
        fields = {"status": status.value, "updated_at": _utcnow(), **kwargs}
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)}, {"$set": fields}
        )

    @staticmethod
    async def update_heartbeat(bot_id: str) -> None:
        db = get_db()
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)},
            {"$set": {"last_heartbeat": _utcnow()}},
        )

    @staticmethod
    async def update_metrics(bot_id: str, metrics_update: dict) -> None:
        """
        Merge-update specific metric fields.
        e.g. metrics_update = {"total_pnl_usdt": 127.45, "total_trades": 48}
        """
        db = get_db()
        set_fields = {f"metrics.{k}": v for k, v in metrics_update.items()}
        set_fields["updated_at"] = _utcnow()
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)},
            {"$set": set_fields},
        )

    @staticmethod
    async def increment_metrics(bot_id: str, inc_fields: dict) -> None:
        """Atomically increment metric counters (e.g. total_trades += 1)."""
        db = get_db()
        inc = {f"metrics.{k}": v for k, v in inc_fields.items()}
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)},
            {"$inc": inc, "$set": {"updated_at": _utcnow()}},
        )

    @staticmethod
    async def save_strategy_state(bot_id: str, state: dict) -> None:
        """Persist in-memory strategy state for crash-safe restart."""
        db = get_db()
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)},
            {"$set": {"strategy_state": state, "updated_at": _utcnow()}},
        )

    # ── Duplicate check ───────────────────────────────────────────────────────

    @staticmethod
    async def check_duplicate_robot(user_id: str, robot_id: str) -> bool:
        """
        Returns True if the user already has an active instance of this robot.
        The partial unique index enforces this at DB level too.
        """
        db = get_db()
        existing = await db["user_bot_instances"].find_one(
            {
                "user_id": user_id,
                "robot_id": robot_id,
                "status": {"$in": ["running", "pending", "paused"]},
            }
        )
        return existing is not None

    # ── Distributed lock ──────────────────────────────────────────────────────

    @staticmethod
    async def acquire_lock(bot_id: str, symbol: str, ttl_seconds: int = 30) -> bool:
        """
        Attempt to acquire an exclusive lock for (bot_id, symbol).
        Uses MongoDB _id uniqueness as the mutex.
        Returns True if the lock was acquired, False if already held.
        """
        db = get_db()
        lock_key = f"lock:bot:{bot_id}:{symbol}"
        expires_at = _utcnow() + timedelta(seconds=ttl_seconds)
        try:
            await db["bot_locks"].insert_one(
                {
                    "_id": lock_key,
                    "bot_instance_id": bot_id,
                    "acquired_at": _utcnow(),
                    "expires_at": expires_at,
                }
            )
            return True
        except DuplicateKeyError:
            return False
        except Exception as exc:
            logger.warning(f"Falha ao adquirir lock {lock_key}: {exc}")
            return False

    @staticmethod
    async def release_lock(bot_id: str, symbol: str) -> None:
        db = get_db()
        lock_key = f"lock:bot:{bot_id}:{symbol}"
        await db["bot_locks"].delete_one({"_id": lock_key})


class BotTradeRepository:
    """CRUD for `bot_trades`."""

    @staticmethod
    async def insert(trade: BotTrade) -> str:
        db = get_db()
        doc = trade.model_dump(exclude={"id"})
        doc["side"] = trade.side.value
        doc["status"] = trade.status.value
        try:
            result = await db["bot_trades"].insert_one(doc)
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(
                f"Trade duplicado ignorado: exchange_order_id={trade.exchange_order_id}"
            )
            return ""

    @staticmethod
    async def get_by_instance(
        bot_id: str, limit: int = 50, skip: int = 0
    ) -> List[dict]:
        db = get_db()
        cursor = (
            db["bot_trades"]
            .find({"bot_instance_id": bot_id})
            .sort("executed_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=None)

    @staticmethod
    async def get_by_user(
        user_id: str, limit: int = 100, skip: int = 0
    ) -> List[dict]:
        db = get_db()
        cursor = (
            db["bot_trades"]
            .find({"user_id": user_id})
            .sort("executed_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=None)

    @staticmethod
    async def count_by_instance(bot_id: str) -> int:
        db = get_db()
        return await db["bot_trades"].count_documents({"bot_instance_id": bot_id})


class BotSnapshotRepository:
    """CRUD for `bot_performance_snapshots`."""

    @staticmethod
    async def upsert_daily(snapshot: dict) -> None:
        """Insert or replace the daily snapshot (unique per bot + date + type)."""
        db = get_db()
        filter_q = {
            "bot_instance_id": snapshot["bot_instance_id"],
            "snapshot_date": snapshot["snapshot_date"],
            "snapshot_type": snapshot.get("snapshot_type", "daily"),
        }
        await db["bot_performance_snapshots"].update_one(
            filter_q, {"$set": snapshot}, upsert=True
        )

    @staticmethod
    async def get_latest(bot_id: str, limit: int = 30) -> List[dict]:
        db = get_db()
        cursor = (
            db["bot_performance_snapshots"]
            .find({"bot_instance_id": bot_id})
            .sort("snapshot_date", DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=None)

    @staticmethod
    async def get_ranking(
        robot_id: str, days: int = 15, limit: int = 50
    ) -> List[dict]:
        """
        Returns the top instances of a given robot ranked by period_pnl_usdt
        in the last `days` days. Used for marketplace ranking.
        """
        from datetime import date
        cutoff = _utcnow() - timedelta(days=days)
        db = get_db()
        cursor = (
            db["bot_performance_snapshots"]
            .find({"robot_id": robot_id, "snapshot_date": {"$gte": cutoff}})
            .sort("period_pnl_usdt", DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=None)
