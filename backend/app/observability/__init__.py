"""
Observability package — DOC-06

Exporta:
  - trading_registry     : CollectorRegistry separado para métricas trading_*
  - métricas individuais : trading_orders_total, trading_order_latency_ms, …
  - StructuredLogger     : logger JSON estruturado
  - HealthCheckService   : verificações ponderadas de saúde
"""

from app.observability.metrics import (
    trading_registry,
    trading_orders_total,
    trading_order_latency_ms,
    trading_order_fill_time_ms,
    trading_ws_connections_active,
    trading_ws_messages_total,
    trading_ws_reconnects_total,
    trading_ws_sequence_gaps_total,
    trading_circuit_breaker_state,
    trading_circuit_breaker_trips,
    trading_risk_rejections_total,
    trading_risk_evaluation_ms,
    trading_redis_command_ms,
    trading_active_bots,
    get_all_metrics,
)
from app.observability.structured_logger import StructuredLogger, get_logger
from app.observability.health_check import HealthCheckService

__all__ = [
    # registry
    "trading_registry",
    # order metrics
    "trading_orders_total",
    "trading_order_latency_ms",
    "trading_order_fill_time_ms",
    # websocket metrics
    "trading_ws_connections_active",
    "trading_ws_messages_total",
    "trading_ws_reconnects_total",
    "trading_ws_sequence_gaps_total",
    # circuit breaker metrics
    "trading_circuit_breaker_state",
    "trading_circuit_breaker_trips",
    # risk metrics
    "trading_risk_rejections_total",
    "trading_risk_evaluation_ms",
    # infra metrics
    "trading_redis_command_ms",
    "trading_active_bots",
    # helpers
    "get_all_metrics",
    # logger
    "StructuredLogger",
    "get_logger",
    # health
    "HealthCheckService",
]
