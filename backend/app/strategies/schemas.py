from __future__ import annotations

from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional


# Schemas para submiss?o de estrat?gias
class StrategySubmission(BaseModel):
    authorName: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=1, max_length=200)
    whatsapp: str = Field(..., min_length=1, max_length=50)
    strategyName: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1)
    submittedAt: datetime = Field(default_factory=datetime.utcnow)
    expiresAt: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=50))
    id: Optional[str] = None

class CodeValidation(BaseModel):
    code: str

class StrategySubmissionResponse(BaseModel):
    success: bool
    message: str
    strategyId: Optional[str] = None
    expiresAt: Optional[str] = None

class ValidationResponse(BaseModel):
    valid: bool
    error: Optional[str] = None


# Schemas antigos
class StrategyTradeResponse(BaseModel):
    id: int
    entry_price: float
    exit_price: float | None
    quantity: float
    side: str
    pnl: float | None
    pnl_percent: float | None
    entry_time: datetime
    exit_time: datetime | None

    class Config:
        from_attributes = True


class StrategyCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: str | None = Field(None, max_length=500)
    strategy_code: str = Field(..., min_length=10)
    symbol: str | None = Field(None, pattern="^[A-Z]{1,10}USDT$")
    timeframe: str | None = Field(None, pattern="^(1m|5m|15m|30m|1h|4h|1d)$")


class StrategyUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = Field(None, max_length=500)
    strategy_code: str | None = Field(None, min_length=10)
    symbol: str | None = Field(None, pattern="^[A-Z]{1,10}USDT$")
    timeframe: str | None = Field(None, pattern="^(1m|5m|15m|30m|1h|4h|1d)$")


class StrategyResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None
    strategy_code: str
    status: str
    trade_count: int
    total_pnl: float
    win_rate: float | None
    symbol: str | None
    timeframe: str | None
    is_active: bool
    is_publishable: bool
    is_expired: bool
    version: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_db(cls, strategy) -> StrategyResponse:
        return cls(
            id=strategy.id,
            user_id=strategy.user_id,
            name=strategy.name,
            description=strategy.description,
            strategy_code=strategy.strategy_code,
            status=strategy.status,
            trade_count=strategy.trade_count,
            total_pnl=strategy.total_pnl,
            win_rate=strategy.win_rate,
            symbol=strategy.symbol,
            timeframe=strategy.timeframe,
            is_active=strategy.is_active,
            is_publishable=strategy.is_publishable(),
            is_expired=strategy.is_expired(),
            version=strategy.version,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at,
            expires_at=strategy.expires_at,
        )


class StrategyListResponse(BaseModel):
    strategies: list[StrategyResponse]
    total: int


class PublishStrategyResponse(BaseModel):
    id: int
    status: str
    message: str


class StrategyValidationRequest(BaseModel):
    strategy_code: str = Field(..., min_length=10)


class StrategyValidationResponse(BaseModel):
    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class BotInstanceRequest(BaseModel):
    symbol: str = Field(..., pattern="^[A-Z]{1,10}USDT$")
    timeframe: str = Field(..., pattern="^(1m|5m|15m|30m|1h|4h|1d)$")


class BotInstanceResponse(BaseModel):
    id: int
    strategy_id: int
    symbol: str
    timeframe: str
    is_running: bool
    created_at: datetime
    started_at: datetime | None
    stopped_at: datetime | None

    class Config:
        from_attributes = True


class TradeCreateRequest(BaseModel):
    entry_price: float = Field(..., gt=0)
    exit_price: float | None = Field(None, gt=0)
    quantity: float = Field(..., gt=0)
    side: str = Field(..., pattern="^(buy|sell)$")


class TradeResponse(BaseModel):
    id: int
    entry_price: float
    exit_price: float | None
    quantity: float
    side: str
    pnl: float | None
    pnl_percent: float | None
    entry_time: datetime
    exit_time: datetime | None

    class Config:
        from_attributes = True
