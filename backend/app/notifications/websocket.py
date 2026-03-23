"""
WebSocket Manager para notifica??es em tempo real
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Set, Optional
from datetime import datetime
import json

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class NotificationWebSocketManager:
    """Gerencia conex?es WebSocket para notifica??es em tempo real"""
    
    def __init__(self):
        # user_id -> set of websockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Aceita conex?o e registra para um usu?rio"""
        await websocket.accept()
        
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        
        logger.info(f"WebSocket connected for user {user_id}. Total connections: {len(self.active_connections.get(user_id, set()))}")
        
        # Enviar mensagem de confirma??o
        await self._send_json(websocket, {
            "type": "connected",
            "message": "Notifica??es em tempo real ativas",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove conex?o"""
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[dict] = None,
        notification_id: Optional[int] = None
    ):
        """Envia notifica??o para todas as conex?es de um usu?rio"""
        if user_id not in self.active_connections:
            logger.debug(f"No active connections for user {user_id}")
            return
        
        payload = {
            "type": "notification",
            "notification": {
                "id": notification_id,
                "type": notification_type,
                "title": title,
                "message": message,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
        
        disconnected = set()
        
        async with self._lock:
            connections = self.active_connections.get(user_id, set()).copy()
        
        for websocket in connections:
            try:
                await self._send_json(websocket, payload)
            except Exception as e:
                logger.warning(f"Failed to send to websocket: {e}")
                disconnected.add(websocket)
        
        # Remove conex?es falhas
        if disconnected:
            async with self._lock:
                if user_id in self.active_connections:
                    self.active_connections[user_id] -= disconnected
    
    async def broadcast_to_user(self, user_id: int, message: dict):
        """Broadcast gen?rico para um usu?rio"""
        if user_id not in self.active_connections:
            return
        
        disconnected = set()
        
        async with self._lock:
            connections = self.active_connections.get(user_id, set()).copy()
        
        for websocket in connections:
            try:
                await self._send_json(websocket, message)
            except Exception:
                disconnected.add(websocket)
        
        if disconnected:
            async with self._lock:
                if user_id in self.active_connections:
                    self.active_connections[user_id] -= disconnected
    
    async def send_unread_count(self, user_id: int, count: int):
        """Envia atualiza??o de contagem de n?o lidas"""
        await self.broadcast_to_user(user_id, {
            "type": "unread_count",
            "count": count,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _send_json(self, websocket: WebSocket, data: dict):
        """Envia dados JSON pelo websocket"""
        await websocket.send_json(data)
    
    def get_connection_count(self, user_id: Optional[int] = None) -> int:
        """Retorna n?mero de conex?es ativas"""
        if user_id is not None:
            return len(self.active_connections.get(user_id, set()))
        return sum(len(conns) for conns in self.active_connections.values())
    
    def get_connected_users(self) -> Set[int]:
        """Retorna IDs dos usu?rios conectados"""
        return set(self.active_connections.keys())


# Singleton global
notification_ws_manager = NotificationWebSocketManager()
