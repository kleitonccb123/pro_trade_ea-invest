#!/usr/bin/env python
"""Script to add user_id to existing bots for the demo user.

Usage:
  python scripts/add_user_to_bots.py

This script will find the demo user and add user_id to all bots that don't have one.
"""
from __future__ import annotations

import asyncio
import os
import logging

from app.core.database import connect_db, disconnect_db, get_db
from app.users.repository import UserRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("add_user_to_bots")


async def main():
    # Ensure offline mode is disabled
    os.environ.setdefault("OFFLINE_MODE", "false")

    await connect_db()

    # Find demo user
    demo_email = "demo@tradehub.com"
    user = await UserRepository.find_by_email(demo_email)
    if not user:
        logger.error(f"Demo user not found: {demo_email}")
        await disconnect_db()
        return

    user_id = str(user["_id"])
    logger.info(f"Found demo user: {demo_email} id={user_id}")

    # Get database
    db = get_db()
    bots_col = db["bots"]

    # Find bots without user_id
    bots_without_user = await bots_col.find({"user_id": {"$exists": False}}).to_list(None)
    logger.info(f"Found {len(bots_without_user)} bots without user_id")

    # Update bots to add user_id
    for bot in bots_without_user:
        await bots_col.update_one(
            {"_id": bot["_id"]},
            {"$set": {"user_id": user_id}}
        )
        logger.info(f"Updated bot {bot.get('name', bot['_id'])} with user_id {user_id}")

    # If no bots exist, create a default bot
    total_bots = await bots_col.count_documents({"user_id": user_id})
    if total_bots == 0:
        logger.info("No bots found for user, creating a default bot...")
        default_bot = {
            "user_id": user_id,
            "name": "Demo Bot",
            "description": "Bot de demonstra??o",
            "strategy": "Custom Strategy",
            "exchange": "binance",
            "pair": "BTC/USDT",
            "status": "stopped",
            "is_running": False,
            "config": {
                "amount": 1000.0,
                "stop_loss": 5.0,
                "take_profit": 10.0,
                "risk_level": "medium",
                "timeframe": "5m",
                "indicators": ["RSI", "MACD"],
                "strategy": "Custom Strategy"
            },
            "profit": 0.0,
            "trades": 0,
            "win_rate": 0.0,
            "runtime": "0h 0m",
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0
        }
        result = await bots_col.insert_one(default_bot)
        logger.info(f"Created default bot with id {result.inserted_id}")

    await disconnect_db()
    logger.info("Script completed successfully")


if __name__ == "__main__":
    asyncio.run(main())