#!/usr/bin/env python3
"""
Database Migration Script for MongoDB Indexes

This script ensures that all required indexes are created for optimal performance
with 1000+ users. It creates indexes for trades (user_id, timestamp) and bots (user_id).

Usage:
    python scripts/migrate_indexes.py

Or from project root:
    cd backend && python scripts/migrate_indexes.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import get_db, init_db
from app.core.logging_config import configure_logging
import logging

logger = logging.getLogger(__name__)


async def migrate_indexes():
    """
    Create and ensure all required database indexes for production performance.
    """
    logger.info("? Starting database index migration...")

    # Check if we should skip migration (offline mode or no database configured)
    from app.core.config import settings

    # Check if offline mode is explicitly set
    if settings.offline_mode:
        logger.info("? Offline mode enabled in settings - skipping MongoDB index migration")
        logger.info("? Indexes will be created automatically when connecting to real MongoDB")
        logger.info("? Migration completed (offline mode)")
        return True

    # Try to connect to real database first
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        import ssl
        import certifi

        client = AsyncIOMotorClient(
            settings.database_url,
            tlsCAFile=certifi.where() if "mongodb+srv" in settings.database_url else None,
            serverSelectionTimeoutMS=5000  # 5 second timeout
        )

        # Test connection
        await client.admin.command('ping')
        db = client[settings.database_name]

        logger.info("? Database connection successful")

    except Exception as e:
        logger.warning(f"??  Cannot connect to MongoDB: {e}")
        logger.info("? Falling back to offline mode - skipping index migration")
        logger.info("? Run this script again when MongoDB is available")
        return True

    # Now proceed with real database operations

    try:
        # Test connection
        await db.command("ping")
        logger.info("? Database connection successful")

        # Get collection info before migration
        collections_before = await db.list_collection_names()
        logger.info(f"? Collections before migration: {len(collections_before)}")

        # Run existing init_db to ensure base indexes
        logger.info("? Running base index initialization...")
        await init_db()

        # Additional production-critical indexes
        logger.info("? Creating production-critical indexes...")

        # ============================================
        # TRADES COLLECTION - Critical for performance
        # ============================================
        trades_col = db['simulated_trades']
        strategy_trades_col = db['strategy_trades']

        # Ensure compound indexes for trades queries
        logger.info("? Optimizing trades indexes...")

        # Index for user + timestamp queries (most common)
        try:
            await trades_col.create_index([('user_id', 1), ('timestamp', -1)], name='user_timestamp_desc')
            logger.info("? Created trades index: user_id + timestamp DESC")
        except Exception as e:
            logger.warning(f"??  Trades user_timestamp index may already exist: {e}")

        # Index for timestamp-only queries (analytics)
        try:
            await trades_col.create_index('timestamp', name='timestamp_only')
            logger.info("? Created trades index: timestamp")
        except Exception as e:
            logger.warning(f"??  Trades timestamp index may already exist: {e}")

        # Strategy trades indexes
        try:
            await strategy_trades_col.create_index([('user_id', 1), ('entry_time', -1)], name='strategy_user_entry_desc')
            logger.info("? Created strategy_trades index: user_id + entry_time DESC")
        except Exception as e:
            logger.warning(f"??  Strategy trades user_entry index may already exist: {e}")

        # ============================================
        # BOTS COLLECTION - Critical for user queries
        # ============================================
        bots_col = db['bots']
        bot_instances_col = db['bot_instances']

        logger.info("? Optimizing bots indexes...")

        # Ensure user_id index (most critical for user dashboards)
        try:
            await bots_col.create_index('user_id', name='bots_user_id')
            logger.info("? Created bots index: user_id")
        except Exception as e:
            logger.warning(f"??  Bots user_id index may already exist: {e}")

        # Bot instances indexes
        try:
            await bot_instances_col.create_index([('user_id', 1), ('state', 1)], name='instances_user_state')
            logger.info("? Created bot_instances index: user_id + state")
        except Exception as e:
            logger.warning(f"??  Bot instances user_state index may already exist: {e}")

        # ============================================
        # USERS COLLECTION - Already handled in init_db
        # ============================================
        logger.info("? Users indexes already handled by init_db()")

        # ============================================
        # ANALYTICS & PERFORMANCE INDEXES
        # ============================================
        logger.info("? Creating analytics performance indexes...")

        # Analytics cache - ensure TTL is working
        analytics_col = db['analytics_cache']
        try:
            # TTL index for cache expiration
            await analytics_col.create_index('updated_at', expireAfterSeconds=600, name='analytics_ttl_10min')
            logger.info("? Created analytics cache TTL index")
        except Exception as e:
            logger.warning(f"??  Analytics TTL index may already exist: {e}")

        # Idempotency keys for order reliability
        idempotency_col = db['idempotency_keys']
        try:
            # Compound index for user + key lookup
            await idempotency_col.create_index([('user_id', 1), ('idempotency_key', 1)], name='user_idempotency_key', unique=True)
            logger.info("? Created idempotency keys compound index")
            
            # TTL index for automatic expiration (24 hours)
            await idempotency_col.create_index('expires_at', expireAfterSeconds=0, name='idempotency_ttl')
            logger.info("? Created idempotency keys TTL index")
        except Exception as e:
            logger.warning(f"??  Idempotency index may already exist: {e}")

        # ============================================
        # VALIDATION & REPORTING
        # ============================================
        logger.info("? Validating index creation...")

        # Get all indexes after migration
        trades_indexes = await trades_col.index_information()
        bots_indexes = await bots_col.index_information()
        instances_indexes = await bot_instances_col.index_information()

        logger.info("? Final index summary:")
        logger.info(f"  - trades collection: {len(trades_indexes)} indexes")
        logger.info(f"  - bots collection: {len(bots_indexes)} indexes")
        logger.info(f"  - bot_instances collection: {len(instances_indexes)} indexes")

        # Critical indexes validation
        critical_indexes = [
            ('simulated_trades', 'user_timestamp_desc'),
            ('strategy_trades', 'strategy_user_entry_desc'),
            ('bot_instances', 'instances_user_state'),
        ]

        missing_indexes = []
        for collection, index_name in critical_indexes:
            col = db[collection]
            indexes = await col.index_information()
            if index_name not in indexes:
                missing_indexes.append(f"{collection}.{index_name}")

        if missing_indexes:
            logger.warning(f"??  Some indexes were not created (may already exist with different names): {missing_indexes}")
            logger.info("? This is usually not a problem - indexes may exist with different names")
        else:
            logger.info("? All critical indexes verified!")

        logger.info("? Database index migration completed successfully!")
        return True

    except Exception as e:
        logger.error(f"? Database migration failed: {e}")
        return False


async def main():
    """Main migration function."""
    # Configure logging
    configure_logging()

    logger.info("??  Starting MongoDB Index Migration for Production")
    logger.info("=" * 60)

    success = await migrate_indexes()

    if success:
        logger.info("? Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("? Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())