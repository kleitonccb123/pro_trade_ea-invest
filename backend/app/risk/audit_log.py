"""
RiskAuditLog — Log imutável com hash encadeado

DOC-05 §10 (Auditoria imutável de todas as decisões do Risk Manager)

Cada entrada inclui um SHA-256 do conteúdo + hash da entrada anterior,
formando uma cadeia verificável de decisões.

Coleção MongoDB: `risk_audit_log`
  - índice em (userId, timestamp) para consultas por usuário
  - nenhuma entrada pode ser deletada/alterada (índice sem TTL)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

COLLECTION = "risk_audit_log"


class RiskAuditLog:
    """Log imutável de decisões do Risk Manager com hash encadeado."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def ensure_indexes(self) -> None:
        try:
            await self._db[COLLECTION].create_index([("user_id", 1), ("timestamp", -1)])
            await self._db[COLLECTION].create_index("entry_hash", unique=True)
            logger.info("RiskAuditLog: índices criados/verificados")
        except Exception as exc:
            logger.warning("RiskAuditLog.ensure_indexes: %s", exc)

    async def record(
        self,
        user_id: str,
        bot_id: str,
        symbol: str,
        action: str,           # "APPROVED" | "REJECTED"
        reason: Optional[str]  = None,
        severity: Optional[str] = None,
        details: Optional[str]  = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Registra uma decisão de risco de forma imutável.

        Returns:
            entry_hash — SHA-256 desta entrada (para rastreabilidade).
        """
        timestamp = datetime.now(timezone.utc)

        # Busca hash da última entrada deste usuário para encadeamento
        prev_hash = await self._get_last_hash(user_id)

        payload: Dict[str, Any] = {
            "user_id":   user_id,
            "bot_id":    bot_id,
            "symbol":    symbol,
            "action":    action,
            "reason":    reason,
            "severity":  severity,
            "details":   details,
            "timestamp": timestamp.isoformat(),
            "prev_hash": prev_hash,
        }

        # Hash do conteúdo desta entrada
        entry_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

        doc: Dict[str, Any] = {
            **payload,
            "timestamp": timestamp,
            "context":   context or {},
            "entry_hash": entry_hash,
        }

        try:
            await self._db[COLLECTION].insert_one(doc)
        except Exception as exc:
            # Nunca falhar silenciosamente — apenas logar
            logger.error(
                "RiskAuditLog: falha ao inserir entrada: %s (user=%s, action=%s)",
                exc, user_id, action,
            )

        return entry_hash

    async def verify_chain(self, user_id: str, limit: int = 100) -> bool:
        """
        Verifica integridade da cadeia de hashes para um usuário.
        Retorna True se a cadeia está íntegra.
        """
        cursor = self._db[COLLECTION].find(
            {"user_id": user_id},
            sort=[("timestamp", 1)],
        ).limit(limit)

        entries = await cursor.to_list(length=limit)
        if not entries:
            return True

        for i, entry in enumerate(entries):
            payload = {
                "user_id":   entry["user_id"],
                "bot_id":    entry["bot_id"],
                "symbol":    entry["symbol"],
                "action":    entry["action"],
                "reason":    entry.get("reason"),
                "severity":  entry.get("severity"),
                "details":   entry.get("details"),
                "timestamp": entry["timestamp"].isoformat()
                             if isinstance(entry["timestamp"], datetime)
                             else str(entry["timestamp"]),
                "prev_hash": entry.get("prev_hash"),
            }
            expected_hash = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()

            if expected_hash != entry.get("entry_hash"):
                logger.error(
                    "RiskAuditLog: hash inválido na entrada %d user=%s "
                    "esperado=%s encontrado=%s",
                    i, user_id, expected_hash, entry.get("entry_hash"),
                )
                return False

        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_last_hash(self, user_id: str) -> Optional[str]:
        doc = await self._db[COLLECTION].find_one(
            {"user_id": user_id},
            sort=[("timestamp", -1)],
            projection={"entry_hash": 1},
        )
        return doc["entry_hash"] if doc else None
