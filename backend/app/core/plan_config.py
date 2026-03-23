"""
Plan Config — Fonte ÚNICA de verdade para nomes e limites de planos.

Todos os módulos devem importar daqui em vez de definir seus próprios mapeamentos.

Uso:
    from app.core.plan_config import PLAN_CONFIG, get_plan_config, resolve_plan_key
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# ── Mapeamento canônico de planos ─────────────────────────────────────────
# Unifica os nomes usados em plan_limits.py, gamification/service.py e
# gamification/model.py numa SÓ estrutura.

PLAN_CONFIG: Dict[str, Dict[str, Any]] = {
    "free": {
        "display": "FREE",
        "bots": 0,
        "pairs_per_bot": 1,
        "timeframes": ["1h"],
        "api_calls_per_min": 10,
        "max_robots_arena": 0,
        "monthly_price": 0.0,
        "initial_points": 0,
        "monthly_bonus_points": 0,
        "initial_xp": 0,
        "xp_boost_multiplier": 1.0,
    },
    "starter": {
        "display": "START",
        "bots": 1,
        "pairs_per_bot": 1,
        "timeframes": ["15m", "1h"],
        "api_calls_per_min": 30,
        "max_robots_arena": 3,
        "monthly_price": 9.99,
        "initial_points": 500,
        "monthly_bonus_points": 500,
        "initial_xp": 50,
        "xp_boost_multiplier": 1.0,
    },
    "pro": {
        "display": "PRO+",
        "bots": 3,
        "pairs_per_bot": 2,
        "timeframes": ["5m", "15m", "1h", "4h"],
        "api_calls_per_min": 60,
        "max_robots_arena": 5,
        "monthly_price": 11.99,
        "initial_points": 1500,
        "monthly_bonus_points": 1500,
        "initial_xp": 150,
        "xp_boost_multiplier": 1.2,
        "is_most_popular": True,
    },
    "pro_plus": {
        "display": "PRO+",
        "bots": 5,
        "pairs_per_bot": 3,
        "timeframes": ["1m", "5m", "15m", "1h", "4h"],
        "api_calls_per_min": 120,
        "max_robots_arena": 8,
        "monthly_price": 14.99,
        "initial_points": 2000,
        "monthly_bonus_points": 2000,
        "initial_xp": 200,
        "xp_boost_multiplier": 1.3,
    },
    "premium": {
        "display": "QUANT",
        "bots": 10,
        "pairs_per_bot": 5,
        "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
        "api_calls_per_min": 300,
        "max_robots_arena": 15,
        "monthly_price": 17.99,
        "initial_points": 3000,
        "monthly_bonus_points": 3000,
        "initial_xp": 300,
        "xp_boost_multiplier": 1.5,
    },
    "enterprise": {
        "display": "BLACK",
        "bots": 20,
        "pairs_per_bot": 10,
        "timeframes": ["all"],
        "api_calls_per_min": 1000,
        "max_robots_arena": 999,
        "monthly_price": 39.99,
        "initial_points": 10000,
        "monthly_bonus_points": 10000,
        "initial_xp": 1000,
        "xp_boost_multiplier": 2.0,
    },
}

# ── Aliases: nomes antigos → nomes canônicos ──────────────────────────────
# Permite que valores salvos com nomes antigos ('start', 'quant', 'black')
# sejam resolvidos sem quebrar.
PLAN_ALIASES: Dict[str, str] = {
    "start": "starter",
    "quant": "premium",
    "black": "enterprise",
}

# Default when plan is None or unknown
DEFAULT_PLAN = "free"


# ── Helper functions ──────────────────────────────────────────────────────

def resolve_plan_key(plan: Optional[str]) -> str:
    """
    Resolve um nome de plano (incl. aliases antigos) para a chave canônica.

    Exemplos:
        resolve_plan_key("quant")  → "premium"
        resolve_plan_key("black")  → "enterprise"
        resolve_plan_key("pro")    → "pro"
        resolve_plan_key(None)     → "free"
    """
    if not plan:
        return DEFAULT_PLAN
    plan_lower = plan.lower().strip()
    # Tenta alias primeiro, depois procura direto
    resolved = PLAN_ALIASES.get(plan_lower, plan_lower)
    if resolved in PLAN_CONFIG:
        return resolved
    logger.warning(f"⚠️ Plano desconhecido: '{plan}' (resolvido como '{resolved}') → usando '{DEFAULT_PLAN}'")
    return DEFAULT_PLAN


def get_plan_config(plan: Optional[str]) -> Dict[str, Any]:
    """Returns the full config dict for the given plan (resolving aliases)."""
    key = resolve_plan_key(plan)
    return PLAN_CONFIG[key]


def get_plan_display(plan: Optional[str]) -> str:
    """Display name for a plan, e.g. 'PRO+', 'BLACK'."""
    return get_plan_config(plan)["display"]


def get_max_robots_arena(plan: Optional[str]) -> int:
    """Max robots a user can unlock in the Arena for this plan."""
    return get_plan_config(plan)["max_robots_arena"]


def get_max_bots(plan: Optional[str]) -> int:
    """Max simultaneous active bots for this plan."""
    return get_plan_config(plan)["bots"]


def get_allowed_timeframes(plan: Optional[str]) -> List[str]:
    """Permitted timeframes list."""
    return get_plan_config(plan)["timeframes"]


def is_timeframe_allowed(plan: Optional[str], timeframe: str) -> bool:
    allowed = get_allowed_timeframes(plan)
    return "all" in allowed or timeframe in allowed


def get_api_rate_limit(plan: Optional[str]) -> int:
    return get_plan_config(plan)["api_calls_per_min"]
