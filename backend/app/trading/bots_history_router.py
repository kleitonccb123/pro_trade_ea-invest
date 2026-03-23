"""
Bot Instance History Router — DOC-10 Etapa 10

Exposes:
  GET /api/trading/bots/{bot_instance_id}/trades?page=1&limit=50
  GET /api/trading/bots/{bot_instance_id}/status

Reads from the ``bot_trades`` collection written by the engine worker and
returns a paginated list of closed trade records plus a summary aggregate.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.user_helpers import get_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trading/bots", tags=["📊 Bot History"])


# ── Response models ───────────────────────────────────────────────────────────


class TradeHistoryItem(BaseModel):
    trade_id: str
    bot_instance_id: str
    pair: str
    entry_timestamp: Optional[datetime]
    exit_timestamp: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    capital_usdt: float
    pnl_net_usdt: Optional[float]
    roi_pct: Optional[float]
    exit_reason: Optional[str]
    holding_minutes: Optional[int]
    entry_fee_usdt: float
    exit_fee_usdt: float
    total_fees_usdt: float
    status: str


class TradeSummary(BaseModel):
    total_trades: int
    closed_trades: int
    open_trades: int
    total_pnl_usdt: float
    win_rate: float
    avg_holding_minutes: float
    total_fees_usdt: float
    roi_pct: float
    max_drawdown_pct: float


class TradeHistoryResponse(BaseModel):
    trades: List[TradeHistoryItem]
    total_trades: int
    page: int
    pages: int
    summary: TradeSummary


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_trade(doc: dict) -> TradeHistoryItem:
    entry_fee = float(doc.get("entry_fee_usdt") or doc.get("fee_usdt") or 0)
    exit_fee = float(doc.get("exit_fee_usdt") or 0)
    pnl = doc.get("pnl_net_usdt")
    capital = float(doc.get("total_usdt") or doc.get("capital_usdt") or 0)
    roi = None
    if pnl is not None and capital and capital > 0:
        roi = round(pnl / capital * 100, 4)
    return TradeHistoryItem(
        trade_id=str(doc.get("_id", "")),
        bot_instance_id=str(doc.get("bot_instance_id", "")),
        pair=str(doc.get("symbol") or doc.get("pair") or ""),
        entry_timestamp=doc.get("entry_timestamp") or doc.get("created_at"),
        exit_timestamp=doc.get("exit_timestamp"),
        entry_price=float(doc.get("entry_price") or doc.get("executed_price") or 0),
        exit_price=doc.get("exit_price"),
        capital_usdt=capital,
        pnl_net_usdt=pnl,
        roi_pct=roi,
        exit_reason=doc.get("exit_reason"),
        holding_minutes=doc.get("holding_minutes"),
        entry_fee_usdt=entry_fee,
        exit_fee_usdt=exit_fee,
        total_fees_usdt=round(entry_fee + exit_fee, 6),
        status=str(doc.get("status") or "open"),
    )


def _compute_summary(docs: List[dict], bot_instance_id: str, db_total: int) -> TradeSummary:
    """Aggregate summary over ALL closed trades for this instance (full scan)."""
    total_pnl = 0.0
    total_fees = 0.0
    holding_sum = 0
    wins = 0
    closed = 0
    open_ = 0
    peak = 0.0
    running_pnl = 0.0
    max_dd = 0.0
    initial_capital: Optional[float] = None

    for doc in docs:
        st = str(doc.get("status") or "open")
        cap = float(doc.get("total_usdt") or doc.get("capital_usdt") or 0)
        if initial_capital is None and cap > 0:
            initial_capital = cap

        if st == "closed":
            closed += 1
            pnl = float(doc.get("pnl_net_usdt") or 0)
            fee_e = float(doc.get("entry_fee_usdt") or doc.get("fee_usdt") or 0)
            fee_x = float(doc.get("exit_fee_usdt") or 0)
            total_pnl += pnl
            total_fees += fee_e + fee_x
            holding_sum += int(doc.get("holding_minutes") or 0)
            if pnl >= 0:
                wins += 1
            # Drawdown: track running equity curve
            running_pnl += pnl
            if running_pnl > peak:
                peak = running_pnl
            dd = (peak - running_pnl) / max(initial_capital or 1, 1) * 100
            if dd > max_dd:
                max_dd = dd
        else:
            open_ += 1

    win_rate = round(wins / closed * 100, 2) if closed else 0.0
    avg_holding = round(holding_sum / closed, 1) if closed else 0.0
    roi_pct = round(total_pnl / max(initial_capital or 1, 1) * 100, 4)

    return TradeSummary(
        total_trades=db_total,
        closed_trades=closed,
        open_trades=open_,
        total_pnl_usdt=round(total_pnl, 6),
        win_rate=win_rate,
        avg_holding_minutes=avg_holding,
        total_fees_usdt=round(total_fees, 6),
        roi_pct=roi_pct,
        max_drawdown_pct=round(max_dd, 4),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/{bot_instance_id}/trades",
    response_model=TradeHistoryResponse,
    summary="Histórico de trades de uma instância de bot",
)
async def get_bot_trades(
    bot_instance_id: str,
    page: int = Query(1, ge=1, description="Página (1-based)"),
    limit: int = Query(50, ge=1, le=200, description="Registros por página"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por status: open | closed"),
    current_user: dict = Depends(get_current_user),
):
    """
    Returns paginated trade history for a specific bot instance.

    The response also includes an aggregate ``summary`` field covering ALL
    closed trades (not just the current page) for this instance.

    Access is restricted to the owner of the bot instance.
    """
    db = get_db()
    user_id = get_user_id(current_user)

    # ── Ownership check ────────────────────────────────────────────────────────
    try:
        instance = await db["user_bot_instances"].find_one(
            {"_id": ObjectId(bot_instance_id)}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="bot_instance_id inválido")

    if not instance:
        raise HTTPException(status_code=404, detail="Instância de bot não encontrada")

    if str(instance.get("user_id", "")) != user_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    # ── Build query ────────────────────────────────────────────────────────────
    query: Dict[str, Any] = {"bot_instance_id": bot_instance_id}
    if status_filter in ("open", "closed"):
        query["status"] = status_filter

    # ── Total count ────────────────────────────────────────────────────────────
    total = await db["bot_trades"].count_documents(query)
    pages = max(1, math.ceil(total / limit))

    # ── Paginated page ────────────────────────────────────────────────────────
    skip = (page - 1) * limit
    cursor = (
        db["bot_trades"]
        .find(query)
        .sort("entry_timestamp", -1)
        .skip(skip)
        .limit(limit)
    )
    page_docs = await cursor.to_list(length=limit)

    # ── Full closed trades for summary (without pagination) ───────────────────
    all_cursor = db["bot_trades"].find(
        {"bot_instance_id": bot_instance_id}
    ).sort("entry_timestamp", 1)
    all_docs = await all_cursor.to_list(length=None)

    return TradeHistoryResponse(
        trades=[_parse_trade(d) for d in page_docs],
        total_trades=total,
        page=page,
        pages=pages,
        summary=_compute_summary(all_docs, bot_instance_id, total),
    )


@router.get(
    "/{bot_instance_id}/status",
    summary="Status atual de uma instância de bot",
)
async def get_bot_instance_status(
    bot_instance_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the current status, open position and uptime of a bot instance.
    Used by the frontend polling loop (DOC-10 Step 5 timeline).
    """
    db = get_db()
    user_id = get_user_id(current_user)

    try:
        instance = await db["user_bot_instances"].find_one(
            {"_id": ObjectId(bot_instance_id)}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="bot_instance_id inválido")

    if not instance:
        raise HTTPException(status_code=404, detail="Instância de bot não encontrada")

    if str(instance.get("user_id", "")) != user_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    started_at: Optional[datetime] = instance.get("started_at")
    uptime_seconds: Optional[int] = None
    if started_at:
        uptime_seconds = int(
            (datetime.now(timezone.utc) - started_at.replace(tzinfo=timezone.utc)
             if started_at.tzinfo is None else
             datetime.now(timezone.utc) - started_at
             ).total_seconds()
        )

    metrics = instance.get("metrics") or {}

    return {
        "bot_instance_id": bot_instance_id,
        "status": instance.get("status", "unknown"),
        "robot_id": instance.get("robot_id"),
        "pair": instance.get("pair") or instance.get("symbol"),
        "timeframe": instance.get("timeframe"),
        "capital_usdt": instance.get("capital_usdt"),
        "current_position": instance.get("current_position"),
        "started_at": started_at,
        "stopped_at": instance.get("stopped_at"),
        "uptime_seconds": uptime_seconds,
        "metrics": {
            "total_pnl_usdt": metrics.get("total_pnl_usdt", 0.0),
            "total_trades": metrics.get("total_trades", 0),
            "winning_trades": metrics.get("winning_trades", 0),
            "win_rate": round(
                metrics.get("winning_trades", 0)
                / max(metrics.get("total_trades", 1), 1)
                * 100,
                2,
            ),
        },
        "last_heartbeat": instance.get("last_heartbeat"),
        "error_message": instance.get("error_message"),
    }


