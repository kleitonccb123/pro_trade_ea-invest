from __future__ import annotations

import asyncio
import logging
import random
import argparse
from typing import List

from app.core.database import init_db
from app.bots import service as bots_service_module
from app.bots.market_data import MarketMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap")


async def run_simulation(bots_count: int = 4, duration_seconds: int = 120):
    """Create bots, start instances, run for duration_seconds and stop cleanly."""
    await init_db()
    service = bots_service_module.BotsService()

    created_instances: List[int] = []

    try:
        logger.info("Creating %s bots...", bots_count)
        for i in range(bots_count):
            name = f"auto-bot-{i+1}"
            symbol = f"FAKE{i+1}USD"
            mode = random.choice([MarketMode.BULL, MarketMode.BEAR, MarketMode.SIDEWAYS])
            config = {"strategy": "rsi_ema", "market_mode": mode}
            bot = await service.create_bot(name, symbol, config)
            instance = await service.create_instance(bot.id, user_id=1, metadata={"auto": True, "mode": mode})
            created_instances.append(instance.id)
            await service.start(instance.id)
            logger.info("Started instance %s for bot %s (mode=%s)", instance.id, bot.name, mode)

        logger.info("Running simulation for %s seconds...", duration_seconds)
        # wait while engine runs (it runs asynchronously)
        await asyncio.sleep(duration_seconds)

    finally:
        logger.info("Stopping %s instances...", len(created_instances))
        for inst_id in created_instances:
            try:
                await service.stop(inst_id)
                logger.info("Stopped instance %s", inst_id)
            except Exception as e:
                logger.exception("Error stopping instance %s: %s", inst_id, e)

        # ensure engine shutdown
        try:
            await service.engine.shutdown()
        except Exception:
            logger.exception("Error shutting down engine")

        logger.info("Simulation finished.")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap simulation: create bots and run simulated engine to generate data.")
    parser.add_argument("--bots", type=int, default=4, help="Number of bots to create (3-5 recommended)")
    parser.add_argument("--duration", type=int, default=120, help="Duration in seconds to run the simulation")
    args = parser.parse_args()

    asyncio.run(run_simulation(bots_count=args.bots, duration_seconds=args.duration))


if __name__ == "__main__":
    main()
