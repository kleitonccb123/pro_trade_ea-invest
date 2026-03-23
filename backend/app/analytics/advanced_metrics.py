"""
Advanced Performance Metrics — PEND-06
========================================

Pure calculation functions for risk-adjusted metrics.
Adapted from BacktestEngine._calculate_metrics for live trade data.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


def compute_advanced_metrics(
    trades: List[Dict[str, Any]],
    initial_balance: float,
) -> Dict[str, Any]:
    """Compute all advanced metrics from a list of trade dicts.

    Each trade dict is expected to have at least:
        - pnl (float|None)
        - timestamp (datetime)
        - symbol (str, optional)
        - instance_id / bot_id (str, optional)
        - entry_price, exit_price, quantity (optional, for duration)
    """
    closed = [t for t in trades if t.get("pnl") is not None]

    if not closed:
        return _empty_metrics()

    pnls = [(t.get("pnl") or 0.0) for t in closed]
    total_pnl = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    num_trades = len(closed)
    win_rate = (len(wins) / num_trades) * 100.0

    # ── Equity curve & drawdown ──
    equity_curve: List[float] = []
    running = initial_balance
    peak = running
    max_dd_abs = 0.0
    max_dd_pct = 0.0
    dd_start: Optional[datetime] = None
    max_dd_duration_days = 0
    current_dd_start: Optional[datetime] = None

    for t in closed:
        running += t.get("pnl") or 0.0
        equity_curve.append(running)
        if running > peak:
            peak = running
            if current_dd_start is not None and t.get("timestamp"):
                dur = (t["timestamp"] - current_dd_start).days
                if dur > max_dd_duration_days:
                    max_dd_duration_days = dur
            current_dd_start = None
        else:
            if current_dd_start is None and t.get("timestamp"):
                current_dd_start = t["timestamp"]
            dd_abs = peak - running
            dd_pct = (dd_abs / peak) * 100.0 if peak > 0 else 0.0
            if dd_abs > max_dd_abs:
                max_dd_abs = dd_abs
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

    # Check if still in drawdown at the end
    if current_dd_start is not None and closed[-1].get("timestamp"):
        dur = (closed[-1]["timestamp"] - current_dd_start).days
        if dur > max_dd_duration_days:
            max_dd_duration_days = dur

    # ── Time-based calculations ──
    timestamps = [t["timestamp"] for t in closed if t.get("timestamp")]
    if len(timestamps) >= 2:
        trading_days = max(1, (max(timestamps) - min(timestamps)).days)
    else:
        trading_days = 1

    total_ret_pct = (total_pnl / initial_balance) * 100.0 if initial_balance > 0 else 0.0
    ann_ret_pct = ((1 + total_ret_pct / 100.0) ** (365.0 / trading_days) - 1) * 100.0

    # ── Sharpe Ratio ──
    sharpe = _calc_sharpe(pnls, initial_balance)

    # ── Sortino Ratio ──
    sortino = _calc_sortino(pnls, initial_balance)

    # ── Profit Factor ──
    gross_wins = sum(wins)
    gross_losses = abs(sum(losses))
    profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else 0.0

    # ── Calmar Ratio ──
    calmar = (ann_ret_pct / max_dd_pct) if max_dd_pct > 0 else 0.0

    # ── Average trade stats ──
    avg_win = (gross_wins / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    best_trade = max(pnls)
    worst_trade = min(pnls)

    # ── Average trade duration ──
    avg_duration_hours = _calc_avg_duration(closed)

    # ── Win rate by period ──
    win_rate_7d = _win_rate_period(closed, days=7)
    win_rate_30d = _win_rate_period(closed, days=30)
    win_rate_90d = _win_rate_period(closed, days=90)

    return {
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_ret_pct, 4),
        "annualized_return_pct": round(ann_ret_pct, 4),
        "num_trades": num_trades,
        "win_rate": round(win_rate, 2),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "max_drawdown_abs": round(max_dd_abs, 2),
        "max_drawdown_duration_days": max_dd_duration_days,
        "calmar_ratio": round(calmar, 4),
        "profit_factor": round(profit_factor, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "avg_trade_duration_hours": round(avg_duration_hours, 2),
        "win_rate_7d": round(win_rate_7d, 2),
        "win_rate_30d": round(win_rate_30d, 2),
        "win_rate_90d": round(win_rate_90d, 2),
        "equity_curve": [round(v, 2) for v in equity_curve],
        "trading_days": trading_days,
    }


def compute_bot_comparison(
    trades: List[Dict[str, Any]],
    initial_balance: float,
    bot_field: str = "instance_id",
) -> List[Dict[str, Any]]:
    """Group trades by bot and compute metrics for each, enabling side-by-side comparison."""
    by_bot: Dict[str, List[Dict[str, Any]]] = {}
    for t in trades:
        bid = str(t.get(bot_field) or t.get("bot_id") or "unknown")
        by_bot.setdefault(bid, []).append(t)

    results = []
    for bot_id, bot_trades in by_bot.items():
        m = compute_advanced_metrics(bot_trades, initial_balance)
        m["bot_id"] = bot_id
        m["symbol"] = _most_common(bot_trades, "symbol")
        results.append(m)

    results.sort(key=lambda x: x["total_pnl"], reverse=True)
    return results


def filter_trades(
    trades: List[Dict[str, Any]],
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    symbol: Optional[str] = None,
    bot_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Apply date / symbol / bot filters to trade list."""
    result = trades
    if start_date:
        result = [t for t in result if t.get("timestamp") and t["timestamp"] >= start_date]
    if end_date:
        result = [t for t in result if t.get("timestamp") and t["timestamp"] <= end_date]
    if symbol:
        sym_upper = symbol.upper()
        result = [t for t in result if (t.get("symbol") or "").upper() == sym_upper]
    if bot_id:
        result = [
            t for t in result
            if str(t.get("instance_id") or t.get("bot_id") or "") == bot_id
        ]
    return result


# ── Private helpers ───────────────────────────────────────────────────────────


def _calc_sharpe(pnls: List[float], initial_balance: float) -> float:
    if len(pnls) < 2 or initial_balance <= 0:
        return 0.0
    returns = [p / initial_balance for p in pnls]
    avg = sum(returns) / len(returns)
    variance = sum((r - avg) ** 2 for r in returns) / len(returns)
    std = math.sqrt(variance)
    return (avg / std) * math.sqrt(252) if std > 0 else 0.0


def _calc_sortino(pnls: List[float], initial_balance: float) -> float:
    if not pnls or initial_balance <= 0:
        return 0.0
    returns = [p / initial_balance for p in pnls]
    avg = sum(returns) / len(returns)
    neg = [r for r in returns if r < 0]
    down_std = math.sqrt(sum(r ** 2 for r in neg) / len(neg)) if neg else 0.0
    return (avg / down_std) * math.sqrt(252) if down_std > 0 else 0.0


def _calc_avg_duration(trades: List[Dict[str, Any]]) -> float:
    """Average duration from entry_time to exit_time (or created_at to closed_at)."""
    durations: List[float] = []
    for t in trades:
        entry = t.get("entry_time") or t.get("created_at")
        exit_ = t.get("exit_time") or t.get("closed_at") or t.get("timestamp")
        if isinstance(entry, datetime) and isinstance(exit_, datetime) and exit_ > entry:
            durations.append((exit_ - entry).total_seconds() / 3600.0)
    return (sum(durations) / len(durations)) if durations else 0.0


def _win_rate_period(trades: List[Dict[str, Any]], days: int) -> float:
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = [t for t in trades if t.get("timestamp") and t["timestamp"] >= cutoff and t.get("pnl") is not None]
    if not recent:
        return 0.0
    wins = len([t for t in recent if (t.get("pnl") or 0) > 0])
    return (wins / len(recent)) * 100.0


def _most_common(trades: List[Dict[str, Any]], field: str) -> str:
    counts: Dict[str, int] = {}
    for t in trades:
        val = t.get(field)
        if val:
            counts[str(val)] = counts.get(str(val), 0) + 1
    if not counts:
        return ""
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _empty_metrics() -> Dict[str, Any]:
    return {
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "num_trades": 0,
        "win_rate": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown_pct": 0.0,
        "max_drawdown_abs": 0.0,
        "max_drawdown_duration_days": 0,
        "calmar_ratio": 0.0,
        "profit_factor": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "avg_trade_duration_hours": 0.0,
        "win_rate_7d": 0.0,
        "win_rate_30d": 0.0,
        "win_rate_90d": 0.0,
        "equity_curve": [],
        "trading_days": 0,
    }


# ── PEND-12: Strategy / Heatmap / Correlation ────────────────────────────────


def compute_strategy_metrics(
    trades: List[Dict[str, Any]],
    initial_balance: float,
) -> List[Dict[str, Any]]:
    """Group trades by strategy_name and compute full metrics per group."""
    by_strategy: Dict[str, List[Dict[str, Any]]] = {}
    for t in trades:
        name = str(t.get("strategy_name") or t.get("strategy") or "unknown")
        by_strategy.setdefault(name, []).append(t)

    results = []
    for strategy_name, strat_trades in by_strategy.items():
        m = compute_advanced_metrics(strat_trades, initial_balance)
        m["strategy_name"] = strategy_name
        m["bot_ids"] = sorted({
            str(t.get("instance_id") or t.get("bot_id") or "")
            for t in strat_trades
            if t.get("instance_id") or t.get("bot_id")
        })
        results.append(m)

    results.sort(key=lambda x: x["total_pnl"], reverse=True)
    return results


def compute_heatmap(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a 7×24 avg-PnL heatmap grouped by day-of-week and hour-of-day."""
    from collections import defaultdict

    cell_pnl: Dict = defaultdict(list)

    for t in trades:
        if t.get("pnl") is None:
            continue
        ts = t.get("timestamp")
        if not isinstance(ts, datetime):
            continue
        cell_pnl[(ts.weekday(), ts.hour)].append(t["pnl"])

    cells = []
    all_avgs: List[float] = []
    for day in range(7):
        for hour in range(24):
            pnls = cell_pnl.get((day, hour), [])
            avg = round(sum(pnls) / len(pnls), 2) if pnls else 0.0
            cells.append({"day": day, "hour": hour, "avg_pnl": avg, "count": len(pnls)})
            if pnls:
                all_avgs.append(avg)

    return {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "hours": list(range(24)),
        "cells": cells,
        "min_pnl": round(min(all_avgs), 2) if all_avgs else 0.0,
        "max_pnl": round(max(all_avgs), 2) if all_avgs else 0.0,
    }


def compute_correlation_matrix(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pearson correlation matrix of daily returns between bots."""
    by_bot: Dict[str, Dict[str, float]] = {}
    for t in trades:
        bot_id = str(t.get("instance_id") or t.get("bot_id") or "unknown")
        ts = t.get("timestamp")
        if not isinstance(ts, datetime) or t.get("pnl") is None:
            continue
        date_key = ts.strftime("%Y-%m-%d")
        by_bot.setdefault(bot_id, {})
        by_bot[bot_id][date_key] = by_bot[bot_id].get(date_key, 0.0) + t["pnl"]

    bots = sorted(by_bot.keys())
    n = len(bots)
    if n == 0:
        return {"bots": [], "matrix": []}
    if n == 1:
        return {"bots": bots, "matrix": [[1.0]]}

    all_dates = sorted({date for bot_dates in by_bot.values() for date in bot_dates})
    series = [[by_bot[b].get(d, 0.0) for d in all_dates] for b in bots]

    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            elif j < i:
                matrix[i][j] = matrix[j][i]
            else:
                matrix[i][j] = round(_pearson(series[i], series[j]), 4)

    return {"bots": bots, "matrix": matrix}


def _pearson(x: List[float], y: List[float]) -> float:
    """Pearson r between two equal-length series."""
    n = len(x)
    if n < 2:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denom = math.sqrt(
        sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)
    )
    return num / denom if denom > 0 else 0.0
