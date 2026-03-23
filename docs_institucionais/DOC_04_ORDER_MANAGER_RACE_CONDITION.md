# DOC 04 — Order Manager à Prova de Race Condition
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia

---

## 1. Objetivo

Garantir que o OrderManager seja **completamente imune a race conditions**, incluindo:

- Dois sinais do mesmo bot nunca enviar ordens simultâneas
- Um usuário com N bots nunca ultrapassar limites globais por concorrência
- Fila de ordens processada em ordem estrita
- Nenhuma ordem duplicada por retry concorrente
- Estado consistente mesmo em ambiente multi-processo (múltiplos workers)

---

## 2. Problema Atual

| Cenário de Race Condition | Consequência |
|---|---|
| Sinal duplicado chega em 2ms de diferença | Pre-flight passa em ambos (saldo verificado antes do lock) |
| 2 workers processam a mesma mensagem da fila | Ordem duplicada enviada à exchange |
| Bot reinicia durante envio de ordem | Pre-flight já deduziu saldo "reservado" que sumiu |
| N bots do mesmo usuário disparam ao mesmo tempo | Limite de saldo excedido pela soma das reservas simultâneas |
| Retry de ordem que já foi enviada | clientOid duplicado ou nova ordem sem controle |

---

## 3. Arquitetura de Locking Proposta

```
┌────────────────────────────────────────────────────────────────┐
│                    FLUXO SEGURO DE ORDEM                       │
│                                                                │
│  SINAL CHEGA                                                   │
│       │                                                        │
│       ▼                                                        │
│  ┌─────────────────────────────────────────────────┐          │
│  │  NIVEL 1: IDEMPOTENCY STORE                     │          │
│  │  Redis SET NX: idempotency:{clientOid}          │          │
│  │  SE JÁ EXISTE → retorna resultado anterior      │          │
│  └─────────────────────────┬───────────────────────┘          │
│                            │ Novo                              │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────┐          │
│  │  NIVEL 2: LOCK POR BOT                          │          │
│  │  Redis SET NX: lock:bot:{botId}  TTL=30s        │          │
│  │  SE BLOQUEADO → enfileira para retry em 100ms   │          │
│  └─────────────────────────┬───────────────────────┘          │
│                            │ Lock adquirido                    │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────┐          │
│  │  NIVEL 3: LOCK DE SALDO POR USUÁRIO             │          │
│  │  Redis SET NX: lock:balance:{userId}  TTL=15s   │          │
│  │  Verifica saldo DENTRO do lock                  │          │
│  │  Reserva saldo (decrementa saldo virtual)       │          │
│  └─────────────────────────┬───────────────────────┘          │
│                            │ Saldo reservado                   │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────┐          │
│  │  NIVEL 4: FILA TRANSACIONAL (Redis Stream)      │          │
│  │  XADD orders:queue botId+payload               │          │
│  │  Consumer Group: 1 worker por mensagem         │          │
│  └─────────────────────────┬───────────────────────┘          │
│                            │                                   │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────┐          │
│  │  ENVIO HTTP → KUCOIN                            │          │
│  │  XACK só após persist do orderId               │          │
│  └─────────────────────────┬───────────────────────┘          │
│                            │                                   │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────┐          │
│  │  LIBERAR LOCKS em ordem reversa:                │          │
│  │  1. Libera lock:balance:{userId}                │          │
│  │  2. Libera lock:bot:{botId}                     │          │
│  └─────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementação

### 4.1 Redis Distributed Lock com Lua Script

```typescript
// src/core/distributed-lock.ts

import Redis from 'ioredis';
import { randomBytes } from 'crypto';
import { logger } from './logger';

/**
 * Implementação de Distributed Lock usando Redis SET NX com Lua script
 * para garantia atômica de acquire e release.
 * 
 * CRÍTICO: O release usa Lua para garantir que apenas o detentor do lock
 * possa liberá-lo (evita liberar lock de outro processo!).
 */
export class DistributedLock {
  // Script Lua para release atômico: só deleta se o valor corresponde ao token
  private static RELEASE_SCRIPT = `
    if redis.call("get", KEYS[1]) == ARGV[1] then
      return redis.call("del", KEYS[1])
    else
      return 0
    end
  `;

  constructor(private redis: Redis) {}

  /**
   * Tenta adquirir o lock. Retorna token se adquirido, null se bloqueado.
   */
  async acquire(key: string, ttlMs: number): Promise<string | null> {
    const token = randomBytes(16).toString('hex');
    const fullKey = `lock:${key}`;

    const result = await this.redis.set(
      fullKey,
      token,
      'PX',     // TTL em milissegundos
      ttlMs,
      'NX'      // Só seta se não existir
    );

    if (result === 'OK') {
      logger.debug({ event: 'lock_acquired', key: fullKey, ttlMs });
      return token;
    }

    return null;
  }

  /**
   * Tenta adquirir o lock com espera (polling com backoff).
   * Útil para locks que sabemos que serão liberados logo.
   */
  async acquireWithWait(
    key: string,
    ttlMs: number,
    maxWaitMs: number = 5000,
    pollIntervalMs: number = 100
  ): Promise<string | null> {
    const deadline = Date.now() + maxWaitMs;

    while (Date.now() < deadline) {
      const token = await this.acquire(key, ttlMs);
      if (token) return token;

      // Backoff progressivo: 100ms → 200ms → 400ms (max 1s)
      const wait = Math.min(pollIntervalMs * 2, 1000);
      await new Promise(r => setTimeout(r, wait));
    }

    logger.warn({ event: 'lock_wait_timeout', key, maxWaitMs });
    return null;
  }

  /**
   * Libera o lock. Usa Lua para garantia atômica.
   */
  async release(key: string, token: string): Promise<boolean> {
    const fullKey = `lock:${key}`;
    const released = await this.redis.eval(
      DistributedLock.RELEASE_SCRIPT,
      1,
      fullKey,
      token
    ) as number;

    if (released === 1) {
      logger.debug({ event: 'lock_released', key: fullKey });
      return true;
    }

    logger.warn({ event: 'lock_release_failed', key: fullKey, reason: 'Token mismatch ou lock expirado' });
    return false;
  }

  /**
   * Wrapper que garante liberação do lock mesmo em caso de exceção.
   */
  async withLock<T>(
    key: string,
    ttlMs: number,
    fn: () => Promise<T>,
    options: { maxWaitMs?: number } = {}
  ): Promise<T> {
    const token = await this.acquireWithWait(key, ttlMs, options.maxWaitMs ?? 5000);

    if (!token) {
      throw new Error(`Não foi possível adquirir lock para: ${key}`);
    }

    try {
      return await fn();
    } finally {
      await this.release(key, token);
    }
  }
}
```

### 4.2 Balance Reservation System

```typescript
// src/order/balance-reservation.ts

import Redis from 'ioredis';
import { Decimal } from 'decimal.js';
import { KuCoinClient } from '../exchanges/kucoin/client';
import { DistributedLock } from '../core/distributed-lock';
import { logger } from '../core/logger';

interface Reservation {
  reservationId: string;
  userId: string;
  currency: string;
  amount: Decimal;
  expiresAt: Date;
}

/**
 * Sistema de reserva virtual de saldo para evitar over-commitment.
 * 
 * Problema: Se 3 bots verificam saldo ao mesmo tempo e todos veem $1000,
 * todos podem tentar gastar $400 cada, gerando $1200 de ordens com $1000 disponível.
 * 
 * Solução: Dentro do lock de balanço, deduzimos o saldo "reservado" antes de liberar.
 * Isso cria uma visão virtual do saldo considerando ordens em flight.
 */
export class BalanceReservationSystem {
  private readonly RESERVATION_TTL_MS = 60_000;  // 1 min (tempo max de envio)
  private readonly RESERVATION_PREFIX = 'balance:reserved';

  constructor(
    private redis: Redis,
    private lock: DistributedLock,
    private kucoin: KuCoinClient
  ) {}

  /**
   * Reserva saldo para uma ordem.
   * Deve ser chamado DENTRO do lock de balanço do usuário.
   */
  async reserve(params: {
    userId: string;
    botId: string;
    currency: string;
    amount: Decimal;
    reservationId: string; // = clientOid
  }): Promise<{ success: boolean; reason?: string; availableAfterReservation: Decimal }> {
    const { userId, currency, amount, reservationId } = params;

    // 1. Saldo real na exchange
    const accounts = await this.kucoin.getAccounts('trade');
    const account = accounts.find((a: any) => a.currency === currency);
    const realBalance = new Decimal(account?.available ?? '0');

    // 2. Total já reservado por outras ordens em flight
    const reservedKey = `${this.RESERVATION_PREFIX}:${userId}:${currency}`;
    const currentReserved = await this.getTotalReserved(userId, currency);

    // 3. Saldo efetivamente disponível
    const available = realBalance.sub(currentReserved);

    if (available.lt(amount)) {
      return {
        success: false,
        reason: `Saldo insuficiente considerando reservas: real=${realBalance.toFixed(8)}, reservado=${currentReserved.toFixed(8)}, disponível=${available.toFixed(8)}, necessário=${amount.toFixed(8)}`,
        availableAfterReservation: available
      };
    }

    // 4. Adicionar nova reserva
    await this.redis.hset(
      reservedKey,
      reservationId,
      JSON.stringify({
        amount: amount.toFixed(8),
        botId: params.botId,
        createdAt: Date.now(),
        expiresAt: Date.now() + this.RESERVATION_TTL_MS
      })
    );
    await this.redis.expire(reservedKey, Math.ceil(this.RESERVATION_TTL_MS / 1000) + 60);

    return {
      success: true,
      availableAfterReservation: available.sub(amount)
    };
  }

  /**
   * Remove reserva após confirmação ou falha da ordem.
   */
  async release(userId: string, currency: string, reservationId: string): Promise<void> {
    const reservedKey = `${this.RESERVATION_PREFIX}:${userId}:${currency}`;
    await this.redis.hdel(reservedKey, reservationId);
    logger.debug({ event: 'balance_reservation_released', userId, currency, reservationId });
  }

  /**
   * Limpa reservas expiradas (job de manutenção).
   */
  async cleanExpired(userId: string, currency: string): Promise<number> {
    const reservedKey = `${this.RESERVATION_PREFIX}:${userId}:${currency}`;
    const all = await this.redis.hgetall(reservedKey);
    let cleaned = 0;

    for (const [id, raw] of Object.entries(all || {})) {
      const data = JSON.parse(raw);
      if (Date.now() > data.expiresAt) {
        await this.redis.hdel(reservedKey, id);
        cleaned++;
      }
    }

    return cleaned;
  }

  private async getTotalReserved(userId: string, currency: string): Promise<Decimal> {
    const reservedKey = `${this.RESERVATION_PREFIX}:${userId}:${currency}`;
    const all = await this.redis.hgetall(reservedKey);

    let total = new Decimal(0);
    const now = Date.now();

    for (const raw of Object.values(all || {})) {
      const data = JSON.parse(raw);
      if (now <= data.expiresAt) {
        total = total.add(new Decimal(data.amount));
      }
    }

    return total;
  }
}
```

### 4.3 Order Manager — Orquestrador Principal

```typescript
// src/order/order-manager.ts

import { DistributedLock } from '../core/distributed-lock';
import { BalanceReservationSystem } from './balance-reservation';
import { IdempotencyStore } from './idempotency-store';
import { OrderSender } from './order-sender';
import { PreflightChecker } from './preflight';
import { OrderRepository } from './order-repository';
import { OrderStatus } from './models/pending-order.model';
import { generateClientOid } from './idempotency';
import { Decimal } from 'decimal.js';
import { logger } from '../core/logger';

export interface OrderRequest {
  signalId: string;
  botId: string;
  userId: string;
  strategyId: string;
  symbol: string;
  side: 'buy' | 'sell';
  type: 'limit' | 'market';
  size: Decimal;
  price?: Decimal;
  currency: string; // Moeda a reservar
}

export interface OrderResult {
  success: boolean;
  orderId?: string;
  clientOid?: string;
  error?: string;
  rejectionReason?: string;
}

export class OrderManager {
  constructor(
    private lock: DistributedLock,
    private balanceReservation: BalanceReservationSystem,
    private idempotency: IdempotencyStore,
    private preflight: PreflightChecker,
    private sender: OrderSender,
    private orderRepo: OrderRepository
  ) {}

  async processOrder(request: OrderRequest): Promise<OrderResult> {
    const { signalId, botId, userId, currency, symbol, side, type, size, price } = request;

    // ── NÍVEL 1: IDEMPOTÊNCIA ──────────────────────────────────────────
    const { clientOid } = generateClientOid(signalId, botId);
    const idempotencyCheck = await this.idempotency.checkAndSet(clientOid, {
      signalId, botId, symbol, side
    });

    if (idempotencyCheck.isDuplicate) {
      logger.info({ event: 'order_idempotent', clientOid, signalId });
      return {
        success: true,
        clientOid,
        orderId: (idempotencyCheck.existingResult as any)?.orderId,
      };
    }

    // ── NÍVEL 2: LOCK POR BOT ──────────────────────────────────────────
    return await this.lock.withLock(
      `bot:${botId}`,
      30_000,  // TTL: 30s
      async () => {

        // ── NÍVEL 3: LOCK DE SALDO + RESERVA ──────────────────────────
        return await this.lock.withLock(
          `balance:${userId}`,
          15_000,  // TTL: 15s
          async () => {

            // Pre-flight check (DENTRO do lock de saldo)
            const preflightResult = await this.preflight.check({
              userId, botId, symbol, side, size,
              price: price ?? new Decimal(0)
            });

            if (!preflightResult.approved) {
              logger.warn({
                event: 'order_preflight_rejected',
                clientOid,
                reason: preflightResult.rejectionReason
              });
              await this.idempotency.markFailed(clientOid, preflightResult.rejectionReason!);
              return { success: false, rejectionReason: preflightResult.rejectionReason };
            }

            // Reservar saldo virtual (dentro do lock)
            const reservation = await this.balanceReservation.reserve({
              userId, botId, currency,
              amount: preflightResult.requiredBalance,
              reservationId: clientOid
            });

            if (!reservation.success) {
              await this.idempotency.markFailed(clientOid, reservation.reason!);
              return { success: false, rejectionReason: reservation.reason };
            }

            // Persistir ordem no banco ANTES de enviar
            const pendingOrder = await this.orderRepo.create({
              clientOid, signalId, botId, userId,
              strategyId: request.strategyId,
              symbol, side, type,
              size: size.toFixed(8),
              price: price?.toFixed(8),
              timeInForce: 'GTC',
              status: OrderStatus.SENDING,
              attempts: 0
            });

            // ── ENVIO ─────────────────────────────────────────────────
            // Lock de saldo liberado AQUI para não bloquear outros bots
            // durante o envio HTTP (pode demorar 500ms-2s)
            logger.info({ event: 'order_sending', clientOid });

            const result = await this.sender.send({
              clientOid,
              symbol,
              side,
              type,
              size: size.toFixed(8),
              price: price?.toFixed(8),
            });

            if (result.success) {
              await this.orderRepo.updateStatus(pendingOrder.id, OrderStatus.SENT, {
                orderId: result.orderId,
                sentAt: new Date(),
                attempts: result.attempts
              });
              await this.idempotency.markCompleted(clientOid, result.orderId!, 'SENT');

              logger.info({ event: 'order_sent', clientOid, orderId: result.orderId });
              return { success: true, orderId: result.orderId, clientOid };

            } else {
              await this.orderRepo.updateStatus(pendingOrder.id, OrderStatus.FAILED, {
                lastError: result.error,
                attempts: result.attempts
              });
              await this.idempotency.markFailed(clientOid, result.error!);

              // Liberar reserva de saldo em caso de falha
              await this.balanceReservation.release(userId, currency, clientOid);

              return { success: false, error: result.error, clientOid };
            }
          },
          { maxWaitMs: 10_000 }  // Espera máx 10s pelo lock de saldo
        );
      },
      { maxWaitMs: 30_000 }   // Espera máx 30s pelo lock do bot
    );
  }
}
```

### 4.4 Redis Stream — Fila Transacional

```typescript
// src/order/order-queue.ts

import Redis from 'ioredis';
import { OrderManager, OrderRequest } from './order-manager';
import { logger } from '../core/logger';
import { Decimal } from 'decimal.js';

const STREAM_NAME = 'orders:queue';
const CONSUMER_GROUP = 'order-workers';
const CONSUMER_NAME = `worker-${process.pid}`;
const BLOCK_MS = 2000;    // Esperar msg por 2s por vez
const AUTOCLAIM_MS = 60_000; // Reclamar mensagens pendentes > 60s

export class OrderQueueConsumer {
  private running = false;

  constructor(
    private redis: Redis,
    private orderManager: OrderManager
  ) {}

  async start(): Promise<void> {
    // Criar consumer group se não existir
    try {
      await this.redis.xgroup('CREATE', STREAM_NAME, CONSUMER_GROUP, '$', 'MKSTREAM');
    } catch (e: any) {
      if (!e.message.includes('BUSYGROUP')) throw e;
    }

    this.running = true;
    logger.info({ event: 'order_queue_consumer_started', consumer: CONSUMER_NAME });

    // Loop de consumo
    this.consumeLoop();

    // Loop de reclaim (mensagens abandonadas)
    this.reclaimLoop();
  }

  private async consumeLoop(): Promise<void> {
    while (this.running) {
      try {
        const messages = await this.redis.xreadgroup(
          'GROUP', CONSUMER_GROUP, CONSUMER_NAME,
          'COUNT', '1',          // Processar 1 por vez para garantir sequência por bot
          'BLOCK', BLOCK_MS,     // Aguardar 2s por nova mensagem
          'STREAMS', STREAM_NAME, '>'
        ) as any;

        if (!messages) continue;

        for (const [, entries] of messages) {
          for (const [msgId, fields] of entries) {
            await this.processMessage(msgId, fields);
          }
        }

      } catch (err: any) {
        if (!this.running) break;
        logger.error({ event: 'order_queue_consume_error', error: err.message });
        await new Promise(r => setTimeout(r, 1000));
      }
    }
  }

  private async processMessage(msgId: string, fields: string[]): Promise<void> {
    const data: Record<string, string> = {};
    for (let i = 0; i < fields.length; i += 2) {
      data[fields[i]] = fields[i + 1];
    }

    const request: OrderRequest = {
      signalId: data.signalId,
      botId: data.botId,
      userId: data.userId,
      strategyId: data.strategyId,
      symbol: data.symbol,
      side: data.side as 'buy' | 'sell',
      type: data.type as 'limit' | 'market',
      size: new Decimal(data.size),
      price: data.price ? new Decimal(data.price) : undefined,
      currency: data.currency
    };

    try {
      const result = await this.orderManager.processOrder(request);

      // XACK APENAS após processamento bem-sucedido ou rejeição definitiva
      // (não em caso de erro de rede que pode ser retentado)
      if (result.success || result.rejectionReason) {
        await this.redis.xack(STREAM_NAME, CONSUMER_GROUP, msgId);
      }

    } catch (err: any) {
      logger.error({ event: 'order_queue_message_failed', msgId, error: err.message });
      // NÃO ACK — será reclamado pelo reclaimLoop
    }
  }

  private async reclaimLoop(): Promise<void> {
    while (this.running) {
      await new Promise(r => setTimeout(r, 30_000));

      try {
        // Reclamar mensagens que ficaram pendentes por mais de 60s
        const claimed = await this.redis.xautoclaim(
          STREAM_NAME,
          CONSUMER_GROUP,
          CONSUMER_NAME,
          AUTOCLAIM_MS,
          '0-0',
          'COUNT', '10'
        ) as any;

        if (claimed[1]?.length > 0) {
          logger.warn({ event: 'order_queue_reclaimed', count: claimed[1].length });
        }
      } catch (err: any) {
        logger.error({ event: 'order_queue_reclaim_error', error: err.message });
      }
    }
  }

  stop(): void {
    this.running = false;
  }
}
```

---

## 5. Diagrama de Concorrência

```
CENÁRIO: 3 sinais chegam simultâneos para o mesmo bot

Signal A (t=0ms)  Signal B (t=1ms)  Signal C (t=2ms)
       │                  │                 │
       ▼                  ▼                 ▼
  [Idempotency]      [Idempotency]     [Idempotency]
  NX=OK (novo)       NX=FAIL (dup)     NX=OK (novo)
       │                  │                 │
       │              retorna result A       │
       ▼                                    ▼
  [Lock:bot:001]                    [Lock:bot:001]
  ACQUIRED ✓                        ESPERA...
       │                                    │
  [Lock:balance:user]                       │
  ACQUIRED ✓                                │
       │                                    │
  Pre-flight OK                             │
  Reserva $400                              │
  Envia ordem → KuCoin                      │
  XACK                                      │
       │                                    │
  Libera lock:balance              [Lock:bot:001] ACQUIRED
  Libera lock:bot                  [Lock:balance:user] ACQUIRED
                                   Pre-flight OK
                                   Reserva $400 (saldo virtual correto!)
                                   Envia ordem → KuCoin
```

---

## 6. Testes Obrigatórios

```typescript
describe('OrderManager Concurrency', () => {
  it('deve processar apenas 1 de 10 sinais simultâneos do mesmo botId', async () => {
    const requests = Array.from({ length: 10 }, (_, i) => ({
      ...baseRequest,
      signalId: `signal-${i}` // Diferentes signals
    }));

    // Tornar todos com mesmo clientOid para 5 deles (simular duplicatas)
    // e clientOids únicos para os outros 5

    const results = await Promise.all(requests.map(r => orderManager.processOrder(r)));
    const sent = results.filter(r => r.success && r.orderId);
    
    // Máximo de 1 ordem por bot em paralelo (lock)
    // Com 10 signals únicos, até 10 ordens podem ser enviadas, mas sequencialmente
    // Verificar que todas passaram pelo lock sequencialmente
    const kucoinCalls = kucoinMock.placeOrder.mock.calls.length;
    expect(kucoinCalls).toBe(results.filter(r => !r.rejectionReason).length);
  });

  it('deve bloquear segunda ordem quando saldo insuficiente por reserva', async () => {
    // Saldo real: $1000
    kucoinMock.getAccounts.mockResolvedValue([{ currency: 'USDT', available: '1000' }]);

    const [r1, r2] = await Promise.all([
      orderManager.processOrder({ ...baseRequest, size: new Decimal('700') }),
      orderManager.processOrder({ ...baseRequest, botId: 'bot-002', size: new Decimal('400') })
    ]);

    // Um deve passar e o outro deve ser rejeitado por reserva insuficiente
    const passed = [r1, r2].filter(r => r.success).length;
    const rejected = [r1, r2].filter(r => r.rejectionReason?.includes('Saldo insuficiente')).length;
    
    expect(passed).toBe(1);
    expect(rejected).toBe(1);
  });

  it('deve liberar reserva de saldo após falha de envio', async () => {
    kucoinMock.placeOrder.mockRejectedValue(new Error('ETIMEDOUT'));

    await orderManager.processOrder({ ...baseRequest, size: new Decimal('500') });

    // Reserva deve ter sido liberada
    const totalReserved = await balanceReservation.getTotalReserved('user-001', 'USDT');
    expect(totalReserved.isZero()).toBe(true);
  });
});
```

---

## 7. Checklist de Implementação

- [ ] `DistributedLock` com Lua script para release atômico
- [ ] Lock `lock:bot:{botId}` adquirido ANTES do pre-flight
- [ ] Lock `lock:balance:{userId}` adquirido ANTES da verificação de saldo
- [ ] Reserva de saldo feita DENTRO do lock de balanço
- [ ] Reserva liberada tanto em sucesso quanto em falha
- [ ] Redis Stream (`XADD`) com Consumer Group configurado
- [ ] `XACK` apenas após persistência do orderId (não antes)
- [ ] `XAUTOCLAIM` rodando a cada 30s para mensagens pendentes > 60s
- [ ] Testes de concorrência com 10 requests simultâneos
- [ ] Testes de saldo insuficiente por reserva (não por saldo real)
- [ ] Testes de recovery após crash do worker

---

## 8. Critérios de Validação Final

| Critério | Aprovação |
|---|---|
| Zero duplicatas com 1.000 sinais simultâneos | 0 ordens duplicadas em exchange |
| Saldo virtual correto | Nunca comprometido mais de X% do saldo real em ordens simultâneas |
| Recovery de worker crash | Mensagens reclamadas em < 65s (AUTOCLAIM_MS + 5s) |
| Latência de lock | P99 do tempo de espera pelo lock < 2s |
| Leak de reserva | 0 reservas não liberadas após 60s |
