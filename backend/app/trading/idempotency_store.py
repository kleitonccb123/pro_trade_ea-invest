"""
IdempotencyStore — Controle de idempotência baseado em Redis

Problema:
  - Retry sem controle pode criar ordens duplicadas na exchange
  - Crash entre geração do clientOid e persistência = estado desconhecido
  - Restart do processo não sabe quais ordens foram enviadas

Solução:
  - SET NX (set-if-not-exists) no Redis com TTL de 7 dias
  - clientOid determinístico baseado em signal_id + bot_id + attempt
  - Fallback em memória se Redis não estiver disponível

Integração:
    before_send:
        check = await idempotency_store.check_and_set(client_oid, payload)
        if check.is_duplicate:
            return check.existing_result    # reusa resultado anterior

    after_success:
        await idempotency_store.mark_completed(client_oid, order_id, "SENT")

    after_failure:
        await idempotency_store.mark_failed(client_oid, error_msg)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def generate_client_oid(signal_id: str, bot_id: str, attempt: int = 0) -> str:
    """
    Gera clientOid determinístico baseado em signal_id + bot_id + attempt.

    Garante que o mesmo sinal NUNCA gera dois clientOids diferentes,
    mesmo após restart do processo.

    KuCoin aceita max 32 chars alfanumérico.
    """
    raw = f"{signal_id}:{bot_id}:{attempt}"
    token = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return token


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class IdempotencyCheckResult:
    is_duplicate: bool
    existing_result: Optional[Dict[str, Any]] = None


# ─── Redis-backed store ───────────────────────────────────────────────────────

class IdempotencyStore:
    """
    Armazena e verifica idempotência de ordens via Redis (ou memória como fallback).

    Uso:
    ```python
    store = IdempotencyStore(redis_client)

    result = await store.check_and_set("abc123", {"symbol": "BTC-USDT"})
    if result.is_duplicate:
        return result.existing_result

    # ... enviar ordem ...

    await store.mark_completed("abc123", "kucoin-order-id", "SENT")
    ```
    """

    TTL_SECONDS = 86_400 * 7  # 7 dias

    def __init__(self, redis_client: Any = None) -> None:
        """
        Args:
            redis_client: instância de redis.asyncio.Redis.
                          Se None, usa fallback em memória (processo único).
        """
        self._redis = redis_client
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._memory_lock = asyncio.Lock()

        if redis_client is None:
            logger.warning(
                "IdempotencyStore: Redis não disponível — usando fallback em memória. "
                "NÃO adequado para múltiplos workers!"
            )

    # ── Verificação e registro ────────────────────────────────────────────────

    async def check_and_set(
        self,
        client_oid: str,
        payload: Dict[str, Any],
    ) -> IdempotencyCheckResult:
        """
        Verifica se client_oid já foi processado.

        Usa SET NX (atômico): se a chave não existe, registra e retorna
        is_duplicate=False. Se já existe, retorna is_duplicate=True com
        o resultado anterior.
        """
        if self._redis is not None:
            return await self._redis_check_and_set(client_oid, payload)
        return await self._memory_check_and_set(client_oid, payload)

    async def mark_completed(
        self,
        client_oid: str,
        order_id: str,
        status: str,
    ) -> None:
        """Marca clientOid como processado com sucesso."""
        if self._redis is not None:
            await self._redis_update(client_oid, {"status": status, "order_id": order_id,
                                                   "completed_at": _now_iso()})
        else:
            await self._memory_update(client_oid, {"status": status, "order_id": order_id,
                                                    "completed_at": _now_iso()})

    async def mark_failed(self, client_oid: str, error: str) -> None:
        """Marca clientOid como falho."""
        if self._redis is not None:
            await self._redis_update(client_oid, {"status": "FAILED", "error": error,
                                                   "failed_at": _now_iso()})
        else:
            await self._memory_update(client_oid, {"status": "FAILED", "error": error,
                                                   "failed_at": _now_iso()})

    async def get(self, client_oid: str) -> Optional[Dict[str, Any]]:
        """Retorna o estado atual de um clientOid, ou None se não existir."""
        key = self._key(client_oid)
        if self._redis is not None:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        async with self._memory_lock:
            return self._memory.get(key)

    # ── Redis helpers ─────────────────────────────────────────────────────────

    async def _redis_check_and_set(
        self,
        client_oid: str,
        payload: Dict[str, Any],
    ) -> IdempotencyCheckResult:
        key = self._key(client_oid)
        initial = json.dumps({
            "payload":    payload,
            "status":     "PROCESSING",
            "created_at": _now_iso(),
        })

        # SET NX EX — atômico
        result = await self._redis.set(key, initial, ex=self.TTL_SECONDS, nx=True)

        if result is None:
            # Chave já existia — duplicata
            raw = await self._redis.get(key)
            existing = json.loads(raw) if raw else None
            logger.info(f"IdempotencyStore: duplicata detectada para {client_oid}")
            return IdempotencyCheckResult(is_duplicate=True, existing_result=existing)

        return IdempotencyCheckResult(is_duplicate=False)

    async def _redis_update(self, client_oid: str, updates: Dict[str, Any]) -> None:
        key = self._key(client_oid)
        raw = await self._redis.get(key)
        if raw:
            data = json.loads(raw)
            data.update(updates)
            await self._redis.set(key, json.dumps(data), ex=self.TTL_SECONDS)

    # ── Memory fallback helpers ───────────────────────────────────────────────

    async def _memory_check_and_set(
        self,
        client_oid: str,
        payload: Dict[str, Any],
    ) -> IdempotencyCheckResult:
        key = self._key(client_oid)
        async with self._memory_lock:
            if key in self._memory:
                return IdempotencyCheckResult(
                    is_duplicate=True,
                    existing_result=self._memory[key],
                )
            self._memory[key] = {
                "payload":    payload,
                "status":     "PROCESSING",
                "created_at": _now_iso(),
            }
        return IdempotencyCheckResult(is_duplicate=False)

    async def _memory_update(self, client_oid: str, updates: Dict[str, Any]) -> None:
        key = self._key(client_oid)
        async with self._memory_lock:
            if key in self._memory:
                self._memory[key].update(updates)

    # ── Utils ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _key(client_oid: str) -> str:
        return f"idempotency:order:{client_oid}"


# ─── Module-level helpers ─────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Instância global (inicializada no startup)
_idempotency_store: Optional[IdempotencyStore] = None


def init_idempotency_store(redis_client: Any = None) -> IdempotencyStore:
    global _idempotency_store
    _idempotency_store = IdempotencyStore(redis_client)
    return _idempotency_store


def get_idempotency_store() -> IdempotencyStore:
    global _idempotency_store
    if _idempotency_store is None:
        # inicializa com fallback em memória se ainda não foi chamado
        _idempotency_store = IdempotencyStore()
    return _idempotency_store
