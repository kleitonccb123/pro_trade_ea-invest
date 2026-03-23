"""
Unified Exchange Service for Crypto (Binance)
"""

from typing import Dict, List, Optional, Literal
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Price:
    """Unified price data across exchanges."""
    symbol: str
    bid: float
    ask: float
    exchange: str
    timestamp: datetime
    
    @property
    def mid(self) -> float:
        """Get mid price."""
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        """Get spread in pips/basis points."""
        return self.ask - self.bid


@dataclass
class Order:
    """Unified order data across exchanges."""
    order_id: int
    symbol: str
    side: Literal["buy", "sell"]
    volume: float
    price: float
    status: str
    exchange: str
    timestamp: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class AccountInfo:
    """Unified account info across exchanges."""
    exchange: str
    balance: float
    equity: float
    free_balance: float
    margin: Optional[float] = None
    margin_level: Optional[float] = None
    leverage: Optional[int] = None
    currency: str = "USD"


class ExchangeClient(ABC):
    """Abstract base class for exchange clients."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to exchange."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from exchange."""
        pass
    
    @abstractmethod
    async def get_price(self, symbol: str) -> Optional[Price]:
        """Get current price for symbol."""
        pass
    
    @abstractmethod
    async def place_order(self,
                         symbol: str,
                         side: str,
                         volume: Decimal,
                         order_type: str = "market",
                         price: Optional[Decimal] = None,
                         stop_loss: Optional[Decimal] = None,
                         take_profit: Optional[float] = None) -> Optional[Order]:
        """Place an order."""
        pass
    
    @abstractmethod
    async def close_order(self, order_id: int, volume: Optional[float] = None) -> bool:
        """Close an order."""
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get list of open orders."""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information."""
        pass


class BinanceClientAdapter(ExchangeClient):
    """Adapter for Binance client to unified interface."""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self.exchange = "binance"
    
    async def connect(self) -> bool:
        """Connect to Binance."""
        try:
            from binance.client import Client
            self.client = Client(self.api_key, self.api_secret)
            logger.info("Connected to Binance")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        if self.client:
            self.client.close_connection()
            logger.info("Disconnected from Binance")
    
    async def get_price(self, symbol: str) -> Optional[Price]:
        """Get current price for symbol."""
        try:
            if not self.client:
                await self.connect()
            
            ticker = self.client.get_symbol_info(symbol)
            if not ticker:
                return None
            
            # For crypto, use last price as both bid/ask
            last_price = self.client.get_symbol_ticker(symbol=symbol)["price"]
            price_float = float(last_price)
            
            return Price(
                symbol=symbol,
                bid=price_float,
                ask=price_float,
                exchange=self.exchange,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error getting price from Binance: {e}")
            return None
    
    async def place_order(self,
                         symbol: str,
                         side: str,
                         volume: Decimal,
                         order_type: str = "market",
                         price: Optional[Decimal] = None,
                         stop_loss: Optional[Decimal] = None,
                         take_profit: Optional[Decimal] = None) -> Optional[Order]:
        """Place an order on Binance."""
        try:
            if not self.client:
                await self.connect()
            
            order_side = "BUY" if side.lower() == "buy" else "SELL"
            order_type_upper = order_type.upper()
            
            params = {
                "symbol": symbol,
                "side": order_side,
                "type": order_type_upper,
                "quantity": volume
            }
            
            if order_type_upper != "MARKET" and price:
                params["price"] = price
            
            result = self.client.order_new(**params)
            
            return Order(
                order_id=result["orderId"],
                symbol=symbol,
                side=side,
                volume=volume,
                price=float(result.get("price", price or 0)),
                status="filled",
                exchange=self.exchange,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error placing order on Binance: {e}")
            return None
    
    async def close_order(self, order_id: int, volume: Optional[float] = None) -> bool:
        """Close an order on Binance."""
        try:
            if not self.client:
                await self.connect()
            
            # This is simplified - actual implementation would need symbol
            result = self.client.cancel_order(orderId=order_id)
            return result["status"] == "CANCELED"
        except Exception as e:
            logger.error(f"Error closing order on Binance: {e}")
            return False
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders from Binance."""
        try:
            if not self.client:
                await self.connect()
            
            orders = self.client.get_open_orders(symbol=symbol) if symbol else self.client.get_open_orders()
            
            return [
                Order(
                    order_id=order["orderId"],
                    symbol=order["symbol"],
                    side="buy" if order["side"] == "BUY" else "sell",
                    volume=float(order["origQty"]),
                    price=float(order["price"]),
                    status=order["status"],
                    exchange=self.exchange,
                    timestamp=datetime.fromtimestamp(order["time"] / 1000)
                )
                for order in orders
            ]
        except Exception as e:
            logger.error(f"Error getting open orders from Binance: {e}")
            return []
    
    async def get_account_info(self) -> Optional[AccountInfo]:
        """Get account info from Binance."""
        try:
            if not self.client:
                await self.connect()
            
            account = self.client.get_account()
            
            return AccountInfo(
                exchange=self.exchange,
                balance=float(account.get("totalWalletBalance", 0)),
                equity=float(account.get("totalWalletBalance", 0)),
                free_balance=float(account.get("totalFreeBalance", 0)),
                currency="USDT"
            )
        except Exception as e:
            logger.error(f"Error getting account info from Binance: {e}")
            return None


class MultiExchangeService:
    """
    Unified service for managing crypto exchanges (Binance).
    
    Provides a single interface for trading operations across Binance.
    """
    
    def __init__(self):
        self.clients: Dict[str, ExchangeClient] = {}
        self._callbacks = {
            'price_update': [],
            'order_update': [],
            'error': []
        }
    
    def register_exchange(self, exchange_type: str, client: ExchangeClient) -> None:
        """Register an exchange client."""
        self.clients[exchange_type] = client
        logger.info(f"Registered {exchange_type} exchange client")
    
    def add_callback(self, event_type: str, callback) -> None:
        """Add callback for events."""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all registered exchanges."""
        results = {}
        for exchange_type, client in self.clients.items():
            try:
                results[exchange_type] = await client.connect()
            except Exception as e:
                logger.error(f"Failed to connect to {exchange_type}: {e}")
                results[exchange_type] = False
        return results
    
    async def disconnect_all(self) -> None:
        """Disconnect from all exchanges."""
        for client in self.clients.values():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
    
    async def get_price(self, symbol: str, exchange: str) -> Optional[Price]:
        """Get price from specific exchange."""
        if exchange not in self.clients:
            logger.error(f"Exchange {exchange} not registered")
            return None
        
        return await self.clients[exchange].get_price(symbol)
    
    async def get_prices(self, symbol: str) -> Dict[str, Price]:
        """Get prices from all exchanges supporting symbol."""
        prices = {}
        for exchange, client in self.clients.items():
            try:
                price = await client.get_price(symbol)
                if price:
                    prices[exchange] = price
            except Exception as e:
                logger.error(f"Error getting price from {exchange}: {e}")
        return prices
    
    async def place_order(self,
                         exchange: str,
                         symbol: str,
                         side: str,
                         volume: Decimal,
                         **kwargs) -> Optional[Order]:
        """Place order on specific exchange."""
        if exchange not in self.clients:
            logger.error(f"Exchange {exchange} not registered")
            return None
        
        order = await self.clients[exchange].place_order(
            symbol=symbol,
            side=side,
            volume=volume,
            **kwargs
        )
        
        if order:
            for callback in self._callbacks['order_update']:
                try:
                    result = callback(order)
                    if hasattr(result, '__await__'):
                        await result
                except Exception as e:
                    logger.error(f"Callback error: {e}")
        
        return order
    
    async def close_order(self, exchange: str, order_id: int, volume: Optional[float] = None) -> bool:
        """Close order on specific exchange."""
        if exchange not in self.clients:
            logger.error(f"Exchange {exchange} not registered")
            return False
        
        return await self.clients[exchange].close_order(order_id, volume)
    
    async def get_open_orders(self, exchange: str, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders from specific exchange."""
        if exchange not in self.clients:
            logger.error(f"Exchange {exchange} not registered")
            return []
        
        return await self.clients[exchange].get_open_orders(symbol)
    
    async def get_account_info(self, exchange: str) -> Optional[AccountInfo]:
        """Get account info from specific exchange."""
        if exchange not in self.clients:
            logger.error(f"Exchange {exchange} not registered")
            return None
        
        return await self.clients[exchange].get_account_info()
    
    async def get_all_account_info(self) -> Dict[str, AccountInfo]:
        """Get account info from all exchanges."""
        accounts = {}
        for exchange, client in self.clients.items():
            try:
                info = await client.get_account_info()
                if info:
                    accounts[exchange] = info
            except Exception as e:
                logger.error(f"Error getting account info from {exchange}: {e}")
        return accounts
    
    def get_exchange_types(self) -> List[str]:
        """Get list of registered exchange types."""
        return list(self.clients.keys())


# Global instance
_multi_exchange_service: Optional[MultiExchangeService] = None


def get_multi_exchange_service() -> MultiExchangeService:
    """Get or create global multi-exchange service."""
    global _multi_exchange_service
    
    if _multi_exchange_service is None:
        _multi_exchange_service = MultiExchangeService()
    
    return _multi_exchange_service
