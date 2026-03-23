"""Strategies package — exported factory function."""

from __future__ import annotations

from app.engine.strategies.base import StrategyBase, TradingSignal


def get_strategy(robot_type: str, config: dict) -> StrategyBase:
    """Factory: return the correct strategy instance for the given robot_type."""
    robot_type = (robot_type or "rsi").lower()

    if robot_type == "grid":
        from app.engine.strategies.grid import GridStrategy
        return GridStrategy(config)
    elif robot_type == "rsi":
        from app.engine.strategies.rsi import RSIStrategy
        return RSIStrategy(config)
    elif robot_type == "macd":
        from app.engine.strategies.macd import MACDStrategy
        return MACDStrategy(config)
    elif robot_type == "dca":
        from app.engine.strategies.dca import DCAStrategy
        return DCAStrategy(config)
    elif robot_type in ("combined", "multi"):
        from app.engine.strategies.combined import CombinedStrategy
        return CombinedStrategy(config)
    elif robot_type == "scalping":
        from app.engine.strategies.scalping import ScalpingStrategy
        return ScalpingStrategy(config)
    else:
        # Fallback to RSI
        from app.engine.strategies.rsi import RSIStrategy
        return RSIStrategy(config)


__all__ = ["get_strategy", "StrategyBase", "TradingSignal"]
