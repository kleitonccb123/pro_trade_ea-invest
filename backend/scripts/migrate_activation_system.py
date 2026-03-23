#!/usr/bin/env python3
"""
Migration Script: Add Activation Credits System

Dds os campos necess?rios para o novo sistema de cr?ditos de ativa??o:

1. Usu?rios:
   - activation_credits (baseado no plano)
   - activation_credits_used (inicialmente 0)

2. Bots:
   - is_active_slot (inicialmente False)
   - swap_count (inicialmente 0)
   - swap_history (lista vazia)
   - Atualiza last_updated timestamp

Uso:
    python scripts/migrate_activation_system.py [--dry-run]

Flags:
    --dry-run: Simula migra??o sem fazer mudan?as permanentes
"""

import asyncio
import argparse
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Plan credits mapping
PLAN_CREDITS = {
    "starter": 1,
    "pro": 5,
    "premium": 15,
    "enterprise": 100,
}


async def migrate_users(db: AsyncIOMotorDatabase, dry_run: bool = False):
    """Adiciona campos de cr?dito aos usu?rios existentes."""
    
    logger.info("=" * 60)
    logger.info("MIGRATING USERS: Adding activation credits...")
    logger.info("=" * 60)
    
    users_col = db["users"]
    
    # Encontrar usu?rios sem o campo activation_credits
    query = {"activation_credits": {"$exists": False}}
    users_without_credits = await users_col.count_documents(query)
    
    logger.info(f"Found {users_without_credits} users without activation_credits field")
    
    if users_without_credits == 0:
        logger.info("? All users already have activation_credits field")
        return 0
    
    # Processando usu?rios em lotes
    batch_size = 100
    processed = 0
    updated = 0
    
    async for user in users_col.find(query).batch_size(batch_size):
        user_id = user.get("_id")
        email = user.get("email", "unknown")
        plan = user.get("plan", "starter")
        
        # Obter cr?ditos baseado no plano
        credits = PLAN_CREDITS.get(plan, 1)
        
        # Preparar documento de atualiza??o
        update_doc = {
            "$set": {
                "activation_credits": credits,
                "activation_credits_used": 0,
                "updated_at": datetime.utcnow(),
            }
        }
        
        if dry_run:
            logger.info(
                f"  [DRY-RUN] User {email}: {plan.upper()} = {credits} credits"
            )
        else:
            result = await users_col.update_one(
                {"_id": user_id},
                update_doc
            )
            if result.modified_count > 0:
                updated += 1
                logger.info(
                    f"  ? User {email}: {plan.upper()} = {credits} credits"
                )
            else:
                logger.warning(f"  ?? User {email}: Update failed or no changes")
        
        processed += 1
        
        # Progress
        if processed % batch_size == 0:
            logger.info(f"  ... Processed {processed} users")
    
    logger.info(f"? Users migration complete: {updated}/{processed} updated")
    return updated


async def migrate_bots(db: AsyncIOMotorDatabase, dry_run: bool = False):
    """Adiciona campos de swap e activation aos bots existentes."""
    
    logger.info("\n" + "=" * 60)
    logger.info("MIGRATING BOTS: Adding swap history and slot fields...")
    logger.info("=" * 60)
    
    bots_col = db["bots"]
    
    # Encontrar bots sem os campos necess?rios
    query = {
        "$or": [
            {"is_active_slot": {"$exists": False}},
            {"swap_count": {"$exists": False}},
            {"swap_history": {"$exists": False}},
        ]
    }
    
    bots_needing_migration = await bots_col.count_documents(query)
    logger.info(f"Found {bots_needing_migration} bots needing migration")
    
    if bots_needing_migration == 0:
        logger.info("? All bots already have required fields")
        return 0
    
    # Processando bots em lotes
    batch_size = 100
    processed = 0
    updated = 0
    
    async for bot in bots_col.find(query).batch_size(batch_size):
        bot_id = bot.get("_id")
        name = bot.get("name", "unknown")
        user_id = bot.get("user_id", "unknown")
        
        # Preparar documento de atualiza??o
        update_fields = {}
        
        if "is_active_slot" not in bot:
            update_fields["is_active_slot"] = False
        
        if "swap_count" not in bot:
            update_fields["swap_count"] = 0
        
        if "swap_history" not in bot:
            update_fields["swap_history"] = []
        
        if "activation_credits_used" not in bot:
            update_fields["activation_credits_used"] = 0
        
        update_fields["last_updated"] = datetime.utcnow()
        
        update_doc = {"$set": update_fields}
        
        if dry_run:
            logger.info(f"  [DRY-RUN] Bot {name}: Adding {len(update_fields)} fields")
        else:
            result = await bots_col.update_one(
                {"_id": bot_id},
                update_doc
            )
            if result.modified_count > 0:
                updated += 1
                logger.info(f"  ? Bot {name}: Updated with {len(update_fields)} fields")
            else:
                logger.warning(f"  ?? Bot {name}: Update failed or no changes")
        
        processed += 1
        
        # Progress
        if processed % batch_size == 0:
            logger.info(f"  ... Processed {processed} bots")
    
    logger.info(f"? Bots migration complete: {updated}/{processed} updated")
    return updated


async def main():
    """Main migration runner."""
    
    parser = argparse.ArgumentParser(
        description="Migrate to Activation Credits system"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without making changes"
    )
    parser.add_argument(
        "--db-url",
        default="mongodb://localhost:27017",
        help="MongoDB connection URL"
    )
    parser.add_argument(
        "--db-name",
        default="crypto_trade_hub",
        help="Database name"
    )
    
    args = parser.parse_args()
    
    # Conectar ao MongoDB
    logger.info(f"Connecting to MongoDB: {args.db_url}")
    client = AsyncIOMotorClient(args.db_url)
    db = client[args.db_name]
    
    try:
        if args.dry_run:
            logger.warning("??  DRY-RUN MODE: No changes will be made")
        
        # Executar migra??es
        users_updated = await migrate_users(db, dry_run=args.dry_run)
        bots_updated = await migrate_bots(db, dry_run=args.dry_run)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Users updated: {users_updated}")
        logger.info(f"Bots updated: {bots_updated}")
        
        if args.dry_run:
            logger.warning("??  This was a DRY-RUN. No changes were made.")
            logger.warning("Run without --dry-run to apply changes")
        else:
            logger.info("? Migration completed successfully!")
        
        logger.info("=" * 60)
        
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
