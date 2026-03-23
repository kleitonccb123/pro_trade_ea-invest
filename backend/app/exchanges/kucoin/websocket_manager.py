"""
KuCoinWebSocketManager

Gerencia conexoes WebSocket com a KuCoin para dados em tempo real.

Canais suportados:
  - /market/ticker:{symbol}                 -> preco em tempo real
  - /market/candles:{symbol}:{interval}     -> candles em tempo real
  - /spotMarket/tradeOrders                 -> execucoes privadas Spot
  - /contractMarket/tradeOrders             -> execucoes privadas Futures

Arquitetura:
    KuCoin REST (snapshot inicial)
          |
    KuCoinWebSocketManager (esta classe)
          |
    Event Dispatcher (callbacks registrados)
          |
    TradingEngine / Frontend via FastAPI SSE / Redis pub-sub

Funcionalidades:
  - Snapshot inicial via REST antes de subscrever candles           [FIX 2]
  - Incrementais via WebSocket (tempo real)
  - Registry de topicos ativos: re-subscribe total apos reconexao   [FIX 1]
  - Reconexao automatica com backoff exponencial
  - Heartbeat / Ping a cada 20 s (KuCoin exige <30 s)
  - Watchdog: detecta conexao zumbi apos 40 s sem mensagem          [FIX 3]
  - Lock em toda operacao de subscribe dinamico (thread-safe)       [FIX 5]
  - Retry com delay em caso de 429 no endpoint de token             [FIX 6]
  - Execution report completo: matchSize, liquidity, tradeId        [FIX 4]
  - Canal Futures separado: /contractMarket/tradeOrders             [FIX 7]
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

import httpx

logger = logging.getLogger(__name__)

# DOC-06: métricas de reconexão WS
try:
    from app.observability.metrics import trading_ws_reconnects_total as _ws_reconnects
    _WS_METRICS_OK = True
except Exception:
    _WS_METRICS_OK = False

# Tipo de callback assíncrono que recebe o evento parsed
EventCallback = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


# ─────────────────────────── Modelos de Evento ───────────────────────────────

@dataclass
class TickerEvent:
    """Evento de ticker em tempo real."""
    symbol: str
    price: Decimal
    best_bid: Decimal
    best_ask: Decimal
    size: Decimal
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CandleEvent:
    """Evento de atualizacao de candle em tempo real."""
    symbol: str
    interval: str       # 1min, 5min, 15min, 1hour, etc.
    timestamp: datetime
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal


@dataclass
class OrderExecutionEvent:
    """
    Evento de execucao de ordem (canal privado Spot ou Futures).

    FIX 4 - Campos adicionados vs versao anterior:
      match_size  -> volume preenchido nesta execucao (evento match)
      liquidity   -> "maker" ou "taker"
      trade_id    -> ID do trade interno KuCoin (reconciliacao de PnL/fee)
      market      -> "spot" ou "futures"
    """
    order_id: str
    client_oid: str
    symbol: str
    side: str
    order_type: str
    status: str         # open, done, cancelled, match
    price: Decimal
    size: Decimal
    filled_size: Decimal
    remaining_size: Decimal
    match_size: Decimal
    liquidity: str      # "maker" | "taker" | ""
    trade_id: str
    fee: Decimal
    fee_currency: str
    market: str = "spot"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ──────────────────────────── Manager Principal ───────────────────────────────

class KuCoinWebSocketManager:
    """
    Gerencia WebSocket com a KuCoin.

    Exemplo de uso:
    ```python
    manager = KuCoinWebSocketManager(
        api_key="...",
        api_secret="...",
        passphrase="...",
        subscribe_futures_orders=True,
    )

    async def on_ticker(event: dict):
        print(f"Preco: {event['price']}")

    manager.on_ticker("BTC-USDT", on_ticker)
    await manager.start()
    # ... (keep running)
    await manager.stop()
    ```
    """

    # Endpoints REST
    REST_TOKEN_PUBLIC  = "https://api.kucoin.com/api/v1/bullet-public"
    REST_TOKEN_PRIVATE = "https://api.kucoin.com/api/v1/bullet-private"
    REST_CANDLES       = "https://api.kucoin.com/api/v1/market/candles"

    PING_INTERVAL_S       = 20   # KuCoin exige ping a cada <30 s
    STALE_THRESHOLD_S     = 40   # apos 40 s sem mensagem -> conexao zumbi [FIX 3]
    WATCHDOG_INTERVAL_S   = 10   # frequencia de checagem do watchdog
    RECONNECT_MAX_RETRIES = 10

    # Delay inicial de retry em caso de 429 no token (segundos)
    TOKEN_429_INITIAL_DELAY_S = 5

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        sandbox: bool = False,
        subscribe_futures_orders: bool = False,
    ):
        self._api_key    = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        self._sandbox    = sandbox

        # ── Callbacks por tipo de dado
        self._ticker_callbacks: Dict[str, List[EventCallback]] = {}            # symbol -> [cb]
        self._candle_callbacks: Dict[str, Dict[str, List[EventCallback]]] = {} # symbol->interval->[cb]
        self._order_callbacks: List[EventCallback] = []                        # Spot privado
        self._futures_order_callbacks: List[EventCallback] = []                # Futures privado [FIX 7]
        self._gap_callbacks:     List[EventCallback] = []                      # DOC-03: gap de sequencia
        self._level2_callbacks:  Dict[str, List[EventCallback]] = {}           # DOC-03: order book
        self._balance_callbacks: List[EventCallback] = []                      # DOC-03: balance privado

        # ── FIX 1: Registry oficial de topicos ativos
        # Chave: topico WS  |  Valor: True = private_channel
        self._active_topics: Dict[str, bool] = {}

        # ── FIX 2: Cache de snapshots REST por cache key (symbol_interval)
        self._snapshot_cache: Dict[str, List[Dict[str, Any]]] = {}

        # ── FIX 7: habilitar canal Futures
        self._subscribe_futures_orders = subscribe_futures_orders and bool(api_key)

        # ── Estado interno
        self._running        = False
        self._ws             = None   # websockets.WebSocketClientProtocol
        self._ping_task:     Optional[asyncio.Task] = None
        self._recv_task:     Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None

        # ── FIX 5: Lock para operacoes de subscribe dinamico
        self._lock = asyncio.Lock()

        # ── FIX 3: Timestamp da ultima mensagem recebida (watchdog)
        self._last_message_ts: float = time.time()

        # ── DOC-03: Sequencia tracking (reset a cada reconexao)
        self._last_sequence: Optional[int] = None

        logger.info("KuCoinWebSocketManager criado")

    # ──────────────────────── Registro de Callbacks ──────────────────────────

    def on_ticker(self, symbol: str, callback: EventCallback) -> None:
        """Registra callback para ticker de um simbolo."""
        self._ticker_callbacks.setdefault(symbol, []).append(callback)
        logger.info(f"Ticker callback registrado: {symbol}")

    def on_candle(self, symbol: str, interval: str, callback: EventCallback) -> None:
        """Registra callback para candles de um simbolo/intervalo."""
        self._candle_callbacks.setdefault(symbol, {}).setdefault(interval, []).append(callback)
        logger.info(f"Candle callback registrado: {symbol}/{interval}")

    def on_order_execution(self, callback: EventCallback) -> None:
        """Registra callback para execucoes de ordens privadas Spot."""
        self._order_callbacks.append(callback)
        logger.info("Order execution (Spot) callback registrado")

    def on_futures_order_execution(self, callback: EventCallback) -> None:
        """FIX 7: Registra callback para execucoes de ordens privadas Futures."""
        self._futures_order_callbacks.append(callback)
        logger.info("Order execution (Futures) callback registrado")

    # ── DOC-03: Novos canais ──────────────────────────────────────────────────

    def on_sequence_gap(self, callback: EventCallback) -> None:
        """DOC-03: Registra callback acionado quando um gap de sequenceId for detectado."""
        self._gap_callbacks.append(callback)

    def on_level2(self, symbol: str, callback: EventCallback) -> None:
        """DOC-03: Registra callback para updates de order book (/market/level2)."""
        self._level2_callbacks.setdefault(symbol, []).append(callback)
        logger.info(f"Level2 (order book) callback registrado: {symbol}")

    def on_balance(self, callback: EventCallback) -> None:
        """DOC-03: Registra callback para eventos de balance (/account/balance)."""
        self._balance_callbacks.append(callback)
        logger.info("Balance callback registrado")

    async def add_level2_subscription(self, symbol: str, callback: EventCallback) -> None:
        """DOC-03: Subscribe dinamico ao canal de order book de um simbolo."""
        self.on_level2(symbol, callback)
        topic = f"/market/level2:{symbol}"
        async with self._lock:
            if topic not in self._active_topics:
                self._active_topics[topic] = False
                if self._ws and self._running:
                    await self._send_subscribe(self._ws, topic, private_channel=False)

    async def subscribe_balance(self, callback: EventCallback) -> None:
        """DOC-03: Subscribe ao canal privado de balance."""
        self.on_balance(callback)
        topic = "/account/balance"
        async with self._lock:
            if topic not in self._active_topics and self._api_key:
                self._active_topics[topic] = True
                if self._ws and self._running:
                    await self._send_subscribe(self._ws, topic, private_channel=True)

    # ──────────────────────────── Inicio / Parada ─────────────────────────────

    async def start(self) -> None:
        """Inicia conexao WebSocket e loop de eventos."""
        if self._running:
            return
        self._running = True
        asyncio.create_task(self._connection_loop())
        logger.info("KuCoinWebSocketManager iniciado")

    async def stop(self) -> None:
        """Para conexao e limpa todas as tasks."""
        self._running = False
        for task in (self._ping_task, self._recv_task, self._watchdog_task):
            if task and not task.done():
                task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        logger.info("KuCoinWebSocketManager parado")

    # ─────────────────────────── Loop de Conexao ─────────────────────────────

    async def _connection_loop(self) -> None:
        """Loop principal com reconexao automatica e backoff exponencial."""
        attempt = 0
        while self._running:
            try:
                attempt += 1
                logger.info(f"Tentativa de conexao #{attempt}...")
                await self._connect()
                attempt = 0  # reset apos sucesso

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break

                wait = min(2 ** attempt, 60)
                logger.error(
                    f"Conexao falhou: {exc}. "
                    f"Reconectando em {wait}s (tentativa {attempt})..."
                )
                # DOC-06: incrementa contador de reconexões
                if _WS_METRICS_OK:
                    try:
                        _ws_reconnects.labels(reason="error").inc()
                    except Exception:
                        pass

                if attempt >= self.RECONNECT_MAX_RETRIES:
                    logger.critical("Maximo de tentativas atingido. WS abandonado.")
                    break

                await asyncio.sleep(wait)

    async def _connect(self) -> None:
        """Obtem token, abre WebSocket, subscreve e processa mensagens."""
        try:
            import websockets
        except ImportError:
            raise RuntimeError(
                "Pacote 'websockets' nao instalado. "
                "Execute: pip install websockets"
            )

        token, endpoint = await self._get_ws_token()
        connect_url = f"{endpoint}?token={token}&connectId={uuid.uuid4().hex}"

        async with websockets.connect(
            connect_url,
            ping_interval=None,  # gerenciamos ping manualmente
        ) as ws:
            self._ws = ws
            # FIX 3: resetar timestamp ao abrir nova conexao
            self._last_message_ts = time.time()
            # DOC-03: resetar sequencia ao reconectar (nova sessao WS)
            self._last_sequence = None
            logger.info(f"WebSocket conectado: {endpoint}")

            # FIX 2: snapshot REST antes das subscricoes de candle
            await self._fetch_all_snapshots()

            # FIX 1: re-subscribe usando registry (funciona em reconexoes tambem)
            await self._subscribe_all(ws)

            # Tarefas paralelas
            self._ping_task     = asyncio.create_task(self._ping_loop(ws))
            self._recv_task     = asyncio.create_task(self._recv_loop(ws))
            self._watchdog_task = asyncio.create_task(self._watchdog_loop(ws))

            await asyncio.gather(
                self._ping_task,
                self._recv_task,
                self._watchdog_task,
                return_exceptions=True,
            )

    # ─────────────────────────── Token de Conexao ────────────────────────────

    async def _get_ws_token(self) -> Tuple[str, str]:
        """
        Obtem token temporario para WebSocket via REST.
        FIX 6: retry com delay progressivo em caso de 429.
        """
        is_private = bool(self._api_key)
        url = self.REST_TOKEN_PRIVATE if is_private else self.REST_TOKEN_PUBLIC

        delay = self.TOKEN_429_INITIAL_DELAY_S
        for attempt in range(1, 6):  # max 5 tentativas
            headers: Dict[str, str] = {}
            if is_private:
                headers = self._build_auth_headers("POST", "/api/v1/bullet-private")

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=headers)

            # FIX 6: limite de taxa por status HTTP
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", delay))
                logger.warning(
                    f"429 (HTTP) no endpoint de token WS. "
                    f"Aguardando {retry_after}s (tentativa {attempt}/5)..."
                )
                await asyncio.sleep(retry_after)
                delay = min(delay * 2, 60)
                continue

            data = resp.json()

            # FIX 6: alguns endpoints retornam 429 como codigo JSON
            if data.get("code") == "429000":
                logger.warning(
                    f"429 (JSON) no token WS. "
                    f"Aguardando {delay}s (tentativa {attempt}/5)..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                continue

            if data.get("code") != "200000":
                raise RuntimeError(f"Erro ao obter token WS: {data}")

            token    = data["data"]["token"]
            servers  = data["data"]["instanceServers"]
            endpoint = servers[0]["endpoint"]

            logger.debug(f"Token WS obtido (privado={is_private})")
            return token, endpoint

        raise RuntimeError("Nao foi possivel obter token WS apos 5 tentativas (429)")

    def _build_auth_headers(self, method: str, path: str) -> Dict[str, str]:
        """Constroi headers HMAC-SHA256 para chamadas REST privadas."""
        import hashlib
        import hmac as hmac_mod
        from base64 import b64encode

        timestamp = str(int(time.time() * 1000))
        message   = timestamp + method + path
        signature = b64encode(
            hmac_mod.new(
                self._api_secret.encode(),
                message.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()
        passphrase_enc = b64encode(
            hmac_mod.new(
                self._api_secret.encode(),
                self._passphrase.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()

        return {
            "KC-API-KEY":         self._api_key,
            "KC-API-SIGN":        signature,
            "KC-API-TIMESTAMP":   timestamp,
            "KC-API-PASSPHRASE":  passphrase_enc,
            "KC-API-KEY-VERSION": "2",
            "Content-Type":       "application/json",
        }

    # ─────────────────────────── Snapshot REST ───────────────────────────────

    async def _fetch_all_snapshots(self) -> None:
        """
        FIX 2: Busca snapshot historico via REST para cada (symbol, interval)
        com callbacks de candle registrados.
        Dispara evento 'candle_snapshot' com a lista completa de candles
        antes de qualquer mensagem WS incremental.
        """
        for symbol, intervals in self._candle_callbacks.items():
            for interval, callbacks in intervals.items():
                if not callbacks:
                    continue
                try:
                    candles = await self.fetch_candle_snapshot(symbol, interval)
                    self._snapshot_cache[f"{symbol}_{interval}"] = candles
                    snapshot_event = {
                        "type":     "candle_snapshot",
                        "symbol":    symbol,
                        "interval":  interval,
                        "candles":   candles,
                    }
                    await self._fire(callbacks, snapshot_event)
                    logger.info(
                        f"Snapshot REST: {symbol}/{interval} ({len(candles)} candles)"
                    )
                except Exception as exc:
                    logger.warning(
                        f"Falha ao carregar snapshot {symbol}/{interval}: {exc}"
                    )

    async def fetch_candle_snapshot(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        GET /api/v1/market/candles?symbol={symbol}&type={interval}

        Retorna lista de candles ordenada por tempo crescente:
          [{"timestamp": datetime, "open": Decimal, "close": Decimal,
            "high": Decimal, "low": Decimal, "volume": Decimal}]
        """
        params = {"symbol": symbol, "type": interval}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self.REST_CANDLES, params=params)

        data = resp.json()
        if data.get("code") != "200000":
            raise RuntimeError(f"Erro ao buscar candles REST: {data}")

        # KuCoin retorna timestamps decrescentes
        raw_list: List[List[str]] = data.get("data", [])
        result: List[Dict[str, Any]] = []
        for row in reversed(raw_list[:limit]):
            # row = [ts_s, open, close, high, low, volume, turnover]
            result.append({
                "timestamp": datetime.fromtimestamp(int(row[0]), tz=timezone.utc),
                "open":      Decimal(row[1]),
                "close":     Decimal(row[2]),
                "high":      Decimal(row[3]),
                "low":       Decimal(row[4]),
                "volume":    Decimal(row[5]),
            })
        return result

    # ──────────────────────────── Subscricoes ────────────────────────────────

    async def _subscribe_all(self, ws) -> None:
        """
        FIX 1: Re-subscribe completo usando o registry _active_topics.
        Na primeira conexao, popula o registry a partir dos callbacks.
        Em reconexoes (registry ja preenchido), re-envia todos os topicos
        incluindo os adicionados dinamicamente apos o start().
        """
        # Primeira conexao: construir registry a partir dos callbacks registrados
        if not self._active_topics:
            for symbol in self._ticker_callbacks:
                self._active_topics[f"/market/ticker:{symbol}"] = False

            for symbol, intervals in self._candle_callbacks.items():
                for interval in intervals:
                    self._active_topics[f"/market/candles:{symbol}_{interval}"] = False

            if self._order_callbacks and self._api_key:
                self._active_topics["/spotMarket/tradeOrders"] = True

            if self._subscribe_futures_orders and self._futures_order_callbacks:
                self._active_topics["/contractMarket/tradeOrders"] = True

        # Re-subscribe em todos os topicos do registry (funciona em reconexoes)
        for topic, is_private in self._active_topics.items():
            await self._send_subscribe(ws, topic, private_channel=is_private)

    async def _send_subscribe(
        self,
        ws,
        topic: str,
        private_channel: bool = False,
    ) -> None:
        """Envia mensagem de subscribe para o WebSocket."""
        payload = json.dumps({
            "id":             uuid.uuid4().hex,
            "type":           "subscribe",
            "topic":          topic,
            "privateChannel": private_channel,
            "response":       True,
        })
        await ws.send(payload)
        logger.debug(f"Subscribe enviado: {topic}")

    # ──────────────────────────── Ping / Recv / Watchdog ─────────────────────

    async def _ping_loop(self, ws) -> None:
        """Envia ping a cada PING_INTERVAL_S segundos."""
        while self._running:
            await asyncio.sleep(self.PING_INTERVAL_S)
            try:
                await ws.send(json.dumps({
                    "id":   uuid.uuid4().hex,
                    "type": "ping",
                }))
                logger.debug("Ping enviado")
            except Exception as exc:
                logger.warning(f"Ping falhou: {exc}")
                break

    async def _recv_loop(self, ws) -> None:
        """Recebe e processa mensagens do WebSocket."""
        async for raw in ws:
            # FIX 3: atualizar timestamp a cada mensagem recebida
            self._last_message_ts = time.time()
            try:
                msg = json.loads(raw)
                await self._dispatch(msg)
            except json.JSONDecodeError:
                logger.warning(f"Mensagem invalida: {raw[:200]}")
            except Exception as exc:
                logger.error(f"Erro no dispatch: {exc}")

    async def _watchdog_loop(self, ws) -> None:
        """
        FIX 3: Detecta conexao zumbi.
        Se nao receber nenhuma mensagem por STALE_THRESHOLD_S segundos,
        fecha o socket e forca reconexao automatica.
        """
        while self._running:
            await asyncio.sleep(self.WATCHDOG_INTERVAL_S)
            elapsed = time.time() - self._last_message_ts
            if elapsed > self.STALE_THRESHOLD_S:
                logger.warning(
                    f"Conexao zumbi: {elapsed:.0f}s sem mensagem. "
                    f"Forcando reconexao..."
                )
                try:
                    await ws.close()
                except Exception:
                    pass
                raise Exception("WS stale — reconectando automaticamente")

    # ─────────────────────────────── Dispatch ────────────────────────────────

    async def _dispatch(self, msg: Dict[str, Any]) -> None:
        """Direciona mensagem recebida para o handler correto."""
        msg_type = msg.get("type", "")

        if msg_type in ("welcome", "pong", "ack"):
            return  # mensagens de controle, ignorar

        if msg_type != "message":
            logger.debug(f"Mensagem ignorada tipo={msg_type}")
            return

        topic: str = msg.get("topic", "")
        data:  Dict = msg.get("data", {})

        # ── DOC-03: Sequence gap detection
        raw_seq = msg.get("sequence")
        if raw_seq is not None:
            try:
                seq_int = int(raw_seq)
                if self._last_sequence is not None:
                    expected = self._last_sequence + 1
                    if seq_int > expected:
                        gap = seq_int - expected
                        logger.warning(
                            f"Sequence gap: expected={expected} got={seq_int} "
                            f"gap={gap} topic={topic}"
                        )
                        gap_event: Dict[str, Any] = {
                            "type":     "sequence_gap",
                            "topic":    topic,
                            "expected": expected,
                            "received": seq_int,
                            "gap":      gap,
                        }
                        await self._fire(self._gap_callbacks, gap_event)
                self._last_sequence = seq_int
            except (ValueError, TypeError):
                pass

        # ── Ticker
        if topic.startswith("/market/ticker:"):
            symbol = topic.split(":")[-1]
            event  = self._parse_ticker(symbol, data)
            await self._fire(self._ticker_callbacks.get(symbol, []), event)
            return

        # ── Candle
        if topic.startswith("/market/candles:"):
            raw_key = topic.split(":")[-1]           # ex: BTC-USDT_1min
            parts   = raw_key.rsplit("_", maxsplit=1)
            symbol, interval = parts if len(parts) == 2 else (raw_key, "unknown")
            event     = self._parse_candle(symbol, interval, data)
            callbacks = self._candle_callbacks.get(symbol, {}).get(interval, [])
            await self._fire(callbacks, event)
            return

        # ── FIX 7: Ordens Spot privadas
        if topic == "/spotMarket/tradeOrders":
            event = self._parse_order_execution(data, market="spot")
            await self._fire(self._order_callbacks, event)
            return

        # ── FIX 7: Ordens Futures privadas
        if topic == "/contractMarket/tradeOrders":
            event = self._parse_order_execution(data, market="futures")
            await self._fire(self._futures_order_callbacks, event)
            return

        # ── DOC-03: Level2 / Order Book
        if topic.startswith("/market/level2:"):
            symbol = topic.split(":")[-1]
            event = {
                "type":           "level2",
                "symbol":          symbol,
                "changes":         data.get("changes", {}),
                "sequence_start":  data.get("sequenceStart"),
                "sequence_end":    data.get("sequenceEnd"),
                "timestamp":       datetime.now(timezone.utc),
            }
            await self._fire(self._level2_callbacks.get(symbol, []), event)
            return

        # ── DOC-03: Account Balance
        if topic == "/account/balance":
            event = {
                "type":       "balance",
                "currency":   data.get("currency", ""),
                "available":  data.get("available", "0"),
                "hold":       data.get("hold", "0"),
                "account_id": data.get("accountId", ""),
                "timestamp":  datetime.now(timezone.utc),
            }
            await self._fire(self._balance_callbacks, event)
            return

        logger.debug(f"Topico nao tratado: {topic}")

    # ──────────────────────────── Parsers ────────────────────────────────────

    @staticmethod
    def _parse_ticker(symbol: str, data: Dict) -> Dict[str, Any]:
        return {
            "type":      "ticker",
            "symbol":     symbol,
            "price":      Decimal(data.get("price", "0")),
            "best_bid":   Decimal(data.get("bestBid", "0")),
            "best_ask":   Decimal(data.get("bestAsk", "0")),
            "size":       Decimal(data.get("size", "0")),
            "timestamp":  datetime.now(timezone.utc),
        }

    @staticmethod
    def _parse_candle(symbol: str, interval: str, data: Dict) -> Dict[str, Any]:
        candle = data.get("candles", [])  # [ts, open, close, high, low, volume, ...]
        if len(candle) < 6:
            return {"type": "candle", "symbol": symbol, "interval": interval, "raw": data}
        return {
            "type":      "candle",
            "symbol":     symbol,
            "interval":   interval,
            "timestamp":  datetime.fromtimestamp(int(candle[0]), tz=timezone.utc),
            "open":       Decimal(candle[1]),
            "close":      Decimal(candle[2]),
            "high":       Decimal(candle[3]),
            "low":        Decimal(candle[4]),
            "volume":     Decimal(candle[5]),
        }

    @staticmethod
    def _parse_order_execution(data: Dict, market: str = "spot") -> Dict[str, Any]:
        """
        FIX 4: Execution report completo.

        Eventos por status:
          open      -> ordem aberta na book (matchSize e tradeId ausentes)
          match     -> execucao parcial; matchSize e tradeId presentes
          done      -> ordem totalmente preenchida ou cancelada
          cancelled -> cancelada pelo usuario

        Campos FIX 4:
          match_size -> volume desta execucao especifica (evento match)
          liquidity  -> "maker" ou "taker" (calculo correto de fee)
          trade_id   -> ID do trade (reconciliacao de PnL e fee real)
          market     -> "spot" ou "futures"
        """
        return {
            "type":           "order_execution",
            "market":          market,
            "order_id":        data.get("orderId", ""),
            "client_oid":      data.get("clientOid", ""),
            "symbol":          data.get("symbol", ""),
            "side":            data.get("side", ""),
            "order_type":      data.get("orderType", ""),
            "status":          data.get("status", ""),
            "price":           Decimal(data.get("price", "0")),
            "size":            Decimal(data.get("size", "0")),
            # Total acumulado preenchido na ordem
            "filled_size":     Decimal(data.get("filledSize", "0")),
            # Volume desta execucao especifica (apenas em 'match')
            "match_size":      Decimal(data.get("matchSize", "0")),
            "remaining_size":  Decimal(data.get("remainSize", "0")),
            # FIX 4: maker/taker para calcular fee corretamente
            "liquidity":       data.get("liquidity", ""),
            # FIX 4: ID do trade para reconciliacao de PnL
            "trade_id":        data.get("tradeId", ""),
            "fee":             Decimal(data.get("fee", "0")),
            "fee_currency":    data.get("feeCurrency", "USDT"),
            "timestamp":       datetime.now(timezone.utc),
        }

    # ─────────────────────────── Utilitarios ─────────────────────────────────

    @staticmethod
    async def _fire(callbacks: List[EventCallback], event: Dict[str, Any]) -> None:
        """Chama todos os callbacks registrados para um evento."""
        for cb in callbacks:
            try:
                await cb(event)
            except Exception as exc:
                logger.error(f"Erro em callback WS: {exc}")

    @property
    def subscribed_symbols(self) -> Set[str]:
        """Retorna conjunto de simbolos com ticker subscrito."""
        return set(self._ticker_callbacks.keys())

    async def add_ticker_subscription(self, symbol: str, callback: EventCallback) -> None:
        """
        FIX 1 + FIX 5: Adiciona subscricao de ticker dinamicamente.
        - Lock garante ausencia de race condition e subscribe duplicado.
        - Registra no _active_topics para re-subscribe apos reconexao.
        """
        self.on_ticker(symbol, callback)
        topic = f"/market/ticker:{symbol}"

        async with self._lock:  # FIX 5
            if topic not in self._active_topics:
                self._active_topics[topic] = False  # FIX 1: registro permanente
                if self._ws and self._running:
                    await self._send_subscribe(self._ws, topic, private_channel=False)

    async def add_candle_subscription(
        self,
        symbol: str,
        interval: str,
        callback: EventCallback,
    ) -> None:
        """
        FIX 1 + FIX 2 + FIX 5: Adiciona subscricao de candle dinamicamente.
        - Busca snapshot REST antes de subscrever (garantia de consistencia).
        - Lock previne race condition em chamadas simultaneas.
        - Registra no _active_topics para re-subscribe apos reconexao.
        """
        self.on_candle(symbol, interval, callback)
        topic = f"/market/candles:{symbol}_{interval}"

        async with self._lock:  # FIX 5
            if topic not in self._active_topics:
                # FIX 2: snapshot antes de subscrever
                try:
                    candles = await self.fetch_candle_snapshot(symbol, interval)
                    self._snapshot_cache[f"{symbol}_{interval}"] = candles
                    await self._fire([callback], {
                        "type":    "candle_snapshot",
                        "symbol":   symbol,
                        "interval": interval,
                        "candles":  candles,
                    })
                except Exception as exc:
                    logger.warning(
                        f"Falha no snapshot dinamico {symbol}/{interval}: {exc}"
                    )

                self._active_topics[topic] = False  # FIX 1
                if self._ws and self._running:
                    await self._send_subscribe(self._ws, topic, private_channel=False)

    async def add_futures_orders_subscription(self, callback: EventCallback) -> None:
        """
        FIX 5 + FIX 7: Adiciona subscricao ao canal de ordens Futures.
        Lock previne race condition em chamadas simultaneas.
        """
        self._futures_order_callbacks.append(callback)
        topic = "/contractMarket/tradeOrders"

        async with self._lock:  # FIX 5
            if topic not in self._active_topics and self._api_key:
                self._active_topics[topic] = True  # FIX 1
                if self._ws and self._running:
                    await self._send_subscribe(self._ws, topic, private_channel=True)


# ─────────────────────────── Instancia Global ────────────────────────────────

_ws_manager: Optional[KuCoinWebSocketManager] = None


def init_ws_manager(
    api_key:                   Optional[str] = None,
    api_secret:                Optional[str] = None,
    passphrase:                Optional[str] = None,
    sandbox:                   bool = False,
    subscribe_futures_orders:  bool = False,
) -> KuCoinWebSocketManager:
    """
    Inicializa a instancia global do WebSocketManager.

    Args:
        subscribe_futures_orders: se True, habilita canal /contractMarket/tradeOrders
                                  (requer api_key valida)
    """
    global _ws_manager
    _ws_manager = KuCoinWebSocketManager(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        sandbox=sandbox,
        subscribe_futures_orders=subscribe_futures_orders,
    )
    return _ws_manager


def get_ws_manager() -> KuCoinWebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        raise RuntimeError(
            "WebSocketManager nao inicializado. "
            "Chame init_ws_manager() durante o startup da aplicacao."
        )
    return _ws_manager
