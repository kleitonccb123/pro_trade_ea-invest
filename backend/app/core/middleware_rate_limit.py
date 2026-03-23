"""
DOC-10 §7.3 — Rate Limiting por userId (e IP como fallback)

Middleware Starlette que limita requisições por usuário autenticado
(extraído do JWT) ou pelo IP de origem quando não autenticado.

Implementação: Redis INCR + EXPIRE (sliding-window aproximada).
  - Sem Redis: fallback para dicionário in-memory Thread-Safe.
  - Limite padrão: 100 req / 60s por userId, 30 req / 60s por IP.
  - Rotas excluídas: /health, /metrics, /docs, /openapi.json.

Headers de resposta:
  X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
  Retry-After (apenas em 429)
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger(__name__)

# ── Configuração ───────────────────────────────────────────────────────────────
_USER_LIMIT = 100      # req por janela (usuário autenticado)
_IP_LIMIT = 30         # req por janela (IP anônimo)
_WINDOW_SEC = 60       # segundos por janela

# Rotas que não sofrem rate limiting
_EXCLUDED_PREFIXES = (
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)

# ── Fallback in-memory (quando Redis não disponível) ───────────────────────────
_mem_counters: dict = defaultdict(lambda: [0, 0.0])  # {key: [count, window_start]}
_mem_lock = Lock()


def _mem_check(key: str, limit: int, window: int) -> tuple[bool, int, int]:
    """Retorna (allowed, remaining, reset_ts)."""
    now = time.time()
    with _mem_lock:
        count, start = _mem_counters[key]
        if now - start >= window:
            _mem_counters[key] = [1, now]
            return True, limit - 1, int(now + window)
        if count < limit:
            _mem_counters[key][0] += 1
            remaining = max(0, limit - count - 1)
            reset_ts = int(start + window)
            return True, remaining, reset_ts
        reset_ts = int(start + window)
        return False, 0, reset_ts


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_user_id(request: Request, secret: str, algorithm: str) -> Optional[str]:
    """Tenta extrair user_id do JWT no header Authorization sem levantar exceção."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return str(payload.get("sub") or payload.get("user_id") or "")
    except JWTError:
        return None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Middleware ─────────────────────────────────────────────────────────────────

class UserRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting baseado em userId (JWT) ou IP (fallback).

    Args:
        app:           ASGI app
        jwt_secret:    Secret key para decodar o JWT e obter user_id
        jwt_algorithm: Algoritmo JWT (default HS256)
        redis_client:  Instância Redis (opcional; usa in-memory se None)
        user_limit:    Máx requisições por usuário autenticado por janela
        ip_limit:      Máx requisições por IP anônimo por janela
        window_sec:    Tamanho da janela em segundos
    """

    def __init__(
        self,
        app,
        jwt_secret: str = "",
        jwt_algorithm: str = "HS256",
        redis_client=None,
        user_limit: int = _USER_LIMIT,
        ip_limit: int = _IP_LIMIT,
        window_sec: int = _WINDOW_SEC,
    ):
        super().__init__(app)
        self._secret = jwt_secret
        self._algorithm = jwt_algorithm
        self._redis = redis_client
        self._user_limit = user_limit
        self._ip_limit = ip_limit
        self._window = window_sec

    # ── Implementação principal ────────────────────────────────────────────────

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Excluir rotas de monitoramento e documentação
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _EXCLUDED_PREFIXES):
            return await call_next(request)

        # Identificador e limite
        user_id = _extract_user_id(request, self._secret, self._algorithm)
        if user_id:
            identifier = f"rl:user:{user_id}"
            limit = self._user_limit
        else:
            ip = _client_ip(request)
            identifier = f"rl:ip:{ip}"
            limit = self._ip_limit

        # Verificar limite
        allowed, remaining, reset_ts = await self._check(identifier, limit)

        if not allowed:
            retry_after = max(1, reset_ts - int(time.time()))
            logger.warning(
                "Rate limit excedido identifier=%s path=%s", identifier, path
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too Many Requests",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_ts),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_ts)
        return response

    # ── Backend Redis ou in-memory ─────────────────────────────────────────────

    async def _check(self, key: str, limit: int) -> tuple[bool, int, int]:
        """
        Retorna (allowed, remaining, reset_unix_ts).
        Usa Redis se disponível, senão in-memory.
        """
        if self._redis is not None:
            return await self._redis_check(key, limit)
        return _mem_check(key, limit, self._window)

    async def _redis_check(self, key: str, limit: int) -> tuple[bool, int, int]:
        """
        Incrementa contador com Redis INCR + EXPIRE.
        Atomicamente seguro: usa pipeline.
        """
        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            results = await pipe.execute()
            count: int = results[0]
            ttl: int = results[1]

            if ttl < 0:
                # Chave nova ou sem TTL — define a janela
                await self._redis.expire(key, self._window)
                ttl = self._window

            reset_ts = int(time.time()) + ttl
            remaining = max(0, limit - count)
            allowed = count <= limit
            return allowed, remaining, reset_ts
        except Exception as exc:
            # Fallback in-memory em caso de falha do Redis
            logger.debug("Redis rate limit fallback: %s", exc)
            return _mem_check(key, limit, self._window)
