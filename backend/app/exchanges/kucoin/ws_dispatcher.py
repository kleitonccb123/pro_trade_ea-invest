"""
WsDispatcher — Fan-out de mensagens WS da KuCoin via Redis Pub/Sub

Registra-se como listener nos callbacks do KuCoinWebSocketManager e
republica cada evento no canal Redis correto, permitindo que N bots
consumam dados de UMA única conexão WebSocket.

Canais Redis:
  ws:ticker:{symbol}        — preço em tempo real
  ws:orderbook:{symbol}     — order book (level2 incremental)
  ws:execution:{userId}     — execution reports privados
  ws:balance:{userId}       — eventos de balance

Gap de sequência:
  Quando detectado, tenta buscar snapshot REST do order book e publica
  nos canais afetados para sincronizar os consumidores.

DOC-03 §4.3
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# DOC-06: métricas de gap de sequência WS
try:
    from app.observability.metrics import trading_ws_sequence_gaps_total as _ws_gaps
    _GAP_METRICS_OK = True
except Exception:
    _GAP_METRICS_OK = False


# ─── Definição de Canais ───────────────────────────────────────────────────────

class WsChannels:
    @staticmethod
    def ticker(symbol: str) -> str:
        return f"ws:ticker:{symbol}"

    @staticmethod
    def orderbook(symbol: str) -> str:
        return f"ws:orderbook:{symbol}"

    @staticmethod
    def execution(user_id: str) -> str:
        return f"ws:execution:{user_id}"

    @staticmethod
    def balance(user_id: str) -> str:
        return f"ws:balance:{user_id}"


# ─── Dispatcher Principal ─────────────────────────────────────────────────────

class WsDispatcher:
    """
    Conecta os callbacks do KuCoinWebSocketManager ao Redis Pub/Sub.

    Uso:
    ```python
    dispatcher = WsDispatcher(redis_client, execution_processor, user_id="u1")
    dispatcher.wire(manager, symbols=["BTC-USDT", "ETH-USDT"])
    await manager.start()
    ```
    """

    SLOW_DISPATCH_MS = 50   # warning se publish levar mais de 50ms

    def __init__(
        self,
        redis_client: Any,                        # redis.asyncio.Redis
        execution_processor: Optional[Any] = None, # ExecutionProcessor (DOC-01)
        user_id: Optional[str] = None,             # para canais privados
        kucoin_client: Optional[Any] = None,       # usado no fallback snapshot
    ) -> None:
        self._redis   = redis_client
        self._exec    = execution_processor
        self._user_id = user_id or ""
        self._kucoin  = kucoin_client
        self.channels = WsChannels

    # ── Wiring ────────────────────────────────────────────────────────────────

    def wire(
        self,
        manager: Any,                       # KuCoinWebSocketManager
        symbols: list[str] | None = None,
    ) -> None:
        """
        Registra callbacks no manager para todos os canais necessários.
        Deve ser chamado ANTES de manager.start().
        """
        symbols = symbols or []

        for symbol in symbols:
            manager.on_ticker(symbol, self._make_ticker_handler(symbol))
            manager.on_level2(symbol, self._make_level2_handler(symbol))

        manager.on_order_execution(self._on_order_execution)
        manager.on_futures_order_execution(self._on_order_execution)
        manager.on_balance(self._on_balance)
        manager.on_sequence_gap(self._on_sequence_gap)

        logger.info(
            "WsDispatcher: wired symbols=%s user_id=%s", symbols, self._user_id
        )

    def wire_symbol(self, manager: Any, symbol: str) -> None:
        """Adiciona wiring para um símbolo novo em runtime."""
        manager.on_ticker(symbol, self._make_ticker_handler(symbol))
        manager.on_level2(symbol, self._make_level2_handler(symbol))

    # ── Factories de handler por símbolo ─────────────────────────────────────

    def _make_ticker_handler(self, symbol: str):
        channel = WsChannels.ticker(symbol)

        async def _handler(event: Dict[str, Any]) -> None:
            await self._publish(channel, event)

        return _handler

    def _make_level2_handler(self, symbol: str):
        channel = WsChannels.orderbook(symbol)

        async def _handler(event: Dict[str, Any]) -> None:
            await self._publish(channel, event)

        return _handler

    # ── Handlers de canais privados ───────────────────────────────────────────

    async def _on_order_execution(self, event: Dict[str, Any]) -> None:
        """
        Execution report → Redis + ExecutionProcessor (DOC-01 integration).
        Tenta usar userId do evento; fallback para self._user_id.
        """
        user_id = event.get("user_id") or self._user_id
        if user_id:
            channel = WsChannels.execution(user_id)
            await self._publish(channel, event)

        # Alimenta o ExecutionProcessor (DOC-01) para atualizar PendingOrders
        if self._exec is not None:
            try:
                await self._exec.process(event)
            except Exception as exc:
                logger.error("WsDispatcher: ExecutionProcessor.process falhou: %s", exc)

    async def _on_balance(self, event: Dict[str, Any]) -> None:
        user_id = event.get("user_id") or self._user_id
        if user_id:
            channel = WsChannels.balance(user_id)
            await self._publish(channel, event)

    # ── Gap recovery ──────────────────────────────────────────────────────────

    async def _on_sequence_gap(self, event: Dict[str, Any]) -> None:
        """
        Quando um gap de sequência é detectado em /market/level2, busca
        o snapshot REST do order book e republica para resincronizar os consumers.
        """
        topic: str = event.get("topic", "")
        gap:   int = event.get("gap", 0)
        logger.warning(
            "WsDispatcher: sequence gap=%d topic=%s — iniciando recovery", gap, topic
        )
        # DOC-06: incrementa contador de gaps
        if _GAP_METRICS_OK:
            try:
                _ws_gaps.labels(channel=topic).inc()
            except Exception:
                pass

        if not topic.startswith("/market/level2:"):
            return

        symbol = topic.split(":")[-1]
        if self._kucoin is None:
            logger.warning("WsDispatcher: sem kucoin_client para recovery de snapshot")
            return

        try:
            snapshot = await self._kucoin.get_order_book(symbol, depth=20)
            recovery_msg = {
                "type":      "orderbook_snapshot",
                "symbol":    symbol,
                "snapshot":  snapshot,
                "recovered": True,
                "_ts":       int(time.time() * 1000),
            }
            await self._publish(WsChannels.orderbook(symbol), recovery_msg)
            logger.info("WsDispatcher: order book snapshot republicado para %s", symbol)

        except Exception as exc:
            logger.error(
                "WsDispatcher: falha ao buscar snapshot para %s: %s", symbol, exc
            )

    # ── Redis publish ─────────────────────────────────────────────────────────

    async def _publish(self, channel: str, event: Dict[str, Any]) -> None:
        if self._redis is None:
            return
        t0 = time.monotonic()
        try:
            payload = self._serialize(event)
            await self._redis.publish(channel, payload)
            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms > self.SLOW_DISPATCH_MS:
                logger.warning(
                    "WsDispatcher: publish lento %.1fms channel=%s", elapsed_ms, channel
                )
        except Exception as exc:
            logger.error("WsDispatcher: falha no publish channel=%s: %s", channel, exc)

    @staticmethod
    def _serialize(event: Dict[str, Any]) -> str:
        """Serializa evento para JSON, convertendo tipos não-serializáveis."""
        from datetime import datetime
        from decimal import Decimal

        def default(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return str(obj)
            return str(obj)

        return json.dumps({**event, "_ts": int(time.time() * 1000)}, default=default)
