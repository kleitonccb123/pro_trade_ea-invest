"""
engine/exchange/kucoin_client.py — thin adapter for BotWorker.

Delegates all REST logic to `app.integrations.kucoin.KuCoinRESTClient`
and all WebSocket streaming to `app.integrations.kucoin.KuCoinWebSocketClient`.

BotWorker imports ONLY this class — it is unaware of the integration layer.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import AsyncIterator, List, Optional

from app.integrations.kucoin.rest_client import KuCoinRESTClient, KuCoinAPIError, KuCoinNetworkError
from app.integrations.kucoin.ws_client import KuCoinWebSocketClient, TOPIC_TICKER

logger = logging.getLogger("engine.exchange.kucoin")

# Re-export so callers don't need to touch the integration layer
KuCoinError = KuCoinAPIError

__all__ = ["KuCoinClient", "KuCoinAPIError", "KuCoinNetworkError", "KuCoinError"]


def _is_sandbox() -> bool:
    return os.getenv("KUCOIN_SANDBOX", "false").lower() in ("1", "true", "yes")


class KuCoinClient:
    """
    High-level KuCoin facade used by BotWorker.

    Wraps KuCoinRESTClient (proper signing + rate-limit + retry from DOC_04)
    and provides the async-generator price_feed() contract expected by BotWorker.
    """

    def __init__(
        self,
        api_key:        str,
        api_secret:     str,
        api_passphrase: str,
        sandbox: bool   = False,
    ):
        self._rest = KuCoinRESTClient(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            sandbox=sandbox or _is_sandbox(),
        )

    # ── Market data ───────────────────────────────────────────────────────────

    async def get_price(self, pair: str) -> float:
        return await self._rest.get_price(pair)

    async def get_ticker(self, pair: str) -> dict:
        return await self._rest.get_ticker(pair)

    async def get_candles(
        self,
        pair:      str,
        timeframe: str = "1hour",
        limit:     int = 200,
    ) -> List[List[float]]:
        return await self._rest.get_candles(pair, timeframe, limit)

    async def get_balance(self, currency: str) -> float:
        return await self._rest.get_balance(currency)

    async def get_account_balances(self) -> list:
        return await self._rest.get_account_balances()

    # ── Trading ───────────────────────────────────────────────────────────────

    async def place_market_order(
        self,
        pair:  str,
        side:  str,
        funds: Optional[float] = None,
        size:  Optional[float] = None,
    ) -> dict:
        return await self._rest.place_market_order(pair=pair, side=side, funds=funds, size=size)

    async def place_limit_order(
        self, pair: str, side: str, price: float, size: float,
        client_oid: Optional[str] = None,
    ) -> dict:
        return await self._rest.place_limit_order(pair, side, price, size, client_oid=client_oid)

    async def cancel_order(self, order_id: str) -> dict:
        return await self._rest.cancel_order(order_id)

    async def cancel_all_orders(self, pair: Optional[str] = None) -> dict:
        return await self._rest.cancel_all_orders(pair)

    async def get_order(self, order_id: str) -> dict:
        return await self._rest.get_order(order_id)

    async def get_open_orders(self, pair: Optional[str] = None) -> list:
        return await self._rest.get_open_orders(pair)

    # DOC-K05: Native stop orders (TP/SL) ────────────────────────────────────

    async def place_stop_order(
        self,
        pair: str,
        side: str,
        stop_price: float,
        size: float,
        stop_type: str = "loss",
        order_type: str = "market",
        limit_price: Optional[float] = None,
        client_oid: Optional[str] = None,
    ) -> dict:
        """Place a native stop order on KuCoin (lives on exchange server)."""
        return await self._rest.place_stop_order(
            pair=pair,
            side=side,
            stop_price=stop_price,
            size=size,
            stop_type=stop_type,
            order_type=order_type,
            limit_price=limit_price,
            client_oid=client_oid,
        )

    async def cancel_stop_order(self, order_id: str) -> dict:
        """Cancel a native stop order by ID."""
        return await self._rest.cancel_stop_order(order_id)

    async def get_open_stop_orders(self, pair: Optional[str] = None) -> list:
        """List active (untriggered) native stop orders."""
        return await self._rest.get_open_stop_orders(pair)

    # ── WebSocket price feed (async generator) ────────────────────────────────

    async def price_feed(
        self,
        pair:       str,
        stop_event: asyncio.Event,
    ) -> AsyncIterator[dict]:
        """
        Async generator yielding {"price": float, "pair": str, "ts": int} ticks.

        Uses KuCoinWebSocketClient with automatic reconnection (DOC_04 §5).
        Stops when stop_event is set.
        """
        tick_queue: asyncio.Queue = asyncio.Queue(maxsize=200)

        async def _on_ticker(data: dict) -> None:
            if not data.get("topic", "").startswith("/market/ticker"):
                return
            raw = data.get("data", {})
            try:
                price = float(raw.get("price", 0))
                if price > 0 and not tick_queue.full():
                    tick_queue.put_nowait({
                        "price":    price,
                        "pair":     pair,
                        "ts":       int(time.time() * 1000),
                        "best_ask": float(raw.get("bestAsk", price)),
                        "best_bid": float(raw.get("bestBid", price)),
                    })
            except (ValueError, TypeError):
                pass

        ws = KuCoinWebSocketClient(
            rest_client=self._rest,
            on_message=_on_ticker,
            private=False,
        )
        ws_task = asyncio.create_task(ws.connect())

        # Wait for WS connection to establish before subscribing
        await asyncio.sleep(1.5)
        await ws.subscribe(TOPIC_TICKER.format(pair=pair))

        try:
            while not stop_event.is_set():
                try:
                    tick = await asyncio.wait_for(tick_queue.get(), timeout=5.0)
                    yield tick
                except asyncio.TimeoutError:
                    continue
        finally:
            await ws.disconnect()
            ws_task.cancel()
            try:
                await ws_task
            except (asyncio.CancelledError, Exception):
                pass

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._rest.close()


