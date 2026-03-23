"""
SpotTpSlManager — Gerencia Take Profit e Stop Loss para mercado Spot

Fluxo ao abrir posição:
  1. Gera tp_client_oid e sl_client_oid deterministicamente
  2. Persiste TpSlRecord no MongoDB (status=ACTIVE) ANTES do envio
  3. Envia ordem TP (Limit GTC) → persiste tp_order_id
  4. Envia ordem SL (Stop-Limit GTC) → persiste sl_order_id
  5. Se SL falhar → cancela TP e raise (estado nunca inconsistente)

Ao receber execution report via WebSocket:
  - TP filled → adquire Redis Lock → cancela SL → fecha registro TP_HIT
  - SL filled → adquire Redis Lock → cancela TP → fecha registro SL_HIT

Proteção de race condition:
  Redis SET NX com TTL de 30s por (position_id).
  Só o primeiro handler que adquirir o lock procede com o cancelamento.
  O segundo encontra o registro já fechado e retorna sem ação.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from app.trading.idempotency_store import generate_client_oid
from app.trading.tpsl.models import MarketType, TpSlRecord, TpSlStatus
from app.trading.tpsl.repository import TpSlRepository

logger = logging.getLogger(__name__)


class SpotTpSlManager:
    """
    Cria e gerencia ordens de Take Profit e Stop Loss para Spot.

    Uso:
    ```python
    manager = SpotTpSlManager(kucoin_client, tpsl_repo, redis_client)

    # Ao abrir posição:
    record = await manager.create(
        bot_id="bot1", user_id="user1", strategy_id="s1",
        position_id="pos123", signal_id="sig456",
        symbol="BTC-USDT", side="buy",
        filled_size=Decimal("0.1"), entry_price=Decimal("50000"),
        tp_price=Decimal("51250"), sl_price=Decimal("49250"),
        sl_stop_price=Decimal("49300"),
    )

    # Ao receber WS event "filled" para o TP:
    await manager.handle_tp_filled(record.tp_client_oid, "0.1")
    ```
    """

    LOCK_TTL_SECONDS = 30

    def __init__(
        self,
        kucoin_client: Any,          # KuCoinRawClient
        tpsl_repo: TpSlRepository,
        redis_client: Optional[Any] = None,  # redis.asyncio.Redis
        position_manager: Optional[Any] = None,
        journal: Optional[Any] = None,
    ) -> None:
        self._kucoin    = kucoin_client
        self._repo      = tpsl_repo
        self._redis     = redis_client
        self._positions = position_manager
        self._journal   = journal
        self._locks: Dict[str, asyncio.Lock] = {}   # fallback em memória
        self._locks_mx  = asyncio.Lock()

    # ── Criação do par TP/SL ──────────────────────────────────────────────────

    async def create(
        self,
        bot_id: str,
        user_id: str,
        strategy_id: str,
        position_id: str,
        signal_id: str,
        symbol: str,
        side: str,              # "buy" (long) | "sell" (short)
        filled_size: Decimal,
        entry_price: Decimal,
        tp_price: Decimal,
        sl_price: Decimal,
        sl_stop_price: Optional[Decimal] = None,
    ) -> TpSlRecord:
        """
        Persiste e envia ordens TP + SL.

        O SL usa stop-limit:
          stopPrice  = sl_stop_price (gatilho)
          limitPrice = sl_price      (preço limite de execução)

        Se sl_stop_price não for fornecido, assume sl_price + 0.1% para buy.
        """
        close_side = "sell" if side == "buy" else "buy"

        # Gatilho padrão: 0.1% mais próximo da entrada do que o limitPrice
        if sl_stop_price is None:
            buf = Decimal("1.001") if side == "buy" else Decimal("0.999")
            sl_stop_price = sl_price * buf

        # clientOids determinísticos (sobrevivem a restart)
        tp_client_oid = generate_client_oid(f"{signal_id}:tp", bot_id)
        sl_client_oid = generate_client_oid(f"{signal_id}:sl", bot_id)

        size_str  = str(filled_size)
        record_id = str(uuid.uuid4())

        # ── 1. Persiste ANTES de enviar ───────────────────────────────────────
        record = await self._repo.create({
            "id":            record_id,
            "bot_id":        bot_id,
            "user_id":       user_id,
            "strategy_id":   strategy_id,
            "position_id":   position_id,
            "market_type":   MarketType.SPOT.value,
            "symbol":        symbol,
            "side":          side,
            "total_size":    size_str,
            "remaining_size": size_str,
            "entry_price":   str(entry_price),
            "tp_price":      str(tp_price),
            "sl_price":      str(sl_price),
            "sl_stop_price": str(sl_stop_price),
            "tp_client_oid": tp_client_oid,
            "sl_client_oid": sl_client_oid,
            "status":        TpSlStatus.ACTIVE.value,
        })

        logger.info(
            "SpotTpSlManager.create: %s %s TP=%s SL=%s size=%s",
            symbol, side, tp_price, sl_price, size_str,
        )

        # ── 2. Envia TP (Limit) ────────────────────────────────────────────────
        try:
            tp_resp = await self._kucoin.place_limit_order(
                symbol=symbol,
                side=close_side,
                size=filled_size,
                price=tp_price,
                client_oid=tp_client_oid,
            )
            tp_order_id = tp_resp.get("orderId", "")
            await self._repo.update_tp_order_id(record_id, tp_order_id)
            logger.info("SpotTpSlManager: TP enviado orderId=%s", tp_order_id)

        except Exception as exc:
            logger.error("SpotTpSlManager: falha ao enviar TP: %s", exc)
            await self._repo.mark_error(record_id, f"TP_SEND_FAILED: {exc}")
            raise

        # ── 3. Envia SL (Stop-Limit) ───────────────────────────────────────────
        try:
            sl_resp = await self._kucoin.place_stop_order(
                symbol=symbol,
                side=close_side,
                size=filled_size,
                price=sl_price,
                stop_price=sl_stop_price,
                stop="loss" if side == "buy" else "entry",
                client_oid=sl_client_oid,
                remark=f"SL:{record_id[:16]}",
            )
            sl_order_id = sl_resp.get("orderId", "")
            await self._repo.update_sl_order_id(record_id, sl_order_id)
            logger.info("SpotTpSlManager: SL enviado orderId=%s", sl_order_id)

        except Exception as exc:
            logger.error("SpotTpSlManager: falha ao enviar SL — cancelando TP: %s", exc)
            await self._repo.mark_sl_failed(record_id, f"SL_SEND_FAILED: {exc}")
            # Rollback: cancela o TP já enviado para não deixar estado inconsistente
            await self._cancel_tp_order(record)
            raise

        # Recarrega do banco com os order IDs atualizados
        updated = await self._repo.find_by_id(record_id)
        return updated or record

    # ── Handlers de execução ──────────────────────────────────────────────────

    async def handle_tp_filled(self, tp_client_oid: str, filled_size: str) -> None:
        """
        Chamado pelo ExecutionProcessor quando TP é executado.
        Cancela o SL e fecha o registro.
        """
        lock_acquired = await self._acquire_lock(f"tpsl:cancel:{tp_client_oid}")
        if not lock_acquired:
            logger.warning(
                "SpotTpSlManager.handle_tp_filled: lock não adquirido (%s) — "
                "provável race condition já resolvida.", tp_client_oid,
            )
            return

        try:
            record = await self._repo.find_by_tp_client_oid(tp_client_oid)
            if not record or record.status != TpSlStatus.ACTIVE:
                return

            logger.info(
                "TP HIT — cancelando SL. record=%s slOrderId=%s",
                record.id, record.sl_order_id,
            )

            await self._cancel_sl_order(record)

            await self._repo.close(record.id, TpSlStatus.TP_HIT, {
                "tp_filled_size":    filled_size,
                "tp_filled_at":      datetime.now(timezone.utc).isoformat(),
                "cancelation_source": "TP_HIT",
            })

            await self._close_position_on_exchange(record, filled_size, record.tp_price)
            await self._record_journal(record, "tpsl_tp_hit", filled_size, record.tp_price)

        finally:
            await self._release_lock(f"tpsl:cancel:{tp_client_oid}")

    async def handle_sl_filled(self, sl_client_oid: str, filled_size: str) -> None:
        """
        Chamado pelo ExecutionProcessor quando SL é executado.
        Cancela o TP e fecha o registro.
        """
        lock_acquired = await self._acquire_lock(f"tpsl:cancel:{sl_client_oid}")
        if not lock_acquired:
            logger.warning(
                "SpotTpSlManager.handle_sl_filled: lock não adquirido (%s).",
                sl_client_oid,
            )
            return

        try:
            record = await self._repo.find_by_sl_client_oid(sl_client_oid)
            if not record or record.status != TpSlStatus.ACTIVE:
                return

            logger.info(
                "SL HIT — cancelando TP. record=%s tpOrderId=%s",
                record.id, record.tp_order_id,
            )

            await self._cancel_tp_order(record)

            await self._repo.close(record.id, TpSlStatus.SL_HIT, {
                "sl_filled_size":    filled_size,
                "sl_filled_at":      datetime.now(timezone.utc).isoformat(),
                "cancelation_source": "SL_HIT",
            })

            await self._close_position_on_exchange(record, filled_size, record.sl_price)
            await self._record_journal(record, "tpsl_sl_hit", filled_size, record.sl_price)

        finally:
            await self._release_lock(f"tpsl:cancel:{sl_client_oid}")

    # ── Cancel helpers ────────────────────────────────────────────────────────

    async def _cancel_tp_order(self, record: TpSlRecord) -> None:
        if not record.tp_order_id:
            return
        try:
            await self._kucoin.cancel_order(record.tp_order_id)
            logger.info("SpotTpSlManager: TP cancelado orderId=%s", record.tp_order_id)
        except Exception as exc:
            logger.warning("SpotTpSlManager: falha ao cancelar TP %s: %s",
                           record.tp_order_id, exc)

    async def _cancel_sl_order(self, record: TpSlRecord) -> None:
        if not record.sl_order_id:
            return
        try:
            await self._kucoin.cancel_stop_order(record.sl_order_id)
            logger.info("SpotTpSlManager: SL cancelado orderId=%s", record.sl_order_id)
        except Exception as exc:
            logger.warning("SpotTpSlManager: falha ao cancelar SL %s: %s",
                           record.sl_order_id, exc)

    # ── PositionManager integration ───────────────────────────────────────────

    async def _close_position_on_exchange(
        self,
        record: TpSlRecord,
        filled_size: str,
        exit_price_str: str,
    ) -> None:
        if not self._positions:
            return
        try:
            await self._positions.close_position(
                position_id=record.position_id,
                exit_order_id=record.tp_order_id or record.sl_order_id or "",
                exit_price=Decimal(exit_price_str),
                exit_size=Decimal(filled_size),
            )
        except Exception as exc:
            logger.error("SpotTpSlManager: falha ao fechar posição: %s", exc)

    # ── Journal integration ───────────────────────────────────────────────────

    async def _record_journal(
        self,
        record: TpSlRecord,
        event_type: str,
        filled_size: str,
        exit_price: str,
    ) -> None:
        if not self._journal:
            return
        try:
            await self._journal.log(
                event_type=event_type,
                data={
                    "record_id":   record.id,
                    "position_id": record.position_id,
                    "symbol":      record.symbol,
                    "side":        record.side,
                    "filled_size": filled_size,
                    "exit_price":  exit_price,
                    "bot_id":      record.bot_id,
                    "user_id":     record.user_id,
                },
            )
        except Exception as exc:
            logger.warning("SpotTpSlManager: falha ao registrar journal: %s", exc)

    # ── Locking (Redis com fallback asyncio.Lock) ─────────────────────────────

    async def _acquire_lock(self, key: str) -> bool:
        if self._redis is not None:
            result = await self._redis.set(key, "1", ex=self.LOCK_TTL_SECONDS, nx=True)
            return result is not None
        # Fallback: asyncio.Lock por chave em memória
        async with self._locks_mx:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            lock = self._locks[key]
        try:
            return lock.acquire_nowait() or True
        except Exception:
            return lock.locked() is False

    async def _release_lock(self, key: str) -> None:
        if self._redis is not None:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
        else:
            async with self._locks_mx:
                lock = self._locks.get(key)
            if lock and lock.locked():
                try:
                    lock.release()
                except Exception:
                    pass


# ─── Instância global (lazy) ──────────────────────────────────────────────────

_spot_manager: Optional[SpotTpSlManager] = None


def init_spot_tpsl_manager(
    kucoin_client: Any,
    tpsl_repo: TpSlRepository,
    redis_client: Optional[Any] = None,
    position_manager: Optional[Any] = None,
    journal: Optional[Any] = None,
) -> SpotTpSlManager:
    global _spot_manager
    _spot_manager = SpotTpSlManager(
        kucoin_client=kucoin_client,
        tpsl_repo=tpsl_repo,
        redis_client=redis_client,
        position_manager=position_manager,
        journal=journal,
    )
    logger.info("SpotTpSlManager inicializado")
    return _spot_manager


def get_spot_tpsl_manager() -> Optional[SpotTpSlManager]:
    return _spot_manager
