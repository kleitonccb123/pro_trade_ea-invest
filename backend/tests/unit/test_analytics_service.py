"""
Unit Tests — Analytics Service
===============================

Tests for AnalyticsService.summary(), drawdown calculation,
and edge cases (empty trades, single trade, etc.).
"""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from app.analytics.service import AnalyticsService, _running_max_drawdown


# ── Max Drawdown calculation ──────────────────────────────────────────────────

class TestRunningMaxDrawdown:
    def test_no_drawdown_ascending(self):
        assert _running_max_drawdown([100, 110, 120, 130]) == 0.0

    def test_full_drawdown(self):
        assert _running_max_drawdown([100, 50]) == 50.0

    def test_recovery_after_drawdown(self):
        series = [100, 80, 90, 70, 110]
        assert _running_max_drawdown(series) == 30.0  # peak 100 → valley 70

    def test_empty_series(self):
        assert _running_max_drawdown([]) == 0.0

    def test_single_value(self):
        assert _running_max_drawdown([100]) == 0.0

    def test_flat_series(self):
        assert _running_max_drawdown([100, 100, 100]) == 0.0


# ── AnalyticsService.summary() ───────────────────────────────────────────────

class TestAnalyticsSummary:
    @pytest.fixture()
    def service(self):
        return AnalyticsService()

    async def test_summary_empty_trades(self, service):
        """Summary with zero trades should return defaults."""
        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_col.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.service.get_db", return_value=mock_db):
            result = await service.summary("user123")

        assert result.num_trades == 0
        assert result.win_rate == 0.0
        assert result.total_pnl == 0.0

    async def test_summary_with_winning_trades(self, service):
        """PnL should sum correctly with winning trades."""
        trades = [
            {"user_id": "u1", "pnl": 100.0, "timestamp": datetime.utcnow()},
            {"user_id": "u1", "pnl": 50.0, "timestamp": datetime.utcnow()},
        ]
        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=trades)
        mock_col.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.service.get_db", return_value=mock_db):
            result = await service.summary("u1")

        assert result.total_pnl == 150.0
        assert result.num_trades == 2
        assert result.win_rate == 100.0

    async def test_summary_mixed_trades(self, service):
        """Win rate calculated correctly with mixed results."""
        trades = [
            {"user_id": "u1", "pnl": 100.0, "timestamp": datetime.utcnow()},
            {"user_id": "u1", "pnl": -30.0, "timestamp": datetime.utcnow()},
            {"user_id": "u1", "pnl": 50.0, "timestamp": datetime.utcnow()},
            {"user_id": "u1", "pnl": -20.0, "timestamp": datetime.utcnow()},
        ]
        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=trades)
        mock_col.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.service.get_db", return_value=mock_db):
            result = await service.summary("u1")

        assert result.total_pnl == 100.0  # 100 - 30 + 50 - 20
        assert result.num_trades == 4
        assert result.win_rate == 50.0  # 2 wins out of 4

    async def test_summary_none_pnl_trades_excluded(self, service):
        """Trades with pnl=None (open) should be excluded from calculations."""
        trades = [
            {"user_id": "u1", "pnl": 100.0, "timestamp": datetime.utcnow()},
            {"user_id": "u1", "pnl": None, "timestamp": datetime.utcnow()},
        ]
        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=trades)
        mock_col.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)

        with patch("app.analytics.service.get_db", return_value=mock_db):
            result = await service.summary("u1")

        assert result.num_trades == 1
        assert result.total_pnl == 100.0


# ── PEND-12: compute_strategy_metrics ────────────────────────────────────────

class TestComputeStrategyMetrics:
    """Tests for the compute_strategy_metrics() pure function."""

    def _trade(self, pnl, strategy="alpha", bot="bot1", ts=None):
        from datetime import datetime as DT
        return {
            "pnl": pnl,
            "strategy_name": strategy,
            "bot_id": bot,
            "timestamp": ts or DT(2024, 1, 15, 10, 0),
            "entry_price": 100.0,
            "exit_price": 100.0 + pnl,
            "side": "buy",
        }

    def test_empty_trades_returns_empty(self):
        from app.analytics.advanced_metrics import compute_strategy_metrics
        assert compute_strategy_metrics([], 1000.0) == []

    def test_single_strategy(self):
        from app.analytics.advanced_metrics import compute_strategy_metrics
        trades = [self._trade(10), self._trade(-5), self._trade(20)]
        result = compute_strategy_metrics(trades, 1000.0)
        assert len(result) == 1
        assert result[0]["strategy_name"] == "alpha"
        assert result[0]["total_pnl"] == pytest.approx(25.0)
        assert result[0]["num_trades"] == 3
        assert "bot1" in result[0]["bot_ids"]

    def test_two_strategies_sorted_by_pnl_desc(self):
        from app.analytics.advanced_metrics import compute_strategy_metrics
        trades = [
            self._trade(5, strategy="small"),
            self._trade(100, strategy="big"),
            self._trade(50, strategy="big"),
        ]
        result = compute_strategy_metrics(trades, 1000.0)
        assert len(result) == 2
        assert result[0]["strategy_name"] == "big"
        assert result[1]["strategy_name"] == "small"

    def test_fallback_to_strategy_field(self):
        """Trades with 'strategy' key (not 'strategy_name') are grouped correctly."""
        from app.analytics.advanced_metrics import compute_strategy_metrics
        from datetime import datetime as DT
        trades = [
            {"pnl": 10.0, "strategy": "gamma", "bot_id": "x", "timestamp": DT(2024, 1, 1)},
        ]
        result = compute_strategy_metrics(trades, 1000.0)
        assert result[0]["strategy_name"] == "gamma"

    def test_unknown_strategy_when_no_strategy_field(self):
        from app.analytics.advanced_metrics import compute_strategy_metrics
        from datetime import datetime as DT
        trades = [{"pnl": 10.0, "timestamp": DT(2024, 1, 1)}]
        result = compute_strategy_metrics(trades, 1000.0)
        assert result[0]["strategy_name"] == "unknown"

    def test_bot_ids_collected_per_strategy(self):
        from app.analytics.advanced_metrics import compute_strategy_metrics
        from datetime import datetime as DT
        trades = [
            self._trade(10, strategy="s1", bot="b1"),
            self._trade(20, strategy="s1", bot="b2"),
            self._trade(5, strategy="s1", bot="b1"),  # duplicate
        ]
        result = compute_strategy_metrics(trades, 1000.0)
        assert sorted(result[0]["bot_ids"]) == ["b1", "b2"]


# ── PEND-12: compute_heatmap ─────────────────────────────────────────────────

class TestComputeHeatmap:
    """Tests for compute_heatmap() pure function."""

    def test_empty_trades_returns_168_zero_cells(self):
        from app.analytics.advanced_metrics import compute_heatmap
        result = compute_heatmap([])
        assert len(result["cells"]) == 168  # 7 × 24
        assert all(c["avg_pnl"] == 0.0 and c["count"] == 0 for c in result["cells"])
        assert result["min_pnl"] == 0.0
        assert result["max_pnl"] == 0.0

    def test_correct_cell_for_known_timestamp(self):
        from app.analytics.advanced_metrics import compute_heatmap
        from datetime import datetime as DT
        # 2024-01-15 is a Monday → weekday() == 0
        trades = [{"pnl": 50.0, "timestamp": DT(2024, 1, 15, 9, 0)}]
        result = compute_heatmap(trades)
        mon_9 = next(c for c in result["cells"] if c["day"] == 0 and c["hour"] == 9)
        assert mon_9["avg_pnl"] == pytest.approx(50.0)
        assert mon_9["count"] == 1

    def test_avg_pnl_across_multiple_trades_same_cell(self):
        from app.analytics.advanced_metrics import compute_heatmap
        from datetime import datetime as DT
        ts = DT(2024, 1, 15, 10, 0)  # Monday 10h
        trades = [{"pnl": 40.0, "timestamp": ts}, {"pnl": 60.0, "timestamp": ts}]
        result = compute_heatmap(trades)
        cell = next(c for c in result["cells"] if c["day"] == 0 and c["hour"] == 10)
        assert cell["avg_pnl"] == pytest.approx(50.0)
        assert cell["count"] == 2

    def test_days_and_hours_labels(self):
        from app.analytics.advanced_metrics import compute_heatmap
        result = compute_heatmap([])
        assert result["days"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        assert result["hours"] == list(range(24))

    def test_trades_without_timestamp_are_skipped(self):
        from app.analytics.advanced_metrics import compute_heatmap
        trades = [{"pnl": 100.0, "timestamp": "not-a-datetime"}]
        result = compute_heatmap(trades)
        assert all(c["count"] == 0 for c in result["cells"])

    def test_min_max_pnl_reflect_cells(self):
        from app.analytics.advanced_metrics import compute_heatmap
        from datetime import datetime as DT
        trades = [
            {"pnl": -20.0, "timestamp": DT(2024, 1, 15, 8, 0)},   # Mon 08
            {"pnl": 80.0,  "timestamp": DT(2024, 1, 16, 14, 0)},  # Tue 14
        ]
        result = compute_heatmap(trades)
        assert result["min_pnl"] == pytest.approx(-20.0)
        assert result["max_pnl"] == pytest.approx(80.0)


# ── PEND-12: compute_correlation_matrix ──────────────────────────────────────

class TestComputeCorrelationMatrix:
    """Tests for compute_correlation_matrix() and _pearson() helpers."""

    def _trade(self, bot, date, pnl):
        from datetime import datetime as DT
        return {"pnl": pnl, "bot_id": bot, "timestamp": DT(*[int(p) for p in date.split("-")])}

    def test_empty_trades_returns_empty_structure(self):
        from app.analytics.advanced_metrics import compute_correlation_matrix
        result = compute_correlation_matrix([])
        assert result == {"bots": [], "matrix": []}

    def test_single_bot_diagonal_one(self):
        from app.analytics.advanced_metrics import compute_correlation_matrix
        trades = [self._trade("b1", "2024-01-01", 10.0)]
        result = compute_correlation_matrix(trades)
        assert result["bots"] == ["b1"]
        assert result["matrix"] == [[1.0]]

    def test_identical_series_correlation_is_one(self):
        from app.analytics.advanced_metrics import compute_correlation_matrix
        # Two bots with identical daily pnls → correlation = 1.0
        trades = [
            self._trade("b1", "2024-01-01", 10.0),
            self._trade("b1", "2024-01-02", 20.0),
            self._trade("b2", "2024-01-01", 10.0),
            self._trade("b2", "2024-01-02", 20.0),
        ]
        result = compute_correlation_matrix(trades)
        assert len(result["bots"]) == 2
        # Off-diagonal should be 1.0
        b1i = result["bots"].index("b1")
        b2i = result["bots"].index("b2")
        assert result["matrix"][b1i][b2i] == pytest.approx(1.0)

    def test_opposite_series_correlation_is_minus_one(self):
        from app.analytics.advanced_metrics import compute_correlation_matrix
        trades = [
            self._trade("b1", "2024-01-01", 10.0),
            self._trade("b1", "2024-01-02", -10.0),
            self._trade("b2", "2024-01-01", -10.0),
            self._trade("b2", "2024-01-02", 10.0),
        ]
        result = compute_correlation_matrix(trades)
        b1i = result["bots"].index("b1")
        b2i = result["bots"].index("b2")
        assert result["matrix"][b1i][b2i] == pytest.approx(-1.0)

    def test_matrix_is_symmetric(self):
        from app.analytics.advanced_metrics import compute_correlation_matrix
        trades = [
            self._trade("b1", "2024-01-01", 5.0),
            self._trade("b1", "2024-01-02", 3.0),
            self._trade("b2", "2024-01-01", 2.0),
            self._trade("b2", "2024-01-02", 8.0),
        ]
        result = compute_correlation_matrix(trades)
        m = result["matrix"]
        assert m[0][1] == pytest.approx(m[1][0])

    def test_diagonal_always_one(self):
        from app.analytics.advanced_metrics import compute_correlation_matrix
        trades = [
            self._trade("b1", "2024-01-01", 10.0),
            self._trade("b2", "2024-01-02", 5.0),
        ]
        result = compute_correlation_matrix(trades)
        for i in range(len(result["bots"])):
            assert result["matrix"][i][i] == pytest.approx(1.0)

    def test_pearson_helper_zero_variance(self):
        from app.analytics.advanced_metrics import _pearson
        # Constant series — denominator is 0 → returns 0.0
        assert _pearson([1.0, 1.0, 1.0], [2.0, 2.0, 2.0]) == pytest.approx(0.0)

    def test_pearson_short_series(self):
        from app.analytics.advanced_metrics import _pearson
        assert _pearson([5.0], [5.0]) == pytest.approx(0.0)  # n < 2
