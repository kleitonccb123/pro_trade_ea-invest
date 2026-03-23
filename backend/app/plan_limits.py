"""
Plan Limits — Quotas por plano de assinatura.

Cada plano define limites de:
- bots: número máximo de bots simultâneos ativos
- pairs_per_bot: pares de trading por bot
- timeframes: timeframes disponíveis
- api_calls_per_min: rate limit de requisições à exchange

Uso:
    from app.plan_limits import PLAN_LIMITS, get_plan_limits, check_bot_quota

"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ── Plan definitions ──────────────────────────────────────────────────────────

PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
    "free": {
        "bots": 0,
        "pairs_per_bot": 1,
        "timeframes": ["1h"],
        "api_calls_per_min": 10,
    },
    "start": {
        "bots": 1,
        "pairs_per_bot": 1,
        "timeframes": ["15m", "1h"],
        "api_calls_per_min": 30,
    },
    "pro": {
        "bots": 3,
        "pairs_per_bot": 2,
        "timeframes": ["5m", "15m", "1h", "4h"],
        "api_calls_per_min": 60,
    },
    "pro_plus": {
        "bots": 5,
        "pairs_per_bot": 3,
        "timeframes": ["1m", "5m", "15m", "1h", "4h"],
        "api_calls_per_min": 120,
    },
    "quant": {
        "bots": 10,
        "pairs_per_bot": 5,
        "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
        "api_calls_per_min": 300,
    },
    "black": {
        "bots": 20,
        "pairs_per_bot": 10,
        "timeframes": ["all"],
        "api_calls_per_min": 1000,
    },
}

# Default plan assigned when no plan is stored for the user
DEFAULT_PLAN = "free"

# ── Helper functions ──────────────────────────────────────────────────────────


def get_plan_limits(plan: Optional[str]) -> Dict[str, Any]:
    """
    Returns the limits dict for the given plan name.

    Falls back to ``DEFAULT_PLAN`` when plan is None or unknown so the
    system is always safe-by-default (deny rather than allow unlimited).
    """
    return PLAN_LIMITS.get(plan or DEFAULT_PLAN, PLAN_LIMITS[DEFAULT_PLAN])


def get_max_bots(plan: Optional[str]) -> int:
    """Maximum simultaneous active bots allowed for a plan."""
    return get_plan_limits(plan)["bots"]


def get_allowed_timeframes(plan: Optional[str]) -> List[str]:
    """Returns the list of permitted timeframes for a plan."""
    return get_plan_limits(plan)["timeframes"]


def is_timeframe_allowed(plan: Optional[str], timeframe: str) -> bool:
    """True if ``timeframe`` is permitted on the given plan."""
    allowed = get_allowed_timeframes(plan)
    return "all" in allowed or timeframe in allowed


def get_api_rate_limit(plan: Optional[str]) -> int:
    """API call rate cap (requests per minute) for the plan."""
    return get_plan_limits(plan)["api_calls_per_min"]


# ── Async quota enforcement ───────────────────────────────────────────────────


async def check_bot_quota(db, user_id: str, plan: Optional[str]) -> None:
    """
    Raises ``ValueError`` if the user already has the maximum number of
    running bots permitted by their plan.

    Args:
        db: Motor AsyncIOMotorDatabase instance.
        user_id: String user id.
        plan: Subscription plan slug, e.g. ``"pro"``.

    Raises:
        ValueError: When the active bot count is at or above the plan limit.
    """
    max_bots = get_max_bots(plan)

    if max_bots == 0:
        raise ValueError(
            f"O plano '{plan or DEFAULT_PLAN}' não permite bots ativos. "
            "Faça upgrade para habilitar robôs de trading."
        )

    active_count = await db["user_bot_instances"].count_documents(
        {"user_id": str(user_id), "status": "running"}
    )

    if active_count >= max_bots:
        raise ValueError(
            f"Limite de bots atingido: o plano '{plan or DEFAULT_PLAN}' permite "
            f"no máximo {max_bots} bot(s) simultâneo(s). "
            f"Você já tem {active_count} ativo(s). Pare um bot ou faça upgrade."
        )


async def check_timeframe_quota(plan: Optional[str], timeframe: str) -> None:
    """
    Raises ``ValueError`` if ``timeframe`` is not allowed on the plan.
    """
    if not is_timeframe_allowed(plan, timeframe):
        allowed = get_allowed_timeframes(plan)
        raise ValueError(
            f"O timeframe '{timeframe}' não está disponível no plano "
            f"'{plan or DEFAULT_PLAN}'. Timeframes permitidos: {', '.join(allowed)}."
        )
