"""
Binance API Client for real trading operations
"""
import hashlib
import hmac
import time
import json
from typing import Dict, List, Optional, Any
import httpx
import websockets
from websockets.exceptions import ConnectionClosed
import asyncio
from decimal import Decimal
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        if testnet:
            self.base_url = "https://testnet.binance.vision"
            self.ws_base = "wss://testnet.binance.vision/ws"
        else:
            self.base_url = "https://api.binance.com"
            self.ws_base = "wss://stream.binance.com:9443/ws"
    
    def _generate_signature(self, params: str) -> str:
        """Generate HMAC SHA256 signature"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key"""
        return {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        endpoint = "/api/v3/account"
        timestamp = int(time.time() * 1000)
        params = f"timestamp={timestamp}"
        signature = self._generate_signature(params)
        
        url = f"{self.base_url}{endpoint}?{params}&signature={signature}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
    
    async def get_balances(self) -> List[Dict[str, Any]]:
        """Get account balances"""
        account_info = await self.get_account_info()
        balances = []
        
        for balance in account_info.get("balances", []):
            free = float(balance["free"])
            locked = float(balance["locked"])
            if free > 0 or locked > 0:
                balances.append({
                    "asset": balance["asset"],
                    "free": free,
                    "locked": locked,
                    "total": free + locked
                })
        
        return balances
    
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: Decimal, price: Optional[Decimal] = None) -> Dict[str, Any]:
        """Place a new order"""
        endpoint = "/api/v3/order"
        timestamp = int(time.time() * 1000)
        
        params = {
            "symbol": symbol,
            "side": side.upper(),  # BUY or SELL
            "type": order_type.upper(),  # MARKET, LIMIT, etc.
            "quantity": str(quantity),
            "timestamp": timestamp
        }
        
        if order_type.upper() == "LIMIT" and price:
            params["price"] = str(price)
            params["timeInForce"] = "GTC"  # Good Till Cancelled
        
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = self._generate_signature(param_string)
        params["signature"] = signature
        
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=params, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders"""
        endpoint = "/api/v3/openOrders"
        timestamp = int(time.time() * 1000)
        
        params = {"timestamp": timestamp}
        if symbol:
            params["symbol"] = symbol
        
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = self._generate_signature(param_string)
        params["signature"] = signature
        
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
    
    async def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order"""
        endpoint = "/api/v3/order"
        timestamp = int(time.time() * 1000)
        
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": timestamp
        }
        
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = self._generate_signature(param_string)
        params["signature"] = signature
        
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

class BinanceWebSocketClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.client = BinanceClient(api_key, api_secret, testnet)
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.subscriptions: Dict[str, set] = {}
    
    async def connect_user_stream(self) -> str:
        """Create a user data stream and return listen key"""
        endpoint = "/api/v3/userDataStream"
        url = f"{self.client.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.client._get_headers())
            response.raise_for_status()
            data = response.json()
            return data["listenKey"]
    
    async def start_user_stream(self, callback):
        """Start user data stream for real-time account updates"""
        listen_key = await self.connect_user_stream()
        ws_url = f"{self.client.ws_base}/{listen_key}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info(f"Connected to Binance User Stream: {listen_key}")
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await callback(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing WebSocket message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
        except ConnectionClosed:
            logger.warning("User stream connection closed, attempting reconnect...")
            await asyncio.sleep(5)
            await self.start_user_stream(callback)
        except Exception as e:
            logger.error(f"User stream error: {e}")
    
    async def subscribe_klines(self, symbol: str, interval: str, callback):
        """Subscribe to kline/candlestick data"""
        stream = f"{symbol.lower()}@kline_{interval}"
        ws_url = f"{self.client.ws_base}/{stream}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info(f"Subscribed to {symbol} {interval} klines")
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await callback(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing kline message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing kline message: {e}")
        except ConnectionClosed:
            logger.warning(f"Kline stream connection closed for {symbol}")
        except Exception as e:
            logger.error(f"Kline stream error for {symbol}: {e}")
    
    async def subscribe_ticker(self, symbol: str, callback):
        """Subscribe to 24hr ticker price change statistics"""
        stream = f"{symbol.lower()}@ticker"
        ws_url = f"{self.client.ws_base}/{stream}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info(f"Subscribed to {symbol} ticker")
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await callback(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing ticker message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing ticker message: {e}")
        except ConnectionClosed:
            logger.warning(f"Ticker stream connection closed for {symbol}")
        except Exception as e:
            logger.error(f"Ticker stream error for {symbol}: {e}")

# Global clients cache
_binance_clients: Dict[str, BinanceClient] = {}
_ws_clients: Dict[str, BinanceWebSocketClient] = {}

def get_binance_client(user_id: str, api_key: str, api_secret: str, testnet: bool = True) -> BinanceClient:
    """Get or create a Binance client for a user"""
    client_key = f"{user_id}_{testnet}"
    
    if client_key not in _binance_clients:
        _binance_clients[client_key] = BinanceClient(api_key, api_secret, testnet)
    
    return _binance_clients[client_key]

def get_binance_ws_client(user_id: str, api_key: str, api_secret: str, testnet: bool = True) -> BinanceWebSocketClient:
    """Get or create a Binance WebSocket client for a user"""
    client_key = f"{user_id}_{testnet}"
    
    if client_key not in _ws_clients:
        _ws_clients[client_key] = BinanceWebSocketClient(api_key, api_secret, testnet)
    
    return _ws_clients[client_key]