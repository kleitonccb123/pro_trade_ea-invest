"""
Health Check Endpoints — DOC-08 §6

Fornece endpoints para balanceadores de carga e sistemas de monitoramento.

Endpoints:
  GET /health          — verificação básica (usado por load balancer / k8s liveness)
  GET /health/detailed — verificação completa (MongoDB, Redis, KuCoin, Engine)

Nota: `/health` básico e `/metrics` já são expostos pelo main.py via DOC-06.
Este módulo adiciona `/health/detailed` (verificação mais detalhada, sem score ponderado)
que complementa o existente `/health` (score ponderado DOC-06).

Uso em main.py::

    from app.monitoring.health import health_router
    app.include_router(health_router)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

import httpx
from fastapi import APIRouter

from app.core.database import get_db
from app.shared.redis_client import get_redis

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["❤️ Health"])


# ── Basic health ──────────────────────────────────────────────────────────────


@health_router.get(
    "/health",
    summary="Health Check Básico",
    description="Verificação básica de liveness — usada por load balancer e k8s.",
    responses={200: {"description": "Serviço operacional"}},
)
async def health_check() -> Dict[str, Any]:
    """Verificação básica — usada por load balancer."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


# ── Detailed health ───────────────────────────────────────────────────────────


@health_router.get(
    "/health/detailed",
    summary="Health Check Detalhado",
    description="Verifica MongoDB, Redis, KuCoin API e Engine. Retorna status por componente.",
)
async def detailed_health_check() -> Dict[str, Any]:
    """
    Verificação completa — usada por monitoramento e alertas.

    Componentes verificados:
      - MongoDB (ping round-trip)
      - Redis (ping round-trip)
      - KuCoin API (GET /api/v1/timestamp, timeout 5s)
      - Engine (lê contagem de bots ativos no Redis)

    Status overall:
      "ok"       — todos os componentes operacionais
      "degraded" — pelo menos um componente com falha
    """
    checks: Dict[str, Any] = {}

    # ── MongoDB ────────────────────────────────────────────────────────────
    try:
        db = get_db()
        await db.command("ping")
        checks["mongodb"] = {"status": "ok"}
    except Exception as exc:
        checks["mongodb"] = {"status": "error", "detail": str(exc)}

    # ── Redis ──────────────────────────────────────────────────────────────
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)}

    # ── KuCoin API ─────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.kucoin.com/api/v1/timestamp")
            if resp.status_code == 200:
                checks["kucoin_api"] = {"status": "ok"}
            else:
                checks["kucoin_api"] = {"status": "degraded", "http_status": resp.status_code}
    except Exception as exc:
        checks["kucoin_api"] = {"status": "error", "detail": str(exc)}

    # ── Engine ─────────────────────────────────────────────────────────────
    try:
        redis = await get_redis()
        active_bots_count = await redis.scard("active_bots")
        checks["engine"] = {
            "status": "ok",
            "active_bots": int(active_bots_count or 0),
        }
    except Exception as exc:
        checks["engine"] = {"status": "error", "detail": str(exc)}

    # ── Resultado geral ────────────────────────────────────────────────────
    all_ok = all(c.get("status") == "ok" for c in checks.values())
    overall = "ok" if all_ok else "degraded"

    return {
        "status":    overall,
        "checks":    checks,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
