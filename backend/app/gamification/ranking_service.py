"""
gamification/ranking_service.py — Real trading PnL ranking (DOC_06).

RankingService:
  - compute_ranking()        : MongoDB aggregation → composite score → cache
  - get_cached_ranking()     : Redis → MongoDB fallback
  - setup_ranking_scheduler(): returns AsyncIOScheduler (requires apscheduler)

Schedule: every 15 minutes via APScheduler (or asyncio periodic task fallback).
Cache: Redis TTL 300 s + MongoDB leaderboard_cache collection (upsert).
Quality filter: minimum 5 closed trades AND roi_pct >= -99.

Composite score weights (sum = 1.0):
  roi_pct        0.35
  win_rate       0.25
  total_pnl_usdt 0.20
  profit_factor  0.15
  total_trades   0.05
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("ranking.service")

PERIOD_DAYS       = 30
CACHE_TTL_SECONDS = 300   # 5 min
MIN_TRADES        = 5
MAX_ENTRIES       = 100

# Weights must sum to 1.0
RANKING_WEIGHTS = {
    "roi_pct":        0.35,
    "win_rate":       0.25,
    "total_pnl_usdt": 0.20,
    "profit_factor":  0.15,
    "total_trades":   0.05,
}


class RankingService:
    """
    Computes and caches the real PnL-based leaderboard.

    Usage:
        svc = RankingService(db=motor_db, redis=redis_client)
        entries = await svc.compute_ranking(period_days=30)
        cached  = await svc.get_cached_ranking(period_days=30)
    """

    def __init__(self, db: AsyncIOMotorDatabase, redis):
        self.db    = db
        self.redis = redis

    # ── Aggregation pipeline ─────────────────────────────────────────────────

    async def compute_ranking(self, period_days: int = PERIOD_DAYS) -> List[dict]:
        """
        Run full MongoDB aggregation on bot_trades, compute composite scores,
        persist to leaderboard_cache + Redis and return sorted entries.
        """
        since = datetime.now(timezone.utc) - timedelta(days=period_days)

        pipeline = [
            # ── 1. Only closed trades in window ───────────────────────────────
            {
                "$match": {
                    "status": "closed",
                    "exit_timestamp": {"$gte": since},
                }
            },
            # ── 2. Group by user + bot ────────────────────────────────────────
            {
                "$group": {
                    "_id": {
                        "user_id":       "$user_id",
                        "bot_instance_id": "$bot_instance_id",
                    },
                    "total_pnl_usdt":   {"$sum": "$pnl_net_usdt"},
                    "total_volume_usdt": {"$sum": "$entry_funds"},
                    "total_trades":     {"$sum": 1},
                    "winning_trades":   {
                        "$sum": {
                            "$cond": [{"$gte": ["$pnl_net_usdt", 0]}, 1, 0]
                        }
                    },
                    "total_positive_pnl": {
                        "$sum": {
                            "$cond": [{"$gte": ["$pnl_net_usdt", 0]}, "$pnl_net_usdt", 0]
                        }
                    },
                    "total_negative_pnl": {
                        "$sum": {
                            "$cond": [{"$lt": ["$pnl_net_usdt", 0]}, "$pnl_net_usdt", 0]
                        }
                    },
                    "total_fees_usdt": {
                        "$sum": {"$add": ["$entry_fee_usdt", "$exit_fee_usdt"]}
                    },
                }
            },
            # ── 3. Join bot instance (capital, pair, robot info) ──────────────
            {
                "$lookup": {
                    "from":         "user_bot_instances",
                    "localField":   "_id.bot_instance_id",
                    "foreignField": "_id",
                    "as":           "instance",
                }
            },
            {
                "$unwind": {
                    "path": "$instance",
                    "preserveNullAndEmpty": True,
                }
            },
            # ── 4. Join user (display_name, avatar — NO email) ─────────────────
            {
                "$lookup": {
                    "from":         "users",
                    "localField":   "_id.user_id",
                    "foreignField": "_id",
                    "as":           "user",
                    "pipeline": [
                        # Strict field exclusion — email/api_key NEVER leave DB
                        {
                            "$project": {
                                "email":      0,
                                "password":   0,
                                "api_key":    0,
                                "api_secret": 0,
                            }
                        }
                    ],
                }
            },
            {
                "$unwind": {
                    "path": "$user",
                    "preserveNullAndEmpty": True,
                }
            },
            # ── 5. Derived metrics ────────────────────────────────────────────
            {
                "$addFields": {
                    "initial_capital": {
                        "$ifNull": ["$instance.metrics.initial_capital_usdt", 1000]
                    },
                    "win_rate": {
                        "$cond": [
                            {"$gt": ["$total_trades", 0]},
                            {
                                "$multiply": [
                                    {"$divide": ["$winning_trades", "$total_trades"]},
                                    100,
                                ]
                            },
                            0,
                        ]
                    },
                    "profit_factor": {
                        "$cond": [
                            {"$lt": ["$total_negative_pnl", 0]},
                            {
                                "$min": [
                                    10,  # cap at 10 if no losses
                                    {
                                        "$divide": [
                                            "$total_positive_pnl",
                                            {"$abs": "$total_negative_pnl"},
                                        ]
                                    },
                                ]
                            },
                            10,
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    "roi_pct": {
                        "$multiply": [
                            {"$divide": ["$total_pnl_usdt", "$initial_capital"]},
                            100,
                        ]
                    }
                }
            },
            # ── 6. Quality filters ────────────────────────────────────────────
            {
                "$match": {
                    "total_trades": {"$gte": MIN_TRADES},
                    "roi_pct":      {"$gte": -99},
                }
            },
            # ── 7. Project public fields (no user_id in output, internal only) ──
            {
                "$project": {
                    "_user_id":       "$_id.user_id",      # internal — stripped later
                    "bot_instance_id": "$_id.bot_instance_id",
                    "display_name":   {"$ifNull": ["$user.display_name", "Trader Anônimo"]},
                    "avatar_url":     "$user.avatar_url",
                    "robot_id":       "$instance.robot_id",
                    "robot_name":     "$instance.robot_name",
                    "pair":           "$instance.configuration.pair",
                    "roi_pct":        {"$round": ["$roi_pct", 2]},
                    "win_rate":       {"$round": ["$win_rate", 1]},
                    "total_pnl_usdt": {"$round": ["$total_pnl_usdt", 4]},
                    "profit_factor":  {"$round": ["$profit_factor", 2]},
                    "total_trades":   1,
                    "total_fees_usdt": {"$round": ["$total_fees_usdt", 4]},
                }
            },
            # ── 8. Pre-sort by ROI, limit to top 100 ─────────────────────────
            {"$sort": {"roi_pct": -1}},
            {"$limit": MAX_ENTRIES},
        ]

        try:
            raw = await self.db["bot_trades"].aggregate(pipeline).to_list(length=MAX_ENTRIES)
        except Exception as exc:
            logger.error("Ranking aggregation failed: %s", exc)
            return []

        ranked = self._compute_composite_scores(raw)

        # ── Persist to MongoDB (upsert) ───────────────────────────────────────
        snapshot = {
            "computed_at": datetime.now(timezone.utc),
            "period_days": period_days,
            "entries":     ranked,
        }
        try:
            await self.db["leaderboard_cache"].replace_one(
                {"period_days": period_days},
                snapshot,
                upsert=True,
            )
        except Exception as exc:
            logger.warning("Failed to persist ranking to MongoDB: %s", exc)

        # ── Persist to Redis ──────────────────────────────────────────────────
        try:
            await self.redis.setex(
                f"ranking:{period_days}d",
                CACHE_TTL_SECONDS,
                json.dumps(ranked, default=str),
            )
        except Exception as exc:
            logger.warning("Failed to cache ranking in Redis: %s", exc)

        logger.info("Ranking computed: %d entries (period=%dd)", len(ranked), period_days)
        return ranked

    # ── Composite score calculation ───────────────────────────────────────────

    @staticmethod
    def _compute_composite_scores(results: list) -> list:
        """
        Normalise each metric by its period max and compute weighted score [0-100].
        Sort descending by composite_score, assign rank_position.
        Strips internal _user_id from public output.
        """
        if not results:
            return []

        def _safe_max(key: str) -> float:
            m = max((r.get(key, 0) for r in results), default=1)
            return m if m and m > 0 else 1

        maxima = {
            "roi_pct":        _safe_max("roi_pct"),
            "win_rate":       _safe_max("win_rate"),
            "total_pnl_usdt": _safe_max("total_pnl_usdt"),
            "profit_factor":  _safe_max("profit_factor"),
            "total_trades":   _safe_max("total_trades"),
        }

        for r in results:
            score = 0.0
            for metric, weight in RANKING_WEIGHTS.items():
                value     = max(0.0, float(r.get(metric, 0)))
                normalised = value / maxima[metric]
                score     += normalised * weight * 100
            r["composite_score"] = round(score, 2)

        results.sort(key=lambda x: x["composite_score"], reverse=True)

        for i, r in enumerate(results):
            r["rank_position"] = i + 1
            # Store user_id internally (used by endpoint for self-lookup)
            r["_user_id"] = str(r.pop("_user_id", ""))
            # Serialise ObjectId from _id
            if "_id" in r:
                r["_id"] = str(r["_id"])
            if "bot_instance_id" in r and not isinstance(r["bot_instance_id"], str):
                r["bot_instance_id"] = str(r["bot_instance_id"])

        return results

    # ── Cache read ────────────────────────────────────────────────────────────

    async def get_cached_ranking(self, period_days: int = PERIOD_DAYS) -> Optional[list]:
        """
        Return ranking from Redis (fast) or MongoDB (fallback).
        Returns None if no ranking has been computed yet.
        """
        # ── Redis ──────────────────────────────────────────────────────────────
        try:
            cached = await self.redis.get(f"ranking:{period_days}d")
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.debug("Redis ranking read failed: %s", exc)

        # ── MongoDB ────────────────────────────────────────────────────────────
        try:
            doc = await self.db["leaderboard_cache"].find_one({"period_days": period_days})
            if doc:
                return doc.get("entries", [])
        except Exception as exc:
            logger.debug("MongoDB ranking read failed: %s", exc)

        return None


# ── Scheduler setup ───────────────────────────────────────────────────────────

def setup_ranking_scheduler(ranking_service: RankingService):
    """
    Configure APScheduler to run compute_ranking every 15 minutes.

    Returns the scheduler instance (not started). Call scheduler.start() in
    the FastAPI lifespan or startup event.

    Requires: pip install apscheduler
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "APScheduler is required for the ranking scheduler. "
            "Add `apscheduler>=3.10` to backend/requirements.txt and reinstall."
        ) from exc

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        ranking_service.compute_ranking,
        trigger="interval",
        minutes=15,
        id="compute_ranking_30d",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


async def ranking_periodic_task(ranking_service: RankingService, interval_minutes: int = 15) -> None:
    """
    Pure-asyncio fallback when APScheduler is not installed.

    Usage in FastAPI lifespan:
        asyncio.create_task(ranking_periodic_task(svc))
    """
    while True:
        try:
            await ranking_service.compute_ranking()
        except Exception as exc:
            logger.error("Periodic ranking task error: %s", exc)
        await asyncio.sleep(interval_minutes * 60)
