"""Trading models package."""
from .pending_order import OrderStatus, PendingOrder

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
    NEW = "NEW"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


# ========================================
# KuCoin Credentials
# ========================================

class KuCoinCredentialCreate(BaseModel):
    api_key: str = Field(..., min_length=10, max_length=200)
    api_secret: str = Field(..., min_length=20, max_length=500)
    api_passphrase: str = Field(..., min_length=6, max_length=100)
    is_sandbox: bool = Field(default=True)


class KuCoinCredentialResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    is_active: bool
    is_sandbox: bool
    created_at: datetime
    last_used: Optional[datetime] = None
    model_config = {"populate_by_name": True, "from_attributes": True}


class KuCoinCredentialInDB(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    user_id: str
    api_key_enc: str
    api_secret_enc: str
    api_passphrase_enc: str
    is_active: bool = True
    is_sandbox: bool = True
    created_at: datetime
    last_used: Optional[datetime] = None
    model_config = {"populate_by_name": True, "from_attributes": True}


class KuCoinCredentialUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_sandbox: Optional[bool] = None


class KuCoinConnectionStatus(BaseModel):
    connected: bool
    status: str
    error: Optional[str] = None
    exchange_info: Optional[dict] = None


# ========================================
# Trading Models
# ========================================

class RealOrder(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    order_id: str
    symbol: str
    side: OrderSideEnum
    order_type: OrderTypeEnum
    quantity: float
    price: Optional[float] = None
    status: OrderStatusEnum
    created_at: datetime
    filled_quantity: float = 0.0
    idempotency_key: Optional[str] = None
    model_config = {"populate_by_name": True, "from_attributes": True}


class RealTrade(BaseModel):
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
    model_config = {"populate_by_name": True, "from_attributes": True}


class TradingSession(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    strategy_id: str
    is_active: bool
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_trades: int = 0
    total_profit_loss: float = 0.0
    model_config = {"populate_by_name": True, "from_attributes": True}


class TradingAlert(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    strategy_id: str
    message: str
    alert_type: str
    read: bool = False
    created_at: datetime
    model_config = {"populate_by_name": True, "from_attributes": True}


class RealTimeMarketData(BaseModel):
    symbol: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    change_24h: float
    timestamp: datetime


class IdempotencyKey(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    idempotency_key: str
    order_data: dict
    order_id: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    model_config = {"populate_by_name": True, "from_attributes": True}


__all__ = [
    "OrderStatus", "PendingOrder",
    "OrderSideEnum", "OrderTypeEnum", "OrderStatusEnum",
    "KuCoinCredentialCreate", "KuCoinCredentialResponse",
    "KuCoinCredentialInDB", "KuCoinCredentialUpdate", "KuCoinConnectionStatus",
    "RealOrder", "RealTrade", "TradingSession", "TradingAlert",
    "RealTimeMarketData", "IdempotencyKey",
]
