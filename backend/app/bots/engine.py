from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import List

from app.bots import repository as bots_repo
from app.bots import model as bots_model
from app.bots.strategy import StrategyRSIEMA
from app.bots.market_data import generate_candles, MarketMode
from app.core.database import get_db

logger = logging.getLogger(__name__)


class BotEngine:
    """Engine that schedules and runs bot instances in a simulated loop.

    Execution, strategy and persistence are separated:
    - strategy: `StrategyRSIEMA`
    - execution: this engine
    - persistence: `bots_repo`
    """

    def __init__(self):
        self._tasks: dict[int, asyncio.Task] = {}
        self._running = False

    async def _simulate_prices(self, length: int = 200, start_price: float = 100.0) -> List[float]:
        # Deprecated: keep for backward compatibility
        prices = [start_price]
        for _ in range(length - 1):
            change = random.uniform(-1.0, 1.0)
            prices.append(max(0.01, prices[-1] + change))
        return prices

    async def _run_instance(self, instance_id: int):
        """Run bot instance simulation."""
        logger.info("Starting simulation for instance %s", instance_id)
        db = get_db()
        await db['bot_instances'].update_one(
            {'_id': instance_id},
            {'$set': {'state': 'running', 'started_at': datetime.utcnow()}}
        )

        # prepare market data and strategy
        candles = generate_candles(count=300, start_price=100.0, mode=MarketMode.SIDEWAYS)
        strategy = StrategyRSIEMA()
        open_trade_id = None

        # run cycles
        for cycle in range(200):
            try:
                # Get window of candles for strategy
                window = candles[max(0, 50 + cycle - 100) : 50 + cycle]
                signal = strategy.on_candles(window)
                current_candle = candles[50 + cycle - 1]
                price = current_candle["close"]
                
                logger.debug("Instance %s cycle %s signal=%s price=%s", instance_id, cycle, signal, price)
                
                # Just simulate, don't access DB for repository methods
                if signal.name == "BUY" and open_trade_id is None:
                    open_trade_id = cycle
                    logger.info("Instance %s opened BUY price=%s", instance_id, price)
                elif signal.name == "SELL" and open_trade_id is not None:
                    logger.info("Instance %s closed trade at=%s", instance_id, price)
                    open_trade_id = None

            except Exception as exc:
                logger.exception("Error in instance %s: %s", instance_id, exc)
                break

            await asyncio.sleep(0.5)

        # Ensure stopped state
        await db['bot_instances'].update_one(
            {'_id': instance_id},
            {'$set': {'state': 'stopped', 'stopped_at': datetime.utcnow()}}
        )
        logger.info("Stopped simulation for instance %s", instance_id)

    async def start_instance(self, instance_id: int):
        if instance_id in self._tasks and not self._tasks[instance_id].done():
            logger.warning("Instance %s already running", instance_id)
            return
        task = asyncio.create_task(self._run_instance(instance_id))
        self._tasks[instance_id] = task

    async def stop_instance(self, instance_id: int):
        task = self._tasks.get(instance_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Instance %s cancelled", instance_id)

    async def shutdown(self):
        for instance_id, task in list(self._tasks.items()):
            await self.stop_instance(instance_id)
