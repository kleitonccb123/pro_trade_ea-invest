"""
engine/trade_models.py — Pydantic models for full trade lifecycle (DOC_05).

TradeRecord represents a complete entry+exit cycle with PnL, fees and slippage.
TradeStatus here tracks trade lifecycle (open/closed), not order status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enumerations ─────────────────────────────────────────────────────────────

class TradeRecordStatus(str, Enum):
    """Lifecycle status of a full entry+exit trade cycle."""
    OPEN             = "open"
    CLOSED           = "closed"
    CANCELLED        = "cancelled"
    PARTIALLY_FILLED = "partially_filled"


class TradeSide(str, Enum):
    BUY  = "buy"
    SELL = "sell"


# ── TradeRecord ───────────────────────────────────────────────────────────────

class TradeRecord(BaseModel):
    """
    Represents a complete entry+exit trade cycle.

    Created when an entry order is filled. Updated (closed) when the
    position is exited via take_profit, stop_loss, manual, or trailing stop.
    """

    bot_instance_id: str
    user_id: str

    # ── Entry ─────────────────────────────────────────────────────────────────
    entry_order_id: str               # order ID on KuCoin
    entry_price: float                # average fill price
    entry_funds: float                # USDT invested (before fee)
    entry_quantity: float             # base asset quantity received
    entry_fee_usdt: float             # fee paid on entry in USDT
    entry_timestamp: datetime

    # ── Exit (None while position is open) ────────────────────────────────────
    exit_order_id: Optional[str]    = None
    exit_price: Optional[float]     = None
    exit_quantity: Optional[float]  = None
    exit_fee_usdt: Optional[float]  = 0.0
    exit_timestamp: Optional[datetime] = None
    exit_reason: Optional[str]      = None   # "take_profit" | "stop_loss" | "manual" | "trailing"

    # ── Slippage ──────────────────────────────────────────────────────────────
    expected_entry_price: Optional[float] = None   # best bid/ask at signal time
    expected_exit_price:  Optional[float] = None
    entry_slippage_pct:   Optional[float] = None   # negative = worse execution
    exit_slippage_pct:    Optional[float] = None

    # ── PnL (populated on close) ──────────────────────────────────────────────
    pnl_gross_usdt: Optional[float] = None   # exit_gross - entry_cost, no fees
    pnl_net_usdt:   Optional[float] = None   # pnl_gross - entry_fee - exit_fee
    pnl_net_pct:    Optional[float] = None   # pnl_net / entry_funds * 100
    roi_pct:        Optional[float] = None   # same as pnl_net_pct (explicit alias)
    holding_minutes: Optional[int]  = None

    status: TradeRecordStatus = TradeRecordStatus.OPEN
    pair: str
    timeframe: str

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("entry_fee_usdt")
    @classmethod
    def fee_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("entry_fee_usdt must be >= 0")
        return v

    @field_validator("entry_quantity")
    @classmethod
    def quantity_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("entry_quantity must be > 0")
        return v

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self.status == TradeRecordStatus.OPEN

    @property
    def total_fees_usdt(self) -> float:
        return (self.entry_fee_usdt or 0.0) + (self.exit_fee_usdt or 0.0)

    def to_mongo(self) -> dict:
        d = self.model_dump()
        for k in ("entry_timestamp", "exit_timestamp"):
            if d.get(k) and isinstance(d[k], datetime):
                d[k] = d[k]
        return d

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}
