"""
OrderManager — tracks open orders per bot instance, wraps cancel_all_orders.

Maintains in-memory state only. The BotWorker owns position state in MongoDB.
OrderManager is a lightweight helper for the worker to query and cancel orders.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("engine.exchange.order_manager")


class OpenOrder:
    __slots__ = ("order_id", "pair", "side", "size", "price", "created_at")

    def __init__(self, order_id: str, pair: str, side: str, size: float, price: float):
        self.order_id = order_id
        self.pair = pair
        self.side = side
        self.size = size
        self.price = price
        self.created_at = datetime.now(timezone.utc)


class OrderManager:
    """
    Tracks open orders placed by a single BotWorker.
    Call .register() when an order is placed and .remove() when confirmed filled/cancelled.
    """

    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self._orders: Dict[str, OpenOrder] = {}

    def register(
        self,
        order_id: str,
        pair: str,
        side: str,
        size: float,
        price: float = 0.0,
    ) -> OpenOrder:
        order = OpenOrder(order_id, pair, side, size, price)
        self._orders[order_id] = order
        logger.debug(f"📋 Ordem registrada {order_id[:8]} — {side} {size} {pair}")
        return order

    def remove(self, order_id: str) -> Optional[OpenOrder]:
        return self._orders.pop(order_id, None)

    def get(self, order_id: str) -> Optional[OpenOrder]:
        return self._orders.get(order_id)

    def list_orders(self) -> List[OpenOrder]:
        return list(self._orders.values())

    def has_open_orders(self) -> bool:
        return bool(self._orders)

    def clear(self) -> int:
        n = len(self._orders)
        self._orders.clear()
        return n

    async def cancel_all(self, exchange) -> int:
        """Cancel all tracked open orders via the exchange client."""
        pairs_cancelled = set()
        for order in list(self._orders.values()):
            if order.pair not in pairs_cancelled:
                try:
                    await exchange.cancel_all_orders(order.pair)
                    pairs_cancelled.add(order.pair)
                except Exception as exc:
                    logger.warning(f"Falha ao cancelar ordens em {order.pair}: {exc}")

        n = self.clear()
        logger.info(f"🗑️  OrderManager: {n} ordem(ns) removida(s) do tracker")
        return n
