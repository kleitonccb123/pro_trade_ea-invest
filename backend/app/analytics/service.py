from __future__ import annotations

from datetime import datetime, time
from typing import List
import logging

from app.core.database import get_db
from app.core.config import settings
from app.analytics import repository as analytics_repo
from app.analytics import schemas

logger = logging.getLogger(__name__)


def _running_max_drawdown(equity_series: List[float]) -> float:
    max_dd = 0.0
    peak = float("-inf")
    for v in equity_series:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
    return max_dd


class AnalyticsService:
    """Service to compute consolidated metrics for dashboard from simulated trades."""

    async def summary(self, user_id: str) -> schemas.SummaryResponse:
        db = get_db()
        trades_col = db['simulated_trades']
        
        # Get all trades from MongoDB for this user
        trades_cursor = trades_col.find({"user_id": user_id})
        trades = await trades_cursor.to_list(None)

        initial = settings.initial_balance
        closed_trades = [t for t in trades if t.get('pnl') is not None]
        total_pnl = sum((t.get('pnl') or 0.0) for t in closed_trades)
        balance = initial + total_pnl
        total_pnl_percent = (total_pnl / initial) * 100 if initial else 0.0
        num_trades = len(closed_trades)
        wins = len([t for t in closed_trades if (t.get('pnl') or 0) > 0])
        win_rate = (wins / num_trades) * 100 if num_trades else 0.0

        # Calculate daily metrics (today's trades) - CORRE??O DA L?GICA DE DATA
        today_start = datetime.combine(datetime.utcnow().date(), time.min)
        
        # Filtrar trades de HOJE usando datetime objects
        daily_trades = [
            t for t in closed_trades 
            if t.get('timestamp') and isinstance(t['timestamp'], datetime) and t['timestamp'] >= today_start
        ]
        
        daily_pnl = sum((t.get('pnl') or 0.0) for t in daily_trades)
        daily_trades_count = len(daily_trades)

        # build equity series by timestamp
        equity = []
        running = initial
        for t in closed_trades:
            running += (t.get('pnl') or 0.0)
            equity.append(running)

        max_drawdown = _running_max_drawdown(equity) if equity else 0.0

        result = schemas.SummaryResponse(
            initial_balance=initial,
            balance=balance,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            daily_pnl=daily_pnl,
            daily_trades=daily_trades_count,
            num_trades=num_trades,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
        )
        
        return result

    async def summary_global(self) -> schemas.SummaryResponse:
        """Global summary for all users (used by scheduler)."""
        db = get_db()
        trades_col = db['simulated_trades']

        # Get all trades from MongoDB
        trades_cursor = trades_col.find({})
        trades = await trades_cursor.to_list(None)

        initial = settings.initial_balance
        closed_trades = [t for t in trades if t.get('pnl') is not None]
        total_pnl = sum((t.get('pnl') or 0.0) for t in closed_trades)
        balance = initial + total_pnl
        total_pnl_percent = (total_pnl / initial) * 100 if initial else 0.0
        num_trades = len(closed_trades)
        wins = len([t for t in closed_trades if (t.get('pnl') or 0) > 0])
        win_rate = (wins / num_trades) * 100 if num_trades else 0.0

        # Calculate daily metrics (today's trades)
        today_start = datetime.combine(datetime.utcnow().date(), time.min)

        # Filter today's trades using datetime objects
        daily_trades = [t for t in closed_trades if t.get('timestamp') and t['timestamp'] >= today_start]
        daily_pnl = sum((t.get('pnl') or 0.0) for t in daily_trades)
        daily_trades_count = len(daily_trades)

        # Calculate max drawdown (simplified)
        max_drawdown = 0.0

        return schemas.SummaryResponse(
            initial_balance=initial,
            balance=balance,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            daily_pnl=daily_pnl,
            daily_trades=daily_trades_count,
            num_trades=num_trades,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
        )

    async def pnl_timeseries(self) -> schemas.PerformanceResponse:
        db = get_db()
        trades_col = db['simulated_trades']
        
        # Get all closed trades from MongoDB
        trades_cursor = trades_col.find({'pnl': {'$ne': None}})
        closed = await trades_cursor.to_list(None)
        
        # group by day
        times = {}
        for t in closed:
            if t.get('timestamp'):
                d = t['timestamp'].date() if hasattr(t['timestamp'], 'date') else datetime.fromisoformat(t['timestamp']).date()
                times.setdefault(d, 0.0)
                times[d] += (t.get('pnl') or 0.0)

        # build ordered series
        ordered = sorted(times.items())
        dates = [datetime.combine(k, datetime.min.time()) for k, _ in ordered]
        pnls = [v for _, v in ordered]

        cumulative = []
        running = settings.initial_balance
        for v in pnls:
            running += v
            cumulative.append(running)

        max_drawdown = _running_max_drawdown(cumulative) if cumulative else 0.0

        points = [schemas.PnLPoint(date=dates[i], pnl=pnls[i]) for i in range(len(dates))]
        return schemas.PerformanceResponse(timeseries=points, cumulative=cumulative, max_drawdown=max_drawdown)

    async def performance(self) -> dict:
        # Lightweight wrapper returning summary + timeseries
        s = await self.summary_global()
        ts = await self.pnl_timeseries()
        return {"summary": s, "timeseries": ts}

    async def bot_status(self, instance_id: int) -> schemas.BotStatusSchema:
        db = get_db()
        instances_col = db['bot_instances']
        
        # Find instance by ID
        inst = await instances_col.find_one({'_id': instance_id})
        if not inst:
            raise ValueError("Instance not found")
        
        return schemas.BotStatusSchema(
            instance_id=inst.get('_id'),
            state=inst.get('state', 'unknown'),
            last_heartbeat=inst.get('last_heartbeat'),
            error_message=inst.get('error_message')
        )

    async def trades_for_instance(self, instance_id: int) -> List[schemas.TradeSchema]:
        db = get_db()
        trades_col = db['simulated_trades']
        
        # Get all trades for this instance
        trades_cursor = trades_col.find({'instance_id': instance_id})
        trades = await trades_cursor.to_list(None)
        
        return [schemas.TradeSchema(**t) for t in trades]
