"""
KillSwitchService — DOC-07 §7.3

Serviço centralizado para gerenciar kill switches via Redis.

Hierarquia:
  1. Global kill switch  → bloqueia TODOS os bots da plataforma
  2. User kill switch    → bloqueia todos os bots de um usuário específico
  3. Bot kill switch     → bloqueia um bot específico (gerenciado pelo RiskManager)

Redis Keys:
  kill_switch:global           → "1" quando ativo
  kill_switch:user:{user_id}   → "1" quando ativo
  kill_switch:bot:{bot_id}     → "1" quando ativo (TTL 7 dias)

Compatibilidade:
  - Usa as mesmas chaves que risk_adapter.py (kill_switch:global / kill_switch:user:{user_id})
  - RiskManager institucional usa chaves separadas (risk:global:kill_switch)

Uso:
    from app.risk.kill_switch import KillSwitchService

    svc = KillSwitchService(redis_client)

    # Verificar
    reason = await svc.check_should_stop(user_id="u1", bot_id="b1")
    if reason:
        await worker.stop(reason)

    # Acionar
    await svc.trigger_user_kill_switch(user_id="u1")
    await svc.trigger_global_kill_switch()

    # Limpar
    await svc.clear_user_kill_switch(user_id="u1")
    await svc.clear_global_kill_switch()
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redis keys
GLOBAL_KILL_KEY  = "kill_switch:global"
USER_KILL_PREFIX = "kill_switch:user:"
BOT_KILL_PREFIX  = "kill_switch:bot:"

# TTLs (seconds)
_GLOBAL_TTL  = 0       # sem expiração automática — requer limpeza manual
_USER_TTL    = 86_400  # 24h (renovado em cada trigger)
_BOT_TTL     = 86_400 * 7  # 7 dias


class KillSwitchService:
    """
    Serviço de kill switch plataforma → usuário → bot.

    Stateless além do cliente Redis. Pode ser instanciado em qualquer lugar.
    Thread-safe (usa apenas operações atômicas do Redis).
    """

    def __init__(self, redis_client: Optional[Any]) -> None:
        self._redis = redis_client

    # ── Verificação ───────────────────────────────────────────────────────

    async def check_should_stop(
        self,
        user_id: str,
        bot_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Verifica ALL kill switches aplicáveis.

        Retorna string descrevendo o motivo de parada, ou None se tudo OK.
        Ordem de verificação: global → usuário → bot.
        """
        if self._redis is None:
            return None

        try:
            # Monta lista de chaves a verificar
            keys = [GLOBAL_KILL_KEY, f"{USER_KILL_PREFIX}{user_id}"]
            if bot_id:
                keys.append(f"{BOT_KILL_PREFIX}{bot_id}")

            values = await self._redis.mget(*keys)

            # Global kill
            if self._is_set(values[0]):
                logger.warning(
                    "KillSwitch: GLOBAL ativo — parando user=%s bot=%s",
                    user_id, bot_id,
                )
                return "kill_switch_global"

            # User kill
            if self._is_set(values[1]):
                logger.warning(
                    "KillSwitch: USUARIO ativo — parando user=%s bot=%s",
                    user_id, bot_id,
                )
                return f"kill_switch_usuario_{user_id}"

            # Bot kill
            if bot_id and len(values) > 2 and self._is_set(values[2]):
                logger.warning(
                    "KillSwitch: BOT ativo — parando bot=%s",
                    bot_id,
                )
                return f"kill_switch_bot_{bot_id}"

        except Exception as exc:
            logger.debug("KillSwitchService.check_should_stop: redis error: %s", exc)

        return None

    async def is_global_active(self) -> bool:
        """Retorna True se o kill switch global está ativo."""
        if self._redis is None:
            return False
        try:
            val = await self._redis.get(GLOBAL_KILL_KEY)
            return self._is_set(val)
        except Exception:
            return False

    async def is_user_active(self, user_id: str) -> bool:
        """Retorna True se o kill switch deste usuário está ativo."""
        if self._redis is None:
            return False
        try:
            val = await self._redis.get(f"{USER_KILL_PREFIX}{user_id}")
            return self._is_set(val)
        except Exception:
            return False

    # ── Ativação ──────────────────────────────────────────────────────────

    async def trigger_global_kill_switch(self) -> bool:
        """
        Ativa o kill switch global.
        Afeta TODOS os bots da plataforma, independente do usuário.
        Retorna True se ativado com sucesso.
        """
        if self._redis is None:
            logger.error("KillSwitchService: Redis não disponível — não foi possível ativar kill global")
            return False
        try:
            await self._redis.set(GLOBAL_KILL_KEY, "1")
            logger.critical("KillSwitchService: KILL SWITCH GLOBAL ATIVADO")
            return True
        except Exception as exc:
            logger.error("KillSwitchService.trigger_global_kill_switch: %s", exc)
            return False

    async def trigger_user_kill_switch(self, user_id: str) -> bool:
        """
        Ativa o kill switch para um usuário específico.
        Afeta todos os bots deste usuário.
        Retorna True se ativado com sucesso.
        """
        if self._redis is None:
            logger.error("KillSwitchService: Redis não disponível — não foi possível ativar kill do usuário %s", user_id)
            return False
        try:
            key = f"{USER_KILL_PREFIX}{user_id}"
            await self._redis.setex(key, _USER_TTL, "1")
            logger.warning("KillSwitchService: kill switch ativado para user=%s", user_id)
            return True
        except Exception as exc:
            logger.error("KillSwitchService.trigger_user_kill_switch user=%s: %s", user_id, exc)
            return False

    async def trigger_bot_kill_switch(self, bot_id: str) -> bool:
        """
        Ativa o kill switch para um bot específico.
        Retorna True se ativado com sucesso.
        """
        if self._redis is None:
            return False
        try:
            key = f"{BOT_KILL_PREFIX}{bot_id}"
            await self._redis.setex(key, _BOT_TTL, "1")
            logger.warning("KillSwitchService: kill switch ativado para bot=%s", bot_id)
            return True
        except Exception as exc:
            logger.error("KillSwitchService.trigger_bot_kill_switch bot=%s: %s", bot_id, exc)
            return False

    # ── Desativação ───────────────────────────────────────────────────────

    async def clear_global_kill_switch(self) -> bool:
        """Desativa o kill switch global. Retorna True se removido com sucesso."""
        if self._redis is None:
            return False
        try:
            await self._redis.delete(GLOBAL_KILL_KEY)
            logger.warning("KillSwitchService: kill switch global desativado")
            return True
        except Exception as exc:
            logger.error("KillSwitchService.clear_global_kill_switch: %s", exc)
            return False

    async def clear_user_kill_switch(self, user_id: str) -> bool:
        """Desativa o kill switch de um usuário. Retorna True se removido."""
        if self._redis is None:
            return False
        try:
            await self._redis.delete(f"{USER_KILL_PREFIX}{user_id}")
            logger.warning("KillSwitchService: kill switch desativado para user=%s", user_id)
            return True
        except Exception as exc:
            logger.error("KillSwitchService.clear_user_kill_switch user=%s: %s", user_id, exc)
            return False

    async def clear_bot_kill_switch(self, bot_id: str) -> bool:
        """Desativa o kill switch de um bot. Retorna True se removido."""
        if self._redis is None:
            return False
        try:
            await self._redis.delete(f"{BOT_KILL_PREFIX}{bot_id}")
            logger.warning("KillSwitchService: kill switch desativado para bot=%s", bot_id)
            return True
        except Exception as exc:
            logger.error("KillSwitchService.clear_bot_kill_switch bot=%s: %s", bot_id, exc)
            return False

    # ── Status ────────────────────────────────────────────────────────────

    async def get_status(self, user_id: Optional[str] = None) -> dict:
        """
        Retorna o status atual de todos os kill switches relevantes.

        Útil para endpoints de administração.
        """
        status: dict = {
            "global_active": False,
            "user_active": False,
            "redis_available": self._redis is not None,
        }

        if self._redis is None:
            return status

        try:
            keys = [GLOBAL_KILL_KEY]
            if user_id:
                keys.append(f"{USER_KILL_PREFIX}{user_id}")

            values = await self._redis.mget(*keys)
            status["global_active"] = self._is_set(values[0])
            if user_id and len(values) > 1:
                status["user_active"] = self._is_set(values[1])
        except Exception as exc:
            logger.debug("KillSwitchService.get_status: %s", exc)

        return status

    # ── Singleton / factory ───────────────────────────────────────────────

    @staticmethod
    async def from_app_redis() -> "KillSwitchService":
        """Cria instância usando o cliente Redis da aplicação."""
        try:
            from app.shared.redis_client import get_redis
            redis = await get_redis()
            return KillSwitchService(redis)
        except Exception as exc:
            logger.warning("KillSwitchService.from_app_redis: %s", exc)
            return KillSwitchService(None)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _is_set(val: Any) -> bool:
        return val in ("1", b"1", 1)
