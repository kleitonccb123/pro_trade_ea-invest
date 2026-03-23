"""
RedisRateLimitManager — Rate limit distribuido entre instancias

Problema sem isso:
  - Cada worker/instancia tem seu proprio KuCoinRateLimitManager em memory
  - Com 2+ workers, cada um acredita ter quota cheia -> 429 massivo
  - Kubernetes / autoscaling = instabilidade garantida

Solucao:
  - Estado de rate limit armazenado no Redis (compartilhado entre instancias)
  - Operacoes atomicas via MULTI/EXEC ou Lua script (sem race condition)
  - Fallback gracioso se Redis estiver indisponivel (usa limite conservador)

Modelo KuCoin:
  - Resource Pool com janela de 30 s
  - Headers de resposta: gw-ratelimit-limit, gw-ratelimit-remaining, gw-ratelimit-reset

Chaves Redis:
  kucoin:rl:remaining   -> INT, TTL = reset_ms/1000 + 5s buffer
  kucoin:rl:limit       -> INT, TTL permanente (atualizado a cada response)
  kucoin:rl:reset_ms    -> INT (timestamp do proximo reset em ms)

Requisito:
  pip install redis[asyncio]
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Constantes de fallback (modo degradado sem Redis)
_FALLBACK_LIMIT     = 30
_FALLBACK_REMAINING = 5    # conservador em modo degradado
_REDIS_PREFIX       = "kucoin:rl"


class RedisRateLimitManager:
    """
    Rate limiter distribuido usando Redis como estado compartilhado.

    Compativel com multi-instancia (Kubernetes, Docker Swarm, workers Uvicorn).

    Uso:
    ```python
    import redis.asyncio as aioredis

    redis_client = aioredis.from_url("redis://localhost:6379")
    rl = RedisRateLimitManager(redis_client)

    # Substituir no KuCoinRawClient:
    await rl.wait_if_needed()      # antes de cada request
    rl.update_from_headers(resp.headers)  # apos cada response
    ```
    """

    def __init__(
        self,
        redis: Any,                   # redis.asyncio.Redis
        key_prefix: str = _REDIS_PREFIX,
        fallback_limit: int = _FALLBACK_LIMIT,
        fallback_remaining: int = _FALLBACK_REMAINING,
    ) -> None:
        self._redis    = redis
        self._prefix   = key_prefix
        self._fallback_limit     = fallback_limit
        self._fallback_remaining = fallback_remaining
        self._redis_ok = True          # flag de saude do Redis

        logger.info(f"RedisRateLimitManager criado (prefix={key_prefix})")

    # ─────────────────────────── Chaves Redis ────────────────────────────────

    @property
    def _key_remaining(self) -> str:
        return f"{self._prefix}:remaining"

    @property
    def _key_limit(self) -> str:
        return f"{self._prefix}:limit"

    @property
    def _key_reset_ms(self) -> str:
        return f"{self._prefix}:reset_ms"

    # ──────────────────────────── Interface publica ───────────────────────────

    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """
        Atualiza estado no Redis a partir dos headers de uma response KuCoin.
        Chamado apos cada requisicao bem-sucedida.
        Operacao fire-and-forget (nao aguarda resultado).
        """
        limit     = headers.get("gw-ratelimit-limit")
        remaining = headers.get("gw-ratelimit-remaining")
        reset_ms  = headers.get("gw-ratelimit-reset")

        if limit is None and remaining is None:
            return  # response sem headers de rate limit (ex: erro de auth)

        asyncio.create_task(
            self._write_to_redis(
                limit=int(limit or self._fallback_limit),
                remaining=int(remaining or self._fallback_remaining),
                reset_ms=int(reset_ms or 30000),
            )
        )

    async def wait_if_needed(self) -> None:
        """
        Bloqueia se remaining <= 0.
        Usa Redis para verificar — se Redis indisponivel, usa fallback conservador.
        """
        try:
            remaining = await self._get_remaining()
            reset_ms  = await self._get_reset_ms()
        except Exception as exc:
            logger.warning(f"Redis indisponivel, usando fallback: {exc}")
            self._redis_ok = False
            # Modo degradado: espera pequena antes de cada request
            await asyncio.sleep(0.5)
            return

        self._redis_ok = True

        if remaining is not None and remaining <= 0:
            wait_s = max(int(reset_ms or 30000) / 1000.0, 0.5)
            logger.warning(
                f"[RedisRL] Quota esgotada (distributed). "
                f"Aguardando {wait_s:.1f}s para reset..."
            )
            await asyncio.sleep(wait_s)

    async def decrement(self) -> None:
        """
        Decrementa atomicamente o contador de remaining no Redis.
        Chamado antes de enviar um request (pessimista).
        """
        try:
            current = await self._redis.get(self._key_remaining)
            if current is None:
                return  # ainda sem dado do servidor
            new_val = max(int(current) - 1, 0)
            ttl = await self._redis.ttl(self._key_remaining)
            await self._redis.setex(self._key_remaining, max(ttl, 1), new_val)
        except Exception as exc:
            logger.debug(f"RedisRL.decrement falhou: {exc}")

    @property
    def is_redis_healthy(self) -> bool:
        """True se o Redis estava acessivel na ultima operacao."""
        return self._redis_ok

    async def current_status(self) -> Dict[str, Any]:
        """Retorna status atual do rate limiter para monitoramento."""
        try:
            remaining = await self._get_remaining()
            limit     = await self._redis.get(self._key_limit)
            reset_ms  = await self._get_reset_ms()
            return {
                "source":    "redis",
                "remaining": remaining,
                "limit":     int(limit) if limit else None,
                "reset_ms":  reset_ms,
                "redis_ok":  True,
            }
        except Exception:
            return {
                "source":    "fallback",
                "remaining": self._fallback_remaining,
                "limit":     self._fallback_limit,
                "reset_ms":  None,
                "redis_ok":  False,
            }

    # ─────────────────────────── Internos ────────────────────────────────────

    async def _write_to_redis(
        self,
        limit: int,
        remaining: int,
        reset_ms: int,
    ) -> None:
        """Grava estado atual no Redis com TTL baseado no reset da KuCoin."""
        try:
            ttl_s = max(int(reset_ms / 1000) + 5, 35)  # +5 s de buffer
            pipe = self._redis.pipeline()
            pipe.setex(self._key_remaining, ttl_s, remaining)
            pipe.setex(self._key_reset_ms,  ttl_s, reset_ms)
            pipe.setex(self._key_limit,     300,   limit)   # TTL longo para limit
            await pipe.execute()
        except Exception as exc:
            logger.warning(f"RedisRL: falha ao gravar estado: {exc}")

    async def _get_remaining(self) -> Optional[int]:
        val = await self._redis.get(self._key_remaining)
        return int(val) if val is not None else None

    async def _get_reset_ms(self) -> Optional[int]:
        val = await self._redis.get(self._key_reset_ms)
        return int(val) if val is not None else None


# ──────────────────── Factory / Singleton ────────────────────────────────────

_redis_rl_instance: Optional[RedisRateLimitManager] = None


def init_redis_rate_limiter(redis_client: Any) -> RedisRateLimitManager:
    """
    Inicializa instancia global do RedisRateLimitManager.

    Chamar no startup da aplicacao apos conectar ao Redis:
    ```python
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.REDIS_URL)
    init_redis_rate_limiter(r)
    ```
    """
    global _redis_rl_instance
    _redis_rl_instance = RedisRateLimitManager(redis_client)
    return _redis_rl_instance


def get_redis_rate_limiter() -> Optional[RedisRateLimitManager]:
    """Retorna instancia global, ou None se nao inicializada."""
    return _redis_rl_instance
