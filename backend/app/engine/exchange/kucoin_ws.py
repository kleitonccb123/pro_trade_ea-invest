"""
KuCoin WebSocket feed with automatic token refresh and reconnection.

Flow:
  1. GET /api/v1/bullet-public → obtain WS endpoint + token (no auth needed for ticker)
  2. Connect to wss://... and subscribe to topic /market/ticker:{pair}
  3. Yield each price tick downstream
  4. On disconnect / error → wait RECONNECT_DELAY and loop

Ping/pong is handled internally (KuCoin requires ping every 30s).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

import aiohttp

logger = logging.getLogger("engine.exchange.ws")

RECONNECT_DELAY = 5   # seconds between reconnect attempts
PING_INTERVAL   = 20  # seconds between pings (KuCoin allows up to 30s)
WS_TIMEOUT      = 60  # aiohttp ws receive timeout


class KuCoinWebSocket:
    """
    Manages a single KuCoin WebSocket subscription for one ticker symbol.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
    ):
        self._key = api_key
        self._secret = api_secret
        self._passphrase = api_passphrase

    # ── Token / Endpoint ─────────────────────────────────────────────────────

    async def _get_ws_endpoint(self) -> tuple[str, str]:
        """
        Returns (ws_url, token) by calling the KuCoin bullet endpoint.
        Uses public endpoint (no auth required for public ticker).
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.kucoin.com/api/v1/bullet-public",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

        if data.get("code") != "200000":
            raise ConnectionError(f"KuCoin bullet error: {data.get('msg')}")

        inner = data["data"]
        token = inner["token"]
        servers = inner.get("instanceServers", [])
        endpoint = servers[0]["endpoint"] if servers else "wss://ws-api.kucoin.com/endpoint"
        return endpoint, token

    # ── Subscription ─────────────────────────────────────────────────────────

    async def subscribe_ticker(
        self, pair: str, stop_event: asyncio.Event
    ) -> AsyncIterator[dict]:
        """
        Async generator yielding {"price": float, "ts": int} ticks.
        Reconnects automatically on errors.
        """
        while not stop_event.is_set():
            try:
                async for tick in self._connect_and_stream(pair, stop_event):
                    yield tick
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning(
                    f"🔌 WebSocket desconectado ({pair}): {exc} — "
                    f"reconectando em {RECONNECT_DELAY}s"
                )
            if stop_event.is_set():
                return
            await asyncio.sleep(RECONNECT_DELAY)

    async def _connect_and_stream(
        self, pair: str, stop_event: asyncio.Event
    ) -> AsyncIterator[dict]:
        endpoint, token = await self._get_ws_endpoint()
        connect_id = str(int(time.time() * 1000))
        ws_url = f"{endpoint}?token={token}&connectId={connect_id}"

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                ws_url,
                heartbeat=PING_INTERVAL,
                receive_timeout=WS_TIMEOUT,
            ) as ws:
                logger.info(f"🔗 WebSocket conectado — {pair}")

                # Wait for welcome message
                welcome = await ws.receive_json()
                if welcome.get("type") != "welcome":
                    raise ConnectionError(f"WS welcome inesperado: {welcome}")

                # Subscribe
                sub_msg = {
                    "id": connect_id,
                    "type": "subscribe",
                    "topic": f"/market/ticker:{pair}",
                    "privateChannel": False,
                    "response": True,
                }
                await ws.send_json(sub_msg)

                # Confirm subscription
                ack = await ws.receive_json()
                if ack.get("type") == "ack":
                    logger.info(f"✅ Subscrito em /market/ticker:{pair}")

                # Stream messages
                async for msg in ws:
                    if stop_event.is_set():
                        return

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        payload = json.loads(msg.data)
                        if payload.get("type") == "message" and "data" in payload:
                            tick_data = payload["data"]
                            price_str = tick_data.get("price", "0")
                            try:
                                price = float(price_str)
                                if price > 0:
                                    yield {
                                        "price": price,
                                        "ts": int(time.time() * 1000),
                                        "pair": pair,
                                        "best_ask": float(tick_data.get("bestAsk", price)),
                                        "best_bid": float(tick_data.get("bestBid", price)),
                                    }
                            except (ValueError, TypeError):
                                pass

                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        logger.warning(f"WebSocket encerrado: {msg.type}")
                        return
