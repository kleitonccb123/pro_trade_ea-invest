from __future__ import annotations

import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from app.core import scheduler as core_scheduler
from app.core.database import get_database, is_offline_mode
from app.core.config import settings
from app.licensing.service import licensing_service

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/scheduler/status")
async def scheduler_status():
    """Return scheduler status snapshot for observability and debug."""
    return core_scheduler.scheduler.get_status()


@router.get("/status")
async def system_status():
    """Return a compact system summary including license and scheduler state.

    This endpoint is read-only and intended for frontend dashboards and health pages.
    """
    lic = await licensing_service.get_license()
    sched = core_scheduler.scheduler.get_status()
    return {
        "license": {
            "plan": lic.plan,
            "valid": lic.valid,
            "expires_at": lic.expires_at,
            "features": lic.features,
        },
        "scheduler": sched,
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint for load balancers and monitoring.

    Returns 200 if system is healthy, 503 if unhealthy.
    This is a lightweight check that doesn't require authentication.
    """
    health_status = {
        "status": "healthy",
        "timestamp": int(time.time()),
        "version": "1.0.0",  # TODO: Get from package.json or git
        "mode": settings.app_mode,
    }

    try:
        # Check database connectivity
        if not is_offline_mode():
            db = await get_database()
            await db.command("ping")
            health_status["database"] = "connected"
        else:
            health_status["database"] = "offline_mode"

        # Check if scheduler is running
        sched_status = core_scheduler.scheduler.get_status()
        health_status["scheduler"] = "running" if sched_status.get("running", False) else "stopped"

        # Overall status
        if health_status["database"] == "connected" and health_status["scheduler"] == "running":
            health_status["status"] = "healthy"
        elif health_status["database"] == "offline_mode":
            health_status["status"] = "degraded"  # Offline mode is acceptable but degraded
        else:
            health_status["status"] = "unhealthy"

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)

    # Return appropriate HTTP status
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint for Kubernetes/load balancers.

    This performs deeper checks including exchange connectivity.
    Returns 200 if system is ready to serve traffic, 503 if not ready.
    """
    readiness_status = {
        "status": "ready",
        "timestamp": int(time.time()),
        "checks": {},
    }

    try:
        # 1. Database check
        if not is_offline_mode():
            try:
                db = await get_database()
                await db.command("ping")
                readiness_status["checks"]["database"] = "ok"
            except Exception as e:
                readiness_status["checks"]["database"] = f"failed: {str(e)}"
                readiness_status["status"] = "not_ready"
        else:
            readiness_status["checks"]["database"] = "offline_mode"

        # 2. Scheduler check
        try:
            sched_status = core_scheduler.scheduler.get_status()
            if sched_status.get("running", False):
                readiness_status["checks"]["scheduler"] = "ok"
            else:
                readiness_status["checks"]["scheduler"] = "stopped"
                readiness_status["status"] = "not_ready"
        except Exception as e:
            readiness_status["checks"]["scheduler"] = f"failed: {str(e)}"
            readiness_status["status"] = "not_ready"

        # 3. Exchange API check (basic connectivity)
        try:
            # Import here to avoid circular imports
            from app.core.resilience import kucoin_circuit

            # Check if circuit breaker is not permanently open
            if kucoin_circuit.stats.state.name == "OPEN":
                readiness_status["checks"]["exchange_api"] = "circuit_open"
                readiness_status["status"] = "not_ready"
            else:
                readiness_status["checks"]["exchange_api"] = "ok"
        except Exception as e:
            readiness_status["checks"]["exchange_api"] = f"failed: {str(e)}"
            # Don't mark as not_ready for exchange issues - system can still serve cached data

        # 4. License check
        try:
            lic = await licensing_service.get_license()
            if lic.valid:
                readiness_status["checks"]["license"] = "valid"
            else:
                readiness_status["checks"]["license"] = "invalid"
                readiness_status["status"] = "not_ready"
        except Exception as e:
            readiness_status["checks"]["license"] = f"failed: {str(e)}"
            readiness_status["status"] = "not_ready"

    except Exception as e:
        readiness_status["status"] = "not_ready"
        readiness_status["error"] = str(e)

    # Return appropriate HTTP status
    if readiness_status["status"] == "not_ready":
        raise HTTPException(status_code=503, detail=readiness_status)

    return readiness_status
