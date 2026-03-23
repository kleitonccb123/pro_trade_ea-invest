"""
Database Models - Pydantic + MongoDB
Schemas para User, Bot, Order, Exchange Credentials
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
from bson import ObjectId


# ========== IDs ==========
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError(f"Invalid ObjectId: {v}")
        return ObjectId(v)


# ========== Enums ==========
class BotStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class OrderStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


# ========== User Models ==========
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: str
    
    @validator('password')
    def password_strong(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserResponse(BaseModel):
    id: str = Field(alias="_id")
    email: str
    username: str
    created_at: datetime
    
    class Config:
        populate_by_name = True


class User(BaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    email: str
    username: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    is_admin: bool = False
    
    class Config:
        populate_by_name = True


# ========== Exchange Credentials ==========
class ExchangeCredentialCreate(BaseModel):
    exchange: str  # kucoin, binance, etc
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None


class ExchangeCredential(BaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: str
    exchange: str
    api_key: str
    api_secret_enc: str  # Encrypted
    passphrase_enc: Optional[str] = None  # Encrypted
    algorithm: str = "fernet"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    class Config:
        populate_by_name = True


# ========== Bot Models ==========
class BotConfig(BaseModel):
    strategy: str  # sma_crossover, etc
    symbol: str
    interval: str  # 1m, 5m, 15m, 1h, 4h, 1d
    leverage: Decimal = Decimal("1.0")
    
    @validator('leverage')
    def validate_leverage(cls, v):
        if v < Decimal("1.0") or v > Decimal("10.0"):
            raise ValueError('Leverage must be between 1.0 and 10.0')
        return v


class BotCreate(BaseModel):
    name: str
    exchange: str  # kucoin
    config: BotConfig


class Bot(BaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: str
    name: str
    exchange: str
    config: BotConfig
    status: BotStatus = BotStatus.IDLE
    trades_count: int = 0
    pnl_total: Decimal = Decimal("0")
    pnl_realized: Decimal = Decimal("0")
    pnl_unrealized: Decimal = Decimal("0")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


# ========== Order Models ==========
class OrderCreate(BaseModel):
    bot_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: Decimal
    price: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None


class Order(BaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: str
    bot_id: str
    request_id: str  # UUID para idempotency
    exchange_order_id: Optional[str] = None
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: Decimal
    price: Optional[Decimal] = None
    filled: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    fee: Decimal = Decimal("0")
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


# ========== Position Models ==========
class Position(BaseModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: str
    bot_id: str
    symbol: str
    side: OrderSide
    opening_order_id: str  # ObjectId da ordem de abertura
    closing_order_id: Optional[str] = None
    entry_price: Decimal
    size: Decimal
    exit_price: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    status: str = "open"  # open, closed, tp_hit, sl_hit
    pnl: Optional[Decimal] = None
    pnl_percent: Optional[Decimal] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


# ========== Trade Signal Models ==========
class TradeSignal(BaseModel):
    symbol: str
    side: OrderSide
    size: Decimal
    confidence: float  # 0-1
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ========== Response Models ==========
class BotResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    exchange: str
    status: BotStatus
    trades_count: int
    pnl_total: str  # String para evitar precision issues
    pnl_realized: str
    pnl_unrealized: str
    created_at: datetime
    
    class Config:
        populate_by_name = True


class OrderResponse(BaseModel):
    id: str = Field(alias="_id")
    symbol: str
    side: OrderSide
    status: OrderStatus
    size: str
    filled: str
    price: Optional[str] = None
    exchange_order_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    
    class Config:
        populate_by_name = True
