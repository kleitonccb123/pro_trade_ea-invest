"""
KuCoin REST client — DOC_04 §4.

Features:
  - HMAC-SHA256 signing via integrations.kucoin.signing
  - Sliding-window rate limiting via KuCoinRateLimiter
  - Exponential-backoff retry for 5xx / 429
  - get_ws_token() — fetches WebSocket connection token

Usage:
    client = KuCoinRESTClient(api_key, api_secret, api_passphrase)
    order  = await client.place_market_order("BTC-USDT", "buy", funds=100)
    await client.close()
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import List, Optional

import aiohttp

from app.integrations.kucoin.rate_limiter import KuCoinRateLimiter, GatewayRateLimitState
from app.integrations.kucoin.signing import build_auth_headers

logger = logging.getLogger("kucoin.rest")

BASE_URL    = "https://api.kucoin.com"
SANDBOX_URL = "https://openapi-sandbox.kucoin.com"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES   = 3
BACKOFF_BASE  = 2.0  # seconds

# DOC-K02: Gateway rate-limit state — singleton que lê headers gw-ratelimit-*
# Compartilhado por todas as requisições desta instância da engine.
_GATEWAY_STATE = GatewayRateLimitState()

# Aliases de compatibilidade (usados por código legado que lê os globals)
def _update_gateway_state(headers) -> None:
    """DOC-K02: Delega para _GATEWAY_STATE.update_from_headers()."""
    _GATEWAY_STATE.update_from_headers(dict(headers))


def get_gateway_rate_limit_status() -> dict:
    """DOC-K02: Retorna estado atual do gateway rate limit para o dashboard."""
    return {
        "gateway_limit": _GATEWAY_STATE.limit,
        "gateway_remaining": _GATEWAY_STATE.remaining,
        "gateway_reset_ms": _GATEWAY_STATE.reset_at_ms,
        "usage_pct": round(_GATEWAY_STATE.usage_pct(), 4),
        "seconds_until_reset": round(_GATEWAY_STATE.seconds_until_reset(), 1),
        "health": "ok" if _GATEWAY_STATE.usage_pct() < 0.8 else (
            "throttling" if _GATEWAY_STATE.usage_pct() < 0.95 else "critical"
        ),
    }

TIMEFRAME_SECONDS = {
    "1min": 60,   "3min": 180,  "5min": 300,
    "15min": 900, "30min": 1800,
    "1hour": 3600, "2hour": 7200, "4hour": 14400,
    "6hour": 21600, "8hour": 28800, "12hour": 43200,
    "1day": 86400, "1week": 604800,
    # Aliases used by the engine
    "1m": 60,  "5m": 300, "15m": 900,
    "1h": 3600, "4h": 14400, "1d": 86400,
}


# ── Custom exceptions ─────────────────────────────────────────────────────────

class KuCoinAPIError(Exception):
    """Raised when KuCoin returns a business-logic error (non-200000 code)."""

    def __init__(self, status: int, code: str, message: str, endpoint: str):
        self.status   = status
        self.code     = code
        self.message  = message
        self.endpoint = endpoint
        super().__init__(f"KuCoin API Error [{code}] on {endpoint}: {message}")


class KuCoinNetworkError(Exception):
    """Raised after all retries are exhausted due to network issues."""


# ── Client ────────────────────────────────────────────────────────────────────

class KuCoinRESTClient:
    """
    Async KuCoin REST client.

    One instance should be shared by a single BotWorker (not across workers,
    because rate-limit state is stored in module-level buckets anyway).
    """

    def __init__(
        self,
        api_key:        str,
        api_secret:     str,
        api_passphrase: str,
        sandbox: bool = False,
    ):
        self.api_key        = api_key
        self.api_secret     = api_secret
        self.api_passphrase = api_passphrase
        self.base_url       = SANDBOX_URL if sandbox else BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None

    # DOC-K01: Prevent accidental credential leakage via repr/str/logging.
    # If this object is ever passed to logger.error() or str(), secrets stay hidden.
    def __repr__(self) -> str:
        key_hint = f"...{self.api_key[-4:]}" if self.api_key else "<empty>"
        mode     = "sandbox" if self.base_url == SANDBOX_URL else "production"
        return f"<KuCoinRESTClient key={key_hint} mode={mode}>"

    def __str__(self) -> str:
        return self.__repr__()

    # ── Session ───────────────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "CryptoTradeHub/1.0"},
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Core request ─────────────────────────────────────────────────────────

    async def request(
        self,
        method:        str,
        endpoint:      str,
        params:        Optional[dict] = None,
        body:          Optional[dict] = None,
        authenticated: bool = True,
    ) -> dict:
        """
        Signed request with rate limiting and exponential-backoff retry.

        Returns the `data` field from a successful KuCoin response.
        Raises KuCoinAPIError for business errors, KuCoinNetworkError for
        persistent network failures.
        """
        body_str = (
            json.dumps(body, separators=(",", ":")) if body else ""
        )
        url = f"{self.base_url}{endpoint}"

        headers: dict = {}
        if authenticated:
            headers = build_auth_headers(
                self.api_key,
                self.api_secret,
                self.api_passphrase,
                method,
                endpoint,
                body_str,
            )

        # === DOC-K02: Throttle preventivo baseado no estado real do gateway ===
        usage = _GATEWAY_STATE.usage_pct()
        if usage > 0.85:
            wait = _GATEWAY_STATE.seconds_until_reset() * 0.1
            if wait > 0:
                logger.warning(
                    "Rate limit gateway em %.0f%% — aguardando %.2fs",
                    usage * 100, wait,
                )
                await asyncio.sleep(wait)

        # Respect rate limit before the first attempt (sliding-window local)
        await KuCoinRateLimiter.acquire(endpoint)

        last_exc: Exception = RuntimeError("No attempts made")

        for attempt in range(MAX_RETRIES + 1):
            try:
                session = await self._get_session()
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=body_str or None,
                    headers=headers,
                ) as response:

                    # DOC-K02: Atualiza estado do gateway com headers de TODA resposta
                    _GATEWAY_STATE.update_from_headers(dict(response.headers))

                    # ── Rate-limit response ──────────────────────────────────
                    if response.status == 429:
                        retry_after_hdr = response.headers.get("Retry-After")
                        if retry_after_hdr:
                            wait_429 = float(retry_after_hdr)
                        else:
                            wait_429 = max(_GATEWAY_STATE.seconds_until_reset() + 1.0, 5.0)
                        logger.warning(
                            "❌ 429 em %s (remaining=%d). Aguardando %.1fs",
                            endpoint, _GATEWAY_STATE.remaining, wait_429,
                        )
                        await asyncio.sleep(wait_429)
                        # Re-acquire slot after waiting
                        await KuCoinRateLimiter.acquire(endpoint)
                        continue

                    # ── Retryable server errors ──────────────────────────────
                    if response.status in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                        wait = BACKOFF_BASE ** attempt
                        logger.warning(
                            f"Status {response.status} em {endpoint}, "
                            f"retry {attempt + 1}/{MAX_RETRIES} em {wait:.1f}s"
                        )
                        await asyncio.sleep(wait)
                        continue

                    data = await response.json(content_type=None)

                    # ── HTTP-level error ─────────────────────────────────────
                    if response.status >= 400:
                        logger.error(
                            f"KuCoin HTTP {response.status} em {endpoint}: {data}"
                        )
                        raise KuCoinAPIError(
                            status=response.status,
                            code=str(data.get("code", response.status)),
                            message=data.get("msg", "Unknown error"),
                            endpoint=endpoint,
                        )

                    # ── Business-logic error (HTTP 200 but code != 200000) ───
                    if str(data.get("code")) != "200000":
                        raise KuCoinAPIError(
                            status=200,
                            code=str(data.get("code", "?")),
                            message=str(data.get("msg", data)),
                            endpoint=endpoint,
                        )

                    return data.get("data", data)

            except KuCoinAPIError:
                raise  # Never retry business errors

            except aiohttp.ClientError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(
                        f"Erro de rede em {endpoint}: {exc}. "
                        f"Retry em {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                else:
                    raise KuCoinNetworkError(
                        f"Falha persistente em {endpoint}: {exc}"
                    ) from exc

        raise KuCoinNetworkError(
            f"Máximo de tentativas atingido para {endpoint}"
        ) from last_exc

    # ── WebSocket token ───────────────────────────────────────────────────────

    async def get_ws_token(
        self, private: bool = False
    ) -> tuple[str, str, float]:
        """
        Obtain a KuCoin WebSocket connection token.

        Returns:
            (token, ws_url_with_token, ping_interval_seconds)

        Private token required for order-update and balance topics.
        """
        endpoint = "/api/v1/bullet-private" if private else "/api/v1/bullet-public"
        data = await self.request("POST", endpoint, body={}, authenticated=private)

        token  = data["token"]
        server = data["instanceServers"][0]
        ws_url = f"{server['endpoint']}?token={token}"
        ping_interval_s = server["pingInterval"] / 1000.0  # ms → s

        return token, ws_url, ping_interval_s

    # ── Market data ───────────────────────────────────────────────────────────

    async def get_ticker(self, pair: str) -> dict:
        """Return market stats for the pair (last price, 24h vol, etc.)."""
        return await self.request(
            "GET", "/api/v1/market/stats",
            params={"symbol": pair},
            authenticated=False,
        )

    async def get_price(self, pair: str) -> float:
        """Convenience: return the latest price as a float."""
        ticker = await self.get_ticker(pair)
        return float(ticker.get("lastTradedPrice") or ticker.get("last") or 0)

    async def get_candles(
        self,
        pair:      str,
        timeframe: str = "1hour",
        limit:     int = 200,
    ) -> List[List[float]]:
        """
        Return OHLCV candles, oldest-first.

        Each element: [timestamp, open, close, high, low, volume, turnover]
        """
        tf_seconds = TIMEFRAME_SECONDS.get(timeframe, 3600)
        end   = int(time.time())
        start = end - (tf_seconds * limit)

        raw = await self.request(
            "GET", "/api/v1/market/candles",
            params={
                "symbol": pair,
                "type":   timeframe,
                "startAt": start,
                "endAt":   end,
            },
            authenticated=False,
        )
        # KuCoin returns newest-first; each row is [str, str, ...]
        candles = [[float(v) for v in row] for row in (raw or [])]
        candles.reverse()  # oldest-first
        return candles[-limit:]

    async def get_orderbook(self, pair: str, depth: int = 20) -> dict:
        """Return the order book (up to `depth` levels)."""
        endpoint = f"/api/v1/market/orderbook/level2_{depth}"
        return await self.request(
            "GET", endpoint,
            params={"symbol": pair},
            authenticated=False,
        )

    # ── Account ───────────────────────────────────────────────────────────────

    async def get_account_balances(self) -> list:
        """Return trade-account balances (requires authentication)."""
        data = await self.request(
            "GET", "/api/v1/accounts",
            params={"type": "trade"},
        )
        return data if isinstance(data, list) else data.get("items", [])

    async def get_balance(self, currency: str) -> float:
        """Return available balance for a specific currency."""
        balances = await self.get_account_balances()
        for b in balances:
            if b.get("currency") == currency and b.get("type") == "trade":
                return float(b.get("available", 0))
        return 0.0

    # ── Orders ────────────────────────────────────────────────────────────────

    async def place_market_order(
        self,
        pair:  str,
        side:  str,
        size:  Optional[float] = None,
        funds: Optional[float] = None,
        client_oid: Optional[str] = None,   # DOC-K04: accept pre-generated clientOid
    ) -> dict:
        """
        Place a market order.

        DOC-K04: Pass ``client_oid`` generated BEFORE this call (via
        OrderIntentStore.generate_client_oid()) to ensure idempotency on retry.
        If None, a new UUID is generated (backwards-compat, NOT idempotent on retry).

        For buy orders, prefer `funds` (USDT amount).
        For sell orders, use `size` (base-currency quantity).
        """
        if not size and not funds:
            raise ValueError("Um de 'size' ou 'funds' deve ser fornecido")

        # DOC-K04: Use provided clientOid or generate new (not idempotent)
        oid = client_oid if client_oid else str(uuid.uuid4())

        body: dict = {
            "clientOid": oid,
            "symbol": pair,
            "side":   side.lower(),
            "type":   "market",
        }
        if funds is not None:
            body["funds"] = str(round(funds, 6))
        if size is not None:
            body["size"] = str(round(size, 8))

        result = await self.request("POST", "/api/v1/orders", body=body)
        order_id = result.get("orderId", "")
        logger.info(f"✅ Ordem {side.upper()} {pair} | orderId={order_id} | clientOid={oid}")

        # Fetch complete fill details
        try:
            return await self.get_order(order_id)
        except Exception:
            return {"orderId": order_id, "dealFunds": funds or 0, "dealPrice": 0, "fee": 0}

    async def place_limit_order(
        self,
        pair:  str,
        side:  str,
        price: float,
        size:  float,
        client_oid: Optional[str] = None,   # DOC-K04
    ) -> dict:
        """Place a limit order at the given price."""
        oid = client_oid if client_oid else str(uuid.uuid4())
        body = {
            "clientOid": oid,
            "symbol": pair,
            "side":   side.lower(),
            "type":   "limit",
            "price":  str(round(price, 8)),
            "size":   str(round(size, 8)),
        }
        return await self.request("POST", "/api/v1/orders", body=body)

    # DOC-K05: Native stop orders (TP/SL) ─────────────────────────

    async def place_stop_order(
        self,
        pair: str,
        side: str,
        stop_price: float,
        size: float,
        stop_type: str = "loss",      # "loss" (sell below) or "entry" (buy above)
        order_type: str = "market",   # "market" or "limit"
        limit_price: Optional[float] = None,
        client_oid: Optional[str] = None,
    ) -> dict:
        """
        DOC-K05: Place a native stop order on KuCoin (/api/v1/stop-order).

        Use for Take Profit and Stop Loss so they remain active even when
        the engine is offline.

        Args:
            stop_type: "loss"  → triggers when price <= stop_price (SL on long)
                       "entry" → triggers when price >= stop_price (TP on long)
        """
        oid = client_oid if client_oid else str(uuid.uuid4())
        body: dict = {
            "clientOid": oid,
            "symbol": pair,
            "side": side.lower(),
            "type": order_type,
            "stopPrice": str(round(stop_price, 8)),
            "stop": stop_type,
        }
        if order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price obrigatório para stop-limit")
            body["price"] = str(round(limit_price, 8))
        body["size"] = str(round(size, 8))

        result = await self.request("POST", "/api/v1/stop-order", body=body)
        order_id = result.get("orderId", "")
        logger.info(
            f"✅ Stop order {stop_type.upper()} {side.upper()} {pair} "
            f"@ {stop_price} | orderId={order_id}"
        )
        return result

    async def cancel_stop_order(self, order_id: str) -> dict:
        """DOC-K05: Cancel a specific native stop order."""
        return await self.request("DELETE", f"/api/v1/stop-order/{order_id}")

    async def get_open_stop_orders(self, pair: Optional[str] = None) -> list:
        """DOC-K05: List active (untriggered) native stop orders."""
        params: dict = {}
        if pair:
            params["symbol"] = pair
        data = await self.request("GET", "/api/v1/stop-order", params=params)
        return data.get("items", []) if isinstance(data, dict) else (data or [])

    async def cancel_order(self, order_id: str) -> dict:
        return await self.request("DELETE", f"/api/v1/orders/{order_id}")

    async def cancel_all_orders(self, pair: Optional[str] = None) -> dict:
        """Cancel all open orders, optionally filtered by trading pair."""
        params: dict = {}
        if pair:
            params["symbol"] = pair
        return await self.request("DELETE", "/api/v1/orders", params=params)

    async def get_order(self, order_id: str) -> dict:
        return await self.request("GET", f"/api/v1/orders/{order_id}")

    async def get_open_orders(self, pair: Optional[str] = None) -> list:
        """Return all active (unfilled) orders, optionally for one pair."""
        params: dict = {"status": "active"}
        if pair:
            params["symbol"] = pair
        data = await self.request("GET", "/api/v1/orders", params=params)
        return data.get("items", []) if isinstance(data, dict) else data

    # ── Symbols & Market Info ────────────────────────────────────────────────

    async def get_symbols(self, market: Optional[str] = None) -> list:
        """
        Return all trading symbols from KuCoin (public, no auth).

        Optional ``market`` filter (e.g. "USDS" for USDT pairs).
        """
        params: dict = {}
        if market:
            params["market"] = market
        data = await self.request(
            "GET", "/api/v1/symbols", params=params, authenticated=False,
        )
        return data if isinstance(data, list) else []

    async def get_24h_stats(self, pair: str) -> dict:
        """Return 24-hour market statistics for a pair."""
        return await self.request(
            "GET", "/api/v1/market/stats",
            params={"symbol": pair},
            authenticated=False,
        )

    async def get_trade_history(self, pair: str) -> list:
        """Return recent public trade history for a pair."""
        data = await self.request(
            "GET", "/api/v1/market/histories",
            params={"symbol": pair},
            authenticated=False,
        )
        return data if isinstance(data, list) else []

    async def get_server_time(self) -> int:
        """Return KuCoin server timestamp (ms). Useful for connection tests."""
        data = await self.request(
            "GET", "/api/v1/timestamp", authenticated=False,
        )
        return int(data) if data else 0

    # ── OCO Orders ────────────────────────────────────────────────────────────

    async def place_oco_order(
        self,
        pair: str,
        side: str,
        size: float,
        take_profit_price: float,
        stop_loss_price: float,
        client_oid: Optional[str] = None,
        limit_price: Optional[float] = None,
    ) -> dict:
        """
        Place an OCO (One-Cancels-Other) order on KuCoin Spot.

        Creates a pair of TP + SL orders that cancel each other when one fills.
        Endpoint: POST /api/v3/oco/order

        Args:
            take_profit_price: limit sell price for take-profit leg
            stop_loss_price: stop trigger price for stop-loss leg
            limit_price: limit execution price for SL leg (default: SL - 1% for sell)
        """
        oid = client_oid if client_oid else str(uuid.uuid4())

        if limit_price is None:
            factor = 0.99 if side.lower() == "sell" else 1.01
            limit_price = round(stop_loss_price * factor, 8)

        body = {
            "clientOid": oid,
            "symbol": pair,
            "side": side.lower(),
            "type": "limit",
            "size": str(round(size, 8)),
            "price": str(round(take_profit_price, 8)),
            "stopPrice": str(round(stop_loss_price, 8)),
            "stopLimitPrice": str(round(limit_price, 8)),
            "tradeType": "TRADE",
        }

        result = await self.request("POST", "/api/v3/oco/order", body=body)
        logger.info(
            "✅ OCO %s %s size=%s TP=%s SL=%s | orderId=%s",
            side.upper(), pair, size, take_profit_price, stop_loss_price,
            result.get("orderId", ""),
        )
        return result

    async def cancel_oco_order(self, order_id: str) -> dict:
        """Cancel an active OCO order."""
        return await self.request("DELETE", f"/api/v3/oco/order/{order_id}")

    async def get_oco_order(self, order_id: str) -> dict:
        """Get details of an OCO order."""
        return await self.request("GET", f"/api/v3/oco/order/{order_id}")
