"""KuCoin integration — exported public API."""

from app.integrations.kucoin.signing import build_auth_headers, build_signature, build_passphrase_signature
from app.integrations.kucoin.rate_limiter import KuCoinRateLimiter
from app.integrations.kucoin.rest_client import KuCoinRESTClient, KuCoinAPIError, KuCoinNetworkError
from app.integrations.kucoin.ws_client import KuCoinWebSocketClient, TOPIC_TICKER, TOPIC_ORDERS, TOPIC_BALANCES, TOPIC_ORDERBOOK, TOPIC_CANDLES

__all__ = [
    "build_auth_headers",
    "build_signature",
    "build_passphrase_signature",
    "KuCoinRateLimiter",
    "KuCoinRESTClient",
    "KuCoinAPIError",
    "KuCoinNetworkError",
    "KuCoinWebSocketClient",
    "TOPIC_TICKER",
    "TOPIC_ORDERS",
    "TOPIC_BALANCES",
    "TOPIC_ORDERBOOK",
    "TOPIC_CANDLES",
]
