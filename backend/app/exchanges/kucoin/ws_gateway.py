"""
WsGateway — Orchestrador do WebSocket Profissional (DOC-03)

Combina:
  - KuCoinWebSocketManager  (conexão, heartbeat, reconexão, sequência)
  - WsDispatcher            (fan-out via Redis Pub/Sub)

Uma única instância de WsGateway mantém UMA conexão WebSocket com a KuCoin
e distribui os dados para N consumidores via Redis.

Funcionalidades DOC-03 cobertas:
  ✅ Token com TTL de 23h (lógico), renovado a cada reconexão
  ✅ Reconexão com backoff exponencial (1s→60s, max 10 tentativas)
  ✅ Heartbeat a cada 20s (watchdog a cada 40s)
  ✅ Sequência gap detection → gap recovery via REST snapshot
  ✅ Fan-out: Redis PUBLISH por canal específico
  ✅ Canal privado /trade/orders → ExecutionProcessor (DOC-01 pipeline)
  ✅ Canal privado /account/balance → Redis ws:balance:{user_id}
  ✅ Canal /market/level2:{symbol} → Redis ws:orderbook:{symbol}
  ✅ Symbols dinâmicos: addSymbol() após start()

Uso:
```python
gateway = WsGateway(
    api_key="...", api_secret="...", passphrase="...",
    redis_client=redis,
)
await gateway.start(symbols=["BTC-USDT", "ETH-USDT"], user_id="user123")
gateway.add_symbol("SOL-USDT")
# ...
await gateway.stop()
```
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class WsGateway:
    """
    Ponto central de bootstrap para o subsistema WebSocket profissional.

    Responsabilidades:
    - Criar e iniciar o KuCoinWebSocketManager
    - Criar e conectar o WsDispatcher ao manager
    - Expor add_symbol() para subscrições dinâmicas
    - Expor stop() para shutdown limpo
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        redis_client: Optional[Any] = None,
        rest_client: Optional[Any] = None,    # KuCoinRawClient (para gap recovery)
        sandbox: bool = False,
        subscribe_futures_orders: bool = True,
    ) -> None:
        self._api_key    = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        self._redis      = redis_client
        self._rest       = rest_client
        self._sandbox    = sandbox
        self._sub_futures = subscribe_futures_orders

        self._manager:    Optional[Any] = None    # KuCoinWebSocketManager
        self._dispatcher: Optional[Any] = None    # WsDispatcher

    async def start(
        self,
        symbols: List[str],
        user_id: Optional[str] = None,
    ) -> None:
        """
        Inicializa a conexão WebSocket e começa a publicar no Redis.

        Args:
            symbols:  lista inicial de símbolos (ex: ["BTC-USDT", "ETH-USDT"])
            user_id:  ID do usuário para canais privados (execuções, balance)
        """
        from app.exchanges.kucoin.websocket_manager import KuCoinWebSocketManager
        from app.exchanges.kucoin.ws_dispatcher import WsDispatcher

        # ── 1. Criar manager
        self._manager = KuCoinWebSocketManager(
            api_key=self._api_key,
            api_secret=self._api_secret,
            passphrase=self._passphrase,
            sandbox=self._sandbox,
            subscribe_futures_orders=self._sub_futures,
        )

        # ── 2. Criar dispatcher e conectar ao manager
        self._dispatcher = WsDispatcher(
            redis_client=self._redis,
            user_id=user_id or "",
            kucoin_rest_client=self._rest,
        )
        self._dispatcher.wire(self._manager, symbols)

        # ── 3. Registrar subscriptions no manager (ticker + level2 + privados)
        for symbol in symbols:
            self._manager._active_topics[f"/market/ticker:{symbol}"]  = False
            self._manager._active_topics[f"/market/level2:{symbol}"]  = False

        if self._api_key:
            self._manager._active_topics["/spotMarket/tradeOrders"]   = True
            self._manager._active_topics["/account/balance"]          = True
            if self._sub_futures:
                self._manager._active_topics["/contractMarket/tradeOrders"] = True

        # ── 4. Iniciar conexão
        await self._manager.start()

        logger.info(
            "WsGateway iniciado: symbols=%s user_id=%s redis=%s",
            symbols, user_id, "sim" if self._redis else "não",
        )

    def add_symbol(self, symbol: str) -> None:
        """
        Adiciona um símbolo dinamicamente após o start.
        Assina ticker e level2 para o novo símbolo.
        """
        if self._manager is None:
            logger.warning("WsGateway.add_symbol: gateway não iniciado")
            return

        import asyncio

        # Registra callback do dispatcher para o novo símbolo
        if self._dispatcher:
            self._manager.on_ticker(symbol, self._dispatcher._make_ticker_handler(symbol))
            self._manager.on_level2(symbol, self._dispatcher._make_orderbook_handler(symbol))

        # Subscribe dinâmico (thread-safe via asyncio.create_task)
        asyncio.create_task(
            self._subscribe_new_symbol(symbol),
            name=f"ws_add_symbol_{symbol}",
        )
        logger.info("WsGateway: símbolo %s adicionado", symbol)

    async def _subscribe_new_symbol(self, symbol: str) -> None:
        if self._manager and self._manager._ws:
            topic_ticker = f"/market/ticker:{symbol}"
            topic_l2     = f"/market/level2:{symbol}"
            async with self._manager._lock:
                if topic_ticker not in self._manager._active_topics:
                    self._manager._active_topics[topic_ticker] = False
                    await self._manager._send_subscribe(
                        self._manager._ws, topic_ticker, private_channel=False
                    )
                if topic_l2 not in self._manager._active_topics:
                    self._manager._active_topics[topic_l2] = False
                    await self._manager._send_subscribe(
                        self._manager._ws, topic_l2, private_channel=False
                    )

    async def stop(self) -> None:
        """Para o WebSocket Gateway e libera recursos."""
        if self._manager:
            await self._manager.stop()
        logger.info("WsGateway parado")

    @property
    def is_running(self) -> bool:
        return (
            self._manager is not None
            and getattr(self._manager, "_running", False)
        )

    @property
    def connected(self) -> bool:
        """Alias para health_check.py (DOC-06): True se o WS está ativo."""
        return self.is_running


# ─── Instância global ─────────────────────────────────────────────────────────

_gateway: Optional[WsGateway] = None


def init_ws_gateway(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    passphrase: Optional[str] = None,
    redis_client: Optional[Any] = None,
    rest_client: Optional[Any] = None,
    sandbox: bool = False,
    subscribe_futures_orders: bool = True,
) -> WsGateway:
    global _gateway
    _gateway = WsGateway(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        redis_client=redis_client,
        rest_client=rest_client,
        sandbox=sandbox,
        subscribe_futures_orders=subscribe_futures_orders,
    )
    logger.info("WsGateway criado")
    return _gateway


def get_ws_gateway() -> Optional[WsGateway]:
    return _gateway
