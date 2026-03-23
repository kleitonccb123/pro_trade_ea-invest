"""
KuCoin Models - Dataclasses DTOs

Define estruturas de dados normalizadas para comunicação com KuCoin.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class KuCoinBalance:
    """Modelo normalizado de saldo de uma moeda."""
    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal
    timestamp: datetime

    def __post_init__(self):
        """Valida que total = free + locked."""
        if self.total != self.free + self.locked:
            raise ValueError(
                f"Saldo inconsistente: {self.total} != {self.free} + {self.locked}"
            )


@dataclass
class KuCoinOrder:
    """Modelo normalizado de uma ordem."""
    order_id: str
    symbol: str
    side: str  # BUY / SELL
    order_type: str  # LIMIT / MARKET
    price: Optional[Decimal] = None
    size: Decimal = Decimal("0")
    filled: Decimal = Decimal("0")
    remaining: Decimal = Decimal("0")
    status: str = "OPEN"  # OPEN / CLOSED / CANCELLED
    fee: Decimal = Decimal("0")
    fee_currency: str = "USDT"
    created_at: datetime = field(default_factory=datetime.now)
    client_oid: Optional[str] = None

    def __post_init__(self):
        """Valida campos obrigatórios."""
        if not self.order_id:
            raise ValueError("order_id é obrigatório")
        if not self.symbol:
            raise ValueError("symbol é obrigatório")


@dataclass
class KuCoinTicker:
    """Modelo normalizado de ticker (preços atuais)."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    timestamp: datetime


@dataclass
class KuCoinCandle:
    """Modelo normalizado de candle (OHLCV)."""
    timestamp: datetime
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
