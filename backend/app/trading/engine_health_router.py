"""
Engine Health Router — PEND-03

Exposes:
  GET /api/engine/health         — overall engine health
  GET /api/engine/latency        — API call latency statistics
  GET /api/engine/circuit-breaker — circuit breaker state
  GET /api/engine/audit/{bot_id} — trade audit trail for a bot
  POST /api/engine/connectivity  — run KuCoin connectivity check (admin)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

logger = logging.getLogger("engine.health_router")
router = APIRouter(prefix="/api/engine", tags=["Engine Health"])

_START_TIME = time.monotonic()


# ─────────────── Response Schemas ────────────────────────────────────────────

class LatencyStats(BaseModel):
    count: int = 0
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    error_rate_pct: float = 0.0


class CircuitBreakerStatus(BaseModel):
    state: str
    consecutive_fails: int = 0
    error_rate_pct: float = 0.0
    opened_at: Optional[float] = None
    window_size: int = 0


class EngineHealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    uptime_s: float
    mode: str  # "sandbox" or "production"
    circuit_breaker: Optional[CircuitBreakerStatus] = None
    latency_global: Optional[LatencyStats] = None
    active_workers: int = 0


class AuditEvent(BaseModel):
    event_type: str
    user_id: str
    bot_id: Optional[str] = None
    order_id: Optional[str] = None
    client_oid: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    amount: Optional[float] = None
    price: Optional[float] = None
    fee: Optional[float] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = {}
    timestamp: Optional[str] = None


# ─────────────── Endpoints ───────────────────────────────────────────────────

@router.get("/health", response_model=EngineHealthResponse)
async def engine_health(current_user=Depends(get_current_user)):
    """Overall engine health: uptime, mode, circuit breaker, latency."""
    uptime = time.monotonic() - _START_TIME
    mode = "sandbox" if os.getenv("KUCOIN_SANDBOX", "false").lower() in ("1", "true", "yes") else "production"

    # Circuit breaker status
    cb_status = None
    try:
        from app.trading.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        if cb:
            raw = cb.status()
            cb_status = CircuitBreakerStatus(**raw)
    except Exception:
        pass

    # Latency
    lat_stats = None
    try:
        from app.trading.production_validator import get_latency_monitor
        lat_stats = LatencyStats(**get_latency_monitor().stats())
    except Exception:
        pass

    # Workers count
    workers = 0
    try:
        from app.engine.orchestrator import BotOrchestrator
        # Orchestrator is typically run in a separate process, so we fallback to 0
    except Exception:
        pass

    # Determine overall status
    status = "healthy"
    if cb_status and cb_status.state == "open":
        status = "unhealthy"
    elif cb_status and cb_status.state == "half_open":
        status = "degraded"
    elif lat_stats and lat_stats.error_rate_pct > 25:
        status = "degraded"

    return EngineHealthResponse(
        status=status,
        uptime_s=round(uptime, 2),
        mode=mode,
        circuit_breaker=cb_status,
        latency_global=lat_stats,
        active_workers=workers,
    )


@router.get("/latency")
async def engine_latency(
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    current_user=Depends(get_current_user),
):
    """Per-endpoint latency statistics."""
    from app.trading.production_validator import get_latency_monitor

    monitor = get_latency_monitor()
    if endpoint:
        return monitor.stats(endpoint)
    return monitor.all_endpoint_stats()


@router.get("/circuit-breaker")
async def circuit_breaker_status(current_user=Depends(get_current_user)):
    """Current circuit breaker state and counters."""
    result: Dict[str, Any] = {}

    # Trading ExchangeHealthMonitor
    try:
        from app.trading.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        if cb:
            result["exchange_health_monitor"] = cb.status()
    except Exception:
        result["exchange_health_monitor"] = None

    # Core resilience circuit breakers
    try:
        from app.core.resilience import CircuitBreaker
        result["resilience_breakers"] = CircuitBreaker.get_all_stats()
    except Exception:
        result["resilience_breakers"] = {}

    return result


@router.get("/audit/{bot_id}", response_model=List[AuditEvent])
async def get_bot_audit_trail(
    bot_id: str,
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user=Depends(get_current_user),
):
    """Trade audit trail for a specific bot."""
    from app.trading.production_validator import get_trade_audit

    user_id = str(current_user.get("_id", current_user.get("id", "")))
    audit = get_trade_audit()
    events = await audit.get_user_events(
        user_id=user_id,
        event_type=event_type,
        bot_id=bot_id,
        limit=limit,
    )
    for e in events:
        if e.get("timestamp"):
            e["timestamp"] = e["timestamp"].isoformat() if hasattr(e["timestamp"], "isoformat") else str(e["timestamp"])
    return events


@router.get("/audit/order/{order_id}")
async def get_order_audit_trail(
    order_id: str,
    current_user=Depends(get_current_user),
):
    """Full lifecycle trail for a single order."""
    from app.trading.production_validator import get_trade_audit

    audit = get_trade_audit()
    events = await audit.get_order_trail(order_id)
    for e in events:
        if e.get("timestamp"):
            e["timestamp"] = e["timestamp"].isoformat() if hasattr(e["timestamp"], "isoformat") else str(e["timestamp"])
    return events
