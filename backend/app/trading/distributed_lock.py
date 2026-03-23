"""
DistributedLock — Redis distributed lock com Lua script para release atômico

DOC-04 §4.1

Garante que apenas o detentor do lock possa liberá-lo.
O script Lua executa atomicamente: só deleta a chave se o valor (token)
corresponder ao token que foi armazenado, evitando que outro processo
libere um lock que não é seu.

Padrões implementados:
  acquire()          — SET NX PX {ttl_ms}
  acquire_with_wait() — polling com backoff progressivo até max_wait_ms
  release()          — Lua script: GET+DEL atômico
  with_lock()        — context manager: acquire → fn() → release (finally)

Fallback (sem Redis):
  Usa asyncio.Lock em memória — funcional em processos únicos.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# Script Lua para release atômico
# KEYS[1] = chave do lock  ARGV[1] = token do detentor
_LUA_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
"""


class DistributedLock:
    """
    Redis distributed lock com token único por acquisição.

    Uso com context manager (recomendado):
    ```python
    lock = DistributedLock(redis_client)
    async with lock.acquire_ctx("bot:bot1", ttl_ms=30_000):
        # seção crítica
        ...

    # Ou com helper de alto nível:
    result = await lock.with_lock("bot:bot1", 30_000, my_coroutine)
    ```
    """

    # Prefixo das chaves no Redis
    KEY_PREFIX = "lock:"

    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self._redis = redis_client
        # Fallback: locks por chave em memória
        self._mem_locks: dict[str, asyncio.Lock] = {}
        self._mem_mx = asyncio.Lock()

    # ── Acquire ───────────────────────────────────────────────────────────────

    async def acquire(self, key: str, ttl_ms: int) -> Optional[str]:
        """
        Tenta adquirir o lock UMA VEZ.

        Returns:
            token (str) se adquirido, None se o lock já está ocupado.
        """
        token = secrets.token_hex(16)
        full_key = f"{self.KEY_PREFIX}{key}"

        if self._redis is not None:
            try:
                result = await self._redis.set(full_key, token, px=ttl_ms, nx=True)
                if result:
                    logger.debug("DistributedLock: acquired key=%s", full_key)
                    return token
                return None
            except Exception as exc:
                logger.warning("DistributedLock.acquire redis error: %s — usando fallback", exc)

        # Fallback assíncrono local
        return await self._mem_acquire(key, token)

    async def acquire_with_wait(
        self,
        key: str,
        ttl_ms: int,
        max_wait_ms: int = 5_000,
        poll_ms: int = 100,
    ) -> Optional[str]:
        """
        Tenta adquirir o lock com polling e backoff progressivo.

        Backoff: poll_ms, poll_ms*2, poll_ms*4 ... capped at 1000ms.
        Retorna None se expirou max_wait_ms sem conseguir o lock.
        """
        import time
        deadline = time.monotonic() + max_wait_ms / 1000.0
        interval = poll_ms / 1000.0

        while time.monotonic() < deadline:
            token = await self.acquire(key, ttl_ms)
            if token:
                return token
            sleep_s = min(interval * 2, 1.0)
            await asyncio.sleep(sleep_s)

        logger.warning(
            "DistributedLock: timeout esperando lock=%s após %dms", key, max_wait_ms
        )
        return None

    # ── Release ───────────────────────────────────────────────────────────────

    async def release(self, key: str, token: str) -> bool:
        """
        Libera o lock somente se o token corresponder (Lua atômico).

        Returns:
            True se liberado, False se token inválido ou lock já expirou.
        """
        full_key = f"{self.KEY_PREFIX}{key}"

        if self._redis is not None:
            try:
                released = await self._redis.eval(_LUA_RELEASE_SCRIPT, 1, full_key, token)
                if released == 1:
                    logger.debug("DistributedLock: released key=%s", full_key)
                    return True
                logger.warning(
                    "DistributedLock: release falhou key=%s "
                    "(token errado ou lock expirou)", full_key,
                )
                return False
            except Exception as exc:
                logger.warning("DistributedLock.release redis error: %s", exc)

        # Fallback
        return await self._mem_release(key, token)

    # ── Context manager ───────────────────────────────────────────────────────

    @asynccontextmanager
    async def acquire_ctx(
        self,
        key: str,
        ttl_ms: int,
        max_wait_ms: int = 5_000,
    ) -> AsyncGenerator[str, None]:
        """
        Async context manager que adquire e libera o lock automaticamente.

        ```python
        async with lock.acquire_ctx("bot:bot1", 30_000) as token:
            # seção crítica
            ...
        ```

        Raises:
            RuntimeError se não conseguir o lock em max_wait_ms.
        """
        token = await self.acquire_with_wait(key, ttl_ms, max_wait_ms)
        if token is None:
            raise RuntimeError(
                f"DistributedLock: não foi possível adquirir lock '{key}' "
                f"em {max_wait_ms}ms"
            )
        try:
            yield token
        finally:
            await self.release(key, token)

    # ── with_lock helper ──────────────────────────────────────────────────────

    async def with_lock(
        self,
        key: str,
        ttl_ms: int,
        fn,
        max_wait_ms: int = 5_000,
    ):
        """
        Adquire o lock, executa `fn` (coroutine ou callable assíncrono),
        libera o lock. Garante release mesmo em caso de exceção.

        Args:
            key:          nome do lock (sem prefixo)
            ttl_ms:       TTL em milissegundos (proteção contra crash)
            fn:           coroutine ou callable async zero-args
            max_wait_ms:  tempo máximo de espera pelo lock

        Returns:
            resultado de fn()

        Raises:
            RuntimeError se não adquirir o lock em max_wait_ms
        """
        async with self.acquire_ctx(key, ttl_ms, max_wait_ms):
            if asyncio.iscoroutinefunction(fn):
                return await fn()
            return await fn

    # ── Fallback em memória ───────────────────────────────────────────────────

    async def _mem_acquire(self, key: str, token: str) -> Optional[str]:
        async with self._mem_mx:
            if key not in self._mem_locks:
                self._mem_locks[key] = asyncio.Lock()
        lock = self._mem_locks[key]
        if lock.locked():
            return None
        try:
            await asyncio.wait_for(lock.acquire(), timeout=0.01)
            # Armazena o token no lock como atributo
            lock._doc04_token = token  # type: ignore[attr-defined]
            return token
        except (asyncio.TimeoutError, RuntimeError):
            return None

    async def _mem_release(self, key: str, token: str) -> bool:
        lock = self._mem_locks.get(key)
        if lock and lock.locked():
            stored = getattr(lock, "_doc04_token", None)
            if stored == token:
                lock.release()
                return True
        return False


# ─── Instância global ─────────────────────────────────────────────────────────

_dist_lock: Optional[DistributedLock] = None


def init_distributed_lock(redis_client: Optional[Any] = None) -> DistributedLock:
    global _dist_lock
    _dist_lock = DistributedLock(redis_client)
    logger.info("DistributedLock inicializado (redis=%s)", "sim" if redis_client else "fallback")
    return _dist_lock


def get_distributed_lock() -> Optional[DistributedLock]:
    return _dist_lock
