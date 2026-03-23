"""
Unit Tests — Advanced Performance Metrics (PEND-06)
=====================================================

Tests for compute_advanced_metrics, compute_bot_comparison, filter_trades,
and all private helper functions.
"""

import math
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.analytics.advanced_metrics import (
    compute_advanced_metrics,
    compute_bot_comparison,
    filter_trades,
    _calc_sharpe,
    _calc_sortino,
    _calc_avg_duration,
    _win_rate_period,
    _most_common,
    _empty_metrics,
)


INITIAL_BALANCE = 10_000.0
NOW = datetime(2025, 6, 1, 12, 0, 0)


def _trade(pnl, days_ago=0, symbol="BTC-USDT", instance_id="bot-1", **extra):
    """Helper to build a trade dict."""
    t = {
        "pnl": pnl,
        "timestamp": NOW - timedelta(days=days_ago),
        "symbol": symbol,
        "instance_id": instance_id,
    }
    t.update(extra)
    return t


# ── compute_advanced_metrics ──────────────────────────────────────────────────


class TestComputeAdvancedMetrics:
    def test_empty_trades_returns_zeros(self):
        result = compute_advanced_metrics([], INITIAL_BALANCE)
        assert result == _empty_metrics()

    def test_trades_with_no_pnl_returns_zeros(self):
        trades = [{"timestamp": NOW, "symbol": "BTC"}]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result == _empty_metrics()

    def test_single_winning_trade(self):
        trades = [_trade(100)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["total_pnl"] == 100.0
        assert result["num_trades"] == 1
        assert result["win_rate"] == 100.0
        assert result["avg_win"] == 100.0
        assert result["avg_loss"] == 0.0
        assert result["best_trade"] == 100.0
        assert result["worst_trade"] == 100.0
        assert result["profit_factor"] == 0.0  # no losses → 0

    def test_single_losing_trade(self):
        trades = [_trade(-50)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["total_pnl"] == -50.0
        assert result["win_rate"] == 0.0
        assert result["avg_loss"] == -50.0
        assert result["worst_trade"] == -50.0

    def test_mixed_trades_basic_metrics(self):
        trades = [
            _trade(200, days_ago=10),
            _trade(-80, days_ago=8),
            _trade(150, days_ago=5),
            _trade(-30, days_ago=2),
        ]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["total_pnl"] == 240.0
        assert result["num_trades"] == 4
        assert result["win_rate"] == 50.0
        assert result["avg_win"] == 175.0   # (200+150)/2
        assert result["avg_loss"] == -55.0   # (-80+-30)/2
        assert result["best_trade"] == 200.0
        assert result["worst_trade"] == -80.0

    def test_total_return_pct(self):
        trades = [_trade(1000)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["total_return_pct"] == 10.0  # 1000/10000 * 100

    def test_equity_curve(self):
        trades = [_trade(100, days_ago=2), _trade(-30, days_ago=1)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["equity_curve"] == [10100.0, 10070.0]

    def test_profit_factor_mixed(self):
        trades = [_trade(300, days_ago=2), _trade(-100, days_ago=1)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["profit_factor"] == 3.0  # 300/100

    def test_max_drawdown(self):
        trades = [
            _trade(500, days_ago=10),   # eq: 10500
            _trade(-300, days_ago=8),   # eq: 10200 → dd from 10500 = 300
            _trade(-400, days_ago=5),   # eq: 9800  → dd from 10500 = 700
            _trade(1000, days_ago=2),   # eq: 10800 → new peak
        ]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["max_drawdown_abs"] == 700.0
        # dd_pct = 700 / 10500 * 100
        expected_pct = round((700 / 10500) * 100, 4)
        assert result["max_drawdown_pct"] == expected_pct

    def test_sharpe_ratio_calculated(self):
        trades = [_trade(100, days_ago=5), _trade(50, days_ago=3), _trade(80, days_ago=1)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        # All positive returns → sharpe should be positive
        assert result["sharpe_ratio"] > 0

    def test_sortino_ratio_with_losses(self):
        trades = [
            _trade(100, days_ago=5),
            _trade(-30, days_ago=3),
            _trade(50, days_ago=1),
        ]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["sortino_ratio"] > 0

    def test_calmar_ratio_positive(self):
        trades = [
            _trade(500, days_ago=10),
            _trade(-200, days_ago=5),
            _trade(300, days_ago=1),
        ]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["calmar_ratio"] > 0

    def test_calmar_zero_when_no_drawdown(self):
        trades = [_trade(100, days_ago=2), _trade(50, days_ago=1)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["calmar_ratio"] == 0.0  # no drawdown → calmar=0

    def test_trading_days(self):
        trades = [_trade(100, days_ago=10), _trade(50, days_ago=0)]
        result = compute_advanced_metrics(trades, INITIAL_BALANCE)
        assert result["trading_days"] == 10


# ── _calc_sharpe ──────────────────────────────────────────────────────────────


class TestCalcSharpe:
    def test_returns_zero_for_single_trade(self):
        assert _calc_sharpe([100], 10000) == 0.0

    def test_returns_zero_for_empty(self):
        assert _calc_sharpe([], 10000) == 0.0

    def test_all_same_returns_zero_std(self):
        # All same pnl → std=0 → sharpe=0
        assert _calc_sharpe([50, 50, 50], 10000) == 0.0

    def test_positive_sharpe_for_positive_returns(self):
        pnls = [100, 80, 130, 95, 110]
        sharpe = _calc_sharpe(pnls, 10000)
        assert sharpe > 0

    def test_negative_sharpe_for_negative_returns(self):
        pnls = [-100, -80, -130, -95, -110]
        sharpe = _calc_sharpe(pnls, 10000)
        assert sharpe < 0

    def test_known_value(self):
        # pnls: [100, -100] → returns [0.01, -0.01]
        # avg=0, std=0.01 → sharpe = (0/0.01)*sqrt(252) = 0
        assert _calc_sharpe([100, -100], 10000) == 0.0


# ── _calc_sortino ─────────────────────────────────────────────────────────────


class TestCalcSortino:
    def test_returns_zero_for_empty(self):
        assert _calc_sortino([], 10000) == 0.0

    def test_all_positive_no_downside(self):
        # No downside deviation → 0
        assert _calc_sortino([100, 50, 80], 10000) == 0.0

    def test_positive_sortino_with_mixed(self):
        pnls = [100, -30, 80, -20, 150]
        sortino = _calc_sortino(pnls, 10000)
        assert sortino > 0  # overall positive mean


# ── _calc_avg_duration ────────────────────────────────────────────────────────


class TestCalcAvgDuration:
    def test_no_time_fields(self):
        trades = [{"pnl": 100}]
        assert _calc_avg_duration(trades) == 0.0

    def test_with_entry_exit_time(self):
        trades = [{
            "pnl": 100,
            "entry_time": datetime(2025, 1, 1, 10, 0),
            "exit_time": datetime(2025, 1, 1, 12, 0),
        }]
        assert _calc_avg_duration(trades) == 2.0  # 2 hours

    def test_average_of_multiple(self):
        trades = [
            {
                "pnl": 100,
                "entry_time": datetime(2025, 1, 1, 10, 0),
                "exit_time": datetime(2025, 1, 1, 14, 0),
            },
            {
                "pnl": -50,
                "entry_time": datetime(2025, 1, 2, 8, 0),
                "exit_time": datetime(2025, 1, 2, 10, 0),
            },
        ]
        assert _calc_avg_duration(trades) == 3.0  # (4+2)/2

    def test_ignores_invalid_times(self):
        trades = [
            {"pnl": 100, "entry_time": "not-a-datetime", "exit_time": datetime(2025, 1, 1)},
            {
                "pnl": 50,
                "entry_time": datetime(2025, 1, 1, 10, 0),
                "exit_time": datetime(2025, 1, 1, 16, 0),
            },
        ]
        assert _calc_avg_duration(trades) == 6.0


# ── _win_rate_period ──────────────────────────────────────────────────────────


class TestWinRatePeriod:
    def test_empty_trades(self):
        assert _win_rate_period([], days=7) == 0.0

    def test_all_old_trades(self):
        old = [_trade(100, days_ago=30)]
        # Patching utcnow so _win_rate_period uses our NOW
        with patch("app.analytics.advanced_metrics.datetime") as mock_dt:
            mock_dt.utcnow.return_value = NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = _win_rate_period(old, days=7)
        assert result == 0.0

    def test_recent_mixed(self):
        trades = [_trade(100, days_ago=2), _trade(-50, days_ago=1)]
        with patch("app.analytics.advanced_metrics.datetime") as mock_dt:
            mock_dt.utcnow.return_value = NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = _win_rate_period(trades, days=7)
        assert result == 50.0


# ── filter_trades ─────────────────────────────────────────────────────────────


class TestFilterTrades:
    def test_no_filters(self):
        trades = [_trade(100), _trade(-50)]
        assert len(filter_trades(trades)) == 2

    def test_filter_by_symbol(self):
        trades = [
            _trade(100, symbol="BTC-USDT"),
            _trade(-50, symbol="ETH-USDT"),
        ]
        result = filter_trades(trades, symbol="btc-usdt")  # case insensitive
        assert len(result) == 1
        assert result[0]["symbol"] == "BTC-USDT"

    def test_filter_by_bot_id(self):
        trades = [
            _trade(100, instance_id="bot-1"),
            _trade(-50, instance_id="bot-2"),
        ]
        result = filter_trades(trades, bot_id="bot-2")
        assert len(result) == 1
        assert result[0]["pnl"] == -50

    def test_filter_by_start_date(self):
        trades = [
            _trade(100, days_ago=10),
            _trade(50, days_ago=2),
        ]
        cutoff = NOW - timedelta(days=5)
        result = filter_trades(trades, start_date=cutoff)
        assert len(result) == 1
        assert result[0]["pnl"] == 50

    def test_filter_by_end_date(self):
        trades = [
            _trade(100, days_ago=10),
            _trade(50, days_ago=2),
        ]
        cutoff = NOW - timedelta(days=5)
        result = filter_trades(trades, end_date=cutoff)
        assert len(result) == 1
        assert result[0]["pnl"] == 100

    def test_combined_filters(self):
        trades = [
            _trade(100, days_ago=2, symbol="BTC-USDT", instance_id="bot-1"),
            _trade(-50, days_ago=2, symbol="ETH-USDT", instance_id="bot-1"),
            _trade(30, days_ago=2, symbol="BTC-USDT", instance_id="bot-2"),
        ]
        result = filter_trades(trades, symbol="BTC-USDT", bot_id="bot-1")
        assert len(result) == 1
        assert result[0]["pnl"] == 100


# ── compute_bot_comparison ────────────────────────────────────────────────────


class TestComputeBotComparison:
    def test_empty_trades(self):
        assert compute_bot_comparison([], INITIAL_BALANCE) == []

    def test_groups_by_bot(self):
        trades = [
            _trade(200, days_ago=5, instance_id="bot-A"),
            _trade(-50, days_ago=3, instance_id="bot-A"),
            _trade(100, days_ago=2, instance_id="bot-B"),
        ]
        result = compute_bot_comparison(trades, INITIAL_BALANCE)
        assert len(result) == 2
        ids = [r["bot_id"] for r in result]
        assert "bot-A" in ids
        assert "bot-B" in ids

    def test_sorted_by_pnl_desc(self):
        trades = [
            _trade(50, instance_id="loser"),
            _trade(500, instance_id="winner"),
        ]
        result = compute_bot_comparison(trades, INITIAL_BALANCE)
        assert result[0]["bot_id"] == "winner"
        assert result[1]["bot_id"] == "loser"

    def test_symbol_is_most_common(self):
        trades = [
            _trade(100, symbol="BTC-USDT", instance_id="bot-1"),
            _trade(50, symbol="BTC-USDT", instance_id="bot-1"),
            _trade(30, symbol="ETH-USDT", instance_id="bot-1"),
        ]
        result = compute_bot_comparison(trades, INITIAL_BALANCE)
        assert result[0]["symbol"] == "BTC-USDT"


# ── _most_common ──────────────────────────────────────────────────────────────


class TestMostCommon:
    def test_empty(self):
        assert _most_common([], "symbol") == ""

    def test_single_value(self):
        trades = [{"symbol": "BTC"}]
        assert _most_common(trades, "symbol") == "BTC"

    def test_picks_most_frequent(self):
        trades = [
            {"symbol": "ETH"},
            {"symbol": "BTC"},
            {"symbol": "BTC"},
        ]
        assert _most_common(trades, "symbol") == "BTC"

    def test_missing_field(self):
        trades = [{"pnl": 100}]
        assert _most_common(trades, "symbol") == ""


# ── _empty_metrics ────────────────────────────────────────────────────────────


class TestEmptyMetrics:
    def test_has_all_keys(self):
        m = _empty_metrics()
        expected_keys = {
            "total_pnl", "total_return_pct", "annualized_return_pct",
            "num_trades", "win_rate", "sharpe_ratio", "sortino_ratio",
            "max_drawdown_pct", "max_drawdown_abs", "max_drawdown_duration_days",
            "calmar_ratio", "profit_factor", "avg_win", "avg_loss",
            "best_trade", "worst_trade", "avg_trade_duration_hours",
            "win_rate_7d", "win_rate_30d", "win_rate_90d",
            "equity_curve", "trading_days",
        }
        assert set(m.keys()) == expected_keys

    def test_all_values_are_zero(self):
        m = _empty_metrics()
        for k, v in m.items():
            if k == "equity_curve":
                assert v == []
            else:
                assert v == 0 or v == 0.0
