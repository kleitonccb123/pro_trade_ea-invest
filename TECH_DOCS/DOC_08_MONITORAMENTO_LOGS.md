# DOC 08 — Sistema de Monitoramento e Logs

> **Nível:** Produção | **Escopo:** Structured Logging, Alertas, Métricas Prometheus, Health Checks  
> **Prioridade:** Alta — sem observability, falhas em produção são cegas

---

## 1. OBJETIVO

Implementar observabilidade completa do sistema:
- **Structured logging** — logs em JSON para ingestão em ferramentas (Loki, CloudWatch, etc.)
- **Métricas Prometheus** — para Grafana, alertas automáticos
- **Health checks** — para balanceadores e orquestração
- **Alertas** — Telegram/e-mail quando algo crítico acontece
- **Log de auditoria** — toda ação financeira rastreável

---

## 2. STRUCTURED LOGGING

```python
# backend/app/core/logging_config.py

import logging
import json
import time
import traceback
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Formata todos os logs como JSON para ingestão em sistemas de log centralizados.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Contexto extra (se passado via extra={...})
        for key in ("user_id", "bot_instance_id", "trade_id", "pair", "request_id"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        # Exception info
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Handler de console (JSON)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Silenciar logs muito verbosos
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

### 2.1 Logger Contextual

```python
# backend/app/core/context_logger.py

import logging
from typing import Optional


class BotLogger:
    """Logger com contexto fixo de bot/usuário para não repetir em cada chamada."""

    def __init__(self, bot_instance_id: str, user_id: str, pair: str):
        self._logger = logging.getLogger(f"bot.{bot_instance_id[:8]}")
        self._extra = {
            "bot_instance_id": bot_instance_id,
            "user_id": user_id,
            "pair": pair,
        }

    def _log(self, level: str, message: str, **kwargs):
        extra = {**self._extra, **kwargs}
        getattr(self._logger, level)(message, extra=extra)

    def info(self, message: str, **kwargs): self._log("info", message, **kwargs)
    def warning(self, message: str, **kwargs): self._log("warning", message, **kwargs)
    def error(self, message: str, **kwargs): self._log("error", message, **kwargs)
    def critical(self, message: str, **kwargs): self._log("critical", message, **kwargs)
    def debug(self, message: str, **kwargs): self._log("debug", message, **kwargs)

    def trade_opened(self, price: float, qty: float, funds: float):
        self.info(
            f"📈 Posição aberta | preço={price} | qty={qty:.6f} | funds={funds:.2f} USDT",
            event="trade_opened", entry_price=price, quantity=qty, funds_usdt=funds
        )

    def trade_closed(self, price: float, pnl: float, reason: str):
        emoji = "✅" if pnl >= 0 else "❌"
        self.info(
            f"{emoji} Trade fechada | preço={price} | PnL={pnl:+.4f} USDT | motivo={reason}",
            event="trade_closed", exit_price=price, pnl_net_usdt=pnl, reason=reason
        )

    def risk_triggered(self, reason: str, details: dict):
        self.critical(
            f"⚠️ RISCO: {reason}",
            event="risk_triggered", stop_reason=reason, **details
        )
```

---

## 3. MÉTRICAS PROMETHEUS

```python
# backend/app/monitoring/metrics.py

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest

REGISTRY = CollectorRegistry()

# Contadores
trades_total = Counter(
    "crypto_trades_total",
    "Total de trades executadas",
    ["robot_id", "pair", "exit_reason"],
    registry=REGISTRY
)
bot_errors_total = Counter(
    "crypto_bot_errors_total",
    "Total de erros de bot",
    ["bot_instance_id", "error_type"],
    registry=REGISTRY
)
kucoin_requests_total = Counter(
    "crypto_kucoin_requests_total",
    "Requests para KuCoin API",
    ["endpoint", "status"],
    registry=REGISTRY
)

# Gauges
active_bots = Gauge(
    "crypto_active_bots",
    "Número de bots ativos",
    registry=REGISTRY
)
open_positions = Gauge(
    "crypto_open_positions",
    "Posições abertas no momento",
    registry=REGISTRY
)
ws_connections = Gauge(
    "crypto_ws_connections",
    "Conexões WebSocket KuCoin ativas",
    registry=REGISTRY
)

# Histogramas
trade_duration_minutes = Histogram(
    "crypto_trade_duration_minutes",
    "Duração das trades em minutos",
    buckets=[5, 15, 30, 60, 120, 360, 720, 1440],
    registry=REGISTRY
)
pnl_distribution = Histogram(
    "crypto_pnl_usdt",
    "Distribuição de PnL por trade em USDT",
    buckets=[-100, -50, -20, -10, -5, 0, 5, 10, 20, 50, 100, 500],
    registry=REGISTRY
)
api_latency_seconds = Histogram(
    "crypto_kucoin_api_latency_seconds",
    "Latência de requests à KuCoin API",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=REGISTRY
)


# ── Endpoint Prometheus ────────────────────────────────────────────────────
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

metrics_router = APIRouter()

@metrics_router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def get_metrics():
    """Endpoint scrapeado pelo Prometheus a cada 15 segundos."""
    return generate_latest(REGISTRY)
```

---

## 4. LOG DE AUDITORIA FINANCEIRA

```python
# backend/app/monitoring/audit_log.py
# IMUTÁVEL — nunca deletar entradas financeiras

async def log_financial_event(
    db,
    event_type: str,        # "order_placed", "order_filled", "balance_changed", etc.
    user_id: str,
    bot_instance_id: str,
    amount_usdt: float,
    metadata: dict,
    severity: str = "info"
):
    """
    Log de auditoria financeira — imutável para compliance.
    Nunca chamar delete nessa coleção.
    """
    doc = {
        "event_type": event_type,
        "user_id": user_id,
        "bot_instance_id": bot_instance_id,
        "amount_usdt": amount_usdt,
        "metadata": metadata,
        "severity": severity,
        "timestamp": datetime.utcnow(),
        "schema_version": "1.0",
    }
    await db["audit_log"].insert_one(doc)
```

### 4.1 Índice da Coleção audit_log

```javascript
// Retenção: 2 anos (legal requirement para transações financeiras)
// Sem TTL — deleção manual mediante compliance
db.audit_log.createIndex({ "user_id": 1, "timestamp": -1 })
db.audit_log.createIndex({ "event_type": 1, "timestamp": -1 })
db.audit_log.createIndex({ "bot_instance_id": 1, "timestamp": -1 })
```

---

## 5. SISTEMA DE ALERTAS

```python
# backend/app/monitoring/alerting.py

import aiohttp
import logging
from enum import Enum

logger = logging.getLogger("alerting")


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TelegramAlerter:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async def send(self, message: str, level: AlertLevel = AlertLevel.INFO):
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}[level]
        text = f"{emoji} *CryptoTradeHub Alert*\n\n{message}"

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(self.base_url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                })
        except Exception as e:
            logger.error(f"Falha ao enviar alerta Telegram: {e}")


# ── Alertas Importantes ────────────────────────────────────────────────────
async def alert_bot_stopped_by_risk(alerter: TelegramAlerter, user_id: str, bot_name: str, reason: str, pnl: float):
    await alerter.send(
        f"Bot *{bot_name}* do usuário `{user_id}` foi parado por risco.\n"
        f"Motivo: `{reason}`\n"
        f"PnL da sessão: `{pnl:+.4f} USDT`",
        AlertLevel.CRITICAL
    )

async def alert_kucoin_connectivity_lost(alerter: TelegramAlerter, minutes_offline: int):
    await alerter.send(
        f"KuCoin API inacessível há *{minutes_offline} minutos*.\n"
        f"Todos os bots foram pausados.",
        AlertLevel.CRITICAL
    )

async def alert_high_error_rate(alerter: TelegramAlerter, errors_per_min: int):
    await alerter.send(
        f"Taxa de erros elevada: *{errors_per_min} erros/min*.\n"
        f"Investigar imediatamente.",
        AlertLevel.WARNING
    )
```

---

## 6. HEALTH CHECK ENDPOINTS

```python
# backend/app/monitoring/health.py

@router.get("/health")
async def health_check():
    """Verificação básica — usada por load balancer."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/detailed")
async def detailed_health_check():
    """Verificação completa — usada por monitoramento."""
    checks = {}

    # MongoDB
    try:
        db = get_db()
        await db.command("ping")
        checks["mongodb"] = {"status": "ok"}
    except Exception as e:
        checks["mongodb"] = {"status": "error", "detail": str(e)}

    # Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "detail": str(e)}

    # KuCoin API
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get("https://api.kucoin.com/api/v1/timestamp", timeout=aiohttp.ClientTimeout(total=5))
            checks["kucoin_api"] = {"status": "ok" if r.status == 200 else "degraded"}
    except Exception:
        checks["kucoin_api"] = {"status": "error"}

    # Engine
    redis = await get_redis()
    active_bots_count = await redis.scard("active_bots")
    checks["engine"] = {"status": "ok", "active_bots": active_bots_count}

    overall = "ok" if all(c["status"] == "ok" for c in checks.values()) else "degraded"
    return {"status": overall, "checks": checks, "timestamp": datetime.utcnow().isoformat()}
```

---

## 7. DASHBOARD DE MONITORAMENTO (FRONTEND ADMIN)

```
Métricas a exibir:
├─ Total de bots ativos (Gauge)
├─ Trades por hora (Rate)
├─ Error rate (Rate)
├─ Latência média KuCoin API (Histogram)
├─ PnL total da plataforma (Gauge)
├─ Conexões WebSocket ativas (Gauge)
└─ Health de cada serviço (MongoDB, Redis, KuCoin)

Gráficos Grafana sugeridos:
├─ Trades over time (rate)
├─ P&L distribution (histogram)
├─ Bot lifecycle (created/started/stopped/error)
└─ KuCoin API latency percentiles (p50, p95, p99)
```

---

## 8. CHECKLIST

- [ ] `JSONFormatter` configurado para todos os loggers
- [ ] `BotLogger` com contexto fixo usado em todos os workers
- [ ] Prometheus endpoint `/metrics` exposto e protegido
- [ ] Counters para: trades, erros, requests KuCoin
- [ ] Gauges para: bots ativos, posições abertas, conexões WS
- [ ] Histograma de latência da KuCoin API
- [ ] `audit_log` coleção imutável para eventos financeiros
- [ ] `detailed_health` verificando MongoDB + Redis + KuCoin
- [ ] Alertas Telegram para: bot parado por risco, KuCoin offline, error burst
- [ ] Grafana dashboard configurado com datasource Prometheus
