from __future__ import annotations

from fastapi import APIRouter, Depends, Body
from typing import Optional

from app.auth.dependencies import get_current_user
from app.real_time.kucoin_service import kucoin_service
from app.websockets.notification_hub import notification_hub, notify_trade, Notification, NotificationType, NotificationPriority
from app.users.repository import UserRepository

router = APIRouter(prefix="/api/test", tags=["Test Realtime"])


@router.post("/start-session")
async def start_session(current_user=Depends(get_current_user)):
    """Start a simulated KuCoin monitoring session for the logged user."""
    user_id = str(getattr(current_user, "id", current_user))

    # start monitoring with mocked credentials / params
    try:
        await kucoin_service.start_monitoring(user_id, credentials={"mode": "mock", "source": "test_router"})
    except Exception as e:
        return {"started": False, "error": str(e)}

    return {"started": True, "user_id": user_id}


@router.post("/mock-trade")
async def mock_trade(payload: dict = Body(...), current_user=Depends(get_current_user)):
    """Inject a mock trade (order filled) to the user's websocket connections.

    Expected payload keys (optional): symbol, side, price, amount
    """
    user_id = str(getattr(current_user, "id", current_user))
    symbol = payload.get("symbol", "BTC/USDT")
    side = payload.get("side", "buy")
    price = float(payload.get("price", 48500))
    amount = float(payload.get("amount", 0.001))
    order_id = payload.get("order_id", f"test-{int(__import__('time').time())}")

    # Use helper to construct canonical notification shape
    sent = await notify_trade(user_id, symbol, side, amount, price, order_id=order_id)

    return {"sent_connections": sent, "user_id": user_id, "payload": {"symbol": symbol, "side": side, "price": price, "amount": amount}}


@router.post("/mock-price")
async def mock_price(payload: dict = Body(...), current_user=Depends(get_current_user)):
    """Inject a simulated ticker/price update. This will be emitted as a lightweight trade tick
    so the frontend chart updates its last candle.
    """
    user_id = str(getattr(current_user, "id", current_user))
    symbol = payload.get("symbol", "BTC/USDT")
    price = float(payload.get("price", 48500))

    # Send a tiny trade tick to make the chart pulse
    sent = await notify_trade(user_id, symbol, "buy", 0.0001, price, order_id=f"tick-{int(__import__('time').time())}")

    return {"sent_connections": sent, "user_id": user_id, "price": price}


@router.post("/ensure-demo-user")
async def ensure_demo_user():
    """Create a demo user in the connected database if it does not exist.

    This helps when running against MongoDB Atlas to ensure a known test account exists.
    """
    demo_email = "demo@tradehub.com"
    existing = await UserRepository.find_by_email(demo_email)
    if existing:
        return {"created": False, "message": "Demo user already exists", "email": demo_email}

    try:
        user = await UserRepository.create(email=demo_email, password="demo123", name="Demo User")
        return {"created": True, "email": demo_email, "user_id": str(user.get("_id"))}
    except Exception as e:
        return {"created": False, "error": str(e)}


@router.post("/create-user")
async def create_user(payload: dict = Body(...)):
    """Create a user with provided email/password for testing.

    payload: { "email": "...", "password": "...", "name": "..." }
    """
    email = payload.get("email")
    password = payload.get("password")
    name = payload.get("name", None)
    if not email or not password:
        return {"created": False, "error": "email and password required"}

    try:
        user = await UserRepository.create(email=email, password=password, name=name)
        return {"created": True, "email": email, "user_id": str(user.get("_id"))}
    except Exception as e:
        return {"created": False, "error": str(e)}
