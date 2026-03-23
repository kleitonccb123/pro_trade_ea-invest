# DOC 06 — Sistema de Monitoramento e Observabilidade
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia / DevOps

---

## 1. Objetivo

Construir um sistema de observabilidade completo que permita:

- Detectar falhas em < 30 segundos (antes do usuário perceber)
- Rastrear cada milissegundo desde o sinal até a execução
- Correlacionar logs + métricas + traces por `requestId` e `traceId`
- Dashboards em tempo real de saúde operacional
- Alertas automáticos com rota de escalação

---

## 2. Problema Atual

| Gap de Observabilidade | Impacto |
|---|---|
| Sem latência de envio de ordens | Não sabemos se estamos lentos |
| Sem rastreio de ordens perdidas | Ordens "em flight" somem silenciosamente |
| Sem métrica de taxa de acerto por bot | Não há base para otimização |
| Logs sem estrutura (strings) | Impossível correlacionar eventos |
| Circuit breaker sem métricas | Não sabemos quando aciona nem frequência |
| WebSocket reconnects sem alarme | Reconexões passam despercebidas |
| Sem health check ponderado | `/health` retorna 200 mesmo com Redis offline |

---

## 3. Arquitetura de Observabilidade

```
┌────────────────────────────────────────────────────────────────────┐
│                    STACK DE OBSERVABILIDADE                        │
│                                                                    │
│  COLETA:                                                           │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐             │
│  │  Pino.js    │   │  prom-client│   │  OpenTelemetry│            │
│  │  (Logs JSON)│   │  (Métricas) │   │  (Traces)   │             │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘             │
│         │                 │                  │                     │
│         ▼                 ▼                  ▼                     │
│  ┌──────────────────────────────────────────────────────┐         │
│  │                TRANSPORTE                            │         │
│  │   Loki (logs)   Prometheus (scrape)   Jaeger (OTLP) │         │
│  └──────────────────────────────────────────────────────┘         │
│                                                                    │
│  STORAGE + VISUALIZAÇAO:                                           │
│  ┌────────────────────────────────────────────────────┐           │
│  │                  Grafana                           │           │
│  │  Dashboard: Trading Ops | Risk | WS | Infra        │           │
│  └────────────────────────────────────────────────────┘           │
│                                                                    │
│  ALERTAS:                                                          │
│  ┌────────────────────────────────────────────────────┐           │
│  │  AlertManager → Slack / PagerDuty / Email          │           │
│  └────────────────────────────────────────────────────┘           │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Logs Estruturados

### 4.1 Logger Central

```typescript
// src/core/logger.ts

import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  formatters: {
    level: (label) => ({ level: label }),
    bindings: (bindings) => ({
      service: process.env.SERVICE_NAME ?? 'trading-backend',
      version: process.env.APP_VERSION ?? '1.0.0',
      host: bindings.hostname,
      pid: bindings.pid,
    }),
  },
  timestamp: pino.stdTimeFunctions.isoTime,
  // Redact dados sensíveis
  redact: {
    paths: ['apiKey', 'apiSecret', 'passphrase', 'authorization', 'cookie', '*.password'],
    censor: '[REDACTED]'
  }
});

// Contexto de requisição (por trace/request ID)
export function createRequestLogger(context: {
  requestId: string;
  traceId?: string;
  userId?: string;
  botId?: string;
}) {
  return logger.child(context);
}
```

### 4.2 Estrutura de Eventos Padronizados

```typescript
// TODOS os logs devem usar esta estrutura
interface LogEvent {
  event: string;          // Identificador do evento (snake_case)
  requestId?: string;     // UUID por request HTTP/WS message
  traceId?: string;       // OpenTelemetry trace ID
  userId?: string;        // Quando aplicável
  botId?: string;
  symbol?: string;
  durationMs?: number;    // Para eventos com latência
  errorCode?: string;
  // Dados do evento (campos adicionais)
  [key: string]: unknown;
}

// Exemplos de uso correto:
logger.info({ event: 'order_sent', requestId, userId, botId, symbol: 'BTC-USDT', orderId, durationMs: 230 });
logger.error({ event: 'kucoin_api_error', requestId, errorCode: '400100', httpStatus: 400, message: 'Invalid size' });
logger.warn({ event: 'ws_reconnect', connectionId, attempt: 3, backoffMs: 4000 });
```

---

## 5. Métricas — prom-client

```typescript
// src/monitoring/metrics.ts

import { Registry, Counter, Histogram, Gauge, Summary } from 'prom-client';

const register = new Registry();

// ── ORDEM / EXECUÇÃO ──────────────────────────────────────────────

export const ordersTotal = new Counter({
  name: 'trading_orders_total',
  help: 'Total de ordens enviadas',
  labelNames: ['status', 'symbol', 'side', 'type', 'userId'],
  registers: [register]
});

export const orderLatencyMs = new Histogram({
  name: 'trading_order_latency_ms',
  help: 'Latência de envio de ordem na KuCoin em milliseconds',
  labelNames: ['symbol', 'type'],
  buckets: [50, 100, 200, 500, 1000, 2000, 5000],
  registers: [register]
});

export const orderFillTimeMs = new Histogram({
  name: 'trading_order_fill_time_ms',
  help: 'Tempo do envio até confirmação de fill (via WS)',
  labelNames: ['symbol', 'type'],
  buckets: [100, 500, 1000, 2000, 5000, 10000, 30000],
  registers: [register]
});

// ── WEBSOCKET ─────────────────────────────────────────────────────

export const wsConnectionsActive = new Gauge({
  name: 'trading_ws_connections_active',
  help: 'Número de conexões WebSocket ativas',
  registers: [register]
});

export const wsMessagesTotal = new Counter({
  name: 'trading_ws_messages_total',
  help: 'Total de mensagens WebSocket recebidas',
  labelNames: ['channel', 'type'],
  registers: [register]
});

export const wsReconnectsTotal = new Counter({
  name: 'trading_ws_reconnects_total',
  help: 'Total de reconexões WebSocket',
  labelNames: ['reason'],
  registers: [register]
});

export const wsSequenceGapsTotal = new Counter({
  name: 'trading_ws_sequence_gaps_total',
  help: 'Total de gaps de sequência detectados',
  labelNames: ['channel'],
  registers: [register]
});

// ── CIRCUIT BREAKER ───────────────────────────────────────────────

export const circuitBreakerState = new Gauge({
  name: 'trading_circuit_breaker_state',
  help: 'Estado do circuit breaker (0=CLOSED, 1=HALF_OPEN, 2=OPEN)',
  labelNames: ['service'],
  registers: [register]
});

export const circuitBreakerTrips = new Counter({
  name: 'trading_circuit_breaker_trips_total',
  help: 'Total de vezes que o circuit breaker abriu',
  labelNames: ['service'],
  registers: [register]
});

// ── RISK MANAGER ──────────────────────────────────────────────────

export const riskRejections = new Counter({
  name: 'trading_risk_rejections_total',
  help: 'Total de ordens rejeitadas pelo Risk Manager',
  labelNames: ['reason', 'severity'],
  registers: [register]
});

export const riskEvaluationMs = new Summary({
  name: 'trading_risk_evaluation_ms',
  help: 'Latência de avaliação de risco em ms',
  percentiles: [0.5, 0.9, 0.99],
  registers: [register]
});

// ── REDIS ─────────────────────────────────────────────────────────

export const redisCommandDurationMs = new Histogram({
  name: 'trading_redis_command_ms',
  help: 'Latência de comandos Redis em ms',
  labelNames: ['command'],
  buckets: [1, 5, 10, 25, 50, 100],
  registers: [register]
});

// ── SISTEMA ───────────────────────────────────────────────────────

export const activeBotsGauge = new Gauge({
  name: 'trading_active_bots',
  help: 'Número de bots ativos',
  labelNames: ['plan'],
  registers: [register]
});

// Endpoint /metrics para Prometheus scrape
export async function getMetrics(): Promise<string> {
  return register.metrics();
}

export { register };
```

### 5.1 Instrumentação do OrderSender

```typescript
// Dentro do OrderSender.send(), instrumentar:
const end = orderLatencyMs.startTimer({ symbol, type });
try {
  const result = await this.http.post('/api/v1/orders', payload);
  ordersTotal.inc({ status: 'success', symbol, side, type, userId });
  return result;
} catch (err) {
  ordersTotal.inc({ status: 'error', symbol, side, type, userId });
  throw err;
} finally {
  end(); // Registra latência automaticamente
}
```

---

## 6. Health Check Ponderado

```typescript
// src/monitoring/health.ts

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  score: number;      // 0-100
  checks: Record<string, CheckResult>;
}

interface CheckResult {
  status: 'ok' | 'warn' | 'fail';
  latencyMs?: number;
  details?: string;
}

export class HealthCheckService {
  async check(): Promise<HealthStatus> {
    const [redisCheck, mongoCheck, kucoinCheck, wsCheck] = await Promise.allSettled([
      this.checkRedis(),
      this.checkMongo(),
      this.checkKuCoinApi(),
      this.checkWebSocket()
    ]);

    const checks: Record<string, CheckResult> = {
      redis: this.resolveCheck(redisCheck),
      mongodb: this.resolveCheck(mongoCheck),
      kucoin_api: this.resolveCheck(kucoinCheck),
      websocket: this.resolveCheck(wsCheck)
    };

    // Pesos por criticidade
    const weights: Record<string, number> = {
      redis: 35,     // Critical
      mongodb: 30,   // Critical
      kucoin_api: 25, // Important
      websocket: 10  // Degraded se offline
    };

    let score = 0;
    for (const [key, result] of Object.entries(checks)) {
      const weight = weights[key] ?? 10;
      if (result.status === 'ok') score += weight;
      else if (result.status === 'warn') score += weight * 0.5;
    }

    return {
      status: score >= 90 ? 'healthy' : score >= 60 ? 'degraded' : 'unhealthy',
      score,
      checks
    };
  }

  private async checkRedis(): Promise<CheckResult> {
    const start = Date.now();
    await this.redis.ping();
    return { status: 'ok', latencyMs: Date.now() - start };
  }

  private async checkKuCoinApi(): Promise<CheckResult> {
    const start = Date.now();
    try {
      await this.kucoin.getServerTime();
      const latencyMs = Date.now() - start;
      return {
        status: latencyMs > 2000 ? 'warn' : 'ok',
        latencyMs,
        details: latencyMs > 2000 ? 'KuCoin API lenta' : undefined
      };
    } catch (e: any) {
      return { status: 'fail', details: e.message };
    }
  }

  private resolveCheck(settled: PromiseSettledResult<CheckResult>): CheckResult {
    if (settled.status === 'fulfilled') return settled.value;
    return { status: 'fail', details: settled.reason?.message };
  }
}
```

---

## 7. Alertas — Regras PrometheusRule

```yaml
# monitoring/alerts/trading-alerts.yaml
groups:
  - name: trading_critical
    rules:
      # Ordem enviada mas sem fill em 30s (market order)
      - alert: OrderFillTimeout
        expr: trading_order_fill_time_ms_bucket{le="30000",type="market"} < trading_orders_total{status="success",type="market"} * 0.95
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Market orders sem fill em 30s"

      # Circuit breaker aberto por > 2min
      - alert: CircuitBreakerOpen
        expr: trading_circuit_breaker_state{service="kucoin"} == 2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker KuCoin aberto por > 2min"

      # WebSocket reconectando frequentemente
      - alert: FrequentWsReconnects
        expr: rate(trading_ws_reconnects_total[5m]) > 0.5
        labels:
          severity: warning
        annotations:
          summary: "Mais de 1 reconexão WS por 2min nos últimos 5min"

      # Alta taxa de rejeição por risk manager
      - alert: HighRiskRejectionRate
        expr: rate(trading_risk_rejections_total[5m]) > 10
        labels:
          severity: warning
        annotations:
          summary: "Risk Manager rejeitando > 10 ordens/min"

      # Redis com latência alta
      - alert: RedisHighLatency
        expr: histogram_quantile(0.99, rate(trading_redis_command_ms_bucket[5m])) > 100
        labels:
          severity: warning
        annotations:
          summary: "Redis P99 > 100ms"
```

---

## 8. Dashboard Grafana — Queries Principais

```
# Total de ordens por hora
sum(rate(trading_orders_total[1h])) by (status)

# Latência P50/P95/P99 de envio de ordens
histogram_quantile(0.99, rate(trading_order_latency_ms_bucket[5m]))

# Circuit breaker state timeline
trading_circuit_breaker_state{service="kucoin"}

# Bots ativos por plano
trading_active_bots

# Taxa de rejeição de risco
sum(rate(trading_risk_rejections_total[5m])) by (reason)

# WS messages por channel
sum(rate(trading_ws_messages_total[1m])) by (channel)
```

---

## 9. Testes Obrigatórios

```typescript
describe('HealthCheck', () => {
  it('deve retornar unhealthy quando Redis offline', async () => {
    redisMock.ping.mockRejectedValue(new Error('ECONNREFUSED'));
    const health = await healthCheck.check();
    // Redis tem peso 35 => score <= 65 => degraded ou unhealthy
    expect(['degraded', 'unhealthy']).toContain(health.status);
    expect(health.checks.redis.status).toBe('fail');
  });

  it('deve retornar degraded quando KuCoin API lenta', async () => {
    kucoinMock.getServerTime.mockImplementation(() =>
      new Promise(r => setTimeout(r, 2500))
    );
    const health = await healthCheck.check();
    expect(health.checks.kucoin_api.status).toBe('warn');
  });
});
```

---

## 10. Checklist de Implementação

- [ ] `pino` configurado com `redact` para dados sensíveis
- [ ] Todos os eventos de log usam `event` field padronizado
- [ ] `requestId` propagado por toda a stack (middleware → service → log)
- [ ] Endpoint `GET /metrics` respondendo com format Prometheus
- [ ] Todas as métricas listadas implementadas e instrumentadas
- [ ] Health check ponderado em `GET /health` e `GET /health/ready`
- [ ] AlertManager configurado com rotas para Slack e email
- [ ] Dashboard Grafana com 4 painéis: Trading Ops, Risk, WS, Infra
- [ ] Logs enviados para Loki (ou CloudWatch em produção)
- [ ] Retenção de logs: 30 dias; métricas: 90 dias

---

## 11. Critérios de Validação Final

| Critério | Alvo |
|---|---|
| MTTD (Mean Time to Detect) de falha | < 30 segundos |
| Cobertura de métricas | 100% dos paths críticos instrumentados |
| Health check responsivo | < 500ms resposta |
| Logs 100% estruturados | 0 `console.log` ou strings não estruturadas |
| Alertas sem falsos positivos | < 2 alertas falsos por semana |
