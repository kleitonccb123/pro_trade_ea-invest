"""
BalanceReservationSystem — Reserva virtual de saldo para ordens em voo

DOC-04 §4.2

Problema que resolve:
  3 bots verificam saldo simultaneamente → todos veem $1000 disponível
  → todos tentam gastar $400 → $1200 de ordens com $1000 real.

Solução:
  DENTRO do lock de balanço (lock:balance:{userId}), antes de liberar o lock,
  registramos uma reserva virtual em Redis via HSET:
    key:  balance:reserved:{userId}:{currency}
    field: {clientOid}
    value: {amount, botId, createdAt, expiresAt}

  Na próxima tentativa de reserva (mesmo ou outro bot do mesmo usuário),
  o saldo "disponível" = realBalance - totalReserved.

TTL de reserva: 60 segundos
  Se o envio HTTP demorar mais de 60s ou a aplicação cair, a reserva
  expira automaticamente e o saldo é liberado.

Uso:
```python
reservation_sys = BalanceReservationSystem(redis_client, kucoin_client)

# DENTRO do lock:balance:{userId}:
result = await reservation_sys.reserve(
    user_id="u1", bot_id="b1", currency="USDT",
    amount=Decimal("400"), reservation_id=client_oid,
    kucoin_client=kucoin_client,
)
if not result["success"]:
    raise InsufficientFundsError(result["reason"])

try:
    # ... envia ordem ...
finally:
    await reservation_sys.release("u1", "USDT", client_oid)
```
"""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BalanceReservationSystem:
    """
    Gerencia reservas virtuais de saldo por usuário/moeda.
    Todas as operações devem ser executadas dentro do lock:balance:{userId}.

    Storage: Redis (primary) with MongoDB fallback when Redis is a MockRedis
    or unavailable.
    """

    # TTL das reservas (em ms e segundos)
    RESERVATION_TTL_MS = 60_000   # 60 segundos
    RESERVATION_TTL_S  = 60       # equivalente

    KEY_PREFIX = "balance:reserved"
    MONGO_COLLECTION = "balance_reservations"

    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self._redis = redis_client
        # Detect if we're using MockRedis (no real distributed guarantees)
        self._redis_is_mock = (
            redis_client is not None
            and type(redis_client).__name__ == "MockRedis"
        )

    # ── Reserve ───────────────────────────────────────────────────────────────

    async def reserve(
        self,
        user_id: str,
        bot_id: str,
        currency: str,
        amount: Decimal,
        reservation_id: str,        # = clientOid da ordem
        kucoin_client: Optional[Any] = None,  # para buscar saldo real
    ) -> Dict[str, Any]:
        """
        Verifica saldo disponível (real - reservado) e cria reserva se suficiente.

        Returns:
          {"success": True, "available_after": Decimal(...)}
          {"success": False, "reason": "Saldo insuficiente..."}
        """
        # 1. Saldo real na exchange
        real_balance = await self._fetch_real_balance(user_id, currency, kucoin_client)

        # 2. Total reservado por ordens em voo
        current_reserved = await self.get_total_reserved(user_id, currency)

        # 3. Saldo efetivamente disponível
        available = real_balance - current_reserved

        if available < amount:
            reason = (
                f"Saldo insuficiente considerando reservas: "
                f"real={real_balance:.8f}, reservado={current_reserved:.8f}, "
                f"disponível={available:.8f}, necessário={amount:.8f} {currency}"
            )
            logger.warning(
                "BalanceReservation.reserve: %s user=%s", reason, user_id
            )
            return {
                "success": False,
                "reason": reason,
                "available": str(available),
            }

        # 4. Cria reserva no Redis
        if self._redis is not None:
            key = self._redis_key(user_id, currency)
            entry = json.dumps({
                "amount":      str(amount),
                "bot_id":      bot_id,
                "created_at":  int(time.time() * 1000),
                "expires_at":  int(time.time() * 1000) + self.RESERVATION_TTL_MS,
            })
            try:
                await self._redis.hset(key, reservation_id, entry)
                # TTL da hash: expiração automática de toda a chave
                await self._redis.expire(key, self.RESERVATION_TTL_S + 120)
            except Exception as exc:
                logger.warning("BalanceReservation.reserve: redis error: %s", exc)

        # 4b. MongoDB fallback when Redis is mock (no real distributed storage)
        if self._redis_is_mock or self._redis is None:
            await self._mongo_upsert_reservation(
                user_id, currency, reservation_id, str(amount), bot_id,
            )

        available_after = available - amount
        logger.info(
            "BalanceReservation: reservado %s %s para user=%s reservationId=%s "
            "(disponível após: %s)",
            amount, currency, user_id, reservation_id, available_after,
        )
        return {
            "success": True,
            "available_after": str(available_after),
        }

    # ── Release ───────────────────────────────────────────────────────────────

    async def release(
        self,
        user_id: str,
        currency: str,
        reservation_id: str,
    ) -> None:
        """Remove reserva após confirmação ou falha da ordem."""
        if self._redis is not None:
            key = self._redis_key(user_id, currency)
            try:
                await self._redis.hdel(key, reservation_id)
                logger.debug(
                    "BalanceReservation: liberado reservationId=%s user=%s %s",
                    reservation_id, user_id, currency,
                )
            except Exception as exc:
                logger.warning("BalanceReservation.release: redis error: %s", exc)

        # MongoDB fallback cleanup
        if self._redis_is_mock or self._redis is None:
            await self._mongo_delete_reservation(user_id, currency, reservation_id)

    # ── Totais ────────────────────────────────────────────────────────────────

    async def get_total_reserved(self, user_id: str, currency: str) -> Decimal:
        """
        Soma todas as reservas ativas (não expiradas) do usuário para a moeda.
        Limpa automaticamente as expiradas encontradas.
        Falls back to MongoDB when Redis is mock.
        """
        # Use MongoDB as source of truth when Redis is mock
        if self._redis_is_mock or self._redis is None:
            return await self._mongo_get_total_reserved(user_id, currency)

        key = self._redis_key(user_id, currency)
        try:
            all_entries = await self._redis.hgetall(key) or {}
        except Exception as exc:
            logger.warning("BalanceReservation.get_total_reserved: %s", exc)
            return Decimal("0")

        total = Decimal("0")
        now_ms = int(time.time() * 1000)
        expired_ids = []

        for reservation_id, raw in all_entries.items():
            try:
                if isinstance(raw, bytes):
                    raw = raw.decode()
                data = json.loads(raw)
                if now_ms > data.get("expires_at", 0):
                    expired_ids.append(reservation_id)
                    continue
                total += Decimal(data["amount"])
            except (json.JSONDecodeError, KeyError, Exception) as exc:
                logger.warning("BalanceReservation: entrada inválida: %s", exc)

        # Limpa expiradas em segundo plano
        if expired_ids:
            try:
                await self._redis.hdel(key, *expired_ids)
                logger.debug(
                    "BalanceReservation: %d reservas expiradas removidas para %s/%s",
                    len(expired_ids), user_id, currency,
                )
            except Exception:
                pass

        return total

    # ── Manutenção ────────────────────────────────────────────────────────────

    async def clean_expired(self, user_id: str, currency: str) -> int:
        """
        Remove todas as reservas expiradas de um usuário/moeda.
        Retorna o número de entradas removidas.
        """
        if self._redis is None:
            return 0

        key = self._redis_key(user_id, currency)
        try:
            all_entries = await self._redis.hgetall(key) or {}
        except Exception:
            return 0

        now_ms = int(time.time() * 1000)
        expired = [
            rid for rid, raw in all_entries.items()
            if self._entry_expired(raw, now_ms)
        ]

        if expired:
            await self._redis.hdel(key, *expired)
            logger.info(
                "BalanceReservation.clean_expired: %d limpos para %s/%s",
                len(expired), user_id, currency,
            )
        return len(expired)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _redis_key(self, user_id: str, currency: str) -> str:
        return f"{self.KEY_PREFIX}:{user_id}:{currency}"

    @staticmethod
    def _entry_expired(raw: Any, now_ms: int) -> bool:
        try:
            if isinstance(raw, bytes):
                raw = raw.decode()
            data = json.loads(raw)
            return now_ms > data.get("expires_at", 0)
        except Exception:
            return True

    async def _fetch_real_balance(
        self,
        user_id: str,
        currency: str,
        kucoin_client: Optional[Any],
    ) -> Decimal:
        """
        Busca saldo real da exchange.
        Se kucoin_client não disponível, assume saldo zero (conservador).
        """
        if kucoin_client is None:
            logger.warning(
                "BalanceReservation: sem kucoin_client para user=%s — "
                "saldo assumido como 0 (conservador)", user_id,
            )
            return Decimal("0")
        try:
            accounts = await kucoin_client.get_accounts(account_type="trade")
            for acc in (accounts or []):
                if acc.get("currency") == currency:
                    return Decimal(str(acc.get("available", "0")))
            return Decimal("0")
        except Exception as exc:
            logger.error(
                "BalanceReservation: falha ao buscar saldo real: %s", exc
            )
            return Decimal("0")


    # ── MongoDB fallback helpers ──────────────────────────────────────────────

    def _mongo_col(self):
        """Get the MongoDB collection for balance reservations."""
        from app.core.database import get_db
        return get_db()[self.MONGO_COLLECTION]

    async def _mongo_upsert_reservation(
        self, user_id: str, currency: str, reservation_id: str,
        amount: str, bot_id: str,
    ) -> None:
        """Write a reservation to MongoDB (fallback when Redis is mock)."""
        try:
            now_ms = int(time.time() * 1000)
            await self._mongo_col().update_one(
                {"reservation_id": reservation_id},
                {"$set": {
                    "user_id": user_id,
                    "currency": currency,
                    "reservation_id": reservation_id,
                    "amount": amount,
                    "bot_id": bot_id,
                    "created_at": now_ms,
                    "expires_at": now_ms + self.RESERVATION_TTL_MS,
                }},
                upsert=True,
            )
        except Exception as exc:
            logger.warning("BalanceReservation._mongo_upsert: %s", exc)

    async def _mongo_delete_reservation(
        self, user_id: str, currency: str, reservation_id: str,
    ) -> None:
        """Remove a reservation from MongoDB."""
        try:
            await self._mongo_col().delete_one({"reservation_id": reservation_id})
        except Exception as exc:
            logger.warning("BalanceReservation._mongo_delete: %s", exc)

    async def _mongo_get_total_reserved(
        self, user_id: str, currency: str,
    ) -> Decimal:
        """Sum active (non-expired) reservations from MongoDB."""
        try:
            col = self._mongo_col()
            now_ms = int(time.time() * 1000)
            # Clean expired
            await col.delete_many({"expires_at": {"$lte": now_ms}})
            # Sum active
            cursor = col.find({
                "user_id": user_id,
                "currency": currency,
                "expires_at": {"$gt": now_ms},
            })
            total = Decimal("0")
            async for doc in cursor:
                total += Decimal(doc.get("amount", "0"))
            return total
        except Exception as exc:
            logger.warning("BalanceReservation._mongo_total: %s", exc)
            return Decimal("0")


# ─── Instância global ─────────────────────────────────────────────────────────

_reservation_sys: Optional[BalanceReservationSystem] = None


def init_balance_reservation(
    redis_client: Optional[Any] = None,
) -> BalanceReservationSystem:
    global _reservation_sys
    _reservation_sys = BalanceReservationSystem(redis_client)
    logger.info("BalanceReservationSystem inicializado")
    return _reservation_sys


def get_balance_reservation() -> Optional[BalanceReservationSystem]:
    return _reservation_sys
