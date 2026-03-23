"""
Notification Schemas - Pydantic schemas para valida??o
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, List

from pydantic import BaseModel, Field

from app.notifications.models import (
    NotificationType, 
    NotificationPriority, 
    NotificationChannel,
    PriceAlertCondition
)


# ============== NOTIFICATION SCHEMAS ==============

class NotificationBase(BaseModel):
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    title: str
    message: str
    data: Optional[dict] = None


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationOut(NotificationBase):
    id: int
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationList(BaseModel):
    notifications: List[NotificationOut]
    total: int
    unread_count: int


# Alias para compatibilidade
NotificationListResponse = NotificationList


class MarkReadRequest(BaseModel):
    notification_ids: List[int]


class MarkReadResponse(BaseModel):
    marked_count: int


# ============== PREFERENCE SCHEMAS ==============

class NotificationPreferenceBase(BaseModel):
    # Canais
    push_enabled: bool = True
    email_enabled: bool = True
    whatsapp_enabled: bool = False
    
    # Tipos
    price_alerts_enabled: bool = True
    bot_trades_enabled: bool = True
    bot_status_enabled: bool = True
    reports_enabled: bool = True
    system_updates_enabled: bool = True
    
    # Hor?rio de sil?ncio
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    
    # Resumos
    daily_summary_enabled: bool = True
    daily_summary_time: str = "08:00"
    weekly_summary_enabled: bool = True
    weekly_summary_day: int = 1
    
    # Som
    sound_enabled: bool = True
    vibration_enabled: bool = True


class NotificationPreferenceUpdate(NotificationPreferenceBase):
    pass


class NotificationPreferenceOut(NotificationPreferenceBase):
    id: int
    user_id: int
    whatsapp_number: Optional[str] = None
    whatsapp_verified: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PushSubscription(BaseModel):
    """Web Push subscription object"""
    endpoint: str
    keys: dict


class RegisterPushRequest(BaseModel):
    subscription: PushSubscription


class PushSubscriptionRequest(BaseModel):
    """Request body para registrar push subscription"""
    endpoint: str
    keys: dict
    expirationTime: Optional[datetime] = None


# ============== PRICE ALERT SCHEMAS ==============

class PriceAlertBase(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    condition: PriceAlertCondition
    target_price: float = Field(..., gt=0)
    percent_change: Optional[float] = None
    repeat: bool = False
    note: Optional[str] = Field(None, max_length=255)
    expires_at: Optional[datetime] = None


class PriceAlertCreate(PriceAlertBase):
    current_price: Optional[float] = None


class PriceAlertUpdate(BaseModel):
    target_price: Optional[float] = None
    is_active: Optional[bool] = None
    repeat: Optional[bool] = None
    note: Optional[str] = None
    expires_at: Optional[datetime] = None


class PriceAlertOut(PriceAlertBase):
    id: int
    user_id: int
    is_active: bool
    is_triggered: bool
    triggered_at: Optional[datetime] = None
    triggered_price: Optional[float] = None
    base_price: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PriceAlertList(BaseModel):
    alerts: List[PriceAlertOut]
    total: int


# ============== STATS ==============

class NotificationStats(BaseModel):
    total_notifications: int
    unread_count: int
    active_price_alerts: int
    triggered_today: int
