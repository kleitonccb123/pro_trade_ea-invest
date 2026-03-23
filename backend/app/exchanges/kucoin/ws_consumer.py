"""
WsConsumer — Consumidor Redis para dados de mercado e execuções

Cada bot/usuário instancia um WsConsumer que:
  1. Subscreve nos canais Redis corretos (ticker, execution, balance)
  2. Chama os handlers registrados para cada mensagem
  3. Monitora silêncio de 10 s → ativa fallback REST (polling 2s)
  4. Ao receber de novo → desativa fallback automaticamente

O consumer se conecta ao Redis usando uma conexão DEDICADA (duplicate),
pois conexões no modo subscribe não podem executar outros comandos.

DOC-03 §4.4
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

TickerHandler    = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]
ExecutionHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]
BalanceHandler   = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]
Level2Handler    = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class WsConsumer:
    """
    Consumer de Redis Pub/Sub para um bot específico.

    Uso:
    ```python
    consumer = WsConsumer(
        redis_client=redis,
        bot_id="bot1",
        symbol="BTC-USDT",
        user_id="user1",
    )
    await consumer.start(
        on_ticker=handle_ticker,
        on_execution=handle_exec,
    )
    # ...
    await consumer.stop()
    ```
    """

    FALLBACK_TRIGGER_S   = 10.0   # silêncio que ativa fallback
    FALLBACK_POLL_S      = 2.0    # intervalo de polling REST
    MONITOR_INTERVAL_S   = 2.0    # frequência de checagem do monitor
    REST_TICKER_URL      = "https://api.kucoin.com/api/v1/market/orderbook/level1"

    def __init__(
        self,
        redis_client: Any,              # redis.asyncio.Redis (será .copy())
        bot_id: str,
        symbol: str,
        user_id: str,
        kucoin_client: Optional[Any] = None,   # para fallback REST
    ) -> None:
        self._redis      = redis_client
        self._bot_id     = bot_id
        self._symbol     = symbol
        self._user_id    = user_id
        self._kucoin     = kucoin_client

        self._last_msg_ts: float = time.monotonic()
        self._fallback_active    = False
        self._running            = False

        # handlers
        self._on_ticker:    Optional[TickerHandler]    = None
        self._on_execution: Optional[ExecutionHandler] = None
        self._on_balance:   Optional[BalanceHandler]   = None
        self._on_level2:    Optional[Level2Handler]    = None

        # tasks
        self._listen_task:   Optional[asyncio.Task] = None
        self._monitor_task:  Optional[asyncio.Task] = None
        self._fallback_task: Optional[asyncio.Task] = None
        self._pubsub: Optional[Any] = None

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    async def start(
        self,
        on_ticker:    Optional[TickerHandler]    = None,
        on_execution: Optional[ExecutionHandler] = None,
        on_balance:   Optional[BalanceHandler]   = None,
        on_level2:    Optional[Level2Handler]    = None,
    ) -> None:
        """Inicia consumer: subscreve canais Redis e listeners."""
        self._on_ticker    = on_ticker
        self._on_execution = on_execution
        self._on_balance   = on_balance
        self._on_level2    = on_level2
        self._running      = True
        self._last_msg_ts  = time.monotonic()

        self._pubsub = self._redis.pubsub()
        channels = self._build_channels()
        await self._pubsub.subscribe(*channels)

        self._listen_task  = asyncio.create_task(self._listen_loop(), name=f"ws_consumer_listen_{self._bot_id}")
        self._monitor_task = asyncio.create_task(self._monitor_loop(), name=f"ws_consumer_monitor_{self._bot_id}")

        logger.info(
            "WsConsumer started: bot=%s symbol=%s user=%s channels=%s",
            self._bot_id, self._symbol, self._user_id, channels,
        )

    async def stop(self) -> None:
        """Encerra o consumer e cancela todas as tasks."""
        self._running = False
        for task in (self._listen_task, self._monitor_task, self._fallback_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.aclose()
            except Exception:
                pass
        logger.info("WsConsumer stopped: bot=%s", self._bot_id)

    # ── Listen loop ───────────────────────────────────────────────────────────

    async def _listen_loop(self) -> None:
        """Aguarda mensagens do Redis e chama handlers."""
        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break
                if message["type"] != "message":
                    continue

                self._last_msg_ts = time.monotonic()
                if self._fallback_active:
                    await self._exit_fallback()

                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                channel: str = message.get("channel", b"").decode() if isinstance(
                    message.get("channel"), bytes
                ) else str(message.get("channel", ""))

                await self._route(channel, data)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("WsConsumer._listen_loop erro: %s", exc)

    async def _route(self, channel: str, data: Dict[str, Any]) -> None:
        """Direciona o evento para o handler correto."""
        from app.exchanges.kucoin.ws_dispatcher import WsChannels

        if channel == WsChannels.ticker(self._symbol) and self._on_ticker:
            await self._safe_call(self._on_ticker, data)

        elif channel == WsChannels.execution(self._user_id) and self._on_execution:
            await self._safe_call(self._on_execution, data)

        elif channel == WsChannels.balance(self._user_id) and self._on_balance:
            await self._safe_call(self._on_balance, data)

        elif channel == WsChannels.orderbook(self._symbol) and self._on_level2:
            await self._safe_call(self._on_level2, data)

    @staticmethod
    async def _safe_call(fn: Callable, data: Any) -> None:
        try:
            await fn(data)
        except Exception as exc:
            logger.error("WsConsumer handler error: %s", exc)

    # ── Fallback monitor ──────────────────────────────────────────────────────

    async def _monitor_loop(self) -> None:
        """
        Verifica a cada MONITOR_INTERVAL_S se há silêncio > FALLBACK_TRIGGER_S.
        Se sim → ativa fallback REST.
        """
        while self._running:
            try:
                await asyncio.sleep(self.MONITOR_INTERVAL_S)
                elapsed = time.monotonic() - self._last_msg_ts
                if elapsed > self.FALLBACK_TRIGGER_S and not self._fallback_active:
                    await self._enter_fallback()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("WsConsumer._monitor_loop erro: %s", exc)

    async def _enter_fallback(self) -> None:
        """Ativa polling REST a cada FALLBACK_POLL_S."""
        self._fallback_active = True
        elapsed = time.monotonic() - self._last_msg_ts
        logger.warning(
            "WsConsumer: FALLBACK REST ativado bot=%s symbol=%s (%.0fs sem mensagem)",
            self._bot_id, self._symbol, elapsed,
        )
        if self._fallback_task and not self._fallback_task.done():
            return
        self._fallback_task = asyncio.create_task(
            self._fallback_poll_loop(), name=f"ws_fallback_{self._bot_id}"
        )

    async def _exit_fallback(self) -> None:
        """Desativa fallback ao receber mensagem WS novamente."""
        self._fallback_active = False
        logger.info(
            "WsConsumer: FALLBACK desativado bot=%s — dados WS restaurados", self._bot_id
        )
        if self._fallback_task and not self._fallback_task.done():
            self._fallback_task.cancel()
            try:
                await self._fallback_task
            except asyncio.CancelledError:
                pass

    async def _fallback_poll_loop(self) -> None:
        """
        Faz polling REST do ticker a cada FALLBACK_POLL_S enquanto o fallback
        estiver ativo, entregando os dados ao handler de ticker se registrado.
        """
        url = f"{self.REST_TICKER_URL}?symbol={self._symbol}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            while self._fallback_active and self._running:
                try:
                    resp = await client.get(url)
                    body = resp.json()
                    if body.get("code") == "200000":
                        raw = body.get("data", {})
                        ticker_event = {
                            "type":     "ticker",
                            "symbol":    self._symbol,
                            "price":     raw.get("price", "0"),
                            "best_bid":  raw.get("bestBid", "0"),
                            "best_ask":  raw.get("bestAsk", "0"),
                            "size":      raw.get("size", "0"),
                            "_fallback": True,
                        }
                        if self._on_ticker:
                            await self._safe_call(self._on_ticker, ticker_event)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning("WsConsumer fallback REST erro: %s", exc)

                try:
                    await asyncio.sleep(self.FALLBACK_POLL_S)
                except asyncio.CancelledError:
                    break

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_channels(self) -> List[str]:
        from app.exchanges.kucoin.ws_dispatcher import WsChannels
        return [
            WsChannels.ticker(self._symbol),
            WsChannels.orderbook(self._symbol),
            WsChannels.execution(self._user_id),
            WsChannels.balance(self._user_id),
        ]

    @property
    def fallback_active(self) -> bool:
        return self._fallback_active
