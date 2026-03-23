"""
CCXT Unified Exchange Service

This module provides a unified interface for trading on multiple exchanges
(Binance, KuCoin) using the CCXT library. It automatically handles:
- Credential retrieval and decryption
- Exchange-specific configuration
- Testnet/sandbox mode switching
- Common trading operations

Supported Exchanges:
- Binance (Spot)
- KuCoin (Spot)

Author: Crypto Trade Hub
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

import ccxt
import ccxt.async_support as ccxt_async

from app.services.network_resilience import (
    resilient_ccxt_call,
    notify_exchange_failure,
    should_pause_bots_on_failure
)

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class Balance:
    """Unified balance data across exchanges."""
    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal
    exchange: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "free": self.free,
            "locked": self.locked,
            "total": self.total,
            "exchange": self.exchange
        }


@dataclass
class Ticker:
    """Unified ticker data."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    timestamp: datetime
    exchange: str
    
    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")
    
    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "mid": self.mid,
            "spread": self.spread
        }


@dataclass
class OrderResult:
    """Unified order result."""
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Optional[Decimal]
    filled: Decimal
    remaining: Decimal
    status: str
    timestamp: datetime
    exchange: str
    raw: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "filled": self.filled,
            "remaining": self.remaining,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange
        }


class CCXTExchangeService:
    """
    Unified exchange service using CCXT.
    
    Supports Binance and KuCoin with automatic credential management.
    """
    
    # Exchange clients cache (per user)
    _clients: Dict[str, ccxt_async.Exchange] = {}
    
    def __init__(self):
        pass
    
    @classmethod
    def _get_client_key(cls, user_id: str, exchange: str) -> str:
        """Generate unique key for caching exchange clients."""
        return f"{user_id}:{exchange}"
    
    @classmethod
    async def get_client(
        cls,
        user_id: str,
        exchange: str | ExchangeType,
        force_new: bool = False
    ) -> Optional[ccxt_async.Exchange]:
        """
        Get or create a CCXT exchange client for a user.
        
        Args:
            user_id: User's ID
            exchange: Exchange name (binance, kucoin)
            force_new: Force creation of new client
            
        Returns:
            Configured CCXT exchange client
        """
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        exchange = exchange.lower()
        client_key = cls._get_client_key(user_id, exchange)
        
        # Check cache
        if not force_new and client_key in cls._clients:
            return cls._clients[client_key]
        
        # Get credentials from repository
        credentials = await CredentialsRepository.get_credentials(
            user_id=user_id,
            exchange=exchange,
            decrypt=True
        )
        
        if not credentials:
            logger.warning(f"No credentials found for user {user_id} on {exchange}")
            return None
        
        # Create exchange client
        client = cls._create_client(
            exchange=exchange,
            api_key=credentials.get("api_key"),
            api_secret=credentials.get("api_secret"),
            passphrase=credentials.get("passphrase"),  # KuCoin only
            is_testnet=credentials.get("is_testnet", True)
        )
        
        if client:
            cls._clients[client_key] = client
            logger.info(f"? Created {exchange} client for user {user_id}")
        
        return client
    
    @classmethod
    def _create_client(
        cls,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str = None,
        is_testnet: bool = True
    ) -> Optional[ccxt_async.Exchange]:
        """
        Create a CCXT exchange client.
        
        Args:
            exchange: Exchange name
            api_key: API key
            api_secret: API secret
            passphrase: API passphrase (KuCoin only)
            is_testnet: Use testnet/sandbox mode
            
        Returns:
            Configured CCXT exchange client
        """
        try:
            config = {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot"
                }
            }
            
            if exchange == "binance":
                if is_testnet:
                    config["options"]["defaultType"] = "spot"
                    config["options"]["sandboxMode"] = True
                client = ccxt_async.binance(config)
                if is_testnet:
                    client.set_sandbox_mode(True)
                    
            elif exchange == "kucoin":
                config["password"] = passphrase
                if is_testnet:
                    config["options"]["sandboxMode"] = True
                client = ccxt_async.kucoin(config)
                if is_testnet:
                    client.set_sandbox_mode(True)
                    
            else:
                logger.error(f"Unsupported exchange: {exchange}")
                return None
            
            logger.info(f"? Created {exchange} client (testnet={is_testnet})")
            return client
            
        except Exception as e:
            logger.error(f"? Failed to create {exchange} client: {e}")
            return None
    
    @classmethod
    async def close_client(cls, user_id: str, exchange: str):
        """Close and remove a client from cache."""
        client_key = cls._get_client_key(user_id, exchange)
        if client_key in cls._clients:
            try:
                await cls._clients[client_key].close()
            except:
                pass
            del cls._clients[client_key]
            logger.info(f"Closed {exchange} client for user {user_id}")
    
    # ==================== TRADING OPERATIONS ====================
    
    @classmethod
    async def test_credentials(
        cls,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str = None,
        is_testnet: bool = True
    ) -> Dict[str, Any]:
        """
        Test exchange credentials without saving them.
        
        Returns connection status and basic account info.
        """
        client = None
        try:
            client = cls._create_client(
                exchange=exchange,
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                is_testnet=is_testnet
            )
            
            if not client:
                return {
                    "valid": False,
                    "error": "Failed to create exchange client"
                }
            
            # Test by fetching balance
            balance = await client.fetch_balance()
            
            return {
                "valid": True,
                "exchange": exchange,
                "testnet": is_testnet,
                "timestamp": datetime.utcnow().isoformat(),
                "info": {
                    "has_spot": True,
                    "total_assets": len([k for k, v in balance.get("total", {}).items() if v > 0])
                }
            }
            
        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication failed for {exchange}: {e}")
            return {
                "valid": False,
                "error": f"Authentication failed: Invalid API credentials"
            }
        except ccxt.NetworkError as e:
            logger.error(f"Network error for {exchange}: {e}")
            return {
                "valid": False,
                "error": f"Network error: Could not connect to {exchange}"
            }
        except Exception as e:
            logger.error(f"Credential test failed for {exchange}: {e}")
            return {
                "valid": False,
                "error": str(e)
            }
        finally:
            if client:
                try:
                    await client.close()
                except:
                    pass
    
    @classmethod
    @resilient_ccxt_call(max_retries=2, base_delay=0.5)
    async def get_balances(
        cls,
        user_id: str,
        exchange: str | ExchangeType,
        min_balance: Decimal = Decimal("0.0")
    ) -> List[Balance]:
        """
        Get account balances.
        
        Args:
            user_id: User's ID
            exchange: Exchange name
            min_balance: Minimum total balance to include (filters dust)
            
        Returns:
            List of Balance objects
        """
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        client = await cls.get_client(user_id, exchange)
        if not client:
            raise ValueError(f"No credentials found for {exchange}")
        
        try:
            raw_balance = await client.fetch_balance()
            balances = []
            
            for asset, amounts in raw_balance.get("total", {}).items():
                total = Decimal(str(amounts or 0))
                if total >= min_balance:
                    free = Decimal(str(raw_balance.get("free", {}).get(asset, 0) or 0))
                    locked = Decimal(str(raw_balance.get("used", {}).get(asset, 0) or 0))
                    
                    balances.append(Balance(
                        asset=asset,
                        free=free,
                        locked=locked,
                        total=total,
                        exchange=exchange
                    ))
            
            # Sort by total balance descending
            balances.sort(key=lambda b: b.total, reverse=True)
            return balances
            
        except Exception as e:
            logger.error(f"Failed to fetch balances from {exchange}: {e}")
            raise
    
    @classmethod
    @resilient_ccxt_call(max_retries=2, base_delay=0.5)
    async def get_ticker(
        cls,
        user_id: str,
        exchange: str | ExchangeType,
        symbol: str
    ) -> Optional[Ticker]:
        """
        Get current ticker for a symbol.
        
        Args:
            user_id: User's ID
            exchange: Exchange name
            symbol: Trading pair (e.g., "BTC/USDT")
            
        Returns:
            Ticker object
        """
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        client = await cls.get_client(user_id, exchange)
        if not client:
            raise ValueError(f"No credentials found for {exchange}")
        
        try:
            raw_ticker = await client.fetch_ticker(symbol)
            
            return Ticker(
                symbol=symbol,
                bid=Decimal(str(raw_ticker.get("bid", 0) or 0)),
                ask=Decimal(str(raw_ticker.get("ask", 0) or 0)),
                last=Decimal(str(raw_ticker.get("last", 0) or 0)),
                high=Decimal(str(raw_ticker.get("high", 0) or 0)),
                low=Decimal(str(raw_ticker.get("low", 0) or 0)),
                volume=Decimal(str(raw_ticker.get("baseVolume", 0) or 0)),
                timestamp=datetime.fromtimestamp(raw_ticker.get("timestamp", 0) / 1000),
                exchange=exchange
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol} from {exchange}: {e}")
            raise
    
    @classmethod
    @resilient_ccxt_call(max_retries=3, base_delay=1.0)
    async def place_order(
        cls,
        user_id: str,
        exchange: str | ExchangeType,
        symbol: str,
        side: str | OrderSide,
        order_type: str | OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None
    ) -> OrderResult:
        """
        Place a trading order.
        
        Args:
            user_id: User's ID
            exchange: Exchange name
            symbol: Trading pair (e.g., "BTC/USDT")
            side: "buy" or "sell"
            order_type: "market" or "limit"
            quantity: Order quantity
            price: Limit price (required for limit orders)
            
        Returns:
            OrderResult object
        """
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        if isinstance(side, OrderSide):
            side = side.value
        if isinstance(order_type, OrderType):
            order_type = order_type.value
        
        client = await cls.get_client(user_id, exchange)
        if not client:
            raise ValueError(f"No credentials found for {exchange}")
        
        try:
            if order_type == "market":
                raw_order = await client.create_market_order(symbol, side, quantity)
            elif order_type == "limit":
                if price is None:
                    raise ValueError("Price is required for limit orders")
                raw_order = await client.create_limit_order(symbol, side, quantity, price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            return OrderResult(
                order_id=str(raw_order.get("id", "")),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=Decimal(str(raw_order.get("price", 0) or price or 0)),
                filled=Decimal(str(raw_order.get("filled", 0) or 0)),
                remaining=Decimal(str(raw_order.get("remaining", quantity) or quantity)),
                status=raw_order.get("status", "unknown"),
                timestamp=datetime.utcnow(),
                exchange=exchange,
                raw=raw_order
            )
            
        except Exception as e:
            logger.error(f"Failed to place order on {exchange}: {e}")
            raise
    
    @classmethod
    @resilient_ccxt_call(max_retries=3, base_delay=1.0)
    async def cancel_order(
        cls,
        user_id: str,
        exchange: str | ExchangeType,
        order_id: str,
        symbol: str
    ) -> bool:
        """
        Cancel an open order.
        
        Returns True if cancelled successfully.
        """
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        client = await cls.get_client(user_id, exchange)
        if not client:
            raise ValueError(f"No credentials found for {exchange}")
        
        try:
            await client.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    @classmethod
    @resilient_ccxt_call(max_retries=2, base_delay=0.5)
    async def get_open_orders(
        cls,
        user_id: str,
        exchange: str | ExchangeType,
        symbol: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get open orders.
        
        Args:
            user_id: User's ID
            exchange: Exchange name
            symbol: Optional symbol filter
            
        Returns:
            List of open orders
        """
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        client = await cls.get_client(user_id, exchange)
        if not client:
            raise ValueError(f"No credentials found for {exchange}")
        
        try:
            orders = await client.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            logger.error(f"Failed to fetch open orders from {exchange}: {e}")
            raise
    
    @classmethod
    @resilient_ccxt_call(max_retries=1, base_delay=0.5)
    async def get_markets(
        cls,
        user_id: str,
        exchange: str | ExchangeType
    ) -> Dict[str, Any]:
        """
        Get available markets/trading pairs.
        
        Returns dict of symbol -> market info.
        """
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        client = await cls.get_client(user_id, exchange)
        if not client:
            raise ValueError(f"No credentials found for {exchange}")
        
        try:
            await client.load_markets()
            return client.markets
        except Exception as e:
            logger.error(f"Failed to fetch markets from {exchange}: {e}")
            raise


# Global service instance
exchange_service = CCXTExchangeService()


# ==================== CONVENIENCE FUNCTIONS ====================

async def test_exchange_credentials(
    exchange: str,
    api_key: str,
    api_secret: str,
    passphrase: str = None,
    is_testnet: bool = True
) -> Dict[str, Any]:
    """Test exchange credentials without saving."""
    return await CCXTExchangeService.test_credentials(
        exchange=exchange,
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        is_testnet=is_testnet
    )


async def get_user_balances(
    user_id: str,
    exchange: str,
    min_balance: Decimal = Decimal("0.0")
) -> List[Dict[str, Any]]:
    """Get user's account balances."""
    balances = await CCXTExchangeService.get_balances(user_id, exchange, min_balance)
    return [b.to_dict() for b in balances]


async def get_ticker_price(
    user_id: str,
    exchange: str | ExchangeType,
    symbol: str
) -> Ticker:
    """
    Get ticker price for a symbol (convenience function).
    
    Returns Ticker object with current market data.
    """
    return await CCXTExchangeService.get_ticker(user_id, exchange, symbol)


# Circuit Breaker Status Endpoint
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get status of all circuit breakers.
    
    Returns:
        Dict with circuit breaker states for each exchange
    """
    from app.services.network_resilience import circuit_breakers, CircuitBreakerState
    
    status = {}
    for exchange, cb in circuit_breakers.items():
        status[exchange] = {
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None,
            "is_open": cb.state == CircuitBreakerState.OPEN,
            "is_half_open": cb.state == CircuitBreakerState.HALF_OPEN
        }
    
    return status


async def get_ticker_price(
    user_id: str,
    exchange: str,
    symbol: str
) -> Dict[str, Any]:
    """Get ticker price for a symbol."""
    ticker = await CCXTExchangeService.get_ticker(user_id, exchange, symbol)
    return ticker.to_dict() if ticker else None
