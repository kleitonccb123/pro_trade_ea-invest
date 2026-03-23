"""
RiskRepository — CRUD de perfis e estados de risco no MongoDB

DOC-05 §4

Coleções:
  risk_user_profiles   — UserRiskProfile por userId (upsert)
  risk_bot_profiles    — BotRiskProfile por botId (upsert)
  risk_states          — RiskState por (userId, date), índice composto único
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.risk.models import BotRiskProfile, RiskState, UserRiskProfile

logger = logging.getLogger(__name__)

# Perfis padrão usados quando o usuário/bot ainda não tem um perfil configurado
_DEFAULT_USER_LIMITS: Dict[str, Any] = {
    "max_daily_loss_usd":             500.0,
    "max_drawdown_pct":               20.0,
    "max_capital_at_risk_pct":        40.0,
    "max_position_size_usd":          2000.0,
    "max_aggregated_position_usd":    5000.0,
    "cooldown_after_loss_minutes":    30,
    "cooldown_after_consecutive_losses": 3,
    "cooldown_duration_minutes":      60,
    "auto_kill_after_loss_breaches":  2,
    "plan":                           "basic",
}

_DEFAULT_BOT_LIMITS: Dict[str, Any] = {
    "max_daily_loss_usd":    200.0,
    "max_open_positions":    3,
    "max_single_order_usd":  500.0,
    "consecutive_loss_limit": 5,
}


class RiskRepository:
    """Acesso ao MongoDB para perfis e estados de risco."""

    def __init__(self, db: Any) -> None:
        self._db = db

    # ── Indexes ───────────────────────────────────────────────────────────────

    async def ensure_indexes(self) -> None:
        try:
            await self._db["risk_user_profiles"].create_index(
                "user_id", unique=True
            )
            await self._db["risk_bot_profiles"].create_index(
                "bot_id", unique=True
            )
            await self._db["risk_states"].create_index(
                [("user_id", 1), ("date", 1)], unique=True
            )
            logger.info("RiskRepository: índices criados/verificados")
        except Exception as exc:
            logger.warning("RiskRepository.ensure_indexes: %s", exc)

    # ── UserRiskProfile ───────────────────────────────────────────────────────

    async def get_user_profile(self, user_id: str) -> UserRiskProfile:
        """
        Retorna o perfil do usuário.
        Se não existir, cria um com os limites padrão.
        """
        doc = await self._db["risk_user_profiles"].find_one({"user_id": user_id})
        if doc:
            return UserRiskProfile.from_doc(doc)

        # Cria perfil default
        profile = UserRiskProfile(user_id=user_id, **_DEFAULT_USER_LIMITS)
        await self.save_user_profile(profile)
        logger.info("RiskRepository: perfil padrão criado para user=%s", user_id)
        return profile

    async def save_user_profile(self, profile: UserRiskProfile) -> None:
        profile.updated_at = datetime.now(timezone.utc)
        doc = profile.to_doc()
        await self._db["risk_user_profiles"].update_one(
            {"user_id": profile.user_id},
            {"$set": doc},
            upsert=True,
        )

    # ── BotRiskProfile ────────────────────────────────────────────────────────

    async def get_bot_profile(self, bot_id: str, user_id: str = "") -> BotRiskProfile:
        doc = await self._db["risk_bot_profiles"].find_one({"bot_id": bot_id})
        if doc:
            return BotRiskProfile.from_doc(doc)

        profile = BotRiskProfile(bot_id=bot_id, user_id=user_id, **_DEFAULT_BOT_LIMITS)
        await self.save_bot_profile(profile)
        logger.info("RiskRepository: perfil padrão criado para bot=%s", bot_id)
        return profile

    async def save_bot_profile(self, profile: BotRiskProfile) -> None:
        profile.updated_at = datetime.now(timezone.utc)
        doc = profile.to_doc()
        await self._db["risk_bot_profiles"].update_one(
            {"bot_id": profile.bot_id},
            {"$set": doc},
            upsert=True,
        )

    # ── RiskState ─────────────────────────────────────────────────────────────

    async def get_or_create_risk_state(
        self, user_id: str, date: str
    ) -> RiskState:
        """
        Retorna o estado de risco do usuário para hoje (criando se não existir).
        """
        doc = await self._db["risk_states"].find_one(
            {"user_id": user_id, "date": date}
        )
        if doc:
            return RiskState.from_doc(doc)

        state = RiskState(user_id=user_id, date=date)
        await self.save_risk_state(state)
        return state

    async def get_risk_state(
        self, user_id: str, date: str
    ) -> Optional[RiskState]:
        doc = await self._db["risk_states"].find_one(
            {"user_id": user_id, "date": date}
        )
        return RiskState.from_doc(doc) if doc else None

    async def save_risk_state(self, state: RiskState) -> None:
        state.updated_at = datetime.now(timezone.utc)
        doc = state.to_doc()
        await self._db["risk_states"].update_one(
            {"user_id": state.user_id, "date": state.date},
            {"$set": doc},
            upsert=True,
        )

    async def update_risk_state(
        self, user_id: str, date: str, updates: Dict[str, Any]
    ) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self._db["risk_states"].update_one(
            {"user_id": user_id, "date": date},
            {"$set": updates},
            upsert=True,
        )

    async def get_users_with_active_states(self, date: str) -> List[str]:
        """Retorna lista de user_ids com estado ativo na data."""
        cursor = self._db["risk_states"].find(
            {"date": date}, {"user_id": 1, "_id": 0}
        )
        docs = await cursor.to_list(length=10_000)
        return [d["user_id"] for d in docs]
