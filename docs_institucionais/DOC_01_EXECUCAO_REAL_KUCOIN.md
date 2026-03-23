# DOC 01 — Execução Real Segura na KuCoin
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia  
> **Status:** Implementação Obrigatória antes de produção real

---

## 1. Objetivo

Garantir que 100% das ordens enviadas à API REST da KuCoin sejam:

- **Idempotentes** — nunca enviadas duas vezes para o mesmo evento
- **Rastreáveis** — com `clientOid` único e persistido antes do envio
- **Auditadas** — toda execução registrada no `ImmutableJournal`
- **Confirmadas** — aceitar como executada somente após WebSocket `execution report`
- **Reconciliadas** — comparadas com estado real da exchange periodicamente
- **Recuperáveis** — capaz de retomar após falha de rede, restart ou crash

O objetivo final é: **nenhuma ordem perdida, nenhuma ordem duplicada, zero inconsistência de saldo.**

---

## 2. Problema Atual

O sistema atual apresenta os seguintes problemas estruturais na execução de ordens:

| Problema | Risco |
|---|---|
| `clientOid` gerado no momento do envio (não pré-persistido) | Crash entre geração e envio = impossível saber se foi enviada |
| Retry sem controle de idempotência | Pode criar ordens duplicadas na exchange |
| Confirmação de execução via polling REST | Alta latência, race condition |
| Sem verificação de saldo atômico antes do envio | Ordens rejeitadas após passar por toda a fila |
| Ausência de fila transacional entre estratégia e exchange | Ordens perdidas em crash do processo |
| Reconciliação manual / não automatizada | Divergências nunca detectadas |

---

## 3. Riscos se Não Corrigir

| Cenário de Falha | Consequência Financeira |
|---|---|
| Retry duplicado executa 2 ordens de compra | Dobra a posição sem intenção |
| Crash pós-envio sem confirmação | Posição aberta não registrada no PositionManager |
| Saldo insuficiente detectado só na exchange | Rejeição = oportunidade perdida + recursos bloqueados |
| Reconciliação ausente por 24h | Hedge incorreto, saldo incorreto, P&L fictício |
| clientOid não persistido antes do envio | Impossível saber se ordem existe na exchange pós-restart |

---

## 4. Arquitetura Proposta

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ESTRATÉGIA (Strategy Engine)                 │
│  Gera: SignalEvent { symbol, side, qty, strategy_id, signal_id }   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Publish
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FILA TRANSACIONAL (Redis Stream)                 │
│  Stream: orders:pending                                             │
│  Cada mensagem: { clientOid (pré-gerado), ...payload }             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ XREADGROUP (consumer group)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ORDER MANAGER                                │
│                                                                     │
│  1. Pre-flight check (saldo, limites risk)                         │
│  2. Idempotency check (clientOid já existe?)                       │
│  3. Persist PendingOrder no DB (status=PENDING_SEND)               │
│  4. Envio HTTP → KuCoin REST API                                   │
│  5. Persist response (orderId real)                                │
│  6. Update status → SENT                                           │
│  7. XACK na fila (só após persist do orderId)                      │
└───────────────┬──────────────────────────────┬──────────────────────┘
                │                              │
                ▼                              ▼
┌──────────────────────┐          ┌─────────────────────────────┐
│  KuCoin REST API     │          │  WebSocket (Private Channel) │
│  POST /api/v1/orders │          │  /trade/orders              │
└──────────────────────┘          │                             │
                                  │  Eventos:                   │
                                  │  - open                     │
                                  │  - match (partial fill)     │
                                  │  - filled                   │
                                  │  - canceled                 │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  EXECUTION PROCESSOR         │
                                  │  - Atualiza PositionManager  │
                                  │  - Registra ImmutableJournal │
                                  │  - Dispara TP/SL automático  │
                                  │  - Notifica usuário          │
                                  └──────────────────────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  RECONCILIATION SERVICE      │
                                  │  (rodando a cada 60s)        │
                                  │  REST GET /fills → compara   │
                                  │  com DB → corrige divergência│
                                  └──────────────────────────────┘
```

---

## 5. Fluxo Detalhado — Passo a Passo

### Passo 1: Geração do ClientOid (PRÉ-PERSISTÊNCIA)

O `clientOid` deve ser gerado e persistido **antes** de qualquer tentativa de envio.

```typescript
// src/order/idempotency.ts

import { v4 as uuidv4 } from 'uuid';
import { createHash } from 'crypto';

export interface IdempotencyKey {
  clientOid: string;        // Enviado para a KuCoin como clientOid
  idempotencyToken: string; // Hash interno para detectar duplicatas de signal
}

/**
 * Gera clientOid determinístico baseado no signal_id + bot_id.
 * Isso garante que o mesmo sinal NUNCA gera dois clientOids diferentes,
 * mesmo que o processo reinicie.
 */
export function generateClientOid(
  signalId: string,
  botId: string,
  attempt: number = 0
): IdempotencyKey {
  // Token baseado no conteúdo do sinal (determinístico)
  const idempotencyToken = createHash('sha256')
    .update(`${signalId}:${botId}:${attempt}`)
    .digest('hex')
    .substring(0, 32);

  // KuCoin aceita max 32 chars alfanumérico
  const clientOid = idempotencyToken;

  return { clientOid, idempotencyToken };
}
```

### Passo 2: Verificação de Idempotência

```typescript
// src/order/idempotency-store.ts

import Redis from 'ioredis';

export class IdempotencyStore {
  private redis: Redis;
  private TTL_SECONDS = 86400 * 7; // 7 dias

  constructor(redis: Redis) {
    this.redis = redis;
  }

  /**
   * Verifica se clientOid já foi processado.
   * Retorna o resultado anterior se já existir (idempotência).
   */
  async checkAndSet(
    clientOid: string,
    payload: object
  ): Promise<{ isDuplicate: boolean; existingResult?: object }> {
    const key = `idempotency:order:${clientOid}`;
    
    // SET NX: só seta se não existir
    const result = await this.redis.set(
      key,
      JSON.stringify({ payload, timestamp: Date.now(), status: 'PROCESSING' }),
      'EX',
      this.TTL_SECONDS,
      'NX'
    );

    if (result === null) {
      // Já existe — buscar resultado armazenado
      const existing = await this.redis.get(key);
      return {
        isDuplicate: true,
        existingResult: existing ? JSON.parse(existing) : undefined
      };
    }

    return { isDuplicate: false };
  }

  async markCompleted(clientOid: string, orderId: string, status: string): Promise<void> {
    const key = `idempotency:order:${clientOid}`;
    const existing = await this.redis.get(key);
    if (existing) {
      const data = JSON.parse(existing);
      await this.redis.set(
        key,
        JSON.stringify({ ...data, status, orderId, completedAt: Date.now() }),
        'EX',
        this.TTL_SECONDS
      );
    }
  }

  async markFailed(clientOid: string, error: string): Promise<void> {
    const key = `idempotency:order:${clientOid}`;
    const existing = await this.redis.get(key);
    if (existing) {
      const data = JSON.parse(existing);
      await this.redis.set(
        key,
        JSON.stringify({ ...data, status: 'FAILED', error, failedAt: Date.now() }),
        'EX',
        this.TTL_SECONDS
      );
    }
  }
}
```

### Passo 3: Pre-flight Check (Saldo + Risk)

```typescript
// src/order/preflight.ts

import { Decimal } from 'decimal.js';
import { KuCoinClient } from '../exchanges/kucoin/client';
import { RiskManager } from '../risk/risk-manager';
import { PositionManager } from '../position/position-manager';

export interface PreflightResult {
  approved: boolean;
  rejectionReason?: string;
  availableBalance: Decimal;
  requiredBalance: Decimal;
}

export class PreflightChecker {
  constructor(
    private kucoin: KuCoinClient,
    private riskManager: RiskManager,
    private positionManager: PositionManager
  ) {}

  async check(params: {
    userId: string;
    botId: string;
    symbol: string;
    side: 'buy' | 'sell';
    size: Decimal;
    price: Decimal;
  }): Promise<PreflightResult> {
    const { userId, botId, symbol, side, size, price } = params;

    // 1. Verificar saldo disponível na exchange
    const [base, quote] = symbol.split('-');
    const currency = side === 'buy' ? quote : base;

    const accounts = await this.kucoin.getAccounts('trade');
    const account = accounts.find(a => a.currency === currency);
    const availableBalance = new Decimal(account?.available ?? '0');

    // 2. Calcular valor necessário
    const requiredBalance = side === 'buy'
      ? size.mul(price).mul(new Decimal('1.001')) // +0.1% fee buffer
      : size;

    if (availableBalance.lt(requiredBalance)) {
      return {
        approved: false,
        rejectionReason: `Saldo insuficiente: disponível ${availableBalance.toFixed(8)} ${currency}, necessário ${requiredBalance.toFixed(8)} ${currency}`,
        availableBalance,
        requiredBalance
      };
    }

    // 3. Verificar limites de risco
    const riskCheck = await this.riskManager.checkOrderRisk({
      userId,
      botId,
      symbol,
      side,
      size,
      price
    });

    if (!riskCheck.approved) {
      return {
        approved: false,
        rejectionReason: `Risk Manager: ${riskCheck.reason}`,
        availableBalance,
        requiredBalance
      };
    }

    // 4. Verificar posição existente (evitar over-exposure)
    const currentPosition = await this.positionManager.getPosition(botId, symbol);
    if (currentPosition && side === currentPosition.side) {
      const totalExposure = currentPosition.size.add(size);
      const maxSinglePosition = await this.riskManager.getMaxPositionSize(userId);
      if (totalExposure.gt(maxSinglePosition)) {
        return {
          approved: false,
          rejectionReason: `Exposição máxima excedida: ${totalExposure.toFixed(8)} > ${maxSinglePosition.toFixed(8)}`,
          availableBalance,
          requiredBalance
        };
      }
    }

    return { approved: true, availableBalance, requiredBalance };
  }
}
```

### Passo 4: Envio com Retry Exponencial

```typescript
// src/order/order-sender.ts

import { Decimal } from 'decimal.js';
import { KuCoinClient } from '../exchanges/kucoin/client';
import { logger } from '../core/logger';

interface RetryConfig {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  jitterFactor: number;
}

const DEFAULT_RETRY: RetryConfig = {
  maxAttempts: 3,
  baseDelayMs: 500,
  maxDelayMs: 8000,
  jitterFactor: 0.2
};

export interface OrderSendResult {
  success: boolean;
  orderId?: string;
  error?: string;
  attempts: number;
  isKnownError: boolean; // Se é um erro que sabemos ser definitivo (sem retry)
}

// Erros que NÃO devem ser retentados — são definitivos
const TERMINAL_ERROR_CODES = new Set([
  '400100', // Order size too small
  '400200', // Insufficient balance
  '400300', // Order price precision error
  '900014', // Invalid symbol
]);

export class OrderSender {
  constructor(
    private kucoin: KuCoinClient,
    private config: RetryConfig = DEFAULT_RETRY
  ) {}

  async send(params: {
    clientOid: string;
    symbol: string;
    side: 'buy' | 'sell';
    type: 'limit' | 'market';
    size: string;
    price?: string;
    timeInForce?: 'GTC' | 'GTT' | 'IOC' | 'FOK';
  }): Promise<OrderSendResult> {
    let lastError: Error | null = null;
    let attempts = 0;

    for (let attempt = 1; attempt <= this.config.maxAttempts; attempt++) {
      attempts = attempt;

      try {
        logger.info({
          event: 'order_send_attempt',
          clientOid: params.clientOid,
          attempt,
          symbol: params.symbol,
          side: params.side,
          size: params.size
        });

        const response = await this.kucoin.placeOrder({
          clientOid: params.clientOid,
          symbol: params.symbol,
          side: params.side,
          type: params.type,
          size: params.size,
          price: params.price,
          timeInForce: params.timeInForce ?? 'GTC'
        });

        logger.info({
          event: 'order_send_success',
          clientOid: params.clientOid,
          orderId: response.orderId,
          attempt
        });

        return {
          success: true,
          orderId: response.orderId,
          attempts,
          isKnownError: false
        };

      } catch (error: any) {
        lastError = error;
        const errorCode = error?.response?.data?.code?.toString();

        logger.warn({
          event: 'order_send_failed',
          clientOid: params.clientOid,
          attempt,
          errorCode,
          errorMessage: error.message
        });

        // Erro terminal: não faz retry
        if (errorCode && TERMINAL_ERROR_CODES.has(errorCode)) {
          logger.error({
            event: 'order_terminal_error',
            clientOid: params.clientOid,
            errorCode,
            reason: 'Erro definitivo, sem retry'
          });
          return {
            success: false,
            error: `Terminal error ${errorCode}: ${error.message}`,
            attempts,
            isKnownError: true
          };
        }

        // Se não é a última tentativa, aguarda antes de retentar
        if (attempt < this.config.maxAttempts) {
          const delay = this.calculateDelay(attempt);
          logger.info({
            event: 'order_retry_wait',
            clientOid: params.clientOid,
            delayMs: delay,
            nextAttempt: attempt + 1
          });
          await this.sleep(delay);
        }
      }
    }

    return {
      success: false,
      error: lastError?.message ?? 'Erro desconhecido após múltiplas tentativas',
      attempts,
      isKnownError: false
    };
  }

  private calculateDelay(attempt: number): number {
    // Exponential backoff com jitter
    const exponential = Math.min(
      this.config.baseDelayMs * Math.pow(2, attempt - 1),
      this.config.maxDelayMs
    );
    const jitter = exponential * this.config.jitterFactor * (Math.random() * 2 - 1);
    return Math.max(0, Math.round(exponential + jitter));
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### Passo 5: Banco de Dados — Modelo PendingOrder

```typescript
// src/order/models/pending-order.model.ts

export enum OrderStatus {
  PENDING_QUEUE   = 'PENDING_QUEUE',    // Na fila, ainda não processado
  PREFLIGHT_OK    = 'PREFLIGHT_OK',     // Pre-flight aprovado
  PREFLIGHT_FAIL  = 'PREFLIGHT_FAIL',   // Pre-flight rejeitado
  IDEMPOTENT      = 'IDEMPOTENT',       // Já processado anteriormente
  SENDING         = 'SENDING',          // Sendo enviado à exchange
  SENT            = 'SENT',             // Aceito pela exchange (201)
  OPEN            = 'OPEN',             // Ordem aberta na exchange
  PARTIAL_FILL    = 'PARTIAL_FILL',     // Execução parcial
  FILLED          = 'FILLED',           // Execução completa
  CANCELED        = 'CANCELED',         // Cancelada
  REJECTED        = 'REJECTED',         // Rejeitada pela exchange
  FAILED          = 'FAILED',           // Falha técnica no envio
  RECONCILED      = 'RECONCILED',       // Confirmada via reconciliação
}

export interface PendingOrder {
  // Identificação
  id: string;                    // MongoDB ObjectId
  clientOid: string;             // Enviado à KuCoin (idempotency key)
  orderId?: string;              // ID real retornado pela KuCoin
  signalId: string;              // Signal que originou esta ordem
  botId: string;
  userId: string;
  strategyId: string;

  // Ordem
  symbol: string;                // Ex: BTC-USDT
  side: 'buy' | 'sell';
  type: 'limit' | 'market';
  size: string;                  // String para preservar precisão decimal
  price?: string;                // Nulo se market
  timeInForce: string;

  // Status e controle
  status: OrderStatus;
  attempts: number;
  lastAttemptAt?: Date;
  lastError?: string;

  // Execução
  filledSize?: string;
  filledFunds?: string;
  avgFillPrice?: string;
  fee?: string;
  feeCurrency?: string;

  // Timestamps
  createdAt: Date;
  updatedAt: Date;
  sentAt?: Date;
  filledAt?: Date;
  canceledAt?: Date;

  // Audit
  preflightResult?: object;
  exchangeResponse?: object;
  reconciled: boolean;
  reconciledAt?: Date;
}
```

### Passo 6: Confirmação via WebSocket — Execution Processor

```typescript
// src/order/execution-processor.ts

import { PositionManager } from '../position/position-manager';
import { ImmutableJournal } from '../audit/immutable-journal';
import { OrderRepository } from './order-repository';
import { OrderStatus } from './models/pending-order.model';
import { logger } from '../core/logger';
import { Decimal } from 'decimal.js';

interface KuCoinExecutionReport {
  type: 'open' | 'match' | 'filled' | 'canceled';
  orderId: string;
  clientOid: string;
  symbol: string;
  side: 'buy' | 'sell';
  size: string;
  filledSize: string;
  remainSize: string;
  price: string;
  ts: number; // nanoseconds timestamp
}

export class ExecutionProcessor {
  constructor(
    private orderRepo: OrderRepository,
    private positionManager: PositionManager,
    private journal: ImmutableJournal
  ) {}

  async process(report: KuCoinExecutionReport): Promise<void> {
    logger.info({
      event: 'execution_report_received',
      type: report.type,
      orderId: report.orderId,
      clientOid: report.clientOid,
      filledSize: report.filledSize
    });

    // Buscar ordem no banco pelo clientOid
    const order = await this.orderRepo.findByClientOid(report.clientOid);
    if (!order) {
      logger.warn({
        event: 'execution_report_orphan',
        clientOid: report.clientOid,
        orderId: report.orderId,
        action: 'Será tratado na próxima reconciliação'
      });
      return;
    }

    switch (report.type) {
      case 'open':
        await this.orderRepo.updateStatus(order.id, OrderStatus.OPEN, {
          orderId: report.orderId
        });
        break;

      case 'match':
        // Execução parcial
        await this.orderRepo.updateStatus(order.id, OrderStatus.PARTIAL_FILL, {
          filledSize: report.filledSize
        });
        // Atualiza posição incrementalmente
        await this.positionManager.applyFill({
          botId: order.botId,
          userId: order.userId,
          symbol: order.symbol,
          side: order.side,
          filledSize: new Decimal(report.filledSize),
          price: new Decimal(report.price),
          timestamp: new Date(report.ts / 1_000_000) // ns → ms
        });
        break;

      case 'filled':
        // Execução completa
        await this.orderRepo.updateStatus(order.id, OrderStatus.FILLED, {
          filledSize: report.filledSize,
          filledAt: new Date()
        });

        // Atualiza posição final
        await this.positionManager.applyFill({
          botId: order.botId,
          userId: order.userId,
          symbol: order.symbol,
          side: order.side,
          filledSize: new Decimal(report.filledSize),
          price: new Decimal(report.price),
          timestamp: new Date(report.ts / 1_000_000)
        });

        // Registra no ImmutableJournal
        await this.journal.record({
          type: 'ORDER_FILLED',
          botId: order.botId,
          userId: order.userId,
          data: {
            clientOid: order.clientOid,
            orderId: report.orderId,
            symbol: order.symbol,
            side: order.side,
            filledSize: report.filledSize,
            price: report.price,
            ts: report.ts
          }
        });
        break;

      case 'canceled':
        await this.orderRepo.updateStatus(order.id, OrderStatus.CANCELED, {
          canceledAt: new Date()
        });
        // Liberar reserva de saldo se houver
        break;
    }
  }
}
```

### Passo 7: Serviço de Reconciliação

```typescript
// src/order/reconciliation.service.ts

import cron from 'node-cron';
import { KuCoinClient } from '../exchanges/kucoin/client';
import { OrderRepository } from './order-repository';
import { PositionManager } from '../position/position-manager';
import { ImmutableJournal } from '../audit/immutable-journal';
import { OrderStatus } from './models/pending-order.model';
import { logger } from '../core/logger';
import { Decimal } from 'decimal.js';
import { MetricsCollector } from '../monitoring/metrics';

export class ReconciliationService {
  private isRunning = false;

  constructor(
    private kucoin: KuCoinClient,
    private orderRepo: OrderRepository,
    private positionManager: PositionManager,
    private journal: ImmutableJournal,
    private metrics: MetricsCollector
  ) {}

  start(): void {
    // Reconciliação completa a cada 60 segundos
    cron.schedule('*/60 * * * * *', () => this.runReconciliation());
    logger.info({ event: 'reconciliation_service_started', interval: '60s' });
  }

  async runReconciliation(): Promise<void> {
    if (this.isRunning) {
      logger.warn({ event: 'reconciliation_skipped', reason: 'Execução anterior ainda em andamento' });
      return;
    }

    this.isRunning = true;
    const startTime = Date.now();

    try {
      logger.info({ event: 'reconciliation_started' });

      // 1. Buscar ordens no DB com status intermediário (podem estar perdidas)
      const pendingSentOrders = await this.orderRepo.findByStatuses([
        OrderStatus.SENDING,
        OrderStatus.SENT,
        OrderStatus.OPEN,
        OrderStatus.PARTIAL_FILL
      ]);

      let divergences = 0;
      let corrected = 0;

      for (const order of pendingSentOrders) {
        if (!order.orderId) continue;

        try {
          // Buscar status real na KuCoin
          const realOrder = await this.kucoin.getOrder(order.orderId);

          if (realOrder.isActive === false) {
            // Ordem não está mais ativa na exchange
            if (realOrder.dealSize && new Decimal(realOrder.dealSize).gt(0)) {
              // Foi executada
              if (order.status !== OrderStatus.FILLED) {
                divergences++;
                logger.warn({
                  event: 'reconciliation_divergence_filled',
                  orderId: order.orderId,
                  dbStatus: order.status,
                  realDealSize: realOrder.dealSize
                });

                await this.orderRepo.updateStatus(order.id, OrderStatus.RECONCILED, {
                  filledSize: realOrder.dealSize,
                  reconciled: true,
                  reconciledAt: new Date()
                });
                await this.positionManager.forceSync(order.botId, order.symbol);
                corrected++;
              }
            } else {
              // Foi cancelada sem execução
              if (order.status !== OrderStatus.CANCELED) {
                divergences++;
                await this.orderRepo.updateStatus(order.id, OrderStatus.CANCELED, {
                  reconciled: true,
                  reconciledAt: new Date()
                });
                corrected++;
              }
            }
          }
        } catch (err: any) {
          logger.error({
            event: 'reconciliation_order_fetch_error',
            orderId: order.orderId,
            error: err.message
          });
        }
      }

      const duration = Date.now() - startTime;
      this.metrics.recordReconciliation({ divergences, corrected, durationMs: duration });

      logger.info({
        event: 'reconciliation_completed',
        ordersChecked: pendingSentOrders.length,
        divergences,
        corrected,
        durationMs: duration
      });

    } catch (err: any) {
      logger.error({ event: 'reconciliation_fatal_error', error: err.message });
    } finally {
      this.isRunning = false;
    }
  }
}
```

---

## 6. Edge Cases

| Caso | Tratamento |
|---|---|
| Crash após envio, antes de persistir orderId | Reconciliação busca por clientOid na KuCoin via GET /orders?clientOid=xxx |
| Exchange retorna 200 mas sem orderId | Retry com mesmo clientOid — KuCoin retorna idempotente |
| WebSocket desconecta durante execução | Execução detectada na próxima reconciliação (60s max) |
| Execução parcial seguida de cancelamento | match + canceled processados em sequência, posição calculada sobre filledSize |
| Ordem rejeitada por preço fora do limite | TERMINAL_ERROR → marca REJECTED, não faz retry, notifica bot |
| Dois bots tentam mesma ordem simultaneamente | Lock por (userId, symbol) no OrderManager impede envio duplicado |
| Fila Redis corrompida | Consumer group permite XAUTOCLAIM para reprocessar mensagens pendentes |

---

## 7. Testes Obrigatórios

### 7.1 Teste de Idempotência

```typescript
describe('Order Idempotency', () => {
  it('deve retornar resultado anterior se clientOid já existe', async () => {
    const store = new IdempotencyStore(redis);
    const clientOid = 'test-oid-001';

    // Primeira chamada — registra
    const first = await store.checkAndSet(clientOid, { symbol: 'BTC-USDT' });
    expect(first.isDuplicate).toBe(false);

    // Segunda chamada — detecta duplicata
    const second = await store.checkAndSet(clientOid, { symbol: 'BTC-USDT' });
    expect(second.isDuplicate).toBe(true);
  });

  it('deve usar clientOid determinístico para mesmo signalId + botId', () => {
    const k1 = generateClientOid('signal-abc', 'bot-001');
    const k2 = generateClientOid('signal-abc', 'bot-001');
    expect(k1.clientOid).toBe(k2.clientOid);
  });
});
```

### 7.2 Teste de Retry Exponencial

```typescript
describe('OrderSender Retry', () => {
  it('não deve retentar erros terminais (400200 insufficient balance)', async () => {
    const mockKucoin = { placeOrder: jest.fn().mockRejectedValue({
      response: { data: { code: '400200' } }
    })};
    const sender = new OrderSender(mockKucoin as any);
    const result = await sender.send({ clientOid: 'test', symbol: 'BTC-USDT', side: 'buy', type: 'market', size: '0.001' });
    
    expect(result.success).toBe(false);
    expect(result.isKnownError).toBe(true);
    expect(mockKucoin.placeOrder).toHaveBeenCalledTimes(1); // Sem retry
  });

  it('deve retentar até maxAttempts em erros de rede', async () => {
    const mockKucoin = { placeOrder: jest.fn().mockRejectedValue(new Error('ETIMEDOUT')) };
    const sender = new OrderSender(mockKucoin as any, { maxAttempts: 3, baseDelayMs: 10, maxDelayMs: 100, jitterFactor: 0 });
    const result = await sender.send({ clientOid: 'test', symbol: 'BTC-USDT', side: 'buy', type: 'market', size: '0.001' });
    
    expect(result.attempts).toBe(3);
    expect(result.success).toBe(false);
  });
});
```

### 7.3 Teste de Reconciliação

```typescript
describe('Reconciliation', () => {
  it('deve corrigir ordem SENT que foi FILLED na exchange', async () => {
    const order = await orderRepo.create({ status: OrderStatus.SENT, orderId: 'real-kucoin-id', ... });
    
    // Mock KuCoin retorna como filled
    kucoinMock.getOrder.mockResolvedValue({ isActive: false, dealSize: '0.001' });
    
    await reconciliationService.runReconciliation();
    
    const updated = await orderRepo.findById(order.id);
    expect(updated.status).toBe(OrderStatus.RECONCILED);
    expect(updated.filledSize).toBe('0.001');
  });
});
```

---

## 8. Checklist de Implementação

- [ ] `IdempotencyStore` implementado e conectado ao Redis
- [ ] `generateClientOid` é determinístico (mesmo signal_id → mesmo clientOid)
- [ ] `PendingOrder` persiste ANTES do envio HTTP
- [ ] `orderId` retornado pela KuCoin salvo ANTES do XACK na fila
- [ ] `PreflightChecker` verifica saldo real via API KuCoin
- [ ] `TERMINAL_ERROR_CODES` configurado com todos os códigos de erro definitivos
- [ ] `ExecutionProcessor` atualiza `PositionManager` e `ImmutableJournal` no fill
- [ ] `ReconciliationService` rodando em cron de 60s
- [ ] Teste com conta sandbox da KuCoin realizado com sucesso
- [ ] Teste de crash forçado (kill -9) pós-envio verificado
- [ ] Monitoring: métricas de `reconciliation_divergences` exportadas
- [ ] Alerta configurado: divergências > 0 por mais de 5 min

---

## 9. Critérios de Validação Final

| Critério | Métrica de Aprovação |
|---|---|
| Zero ordens duplicadas | 0 duplicatas em 1.000 sinais em teste de carga |
| Recovery após crash | Reconciliação corrige 100% das divergências em < 120s |
| Latência de envio | P99 < 2.000ms (pré-flight + envio + persist) |
| Idempotência | 10.000 reenvios do mesmo clientOid = 0 ordens duplicadas |
| Saldo pré-validado | 100% das ordens com saldo insuficiente bloqueadas antes do envio |
| Auditoria | 100% das ordens FILLED presentes no ImmutableJournal |
| Reconciliação | < 1 divergência não corrigida em 24h de operação |

---

*Este documento deve ser revisado por pelo menos 2 engenheiros sênior antes da implementação.*
*Testes com conta sandbox são OBRIGATÓRIOS antes de habilitar em produção.*
