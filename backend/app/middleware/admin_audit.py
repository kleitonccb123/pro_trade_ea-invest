"""
Admin Audit Trail — Logs all administrative actions to MongoDB.

Usage:
    from app.middleware.admin_audit import log_admin_action

    await log_admin_action(
        db=db,
        admin_id="user_123",
        action="kill_switch_activated",
        target_user_id="user_456",
        details={"reason": "suspicious activity"},
        ip="192.168.1.1",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

_COLLECTION = "admin_audit_log"


async def log_admin_action(
    db: Any,
    admin_id: str,
    action: str,
    target_user_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip: Optional[str] = None,
) -> None:
    """
    Persist an admin action to the audit log (immutable).

    Parameters
    ----------
    db              : AsyncIOMotorDatabase
    admin_id        : ID of the admin performing the action
    action          : action key (e.g. "user_banned", "plan_changed", "kill_switch")
    target_user_id  : user affected by the action (if applicable)
    details         : additional context about the action
    ip              : IP address of the admin
    """
    doc = {
        "admin_id": admin_id,
        "action": action,
        "target_user_id": target_user_id,
        "details": details or {},
        "ip": ip,
        "timestamp": datetime.utcnow(),
    }
    try:
        await db[_COLLECTION].insert_one(doc)
    except Exception as exc:
        logger.error(
            "admin_audit: failed to log action=%s admin=%s: %s",
            action, admin_id, exc,
        )


async def create_admin_audit_indexes(db: Any) -> None:
    """Create indexes for admin_audit_log. Call on startup."""
    coll = db[_COLLECTION]
    try:
        await coll.create_index([("admin_id", 1), ("timestamp", -1)], background=True)
        await coll.create_index([("action", 1), ("timestamp", -1)], background=True)
        await coll.create_index([("target_user_id", 1)], sparse=True, background=True)
        logger.info("admin_audit_log: indexes created")
    except Exception as exc:
        logger.warning("admin_audit_log: index creation failed: %s", exc)
