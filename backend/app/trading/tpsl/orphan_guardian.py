"""
OrphanGuardian — Loop periódico que detecta e fecha TpSlRecords órfãos

Um TpSlRecord é órfão quando:
  - status = ACTIVE
  - MAS a posição associada está FECHADA (ou inexistente) no PositionManager

Isso pode ocorrer quando:
  - A posição foi fechada manualmente fora do sistema
  - Um crash ocorreu entre o fechamento da posição e o cancelamento de TP/SL
  - Msg de WS perdida e reconciliação não cobriu o caso

Ação:
  1. Cancela tp_order_id via cancel_order (Limit)
  2. Cancela sl_order_id via cancel_stop_order (Stop-Limit)
  3. Marca o TpSlRecord como ORPHANED

Ciclo padrão: 300 segundos (5 minutos)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.trading.tpsl.models import TpSlStatus
from app.trading.tpsl.repository import TpSlRepository

logger = logging.getLogger(__name__)


class OrphanGuardian:
    """
    Garante que não existam ordens TP/SL ativas para posições já fechadas.

    Uso:
    ```python
    guardian = OrphanGuardian(
        tpsl_repo=repo,
        position_manager=pm,
        kucoin_client=client,
        interval_s=300.0,
    )
    await guardian.start()
    # ...
    await guardian.stop()
    ```
    """

    def __init__(
        self,
        tpsl_repo: TpSlRepository,
        position_manager: Any,         # PositionManager
        kucoin_client: Any,            # KuCoinRawClient
        interval_s: float = 300.0,
    ) -> None:
        self._repo      = tpsl_repo
        self._positions = position_manager
        self._kucoin    = kucoin_client
        self._interval  = interval_s
        self._task: Optional[asyncio.Task] = None
        self._running   = False

    async def start(self) -> None:
        if self._task and not self._task.done():
            logger.warning("OrphanGuardian já está rodando")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="orphan_guardian")
        logger.info("OrphanGuardian iniciado (intervalo=%.0fs)", self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OrphanGuardian encerrado")

    # ── Loop principal ────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._scan_and_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("OrphanGuardian: erro no scan: %s", exc, exc_info=True)
            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break

    async def _scan_and_cleanup(self) -> None:
        active_records = await self._repo.find_by_status(TpSlStatus.ACTIVE)

        if not active_records:
            logger.debug("OrphanGuardian: nenhum TpSlRecord ACTIVE encontrado")
            return

        logger.debug("OrphanGuardian: verificando %d registros ACTIVE", len(active_records))
        cleaned = 0

        for record in active_records:
            try:
                is_orphan = await self._is_position_closed(record.position_id)
                if not is_orphan:
                    continue

                logger.warning(
                    "OrphanGuardian: ORPHAN detectado record=%s position=%s symbol=%s",
                    record.id, record.position_id, record.symbol,
                )

                await self._cancel_orders(record)
                await self._repo.update_status(record.id, TpSlStatus.ORPHANED)
                cleaned += 1

            except Exception as exc:
                logger.error(
                    "OrphanGuardian: erro ao processar record=%s: %s",
                    record.id, exc,
                )

        if cleaned:
            logger.info("OrphanGuardian: %d registro(s) órfão(s) limpos", cleaned)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _is_position_closed(self, position_id: str) -> bool:
        """Retorna True se a posição NÃO existe ou está fechada/zerada."""
        if self._positions is None:
            return False
        try:
            pos = await self._positions.get_position(position_id)
            if pos is None:
                return True
            # Considera fechada se size == 0 ou status em {closed, flat, done}
            size = getattr(pos, "size", None) or pos.get("size", None)
            if size is not None and float(size) == 0.0:
                return True
            status = (
                getattr(pos, "status", None) or pos.get("status", "")
            )
            return str(status).lower() in {"closed", "flat", "done", "canceled"}
        except Exception as exc:
            logger.warning(
                "OrphanGuardian: não foi possível verificar posição %s: %s",
                position_id, exc,
            )
            return False

    async def _cancel_orders(self, record: Any) -> None:
        """Cancela TP (Limit) e SL (Stop-Limit) na exchange, silenciosamente."""
        if record.tp_order_id:
            try:
                await self._kucoin.cancel_order(record.tp_order_id)
                logger.info(
                    "OrphanGuardian: TP cancelado orderId=%s", record.tp_order_id
                )
            except Exception as exc:
                logger.warning(
                    "OrphanGuardian: falha ao cancelar TP %s: %s",
                    record.tp_order_id, exc,
                )

        if record.sl_order_id:
            try:
                await self._kucoin.cancel_stop_order(record.sl_order_id)
                logger.info(
                    "OrphanGuardian: SL cancelado orderId=%s", record.sl_order_id
                )
            except Exception as exc:
                logger.warning(
                    "OrphanGuardian: falha ao cancelar SL %s: %s",
                    record.sl_order_id, exc,
                )


# ─── Instância global (lazy) ──────────────────────────────────────────────────

_guardian: Optional[OrphanGuardian] = None


def init_orphan_guardian(
    tpsl_repo: TpSlRepository,
    position_manager: Any,
    kucoin_client: Any,
    interval_s: float = 300.0,
) -> OrphanGuardian:
    global _guardian
    _guardian = OrphanGuardian(
        tpsl_repo=tpsl_repo,
        position_manager=position_manager,
        kucoin_client=kucoin_client,
        interval_s=interval_s,
    )
    logger.info("OrphanGuardian criado (intervalo=%.0fs)", interval_s)
    return _guardian


def get_orphan_guardian() -> Optional[OrphanGuardian]:
    return _guardian
