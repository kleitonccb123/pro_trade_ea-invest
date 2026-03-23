"""
pnl/__init__.py — PnL calculation package (DOC_05).

Public API:
  PnLCalculator          — static methods for fee/slippage/close calculations
  BotMetricsAccumulator  — in-memory accumulator, persisted to MongoDB
  take_bot_performance_snapshot — async function for hourly capital snapshots
"""

from app.pnl.calculator import PnLCalculator
from app.pnl.metrics_aggregator import BotMetricsAccumulator
from app.pnl.snapshot_service import take_bot_performance_snapshot

__all__ = [
    "PnLCalculator",
    "BotMetricsAccumulator",
    "take_bot_performance_snapshot",
]
