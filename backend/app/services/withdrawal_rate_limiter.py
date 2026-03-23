"""
Rate Limiter para Saques de Afiliados

Previne abuso:
- Máximo 1 saque por hora por usuário
- Máximo 5 saques por dia por usuário
- Máximo 50 saques por dia no total
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Limites
MAX_WITHDRAWALS_PER_HOUR = 1
MAX_WITHDRAWALS_PER_DAY = 5
MAX_TOTAL_WITHDRAWALS_PER_DAY = 50


class WithdrawalRateLimiter:
    """Rate limiter para saques de afiliados"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.rate_limit_col = db["withdrawal_rate_limits"]

    async def check_rate_limit(self, user_id: str) -> Tuple[bool, str]:
        """
        Verifica se usuário pode solicitar saque.

        Args:
            user_id: ID do usuário

        Returns:
            (permitido: bool, mensagem: str)
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        logger.info(f"🔍 Verificando rate limit para {user_id}")

        try:
            # Conta saques na última 1 hora
            count_1h = await self.rate_limit_col.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": one_hour_ago}
            })

            if count_1h >= MAX_WITHDRAWALS_PER_HOUR:
                msg = f"⏳ Você já solicitou um saque nos últimos 60 minutos. \nTente novamente depois."
                logger.warning(f"⚠️  {msg} (user={user_id})")
                return False, msg

            # Conta saques hoje
            count_today = await self.rate_limit_col.count_documents({
                "user_id": user_id,
                "created_at": {"$gte": today_start}
            })

            if count_today >= MAX_WITHDRAWALS_PER_DAY:
                msg = f"📅 Você atingiu o limite de {MAX_WITHDRAWALS_PER_DAY} saques hoje. \nTente novamente amanhã."
                logger.warning(f"⚠️  {msg} (user={user_id})")
                return False, msg

            # Conta total de saques no sistema hoje
            total_today = await self.rate_limit_col.count_documents({
                "created_at": {"$gte": today_start}
            })

            if total_today >= MAX_TOTAL_WITHDRAWALS_PER_DAY:
                msg = "🛑 Sistema atingiu limite diário de saques. Tente novamente amanhã."
                logger.warning(f"⚠️  {msg}")
                return False, msg

            logger.info(f"✅ Rate limit OK para {user_id}")
            return True, "OK"

        except Exception as e:
            logger.error(f"❌ Erro ao verificar rate limit: {str(e)}", exc_info=True)
            # Em erro, permite (fail-open)
            return True, "OK"

    async def record_withdrawal_attempt(self, user_id: str, withdrawal_id: str = None):
        """
        Registra uma tentativa de saque para rate limiting.

        Args:
            user_id: ID do usuário
            withdrawal_id: ID do saque (opcional)
        """
        try:
            await self.rate_limit_col.insert_one({
                "user_id": user_id,
                "withdrawal_id": withdrawal_id,
                "created_at": datetime.utcnow()
            })

            logger.info(f"📝 Tentativa de saque registrada para {user_id}")

        except Exception as e:
            logger.error(f"❌ Erro ao registrar tentativa: {str(e)}", exc_info=True)

    async def reset_daily_limit(self):
        """
        Job agendado para resetar limite diário (meia-noite UTC).
        Pode ser chamado via scheduler.
        """
        try:
            yesterday = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=1)

            result = await self.rate_limit_col.delete_many({
                "created_at": {"$lt": yesterday}
            })

            logger.info(f"🧹 Limpeza de rate limits: {result.deleted_count} registros deletados")

        except Exception as e:
            logger.error(f"❌ Erro ao resetar limite: {str(e)}", exc_info=True)
