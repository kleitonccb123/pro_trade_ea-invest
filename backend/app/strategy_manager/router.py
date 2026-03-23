"""
Strategy Manager — FastAPI Router

Endpoints:
  POST /api/strategy-manager/{bot_id}/activate  — Activate/switch strategy
  POST /api/strategy-manager/deactivate         — Deactivate current strategy
  GET  /api/strategy-manager/active             — Get active strategy
  GET  /api/strategy-manager/state              — Get full system state
  GET  /api/strategy-manager/audit-log          — Recent audit events

All endpoints require Bearer token authentication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.services.strategy_manager import ActivationResult, StrategyManager, StrategyState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy-manager", tags=["🤖 Strategy Manager"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class ActivateRequest(BaseModel):
    """Optional body for activation — all metadata comes from path/token."""
    note: Optional[str] = Field(None, description="Optional note about why this strategy is being activated.")


class ActivationResponse(BaseModel):
    success:          bool
    strategy_id:      Optional[str] = None
    status:           str
    message:          str
    detail:           Optional[Dict[str, Any]] = None
    activated_at:     Optional[str] = None


class SystemStateResponse(BaseModel):
    system_state:      str
    active_strategy:   Optional[str] = None
    previous_strategy: Optional[str] = None
    last_switch:       Optional[str] = None
    uptime_seconds:    Optional[int] = None


class AuditLogEntry(BaseModel):
    timestamp: Optional[str] = None
    level:     Optional[str] = None
    event:     Optional[str] = None
    data:      Optional[Dict[str, Any]] = None


class AuditLogResponse(BaseModel):
    entries: List[AuditLogEntry]
    total:   int


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _user_id(current_user: dict) -> str:
    uid = current_user.get("id") or current_user.get("_id")
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User identity missing.")
    return str(uid)


def _map_result(result: ActivationResult, activated_at: Optional[str] = None) -> ActivationResponse:
    return ActivationResponse(
        success=result.success,
        strategy_id=result.strategy_id,
        status=result.status,
        message=result.message,
        detail=result.detail,
        activated_at=activated_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{bot_id}/activate",
    response_model=ActivationResponse,
    summary="Activate or switch to a strategy",
    description="""
Activates the specified bot/strategy for the authenticated user.

**Single Strategy Mode enforced:**
- If no strategy is active → activates immediately.
- If another strategy is active → triggers the full safe-switch pipeline:
  1. Block new entries on current strategy
  2. Close all open positions & cancel pending orders
  3. Verify zero-risk state
  4. Clean context of previous strategy
  5. Activate new strategy

**Rejection codes:**
- `TOO_SOON` — Minimum switch interval not elapsed
- `ALREADY_ACTIVE` — This strategy is already active
- `SYSTEM_IN_TRANSITION` — A switch is already in progress
- `BOT_NOT_FOUND` — Bot does not exist or does not belong to user
- `LOCK_UNAVAILABLE` — Concurrent activation attempt rejected
- `WAITING_POSITIONS_CLOSE` — Positions could not be fully closed
""",
)
async def activate_strategy(
    bot_id: str,
    body: Optional[ActivateRequest] = None,
    current_user: dict = Depends(get_current_user),
) -> ActivationResponse:
    uid = _user_id(current_user)
    mgr = StrategyManager(uid)

    try:
        result = await mgr.activate_strategy(
            bot_id=bot_id,
            requested_by=uid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"[strategy-manager] activate error user={uid} bot={bot_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during strategy activation.",
        )

    if not result.success:
        # Map rejection codes to appropriate HTTP status
        code_map = {
            "TOO_SOON":              status.HTTP_429_TOO_MANY_REQUESTS,
            "ALREADY_ACTIVE":        status.HTTP_409_CONFLICT,
            "SYSTEM_IN_TRANSITION":  status.HTTP_409_CONFLICT,
            "BOT_NOT_FOUND":         status.HTTP_404_NOT_FOUND,
            "LOCK_UNAVAILABLE":      status.HTTP_503_SERVICE_UNAVAILABLE,
            "WAITING_POSITIONS_CLOSE": status.HTTP_409_CONFLICT,
        }
        http_code = code_map.get(result.status, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=http_code, detail=result.to_dict())

    return _map_result(result, activated_at=datetime.now(timezone.utc).isoformat())


@router.post(
    "/deactivate",
    response_model=ActivationResponse,
    summary="Deactivate the currently active strategy",
    description="Stops the active strategy and returns the system to IDLE state.",
)
async def deactivate_strategy(
    current_user: dict = Depends(get_current_user),
) -> ActivationResponse:
    uid = _user_id(current_user)
    mgr = StrategyManager(uid)

    try:
        result = await mgr.deactivate_strategy(requested_by=uid)
    except Exception as exc:
        logger.error(f"[strategy-manager] deactivate error user={uid}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during deactivation.",
        )

    if not result.success:
        code_map = {
            "NOT_ACTIVE":           status.HTTP_409_CONFLICT,
            "SYSTEM_IN_TRANSITION": status.HTTP_409_CONFLICT,
            "LOCK_UNAVAILABLE":     status.HTTP_503_SERVICE_UNAVAILABLE,
        }
        http_code = code_map.get(result.status, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=http_code, detail=result.to_dict())

    return _map_result(result)


@router.get(
    "/state",
    response_model=SystemStateResponse,
    summary="Get current system state",
    description="Returns the current state of the Strategy Manager for the authenticated user.",
)
async def get_system_state(
    current_user: dict = Depends(get_current_user),
) -> SystemStateResponse:
    uid = _user_id(current_user)
    mgr = StrategyManager(uid)
    state = await mgr.get_state()
    return SystemStateResponse(**state)


@router.get(
    "/active",
    response_model=Dict[str, Any],
    summary="Get the currently active strategy",
    description="Returns the active bot/strategy identifier and activation time.",
)
async def get_active_strategy(
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = _user_id(current_user)
    mgr = StrategyManager(uid)
    state = await mgr.get_state()

    return {
        "active_strategy": state.get("active_strategy"),
        "system_state":    state.get("system_state"),
        "last_switch":     state.get("last_switch"),
        "uptime_seconds":  state.get("uptime_seconds"),
    }


@router.get(
    "/switch-status",
    response_model=Dict[str, Any],
    summary="Get status of an in-progress strategy switch",
    description="Returns detailed transition status when the system is in a switching state.",
)
async def get_switch_status(
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = _user_id(current_user)
    mgr = StrategyManager(uid)
    state = await mgr.get_state()

    system_state = state.get("system_state", StrategyState.IDLE)
    in_transition = system_state not in (StrategyState.IDLE, StrategyState.ACTIVE)

    return {
        "in_transition":     in_transition,
        "current_state":     system_state,
        "active_strategy":   state.get("active_strategy"),
        "previous_strategy": state.get("previous_strategy"),
    }


@router.get(
    "/audit-log",
    response_model=AuditLogResponse,
    summary="Get recent strategy audit events",
    description="Returns the N most recent audit log entries for the authenticated user.",
)
async def get_audit_log(
    limit: int = Query(default=50, ge=1, le=200, description="Number of recent entries to return"),
    current_user: dict = Depends(get_current_user),
) -> AuditLogResponse:
    uid = _user_id(current_user)

    try:
        db = get_db()
        col = db["strategy_audit_log"]
        docs = col.find({"user_id": uid}).sort("timestamp", -1).limit(limit)

        entries = []
        if hasattr(docs, "__aiter__"):
            async for doc in docs:
                entries.append(_doc_to_entry(doc))
        else:
            try:
                for doc in docs:
                    entries.append(_doc_to_entry(doc))
            except Exception:
                pass

        return AuditLogResponse(entries=entries, total=len(entries))

    except Exception as exc:
        logger.error(f"[strategy-manager] audit-log error user={uid}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve audit log.",
        )


def _doc_to_entry(doc: Dict[str, Any]) -> AuditLogEntry:
    ts = doc.get("timestamp")
    return AuditLogEntry(
        timestamp=ts.isoformat() if isinstance(ts, datetime) else str(ts) if ts else None,
        level=doc.get("level"),
        event=doc.get("event"),
        data=doc.get("data"),
    )
