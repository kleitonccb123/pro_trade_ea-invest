"""
Backtest Router — API endpoints for running and retrieving backtests.

Endpoints:
  POST /api/backtest/run           — Run a new backtest
  GET  /api/backtest/{backtest_id} — Get a specific backtest result
  GET  /api/backtest/strategy/{id} — List backtests for a strategy
  GET  /api/backtest/symbols       — List available trading pairs
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.user_helpers import get_user_id
from app.strategies.backtest import BacktestConfig, BacktestEngine, BacktestResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# Popular trading pairs available on KuCoin
AVAILABLE_SYMBOLS = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "ADA-USDT",
    "DOGE-USDT", "AVAX-USDT", "DOT-USDT", "LINK-USDT", "MATIC-USDT",
    "UNI-USDT", "ATOM-USDT", "LTC-USDT", "FIL-USDT", "APT-USDT",
    "ARB-USDT", "OP-USDT", "NEAR-USDT", "ICP-USDT", "ALGO-USDT",
]


# ── Request / Response models ─────────────────────────────────────────────────

class BacktestRunRequest(BaseModel):
    strategy_id: str
    symbol: str = "BTC-USDT"
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    initial_capital: float = Field(1000.0, ge=100, le=1_000_000)
    short_period: int = Field(9, ge=2, le=200)
    long_period: int = Field(21, ge=5, le=500)
    stop_loss_pct: float = Field(5.0, ge=0.5, le=50.0)
    take_profit_pct: float = Field(10.0, ge=1.0, le=100.0)
    maker_fee_pct: float = Field(0.1, ge=0.0, le=1.0)
    taker_fee_pct: float = Field(0.1, ge=0.0, le=1.0)


class BacktestSummary(BaseModel):
    backtest_id: str
    strategy_id: str
    symbol: str
    initial_capital: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    buy_hold_return_pct: float
    passed: bool
    completed_at: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/symbols")
async def list_symbols():
    """Return list of available trading pairs for backtesting."""
    return {"symbols": AVAILABLE_SYMBOLS}


@router.post("/run", status_code=status.HTTP_201_CREATED)
async def run_backtest(
    req: BacktestRunRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Run a backtest for a strategy with the given parameters.
    Uses real KuCoin historical klines data.
    """
    # Validate symbol
    if req.symbol not in AVAILABLE_SYMBOLS:
        raise HTTPException(400, f"Symbol '{req.symbol}' not available. Use /api/backtest/symbols for list.")

    if req.short_period >= req.long_period:
        raise HTTPException(400, "short_period must be less than long_period")

    # Parse dates
    try:
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

    if end_dt <= start_dt:
        raise HTTPException(400, "end_date must be after start_date")

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    # Verify strategy belongs to user (or is public)
    db = get_db()
    user_id = get_user_id(current_user)
    strategy = await db["strategies"].find_one({"_id": __import__("bson").ObjectId(req.strategy_id)})
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    is_owner = strategy.get("user_id") == user_id
    is_public = strategy.get("is_public", False)
    if not (is_owner or is_public):
        raise HTTPException(403, "No permission to backtest this strategy")

    config = BacktestConfig(
        strategy_id=req.strategy_id,
        version_id="latest",
        symbol=req.symbol,
        start_ts=start_ts,
        end_ts=end_ts,
        initial_capital_usd=req.initial_capital,
        maker_fee_pct=req.maker_fee_pct,
        taker_fee_pct=req.taker_fee_pct,
        parameters={
            "short_period": req.short_period,
            "long_period": req.long_period,
            "stop_loss_pct": req.stop_loss_pct,
            "take_profit_pct": req.take_profit_pct,
        },
    )

    engine = BacktestEngine(db)
    result = await engine.run(config)

    logger.info(
        "Backtest completed user=%s strategy=%s passed=%s trades=%d",
        user_id, req.strategy_id, result.passed, result.metrics.total_trades,
    )

    return result.model_dump()


@router.get("/{backtest_id}")
async def get_backtest_result(
    backtest_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve a specific backtest result by ID."""
    db = get_db()
    engine = BacktestEngine(db)
    result = await engine.get_result(backtest_id)
    if not result:
        raise HTTPException(404, "Backtest result not found")
    return result.model_dump()


@router.get("/strategy/{strategy_id}")
async def list_strategy_backtests(
    strategy_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """List recent backtests for a given strategy."""
    db = get_db()
    engine = BacktestEngine(db)
    results = await engine.list_results(strategy_id, limit=limit)

    summaries = []
    for r in results:
        summaries.append(BacktestSummary(
            backtest_id=r.backtest_id,
            strategy_id=r.strategy_id,
            symbol=r.config.symbol,
            initial_capital=r.config.initial_capital_usd,
            total_return_pct=r.metrics.total_return_pct,
            sharpe_ratio=r.metrics.sharpe_ratio,
            max_drawdown_pct=r.metrics.max_drawdown_pct,
            win_rate=r.metrics.win_rate,
            total_trades=r.metrics.total_trades,
            buy_hold_return_pct=r.buy_hold_return_pct,
            passed=r.passed,
            completed_at=r.completed_at.isoformat(),
        ))

    return {"results": [s.model_dump() for s in summaries]}
