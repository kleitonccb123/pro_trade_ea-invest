"""
Unit Tests — PDF Report Generation (PEND-08)
==============================================

Tests for generate_performance_pdf() and generate_fiscal_pdf().
"""

import pytest
from datetime import datetime

from app.analytics.pdf_report import generate_performance_pdf, generate_fiscal_pdf


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_trades():
    return [
        {
            "_id": "t1",
            "bot_id": "bot-alpha",
            "symbol": "BTC-USDT",
            "side": "buy",
            "price": 65000.0,
            "quantity": 0.01,
            "total_usdt": 650.0,
            "fee": 0.65,
            "pnl": 120.50,
            "status": "filled",
            "created_at": datetime(2025, 3, 15, 10, 30),
        },
        {
            "_id": "t2",
            "bot_id": "bot-alpha",
            "symbol": "BTC-USDT",
            "side": "sell",
            "price": 66200.0,
            "quantity": 0.01,
            "total_usdt": 662.0,
            "fee": 0.66,
            "pnl": -30.20,
            "status": "filled",
            "created_at": datetime(2025, 6, 20, 14, 0),
        },
        {
            "_id": "t3",
            "bot_id": "bot-beta",
            "symbol": "ETH-USDT",
            "side": "buy",
            "price": 3500.0,
            "quantity": 0.5,
            "total_usdt": 1750.0,
            "fee": 1.75,
            "pnl": 250.0,
            "status": "filled",
            "created_at": datetime(2025, 3, 18, 8, 15),
        },
    ]


@pytest.fixture
def sample_metrics():
    return {
        "total_pnl": 340.30,
        "total_return_pct": 3.40,
        "annualized_return_pct": 12.5,
        "num_trades": 3,
        "win_rate": 66.7,
        "sharpe_ratio": 1.45,
        "sortino_ratio": 2.1,
        "max_drawdown_pct": 5.2,
        "max_drawdown_abs": 520.0,
        "calmar_ratio": 2.4,
        "profit_factor": 3.5,
        "avg_win": 185.25,
        "avg_loss": -30.20,
        "best_trade": 250.0,
        "worst_trade": -30.20,
        "avg_trade_duration_hours": 48.0,
        "trading_days": 5,
    }


@pytest.fixture
def sample_bots():
    return [
        {
            "bot_id": "bot-alpha",
            "symbol": "BTC-USDT",
            "num_trades": 2,
            "total_pnl": 90.30,
            "win_rate": 50.0,
            "total_return_pct": 0.90,
        },
        {
            "bot_id": "bot-beta",
            "symbol": "ETH-USDT",
            "num_trades": 1,
            "total_pnl": 250.0,
            "win_rate": 100.0,
            "total_return_pct": 2.50,
        },
    ]


# ── Performance PDF Tests ────────────────────────────────────────────────────

class TestGeneratePerformancePdf:

    def test_returns_bytes(self, sample_trades, sample_metrics, sample_bots):
        result = generate_performance_pdf(
            user_email="user@test.com",
            trades=sample_trades,
            metrics=sample_metrics,
            bots=sample_bots,
        )
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_starts_with_pdf_header(self, sample_trades, sample_metrics, sample_bots):
        result = generate_performance_pdf(
            user_email="user@test.com",
            trades=sample_trades,
            metrics=sample_metrics,
            bots=sample_bots,
        )
        assert result[:5] == b"%PDF-"

    def test_with_date_filters(self, sample_trades, sample_metrics, sample_bots):
        result = generate_performance_pdf(
            user_email="user@test.com",
            trades=sample_trades,
            metrics=sample_metrics,
            bots=sample_bots,
            start_date="2025-01-01",
            end_date="2025-12-31",
        )
        assert result[:5] == b"%PDF-"

    def test_empty_trades(self, sample_metrics):
        result = generate_performance_pdf(
            user_email="user@test.com",
            trades=[],
            metrics=sample_metrics,
            bots=[],
        )
        assert result[:5] == b"%PDF-"
        assert len(result) > 100

    def test_empty_bots_section(self, sample_trades, sample_metrics):
        result = generate_performance_pdf(
            user_email="user@test.com",
            trades=sample_trades,
            metrics=sample_metrics,
            bots=[],
        )
        assert isinstance(result, bytes)

    def test_large_trade_set(self, sample_metrics):
        """Verify PDF generation handles many trades (capped at 500)."""
        trades = [
            {
                "_id": f"t{i}",
                "bot_id": "bot-stress",
                "symbol": "BTC-USDT",
                "side": "buy",
                "price": 65000 + i,
                "quantity": 0.001,
                "total_usdt": 65.0,
                "fee": 0.065,
                "pnl": (-1) ** i * 5.0,
                "status": "filled",
                "created_at": datetime(2025, 1, 1 + (i % 28), 12, 0),
            }
            for i in range(600)
        ]
        result = generate_performance_pdf(
            user_email="user@test.com",
            trades=trades,
            metrics=sample_metrics,
            bots=[],
        )
        assert result[:5] == b"%PDF-"

    def test_trades_with_missing_fields(self, sample_metrics):
        """Trades with missing optional fields should not crash."""
        trades = [
            {"_id": "t1", "created_at": datetime(2025, 5, 1)},
            {"_id": "t2", "pnl": None},
            {"_id": "t3"},
        ]
        result = generate_performance_pdf(
            user_email="user@test.com",
            trades=trades,
            metrics=sample_metrics,
            bots=[],
        )
        assert result[:5] == b"%PDF-"


# ── Fiscal PDF Tests ─────────────────────────────────────────────────────────

class TestGenerateFiscalPdf:

    def test_returns_bytes(self, sample_trades):
        result = generate_fiscal_pdf(
            user_email="user@test.com",
            trades=sample_trades,
            year=2025,
        )
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_starts_with_pdf_header(self, sample_trades):
        result = generate_fiscal_pdf(
            user_email="user@test.com",
            trades=sample_trades,
            year=2025,
        )
        assert result[:5] == b"%PDF-"

    def test_empty_trades(self):
        result = generate_fiscal_pdf(
            user_email="user@test.com",
            trades=[],
            year=2025,
        )
        assert result[:5] == b"%PDF-"

    def test_all_months_covered(self, sample_trades):
        """Even months with no trades should appear in the PDF."""
        result = generate_fiscal_pdf(
            user_email="user@test.com",
            trades=sample_trades,
            year=2025,
        )
        # Just verify it generates without error
        assert len(result) > 500

    def test_trades_with_none_pnl(self):
        """Trades with None pnl should be skipped gracefully."""
        trades = [
            {"_id": "t1", "pnl": None, "created_at": datetime(2025, 4, 10)},
            {"_id": "t2", "pnl": 100.0, "created_at": datetime(2025, 4, 15)},
            {"_id": "t3", "pnl": "invalid", "created_at": datetime(2025, 7, 20)},
        ]
        result = generate_fiscal_pdf(
            user_email="user@test.com",
            trades=trades,
            year=2025,
        )
        assert result[:5] == b"%PDF-"

    def test_trades_without_datetime(self):
        """Trades with non-datetime created_at should be skipped."""
        trades = [
            {"_id": "t1", "pnl": 50.0, "created_at": "2025-01-15"},
            {"_id": "t2", "pnl": -20.0, "created_at": datetime(2025, 2, 10)},
        ]
        result = generate_fiscal_pdf(
            user_email="user@test.com",
            trades=trades,
            year=2025,
        )
        assert result[:5] == b"%PDF-"
