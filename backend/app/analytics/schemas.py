from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class TradeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    timestamp: datetime
    side: str


class SummaryResponse(BaseModel):
    initial_balance: float
    balance: float
    total_pnl: float
    total_pnl_percent: float
    daily_pnl: float
    daily_trades: int
    num_trades: int
    win_rate: float
    max_drawdown: float


class PnLPoint(BaseModel):
    date: datetime
    pnl: float


class PerformanceResponse(BaseModel):
    timeseries: List[PnLPoint]
    cumulative: List[float]
    max_drawdown: float


class AdvancedMetricsResponse(BaseModel):
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_abs: float = 0.0
    max_drawdown_duration_days: int = 0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade_duration_hours: float = 0.0
    win_rate_7d: float = 0.0
    win_rate_30d: float = 0.0
    win_rate_90d: float = 0.0
    equity_curve: List[float] = []
    trading_days: int = 0


class BotComparisonItem(BaseModel):
    bot_id: str = ""
    symbol: str = ""
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0
    avg_trade_duration_hours: float = 0.0


class BotStatusSchema(BaseModel):
    instance_id: int
    state: str
    last_heartbeat: Optional[datetime] = None
    error_message: Optional[str] = None


# ── PEND-12: Strategy / Heatmap / Correlation ───────────────────────────────────


class StrategyMetricsItem(BaseModel):
    strategy_name: str = ""
    bot_ids: List[str] = []
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade_duration_hours: float = 0.0


class HeatmapCell(BaseModel):
    day: int
    hour: int
    avg_pnl: float
    count: int


class HeatmapResponse(BaseModel):
    days: List[str]
    hours: List[int]
    cells: List[HeatmapCell]
    min_pnl: float
    max_pnl: float


class CorrelationMatrixResponse(BaseModel):
    bots: List[str]
    matrix: List[List[float]]


# ── PEND-15: Monte Carlo Simulation ─────────────────────────────────────────


class MonteCarloRequest(BaseModel):
    initial_capital: float = 10000.0      # Starting capital in USD
    monthly_return_pct: float = 5.0       # Expected monthly return, e.g. 5 = 5%
    annual_volatility_pct: float = 20.0   # Annual volatility, e.g. 20 = 20%
    horizon_months: int = 12              # Number of months to simulate
    n_simulations: int = 1000             # Number of simulation paths (1–10000)


class MonteCarloPathPoint(BaseModel):
    month: int
    p10: float
    p50: float
    p90: float


class MonteCarloResponse(BaseModel):
    paths: List[MonteCarloPathPoint]   # One data point per month (0..horizon)
    final_p10: float
    final_p50: float
    final_p90: float
    prob_profit_pct: float             # % of simulations ending above initial_capital
    initial_capital: float
    n_simulations: int
    horizon_months: int
