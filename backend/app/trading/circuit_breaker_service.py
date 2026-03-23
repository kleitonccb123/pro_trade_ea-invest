"""
CircuitBreakerService — Task 3.2

Serviço de produção que combina:
  1. ExchangeHealthMonitor (circuit breaker base)
  2. Health probes ativas (testa exchange periodicamente)
  3. Alerta automático quando circuito abre/fecha
  4. Métricas Prometheus (trading_circuit_breaker_state)
  5. Recovery automático com probes de saúde

Arquitetura:
  ┌─────────────────────────────────────────────────────┐
  │              CircuitBreakerService                   │
  │                                                     │
  │  ┌───────────────┐   ┌──────────────────────────┐  │
  │  │HealthMonitor  │   │  HealthProbeTask (background)│
  │  │(circuit state)│   │  - pinga exchange a cada Ns  │
  │  │               │   │  - record_success/failure     │
  │  └───────┬───────┘   │  - detecta recovery           │
  │          │            └──────────────────────────┘  │
  │          │                                          │
  │  ┌───────▼───────┐   ┌─────────────────────────┐   │
  │  │  Prometheus    │   │  AlertManager            │   │
  │  │  (métricas)    │   │  (notifica quando abre)  │   │
  │  └───────────────┘   └─────────────────────────┘   │
  └─────────────────────────────────────────────────────┘

Integração no main.py:
    from app.trading.circuit_breaker_service import (
        init_circuit_breaker_service, shutdown_circuit_breaker_service
    )

    @app.on_event("startup")
    async def on_startup():
        await init_circuit_breaker_service()

    @app.on_event("shutdown")
    async def on_shutdown():
        await shutdown_circuit_breaker_service()
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from app.trading.circuit_breaker import (
    CircuitOpenError,
    CircuitState,
    ExchangeHealthMonitor,
    get_circuit_breaker,
    init_circuit_breaker,
)

logger = logging.getLogger(__name__)

# Tenta importar Prometheus — graceful se não disponível
try:
    from app.observability.metrics import (
        trading_circuit_breaker_state,
        trading_circuit_breaker_trips,
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


class CircuitBreakerService:
    """
    Serviço de circuit breaker com:
    - Health probes ativas em background
    - Alertas automáticos (callback)
    - Métricas Prometheus
    - Recovery automático
    """

    def __init__(
        self,
        *,
        probe_interval_s: float = 30.0,
        probe_timeout_s: float = 10.0,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        recovery_timeout_s: float = 60.0,
        exchange: str = "kucoin",
    ) -> None:
        self.exchange = exchange
        self.probe_interval_s = probe_interval_s
        self.probe_timeout_s = probe_timeout_s

        # Inicializa o circuit breaker base (global)
        self.monitor = init_circuit_breaker(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_s=recovery_timeout_s,
        )

        # Background tasks
        self._probe_task: Optional[asyncio.Task] = None
        self._running = False

        # Callbacks de alerta
        self._alert_callbacks: List[Callable] = []

        # Histórico de eventos (últimos 100)
        self._event_log: List[Dict[str, Any]] = []
        self._max_events = 100

        # Estado anterior (para detectar transições)
        self._prev_state = CircuitState.CLOSED

        logger.info(
            f"CircuitBreakerService criado (exchange={exchange}, "
            f"probe_interval={probe_interval_s}s, "
            f"failure_threshold={failure_threshold})"
        )

    # ─────────────────── Lifecycle ───────────────────

    async def start(self) -> None:
        """Inicia health probes em background."""
        if self._running:
            return
        self._running = True
        self._probe_task = asyncio.create_task(self._probe_loop())
        self._update_metrics()
        logger.info(f"CircuitBreakerService iniciado (probe a cada {self.probe_interval_s}s)")

    async def stop(self) -> None:
        """Para tudo de forma graciosa."""
        self._running = False
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass
        logger.info("CircuitBreakerService parado")

    # ─────────────────── Alert Callbacks ───────────────────

    def on_alert(self, callback: Callable) -> None:
        """
        Registra callback para alertas.

        O callback recebe: (event_type: str, details: dict)
        event_type pode ser: "circuit_opened", "circuit_closed", "circuit_half_open",
                             "probe_failed", "probe_recovered"
        """
        self._alert_callbacks.append(callback)

    async def _dispatch_alert(self, event_type: str, details: Dict[str, Any]) -> None:
        """Dispara alertas para todos os callbacks registrados."""
        event = {
            "type": event_type,
            "exchange": self.exchange,
            "timestamp": datetime.utcnow().isoformat(),
            **details,
        }

        # Log do evento
        self._event_log.append(event)
        if len(self._event_log) > self._max_events:
            self._event_log = self._event_log[-self._max_events:]

        # Loga no nível apropriado
        if event_type == "circuit_opened":
            logger.critical(f"ALERTA: Circuit breaker ABERTO — {details.get('reason', '')}")
        elif event_type == "circuit_closed":
            logger.info(f"RECUPERADO: Circuit breaker fechado — exchange normalizada")
        elif event_type == "probe_failed":
            logger.warning(f"Health probe falhou: {details.get('error', '')}")

        # Dispara callbacks (fire-and-forget, sem bloquear)
        for cb in self._alert_callbacks:
            try:
                result = cb(event_type, event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error(f"Erro no alert callback: {exc}")

    # ─────────────────── Health Probes ───────────────────

    async def _probe_loop(self) -> None:
        """Loop que testa saúde da exchange periodicamente."""
        while self._running:
            try:
                await asyncio.sleep(self.probe_interval_s)
                if not self._running:
                    break
                await self._run_probe()
                self._check_state_transition()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Erro no probe loop: {exc}")

    async def _run_probe(self) -> None:
        """
        Executa um health probe na exchange.

        Se o circuit breaker está OPEN ou HALF_OPEN, esta probe
        tenta reconectar ativamente para acelerar recovery.
        """
        current_state = self.monitor.state

        # Se CLOSED, probe serve para monitoramento contínuo
        # Se OPEN/HALF_OPEN, probe serve para testar recovery
        try:
            success = await self._ping_exchange()
            if success:
                self.monitor.record_success()
                if current_state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
                    logger.info(
                        f"Probe: exchange respondendo OK "
                        f"(state={current_state.value})"
                    )
            else:
                self.monitor.record_failure(Exception("Probe retornou falha"))
                if current_state == CircuitState.CLOSED:
                    await self._dispatch_alert("probe_failed", {
                        "error": "Probe retornou falha",
                        "state": current_state.value,
                    })
        except Exception as exc:
            self.monitor.record_failure(exc)
            if current_state == CircuitState.CLOSED:
                await self._dispatch_alert("probe_failed", {
                    "error": str(exc),
                    "state": current_state.value,
                })

    async def _ping_exchange(self) -> bool:
        """
        Testa conectividade com a exchange.

        Tenta usar o endpoint de timestamp da KuCoin (leve, sem auth).
        Fallback: sempre True se não houver teste disponível.
        """
        try:
            import aiohttp
            url = "https://api.kucoin.com/api/v1/timestamp"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.probe_timeout_s),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("code") == "200000"
                    return False
        except ImportError:
            # aiohttp não disponível — assume OK
            logger.debug("aiohttp não disponível para health probe")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Health probe timeout ({self.probe_timeout_s}s)")
            return False
        except Exception as exc:
            logger.warning(f"Health probe falhou: {exc}")
            return False

    # ─────────────────── State Transitions ───────────────────

    def _check_state_transition(self) -> None:
        """Detecta transições de estado e dispara alertas/métricas."""
        current = self.monitor.state
        if current == self._prev_state:
            return

        # Transição detectada
        logger.info(
            f"Circuit breaker: {self._prev_state.value} → {current.value}"
        )

        if current == CircuitState.OPEN and self._prev_state != CircuitState.OPEN:
            asyncio.create_task(self._dispatch_alert("circuit_opened", {
                "reason": "Falhas consecutivas excederam threshold",
                "previous_state": self._prev_state.value,
                "consecutive_fails": self.monitor._consecutive_fails,
            }))
            if _HAS_PROMETHEUS:
                trading_circuit_breaker_trips.labels(service=self.exchange).inc()

        elif current == CircuitState.CLOSED and self._prev_state != CircuitState.CLOSED:
            asyncio.create_task(self._dispatch_alert("circuit_closed", {
                "previous_state": self._prev_state.value,
                "recovery_time_s": self._estimate_recovery_time(),
            }))

        elif current == CircuitState.HALF_OPEN:
            asyncio.create_task(self._dispatch_alert("circuit_half_open", {
                "previous_state": self._prev_state.value,
            }))

        self._prev_state = current
        self._update_metrics()

    def _update_metrics(self) -> None:
        """Atualiza gauge Prometheus com estado atual."""
        if not _HAS_PROMETHEUS:
            return
        state_map = {
            CircuitState.CLOSED: 0,
            CircuitState.HALF_OPEN: 1,
            CircuitState.OPEN: 2,
        }
        trading_circuit_breaker_state.labels(
            service=self.exchange
        ).set(state_map.get(self.monitor.state, 0))

    def _estimate_recovery_time(self) -> float:
        """Estima tempo de recovery baseado no log de eventos."""
        opened_events = [
            e for e in self._event_log
            if e.get("type") == "circuit_opened"
        ]
        if not opened_events:
            return 0.0
        last_opened = opened_events[-1]
        try:
            opened_at = datetime.fromisoformat(last_opened["timestamp"])
            return (datetime.utcnow() - opened_at).total_seconds()
        except (KeyError, ValueError):
            return 0.0

    # ─────────────────── Status / Dashboard ───────────────────

    def status(self) -> Dict[str, Any]:
        """Retorna status completo para dashboard."""
        monitor_status = self.monitor.status()
        return {
            "exchange": self.exchange,
            "state": monitor_status["state"],
            "consecutive_fails": monitor_status["consecutive_fails"],
            "error_rate_pct": monitor_status["error_rate_pct"],
            "window_size": monitor_status["window_size"],
            "probe_interval_s": self.probe_interval_s,
            "running": self._running,
            "recent_events": self._event_log[-10:],
        }

    # ─────────────────── Guard (shortcut) ───────────────────

    def pre_request(self) -> None:
        """Alias para uso nos serviços."""
        self.monitor.pre_request()
        self._check_state_transition()

    def record_success(self) -> None:
        self.monitor.record_success()
        self._check_state_transition()

    def record_failure(self, exc: Optional[Exception] = None) -> None:
        self.monitor.record_failure(exc)
        self._check_state_transition()

    async def guard(self, fn, *args, **kwargs):
        """Executa fn protegida pelo circuit breaker."""
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


# ═══════════════════════════════════════════════════════════════════════
# Singleton & Funções de módulo
# ═══════════════════════════════════════════════════════════════════════

_service: Optional[CircuitBreakerService] = None


async def init_circuit_breaker_service(
    *,
    exchange: str = "kucoin",
    probe_interval_s: float = 30.0,
    failure_threshold: int = 5,
    recovery_timeout_s: float = 60.0,
    alert_callback: Optional[Callable] = None,
) -> CircuitBreakerService:
    """Inicializa e inicia o serviço global de circuit breaker."""
    global _service
    _service = CircuitBreakerService(
        exchange=exchange,
        probe_interval_s=probe_interval_s,
        failure_threshold=failure_threshold,
        recovery_timeout_s=recovery_timeout_s,
    )
    if alert_callback:
        _service.on_alert(alert_callback)
    await _service.start()
    return _service


async def shutdown_circuit_breaker_service() -> None:
    """Para o serviço global."""
    global _service
    if _service:
        await _service.stop()
        _service = None


def get_circuit_breaker_service() -> Optional[CircuitBreakerService]:
    """Retorna o serviço global, ou None."""
    return _service
