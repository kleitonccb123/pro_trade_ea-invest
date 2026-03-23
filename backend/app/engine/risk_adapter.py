"""
RiskAdapter — bridges BotWorker to the platform's risk layer.

Responsibilities:
  - Position-level stop-loss / take-profit / trailing stop / max holding time
  - Session daily-drawdown / consecutive-loss / error-burst circuit breakers
  - Kill-switch check (global / per-user / per-bot via Redis)

Delegates to:
  app.risk.manager.PositionRiskManager  — all position & session logic
  app.risk.kill_switch.KillSwitchService — Redis kill-switch checks

Backward-compatible public API (worker.py still calls the same methods):
  check_position_exit(entry_price, current_price, entry_timestamp) → Optional[str]
  record_trade_result(pnl_net)
  check_kill_switch(user_id) → Optional[str]
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.risk.manager import PositionRiskManager, RiskConfig, StopReason

logger = logging.getLogger("engine.risk")


class RiskAdapter:
    """
    Thin adapter that wires BotWorker to PositionRiskManager + KillSwitchService.
    One instance per BotWorker.

    Config keys recognised (all optional, have defaults):
      stop_loss_pct              — % queda desde entrada (default 2.5)
      take_profit_pct            — % alta desde entrada (default 5.0)
      trailing_stop              — bool (default False)
      trailing_stop_pct          — % queda desde pico (default 2.5)
      max_holding_hours          — 0 = desabilitado (default 0)
      max_daily_loss             — USDT absoluto, legacy; preferir max_daily_drawdown_pct
      max_daily_drawdown_pct     — % sobre capital inicial (default 10.0)
      max_consecutive_losses     — 0 = desabilitado (default 5)
      max_error_burst            — N erros em janela (default 10)
      error_burst_window_seconds — janela em segundos (default 300)
    """

    def __init__(self, bot_id: str, config: dict):
        self.bot_id = bot_id

        # ── Suporte legado ao campo max_daily_loss (USDT absoluto) ────────
        # O novo max_daily_drawdown_pct (%) tem precedência se presente.
        self._max_daily_loss_usdt: float = float(config.get("max_daily_loss", 50.0))

        cfg = RiskConfig.from_dict({
            "stop_loss_pct":              float(config.get("stop_loss_pct", 2.5)),
            "take_profit_pct":            float(config.get("take_profit_pct", 5.0)),
            "trailing_stop":              bool(config.get("trailing_stop", False)),
            "trailing_stop_pct":          float(config.get("trailing_stop_pct", 2.5)),
            "max_holding_hours":          float(config.get("max_holding_hours", 0.0)),
            "max_daily_drawdown_pct":     float(config.get("max_daily_drawdown_pct", 10.0)),
            "max_consecutive_losses":     int(config.get("max_consecutive_losses", 5)),
            "max_error_burst":            int(config.get("max_error_burst", 10)),
            "error_burst_window_seconds": int(config.get("error_burst_window_seconds", 300)),
        })

        self._rm = PositionRiskManager(bot_id=bot_id, config=cfg)


    # ── Public API (backward-compatible with BotWorker calls) ─────────────────

    def check_position_exit(
        self,
        entry_price: float,
        current_price: float,
        entry_timestamp: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Returns a string exit reason if the position should be closed now, else None.

        Delegates to PositionRiskManager which implements all 3 exit conditions:
          stop_loss, take_profit, trailing_stop, max_holding_time.
        """
        reason: Optional[StopReason] = self._rm.check_position_exit(
            entry_price=entry_price,
            current_price=current_price,
            entry_timestamp=entry_timestamp,
        )
        return reason.value if reason else None

    def record_trade_result(self, pnl_net: float) -> Optional[str]:
        """
        Records a closed trade's PnL and returns a stop reason if a session
        circuit-breaker was triggered (daily_drawdown or consecutive_losses).

        BotWorker should stop the session if this returns a non-None value.
        """
        # Legacy: also check absolute max_daily_loss in USDT
        reason: Optional[StopReason] = self._rm.record_trade_result(pnl_net)

        if reason:
            return reason.value

        # Fallback: legacy absolute-USDT daily loss cap
        if self._rm.session_pnl <= -abs(self._max_daily_loss_usdt):
            return f"daily_loss_cap_{abs(self._max_daily_loss_usdt):.2f}usdt"

        return None

    def record_error(self) -> Optional[str]:
        """
        Records an execution error.
        Returns 'error_burst' reason string if the burst threshold is exceeded.
        """
        reason: Optional[StopReason] = self._rm.record_error()
        return reason.value if reason else None

    async def check_kill_switch(self, user_id: str) -> Optional[str]:
        """
        Returns a stop reason string if any kill-switch is active.

        Checks in order:
          1. Global kill switch (Redis key: kill_switch:global)
          2. User kill switch   (Redis key: kill_switch:user:{user_id})
        """
        try:
            from app.risk.kill_switch import KillSwitchService
            svc = await KillSwitchService.from_app_redis()
            return await svc.check_should_stop(user_id=user_id, bot_id=self.bot_id)
        except Exception as exc:
            logger.debug("RiskAdapter.check_kill_switch: %s", exc)
            return None

    # ── Convenience pass-throughs ─────────────────────────────────────────────

    def set_initial_capital(self, capital_usdt: float) -> None:
        """Set the starting capital for daily drawdown % calculation."""
        self._rm.set_initial_capital(capital_usdt)

    @property
    def session_pnl(self) -> float:
        return self._rm.session_pnl

    @property
    def consecutive_losses(self) -> int:
        return self._rm.consecutive_losses
