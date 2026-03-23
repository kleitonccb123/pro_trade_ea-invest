from __future__ import annotations

import logging
import sys
import json
from datetime import datetime
from typing import Dict, Any

from app.core.config import settings


LEVEL_MAP: Dict[str, int] = {
    "dev": logging.DEBUG,
    "staging": logging.INFO,
    "prod": logging.WARNING,
}


class JSONFormatter(logging.Formatter):
    """JSON structured logging formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Create base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # DOC-08: module/function/line for traceability
            "module":   record.module,
            "function": record.funcName,
            "line":     record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # DOC-08 context keys — extracted if passed via extra={...}
        for _key in (
            "request_id", "user_id", "ip_address",
            # DOC-08 trading context
            "bot_instance_id", "trade_id", "pair", "event",
        ):
            if hasattr(record, _key):
                log_entry[_key] = getattr(record, _key)

        return json.dumps(log_entry, ensure_ascii=False)


def configure_logging() -> None:
    """Configure structured logging with JSON output and Sentry integration."""

    mode = (settings.app_mode or "dev").lower()
    level = LEVEL_MAP.get(mode, logging.DEBUG)

    # Clear existing handlers to avoid duplicate messages
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    # Choose formatter based on mode
    if mode in ["staging", "prod"]:
        # JSON structured logging for production
        formatter = JSONFormatter()
        handler = logging.StreamHandler(stream=sys.stdout)
    else:
        # Human-readable logging for development
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler = logging.StreamHandler(stream=sys.stdout)

    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level)

    # Configure library loggers to not be too verbose
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Silence noisy HTTP client loggers (httpx, httpcore) - Exchange API calls
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)

    # Reduce motor/pymongo noise
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    # Uvicorn loggers - disable access logs (too noisy), keep errors
    logging.getLogger("uvicorn.error").propagate = True
    logging.getLogger("uvicorn.access").propagate = False

    # FastAPI loggers
    logging.getLogger("fastapi").setLevel(logging.INFO)

    # Add error notifier handler for CRITICAL logs (if webhooks configured)
    try:
        from app.services.error_notifier_handler import setup_error_notifier_handler
        
        # Setup error notifier for app.core logger (catches database/system errors)
        app_logger = logging.getLogger("app.core")
        setup_error_notifier_handler(
            app_logger,
            severity_threshold=logging.CRITICAL
        )
        
        # Also monitor app.services for critical issues
        services_logger = logging.getLogger("app.services")
        setup_error_notifier_handler(
            services_logger,
            severity_threshold=logging.CRITICAL
        )
        
    except Exception as e:
        root.warning(f"Failed to setup error notifier handler: {e}")

    # Configure Sentry if DSN is provided
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastAPIIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=mode,
                integrations=[
                    FastAPIIntegration(),
                    LoggingIntegration(
                        level=logging.WARNING,  # Send WARNING+ to Sentry
                        event_level=logging.ERROR,  # Send ERROR+ as events
                    ),
                ],
                # Performance monitoring
                traces_sample_rate=0.1 if mode == "prod" else 1.0,
                # Release tracking
                release=f"crypto-trade-hub@{settings.app_mode}",
                # Error filtering
                before_send=lambda event, hint: event if should_report_error(event) else None,
            )

            root.info("Sentry error tracking enabled", extra={"sentry_dsn_configured": True})

        except ImportError:
            root.warning("Sentry SDK not installed, error tracking disabled")
        except Exception as e:
            root.error("Failed to initialize Sentry", exc_info=e)
    else:
        root.info("Sentry DSN not configured, error tracking disabled")

    root.info(
        "Logging configured",
        extra={
            "mode": mode,
            "level": logging.getLevelName(level),
            "structured": mode in ["staging", "prod"],
            "sentry_enabled": bool(settings.sentry_dsn),
        }
    )


def should_report_error(event: Dict[str, Any]) -> bool:
    """Filter out errors that shouldn't be reported to Sentry."""
    # Don't report 4xx client errors (user errors)
    if "exception" in event:
        for exc in event["exception"]["values"]:
            if exc.get("type") in ["HTTPException", "ValidationError"]:
                # Check if it's a 4xx error
                if hasattr(exc, "value") and hasattr(exc.value, "status_code"):
                    if 400 <= exc.value.status_code < 500:
                        return False

    return True


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    return logging.getLogger(name)


# DOC-08: alias for backward compatibility
setup_logging = configure_logging
