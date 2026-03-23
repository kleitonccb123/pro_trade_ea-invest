"""
API Routers - FastAPI route definitions.

Modules:
- exchanges: Exchange credential setup and verification
- bots: Trading bot management
- orders: Order placement and tracking
- auth: User authentication (TODO)
"""

from app.routers.exchanges import router as exchanges_router
from app.routers.bots import router as bots_router
from app.routers.orders import router as orders_router

__all__ = [
    "exchanges_router",
    "bots_router",
    "orders_router",
]
