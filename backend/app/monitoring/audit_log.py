"""
Log de Auditoria Financeira — DOC-08 §4

IMUTÁVEL — nunca deletar entradas desta coleção.

Toda ação monetária do sistema deve ser registrada aqui para compliance.
Tipos de eventos comuns:
  "order_placed"     — ordem enviada à exchange
  "order_filled"     — ordem preenchida na exchange
  "trade_opened"     — posição aberta
  "trade_closed"     — posição fechada com PnL
  "balance_changed"  — saldo alterado (depósito/retirada)
  "kill_switch"      — bot parado por kill switch
  "risk_breach"      — violação de regra de risco

Uso::

    from app.monitoring.audit_log import log_financial_event, create_audit_indexes

    # No startup:
    await create_audit_indexes(db)

    # Em qualquer operação financeira:
    await log_financial_event(
        db=db,
        event_type="trade_closed",
        user_id="u1",
        bot_instance_id="bot-abc",
        amount_usdt=12.50,
        metadata={"exit_price": 68000, "pnl_net": 2.83, "reason": "take_profit"},
        severity="info",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

_AUDIT_COLLECTION = "audit_log"
_SCHEMA_VERSION   = "1.0"


async def log_financial_event(
    db: Any,
    event_type: str,
    user_id: str,
    bot_instance_id: str,
    amount_usdt: float,
    metadata: dict,
    severity: str = "info",
    trade_id: Optional[str] = None,
) -> None:
    """
    Registra evento financeiro no log de auditoria (imutável).

    Parâmetros
    ----------
    db              : AsyncIOMotorDatabase — banco Motor
    event_type      : tipo do evento (ex: "trade_closed", "order_placed")
    user_id         : ID do usuário dono do bot
    bot_instance_id : ID da instância do bot
    amount_usdt     : valor monetário envolvido (positivo = crédito, negativo = débito)
    metadata        : dados adicionais do evento (preços, quantidades, motivos, etc.)
    severity        : "info" | "warning" | "critical"
    trade_id        : ID opcional do trade para rastreabilidade cruzada
    """
    doc: dict = {
        "event_type":       event_type,
        "user_id":          user_id,
        "bot_instance_id":  bot_instance_id,
        "amount_usdt":      amount_usdt,
        "metadata":         metadata,
        "severity":         severity,
        "schema_version":   _SCHEMA_VERSION,
        "timestamp":        datetime.utcnow(),
    }
    if trade_id is not None:
        doc["trade_id"] = trade_id

    try:
        await db[_AUDIT_COLLECTION].insert_one(doc)
    except Exception as exc:
        # Log mas não propaga — falha de auditoria não deve quebrar o fluxo de negócio
        logger.error(
            "audit_log: falha ao registrar evento event_type=%s user=%s: %s",
            event_type, user_id, exc,
        )


# ─── Índices da coleção audit_log ─────────────────────────────────────────────


async def create_audit_indexes(db: Any) -> None:
    """
    Cria índices na coleção audit_log.

    Deve ser chamado no startup da aplicação (via lifespan ou on_event).
    Retenção mínima: 2 anos (requisito legal para transações financeiras).
    NÃO criar TTL — deleção apenas mediante processo de compliance.
    """
    coll = db[_AUDIT_COLLECTION]
    try:
        await coll.create_index([("user_id", 1), ("timestamp", -1)], background=True)
        await coll.create_index([("event_type", 1), ("timestamp", -1)], background=True)
        await coll.create_index([("bot_instance_id", 1), ("timestamp", -1)], background=True)
        if hasattr(coll, "create_index"):
            # índice opcional por trade_id para rastreio cruzado
            await coll.create_index(
                [("trade_id", 1)],
                sparse=True,
                background=True,
            )
        logger.info("audit_log: índices criados com sucesso")
    except Exception as exc:
        logger.warning("audit_log: erro ao criar índices: %s", exc)
