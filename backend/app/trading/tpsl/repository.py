"""
TpSlRepository — Acesso ao banco de dados para registros de TP/SL

Coleção MongoDB: tpsl_records

Índices recomendados (criados no startup):
  - { position_id: 1 }
  - { tp_client_oid: 1 }
  - { sl_client_oid: 1 }
  - { status: 1 }
  - { user_id: 1, status: 1 }
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.trading.tpsl.models import TpSlRecord, TpSlStatus

logger = logging.getLogger(__name__)

COLLECTION = "tpsl_records"


class TpSlRepository:
    """CRUD operations for TpSlRecord on MongoDB."""

    def __init__(self, db: Any) -> None:
        self._col = db[COLLECTION]

    # ── Criação ───────────────────────────────────────────────────────────────

    async def create(self, data: Dict[str, Any]) -> TpSlRecord:
        """Insere novo registro. Gera id se não fornecido."""
        if "id" not in data or not data["id"]:
            data["id"] = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        data.setdefault("status", TpSlStatus.ACTIVE.value)

        doc = dict(data)
        doc["_id"] = data["id"]
        await self._col.insert_one(doc)
        logger.debug("TpSlRepository: criado %s", data["id"])
        return TpSlRecord.from_dict(data)

    # ── Consultas ─────────────────────────────────────────────────────────────

    async def find_by_id(self, record_id: str) -> Optional[TpSlRecord]:
        doc = await self._col.find_one({"_id": record_id})
        return TpSlRecord.from_dict(doc) if doc else None

    async def find_by_tp_client_oid(self, client_oid: str) -> Optional[TpSlRecord]:
        doc = await self._col.find_one({"tp_client_oid": client_oid})
        return TpSlRecord.from_dict(doc) if doc else None

    async def find_by_sl_client_oid(self, client_oid: str) -> Optional[TpSlRecord]:
        doc = await self._col.find_one({"sl_client_oid": client_oid})
        return TpSlRecord.from_dict(doc) if doc else None

    async def find_active_by_position(self, position_id: str) -> Optional[TpSlRecord]:
        """Retorna o registro ACTIVE para uma posição (deve haver no máximo 1)."""
        doc = await self._col.find_one(
            {"position_id": position_id, "status": TpSlStatus.ACTIVE.value}
        )
        return TpSlRecord.from_dict(doc) if doc else None

    async def find_by_status(self, status: TpSlStatus) -> List[TpSlRecord]:
        cursor = self._col.find({"status": status.value})
        docs = await cursor.to_list(length=1000)
        return [TpSlRecord.from_dict(d) for d in docs]

    async def find_active_by_user(self, user_id: str) -> List[TpSlRecord]:
        cursor = self._col.find({"user_id": user_id, "status": TpSlStatus.ACTIVE.value})
        docs = await cursor.to_list(length=1000)
        return [TpSlRecord.from_dict(d) for d in docs]

    # ── Atualizações isoladas ─────────────────────────────────────────────────

    async def update_tp_order_id(self, record_id: str, order_id: str) -> None:
        await self._col.update_one(
            {"_id": record_id},
            {"$set": {"tp_order_id": order_id,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    async def update_sl_order_id(self, record_id: str, order_id: str) -> None:
        await self._col.update_one(
            {"_id": record_id},
            {"$set": {"sl_order_id": order_id,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    async def update_status(self, record_id: str, status: TpSlStatus) -> None:
        await self._col.update_one(
            {"_id": record_id},
            {"$set": {"status": status.value,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    # ── Fechamento (TP hit ou SL hit) ─────────────────────────────────────────

    async def close(
        self,
        record_id: str,
        status: TpSlStatus,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Marca registro como fechado com status final (TP_HIT ou SL_HIT)."""
        updates: Dict[str, Any] = {
            "status":     status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            updates.update(extra)
        await self._col.update_one({"_id": record_id}, {"$set": updates})
        logger.info("TpSlRepository: %s → %s", record_id, status.value)

    async def cancel(self, record_id: str, reason: str = "") -> None:
        await self._col.update_one(
            {"_id": record_id},
            {"$set": {
                "status":             TpSlStatus.CANCELED.value,
                "cancelation_source": reason,
                "updated_at":         datetime.now(timezone.utc).isoformat(),
            }},
        )

    async def mark_error(self, record_id: str, error: str) -> None:
        await self._col.update_one(
            {"_id": record_id},
            {"$set": {"error": error,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    async def mark_sl_failed(self, record_id: str, error: str) -> None:
        """SL falhou na exchange — anotado para auditoria."""
        await self._col.update_one(
            {"_id": record_id},
            {"$set": {"sl_send_error": error,
                      "updated_at":   datetime.now(timezone.utc).isoformat()}},
        )

    # ── Índices ───────────────────────────────────────────────────────────────

    async def ensure_indexes(self) -> None:
        """Cria índices necessários. Chamar no startup."""
        try:
            await self._col.create_index("position_id")
            await self._col.create_index("tp_client_oid", sparse=True)
            await self._col.create_index("sl_client_oid", sparse=True)
            await self._col.create_index("status")
            await self._col.create_index([("user_id", 1), ("status", 1)])
            logger.info("TpSlRepository: índices criados/verificados")
        except Exception as exc:
            logger.warning("TpSlRepository.ensure_indexes: %s", exc)
