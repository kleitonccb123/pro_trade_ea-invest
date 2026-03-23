"""
StructuredLogger — DOC-06 §3

Logger JSON estruturado para produção:
  - Todos os registros incluem obrigatoriamente o campo `event`
  - Campos sensíveis são automaticamente redigidos
  - Suporta child loggers com contexto fixo (requestId, traceId, userId, botId)
  - Plugável no sistema logging padrão do Python via JSONFormatter

Uso básico::

    from app.observability.structured_logger import get_logger

    log = get_logger("order_manager")
    log.info("ordem.enviada", symbol="BTC-USDT", side="buy", size="0.001")

    # Child com contexto fixo
    req_log = log.child(requestId="abc-123", userId="u42")
    req_log.warning("taxa.alta", fee_usd=12.5)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional


# ─── Campos sensíveis → "[REDACTED]" ─────────────────────────────────────────

_REDACT_FIELDS: frozenset[str] = frozenset(
    {
        "api_key",
        "api_secret",
        "passphrase",
        "authorization",
        "cookie",
        "password",
        "token",
        "secret",
        "private_key",
        "access_token",
        "refresh_token",
    }
)

_SERVICE = os.getenv("SERVICE_NAME", "trading-backend")
_VERSION  = os.getenv("APP_VERSION", "1.0.0")
_ENV      = os.getenv("ENVIRONMENT", "production")


# ─── JSON Formatter para stdlib logging ─────────────────────────────────────


class JSONFormatter(logging.Formatter):
    """
    Formata cada LogRecord como uma única linha JSON.
    Adiciona campos padrão e redige campos sensíveis.
    """

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)
            )
            + f".{int((record.created % 1) * 1000):03d}Z",
            "level":   record.levelname,
            "service": _SERVICE,
            "version": _VERSION,
            "env":     _ENV,
            "logger":  record.name,
            "event":   record.getMessage(),
        }

        # Copia extras (campos adicionados via `extra={...}`)
        _skip = {
            "args", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message",
            "module", "msecs", "msg", "name", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "taskName",
            "thread", "threadName",
        }
        for key, val in record.__dict__.items():
            if key not in _skip:
                payload[key] = val

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        _redact_inplace(payload)

        return json.dumps(payload, default=str, ensure_ascii=False)


def _redact_inplace(data: Dict[str, Any]) -> None:
    """Substitui valores de chaves sensíveis por '[REDACTED]' (in-place, 1 nível)."""
    for key in list(data.keys()):
        if key.lower() in _REDACT_FIELDS:
            data[key] = "[REDACTED]"


def _configure_root_json_logging() -> None:
    """
    Substitui o handler raiz por um que emite JSON se LOG_FORMAT=json
    (ou em produção por padrão).
    """
    log_format = os.getenv("LOG_FORMAT", "json").lower()
    if log_format != "json":
        return

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    else:
        for h in root.handlers:
            if not isinstance(h.formatter, JSONFormatter):
                h.setFormatter(JSONFormatter())


# Aplica na importação do módulo (unit-testável — basta não set LOG_FORMAT=json)
_configure_root_json_logging()


# ─── StructuredLogger ─────────────────────────────────────────────────────────


class StructuredLogger:
    """
    Wrapper sobre `logging.Logger` com API ergonômica orientada a eventos.

    Métodos: `info`, `warning`, `error`, `debug`, `critical`
    Todos aceitam `event` como primeiro argumento posicional e kwargs livres.

    Exemplo::

        log = StructuredLogger("trading")
        log.info("bot.started", bot_id="b1", symbol="BTC-USDT")
        log.error("ordem.falhou", symbol="ETH-USDT", exc=str(e))
    """

    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        _parent: Optional["StructuredLogger"] = None,
    ) -> None:
        self._name    = name
        self._context: Dict[str, Any] = dict(context or {})
        self._logger  = logging.getLogger(name)

    # ── Métodos de log ───────────────────────────────────────────────────────

    def _emit(self, level: int, event: str, **kwargs: Any) -> None:
        extra = {**self._context, **kwargs}
        # Garante o campo `event` sempre presente mesmo se o caller usar `msg`
        extra.setdefault("event", event)
        _redact_inplace(extra)
        # A mensagem para stdlib é o event (JSONFormatter vai usar record.getMessage())
        self._logger.log(level, event, extra=extra)

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.CRITICAL, event, **kwargs)

    # ── Child logger ─────────────────────────────────────────────────────────

    def child(self, **context: Any) -> "StructuredLogger":
        """
        Retorna novo StructuredLogger com contexto adicional fixo.

        ::

            req_log = log.child(requestId="abc-123", userId="u42")
            req_log.info("auth.ok")
            # → {"event": "auth.ok", "requestId": "abc-123", "userId": "u42", …}
        """
        merged = {**self._context, **context}
        return StructuredLogger(self._name, context=merged)

    # ── Compatibilidade stdlib ───────────────────────────────────────────────

    def getChild(self, suffix: str) -> "StructuredLogger":
        return StructuredLogger(f"{self._name}.{suffix}", context=self._context)


# ─── Factory ─────────────────────────────────────────────────────────────────

_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str) -> StructuredLogger:
    """
    Retorna (ou cria) um StructuredLogger para o nome dado.
    Funciona como `logging.getLogger` mas retorna nossa classe wrapper.
    """
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name)
    return _loggers[name]
