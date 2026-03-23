"""
order_intent_store.py — DOC-K04

Write-Ahead Log (WAL) para ordens KuCoin.

Fluxo correto:
  1. Gerar clientOid UMA VEZ (antes de qualquer await)
  2. Persistir intent com status="pending" no MongoDB
  3. Enviar ordem para a KuCoin usando o mesmo clientOid
  4. Atualizar status para "sent" / "filled" / "error"

Em caso de retry, o intent com o mesmo clientOid já existe (índice único)
→ a KuCoin deduplica via clientOid → sem duplicatas.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger("engine.order_intent_store")


class DuplicateOrderIntentError(Exception):
    """Raised when an intent with the same client_oid already exists."""


class OrderIntentStore:
    """
    Persiste intenções de ordem ANTES de enviá-las à exchange.

    Collection MongoDB: ``order_intents``
    Índice único: ``client_oid`` (garantido no startup via ensure_indexes)
    """

    COLLECTION = "order_intents"

    def __init__(self, db):
        self._db = db

    # ── Indexes ───────────────────────────────────────────────────────────────

    @classmethod
    async def ensure_indexes(cls, db) -> None:
        """
        Criar índice único em client_oid.
        Chamar no startup da aplicação (lifespan / before server start).
        """
        col = db[cls.COLLECTION]
        await col.create_index("client_oid", unique=True, background=True)
        await col.create_index("bot_instance_id", background=True)
        await col.create_index(
            [("status", 1), ("created_at", 1)], background=True
        )
        logger.info("[DOC-K04] Índices de order_intents confirmados")

    # ── Write ─────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_client_oid() -> str:
        """
        Gera um clientOid único.
        DEVE ser chamado UMA VEZ e armazenado — não regerar em retries.
        """
        return str(uuid.uuid4()).replace("-", "")[:32]

    async def create_intent(
        self,
        bot_instance_id: str,
        user_id: str,
        pair: str,
        side: str,
        order_type: str,
        funds: Optional[float] = None,
        size: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_oid: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """
        Persiste uma intenção de ordem com status='pending'.

        Args:
            client_oid: Se None, um novo UUID será gerado. Em retries,
                        PASSAR O MESMO client_oid do intent original.

        Returns:
            O documento inserido (inclui ``_id`` e ``client_oid``).

        Raises:
            DuplicateOrderIntentError: se client_oid já existe no banco.
        """
        if client_oid is None:
            client_oid = self.generate_client_oid()

        doc = {
            "client_oid": client_oid,
            "bot_instance_id": bot_instance_id,
            "user_id": user_id,
            "pair": pair,
            "side": side,
            "order_type": order_type,
            "funds": funds,
            "size": size,
            "price": price,
            "stop_price": stop_price,
            "status": "pending",   # pending → sent → filled | error | cancelled
            "exchange_order_id": None,
            "fill_price": None,
            "fill_funds": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            **(extra or {}),
        }

        from pymongo.errors import DuplicateKeyError

        try:
            result = await self._db[self.COLLECTION].insert_one(doc)
            doc["_id"] = result.inserted_id
            logger.debug(
                f"[DOC-K04] Intent criado: client_oid={client_oid} "
                f"side={side} pair={pair}"
            )
            return doc
        except DuplicateKeyError:
            existing = await self._db[self.COLLECTION].find_one(
                {"client_oid": client_oid}
            )
            logger.warning(
                f"[DOC-K04] Intent duplicado: client_oid={client_oid} "
                f"— retornando existente (status={existing.get('status')})"
            )
            raise DuplicateOrderIntentError(
                f"client_oid={client_oid} já existe com status={existing.get('status')}"
            )

    async def mark_sent(self, client_oid: str, exchange_order_id: str) -> None:
        """Atualiza status para 'sent' após envio bem-sucedido à exchange."""
        await self._db[self.COLLECTION].update_one(
            {"client_oid": client_oid},
            {
                "$set": {
                    "status": "sent",
                    "exchange_order_id": exchange_order_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    async def mark_filled(
        self,
        client_oid: str,
        exchange_order_id: str,
        fill_price: float,
        fill_funds: float,
        fee: float,
    ) -> None:
        """Atualiza status para 'filled' via execution report do WebSocket."""
        await self._db[self.COLLECTION].update_one(
            {"client_oid": client_oid},
            {
                "$set": {
                    "status": "filled",
                    "exchange_order_id": exchange_order_id,
                    "fill_price": fill_price,
                    "fill_funds": fill_funds,
                    "fee": fee,
                    "filled_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    async def mark_error(self, client_oid: str, error: str) -> None:
        """Atualiza status para 'error' após falha confirmada."""
        await self._db[self.COLLECTION].update_one(
            {"client_oid": client_oid},
            {
                "$set": {
                    "status": "error",
                    "error": error[:500],
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    async def mark_cancelled(self, client_oid: str) -> None:
        """Atualiza status para 'cancelled'."""
        await self._db[self.COLLECTION].update_one(
            {"client_oid": client_oid},
            {
                "$set": {
                    "status": "cancelled",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_client_oid(self, client_oid: str) -> Optional[dict]:
        return await self._db[self.COLLECTION].find_one({"client_oid": client_oid})

    async def get_pending_for_bot(self, bot_instance_id: str) -> list:
        """Retorna intents em estado pending/sent para um bot — usado na reconciliação."""
        cursor = self._db[self.COLLECTION].find(
            {
                "bot_instance_id": bot_instance_id,
                "status": {"$in": ["pending", "sent"]},
            }
        )
        return await cursor.to_list(length=100)
