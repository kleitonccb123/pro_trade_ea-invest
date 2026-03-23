"""
Audit Logger — Strategy Manager Events

Append-only structured logger for strategy lifecycle events.
All events are persisted in MongoDB collection `strategy_audit_log`.

Retention: 90+ days (enforced by TTL index created on startup).
"""

from __future__ import annotations

import logging
import socket
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.database import get_db

logger = logging.getLogger(__name__)

_HOSTNAME = socket.gethostname()

# ─────────────────────────────────────────────────────────────────────────────
# Event constants
# ─────────────────────────────────────────────────────────────────────────────
class AuditEvent:
    STRATEGY_ACTIVATED        = "STRATEGY_ACTIVATED"
    STRATEGY_DEACTIVATED      = "STRATEGY_DEACTIVATED"
    SWITCH_INITIATED          = "SWITCH_INITIATED"
    POSITION_CLOSED           = "POSITION_CLOSED"
    ORDER_CANCELLED           = "ORDER_CANCELLED"
    RISK_ZERO_CONFIRMED       = "RISK_ZERO_CONFIRMED"
    CONTEXT_CLEARED           = "CONTEXT_CLEARED"
    STRATEGY_SWITCHED         = "STRATEGY_SWITCHED"
    STATE_TRANSITION          = "STATE_TRANSITION"
    SWITCH_ABORTED_RISK_ACTIVE = "SWITCH_ABORTED_RISK_ACTIVE"
    WORKER_FORCE_KILLED       = "WORKER_FORCE_KILLED"
    POSITION_CLOSE_FAILED     = "POSITION_CLOSE_FAILED"
    SWITCH_UNHANDLED_ERROR    = "SWITCH_UNHANDLED_ERROR"
    STARTUP_RECOVERY          = "STARTUP_RECOVERY"
    STARTUP_RECOVERY_COMPLETE = "STARTUP_RECOVERY_COMPLETE"
    ACTIVATION_FAILED         = "ACTIVATION_FAILED"
    NEW_STRATEGY_ACTIVATION_FAILED = "NEW_STRATEGY_ACTIVATION_FAILED"
    ALL_WORKERS_STOPPED       = "ALL_WORKERS_STOPPED"
    RISK_CHECK_PENDING        = "RISK_CHECK_PENDING"


# ─────────────────────────────────────────────────────────────────────────────
# AuditLogger
# ─────────────────────────────────────────────────────────────────────────────
class AuditLogger:
    """
    Append-only structured audit logger backed by MongoDB.
    Thread/coroutine-safe: each write is an independent insert_one.
    """

    COLLECTION = "strategy_audit_log"

    def __init__(self, user_id: str):
        self.user_id = user_id

    # ── public level helpers ──────────────────────────────────────────────────

    def info(self, event: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._write("INFO", event, data or kwargs)

    def debug(self, event: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._write("DEBUG", event, data or kwargs)

    def warning(self, event: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._write("WARNING", event, data or kwargs)

    def error(self, event: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._write("ERROR", event, data or kwargs)

    def critical(self, event: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._write("CRITICAL", event, data or kwargs)

    # ── internal ─────────────────────────────────────────────────────────────

    def _write(self, level: str, event: str, data: Dict[str, Any]):
        """Fire-and-forget write to Python logger + async DB persist."""
        try:
            # Always emit to Python logging first (synchronous, never fails)
            py_logger = logging.getLogger("strategy_audit")
            msg = f"[AUDIT][{level}][{event}] user={self.user_id} data={data}"
            getattr(py_logger, level.lower(), py_logger.info)(msg)

            # Async-compatible write: schedule coroutine without blocking
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._async_persist(level, event, data))
                else:
                    loop.run_until_complete(self._async_persist(level, event, data))
            except RuntimeError:
                # No event loop — best-effort only (e.g., during tests)
                pass
        except Exception as exc:
            logger.warning(f"[AuditLogger] Failed to write event {event}: {exc}")

    async def _async_persist(self, level: str, event: str, data: Dict[str, Any]):
        """Persist one audit record to MongoDB (append-only)."""
        try:
            db = get_db()
            col = db[self.COLLECTION]
            record = {
                "timestamp":    datetime.now(timezone.utc),
                "level":        level,
                "event":        event,
                "user_id":      self.user_id,
                "data":         data,
                "host":         _HOSTNAME,
            }
            # Synchronous insert because get_db() may return a MockCollection
            if hasattr(col.insert_one, "__call__"):
                result = col.insert_one(record)
                # Support both sync and async insert_one
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            logger.warning(f"[AuditLogger] DB persist failed for {event}: {exc}")

    # ── TTL index setup ───────────────────────────────────────────────────────

    @classmethod
    async def ensure_ttl_index(cls, retention_days: int = 90):
        """
        Create TTL index on `timestamp` field so records expire automatically.
        Call once on application startup.
        """
        try:
            db = get_db()
            col = db[cls.COLLECTION]
            if hasattr(col, "create_index"):
                await col.create_index(
                    "timestamp",
                    expireAfterSeconds=retention_days * 86400,
                    background=True,
                )
            logger.info(f"[AuditLogger] TTL index set: {retention_days} days retention")
        except Exception as exc:
            logger.warning(f"[AuditLogger] Could not create TTL index: {exc}")
