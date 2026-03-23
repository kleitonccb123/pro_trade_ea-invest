"""
License Middleware - Verifica licen?as de usu?rio antes de opera??es cr?ticas

Este m?dulo implementa:
1. Verifica??o de licen?a ativa antes de bot.start()
2. Verifica??o de limites de rob?s por plano
3. Verifica??o de recursos premium por tipo de licen?a

Planos:
- free: 0 rob?s (sem licen?a)
- starter: 3 rob?s
- pro: 5 rob?s
- quant: 10 rob?s
- black: 20 rob?s

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
from bson import ObjectId

from fastapi import HTTPException, status
from app.core.database import get_db

logger = logging.getLogger(__name__)


# Defini??o dos planos e limites
LICENSE_PLANS = {
    "free": {
        "max_bots": 0,
        "max_strategies": 0,
        "features": [],
        "price": 0,
    },
    "starter": {
        "max_bots": 3,
        "max_strategies": 3,
        "features": ["telegram_alerts", "email_support", "30_day_history"],
        "price": 49.99,
    },
    "pro": {
        "max_bots": 5,
        "max_strategies": 5,
        "features": [
            "telegram_alerts", "priority_support", "90_day_history",
            "copy_trading", "multi_exchange", "push_notifications"
        ],
        "price": 55.99,
    },
    "quant": {
        "max_bots": 10,
        "max_strategies": 10,
        "features": [
            "telegram_alerts", "vip_support", "unlimited_history",
            "copy_trading", "multi_exchange", "push_notifications",
            "backtest_unlimited", "ai_predictive", "api_rest", "webhooks"
        ],
        "price": 89.99,
    },
    "black": {
        "max_bots": 20,
        "max_strategies": 20,
        "features": [
            "all_features", "dedicated_server", "personal_manager",
            "early_access", "twap_vwap", "whitelabel"
        ],
        "price": 198.99,
    },
}


class LicenseService:
    """Servi?o de verifica??o e gerenciamento de licen?as."""
    
    COLLECTION_NAME = "users"
    
    @classmethod
    def _get_collection(cls):
        """Get the users collection."""
        db = get_db()
        return db[cls.COLLECTION_NAME]
    
    @classmethod
    async def get_user_license(cls, user_id: str | ObjectId) -> Dict[str, Any]:
        """
        Obt?m informa??es da licen?a do usu?rio.
        
        Returns:
            Dict com: plan, is_active, expires_at, max_bots, features
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except:
                pass
        
        user = await collection.find_one({"_id": user_id})
        
        if not user:
            return {
                "plan": "free",
                "is_active": False,
                "expires_at": None,
                "max_bots": 0,
                "active_bots": 0,
                "features": [],
            }
        
        plan = user.get("license_plan", "free")
        expires_at = user.get("license_expires_at")
        
        # Verificar se a licen?a expirou
        is_active = user.get("license_active", False)
        if expires_at and isinstance(expires_at, datetime):
            if expires_at < datetime.utcnow():
                is_active = False
                # Atualizar no banco
                await collection.update_one(
                    {"_id": user_id},
                    {"$set": {"license_active": False}}
                )
        
        plan_config = LICENSE_PLANS.get(plan, LICENSE_PLANS["free"])
        
        # Contar bots ativos do usu?rio
        db = get_db()
        instances_col = db["bot_instances"]
        active_bots = await instances_col.count_documents({
            "user_id": user_id,
            "state": {"$in": ["running", "paused"]}
        })
        
        return {
            "plan": plan,
            "is_active": is_active,
            "expires_at": expires_at,
            "max_bots": plan_config["max_bots"],
            "max_strategies": plan_config["max_strategies"],
            "active_bots": active_bots,
            "features": plan_config["features"],
            "remaining_bots": max(0, plan_config["max_bots"] - active_bots),
        }
    
    @classmethod
    async def check_can_start_bot(cls, user_id: str | ObjectId) -> tuple[bool, str]:
        """
        Verifica se o usu?rio pode iniciar um novo bot.
        
        Returns:
            Tuple (can_start, reason)
        """
        license_info = await cls.get_user_license(user_id)
        
        if not license_info["is_active"]:
            return False, "Licen?a inativa ou expirada. Por favor, renove sua assinatura."
        
        if license_info["active_bots"] >= license_info["max_bots"]:
            return False, f"Limite de {license_info['max_bots']} rob?s atingido para o plano {license_info['plan'].upper()}. Fa?a upgrade para mais rob?s."
        
        return True, "OK"
    
    @classmethod
    async def check_feature_access(
        cls,
        user_id: str | ObjectId,
        feature: str
    ) -> bool:
        """Verifica se o usu?rio tem acesso a uma feature espec?fica."""
        license_info = await cls.get_user_license(user_id)
        
        if not license_info["is_active"]:
            return False
        
        # BLACK tem acesso a tudo
        if "all_features" in license_info["features"]:
            return True
        
        return feature in license_info["features"]
    
    @classmethod
    async def activate_license(
        cls,
        user_id: str | ObjectId,
        plan: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Ativa ou renova uma licen?a para o usu?rio.
        
        Args:
            user_id: ID do usu?rio
            plan: Nome do plano (starter, pro, quant, black)
            days: Dura??o da licen?a em dias
            
        Returns:
            Licen?a atualizada
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        if plan not in LICENSE_PLANS:
            raise ValueError(f"Plano inv?lido: {plan}")
        
        now = datetime.utcnow()
        
        # Verificar se j? tem licen?a ativa para estender
        user = await collection.find_one({"_id": user_id})
        if user and user.get("license_expires_at"):
            current_expiry = user["license_expires_at"]
            if isinstance(current_expiry, datetime) and current_expiry > now:
                # Estender a partir da data atual de expira??o
                from datetime import timedelta
                new_expiry = current_expiry + timedelta(days=days)
            else:
                from datetime import timedelta
                new_expiry = now + timedelta(days=days)
        else:
            from datetime import timedelta
            new_expiry = now + timedelta(days=days)
        
        result = await collection.find_one_and_update(
            {"_id": user_id},
            {
                "$set": {
                    "license_plan": plan,
                    "license_active": True,
                    "license_expires_at": new_expiry,
                    "license_activated_at": now,
                    "updated_at": now,
                }
            },
            return_document=True
        )
        
        logger.info(f"? Licen?a {plan} ativada para user {user_id}, expira em {new_expiry}")
        
        return {
            "plan": plan,
            "is_active": True,
            "expires_at": new_expiry,
            "activated_at": now,
        }
    
    @classmethod
    async def deactivate_license(cls, user_id: str | ObjectId) -> bool:
        """Desativa a licen?a de um usu?rio."""
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        result = await collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "license_active": False,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        return result.modified_count > 0


async def require_active_license(user: dict) -> dict:
    """
    Dependency para verificar licen?a ativa.
    
    Uso:
        @router.post("/bots/{id}/start")
        async def start_bot(
            id: int,
            current_user: dict = Depends(get_current_user),
            _: dict = Depends(require_active_license)
        ):
    """
    user_id = user.get("_id") or user.get("id")
    
    license_info = await LicenseService.get_user_license(user_id)
    
    if not license_info["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "LICENSE_INACTIVE",
                "message": "Sua licen?a est? inativa ou expirada.",
                "plan": license_info["plan"],
                "upgrade_url": "/licenses"
            }
        )
    
    return license_info


async def require_bot_slot(user: dict) -> dict:
    """
    Dependency para verificar se tem slot dispon?vel para novo bot.
    """
    user_id = user.get("_id") or user.get("id")
    
    can_start, reason = await LicenseService.check_can_start_bot(user_id)
    
    if not can_start:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "BOT_LIMIT_REACHED",
                "message": reason,
                "upgrade_url": "/licenses"
            }
        )
    
    return await LicenseService.get_user_license(user_id)


def require_feature(feature: str):
    """
    Factory para criar dependency de verifica??o de feature.
    
    Uso:
        @router.get("/copy-trading")
        async def get_copy_trading(
            current_user: dict = Depends(get_current_user),
            _: None = Depends(require_feature("copy_trading"))
        ):
    """
    async def check_feature(user: dict):
        user_id = user.get("_id") or user.get("id")
        
        has_access = await LicenseService.check_feature_access(user_id, feature)
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FEATURE_NOT_AVAILABLE",
                    "message": f"O recurso '{feature}' n?o est? dispon?vel no seu plano.",
                    "feature": feature,
                    "upgrade_url": "/licenses"
                }
            )
    
    return check_feature


# Inst?ncia global
license_service = LicenseService()
