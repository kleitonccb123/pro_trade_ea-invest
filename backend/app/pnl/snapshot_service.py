"""
pnl/snapshot_service.py — Hourly capital-curve snapshots (DOC_05 §6).

Called by BotWorker or APScheduler every hour to record a point on the
equity curve for each running bot. Snapshots feed the performance charts
in the frontend.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId

from app.pnl.calculator import PnLCalculator

logger = logging.getLogger("pnl.snapshot")


async def take_bot_performance_snapshot(
    bot_instance_id: str,
    db: Any,
    current_prices: Dict[str, float],
) -> Optional[str]:
    """
    Persist one equity-curve snapshot for `bot_instance_id`.

    Args:
        bot_instance_id: MongoDB ObjectId string of the bot instance.
        db:              AsyncIOMotorDatabase (Motor).
        current_prices:  dict mapping pair → current price, e.g. {"BTC-USDT": 65000.0}.

    Returns:
        Inserted document _id as string, or None if the bot is not running.
    """
    try:
        instance = await db["user_bot_instances"].find_one(
            {"_id": ObjectId(bot_instance_id)}
        )
    except Exception as exc:
        logger.warning("Snapshot %s — invalid ObjectId: %s", bot_instance_id, exc)
        return None

    if not instance:
        logger.debug("Snapshot %s — instance not found", bot_instance_id)
        return None

    if instance.get("status") != "running":
        logger.debug("Snapshot %s — status=%s (skipped)", bot_instance_id, instance.get("status"))
        return None

    metrics      = instance.get("metrics", {})
    open_position = instance.get("current_position")
    pair         = instance.get("configuration", {}).get("pair", "")

    # ── Unrealized PnL ────────────────────────────────────────────────────────
    unrealized: Dict[str, float] = {}
    if open_position and pair:
        current_price = current_prices.get(pair, 0.0)
        if current_price > 0:
            try:
                unrealized = PnLCalculator.calc_unrealized_pnl(
                    entry_price    = float(open_position.get("entry_price", 0)),
                    current_price  = current_price,
                    entry_quantity = float(open_position.get("quantity", 0)),
                    entry_fee_usdt = float(open_position.get("entry_fee_usdt", 0)),
                )
            except Exception as exc:
                logger.warning("Snapshot %s — unrealized calc error: %s", bot_instance_id, exc)

    realized_pnl   = float(metrics.get("total_pnl_usdt", 0.0))
    unrealized_pnl = unrealized.get("unrealized_pnl_usdt", 0.0)

    snapshot = {
        "bot_instance_id":    bot_instance_id,
        "user_id":            instance.get("user_id", ""),
        "timestamp":          datetime.now(timezone.utc),
        "realized_pnl_usdt":  realized_pnl,
        "unrealized_pnl_usdt": unrealized_pnl,
        "total_pnl_usdt":     round(realized_pnl + unrealized_pnl, 6),
        "capital_usdt":       float(metrics.get("current_capital_usdt", 0.0)),
        "total_trades":       int(metrics.get("total_trades", 0)),
        "win_rate":           float(metrics.get("win_rate", 0.0)),
        "roi_pct":            float(metrics.get("roi_pct", 0.0)),
        "total_fees_usdt":    float(metrics.get("total_fees_usdt", 0.0)),
        "max_drawdown_pct":   float(metrics.get("max_drawdown_pct", 0.0)),
        "profit_factor":      float(metrics.get("profit_factor", 1.0)),
        # Optional: mark-to-market position value
        "current_position_value_usdt": unrealized.get("current_value_usdt", 0.0),
    }

    try:
        result = await db["bot_performance_snapshots"].insert_one(snapshot)
        inserted_id = str(result.inserted_id)
        logger.debug("Snapshot %s saved (id=%s)", bot_instance_id, inserted_id)
        return inserted_id
    except Exception as exc:
        logger.error("Snapshot %s — insert error: %s", bot_instance_id, exc)
        return None


async def take_all_running_bots_snapshot(
    db: Any,
    current_prices: Dict[str, float],
) -> int:
    """
    Convenience function: snapshot every running bot in one call.

    Returns the number of successful snapshots taken.
    Intended to be registered as an APScheduler job every hour.
    """
    cursor = db["user_bot_instances"].find({"status": "running"}, {"_id": 1})
    bot_ids = [str(doc["_id"]) async for doc in cursor]

    count = 0
    for bot_id in bot_ids:
        result = await take_bot_performance_snapshot(bot_id, db, current_prices)
        if result:
            count += 1

    logger.info("Hourly snapshot: %d/%d bots captured", count, len(bot_ids))
    return count
