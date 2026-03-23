"""
pnl/metrics_aggregator.py — In-memory accumulator for bot trading metrics (DOC_05 §5).

BotMetricsAccumulator is updated in-memory on every closed trade and periodically
persisted to MongoDB via repository.update_metrics().

The doc's `profit_factor` property used `sum(...)` as a placeholder.
This implementation tracks `total_gains_usdt` and `total_losses_abs_usdt`
as running totals so profit_factor is O(1) without DB queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotMetricsAccumulator:
    """
    Running statistics accumulator for one bot instance.

    Initialised from the values stored in MongoDB when the BotWorker starts.
    Updated after each closed trade, then flushed to MongoDB (async, via worker).
    """

    initial_capital_usdt: float
    current_capital_usdt: float

    # ── Totals ────────────────────────────────────────────────────────────────
    total_pnl_usdt:     float = 0.0
    total_fees_usdt:    float = 0.0
    total_volume_usdt:  float = 0.0
    total_trades:       int   = 0
    winning_trades:     int   = 0
    losing_trades:      int   = 0

    # ── Best / worst ──────────────────────────────────────────────────────────
    largest_win_usdt:  float = 0.0
    largest_loss_usdt: float = 0.0

    # ── Profit factor inputs (running sums) ───────────────────────────────────
    total_gains_usdt:      float = 0.0   # sum of positive pnl_net_usdt
    total_losses_abs_usdt: float = 0.0   # sum of abs(negative pnl_net_usdt)

    # ── Duration ──────────────────────────────────────────────────────────────
    avg_holding_minutes: float = 0.0

    # ── Streaks ───────────────────────────────────────────────────────────────
    consecutive_wins:     int = 0
    consecutive_losses:   int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # ── Drawdown ──────────────────────────────────────────────────────────────
    max_drawdown_pct: float = 0.0
    peak_capital:     float = 0.0

    # ── record_trade ─────────────────────────────────────────────────────────

    def record_trade(
        self,
        pnl_net_usdt:    float,
        fee_usdt:        float,
        volume_usdt:     float,
        holding_minutes: int,
    ) -> None:
        """
        Update all statistics after a trade is closed.

        Args:
            pnl_net_usdt:    net P&L in USDT (positive = profit, negative = loss)
            fee_usdt:        total fees for this trade (entry + exit)
            volume_usdt:     gross entry value (entry_funds)
            holding_minutes: duration of the trade
        """
        assert fee_usdt >= 0, f"fee_usdt must be >= 0, got {fee_usdt}"

        self.total_trades       += 1
        self.total_pnl_usdt      = round(self.total_pnl_usdt     + pnl_net_usdt, 6)
        self.total_fees_usdt     = round(self.total_fees_usdt     + fee_usdt,     6)
        self.total_volume_usdt   = round(self.total_volume_usdt   + volume_usdt,  2)
        self.current_capital_usdt = round(self.current_capital_usdt + pnl_net_usdt, 6)

        if pnl_net_usdt >= 0:
            # ── Win ───────────────────────────────────────────────────────────
            self.winning_trades       += 1
            self.consecutive_wins     += 1
            self.consecutive_losses    = 0
            self.max_consecutive_wins  = max(self.max_consecutive_wins, self.consecutive_wins)
            self.total_gains_usdt     += pnl_net_usdt
            if pnl_net_usdt > self.largest_win_usdt:
                self.largest_win_usdt = pnl_net_usdt
        else:
            # ── Loss ──────────────────────────────────────────────────────────
            self.losing_trades          += 1
            self.consecutive_losses     += 1
            self.consecutive_wins        = 0
            self.max_consecutive_losses  = max(self.max_consecutive_losses, self.consecutive_losses)
            self.total_losses_abs_usdt  += abs(pnl_net_usdt)
            if pnl_net_usdt < self.largest_loss_usdt:
                self.largest_loss_usdt = pnl_net_usdt

        # ── Drawdown ──────────────────────────────────────────────────────────
        if self.current_capital_usdt > self.peak_capital:
            self.peak_capital = self.current_capital_usdt
        elif self.peak_capital > 0:
            dd = (
                (self.peak_capital - self.current_capital_usdt) / self.peak_capital
            ) * 100
            self.max_drawdown_pct = max(self.max_drawdown_pct, dd)

        # ── Rolling average duration ──────────────────────────────────────────
        self.avg_holding_minutes = (
            (self.avg_holding_minutes * (self.total_trades - 1) + holding_minutes)
            / self.total_trades
        )

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def win_rate(self) -> float:
        """Win Rate = winning_trades / total_trades × 100"""
        if self.total_trades == 0:
            return 0.0
        return round((self.winning_trades / self.total_trades) * 100, 2)

    @property
    def profit_factor(self) -> float:
        """
        Profit Factor = total_gains / total_losses_abs.

        Ideal: > 1.5. Returns float("inf") if no losses yet.
        """
        if self.total_losses_abs_usdt == 0:
            return float("inf") if self.total_gains_usdt > 0 else 1.0
        return round(self.total_gains_usdt / self.total_losses_abs_usdt, 2)

    @property
    def roi_pct(self) -> float:
        """ROI = total_pnl / initial_capital × 100"""
        if self.initial_capital_usdt == 0:
            return 0.0
        return round((self.total_pnl_usdt / self.initial_capital_usdt) * 100, 4)

    @property
    def avg_trade_pnl(self) -> float:
        """Average PnL per trade in USDT."""
        if self.total_trades == 0:
            return 0.0
        return round(self.total_pnl_usdt / self.total_trades, 6)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a plain dict suitable for MongoDB $set."""
        return {
            "initial_capital_usdt":     self.initial_capital_usdt,
            "current_capital_usdt":     self.current_capital_usdt,
            "total_pnl_usdt":           self.total_pnl_usdt,
            "total_fees_usdt":          self.total_fees_usdt,
            "total_volume_usdt":        self.total_volume_usdt,
            "total_trades":             self.total_trades,
            "winning_trades":           self.winning_trades,
            "losing_trades":            self.losing_trades,
            "largest_win_usdt":         self.largest_win_usdt,
            "largest_loss_usdt":        self.largest_loss_usdt,
            "total_gains_usdt":         self.total_gains_usdt,
            "total_losses_abs_usdt":    self.total_losses_abs_usdt,
            "avg_holding_minutes":      self.avg_holding_minutes,
            "consecutive_wins":         self.consecutive_wins,
            "consecutive_losses":       self.consecutive_losses,
            "max_consecutive_wins":     self.max_consecutive_wins,
            "max_consecutive_losses":   self.max_consecutive_losses,
            "max_drawdown_pct":         self.max_drawdown_pct,
            "peak_capital":             self.peak_capital,
            # Computed (stored for fast API reads)
            "win_rate":                 self.win_rate,
            "profit_factor":            self.profit_factor if self.profit_factor != float("inf") else 999.0,
            "roi_pct":                  self.roi_pct,
            "avg_trade_pnl":            self.avg_trade_pnl,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BotMetricsAccumulator":
        """Reconstruct from a MongoDB metrics subdocument."""
        return cls(
            initial_capital_usdt   = d.get("initial_capital_usdt",  0.0),
            current_capital_usdt   = d.get("current_capital_usdt",  0.0),
            total_pnl_usdt         = d.get("total_pnl_usdt",         0.0),
            total_fees_usdt        = d.get("total_fees_usdt",         0.0),
            total_volume_usdt      = d.get("total_volume_usdt",       0.0),
            total_trades           = d.get("total_trades",             0),
            winning_trades         = d.get("winning_trades",           0),
            losing_trades          = d.get("losing_trades",            0),
            largest_win_usdt       = d.get("largest_win_usdt",         0.0),
            largest_loss_usdt      = d.get("largest_loss_usdt",        0.0),
            total_gains_usdt       = d.get("total_gains_usdt",         0.0),
            total_losses_abs_usdt  = d.get("total_losses_abs_usdt",    0.0),
            avg_holding_minutes    = d.get("avg_holding_minutes",      0.0),
            consecutive_wins       = d.get("consecutive_wins",          0),
            consecutive_losses     = d.get("consecutive_losses",        0),
            max_consecutive_wins   = d.get("max_consecutive_wins",      0),
            max_consecutive_losses = d.get("max_consecutive_losses",    0),
            max_drawdown_pct       = d.get("max_drawdown_pct",          0.0),
            peak_capital           = d.get("peak_capital",              0.0),
        )
