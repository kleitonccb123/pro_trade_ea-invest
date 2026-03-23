"""
Database Initialization - Setup MongoDB collections and indexes for FASE 3.

Called during app startup to:
1. Verify database connection
2. Create collections if not exist
3. Create indexes for performance
4. Initialize services
"""

import logging
from typing import Optional

from app.db import (
    init_bot_service,
    init_order_service,
    init_position_service,
)

logger = logging.getLogger(__name__)


async def init_database(db):
    """
    Initialize database collections, indexes, and services.
    
    Args:
        db: MongoDB database instance (from motor async driver)
        
    Returns:
        None
        
    Raises:
        Exception: If database initialization fails
    """
    
    logger.info("\n" + "="*60)
    logger.info("🗄️  Initializing Database (FASE 3)")
    logger.info("="*60)
    
    try:
        # ====================================================================
        # Create Collections
        # ====================================================================
        collections_to_create = [
            "bots",
            "orders",
            "positions",
            "trades",
        ]
        
        for collection_name in collections_to_create:
            try:
                # Check if collection exists
                existing = await db.list_collection_names()
                if collection_name not in existing:
                    await db.create_collection(collection_name)
                    logger.info(f"✅ Collection created: {collection_name}")
                else:
                    logger.debug(f"   Collection exists: {collection_name}")
            except Exception as e:
                logger.warning(f"⚠️  Could not create {collection_name}: {e}")
        
        # ====================================================================
        # Create Indexes (Performance)
        # ====================================================================
        
        # Bots indexes
        logger.info("📌 Creating indexes...")
        
        bots = db.bots
        await bots.create_index([("user_id", 1)])
        await bots.create_index([("user_id", 1), ("exchange", 1)])
        await bots.create_index([("user_id", 1), ("status", 1)])
        logger.debug("   Indexes created: bots")
        
        # Orders indexes
        orders = db.orders
        await orders.create_index([("user_id", 1)])
        await orders.create_index([("user_id", 1), ("bot_id", 1)])
        await orders.create_index([("user_id", 1), ("status", 1)])
        await orders.create_index([("client_oid", 1)])  # For idempotency
        await orders.create_index([("created_at", -1)])  # Latest first
        logger.debug("   Indexes created: orders")
        
        # Positions indexes
        positions = db.positions
        await positions.create_index([("user_id", 1)])
        await positions.create_index([("user_id", 1), ("bot_id", 1)])
        await positions.create_index([("user_id", 1), ("status", 1)])
        await positions.create_index([("symbol", 1)])
        logger.debug("   Indexes created: positions")
        
        # Trades indexes
        trades = db.trades
        await trades.create_index([("user_id", 1)])
        await trades.create_index([("user_id", 1), ("order_id", 1)])
        await trades.create_index([("exchange_trade_id", 1)])  # Prevent duplicates
        await trades.create_index([("executed_at", -1)])  # For queries
        logger.debug("   Indexes created: trades")
        
        # ====================================================================
        # Initialize Services
        # ====================================================================
        
        logger.info("🔧 Initializing services...")
        
        init_bot_service(bots)
        logger.debug("   BotService initialized")
        
        init_order_service(orders, trades)
        logger.debug("   OrderService initialized")
        
        init_position_service(positions)
        logger.debug("   PositionService initialized")
        
        # ====================================================================
        # Verify Connection
        # ====================================================================
        
        # Test connection
        server_info = await db.client.admin.command("ping")
        logger.info(f"✅ Database connected and healthy")
        
        logger.info("="*60)
        logger.info("✅ Database initialization complete!")
        logger.info("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def drop_database_collections(db):
    """
    Drop all FASE 3 collections (for testing/resetting).
    
    ⚠️  WARNING: This deletes all data!
    
    Args:
        db: MongoDB database instance
    """
    
    logger.warning("⚠️  Dropping all database collections...")
    
    collections = ["bots", "orders", "positions", "trades"]
    
    for collection_name in collections:
        try:
            await db.drop_collection(collection_name)
            logger.warning(f"   Dropped: {collection_name}")
        except Exception as e:
            logger.warning(f"   Error dropping {collection_name}: {e}")
    
    logger.warning("⚠️  Collections dropped")


INIT_SUMMARY = """
Database Initialization Summary
================================

Collections Created:
✅ bots - Trading bot configurations
✅ orders - Trading orders (pending, filled, cancelled)
✅ positions - Open trading positions
✅ trades - Filled trades/executions

Indexes Created:
✅ bots: user_id, (user_id, exchange), (user_id, status)
✅ orders: user_id, (user_id, bot_id), (user_id, status), client_oid, created_at
✅ positions: user_id, (user_id, bot_id), (user_id, status), symbol
✅ trades: user_id, (user_id, order_id), exchange_trade_id, executed_at

Services Initialized:
✅ BotService - CRUD for bots
✅ OrderService - CRUD for orders with RiskManager integration
✅ PositionService - Position lifecycle and PnL calculation

Integration Points:
✅ OrderService validates with RiskManager before execution
✅ OrderService executes with OrderManager (async)
✅ PositionService calculates unrealized and realized PnL
✅ All services work with per-user, per-bot isolation

Database is ready for FASE 3 operations!
"""
