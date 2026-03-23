"""
Normalizer - Camada 2

Converte respostas da KuCoin (strings, timestamps em ms, etc)
para tipos Python/Decimal seguros.

Responsabilidades:
- String → Decimal
- Nanoseconds/Milliseconds → datetime
- Array responses → Dataclass models
- Tratamento de campos opcionais
- Sem lógica de business, apenas conversão
"""

from __future__ import annotations

import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OrderStatus(str, Enum):
    OPEN = "open"
    CLOSED = "done"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class NormalizedBalance:
    """Modelo normalizado de saldo."""
    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        assert self.total == self.free + self.locked, "total != free + locked"


@dataclass
class NormalizedOrder:
    """Modelo normalizado de ordem."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: str  # market, limit, stop
    price: Optional[Decimal] = None
    size: Decimal = Decimal("0")
    filled: Decimal = Decimal("0")
    remaining: Decimal = Decimal("0")
    status: OrderStatus = OrderStatus.OPEN
    fee: Decimal = Decimal("0")
    fee_currency: str = "USDT"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    client_oid: Optional[str] = None
    
    def __post_init__(self):
        if self.status in (OrderStatus.CLOSED, OrderStatus.CANCELLED):
            assert self.remaining == Decimal("0"), "remaining deve ser 0 quando fechado"


@dataclass
class NormalizedCandle:
    """Modelo normalizado de candle."""
    timestamp: datetime
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal  # base currency
    quote_asset_volume: Decimal = Decimal("0")  # quote currency


@dataclass
class NormalizedTrade:
    """Modelo normalizado de trade (resultado de execução de ordem)."""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    size: Decimal
    fee: Decimal
    fee_currency: str
    timestamp: datetime
    is_buyer_maker: bool


class PayloadNormalizer:
    """Normaliza respostas da KuCoin."""
    
    @staticmethod
    def normalize_balance(raw: Dict[str, Any], account_id: str) -> NormalizedBalance:
        """
        Normaliza resposta de saldo.
        
        Raw (da KuCoin):
        {
            "id": "5bd6e042953c76160ce6c88f",
            "currency": "BTC",
            "type": "trade",
            "balance": "1.0",
            "available": "1.0",
            "holds": "0"
        }
        """
        return NormalizedBalance(
            asset=raw.get("currency", "").upper(),
            free=Decimal(raw.get("available", "0")),
            locked=Decimal(raw.get("holds", "0")),
            total=Decimal(raw.get("balance", "0")),
            timestamp=datetime.now(timezone.utc),
        )
    
    @staticmethod
    def normalize_order(raw: Dict[str, Any]) -> NormalizedOrder:
        """
        Normaliza resposta de ordem.
        
        Raw (da KuCoin):
        {
            "id": "5f3113a1689401000612a12a",
            "symbol": "BTC-USDT",
            "opType": "DEAL",
            "type": "limit",
            "side": "buy",
            "price": "34567.89",
            "size": "0.1",
            "dealSize": "0.1",
            "remainSize": "0",
            "fee": "0.346848",
            "feeCurrency": "USDT",
            "stp": "",
            "stop": "",
            "stopTriggered": False,
            "stopPrice": "0",
            "timeInForce": "GTC",
            "postOnly": False,
            "hidden": False,
            "icebergShow": "",
            "visibleSize": "",
            "cancelAfter": 0,
            "clientOid": "5f3113a16894010006129d3f",
            "remark": "",
            "tags": "",
            "isActive": False,
            "cancelExist": False,
            "createdAt": 1597192621959,
            "tradeType": "TRADE"
        }
        """
        
        size = Decimal(raw.get("size", "0"))
        filled = Decimal(raw.get("dealSize", "0"))
        
        # Determina status
        is_active = raw.get("isActive", False)
        if is_active:
            if filled > 0:
                status = OrderStatus.PARTIALLY_FILLED
            else:
                status = OrderStatus.OPEN
        elif raw.get("cancelExist", False):
            status = OrderStatus.CANCELLED
        else:
            status = OrderStatus.CLOSED
        
        return NormalizedOrder(
            order_id=raw.get("id", ""),
            symbol=raw.get("symbol", ""),
            side=OrderSide(raw.get("side", "buy").lower()),
            order_type=raw.get("type", "limit").lower(),
            price=Decimal(raw.get("price", "0")) if raw.get("price") else None,
            size=size,
            filled=filled,
            remaining=size - filled,
            status=status,
            fee=Decimal(raw.get("fee", "0")),
            fee_currency=raw.get("feeCurrency", "USDT"),
            created_at=datetime.fromtimestamp(int(raw.get("createdAt", 0)) / 1000, tz=timezone.utc),
            updated_at=datetime.now(timezone.utc),
            client_oid=raw.get("clientOid"),
        )
    
    @staticmethod
    def normalize_candle(raw: List[str]) -> NormalizedCandle:
        """
        Normaliza candle.
        
        Raw (array de strings):
        [
            "1545904980",  // timestamp
            "7.0",         // open
            "8.0",         // close
            "9.0",         // high
            "6.0",         // low
            "0.0033"       // volume
        ]
        """
        return NormalizedCandle(
            timestamp=datetime.fromtimestamp(int(raw[0]), tz=timezone.utc),
            open=Decimal(raw[1]),
            close=Decimal(raw[2]),
            high=Decimal(raw[3]),
            low=Decimal(raw[4]),
            volume=Decimal(raw[5]),
        )
    
    @staticmethod
    def normalize_trade(raw: Dict[str, Any]) -> NormalizedTrade:
        """Normaliza trade (fill de ordem)."""
        return NormalizedTrade(
            trade_id=raw.get("tradeId", ""),
            order_id=raw.get("orderId", ""),
            symbol=raw.get("symbol", ""),
            side=OrderSide(raw.get("side", "buy").lower()),
            price=Decimal(raw.get("price", "0")),
            size=Decimal(raw.get("size", "0")),
            fee=Decimal(raw.get("fee", "0")),
            fee_currency=raw.get("feeCurrency", "USDT"),
            timestamp=datetime.fromtimestamp(int(raw.get("createdAt", 0)) / 1000, tz=timezone.utc),
            is_buyer_maker=raw.get("counterOrderId", "") != "",
        )
