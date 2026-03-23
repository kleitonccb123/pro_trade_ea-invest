"""
Métricas Prometheus — DOC-06 §2

Usa um CollectorRegistry SEPARADO (`trading_registry`) para não colidir
com o `registry` já existente em `app.core.metrics`.

Prefixo: `trading_`

Endpoint /metrics expõe AMBOS os registries via `get_all_metrics()`.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
)

# ─── Registry exclusivo DOC-06 ───────────────────────────────────────────────

trading_registry = CollectorRegistry()

# ─── Ordens ──────────────────────────────────────────────────────────────────

trading_orders_total = Counter(
    "trading_orders_total",
    "Total de ordens enviadas à exchange",
    ["status", "symbol", "side", "type", "user_id"],
    registry=trading_registry,
)

trading_order_latency_ms = Histogram(
    "trading_order_latency_ms",
    "Latência do envio de ordem à exchange (ms) — da chamada até ACK",
    ["symbol", "type"],
    buckets=[50, 100, 200, 500, 1_000, 2_000, 5_000],
    registry=trading_registry,
)

trading_order_fill_time_ms = Histogram(
    "trading_order_fill_time_ms",
    "Tempo até preenchimento completo da ordem (ms) — criação até filled",
    ["symbol", "type"],
    buckets=[100, 500, 1_000, 2_000, 5_000, 10_000, 30_000],
    registry=trading_registry,
)

# ─── WebSocket ───────────────────────────────────────────────────────────────

trading_ws_connections_active = Gauge(
    "trading_ws_connections_active",
    "Conexões WebSocket ativas com a exchange",
    registry=trading_registry,
)

trading_ws_messages_total = Counter(
    "trading_ws_messages_total",
    "Total de mensagens recebidas via WebSocket",
    ["channel", "type"],
    registry=trading_registry,
)

trading_ws_reconnects_total = Counter(
    "trading_ws_reconnects_total",
    "Total de reconexões WebSocket realizadas",
    ["reason"],
    registry=trading_registry,
)

trading_ws_sequence_gaps_total = Counter(
    "trading_ws_sequence_gaps_total",
    "Total de gaps de sequência detectados no feed WebSocket",
    ["channel"],
    registry=trading_registry,
)

# ─── Circuit Breaker ─────────────────────────────────────────────────────────

trading_circuit_breaker_state = Gauge(
    "trading_circuit_breaker_state",
    "Estado do circuit breaker por serviço: 0=CLOSED, 1=HALF_OPEN, 2=OPEN",
    ["service"],
    registry=trading_registry,
)

trading_circuit_breaker_trips = Counter(
    "trading_circuit_breaker_trips_total",
    "Total de trips (aberturas) do circuit breaker por serviço",
    ["service"],
    registry=trading_registry,
)

# ─── Risk Manager ────────────────────────────────────────────────────────────

trading_risk_rejections_total = Counter(
    "trading_risk_rejections_total",
    "Total de ordens rejeitadas pelo RiskManager",
    ["reason", "severity"],
    registry=trading_registry,
)

trading_risk_evaluation_ms = Summary(
    "trading_risk_evaluation_ms",
    "Latência da avaliação completa de risco (ms)",
    registry=trading_registry,
)

# ─── Redis ───────────────────────────────────────────────────────────────────

trading_redis_command_ms = Histogram(
    "trading_redis_command_ms",
    "Latência de comandos Redis (ms)",
    ["command"],
    buckets=[1, 5, 10, 25, 50, 100],
    registry=trading_registry,
)

# ─── Sistema ─────────────────────────────────────────────────────────────────

trading_active_bots = Gauge(
    "trading_active_bots",
    "Número de bots de trading ativos por plano",
    ["plan"],
    registry=trading_registry,
)

# ─── Merge endpoint ──────────────────────────────────────────────────────────


async def get_all_metrics() -> tuple[bytes, str]:
    """
    Retorna (dados, content_type) combinando:
      - app.core.metrics.registry       (métricas de infra FastAPI)
      - trading_registry                (métricas de trading DOC-06)
      - app.monitoring.metrics.REGISTRY (métricas operacionais DOC-08 crypto_*)

    Uso em main.py::

        data, ct = await get_all_metrics()
        return Response(content=data, media_type=ct)
    """
    from app.core.metrics import registry as core_registry  # import tardio evita circular

    combined = generate_latest(core_registry) + generate_latest(trading_registry)

    # DOC-08: adiciona métricas crypto_* se disponíveis
    try:
        from app.monitoring.metrics import REGISTRY as monitoring_registry
        combined += generate_latest(monitoring_registry)
    except Exception:
        pass

    return combined, CONTENT_TYPE_LATEST
