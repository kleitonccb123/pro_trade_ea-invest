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


class KuCoinRateLimitManager:
    """
    Rate-limit manager baseado nos headers REAIS da KuCoin.

    A KuCoin usa um modelo de Resource Pool com janela de 30 segundos e
    devolve o estado atual em cada resposta:

        gw-ratelimit-limit     -> quota total da janela
        gw-ratelimit-remaining -> requisições restantes
        gw-ratelimit-reset     -> ms até o próximo reset

    Este manager lê esses headers após cada resposta e bloqueia
    automaticamente quando o pool está esgotado.
    """

    DEFAULT_LIMIT = 1800  # valor padrão KuCoin para contas gerais

    def __init__(self):
        self.limit: int = self.DEFAULT_LIMIT
        self.remaining: int = self.DEFAULT_LIMIT
        self.reset_ms: int = 30_000
        self._lock = asyncio.Lock()

    def update_from_headers(self, headers: dict) -> None:
        """Atualiza state a partir dos headers HTTP de resposta."""
        try:
            self.limit = int(headers.get("gw-ratelimit-limit", self.limit))
            self.remaining = int(headers.get("gw-ratelimit-remaining", self.remaining))
            self.reset_ms = int(headers.get("gw-ratelimit-reset", self.reset_ms))
            logger.debug(
                f"🔢 Rate-limit: {self.remaining}/{self.limit} "
                f"(reset em {self.reset_ms}ms)"
            )
        except (ValueError, TypeError) as exc:
            logger.warning(f"⚠️ Não foi possível ler headers de rate-limit: {exc}")

    async def wait_if_needed(self) -> None:
        """Bloqueia se o pool estiver esgotado até o próximo ciclo."""
        async with self._lock:
            if self.remaining <= 0:
                wait_s = max(self.reset_ms / 1000, 0.5)
                logger.warning(
                    f"⏸ Pool de rate-limit esgotado. "
                    f"Aguardando {wait_s:.1f}s..."
                )
                await asyncio.sleep(wait_s)
                # Após reset pessimista, assume pool cheio
                self.remaining = self.limit

    @property
    def is_throttled(self) -> bool:
        return self.remaining <= 0


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
        self.rate_limiter = KuCoinRateLimitManager()
        
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

        # Aguarda se pool esgotado ANTES de enviar request
        await self.rate_limiter.wait_if_needed()

        for attempt in range(1, max_retries + 1):
            try:
                response = await self.http_client.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    headers=headers,
                    params=params,
                    json=json_body,
                )

                # Atualiza state do rate-limit com headers reais de resposta
                self.rate_limiter.update_from_headers(dict(response.headers))

                # 429 = Rate Limited (pool esgotado no lado do servidor)
                if response.status_code == 429:
                    retry_after = float(
                        response.headers.get("Retry-After", 2 ** attempt)
                    )
                    # Força remaining=0 para que wait_if_needed bloqueie
                    self.rate_limiter.remaining = 0
                    self.rate_limiter.reset_ms = int(retry_after * 1000)
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
                        http_status=response.status_code,
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
            params={"symbol": symbol},
        )

    # ==================== IDEMPOTÊNCIA ====================

    async def get_order_by_client_oid(self, client_oid: str) -> Dict[str, Any]:
        """
        GET /api/v1/order/client-order/{clientOid}

        Busca ordem pelo clientOid gerado internamente.
        Usar ANTES de retry para garantir idempotência:

            existing = await client.get_order_by_client_oid(client_oid)
            if existing:           # ordem já chegou na KuCoin
                return existing    # não reenvia
        """
        return await self._make_request(
            "GET",
            f"/api/v1/order/client-order/{client_oid}",
        )

    # ==================== TP / SL (SPOT — OCO) ====================

    async def place_oco_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        take_profit_price: Decimal,
        stop_loss_price: Decimal,
        client_oid: Optional[str] = None,
        limit_price: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v3/oco/order  (KuCoin OCO — Spot)

        Cria par de ordens TP + SL que se cancelam mutuamente.

        Args:
            symbol: par, ex. "BTC-USDT"
            side: "buy" ou "sell" (geralmente "sell" para fechar posição)
            size: quantidade base
            take_profit_price: preço de take-profit (limit)
            stop_loss_price: preço de stop-loss (stop-limit)
            limit_price: preço limite para a perna de stop (padrão: stopPrice - 1%)
        """
        import uuid
        if not client_oid:
            client_oid = str(uuid.uuid4())

        # Se limit_price não fornecido, 1% abaixo do stopPrice (para sell SL)
        if limit_price is None:
            factor = Decimal("0.99") if side.lower() == "sell" else Decimal("1.01")
            limit_price = (stop_loss_price * factor).quantize(Decimal("0.01"))

        body = {
            "clientOid": client_oid,
            "symbol": symbol,
            "side": side.lower(),
            "type": "limit",
            "size": str(size),
            "price": str(take_profit_price),
            "stopPrice": str(stop_loss_price),
            "stopLimitPrice": str(limit_price),
            "tradeType": "TRADE",
        }

        logger.info(
            f"📌 OCO {symbol} {side} size={size} "
            f"TP={take_profit_price} SL={stop_loss_price}"
        )
        return await self._make_request("POST", "/api/v3/oco/order", json_body=body)

    # ==================== TP / SL (FUTURES) ====================

    async def place_futures_order_with_sl_tp(
        self,
        symbol: str,
        side: str,
        size: int,                      # contratos
        leverage: int,
        stop_loss_price: Optional[Decimal] = None,
        take_profit_price: Optional[Decimal] = None,
        order_type: str = "market",
        client_oid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/orders  (KuCoin Futures)

        Coloca ordem com TP e/ou SL nativos via campos stop/stopPrice.

        Campos específicos de Futures de acordo com a documentação:
            stop        : "up" (acionar acima) | "down" (acionar abaixo)
            stopPrice   : preço de acionamento
            reduceOnly  : True para garantir que é de fechamento
            closeOrder  : True para fechar toda a posição
        """
        import uuid
        if not client_oid:
            client_oid = str(uuid.uuid4())

        FUTURES_URL = "https://api-futures.kucoin.com"
        if self.sandbox:
            FUTURES_URL = "https://api-sandbox-futures.kucoin.com"

        body: Dict[str, Any] = {
            "clientOid": client_oid,
            "symbol": symbol,
            "side": side.lower(),
            "type": order_type,
            "size": size,
            "leverage": leverage,
        }

        if stop_loss_price:
            body["stop"] = "down" if side.lower() == "sell" else "up"
            body["stopPrice"] = str(stop_loss_price)
            body["reduceOnly"] = True
            body["closeOrder"] = False

        if take_profit_price:
            # TP separado (segunda requisição) pois a KuCoin Futures
            # não aceita TP+SL na mesma ordem. Chamador deve encadear.
            body["_pendingTakeProfit"] = str(take_profit_price)

        logger.info(
            f"📌 Futures {symbol} {side} size={size}x lev={leverage} "
            f"SL={stop_loss_price} TP={take_profit_price}"
        )

        # Usa base_url temporariamente (Futures usa host próprio)
        original_base = self.base_url
        self.base_url = FUTURES_URL
        try:
            result = await self._make_request("POST", "/api/v1/orders", json_body=body)
        finally:
            self.base_url = original_base

        return result

    # ==================== STOP ORDERS (Spot Stop-Limit) ====================

    async def place_stop_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,           # Limite de execução
        stop_price: Decimal,      # Gatilho (trigger)
        stop: str = "loss",       # "loss" (down) ou "entry" (up)
        client_oid: Optional[str] = None,
        time_in_force: str = "GTC",
        remark: str = "",
    ) -> Dict[str, Any]:
        """
        POST /api/v1/stop-order — Coloca ordem stop-limit para Spot.

        Args:
            symbol:      Par de moedas, ex. "BTC-USDT"
            side:        "buy" ou "sell"
            size:        Quantidade
            price:       Preço limite de execução
            stop_price:  Preço de gatilho (stopPrice)
            stop:        "loss" → ativa quando preço CAI até stopPrice (SL para long)
                         "entry" → ativa quando preço SOBE até stopPrice (SL para short)
            client_oid:  ID de idempotência
            remark:      Observação (ex: "SL:recordId")

        Returns:
            {"orderId": "...", "clientOid": "..."}
        """
        import uuid
        if not client_oid:
            client_oid = str(uuid.uuid4())

        body: Dict[str, Any] = {
            "clientOid":   client_oid,
            "symbol":      symbol,
            "side":        side.lower(),
            "type":        "limit",
            "size":        str(size),
            "price":       str(price),
            "stopPrice":   str(stop_price),
            "stop":        stop,            # "loss" ou "entry"
            "stopPriceType": "TP",          # TP = last traded price
            "timeInForce": time_in_force,
        }
        if remark:
            body["remark"] = remark[:100]  # KuCoin max 100 chars

        logger.info(
            "🛑 StopOrder %s %s size=%s limit=%s stop=%s trigger=%s",
            symbol, side, size, price, stop, stop_price,
        )
        return await self._make_request("POST", "/api/v1/stop-order", json_body=body)

    async def cancel_stop_order(self, order_id: str) -> Dict[str, Any]:
        """
        DELETE /api/v1/stop-order/{orderId} — Cancela ordem stop.

        Diferente das ordens normais, stop orders usam o endpoint /stop-order.
        """
        return await self._make_request("DELETE", f"/api/v1/stop-order/{order_id}")

    async def get_stop_order(self, order_id: str) -> Dict[str, Any]:
        """GET /api/v1/stop-order/{orderId}"""
        return await self._make_request("GET", f"/api/v1/stop-order/{order_id}")

    # ==================== MARKET DATA (Public) ====================

    async def get_symbols(self, market: str = "USDS") -> List[Dict[str, Any]]:
        """
        GET /api/v2/symbols — List available trading symbols.

        Args:
            market: Market filter (e.g. "USDS" for USDT pairs). None for all.
        Returns:
            List of symbol dicts with fields: symbol, name, baseCurrency,
            quoteCurrency, baseMinSize, quoteMinSize, priceIncrement, etc.
        """
        params: Dict[str, Any] = {}
        if market:
            params["market"] = market
        return await self._make_request("GET", "/api/v2/symbols", params=params)

    async def get_24h_stats(self, symbol: str) -> Dict[str, Any]:
        """
        GET /api/v1/market/stats — 24-hour stats for a symbol.

        Returns: changeRate, changePrice, high, low, vol, volValue,
                 last, averagePrice, buy, sell, etc.
        """
        return await self._make_request(
            "GET", "/api/v1/market/stats", params={"symbol": symbol}
        )

    async def get_orderbook_l2(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """
        GET /api/v1/market/orderbook/level2_{depth} — Order book snapshot.

        Args:
            symbol: Trading pair, e.g. "BTC-USDT"
            depth:  20 or 100
        Returns:
            {"sequence": ..., "bids": [[price, size], ...], "asks": [...]}
        """
        if depth not in (20, 100):
            depth = 20
        return await self._make_request(
            "GET", f"/api/v1/market/orderbook/level2_{depth}",
            params={"symbol": symbol},
        )

    async def get_futures_contracts(self) -> List[Dict[str, Any]]:
        """
        GET /api/v1/contracts/active — List active futures contracts.

        Uses the KuCoin Futures API host.
        Returns list of contract dicts: symbol, rootSymbol, type,
        maxLeverage, tickSize, lotSize, etc.
        """
        FUTURES_URL = "https://api-futures.kucoin.com"
        if self.sandbox:
            FUTURES_URL = "https://api-sandbox-futures.kucoin.com"

        original_base = self.base_url
        self.base_url = FUTURES_URL
        try:
            return await self._make_request("GET", "/api/v1/contracts/active")
        finally:
            self.base_url = original_base

    # ==================== UTILITIES ====================

    @property
    def rate_limit_status(self) -> Dict[str, Any]:
        """Retorna estado atual do rate limiter para monitoramento."""
        return {
            "limit": self.rate_limiter.limit,
            "remaining": self.rate_limiter.remaining,
            "reset_ms": self.rate_limiter.reset_ms,
            "throttled": self.rate_limiter.is_throttled,
        }
    
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
