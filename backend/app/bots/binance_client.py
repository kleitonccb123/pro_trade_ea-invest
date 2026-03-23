from __future__ import annotations

import asyncio
import logging
import json
from typing import Dict, List, Optional, Callable
from decimal import Decimal
from datetime import datetime

import ccxt
from binance import AsyncClient, BinanceSocketManager
from binance.enums import *
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)


class BinanceRealTimeClient:
    """Binance client for real-time trading operations."""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client: Optional[AsyncClient] = None
        self.socket_manager: Optional[BinanceSocketManager] = None
        self._connected = False
        self._callbacks: Dict[str, List[Callable]] = {
            'trade': [],
            'kline': [],
            'ticker': [],
            'order_update': []
        }
    
    async def connect(self):
        """Initialize Binance client connection."""
        try:
            self.client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            self.socket_manager = BinanceSocketManager(self.client)
            self._connected = True
            logger.info(f"Connected to Binance {'testnet' if self.testnet else 'mainnet'}")
            
            # Test connection
            account_info = await self.client.get_account()
            logger.info(f"Account balance: {len(account_info['balances'])} assets")
            
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            self._connected = False
            raise
    
    async def disconnect(self):
        """Close Binance connection."""
        if self.socket_manager:
            await self.socket_manager.close()
        if self.client:
            await self.client.close_connection()
        self._connected = False
        logger.info("Disconnected from Binance")
    
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for real-time events."""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
    
    async def start_kline_stream(self, symbol: str, interval: str = '1m'):
        """Start real-time kline stream."""
        if not self._connected:
            await self.connect()
        
        async def handle_kline(msg):
            kline_data = {
                'symbol': msg['s'],
                'open_time': msg['k']['t'],
                'close_time': msg['k']['T'],
                'open': float(msg['k']['o']),
                'high': float(msg['k']['h']),
                'low': float(msg['k']['l']),
                'close': float(msg['k']['c']),
                'volume': float(msg['k']['v']),
                'closed': msg['k']['x']  # Whether kline is closed
            }
            for callback in self._callbacks['kline']:
                await callback(kline_data)
        
        ts = self.socket_manager.kline_socket(symbol=symbol, interval=interval)
        async with ts as stream:
            while True:
                msg = await stream.recv()
                await handle_kline(msg)
    
    async def start_user_stream(self):
        """Start user data stream for order updates."""
        if not self._connected:
            await self.connect()
        
        async def handle_user_data(msg):
            if msg['e'] == 'executionReport':  # Order update
                order_data = {
                    'symbol': msg['s'],
                    'side': msg['S'],
                    'order_type': msg['o'],
                    'quantity': float(msg['q']),
                    'price': float(msg['p']),
                    'status': msg['X'],
                    'filled_qty': float(msg['z']),
                    'avg_price': float(msg['Z']) / float(msg['z']) if float(msg['z']) > 0 else 0,
                    'timestamp': msg['T']
                }
                for callback in self._callbacks['order_update']:
                    await callback(order_data)
        
        ts = self.socket_manager.user_socket()
        async with ts as stream:
            while True:
                msg = await stream.recv()
                await handle_user_data(msg)
    
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        """Place market order."""
        if not self._connected:
            await self.connect()
        
        try:
            order = await self.client.order_market(
                symbol=symbol,
                side=side,
                quantity=quantity
            )
            logger.info(f"Market order placed: {symbol} {side} {quantity}")
            return {
                'order_id': order['orderId'],
                'symbol': order['symbol'],
                'side': order['side'],
                'quantity': float(order['origQty']),
                'status': order['status'],
                'timestamp': order['transactTime']
            }
        except BinanceAPIException as e:
            logger.error(f"Order failed: {e}")
            raise
    
    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        """Place limit order."""
        if not self._connected:
            await self.connect()
        
        try:
            order = await self.client.order_limit(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price
            )
            logger.info(f"Limit order placed: {symbol} {side} {quantity} @ {price}")
            return {
                'order_id': order['orderId'],
                'symbol': order['symbol'],
                'side': order['side'],
                'quantity': float(order['origQty']),
                'price': float(order['price']),
                'status': order['status'],
                'timestamp': order['transactTime']
            }
        except BinanceAPIException as e:
            logger.error(f"Order failed: {e}")
            raise
    
    async def get_account_balance(self) -> List[dict]:
        """Get account balances."""
        if not self._connected:
            await self.connect()
        
        account = await self.client.get_account()
        balances = []
        for balance in account['balances']:
            if float(balance['free']) > 0 or float(balance['locked']) > 0:
                balances.append({
                    'asset': balance['asset'],
                    'free': float(balance['free']),
                    'locked': float(balance['locked']),
                    'total': float(balance['free']) + float(balance['locked'])
                })
        return balances
    
    async def get_symbol_info(self, symbol: str) -> dict:
        """Get symbol trading info."""
        if not self._connected:
            await self.connect()
        
        exchange_info = await self.client.get_exchange_info()
        for sym in exchange_info['symbols']:
            if sym['symbol'] == symbol:
                return {
                    'symbol': sym['symbol'],
                    'status': sym['status'],
                    'base_asset': sym['baseAsset'],
                    'quote_asset': sym['quoteAsset'],
                    'min_qty': next((f['minQty'] for f in sym['filters'] if f['filterType'] == 'LOT_SIZE'), '0'),
                    'tick_size': next((f['tickSize'] for f in sym['filters'] if f['filterType'] == 'PRICE_FILTER'), '0')
                }
        raise ValueError(f"Symbol {symbol} not found")