from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, List, Set
from datetime import datetime

from fastapi import WebSocket

# Motor and MongoDB imports
from app.core.database import get_db

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time trading data."""
    
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {
            'dashboard': [],
            'robots': [],
            'trades': []
        }
        self.binance_clients: Dict[int, BinanceRealTimeClient] = {}
        self.active_streams: Set[str] = set()
    
    async def connect(self, websocket: WebSocket, client_type: str = 'dashboard'):
        """Connect new WebSocket client."""
        await websocket.accept()
        if client_type not in self.connections:
            self.connections[client_type] = []
        self.connections[client_type].append(websocket)
        logger.info(f"WebSocket client connected: {client_type}")
    
    def disconnect(self, websocket: WebSocket, client_type: str = 'dashboard'):
        """Disconnect WebSocket client."""
        if client_type in self.connections:
            if websocket in self.connections[client_type]:
                self.connections[client_type].remove(websocket)
        logger.info(f"WebSocket client disconnected: {client_type}")
    
    async def broadcast_to_type(self, client_type: str, message: dict):
        """Broadcast message to all clients of a specific type."""
        if client_type not in self.connections:
            return
        
        disconnected = []
        for websocket in self.connections[client_type]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send message to {client_type} client: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.connections[client_type].remove(ws)
    
    async def broadcast_trade_update(self, trade_data: dict):
        """Broadcast trade updates to all connected clients."""
        message = {
            'type': 'trade_update',
            'data': trade_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.broadcast_to_type('dashboard', message)
        await self.broadcast_to_type('trades', message)
    
    async def broadcast_kline_update(self, kline_data: dict):
        """Broadcast kline/candlestick updates."""
        message = {
            'type': 'kline_update',
            'data': kline_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.broadcast_to_type('dashboard', message)
        await self.broadcast_to_type('robots', message)
    
    async def broadcast_robot_status(self, robot_data: dict):
        """Broadcast robot status updates."""
        message = {
            'type': 'robot_status',
            'data': robot_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        await self.broadcast_to_type('robots', message)
        await self.broadcast_to_type('dashboard', message)
    
    async def start_binance_stream(self, instance_id: int, api_key: str, api_secret: str, symbol: str, testnet: bool = True):
        """Start Binance stream for a robot instance."""
        try:
            # Create Binance client for this instance
            binance_client = BinanceRealTimeClient(api_key, api_secret, testnet)
            self.binance_clients[instance_id] = binance_client
            
            # Add callbacks for real-time data
            binance_client.add_callback('kline', self._handle_kline_data)
            binance_client.add_callback('order_update', self._handle_order_update)
            
            # Start streams
            await binance_client.connect()
            
            # Start kline stream in background
            asyncio.create_task(binance_client.start_kline_stream(symbol, '1m'))
            
            # Start user data stream in background
            asyncio.create_task(binance_client.start_user_stream())
            
            logger.info(f"Started Binance streams for instance {instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to start Binance stream for instance {instance_id}: {e}")
            raise
    
    async def stop_binance_stream(self, instance_id: int):
        """Stop Binance stream for a robot instance."""
        if instance_id in self.binance_clients:
            await self.binance_clients[instance_id].disconnect()
            del self.binance_clients[instance_id]
            logger.info(f"Stopped Binance stream for instance {instance_id}")
    
    async def _handle_kline_data(self, kline_data: dict):
        """Handle real-time kline data from Binance."""
        await self.broadcast_kline_update(kline_data)
    
    async def _handle_order_update(self, order_data: dict):
        """Handle order updates from Binance and save to database."""
        try:
            # Save trade to database
            db = get_db()
            # TODO: Refator para Motor/MongoDB
            # Find which instance this order belongs to
            # (In a real implementation, you'd track this mapping)
            # await self._save_real_trade(db, order_data)
            
            # Broadcast to connected clients
            await self.broadcast_trade_update(order_data)
            
        except Exception as e:
            logger.error(f"Failed to handle order update: {e}")
    
    async def _save_real_trade(self, db, order_data: dict):
        """Save real trade data to database."""
        # TODO: Implement Motor/MongoDB version
        pass
    
    async def place_order(self, instance_id: int, symbol: str, side: str, quantity: Decimal, order_type: str = 'market', price: Optional[Decimal] = None) -> dict:
        """Place order through Binance client."""
        if instance_id not in self.binance_clients:
            raise ValueError(f"No active Binance client for instance {instance_id}")
        
        binance_client = self.binance_clients[instance_id]
        
        if order_type == 'market':
            return await binance_client.place_market_order(symbol, side, quantity)
        elif order_type == 'limit' and price:
            return await binance_client.place_limit_order(symbol, side, quantity, price)
        else:
            raise ValueError(f"Invalid order type or missing price for limit order")
    
    async def get_account_balance(self, instance_id: int) -> List[dict]:
        """Get account balance through Binance client."""
        if instance_id not in self.binance_clients:
            raise ValueError(f"No active Binance client for instance {instance_id}")
        
        return await self.binance_clients[instance_id].get_account_balance()


# Global WebSocket manager instance
websocket_manager = WebSocketManager()