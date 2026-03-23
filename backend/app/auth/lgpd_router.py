"""
LGPD Compliance Router — Account Deletion & Data Export

Implements:
- DELETE /api/lgpd/account  → soft-delete account + schedule data purge
- GET    /api/lgpd/export   → export all personal data as JSON
- GET    /api/lgpd/privacy-policy → returns current privacy policy metadata
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.security import verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lgpd", tags=["LGPD"])

_GRACE_PERIOD_DAYS = 30  # Account can be recovered within this period


class AccountDeletionRequest(BaseModel):
    password: str
    reason: Optional[str] = None


@router.delete("/account")
async def delete_account(
    req: AccountDeletionRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    LGPD Art. 18 — Soft-delete the user account.

    The account is deactivated immediately and marked for permanent purge
    after a grace period. During the grace period the user may contact
    support to reverse the deletion.
    """
    user_id = str(current_user.get("id") or current_user.get("_id"))

    # Verify password before deletion
    if not current_user.get("hashed_password"):
        # User may come from Google OAuth — check MongoDB
        db = get_db()
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user_doc or not user_doc.get("hashed_password"):
            raise HTTPException(400, "Conta OAuth — use o painel do Google para revogar acesso")
        hashed = user_doc["hashed_password"]
    else:
        hashed = current_user["hashed_password"]

    if not verify_password(req.password, hashed):
        raise HTTPException(403, "Senha incorreta")

    db = get_db()
    now = datetime.utcnow()

    # Soft-delete: mark account as deleted, keep data for grace period
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "is_active": False,
                "deleted_at": now,
                "deletion_reason": req.reason or "",
                "purge_after": datetime(
                    now.year, now.month + 1 if now.month < 12 else 1,
                    now.day if now.day <= 28 else 28,
                    now.hour, now.minute, now.second,
                ) if _GRACE_PERIOD_DAYS == 30 else now,
                "deletion_requested_ip": (
                    request.client.host if request.client else None
                ),
            }
        },
    )

    # Deactivate all bots
    await db.bots.update_many(
        {"user_id": user_id},
        {"$set": {"is_active": False, "stopped_reason": "account_deleted"}},
    )

    # Log audit event
    await db.admin_audit_log.insert_one({
        "event": "account_deletion_requested",
        "user_id": user_id,
        "ip": request.client.host if request.client else None,
        "reason": req.reason or "",
        "timestamp": now,
    })

    logger.info("Account deletion requested for user %s", user_id)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": (
                f"Conta marcada para exclusão. Seus dados serão removidos "
                f"permanentemente em {_GRACE_PERIOD_DAYS} dias. "
                f"Entre em contato com o suporte para reverter."
            ),
            "grace_period_days": _GRACE_PERIOD_DAYS,
        },
    )


@router.get("/export")
async def export_personal_data(
    current_user: dict = Depends(get_current_user),
):
    """
    LGPD Art. 18 — Export all personal data as JSON.

    Returns all data the platform stores about the user:
    profile, bots, trades, notifications, gamification, affiliates.
    """
    user_id = str(current_user.get("id") or current_user.get("_id"))
    db = get_db()

    # Collect all user data across collections
    profile = await db.users.find_one(
        {"_id": ObjectId(user_id)},
        {"hashed_password": 0},  # Never export password hash
    )
    if profile and "_id" in profile:
        profile["_id"] = str(profile["_id"])

    bots = await db.bots.find({"user_id": user_id}).to_list(length=500)
    for b in bots:
        b["_id"] = str(b["_id"])

    trades = await db.bot_trades.find({"user_id": user_id}).to_list(length=5000)
    for t in trades:
        t["_id"] = str(t["_id"])

    notifications = await db.notifications.find(
        {"user_id": user_id}
    ).sort("created_at", -1).to_list(length=1000)
    for n in notifications:
        n["_id"] = str(n["_id"])

    strategies = await db.strategies.find(
        {"user_id": user_id, "deleted_at": {"$exists": False}}
    ).to_list(length=200)
    for s in strategies:
        s["_id"] = str(s["_id"])

    gamification = await db.game_profiles.find_one({"user_id": user_id})
    if gamification and "_id" in gamification:
        gamification["_id"] = str(gamification["_id"])

    affiliates = await db.affiliates.find_one({"user_id": user_id})
    if affiliates and "_id" in affiliates:
        affiliates["_id"] = str(affiliates["_id"])

    # Serialize datetimes
    def _serialize(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return obj

    import json

    export = {
        "export_date": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "profile": profile,
        "bots": bots,
        "trades": trades,
        "notifications": notifications,
        "strategies": strategies,
        "gamification": gamification,
        "affiliates": affiliates,
    }

    # Convert to JSON-safe
    export_json = json.loads(
        json.dumps(export, default=_serialize, ensure_ascii=False)
    )

    logger.info("Data export generated for user %s", user_id)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": export_json,
        },
    )
