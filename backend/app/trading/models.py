"""
Modelos Pydantic para Trading (KuCoin)
======================================

Credenciais, Ordens, Trades e Alertas com suporte a KuCoin.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import enum


# ========================================
# Enums
# ========================================

class OrderSideEnum(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderTypeEnum(enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatusEnum(enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


# ========================================
# KuCoin Credentials
# ========================================

class KuCoinCredentialCreate(BaseModel):
    """Input: Dados do usu?rio para conectar KuCoin"""
    
    api_key: str = Field(
        ...,
        min_length=10,
        max_length=200,
        description="API Key da KuCoin"
    )
    api_secret: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Secret da KuCoin"
    )
    api_passphrase: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Passphrase (senha adicional da KuCoin)"
    )
    is_sandbox: bool = Field(
        default=True,
        description="True = teste (sem risco), False = produ??o"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "api_key": "63d6ff48c50c8b7e85f55d3f",
                "api_secret": "c8a6b7e9-1f3a-4b5c-8d9e-0f1a2b3c4d5e",
                "api_passphrase": "myPassword123",
                "is_sandbox": True
            }
        }
    }


class KuCoinCredentialResponse(BaseModel):
    """Output: Resposta segura (SEM secrets)"""
    
    id: str = Field(alias="_id")
    user_id: str
    is_active: bool
    is_sandbox: bool
    created_at: datetime
    last_used: Optional[datetime] = None
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "63d6ff48c50c8b7e85f55d3f",
                "user_id": "63d6ff48c50c8b7e85f55d3f",
                "is_active": True,
                "is_sandbox": True,
                "created_at": "2024-01-15T10:30:00Z",
                "last_used": None
            }
        }
    }


class KuCoinCredentialInDB(BaseModel):
    """Interno: Formato no MongoDB (com dados encriptados)"""
    
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    api_key_enc: str
    api_secret_enc: str
    api_passphrase_enc: str
    is_active: bool = True
    is_sandbox: bool = True
    created_at: datetime
    last_used: Optional[datetime] = None
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }


class KuCoinCredentialUpdate(BaseModel):
    """Campos para editar credenciais"""
    
    is_active: Optional[bool] = None
    is_sandbox: Optional[bool] = None


class KuCoinConnectionStatus(BaseModel):
    """Status da conex?o com KuCoin"""
    
    connected: bool
    status: str
    error: Optional[str] = None
    exchange_info: Optional[dict] = None


# ========================================
# Trading
# ========================================

class RealOrder(BaseModel):
    """Ordem de trading na KuCoin"""
    
    id: str = Field(alias="_id")
    user_id: str
    order_id: str  # ID da KuCoin
    symbol: str
    side: OrderSideEnum
    order_type: OrderTypeEnum
    quantity: float
    price: Optional[float] = None
    status: OrderStatusEnum
    created_at: datetime
    filled_quantity: float = 0.0
    idempotency_key: Optional[str] = None
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }


class RealTrade(BaseModel):
    """Trade executado na KuCoin"""
    
    id: str = Field(alias="_id")
    user_id: str
    order_id: str
    symbol: str
    side: OrderSideEnum
    quantity: float
    price: float
    commission: float
    commission_asset: str
    timestamp: datetime
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }


class TradingSession(BaseModel):
    """Sess?o de trading"""
    
    id: str = Field(alias="_id")
    user_id: str
    strategy_id: str
    is_active: bool
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_trades: int = 0
    total_profit_loss: float = 0.0
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }


class TradingAlert(BaseModel):
    """Alerta de trading"""
    
    id: str = Field(alias="_id")
    user_id: str
    strategy_id: str
    message: str
    alert_type: str  # "price_reached", "order_filled", "error"
    read: bool = False
    created_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }


class RealTimeMarketData(BaseModel):
    """Dados de mercado em tempo real"""
    
    symbol: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    change_24h: float
    timestamp: datetime


class IdempotencyKey(BaseModel):
    """Idempotency key para prevenir ordens duplicadas"""
    
    id: str = Field(alias="_id")
    user_id: str
    idempotency_key: str
    order_data: dict  # Dados da ordem original
    order_id: Optional[str] = None  # ID da ordem criada
    created_at: datetime
    expires_at: datetime  # TTL para limpeza autom?tica
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
