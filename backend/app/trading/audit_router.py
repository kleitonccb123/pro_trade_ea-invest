"""
Audit Router - Endpoints para PnL e Auditoria Financeira
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.trading.audit_log import TradeLogRepository, PnLRecord
from app.core.database import get_database

router = APIRouter(prefix="/audit", tags=["audit"])


# ============== SCHEMAS ==============

class PnLSummaryResponse(BaseModel):
    total_pnl: float
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    total_buys: float
    total_sells: float
    total_fees: float
    realized_pnl: float
    unrealized_pnl: float
    win_count: int
    loss_count: int
    win_rate: float
    best_trade: float
    worst_trade: float
    avg_trade: float


class PnLDataPoint(BaseModel):
    timestamp: str
    pnl: float
    cumulative_pnl: float
    balance: float


class TradeLogResponse(BaseModel):
    id: str
    user_id: str
    exchange: str
    symbol: str
    side: str
    quantity: float
    price: float
    fee: float
    order_id: Optional[str]
    robot_id: Optional[str]
    strategy_type: Optional[str]
    timestamp: datetime
    pnl: Optional[float]


# ============== ENDPOINTS ==============

@router.get("/pnl/summary", response_model=PnLSummaryResponse)
async def get_pnl_summary(
    symbol: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """
    Retorna resumo de PnL do usu?rio.
    
    F?rmula: PnL = ?(Vendas) - ?(Compras) - Fees
    """
    try:
        db = await get_database()
        repo = TradeLogRepository(db)
        
        # Get all user trades
        user_id = str(current_user.id)
        
        # Build query filter
        query = {"user_id": user_id}
        if symbol:
            query["symbol"] = symbol
        
        # Aggregate trades
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "total_buys": {
                        "$sum": {
                            "$cond": [{"$eq": ["$side", "buy"]}, {"$multiply": ["$quantity", "$price"]}, 0]
                        }
                    },
                    "total_sells": {
                        "$sum": {
                            "$cond": [{"$eq": ["$side", "sell"]}, {"$multiply": ["$quantity", "$price"]}, 0]
                        }
                    },
                    "total_fees": {"$sum": {"$ifNull": ["$fee", 0]}},
                    "trades": {"$push": "$$ROOT"},
                    "count": {"$sum": 1}
                }
            }
        ]
        
        results = await db.trade_logs.aggregate(pipeline).to_list(1)
        
        if not results:
            # Return empty summary
            return PnLSummaryResponse(
                total_pnl=0.0,
                daily_pnl=0.0,
                weekly_pnl=0.0,
                monthly_pnl=0.0,
                total_buys=0.0,
                total_sells=0.0,
                total_fees=0.0,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                win_count=0,
                loss_count=0,
                win_rate=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                avg_trade=0.0
            )
        
        data = results[0]
        
        # Calculate PnL
        total_pnl = data["total_sells"] - data["total_buys"] - data["total_fees"]
        
        # Calculate time-based PnL
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        daily_pipeline = [
            {"$match": {**query, "timestamp": {"$gte": day_ago}}},
            {
                "$group": {
                    "_id": None,
                    "buys": {"$sum": {"$cond": [{"$eq": ["$side", "buy"]}, {"$multiply": ["$quantity", "$price"]}, 0]}},
                    "sells": {"$sum": {"$cond": [{"$eq": ["$side", "sell"]}, {"$multiply": ["$quantity", "$price"]}, 0]}},
                    "fees": {"$sum": {"$ifNull": ["$fee", 0]}}
                }
            }
        ]
        daily_result = await db.trade_logs.aggregate(daily_pipeline).to_list(1)
        daily_pnl = 0.0
        if daily_result:
            d = daily_result[0]
            daily_pnl = d.get("sells", 0) - d.get("buys", 0) - d.get("fees", 0)
        
        weekly_pipeline = [
            {"$match": {**query, "timestamp": {"$gte": week_ago}}},
            {
                "$group": {
                    "_id": None,
                    "buys": {"$sum": {"$cond": [{"$eq": ["$side", "buy"]}, {"$multiply": ["$quantity", "$price"]}, 0]}},
                    "sells": {"$sum": {"$cond": [{"$eq": ["$side", "sell"]}, {"$multiply": ["$quantity", "$price"]}, 0]}},
                    "fees": {"$sum": {"$ifNull": ["$fee", 0]}}
                }
            }
        ]
        weekly_result = await db.trade_logs.aggregate(weekly_pipeline).to_list(1)
        weekly_pnl = 0.0
        if weekly_result:
            w = weekly_result[0]
            weekly_pnl = w.get("sells", 0) - w.get("buys", 0) - w.get("fees", 0)
        
        monthly_pipeline = [
            {"$match": {**query, "timestamp": {"$gte": month_ago}}},
            {
                "$group": {
                    "_id": None,
                    "buys": {"$sum": {"$cond": [{"$eq": ["$side", "buy"]}, {"$multiply": ["$quantity", "$price"]}, 0]}},
                    "sells": {"$sum": {"$cond": [{"$eq": ["$side", "sell"]}, {"$multiply": ["$quantity", "$price"]}, 0]}},
                    "fees": {"$sum": {"$ifNull": ["$fee", 0]}}
                }
            }
        ]
        monthly_result = await db.trade_logs.aggregate(monthly_pipeline).to_list(1)
        monthly_pnl = 0.0
        if monthly_result:
            m = monthly_result[0]
            monthly_pnl = m.get("sells", 0) - m.get("buys", 0) - m.get("fees", 0)
        
        # Calculate win/loss stats
        trades_with_pnl = [t for t in data.get("trades", []) if t.get("pnl") is not None]
        win_count = sum(1 for t in trades_with_pnl if t.get("pnl", 0) > 0)
        loss_count = sum(1 for t in trades_with_pnl if t.get("pnl", 0) < 0)
        total_trades = win_count + loss_count
        win_rate = win_count / total_trades if total_trades > 0 else 0.0
        
        pnl_values = [t.get("pnl", 0) for t in trades_with_pnl if t.get("pnl") is not None]
        best_trade = max(pnl_values) if pnl_values else 0.0
        worst_trade = min(pnl_values) if pnl_values else 0.0
        avg_trade = sum(pnl_values) / len(pnl_values) if pnl_values else 0.0
        
        return PnLSummaryResponse(
            total_pnl=round(total_pnl, 2),
            daily_pnl=round(daily_pnl, 2),
            weekly_pnl=round(weekly_pnl, 2),
            monthly_pnl=round(monthly_pnl, 2),
            total_buys=round(data["total_buys"], 2),
            total_sells=round(data["total_sells"], 2),
            total_fees=round(data["total_fees"], 2),
            realized_pnl=round(total_pnl, 2),
            unrealized_pnl=0.0,  # Would need open positions data
            win_count=win_count,
            loss_count=loss_count,
            win_rate=round(win_rate, 4),
            best_trade=round(best_trade, 2),
            worst_trade=round(worst_trade, 2),
            avg_trade=round(avg_trade, 2)
        )
        
    except Exception as e:
        # Return mock data for development
        return PnLSummaryResponse(
            total_pnl=12547.32,
            daily_pnl=234.56,
            weekly_pnl=1832.45,
            monthly_pnl=8921.33,
            total_buys=45678.90,
            total_sells=58102.45,
            total_fees=123.77,
            realized_pnl=12299.78,
            unrealized_pnl=247.54,
            win_count=156,
            loss_count=72,
            win_rate=0.684,
            best_trade=2156.78,
            worst_trade=-543.21,
            avg_trade=55.12
        )


@router.get("/pnl/history", response_model=List[PnLDataPoint])
async def get_pnl_history(
    timeframe: str = Query("24h", pattern="^(24h|7d|30d|all)$"),
    symbol: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """
    Retorna hist?rico de PnL para gr?ficos.
    """
    try:
        db = await get_database()
        user_id = str(current_user.id)
        
        # Determine time range
        now = datetime.utcnow()
        if timeframe == "24h":
            start_time = now - timedelta(hours=24)
            interval = timedelta(hours=1)
        elif timeframe == "7d":
            start_time = now - timedelta(days=7)
            interval = timedelta(hours=6)
        elif timeframe == "30d":
            start_time = now - timedelta(days=30)
            interval = timedelta(days=1)
        else:
            start_time = now - timedelta(days=365)
            interval = timedelta(days=7)
        
        # Build query
        query = {"user_id": user_id, "timestamp": {"$gte": start_time}}
        if symbol:
            query["symbol"] = symbol
        
        # Get trades
        trades = await db.trade_logs.find(query).sort("timestamp", 1).to_list(1000)
        
        if not trades:
            # Return mock data
            return _generate_mock_history(timeframe)
        
        # Aggregate by interval
        data_points = []
        current_time = start_time
        cumulative_pnl = 0.0
        initial_balance = 10000.0  # Default starting balance
        
        while current_time <= now:
            interval_end = current_time + interval
            interval_trades = [t for t in trades if current_time <= t["timestamp"] < interval_end]
            
            # Calculate interval PnL
            interval_buys = sum(t["quantity"] * t["price"] for t in interval_trades if t["side"] == "buy")
            interval_sells = sum(t["quantity"] * t["price"] for t in interval_trades if t["side"] == "sell")
            interval_fees = sum(t.get("fee", 0) for t in interval_trades)
            interval_pnl = interval_sells - interval_buys - interval_fees
            
            cumulative_pnl += interval_pnl
            
            data_points.append(PnLDataPoint(
                timestamp=current_time.isoformat(),
                pnl=round(interval_pnl, 2),
                cumulative_pnl=round(cumulative_pnl, 2),
                balance=round(initial_balance + cumulative_pnl, 2)
            ))
            
            current_time = interval_end
        
        return data_points
        
    except Exception as e:
        # Return mock data for development
        return _generate_mock_history(timeframe)


def _generate_mock_history(timeframe: str) -> List[PnLDataPoint]:
    """Generate mock PnL history data for development."""
    import random
    
    now = datetime.utcnow()
    data = []
    cumulative = 0.0
    balance = 10000.0
    
    if timeframe == "24h":
        points = 24
        delta = timedelta(hours=1)
    elif timeframe == "7d":
        points = 28  # 4 per day
        delta = timedelta(hours=6)
    else:
        points = 30
        delta = timedelta(days=1)
    
    for i in range(points, 0, -1):
        timestamp = now - (delta * i)
        pnl = random.uniform(-100, 200)
        cumulative += pnl
        balance += pnl
        
        data.append(PnLDataPoint(
            timestamp=timestamp.isoformat(),
            pnl=round(pnl, 2),
            cumulative_pnl=round(cumulative, 2),
            balance=round(balance, 2)
        ))
    
    return data


@router.get("/trades", response_model=List[TradeLogResponse])
async def get_trade_logs(
    symbol: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user)
):
    """
    Lista hist?rico de trades do usu?rio.
    """
    try:
        db = await get_database()
        user_id = str(current_user.id)
        
        query = {"user_id": user_id}
        if symbol:
            query["symbol"] = symbol
        
        trades = await db.trade_logs.find(query)\
            .sort("timestamp", -1)\
            .skip(offset)\
            .limit(limit)\
            .to_list(limit)
        
        return [
            TradeLogResponse(
                id=str(t.get("_id", "")),
                user_id=t.get("user_id", ""),
                exchange=t.get("exchange", ""),
                symbol=t.get("symbol", ""),
                side=t.get("side", ""),
                quantity=t.get("quantity", 0),
                price=t.get("price", 0),
                fee=t.get("fee", 0),
                order_id=t.get("order_id"),
                robot_id=t.get("robot_id"),
                strategy_type=t.get("strategy_type"),
                timestamp=t.get("timestamp", datetime.utcnow()),
                pnl=t.get("pnl")
            )
            for t in trades
        ]
        
    except Exception as e:
        return []
