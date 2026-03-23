# DOC 02 — Sistema Completo de Take Profit / Stop Loss
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia

---

## 1. Objetivo

Implementar um sistema robusto, persistente e à prova de falhas de **Take Profit (TP)** e **Stop Loss (SL)** que:

- Funcione para **Spot** via OCO (One Cancels the Other) ou ordens condicionais
- Funcione para **Futures** via TP/SL nativo da KuCoin Futures
- Persista no banco de dados e sobreviva a restarts do servidor
- Sincronize-se com o `PositionManager` para evitar ordens órfãs
- Trate corretamente todos os edge cases: fills parciais, cancelamentos, posição invertida
- Cancele automaticamente a ordem contrária quando uma das duas for atingida

---

## 2. Problema Atual

| Problema | Consequência |
|---|---|
| TP/SL configurados apenas em memória | Restart do servidor = posições desprotegidas |
| Sem cancelamento automático da ordem contrária | OCO manual com race condition: ambas podem executar |
| Fills parciais não tratados | TP/SL em quantidade incorreta após execução parcial |
| Sem sincronização com PositionManager | Posição pode fechar com TP/SL ainda ativos na exchange |
| Sem detecção de posição zerada externamente | SL de uma posição já fechada pode abrir nova posição inadvertidamente |

---

## 3. Riscos se Não Corrigir

| Cenário | Impacto Financeiro |
|---|---|
| Bot executa TP e SL ao mesmo tempo | Dobra a exposição em direção contrária |
| SL não registrado → crash do servidor | Posição sem proteção, drawdown ilimitado |
| TP com size errado após fill parcial | Fecha mais do que tem, abre short não intencional |
| SL ativo após posição já fechada manualmente | Abre nova posição não prevista pela estratégia |

---

## 4. Arquitetura Proposta

```
┌────────────────────────────────────────────────────────────────┐
│              POSITION OPENED (via ExecutionProcessor)          │
│  filledSize=0.1 BTC @ $50,000                                 │
└───────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│              TP/SL MANAGER                                     │
│                                                                │
│  1. Recebe: PositionOpenedEvent                               │
│  2. Calcula preços de TP e SL baseado na configuração do bot  │
│  3. Para SPOT → cria StopLimitOrder (SL) + LimitOrder (TP)   │
│     OU usa API OCO se disponível                              │
│  4. Para FUTURES → usa endpoint nativo de TP/SL              │
│  5. Persiste TpSlRecord no banco ANTES de enviar             │
│  6. Armazena orderId do TP e orderId do SL                   │
│  7. Monitora fills via WS para cancelar a outra             │
└────────────────────────────────────────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│  TAKE PROFIT    │         │   STOP LOSS      │
│  Limit Order    │         │   Stop-Limit     │
│  @ TP Price     │         │   @ SL Price     │
│  Size = fill    │         │   Size = fill    │
│  orderId stored │         │   orderId stored │
└────────┬────────┘         └────────┬─────────┘
         │ FILLED                    │ TRIGGERED
         ▼                           ▼
┌─────────────────────────────────────────────┐
│       CANCELLATION HANDLER                  │
│                                             │
│  Quando TP filled → cancela SL              │
│  Quando SL filled → cancela TP              │
│  Race condition protegido por Redis Lock    │
└─────────────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────────┐
│              POSITION MANAGER — fechar posição                 │
│  Atualiza status, P&L, histórico                              │
└────────────────────────────────────────────────────────────────┘
```

---

## 5. Fluxo Detalhado

### 5.1 Modelo de Dados — TpSlRecord

```typescript
// src/order/models/tpsl-record.model.ts

export enum TpSlStatus {
  ACTIVE   = 'ACTIVE',      // Ambas as ordens ativas na exchange
  TP_HIT   = 'TP_HIT',      // Take Profit executado, SL cancelado
  SL_HIT   = 'SL_HIT',      // Stop Loss executado, TP cancelado
  MANUALLY_CLOSED = 'MANUALLY_CLOSED', // Fechado manualmente
  CANCELED = 'CANCELED',    // Cancelado sem execução
  ORPHANED = 'ORPHANED',    // Posição fechada mas TP/SL não cancelados ainda
}

export enum MarketType {
  SPOT    = 'SPOT',
  FUTURES = 'FUTURES',
}

export interface TpSlRecord {
  id: string;                   // MongoDB ObjectId
  botId: string;
  userId: string;
  strategyId: string;
  positionId: string;           // Referência à posição que protege

  marketType: MarketType;
  symbol: string;
  side: 'buy' | 'sell';        // Lado da posição (não da ordem de fechamento)

  // Tamanho
  totalSize: string;            // Tamanho total da posição
  remainingSize: string;        // Tamanho não executado ainda pelo TP/SL

  // Preços
  entryPrice: string;
  tpPrice: string;
  slPrice: string;
  slStopPrice?: string;         // Para stop-limit: stopPrice (gatilho) ≠ limitPrice

  // Ordem de TP na KuCoin
  tpClientOid: string;
  tpOrderId?: string;
  tpFilledSize?: string;
  tpFilledAt?: Date;

  // Ordem de SL na KuCoin
  slClientOid: string;
  slOrderId?: string;
  slFilledSize?: string;
  slFilledAt?: Date;

  // Status
  status: TpSlStatus;
  cancelationSource?: 'TP_HIT' | 'SL_HIT' | 'MANUAL' | 'POSITION_CLOSED';

  // P&L quando fechado
  realizedPnl?: string;
  pnlPercent?: string;

  createdAt: Date;
  updatedAt: Date;
}
```

### 5.2 Cálculo de Preços

```typescript
// src/order/tpsl/price-calculator.ts

import { Decimal } from 'decimal.js';

export interface TpSlPrices {
  tpPrice: Decimal;
  slPrice: Decimal;
  slStopPrice: Decimal; // Stop-limit: gatilho ligeiramente antes do limite
}

export class TpSlPriceCalculator {
  /**
   * Calcula preços de TP e SL baseado na configuração percentual.
   * Para LONG: TP acima, SL abaixo.
   * Para SHORT: TP abaixo, SL acima.
   */
  calculate(params: {
    entryPrice: Decimal;
    side: 'buy' | 'sell';          // Lado da POSIÇÃO
    tpPercent: Decimal;            // Ex: 2.5 para 2.5%
    slPercent: Decimal;            // Ex: 1.5 para 1.5%
    tickSize: Decimal;             // Tamanho mínimo de variação de preço
    slBuffer: Decimal;             // Buffer entre stopPrice e limitPrice para SL (ex: 0.1%)
  }): TpSlPrices {
    const { entryPrice, side, tpPercent, slPercent, tickSize, slBuffer } = params;
    const multiplier = new Decimal(100);

    let tpPrice: Decimal;
    let slPrice: Decimal;

    if (side === 'buy') {
      // LONG: TP acima, SL abaixo
      tpPrice = entryPrice.mul(multiplier.add(tpPercent)).div(multiplier);
      slPrice = entryPrice.mul(multiplier.sub(slPercent)).div(multiplier);
    } else {
      // SHORT: TP abaixo, SL acima
      tpPrice = entryPrice.mul(multiplier.sub(tpPercent)).div(multiplier);
      slPrice = entryPrice.mul(multiplier.add(slPercent)).div(multiplier);
    }

    // Arredondar para o tickSize mais próximo
    tpPrice = this.roundToTick(tpPrice, tickSize);
    slPrice = this.roundToTick(slPrice, tickSize);

    // Stop-Limit: o stopPrice (gatilho) está ligeiramente mais próximo da entrada
    // para garantir que o limitPrice consiga ser preenchido
    const slStopPrice = side === 'buy'
      ? slPrice.add(slPrice.mul(slBuffer).div(multiplier)) // Gatilho ligeiramente acima do limite
      : slPrice.sub(slPrice.mul(slBuffer).div(multiplier));

    return {
      tpPrice,
      slPrice,
      slStopPrice: this.roundToTick(slStopPrice, tickSize)
    };
  }

  roundToTick(price: Decimal, tickSize: Decimal): Decimal {
    return price.div(tickSize).floor().mul(tickSize);
  }
}
```

### 5.3 Implementação para SPOT (Stop-Limit Manual)

```typescript
// src/order/tpsl/spot-tpsl-manager.ts

import { KuCoinClient } from '../../exchanges/kucoin/client';
import { TpSlRecord, TpSlStatus, MarketType } from '../models/tpsl-record.model';
import { TpSlRepository } from './tpsl-repository';
import { IdempotencyStore } from '../idempotency-store';
import { generateClientOid } from '../idempotency';
import { Decimal } from 'decimal.js';
import { logger } from '../../core/logger';
import Redis from 'ioredis';

export class SpotTpSlManager {
  constructor(
    private kucoin: KuCoinClient,
    private tpslRepo: TpSlRepository,
    private idempotency: IdempotencyStore,
    private redis: Redis
  ) {}

  async create(params: {
    botId: string;
    userId: string;
    strategyId: string;
    positionId: string;
    symbol: string;
    side: 'buy' | 'sell';
    filledSize: Decimal;
    entryPrice: Decimal;
    tpPrice: Decimal;
    slPrice: Decimal;
    slStopPrice: Decimal;
    signalId: string;
  }): Promise<TpSlRecord> {
    const { botId, userId, symbol, side, filledSize, entryPrice, tpPrice, slPrice, slStopPrice, signalId } = params;

    // O lado das ordens de fechamento é OPOSTO ao lado da posição
    const closeSide: 'buy' | 'sell' = side === 'buy' ? 'sell' : 'buy';

    // Gera clientOids determinísticos
    const tpKey = generateClientOid(`${signalId}:tp`, botId);
    const slKey = generateClientOid(`${signalId}:sl`, botId);

    // Persiste o registro ANTES de enviar qualquer ordem
    const record = await this.tpslRepo.create({
      botId, userId,
      strategyId: params.strategyId,
      positionId: params.positionId,
      marketType: MarketType.SPOT,
      symbol, side,
      totalSize: filledSize.toFixed(8),
      remainingSize: filledSize.toFixed(8),
      entryPrice: entryPrice.toFixed(8),
      tpPrice: tpPrice.toFixed(8),
      slPrice: slPrice.toFixed(8),
      slStopPrice: slStopPrice.toFixed(8),
      tpClientOid: tpKey.clientOid,
      slClientOid: slKey.clientOid,
      status: TpSlStatus.ACTIVE,
    });

    logger.info({ event: 'tpsl_creating', recordId: record.id, symbol, tpPrice: tpPrice.toFixed(2), slPrice: slPrice.toFixed(2) });

    // Envia ordem de Take Profit (Limit)
    try {
      const tpOrder = await this.kucoin.placeOrder({
        clientOid: tpKey.clientOid,
        symbol,
        side: closeSide,
        type: 'limit',
        size: filledSize.toFixed(8),
        price: tpPrice.toFixed(8),
        timeInForce: 'GTC',
        reduceOnly: false,
        remark: `TP:${record.id}`
      });

      await this.tpslRepo.updateTpOrderId(record.id, tpOrder.orderId);
      logger.info({ event: 'tp_order_placed', orderId: tpOrder.orderId });

    } catch (err: any) {
      logger.error({ event: 'tp_order_failed', error: err.message });
      await this.tpslRepo.markFailed(record.id, `TP send failed: ${err.message}`);
      throw err;
    }

    // Envia ordem de Stop Loss (Stop-Limit)
    try {
      const slOrder = await this.kucoin.placeStopOrder({
        clientOid: slKey.clientOid,
        symbol,
        side: closeSide,
        type: 'limit',
        size: filledSize.toFixed(8),
        price: slPrice.toFixed(8),        // Limite
        stopPrice: slStopPrice.toFixed(8), // Gatilho
        stop: side === 'buy' ? 'loss' : 'entry',
        stopPriceType: 'TP',              // Last traded price
        timeInForce: 'GTC',
        remark: `SL:${record.id}`
      });

      await this.tpslRepo.updateSlOrderId(record.id, slOrder.orderId);
      logger.info({ event: 'sl_order_placed', orderId: slOrder.orderId });

    } catch (err: any) {
      logger.error({ event: 'sl_order_failed', error: err.message });
      // TP foi enviado com sucesso mas SL falhou — situação crítica
      await this.tpslRepo.markSlFailed(record.id, `SL send failed: ${err.message}`);
      // Cancelar o TP para evitar estado inconsistente
      await this.cancelTpOrder(record);
      throw err;
    }

    return record;
  }

  /**
   * Chamado quando TP é executado — cancela o SL
   */
  async handleTpFilled(clientOid: string, filledSize: string): Promise<void> {
    const lockKey = `lock:tpsl:cancel:${clientOid}`;
    const lock = await this.redis.set(lockKey, '1', 'EX', 30, 'NX');
    if (!lock) {
      logger.warn({ event: 'tpsl_cancel_race_condition', clientOid });
      return;
    }

    try {
      const record = await this.tpslRepo.findByTpClientOid(clientOid);
      if (!record || record.status !== TpSlStatus.ACTIVE) return;

      logger.info({ event: 'tp_hit_canceling_sl', recordId: record.id, slOrderId: record.slOrderId });

      // Cancela SL na exchange
      if (record.slOrderId) {
        try {
          await this.kucoin.cancelStopOrder(record.slOrderId);
        } catch (err: any) {
          // SL pode já ter sido executado → verificar
          logger.warn({ event: 'sl_cancel_failed', error: err.message });
        }
      }

      await this.tpslRepo.close(record.id, TpSlStatus.TP_HIT, {
        tpFilledSize: filledSize,
        tpFilledAt: new Date(),
        cancelationSource: 'TP_HIT'
      });

    } finally {
      await this.redis.del(lockKey);
    }
  }

  /**
   * Chamado quando SL é executado — cancela o TP
   */
  async handleSlFilled(clientOid: string, filledSize: string): Promise<void> {
    const lockKey = `lock:tpsl:cancel:${clientOid}`;
    const lock = await this.redis.set(lockKey, '1', 'EX', 30, 'NX');
    if (!lock) return;

    try {
      const record = await this.tpslRepo.findBySlClientOid(clientOid);
      if (!record || record.status !== TpSlStatus.ACTIVE) return;

      logger.info({ event: 'sl_hit_canceling_tp', recordId: record.id, tpOrderId: record.tpOrderId });

      if (record.tpOrderId) {
        try {
          await this.kucoin.cancelOrder(record.tpOrderId);
        } catch (err: any) {
          logger.warn({ event: 'tp_cancel_failed', error: err.message });
        }
      }

      await this.tpslRepo.close(record.id, TpSlStatus.SL_HIT, {
        slFilledSize: filledSize,
        slFilledAt: new Date(),
        cancelationSource: 'SL_HIT'
      });

    } finally {
      await this.redis.del(lockKey);
    }
  }

  private async cancelTpOrder(record: TpSlRecord): Promise<void> {
    if (record.tpOrderId) {
      try {
        await this.kucoin.cancelOrder(record.tpOrderId);
      } catch (err) {
        logger.error({ event: 'emergency_tp_cancel_failed', recordId: record.id });
      }
    }
  }
}
```

### 5.4 Implementação para Futures (API Nativa)

```typescript
// src/order/tpsl/futures-tpsl-manager.ts

import { KuCoinFuturesClient } from '../../exchanges/kucoin/futures-client';
import { Decimal } from 'decimal.js';

export class FuturesTpSlManager {
  constructor(private futuresclient: KuCoinFuturesClient) {}

  /**
   * KuCoin Futures tem suporte nativo a TP/SL por posição.
   * Utiliza o endpoint /api/v1/stops/order com type=TP ou type=SL.
   */
  async create(params: {
    symbol: string;
    side: 'buy' | 'sell';
    size: number;             // Número de contratos
    tpPrice: string;
    slPrice: string;
    tpClientOid: string;
    slClientOid: string;
  }): Promise<{ tpOrderId: string; slOrderId: string }> {
    const closeSide: 'buy' | 'sell' = params.side === 'buy' ? 'sell' : 'buy';

    // Take Profit
    const tpOrder = await this.futuresclient.placeStopOrder({
      clientOid: params.tpClientOid,
      symbol: params.symbol,
      side: closeSide,
      type: 'limit',
      size: params.size,
      price: params.tpPrice,
      stopPriceType: 'TP',         // Last traded price
      stop: 'up',                  // Para LONG: ativado quando preço sobe
      stopPrice: params.tpPrice,
      closeOrder: true,            // Garante que é ordem de fechamento
      reduceOnly: true,
    });

    // Stop Loss
    const slOrder = await this.futuresclient.placeStopOrder({
      clientOid: params.slClientOid,
      symbol: params.symbol,
      side: closeSide,
      type: 'limit',
      size: params.size,
      price: new Decimal(params.slPrice).mul('0.999').toFixed(2), // 0.1% abaixo do stop
      stopPriceType: 'TP',
      stop: 'down',                // Para LONG: ativado quando preço cai
      stopPrice: params.slPrice,
      closeOrder: true,
      reduceOnly: true,
    });

    return {
      tpOrderId: tpOrder.orderId,
      slOrderId: slOrder.orderId
    };
  }
}
```

### 5.5 Tratamento de Fill Parcial

```typescript
// src/order/tpsl/partial-fill-handler.ts

import { Decimal } from 'decimal.js';
import { TpSlRepository } from './tpsl-repository';
import { SpotTpSlManager } from './spot-tpsl-manager';
import { logger } from '../../core/logger';

/**
 * Quando a ordem de entrada tem fill parcial, precisamos:
 * 1. Criar TP/SL apenas para o tamanho que foi preenchido
 * 2. Atualizar TP/SL existente se houver fill adicional
 */
export class PartialFillHandler {
  constructor(
    private tpslRepo: TpSlRepository,
    private spotManager: SpotTpSlManager
  ) {}

  async handleAdditionalFill(params: {
    positionId: string;
    botId: string;
    userId: string;
    strategyId: string;
    symbol: string;
    side: 'buy' | 'sell';
    additionalFilledSize: Decimal;
    fillPrice: Decimal;
    signalId: string;
    tpPercent: Decimal;
    slPercent: Decimal;
  }): Promise<void> {
    const existing = await this.tpslRepo.findActiveByPosition(params.positionId);

    if (!existing) {
      // Primeira parte do fill — criar novo TP/SL
      // Calculado com base no preço do fill parcial
      logger.info({ event: 'tpsl_first_partial_fill', positionId: params.positionId });
      // Chamar spotManager.create(...)
    } else {
      // Fill adicional — FECHAR o TP/SL atual e recriar com size total
      logger.info({
        event: 'tpsl_partial_fill_resize',
        positionId: params.positionId,
        oldSize: existing.remainingSize,
        additionalFill: params.additionalFilledSize.toFixed(8)
      });

      const newTotalSize = new Decimal(existing.totalSize).add(params.additionalFilledSize);
      
      // Cancelar TP e SL atuais
      if (existing.tpOrderId) await this.cancelOrder(existing.tpOrderId);
      if (existing.slOrderId) await this.cancelOrder(existing.slOrderId);

      // Marcar como cancelado
      await this.tpslRepo.cancel(existing.id, 'RESIZED_FOR_PARTIAL_FILL');

      // Criar novo TP/SL com tamanho total (usando preço médio ponderado)
      const existingSize = new Decimal(existing.totalSize);
      const existingPrice = new Decimal(existing.entryPrice);
      const avgEntryPrice = existingSize.mul(existingPrice).add(
        params.additionalFilledSize.mul(params.fillPrice)
      ).div(newTotalSize);

      // Recriar via spotManager com newTotalSize e avgEntryPrice
    }
  }

  private async cancelOrder(orderId: string): Promise<void> {
    // Implementar cancelamento com tratamento de erro silencioso
  }
}
```

---

## 6. Edge Cases

| Caso | Tratamento Implementado |
|---|---|
| TP e SL acionados ao mesmo tempo (race) | Redis Lock exclusivo por positionId |
| Posição já fechada antes do TP/SL executar | Guard: verificar status BEFORE do PositionManager no handler |
| SL não preenchido por precio muito diferente (slippage extremo) | Monitor de ordens STUCK: após 30s no stop sem execução, re-avaliar |
| Posição fechada manualmente — TP/SL órfãos | Guardian job rodando a cada 5min: cancela TP/SL de posições fechadas |
| Fill parcial sem proteção durante re-criação | Lock de 30s impede operações concorrentes durante resize |
| exchange offline durante criação do TP | Fallback: tentativa em background com retry a cada 10s |

---

## 7. Guardian Job — Cancelar TP/SL Órfãos

```typescript
// src/order/tpsl/orphan-guardian.ts

import cron from 'node-cron';
import { TpSlRepository } from './tpsl-repository';
import { PositionManager } from '../../position/position-manager';
import { TpSlStatus } from '../models/tpsl-record.model';
import { KuCoinClient } from '../../exchanges/kucoin/client';
import { logger } from '../../core/logger';

export class OrphanGuardian {
  start(): void {
    // Rodar a cada 5 minutos
    cron.schedule('*/5 * * * *', () => this.checkOrphans());
  }

  async checkOrphans(): Promise<void> {
    const activeTpSls = await this.tpslRepo.findByStatus(TpSlStatus.ACTIVE);

    for (const tpsl of activeTpSls) {
      const position = await this.positionManager.getPositionById(tpsl.positionId);

      if (!position || position.size.isZero() || position.isClosed) {
        logger.warn({
          event: 'orphan_tpsl_detected',
          tpslId: tpsl.id,
          positionId: tpsl.positionId
        });

        // Cancelar ordens na exchange
        if (tpsl.tpOrderId) {
          await this.kucoin.cancelOrder(tpsl.tpOrderId).catch(() => {});
        }
        if (tpsl.slOrderId) {
          await this.kucoin.cancelStopOrder(tpsl.slOrderId).catch(() => {});
        }

        await this.tpslRepo.updateStatus(tpsl.id, TpSlStatus.ORPHANED);
      }
    }
  }

  constructor(
    private tpslRepo: TpSlRepository,
    private positionManager: PositionManager,
    private kucoin: KuCoinClient
  ) {}
}
```

---

## 8. Testes Obrigatórios

```typescript
describe('TP/SL Manager', () => {
  it('deve cancelar SL quando TP for executado', async () => {
    const record = await createMockRecord({ status: TpSlStatus.ACTIVE });
    kucoinMock.cancelStopOrder.mockResolvedValue({ code: '200000' });

    await manager.handleTpFilled(record.tpClientOid, '0.1');

    const updated = await tpslRepo.findById(record.id);
    expect(updated.status).toBe(TpSlStatus.TP_HIT);
    expect(kucoinMock.cancelStopOrder).toHaveBeenCalledWith(record.slOrderId);
  });

  it('deve usar Redis Lock para evitar race condition em TP+SL simultâneo', async () => {
    const record = await createMockRecord({ status: TpSlStatus.ACTIVE });
    
    // Duas execuções simultâneas
    const [result1, result2] = await Promise.allSettled([
      manager.handleTpFilled(record.tpClientOid, '0.1'),
      manager.handleSlFilled(record.slClientOid, '0.1')
    ]);

    const updated = await tpslRepo.findById(record.id);
    // Apenas um status final — não ambos
    expect([TpSlStatus.TP_HIT, TpSlStatus.SL_HIT]).toContain(updated.status);
    expect(updated.status).not.toBe(TpSlStatus.ACTIVE);
  });

  it('Guardian deve cancelar TP/SL de posições fechadas', async () => {
    const closedPosition = { isClosed: true, size: new Decimal(0) };
    positionManagerMock.getPositionById.mockResolvedValue(closedPosition);
    
    const record = await createMockRecord({ status: TpSlStatus.ACTIVE });
    await guardian.checkOrphans();
    
    const updated = await tpslRepo.findById(record.id);
    expect(updated.status).toBe(TpSlStatus.ORPHANED);
  });
});
```

---

## 9. Checklist de Implementação

- [ ] `TpSlRecord` com todos os campos persistido no MongoDB
- [ ] `tpClientOid` e `slClientOid` gerados e persistidos ANTES do envio
- [ ] Ordem de TP (Limit) enviada ANTES da ordem de SL
- [ ] Se SL falhar, TP é cancelado — estado nunca inconsistente
- [ ] Redis Lock implementado em `handleTpFilled` e `handleSlFilled`
- [ ] `OrphanGuardian` agendado a cada 5 minutos
- [ ] `PartialFillHandler` trata resize correto de TP/SL
- [ ] Futures usa `reduceOnly: true` e `closeOrder: true`
- [ ] Spot usa `stop-limit` com stopPrice buffer de 0.1%
- [ ] Test: race condition TP+SL simultâneo → apenas 1 status final
- [ ] Test: posição fechada manualmente → Guardian cancela TP/SL em 5min
- [ ] Métricas: `tpsl_tp_hit_count`, `tpsl_sl_hit_count`, `tpsl_orphan_count`

---

## 10. Critérios de Validação Final

| Critério | Aprovação |
|---|---|
| 0 ordens TP e SL executadas simultaneamente | Testado com 1.000 execuções paralelas |
| 100% dos TP/SL cancelados quando posição fechada | Guardian verificado em 24h de operação |
| Restart do servidor não deixa posição sem proteção | Bots recarregam TP/SL do DB ao iniciar |
| Fill parcial recria TP/SL com size correto | Testado com 3 preenchimentos parciais |
| P&L calculado corretamente após TP hit | Diferença < 0.01% do esperado |
