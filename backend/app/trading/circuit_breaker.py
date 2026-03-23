"""
CircuitBreaker — Protecao contra cascata de falhas da exchange

Problema sem isso:
  - KuCoin comeca a responder lento ou com 500/503
  - Sistema continua tentando colocar ordens
  - Rate limit esgota, capital em risco, logs inundados
  - Cascata de prejuizo sem controle

Solucao (padrao Circuit Breaker classico):
  CLOSED  -> operacao normal, monitora taxa de erro
  OPEN    -> falhas acima do threshold, bloqueia novos trades
  HALF-OPEN -> apos timeout, permite 1 request de teste

                +----------+
                |  CLOSED  | <-- estado normal
                +----------+
                     | falhas > threshold
                     v
                +----------+
                |   OPEN   | <-- bloqueia trades novos
                +----------+
                     | timeout
                     v
               +------------+
               | HALF-OPEN  | <-- 1 request de teste
               +------------+
              sucesso |  | falha
                      v  v
               CLOSED    OPEN

Integracao:
  Adicionar ao TradingEngine antes de qualquer request:
  ```python
  circuit_breaker.pre_request()  # lanca CircuitOpenError se OPEN
  try:
      resp = await client.place_order(...)
      circuit_breaker.record_success()
  except KuCoinAPIError as e:
      circuit_breaker.record_failure(e)
      raise
  ```
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED    = "closed"     # normal
    OPEN      = "open"       # bloqueado
    HALF_OPEN = "half_open"  # testando recuperacao


class CircuitOpenError(Exception):
    """Lancada quando o circuit breaker esta OPEN."""
    pass


class ExchangeHealthMonitor:
    """
    Circuit Breaker para protecao contra falhas da exchange.

    Parametros:
      failure_threshold   -> numero de falhas para abrir o circuito
      success_threshold   -> numero de sucessos (em HALF_OPEN) para fechar
      timeout_s           -> segundos ate tentar HALF_OPEN
      error_rate_window   -> janela de tempo para calcular taxa de erro (s)

    Uso como guard:
    ```python
    monitor = ExchangeHealthMonitor()

    async def place_order_safe(...):
        monitor.pre_request()          # lanca CircuitOpenError se OPEN
        try:
            result = await engine.place_market_order(...)
            monitor.record_success()
            return result
        except Exception as e:
            monitor.record_failure(e)
            raise
    ```

    Uso como decorator:
    ```python
    @monitor.guard
    async def place_order(...):
        return await engine.place_order(...)
    ```
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_s: float = 60.0,
        error_rate_pct: float = 50.0,    # % de erros na janela para abrir
        window_s: float = 60.0,          # janela de observacao (segundos)
    ) -> None:
        self._failure_threshold  = failure_threshold
        self._success_threshold  = success_threshold
        self._timeout_s          = timeout_s
        self._error_rate_pct     = error_rate_pct
        self._window_s           = window_s

        self._state              = CircuitState.CLOSED
        self._consecutive_fails  = 0
        self._consecutive_ok     = 0
        self._opened_at: Optional[float] = None

        # Contadores de janela deslizante
        self._window_requests: list[tuple[float, bool]] = []  # (ts, success)

        logger.info(
            f"ExchangeHealthMonitor criado "
            f"(threshold={failure_threshold}, timeout={timeout_s}s)"
        )

    # ─────────────────────────── Interface publica ───────────────────────────

    @property
    def state(self) -> CircuitState:
        self._check_timeout()
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def pre_request(self) -> None:
        """
        Chamar antes de cada request a exchange.
        Lanca CircuitOpenError se o circuito estiver OPEN.
        """
        self._check_timeout()

        if self._state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit OPEN: exchange com muitas falhas. "
                f"Aguardando recuperacao (timeout={self._timeout_s}s). "
                f"Novos trades bloqueados."
            )

        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit HALF_OPEN: enviando request de teste...")

    def record_success(self) -> None:
        """Registrar apos request bem-sucedido."""
        self._window_requests.append((time.monotonic(), True))
        self._prune_window()
        self._consecutive_fails = 0

        if self._state == CircuitState.HALF_OPEN:
            self._consecutive_ok += 1
            if self._consecutive_ok >= self._success_threshold:
                self._close()
        else:
            self._consecutive_ok += 1

    def record_failure(self, exc: Optional[Exception] = None) -> None:
        """Registrar apos request com falha."""
        self._window_requests.append((time.monotonic(), False))
        self._prune_window()
        self._consecutive_fails += 1
        self._consecutive_ok    = 0

        error_label = type(exc).__name__ if exc else "unknown"
        logger.warning(
            f"ExchangeHealthMonitor: falha registrada ({error_label}), "
            f"consecutivas={self._consecutive_fails}"
        )

        # Verifica threshold de falhas consecutivas
        if self._consecutive_fails >= self._failure_threshold:
            self._open(reason=f"{self._consecutive_fails} falhas consecutivas")
            return

        # Verifica taxa de erro na janela
        error_rate = self._current_error_rate()
        if error_rate >= self._error_rate_pct:
            self._open(reason=f"taxa de erro={error_rate:.1f}%")

    def guard(
        self,
        fn: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        """Decorator que envolve coroutines com o circuit breaker."""
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.pre_request()
            try:
                result = await fn(*args, **kwargs)
                self.record_success()
                return result
            except CircuitOpenError:
                raise
            except Exception as exc:
                self.record_failure(exc)
                raise
        return wrapper

    def status(self) -> dict:
        """Retorna status para monitoramento / health endpoint."""
        return {
            "state":              self.state.value,
            "consecutive_fails":  self._consecutive_fails,
            "error_rate_pct":     self._current_error_rate(),
            "opened_at":          self._opened_at,
            "window_size":        len(self._window_requests),
        }

    # ─────────────────────────── Internos ────────────────────────────────────

    def _open(self, reason: str = "") -> None:
        if self._state != CircuitState.OPEN:
            self._state     = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.critical(
                f"Circuit ABERTO: {reason}. "
                f"Novos trades bloqueados por {self._timeout_s}s."
            )

    def _close(self) -> None:
        self._state             = CircuitState.CLOSED
        self._consecutive_fails = 0
        self._consecutive_ok    = 0
        self._opened_at         = None
        logger.info("Circuit FECHADO: exchange recuperada, operacao normal retomada.")

    def _check_timeout(self) -> None:
        """Transicao OPEN -> HALF_OPEN apos timeout."""
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self._timeout_s
        ):
            self._state          = CircuitState.HALF_OPEN
            self._consecutive_ok = 0
            logger.info(
                f"Circuit HALF_OPEN: timeout atingido ({self._timeout_s}s). "
                f"Testando recuperacao da exchange..."
            )

    def _prune_window(self) -> None:
        """Remove eventos fora da janela de observacao."""
        cutoff = time.monotonic() - self._window_s
        self._window_requests = [
            (ts, ok) for ts, ok in self._window_requests if ts >= cutoff
        ]

    def _current_error_rate(self) -> float:
        """Calcula taxa de erro na janela atual (%)."""
        if not self._window_requests:
            return 0.0
        total  = len(self._window_requests)
        errors = sum(1 for _, ok in self._window_requests if not ok)
        return (errors / total) * 100.0


# ────────────────────────── Instancia Global ─────────────────────────────────

_circuit_breaker: Optional[ExchangeHealthMonitor] = None


def init_circuit_breaker(
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout_s: float = 60.0,
    error_rate_pct: float = 50.0,
    window_s: float = 60.0,
) -> ExchangeHealthMonitor:
    """Inicializa instancia global do circuit breaker."""
    global _circuit_breaker
    _circuit_breaker = ExchangeHealthMonitor(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout_s=timeout_s,
        error_rate_pct=error_rate_pct,
        window_s=window_s,
    )
    return _circuit_breaker


def get_circuit_breaker() -> Optional[ExchangeHealthMonitor]:
    """Retorna instancia global, ou None se nao inicializada."""
    return _circuit_breaker
