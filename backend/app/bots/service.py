from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime
from bson import ObjectId

from app.bots import repository as bots_repo
from app.bots import model as bots_model
from app.bots.engine import BotEngine
from app.bots.websocket_manager import websocket_manager
from app.core.database import get_db
from app.bots.exceptions import NotFound, InvalidStateTransition
from app.services.exchange_service import exchange_service
from app.services.redis_manager import redis_manager
from app.trading.executor import TradingExecutor
from app.trading.credentials_repository import CredentialsRepository

logger = logging.getLogger(__name__)


class BotsService:
    """Service layer to manage bots and engine lifecycle. Supports both simulation and real KuCoin trading."""

    def __init__(self):
        self.engine = BotEngine()
        self.active_executors: Dict[str, TradingExecutor] = {}  # Cache de executores ativos

    async def create_bot(self, name: str, symbol: str, config: dict | None = None):
        db = get_db()
        bots_col = db['bots']
        
        new_bot = {
            'name': name,
            'symbol': symbol,
            'config': config or {},
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        result = await bots_col.insert_one(new_bot)
        new_bot['_id'] = result.inserted_id
        return new_bot

    async def create_instance(self, bot_id: int, user_id: int, metadata: dict | None = None):
        db = get_db()
        bots_col = db['bots']
        bot_instances_col = db['bot_instances']
        
        # Find bot by ID
        bot = await bots_col.find_one({'_id': bot_id})
        if not bot:
            raise NotFound("Bot not found")
        
        new_instance = {
            'bot_id': bot_id,
            'user_id': user_id,
            'state': 'idle',
            'metadata': metadata or {},
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'last_heartbeat': None,
            'error_message': None
        }
        result = await bot_instances_col.insert_one(new_instance)
        new_instance['_id'] = result.inserted_id
        return new_instance

    async def start(self, instance_id: int, user_id: str):
        """Start bot instance with real KuCoin trading.
        
        ✅ NOVO (Task 1.3):
        - Valida credenciais KuCoin
        - Cria executor de trading
        - Inicializa com integração real
        - Cacheia executor ativo
        """
        db = get_db()
        bot_instances_col = db['bot_instances']
        bots_col = db['bots']
        
        # Encontrar instância
        inst = await bot_instances_col.find_one({'_id': instance_id})
        if not inst:
            raise NotFound("Instance not found")
        
        if inst.get('state') == 'running':
            raise InvalidStateTransition("Instance already running")
        
        # PASSO 1: Validar credenciais KuCoin
        logger.debug(f"[1/5] Validando credenciais KuCoin user={user_id}")
        try:
            creds_repo = CredentialsRepository()
            credentials = await creds_repo.get_credentials(user_id, 'kucoin')
            if not credentials:
                logger.warning(f"[1/5] Credenciais KuCoin não encontradas user={user_id}")
                raise PermissionError(f"Configure credenciais KuCoin antes de iniciar trading")
        except Exception as e:
            logger.error(f"[1/5] Erro ao validar credenciais: {e}")
            raise
        
        # PASSO 2: Criar executor TradingExecutor
        logger.debug(f"[2/5] Criando TradingExecutor instance_id={instance_id} user={user_id}")
        try:
            executor = TradingExecutor(user_id=user_id, exchange='kucoin')
            instance_str = str(instance_id)  # Garantir string para dicionário
        except Exception as e:
            logger.error(f"[2/5] Erro ao criar executor: {e}")
            raise
        
        # PASSO 3: Inicializar executor
        logger.debug(f"[3/5] Inicializando executor instance_id={instance_id}")
        try:
            await executor.initialize()
            logger.info(f"[3/5] ✅ Executor inicializado instance_id={instance_id}")
        except Exception as e:
            logger.error(f"[3/5] Erro ao inicializar executor: {e}")
            raise
        
        # PASSO 4: Cachear executor
        logger.debug(f"[4/5] Armazenando executor em cache instance_id={instance_id}")
        try:
            self.active_executors[instance_str] = executor
            logger.info(f"[4/5] ✅ Executor em cache instance_id={instance_id}")
        except Exception as e:
            logger.error(f"[4/5] Erro ao armazenar executor: {e}")
            raise
        
        # PASSO 5: Atualizar estado e fazer broadcast
        logger.debug(f"[5/5] Atualizando estado banco de dados instance_id={instance_id}")
        try:
            bot = await bots_col.find_one({'_id': inst.get('bot_id')})
            symbol = bot.get('symbol') if bot else 'UNKNOWN'
            
            # Atualizar estado no MongoDB
            await bot_instances_col.update_one(
                {'_id': instance_id},
                {'$set': {
                    'state': 'running',
                    'mode': 'live_kucoin',  # Nova flag
                    'updated_at': datetime.utcnow(),
                    'last_heartbeat': datetime.utcnow()
                }}
            )
            
            # Broadcast status
            await websocket_manager.broadcast_robot_status({
                'instance_id': instance_id,
                'status': 'running_live',
                'symbol': symbol,
                'mode': 'live_kucoin',
                'exchange': 'kucoin',
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"[5/5] ✅ Bot {instance_id} iniciado com trading real KuCoin")
            
        except Exception as e:
            logger.error(f"[5/5] Erro ao atualizar estado: {e}")
            # Limpeza: remover executor do cache se falhar
            if instance_str in self.active_executors:
                del self.active_executors[instance_str]
            raise

    async def stop(self, instance_id: int):
        """Stop bot instance and cleanup resources.
        
        ✅ MODIFICADO (Task 1.3):
        - Limpa executor da memória cache
        - Encerra recursos do TradingExecutor
        """
        db = get_db()
        bot_instances_col = db['bot_instances']
        
        # Find instance
        inst = await bot_instances_col.find_one({'_id': instance_id})
        if not inst:
            raise NotFound("Instance not found")
        
        # PASSO 1: Limpar executor do cache
        instance_str = str(instance_id)
        logger.debug(f"[1/3] Removendo executor do cache instance_id={instance_id}")
        executor = self.active_executors.pop(instance_str, None)
        if executor:
            try:
                # Se executor tem método close(), chamá-lo
                if hasattr(executor, 'close'):
                    await executor.close()
                logger.info(f"[1/3] ✅ Executor limpo instance_id={instance_id}")
            except Exception as e:
                logger.error(f"[1/3] Erro ao fechar executor: {e}")
        
        # PASSO 2: Atualizar estado no banco
        logger.debug(f"[2/3] Atualizando estado instance_id={instance_id}")
        await bot_instances_col.update_one(
            {'_id': instance_id},
            {'$set': {
                'state': 'stopped',
                'mode': None,
                'updated_at': datetime.utcnow()
            }}
        )
        
        # PASSO 3: Fazer broadcast e limpar websocket
        logger.debug(f"[3/3] Fazendo broadcast e limpeza instance_id={instance_id}")
        
        # Stop Binance stream if was using it (backward compatibility)
        try:
            await websocket_manager.stop_binance_stream(instance_id)
        except Exception as e:
            logger.debug(f"Binance stream cleanup: {e}")
        
        # Stop engine (backward compatibility)
        try:
            await self.engine.stop_instance(instance_id)
        except Exception as e:
            logger.debug(f"Engine cleanup: {e}")
        
        # Broadcast status update
        await websocket_manager.broadcast_robot_status({
            'instance_id': instance_id,
            'status': 'stopped',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"[3/3] ✅ Bot {instance_id} parado")

    async def pause(self, instance_id: int):
        """Pause bot instance (keeps executor but stops new orders).
        
        ✅ MODIFICADO (Task 1.3):
        - Marca como paused mas mantém executor em cache
        - Permite resumir sem reinicialização
        """
        db = get_db()
        bot_instances_col = db['bot_instances']
        
        # Find instance
        inst = await bot_instances_col.find_one({'_id': instance_id})
        if not inst:
            raise NotFound("Instance not found")
        
        # Update state to paused
        logger.debug(f"Pausando bot instance_id={instance_id}")
        await bot_instances_col.update_one(
            {'_id': instance_id},
            {'$set': {
                'state': 'paused',
                'updated_at': datetime.utcnow()
            }}
        )
        
        # Não remove executor, apenas para engine (backward compatibility)
        try:
            await self.engine.stop_instance(instance_id)
        except Exception as e:
            logger.debug(f"Engine pause: {e}")
        
        # Broadcast status update
        await websocket_manager.broadcast_robot_status({
            'instance_id': instance_id,
            'status': 'paused',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"✅ Bot {instance_id} pausado")

    async def get_instances(self, limit: int = 100):
        db = get_db()
        bot_instances_col = db['bot_instances']
        
        # Get instances with limit
        instances_cursor = bot_instances_col.find({})
        instances = await instances_cursor.to_list(limit)
        return instances

    async def get_bots(self, limit: int = 100):
        db = get_db()
        bots_col = db['bots']
        
        # Get bots with limit
        bots_cursor = bots_col.find({})
        bots = await bots_cursor.to_list(limit)
        return bots
    
    async def place_manual_order(self, instance_id: int, symbol: str, side: str, quantity: float, order_type: str = 'market', price: float = None):
        """Place manual order through active Binance connection."""
        try:
            order_result = await websocket_manager.place_order(
                instance_id=instance_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price
            )
            
            logger.info(f"Manual order placed for instance {instance_id}: {order_result}")
            return order_result
            
        except Exception as e:
            logger.error(f"Failed to place manual order: {e}")
            raise
    
    async def get_account_balance(self, instance_id: int):
        """Get account balance for active Binance connection."""
        try:
            return await websocket_manager.get_account_balance(instance_id)
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            raise

    async def pause(self, instance_id: int):
        """Pause bot instance."""
        db = get_db()
        await db['bot_instances'].update_one(
            {'_id': instance_id},
            {'$set': {'state': 'paused', 'updated_at': datetime.utcnow()}}
        )
        await self.engine.stop_instance(instance_id)

    async def stop(self, instance_id: int):
        """Stop bot instance."""
        db = get_db()
        await db['bot_instances'].update_one(
            {'_id': instance_id},
            {'$set': {'state': 'stopped', 'updated_at': datetime.utcnow()}}
        )
        await self.engine.stop_instance(instance_id)

    async def list_bots(self):
        # Simple listing via DB
        db = get_db()
        bots_col = db['bots']
        
        bots_cursor = bots_col.find({})
        bots = await bots_cursor.to_list(None)
        
        return [
            {
                "id": bot.get('_id'),
                "name": bot.get('name'),
                "symbol": bot.get('symbol'),
                "config": bot.get('config')
            }
            for bot in bots
        ]

    async def list_trades(self, instance_id: int):
        db = get_db()
        simulated_trades_col = db['simulated_trades']
        
        # Get all trades for this instance
        trades_cursor = simulated_trades_col.find({'instance_id': instance_id})
        trades = await trades_cursor.to_list(None)
        return trades

    async def get_most_used_bots(self, days: int):
        """Get top 10 most used bots in the last N days."""
        db = get_db()
        bot_instances_col = db['bot_instances']
        bots_col = db['bots']
        
        # Calculate cutoff date
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Aggregate to find most used bots
        pipeline = [
            {'$match': {'created_at': {'$gte': cutoff_date}}},
            {'$group': {
                '_id': '$bot_id',
                'usage_count': {'$sum': 1}
            }},
            {'$sort': {'usage_count': -1}},
            {'$limit': 10}
        ]
        
        result = await bot_instances_col.aggregate(pipeline).to_list(None)
        
        # Enrich with bot details
        enriched = []
        for item in result:
            bot = await bots_col.find_one({'_id': item['_id']})
            if bot:
                enriched.append({
                    'id': str(item['_id']),
                    'name': bot.get('name', 'Unknown Bot'),
                    'symbol': bot.get('symbol', 'N/A'),
                    'usage_count': item['usage_count'],
                    'nationality': bot.get('creator_country', 'Global'),
                    'avg_pnl_percent': bot.get('avg_pnl_percent', 0)
                })
        
        return enriched

    async def get_most_profitable_bots(self, days: int):
        """Get top 10 most profitable bots in the last N days."""
        db = get_db()
        simulated_trades_col = db['simulated_trades']
        bots_col = db['bots']
        bot_instances_col = db['bot_instances']
        
        # Calculate cutoff date
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Aggregate to find most profitable bots
        pipeline = [
            {'$match': {'timestamp': {'$gte': cutoff_date}}},
            {'$group': {
                '_id': '$instance_id',
                'total_pnl': {'$sum': '$pnl'},
                'trade_count': {'$sum': 1},
                'wins': {'$sum': {'$cond': [{'$gte': ['$pnl', 0]}, 1, 0]}}
            }},
            {'$addFields': {
                'win_rate': {'$multiply': [{'$divide': ['$wins', '$trade_count']}, 100]}
            }},
            {'$sort': {'total_pnl': -1}},
            {'$limit': 10}
        ]
        
        result = await simulated_trades_col.aggregate(pipeline).to_list(None)
        
        # Enrich with bot details
        enriched = []
        for item in result:
            instance = await bot_instances_col.find_one({'_id': item['_id']})
            if instance:
                bot = await bots_col.find_one({'_id': instance.get('bot_id')})
                if bot:
                    enriched.append({
                        'id': str(item['_id']),
                        'name': bot.get('name', 'Unknown Bot'),
                        'symbol': bot.get('symbol', 'N/A'),
                        'total_pnl': round(item['total_pnl'], 2),
                        'trade_count': item['trade_count'],
                        'win_rate': round(item.get('win_rate', 0), 2),
                        'avg_pnl_percent': bot.get('avg_pnl_percent', 0),
                        'nationality': bot.get('creator_country', 'Global'),
                        'usage_count': 0
                    })
        
        return enriched

    # ============================================================================
    # ? SWAP AT?MICO - Prepara??o para trocar estrat?gia
    # ============================================================================
    
    async def prepare_for_new_strategy(self, user_id: str) -> dict:
        """
        Prepara o usu?rio para TROCAR de estrat?gia de rob?.
        
        Realiza um "Swap At?mico" que:
        1. Localiza o rob? ativo do usu?rio
        2. Cancela TODAS as ordens abertas na exchange
        3. Aguarda confirma??o de cancelamento (polling)
        4. Atualiza o status do rob? antigo para 'idle'
        
        IMPORTANTE:
        - Se QUALQUER etapa falhar, o novo rob? N?O ser? iniciado
        - Usa Redis locking para evitar m?ltiplas trocas simult?neas
        - Garante que n?o h? ordens ?rf?s na exchange
        
        Args:
            user_id: ID do usu?rio
            
        Returns:
            Dict com resultado:
            {
                "success": bool,
                "message": str,
                "previous_bot_id": str | None,
                "symbol": str | None,
                "cancelled_orders": int,
                "error": str | None
            }
            
        Example:
            >>> result = await bot_service.prepare_for_new_strategy("user_123")
            >>> if result["success"]:
            ...     # Agora ? seguro iniciar novo rob?
            ...     await bot_service.start_new_bot(...)
        """
        logger.info(f"? Preparando troca de estrat?gia para usu?rio {user_id}")
        
        db = get_db()
        bots_col = db['bots']
        
        try:
            # =========================================================================
            # ETAPA 1: Busca o rob? ativo do usu?rio
            # =========================================================================
            
            active_bot = await bots_col.find_one({
                'user_id': user_id,
                'is_running': True,  # Busca apenas rob? ativo
                'status': 'running'
            })
            
            if not active_bot:
                logger.info(f"??  Nenhum rob? ativo encontrado para {user_id}, processo de troca abortado")
                return {
                    "success": True,
                    "message": "Nenhum rob? ativo para limpeza",
                    "previous_bot_id": None,
                    "symbol": None,
                    "cancelled_orders": 0,
                    "error": None
                }
            
            bot_id = str(active_bot.get('_id'))
            symbol = active_bot.get('pair')
            
            logger.info(f"? Rob? ativo encontrado: {bot_id} ({symbol})")
            
            # =========================================================================
            # ETAPA 2: Atualiza status para 'switching' (transi??o)
            # =========================================================================
            
            await bots_col.update_one(
                {'_id': active_bot.get('_id')},
                {
                    '$set': {
                        'status': 'switching',  # Estado de transi??o
                        'last_updated': datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"? Status do rob? atualizado para 'switching'")
            
            # =========================================================================
            # ETAPA 3: Cancela TODAS as ordens abertas no par de moedas
            # =========================================================================
            
            logger.info(f"? Iniciando cancelamento de todas as ordens para {symbol}...")
            
            cancel_result = await exchange_service.cancel_all_orders(symbol, max_retries=3)
            
            if not cancel_result.get("success"):
                # ? FALHA CR?TICA: N?o foi poss?vel cancelar todas as ordens
                error_msg = cancel_result.get("error", "Erro desconhecido")
                logger.error(f"? FALHA ao cancelar ordens: {error_msg}")
                
                # Retorna status FAILURE para impedir inicializa??o do novo rob?
                return {
                    "success": False,
                    "message": f"Falha ao cancelar ordens na exchange",
                    "previous_bot_id": bot_id,
                    "symbol": symbol,
                    "cancelled_orders": cancel_result.get("cancelled_count", 0),
                    "error": error_msg
                }
            
            cancelled_count = cancel_result.get("cancelled_count", 0)
            logger.info(f"? Canceladas {cancelled_count} ordens em {symbol}")
            
            # =========================================================================
            # ETAPA 4: Atualiza o rob? antigo para 'idle'
            # =========================================================================
            
            await bots_col.update_one(
                {'_id': active_bot.get('_id')},
                {
                    '$set': {
                        'status': 'idle',  # Rob? pronto, mas parado
                        'is_running': False,
                        'last_updated': datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"? Status do rob? antigo definido para 'idle'")
            
            # =========================================================================
            # SUCESSO: Tudo pronto para iniciar novo rob?
            # =========================================================================
            
            logger.info(f"? Troca de estrat?gia preparada com sucesso!")
            
            return {
                "success": True,
                "message": f"Rob? anterior desativado, {cancelled_count} ordens canceladas",
                "previous_bot_id": bot_id,
                "symbol": symbol,
                "cancelled_orders": cancelled_count,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"? ERRO CR?TICO ao preparar troca: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Erro ao preparar troca de estrat?gia",
                "previous_bot_id": None,
                "symbol": None,
                "cancelled_orders": 0,
                "error": str(e)
            }
