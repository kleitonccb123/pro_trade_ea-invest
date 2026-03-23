"""
Pydantic models for the trading engine — DOC_02.

Collections covered:
  user_bot_instances      → UserBotInstance
  bot_trades              → BotTrade
  bot_performance_snapshots → BotPerformanceSnapshot
  bot_execution_logs      → (dict-based, no dedicated model needed)
  bot_locks               → (dict-based, managed by repository)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class BotStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED  = "paused"
    STOPPED = "stopped"
    ERROR   = "error"


class TradeSide(str, Enum):
    BUY  = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    PENDING   = "pending"
    FILLED    = "filled"
    CANCELLED = "cancelled"
    REJECTED  = "rejected"


class SnapshotType(str, Enum):
    DAILY      = "daily"
    WEEKLY     = "weekly"
    RANKING_15D = "ranking_15d"


# ── Sub-models ─────────────────────────────────────────────────────────────────

# DOC-K05: Native TP/SL configuration models

class TakeProfitConfig(BaseModel):
    """Configuration for Take Profit orders."""
    mode: Literal["percentage", "fixed_price"] = "percentage"
    value: float = Field(..., gt=0, description="% gain or absolute price")
    use_native_order: bool = Field(
        False,
        description=(
            "If True, place a native limit sell on KuCoin immediately after "
            "entry fill. Order lives on the exchange server — survives engine restart."
        ),
    )


class StopLossConfig(BaseModel):
    """Configuration for Stop Loss orders."""
    mode: Literal["percentage", "fixed_price", "trailing"] = "percentage"
    value: float = Field(..., gt=0, description="% loss or absolute price")
    trailing_callback_pct: Optional[float] = Field(
        None, ge=0.1, description="Trailing callback % (mode=trailing only)"
    )
    use_native_order: bool = Field(
        False,
        description=(
            "If True, place a native stop-limit on KuCoin immediately after "
            "entry fill. Order lives on the exchange server — survives engine restart."
        ),
    )


class BotConfiguration(BaseModel):
    pair: str = Field(
        ...,
        pattern=r"^[A-Z]+-[A-Z]+$",
        description="Par de trading KuCoin, ex: BTC-USDT",
    )
    capital_usdt: float = Field(..., gt=10.0, le=100_000.0)
    timeframe: str = Field(
        "1h",
        pattern=r"^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d|1w)$",
    )
    stop_loss_pct: float = Field(5.0, ge=0.5, le=50.0)
    take_profit_pct: float = Field(15.0, ge=1.0, le=200.0)
    max_daily_loss_usdt: float = Field(50.0, gt=0)
    strategy_params: Dict[str, Any] = Field(default_factory=dict)

    # DOC-K05: Rich TP/SL config (optional — backward-compatible with pct fields)
    take_profit: Optional[TakeProfitConfig] = None
    stop_loss: Optional[StopLossConfig] = None


class BotMetrics(BaseModel):
    total_pnl_usdt: float = 0.0
    unrealized_pnl_usdt: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    largest_win_usdt: float = 0.0
    largest_loss_usdt: float = 0.0
    total_fees_paid_usdt: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    initial_capital_usdt: float = 0.0
    current_capital_usdt: float = 0.0

    def recompute_derived(self) -> None:
        """Recompute win_rate and profit_factor from raw counters."""
        total = self.winning_trades + self.losing_trades
        if total > 0:
            self.win_rate = round(self.winning_trades / total * 100, 2)
        gross_wins  = max(self.total_pnl_usdt, 0)
        gross_losses = abs(min(self.total_pnl_usdt, 0)) or 1
        self.profit_factor = round(gross_wins / gross_losses, 4)


# ── Main models ────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserBotInstance(BaseModel):
    """Maps to the `user_bot_instances` collection."""

    id: Optional[str] = None
    user_id: str
    robot_id: str
    robot_name: str
    robot_type: str
    configuration: BotConfiguration
    status: BotStatus = BotStatus.PENDING
    stop_reason: Optional[str] = None
    error_message: Optional[str] = None
    metrics: BotMetrics = Field(default_factory=BotMetrics)
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_trade_at: Optional[datetime] = None
    credentials_id: str = ""
    strategy_state: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def to_mongo(self) -> dict:
        """Return a dict suitable for MongoDB insertion (excludes id)."""
        data = self.model_dump(exclude={"id"})
        # Convert nested enums to their string values
        data["status"] = self.status.value
        if data.get("configuration"):
            # configuration is already a dict via model_dump
            pass
        return data


class BotTrade(BaseModel):
    """Maps to the `bot_trades` collection."""

    id: Optional[str] = None
    bot_instance_id: str
    user_id: str
    robot_id: str
    exchange_order_id: str
    exchange: str = "kucoin"
    symbol: str
    side: TradeSide
    order_type: str = "market"
    requested_quantity: float = 0.0
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    total_usdt: float = 0.0
    fee_usdt: float = 0.0
    fee_currency: str = "USDT"
    slippage_pct: float = 0.0
    realized_pnl_usdt: Optional[float] = None
    matched_buy_order_id: Optional[str] = None
    strategy_reason: str = ""
    market_price_at_signal: float = 0.0
    signal_timestamp: Optional[datetime] = None
    status: TradeStatus = TradeStatus.FILLED
    executed_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)
    exchange_response: Dict[str, Any] = Field(default_factory=dict)


class BotPerformanceSnapshot(BaseModel):
    """Maps to the `bot_performance_snapshots` collection."""

    id: Optional[str] = None
    bot_instance_id: str
    robot_id: str
    user_id: str
    snapshot_date: datetime
    snapshot_type: SnapshotType = SnapshotType.DAILY
    # Period metrics
    period_pnl_usdt: float = 0.0
    period_trades: int = 0
    period_win_rate: float = 0.0
    period_fees_usdt: float = 0.0
    # Cumulative
    cumulative_pnl_usdt: float = 0.0
    cumulative_trades: int = 0
    cumulative_win_rate: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    # Capital
    capital_start_usdt: float = 0.0
    capital_end_usdt: float = 0.0
    roi_pct: float = 0.0
    created_at: datetime = Field(default_factory=_utcnow)


# ── Request / Response models (for FastAPI routes) ─────────────────────────────

class CreateBotInstanceRequest(BaseModel):
    robot_id: str
    robot_name: str
    robot_type: str
    configuration: BotConfiguration
    credentials_id: str


class BotInstanceResponse(BaseModel):
    """Slimmed-down view returned by API endpoints."""

    id: str
    user_id: str
    robot_id: str
    robot_name: str
    robot_type: str
    status: BotStatus
    configuration: BotConfiguration
    metrics: BotMetrics
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    last_heartbeat: Optional[datetime]
    stop_reason: Optional[str]
    error_message: Optional[str]

    @classmethod
    def from_mongo(cls, doc: dict) -> "BotInstanceResponse":
        doc = dict(doc)
        doc["id"] = str(doc.pop("_id", ""))
        return cls(**doc)


class TradeHistoryResponse(BaseModel):
    trades: List[dict]
    total: int
    page: int
    page_size: int
