"""
Métricas Prometheus — DOC-08 §3

Usa CollectorRegistry SEPARADO (`REGISTRY`) com prefixo `crypto_` para
não colidir com os registries de app.core.metrics e app.observability.metrics.

Endpoint /metrics (registrado em monitoring/health.py) expõe este registry.

Métricas definidas aqui:
  Counters  : crypto_trades_total, crypto_bot_errors_total, crypto_kucoin_requests_total
  Gauges    : crypto_active_bots, crypto_open_positions, crypto_ws_connections
  Histograms: crypto_trade_duration_minutes, crypto_pnl_usdt, crypto_kucoin_api_latency_seconds

Uso::

    from app.monitoring.metrics import (
        trades_total, bot_errors_total, active_bots,
        trade_duration_minutes, pnl_distribution,
        api_latency_seconds, REGISTRY,
    )

    trades_total.labels(robot_id="r1", pair="BTC-USDT", exit_reason="take_profit").inc()
    active_bots.set(5)
    api_latency_seconds.labels(endpoint="place_order").observe(0.35)
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ─── Registry exclusivo DOC-08 ───────────────────────────────────────────────

REGISTRY = CollectorRegistry()

# ─── Contadores ──────────────────────────────────────────────────────────────

trades_total = Counter(
    "crypto_trades_total",
    "Total de trades executadas",
    ["robot_id", "pair", "exit_reason"],
    registry=REGISTRY,
)

bot_errors_total = Counter(
    "crypto_bot_errors_total",
    "Total de erros de bot",
    ["bot_instance_id", "error_type"],
    registry=REGISTRY,
)

kucoin_requests_total = Counter(
    "crypto_kucoin_requests_total",
    "Requests para KuCoin API",
    ["endpoint", "status"],
    registry=REGISTRY,
)

# ─── Gauges ──────────────────────────────────────────────────────────────────

active_bots = Gauge(
    "crypto_active_bots",
    "Número de bots ativos",
    registry=REGISTRY,
)

open_positions = Gauge(
    "crypto_open_positions",
    "Posições abertas no momento",
    registry=REGISTRY,
)

ws_connections = Gauge(
    "crypto_ws_connections",
    "Conexões WebSocket KuCoin ativas",
    registry=REGISTRY,
)

# ─── Histogramas ─────────────────────────────────────────────────────────────

trade_duration_minutes = Histogram(
    "crypto_trade_duration_minutes",
    "Duração das trades em minutos",
    buckets=[5, 15, 30, 60, 120, 360, 720, 1440],
    registry=REGISTRY,
)

pnl_distribution = Histogram(
    "crypto_pnl_usdt",
    "Distribuição de PnL por trade em USDT",
    buckets=[-100, -50, -20, -10, -5, 0, 5, 10, 20, 50, 100, 500],
    registry=REGISTRY,
)

api_latency_seconds = Histogram(
    "crypto_kucoin_api_latency_seconds",
    "Latência de requests à KuCoin API",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=REGISTRY,
)

# ─── Router Prometheus ────────────────────────────────────────────────────────

metrics_router = APIRouter()


@metrics_router.get(
    "/metrics",
    response_class=PlainTextResponse,
    include_in_schema=False,
    summary="Prometheus scrape endpoint",
)
async def get_metrics() -> str:
    """Endpoint scrapeado pelo Prometheus a cada 15 segundos."""
    return generate_latest(REGISTRY).decode("utf-8")
