"""
Database Models - MongoDB schemas for bots, orders, positions, and trades.

Using Pydantic v2 for validation with MongoDB compatibility.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from bson import ObjectId


# ============================================================================
# Enums
# ============================================================================

class BotStatus(str, Enum):
    """Bot execution status."""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    PAUSED = "paused"


class OrderStatus(str, Enum):
    """Order execution status."""
    PENDING = "pending"          # Waiting to be sent to exchange
    OPEN = "open"                # Sent and accepted by exchange
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"


class OrderSide(str, Enum):
    """Order side - buy or sell."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type - market or limit."""
    MARKET = "market"
    LIMIT = "limit"


class PositionStatus(str, Enum):
    """Position status."""
    OPENING = "opening"          # Orders being placed
    OPEN = "open"                # Position established
    CLOSING = "closing"          # Close orders being placed
    CLOSED = "closed"            # Position closed


# ============================================================================
# PyObjectId - For MongoDB ID serialization
# ============================================================================

class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2."""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        return core_schema.with_info_plain_validator_function(cls.validate)
    
    @classmethod
    def validate(cls, v, _info=None):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            return ObjectId(v)
        raise TypeError(f"Invalid ObjectId: {v}")
    
    def __repr__(self):
        return f"ObjectId('{str(self)}')"


# ============================================================================
# Bot Models
# ============================================================================

class BotConfig(BaseModel):
    """Strategy-specific configuration."""
    strategy_type: str  # sma_crossover, rsi, grid, etc
    
    # SMA Crossover params
    fast_ma: Optional[int] = 20
    slow_ma: Optional[int] = 50
    
    # RSI params
    rsi_period: Optional[int] = 14
    rsi_overbought: Optional[int] = 70
    rsi_oversold: Optional[int] = 30
    
    # Grid strategy params
    grid_levels: Optional[int] = 10
    grid_spacing: Optional[Decimal] = None
    
    # Additional custom config
    custom: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Bot(BaseModel):
    """Trading bot configuration and state."""
    model_config = ConfigDict(populate_by_name=True)
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    name: str
    exchange: str  # kucoin, binance
    account_id: str  # Exchange account UID
    symbol: str  # BTC-USDT
    
    strategy_type: str
    config: BotConfig
    
    # Risk management
    risk_config: Optional[Dict[str, Decimal]] = Field(default_factory=dict)
    
    # Bot state
    status: BotStatus = BotStatus.STOPPED
    enabled: bool = True
    
    # Statistics
    trades_count: int = 0
    total_pnl: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error_message: Optional[str] = None


# ============================================================================
# Order Models
# ============================================================================

class OrderExecution(BaseModel):
    """Single order execution record."""
    exchange_order_id: str
    filled_size: Decimal
    fill_price: Decimal
    fee: Decimal
    fee_currency: str
    executed_at: datetime


class Order(BaseModel):
    """Trading order record."""
    model_config = ConfigDict(populate_by_name=True)
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    bot_id: PyObjectId
    
    symbol: str
    side: OrderSide
    order_type: OrderType
    
    # Order specs
    size: Decimal
    price: Optional[Decimal] = None  # For limit orders
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    
    # Execution state
    status: OrderStatus = OrderStatus.PENDING
    filled_size: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    total_fee: Decimal = Decimal("0")
    
    # Exchange tracking
    exchange_order_id: Optional[str] = None
    client_oid: str  # For idempotency
    
    # Execution history
    executions: List[OrderExecution] = Field(default_factory=list)
    
    # Position tracking
    associated_position_id: Optional[PyObjectId] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Metadata
    retry_count: int = 0
    last_error: Optional[str] = None


# ============================================================================
# Position Models
# ============================================================================

class Position(BaseModel):
    """Open trading position."""
    model_config = ConfigDict(populate_by_name=True)
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    bot_id: PyObjectId
    
    symbol: str
    side: OrderSide  # LONG (buy) or SHORT (sell)
    
    # Position details
    size: Decimal  # Total amount held
    entry_price: Decimal
    entry_cost: Decimal  # size * entry_price
    
    # Linked orders
    entry_order_id: PyObjectId  # The order that opened this
    exit_order_id: Optional[PyObjectId] = None  # The order that closed this
    
    # Current state
    status: PositionStatus = PositionStatus.OPENING
    
    # PnL calculation values
    current_price: Optional[Decimal] = None  # Last market price
    unrealized_pnl: Optional[Decimal] = None  # current price - entry price
    unrealized_pnl_percent: Optional[Decimal] = None
    
    realized_pnl: Optional[Decimal] = None  # When position closed
    
    # Risk parameters
    take_profit_price: Optional[Decimal] = None
    stop_loss_price: Optional[Decimal] = None
    
    # Timestamps
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    last_price_update: Optional[datetime] = None


# ============================================================================
# Trade/Execution Models
# ============================================================================

class Trade(BaseModel):
    """Completed trade execution (filled order or partial fill)."""
    model_config = ConfigDict(populate_by_name=True)
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    bot_id: PyObjectId
    order_id: PyObjectId
    position_id: Optional[PyObjectId] = None
    
    symbol: str
    side: OrderSide
    
    # Execution details
    size: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str
    
    # Exchange info
    exchange_trade_id: str
    exchange_order_id: str
    
    # Timestamps
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Response Models (for FastAPI)
# ============================================================================

class BotResponse(BaseModel):
    """Bot response for API."""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str = Field(alias="_id")
    user_id: str
    name: str
    exchange: str
    symbol: str
    strategy_type: str
    status: str
    enabled: bool
    trades_count: int
    total_pnl: str
    win_rate: str
    created_at: str
    updated_at: str


class OrderResponse(BaseModel):
    """Order response for API."""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str = Field(alias="_id")
    bot_id: str
    symbol: str
    side: str
    order_type: str
    size: str
    price: Optional[str]
    status: str
    filled_size: str
    fee: str
    created_at: str


class PositionResponse(BaseModel):
    """Position response for API."""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str = Field(alias="_id")
    bot_id: str
    symbol: str
    side: str
    size: str
    entry_price: str
    current_price: Optional[str]
    unrealized_pnl: Optional[str]
    unrealized_pnl_percent: Optional[str]
    opened_at: str
