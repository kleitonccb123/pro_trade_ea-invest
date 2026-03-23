from __future__ import annotations

import asyncio
import logging

# from app.core.database import init_db, AsyncSessionLocal  # TODO: Migrar para MongoDB
from app.bots import repository as bots_repo
from app.bots.engine import BotEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Ensure DB tables exist
    await init_db()

    # create a demo bot and instance
    async with AsyncSessionLocal() as db:
        bot = await bots_repo.create_bot(db, name="demo-rsi-ema", symbol="FAKEUSD", config={"notes": "simulated"})
        instance = await bots_repo.create_instance(db, bot.id, user_id="507f1f77bcf86cd799439011", metadata={"run": "demo"})

    engine = BotEngine()
    # start instance
    await engine.start_instance(instance.id)

    # wait for engine tasks to complete (they stop themselves)
    await asyncio.sleep(30)
    await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
