"""
ReconciliationJob — Sincronizacao periodica banco <-> KuCoin

Problema sem isso:
  - WebSocket pode dropar eventos (reconexao, restart do cluster KuCoin)
  - Ordens ficam em estado PENDING / OPEN no banco sem terem sido preenchidas
  - Sistema acredita que tem posicao aberta quando ela nao existe mais

Solucao:
  - Cron a cada 60-120 s: GET /api/v1/orders?status=active
  - Compara com banco (ordens status=OPEN)
  - Divergencias sao corrigidas e logadas no ImmutableJournal

Fluxo:
    Scheduler (APScheduler ou asyncio.Task periodica)
        |
    ReconciliationJob.run()
        |
    GET /api/v1/orders?status=active (KuCoin)
        |
    Compara com banco: query orders WHERE status IN (PENDING, OPEN)
        |
    Divergencias -> atualiza banco + emite evento + registra journal
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ReconciliationResult:
    """Resultado de um ciclo de reconciliacao."""

    def __init__(self) -> None:
        self.checked_at: datetime = datetime.now(timezone.utc)
        self.orders_on_exchange: int = 0
        self.orders_in_db: int = 0
        self.divergences_found: int = 0
        self.divergences_fixed: int = 0
        self.errors: List[str] = []

    def __repr__(self) -> str:
        return (
            f"ReconciliationResult("
            f"checked_at={self.checked_at.isoformat()}, "
            f"exchange={self.orders_on_exchange}, "
            f"db={self.orders_in_db}, "
            f"divergences={self.divergences_found}, "
            f"fixed={self.divergences_fixed})"
        )


class ReconciliationJob:
    """
    Job periodico de reconciliacao banco <-> KuCoin.

    Uso no startup:
    ```python
    job = ReconciliationJob(
        kucoin_client=kucoin_client,
        db=db,
        journal=immutable_journal,
        interval_s=90,
    )
    await job.start()
    # ... on shutdown:
    await job.stop()
    ```
    """

    def __init__(
        self,
        kucoin_client: Any,          # KuCoinRawClient
        db: Any,                     # motor AsyncIOMotorDatabase
        journal: Optional[Any] = None,  # ImmutableJournal
        interval_s: float = 90.0,
        max_errors_before_alert: int = 3,
    ) -> None:
        self._client   = kucoin_client
        self._db       = db
        self._journal  = journal
        self._interval = interval_s
        self._max_errors = max_errors_before_alert

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._consecutive_errors = 0
        self._last_result: Optional[ReconciliationResult] = None

        logger.info(
            f"ReconciliationJob criado (intervalo={interval_s}s)"
        )

    # ──────────────────────────── Ciclo de vida ──────────────────────────────

    async def start(self) -> None:
        """Inicia o loop periodico em background."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ReconciliationJob iniciado")

    async def stop(self) -> None:
        """Para o loop e aguarda finalizacao."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ReconciliationJob parado")

    @property
    def last_result(self) -> Optional[ReconciliationResult]:
        return self._last_result

    # ─────────────────────────── Loop principal ──────────────────────────────

    async def _loop(self) -> None:
        """Loop que executa reconciliacao a cada _interval segundos."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if not self._running:
                    break
                result = await self.run()
                self._last_result = result
                self._consecutive_errors = 0
                logger.info(f"Reconciliacao concluida: {result}")

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._consecutive_errors += 1
                logger.error(
                    f"Erro no ReconciliationJob: {exc} "
                    f"(consecutivos: {self._consecutive_errors})"
                )
                if self._consecutive_errors >= self._max_errors:
                    logger.critical(
                        f"ReconciliationJob: {self._max_errors} erros consecutivos. "
                        f"Verificar conectividade com KuCoin e banco."
                    )

    # ─────────────────────────── Logica principal ────────────────────────────

    async def run(self) -> ReconciliationResult:
        """
        Executa um ciclo completo de reconciliacao.

        Etapas:
        1. Busca ordens ativas na KuCoin (REST)
        2. Busca ordens PENDING/OPEN no banco
        3. Detecta divergencias
        4. Corrige banco e registra no journal
        """
        result = ReconciliationResult()

        try:
            exchange_orders = await self._fetch_active_orders_from_exchange()
            result.orders_on_exchange = len(exchange_orders)
        except Exception as exc:
            result.errors.append(f"Falha ao buscar ordens da exchange: {exc}")
            logger.error(f"Reconciliacao: erro ao consultar KuCoin: {exc}")
            return result

        try:
            db_orders = await self._fetch_pending_orders_from_db()
            result.orders_in_db = len(db_orders)
        except Exception as exc:
            result.errors.append(f"Falha ao buscar ordens do banco: {exc}")
            logger.error(f"Reconciliacao: erro ao consultar banco: {exc}")
            return result

        # Indice por order_id da exchange
        exchange_ids: Set[str] = {o["orderId"] for o in exchange_orders if o.get("orderId")}
        # Indice por order_id do banco
        db_by_exchange_id: Dict[str, Dict] = {}
        for order in db_orders:
            eid = order.get("exchange_order_id") or order.get("orderId", "")
            if eid:
                db_by_exchange_id[eid] = order

        # ── Divergencia 1: ordem no banco como OPEN mas nao existe na exchange
        # → Provavelmente foi preenchida/cancelada e o WS perdeu o evento
        for eid, db_order in db_by_exchange_id.items():
            if eid not in exchange_ids:
                result.divergences_found += 1
                await self._handle_missing_from_exchange(db_order, result)

        # ── Divergencia 2: ordem ativa na exchange mas nao esta no banco
        # → Ordem colocada manualmente ou via outro sistema
        for ex_order in exchange_orders:
            eid = ex_order.get("orderId", "")
            if eid not in db_by_exchange_id:
                result.divergences_found += 1
                await self._handle_ghost_exchange_order(ex_order, result)

        return result

    # ─────────────────────────── Helpers ─────────────────────────────────────

    async def _fetch_active_orders_from_exchange(self) -> List[Dict]:
        """GET /api/v1/orders?status=active"""
        raw = await self._client.get_orders(status="active")
        return raw if isinstance(raw, list) else raw.get("items", [])

    async def _fetch_pending_orders_from_db(self) -> List[Dict]:
        """Busca ordens com status PENDING ou OPEN no banco."""
        try:
            cursor = self._db["orders"].find(
                {"status": {"$in": ["PENDING", "OPEN", "pending", "open"]}},
                {"_id": 1, "exchange_order_id": 1, "orderId": 1,
                 "status": 1, "symbol": 1, "user_id": 1},
            )
            return await cursor.to_list(length=1000)
        except Exception as exc:
            logger.warning(f"Erro ao consultar banco (modo degradado): {exc}")
            return []

    async def _handle_missing_from_exchange(
        self,
        db_order: Dict,
        result: ReconciliationResult,
    ) -> None:
        """
        Ordem estava OPEN no banco mas nao existe mais na exchange ativa.
        Busca detalhes individuais para saber o status real.
        """
        order_id = db_order.get("exchange_order_id") or db_order.get("orderId", "")
        symbol   = db_order.get("symbol", "?")
        user_id  = db_order.get("user_id", "unknown")

        try:
            # Busca o estado real da ordem
            detail = await self._client.get_order(order_id)
            real_status = detail.get("isActive", True)

            new_status = "OPEN" if real_status else "FILLED"
            if detail.get("cancelExist"):
                new_status = "CANCELLED"

            # Atualiza banco
            await self._db["orders"].update_one(
                {"exchange_order_id": order_id},
                {"$set": {
                    "status": new_status,
                    "reconciled_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

            # Registra no journal imutavel
            if self._journal:
                await self._journal.log(
                    event_type="reconciliation_fix",
                    data={
                        "order_id":   order_id,
                        "symbol":     symbol,
                        "user_id":    user_id,
                        "old_status": db_order.get("status"),
                        "new_status": new_status,
                        "source":     "reconciliation_job",
                    },
                )

            result.divergences_fixed += 1
            logger.warning(
                f"Reconciliacao: ordem {order_id} ({symbol}) "
                f"corrigida para {new_status}"
            )

        except Exception as exc:
            err = f"Falha ao corrigir {order_id}: {exc}"
            result.errors.append(err)
            logger.error(f"Reconciliacao: {err}")

    async def _handle_ghost_exchange_order(
        self,
        ex_order: Dict,
        result: ReconciliationResult,
    ) -> None:
        """
        Ordem existe na exchange mas nao esta no banco.
        Registra como aviso — pode ser ordem manual do usuario.
        """
        order_id = ex_order.get("orderId", "?")
        symbol   = ex_order.get("symbol", "?")

        logger.warning(
            f"Reconciliacao: ordem fantasma na exchange "
            f"{order_id} ({symbol}) — nao encontrada no banco. "
            f"Pode ser ordem manual do usuario."
        )

        if self._journal:
            await self._journal.log(
                event_type="reconciliation_ghost_order",
                data={
                    "order_id": order_id,
                    "symbol":   symbol,
                    "side":     ex_order.get("side"),
                    "size":     str(ex_order.get("size", "0")),
                    "source":   "reconciliation_job",
                },
            )

        result.divergences_fixed += 1
