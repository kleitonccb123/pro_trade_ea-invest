"""
Notification Router - Endpoints da API de notifica??es
"""
from __future__ import annotations

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.notifications.service import notification_service
from app.notifications.models import NotificationType, NotificationPriority, PriceAlertCondition
from app.notifications.websocket import notification_ws_manager
from app.notifications.schemas import (
    NotificationOut,
    NotificationListResponse,
    MarkReadRequest,
    MarkReadResponse,
    NotificationPreferenceOut,
    NotificationPreferenceUpdate,
    PriceAlertOut,
    PriceAlertCreate,
    PriceAlertUpdate,
    PushSubscriptionRequest,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ============== VAPID PUBLIC KEY ==============

@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Return the VAPID public key so the frontend can subscribe to push."""
    return {"public_key": settings.vapid_public_key or ""}


# ============== NOTIFICATIONS ==============

@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
):
    """Lista notifica??es do usu?rio"""
    notifications, total, unread_count = await notification_service.get_notifications(
        user_id=current_user.get("id") or current_user.get("_id"),
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    
    return NotificationListResponse(
        notifications=[NotificationOut.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user),
):
    """Retorna apenas a contagem de n?o lidas"""
    _, _, unread_count = await notification_service.get_notifications(
        user_id=current_user.get("id") or current_user.get("_id"),
        limit=1,
    )
    return {"unread_count": unread_count}


@router.post("/mark-read", response_model=MarkReadResponse)
async def mark_as_read(
    request: MarkReadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Marca notifica??es como lidas"""
    count = await notification_service.mark_as_read(
        user_id=current_user.get("id") or current_user.get("_id"),
        notification_ids=request.notification_ids,
    )
    return MarkReadResponse(marked_count=count)


@router.post("/mark-all-read", response_model=MarkReadResponse)
async def mark_all_as_read(
    current_user: dict = Depends(get_current_user),
):
    """Marca todas as notifica??es como lidas"""
    count = await notification_service.mark_all_as_read(
        user_id=current_user.get("id") or current_user.get("_id"),
    )
    return MarkReadResponse(marked_count=count)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Deleta uma notifica??o"""
    success = await notification_service.delete_notification(
        user_id=current_user.get("id") or current_user.get("_id"),
        notification_id=notification_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"success": True}


# ============== PREFERENCES ==============

@router.get("/preferences", response_model=NotificationPreferenceOut)
async def get_preferences(
    current_user: dict = Depends(get_current_user),
):
    """Retorna prefer?ncias de notifica??o do usu?rio"""
    prefs = await notification_service.get_or_create_preferences(
        user_id=current_user.get("id") or current_user.get("_id"),
    )
    return NotificationPreferenceOut.model_validate(prefs)


@router.put("/preferences", response_model=NotificationPreferenceOut)
async def update_preferences(
    updates: NotificationPreferenceUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Atualiza prefer?ncias de notifica??o"""
    prefs = await notification_service.update_preferences(
        user_id=current_user.get("id") or current_user.get("_id"),
        updates=updates.model_dump(exclude_unset=True),
    )
    return NotificationPreferenceOut.model_validate(prefs)


@router.post("/preferences/push-subscription")
async def register_push_subscription(
    request: PushSubscriptionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Registra subscription para push notifications (Web Push API)"""
    success = await notification_service.register_push_subscription(
        user_id=current_user.get("id") or current_user.get("_id"),
        subscription=request.model_dump(),
    )
    return {"success": success}


# ============== PRICE ALERTS ==============

@router.get("/alerts", response_model=List[PriceAlertOut])
async def get_price_alerts(
    active_only: bool = Query(default=True),
    current_user: dict = Depends(get_current_user),
):
    """Lista alertas de pre?o do usu?rio"""
    alerts = await notification_service.get_price_alerts(
        user_id=current_user.get("id") or current_user.get("_id"),
        active_only=active_only,
    )
    return [PriceAlertOut.model_validate(a) for a in alerts]


@router.post("/alerts", response_model=PriceAlertOut, status_code=status.HTTP_201_CREATED)
async def create_price_alert(
    alert: PriceAlertCreate,
    current_user: dict = Depends(get_current_user),
):
    """Cria um novo alerta de pre?o"""
    
    # Limitar n?mero de alertas por usu?rio
    existing = await notification_service.get_price_alerts(
        user_id=current_user.get("id") or current_user.get("_id"),
        active_only=True,
    )
    
    if len(existing) >= 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum number of active alerts reached (50)"
        )
    
    new_alert = await notification_service.create_price_alert(
        user_id=current_user.get("id") or current_user.get("_id"),
        symbol=alert.symbol,
        condition=alert.condition,
        target_price=alert.target_price,
        percent_change=alert.percent_change,
        repeat=alert.repeat,
        note=alert.note,
        expires_at=alert.expires_at,
        current_price=alert.current_price,
    )
    
    return PriceAlertOut.model_validate(new_alert)


@router.put("/alerts/{alert_id}", response_model=PriceAlertOut)
async def update_price_alert(
    alert_id: int,
    updates: PriceAlertUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Atualiza um alerta de pre?o"""
    alert = await notification_service.update_price_alert(
        user_id=current_user.get("id") or current_user.get("_id"),
        alert_id=alert_id,
        updates=updates.model_dump(exclude_unset=True),
    )
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price alert not found"
        )
    
    return PriceAlertOut.model_validate(alert)


@router.delete("/alerts/{alert_id}")
async def delete_price_alert(
    alert_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Deleta um alerta de pre?o"""
    success = await notification_service.delete_price_alert(
        user_id=current_user.get("id") or current_user.get("_id"),
        alert_id=alert_id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price alert not found"
        )
    
    return {"success": True}


# ============== WEBSOCKET ==============

@router.websocket("/ws")
async def notification_websocket(websocket: WebSocket, token: str = None):
    """
    WebSocket endpoint para notifica??es em tempo real.
    Conectar com: ws://host/notifications/ws?token=JWT_TOKEN
    """
    user_id = None
    
    try:
        # Autenticar via token
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return
        
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
            user_id = payload.get("sub")
            if not user_id:
                await websocket.close(code=4002, reason="Invalid token")
                return
            user_id = int(user_id)
        except jwt.ExpiredSignatureError:
            await websocket.close(code=4003, reason="Token expired")
            return
        except JWTError:
            await websocket.close(code=4002, reason="Invalid token")
            return
        
        # Conectar
        await notification_ws_manager.connect(websocket, user_id)
        
        # Enviar contagem inicial de n?o lidas
        _, _, unread_count = await notification_service.get_notifications(
            user_id=user_id,
            limit=1
        )
        await notification_ws_manager.send_unread_count(user_id, unread_count)
        
        # Keep connection alive e processar mensagens
        while True:
            try:
                data = await websocket.receive_json()
                
                # Processar comandos do cliente
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "mark_read":
                    notification_ids = data.get("ids", [])
                    if notification_ids:
                        await notification_service.mark_as_read(user_id, notification_ids)
                        # Atualizar contagem
                        _, _, unread_count = await notification_service.get_notifications(
                            user_id=user_id,
                            limit=1
                        )
                        await notification_ws_manager.send_unread_count(user_id, unread_count)
                        
            except WebSocketDisconnect:
                break
            except Exception:
                continue
                
    finally:
        if user_id:
            await notification_ws_manager.disconnect(websocket, user_id)


# ============== TEST/ADMIN ENDPOINTS ==============

@router.post("/test")
async def send_test_notification(
    current_user: dict = Depends(get_current_user),
):
    """Envia uma notifica??o de teste"""
    notification = await notification_service.create_notification(
        user_id=current_user.get("id") or current_user.get("_id"),
        type=NotificationType.SYSTEM_UPDATE,
        title="? Notifica??o de Teste",
        message="Se voc? est? vendo isso, o sistema de notifica??es est? funcionando!",
        priority=NotificationPriority.MEDIUM,
    )
    
    # Enviar via WebSocket tamb?m
    if notification:
        await notification_ws_manager.send_notification(
            user_id=current_user.get("id") or current_user.get("_id"),
            notification_type=notification.type.value,
            title=notification.title,
            message=notification.message,
            notification_id=notification.id
        )
        return {"success": True, "notification_id": notification.id}
    return {"success": False, "message": "Notification type may be disabled"}

