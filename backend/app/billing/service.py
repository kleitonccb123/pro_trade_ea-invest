"""
Billing Service — Subscription Management, Invoices & Revenue Metrics

Provides:
  - Subscription lifecycle: cancel, change plan
  - Invoices: auto-generated from webhook events
  - Admin revenue metrics: MRR, churn, active subscribers
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Invoice generation from webhook events
# ---------------------------------------------------------------------------

async def generate_invoice_from_event(
    db: Any,
    user_id: str,
    sale_id: str,
    payload: dict,
) -> str:
    """
    Creates an invoice document from a Perfect Pay postback.
    Returns the invoice_id (str representation of the inserted _id).
    """
    now = datetime.now(timezone.utc)
    amount_str = payload.get("sale_amount") or "0"
    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        amount = 0.0

    doc = {
        "user_id":        user_id,
        "sale_id":        sale_id,
        "status":         "paid",
        "amount":         amount,
        "currency":       "BRL",
        "payment_method": payload.get("payment_method"),
        "product_name":   payload.get("product_name"),
        "subscription_id": payload.get("subscription_id"),
        "customer_email": payload.get("customer_email"),
        "created_at":     now,
    }
    result = await db.invoices.insert_one(doc)
    return str(result.inserted_id)


async def get_user_invoices(
    db: Any,
    user_id: str,
    limit: int = 50,
) -> List[dict]:
    """Returns the most recent invoices for a user, newest first."""
    cursor = db.invoices.find(
        {"user_id": user_id},
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ---------------------------------------------------------------------------
# Subscription cancel request (user-initiated)
# ---------------------------------------------------------------------------

async def cancel_subscription(
    db: Any,
    user_id: str,
    reason: str = "user_request",
) -> dict:
    """
    Records a cancellation request and initiates grace period.

    The actual plan downgrade happens when the grace period expires
    (handled by LicensingService._resolve_license).
    """
    now = datetime.now(timezone.utc)
    grace_until = now + timedelta(days=3)

    # Update licenses collection
    await db.licenses.update_one(
        {"user_id": user_id},
        {"$set": {
            "cancel_requested_at": now,
            "cancel_reason":       reason,
            "in_grace_period":     True,
            "grace_until":         grace_until,
            "updated_at":          now,
        }},
    )

    # Audit trail
    await db.license_audit.insert_one({
        "user_id":   user_id,
        "event":     "cancel_requested",
        "context":   {"reason": reason, "grace_until": grace_until.isoformat()},
        "timestamp": now,
    })

    return {
        "canceled": True,
        "grace_until": grace_until.isoformat(),
        "message": "Assinatura será encerrada após o período de carência.",
    }


# ---------------------------------------------------------------------------
# Admin revenue metrics
# ---------------------------------------------------------------------------

async def compute_revenue_metrics(db: Any) -> Dict[str, Any]:
    """
    Computes key billing metrics from the licenses and invoices collections.

    Returns:
      - mrr (Monthly Recurring Revenue)
      - active_subscribers (count)
      - churned_30d (users who downgraded in the last 30 days)
      - churn_rate (churned / (active + churned))
      - total_revenue (sum of all invoices)
      - revenue_30d (last 30 days)
      - avg_revenue_per_user (ARPU)
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Active subscribers: license plan != 'free', not expired
    active_count = await db.licenses.count_documents({
        "plan": {"$nin": ["free", "starter"]},
        "$or": [
            {"expires_at": {"$gte": now}},
            {"expires_at": None},
        ],
    })

    # Churned in last 30 days
    churned_count = await db.license_audit.count_documents({
        "event": "downgraded_to_free",
        "timestamp": {"$gte": thirty_days_ago},
    })

    # Churn rate
    denominator = active_count + churned_count
    churn_rate = round(churned_count / denominator, 4) if denominator > 0 else 0.0

    # Revenue metrics from invoices
    pipeline_total = [
        {"$match": {"status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    total_agg = await db.invoices.aggregate(pipeline_total).to_list(length=1)
    total_revenue = total_agg[0]["total"] if total_agg else 0.0
    total_invoices = total_agg[0]["count"] if total_agg else 0

    pipeline_30d = [
        {"$match": {"status": "paid", "created_at": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    rev_30d_agg = await db.invoices.aggregate(pipeline_30d).to_list(length=1)
    revenue_30d = rev_30d_agg[0]["total"] if rev_30d_agg else 0.0

    # MRR = revenue in last 30 days (simple approximation)
    mrr = round(revenue_30d, 2)

    # ARPU
    arpu = round(total_revenue / active_count, 2) if active_count > 0 else 0.0

    return {
        "mrr":                round(mrr, 2),
        "active_subscribers": active_count,
        "churned_30d":        churned_count,
        "churn_rate":         churn_rate,
        "total_revenue":      round(total_revenue, 2),
        "revenue_30d":        round(revenue_30d, 2),
        "total_invoices":     total_invoices,
        "arpu":               round(arpu, 2),
        "computed_at":        now.isoformat(),
    }


async def list_active_subscribers(
    db: Any,
    skip: int = 0,
    limit: int = 50,
) -> List[dict]:
    """Returns active subscriber license docs newest first."""
    now = datetime.now(timezone.utc)
    cursor = db.licenses.find(
        {
            "plan": {"$nin": ["free", "starter"]},
            "$or": [
                {"expires_at": {"$gte": now}},
                {"expires_at": None},
            ],
        },
    ).sort("activated_at", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def list_billing_events(
    db: Any,
    limit: int = 100,
) -> List[dict]:
    """Returns recent webhook events newest first."""
    cursor = db.webhook_events.find(
        {},
    ).sort("processed_at", -1).limit(limit)
    return await cursor.to_list(length=limit)
