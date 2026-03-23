"""
Billing Management Router — Subscription Lifecycle & Admin Revenue

Endpoints (user):
  POST /api/billing/cancel         — Cancel subscription (grace period)
  GET  /api/billing/invoices       — User's billing history
  GET  /api/billing/invoices/{id}  — Single invoice detail

Endpoints (admin):
  GET  /api/admin/billing/metrics      — MRR, churn, revenue
  GET  /api/admin/billing/subscribers  — Active subscriber list
  GET  /api/admin/billing/events       — Recent billing events
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.database import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/billing", tags=["Billing"])
admin_router = APIRouter(prefix="/api/admin/billing", tags=["Admin Billing"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CancelRequest(BaseModel):
    reason: str = Field(
        default="user_request",
        description="Motivo do cancelamento",
        max_length=500,
    )


class CancelResponse(BaseModel):
    canceled: bool
    grace_until: str
    message: str


class InvoiceOut(BaseModel):
    sale_id: str
    status: str
    amount: float
    currency: str = "BRL"
    payment_method: Optional[str] = None
    product_name: Optional[str] = None
    subscription_id: Optional[str] = None
    created_at: Optional[str] = None


class RevenueMetricsOut(BaseModel):
    mrr: float
    active_subscribers: int
    churned_30d: int
    churn_rate: float
    total_revenue: float
    revenue_30d: float
    total_invoices: int
    arpu: float
    computed_at: str


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/cancel",
    response_model=CancelResponse,
    summary="Cancelar assinatura (inicia grace period de 3 dias)",
)
async def cancel_subscription_endpoint(
    body: CancelRequest,
    current_user: dict = Depends(get_current_user),
) -> CancelResponse:
    """
    O cancelamento não é imediato — o usuário mantém acesso por 3 dias
    (grace period) para que possa reverter a decisão.
    """
    user_id = str(current_user["_id"])
    plan = str(current_user.get("plan", "free")).lower()
    if plan in ("free", "starter"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não há assinatura ativa para cancelar.",
        )

    from app.billing.service import cancel_subscription
    db = get_db()
    result = await cancel_subscription(db, user_id, body.reason)

    # Invalidate license cache
    from app.licensing.service import get_licensing_service
    svc = get_licensing_service()
    if svc:
        await svc.invalidate_cache(user_id)

    return CancelResponse(**result)


@router.get(
    "/invoices",
    response_model=List[InvoiceOut],
    summary="Histórico de faturas do usuário",
)
async def list_invoices(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
) -> List[dict]:
    from app.billing.service import get_user_invoices
    db = get_db()
    user_id = str(current_user["_id"])
    invoices = await get_user_invoices(db, user_id, limit=limit)
    for inv in invoices:
        if inv.get("created_at"):
            inv["created_at"] = inv["created_at"].isoformat()
    return invoices


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

def _require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem acessar este recurso.",
        )
    return current_user


@admin_router.get(
    "/metrics",
    response_model=RevenueMetricsOut,
    summary="Métricas de receita (MRR, churn, ARPU)",
)
async def revenue_metrics(
    _admin: dict = Depends(_require_admin),
) -> Dict[str, Any]:
    from app.billing.service import compute_revenue_metrics
    db = get_db()
    return await compute_revenue_metrics(db)


@admin_router.get(
    "/subscribers",
    summary="Lista de assinantes ativos",
)
async def active_subscribers(
    _admin: dict = Depends(_require_admin),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> List[dict]:
    from app.billing.service import list_active_subscribers
    db = get_db()
    return await list_active_subscribers(db, skip=skip, limit=limit)


@admin_router.get(
    "/events",
    summary="Eventos de billing recentes",
)
async def billing_events(
    _admin: dict = Depends(_require_admin),
    limit: int = Query(default=100, ge=1, le=500),
) -> List[dict]:
    from app.billing.service import list_billing_events
    db = get_db()
    return await list_billing_events(db, limit=limit)


# ---------------------------------------------------------------------------
# Perfect Pay Webhook
# ---------------------------------------------------------------------------


@router.post(
    "/webhook/perfectpay",
    summary="Perfect Pay postback/webhook receiver",
    status_code=200,
)
async def perfectpay_webhook(
    payload: Dict[str, Any],
):
    """
    Receives Perfect Pay payment notifications.

    Processes subscription events (purchase, cancellation, refund)
    and updates user subscription status accordingly.
    """

    db = get_db()

    event = payload.get("event", "")
    data = payload.get("data", {})

    customer_email = data.get("customer", {}).get("email", "")
    transaction_id = data.get("transaction_id", "")
    plan = data.get("product", {}).get("name", "")
    amount = data.get("amount", 0)

    logger.info(
        "PerfectPay webhook: event=%s email=%s tx=%s plan=%s amount=%s",
        event, customer_email, transaction_id, plan, amount,
    )

    if event in ("purchase_approved", "subscription_active"):
        await db["billing_events"].insert_one({
            "type": "perfectpay",
            "event": event,
            "email": customer_email,
            "transaction_id": transaction_id,
            "plan": plan,
            "amount": amount,
            "raw": payload,
        })
        # Activate subscription for user
        if customer_email:
            await db["users"].update_one(
                {"email": customer_email},
                {"$set": {"subscription_status": "active", "plan": plan}},
            )
    elif event in ("subscription_canceled", "refund_approved"):
        await db["billing_events"].insert_one({
            "type": "perfectpay",
            "event": event,
            "email": customer_email,
            "transaction_id": transaction_id,
            "raw": payload,
        })
        if customer_email:
            await db["users"].update_one(
                {"email": customer_email},
                {"$set": {"subscription_status": "canceled"}},
            )
    else:
        logger.info("PerfectPay: unhandled event %s", event)

    return {"status": "ok"}
