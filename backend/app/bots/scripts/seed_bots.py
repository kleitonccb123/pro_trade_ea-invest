from __future__ import annotations

import asyncio
import random
import pathlib
import sys

# Ensure backend path is importable when running as script
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# from app.core.database import init_db, AsyncSessionLocal  # TODO: Migrar para MongoDB
from app.bots import repository as bots_repo
from app.bots import model as bots_model


async def seed():
    await init_db()
    created = {"bots": 0, "instances": 0, "trades": 0}

    async with AsyncSessionLocal() as db:
        # create 3 bots
        defs = [("Seed Running Bot", "BTC"), ("Seed Paused Bot", "ETH"), ("Seed Stopped Bot", "SOL")]
        bots = []
        for name, symbol in defs:
            b = await bots_repo.create_bot(db, name=name, symbol=symbol, config={"seed": True})
            bots.append(b)
            created["bots"] += 1

        # create instances for each bot
        instances = []
        for b in bots:
            inst = await bots_repo.create_instance(db, b.id, user_id="507f1f77bcf86cd799439011", metadata={"seed": True})
            instances.append(inst)
            created["instances"] += 1

        # set states: running, paused, stopped
        await bots_repo.update_instance_state(db, instances[0].id, bots_model.BotState.running)
        await bots_repo.update_instance_state(db, instances[1].id, bots_model.BotState.paused)
        await bots_repo.update_instance_state(db, instances[2].id, bots_model.BotState.stopped)

        # create 10 trades across instances with varied pnl
        for _ in range(10):
            inst = random.choice(instances)
            side = random.choice(["buy", "sell"])
            entry = round(random.uniform(10.0, 60000.0), 2)
            qty = round(random.uniform(0.001, 2.0), 6)
            trade = await bots_repo.create_entry_trade(db, inst.id, side, entry, qty)
            # random exit price +/-20%
            exit_price = round(entry * (1 + random.uniform(-0.2, 0.2)), 2)
            await bots_repo.close_trade(db, trade.id, exit_price)
            created["trades"] += 1

    print("Seeding complete:", created)


def main():
    asyncio.run(seed())


if __name__ == "__main__":
    main()
