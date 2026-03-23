"""
License Middleware - Sistema de Prote??o de Licen?a

Este m?dulo implementa:
1. Verifica??o de licen?a ativa
2. Dependency Injection para rotas protegidas
3. Gest?o de planos (Free, Pro, Enterprise)

Campos no user document:
- license_type: "free" | "pro" | "enterprise"
- license_expires_at: datetime | None (None = vital?cio)
- license_max_bots: int
- license_features: list[str]

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from fastapi import HTTPException, status, Depends
from bson import ObjectId

from app.core.database import get_db
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)


# ============== LICENSE TYPES ==============

class LicenseType(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ============== LICENSE FEATURES ==============

LICENSE_FEATURES = {
    LicenseType.FREE: {
        "max_bots": 1,
        "max_trades_per_day": 10,
        "strategies": ["grid"],
        "exchanges": ["binance"],
        "features": [
            "basic_dashboard",
            "manual_trading",
            "basic_analytics"
        ],
        "price_monthly": 0,
        "price_yearly": 0,
        "name": "Free",
        "description": "Comece gratuitamente"
    },
    LicenseType.PRO: {
        "max_bots": 10,
        "max_trades_per_day": 500,
        "strategies": ["grid", "dca", "rsi", "macd"],
        "exchanges": ["binance", "kucoin", "bybit"],
        "features": [
            "basic_dashboard",
            "manual_trading",
            "basic_analytics",
            "advanced_analytics",
            "telegram_alerts",
            "discord_alerts",
            "api_access",
            "priority_support",
            "custom_strategies"
        ],
        "price_monthly": 49.90,
        "price_yearly": 399.90,
        "name": "Pro",
        "description": "Para traders s?rios"
    },
    LicenseType.ENTERPRISE: {
        "max_bots": 100,
        "max_trades_per_day": 10000,
        "strategies": ["grid", "dca", "rsi", "macd", "custom"],
        "exchanges": ["binance", "kucoin", "bybit", "okx", "kraken"],
        "features": [
            "basic_dashboard",
            "manual_trading",
            "basic_analytics",
            "advanced_analytics",
            "telegram_alerts",
            "discord_alerts",
            "api_access",
            "priority_support",
            "custom_strategies",
            "white_label",
            "dedicated_support",
            "custom_integration",
            "sla_99_9"
        ],
        "price_monthly": 199.90,
        "price_yearly": 1599.90,
        "name": "Enterprise",
        "description": "Para equipes e fundos"
    }
}


# ============== LICENSE HELPER FUNCTIONS ==============

def get_user_license_info(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai informa??es de licen?a do documento do usu?rio.
    
    Returns:
        Dict com license_type, expires_at, is_active, features
    """
    license_type = user.get("license_type", LicenseType.FREE.value)
    expires_at = user.get("license_expires_at")
    
    # Verificar se a licen?a expirou
    is_expired = False
    if expires_at and isinstance(expires_at, datetime):
        is_expired = expires_at < datetime.utcnow()
    
    # Se expirou, usar features do plano Free
    if is_expired:
        license_type = LicenseType.FREE.value
    
    features = LICENSE_FEATURES.get(
        LicenseType(license_type),
        LICENSE_FEATURES[LicenseType.FREE]
    )
    
    return {
        "license_type": license_type,
        "license_expires_at": expires_at,
        "is_active": not is_expired,
        "is_expired": is_expired,
        "features": features,
        "max_bots": features["max_bots"],
        "max_trades_per_day": features["max_trades_per_day"],
        "allowed_strategies": features["strategies"],
        "allowed_exchanges": features["exchanges"],
        "allowed_features": features["features"]
    }


def check_feature_access(user: Dict[str, Any], feature: str) -> bool:
    """Verifica se usu?rio tem acesso a uma feature espec?fica."""
    license_info = get_user_license_info(user)
    return feature in license_info["allowed_features"]


def check_strategy_access(user: Dict[str, Any], strategy: str) -> bool:
    """Verifica se usu?rio pode usar uma estrat?gia espec?fica."""
    license_info = get_user_license_info(user)
    return strategy.lower() in license_info["allowed_strategies"]


def check_exchange_access(user: Dict[str, Any], exchange: str) -> bool:
    """Verifica se usu?rio pode usar uma exchange espec?fica."""
    license_info = get_user_license_info(user)
    return exchange.lower() in license_info["allowed_exchanges"]


async def check_bot_limit(user: Dict[str, Any]) -> bool:
    """Verifica se usu?rio pode criar mais bots."""
    license_info = get_user_license_info(user)
    max_bots = license_info["max_bots"]
    
    db = get_db()
    bots_col = db["bots"]
    
    # Contar bots ativos do usu?rio
    user_id = str(user["_id"])
    active_bots = await bots_col.count_documents({
        "user_id": user_id,
        "status": {"$ne": "deleted"}
    })
    
    return active_bots < max_bots


# ============== DEPENDENCY INJECTIONS ==============

async def check_active_license(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency que verifica se o usu?rio tem licen?a ativa.
    
    Retorna o usu?rio com informa??es de licen?a adicionadas.
    Levanta HTTPException 403 se licen?a expirada.
    
    Usage:
        @router.post("/bots/start")
        async def start_bot(user: dict = Depends(check_active_license)):
            ...
    """
    license_info = get_user_license_info(current_user)
    
    if license_info["is_expired"]:
        logger.warning(f"User {current_user.get('email')} has expired license")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "license_expired",
                "message": "Sua licen?a expirou. Renove para continuar usando.",
                "expired_at": license_info["license_expires_at"].isoformat() if license_info["license_expires_at"] else None,
                "upgrade_url": "/planos"
            }
        )
    
    # Adicionar license_info ao user para uso na rota
    current_user["license_info"] = license_info
    return current_user


async def check_pro_license(
    current_user: dict = Depends(check_active_license)
) -> dict:
    """
    Dependency que verifica se o usu?rio tem licen?a Pro ou Enterprise.
    
    Usage:
        @router.post("/bots/advanced")
        async def advanced_feature(user: dict = Depends(check_pro_license)):
            ...
    """
    license_type = current_user.get("license_info", {}).get("license_type", "free")
    
    if license_type not in [LicenseType.PRO.value, LicenseType.ENTERPRISE.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "pro_required",
                "message": "Esta funcionalidade requer plano Pro ou Enterprise.",
                "current_plan": license_type,
                "upgrade_url": "/planos"
            }
        )
    
    return current_user


async def check_enterprise_license(
    current_user: dict = Depends(check_active_license)
) -> dict:
    """
    Dependency que verifica se o usu?rio tem licen?a Enterprise.
    """
    license_type = current_user.get("license_info", {}).get("license_type", "free")
    
    if license_type != LicenseType.ENTERPRISE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "enterprise_required",
                "message": "Esta funcionalidade requer plano Enterprise.",
                "current_plan": license_type,
                "upgrade_url": "/planos"
            }
        )
    
    return current_user


def require_feature(feature: str):
    """
    Factory para criar dependency que verifica uma feature espec?fica.
    
    Usage:
        @router.post("/webhooks/telegram")
        async def setup_telegram(
            user: dict = Depends(require_feature("telegram_alerts"))
        ):
            ...
    """
    async def _check_feature(
        current_user: dict = Depends(check_active_license)
    ) -> dict:
        if not check_feature_access(current_user, feature):
            license_info = current_user.get("license_info", {})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "message": f"A funcionalidade '{feature}' n?o est? dispon?vel no seu plano.",
                    "current_plan": license_info.get("license_type", "free"),
                    "upgrade_url": "/planos"
                }
            )
        return current_user
    
    return _check_feature


def require_strategy(strategy: str):
    """
    Factory para criar dependency que verifica acesso a uma estrat?gia.
    
    Usage:
        @router.post("/bots/create-macd")
        async def create_macd_bot(
            user: dict = Depends(require_strategy("macd"))
        ):
            ...
    """
    async def _check_strategy(
        current_user: dict = Depends(check_active_license)
    ) -> dict:
        if not check_strategy_access(current_user, strategy):
            license_info = current_user.get("license_info", {})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "strategy_not_available",
                    "message": f"A estrat?gia '{strategy}' n?o est? dispon?vel no seu plano.",
                    "current_plan": license_info.get("license_type", "free"),
                    "available_strategies": license_info.get("allowed_strategies", ["grid"]),
                    "upgrade_url": "/planos"
                }
            )
        return current_user
    
    return _check_strategy


async def check_can_create_bot(
    current_user: dict = Depends(check_active_license)
) -> dict:
    """
    Verifica se o usu?rio pode criar mais bots (n?o atingiu o limite).
    """
    can_create = await check_bot_limit(current_user)
    
    if not can_create:
        license_info = current_user.get("license_info", {})
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "bot_limit_reached",
                "message": f"Voc? atingiu o limite de {license_info['max_bots']} bot(s) do seu plano.",
                "current_plan": license_info.get("license_type", "free"),
                "max_bots": license_info.get("max_bots", 1),
                "upgrade_url": "/planos"
            }
        )
    
    return current_user


# ============== LICENSE MANAGEMENT ==============

async def update_user_license(
    user_id: str,
    license_type: LicenseType,
    expires_at: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Atualiza a licen?a de um usu?rio.
    
    Args:
        user_id: ID do usu?rio
        license_type: Tipo de licen?a (free, pro, enterprise)
        expires_at: Data de expira??o (None = vital?cio)
        
    Returns:
        Documento do usu?rio atualizado
    """
    db = get_db()
    users_col = db["users"]
    
    update_data = {
        "license_type": license_type.value,
        "license_expires_at": expires_at,
        "license_updated_at": datetime.utcnow()
    }
    
    result = await users_col.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": update_data},
        return_document=True
    )
    
    if result:
        logger.info(f"Updated license for user {user_id}: {license_type.value}")
    
    return result


async def get_all_plans() -> List[Dict[str, Any]]:
    """
    Retorna todos os planos dispon?veis com suas features.
    """
    plans = []
    for license_type, features in LICENSE_FEATURES.items():
        plans.append({
            "type": license_type.value,
            "name": features["name"],
            "description": features["description"],
            "price_monthly": features["price_monthly"],
            "price_yearly": features["price_yearly"],
            "max_bots": features["max_bots"],
            "max_trades_per_day": features["max_trades_per_day"],
            "strategies": features["strategies"],
            "exchanges": features["exchanges"],
            "features": features["features"]
        })
    return plans
