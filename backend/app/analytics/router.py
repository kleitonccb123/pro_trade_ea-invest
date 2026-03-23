from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse

from app.analytics.service import AnalyticsService
from app.analytics.advanced_metrics import (
    compute_advanced_metrics,
    compute_bot_comparison,
    compute_strategy_metrics,
    compute_heatmap,
    compute_correlation_matrix,
    filter_trades,
)
from app.analytics import schemas
from app.auth.dependencies import get_current_user
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])
service = AnalyticsService()


@router.get("/dashboard/summary", response_model=schemas.SummaryResponse)
async def dashboard_summary(current_user: dict = Depends(get_current_user)):
    user_id = str(current_user["_id"])
    try:
        result = await service.summary(user_id)
        if result is None:
            # Return a default summary if None
            from app.core.config import settings
            return schemas.SummaryResponse(
                initial_balance=settings.initial_balance,
                balance=settings.initial_balance,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                daily_pnl=0.0,
                daily_trades=0,
                num_trades=0,
                win_rate=0.0,
                max_drawdown=0.0,
            )
        return result
    except Exception as e:
        # Log the error but return a default summary
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting analytics summary: {e}")
        from app.core.config import settings
        return schemas.SummaryResponse(
            initial_balance=settings.initial_balance,
            balance=settings.initial_balance,
            total_pnl=0.0,
            total_pnl_percent=0.0,
            daily_pnl=0.0,
            daily_trades=0,
            num_trades=0,
            win_rate=0.0,
            max_drawdown=0.0,
        )


@router.get("/pnl", response_model=schemas.PerformanceResponse)
async def pnl(current_user: dict = Depends(get_current_user)):
    return await service.pnl_timeseries()


@router.get("/performance")
async def performance(current_user: dict = Depends(get_current_user)):
    return await service.performance()


# ── PEND-06: Advanced Performance Dashboard ──────────────────────────────────


@router.get(
    "/advanced-metrics",
    response_model=schemas.AdvancedMetricsResponse,
)
async def advanced_metrics(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol (e.g. BTC-USDT)"),
    bot_id: Optional[str] = Query(None, description="Filter by bot/instance ID"),
    strategy: Optional[str] = Query(None, description="Filter by strategy_name"),
):
    """Return Sharpe, Sortino, Calmar, Profit Factor, drawdown, win-rate by period, etc."""
    user_id = str(current_user["_id"])
    db = get_db()

    trades = await db["simulated_trades"].find({"user_id": user_id}).to_list(None)
    trades = filter_trades(
        trades,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, eod=True),
        symbol=symbol,
        bot_id=bot_id,
    )
    if strategy:
        sl = strategy.lower()
        trades = [
            t for t in trades
            if (t.get("strategy_name") or t.get("strategy") or "").lower() == sl
        ]

    from app.core.config import settings
    result = compute_advanced_metrics(trades, settings.initial_balance)
    return schemas.AdvancedMetricsResponse(**result)


@router.get(
    "/bot-comparison",
    response_model=List[schemas.BotComparisonItem],
)
async def bot_comparison(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
):
    """Side-by-side comparison of all user bots with key metrics."""
    user_id = str(current_user["_id"])
    db = get_db()

    trades = await db["simulated_trades"].find({"user_id": user_id}).to_list(None)
    trades = filter_trades(
        trades,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, eod=True),
    )

    from app.core.config import settings
    rows = compute_bot_comparison(trades, settings.initial_balance)
    return [schemas.BotComparisonItem(**r) for r in rows]


def _parse_date(val: Optional[str], *, eod: bool = False) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if eod and dt.hour == 0 and dt.minute == 0:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt
    except ValueError:
        raise HTTPException(400, f"Data inválida: {val} (use YYYY-MM-DD)")


# ── PEND-12: Strategy / Heatmap / Correlation ──────────────────────────────────


@router.get(
    "/by-strategy",
    response_model=List[schemas.StrategyMetricsItem],
)
async def by_strategy(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
):
    """Metrics grouped by strategy_name: PnL, win rate, Sharpe, drawdown, etc."""
    user_id = str(current_user["_id"])
    db = get_db()

    trades = await db["simulated_trades"].find({"user_id": user_id}).to_list(None)
    trades = filter_trades(
        trades,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, eod=True),
        symbol=symbol,
        bot_id=bot_id,
    )

    from app.core.config import settings
    rows = compute_strategy_metrics(trades, settings.initial_balance)
    return [schemas.StrategyMetricsItem(**r) for r in rows]


@router.get(
    "/heatmap",
    response_model=schemas.HeatmapResponse,
)
async def performance_heatmap(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    strategy: Optional[str] = Query(None, description="Filter by strategy_name"),
):
    """7×24 performance heatmap: avg PnL grouped by day-of-week × hour-of-day."""
    user_id = str(current_user["_id"])
    db = get_db()

    trades = await db["simulated_trades"].find({"user_id": user_id}).to_list(None)
    trades = filter_trades(
        trades,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, eod=True),
        symbol=symbol,
        bot_id=bot_id,
    )
    if strategy:
        sl = strategy.lower()
        trades = [
            t for t in trades
            if (t.get("strategy_name") or t.get("strategy") or "").lower() == sl
        ]

    data = compute_heatmap(trades)
    return schemas.HeatmapResponse(**data)


@router.get(
    "/correlation",
    response_model=schemas.CorrelationMatrixResponse,
)
async def bot_correlation(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
):
    """Pearson correlation matrix of daily returns between bots."""
    user_id = str(current_user["_id"])
    db = get_db()

    trades = await db["simulated_trades"].find({"user_id": user_id}).to_list(None)
    trades = filter_trades(
        trades,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, eod=True),
    )

    data = compute_correlation_matrix(trades)
    return schemas.CorrelationMatrixResponse(**data)


@router.get("/bots/{instance_id}/status", response_model=schemas.BotStatusSchema)
async def bot_status(instance_id: int):
    try:
        return await service.bot_status(instance_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Instance not found")


@router.get("/bots/{instance_id}/trades", response_model=list[schemas.TradeSchema])
async def bot_trades(instance_id: int):
    return await service.trades_for_instance(instance_id)


@router.get("/export/csv")
async def export_trades_csv(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
):
    """
    Export user's trade history as CSV file.
    Optional date filters via query params.
    """
    user_id = str(current_user.get("id") or current_user.get("_id"))
    db = get_db()

    query: dict = {"user_id": user_id}
    if start_date or end_date:
        date_filter: dict = {}
        if start_date:
            try:
                date_filter["$gte"] = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(400, "start_date inválido (use YYYY-MM-DD)")
        if end_date:
            try:
                date_filter["$lte"] = datetime.fromisoformat(end_date + "T23:59:59")
            except ValueError:
                raise HTTPException(400, "end_date inválido (use YYYY-MM-DD)")
        if date_filter:
            query["created_at"] = date_filter

    trades = await db.bot_trades.find(query).sort("created_at", -1).to_list(length=10000)

    # Build CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Data", "Bot", "Símbolo", "Lado", "Preço",
        "Quantidade", "Total (USDT)", "Taxa", "PnL", "Status",
    ])

    for t in trades:
        writer.writerow([
            t.get("created_at", "").isoformat() if isinstance(t.get("created_at"), datetime) else str(t.get("created_at", "")),
            t.get("bot_id", ""),
            t.get("symbol", ""),
            t.get("side", ""),
            t.get("price", ""),
            t.get("quantity", ""),
            t.get("total_usdt", ""),
            t.get("fee", ""),
            t.get("pnl", ""),
            t.get("status", ""),
        ])

    output.seek(0)
    filename = f"trades_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── PEND-08: PDF Export Reports ──────────────────────────────────────────────


@router.get("/export/pdf")
async def export_performance_pdf(
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
):
    """Export a professional PDF performance report with metrics and trade history."""
    from app.analytics.pdf_report import generate_performance_pdf
    from app.core.config import settings

    user_id = str(current_user.get("id") or current_user.get("_id"))
    user_email = current_user.get("email", user_id)
    db = get_db()

    # Fetch trades (same source as advanced-metrics)
    all_trades = await db["simulated_trades"].find({"user_id": user_id}).to_list(None)
    trades = filter_trades(
        all_trades,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date, eod=True),
        symbol=symbol,
        bot_id=bot_id,
    )

    metrics = compute_advanced_metrics(trades, settings.initial_balance)
    bots = compute_bot_comparison(trades, settings.initial_balance)

    pdf_bytes = generate_performance_pdf(
        user_email=user_email,
        trades=trades,
        metrics=metrics,
        bots=bots,
        start_date=start_date,
        end_date=end_date,
    )

    filename = f"performance_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf/fiscal")
async def export_fiscal_pdf(
    current_user: dict = Depends(get_current_user),
    year: int = Query(
        default=None,
        description="Tax year (defaults to current year)",
    ),
):
    """Export a fiscal / tax gains report PDF grouped by month for a given year."""
    from app.analytics.pdf_report import generate_fiscal_pdf

    user_id = str(current_user.get("id") or current_user.get("_id"))
    user_email = current_user.get("email", user_id)
    db = get_db()

    if year is None:
        year = datetime.utcnow().year

    # Fetch all trades for the year
    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31, 23, 59, 59)

    trades = (
        await db["simulated_trades"]
        .find({
            "user_id": user_id,
            "created_at": {"$gte": start, "$lte": end},
        })
        .sort("created_at", 1)
        .to_list(None)
    )

    pdf_bytes = generate_fiscal_pdf(
        user_email=user_email,
        trades=trades,
        year=year,
    )

    filename = f"fiscal_{user_id}_{year}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── PEND-15: Monte Carlo Simulation ─────────────────────────────────────────


@router.post("/simulate/montecarlo", response_model=schemas.MonteCarloResponse)
async def simulate_montecarlo(
    req: schemas.MonteCarloRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Run a Monte Carlo simulation using Geometric Brownian Motion.

    Simulates ``n_simulations`` equity paths over ``horizon_months`` months,
    each starting at ``initial_capital``.  Returns the P10/P50/P90 percentile
    paths and summary statistics so the frontend can draw a probability cone.
    """
    import math
    import random

    # ── Input validation ────────────────────────────────────────────────────
    if not (1 <= req.n_simulations <= 10_000):
        raise HTTPException(status_code=422, detail="n_simulations must be between 1 and 10 000")
    if not (1 <= req.horizon_months <= 120):
        raise HTTPException(status_code=422, detail="horizon_months must be between 1 and 120")
    if req.initial_capital <= 0:
        raise HTTPException(status_code=422, detail="initial_capital must be positive")

    # ── GBM parameters (daily steps, 30 trading days per month) ─────────────
    days_per_month = 30
    total_days = req.horizon_months * days_per_month
    mu_daily = (req.monthly_return_pct / 100.0) / days_per_month
    sigma_daily = (req.annual_volatility_pct / 100.0) / math.sqrt(252)
    dt = 1.0  # one day per step

    # ── Run simulations ──────────────────────────────────────────────────────
    # month_buckets[m] keeps the portfolio value at end of month m for every sim
    month_buckets: list[list[float]] = [[] for _ in range(req.horizon_months + 1)]

    for _ in range(req.n_simulations):
        s = req.initial_capital
        month_buckets[0].append(s)
        for day in range(1, total_days + 1):
            z = random.gauss(0.0, 1.0)
            # GBM: S_{t+1} = S_t * exp((mu - sigma²/2)*dt + sigma*sqrt(dt)*Z)
            s *= math.exp(
                (mu_daily - 0.5 * sigma_daily ** 2) * dt
                + sigma_daily * math.sqrt(dt) * z
            )
            if day % days_per_month == 0:
                month_buckets[day // days_per_month].append(s)

    # ── Percentile helper ────────────────────────────────────────────────────
    def _pct(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, min(int(len(sorted_vals) * p / 100.0), len(sorted_vals) - 1))
        return round(sorted_vals[idx], 4)

    # ── Build per-month percentile path ────────────────────────────────────
    paths = [
        schemas.MonteCarloPathPoint(
            month=m,
            p10=_pct(month_buckets[m], 10),
            p50=_pct(month_buckets[m], 50),
            p90=_pct(month_buckets[m], 90),
        )
        for m in range(req.horizon_months + 1)
    ]

    # Final values (last day of last month)
    final_values = month_buckets[req.horizon_months]
    prob_profit = (
        sum(1 for v in final_values if v > req.initial_capital) / len(final_values) * 100
        if final_values
        else 0.0
    )

    return schemas.MonteCarloResponse(
        paths=paths,
        final_p10=paths[-1].p10,
        final_p50=paths[-1].p50,
        final_p90=paths[-1].p90,
        prob_profit_pct=round(prob_profit, 1),
        initial_capital=req.initial_capital,
        n_simulations=req.n_simulations,
        horizon_months=req.horizon_months,
    )


@router.get("/sentiment/{symbol}")
async def get_market_sentiment(
    symbol: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get AI-powered market sentiment analysis for a symbol.

    Uses Groq LLM when GROQ_API_KEY is configured, otherwise returns
    a technical-indicator-based projection.
    """
    import aiohttp
    from app.analytics.ai import analyze_sentiment_ai, project_market_scenario

    # Fetch basic market data from KuCoin for context
    market_data = {}
    kucoin_symbol = symbol.upper()
    if "-" not in kucoin_symbol and "USDT" in kucoin_symbol:
        kucoin_symbol = kucoin_symbol.replace("USDT", "-USDT")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.kucoin.com/api/v1/market/stats?symbol={kucoin_symbol}",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    data = (await resp.json()).get("data", {})
                    market_data["price"] = float(data.get("last", 0))
                    change = float(data.get("changeRate", 0)) * 100
                    market_data["change_24h"] = round(change, 2)
                    market_data["volume_24h"] = float(data.get("vol", 0))
    except Exception as e:
        logger.warning(f"Failed to fetch market stats for {symbol}: {e}")

    # Run AI sentiment analysis
    sentiment = await analyze_sentiment_ai(symbol, market_data)

    # Also get a technical projection
    projection = project_market_scenario(symbol, market_data)

    return {
        "symbol": symbol,
        "sentiment": sentiment,
        "projection": projection,
        "market_data": market_data,
    }
