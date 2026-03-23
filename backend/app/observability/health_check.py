"""
HealthCheckService — DOC-06 §4

Verificação de saúde ponderada com pontuação 0-100:

  Componente    Peso
  ──────────────────
  Redis          35
  MongoDB        30
  KuCoin API     25
  WebSocket      10

  score >= 90  → "healthy"
  score >= 60  → "degraded"
  score <  60  → "unhealthy"

Uso em main.py::

    from app.observability.health_check import HealthCheckService

    svc = HealthCheckService(
        redis_client=redis_manager.redis_client,
        db=get_database(),
        kucoin_client=get_kucoin_client(),    # opcional
        ws_gateway=app.state.ws_gateway,     # opcional
    )
    result = await svc.check()
    # result = {"status": "healthy", "score": 95, "checks": {...}}
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Modelos internos ─────────────────────────────────────────────────────────


class CheckResult:
    __slots__ = ("component", "ok", "latency_ms", "message")

    def __init__(
        self,
        component: str,
        ok: bool,
        latency_ms: float = 0.0,
        message: str = "",
    ) -> None:
        self.component  = component
        self.ok         = ok
        self.latency_ms = round(latency_ms, 2)
        self.message    = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":         self.ok,
            "latency_ms": self.latency_ms,
            "message":    self.message,
        }


# ─── HealthCheckService ───────────────────────────────────────────────────────


class HealthCheckService:
    """
    Executa verificações em paralelo e calcula score ponderado.

    Parâmetros
    ----------
    redis_client   : cliente Redis (opcional — None → check falha gracefully)
    db             : banco de dados Motor/AsyncIOMotorDatabase (opcional)
    kucoin_client  : cliente KuCoin (qualquer obj com método async capable) (opcional)
    ws_gateway     : WsGateway com atributo `connected` ou `is_connected` (opcional)
    """

    WEIGHTS: Dict[str, int] = {
        "redis":      35,
        "mongodb":    30,
        "kucoin_api": 25,
        "websocket":  10,
    }

    def __init__(
        self,
        *,
        redis_client: Optional[Any] = None,
        db: Optional[Any] = None,
        kucoin_client: Optional[Any] = None,
        ws_gateway: Optional[Any] = None,
    ) -> None:
        self._redis   = redis_client
        self._db      = db
        self._kucoin  = kucoin_client
        self._gateway = ws_gateway

    # ── check() principal ─────────────────────────────────────────────────────

    async def check(self) -> Dict[str, Any]:
        """
        Executa todos os checks em paralelo (asyncio.gather com return_exceptions).
        Retorna dict com status, score e detalhe por componente.
        """
        results = await asyncio.gather(
            self._check_redis(),
            self._check_mongodb(),
            self._check_kucoin_api(),
            self._check_websocket(),
            return_exceptions=True,
        )

        checks: Dict[str, Any] = {}
        score = 0

        components = ["redis", "mongodb", "kucoin_api", "websocket"]
        for component, result in zip(components, results):
            if isinstance(result, Exception):
                cr = CheckResult(component, False, 0.0, f"Exception: {result}")
            else:
                cr = result  # type: ignore[assignment]

            checks[component] = cr.to_dict()
            if cr.ok:
                score += self.WEIGHTS[component]

        if score >= 90:
            status = "healthy"
        elif score >= 60:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "score":  score,
            "checks": checks,
        }

    # ── check() rápido (sem KuCoin API) ─────────────────────────────────────

    async def check_ready(self) -> Dict[str, Any]:
        """
        Verificação rápida — apenas Redis + MongoDB (sem chamadas externas).
        Usado no endpoint /health/ready para liveness rápido.
        """
        results = await asyncio.gather(
            self._check_redis(),
            self._check_mongodb(),
            return_exceptions=True,
        )

        checks: Dict[str, Any] = {}
        score = 0
        max_score = self.WEIGHTS["redis"] + self.WEIGHTS["mongodb"]

        for component, result in zip(["redis", "mongodb"], results):
            if isinstance(result, Exception):
                cr = CheckResult(component, False, 0.0, f"Exception: {result}")
            else:
                cr = result  # type: ignore[assignment]
            checks[component] = cr.to_dict()
            if cr.ok:
                score += self.WEIGHTS[component]

        # Normaliza para 100
        normalized = int(score * 100 / max_score) if max_score > 0 else 0

        if normalized >= 90:
            status = "healthy"
        elif normalized >= 60:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "score":  normalized,
            "checks": checks,
        }

    # ── Checks individuais ────────────────────────────────────────────────────

    async def _check_redis(self) -> CheckResult:
        if self._redis is None:
            return CheckResult("redis", False, 0.0, "Redis não configurado")

        t0 = time.perf_counter()
        try:
            pong = await asyncio.wait_for(self._redis.ping(), timeout=2.0)
            latency = (time.perf_counter() - t0) * 1_000
            ok = pong is True or pong == b"PONG" or str(pong).upper() == "PONG"
            msg = "OK" if ok else f"PONG inesperado: {pong!r}"
            return CheckResult("redis", ok, latency, msg)
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - t0) * 1_000
            return CheckResult("redis", False, latency, "Timeout (>2s)")
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1_000
            return CheckResult("redis", False, latency, str(exc))

    async def _check_mongodb(self) -> CheckResult:
        if self._db is None:
            return CheckResult("mongodb", False, 0.0, "Database não configurado")

        t0 = time.perf_counter()
        try:
            await asyncio.wait_for(
                self._db.command("ping"),
                timeout=3.0,
            )
            latency = (time.perf_counter() - t0) * 1_000
            return CheckResult("mongodb", True, latency, "OK")
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - t0) * 1_000
            return CheckResult("mongodb", False, latency, "Timeout (>3s)")
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1_000
            return CheckResult("mongodb", False, latency, str(exc))

    async def _check_kucoin_api(self) -> CheckResult:
        if self._kucoin is None:
            # Tenta importar e chamar diretamente
            try:
                from app.exchanges.kucoin.client import KuCoinClient  # type: ignore
                client: Any = KuCoinClient()
                return await self._ping_kucoin(client)
            except Exception as exc:
                return CheckResult("kucoin_api", False, 0.0, f"Import error: {exc}")
        return await self._ping_kucoin(self._kucoin)

    async def _ping_kucoin(self, client: Any) -> CheckResult:
        t0 = time.perf_counter()
        try:
            # Tenta getServerTime como ping leve
            if hasattr(client, "get_server_time"):
                await asyncio.wait_for(client.get_server_time(), timeout=5.0)
            elif hasattr(client, "get_ticker"):
                await asyncio.wait_for(client.get_ticker("BTC-USDT"), timeout=5.0)
            else:
                # Fallback: GET público sem auth
                import httpx  # type: ignore
                async with httpx.AsyncClient(timeout=5.0) as http:
                    resp = await http.get("https://api.kucoin.com/api/v1/timestamp")
                    resp.raise_for_status()

            latency = (time.perf_counter() - t0) * 1_000
            msg = "OK" if latency <= 2_000 else f"Lento ({latency:.0f}ms > 2000ms)"
            ok = True
            if latency > 2_000:
                logger.warning("health_check.kucoin: latência alta %dms", int(latency))
            return CheckResult("kucoin_api", ok, latency, msg)
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - t0) * 1_000
            return CheckResult("kucoin_api", False, latency, "Timeout (>5s)")
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1_000
            return CheckResult("kucoin_api", False, latency, str(exc))

    async def _check_websocket(self) -> CheckResult:
        if self._gateway is None:
            # Tenta obter gateway global
            try:
                from app.exchanges.kucoin.ws_gateway import get_ws_gateway  # type: ignore
                gw = get_ws_gateway()
                if gw is None:
                    return CheckResult("websocket", False, 0.0, "Gateway não inicializado")
                self._gateway = gw
            except Exception as exc:
                return CheckResult("websocket", False, 0.0, f"Import error: {exc}")

        try:
            # Verifica flag de conexão — compatível com ws_gateway.py do DOC-03
            connected: bool = False
            if hasattr(self._gateway, "connected"):
                connected = bool(self._gateway.connected)
            elif hasattr(self._gateway, "is_connected"):
                val = self._gateway.is_connected
                connected = val() if callable(val) else bool(val)
            elif hasattr(self._gateway, "_connected"):
                connected = bool(self._gateway._connected)

            msg = "OK" if connected else "WebSocket desconectado"
            return CheckResult("websocket", connected, 0.0, msg)
        except Exception as exc:
            return CheckResult("websocket", False, 0.0, str(exc))
