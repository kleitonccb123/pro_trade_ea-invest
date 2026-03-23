"""
User Settings Router - Gerenciamento de configura??es do usu?rio
Inclui: Perfil, Exchanges (API Keys), Seguran?a (2FA, Webhooks)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
import ccxt

from app.auth.dependencies import get_current_user
from app.core.database import get_database
from app.core.encryption import encrypt_credential, decrypt_credential

router = APIRouter(prefix="/user/settings", tags=["user-settings"])


# ============== SCHEMAS ==============

class ExchangeCredentialsRequest(BaseModel):
    """Request para adicionar/atualizar credenciais de exchange."""
    exchange: str = Field(..., description="ID da exchange (binance, kucoin)")
    api_key: str = Field(..., min_length=10, description="API Key")
    api_secret: str = Field(..., min_length=10, description="API Secret")
    passphrase: Optional[str] = Field(None, description="Passphrase (obrigat?rio para KuCoin)")
    sandbox: bool = Field(False, description="Usar ambiente de testes")


class ExchangeCredentialsResponse(BaseModel):
    """Response com credenciais (mascaradas)."""
    exchange: str
    api_key_masked: str
    connected: bool
    sandbox: bool
    last_validated: Optional[datetime]
    balance_usd: Optional[float] = None


class ProfileUpdateRequest(BaseModel):
    """Request para atualizar perfil."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    timezone: Optional[str] = "America/Sao_Paulo"
    language: Optional[str] = "pt-BR"


class ProfileResponse(BaseModel):
    """Response do perfil do usu?rio."""
    id: str
    email: str
    name: Optional[str]
    phone: Optional[str]
    timezone: str
    language: str
    created_at: datetime
    two_factor_enabled: bool


class WebhookSettingsRequest(BaseModel):
    """Request para configurar webhooks de notifica??o."""
    telegram_enabled: bool = False
    telegram_chat_id: Optional[str] = None
    discord_enabled: bool = False
    discord_webhook_url: Optional[str] = None
    email_notifications: bool = True
    notify_on_trade: bool = True
    notify_on_error: bool = True
    notify_daily_summary: bool = False


class WebhookSettingsResponse(BaseModel):
    """Response das configura??es de webhook."""
    telegram_enabled: bool
    telegram_configured: bool
    discord_enabled: bool
    discord_configured: bool
    email_notifications: bool
    notify_on_trade: bool
    notify_on_error: bool
    notify_daily_summary: bool


# ============== EXCHANGE ENDPOINTS ==============

@router.post("/exchanges", response_model=ExchangeCredentialsResponse)
async def add_exchange_credentials(
    request: ExchangeCredentialsRequest,
    current_user = Depends(get_current_user)
):
    """
    Adiciona ou atualiza credenciais de uma exchange.
    
    Processo:
    1. Valida credenciais via CCXT
    2. Encripta secrets com Fernet
    3. Salva no MongoDB
    """
    db = await get_database()
    user_id = str(current_user.id)
    
    # Validar exchange suportada
    supported_exchanges = ["binance", "kucoin", "bybit", "okx"]
    if request.exchange.lower() not in supported_exchanges:
        raise HTTPException(
            status_code=400,
            detail=f"Exchange n?o suportada. Op??es: {', '.join(supported_exchanges)}"
        )
    
    # KuCoin requer passphrase
    if request.exchange.lower() == "kucoin" and not request.passphrase:
        raise HTTPException(
            status_code=400,
            detail="KuCoin requer passphrase"
        )
    
    # Validar credenciais via CCXT
    try:
        exchange_class = getattr(ccxt, request.exchange.lower())
        
        exchange_config = {
            'apiKey': request.api_key,
            'secret': request.api_secret,
            'enableRateLimit': True,
        }
        
        if request.passphrase:
            exchange_config['password'] = request.passphrase
        
        if request.sandbox:
            exchange_config['sandbox'] = True
        
        exchange = exchange_class(exchange_config)
        
        # Testar conex?o buscando saldo
        balance = await _fetch_balance_async(exchange)
        
        if not balance:
            raise HTTPException(
                status_code=400,
                detail="N?o foi poss?vel validar as credenciais. Verifique as permiss?es da API."
            )
        
        # Calcular saldo total em USD
        total_usd = _calculate_usd_balance(balance)
        
    except ccxt.AuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Credenciais inv?lidas. Verifique API Key, Secret e Passphrase."
        )
    except ccxt.ExchangeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro da exchange: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao validar credenciais: {str(e)}"
        )
    
    # Encriptar credenciais sens?veis
    encrypted_data = {
        "user_id": user_id,
        "exchange": request.exchange.lower(),
        "api_key": request.api_key,  # Key n?o ? secret
        "api_key_masked": _mask_api_key(request.api_key),
        "api_secret_encrypted": encrypt_credential(request.api_secret),
        "sandbox": request.sandbox,
        "connected": True,
        "last_validated": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    if request.passphrase:
        encrypted_data["passphrase_encrypted"] = encrypt_credential(request.passphrase)
    
    # Upsert no MongoDB
    await db.api_credentials.update_one(
        {"user_id": user_id, "exchange": request.exchange.lower()},
        {"$set": encrypted_data},
        upsert=True
    )
    
    return ExchangeCredentialsResponse(
        exchange=request.exchange.lower(),
        api_key_masked=_mask_api_key(request.api_key),
        connected=True,
        sandbox=request.sandbox,
        last_validated=datetime.utcnow(),
        balance_usd=total_usd
    )


@router.get("/exchanges", response_model=List[ExchangeCredentialsResponse])
async def list_exchange_credentials(
    current_user = Depends(get_current_user)
):
    """Lista todas as exchanges configuradas pelo usu?rio."""
    db = await get_database()
    user_id = str(current_user.id)
    
    credentials = await db.api_credentials.find(
        {"user_id": user_id}
    ).to_list(10)
    
    return [
        ExchangeCredentialsResponse(
            exchange=cred.get("exchange", ""),
            api_key_masked=cred.get("api_key_masked", "****"),
            connected=cred.get("connected", False),
            sandbox=cred.get("sandbox", False),
            last_validated=cred.get("last_validated"),
            balance_usd=cred.get("balance_usd")
        )
        for cred in credentials
    ]


@router.delete("/exchanges/{exchange}")
async def remove_exchange_credentials(
    exchange: str,
    current_user = Depends(get_current_user)
):
    """Remove credenciais de uma exchange."""
    db = await get_database()
    user_id = str(current_user.id)
    
    result = await db.api_credentials.delete_one({
        "user_id": user_id,
        "exchange": exchange.lower()
    })
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Credenciais n?o encontradas"
        )
    
    return {"message": f"Credenciais da {exchange} removidas com sucesso"}


@router.post("/exchanges/{exchange}/validate")
async def validate_exchange_credentials(
    exchange: str,
    current_user = Depends(get_current_user)
):
    """Revalida credenciais de uma exchange."""
    db = await get_database()
    user_id = str(current_user.id)
    
    # Buscar credenciais
    cred = await db.api_credentials.find_one({
        "user_id": user_id,
        "exchange": exchange.lower()
    })
    
    if not cred:
        raise HTTPException(
            status_code=404,
            detail="Credenciais n?o encontradas"
        )
    
    try:
        # Decriptar
        api_secret = decrypt_credential(cred.get("api_secret_encrypted", ""))
        passphrase = None
        if cred.get("passphrase_encrypted"):
            passphrase = decrypt_credential(cred["passphrase_encrypted"])
        
        # Validar via CCXT
        exchange_class = getattr(ccxt, exchange.lower())
        exchange_config = {
            'apiKey': cred.get("api_key"),
            'secret': api_secret,
            'enableRateLimit': True,
        }
        
        if passphrase:
            exchange_config['password'] = passphrase
        
        if cred.get("sandbox"):
            exchange_config['sandbox'] = True
        
        ex = exchange_class(exchange_config)
        balance = await _fetch_balance_async(ex)
        
        if not balance:
            raise Exception("Falha na valida??o")
        
        total_usd = _calculate_usd_balance(balance)
        
        # Atualizar status
        await db.api_credentials.update_one(
            {"_id": cred["_id"]},
            {
                "$set": {
                    "connected": True,
                    "last_validated": datetime.utcnow(),
                    "balance_usd": total_usd,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "valid": True,
            "balance_usd": total_usd,
            "last_validated": datetime.utcnow()
        }
        
    except Exception as e:
        # Marcar como desconectado
        await db.api_credentials.update_one(
            {"_id": cred["_id"]},
            {
                "$set": {
                    "connected": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        raise HTTPException(
            status_code=400,
            detail=f"Falha na valida??o: {str(e)}"
        )


# ============== PROFILE ENDPOINTS ==============

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user = Depends(get_current_user)
):
    """Retorna perfil do usu?rio."""
    db = await get_database()
    user_id = str(current_user.id)
    
    # Buscar dados adicionais do perfil
    profile = await db.user_profiles.find_one({"user_id": user_id})
    
    return ProfileResponse(
        id=user_id,
        email=current_user.email,
        name=profile.get("name") if profile else None,
        phone=profile.get("phone") if profile else None,
        timezone=profile.get("timezone", "America/Sao_Paulo") if profile else "America/Sao_Paulo",
        language=profile.get("language", "pt-BR") if profile else "pt-BR",
        created_at=current_user.created_at,
        two_factor_enabled=getattr(current_user, 'two_factor_enabled', False)
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user = Depends(get_current_user)
):
    """Atualiza perfil do usu?rio."""
    db = await get_database()
    user_id = str(current_user.id)
    
    update_data = {
        "user_id": user_id,
        "updated_at": datetime.utcnow()
    }
    
    if request.name is not None:
        update_data["name"] = request.name
    if request.phone is not None:
        update_data["phone"] = request.phone
    if request.timezone is not None:
        update_data["timezone"] = request.timezone
    if request.language is not None:
        update_data["language"] = request.language
    
    await db.user_profiles.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )
    
    return await get_profile(current_user)


# ============== WEBHOOK ENDPOINTS ==============

@router.get("/webhooks", response_model=WebhookSettingsResponse)
async def get_webhook_settings(
    current_user = Depends(get_current_user)
):
    """Retorna configura??es de webhooks."""
    db = await get_database()
    user_id = str(current_user.id)
    
    settings = await db.webhook_settings.find_one({"user_id": user_id})
    
    if not settings:
        return WebhookSettingsResponse(
            telegram_enabled=False,
            telegram_configured=False,
            discord_enabled=False,
            discord_configured=False,
            email_notifications=True,
            notify_on_trade=True,
            notify_on_error=True,
            notify_daily_summary=False
        )
    
    return WebhookSettingsResponse(
        telegram_enabled=settings.get("telegram_enabled", False),
        telegram_configured=bool(settings.get("telegram_chat_id")),
        discord_enabled=settings.get("discord_enabled", False),
        discord_configured=bool(settings.get("discord_webhook_url")),
        email_notifications=settings.get("email_notifications", True),
        notify_on_trade=settings.get("notify_on_trade", True),
        notify_on_error=settings.get("notify_on_error", True),
        notify_daily_summary=settings.get("notify_daily_summary", False)
    )


@router.put("/webhooks", response_model=WebhookSettingsResponse)
async def update_webhook_settings(
    request: WebhookSettingsRequest,
    current_user = Depends(get_current_user)
):
    """Atualiza configura??es de webhooks."""
    db = await get_database()
    user_id = str(current_user.id)
    
    update_data = {
        "user_id": user_id,
        "telegram_enabled": request.telegram_enabled,
        "discord_enabled": request.discord_enabled,
        "email_notifications": request.email_notifications,
        "notify_on_trade": request.notify_on_trade,
        "notify_on_error": request.notify_on_error,
        "notify_daily_summary": request.notify_daily_summary,
        "updated_at": datetime.utcnow()
    }
    
    if request.telegram_chat_id:
        update_data["telegram_chat_id"] = request.telegram_chat_id
    
    if request.discord_webhook_url:
        update_data["discord_webhook_url"] = request.discord_webhook_url
    
    await db.webhook_settings.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )
    
    return await get_webhook_settings(current_user)


# ============== HELPER FUNCTIONS ==============

def _mask_api_key(api_key: str) -> str:
    """Mascara uma API key para exibi??o segura."""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


async def _fetch_balance_async(exchange) -> dict:
    """Busca saldo de forma ass?ncrona."""
    import asyncio
    
    try:
        if hasattr(exchange, 'fetch_balance'):
            # CCXT sync - rodar em thread pool
            loop = asyncio.get_event_loop()
            balance = await loop.run_in_executor(None, exchange.fetch_balance)
            return balance
    except Exception as e:
        print(f"Erro ao buscar saldo: {e}")
        return None


def _calculate_usd_balance(balance: dict) -> float:
    """Calcula saldo total aproximado em USD."""
    if not balance:
        return 0.0
    
    total = balance.get('total', {})
    
    # Somar stablecoins diretamente
    usd_value = 0.0
    stablecoins = ['USDT', 'USDC', 'BUSD', 'USD', 'TUSD']
    
    for coin in stablecoins:
        if coin in total and total[coin]:
            usd_value += float(total[coin])
    
    # Nota: Em produ??o, converter outros ativos para USD
    # usando pre?os de mercado
    
    return round(usd_value, 2)
