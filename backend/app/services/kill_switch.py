"""
Kill Switch Service

Implementa um "circuit breaker" de seguran?a para desativar todos os rob?s
de um usu?rio instantaneamente em caso de suspeita de hack ou erro cr?tico.

Uso: Admin pode disparar via endpoint POST /admin/users/{user_id}/kill-switch
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Dict, Any
from bson import ObjectId

from app.core.database import get_db
from app.bots import repository as bots_repo

logger = logging.getLogger(__name__)


class KillSwitch:
    """Controle de emerg?ncia para parar todos os bots de um usu?rio."""

    @classmethod
    async def activate_for_user(
        cls,
        user_id: str | ObjectId,
        reason: str = "Security incident",
        triggered_by: str = "admin",
    ) -> Dict[str, Any]:
        """
        Ativa o Kill Switch para todos os bots de um usu?rio.

        Steps:
        1. Encontrar todos os bots do usu?rio
        2. Parar todos que est?o em execu??o
        3. Desativar is_active_slot de todos
        4. Registrar evento no hist?rico de auditoria

        Args:
            user_id: ID do usu?rio
            reason: Motivo da ativa??o (security, api_key_leak, etc)
            triggered_by: Quem dispparou (admin, automated, user)

        Returns:
            {
                "activated": bool,
                "bots_stopped": int,
                "bots_deactivated": int,
                "timestamp": datetime,
                "audit_id": str
            }
        """
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        db = get_db()
        bots_col = db["bots"]

        # Encontrar todos os bots do usu?rio
        all_bots = await bots_col.find({"user_id": user_id}).to_list(None)

        if not all_bots:
            logger.info(f"?? Kill Switch: No bots found for user {user_id}")
            return {
                "activated": True,
                "bots_stopped": 0,
                "bots_deactivated": 0,
                "timestamp": datetime.utcnow(),
                "audit_id": None,
            }

        # Parar todos os bots em execu??o
        now = datetime.utcnow()
        stopped_count = 0
        deactivated_count = 0

        for bot in all_bots:
            bot_id = bot["_id"]

            # Se estava em execu??o, parar
            if bot.get("is_running", False):
                await bots_col.update_one(
                    {"_id": bot_id},
                    {
                        "$set": {
                            "is_running": False,
                            "is_active_slot": False,
                            "status": "stopped",
                            "last_updated": now,
                        }
                    },
                )
                stopped_count += 1
            elif bot.get("is_active_slot", False):
                # Se estava em slot ativo, desativar
                await bots_col.update_one(
                    {"_id": bot_id},
                    {
                        "$set": {
                            "is_active_slot": False,
                            "last_updated": now,
                        }
                    },
                )
                deactivated_count += 1

        # Registrar evento na auditoria
        audit_id = await cls._log_kill_switch_event(
            user_id=user_id,
            bots_affected=len(all_bots),
            reason=reason,
            triggered_by=triggered_by,
            timestamp=now,
        )

        logger.critical(
            f"? KILL SWITCH ACTIVATED for user {user_id}. "
            f"Reason: {reason}. Bots stopped: {stopped_count}, deactivated: {deactivated_count}"
        )

        return {
            "activated": True,
            "bots_stopped": stopped_count,
            "bots_deactivated": deactivated_count,
            "timestamp": now,
            "audit_id": str(audit_id),
        }

    @classmethod
    async def deactivate_for_user(
        cls,
        user_id: str | ObjectId,
        reason: str = "User acknowledges issue",
    ) -> Dict[str, Any]:
        """
        Desativa o Kill Switch e permite que o usu?rio volte a usar seus bots.

        Nota: N?o reinicia os bots automaticamente, apenas permite novo start.

        Args:
            user_id: ID do usu?rio
            reason: Motivo da desativa??o

        Returns:
            {
                "deactivated": bool,
                "timestamp": datetime
            }
        """
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        db = get_db()
        users_col = db["users"]

        now = datetime.utcnow()

        await users_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "kill_switch_active": False,
                    "last_kill_switch_deactivated": now,
                }
            },
        )

        logger.info(f"? Kill Switch deactivated for user {user_id}. Reason: {reason}")

        return {
            "deactivated": True,
            "timestamp": now,
        }

    @classmethod
    async def is_active(cls, user_id: str | ObjectId) -> bool:
        """Verifica se Kill Switch est? ativo para um usu?rio."""
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        db = get_db()
        users_col = db["users"]

        user = await users_col.find_one({"_id": user_id})
        return user and user.get("kill_switch_active", False)

    @classmethod
    async def _log_kill_switch_event(
        cls,
        user_id: ObjectId,
        bots_affected: int,
        reason: str,
        triggered_by: str,
        timestamp: datetime,
    ) -> ObjectId:
        """Registra evento de Kill Switch para auditoria."""
        db = get_db()
        audit_col = db["audit_logs"]

        audit_event = {
            "event_type": "kill_switch_activated",
            "user_id": user_id,
            "bots_affected": bots_affected,
            "reason": reason,
            "triggered_by": triggered_by,
            "timestamp": timestamp,
            "severity": "critical",
        }

        result = await audit_col.insert_one(audit_event)
        return result.inserted_id

    @classmethod
    async def get_history(
        cls, user_id: str | ObjectId, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retorna hist?rico de ativa??es de Kill Switch para um usu?rio."""
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)

        db = get_db()
        audit_col = db["audit_logs"]

        events = (
            await audit_col.find(
                {
                    "event_type": "kill_switch_activated",
                    "user_id": user_id,
                }
            )
            .sort("timestamp", -1)
            .limit(limit)
            .to_list(None)
        )

        return events
