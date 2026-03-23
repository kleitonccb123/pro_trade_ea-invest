"""
KuCoin WebSocket client with automatic reconnection — DOC_04 §5.

Features:
  - Obtains fresh WS token per connection session via REST
  - Automatic reconnection up to MAX_RECONNECT_ATTEMPTS with exponential backoff
  - Re-subscribes to all previous topics after reconnect
  - Ping loop at 80% of server-specified interval
  - on_disconnect callback for BotWorker notification

Usage:
    async def handle(data):
        price = float(data["data"]["price"])

    client = KuCoinWebSocketClient(
        rest_client=rest,
        on_message=handle,
        private=True,
    )
    ws_task = asyncio.create_task(client.connect())
    await client.subscribe(f"/market/ticker:BTC-USDT")
    await client.subscribe(TOPIC_ORDERS, private=True)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, List, Optional

import aiohttp

logger = logging.getLogger("kucoin.ws")

MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_BACKOFF_BASE = 2.0
RECONNECT_MAX_WAIT     = 60.0

# ── Topic constants ───────────────────────────────────────────────────────────
TOPIC_TICKER     = "/market/ticker:{pair}"              # real-time price
TOPIC_ORDERBOOK  = "/spotMarket/level2Depth5:{pair}"   # order book (5 levels)
TOPIC_CANDLES    = "/market/candles:{pair}_{timeframe}" # live candle updates
TOPIC_ORDERS     = "/spotMarket/tradeOrders"            # private: user order fills
TOPIC_BALANCES   = "/account/balance"                   # private: balance changes


class KuCoinWebSocketClient:
    """
    Persistent KuCoin WebSocket connection.

    Create ONE instance per BotWorker and reuse it for the worker's lifetime.
    Call `disconnect()` during graceful shutdown.
    """

    def __init__(
        self,
        rest_client:   "KuCoinRESTClient",          # noqa: F821
        on_message:    Callable[[dict], None],
        on_disconnect: Optional[Callable[[int], None]] = None,
        private:       bool = True,
    ):
        """
        Args:
            rest_client:   A KuCoinRESTClient instance (used to fetch WS token).
            on_message:    Async or sync callable invoked for each data message.
            on_disconnect: Optional callable(reconnect_count) called before each
                           reconnect attempt.
            private:       True → uses private token (order/balance topics).
                           False → public token only (market data).
        """
        self.rest          = rest_client
        self.on_message    = on_message
        self.on_disconnect = on_disconnect
        self.private       = private

        self._ws:                Optional[aiohttp.ClientWebSocketResponse] = None
        self._session:           Optional[aiohttp.ClientSession] = None
        self._running:           bool = False
        self._subscriptions:     List[dict] = []
        self._ping_task:         Optional[asyncio.Task] = None
        self._reconnect_count:   int = 0
        self._msg_id:            int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """
        Start the main reconnect loop. Run as an asyncio.Task.

        Returns when the client is stopped (disconnect() called) or the
        maximum reconnect attempts are exceeded.
        """
        self._running = True
        self._reconnect_count = 0

        while self._running:
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break  # intentional stop

                self._reconnect_count += 1
                if self._reconnect_count > MAX_RECONNECT_ATTEMPTS:
                    logger.critical(
                        f"WebSocket KuCoin: máximo de {MAX_RECONNECT_ATTEMPTS} "
                        f"reconexões atingido — encerrando"
                    )
                    break

                wait = min(
                    RECONNECT_BACKOFF_BASE ** self._reconnect_count,
                    RECONNECT_MAX_WAIT,
                )
                logger.warning(
                    f"WebSocket desconectado: {exc}. "
                    f"Reconectando em {wait:.1f}s "
                    f"(tentativa {self._reconnect_count}/{MAX_RECONNECT_ATTEMPTS})"
                )
                await asyncio.sleep(wait)

                if self.on_disconnect:
                    try:
                        result = self.on_disconnect(self._reconnect_count)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as cb_exc:
                        logger.debug(f"Erro no on_disconnect callback: {cb_exc}")

    async def subscribe(self, topic: str, private: bool = False) -> None:
        """
        Subscribe to a KuCoin topic.

        The subscription is stored so it can be replayed after reconnection.
        If already connected, the subscribe message is sent immediately.
        """
        entry = {"topic": topic, "private": private}
        # Avoid duplicate subscriptions
        if entry not in self._subscriptions:
            self._subscriptions.append(entry)

        if self._ws and not self._ws.closed:
            await self._send_subscribe(topic, private)

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic and remove it from the replay list."""
        self._subscriptions = [
            s for s in self._subscriptions if s["topic"] != topic
        ]
        if self._ws and not self._ws.closed:
            await self._ws.send_str(
                json.dumps({
                    "id": self._next_id(),
                    "type": "unsubscribe",
                    "topic": topic,
                    "privateChannel": False,
                    "response": True,
                })
            )

    async def disconnect(self) -> None:
        """Signal the client to stop; close the current WebSocket if open."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _next_id(self) -> str:
        self._msg_id += 1
        return str(self._msg_id)

    async def _connect_once(self) -> None:
        """
        Tenta UMA conexão WebSocket (DOC-K08).
        Cada chamada obtém um token NOVO — nunca reutiliza token de sessão anterior.
        """
        # === CORREÇÃO 1: Token sempre fresco por tentativa ===
        token, ws_url, ping_interval_s = await self.rest.get_ws_token(
            private=self.private
        )
        logger.debug("WS token obtido (expira em ~24h): ...%s", token[-8:])

        # === CORREÇÃO 2: Cancelar ping task anterior antes de criar novo ===
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        # Gerenciar sessão aiohttp separada por conexão
        if self._session and not self._session.closed:
            await self._session.close()

        self._session = aiohttp.ClientSession()
        try:
            async with self._session.ws_connect(
                ws_url,
                heartbeat=None,
                receive_timeout=ping_interval_s * 2,
                max_msg_size=0,   # sem limite de tamanho de mensagem
            ) as ws:
                self._ws = ws
                self._reconnect_count = 0
                label = "private" if self.private else "public"
                logger.info("✅ WebSocket KuCoin conectado (%s) — ping=%.0fs", label, ping_interval_s)

                # Replay subscriptions after reconnect
                for sub in list(self._subscriptions):
                    await self._send_subscribe(sub["topic"], sub["private"])
                    await asyncio.sleep(0.1)   # pequeno delay entre subs

                # Iniciar ping loop
                self._ping_task = asyncio.create_task(
                    self._ping_loop(ws, ping_interval_s),
                    name=f"ws_ping_{label}",
                )

                await self._message_loop(ws)

        finally:
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()
            self._ws = None
            if self._session and not self._session.closed:
                await self._session.close()

    async def _message_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Loop de leitura de mensagens com tratamento de todos os tipos (DOC-K08)."""
        async for raw in ws:
            if raw.type == aiohttp.WSMsgType.TEXT:
                try:
                    msg = json.loads(raw.data)
                except json.JSONDecodeError:
                    logger.warning("WS mensagem inválida (não-JSON): %s", raw.data[:100])
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "welcome":
                    logger.debug("WS: welcome recebido")
                elif msg_type == "pong":
                    logger.debug("WS: pong recebido")
                elif msg_type == "ack":
                    logger.debug("WS: ack de subscription: topic=%s", msg.get("topic"))
                elif msg_type == "error":
                    logger.error("WS: erro do servidor KuCoin: %s", msg)
                elif msg_type in ("message", "data"):
                    try:
                        result = self.on_message(msg)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as cb_exc:
                        logger.error("Erro no handler de mensagem WS: %s", cb_exc, exc_info=True)
                else:
                    logger.debug("Tipo de mensagem WS desconhecido ignorado: %s", msg_type)

            elif raw.type == aiohttp.WSMsgType.CLOSED:
                logger.warning("WS: conexão fechada pelo servidor (code=%s)", ws.close_code)
                break
            elif raw.type == aiohttp.WSMsgType.ERROR:
                logger.error("WS: erro de protocolo: %s", ws.exception())
                break

    async def _ping_loop(
        self,
        ws: aiohttp.ClientWebSocketResponse,
        interval_s: float,
    ) -> None:
        """
        Envio periódico de ping (DOC-K08).
        KuCoin recomenda 80% do intervalo (pingTimeout).
        """
        ping_interval = interval_s * 0.8
        try:
            while not ws.closed:
                await asyncio.sleep(ping_interval)
                if ws.closed:
                    break
                msg_id = self._next_id()
                await ws.send_str(json.dumps({"id": msg_id, "type": "ping"}))
                logger.debug("WS ping enviado (id=%s)", msg_id)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("WS ping loop encerrado: %s", exc)

    async def _handle_message(self, data: dict) -> None:
        msg_type = data.get("type")

        # DOC-K08: Handle all KuCoin WS message types explicitly
        if msg_type == "pong":
            return  # Ping acknowledged — connection healthy

        if msg_type == "welcome":
            logger.debug("WebSocket welcome recebido")
            return

        if msg_type == "ack":
            logger.debug(f"Subscrição confirmada: {data.get('id')}")
            return

        if msg_type == "notice":
            logger.info(f"WebSocket notice: {data.get('data')}")
            return

        if msg_type in ("message", "data"):
            try:
                if asyncio.iscoroutinefunction(self.on_message):
                    await self.on_message(data)
                else:
                    self.on_message(data)
            except Exception as exc:
                logger.error(f"Erro ao processar mensagem WS: {exc}", exc_info=True)
            return

        logger.debug(f"[DOC-K08] Tipo de mensagem WS desconhecido ignorado: {msg_type}")

    async def _send_subscribe(self, topic: str, private: bool) -> None:
        if not self._ws or self._ws.closed:
            return
        msg = {
            "id": self._next_id(),
            "type": "subscribe",
            "topic": topic,
            "privateChannel": private,
            "response": True,
        }
        await self._ws.send_str(json.dumps(msg))
        logger.debug(f"Subscrito: {topic}")
