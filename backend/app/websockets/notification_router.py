"""
WebSocket Notification Router

Endpoints:
- WS /ws/notifications - Hub unificado de notifica??es

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError

from app.core.config import settings
from app.websockets.notification_hub import notification_hub, Notification, NotificationType, NotificationPriority

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket Notifications"])


async def authenticate_websocket(token: str) -> dict | None:
    """Autentica token JWT do WebSocket."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.algorithm]
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
        return {"user_id": user_id, "email": payload.get("email")}
    except JWTError as e:
        logger.warning(f"?? Token inv?lido: {e}")
        return None


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(None)
):
    """
    WebSocket endpoint para notifica??es em tempo real.
    
    Conex?o:
    - ws://host/ws/notifications?token=JWT_TOKEN
    
    Mensagens recebidas (cliente -> servidor):
    - {"type": "ping"} - Keepalive
    - {"type": "subscribe", "topics": ["price_alerts", "bots"]} - Inscrever em t?picos
    - {"type": "unsubscribe", "topics": ["price_alerts"]} - Desinscrever de t?picos
    - {"type": "ack", "notification_id": "xxx"} - Confirmar recebimento
    
    Mensagens enviadas (servidor -> cliente):
    - Notifica??es em formato JSON (ver notification_hub.Notification)
    """
    # Autenticar
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return
    
    user_data = await authenticate_websocket(token)
    if not user_data:
        await websocket.close(code=4002, reason="Invalid token")
        return
    
    user_id = user_data["user_id"]
    
    # Conectar ao hub
    connected = await notification_hub.connect(websocket, user_id)
    if not connected:
        return
    
    try:
        # Loop de mensagens
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    # Responder com pong
                    await websocket.send_json({"type": "pong"})
                
                elif msg_type == "subscribe":
                    # Inscrever em t?picos espec?ficos
                    topics = message.get("topics", [])
                    logger.info(f"? User {user_id} subscribed to: {topics}")
                    await websocket.send_json({
                        "type": "subscribed",
                        "topics": topics
                    })
                
                elif msg_type == "unsubscribe":
                    topics = message.get("topics", [])
                    logger.info(f"? User {user_id} unsubscribed from: {topics}")
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "topics": topics
                    })
                
                elif msg_type == "ack":
                    # Confirma??o de recebimento
                    notification_id = message.get("notification_id")
                    logger.debug(f"? Notification {notification_id} acknowledged by {user_id}")
                
                else:
                    logger.warning(f"?? Unknown message type: {msg_type}")
                    
            except json.JSONDecodeError:
                logger.warning(f"?? Invalid JSON from {user_id}")
                
    except WebSocketDisconnect:
        logger.info(f"? WebSocket disconnected: {user_id}")
    except Exception as e:
        logger.error(f"? WebSocket error: {e}")
    finally:
        await notification_hub.disconnect(websocket)


@router.get("/api/notifications/stats")
async def get_notification_stats():
    """
    Retorna estat?sticas do hub de notifica??es.
    """
    return notification_hub.get_stats()


@router.get("/api/notifications/connected")
async def get_connected_users():
    """
    Retorna lista de usu?rios conectados (admin only).
    """
    users = notification_hub.get_connected_users()
    return {
        "connected_users": len(users),
        "user_ids": users[:10],  # Limitar por privacidade
    }
