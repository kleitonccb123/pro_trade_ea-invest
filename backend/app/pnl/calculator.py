"""
pnl/calculator.py — Stateless PnL calculation helpers (DOC_05 §4).

All methods are pure functions / @staticmethods with no external I/O.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.engine.trade_models import TradeRecord, TradeRecordStatus

logger = logging.getLogger("pnl.calculator")

# ── Fee constants (KuCoin Spot standard tier) ─────────────────────────────────
MAKER_FEE = 0.001   # 0.10%
TAKER_FEE = 0.001   # 0.10%


class PnLCalculator:
    """
    Stateless PnL calculator.

    All methods are @staticmethod / @classmethod so they can be called
    without instantiation — e.g. PnLCalculator.close_trade(trade, ...).
    """

    # ── Fee helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def calculate_entry_fee(funds_usdt: float, order_type: str = "market") -> float:
        """
        Fee for the entry order.
        market → taker fee | limit → maker fee
        """
        assert funds_usdt >= 0, "funds_usdt must be >= 0"
        rate = TAKER_FEE if order_type == "market" else MAKER_FEE
        fee = round(funds_usdt * rate, 8)
        assert fee >= 0, "Calculated entry fee must be >= 0"
        return fee

    @staticmethod
    def calculate_exit_fee(exit_value_usdt: float, order_type: str = "market") -> float:
        """
        Fee for the exit order, computed on gross exit proceeds.
        """
        assert exit_value_usdt >= 0, "exit_value_usdt must be >= 0"
        rate = TAKER_FEE if order_type == "market" else MAKER_FEE
        fee = round(exit_value_usdt * rate, 8)
        assert fee >= 0, "Calculated exit fee must be >= 0"
        return fee

    @staticmethod
    def calculate_entry_quantity(
        funds_usdt: float,
        entry_price: float,
        fee_usdt: float,
    ) -> float:
        """
        Effective quantity received after fee deduction.

        quantity = (funds - fee) / price
        """
        assert entry_price > 0, "entry_price must be > 0"
        net_funds = funds_usdt - fee_usdt
        qty = round(net_funds / entry_price, 8)
        assert qty > 0, "Calculated entry_quantity must be > 0"
        return qty

    # ── Slippage ──────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_slippage(
        expected_price: float,
        executed_price: float,
        side: str,
    ) -> float:
        """
        Slippage as a percentage.  Negative = worse execution.

        Buy  side: higher executed price → negative slippage
        Sell side: lower  executed price → negative slippage
        """
        if expected_price <= 0:
            return 0.0
        raw_pct = ((executed_price - expected_price) / expected_price) * 100
        return round(-raw_pct if side.lower() == "buy" else raw_pct, 6)

    # ── Trade close ───────────────────────────────────────────────────────────

    @classmethod
    def close_trade(
        cls,
        trade: TradeRecord,
        exit_price: float,
        exit_quantity: float,
        exit_order_id: str,
        exit_reason: str,
        exit_order_type: str = "market",
        expected_exit_price: Optional[float] = None,
    ) -> TradeRecord:
        """
        Closes an open TradeRecord and computes all PnL fields.

        Mutates and returns the same TradeRecord instance so callers can
        chain: closed = PnLCalculator.close_trade(trade, ...) and then
        persist the result.
        """
        assert exit_price > 0,    "exit_price must be > 0"
        assert exit_quantity > 0, "exit_quantity must be > 0"
        assert trade.is_open,     f"Trade {trade.entry_order_id} is already {trade.status}"

        # ── Exit proceeds ──────────────────────────────────────────────────────
        exit_gross_usdt = exit_price * exit_quantity
        exit_fee_usdt   = cls.calculate_exit_fee(exit_gross_usdt, exit_order_type)

        # ── PnL computation ────────────────────────────────────────────────────
        #   pnl_gross = (exit gross revenue) - (entry cost, before fees)
        #   pnl_net   = pnl_gross      - entry_fee - exit_fee
        #   roi_pct   = pnl_net / entry_funds * 100
        pnl_gross  = exit_gross_usdt - trade.entry_funds
        total_fees = trade.entry_fee_usdt + exit_fee_usdt
        pnl_net    = pnl_gross - total_fees
        pnl_net_pct = (pnl_net / trade.entry_funds) * 100 if trade.entry_funds else 0.0
        roi_pct     = pnl_net_pct  # identical — kept for frontend clarity

        # ── Slippage ───────────────────────────────────────────────────────────
        exit_slippage = (
            cls.calculate_slippage(expected_exit_price, exit_price, "sell")
            if expected_exit_price
            else None
        )

        # ── Duration ───────────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        # Ensure both datetimes are tz-aware before subtraction
        entry_ts = trade.entry_timestamp
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.replace(tzinfo=timezone.utc)
        holding_minutes = max(0, int((now - entry_ts).total_seconds() / 60))

        # ── Mutate record ──────────────────────────────────────────────────────
        trade.exit_order_id      = exit_order_id
        trade.exit_price         = exit_price
        trade.exit_quantity      = exit_quantity
        trade.exit_fee_usdt      = exit_fee_usdt
        trade.exit_timestamp     = now
        trade.exit_reason        = exit_reason
        trade.expected_exit_price = expected_exit_price
        trade.exit_slippage_pct  = exit_slippage
        trade.pnl_gross_usdt     = round(pnl_gross, 6)
        trade.pnl_net_usdt       = round(pnl_net, 6)
        trade.pnl_net_pct        = round(pnl_net_pct, 4)
        trade.roi_pct            = round(roi_pct, 4)
        trade.holding_minutes    = holding_minutes
        trade.status             = TradeRecordStatus.CLOSED

        logger.info(
            "Trade fechada: %s | PnL líquido: %+.4f USDT (%+.2f%%) | "
            "Fees: %.4f USDT | Razão: %s | Duração: %dmin",
            trade.bot_instance_id,
            pnl_net, pnl_net_pct,
            total_fees,
            exit_reason,
            holding_minutes,
        )
        return trade

    # ── Unrealized PnL ────────────────────────────────────────────────────────

    @staticmethod
    def calc_unrealized_pnl(
        entry_price:    float,
        current_price:  float,
        entry_quantity: float,
        entry_fee_usdt: float,
    ) -> dict:
        """
        PnL for an open position at the current market price.

        Returns:
          unrealized_pnl_usdt  — absolute gain/loss vs initial cost
          unrealized_pnl_pct   — percentage vs initial cost
          current_value_usdt   — mark-to-market value of position
        """
        current_value = current_price * entry_quantity
        initial_cost  = entry_price   * entry_quantity + entry_fee_usdt

        unrealized_usdt = current_value - initial_cost
        unrealized_pct  = (unrealized_usdt / initial_cost * 100) if initial_cost else 0.0

        return {
            "unrealized_pnl_usdt":  round(unrealized_usdt, 4),
            "unrealized_pnl_pct":   round(unrealized_pct,  4),
            "current_value_usdt":   round(current_value,   4),
        }
