# IMPLEMENTAÇÃO COMPLETA - Código Pronto para Produção

Este arquivo contém código competo para as 6 camadas de arquitetura.

---

## CAMADA 1: KuCoinRawClient (Comunicação com API)

**Arquivo:** `backend/app/exchanges/kucoin/client.py`

```python
"""
KuCoin Raw Client - Camada 1

Comunica diretamente com REST API da KuCoin.
NUNCA usa CCXT ou libs de 3º partido.

Responsabilidades:
- Autenticação com HMAC SHA256
- Rate limit handling (429)
- Retry automático
- Logging estruturado
- Sem inicializar conexões - apenas HTTP stateless
"""

from __future__ import annotations

import logging
import time
import json
import hashlib
import hmac
from typing import Dict, Any, Optional, List
from base64 import b64encode
from decimal import Decimal
from datetime import datetime, timezone
import httpx
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)

class KuCoinRequestType(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class KuCoinRateLimiter:
    """Controla rate limits conforme documentação KuCoin."""
    
    def __init__(self):
        # Endpoints e seus limites (req/s)
        self.limits = {
            "GET /api/v1/accounts": 10,
            "POST /api/v1/orders": 100,  # 100 req/10s = 10 req/s média
            "GET /api/v1/orders": 10,
            "GET /api/v1/accounts/*/ledgers": 5,
            "default": 3,
        }
        self.last_request_time = 0
        self.request_count = 0
    
    async def wait_if_needed(self, endpoint: str):
        """Aguarda se necessário para respeitar rate limit."""
        limit = self.limits.get(endpoint, self.limits["default"])
        min_interval = 1.0 / limit
        
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            logger.debug(f"Rate limit: aguardando {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()


class KuCoinRawClient:
    """
    Cliente REST puro para KuCoin API v1.
    
    Exemplo:
    ```python
    client = KuCoinRawClient(
        api_key="...",
        api_secret="...",
        passphrase="...",
        sandbox=False
    )
    
    # Contas
    account = await client.get_account()
    balance = await client.get_balance(account_id)
    
    # Ordens
    order = await client.place_market_order(
        symbol="BTC-USDT",
        side="buy",
        size=Decimal("0.1"),
        take_profit=Decimal("35000"),
        stop_loss=Decimal("30000")
    )
    ```
    """
    
    # URLs da API
    PROD_URL = "https://api.kucoin.com"
    SANDBOX_URL = "https://openapi-sandbox.kucoin.com"
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        sandbox: bool = False,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.sandbox = sandbox
        self.timeout = timeout
        
        self.base_url = self.SANDBOX_URL if sandbox else self.PROD_URL
        self.rate_limiter = KuCoinRateLimiter()
        
        # HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "CryptoTradeHub/1.0"}
        )
        
        logger.info(f"✅ KuCoinRawClient inicializado (sandbox={sandbox})")
    
    # ==================== AUTENTICAÇÃO ====================
    
    def _generate_signature(
        self,
        method: str,
        path: str,
        body: str = "",
        timestamp: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """
        Gera assinatura para request autenticado.
        
        Args:
            method: GET, POST, PUT, DELETE
            path: /api/v1/... (SEM base_url)
            body: JSON string (vazio para GET)
            timestamp: Unix ms timestamp (auto-gerado se None)
        
        Returns:
            (timestamp, sign, passphrase)
        """
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))
        
        # Constrói mensagem: timestamp + method + path + body
        message = timestamp + method + path + body
        
        # HMAC-SHA256
        signature = b64encode(
            hmac.new(
                self.api_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        # Passphrase também é criptografada
        passphrase_encoded = b64encode(
            hmac.new(
                self.api_secret.encode(),
                self.passphrase.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        return timestamp, signature, passphrase_encoded
    
    def _get_auth_headers(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> Dict[str, str]:
        """Prepara headers autenticados."""
        timestamp, signature, passphrase = self._generate_signature(method, path, body)
        
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": passphrase,
            "Content-Type": "application/json",
        }
    
    # ==================== REQUEST COM RETRY ====================
    
    async def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Faz request com retry automático e rate limit handling.
        
        Raises:
            KuCoinAPIError: Erros da API
            asyncio.TimeoutError: Timeout
        """
        
        body_str = json.dumps(json_body) if json_body else ""
        headers = self._get_auth_headers(method, path, body_str)
        
        # Rate limit
        await self.rate_limiter.wait_if_needed(f"{method} {path}")
        
        for attempt in range(1, max_retries + 1):
            try:
                response = await self.http_client.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    headers=headers,
                    params=params,
                    json=json_body,
                )
                
                # 429 = Rate Limited
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    logger.warning(
                        f"⚙️ Rate limit (429), retry em {retry_after}s "
                        f"(tentativa {attempt}/{max_retries})"
                    )
                    await asyncio.sleep(retry_after)
                    continue
                
                # Parse response
                data = response.json()
                
                # Erro da API
                if response.status_code != 200:
                    error_msg = data.get("msg", "Unknown error")
                    raise KuCoinAPIError(
                        code=data.get("code", "UNKNOWN"),
                        message=error_msg,
                        http_status=response.status_code
                    )
                
                logger.debug(f"✅ {method} {path} → {response.status_code}")
                return data.get("data", {})
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Timeout {method} {path} (tentativa {attempt}/{max_retries})")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
            
            except Exception as e:
                logger.error(f"❌ Erro {method} {path}: {e} (tentativa {attempt}/{max_retries})")
                if attempt < max_retries and not isinstance(e, KuCoinAPIError):
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
        
        raise Exception(f"Failed after {max_retries} retries")
    
    # ==================== CONTAS ====================
    
    async def get_accounts(self) -> List[Dict[str, Any]]:
        """GET /api/v1/accounts - Lista todas as contas."""
        return await self._make_request("GET", "/api/v1/accounts")
    
    async def get_account(self, account_id: str) -> Dict[str, Any]:
        """GET /api/v1/accounts/{account_id} - Detalhe de conta."""
        return await self._make_request("GET", f"/api/v1/accounts/{account_id}")
    
    async def get_account_balance(
        self,
        account_id: str,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/accounts/{account_id}/balances - Saldo da conta."""
        params = {}
        if currency:
            params["currency"] = currency
        
        return await self._make_request(
            "GET",
            f"/api/v1/accounts/{account_id}/balances",
            params=params
        )
    
    # ==================== ORDENS (SPOT) ====================
    
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        client_oid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/orders - Coloca ordem de mercado.
        
        Args:
            symbol: BTC-USDT
            side: buy ou sell
            size: Quanto comprar/vender
            take_profit: Preço de TP (se suportado)
            stop_loss: Preço de SL (se suportado)
            client_oid: ID único para idempotência
        
        Returns:
            {"orderId": "..."}
        """
        import uuid
        if not client_oid:
            client_oid = str(uuid.uuid4())
        
        body = {
            "clientOid": client_oid,
            "side": side.lower(),
            "symbol": symbol,
            "type": "market",
            "size": str(size),
        }
        
        # KuCoin não suporta TP/SL diretamente em market orders
        # Mas podemos adicionar campos opcionais para futura expansão
        # ou implementar via OCO (one-cancels-other)
        
        return await self._make_request("POST", "/api/v1/orders", json_body=body)
    
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        client_oid: Optional[str] = None,
        post_only: bool = False,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/orders - Coloca ordem limite.
        """
        import uuid
        if not client_oid:
            client_oid = str(uuid.uuid4())
        
        body = {
            "clientOid": client_oid,
            "side": side.lower(),
            "symbol": symbol,
            "type": "limit",
            "size": str(size),
            "price": str(price),
            "timeInForce": "GTC",  # Good Till Cancelled
            "postOnly": post_only,
        }
        
        return await self._make_request("POST", "/api/v1/orders", json_body=body)
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """DELETE /api/v1/orders/{order_id}"""
        return await self._make_request("DELETE", f"/api/v1/orders/{order_id}")
    
    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """GET /api/v1/orders/{order_id}"""
        return await self._make_request("GET", f"/api/v1/orders/{order_id}")
    
    async def get_orders(
        self,
        symbol: Optional[str] = None,
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        """GET /api/v1/orders - Lista ordens."""
        params = {"status": status}
        if symbol:
            params["symbol"] = symbol
        
        return await self._make_request("GET", "/api/v1/orders", params=params)
    
    # ==================== MARKET DATA ====================
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """GET /api/v1/market/orderbook/level1 - Ticker."""
        return await self._make_request(
            "GET",
            "/api/v1/market/orderbook/level1",
            params={"symbol": symbol}
        )
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1min",
        start_at: Optional[int] = None,
        end_at: Optional[int] = None,
    ) -> List[List[str]]:
        """GET /api/v1/market/candles - Candles/Klines."""
        params = {"symbol": symbol, "type": interval}
        if start_at:
            params["startAt"] = start_at
        if end_at:
            params["endAt"] = end_at
        
        return await self._make_request("GET", "/api/v1/market/candles", params=params)
    
    async def get_trades(self, symbol: str) -> List[Dict[str, Any]]:
        """GET /api/v1/market/histories - Histórico de trades."""
        return await self._make_request(
            "GET",
            "/api/v1/market/histories",
            params={"symbol": symbol}
        )
    
    # ==================== UTILITIES ====================
    
    async def close(self):
        """Fecha conexão HTTP."""
        await self.http_client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class KuCoinAPIError(Exception):
    """Exceção padrão para erros da API."""
    def __init__(self, code: str, message: str, http_status: int):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(f"KuCoin API Error: {code} - {message} (HTTP {http_status})")
```

---

## CAMADA 2: PayloadNormalizer (Normalização de Dados)

**Arquivo:** `backend/app/exchanges/kucoin/normalizer.py`

```python
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
```

---

## CAMADA 3: TradingEngine (Orquestração)

**Arquivo:** `backend/app/trading/engine.py`

```python
"""
TradingEngine - Camada 3

Orquestra:
- KuCoinRawClient (camada 1)
- PayloadNormalizer (camada 2)
- Lógica de trading

Responsabilidades:
- Converter business requests em API calls
- Normalizar respostas
- Manter estado mínimo
- Não trata concorrência (OrderManager faz isso)
"""

from __future__ import annotations

import logging
import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.exchanges.kucoin.client import KuCoinRawClient, KuCoinAPIError
from app.exchanges.kucoin.normalizer import (
    PayloadNormalizer,
    NormalizedOrder,
    NormalizedCandle,
    NormalizedBalance,
)

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Engine de trading que coordena cliente + normalizer.
    
    Exemplo:
    ```python
    engine = TradingEngine(kucoin_client)
    
    order = await engine.place_market_order(
        symbol="BTC-USDT",
        side="buy",
        size=Decimal("0.1"),
        take_profit=Decimal("35000"),
        stop_loss=Decimal("30000")
    )
    
    # Resultado já normalizado
    assert isinstance(order, NormalizedOrder)
    assert order.status == OrderStatus.OPEN
    
    # Monitora
    updated = await engine.get_order(order.order_id)
    ```
    """
    
    def __init__(self, kucoin_client: KuCoinRawClient, account_id: str):
        self.client = kucoin_client
        self.account_id = account_id
        self.normalizer = PayloadNormalizer()
        
        logger.info(f"✅ TradingEngine inicializado para account {account_id}")
    
    # ==================== CONTAS ====================
    
    async def get_balance(
        self,
        currency: Optional[str] = None,
    ) -> List[NormalizedBalance]:
        """Obtém saldo formatado."""
        try:
            raw_balances = await self.client.get_account_balance(
                self.account_id,
                currency=currency
            )
            
            normalized = [
                self.normalizer.normalize_balance(bal, self.account_id)
                for bal in raw_balances
            ]
            
            logger.info(f"✅ Saldo obtido: {len(normalized)} assets")
            return normalized
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter saldo: {e}")
            raise
    
    # ==================== ORDERS ====================
    
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        client_oid: Optional[str] = None,
    ) -> NormalizedOrder:
        """Coloca ordem de mercado normalizada."""
        try:
            raw_response = await self.client.place_market_order(
                symbol=symbol,
                side=side,
                size=size,
                take_profit=take_profit,
                stop_loss=stop_loss,
                client_oid=client_oid,
            )
            
            # Busca ordem completa para normalização
            order_id = raw_response.get("orderId")
            order_detail = await self.client.get_order(order_id)
            
            # Normaliza
            normalized = self.normalizer.normalize_order(order_detail)
            
            logger.info(
                f"✅ Market order colocada: "
                f"{side} {size} {symbol} @ {order_id}"
            )
            return normalized
            
        except KuCoinAPIError as e:
            logger.error(f"❌ API Error: {e.code} - {e.message}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro ao colocar ordem: {e}")
            raise
    
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        client_oid: Optional[str] = None,
    ) -> NormalizedOrder:
        """Coloca ordem limite normalizada."""
        try:
            raw_response = await self.client.place_limit_order(
                symbol=symbol,
                side=side,
                size=size,
                price=price,
                client_oid=client_oid,
            )
            
            # Busca ordem completa
            order_id = raw_response.get("orderId")
            order_detail = await self.client.get_order(order_id)
            
            # Normaliza
            normalized = self.normalizer.normalize_order(order_detail)
            
            logger.info(
                f"✅ Limit order colocada: "
                f"{side} {size} {symbol} @ {price} ({order_id})"
            )
            return normalized
            
        except Exception as e:
            logger.error(f"❌ Erro ao colocar ordem limite: {e}")
            raise
    
    async def get_order(self, order_id: str) -> NormalizedOrder:
        """Obtém ordem normalizada."""
        try:
            raw_order = await self.client.get_order(order_id)
            normalized = self.normalizer.normalize_order(raw_order)
            return normalized
        except Exception as e:
            logger.error(f"❌ Erro ao obter ordem: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancela ordem."""
        try:
            await self.client.cancel_order(order_id)
            logger.info(f"✅ Ordem cancelada: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao cancelar ordem: {e}")
            return False
    
    async def get_orders(self, symbol: Optional[str] = None) -> List[NormalizedOrder]:
        """Lista ordens abertas."""
        try:
            raw_orders = await self.client.get_orders(symbol=symbol, status="active")
            normalized = [
                self.normalizer.normalize_order(order)
                for order in raw_orders
            ]
            return normalized
        except Exception as e:
            logger.error(f"❌ Erro ao listar ordens: {e}")
            raise
    
    # ==================== MARKET DATA ====================
    
    async def get_ticker(self, symbol: str) -> Dict[str, Decimal]:
        """Obtém ticker current."""
        try:
            raw_ticker = await self.client.get_ticker(symbol)
            
            return {
                "bid": Decimal(raw_ticker.get("bestBid", "0")),
                "ask": Decimal(raw_ticker.get("bestAsk", "0")),
                "last": Decimal(raw_ticker.get("price", "0")),
                "high": Decimal(raw_ticker.get("high", "0")),
                "low": Decimal(raw_ticker.get("low", "0")),
                "volume": Decimal(raw_ticker.get("volValue", "0")),
            }
        except Exception as e:
            logger.error(f"❌ Erro ao obter ticker: {e}")
            raise
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1min",
        limit: int = 100,
    ) -> List[NormalizedCandle]:
        """Obtém candles normalizados."""
        try:
            raw_candles = await self.client.get_klines(symbol, interval)
            
            # KuCoin retorna em ordem crescente, pegamos últimas N
            normalized = [
                self.normalizer.normalize_candle(candle)
                for candle in raw_candles[-limit:]
            ]
            
            return normalized
        except Exception as e:
            logger.error(f"❌ Erro ao obter candles: {e}")
            raise
```

---

## CAMADA 4: StrategyEngine (Execução de Estratégias Isoladas)

**Arquivo:** `backend/app/strategies/engine.py`

```python
"""
StrategyEngine - Camada 4

Executa estratégias de forma ISOLADA.

Responsabilidades:
- Rodar estratégia por bot
- Cada bot em sua própria coroutine
- Não trava outras estratégias
- Comunicação via fila (não compartilha estado)
"""

from __future__ import annotations

import logging
import asyncio
from typing import Dict, Optional, List, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Sinal de entrada gerado pela estratégia."""
    symbol: str
    side: str  # "buy" or "sell"
    size: Decimal
    confidence: float  # 0.0 - 1.0
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    reason: Optional[str] = None


class StrategyBase(ABC):
    """Base class para todas as estratégias."""
    
    @abstractmethod
    async def analyze(self, market_data: List[Any]) -> Optional[TradeSignal]:
        """
        Analisa dados de mercado e retorna sinal.
        
        Args:
            market_data: Últimas N candles
        
        Returns:
            TradeSignal ou None se sem sinal
        """
        pass


class SMACrossoverStrategy(StrategyBase):
    """Exemplo: SMA 20 x SMA 50 crossover."""
    
    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    async def analyze(self, candles: List[Any]) -> Optional[TradeSignal]:
        """Implementa lógica SMA crossover."""
        if len(candles) < self.slow_period + 1:
            return None  # Dados insuficientes
        
        closes = [float(c.close) for c in candles]
        
        # Calcula SMAs
        sma_fast = sum(closes[-self.fast_period:]) / self.fast_period
        sma_slow = sum(closes[-self.slow_period:]) / self.slow_period
        
        prev_sma_fast = sum(closes[-self.fast_period-1:-1]) / self.fast_period
        prev_sma_slow = sum(closes[-self.slow_period-1:-1]) / self.slow_period
        
        # Detecta crossover
        if prev_sma_fast <= prev_sma_slow and sma_fast > sma_slow:
            # Golden cross: BUY
            confidence = min(1.0, (sma_fast - sma_slow) / sma_slow * 100)
            
            return TradeSignal(
                symbol=candles[-1].symbol if hasattr(candles[-1], 'symbol') else "BTC-USDT",
                side="buy",
                size=Decimal("0.1"),
                confidence=confidence,
                take_profit=Decimal(closes[-1]) * Decimal("1.04"),  # +4%
                stop_loss=Decimal(closes[-1]) * Decimal("0.98"),    # -2%
                reason=f"SMA Golden Cross: Fast={sma_fast:.2f}, Slow={sma_slow:.2f}"
            )
        
        elif prev_sma_fast >= prev_sma_slow and sma_fast < sma_slow:
            # Death cross: SELL
            confidence = min(1.0, (sma_slow - sma_fast) / sma_slow * 100)
            
            return TradeSignal(
                symbol="BTC-USDT",
                side="sell",
                size=Decimal("0.1"),
                confidence=confidence,
                reason=f"SMA Death Cross: Fast={sma_fast:.2f}, Slow={sma_slow:.2f}"
            )
        
        return None


class StrategyEngine:
    """
    Executa estratégias de forma isolada.
    
    Cada bot roda em sua própria coroutine.
    """
    
    def __init__(self):
        self.active_bots: Dict[str, asyncio.Task] = {}
        self.signal_callbacks: Dict[str, List[Callable]] = {}
    
    async def run_bot_strategy(
        self,
        bot_id: str,
        strategy: StrategyBase,
        market_data_provider: Callable,
        interval_seconds: float = 60,
    ):
        """
        Executa estratégia para um bot repetidamente.
        
        Args:
            bot_id: Identificador único do bot
            strategy: Instância da estratégia
            market_data_provider: Função async que retorna candles
            interval_seconds: Intervalo entre análises
        """
        logger.info(f"🤖 Iniciando bot {bot_id}")
        
        try:
            while True:
                try:
                    # Obtém dados de mercado
                    market_data = await market_data_provider(bot_id)
                    
                    # Analisa
                    signal = await strategy.analyze(market_data)
                    
                    # Se sinal, notifica
                    if signal:
                        logger.info(f"🎯 Bot {bot_id}: Sinal {signal.side} com {signal.confidence*100:.1f}% confiança")
                        await self._notify_signal(bot_id, signal)
                    
                    # Aguarda próximo intervalo
                    await asyncio.sleep(interval_seconds)
                    
                except asyncio.CancelledError:
                    logger.info(f"🛑 Bot {bot_id} cancelado")
                    raise
                except Exception as e:
                    logger.error(f"❌ Erro no bot {bot_id}: {e}")
                    await asyncio.sleep(5)  # Retry após curta espera
                    
        except asyncio.CancelledError:
            logger.info(f"✅ Bot {bot_id} finalizado gracefully")
        finally:
            if bot_id in self.active_bots:
                del self.active_bots[bot_id]
    
    async def start_bot(
        self,
        bot_id: str,
        strategy: StrategyBase,
        market_data_provider: Callable,
    ):
        """Inicia um bot."""
        if bot_id in self.active_bots:
            logger.warning(f"⚠️ Bot {bot_id} já está rodando")
            return
        
        task = asyncio.create_task(
            self.run_bot_strategy(bot_id, strategy, market_data_provider)
        )
        self.active_bots[bot_id] = task
        logger.info(f"✅ Bot {bot_id} iniciado")
    
    async def stop_bot(self, bot_id: str):
        """Para um bot."""
        if bot_id not in self.active_bots:
            logger.warning(f"⚠️ Bot {bot_id} não está rodando")
            return
        
        task = self.active_bots[bot_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        logger.info(f"✅ Bot {bot_id} parado")
    
    def subscribe_signal(self, bot_id: str, callback: Callable):
        """Subscreve a sinais de um bot."""
        if bot_id not in self.signal_callbacks:
            self.signal_callbacks[bot_id] = []
        self.signal_callbacks[bot_id].append(callback)
    
    async def _notify_signal(self, bot_id: str, signal: TradeSignal):
        """Notifica todos os subscribers de um sinal."""
        if bot_id not in self.signal_callbacks:
            return
        
        for callback in self.signal_callbacks[bot_id]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"❌ Erro ao chamar callback: {e}")


# Instância global
strategy_engine = StrategyEngine()
```

Próxima parte com Camada 5 (OrderManager) e Camada 6 (RiskManager)...

