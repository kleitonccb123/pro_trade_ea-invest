"""
OrderQueueConsumer — Fila transacional via Redis Streams

DOC-04 §4.4

Garante processamento exatamente-uma-vez de ordens usando Redis Streams:
  - XADD orders:queue  → producer enfileira pedido de ordem
  - XREADGROUP         → consumer pega 1 mensagem por vez
  - XACK              → apenas APÓS persistência do orderId na exchange
  - XAUTOCLAIM (30s)  → mensagens pendentes > 60s são reivindicadas de volta

Isso elimina a perda de ordens por crash do worker entre enfileirar e processar.

Integração com OrderManager:
  O OrderQueueConsumer chama `safe_process_order()` que internamente:
  1. Nível 1: Idempotency Store (clientOid SET NX)
  2. Nível 2: DistributedLock bot:{botId}  TTL=30s
  3. Nível 3: DistributedLock balance:{userId} TTL=15s → BalanceReservation
  4. Envia para KuCoin
  5. Libera locks em ordem reversa

Producer:
  Use `OrderQueueProducer.enqueue()` para adicionar ordens na fila.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, Optional

# TerminalOrderError importada de order_manager (sem circular import — apenas
# o tipo é importado; a instância de OrderManager é passada por parâmetro em runtime)
try:
    from app.trading.order_manager import TerminalOrderError
except ImportError:
    # fallback se executado antes do módulo estar disponível (testes unitários)
    class TerminalOrderError(Exception):  # type: ignore[no-redef]
        pass


logger = logging.getLogger(__name__)

STREAM_NAME    = "orders:queue"
CONSUMER_GROUP = "order-workers"
BLOCK_MS       = 2_000    # 2s de espera por nova mensagem
AUTOCLAIM_MS   = 60_000   # reclamar mensagens pendentes > 60s
RECLAIM_INTERVAL_S = 30   # verificar mensagens abandonadas a cada 30s


# ─── Producer ─────────────────────────────────────────────────────────────────

class OrderQueueProducer:
    """
    Publica pedidos de ordem no Redis Stream.

    Uso:
    ```python
    producer = OrderQueueProducer(redis_client)
    msg_id = await producer.enqueue(
        signal_id="sig1", bot_id="bot1", user_id="u1",
        strategy_id="s1", symbol="BTC-USDT", side="buy",
        order_type="limit", size="0.001", price="50000",
        currency="USDT",
    )
    ```
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def enqueue(
        self,
        signal_id: str,
        bot_id: str,
        user_id: str,
        strategy_id: str,
        symbol: str,
        side: str,
        order_type: str,
        size: str,
        currency: str,
        price: Optional[str] = None,
    ) -> str:
        """
        Adiciona pedido no Stream. Retorna o ID da mensagem.
        """
        fields: Dict[str, str] = {
            "signal_id":   signal_id,
            "bot_id":      bot_id,
            "user_id":     user_id,
            "strategy_id": strategy_id,
            "symbol":      symbol,
            "side":        side,
            "order_type":  order_type,
            "size":        size,
            "currency":    currency,
        }
        if price is not None:
            fields["price"] = price

        msg_id = await self._redis.xadd(STREAM_NAME, fields)
        msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
        logger.info(
            "OrderQueueProducer: enfileirado signal=%s bot=%s symbol=%s id=%s",
            signal_id, bot_id, symbol, msg_id_str,
        )
        return msg_id_str


# ─── Consumer ─────────────────────────────────────────────────────────────────

class OrderQueueConsumer:
    """
    Consome pedidos de ordem do Redis Stream e os processa via OrderManager.

    Garante:
    - Uma mensagem processada por 1 worker por vez (XREADGROUP COUNT 1)
    - XACK apenas após resultado definitivo (sucesso ou rejeição terminal)
    - XAUTOCLAIM recupera mensagens pendentes > 60s de workers crashados
    """

    def __init__(
        self,
        redis_client: Any,
        order_manager: Any,           # RaceConditionSafeOrderManager
        consumer_name: Optional[str] = None,
    ) -> None:
        self._redis    = redis_client
        self._manager  = order_manager
        self._consumer = consumer_name or f"worker-{os.getpid()}"
        self._running  = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Inicializa consumer group e inicia loops."""
        await self._ensure_consumer_group()
        self._running = True
        self._tasks = [
            asyncio.create_task(self._consume_loop(), name="order_queue_consume"),
            asyncio.create_task(self._reclaim_loop(),  name="order_queue_reclaim"),
        ]
        logger.info(
            "OrderQueueConsumer iniciado: consumer=%s stream=%s group=%s",
            self._consumer, STREAM_NAME, CONSUMER_GROUP,
        )

    async def stop(self) -> None:
        """Para os loops de consumo e reclaim."""
        self._running = False
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("OrderQueueConsumer parado: consumer=%s", self._consumer)

    # ── Consumer group ────────────────────────────────────────────────────────

    async def _ensure_consumer_group(self) -> None:
        """Cria o consumer group se não existir."""
        try:
            await self._redis.xgroup_create(
                STREAM_NAME, CONSUMER_GROUP, id="$", mkstream=True
            )
            logger.info(
                "OrderQueueConsumer: consumer group '%s' criado", CONSUMER_GROUP
            )
        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug("OrderQueueConsumer: consumer group já existe")
            else:
                logger.error(
                    "OrderQueueConsumer: erro ao criar consumer group: %s", exc
                )

    # ── Consume loop ──────────────────────────────────────────────────────────

    async def _consume_loop(self) -> None:
        """
        Lê 1 mensagem por vez do Stream.
        COUNT=1 garante ordenação estrita e que cada mensagem é processada
        completamente antes da próxima (evita concorrência intra-worker).
        """
        while self._running:
            try:
                entries = await self._redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=self._consumer,
                    streams={STREAM_NAME: ">"},
                    count=1,
                    block=BLOCK_MS,
                )

                if not entries:
                    continue

                for _, messages in entries:
                    for msg_id, fields in messages:
                        msg_id_str = (
                            msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                        )
                        await self._process_message(msg_id_str, fields)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.error("OrderQueueConsumer._consume_loop: %s", exc)
                await asyncio.sleep(1.0)

    async def _process_message(
        self,
        msg_id: str,
        raw_fields: Dict[bytes, bytes],
    ) -> None:
        """
        Deserializa a mensagem e delega ao OrderManager.
        XACK apenas em resultado definitivo (sucesso ou rejeição permanente).
        Erros de rede/temporários → sem XACK → XAUTOCLAIM vai reprocessar.
        """
        fields: Dict[str, str] = {
            (k.decode() if isinstance(k, bytes) else k):
            (v.decode() if isinstance(v, bytes) else v)
            for k, v in raw_fields.items()
        }

        try:
            price_str = fields.get("price")
            await self._manager.safe_process_order(
                signal_id=fields["signal_id"],
                bot_id=fields["bot_id"],
                user_id=fields["user_id"],
                strategy_id=fields.get("strategy_id", ""),
                symbol=fields["symbol"],
                side=fields["side"],
                order_type=fields.get("order_type", "market"),
                size=Decimal(fields["size"]),
                price=Decimal(price_str) if price_str else None,
                currency=fields.get("currency", "USDT"),
            )
            # XACK → mensagem processada com sucesso (definitivo)
            await self._redis.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
            logger.debug("OrderQueueConsumer: XACK msg_id=%s", msg_id)

        except TerminalOrderError as exc:
            # Rejeição permanente (saldo, preflight, erro terminal KuCoin)
            # → XACK para não reprocessar
            logger.warning(
                "OrderQueueConsumer: rejeição terminal msg_id=%s: %s", msg_id, exc
            )
            await self._redis.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)

        except Exception as exc:
            # Erro transitório (rede, timeout, Redis offline)
            # → SEM XACK → XAUTOCLAIM vai reprocessar
            logger.error(
                "OrderQueueConsumer: erro transitório msg_id=%s: %s — "
                "sem XACK, será reclamado", msg_id, exc,
            )

    # ── Reclaim loop ──────────────────────────────────────────────────────────

    async def _reclaim_loop(self) -> None:
        """
        A cada RECLAIM_INTERVAL_S, reivindica mensagens pendentes > AUTOCLAIM_MS.
        Garante recovery após crash de worker.
        """
        while self._running:
            try:
                await asyncio.sleep(RECLAIM_INTERVAL_S)
                if not self._running:
                    break

                result = await self._redis.xautoclaim(
                    STREAM_NAME,
                    CONSUMER_GROUP,
                    self._consumer,
                    min_idle_time=AUTOCLAIM_MS,
                    start_id="0-0",
                    count=10,
                )

                # result = (next_start_id, [(msg_id, fields), ...], [deleted_ids])
                claimed_msgs = result[1] if result and len(result) > 1 else []
                if claimed_msgs:
                    logger.warning(
                        "OrderQueueConsumer: reivindicou %d mensagens abandonadas",
                        len(claimed_msgs),
                    )
                    for msg_id, fields in claimed_msgs:
                        msg_id_str = (
                            msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                        )
                        await self._process_message(msg_id_str, fields)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.error("OrderQueueConsumer._reclaim_loop: %s", exc)




# ─── Instâncias globais ───────────────────────────────────────────────────────

_producer: Optional[OrderQueueProducer] = None
_consumer: Optional[OrderQueueConsumer] = None


def init_order_queue(
    redis_client: Any,
    order_manager: Any,
    consumer_name: Optional[str] = None,
) -> tuple[OrderQueueProducer, OrderQueueConsumer]:
    global _producer, _consumer
    _producer = OrderQueueProducer(redis_client)
    _consumer = OrderQueueConsumer(redis_client, order_manager, consumer_name)
    logger.info("OrderQueue inicializado (stream=%s)", STREAM_NAME)
    return _producer, _consumer


def get_order_queue_producer() -> Optional[OrderQueueProducer]:
    return _producer


def get_order_queue_consumer() -> Optional[OrderQueueConsumer]:
    return _consumer
