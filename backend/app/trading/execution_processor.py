"""
ExecutionProcessor — Processa execution reports do WebSocket KuCoin

Responsabilidades:
  1. Receber eventos do canal privado /trade/orders
  2. Buscar a PendingOrder correspondente pelo client_oid
  3. Atualizar status no banco
  4. Notificar PositionManager (preco medio, filled_size)
  5. Registrar no ImmutableJournal (only on FILLED)
  6. Tratar ordem órfã (sem client_oid no banco) → delega à reconciliação

Eventos KuCoin (type):
  - open      → ordem aceita, aguardando match
  - match     → execução parcial
  - filled    → execução completa
  - canceled  → cancelada

Garantia de entrega: se o WS dropar um evento, a ReconciliationJob (60s)
detecta e corrige o divergência automaticamente.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from app.trading.models.pending_order import OrderStatus

logger = logging.getLogger(__name__)


# ─── Tipos de evento KuCoin ───────────────────────────────────────────────────

KUCOIN_EVENT_OPEN     = "open"
KUCOIN_EVENT_MATCH    = "match"
KUCOIN_EVENT_FILLED   = "filled"
KUCOIN_EVENT_CANCELED = "canceled"


class ExecutionProcessor:
    """
    Processa execution reports recebidos via WebSocket KuCoin.

    Uso no WebSocketManager:
    ```python
    processor = ExecutionProcessor(db, position_manager, journal)

    # Ao receber mensagem WS do canal /trade/orders:
    await processor.process(ws_event)
    ```
    """

    # Coleção MongoDB onde as PendingOrders são persistidas
    ORDERS_COLLECTION = "pending_orders"

    def __init__(
        self,
        db: Any,                             # motor AsyncIOMotorDatabase
        position_manager: Any,               # PositionManager
        journal: Optional[Any] = None,       # ImmutableJournal
        notification_callback: Optional[Any] = None,  # async callable(user_id, event)
    ) -> None:
        self._db = db
        self._col = db[self.ORDERS_COLLECTION] if db is not None else None
        self._positions = position_manager
        self._journal = journal
        self._notify = notification_callback

    # ── Entrada principal ─────────────────────────────────────────────────────

    async def process(self, raw_event: Dict[str, Any]) -> None:
        """
        Processa um execution report vindo do WebSocket.

        raw_event esperado (formato KuCoin /trade/orders):
        {
          "type":        "open" | "match" | "filled" | "canceled",
          "orderId":     "kucoin-internal-id",
          "clientOid":   "our-client-oid",
          "symbol":      "BTC-USDT",
          "side":        "buy" | "sell",
          "size":        "0.001",
          "filledSize":  "0.001",
          "remainSize":  "0",
          "price":       "50000",
          "ts":          1700000000000000000,   # nanoseconds
        }
        """
        event_type = raw_event.get("type", "")
        client_oid = raw_event.get("clientOid", raw_event.get("client_oid", ""))
        order_id   = raw_event.get("orderId", raw_event.get("order_id", ""))
        symbol     = raw_event.get("symbol", "")

        logger.info(
            "ExecutionProcessor.process: type=%s clientOid=%s orderId=%s symbol=%s",
            event_type, client_oid, order_id, symbol,
        )

        if not client_oid:
            logger.warning(
                "ExecutionProcessor: evento sem clientOid — ignorado. orderId=%s",
                order_id,
            )
            return

        # Busca PendingOrder pelo client_oid
        order = await self._find_order(client_oid)
        if order is None:
            # Pode ser uma ordem TP/SL (não passa por PendingOrder)
            await self._route_tpsl_event(event_type, client_oid, raw_event)
            return

        if event_type == KUCOIN_EVENT_OPEN:
            await self._handle_open(order, order_id)

        elif event_type == KUCOIN_EVENT_MATCH:
            await self._handle_match(order, raw_event)

        elif event_type == KUCOIN_EVENT_FILLED:
            await self._handle_filled(order, raw_event, order_id)

        elif event_type == KUCOIN_EVENT_CANCELED:
            await self._handle_canceled(order)

        else:
            logger.debug(
                "ExecutionProcessor: tipo de evento não tratado: %s", event_type
            )
    # ── TP/SL routing ──────────────────────────────────────────────────

    async def _route_tpsl_event(
        self,
        event_type: str,
        client_oid: str,
        event: Dict[str, Any],
    ) -> None:
        """
        Tenta rotear evento para SpotTpSlManager quando o clientOid não
        pertence a uma PendingOrder (i.e., é uma ordem TP ou SL).
        Se não for TP/SL, loga como órfã para a ReconciliationJob tratar.
        """
        if event_type not in (KUCOIN_EVENT_FILLED, KUCOIN_EVENT_MATCH):
            # Eventos open/canceled para ordens TP/SL são informativos; sem ação.
            logger.debug(
                "ExecutionProcessor: evento %s para clientOid=%s (sem PendingOrder) ignorado.",
                event_type, client_oid,
            )
            return

        # Import lazy para evitar ciclo na inicialização
        try:
            from app.trading.tpsl.spot_manager import get_spot_tpsl_manager
            from app.trading.tpsl.repository import TpSlRepository
        except ImportError:
            logger.warning("ExecutionProcessor: módulos TPSL não disponíveis")
            return

        manager = get_spot_tpsl_manager()
        if manager is None:
            logger.warning(
                "ExecutionProcessor: SpotTpSlManager não inicializado. "
                "clientOid=%s tratado como órfã.", client_oid,
            )
            return

        repo: TpSlRepository = manager._repo
        filled_size = event.get("filledSize", event.get("filled_size", "0"))

        # Testa se é TP
        tp_rec = await repo.find_by_tp_client_oid(client_oid)
        if tp_rec is not None:
            if event_type == KUCOIN_EVENT_FILLED:
                logger.info(
                    "ExecutionProcessor: TP FILLED clientOid=%s", client_oid
                )
                await manager.handle_tp_filled(client_oid, filled_size)
            return

        # Testa se é SL
        sl_rec = await repo.find_by_sl_client_oid(client_oid)
        if sl_rec is not None:
            if event_type == KUCOIN_EVENT_FILLED:
                logger.info(
                    "ExecutionProcessor: SL FILLED clientOid=%s", client_oid
                )
                await manager.handle_sl_filled(client_oid, filled_size)
            return

        # Não é TP nem SL
        logger.warning(
            "ExecutionProcessor: ordem órfã (client_oid=%s). "
            "Será corrigida pela ReconciliationJob em até 90s.", client_oid,
        )
    # ── Handlers individuais ──────────────────────────────────────────────────

    async def _handle_open(self, order: Dict, order_id: str) -> None:
        """Ordem aceita e aberta na exchange."""
        await self._update_order(
            client_oid=order["client_oid"],
            status=OrderStatus.OPEN,
            extra={"order_id": order_id},
        )

    async def _handle_match(self, order: Dict, event: Dict[str, Any]) -> None:
        """Execução parcial."""
        filled_size = event.get("filledSize", event.get("filled_size", "0"))
        price        = event.get("price", "0")
        fee          = event.get("fee", "0")
        fee_currency = event.get("feeCurrency", event.get("fee_currency", "USDT"))
        ts_ns        = int(event.get("ts", 0))

        await self._update_order(
            client_oid=order["client_oid"],
            status=OrderStatus.PARTIAL_FILL,
            extra={"filled_size": filled_size},
        )

        await self._apply_position_fill(
            order=order,
            match_size=Decimal(filled_size),
            price=Decimal(price),
            fee=Decimal(fee),
            fee_currency=fee_currency,
            ts_ns=ts_ns,
        )

    async def _handle_filled(
        self,
        order: Dict,
        event: Dict[str, Any],
        order_id: str,
    ) -> None:
        """Execução completa."""
        filled_size  = event.get("filledSize", event.get("filled_size", "0"))
        price        = event.get("price", "0")
        fee          = event.get("fee", "0")
        fee_currency = event.get("feeCurrency", event.get("fee_currency", "USDT"))
        ts_ns        = int(event.get("ts", 0))

        await self._update_order(
            client_oid=order["client_oid"],
            status=OrderStatus.FILLED,
            extra={
                "order_id":   order_id,
                "filled_size": filled_size,
                "filled_at":  datetime.now(timezone.utc).isoformat(),
            },
        )

        await self._apply_position_fill(
            order=order,
            match_size=Decimal(filled_size),
            price=Decimal(price),
            fee=Decimal(fee),
            fee_currency=fee_currency,
            ts_ns=ts_ns,
        )

        # Registra no ImmutableJournal
        if self._journal:
            try:
                await self._journal.log(
                    event_type="order_filled",
                    data={
                        "client_oid":  order["client_oid"],
                        "order_id":    order_id,
                        "symbol":      order.get("symbol"),
                        "side":        order.get("side"),
                        "filled_size": filled_size,
                        "price":       price,
                        "fee":         fee,
                        "fee_currency": fee_currency,
                        "bot_id":      order.get("bot_id"),
                        "user_id":     order.get("user_id"),
                        "ts_ns":       ts_ns,
                    },
                )
            except Exception as exc:
                logger.error("ExecutionProcessor: falha ao registrar journal: %s", exc)

        # Notificação ao usuário (se callback configurado)
        if self._notify:
            try:
                await self._notify(
                    order.get("user_id", ""),
                    {
                        "event":      "order_filled",
                        "symbol":     order.get("symbol"),
                        "side":       order.get("side"),
                        "size":       filled_size,
                        "price":      price,
                        "client_oid": order["client_oid"],
                    },
                )
            except Exception as exc:
                logger.warning("ExecutionProcessor: falha na notificação: %s", exc)

    async def _handle_canceled(self, order: Dict) -> None:
        """Ordem cancelada."""
        await self._update_order(
            client_oid=order["client_oid"],
            status=OrderStatus.CANCELED,
            extra={"canceled_at": datetime.now(timezone.utc).isoformat()},
        )

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _find_order(self, client_oid: str) -> Optional[Dict]:
        """Busca PendingOrder pelo client_oid."""
        if self._col is None:
            logger.warning("ExecutionProcessor: sem conexão com DB.")
            return None
        try:
            return await self._col.find_one({"client_oid": client_oid})
        except Exception as exc:
            logger.error("ExecutionProcessor._find_order: %s", exc)
            return None

    async def _update_order(
        self,
        client_oid: str,
        status: OrderStatus,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Atualiza status da PendingOrder no banco."""
        if self._col is None:
            return
        updates: Dict[str, Any] = {
            "status":     status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            updates.update(extra)
        try:
            await self._col.update_one(
                {"client_oid": client_oid},
                {"$set": updates},
            )
            logger.debug(
                "ExecutionProcessor: order %s → %s", client_oid, status.value
            )
        except Exception as exc:
            logger.error("ExecutionProcessor._update_order: %s", exc)

    # ── Position helper ───────────────────────────────────────────────────────

    async def _apply_position_fill(
        self,
        order: Dict,
        match_size: Decimal,
        price: Decimal,
        fee: Decimal,
        fee_currency: str,
        ts_ns: int,
    ) -> None:
        """Delega atualização de posição ao PositionManager."""
        if self._positions is None:
            return
        try:
            await self._positions.apply_execution(
                position_id=order.get("position_id"),   # pode ser None se não aberta ainda
                event={
                    "status":       "match",
                    "match_size":   match_size,
                    "price":        price,
                    "fee":          fee,
                    "fee_currency": fee_currency,
                    "client_oid":   order.get("client_oid"),
                    "bot_id":       order.get("bot_id"),
                    "user_id":      order.get("user_id"),
                    "symbol":       order.get("symbol"),
                    "side":         order.get("side"),
                },
            )
        except Exception as exc:
            logger.error(
                "ExecutionProcessor: falha ao atualizar PositionManager: %s", exc
            )


# ─── Instância global (lazy) ──────────────────────────────────────────────────

_processor: Optional[ExecutionProcessor] = None


def init_execution_processor(
    db: Any,
    position_manager: Any,
    journal: Optional[Any] = None,
    notification_callback: Optional[Any] = None,
) -> ExecutionProcessor:
    global _processor
    _processor = ExecutionProcessor(
        db=db,
        position_manager=position_manager,
        journal=journal,
        notification_callback=notification_callback,
    )
    logger.info("ExecutionProcessor inicializado")
    return _processor


def get_execution_processor() -> Optional[ExecutionProcessor]:
    return _processor
