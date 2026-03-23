"""
RiskManager — Gate principal de todas as ordens

DOC-05 §5

Implementa a hierarquia de 4 camadas de controle de risco:

  Camada 1 — Plataforma global
    • Kill-switch global    (Redis key: risk:global:kill_switch = "1")
    • Volatilidade extrema  (MarketVolatilityIndexer score > 85)

  Camada 2 — Por usuário
    • Cooldown ativo (bloqueio pós-perda, mas permite fechamentos)
    • Max daily loss USD
    • Max drawdown desde peak
    • Max capital em risco simultâneo
    • Max position size por símbolo

  Camada 3 — Por bot
    • Perdas consecutivas >= consecutiveLossLimit → matar bot

  Todos os eventos são registrados no RiskAuditLog (imutável, hash encadeado).

Integração:
  - Chamado por OrderManager.safe_process_order() ANTES do Level 2 Bot Lock
  - Ou diretamente no PreflightChecker

Uso:
```python
from app.risk import get_risk_manager

rm = get_risk_manager()
from app.risk.models import RiskEvaluationInput

decision = await rm.evaluate(RiskEvaluationInput(
    user_id="u1", bot_id="b1", symbol="BTC-USDT",
    side="buy", estimated_value_usd=400.0,
    current_position_usd=0.0,
))
if not decision.approved:
    raise ValueError(f"Risco: {decision.reason} — {decision.details}")
```
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.risk.audit_log import RiskAuditLog
from app.risk.models import (
    BotRiskProfile,
    RiskDecision,
    RiskEvaluationInput,
    RiskRejectionReason,
    RiskSeverity,
    RiskState,
    UserRiskProfile,
)
from app.risk.repository import RiskRepository
from app.risk.volatility_indexer import MarketVolatilityIndexer

logger = logging.getLogger(__name__)

# DOC-06 — métricas de risco (import tardio para evitar circular)
try:
    from app.observability.metrics import (
        trading_risk_evaluation_ms,
        trading_risk_rejections_total,
    )
    _METRICS_OK = True
except Exception:  # pragma: no cover
    _METRICS_OK = False

# Redis keys
_KEY_GLOBAL_KILL    = "risk:global:kill_switch"
_KEY_BOT_KILL       = "bot:kill:{bot_id}"
_KEY_BOT_LOSSES     = "risk:bot:{bot_id}:consecutive_losses"
_KEY_BALANCE_CACHE  = "risk:balance_usd:{user_id}"


class RiskManager:
    """
    Gate institucional de risco.
    Deve ser chamado ANTES de toda ordem, dentro de `safe_process_order()`.
    """

    def __init__(
        self,
        redis_client: Optional[Any],
        risk_repo: RiskRepository,
        audit_log: RiskAuditLog,
        volatility_indexer: MarketVolatilityIndexer,
    ) -> None:
        self._redis              = redis_client
        self._repo               = risk_repo
        self._audit              = audit_log
        self._volatility         = volatility_indexer

    # ── Método principal ──────────────────────────────────────────────────────

    async def evaluate(self, inp: RiskEvaluationInput) -> RiskDecision:
        """
        GATE PRINCIPAL — avalia todos os controles de risco.
        Retorna RiskDecision(approved=True) se a ordem pode prosseguir.
        """
        _t0 = time.perf_counter()
        try:
            return await self._evaluate_inner(inp)
        finally:
            if _METRICS_OK:
                trading_risk_evaluation_ms.observe(
                    (time.perf_counter() - _t0) * 1_000
                )

    async def _evaluate_inner(self, inp: RiskEvaluationInput) -> RiskDecision:
        """Lógica interna de avaliação de risco (chamada por evaluate())."""

        # ── Camada 1: Kill-switch global ───────────────────────────────────
        if await self._is_global_kill_active():
            return await self._deny(
                inp, RiskRejectionReason.GLOBAL_KILL_SWITCH, RiskSeverity.KILL,
                "Kill switch global ativo",
            )

        # ── Camada 1: Volatilidade extrema ─────────────────────────────────
        vol_score = await self._volatility.get_volatility_score(inp.symbol)
        if vol_score > 85.0:
            return await self._deny(
                inp, RiskRejectionReason.MARKET_VOLATILITY_HIGH, RiskSeverity.BLOCK,
                f"Volatilidade extrema: score={vol_score:.1f}/100 para {inp.symbol}",
            )

        # ── Carrega perfis e estado em paralelo ────────────────────────────
        import asyncio
        today = self._today()
        user_profile, bot_profile, risk_state = await asyncio.gather(
            self._repo.get_user_profile(inp.user_id),
            self._repo.get_bot_profile(inp.bot_id, inp.user_id),
            self._repo.get_or_create_risk_state(inp.user_id, today),
        )

        # ── Camada 2: Cooldown ativo ────────────────────────────────────────
        # Exceção: ordens de fechamento NUNCA são bloqueadas por cooldown
        if not inp.is_closing_order:
            cd = await self._check_cooldown(inp, risk_state)
            if cd is not None:
                return cd

        # ── Camada 2: Max daily loss ────────────────────────────────────────
        if risk_state.daily_pnl_usd <= -user_profile.max_daily_loss_usd:
            await self._activate_cooldown(inp.user_id, today, risk_state, user_profile)
            return await self._deny(
                inp, RiskRejectionReason.MAX_DAILY_LOSS_REACHED, RiskSeverity.BLOCK,
                f"Daily loss atingido: PnL={risk_state.daily_pnl_usd:.2f} USD, "
                f"limite=-{user_profile.max_daily_loss_usd:.2f} USD",
            )

        # ── Camada 2: Max drawdown ──────────────────────────────────────────
        if risk_state.current_drawdown_pct >= user_profile.max_drawdown_pct:
            return await self._deny(
                inp, RiskRejectionReason.MAX_DRAWDOWN_REACHED, RiskSeverity.BLOCK,
                f"Drawdown atingido: {risk_state.current_drawdown_pct:.2f}% "
                f">= limite {user_profile.max_drawdown_pct:.2f}%",
            )

        # ── Camada 2: Max capital em risco ──────────────────────────────────
        account_balance = await self._get_account_balance(inp.user_id)
        capital_limit   = account_balance * (user_profile.max_capital_at_risk_pct / 100.0)
        projected_cap   = risk_state.capital_at_risk_usd + inp.estimated_value_usd

        if projected_cap > capital_limit:
            return await self._deny(
                inp, RiskRejectionReason.MAX_CAPITAL_AT_RISK, RiskSeverity.WARN,
                f"Capital em risco: projetado={projected_cap:.2f} USD, "
                f"limite={capital_limit:.2f} USD "
                f"({user_profile.max_capital_at_risk_pct:.0f}% de {account_balance:.2f} USD)",
            )

        # ── Camada 2: Max position size ─────────────────────────────────────
        projected_pos = inp.current_position_usd + inp.estimated_value_usd
        if projected_pos > user_profile.max_position_size_usd:
            return await self._deny(
                inp, RiskRejectionReason.MAX_POSITION_SIZE, RiskSeverity.BLOCK,
                f"Posição máxima: projetada={projected_pos:.2f} USD, "
                f"limite={user_profile.max_position_size_usd:.2f} USD em {inp.symbol}",
            )

        # ── Camada 3: Bot morto (kill) ──────────────────────────────────────
        if await self._is_bot_killed(inp.bot_id):
            return await self._deny(
                inp, RiskRejectionReason.BOT_KILLED, RiskSeverity.KILL,
                f"Bot {inp.bot_id} foi desativado pelo Risk Manager",
            )

        # ── Camada 3: Perdas consecutivas ───────────────────────────────────
        consecutive = await self._get_bot_consecutive_losses(inp.bot_id)
        if consecutive >= bot_profile.consecutive_loss_limit:
            await self._kill_bot(
                inp.bot_id,
                f"{consecutive} perdas consecutivas >= limite {bot_profile.consecutive_loss_limit}",
            )
            return await self._deny(
                inp, RiskRejectionReason.CONSECUTIVE_LOSSES_LIMIT, RiskSeverity.KILL,
                f"Bot {inp.bot_id} morto após {consecutive} perdas consecutivas",
            )

        # ── Aprovado ────────────────────────────────────────────────────────
        await self._audit.record(
            user_id=inp.user_id, bot_id=inp.bot_id, symbol=inp.symbol,
            action="APPROVED",
            context={
                "vol_score":          vol_score,
                "daily_pnl_usd":      risk_state.daily_pnl_usd,
                "drawdown_pct":       risk_state.current_drawdown_pct,
                "capital_at_risk_usd": risk_state.capital_at_risk_usd,
                "estimated_value_usd": inp.estimated_value_usd,
            },
        )
        return RiskDecision.allow()

    # ── recordTradeClosed ─────────────────────────────────────────────────────

    async def record_trade_closed(
        self,
        user_id: str,
        bot_id: str,
        pnl_usd: float,
    ) -> None:
        """
        Registra o resultado de um trade fechado e atualiza o RiskState.
        Deve ser chamado pelo ExecutionProcessor após cada trade finalizado.
        """
        today = self._today()
        state = await self._repo.get_or_create_risk_state(user_id, today)

        new_daily_pnl = state.daily_pnl_usd + pnl_usd

        # Peak: sobe quando há lucro, nunca desce
        peak = max(state.peak_daily_balance_usd, state.peak_daily_balance_usd + pnl_usd)

        # Drawdown = (peak - saldo_atual) / peak × 100
        current_balance = await self._get_account_balance(user_id)
        drawdown = ((peak - current_balance) / peak * 100.0) if peak > 0 else 100.0
        drawdown = max(0.0, min(100.0, drawdown))

        new_consecutive = 0 if pnl_usd >= 0 else state.consecutive_losses + 1

        await self._repo.update_risk_state(user_id, today, {
            "daily_pnl_usd":         new_daily_pnl,
            "peak_daily_balance_usd": peak,
            "current_drawdown_pct":   drawdown,
            "consecutive_losses":     new_consecutive,
        })

        # Atualizar consecutive losses do bot no Redis
        if self._redis is not None:
            try:
                bot_key = _KEY_BOT_LOSSES.format(bot_id=bot_id)
                if pnl_usd < 0:
                    await self._redis.incr(bot_key)
                    await self._redis.expire(bot_key, 86_400)  # TTL 24h
                else:
                    await self._redis.delete(bot_key)
            except Exception as exc:
                logger.warning("RiskManager.record_trade_closed: redis error: %s", exc)

        logger.info(
            "RiskManager: trade registrado user=%s bot=%s pnl=%.2f "
            "daily_pnl=%.2f drawdown=%.2f%%",
            user_id, bot_id, pnl_usd, new_daily_pnl, drawdown,
        )

    # ── Admin helpers ─────────────────────────────────────────────────────────

    async def activate_global_kill_switch(self) -> None:
        """Ativa o kill-switch global (bloqueia TODAS as novas ordens)."""
        if self._redis is not None:
            await self._redis.set(_KEY_GLOBAL_KILL, "1")
        logger.critical("RiskManager: KILL SWITCH GLOBAL ATIVADO")

    async def deactivate_global_kill_switch(self) -> None:
        if self._redis is not None:
            await self._redis.delete(_KEY_GLOBAL_KILL)
        logger.warning("RiskManager: kill switch global desativado")

    async def update_balance_cache(self, user_id: str, balance_usd: float) -> None:
        """Atualiza o cache de saldo usado para cálculo de limites de capital."""
        if self._redis is not None:
            key = _KEY_BALANCE_CACHE.format(user_id=user_id)
            try:
                await self._redis.setex(key, 300, str(balance_usd))  # TTL 5min
            except Exception as exc:
                logger.warning("RiskManager.update_balance_cache: %s", exc)

    # ── Privados ──────────────────────────────────────────────────────────────

    async def _check_cooldown(
        self, inp: RiskEvaluationInput, state: RiskState
    ) -> Optional[RiskDecision]:
        """Retorna um RiskDecision de rejeição se cooldown ativo, senão None."""
        if not state.is_in_cooldown:
            return None
        if state.cooldown_until is None:
            return None

        now = datetime.now(timezone.utc)
        # Normaliza para tz-aware se necessário
        cd_until = state.cooldown_until
        if cd_until.tzinfo is None:
            cd_until = cd_until.replace(tzinfo=timezone.utc)

        if cd_until <= now:
            # Cooldown expirou — limpa
            await self._repo.update_risk_state(inp.user_id, self._today(), {
                "is_in_cooldown": False,
                "cooldown_until": None,
            })
            return None

        remaining = (cd_until - now).total_seconds() / 60.0
        return await self._deny(
            inp, RiskRejectionReason.COOLDOWN_ACTIVE, RiskSeverity.BLOCK,
            f"Cooldown ativo: {remaining:.0f}min restantes",
        )

    async def _activate_cooldown(
        self,
        user_id: str,
        today: str,
        state: RiskState,
        profile: UserRiskProfile,
    ) -> None:
        from datetime import timedelta
        cd_until = datetime.now(timezone.utc) + timedelta(
            minutes=profile.cooldown_duration_minutes
        )
        await self._repo.update_risk_state(user_id, today, {
            "is_in_cooldown":  True,
            "cooldown_until":  cd_until,
            "breach_count":    state.breach_count + 1,
        })
        logger.warning(
            "RiskManager: cooldown ativado user=%s por %d min até %s",
            user_id, profile.cooldown_duration_minutes, cd_until.isoformat(),
        )

    async def _kill_bot(self, bot_id: str, reason: str) -> None:
        if self._redis is not None:
            try:
                key = _KEY_BOT_KILL.format(bot_id=bot_id)
                await self._redis.setex(key, 86_400 * 7, "1")  # 7 dias
            except Exception as exc:
                logger.warning("RiskManager._kill_bot: redis error: %s", exc)
        logger.error("RiskManager: BOT MORTO bot=%s motivo=%s", bot_id, reason)

    async def _is_bot_killed(self, bot_id: str) -> bool:
        if self._redis is None:
            return False
        try:
            val = await self._redis.get(_KEY_BOT_KILL.format(bot_id=bot_id))
            return val == "1" or val == b"1"
        except Exception:
            return False

    async def _is_global_kill_active(self) -> bool:
        if self._redis is None:
            return False
        try:
            val = await self._redis.get(_KEY_GLOBAL_KILL)
            return val == "1" or val == b"1"
        except Exception:
            return False

    async def _get_bot_consecutive_losses(self, bot_id: str) -> int:
        if self._redis is None:
            return 0
        try:
            val = await self._redis.get(_KEY_BOT_LOSSES.format(bot_id=bot_id))
            return int(val or 0)
        except Exception:
            return 0

    async def _get_account_balance(self, user_id: str) -> float:
        if self._redis is None:
            return 0.0
        try:
            cached = await self._redis.get(_KEY_BALANCE_CACHE.format(user_id=user_id))
            return float(cached or 0)
        except Exception:
            return 0.0

    async def _deny(
        self,
        inp: RiskEvaluationInput,
        reason: RiskRejectionReason,
        severity: RiskSeverity,
        details: str,
    ) -> RiskDecision:
        logger.warning(
            "RiskManager: REJEITADO reason=%s severity=%s user=%s bot=%s "
            "symbol=%s details=%s",
            reason.value, severity.value, inp.user_id, inp.bot_id,
            inp.symbol, details,
        )
        # DOC-06: incrementa contador de rejeições
        if _METRICS_OK:
            try:
                trading_risk_rejections_total.labels(
                    reason=reason.value, severity=severity.value
                ).inc()
            except Exception:
                pass
        await self._audit.record(
            user_id=inp.user_id, bot_id=inp.bot_id, symbol=inp.symbol,
            action="REJECTED",
            reason=reason.value,
            severity=severity.value,
            details=details,
        )
        return RiskDecision.deny(reason, severity, details)

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ─── Instância global ─────────────────────────────────────────────────────────

_risk_manager: Optional[RiskManager] = None


def init_risk_manager(
    redis_client: Optional[Any],
    risk_repo: RiskRepository,
    audit_log: RiskAuditLog,
    volatility_indexer: MarketVolatilityIndexer,
) -> RiskManager:
    global _risk_manager
    _risk_manager = RiskManager(redis_client, risk_repo, audit_log, volatility_indexer)
    logger.info("RiskManager inicializado")
    return _risk_manager


def get_risk_manager() -> Optional[RiskManager]:
    return _risk_manager
