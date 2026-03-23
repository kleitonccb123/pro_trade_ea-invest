"""
Redis-based Connection Manager for WebSocket scalability.
Uses Redis Pub/Sub to broadcast messages across multiple API instances.
Includes distributed locking (Mutex) for atomic bot operations.

IMPORTANT: Redis is OPTIONAL. If not configured or not available,
the app runs without Redis support.
"""
import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional
from fastapi import WebSocket

from app.core.config import get_settings

# Lazy import of Redis - only import if needed
redis = None

logger = logging.getLogger(__name__)
settings = get_settings()


def _init_redis():
    global redis
    if redis is None and settings.redis_url:
        try:
            import redis.asyncio
            redis = redis.asyncio
        except ImportError:
            logger.warning("[Redis] redis library not available - Redis disabled")
            redis = None
    return redis


class RedisConnectionManager:
    """
    WebSocket connection manager that uses Redis Pub/Sub for horizontal scaling.

    Each API instance maintains its own WebSocket connections, but messages
    are broadcasted via Redis Pub/Sub to reach all connected clients across instances.
    """

    def __init__(self):
        self.redis_client: redis.Redis = None
        self.pubsub = None
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self._subscriber_task: asyncio.Task = None
        self._is_subscribed = False

    async def initialize(self):
        """Initialize Redis connection and start subscriber.
        
        Redis is OPTIONAL - if it can't connect, the app continues without it.
        """
        # Set Redis to disabled by default
        self.redis_client = None
        self.pubsub = None
        self._is_subscribed = False
        
        try:
            redis_url = settings.redis_url
            if not redis_url:
                logger.info("[Redis] No Redis URL configured - running without Redis")
                return
            
            # Lazy import and init Redis module
            _init_redis()
            if redis is None:
                logger.warning("[Redis] Redis module not available - running without Redis")
                return
                
            logger.info(f"[Redis] Initializing...")
            
            # Try to create and test the connection
            try:
                # Create client with short timeouts
                test_client = redis.from_url(
                    redis_url, 
                    decode_responses=False,
                    socket_connect_timeout=0.1,
                    socket_timeout=0.1,
                    retry_on_timeout=False
                )
                logger.debug("[Redis] Client created")
                
                self.redis_client = test_client
                self.pubsub = self.redis_client.pubsub()
                self._is_subscribed = True
                
                # Start subscriber task WITHOUT awaiting it
                # If it fails, it fails in the background
                try:
                    self._subscriber_task = asyncio.create_task(self._safe_subscribe_to_channel())
                    logger.info("✓ [Redis] Initialized successfully")
                except Exception as e:
                    logger.warning(f"[Redis] Could not start subscriber task: {e}")
                    self.redis_client = None
                    self.pubsub = None
                    self._is_subscribed = False
                    
            except Exception as e:
                logger.warning(f"[Redis] Not available: {e} - continuing without Redis")
                self.redis_client = None
                self.pubsub = None
                self._is_subscribed = False
                
        except Exception as e:
            logger.warning(f"[Redis] Initialization failed: {e} - continuing without Redis")
            self.redis_client = None
            self.pubsub = None
            self._is_subscribed = False

    async def _safe_subscribe_to_channel(self):
        """Wrapper to safely run subscriber with exception handling."""
        try:
            await self._subscribe_to_channel()
        except asyncio.CancelledError:
            logger.debug("[Redis] Subscriber task cancelled")
        except Exception as e:
            logger.warning(f"[Redis] Subscriber failed: {e}")
            # Disable Redis on any error
            self.redis_client = None
            self.pubsub = None
            self._is_subscribed = False

    async def _subscribe_to_channel(self):
        """Subscribe to Redis channel and handle incoming messages."""
        if not self.pubsub or not self.redis_client:
            logger.warning("[Redis] Redis not available, skipping subscriber")
            return
            
        try:
            await self.pubsub.subscribe(settings.redis_pubsub_channel)
            logger.info(f"[Redis] Subscribed to channel: {settings.redis_pubsub_channel}")

            while True:
                try:
                    message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                    if message:
                        await self._handle_pubsub_message(message)
                    await asyncio.sleep(0.01)
                except (ConnectionError, OSError, asyncio.TimeoutError) as e:
                    logger.warning(f"[Redis] Subscriber connection lost: {e}")
                    break
                except Exception as e:
                    logger.warning(f"[Redis] Subscriber error: {e}")
                    await asyncio.sleep(1)

        except (ConnectionError, OSError) as e:
            logger.warning(f"[Redis] Subscriber init failed: {e}")
            self._is_subscribed = False
        except Exception as e:
            logger.warning(f"[Redis] Unexpected subscriber error: {e}")
            self._is_subscribed = False

    async def _handle_pubsub_message(self, message):
        """Handle incoming message from Redis Pub/Sub."""
        try:
            data = json.loads(message['data'])
            message_type = data.get('type')
            session_id = data.get('session_id')
            content = data.get('content')

            if message_type == 'broadcast_to_session' and session_id is not None:
                await self.broadcast_to_session(content, session_id)
            elif message_type == 'broadcast_all':
                await self.broadcast_all(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Redis message: {e}")
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")

    async def connect(self, websocket: WebSocket, session_id: int):
        """Connect a WebSocket to a session."""
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        logger.debug(f"WebSocket connected to session {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: int):
        """Disconnect a WebSocket from a session."""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        logger.debug(f"WebSocket disconnected from session {session_id}")

    async def send_personal_message(self, message: str, session_id: int):
        """Send message to all connections in a specific session (local only)."""
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send message to WebSocket: {e}")
                    # Remove broken connection
                    self.disconnect(connection, session_id)

    async def broadcast_to_session(self, message: str, session_id: int):
        """Broadcast message to all connections in a session across all instances."""
        # First, send to local connections
        await self.send_personal_message(message, session_id)

        # Then publish to Redis for other instances
        if self.redis_client:
            try:
                data = {
                    'type': 'broadcast_to_session',
                    'session_id': session_id,
                    'content': message
                }
                await self.redis_client.publish(
                    settings.redis_pubsub_channel,
                    json.dumps(data)
                )
            except Exception as e:
                logger.error(f"Failed to publish to Redis: {e}")

    async def broadcast_all(self, message: str):
        """Broadcast message to all connected clients across all instances."""
        # Send to all local connections
        for session_connections in self.active_connections.values():
            for connection in session_connections:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send message to WebSocket: {e}")

        # Publish to Redis for other instances
        if self.redis_client:
            try:
                data = {
                    'type': 'broadcast_all',
                    'content': message
                }
                await self.redis_client.publish(
                    settings.redis_pubsub_channel,
                    json.dumps(data)
                )
            except Exception as e:
                logger.error(f"Failed to publish to Redis: {e}")

    async def close(self):
        """Close Redis connections and cleanup."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

        logger.info("Redis ConnectionManager closed")

    # ============================================================================
    # ? DISTRIBUTED LOCKING (MUTEX) - Para opera??es at?micas de bots
    # ============================================================================
    
    async def acquire_lock(
        self,
        lock_key: str,
        timeout_seconds: int = 5,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ) -> bool:
        """
        Adquire um lock distribu?do usando Redis.
        
        Args:
            lock_key: Chave ?nica do lock (ex: "lock:user:123")
            timeout_seconds: Tempo de expira??o do lock em segundos
            max_retries: N?mero m?ximo de tentativas
            retry_delay: Delay entre tentativas em segundos
            
        Returns:
            True se lock foi adquirido, False caso contr?rio
            
        Example:
            >>> acquired = await redis_manager.acquire_lock(f"lock:user:{user_id}")
            >>> if acquired:
            ...     try:
            ...         # Fazer opera??o cr?tica aqui
            ...         pass
            ...     finally:
            ...         await redis_manager.release_lock(f"lock:user:{user_id}")
        
        Approach:
            - Usa SET com NX (set if not exists) do Redis
            - Atomicamente: se a chave n?o existe, cria com TTL
            - Se j? existe, significa outro worker tem o lock
            - Retry com backoff exponencial se falhar
        """
        if not self.redis_client:
            logger.warning("Redis client not initialized for lock operation")
            return False
        
        lock_id = str(uuid.uuid4())  # Identificador ?nico deste lock
        
        for attempt in range(max_retries):
            try:
                # Tenta adquirir o lock (SET NX = set if not exists)
                result = await self.redis_client.set(
                    lock_key,
                    lock_id,
                    nx=True,  # S? funciona se a chave n?o existe
                    ex=timeout_seconds  # Expira em timeout_seconds
                )
                
                if result:
                    logger.info(f"? Lock adquirido: {lock_key} (id: {lock_id})")
                    return True
                else:
                    # Lock j? existe, aguarda antes de tentar novamente
                    logger.debug(f"? Lock j? existe: {lock_key}, tentativa {attempt + 1}/{max_retries}")
                    await asyncio.sleep(retry_delay)
                    
            except Exception as e:
                logger.error(f"? Erro ao adquirir lock {lock_key}: {e}")
                await asyncio.sleep(retry_delay)
        
        logger.warning(f"? Falhou em adquirir lock ap?s {max_retries} tentativas: {lock_key}")
        return False
    
    async def release_lock(self, lock_key: str) -> bool:
        """
        Libera um lock distribu?do.
        
        Args:
            lock_key: Chave do lock a liberar
            
        Returns:
            True se lock foi deletado, False se n?o existia
        """
        if not self.redis_client:
            logger.warning("Redis client not initialized for unlock operation")
            return False
        
        try:
            result = await self.redis_client.delete(lock_key)
            if result > 0:
                logger.info(f"? Lock liberado: {lock_key}")
                return True
            else:
                logger.warning(f"??  Lock n?o encontrado: {lock_key}")
                return False
        except Exception as e:
            logger.error(f"? Erro ao liberar lock {lock_key}: {e}")
            return False
    
    async def is_locked(self, lock_key: str) -> bool:
        """
        Verifica se um lock est? ativo.
        
        Args:
            lock_key: Chave do lock a verificar
            
        Returns:
            True se lock existe, False caso contr?rio
        """
        if not self.redis_client:
            return False
        
        try:
            exists = await self.redis_client.exists(lock_key)
            return exists > 0
        except Exception as e:
            logger.error(f"? Erro ao verificar lock {lock_key}: {e}")
            return False


# Global instance
redis_manager = RedisConnectionManager()