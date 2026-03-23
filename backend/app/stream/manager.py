"""
StreamManager - Gerencia streams em tempo real da KuCoin.

Utiliza WebSocket para:
- Klines (candlesticks)
- Trades
- Order Book incremental
- Execution reports

Responsabilidades:
- Reconexão automática
- Heartbeat monitoring
- Normalização de payload
- Distribuição para estratégias
"""

from __future__ import annotations

import logging
import asyncio
import json
import time
from typing import Dict, List, Callable, Optional
from datetime import datetime, timezone
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class StreamSubscription:
    """Representa uma subscrição a um stream."""
    
    def __init__(self, topic: str, callback: Callable):
        self.topic = topic
        self.callback = callback
        self.active = True
    
    async def notify(self, data: Dict):
        """Notifica subscriber."""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(data)
            else:
                self.callback(data)
        except Exception as e:
            logger.error(f"❌ Erro no callback {self.topic}: {e}")


class KuCoinWebSocketHandler:
    """Handler de WebSocket com reconexão automática."""
    
    WS_URL = "wss://ws-api.kucoin.com/socket.io"
    SANDBOX_URL = "wss://ws-api.sandbox.kucoin.com/socket.io"
    
    def __init__(self, sandbox: bool = False):
        self.base_url = self.SANDBOX_URL if sandbox else self.WS_URL
        self.ws = None
        self.is_connected = False
        self.ping_interval = 30  # segundos
        self.last_message_time = time.time()
        self.callbacks: Dict[str, List[Callable]] = {}
    
    async def connect(self):
        """Conecta ao WebSocket."""
        try:
            logger.info(f"Conectando ao WebSocket: {self.base_url}")
            self.ws = await websockets.connect(f"{self.base_url}?token=")
            self.is_connected = True
            logger.info(f"✅ WebSocket conectado: {self.base_url}")
            
            # Inicia tasks de monitoramento
            asyncio.create_task(self._monitor_heartbeat())
            asyncio.create_task(self._listen_messages())
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar WebSocket: {e}")
            self.is_connected = False
            raise
    
    async def subscribe(self, topic: str, callback: Callable) -> str:
        """Subscreve a um topic."""
        if not self.ws:
            raise RuntimeError("WebSocket não conectado")
        
        request = {
            "id": str(int(time.time() * 1000)),
            "type": "subscribe",
            "topic": topic,
            "response": True
        }
        
        try:
            await self.ws.send(json.dumps(request))
            
            # Registra callback
            if topic not in self.callbacks:
                self.callbacks[topic] = []
            self.callbacks[topic].append(callback)
            
            logger.info(f"📡 Subscrição: {topic}")
            return topic
            
        except Exception as e:
            logger.error(f"❌ Erro ao subscrever {topic}: {e}")
            raise
    
    async def _listen_messages(self):
        """Escuta mensagens do servidor."""
        try:
            async for message in self.ws:
                self.last_message_time = time.time()
                
                try:
                    data = json.loads(message)
                    
                    # Responde ao ping
                    if data.get("type") == "ping":
                        pong = {"type": "pong", "id": data.get("id")}
                        await self.ws.send(json.dumps(pong))
                        logger.debug(f"🔄 Pong enviado: {data.get('id')}")
                    
                    # Processa data
                    elif data.get("type") == "message":
                        await self._handle_data(data)
                
                except Exception as e:
                    logger.error(f"❌ Erro processando mensagem: {e}")
        
        except ConnectionClosed:
            logger.warning("⚠️ WebSocket conexão fechada")
            self.is_connected = False
            await self.reconnect()
        except Exception as e:
            logger.error(f"❌ Erro fatal no listener: {e}")
            self.is_connected = False
            await self.reconnect()
    
    async def _monitor_heartbeat(self):
        """Monitora inatividade e reconecta se necessário."""
        timeout = 60  # segundos
        
        while True:
            await asyncio.sleep(10)
            
            if not self.is_connected:
                continue
            
            elapsed = time.time() - self.last_message_time
            if elapsed > timeout:
                logger.error(f"❌ WebSocket inativo por {elapsed}s, reconectando...")
                await self.reconnect()
            else:
                logger.debug(f"🔄 Heartbeat OK, última mensagem há {elapsed:.1f}s")
    
    async def _handle_data(self, data: Dict):
        """Distribui dados para subscribers."""
        topic = data.get("topic", "")
        
        # Localiza callbacks para este topic
        if topic in self.callbacks:
            for callback in self.callbacks[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"❌ Erro no callback {topic}: {e}")
    
    async def reconnect(self, max_attempts: int = 10):
        """Reconecta com exponential backoff."""
        for attempt in range(1, max_attempts + 1):
            try:
                wait_time = min(2 ** attempt, 300)  # Max 5 min
                logger.info(f"🔄 Reconectando em {wait_time}s (tentativa {attempt}/{max_attempts})")
                await asyncio.sleep(wait_time)
                await self.connect()
                return
            except Exception as e:
                logger.error(f"❌ Falha na reconexão {attempt}: {e}")
        
        logger.error(f"❌ Falha permanente após {max_attempts} tentativas")
        self.is_connected = False
    
    async def close(self):
        """Fecha conexão."""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("✅ WebSocket fechado")


class StreamManager:
    """Gerencia múltiplos streams em tempo real."""
    
    def __init__(self, sandbox: bool = False):
        self.handler = KuCoinWebSocketHandler(sandbox=sandbox)
        self.subscriptions: Dict[str, List[StreamSubscription]] = {}
        logger.info("✅ StreamManager inicializado")
    
    async def start(self):
        """Inicia o manager."""
        await self.handler.connect()
    
    async def subscribe_kline(
        self,
        symbol: str,
        interval: str = "1m",
        callback: Optional[Callable] = None,
    ) -> str:
        """Subscreve a klines (candlesticks)."""
        topic = f"/market/candles:{symbol}_{interval}"
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
            await self.handler.subscribe(topic, self._dispatch_kline)
        
        if callback:
            sub = StreamSubscription(topic, callback)
            self.subscriptions[topic].append(sub)
            logger.info(f"📊 Subscrição Kline: {symbol} {interval}")
        
        return topic
    
    async def subscribe_trades(
        self,
        symbol: str,
        callback: Optional[Callable] = None,
    ) -> str:
        """Subscreve a trades."""
        topic = f"/market/match:{symbol}"
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
            await self.handler.subscribe(topic, self._dispatch_trades)
        
        if callback:
            sub = StreamSubscription(topic, callback)
            self.subscriptions[topic].append(sub)
            logger.info(f"💱 Subscrição Trades: {symbol}")
        
        return topic
    
    async def subscribe_orderbook(
        self,
        symbol: str,
        level: str = "20",
        callback: Optional[Callable] = None,
    ) -> str:
        """Subscreve a order book."""
        topic = f"/spotMarket/level2Depth{level}:{symbol}"
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
            await self.handler.subscribe(topic, self._dispatch_orderbook)
        
        if callback:
            sub = StreamSubscription(topic, callback)
            self.subscriptions[topic].append(sub)
            logger.info(f"📈 Subscrição OrderBook: {symbol} L{level}")
        
        return topic
    
    async def _dispatch_kline(self, data: Dict):
        """Distribui candle para subscribers."""
        topic = data.get("topic", "")
        for sub in self.subscriptions.get(topic, []):
            if sub.active:
                await sub.notify(data)
    
    async def _dispatch_trades(self, data: Dict):
        """Distribui trade para subscribers."""
        topic = data.get("topic", "")
        for sub in self.subscriptions.get(topic, []):
            if sub.active:
                await sub.notify(data)
    
    async def _dispatch_orderbook(self, data: Dict):
        """Distribui order book para subscribers."""
        topic = data.get("topic", "")
        for sub in self.subscriptions.get(topic, []):
            if sub.active:
                await sub.notify(data)
    
    async def unsubscribe(self, topic: str):
        """Desinscreve de um topic."""
        if topic in self.subscriptions:
            for sub in self.subscriptions[topic]:
                sub.active = False
            del self.subscriptions[topic]
            logger.info(f"🗑️ Desinscrito: {topic}")
    
    async def close(self):
        """Fecha o manager."""
        await self.handler.close()
        logger.info("✅ StreamManager fechado")
    
    def is_connected(self) -> bool:
        """Retorna status de conexão."""
        return self.handler.is_connected


# Instância global
stream_manager: Optional[StreamManager] = None

async def init_stream_manager(sandbox: bool = False):
    global stream_manager
    stream_manager = StreamManager(sandbox=sandbox)
    await stream_manager.start()
    logger.info("✅ StreamManager inicializado e conectado")
    return stream_manager
