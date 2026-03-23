"""
Database Module - MongoDB models, services, and initialization.

Includes:
- Models: Bot, Order, Position, Trade
- Services: BotService, OrderService, PositionService
- Initialization: Database connection and collection setup
"""

from app.db.models import (
    Bot, Order, Position, Trade,
    BotStatus, OrderStatus, OrderSide, OrderType, PositionStatus,
    BotConfig, OrderResponse, PositionResponse,
)

from app.db.bot_service import (
    BotService,
    init_bot_service,
    get_bot_service,
)

from app.db.order_service import (
    OrderService,
    init_order_service,
    get_order_service,
)

from app.db.position_service import (
    PositionService,
    init_position_service,
    get_position_service,
)

__all__ = [
    # Models
    "Bot", "Order", "Position", "Trade",
    "BotStatus", "OrderStatus", "OrderSide", "OrderType", "PositionStatus",
    "BotConfig", "OrderResponse", "PositionResponse",
    
    # Services
    "BotService", "OrderService", "PositionService",
    "init_bot_service", "get_bot_service",
    "init_order_service", "get_order_service",
    "init_position_service", "get_position_service",
]
