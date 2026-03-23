from __future__ import annotations
import enum

class NotificationType(str, enum.Enum):
    PRICE_ALERT = "price_alert"
    BOT_TRADE = "bot_trade"
    BOT_CREATED = "bot_created"
    BOT_ERROR = "bot_error"
    STRATEGY_TRADE = "strategy_trade"
    AFFILIATE_COMMISSION = "affiliate_commission"

class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"

class NotificationPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PriceAlertCondition(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"
    EQUALS = "equals"

# Placeholder classes - TODO: Convert to MongoDB schemas
class Notification:
    pass

class NotificationPreference:
    pass

class PriceAlert:
    pass

# TODO: Migrar para MongoDB schemas
