"""
Affiliate Router - API endpoints para sistema de afiliados

Endpoints:
- GET /api/affiliates/me - Dados do afiliado do usu?rio atual
- GET /api/affiliates/stats - Estat?sticas completas
- GET /api/affiliates/referrals - Lista de indicados
- POST /api/affiliates/generate-code - Gerar c?digo de afiliado
- GET /api/affiliates/validate/{code} - Validar c?digo de referral
- POST /api/affiliates/register-referral - Registrar referral no signup

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, Query
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.auth.dependencies import get_current_user
from app.auth.utils import get_client_ip
from app.affiliates.service import AffiliateService
from app.affiliates.wallet_service import AffiliateWalletService
from app.affiliates.models import WithdrawalMethod, WithdrawalMethodType
from app.core.database import get_db
from app.services.kucoin_payout_service import KuCoinPayoutService
from app.services.withdrawal_rate_limiter import WithdrawalRateLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/affiliates", tags=["Affiliates"])


# ==================== SCHEMAS ====================

class AffiliateCodeResponse(BaseModel):
    affiliate_code: str
    affiliate_link: str
    created_at: Optional[datetime] = None


class AffiliateStatsResponse(BaseModel):
    affiliate_code: str
    affiliate_link: str
    tier: str
    commission_rate: float
    total_referrals: int
    converted_referrals: int
    conversion_rate: float
    earnings: dict
    next_tier: Optional[str]
    referrals_to_next_tier: int


class ReferralItem(BaseModel):
    id: str
    referred_email: str
    referred_name: Optional[str]
    status: str
    created_at: datetime
    converted_at: Optional[datetime]
    total_revenue: float
    total_commission: float


class ReferralsListResponse(BaseModel):
    referrals: list
    total: int
    page: int
    per_page: int


class ValidateCodeResponse(BaseModel):
    valid: bool
    code: str
    referrer_name: Optional[str] = None


class RegisterReferralRequest(BaseModel):
    new_user_id: str
    referrer_code: str


class RegisterReferralResponse(BaseModel):
    success: bool
    message: str
    referrer_id: Optional[str] = None


# ==================== WALLET SCHEMAS ====================

class WithdrawalMethodRequest(BaseModel):
    """Cadastro de método de saque"""
    type: str  # "pix", "crypto", "bank_transfer"
    key: str  # Chave PIX, endereço crypto, ou conta bancária
    holder_name: str


class WalletResponse(BaseModel):
    """Resposta com stats da carteira"""
    pending_balance: float
    available_balance: float
    total_balance: float
    total_earned: float
    total_withdrawn: float
    withdrawal_method: Optional[dict]
    is_withdrawal_ready: bool
    recent_transactions: list
    completed_withdrawals_count: int
    last_withdrawal_at: Optional[datetime]


class WithdrawRequest(BaseModel):
    """Requisição de saque"""
    amount_usd: float  # Mínimo: $50


class WithdrawResponse(BaseModel):
    """Resposta de saque"""
    success: bool
    message: str
    withdrawal_id: Optional[str]


class TransactionResponse(BaseModel):
    """Transação de wallet"""
    id: str
    type: str
    status: str
    amount_usd: float
    created_at: datetime
    release_at: Optional[datetime]
    notes: Optional[str]


class TransactionsListResponse(BaseModel):
    """Lista de transações"""
    transactions: list[TransactionResponse]
    total: int
    page: int
    per_page: int



# ==================== ENDPOINTS ====================

@router.get("/me", response_model=AffiliateCodeResponse)
async def get_my_affiliate_code(current_user: dict = Depends(get_current_user)):
    """
    Obt?m o c?digo de afiliado do usu?rio atual.
    Cria automaticamente se n?o existir.
    """
    try:
        user_id = str(current_user["_id"])
        code = await AffiliateService.get_or_create_affiliate_code(user_id)
        link = AffiliateService.generate_affiliate_link(code)
        
        return AffiliateCodeResponse(
            affiliate_code=code,
            affiliate_link=link,
            created_at=current_user.get("affiliate_created_at")
        )
    except Exception as e:
        logger.error(f"? Erro ao obter c?digo de afiliado: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-code", response_model=AffiliateCodeResponse)
async def generate_affiliate_code(current_user: dict = Depends(get_current_user)):
    """
    Gera um novo c?digo de afiliado para o usu?rio.
    Se j? existir, retorna o c?digo existente.
    """
    try:
        user_id = str(current_user["_id"])
        code = await AffiliateService.get_or_create_affiliate_code(user_id)
        link = AffiliateService.generate_affiliate_link(code)
        
        logger.info(f"? C?digo de afiliado gerado para user {user_id}: {code}")
        
        return AffiliateCodeResponse(
            affiliate_code=code,
            affiliate_link=link,
            created_at=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"? Erro ao gerar c?digo de afiliado: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=AffiliateStatsResponse)
async def get_affiliate_stats(current_user: dict = Depends(get_current_user)):
    """
    Obt?m estat?sticas completas do programa de afiliados.
    """
    try:
        user_id = str(current_user["_id"])
        stats = await AffiliateService.get_affiliate_stats(user_id)
        
        return AffiliateStatsResponse(**stats)
    except Exception as e:
        logger.error(f"? Erro ao obter stats de afiliado: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/referrals", response_model=ReferralsListResponse)
async def get_referrals_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Lista os usu?rios indicados pelo afiliado.
    """
    try:
        user_id = str(current_user["_id"])
        skip = (page - 1) * per_page
        
        referrals = await AffiliateService.get_referrals_list(
            user_id,
            limit=per_page,
            skip=skip
        )
        
        # Converter _id para id
        for ref in referrals:
            ref["id"] = ref.pop("_id", "")
        
        return ReferralsListResponse(
            referrals=referrals,
            total=len(referrals),  # TODO: Adicionar contagem total
            page=page,
            per_page=per_page
        )
    except Exception as e:
        logger.error(f"? Erro ao listar referrals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/{code}", response_model=ValidateCodeResponse)
async def validate_affiliate_code(code: str):
    """
    Valida um c?digo de afiliado.
    P?blico - usado na p?gina de signup.
    """
    try:
        referrer = await AffiliateService.find_user_by_affiliate_code(code)
        
        if referrer:
            return ValidateCodeResponse(
                valid=True,
                code=code.upper(),
                referrer_name=referrer.get("name", "Afiliado")
            )
        else:
            return ValidateCodeResponse(
                valid=False,
                code=code.upper(),
                referrer_name=None
            )
    except Exception as e:
        logger.error(f"? Erro ao validar c?digo: {e}")
        return ValidateCodeResponse(valid=False, code=code, referrer_name=None)


@router.post("/register-referral", response_model=RegisterReferralResponse)
async def register_referral(request: RegisterReferralRequest):
    """
    Registra uma indica??o ap?s o signup de um novo usu?rio.
    Chamado internamente ap?s o cadastro.
    """
    try:
        referral = await AffiliateService.register_referral(
            new_user_id=request.new_user_id,
            referrer_code=request.referrer_code
        )
        
        if referral:
            return RegisterReferralResponse(
                success=True,
                message="Indica??o registrada com sucesso",
                referrer_id=str(referral["referrer_id"])
            )
        else:
            return RegisterReferralResponse(
                success=False,
                message="C?digo de afiliado inv?lido ou j? foi indicado",
                referrer_id=None
            )
    except Exception as e:
        logger.error(f"? Erro ao registrar referral: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/track/{code}")
async def track_affiliate_click(code: str, response: Response):
    """
    Endpoint para rastrear cliques em links de afiliados.
    Define um cookie com o c?digo do afiliado.
    """
    try:
        # Validar c?digo
        referrer = await AffiliateService.find_user_by_affiliate_code(code)
        
        if referrer:
            # Definir cookie com validade de 30 dias
            response.set_cookie(
                key="ref_code",
                value=code.upper(),
                max_age=30 * 24 * 60 * 60,  # 30 dias
                httponly=False,  # Acess?vel pelo frontend
                samesite="lax"
            )
            
            return {
                "success": True,
                "message": "Refer?ncia rastreada",
                "referrer_name": referrer.get("name", "Afiliado")
            }
        else:
            return {
                "success": False,
                "message": "C?digo inv?lido"
            }
    except Exception as e:
        logger.error(f"? Erro ao rastrear click: {e}")
        return {"success": False, "message": str(e)}


@router.get("/tiers")
async def get_affiliate_tiers():
    """
    Retorna informa??es sobre os n?veis de afiliado.
    """
    tiers = []
    for name, config in AffiliateService.AFFILIATE_TIERS.items():
        tiers.append({
            "name": name,
            "min_referrals": config["min_referrals"],
            "commission_rate": config["commission_rate"],
            "commission_percentage": f"{config['commission_rate'] * 100:.0f}%"
        })
    
    return {"tiers": sorted(tiers, key=lambda x: x["min_referrals"])}


# ==================== WALLET ENDPOINTS ====================

async def get_wallet_service(db=Depends(get_db)) -> AffiliateWalletService:
    """Dependency: Retorna serviço de wallet"""
    return AffiliateWalletService(db)


@router.get("/wallet", response_model=WalletResponse)
async def get_wallet_stats(
    current_user: dict = Depends(get_current_user),
    wallet_service: AffiliateWalletService = Depends(get_wallet_service)
):
    """
    Obtém as estatísticas da carteira do afiliado.
    
    Retorna:
    - pending_balance: Saldo em carência (7 dias)
    - available_balance: Saldo disponível para saque
    - total_balance: Total pendente + disponível
    - total_earned: Total ganho em comissões
    """
    try:
        user_id = str(current_user["_id"])
        stats = await wallet_service.get_wallet_stats(user_id)
        
        logger.info(f"📊 Wallet stats obtidos para {user_id}")
        return WalletResponse(**stats)
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter wallet stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/withdrawal-method", response_model=dict)
async def set_withdrawal_method(
    method: WithdrawalMethodRequest,
    current_user: dict = Depends(get_current_user),
    wallet_service: AffiliateWalletService = Depends(get_wallet_service)
):
    """
    Cadastra ou atualiza método de saque.
    
    Tipos:
    - pix: Chave PIX (CPF, email, telefone ou aleatória)
    - crypto: Endereço de carteira (TRC20)
    - bank_transfer: Dados bancários
    """
    try:
        user_id = str(current_user["_id"])
        
        # Validar tipo
        if method.type not in ["pix", "crypto", "bank_transfer", "kucoin_uid"]:
            raise HTTPException(
                status_code=400,
                detail="Tipo de saque inválido. Use: pix, crypto, bank_transfer, kucoin_uid"
            )
        
        # Criar modelo
        withdrawal_method = WithdrawalMethod(
            type=method.type,
            key=method.key,
            holder_name=method.holder_name,
            is_verified=False  # Será verificado em produção
        )
        
        # Busca e atualiza wallet
        wallet = await wallet_service.get_or_create_wallet(user_id)
        wallet.withdrawal_method = withdrawal_method
        await wallet_service.save_wallet(wallet)
        
        logger.info(f"✅ Método de saque cadastrado para {user_id}: {method.type}")
        
        return {
            "success": True,
            "message": f"Método de saque {method.type} cadastrado com sucesso",
            "method": withdrawal_method.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao cadastrar método: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/withdraw", response_model=WithdrawResponse)
async def process_withdrawal(
    request: WithdrawRequest,
    current_user: dict = Depends(get_current_user),
    wallet_service: AffiliateWalletService = Depends(get_wallet_service),
    db=Depends(get_db)
):
    """
    Processa um saque de USD para o método cadastrado (PIX, Crypto, Banco, KuCoin UID).
    
    Requisitos:
    - Mínimo: $50
    - Método de saque cadastrado
    - Saldo disponível >= Valor solicitado
    - Rate limit: máximo 1 saque por hora por usuário
    
    Fluxo para KUCOIN_UID:
    1. Validar rate limit
    2. Validar saldo e UID
    3. Deduzir saldo (atômico)
    4. Enviar para KuCoin Internal Transfer
    5. Se sucesso: marca como completed
    6. Se falha: reverte saldo e marca como failed
    """
    try:
        user_id = str(current_user["_id"])
        
        logger.info(f"💳 Processando saque para {user_id}: ${request.amount_usd}")
        
        # ✅ STEP 1: Verificar Rate Limit
        rate_limiter = WithdrawalRateLimiter(db)
        permitted, rate_msg = await rate_limiter.check_rate_limit(user_id)
        
        if not permitted:
            logger.warning(f"⏳ Rate limit atingido: {rate_msg}")
            return WithdrawResponse(
                success=False,
                message=rate_msg,
                withdrawal_id=None
            )
        
        # ✅ STEP 2: Get wallet
        wallet = await wallet_service.get_or_create_wallet(user_id)
        
        if not wallet.withdrawal_method:
            msg = "Método de saque não configurado. Configure sua chave PIX ou UID KuCoin primeiro."
            logger.warning(f"⚠️ {msg}")
            return WithdrawResponse(success=False, message=msg, withdrawal_id=None)
        
        # ✅ STEP 3: Se KuCoin, processa aqui
        if wallet.withdrawal_method.type == "kucoin_uid":
            logger.info("🟡 Detectado saque KuCoin - acionando KuCoinPayoutService")
            
            # Validar saldo (converter para Decimal para comparação precisa)
            available_decimal = Decimal(str(wallet.available_balance)) if isinstance(wallet.available_balance, float) else wallet.available_balance
            if available_decimal < request.amount_usd:
                msg = f"Saldo insuficiente. Disponível: ${available_decimal:.2f}"
                logger.warning(f"⚠️ {msg}")
                return WithdrawResponse(success=False, message=msg, withdrawal_id=None)
            
            # Inicializa serviço KuCoin
            kucoin_service = KuCoinPayoutService(db)
            destination_uid = wallet.withdrawal_method.key
            
            # Processa a transferência interna
            success, kucoin_msg, transfer_id = await kucoin_service.process_internal_transfer(
                destination_uid=destination_uid,
                amount_usd=request.amount_usd,
                user_id=user_id
            )
            
            if success:
                # ✅ Débita saldo e marca como sucesso
                success_wallet, success_msg, withdrawal_id = await wallet_service.process_withdrawal(
                    user_id,
                    request.amount_usd
                )
                
                # Registra tentativa para rate limiting
                await rate_limiter.record_withdrawal_attempt(user_id, withdrawal_id)
                
                logger.info(f"✅ Saque KuCoin processado: ID={withdrawal_id}, Transfer={transfer_id}")
                return WithdrawResponse(
                    success=True,
                    message=f"Saque de ${request.amount_usd:.2f} USDT enviado para seu UID KuCoin!",
                    withdrawal_id=withdrawal_id
                )
            else:
                # ❌ KuCoin falhou, não débita nada
                logger.warning(f"❌ Falha KuCoin: {kucoin_msg}")
                
                # Ainda registra tentativa para rate limiting (falha conta também)
                await rate_limiter.record_withdrawal_attempt(user_id)
                
                return WithdrawResponse(
                    success=False,
                    message=f"Erro ao transferir para KuCoin: {kucoin_msg}",
                    withdrawal_id=None
                )
        
        else:
            # ✅ Outros métodos (PIX, Crypto, Banco) - usa o serviço de wallet
            logger.info(f"🟢 Saque via {wallet.withdrawal_method.type} - acionando WalletService")
            
            success, message, withdrawal_id = await wallet_service.process_withdrawal(
                user_id,
                request.amount_usd
            )
            
            if success:
                # Registra tentativa para rate limiting
                await rate_limiter.record_withdrawal_attempt(user_id, withdrawal_id)
                logger.info(f"✅ Saque processado com ID: {withdrawal_id}")
            else:
                logger.warning(f"⚠️ Saque falhou: {message}")
            
            return WithdrawResponse(
                success=success,
                message=message,
                withdrawal_id=withdrawal_id
            )
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar saque: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions", response_model=TransactionsListResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    wallet_service: AffiliateWalletService = Depends(get_wallet_service)
):
    """
    Obtém histórico de transações da carteira.
    
    Inclui:
    - Comissões (Pending/Available)
    - Saques (Processing/Completed/Failed)
    - Reversões (Refunds)
    """
    try:
        user_id = str(current_user["_id"])
        db = wallet_service.db
        transaction_col = db["affiliate_transactions"]
        
        skip = (page - 1) * per_page
        
        # Busca transações
        cursor = transaction_col.find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(per_page)
        
        transactions = await cursor.to_list(per_page)
        
        # Conta total
        total = await transaction_col.count_documents({"user_id": user_id})
        
        # Formata resposta
        transactions_list = [
            TransactionResponse(
                id=str(t["_id"]),
                type=t.get("type"),
                status=t.get("status"),
                amount_usd=round(t.get("amount_usd", 0), 2),
                created_at=t.get("created_at"),
                release_at=t.get("release_at"),
                notes=t.get("notes")
            )
            for t in transactions
        ]
        
        logger.info(f"📋 {len(transactions_list)} transações obtidas para {user_id}")
        
        return TransactionsListResponse(
            transactions=transactions_list,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter transações: {e}")
        raise HTTPException(status_code=500, detail=str(e))

