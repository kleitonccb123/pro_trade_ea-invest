from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, ConfigDict
from bson import ObjectId

from app.bots import service as bots_service
from app.bots.repository import BotsRepository
from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.services.strategy_engine import strategy_engine
from app.services.redis_manager import redis_manager
from app.workers.task_queue import task_queue, TaskType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots", tags=["bots-execution"])
service = bots_service.BotsService()


class BotConfigUpdate(BaseModel):
    """Schema for updating bot configuration."""
    model_config = ConfigDict(from_attributes=True)
    
    amount: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_level: Optional[str] = None
    timeframe: Optional[str] = None
    indicators: Optional[List[str]] = None


class BotResponse(BaseModel):
    """Response schema for bot information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    description: Optional[str] = None
    strategy: str
    exchange: str
    pair: str
    status: str
    profit: float
    trades: int
    win_rate: float
    runtime: str
    amount: float
    stop_loss: float
    take_profit: float
    risk_level: str
    timeframe: str
    indicators: List[str]
    max_drawdown: float
    sharpe_ratio: float
    created_at: datetime
    last_updated: datetime
    is_running: bool
    last_started: Optional[datetime] = None
    config: Dict[str, Any]


class TradeResponse(BaseModel):
    """Response schema for trade information."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    bot_id: str
    symbol: str
    side: str
    price: float
    amount: float
    pnl: float
    status: str
    strategy: str
    timestamp: datetime


@router.post("/{bot_id}/start", response_model=Dict[str, Any])
async def start_bot(
    bot_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Start a bot instance com SWAP AT?MICO.
    
    ? SWAP AT?MICO:
    - Antes de iniciar o novo rob?, cancela TODAS as ordens do rob? anterior
    - Usa Redis locking para evitar m?ltiplos starts simult?neos (max 1 start a cada 5s)
    - Safety First: Se falhar em cancelar ordens, novo rob? N?O inicia
    
    Args:
        bot_id: The bot ID to start
        current_user: Current authenticated user
        
    Returns:
        Success message with bot status (ou erro se lock n?o conseguir ser adquirido)
        
    Raises:
        HTTPException: Se bot n?o encontrado, j? est? executando, ou swap at?mico falha
    """
    user_id = str(current_user.get('_id', current_user.get('id')))
    lock_key = f"lock:bot:start:{user_id}"  # Redis lock key
    
    logger.info(f"? Iniciando bot {bot_id} para usu?rio {user_id}")
    
    # =========================================================================
    # ? ADQUIRE LOCK DISTRIBU?DO (Mutex)
    # =========================================================================
    
    lock_acquired = await redis_manager.acquire_lock(
        lock_key=lock_key,
        timeout_seconds=5,  # Lock expira em 5 segundos
        max_retries=3,      # Tenta 3 vezes
        retry_delay=0.5     # 500ms entre tentativas
    )
    
    if not lock_acquired:
        logger.warning(f"? Outro processo est? iniciando um rob?. Tente novamente em alguns segundos.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Outro processo est? iniciando um rob?. Tente novamente em alguns segundos."
        )
    
    try:
        db = get_db()
        bots_col = db['bots']
        
        # =========================================================================
        # Valida que o bot existe e pertence ao usu?rio
        # =========================================================================
        
        bot = await bots_col.find_one({'_id': ObjectId(bot_id), 'user_id': user_id})
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot n?o encontrado ou acesso negado"
            )
        
        # Verifica se bot j? est? running
        if bot.get('is_running', False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bot {bot_id} j? est? em execu??o"
            )
        
        # =========================================================================
        # ? EXECUTA SWAP AT?MICO: Limpa rob? anterior
        # =========================================================================
        
        logger.info(f"? Preparando troca de estrat?gia (cancelando rob? anterior se existir)...")
        
        prepare_result = await service.prepare_for_new_strategy(user_id)
        
        if not prepare_result["success"]:
            # ? FALHA: N?o foi poss?vel completar o swap at?mico
            error_msg = prepare_result.get("error", "Erro desconhecido")
            logger.error(f"? SWAP AT?MICO FALHOU: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao desativar rob? anterior. Erro: {error_msg}. "
                       f"Seu novo rob? N?O foi iniciado para garantir seguran?a."
            )
        
        # ? SWAP AT?MICO SUCESSO: Rob? anterior foi limpado
        logger.info(f"? Swap at?mico completo - {prepare_result['cancelled_orders']} ordens canceladas")
        
        # =========================================================================
        # Atualiza status do novo bot para 'running'
        # =========================================================================
        
        now = datetime.utcnow()
        await bots_col.update_one(
            {'_id': ObjectId(bot_id)},
            {
                '$set': {
                    'is_running': True,
                    'last_started': now,
                    'last_updated': now,
                    'status': 'running'
                }
            }
        )
        
        logger.info(f"? Status do novo bot atualizado para 'running'")
        
        # =========================================================================
        # Enfileira task para inicializa??o em background
        # =========================================================================
        
        task_id = await task_queue.enqueue_task(
            TaskType.START_BOT,
            bot_id,
            str(current_user.id)
        )
        
        logger.info(f"? Bot {bot_id} enfileirado para execu??o: task_id={task_id}")
        
        return {
            "success": True,
            "message": f"Bot iniciado com sucesso (swap at?mico: {prepare_result['cancelled_orders']} ordens canceladas)",
            "bot_id": bot_id,
            "task_id": task_id,
            "status": "running",
            "started_at": now.isoformat(),
            "atomic_swap": {
                "success": True,
                "previous_bot_id": prepare_result["previous_bot_id"],
                "symbol": prepare_result["symbol"],
                "cancelled_orders": prepare_result["cancelled_orders"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao iniciar bot {bot_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao iniciar bot: {str(e)}"
        )
    finally:
        # =========================================================================
        # ? LIBERA LOCK DISTRIBU?DO
        # =========================================================================
        
        lock_released = await redis_manager.release_lock(lock_key)
        if lock_released:
            logger.info(f"? Lock liberado: {lock_key}")
        else:
            logger.warning(f"??  Falha ao liberar lock: {lock_key}")


@router.post("/{bot_id}/stop", response_model=Dict[str, Any])
async def stop_bot(
    bot_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Stop a bot instance.
    
    Args:
        bot_id: The bot ID to stop
        current_user: Current authenticated user
        
    Returns:
        Success message with bot status
        
    Raises:
        HTTPException: If bot not found or not running
    """
    try:
        logger.info(f"Stopping bot {bot_id} for user {current_user.get('id')}")
        
        # Find bot in database
        db = get_db()
        bots_col = db['bots']
        user_id = str(current_user.get('_id', current_user.get('id')))
        bot = await bots_col.find_one({'_id': ObjectId(bot_id), 'user_id': user_id})
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot n?o encontrado ou acesso negado"
            )
        
        # Check if bot is running
        if not bot.get('is_running', False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bot {bot_id} is not running"
            )
        
        # Update bot status to stopped
        now = datetime.utcnow()
        await bots_col.update_one(
            {'_id': ObjectId(bot_id)},
            {
                '$set': {
                    'is_running': False,
                    'last_updated': now,
                    'status': 'stopped'
                }
            }
        )
        
        # Enqueue bot stop task for background processing
        task_id = await task_queue.enqueue_task(
            TaskType.STOP_BOT,
            bot_id,
            str(current_user.id)
        )
        
        logger.info(f"Bot {bot_id} stop task enqueued: {task_id}")
        
        return {
            "success": True,
            "message": f"Bot {bot_id} stop task enqueued successfully",
            "bot_id": bot_id,
            "task_id": task_id,
            "status": "pending",
            "stopped_at": now.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )


@router.get("", response_model=List[BotResponse])
async def list_bots(
    current_user: Dict = Depends(get_current_user)
) -> List[BotResponse]:
    """
    List all bots for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List of bot information
    """
    try:
        logger.info(f"Listing bots for user {current_user.get('id')}")
        
        # Get bots from database
        db = get_db()
        bots_col = db['bots']
        user_id = str(current_user.get('_id', current_user.get('id')))
        bots_cursor = bots_col.find({"user_id": user_id})
        bots = await bots_cursor.to_list(None)
        
        # Transform to response format
        bot_responses = []
        for bot in bots:
            # Get performance data (mock for now)
            performance = await _get_bot_performance(str(bot['_id']))
            
            bot_response = BotResponse(
                id=str(bot['_id']),
                name=bot.get('name', 'Unnamed Bot'),
                description=bot.get('description', ''),
                strategy=bot.get('strategy', 'Custom Strategy'),
                exchange=bot.get('exchange', 'binance'),
                pair=bot.get('pair', 'BTC/USDT'),
                status=bot.get('status', 'stopped'),
                profit=performance.get('total_pnl', 0.0),
                trades=performance.get('total_trades', 0),
                win_rate=performance.get('win_rate', 0.0),
                runtime=performance.get('runtime', '0h 0m'),
                amount=bot.get('config', {}).get('amount', 1000.0),
                stop_loss=bot.get('config', {}).get('stop_loss', 5.0),
                take_profit=bot.get('config', {}).get('take_profit', 10.0),
                risk_level=bot.get('config', {}).get('risk_level', 'medium'),
                timeframe=bot.get('config', {}).get('timeframe', '5m'),
                indicators=bot.get('config', {}).get('indicators', ['RSI', 'MACD']),
                max_drawdown=performance.get('max_drawdown', 0.0),
                sharpe_ratio=performance.get('sharpe_ratio', 0.0),
                created_at=bot.get('created_at', datetime.utcnow()),
                last_updated=bot.get('last_updated', datetime.utcnow()),
                is_running=bot.get('is_running', False),
                last_started=bot.get('last_started'),
                config=bot.get('config', {})
            )
            bot_responses.append(bot_response)
        
        return bot_responses
        
    except Exception as e:
        logger.error(f"Failed to list bots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list bots: {str(e)}"
        )


@router.put("/{bot_id}/config", response_model=Dict[str, Any])
async def update_bot_config(
    bot_id: str,
    config_update: BotConfigUpdate,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update bot configuration.
    
    Args:
        bot_id: The bot ID to update
        config_update: Configuration updates
        current_user: Current authenticated user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If bot not found
    """
    try:
        logger.info(f"Updating config for bot {bot_id}")
        
        # Find bot in database
        db = get_db()
        bots_col = db['bots']
        bot = await bots_col.find_one({'_id': ObjectId(bot_id)})
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot {bot_id} not found"
            )
        
        # Prepare update data
        update_data = {'last_updated': datetime.utcnow()}
        config_updates = {}
        
        # Only update fields that are provided
        if config_update.amount is not None:
            config_updates['amount'] = config_update.amount
        if config_update.stop_loss is not None:
            config_updates['stop_loss'] = config_update.stop_loss
        if config_update.take_profit is not None:
            config_updates['take_profit'] = config_update.take_profit
        if config_update.risk_level is not None:
            config_updates['risk_level'] = config_update.risk_level
        if config_update.timeframe is not None:
            config_updates['timeframe'] = config_update.timeframe
        if config_update.indicators is not None:
            config_updates['indicators'] = config_update.indicators
        
        if config_updates:
            update_data['config'] = {**bot.get('config', {}), **config_updates}
        
        # Update bot
        await bots_col.update_one(
            {'_id': ObjectId(bot_id)},
            {'$set': update_data}
        )
        
        logger.info(f"Bot {bot_id} config updated successfully")
        
        return {
            "success": True,
            "message": f"Bot {bot_id} configuration updated successfully",
            "bot_id": bot_id,
            "updated_fields": list(config_updates.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update bot config {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update bot configuration: {str(e)}"
        )


async def _get_bot_performance(bot_id: str) -> Dict[str, Any]:
    """
    Get performance data for a bot.
    This is a mock implementation - in a real system this would query actual trade data.
    """
    # Mock performance data - replace with real analytics
    return {
        'total_pnl': 1234.56,
        'total_trades': 45,
        'win_rate': 68.5,
        'runtime': '24h 15m',
        'max_drawdown': 5.2,
        'sharpe_ratio': 2.1
    }


@router.get("/trades/history", response_model=List[TradeResponse])
async def get_trades_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Dict = Depends(get_current_user)
) -> List[TradeResponse]:
    """
    Lista hist?rico de trades do usu?rio gerados pelos bots.
    """
    try:
        db = get_db()
        user_id = str(current_user.get('_id', current_user.get('id')))

        # Buscar trades do usu?rio ordenados por timestamp (mais recentes primeiro)
        trades_cursor = db.trades.find({"user_id": user_id})\
            .sort("timestamp", -1)\
            .skip(offset)\
            .limit(limit)

        trades = await trades_cursor.to_list(length=None)

        return [
            TradeResponse(
                id=str(trade["_id"]),
                bot_id=trade.get("bot_id", ""),
                symbol=trade.get("symbol", ""),
                side=trade.get("side", ""),
                price=trade.get("price", 0.0),
                amount=trade.get("amount", 0.0),
                pnl=trade.get("pnl", 0.0),
                status=trade.get("status", "unknown"),
                strategy=trade.get("strategy", "unknown"),
                timestamp=trade.get("timestamp")
            )
            for trade in trades
        ]

    except Exception as e:
        logger.error(f"Erro ao buscar hist?rico de trades: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar hist?rico de trades"
        )

@router.get("/queue/status", summary="Get task queue status")
async def get_queue_status(current_user: Any = Depends(get_current_user)):
    """
    Get the current status of the background task queue.
    Shows active workers, pending tasks, and bot status.
    """
    try:
        status = await task_queue.get_queue_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving queue status"
        )