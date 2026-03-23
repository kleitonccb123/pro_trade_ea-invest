"""
DailyResetJob — Reset automático do RiskState às 00:00 UTC

DOC-05 §8.2 (Edge Case: Reset Diário Seguro)

O que reseta:
  ✅ dailyPnlUSD           → 0
  ✅ peakDailyBalanceUSD   → saldo atual da conta (novo ponto de referência)
  ✅ currentDrawdownPct    → 0
  ✅ isInCooldown          → False (cooldown diário zerado)
  ✅ cooldownUntil         → None

O que NÃO reseta:
  ❌ consecutiveLosses     → persiste entre dias (tendência do bot)
  ❌ capitalAtRiskUSD      → posições abertas continuam abertas
  ❌ breachCount           → resetado semanalmente (não diariamente)

Ciclo de vida:
  await daily_reset_job.start()   # inicia via asyncio.Task
  await daily_reset_job.stop()    # para o loop no shutdown

Agendamento:
  O job dorme até meia-noite UTC e executa o reset.
  Em caso de falha, aguarda 60s e tenta novamente no mesmo ciclo.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.risk.repository import RiskRepository

logger = logging.getLogger(__name__)


class DailyResetJob:
    """
    Loop assíncrono que executa o reset de risco diário a 00:00 UTC.
    """

    def __init__(
        self,
        risk_repo: RiskRepository,
        kucoin_client: Optional[Any] = None,  # para buscar saldo real no reset
    ) -> None:
        self._repo    = risk_repo
        self._kucoin  = kucoin_client
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="daily_risk_reset")
        logger.info("DailyResetJob iniciado")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("DailyResetJob parado")

    # ── Loop principal ────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                # Aguarda até meia-noite UTC
                wait_secs = self._seconds_until_midnight()
                logger.info(
                    "DailyResetJob: aguardando %ds até meia-noite UTC", wait_secs
                )
                await asyncio.sleep(wait_secs)

                if not self._running:
                    break

                await self._execute_reset()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("DailyResetJob: erro no loop: %s — retry em 60s", exc)
                await asyncio.sleep(60)

    async def _execute_reset(self) -> None:
        """Executa o reset de todos os estados de risco ativos."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        today     = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        logger.info("DailyResetJob: iniciando reset diário do dia %s → %s", yesterday, today)

        try:
            user_ids = await self._repo.get_users_with_active_states(yesterday)
        except Exception as exc:
            logger.error("DailyResetJob: falha ao buscar usuários: %s", exc)
            return

        reset_count = 0
        for user_id in user_ids:
            try:
                await self._reset_for_user(user_id, yesterday, today)
                reset_count += 1
            except Exception as exc:
                logger.error(
                    "DailyResetJob: falha ao resetar user=%s: %s", user_id, exc
                )

        logger.info(
            "DailyResetJob: reset concluído — %d/%d usuários resetados",
            reset_count, len(user_ids),
        )

    async def _reset_for_user(
        self, user_id: str, yesterday: str, today: str
    ) -> None:
        """
        Reseta o estado de risco de um usuário para o novo dia.
        Le o estado anterior para preservar capitalAtRiskUSD e consecutiveLosses.
        """
        prev_state = await self._repo.get_or_create_risk_state(user_id, yesterday)

        # Saldo real do início do novo dia (referência para o novo peak)
        new_peak = await self._fetch_account_balance(user_id)
        if new_peak <= 0.0:
            # Fallback: usar peak anterior para não perder a referência
            new_peak = prev_state.peak_daily_balance_usd

        # Cria estado fresco para hoje
        from app.risk.models import RiskState
        new_state = RiskState(
            user_id=user_id,
            date=today,
            daily_pnl_usd=0.0,
            peak_daily_balance_usd=new_peak,
            current_drawdown_pct=0.0,
            capital_at_risk_usd=prev_state.capital_at_risk_usd,  # posições abertas persistem
            is_in_cooldown=False,                                  # cooldown reseta diariamente
            cooldown_until=None,
            consecutive_losses=prev_state.consecutive_losses,     # NÃO reseta
            breach_count=prev_state.breach_count,
        )
        await self._repo.save_risk_state(new_state)

    async def _fetch_account_balance(self, user_id: str) -> float:
        """
        Busca saldo total da conta.
        Se kucoin_client não disponível, retorna 0.0.
        """
        if self._kucoin is None:
            return 0.0
        try:
            accounts = await self._kucoin.get_accounts()
            total = 0.0
            for acc in (accounts or []):
                if acc.get("type") == "trade":
                    # Simplificado: soma todos os ativos em USDT equivalente
                    # Em produção: converter cada moeda para USDT via ticker
                    currency = acc.get("currency", "")
                    if currency == "USDT":
                        total += float(acc.get("balance", 0))
            return total
        except Exception as exc:
            logger.warning(
                "DailyResetJob: falha ao buscar saldo de user=%s: %s", user_id, exc
            )
            return 0.0

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _seconds_until_midnight() -> float:
        """Calcula segundos até a próxima meia-noite UTC."""
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return max(1.0, (tomorrow - now).total_seconds())
