"""
Activation Manager Service

Gerencia o sistema de cr?ditos de ativa??o, valida??es de singleton,
e hist?rico de swaps (remanejamentos de configura??o).

Regras de Neg?cio:
1. CR?DITOS: Usu?rio recebe cr?ditos ao assinar plano (Starter=1, Pro=5, Premium=15)
2. SINGLETON: Apenas 1 rob? pode estar running por vez (graceful_stop autom?tico)
3. SWAP LIMIT: Primeiras 2 mudan?as estruturais s?o gratuitas, 3?+ custa 1 cr?dito
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId

from app.users import repository as user_repo
from app.bots import repository as bots_repo
from app.core.database import get_db

logger = logging.getLogger(__name__)


class ActivationManager:
    """Gerencia cr?ditos de ativa??o, execu??o singleton e limites de swap."""

    # Planos e seus cr?ditos
    PLAN_CREDITS = {
        "starter": 1,
        "pro": 5,
        "premium": 15,
        "enterprise": 100,  # Customiz?vel
    }

    # Limites de swap gratuitos
    FREE_SWAPS_LIMIT = 2

    @classmethod
    async def validate_activation(
        cls,
        user_id: str | ObjectId,
        bot_id: str | ObjectId
    ) -> Dict[str, Any]:
        """
        Valida se um usu?rio pode ativar um bot.

        Verifica:
        1. Se o usu?rio tem cr?ditos dispon?veis
        2. Se o bot j? foi ativado (consome cr?dito apenas na 1? ativa??o)
        3. Aplica graceful stop ao bot anterior se necess?rio

        Returns:
            {
                "can_activate": bool,
                "credits_remaining": int,
                "requires_credit_consumption": bool,
                "previous_bot_id": str | None,
                "message": str
            }

        Raises:
            ValueError: Se usu?rio n?o encontrado ou bot n?o encontrado
        """
        user = await user_repo.find_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)

        bot = await bots_repo.find_bot_by_id(bot_id)
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")

        # Verificar cr?ditos dispon?veis
        credits_remaining = user.get("activation_credits", 1) - user.get(
            "activation_credits_used", 0
        )

        # Verificar se bot j? foi ativado
        is_first_activation = not bot.get("is_active_slot", False)
        requires_credit = is_first_activation

        if requires_credit and credits_remaining <= 0:
            return {
                "can_activate": False,
                "credits_remaining": 0,
                "requires_credit_consumption": requires_credit,
                "previous_bot_id": None,
                "message": "Insufficient activation credits. Upgrade your plan.",
            }

        # Buscar bot anteriormente em execu??o (singleton check)
        previous_bot = await cls._find_running_bot(user_id)

        return {
            "can_activate": True,
            "credits_remaining": credits_remaining - (1 if requires_credit else 0),
            "requires_credit_consumption": requires_credit,
            "previous_bot_id": str(previous_bot.get("_id")) if previous_bot else None,
            "message": "Ready to activate bot.",
        }

    @classmethod
    async def activate_bot(
        cls,
        user_id: str | ObjectId,
        bot_id: str | ObjectId,
        graceful_stop_previous: bool = True,
    ) -> Dict[str, Any]:
        """
        Ativa um bot, consumindo cr?ditos se necess?rio.

        Steps:
        1. Validar ativa??o
        2. Se h? bot anterior, fazer graceful_stop
        3. Marcar novo bot como active_slot
        4. Consumir cr?dito se primeira ativa??o
        5. Registrar timestamp de execu??o

        Returns:
            {
                "activated": bool,
                "bot_id": str,
                "credits_consumed": int,
                "previous_bot_stopped": bool,
                "timestamp": datetime
            }
        """
        # Validar
        validation = await cls.validate_activation(user_id, bot_id)
        if not validation["can_activate"]:
            raise ValueError(validation["message"])

        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)

        # Graceful stop ao bot anterior
        previous_bot_stopped = False
        if validation["previous_bot_id"] and graceful_stop_previous:
            prev_bot_oid = ObjectId(validation["previous_bot_id"])
            await cls.graceful_stop_bot(user_id, prev_bot_oid)
            previous_bot_stopped = True

        # Atualizar novo bot como active_slot
        now = datetime.utcnow()
        credits_consumed = 1 if validation["requires_credit_consumption"] else 0

        await bots_repo.update_bot(
            bot_id,
            {
                "is_active_slot": True,
                "is_running": True,
                "last_run_timestamp": now,
                "activation_credits_used": credits_consumed,
            },
        )

        # Consumir cr?dito do usu?rio se necess?rio
        if credits_consumed > 0:
            await user_repo.update(
                user_id,
                {
                    "activation_credits_used": (
                        user.get("activation_credits_used", 0) + credits_consumed
                    )
                },
            )

        logger.info(
            f"? Bot {bot_id} activated for user {user_id}. "
            f"Credits consumed: {credits_consumed}"
        )

        return {
            "activated": True,
            "bot_id": str(bot_id),
            "credits_consumed": credits_consumed,
            "previous_bot_stopped": previous_bot_stopped,
            "timestamp": now,
        }

    @classmethod
    async def _find_running_bot(cls, user_id: str | ObjectId) -> Optional[Dict]:
        """Encontra o bot em execu??o do usu?rio."""
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        db = get_db()
        bots_col = db["bots"]

        running_bot = await bots_col.find_one(
            {"user_id": user_id, "is_running": True, "is_active_slot": True}
        )
        return running_bot

    @classmethod
    async def graceful_stop_bot(
        cls, user_id: str | ObjectId, bot_id: str | ObjectId
    ) -> bool:
        """
        Para um bot de forma graceful (segura).

        Remove-o do slot ativo, mas mant?m hist?rico e estat?sticas.
        """
        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)

        now = datetime.utcnow()

        result = await bots_repo.update_bot(
            bot_id,
            {
                "is_running": False,
                "is_active_slot": False,
                "status": "stopped",
                "last_updated": now,
            },
        )

        logger.info(f"?? Bot {bot_id} gracefully stopped.")
        return result is not None

    @classmethod
    async def validate_swap(
        cls, user_id: str | ObjectId, bot_id: str | ObjectId
    ) -> Dict[str, Any]:
        """
        Valida se um swap (reconfigura??o) ? permitido e custo associado.

        Regra: Primeiras 2 swaps s?o gratuitas. A partir da 3?, custa 1 cr?dito.

        Returns:
            {
                "can_swap": bool,
                "is_free": bool,
                "will_consume_credits": int,
                "credits_remaining_after": int,
                "message": str
            }
        """
        user = await user_repo.find_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)

        bot = await bots_repo.find_bot_by_id(bot_id)
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")

        # Owner check
        if str(bot.get("user_id")) != str(user_id):
            raise ValueError("Bot does not belong to this user")

        current_swap_count = bot.get("swap_count", 0)
        is_free = current_swap_count < cls.FREE_SWAPS_LIMIT

        if is_free:
            return {
                "can_swap": True,
                "is_free": True,
                "will_consume_credits": 0,
                "credits_remaining_after": user.get("activation_credits", 1)
                - user.get("activation_credits_used", 0),
                "message": f"Free swap ({current_swap_count + 1}/{cls.FREE_SWAPS_LIMIT})",
            }
        else:
            # Custa 1 cr?dito
            credits_available = user.get("activation_credits", 1) - user.get(
                "activation_credits_used", 0
            )
            can_swap = credits_available >= 1

            return {
                "can_swap": can_swap,
                "is_free": False,
                "will_consume_credits": 1 if can_swap else 0,
                "credits_remaining_after": max(0, credits_available - 1),
                "message": (
                    "Swap requires 1 activation credit (beyond free limit)"
                    if can_swap
                    else "Insufficient credits for swap"
                ),
            }

    @classmethod
    async def record_swap(
        cls,
        user_id: str | ObjectId,
        bot_id: str | ObjectId,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
        change_type: str = "config_update",
    ) -> Dict[str, Any]:
        """
        Registra um swap (reconfigura??o) no hist?rico do bot.

        Se for um swap pago, consome 1 cr?dito do usu?rio.

        Returns:
            {
                "recorded": bool,
                "swap_number": int,
                "was_free": bool,
                "credits_consumed": int,
                "timestamp": datetime
            }
        """
        # Validar swap
        swap_validation = await cls.validate_swap(user_id, bot_id)
        if not swap_validation["can_swap"]:
            raise ValueError(swap_validation["message"])

        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)

        bot = await bots_repo.find_bot_by_id(bot_id)
        is_free = swap_validation["is_free"]
        credits_consumed = 0 if is_free else 1

        now = datetime.utcnow()

        # Novo registro de swap
        swap_record = {
            "timestamp": now,
            "old_config": old_config,
            "new_config": new_config,
            "credit_charged": not is_free,
            "change_type": change_type,
        }

        # Atualizar bot
        new_swap_count = bot.get("swap_count", 0) + 1
        swap_history = bot.get("swap_history", [])
        swap_history.append(swap_record)

        await bots_repo.update_bot(
            bot_id,
            {
                "swap_count": new_swap_count,
                "swap_history": swap_history,
                "last_updated": now,
            },
        )

        # Consumir cr?dito se necess?rio
        if credits_consumed > 0:
            user = await user_repo.find_by_id(user_id)
            await user_repo.update(
                user_id,
                {
                    "activation_credits_used": (
                        user.get("activation_credits_used", 0) + credits_consumed
                    )
                },
            )

        logger.info(
            f"? Swap recorded for bot {bot_id} "
            f"(#{new_swap_count}, free={is_free})"
        )

        return {
            "recorded": True,
            "swap_number": new_swap_count,
            "was_free": is_free,
            "credits_consumed": credits_consumed,
            "timestamp": now,
        }

    @classmethod
    async def upgrade_plan(
        cls, user_id: str | ObjectId, new_plan: str
    ) -> Dict[str, Any]:
        """
        Faz upgrade do plano de um usu?rio, adicionando novos cr?ditos.

        Mant?m cr?ditos j? utilizados.

        Returns:
            {
                "upgraded": bool,
                "new_plan": str,
                "new_total_credits": int,
                "additional_credits": int,
                "timestamp": datetime
            }
        """
        if new_plan not in cls.PLAN_CREDITS:
            raise ValueError(f"Invalid plan: {new_plan}")

        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        user = await user_repo.find_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        old_credits = user.get("activation_credits", 1)
        new_total_credits = cls.PLAN_CREDITS[new_plan]
        additional_credits = new_total_credits - old_credits

        await user_repo.update(
            user_id,
            {
                "plan": new_plan,
                "activation_credits": new_total_credits,
            },
        )

        logger.info(
            f"? User {user_id} upgraded to {new_plan}. "
            f"New credits: {new_total_credits}"
        )

        return {
            "upgraded": True,
            "new_plan": new_plan,
            "new_total_credits": new_total_credits,
            "additional_credits": additional_credits,
            "timestamp": datetime.utcnow(),
        }
