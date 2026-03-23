"""
ImmutableJournal — Log imutavel de auditoria financeira

Problema sem isso:
  - Logs de ordem, execucao e risco sao mutaveis (update/delete possivel)
  - Sem trilha de auditoria forense
  - Impossivel rastrear divergencias pos-fato
  - Incompativel com requisitos de compliance financeiro

Solucao:
  - Colecao MongoDB append-only (sem update, sem delete por design)
  - Hash encadeado (cada entrada inclui hash da anterior) -> integridade
  - Tipos de entrada: ORDER, EXECUTION, RISK_CHANGE, RECONCILIATION, SYSTEM
  - API forcosamente aditiva: so log(), nao update() nem delete()

Schema de cada entrada:
  {
    "_id":          ObjectId (imutavel),
    "seq":          int (sequencial unico, monotonicamente crescente),
    "event_type":   str,
    "timestamp":    datetime UTC,
    "data":         dict,    # payload do evento
    "prev_hash":    str,     # SHA256 da entrada anterior (encadeamento)
    "entry_hash":   str,     # SHA256 desta entrada (prev_hash + seq + data)
  }

Garantias no MongoDB:
  - Nao chamar update/replace/delete nesta classe (enforced by design)
  - Recomendado: criar usuario MongoDB com permissao apenas insert + find
    na colecao journal

Integridade:
  - audit_journal.verify_chain() percorre todos os registros
    e recomputa os hashes
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ImmutableJournal:
    """
    Diario financeiro imutavel com integridade verificavel por hash encadeado.

    Uso:
    ```python
    journal = ImmutableJournal(db)

    # Registrar qualquer evento critico:
    await journal.log(
        event_type="order_placed",
        data={"order_id": "abc", "symbol": "BTC-USDT", "size": "0.1"}
    )

    # Verificar integridade da cadeia:
    ok, broken_at = await journal.verify_chain()
    ```
    """

    COLLECTION = "immutable_journal"

    # Tipos de evento padronizados
    EVENT_ORDER_PLACED       = "order_placed"
    EVENT_ORDER_FILLED       = "order_filled"
    EVENT_ORDER_CANCELLED    = "order_cancelled"
    EVENT_ORDER_REJECTED     = "order_rejected"
    EVENT_EXECUTION_REPORT   = "execution_report"
    EVENT_RISK_CHANGE        = "risk_change"
    EVENT_KILL_SWITCH_ON     = "kill_switch_activated"
    EVENT_KILL_SWITCH_OFF    = "kill_switch_deactivated"
    EVENT_RECONCILIATION_FIX = "reconciliation_fix"
    EVENT_CIRCUIT_OPEN       = "circuit_breaker_open"
    EVENT_CIRCUIT_CLOSE      = "circuit_breaker_close"
    EVENT_SYSTEM             = "system"

    def __init__(self, db: Any) -> None:
        self._db  = db
        self._col = db[self.COLLECTION]
        self._last_hash: Optional[str] = None  # cache do ultimo hash

    # ──────────────────────────── Interface publica ───────────────────────────

    async def log(
        self,
        event_type: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> str:
        """
        Adiciona uma entrada imutavel ao journal.

        Retorna: entry_hash (SHA256 da entrada)
        """
        seq = await self._next_seq()
        prev_hash = await self._get_last_hash(seq)

        timestamp = datetime.now(timezone.utc)

        # Garante que data e serializavel
        safe_data = self._make_serializable(data)

        entry_hash = self._compute_hash(
            prev_hash=prev_hash,
            seq=seq,
            event_type=event_type,
            timestamp=timestamp.isoformat(),
            data=safe_data,
        )

        doc: Dict[str, Any] = {
            "seq":        seq,
            "event_type": event_type,
            "timestamp":  timestamp,
            "user_id":    user_id,
            "data":       safe_data,
            "prev_hash":  prev_hash,
            "entry_hash": entry_hash,
        }

        await self._col.insert_one(doc)
        self._last_hash = entry_hash

        logger.debug(f"Journal: [{seq}] {event_type} hash={entry_hash[:12]}...")
        return entry_hash

    async def verify_chain(self) -> tuple[bool, Optional[int]]:
        """
        Percorre todas as entradas e recomputa os hashes.

        Retorna: (ok: bool, broken_at_seq: int | None)
          - ok=True significa cadeia integra
          - broken_at_seq indica onde a cadeia foi quebrada
        """
        cursor = self._col.find({}, sort=[("seq", 1)])
        entries = await cursor.to_list(length=100_000)

        if not entries:
            return True, None

        prev_hash = "genesis"

        for entry in entries:
            seq        = entry["seq"]
            stored_ph  = entry.get("prev_hash", "")
            stored_eh  = entry.get("entry_hash", "")

            if stored_ph != prev_hash:
                logger.error(
                    f"verify_chain: prev_hash divergente em seq={seq}. "
                    f"Esperado={prev_hash[:12]}... Encontrado={stored_ph[:12]}..."
                )
                return False, seq

            recomputed = self._compute_hash(
                prev_hash=stored_ph,
                seq=seq,
                event_type=entry.get("event_type", ""),
                timestamp=entry["timestamp"].isoformat()
                           if isinstance(entry["timestamp"], datetime)
                           else str(entry["timestamp"]),
                data=entry.get("data", {}),
            )

            if recomputed != stored_eh:
                logger.error(
                    f"verify_chain: entry_hash corrompido em seq={seq}. "
                    f"Esperado={recomputed[:12]}... Armazenado={stored_eh[:12]}..."
                )
                return False, seq

            prev_hash = stored_eh

        logger.info(f"verify_chain: cadeia OK ({len(entries)} entradas)")
        return True, None

    async def get_entries(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Consulta entradas do journal (somente leitura)."""
        query: Dict[str, Any] = {}
        if event_type:
            query["event_type"] = event_type
        if user_id:
            query["user_id"] = user_id

        cursor = self._col.find(query, sort=[("seq", -1)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    # ─────────────────────────── Internos ────────────────────────────────────

    async def _next_seq(self) -> int:
        """Retorna proximo numero de sequencia monotonicamente crescente."""
        try:
            last = await self._col.find_one(
                {},
                sort=[("seq", -1)],
                projection={"seq": 1},
            )
            return (last["seq"] + 1) if last else 1
        except Exception:
            return 1

    async def _get_last_hash(self, current_seq: int) -> str:
        """Retorna o entry_hash da entrada anterior (para encadeamento)."""
        if current_seq == 1:
            return "genesis"

        if self._last_hash:
            return self._last_hash

        try:
            last = await self._col.find_one(
                {},
                sort=[("seq", -1)],
                projection={"entry_hash": 1},
            )
            return last["entry_hash"] if last else "genesis"
        except Exception:
            return "genesis"

    @staticmethod
    def _compute_hash(
        prev_hash: str,
        seq: int,
        event_type: str,
        timestamp: str,
        data: Any,
    ) -> str:
        """SHA256 do conteudo canonico da entrada."""
        payload = json.dumps(
            {
                "prev_hash":  prev_hash,
                "seq":        seq,
                "event_type": event_type,
                "timestamp":  timestamp,
                "data":       data,
            },
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _make_serializable(data: Any) -> Any:
        """Converte Decimal, datetime e outros tipos nao-JSON-nativos."""
        if isinstance(data, dict):
            return {k: ImmutableJournal._make_serializable(v) for k, v in data.items()}
        if isinstance(data, list):
            return [ImmutableJournal._make_serializable(i) for i in data]
        if hasattr(data, "__float__"):  # Decimal
            return str(data)
        if isinstance(data, datetime):
            return data.isoformat()
        return data


# ────────────────────────── Instancia Global ─────────────────────────────────

_journal_instance: Optional[ImmutableJournal] = None


def init_immutable_journal(db: Any) -> ImmutableJournal:
    """
    Inicializa instancia global do ImmutableJournal.

    Chamar no startup:
    ```python
    from app.trading.immutable_journal import init_immutable_journal
    journal = init_immutable_journal(db)
    ```
    """
    global _journal_instance
    _journal_instance = ImmutableJournal(db)
    return _journal_instance


def get_journal() -> Optional[ImmutableJournal]:
    """Retorna instancia global, ou None se nao inicializada."""
    return _journal_instance
