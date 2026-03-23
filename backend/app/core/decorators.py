"""Decoradores para tratamento robusto de exceções e logging"""

import logging
from functools import wraps
from typing import Callable, Any
import asyncio

logger = logging.getLogger(__name__)


def safe_operation(operation_name: str = "operation"):
    """
    Decorator para envolver operações com tratamento consistente de exceções.
    
    Uso:
        @safe_operation("fetch_user_balance")
        async def fetch_balance(user_id: str) -> dict:
            return await db.get_balance(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {operation_name} ({func.__name__}): {str(e)[:200]}",
                    exc_info=False
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {operation_name} ({func.__name__}): {str(e)[:200]}",
                    exc_info=False
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def handle_db_errors(func: Callable) -> Callable:
    """Especifico para operações com database"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise
    return wrapper
