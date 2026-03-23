from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List

from app.core.database import get_db
from app.affiliate.service import AffiliateService
from app.affiliate.repository import AffiliateRepository
from app.affiliate.schemas import (
    AffiliateResponse, AffiliateStatsResponse, ReferralResponse,
    CommissionResponse, WithdrawalCreate, WithdrawalResponse,
    LevelBonusResponse, AffiliateDashboardResponse
)


router = APIRouter(prefix="/affiliate", tags=["affiliate"])


@router.post("/create", response_model=AffiliateResponse)
async def create_affiliate(user_id: int, db: AsyncSession = Depends(get_db)):
    """Cria novo afiliado para o usu?rio"""
    try:
        affiliate = await AffiliateService.create_affiliate(db, user_id)
        return affiliate
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard", response_model=AffiliateDashboardResponse)
async def get_dashboard(user_id: int, db: AsyncSession = Depends(get_db)):
    """Obt?m dashboard completo do afiliado"""
    try:
        dashboard = await AffiliateService.get_affiliate_dashboard(db, user_id)
        return dashboard
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats", response_model=AffiliateStatsResponse)
async def get_stats(user_id: int, db: AsyncSession = Depends(get_db)):
    """Obt?m estat?sticas do afiliado"""
    try:
        affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        stats = await AffiliateRepository.get_affiliate_stats(db, affiliate.id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/referrals", response_model=List[ReferralResponse])
async def get_referrals(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Obt?m refer?ncias do afiliado"""
    affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Afiliado n?o encontrado")
    
    referrals = await AffiliateRepository.get_referrals(db, affiliate.id, skip, limit)
    return referrals


@router.get("/commissions", response_model=List[CommissionResponse])
async def get_commissions(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Obt?m comiss?es do afiliado"""
    affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
    if not affiliate:
        raise HTTPException(status_code=404, detail="Afiliado n?o encontrado")
    
    commissions = await AffiliateRepository.get_commissions(db, affiliate.id, skip, limit)
    return commissions


@router.post("/withdrawal", response_model=WithdrawalResponse)
async def request_withdrawal(
    user_id: int,
    withdrawal: WithdrawalCreate,
    db: AsyncSession = Depends(get_db)
):
    """Solicita saque de comiss?o"""
    try:
        affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        withdrawal_result = await AffiliateService.request_withdrawal(
            db, affiliate.id, withdrawal.amount,
            withdrawal.bank_account, withdrawal.bank_name, withdrawal.cpf
        )
        return withdrawal_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/levels", response_model=List[LevelBonusResponse])
async def get_level_benefits(db: AsyncSession = Depends(get_db)):
    """Obt?m benef?cios por n?vel"""
    bonuses = await AffiliateRepository.get_level_bonuses(db)
    return bonuses


@router.get("/next-level")
async def get_next_level_info(user_id: int, db: AsyncSession = Depends(get_db)):
    """Obt?m informa??es de progress?o para pr?ximo n?vel"""
    try:
        affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        next_level_info = await AffiliateService.calculate_next_level_bonus(db, affiliate.id)
        return next_level_info
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/referral/add")
async def add_referral(
    user_id: int,
    referred_user_id: int,
    referred_email: str = None,
    referred_name: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Adiciona nova refer?ncia (interno - chamado ap?s signup)"""
    try:
        affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        referral = await AffiliateService.add_referral(
            db, affiliate.id, referred_user_id, referred_email, referred_name
        )
        return {"success": True, "referral_id": referral.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/referral/commission")
async def record_commission(
    user_id: int,
    referred_user_id: int,
    purchase_amount: float,
    db: AsyncSession = Depends(get_db)
):
    """Registra comiss?o de compra do usu?rio referido"""
    try:
        affiliate = await AffiliateRepository.get_affiliate_by_user_id(db, user_id)
        if not affiliate:
            raise ValueError("Afiliado n?o encontrado")
        
        commission = await AffiliateService.register_purchase_commission(
            db, affiliate.id, referred_user_id, purchase_amount
        )
        return {"success": True, "commission_amount": commission.amount}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/validate-code")
async def validate_referral_code(code: str, db: AsyncSession = Depends(get_db)):
    """Valida c?digo de refer?ncia"""
    try:
        result = await AffiliateService.validate_referral_code(db, code)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
