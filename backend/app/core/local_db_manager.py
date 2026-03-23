"""
Singleton manager para LocalUserDatabase
Evita circular imports e garante uma única instância
"""

import logging
from typing import Optional
from app.core.local_db import LocalUserDatabase

logger = logging.getLogger(__name__)

# Singleton instance
_local_db_instance: Optional[LocalUserDatabase] = None


def get_local_db() -> LocalUserDatabase:
    """
    Obtém a instância global do LocalUserDatabase.
    
    Se não estiver inicializada, retorna None e loga erro.
    Isso será inicializado em app.main na startup.
    """
    global _local_db_instance
    
    if _local_db_instance is None:
        logger.error("❌ LocalUserDatabase not initialized. Call init_local_db() in startup.")
        raise RuntimeError("LocalUserDatabase not initialized")
    
    return _local_db_instance


async def init_local_db() -> LocalUserDatabase:
    """
    Inicializa o SQLite local database (chamado na startup)
    """
    global _local_db_instance
    
    try:
        _local_db_instance = LocalUserDatabase()
        await _local_db_instance.connect()
        logger.info("✓ LocalUserDatabase initialized")
        return _local_db_instance
    except Exception as e:
        logger.error(f"❌ Failed to initialize LocalUserDatabase: {e}")
        raise


async def close_local_db():
    """
    Fecha a conexão com o SQLite local database (chamado na shutdown)
    """
    global _local_db_instance
    
    if _local_db_instance and _local_db_instance._connection:
        try:
            await _local_db_instance._connection.close()
            logger.info("✓ LocalUserDatabase closed")
        except Exception as e:
            logger.error(f"❌ Error closing LocalUserDatabase: {e}")
    
    _local_db_instance = None


def reset_for_testing():
    """Reset the singleton (apenas para testes)"""
    global _local_db_instance
    _local_db_instance = None
