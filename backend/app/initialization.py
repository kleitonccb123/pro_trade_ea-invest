"""
Application Initialization - Setup security, routers, middleware, and database.

Called from main.py to initialize:
1. Credential encryption (FASE 2)
2. Credential store (FASE 2)
3. API routers (FASE 2)
4. Request/response middleware (FASE 2)
5. Database collections and services (FASE 3)
"""

import logging
import os
from fastapi import FastAPI

from app.security import (
    init_credential_encryption,
    init_credential_store,
    LogSanitizer,
)
from app.routers import (
    exchanges_router,
    bots_router,
    orders_router,
)
from app.middleware import setup_middleware
from app.db.database_init import init_database, INIT_SUMMARY

logger = logging.getLogger(__name__)


def init_security(app: FastAPI):
    """
    Initialize security components.
    
    Args:
        app: FastAPI application instance
    """
    logger.info("Initializing security components...")
    
    # Initialize credential encryption
    try:
        encryption_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
        if not encryption_key:
            # Generate key for development
            from app.security.credential_encryption import CredentialEncryption
            encryption_key = CredentialEncryption.generate_key()
            logger.warning(
                f"⚠️  CREDENTIAL_ENCRYPTION_KEY not set. Using generated key:\n"
                f"CREDENTIAL_ENCRYPTION_KEY={encryption_key}\n"
                f"Set this in .env for production!"
            )
        
        init_credential_encryption(encryption_key)
        logger.info("✅ Credential encryption initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize credential encryption: {e}")
        raise


def init_database_components(app: FastAPI, db):
    """
    Initialize database-dependent components.
    
    Args:
        app: FastAPI application instance
        db: MongoDB database instance
    """
    logger.info("Initializing database components...")
    
    try:
        # Initialize credential store with database
        credential_collection = db.user_exchange_credentials
        init_credential_store(credential_collection)
        
        # Create indexes for efficient queries
        credential_collection.create_index([("user_id", 1), ("exchange", 1)], unique=True)
        credential_collection.create_index([("user_id", 1)])
        
        logger.info("✅ Database components initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database components: {e}")
        raise


def register_routers(app: FastAPI):
    """
    Register API routers.
    
    Args:
        app: FastAPI application instance
    """
    logger.info("Registering API routers...")
    
    # Exchange endpoints
    app.include_router(exchanges_router, prefix="/api", tags=["exchanges"])
    
    # Bot management endpoints
    app.include_router(bots_router, prefix="/api", tags=["bots"])
    
    # Order management endpoints
    app.include_router(orders_router, prefix="/api", tags=["orders"])
    
    logger.info("✅ API routers registered")


def setup_health_check(app: FastAPI):
    """
    Setup health check endpoint.
    
    Args:
        app: FastAPI application instance
    """
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint for load balancers."""
        return {
            "status": "ok",
            "service": "crypto-trade-hub-api",
            "version": "2.0.0"  # FASE 2
        }
    
    logger.info("✅ Health check endpoint configured")


def init_fase_2(app: FastAPI, db=None):
    """
    Complete FASE 2 initialization.
    
    Initializes:
    1. Security (encryption, sanitization)
    2. Database components (credential store)
    3. Middleware (auth, logging, error handling)
    4. API routers (exchanges, bots, orders)
    5. Health checks
    
    Args:
        app: FastAPI application instance
        db: MongoDB database instance (optional)
    
    Usage:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> from app.initialization import init_fase_2
        >>> # After connecting to DB:
        >>> init_fase_2(app, db)
    """
    
    logger.info("\n" + "="*60)
    logger.info("🚀 INITIALIZING FASE 2 - Security & FastAPI Integration")
    logger.info("="*60)
    
    try:
        # Step 1: Initialize security
        init_security(app)
        
        # Step 2: Initialize database components (if db provided)
        if db:
            init_database_components(app, db)
        else:
            logger.warning("⚠️  Database not provided - credential store will fail at runtime")
        
        # Step 3: Setup middleware
        setup_middleware(app)
        
        # Step 4: Register routers
        register_routers(app)
        
        # Step 5: Setup health check
        setup_health_check(app)
        
        logger.info("="*60)
        logger.info("✅ FASE 2 initialization complete!")
        logger.info("="*60 + "\n")
        
        return app
        
    except Exception as e:
        logger.error(f"❌ FASE 2 initialization failed: {LogSanitizer.sanitize(str(e))}")
        raise


async def init_fase_3(app: FastAPI, db):
    """
    Complete FASE 3 initialization (Database & Services).
    
    Must be called AFTER init_fase_2.
    
    Initializes:
    1. MongoDB collections and indexes
    2. Database services (BotService, OrderService, PositionService)
    3. Integration with RiskManager and OrderManager
    
    Args:
        app: FastAPI application instance (already initialized with init_fase_2)
        db: MongoDB database instance (required)
        
    Usage:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> from app.initialization import init_fase_2, init_fase_3
        >>> 
        >>> # First FASE 2:
        >>> init_fase_2(app, db)
        >>> 
        >>> # Then FASE 3 (async, call at startup):
        >>> await init_fase_3(app, db)
    """
    
    logger.info("\n" + "="*60)
    logger.info("🚀 INITIALIZING FASE 3 - Database & Services")
    logger.info("="*60)
    
    try:
        # Initialize database collections, indexes, and services
        await init_database(db)
        
        logger.info("="*60)
        logger.info("✅ FASE 3 initialization complete!")
        logger.info(INIT_SUMMARY)
        logger.info("="*60 + "\n")
        
        return app
        
    except Exception as e:
        logger.error(f"❌ FASE 3 initialization failed: {LogSanitizer.sanitize(str(e))}")
        raise


async def init_complete(app: FastAPI, db):
    """
    Initialize all FASE components (FASE 1+2+3).
    
    Convenience function that calls:
    1. init_fase_2 (security, routers, middleware)
    2. init_fase_3 (database, services)
    
    Args:
        app: FastAPI application instance
        db: MongoDB database instance
        
    Usage:
        >>> from fastapi import FastAPI
        >>> from app.initialization import init_complete
        >>> 
        >>> app = FastAPI()
        >>> # At startup:
        >>> await init_complete(app, db)
    """
    init_fase_2(app, db)
    await init_fase_3(app, db)
    return app


# Summary of implemented components
FASE_2_SUMMARY = """
FASE 2 Implementation Summary
============================

Security Features:
✅ LogSanitizer - Remove API keys, secrets, tokens from logs
✅ CredentialEncryption - Fernet-based encryption for credentials
✅ CredentialStore - Per-user, per-exchange credential storage with encryption

API Routers:
✅ /api/exchanges/* - Setup and manage exchange credentials
   - POST /api/exchanges/setup - Store encrypted credentials
   - GET /api/exchanges - List connected exchanges
   - POST /api/exchanges/verify - Verify credentials work
   - DELETE /api/exchanges/{exchange} - Remove credentials

✅ /api/bots/* - Trading bot management (stubs)
   - POST /api/bots - Create bot
   - GET /api/bots - List bots
   - POST /api/bots/{bot_id}/start - Start bot
   - POST /api/bots/{bot_id}/stop - Stop bot

✅ /api/orders/* - Order management (stubs)
   - POST /api/orders/place - Place order with risk validation
   - GET /api/orders - List orders
   - POST /api/orders/{order_id}/cancel - Cancel order
   - GET /api/positions - List open positions

Middleware:
✅ AuthorizationMiddleware - Validate Bearer tokens
✅ RequestLoggingMiddleware - Log requests with sanitization
✅ ErrorHandlingMiddleware - Centralized error handling
✅ CORS support

Database:
✅ MongoDB indexes on user_exchange_credentials for efficient queries
✅ StoredCredential model for type-safe database operations

Next Steps (FASE 3):
⏳ Database models for bots, orders, positions
⏳ Integration of OrderManager and RiskManager from FASE 1
⏳ WebSocket streaming integration
⏳ Authentication and JWT token validation
"""
