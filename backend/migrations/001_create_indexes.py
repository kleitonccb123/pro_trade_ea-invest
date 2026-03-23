#!/usr/bin/env python3
"""
DOC-10 §8.8 — MongoDB Migration Script
Cria todos os índices institucionais necessários para produção.

Uso:
    python -m backend.migrations.001_create_indexes
    # ou
    cd backend && python migrations/001_create_indexes.py

Idempotente: pode ser executado múltiplas vezes sem causar erros.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime

# Ajusta PYTHONPATH para importar app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MIGRATION_ID = "001_create_indexes"
MIGRATION_DESC = "Índices institucionais completos — DOC-01 a DOC-10"


async def run_migration(db) -> None:
    """Aplica todos os índices de forma idempotente."""

    created = 0

    async def idx(collection: str, keys, **kwargs) -> None:
        nonlocal created
        try:
            if isinstance(keys, str):
                await db[collection].create_index(keys, **kwargs)
            else:
                await db[collection].create_index(keys, **kwargs)
            created += 1
            logger.info("  ✓  %s  %s", collection, keys)
        except Exception as exc:
            if "already exists" in str(exc).lower() or "IndexKeySpecsConflict" in str(exc):
                logger.debug("  ~  %s  %s  (já existe)", collection, keys)
            else:
                logger.warning("  !  %s  %s  → %s", collection, keys, exc)

    logger.info("=== Iniciando migration: %s ===", MIGRATION_ID)
    logger.info(MIGRATION_DESC)

    # ── DOC-01: Execução de Ordens ─────────────────────────────────────────────
    logger.info("--- DOC-01: orders / pending_orders ---")
    await idx("orders", "client_oid", unique=True)
    await idx("orders", [("user_id", 1), ("created_at", -1)])
    await idx("orders", [("bot_id", 1), ("status", 1)])
    await idx("orders", "status")
    await idx("pending_orders", "client_oid", unique=True)
    await idx("pending_orders", [("created_at", 1)], expireAfterSeconds=3600)

    # ── DOC-02: TP/SL ─────────────────────────────────────────────────────────
    logger.info("--- DOC-02: tpsl_orders ---")
    await idx("tpsl_orders", [("position_id", 1), ("order_type", 1)])
    await idx("tpsl_orders", [("user_id", 1), ("status", 1)])
    await idx("tpsl_orders", "exchange_order_id")

    # ── DOC-03: WebSocket / Heartbeat ─────────────────────────────────────────
    logger.info("--- DOC-03: ws_sessions ---")
    await idx("ws_sessions", "user_id")
    await idx("ws_sessions", [("last_ping_at", 1)], expireAfterSeconds=120)

    # ── DOC-04: Locks / Streams ───────────────────────────────────────────────
    logger.info("--- DOC-04: signal_events ---")
    await idx("signal_events", "signal_id", unique=True)
    await idx("signal_events", [("created_at", 1)], expireAfterSeconds=86400)

    # ── DOC-05: Risk Management ───────────────────────────────────────────────
    logger.info("--- DOC-05: risk_state / risk_audit_log ---")
    await idx("risk_state", "user_id", unique=True)
    await idx("risk_audit_log", [("user_id", 1), ("timestamp", -1)])
    await idx("risk_audit_log", "entry_hash", unique=True)
    await idx("bot_kill_flags", "bot_id", unique=True)

    # ── DOC-06: Monitoramento / Health ────────────────────────────────────────
    logger.info("--- DOC-06: health_snapshots / audit_logs ---")
    await idx("health_snapshots", [("created_at", -1)])
    await idx("health_snapshots", [("created_at", 1)], expireAfterSeconds=604800)  # 7 dias
    await idx("audit_logs", [("created_at", -1)])
    await idx("audit_logs", [("event_type", 1), ("created_at", -1)])

    # ── DOC-07: Licenciamento ─────────────────────────────────────────────────
    logger.info("--- DOC-07: licenses / webhook_events / license_audit ---")
    await idx("licenses", "user_id", unique=True)
    await idx("licenses", "subscription_id")
    await idx("licenses", [("expires_at", 1)])
    await idx("webhook_events", "sale_id", unique=True)
    await idx("webhook_events", [("processed_at", 1)], expireAfterSeconds=7776000)  # 90 dias
    await idx("license_audit", [("user_id", 1), ("timestamp", -1)])

    # ── DOC-08: Marketplace de Estratégias ────────────────────────────────────
    logger.info("--- DOC-08: strategies / subscriptions / backtest_results ---")
    await idx("strategies", "strategy_id", unique=True)
    await idx("strategies", "creator_id")
    await idx("strategies", "category")
    await idx("strategies", [("metrics.sharpe_ratio", -1)])
    await idx("strategies", [("is_published", 1), ("metrics.sharpe_ratio", -1)])
    await idx("strategy_subscriptions", [("user_id", 1), ("strategy_id", 1)])
    await idx("strategy_subscriptions", [("user_id", 1), ("is_active", 1)])
    await idx("strategy_bot_instances", [("user_id", 1), ("strategy_id", 1)])
    await idx("strategy_bot_instances", [("is_active", 1)])
    await idx("strategy_trades", "instance_id")
    await idx("strategy_trades", [("user_id", 1), ("entry_at", -1)])
    await idx("strategy_trades", "strategy_id")
    await idx("backtest_results", "backtest_id", unique=True)
    await idx("backtest_results", "strategy_id")
    await idx("revenue_events", "subscription_id")
    await idx("revenue_events", [("creator_id", 1), ("processed_at", -1)])
    await idx("strategy_creator_wallets", "user_id", unique=True)

    # ── Usuários / Auth ────────────────────────────────────────────────────────
    logger.info("--- Core: users / sessions ---")
    await idx("users", "email", unique=True)
    await idx("users", "username", sparse=True)
    await idx("sessions", "user_id")
    await idx("sessions", [("created_at", 1)], expireAfterSeconds=604800)

    # ── Afiliados ──────────────────────────────────────────────────────────────
    logger.info("--- Affiliates ---")
    await idx("affiliate_wallets", "user_id", unique=True)
    await idx("affiliate_transactions", [("user_id", 1), ("created_at", -1)])
    await idx("affiliate_withdraw_requests", [("user_id", 1), ("status", 1)])

    logger.info("=== Migration concluída: %d índices criados/verificados ===", created)

    # Registra migration no histórico
    await db["_migrations"].update_one(
        {"migration_id": MIGRATION_ID},
        {
            "$set": {
                "migration_id": MIGRATION_ID,
                "description": MIGRATION_DESC,
                "applied_at": datetime.utcnow(),
                "indexes_created": created,
                "status": "applied",
            }
        },
        upsert=True,
    )
    logger.info("Migration registrada em _migrations.%s", MIGRATION_ID)


async def main() -> None:
    mongo_url = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DATABASE_NAME", "trading_app_db")

    logger.info("Conectando a %s / %s", mongo_url.split("@")[-1], db_name)
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10_000)
    db = client[db_name]

    try:
        # Verifica conectividade
        await client.admin.command("ping")
        logger.info("MongoDB: conexão estabelecida")
        await run_migration(db)
    except Exception as exc:
        logger.error("Falha na migration: %s", exc)
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
