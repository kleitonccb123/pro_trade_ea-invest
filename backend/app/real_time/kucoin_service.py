"""KuCoin RealTime Service

Background service that manages private WebSocket connections to KuCoin
for each user who started a bot. It receives order/trade events and forwards
them to the internal Notification Hub (`notification_hub`) so the frontend
can display trades in real time.

This is a lightweight, pluggable implementation: the real KuCoin connection
is represented as a stub/simulator when running in `OFFLINE_MODE`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any

from app.websockets.notification_hub import notify_trade

logger = logging.getLogger(__name__)


class KuCoinRealTimeService:
    """Service that manages per-user KuCoin private streams.

    In production this would use `ccxt.pro` or the KuCoin websocket auth
    flow. Here we provide a simple API used by the rest of the application:
    - start_monitoring(user_id, credentials)
    - stop_monitoring(user_id)
    """

    def __init__(self):
        # map user_id -> asyncio.Task
        self._tasks: Dict[str, asyncio.Task] = {}

    async def _simulate_stream(self, user_id: str, credentials: Dict[str, Any]):
        """Simulation loop that emits fake trade events every few seconds.

        Replace this implementation with a real KuCoin subscription using
        websockets or ccxt.pro.
        """
        logger.info(f"[KuCoinService] Starting simulated stream for {user_id}")
        try:
            counter = 0
            while True:
                await asyncio.sleep(5)
                # Simulate an execution event
                counter += 1
                side = 'buy' if counter % 2 == 0 else 'sell'
                price = 45000 + (counter % 10) * (1 if side == 'buy' else -1) * 10
                amount = round(0.01 * (1 + (counter % 5)), 5)

                # Persist to DB: omitted (the real implementation should save the trade)

                # Forward to frontend via notification hub
                try:
                    await notify_trade(user_id=user_id, symbol='BTC/USDT', side=side, amount=amount, price=price, order_id=f'sim-{counter}')
                    logger.debug(f"[KuCoinService] Simulated trade forwarded for {user_id}: {side} {amount}@{price}")
                except Exception:
                    logger.exception("Failed to notify trade")

        except asyncio.CancelledError:
            logger.info(f"[KuCoinService] Stream cancelled for {user_id}")
        except Exception as e:
            logger.exception(f"[KuCoinService] Stream error for {user_id}: {e}")

    async def start_monitoring(self, user_id: str, credentials: Dict[str, Any]) -> None:
        """Start monitoring for a specific user (idempotent)."""
        if user_id in self._tasks:
            logger.info(f"[KuCoinService] Already monitoring {user_id}")
            return

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._simulate_stream(user_id, credentials))
        self._tasks[user_id] = task

    async def stop_monitoring(self, user_id: str) -> None:
        task = self._tasks.pop(user_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def stop_all(self) -> None:
        tasks = list(self._tasks.keys())
        for u in tasks:
            await self.stop_monitoring(u)


# Global instance used by the application
kucoin_service = KuCoinRealTimeService()
