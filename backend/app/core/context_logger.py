"""
BotLogger — DOC-08 §2.1

Logger contextual com campos fixos de bot/usuário/par para eliminar
repetição de contexto em cada chamada de log.

Emite eventos padronizados (trade_opened, trade_closed, risk_triggered)
compatíveis com o JSONFormatter do logging_config.py.

Uso::

    from app.core.context_logger import BotLogger

    logger = BotLogger(
        bot_instance_id="abc123",
        user_id="u1",
        pair="BTC-USDT",
    )

    logger.trade_opened(price=65000.0, qty=0.001, funds=65.0)
    logger.trade_closed(price=68000.0, pnl=2.83, reason="take_profit")
    logger.risk_triggered(reason="daily_drawdown", details={"pct": 10.5})
"""

from __future__ import annotations

import logging
from typing import Any


class BotLogger:
    """
    Logger com contexto fixo de bot/usuário para não repetir em cada chamada.
    Cada instância é associada a um (bot_instance_id, user_id, pair) específico.
    """

    def __init__(self, bot_instance_id: str, user_id: str, pair: str) -> None:
        self._logger = logging.getLogger(f"bot.{bot_instance_id[:8]}")
        self._extra: dict[str, Any] = {
            "bot_instance_id": bot_instance_id,
            "user_id": user_id,
            "pair": pair,
        }

    # ── Core log methods ──────────────────────────────────────────────────────

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        extra = {**self._extra, **kwargs}
        getattr(self._logger, level)(message, extra=extra)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log("debug", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log("info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log("warning", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log("error", message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self._log("critical", message, **kwargs)

    # ── High-level trade events ───────────────────────────────────────────────

    def trade_opened(self, price: float, qty: float, funds: float) -> None:
        """Log padronizado de abertura de posição."""
        self.info(
            f"📈 Posição aberta | preço={price} | qty={qty:.6f} | funds={funds:.2f} USDT",
            event="trade_opened",
            entry_price=price,
            quantity=qty,
            funds_usdt=funds,
        )

    def trade_closed(self, price: float, pnl: float, reason: str) -> None:
        """Log padronizado de fechamento de posição."""
        emoji = "✅" if pnl >= 0 else "❌"
        self.info(
            f"{emoji} Trade fechada | preço={price} | PnL={pnl:+.4f} USDT | motivo={reason}",
            event="trade_closed",
            exit_price=price,
            pnl_net_usdt=pnl,
            reason=reason,
        )

    def risk_triggered(self, reason: str, details: dict) -> None:
        """Log padronizado de acionamento de risco (stop automático)."""
        self.critical(
            f"⚠️ RISCO: {reason}",
            event="risk_triggered",
            stop_reason=reason,
            **details,
        )

    def cycle_error(self, error: Exception, cycle: int = 0) -> None:
        """Log de erro em ciclo de trade."""
        self.error(
            f"❌ Erro no ciclo {cycle}: {error}",
            event="cycle_error",
            error_type=type(error).__name__,
            error_message=str(error),
            cycle=cycle,
        )

    def bot_started(self) -> None:
        self.info("▶️ Bot iniciado", event="bot_started")

    def bot_stopped(self, reason: str) -> None:
        self.info(f"⏹️ Bot parado | motivo={reason}", event="bot_stopped", reason=reason)

    def bot_paused(self) -> None:
        self.info("⏸️ Bot pausado", event="bot_paused")

    def bot_resumed(self) -> None:
        self.info("▶️ Bot retomado", event="bot_resumed")
