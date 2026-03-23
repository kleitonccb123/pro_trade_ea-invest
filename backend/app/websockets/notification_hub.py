"""
Unified Notification WebSocket Hub

Este m?dulo unifica todos os tipos de notifica??es em tempo real:
- Alertas de pre?o
- Eventos de sistema (bot started, stopped, error)
- Alertas de trading (execu??o de ordens)
- Notifica??es de afiliados (novo referral, comiss?o)
- Notifica??es educacionais (novo curso, certificado)

Uso:
1. Cliente conecta em ws://host/ws/notifications
2. Autentica com token
3. Recebe notifica??es em tempo real

Author: Crypto Trade Hub
"""

from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from enum import Enum
from dataclasses import dataclass, asdict
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Tipos de notifica??o."""
    # Pre?os
    PRICE_ALERT = "price_alert"
    PRICE_CHANGE = "price_change"
    
    # Trading
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    TRADE_EXECUTED = "trade_executed"
    
    # Bots
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BOT_ERROR = "bot_error"
    BOT_PROFIT = "bot_profit"
    BOT_LOSS = "bot_loss"
    
    # Sistema
    SYSTEM_INFO = "system_info"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_ERROR = "system_error"
    MAINTENANCE = "maintenance"
    
    # Afiliados
    NEW_REFERRAL = "new_referral"
    REFERRAL_CONVERTED = "referral_converted"
    COMMISSION_EARNED = "commission_earned"
    COMMISSION_PAID = "commission_paid"
    
    # Educa??o
    NEW_COURSE = "new_course"
    COURSE_COMPLETED = "course_completed"
    CERTIFICATE_ISSUED = "certificate_issued"
    
    # Licen?as
    LICENSE_EXPIRING = "license_expiring"
    LICENSE_EXPIRED = "license_expired"
    LICENSE_UPGRADED = "license_upgraded"


class NotificationPriority(str, Enum):
    """Prioridade da notifica??o."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """Estrutura de uma notifica??o."""
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.id is None:
            import uuid
            self.id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicion?rio."""
        result = asdict(self)
        result["type"] = self.type.value if isinstance(self.type, NotificationType) else self.type
        result["priority"] = self.priority.value if isinstance(self.priority, NotificationPriority) else self.priority
        return result
    
    def to_json(self) -> str:
        """Converte para JSON."""
        return json.dumps(self.to_dict())


class NotificationHub:
    """
    Hub central de notifica??es WebSocket.
    
    Gerencia conex?es de usu?rios e broadcast de notifica??es.
    """
    
    def __init__(self):
        # Map de user_id -> Set de WebSockets (um usu?rio pode ter m?ltiplas conex?es)
        self._connections: Dict[str, Set[WebSocket]] = {}
        
        # Map de WebSocket -> user_id
        self._websocket_users: Dict[WebSocket, str] = {}
        
        # Prefer?ncias de notifica??o por usu?rio (carregadas do DB)
        self._user_preferences: Dict[str, Dict[str, bool]] = {}
        
        # Lock para opera??es thread-safe
        self._lock = asyncio.Lock()
        
        # Estat?sticas
        self._stats = {
            "total_connections": 0,
            "total_notifications_sent": 0,
            "notifications_by_type": {},
        }
    
    async def connect(self, websocket: WebSocket, user_id: str) -> bool:
        """
        Registra uma nova conex?o WebSocket para um usu?rio.
        
        Args:
            websocket: Conex?o WebSocket
            user_id: ID do usu?rio
            
        Returns:
            True se conectado com sucesso
        """
        try:
            await websocket.accept()
            
            async with self._lock:
                if user_id not in self._connections:
                    self._connections[user_id] = set()
                
                self._connections[user_id].add(websocket)
                self._websocket_users[websocket] = user_id
                self._stats["total_connections"] += 1
            
            logger.info(f"? WebSocket conectado: user={user_id}")
            
            # Enviar mensagem de boas-vindas
            welcome = Notification(
                type=NotificationType.SYSTEM_INFO,
                title="Conectado",
                message="Notifica??es em tempo real ativadas",
                priority=NotificationPriority.LOW
            )
            await self._send_to_websocket(websocket, welcome)
            
            return True
            
        except Exception as e:
            logger.error(f"? Erro ao conectar WebSocket: {e}")
            return False
    
    async def disconnect(self, websocket: WebSocket):
        """Remove uma conex?o WebSocket."""
        async with self._lock:
            user_id = self._websocket_users.pop(websocket, None)
            
            if user_id and user_id in self._connections:
                self._connections[user_id].discard(websocket)
                
                # Remover user_id se n?o tem mais conex?es
                if not self._connections[user_id]:
                    del self._connections[user_id]
        
        logger.info(f"? WebSocket desconectado: user={user_id}")
    
    async def _send_to_websocket(self, websocket: WebSocket, notification: Notification) -> bool:
        """Envia notifica??o para um WebSocket espec?fico."""
        try:
            await websocket.send_text(notification.to_json())
            return True
        except Exception as e:
            logger.warning(f"?? Erro ao enviar notifica??o: {e}")
            return False
    
    async def send_to_user(self, user_id: str, notification: Notification) -> int:
        """
        Envia notifica??o para todas as conex?es de um usu?rio.
        
        Args:
            user_id: ID do usu?rio
            notification: Notifica??o a enviar
            
        Returns:
            N?mero de conex?es que receberam a notifica??o
        """
        sent_count = 0
        dead_connections = []
        
        async with self._lock:
            websockets = self._connections.get(user_id, set()).copy()
        
        for ws in websockets:
            try:
                success = await self._send_to_websocket(ws, notification)
                if success:
                    sent_count += 1
                else:
                    dead_connections.append(ws)
            except:
                dead_connections.append(ws)
        
        # Limpar conex?es mortas
        for ws in dead_connections:
            await self.disconnect(ws)
        
        # Estat?sticas
        if sent_count > 0:
            self._stats["total_notifications_sent"] += 1
            type_key = notification.type.value if isinstance(notification.type, NotificationType) else notification.type
            self._stats["notifications_by_type"][type_key] = \
                self._stats["notifications_by_type"].get(type_key, 0) + 1
        
        return sent_count
    
    async def broadcast(self, notification: Notification, user_ids: Optional[List[str]] = None) -> int:
        """
        Envia notifica??o para m?ltiplos usu?rios.
        
        Args:
            notification: Notifica??o a enviar
            user_ids: Lista de user_ids (None = todos)
            
        Returns:
            Total de conex?es que receberam
        """
        total_sent = 0
        
        if user_ids is None:
            user_ids = list(self._connections.keys())
        
        for user_id in user_ids:
            sent = await self.send_to_user(user_id, notification)
            total_sent += sent
        
        logger.info(f"? Broadcast enviado: {notification.type.value} -> {total_sent} conex?es")
        return total_sent
    
    async def broadcast_all(self, notification: Notification) -> int:
        """Envia notifica??o para todos os usu?rios conectados."""
        return await self.broadcast(notification, None)
    
    def get_connected_users(self) -> List[str]:
        """Retorna lista de user_ids conectados."""
        return list(self._connections.keys())
    
    def get_connection_count(self, user_id: str = None) -> int:
        """Retorna n?mero de conex?es."""
        if user_id:
            return len(self._connections.get(user_id, set()))
        return sum(len(conns) for conns in self._connections.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estat?sticas do hub."""
        return {
            **self._stats,
            "connected_users": len(self._connections),
            "active_connections": self.get_connection_count(),
        }


# Inst?ncia global do hub
notification_hub = NotificationHub()


# ==================== HELPER FUNCTIONS ====================

async def notify_price_alert(
    user_id: str,
    symbol: str,
    target_price: float,
    current_price: float,
    direction: str = "above"
) -> int:
    """Envia alerta de pre?o."""
    notification = Notification(
        type=NotificationType.PRICE_ALERT,
        title=f"Alerta de Pre?o: {symbol}",
        message=f"{symbol} atingiu ${current_price:.2f} ({direction} ${target_price:.2f})",
        priority=NotificationPriority.HIGH,
        data={
            "symbol": symbol,
            "target_price": target_price,
            "current_price": current_price,
            "direction": direction,
        }
    )
    return await notification_hub.send_to_user(user_id, notification)


async def notify_bot_event(
    user_id: str,
    bot_id: str,
    bot_name: str,
    event: str,
    details: str = None
) -> int:
    """Envia evento de bot."""
    event_map = {
        "started": NotificationType.BOT_STARTED,
        "stopped": NotificationType.BOT_STOPPED,
        "error": NotificationType.BOT_ERROR,
        "profit": NotificationType.BOT_PROFIT,
        "loss": NotificationType.BOT_LOSS,
    }
    
    notification = Notification(
        type=event_map.get(event, NotificationType.SYSTEM_INFO),
        title=f"Bot: {bot_name}",
        message=details or f"Bot {event}",
        priority=NotificationPriority.HIGH if event == "error" else NotificationPriority.NORMAL,
        data={
            "bot_id": bot_id,
            "bot_name": bot_name,
            "event": event,
        }
    )
    return await notification_hub.send_to_user(user_id, notification)


async def notify_trade(
    user_id: str,
    symbol: str,
    side: str,
    amount: float,
    price: float,
    order_id: str = None
) -> int:
    """Envia notifica??o de trade executado."""
    notification = Notification(
        type=NotificationType.TRADE_EXECUTED,
        title=f"Trade Executado: {symbol}",
        message=f"{side.upper()} {amount} {symbol} @ ${price:.2f}",
        priority=NotificationPriority.NORMAL,
        data={
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "order_id": order_id,
            "total": amount * price,
        }
    )
    return await notification_hub.send_to_user(user_id, notification)


async def notify_new_referral(
    user_id: str,
    referral_email: str
) -> int:
    """Envia notifica??o de novo referral."""
    notification = Notification(
        type=NotificationType.NEW_REFERRAL,
        title="Novo Indicado!",
        message=f"Voc? indicou {referral_email[:3]}***",
        priority=NotificationPriority.HIGH,
        data={"referral_email_masked": f"{referral_email[:3]}***"}
    )
    return await notification_hub.send_to_user(user_id, notification)


async def notify_commission(
    user_id: str,
    amount: float,
    referral_email: str = None
) -> int:
    """Envia notifica??o de comiss?o."""
    notification = Notification(
        type=NotificationType.COMMISSION_EARNED,
        title="Comiss?o Recebida!",
        message=f"Voc? ganhou ${amount:.2f} de comiss?o",
        priority=NotificationPriority.HIGH,
        data={"amount": amount}
    )
    return await notification_hub.send_to_user(user_id, notification)


async def notify_system(
    message: str,
    title: str = "Sistema",
    priority: NotificationPriority = NotificationPriority.NORMAL,
    user_ids: List[str] = None
) -> int:
    """Envia notifica??o do sistema."""
    notification = Notification(
        type=NotificationType.SYSTEM_INFO,
        title=title,
        message=message,
        priority=priority
    )
    return await notification_hub.broadcast(notification, user_ids)
