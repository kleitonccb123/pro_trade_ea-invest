"""
Core MongoDB indexes for main application collections.
Called once at startup — safe to re-run (idempotent).
"""
import logging

logger = logging.getLogger(__name__)


async def create_core_indexes() -> None:
    """Create indexes on core business collections."""
    from app.core.database import get_db
    db = get_db()

    # strategies
    await db["strategies"].create_index([("user_id", 1)])
    await db["strategies"].create_index([("is_public", 1), ("created_at", -1)])

    # bots
    await db["bots"].create_index([("user_id", 1)])

    # notifications
    await db["notifications"].create_index([("user_id", 1), ("read_at", 1)])

    # trades
    await db["trades"].create_index([("user_id", 1), ("created_at", -1)])

    # user_2fa — unique per user
    await db["user_2fa"].create_index([("user_id", 1)], unique=True)

    # task queue
    await db["background_tasks"].create_index([("status", 1), ("created_at", 1)])

    logger.info("[OK] Índices principais criados/verificados")
