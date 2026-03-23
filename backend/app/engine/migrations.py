"""
MongoDB index migrations for the trading engine — DOC_02 §6.

Called once during engine and API startup via create_indexes().
Motor's create_index is idempotent — safe to call on every restart.
"""

from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING

from app.core.database import get_db

logger = logging.getLogger("engine.migrations")


async def create_indexes() -> None:
    """Create all required indexes for the trading engine collections."""
    db = get_db()

    # ── user_bot_instances ────────────────────────────────────────────────────
    col = db["user_bot_instances"]

    # Most common query: user's bots filtered by status
    await col.create_index([("user_id", ASCENDING), ("status", ASCENDING)])

    # Marketplace ranking: bots per robot
    await col.create_index([("robot_id", ASCENDING), ("status", ASCENDING)])

    # Heartbeat monitor (detect dead workers)
    await col.create_index([("last_heartbeat", ASCENDING)])

    # Uniqueness constraint: one active instance per (user, robot)
    # partial filter ensures constraint only applies to active statuses
    await col.create_index(
        [("user_id", ASCENDING), ("robot_id", ASCENDING), ("status", ASCENDING)],
        unique=True,
        partialFilterExpression={"status": {"$in": ["running", "pending", "paused"]}},
        name="unique_active_robot_per_user",
    )

    logger.info("✅ Indexes criados: user_bot_instances")

    # ── bot_trades ────────────────────────────────────────────────────────────
    col = db["bot_trades"]

    # Trade history per instance (primary read pattern)
    await col.create_index(
        [("bot_instance_id", ASCENDING), ("executed_at", DESCENDING)]
    )

    # Trade history per user (dashboard)
    await col.create_index(
        [("user_id", ASCENDING), ("executed_at", DESCENDING)]
    )

    # Exchange order reconciliation — MUST be unique to prevent duplicates
    await col.create_index(
        [("exchange_order_id", ASCENDING)],
        unique=True,
        name="unique_exchange_order_id",
    )

    # Ranking P&L queries
    await col.create_index(
        [("robot_id", ASCENDING), ("executed_at", DESCENDING), ("realized_pnl_usdt", DESCENDING)]
    )

    logger.info("✅ Indexes criados: bot_trades")

    # ── bot_performance_snapshots ─────────────────────────────────────────────
    col = db["bot_performance_snapshots"]

    # Latest snapshot for a given instance
    await col.create_index(
        [("bot_instance_id", ASCENDING), ("snapshot_date", DESCENDING)]
    )

    # Ranking queries (covers robot_id + date range + pnl sort)
    await col.create_index(
        [
            ("robot_id", ASCENDING),
            ("snapshot_date", DESCENDING),
            ("period_pnl_usdt", DESCENDING),
        ]
    )

    # One snapshot per (bot instance, date, type)
    await col.create_index(
        [
            ("bot_instance_id", ASCENDING),
            ("snapshot_date", ASCENDING),
            ("snapshot_type", ASCENDING),
        ],
        unique=True,
        name="unique_snapshot_per_bot_per_day",
    )

    logger.info("✅ Indexes criados: bot_performance_snapshots")

    # ── bot_execution_logs ────────────────────────────────────────────────────
    col = db["bot_execution_logs"]

    # UI: recent logs per instance
    await col.create_index(
        [("bot_instance_id", ASCENDING), ("timestamp", DESCENDING)]
    )

    # TTL: auto-delete logs older than 30 days (2 592 000 seconds)
    await col.create_index(
        [("timestamp", ASCENDING)],
        expireAfterSeconds=2_592_000,
        name="ttl_30_days",
    )

    # Partial index for error alerting queries
    await col.create_index(
        [("level", ASCENDING), ("timestamp", DESCENDING)],
        partialFilterExpression={"level": {"$in": ["ERROR", "CRITICAL"]}},
        name="error_logs_idx",
    )

    logger.info("✅ Indexes criados: bot_execution_logs")

    # ── bot_locks ─────────────────────────────────────────────────────────────
    col = db["bot_locks"]

    # TTL = 0 → MongoDB deletes the document exactly when expires_at is reached
    await col.create_index(
        [("expires_at", ASCENDING)],
        expireAfterSeconds=0,
        name="ttl_lock_expiry",
    )

    logger.info("✅ Indexes criados: bot_locks")
    logger.info("🗄️  Migração de índices concluída com sucesso")
