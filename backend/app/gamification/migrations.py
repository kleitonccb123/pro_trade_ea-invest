"""
Gamification Migrations - Garantir integridade e performance do banco de dados

Responsabilidades:
- Criar/validar collection `game_profiles`
- Inicializar índices para performance (trade_points DESC, user_id UNIQUE)
- Executar ao startup da aplicação
"""

import logging
from app.core.database import get_db

logger = logging.getLogger(__name__)


class GameificationMigrations:
    """Gerenciador de migrações do sistema de gamificação"""
    
    @staticmethod
    async def run_all():
        """
        Executa todas as migrações necessárias.
        Deve ser chamado no evento de startup da aplicação (main.py).
        """
        logger.info("=" * 80)
        logger.info("🚀 INICIANDO MIGRAÇÕES DE GAMIFICAÇÃO")
        logger.info("=" * 80)
        
        try:
            await GameificationMigrations.ensure_collection()
            await GameificationMigrations.ensure_indexes()
            
            logger.info("=" * 80)
            logger.info("✅ MIGRAÇÕES COMPLETADAS COM SUCESSO")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ ERRO CRÍTICO NA MIGRAÇÃO: {str(e)}")
            raise
    
    @staticmethod
    async def ensure_collection():
        """
        Garante que a collection `game_profiles` existe.
        Cria se não existir.
        """
        db = get_db()
        
        try:
            # Lista as collections existentes
            existing_collections = await db.list_collection_names()
            
            if "game_profiles" in existing_collections:
                logger.info("✓ Collection 'game_profiles' já existe")
                return
            
            # Cria a collection com validação de schema
            await db.create_collection(
                "game_profiles",
                validator={
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": ["user_id", "trade_points", "level"],
                        "properties": {
                            "_id": {"bsonType": "objectId"},
                            "user_id": {
                                "bsonType": "string",
                                "description": "ID do usuário (único)"
                            },
                            "trade_points": {
                                "bsonType": "int",
                                "minimum": 0,
                                "description": "Saldo de pontos de trading"
                            },
                            "level": {
                                "bsonType": "int",
                                "minimum": 1,
                                "maximum": 100,
                                "description": "Nível do usuário"
                            },
                            "xp": {
                                "bsonType": "int",
                                "minimum": 0,
                                "description": "Experiência acumulada"
                            },
                            "unlocked_robots": {
                                "bsonType": "array",
                                "items": {"bsonType": "string"},
                                "description": "Lista de robôs desbloqueados"
                            },
                            "lifetime_profit": {
                                "bsonType": "double",
                                "description": "Lucro total acumulado"
                            },
                            "last_daily_chest_opened": {
                                "bsonType": ["date", "null"],
                                "description": "Último baú aberto"
                            },
                            "streak_count": {
                                "bsonType": "int",
                                "minimum": 0,
                                "description": "Dias consecutivos de baú aberto"
                            },
                            "created_at": {
                                "bsonType": "date",
                                "description": "Data de criação do perfil"
                            },
                            "updated_at": {
                                "bsonType": "date",
                                "description": "Data da última atualização"
                            }
                        }
                    }
                }
            )
            
            logger.info("✅ Collection 'game_profiles' criada com schema validation")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao criar collection (pode já existir): {str(e)}")
    
    @staticmethod
    async def ensure_indexes():
        """
        Cria os índices necessários para performance.
        
        Índices:
        1. user_id UNIQUE - Evitar perfis duplicados
        2. trade_points DESC - Optimizar queries de leaderboard
        """
        db = get_db()
        collection = db["game_profiles"]
        
        try:
            # Índice 1: user_id ÚNICO (previne duplicatas)
            await collection.create_index(
                "user_id",
                unique=True,
                name="idx_user_id_unique",
                background=True,
                sparse=True
            )
            logger.info("✅ Índice criado: idx_user_id_unique (UNIQUE)")
            
            # Índice 2: trade_points DESC (leaderboard performance)
            await collection.create_index(
                [("trade_points", -1)],
                name="idx_trade_points_desc",
                background=True
            )
            logger.info("✅ Índice criado: idx_trade_points_desc (DESC)")
            
            # Índice 3: created_at DESC (para queries de usuários recentes)
            await collection.create_index(
                [("created_at", -1)],
                name="idx_created_at_desc",
                background=True
            )
            logger.info("✅ Índice criado: idx_created_at_desc (DESC)")
            
            # Índice 4: level DESC (para ranking por nível)
            await collection.create_index(
                [("level", -1)],
                name="idx_level_desc",
                background=True
            )
            logger.info("✅ Índice criado: idx_level_desc (DESC)")
            
            # Lista todos os índices existentes
            indexes = await collection.list_indexes()
            index_count = 0
            logger.info("\n📊 ÍNDICES ATIVOS NA COLLECTION 'game_profiles':")
            
            async for index in indexes:
                index_count += 1
                index_name = index.get("name", "unknown")
                index_keys = index.get("key", [])
                is_unique = index.get("unique", False)
                logger.info(f"   #{index_count}: {index_name} - {index_keys} {'[UNIQUE]' if is_unique else ''}")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao criar índices (podem já existir): {str(e)}")


async def run_migrations():
    """Função auxiliar para executar migrações"""
    await GameificationMigrations.run_all()


async def create_ranking_indexes() -> None:
    """
    Create indexes required by the real trading ranking (DOC_06 §8).

    - bot_trades: compound index for aggregation pipeline (status + exit_timestamp + user_id)
    - bot_trades: compound index for instance queries
    - leaderboard_cache: unique index on period_days
    """
    db = get_db()
    try:
        from pymongo import ASCENDING, DESCENDING

        # Fast aggregation pipeline filter
        await db["bot_trades"].create_index(
            [("status", ASCENDING), ("exit_timestamp", DESCENDING), ("user_id", ASCENDING)],
            name="ranking_pipeline_filter",
            background=True,
        )
        # Instance-based queries
        await db["bot_trades"].create_index(
            [("bot_instance_id", ASCENDING), ("status", ASCENDING)],
            name="ranking_instance_status",
            background=True,
        )
        # leaderboard_cache: unique per period
        await db["leaderboard_cache"].create_index(
            [("period_days", ASCENDING)],
            name="leaderboard_period_unique",
            unique=True,
            background=True,
        )
        logger.info("Ranking indexes created (DOC_06)")
    except Exception as exc:
        logger.warning("Ranking index creation warning (may already exist): %s", exc)
