"""
Prometheus Metrics Configuration

Provides comprehensive observability for the Crypto Trade Hub API.
Includes automatic FastAPI instrumentation and custom business metrics.
"""
import time
from typing import Callable, Any
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_fastapi_instrumentator.metrics import Info

# Create a custom registry for our metrics
registry = CollectorRegistry()

# ============================================
# BUSINESS METRICS
# ============================================

# Trade execution metrics
trades_executed_total = Counter(
    'trades_executed_total',
    'Total number of trades executed',
    ['exchange', 'symbol', 'side', 'status'],
    registry=registry
)

trades_pnl_total = Counter(
    'trades_pnl_total',
    'Total P&L from trades',
    ['exchange', 'symbol', 'currency'],
    registry=registry
)

# Bot metrics
bots_active_total = Gauge(
    'bots_active_total',
    'Number of currently active bots',
    ['exchange', 'strategy'],
    registry=registry
)

bots_started_total = Counter(
    'bots_started_total',
    'Total number of bot starts',
    ['exchange', 'strategy', 'reason'],
    registry=registry
)

bots_stopped_total = Counter(
    'bots_stopped_total',
    'Total number of bot stops',
    ['exchange', 'strategy', 'reason'],
    registry=registry
)

# User metrics
users_active_total = Gauge(
    'users_active_total',
    'Number of currently active users',
    registry=registry
)

user_sessions_total = Counter(
    'user_sessions_total',
    'Total user sessions created',
    ['auth_method'],
    registry=registry
)

# WebSocket metrics
websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections',
    ['type'],
    registry=registry
)

websocket_messages_total = Counter(
    'websocket_messages_total',
    'Total WebSocket messages sent',
    ['type', 'direction'],
    registry=registry
)

# Queue metrics
task_queue_size = Gauge(
    'task_queue_size',
    'Current size of the task queue',
    registry=registry
)

task_queue_processed_total = Counter(
    'task_queue_processed_total',
    'Total tasks processed by the queue',
    ['task_type', 'status'],
    registry=registry
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Current state of circuit breakers (0=closed, 1=open, 2=half_open)',
    ['exchange'],
    registry=registry
)

circuit_breaker_failures_total = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['exchange'],
    registry=registry
)

# ============================================
# PERFORMANCE METRICS
# ============================================

# API request duration (complements the automatic instrumentation)
api_request_duration_custom = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds (custom business logic)',
    ['endpoint', 'method', 'status'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

# Database operation metrics
db_operation_duration = Histogram(
    'db_operation_duration_seconds',
    'Database operation duration',
    ['operation', 'collection'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
    registry=registry
)

# External API call metrics
external_api_calls_total = Counter(
    'external_api_calls_total',
    'Total external API calls made',
    ['service', 'endpoint', 'status'],
    registry=registry
)

external_api_duration = Histogram(
    'external_api_duration_seconds',
    'External API call duration',
    ['service', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

# ============================================
# SYSTEM METRICS
# ============================================

# Memory usage
memory_usage_bytes = Gauge(
    'memory_usage_bytes',
    'Current memory usage in bytes',
    registry=registry
)

# Error metrics
errors_total = Counter(
    'errors_total',
    'Total number of errors',
    ['type', 'component'],
    registry=registry
)

# ============================================
# DECORATORS FOR BUSINESS LOGIC INSTRUMENTATION
# ============================================

def track_trade_execution(exchange: str, symbol: str, side: str):
    """Decorator to track trade execution metrics."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)

                # Track successful trade
                status = getattr(result, 'status', 'unknown') if hasattr(result, '__dict__') else 'unknown'
                trades_executed_total.labels(
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    status=status
                ).inc()

                # Track P&L if available
                if hasattr(result, 'pnl') and result.pnl is not None:
                    trades_pnl_total.labels(
                        exchange=exchange,
                        symbol=symbol,
                        currency='USDT'  # Assuming USDT base
                    ).inc(result.pnl)

                return result
            except Exception as e:
                # Track failed trade
                trades_executed_total.labels(
                    exchange=exchange,
                    symbol=symbol,
                    side=side,
                    status='failed'
                ).inc()
                raise e
        return wrapper
    return decorator


def track_bot_operation(operation: str):
    """Decorator to track bot operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)

                if operation == 'start':
                    bots_started_total.labels(
                        exchange='unknown',  # Would need to extract from args
                        strategy='unknown',
                        reason='manual'
                    ).inc()
                elif operation == 'stop':
                    bots_stopped_total.labels(
                        exchange='unknown',
                        strategy='unknown',
                        reason='manual'
                    ).inc()

                return result
            except Exception as e:
                errors_total.labels(type='bot_operation', component='bot_service').inc()
                raise e
        return wrapper
    return decorator


def track_db_operation(operation: str, collection: str):
    """Decorator to track database operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                db_operation_duration.labels(
                    operation=operation,
                    collection=collection
                ).observe(duration)
                return result
            except Exception as e:
                errors_total.labels(type='db_operation', component=collection).inc()
                raise e
        return wrapper
    return decorator


def track_external_api_call(service: str, endpoint: str):
    """Decorator to track external API calls."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                external_api_calls_total.labels(
                    service=service,
                    endpoint=endpoint,
                    status='success'
                ).inc()

                external_api_duration.labels(
                    service=service,
                    endpoint=endpoint
                ).observe(duration)

                return result
            except Exception as e:
                external_api_calls_total.labels(
                    service=service,
                    endpoint=endpoint,
                    status='error'
                ).inc()
                raise e
        return wrapper
    return decorator


# ============================================
# INSTRUMENTATION SETUP
# ============================================

def setup_prometheus_instrumentation(app):
    """
    Setup Prometheus instrumentation for the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Create instrumentator with custom registry
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_group_untemplated=True,
        excluded_handlers=["/metrics", "/health", "/docs", "/redoc", "/openapi.json"],
        registry=registry
    )

    # Add custom metrics
    instrumentator.add(
        metrics.request_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )

    instrumentator.add(
        metrics.response_size(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )

    # Add custom histogram for API request duration
    instrumentator.add(
        metrics.latency(
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
        )
    )

    # Instrument the app
    instrumentator.instrument(app)

    # Expose metrics endpoint
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)

    return instrumentator


def get_metrics() -> str:
    """Get current metrics in Prometheus format."""
    return generate_latest(registry).decode('utf-8')


# ============================================
# UTILITY FUNCTIONS
# ============================================

def update_bot_count(exchange: str, strategy: str, delta: int):
    """Update active bot count."""
    bots_active_total.labels(exchange=exchange, strategy=strategy).inc(delta)


def update_websocket_connections(connection_type: str, delta: int):
    """Update WebSocket connection count."""
    websocket_connections_active.labels(type=connection_type).inc(delta)


def update_queue_size(size: int):
    """Update task queue size."""
    task_queue_size.set(size)


def update_circuit_breaker_state(exchange: str, state: int):
    """Update circuit breaker state (0=closed, 1=open, 2=half_open)."""
    circuit_breaker_state.labels(exchange=exchange).set(state)