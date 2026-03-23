# DOC 04 — Integração KuCoin (Signing, Rate Limit, WebSocket, Retry)

> **Nível:** Produção | **Exchange:** KuCoin Spot API v2  
> **Prioridade:** Crítica — sem isso, nenhum trade pode ser executado

---

## 1. OBJETIVO

Implementar o wrapper de integração com a KuCoin que:
- Assina corretamente cada request REST (HMAC-SHA256)
- Respeita os rate limits dinâmicos por endpoint
- Mantém conexão WebSocket persistente com reconexão automática
- Retry idempotente com backoff exponencial
- Abstrai toda a complexidade para `BotWorker` consumir

---

## 2. AUTENTICAÇÃO E ASSINATURA

### 2.1 Algoritmo de Signing

Cada request privado à KuCoin exige os headers:
```
KC-API-KEY          → sua api_key
KC-API-SIGN         → assinatura HMAC-SHA256
KC-API-TIMESTAMP    → timestamp em ms
KC-API-PASSPHRASE   → passphrase encriptada com HMAC-SHA256
KC-API-KEY-VERSION  → "2" (obrigatório para versão 2)
```

### 2.2 Cálculo da Assinatura

```python
# backend/app/integrations/kucoin/signing.py

import hmac
import hashlib
import base64
import time


def build_signature(api_secret: str, timestamp: str, method: str, endpoint: str, body: str = "") -> str:
    """
    Constrói a assinatura HMAC-SHA256 para autenticação na KuCoin.
    
    signature = base64(HMAC-SHA256(api_secret, timestamp + method + endpoint + body))
    """
    message = f"{timestamp}{method.upper()}{endpoint}{body}"
    mac = hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode('utf-8')


def build_passphrase_signature(api_secret: str, passphrase: str) -> str:
    """
    Encripta a passphrase com HMAC-SHA256 (obrigatório v2).
    """
    mac = hmac.new(api_secret.encode('utf-8'), passphrase.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode('utf-8')


def build_auth_headers(
    api_key: str,
    api_secret: str,
    api_passphrase: str,
    method: str,
    endpoint: str,
    body: str = ""
) -> dict:
    """
    Gera os 5 headers de autenticação necessários.
    """
    timestamp = str(int(time.time() * 1000))
    return {
        "KC-API-KEY": api_key,
        "KC-API-SIGN": build_signature(api_secret, timestamp, method, endpoint, body),
        "KC-API-TIMESTAMP": timestamp,
        "KC-API-PASSPHRASE": build_passphrase_signature(api_secret, api_passphrase),
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json",
    }
```

---

## 3. RATE LIMIT MANAGER

A KuCoin tem limites por endpoint com janela de 30s. Exceder resulta em `429` e possível blacklist temporária.

```python
# backend/app/integrations/kucoin/rate_limiter.py

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RateLimitBucket:
    """
    Janela deslizante de requests para um endpoint específico.
    """
    max_requests: int
    window_seconds: int
    timestamps: deque = field(default_factory=deque)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds

            # Remover timestamps fora da janela
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()

            if len(self.timestamps) >= self.max_requests:
                # Calcular tempo de espera até o próximo slot
                wait_time = self.timestamps[0] + self.window_seconds - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Limpar novamente após espera
                    cutoff = time.monotonic() - self.window_seconds
                    while self.timestamps and self.timestamps[0] < cutoff:
                        self.timestamps.popleft()

            self.timestamps.append(time.monotonic())


# Limites oficiais da KuCoin por categoria
KUCOIN_RATE_LIMITS: Dict[str, RateLimitBucket] = {
    "market_data": RateLimitBucket(max_requests=30, window_seconds=10),
    "order_place": RateLimitBucket(max_requests=45, window_seconds=10),
    "order_cancel": RateLimitBucket(max_requests=60, window_seconds=10),
    "account": RateLimitBucket(max_requests=20, window_seconds=10),
    "order_list": RateLimitBucket(max_requests=30, window_seconds=10),
    "default": RateLimitBucket(max_requests=20, window_seconds=10),
}

ENDPOINT_CATEGORY_MAP = {
    "/api/v1/market/candles": "market_data",
    "/api/v1/market/orderbook/level2_20": "market_data",
    "/api/v1/market/stats": "market_data",
    "/api/v1/orders": "order_place",
    "/api/v1/orders/cancel": "order_cancel",
    "/api/v1/accounts": "account",
}


class KuCoinRateLimiter:
    @staticmethod
    async def acquire(endpoint: str):
        category = "default"
        for prefix, cat in ENDPOINT_CATEGORY_MAP.items():
            if endpoint.startswith(prefix):
                category = cat
                break
        await KUCOIN_RATE_LIMITS[category].acquire()
```

---

## 4. REST CLIENT COM RETRY

```python
# backend/app/integrations/kucoin/rest_client.py

import aiohttp
import asyncio
import json
import logging
from typing import Optional
from app.integrations.kucoin.signing import build_auth_headers
from app.integrations.kucoin.rate_limiter import KuCoinRateLimiter

logger = logging.getLogger("kucoin.rest")

BASE_URL = "https://api.kucoin.com"
SANDBOX_URL = "https://openapi-sandbox.kucoin.com"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # segundos


class KuCoinRESTClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        sandbox: bool = False
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.base_url = SANDBOX_URL if sandbox else BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "CryptoTradeHub/1.0"}
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        authenticated: bool = True,
    ) -> dict:
        """
        Executa um request com rate limit e retry exponencial.
        """
        body_str = json.dumps(body, separators=(',', ':')) if body else ""
        url = f"{self.base_url}{endpoint}"

        headers = {}
        if authenticated:
            headers = build_auth_headers(
                self.api_key, self.api_secret, self.api_passphrase,
                method, endpoint, body_str
            )

        # Aplicar rate limit
        await KuCoinRateLimiter.acquire(endpoint)

        for attempt in range(MAX_RETRIES + 1):
            try:
                session = await self._get_session()
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=body_str if body else None,
                    headers=headers
                ) as response:

                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logger.warning(f"Rate limit atingido em {endpoint}. Aguardando {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                        wait = BACKOFF_BASE ** attempt
                        logger.warning(f"Status {response.status} em {endpoint}, retry {attempt+1}/{MAX_RETRIES} em {wait}s")
                        await asyncio.sleep(wait)
                        continue

                    data = await response.json()

                    if response.status >= 400:
                        logger.error(f"KuCoin API erro: status={response.status}, body={data}")
                        raise KuCoinAPIError(
                            status=response.status,
                            code=data.get("code"),
                            message=data.get("msg", "Unknown error"),
                            endpoint=endpoint
                        )

                    if data.get("code") != "200000":
                        raise KuCoinAPIError(
                            status=200,
                            code=data.get("code"),
                            message=data.get("msg"),
                            endpoint=endpoint
                        )

                    return data.get("data", data)

            except aiohttp.ClientError as e:
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(f"Erro de rede em {endpoint}: {e}. Retry em {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise KuCoinNetworkError(f"Falha persistente em {endpoint}: {e}")

        raise KuCoinNetworkError(f"Máximo de tentativas atingido para {endpoint}")

    # ── Métodos de Alto Nível ────────────────────────────────────────────────

    async def get_account_balances(self) -> list:
        return await self.request("GET", "/api/v1/accounts", params={"type": "trade"})

    async def get_ticker(self, pair: str) -> dict:
        data = await self.request(
            "GET", "/api/v1/market/stats",
            params={"symbol": pair},
            authenticated=False
        )
        return data

    async def get_candles(self, pair: str, timeframe: str, limit: int = 200) -> list:
        end = int(time.time())
        start = end - (TIMEFRAME_SECONDS[timeframe] * limit)
        return await self.request(
            "GET", "/api/v1/market/candles",
            params={"symbol": pair, "type": timeframe, "startAt": start, "endAt": end},
            authenticated=False
        )

    async def place_market_order(self, pair: str, side: str, size: Optional[float] = None, funds: Optional[float] = None) -> dict:
        """
        Coloca ordem a mercado. Use size (quantidade) ou funds (valor em USDT, para side=buy).
        """
        import uuid
        body = {
            "clientOid": str(uuid.uuid4()),
            "symbol": pair,
            "side": side,     # "buy" ou "sell"
            "type": "market",
        }
        if funds:
            body["funds"] = str(round(funds, 6))
        if size:
            body["size"] = str(round(size, 8))

        return await self.request("POST", "/api/v1/orders", body=body)

    async def place_limit_order(self, pair: str, side: str, price: float, size: float) -> dict:
        import uuid
        body = {
            "clientOid": str(uuid.uuid4()),
            "symbol": pair,
            "side": side,
            "type": "limit",
            "price": str(round(price, 8)),
            "size": str(round(size, 8)),
        }
        return await self.request("POST", "/api/v1/orders", body=body)

    async def cancel_order(self, order_id: str) -> dict:
        return await self.request("DELETE", f"/api/v1/orders/{order_id}")

    async def get_order(self, order_id: str) -> dict:
        return await self.request("GET", f"/api/v1/orders/{order_id}")

    async def get_open_orders(self, pair: Optional[str] = None) -> list:
        params = {"status": "active"}
        if pair:
            params["symbol"] = pair
        data = await self.request("GET", "/api/v1/orders", params=params)
        return data.get("items", [])


# ── Erros Customizados ───────────────────────────────────────────────────────

class KuCoinAPIError(Exception):
    def __init__(self, status: int, code: str, message: str, endpoint: str):
        self.status = status
        self.code = code
        self.message = message
        self.endpoint = endpoint
        super().__init__(f"KuCoin API Error [{code}] on {endpoint}: {message}")

class KuCoinNetworkError(Exception):
    pass

TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900,
    "1h": 3600, "4h": 14400, "1d": 86400
}
```

---

## 5. WEBSOCKET CLIENT COM RECONEXÃO

### 5.1 Obter Token de Conexão

```python
async def get_ws_token(self, private: bool = False) -> tuple[str, str]:
    """
    KuCoin exige token único para cada sessão WebSocket.
    Token privado = necessário para updates de ordens e saldo.
    """
    endpoint = "/api/v1/bullet-private" if private else "/api/v1/bullet-public"
    data = await self.request("POST", endpoint, body={}, authenticated=private)
    token = data["token"]
    server = data["instanceServers"][0]
    endpoint_url = server["endpoint"]
    ping_interval = server["pingInterval"]  # ms
    return token, f"{endpoint_url}?token={token}", ping_interval
```

### 5.2 WebSocket Manager

```python
# backend/app/integrations/kucoin/ws_client.py

import asyncio
import json
import logging
import time
from typing import Callable, Optional
import aiohttp

logger = logging.getLogger("kucoin.ws")

MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_BACKOFF_BASE = 2.0
RECONNECT_MAX_WAIT = 60.0


class KuCoinWebSocketClient:
    def __init__(
        self,
        rest_client: "KuCoinRESTClient",
        on_message: Callable[[dict], None],
        on_disconnect: Optional[Callable] = None,
        private: bool = True
    ):
        self.rest = rest_client
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.private = private
        self._ws = None
        self._session = None
        self._running = False
        self._subscriptions: list[dict] = []
        self._ping_task: Optional[asyncio.Task] = None
        self._reconnect_count = 0
        self._msg_id = 0

    def _next_id(self) -> str:
        self._msg_id += 1
        return str(self._msg_id)

    async def connect(self):
        """Conecta ao WebSocket com loop de reconexão automática."""
        self._running = True
        self._reconnect_count = 0

        while self._running:
            try:
                await self._connect_once()
            except Exception as e:
                if not self._running:
                    break  # Parada intencional

                self._reconnect_count += 1
                if self._reconnect_count > MAX_RECONNECT_ATTEMPTS:
                    logger.critical(f"WebSocket: máximo de reconexões atingido. Encerrando.")
                    break

                wait = min(
                    RECONNECT_BACKOFF_BASE ** self._reconnect_count,
                    RECONNECT_MAX_WAIT
                )
                logger.warning(f"WebSocket desconectado: {e}. Reconectando em {wait:.1f}s (tentativa {self._reconnect_count})")
                await asyncio.sleep(wait)

                if self.on_disconnect:
                    asyncio.create_task(self.on_disconnect(self._reconnect_count))

    async def _connect_once(self):
        """Tenta uma única conexão."""
        token, ws_url, ping_interval_ms = await self.rest.get_ws_token(private=self.private)
        ping_interval = ping_interval_ms / 1000.0

        self._session = aiohttp.ClientSession()
        try:
            async with self._session.ws_connect(ws_url, heartbeat=None) as ws:
                self._ws = ws
                self._reconnect_count = 0  # Reset contador ao conectar com sucesso
                logger.info(f"✅ WebSocket KuCoin conectado ({'private' if self.private else 'public'})")

                # Re-aplicar subscrições após reconexão
                for sub in self._subscriptions:
                    await self._send_subscribe(sub["topic"], sub["private"])

                # Iniciar ping loop
                self._ping_task = asyncio.create_task(
                    self._ping_loop(ws, ping_interval)
                )

                # Loop principal de mensagens
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        await self._handle_message(data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket erro: {ws.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        logger.warning("WebSocket fechado pelo servidor")
                        break
        finally:
            if self._ping_task:
                self._ping_task.cancel()
            await self._session.close()

    async def _ping_loop(self, ws, interval: float):
        """Mantém a conexão ativa com pings periódicos."""
        while True:
            await asyncio.sleep(interval * 0.8)  # 80% do intervalo
            try:
                await ws.send_str(json.dumps({"id": self._next_id(), "type": "ping"}))
            except Exception:
                break  # WebSocket fechado

    async def _handle_message(self, data: dict):
        msg_type = data.get("type")

        if msg_type == "pong":
            return  # Ignorar pong

        if msg_type == "welcome":
            logger.debug("WebSocket welcome recebido")
            return

        if msg_type == "ack":
            return  # Confirmação de subscrição

        if msg_type in ("message", "data"):
            try:
                await self.on_message(data)
            except Exception as e:
                logger.error(f"Erro ao processar mensagem WS: {e}")

    async def subscribe(self, topic: str, private: bool = False):
        """Subscreve a um tópico e armazena para re-subscribe após reconexão."""
        self._subscriptions.append({"topic": topic, "private": private})
        if self._ws and not self._ws.closed:
            await self._send_subscribe(topic, private)

    async def _send_subscribe(self, topic: str, private: bool):
        msg = {
            "id": self._next_id(),
            "type": "subscribe",
            "topic": topic,
            "privateChannel": private,
            "response": True
        }
        await self._ws.send_str(json.dumps(msg))
        logger.debug(f"Subscrito ao tópico: {topic}")

    async def unsubscribe(self, topic: str):
        self._subscriptions = [s for s in self._subscriptions if s["topic"] != topic]
        if self._ws and not self._ws.closed:
            msg = {
                "id": self._next_id(),
                "type": "unsubscribe",
                "topic": topic,
                "privateChannel": False,
                "response": True
            }
            await self._ws.send_str(json.dumps(msg))

    async def disconnect(self):
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()


# ── Tópicos Importantes ─────────────────────────────────────────────────────
# Public:
TOPIC_TICKER = "/market/ticker:{pair}"                # preço em tempo real
TOPIC_ORDERBOOK = "/spotMarket/level2Depth5:{pair}"  # livro de ordens
TOPIC_CANDLES = "/market/candles:{pair}_{timeframe}" # candles em tempo real
# Private:
TOPIC_ORDERS = "/spotMarket/tradeOrders"              # updates de ordens do usuário
TOPIC_BALANCES = "/account/balance"                   # mudanças de saldo
```

---

## 6. USO NO BOTWORKER

```python
# Dentro de BotWorker.start()

# 1. Criar clientes
self.rest_client = KuCoinRESTClient(
    api_key=self.config.api_key,
    api_secret=self.config.api_secret,
    api_passphrase=self.config.api_passphrase,
    sandbox=settings.KUCOIN_SANDBOX
)

# 2. Configurar WebSocket
async def on_ticker_message(data: dict):
    if data.get("topic", "").startswith("/market/ticker"):
        subject = data.get("data", {})
        await self._process_price_update(
            price=float(subject.get("price", 0))
        )

self.ws_client = KuCoinWebSocketClient(
    rest_client=self.rest_client,
    on_message=on_ticker_message,
    on_disconnect=self._handle_ws_disconnect,
    private=True  # para receber updates de ordens
)

# 3. Conectar em task separada
self._ws_task = asyncio.create_task(self.ws_client.connect())

# 4. Subscrever aos tópicos necessários
await asyncio.sleep(1)  # aguardar conexão estabelecer
pair = self.config.pair
await self.ws_client.subscribe(f"/market/ticker:{pair}")
await self.ws_client.subscribe(TOPIC_ORDERS, private=True)
```

---

## 7. ERROS COMUNS E SOLUÇÕES

| Código KuCoin | Significado | Solução |
|---|---|---|
| `400006` | Assinatura inválida | Verificar timestamp do servidor vs local |
| `400007` | API key inativa | Checar status da key no painel KuCoin |
| `400008` | IP não autorizado | Whitelist do IP no painel KuCoin |
| `400200` | Fondos insuficientes | Verificar saldo antes de cada ordem |
| `400500` | Ordem abaixo do mínimo | Par tem minimum order size (~10 USDT) |
| `429000` | Rate limit | RateLimiter deve prevenir; se ocorrer, esperar |

---

## 8. CHECKLIST

- [ ] HMAC-SHA256 signing funciona (testar com sandbox)
- [ ] Headers KC-API-KEY-VERSION: "2" incluído
- [ ] Rate limiter com janela deslizante por categoria
- [ ] Retry exponencial para erros 5xx e 429
- [ ] WebSocket reconecta automaticamente até 10x
- [ ] Re-subscribe nos mesmos tópicos após reconexão
- [ ] on_disconnect callback notifica BotWorker
- [ ] Sandbox mode configurável via variável de ambiente
- [ ] Minimum order size respeitado (10 USDT para maioria dos pares)
- [ ] Testar assinatura com `/api/v1/accounts` (endpoint privado simples)
