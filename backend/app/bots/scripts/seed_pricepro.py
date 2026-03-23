"""
seed_pricepro.py — Registra o PRICEPRO_MONEY-EA no MongoDB

Execução
--------
    # A partir da raiz do backend (com .venv ativo):
    python -m app.bots.scripts.seed_pricepro --user-id <USER_ID>

    # Modo dry-run (imprime o documento sem inserir):
    python -m app.bots.scripts.seed_pricepro --user-id <USER_ID> --dry-run

O script é idempotente: se um documento com o mesmo user_id + strategy_id
já existir, ele é atualizado (upsert), nunca duplicado.

Campos inseridos
----------------
Todos os campos obrigatórios definidos em DOC-STRAT-01 seção 1.4.
O documento resultante é compatível com _StateStore.bot_exists() e
mark_bot_running() / mark_bot_stopped() do StrategyManager.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from datetime import datetime, timezone
from pprint import pprint

# Garante que o backend seja importável ao rodar como script
ROOT = pathlib.Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import get_db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

# ─── Documento canônico do PRICEPRO_MONEY-EA ─────────────────────────────────
PRICEPRO_DOCUMENT_TEMPLATE = {
    # Identificação
    "strategy_id":    "pricepro_money_v1",
    "display_name":   "PRICEPRO MONEY",
    "name":           "PRICEPRO MONEY",
    "description":    "Expert Advisor PRICEPRO MONEY adaptado ao SaaS Strategy Manager. "
                      "Controle remoto via control.json, heartbeat via state.json.",

    # Controle pelo Strategy Manager
    "magic_number":   20240001,
    "is_running":     False,
    "is_active_slot": False,
    "status":         "stopped",        # stopped | running | error | shutdown

    # Estado de execução (preenchido durante operação)
    "runtime_state":  None,             # snapshot do último state.json recebido

    # Timestamps
    "last_started":   None,
    "last_stopped":   None,
    "last_heartbeat": None,

    # Métricas de performance
    "profit":         0.0,
    "trades":         0,
    "win_rate":       0.0,
    "max_drawdown":   0.0,
    "sharpe_ratio":   0.0,

    # Configuração padrão
    "exchange":       "metatrader5",
    "pair":           "XAUUSD",         # ativo principal do PRICEPRO
    "config": {
        "timeframe":      "M15",
        "risk_percent":   1.0,
        "magic_number":   20240001,
        "control_path":   "C:/MT5_Control/{user_id}/pricepro_money_v1/control.json",
        "state_path":     "C:/MT5_Control/{user_id}/pricepro_money_v1/state.json",
    },

    # SaaS integration flags
    "saas_module":         "pricepro_money_v1",
    "saas_compatible":     True,
    "safe_shutdown_timeout_s": 120,
    "handshake_timeout_s":     30,
    "min_switch_interval_s":   60,

    # Créditos e slots
    "is_active_slot":           False,
    "activation_credits_used":  0,
    "swap_count":               0,
    "swap_history":             [],
}


def build_document(user_id: str) -> dict:
    """Constrói o documento final para o user_id informado."""
    now = datetime.now(timezone.utc)
    doc = dict(PRICEPRO_DOCUMENT_TEMPLATE)
    doc["user_id"]    = user_id
    doc["created_at"] = now
    doc["updated_at"] = now

    # Substitui {user_id} nos caminhos de config
    doc["config"] = {
        k: v.format(user_id=user_id) if isinstance(v, str) else v
        for k, v in doc["config"].items()
    }
    return doc


def run(user_id: str, dry_run: bool = False) -> None:
    db  = get_db()
    col = db["bots"]

    doc = build_document(user_id)

    if dry_run:
        print("\n── Documento que seria inserido (dry-run) ──────────────────")
        pprint(doc)
        print("────────────────────────────────────────────────────────────\n")
        return

    filter_q = {"user_id": user_id, "strategy_id": "pricepro_money_v1"}
    result   = col.update_one(
        filter_q,
        {"$setOnInsert": {"created_at": doc["created_at"]},
         "$set":         {k: v for k, v in doc.items() if k != "created_at"}},
        upsert=True,
    )

    if result.upserted_id:
        logger.info(
            "✅ PRICEPRO_MONEY-EA registrado com sucesso. "
            "_id=%s  user_id=%s", result.upserted_id, user_id
        )
    elif result.modified_count:
        logger.info(
            "♻️  Documento existente atualizado. user_id=%s", user_id
        )
    else:
        logger.info(
            "ℹ️  Documento já existe e não precisou de alterações. user_id=%s", user_id
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Registra o PRICEPRO_MONEY-EA no MongoDB do SaaS."
    )
    parser.add_argument(
        "--user-id", required=True,
        help="ObjectId ou string do user_id no MongoDB"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Imprime o documento sem inserir no banco"
    )
    args = parser.parse_args()
    run(user_id=args.user_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
