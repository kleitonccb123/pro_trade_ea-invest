"""
License Router - Endpoints de Licen?a e Planos

Endpoints:
- GET /api/license/plans - Lista planos dispon?veis
- GET /api/license/my-plan - Retorna plano atual do usu?rio
- POST /api/license/upgrade - Inicia upgrade de plano

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.auth.license_middleware import (
    get_user_license_info,
    get_all_plans,
    update_user_license,
    LicenseType,
    LICENSE_FEATURES
)
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/license", tags=["License"])


# ============== SCHEMAS ==============

class PlanResponse(BaseModel):
    type: str
    name: str
    description: str
    price_monthly: float
    price_yearly: float
    max_bots: int
    max_trades_per_day: int
    strategies: list[str]
    exchanges: list[str]
    features: list[str]


class MyPlanResponse(BaseModel):
    license_type: str
    license_name: str
    license_expires_at: Optional[datetime]
    is_active: bool
    is_expired: bool
    days_remaining: Optional[int]
    max_bots: int
    bots_used: int
    max_trades_per_day: int
    allowed_strategies: list[str]
    allowed_exchanges: list[str]
    allowed_features: list[str]


class UpgradeRequest(BaseModel):
    plan: str  # "pro" or "enterprise"
    billing_cycle: str = "monthly"  # "monthly" or "yearly"


class UpgradeResponse(BaseModel):
    success: bool
    message: str
    checkout_url: Optional[str] = None
    new_plan: Optional[str] = None


# ============== ENDPOINTS ==============

@router.get("/plans", response_model=list[PlanResponse])
async def list_plans():
    """
    Lista todos os planos dispon?veis com suas features.
    """
    plans = await get_all_plans()
    return plans


@router.get("/my-plan", response_model=MyPlanResponse)
async def get_my_plan(current_user: dict = Depends(get_current_user)):
    """
    Retorna informa??es detalhadas do plano atual do usu?rio.
    """
    license_info = get_user_license_info(current_user)
    
    # Contar bots usados
    db = get_db()
    bots_col = db["bots"]
    user_id = str(current_user["_id"])
    bots_used = await bots_col.count_documents({
        "user_id": user_id,
        "status": {"$ne": "deleted"}
    })
    
    # Calcular dias restantes
    days_remaining = None
    if license_info["license_expires_at"]:
        delta = license_info["license_expires_at"] - datetime.utcnow()
        days_remaining = max(0, delta.days)
    
    # Nome do plano
    license_type = license_info["license_type"]
    license_name = LICENSE_FEATURES.get(
        LicenseType(license_type), 
        LICENSE_FEATURES[LicenseType.FREE]
    )["name"]
    
    return MyPlanResponse(
        license_type=license_type,
        license_name=license_name,
        license_expires_at=license_info["license_expires_at"],
        is_active=license_info["is_active"],
        is_expired=license_info["is_expired"],
        days_remaining=days_remaining,
        max_bots=license_info["max_bots"],
        bots_used=bots_used,
        max_trades_per_day=license_info["max_trades_per_day"],
        allowed_strategies=license_info["allowed_strategies"],
        allowed_exchanges=license_info["allowed_exchanges"],
        allowed_features=license_info["allowed_features"]
    )


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade_plan(
    request: UpgradeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Inicia processo de upgrade de plano.
    
    Em produ??o, isso integraria com gateway de pagamento (Stripe, etc).
    Por ora, simula a cria??o de um checkout.
    """
    # Validar plano solicitado
    try:
        new_license = LicenseType(request.plan)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plano inv?lido: {request.plan}. Use 'free', 'pro' ou 'enterprise'."
        )
    
    current_license = current_user.get("license_type", "free")
    
    # N?o pode fazer downgrade por este endpoint
    license_order = {"free": 0, "pro": 1, "enterprise": 2}
    if license_order.get(new_license.value, 0) <= license_order.get(current_license, 0):
        if new_license.value == current_license:
            return UpgradeResponse(
                success=False,
                message=f"Voc? j? possui o plano {new_license.value.title()}."
            )
        else:
            return UpgradeResponse(
                success=False,
                message="Para fazer downgrade, entre em contato com o suporte."
            )
    
    # Obter pre?o do plano
    plan_features = LICENSE_FEATURES[new_license]
    price = plan_features["price_yearly"] if request.billing_cycle == "yearly" else plan_features["price_monthly"]
    
    # Em produ??o: criar sess?o no Stripe/gateway
    # Por ora: simular URL de checkout
    checkout_url = f"/checkout?plan={new_license.value}&billing={request.billing_cycle}&price={price}"
    
    logger.info(f"User {current_user.get('email')} initiated upgrade to {new_license.value}")
    
    return UpgradeResponse(
        success=True,
        message=f"Redirecionando para checkout do plano {plan_features['name']}...",
        checkout_url=checkout_url,
        new_plan=new_license.value
    )


@router.post("/activate-trial")
async def activate_trial(current_user: dict = Depends(get_current_user)):
    """
    Ativa trial de 7 dias do plano Pro.
    Apenas usu?rios que nunca tiveram trial podem usar.
    """
    # Verificar se j? usou trial
    if current_user.get("trial_used"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voc? j? utilizou seu per?odo de trial."
        )
    
    # Verificar se j? ? Pro ou Enterprise
    current_license = current_user.get("license_type", "free")
    if current_license in ["pro", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trial dispon?vel apenas para usu?rios do plano Free."
        )
    
    # Ativar trial de 7 dias
    user_id = str(current_user["_id"])
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    db = get_db()
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "license_type": "pro",
                "license_expires_at": expires_at,
                "trial_used": True,
                "trial_started_at": datetime.utcnow()
            }
        }
    )
    
    logger.info(f"User {current_user.get('email')} activated Pro trial")
    
    return {
        "success": True,
        "message": "Trial Pro de 7 dias ativado com sucesso!",
        "expires_at": expires_at.isoformat(),
        "plan": "pro"
    }


# Endpoint admin para atualizar licen?a (em produ??o, proteger com admin check)
@router.post("/admin/update-license/{user_id}")
async def admin_update_license(
    user_id: str,
    license_type: str,
    days: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    [ADMIN] Atualiza licen?a de um usu?rio manualmente.
    """
    # Em produ??o: verificar se current_user ? admin
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem usar este endpoint."
        )
    
    try:
        new_license = LicenseType(license_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de licen?a inv?lido: {license_type}"
        )
    
    expires_at = None
    if days:
        expires_at = datetime.utcnow() + timedelta(days=days)
    
    updated = await update_user_license(user_id, new_license, expires_at)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usu?rio n?o encontrado."
        )
    
    return {
        "success": True,
        "user_id": user_id,
        "new_license": new_license.value,
        "expires_at": expires_at.isoformat() if expires_at else None
    }
