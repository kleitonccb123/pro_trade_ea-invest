"""
Controle de features por plano — DOC-07

Define as capacidades de cada plano e expõe a dependência FastAPI
`require_feature()` para proteger endpoints de forma granular.

Planos suportados (em ordem crescente):
  free → basic → pro → enterprise

Alias legado: "premium" é tratado como "pro" para compatibilidade
com registros antigos no banco.

Uso nos routers::

    from app.licensing.features import require_feature

    @router.post("/bots")
    async def create_bot(
        current_user=Depends(get_current_user),
        _=Depends(require_feature("max_bots", min_value=1)),
    ):
        ...
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user

# ─── Hierarquia de planos ────────────────────────────────────────────────────

PLAN_ORDER: Dict[str, int] = {
    "free":       0,
    "basic":      1,
    "pro":        2,
    "premium":    2,   # legado — equivale a pro
    "enterprise": 3,
}

# ─── Limites e capacidades por plano ─────────────────────────────────────────

PLAN_FEATURES: Dict[str, Dict[str, Any]] = {
    "free": {
        "max_bots":          0,
        "max_symbols":       0,
        "backtesting":       False,
        "marketplace":       "none",
        "support":           "none",
        "tp_sl":             False,
        "analytics":         False,
        "multi_exchange":    False,
        "api_access":        False,
    },
    "basic": {
        "max_bots":          1,
        "max_symbols":       3,
        "backtesting":       False,
        "marketplace":       "read",
        "support":           "community",
        "tp_sl":             False,
        "analytics":         False,
        "multi_exchange":    False,
        "api_access":        False,
    },
    "pro": {
        "max_bots":          5,
        "max_symbols":       20,
        "backtesting":       True,
        "marketplace":       "read+write",
        "support":           "email",
        "tp_sl":             True,
        "analytics":         True,
        "multi_exchange":    False,
        "api_access":        False,
    },
    "enterprise": {
        "max_bots":          -1,    # ilimitado
        "max_symbols":       -1,    # ilimitado
        "backtesting":       True,
        "marketplace":       "read+write+sell",
        "support":           "dedicated",
        "tp_sl":             True,
        "analytics":         True,
        "multi_exchange":    True,
        "api_access":        True,
    },
}

# "premium" é alias legado de "pro"
PLAN_FEATURES["premium"] = PLAN_FEATURES["pro"]
# "starter" é alias legado de "free"
PLAN_FEATURES["starter"] = PLAN_FEATURES["free"]


def features_for_plan(plan: str) -> Dict[str, Any]:
    """Retorna o dict de features para o plano informado. Fallback para 'free'."""
    return PLAN_FEATURES.get(plan.lower(), PLAN_FEATURES["free"])


def plan_level(plan: str) -> int:
    """Retorna o nível numérico do plano (maior = mais recursos)."""
    return PLAN_ORDER.get(plan.lower(), 0)


def to_bool_features(plan: str) -> Dict[str, bool]:
    """
    Converte features do plano para o formato Dict[str, bool] compatível com
    o LicenseResponse.features legado.

    Valores numéricos > 0 ou -1 → True; False → False; strings → True se não 'none'.
    """
    raw = features_for_plan(plan)
    result: Dict[str, bool] = {}
    for key, val in raw.items():
        if isinstance(val, bool):
            result[key] = val
        elif isinstance(val, int):
            result[key] = val != 0   # -1 (ilimitado) e N > 0 → True
        elif isinstance(val, str):
            result[key] = val.lower() not in ("none", "false", "0", "")
        else:
            result[key] = bool(val)
    return result


# ─── Dependência FastAPI ──────────────────────────────────────────────────────


def require_plan(min_plan: str):
    """
    Dependência FastAPI: garante que o usuário tem nível mínimo de plano.

    Uso::

        @router.post("/analytics")
        async def analytics(_=Depends(require_plan("pro"))):
            ...
    """
    required_level = plan_level(min_plan)

    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        plan = str(current_user.get("plan", "free")).lower()
        if bool(current_user.get("is_superuser")):
            return current_user
        if plan_level(plan) < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Recurso não disponível no seu plano",
                    "current_plan": plan,
                    "required_plan": min_plan,
                    "upgrade": "/planos",
                },
            )
        return current_user

    return _check


def require_feature(feature: str, min_value: Any = True):
    """
    Dependência FastAPI: garante que o plano do usuário inclui uma feature.

    Para features numéricas (max_bots), ``min_value`` é o número mínimo aceito::

        @router.post("/bots")
        async def create_bot(_=Depends(require_feature("max_bots", min_value=1))):
            ...

    Para features booleanas::

        @router.get("/backtesting")
        async def backtest(_=Depends(require_feature("backtesting"))):
            ...
    """
    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if bool(current_user.get("is_superuser")):
            return current_user

        plan = str(current_user.get("plan", "free")).lower()
        feats = features_for_plan(plan)
        val = feats.get(feature)

        # Feature ausente no plano
        if val is None:
            _deny(feature, plan)

        # Boolean feature
        if isinstance(val, bool):
            if not val:
                _deny(feature, plan)

        # Numeric feature: -1 = ilimitado, 0 = bloqueado
        elif isinstance(val, int):
            if val == 0:
                _deny(feature, plan)
            if val != -1 and isinstance(min_value, int) and val < min_value:
                _deny(feature, plan)

        # String feature (ex: "none", "read", "read+write")
        elif isinstance(val, str):
            if val.lower() in ("none", "false", "0", ""):
                _deny(feature, plan)
            if isinstance(min_value, str) and min_value not in val:
                _deny(feature, plan)

        return current_user

    return _check


def _deny(feature: str, plan: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "Recurso não disponível no seu plano",
            "feature": feature,
            "current_plan": plan,
            "upgrade": "/planos",
        },
    )
