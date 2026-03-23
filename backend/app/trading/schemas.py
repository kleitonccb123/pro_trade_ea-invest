"""
Real trading models and schemas
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class ExchangeType(str, Enum):
    """Supported exchanges."""
    BINANCE = "binance"
    KUCOIN = "kucoin"
    BYBIT = "bybit"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"

class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ==================== CREDENTIALS SCHEMAS ====================

class ExchangeCredentialsCreate(BaseModel):
    """Schema for creating exchange credentials."""
    model_config = ConfigDict(from_attributes=True)
    
    exchange: ExchangeType = Field(..., description="Exchange name (binance, kucoin)")
    api_key: str = Field(..., min_length=10, description="API key")
    api_secret: str = Field(..., min_length=10, description="API secret")
    passphrase: Optional[str] = Field(None, description="API passphrase (required for KuCoin)")
    is_testnet: bool = Field(default=True, description="Use testnet/sandbox mode")
    label: Optional[str] = Field(None, description="Optional label for this credential set")
    
    @field_validator('passphrase')
    @classmethod
    def validate_passphrase(cls, v, info):
        """KuCoin requires a passphrase."""
        exchange = info.data.get('exchange')
        if exchange == ExchangeType.KUCOIN and not v:
            raise ValueError("Passphrase is required for KuCoin")
        return v


class ExchangeCredentialsResponse(BaseModel):
    """Schema for credential responses (no sensitive data)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="Credential ID")
    exchange: str = Field(..., description="Exchange name")
    api_key_partial: str = Field(..., description="Masked API key (xxxx...yyyy)")
    is_testnet: bool = Field(..., description="Using testnet mode")
    is_active: bool = Field(..., description="Credentials active status")
    label: Optional[str] = Field(None, description="Credential label")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class TestCredentialsRequest(BaseModel):
    """Schema for testing credentials without saving."""
    model_config = ConfigDict(from_attributes=True)
    
    exchange: ExchangeType = Field(..., description="Exchange name")
    api_key: str = Field(..., min_length=10, description="API key")
    api_secret: str = Field(..., min_length=10, description="API secret")
    passphrase: Optional[str] = Field(None, description="API passphrase (KuCoin)")
    is_testnet: bool = Field(default=True, description="Use testnet/sandbox mode")


class TestCredentialsResponse(BaseModel):
    """Schema for credential test results."""
    model_config = ConfigDict(from_attributes=True)
    
    valid: bool = Field(..., description="Credentials are valid")
    exchange: Optional[str] = Field(None, description="Exchange name")
    testnet: Optional[bool] = Field(None, description="Testnet mode")
    error: Optional[str] = Field(None, description="Error message if invalid")
    info: Optional[Dict[str, Any]] = Field(None, description="Additional info if valid")


# ==================== BALANCE SCHEMAS ====================

class BalanceRequest(BaseModel):
    """Schema for balance request."""
    exchange: ExchangeType = Field(..., description="Exchange to fetch balances from")
    min_balance: float = Field(default=0.0, ge=0, description="Minimum balance to include")


class TradingCredentials(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    api_key: str = Field(..., description="Binance API key")
    api_secret: str = Field(..., description="Binance API secret")
    testnet: bool = Field(default=True, description="Use testnet instead of mainnet")

class AccountBalance(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    asset: str = Field(..., description="Asset symbol (e.g., BTC, USDT)")
    free: float = Field(..., description="Available balance")
    locked: float = Field(..., description="Locked balance")
    total: float = Field(..., description="Total balance")

class PlaceOrderRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    symbol: str = Field(..., description="Trading pair symbol (e.g., BTCUSDT)")
    side: OrderSide = Field(..., description="Order side")
    type: OrderType = Field(..., description="Order type")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    price: Optional[Decimal] = Field(None, gt=0, description="Order price (required for LIMIT orders)")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key to prevent duplicate orders")

class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    symbol: str = Field(..., description="Trading pair symbol")
    orderId: int = Field(..., description="Order ID")
    clientOrderId: str = Field(..., description="Client order ID")
    transactTime: int = Field(..., description="Transaction time")
    price: str = Field(..., description="Order price")
    origQty: str = Field(..., description="Original quantity")
    executedQty: str = Field(..., description="Executed quantity")
    cummulativeQuoteQty: str = Field(..., description="Cumulative quote quantity")
    status: OrderStatus = Field(..., description="Order status")
    timeInForce: str = Field(..., description="Time in force")
    type: OrderType = Field(..., description="Order type")
    side: OrderSide = Field(..., description="Order side")

class OpenOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    symbol: str
    orderId: int
    clientOrderId: str
    price: str
    origQty: str
    executedQty: str
    cummulativeQuoteQty: str
    status: OrderStatus
    timeInForce: str
    type: OrderType
    side: OrderSide
    stopPrice: str
    icebergQty: str
    time: int
    updateTime: int
    isWorking: bool

class KlineData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    symbol: str = Field(..., description="Trading pair symbol")
    open_time: int = Field(..., description="Kline open time")
    close_time: int = Field(..., description="Kline close time")
    open_price: float = Field(..., description="Open price")
    high_price: float = Field(..., description="High price")
    low_price: float = Field(..., description="Low price")
    close_price: float = Field(..., description="Close price")
    volume: float = Field(..., description="Volume")
    interval: str = Field(..., description="Kline interval")

class TickerData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    symbol: str = Field(..., description="Trading pair symbol")
    price_change: float = Field(..., description="24hr price change")
    price_change_percent: float = Field(..., description="24hr price change percent")
    weighted_avg_price: float = Field(..., description="Weighted average price")
    prev_close_price: float = Field(..., description="Previous close price")
    last_price: float = Field(..., description="Last price")
    bid_price: float = Field(..., description="Best bid price")
    ask_price: float = Field(..., description="Best ask price")
    open_price: float = Field(..., description="Open price")
    high_price: float = Field(..., description="High price")
    low_price: float = Field(..., description="Low price")
    volume: float = Field(..., description="Volume")
    quote_volume: float = Field(..., description="Quote volume")
    open_time: int = Field(..., description="Open time")
    close_time: int = Field(..., description="Close time")
    count: int = Field(..., description="Trade count")

class UserStreamData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    event_type: str = Field(..., description="Event type")
    event_time: int = Field(..., description="Event time")
    data: Dict[str, Any] = Field(..., description="Event data")

class RealTradeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    bot_instance_id: int = Field(..., description="Bot instance ID")
    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(..., description="Order type")
    quantity: float = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(None, gt=0, description="Order price")
    binance_order_id: Optional[int] = Field(None, description="Binance order ID")
    status: OrderStatus = Field(default=OrderStatus.NEW, description="Order status")

class RealTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    bot_instance_id: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    binance_order_id: Optional[int]
    status: OrderStatus
    created_at: datetime
    updated_at: Optional[datetime]

class TradingBotConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    bot_id: int = Field(..., description="Bot ID")
    symbol: str = Field(..., description="Trading pair symbol")
    api_key: str = Field(..., description="Binance API key")
    api_secret: str = Field(..., description="Binance API secret")
    testnet: bool = Field(default=True, description="Use testnet")
    auto_trade: bool = Field(default=False, description="Enable auto trading")
    max_position_size: float = Field(default=0.01, gt=0, description="Maximum position size")
    stop_loss_percent: Optional[float] = Field(None, gt=0, le=100, description="Stop loss percentage")
    take_profit_percent: Optional[float] = Field(None, gt=0, description="Take profit percentage")

class RealTimeData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    type: str = Field(..., description="Data type (kline, ticker, user_stream)")
    symbol: str = Field(..., description="Trading pair symbol")
    data: Dict[str, Any] = Field(..., description="Real-time data")
    timestamp: int = Field(..., description="Timestamp")

class TradingSessionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    bot_instance_id: int = Field(..., description="Bot instance ID")
    symbol: str = Field(..., description="Trading pair symbol")
    initial_balance: float = Field(..., gt=0, description="Initial balance")
    api_key: str = Field(..., description="Binance API key")
    api_secret: str = Field(..., description="Binance API secret")
    testnet: bool = Field(default=True, description="Use testnet")

class TradingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    bot_instance_id: int
    symbol: str
    initial_balance: float
    current_balance: float
    total_trades: int
    profitable_trades: int
    total_pnl: float
    max_drawdown: float
    is_active: bool
    started_at: datetime
    ended_at: Optional[datetime]