# DOC 08 — Marketplace de Estratégias
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia

---

## 1. Objetivo

Migrar as classes placeholder (`UserStrategy`, `StrategyBotInstance`, `StrategyTrade`) para um sistema de marketplace completo que permita:

- Criadores publicarem estratégias com versionamento semântico
- Compradores assinarem e executarem sem acesso ao código-fonte
- Backtesting obrigatório antes da publicação
- Controle de propriedade intelectual
- Revenue share automático para criadores
- Rastreabilidade completa de performance por estratégia

---

## 2. Problema Atual

```python
# backend/app/strategies/model.py — ESTADO ATUAL (PLACEHOLDER)
class UserStrategy:
    pass  # TODO: Migrar para MongoDB schemas

class StrategyBotInstance:
    pass  # TODO: Migrar para MongoDB schemas

class StrategyTrade:
    pass  # TODO: Migrar para MongoDB schemas
```

**Problema:** Nenhuma estratégia pode ser criada, publicada ou executada de forma real. O marketplace é apenas visual.

---

## 3. Arquitetura do Marketplace

```
┌────────────────────────────────────────────────────────────────────┐
│                    FLUXO DO MARKETPLACE                            │
│                                                                    │
│  CRIADOR                                                           │
│     │  1. Cria estratégia (código + config)                       │
│     │  2. Submete para backtesting                                │
│     │  3. Aprova publicação (>60% Sharpe) ou rejeita              │
│     │  4. Define preço e tier mínimo                              │
│     ▼                                                              │
│  MARKETPLACE                                                       │
│     │  - Listagem por performance, categoria, exchange            │
│     │  - Métricas verificadas: Sharpe, Max DD, Win Rate          │
│     │  - Assinatura mensal ou compra única                        │
│     ▼                                                              │
│  COMPRADOR                                                         │
│     │  1. Assina estratégia                                       │
│     │  2. Configura parâmetros (risk, símbolos)                   │
│     │  3. Cria bot instanciado com essa estratégia                │
│     │  4. Bot executa logica encapsulada (sem acesso ao código)   │
│     ▼                                                              │
│  REVENUE SHARE                                                     │
│     └── Criador recebe X% das assinaturas mensalmente             │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Modelos de Dados

```typescript
// src/strategies/models/strategy.model.ts

export interface StrategyVersion {
  versionId: string;
  semver: string;          // "1.2.0"
  code: string;            // Código compilado/encriptado
  codeHash: string;        // SHA-256 do código original
  parameters: StrategyParameter[];
  changelog: string;
  createdAt: Date;
  backtestResultId?: string;
  status: 'draft' | 'backtesting' | 'approved' | 'rejected' | 'published' | 'deprecated';
}

export interface StrategyParameter {
  key: string;
  label: string;
  type: 'number' | 'string' | 'boolean' | 'select';
  default: unknown;
  min?: number;
  max?: number;
  options?: string[];      // Para tipo 'select'
  required: boolean;
  description: string;
}

export interface UserStrategy {
  strategyId: string;
  creatorId: string;
  name: string;
  description: string;
  category: 'trend_following' | 'mean_reversion' | 'scalping' | 'arbitrage' | 'custom';
  exchanges: string[];        // ['kucoin', 'binance']
  assetTypes: ('spot' | 'futures')[];
  currentVersion: string;     // Semver atual publicada
  versions: StrategyVersion[];
  pricing: {
    type: 'free' | 'monthly' | 'one_time';
    amountUSD: number;
    requiredPlan: 'basic' | 'pro' | 'enterprise';
  };
  metrics: StrategyPublicMetrics; // Calculadas do backtesting
  totalSubscribers: number;
  totalRevenue: number;       // Para o dashboard do criador
  isPublished: boolean;
  createdAt: Date;
  publishedAt?: Date;
}

export interface StrategyPublicMetrics {
  backtestPeriodDays: number;
  totalReturnPct: number;
  annualizedReturnPct: number;
  sharpeRatio: number;
  maxDrawdownPct: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  avgTradeDuration: string;
  verifiedAt: Date;           // Quando o backtesting foi validado
}

export interface StrategyBotInstance {
  instanceId: string;
  botId: string;
  userId: string;
  strategyId: string;
  strategyVersion: string;
  subscriptionId?: string;    // Referência ao pagamento
  parameters: Record<string, unknown>;  // Configurados pelo comprador
  isActive: boolean;
  startedAt: Date;
  createdAt: Date;
}

export interface StrategyTrade {
  tradeId: string;
  instanceId: string;
  strategyId: string;
  userId: string;
  symbol: string;
  side: 'long' | 'short';
  entryPrice: number;
  exitPrice?: number;
  size: number;
  pnlUSD?: number;
  pnlPct?: number;
  entryOrderId: string;
  exitOrderId?: string;
  entryAt: Date;
  exitAt?: Date;
  status: 'open' | 'closed' | 'cancelled';
  exitReason?: 'tp_hit' | 'sl_hit' | 'manual' | 'strategy_signal';
}
```

---

## 5. Sistema de Backtesting

```typescript
// src/strategies/backtesting/backtest-engine.ts

import { Decimal } from 'decimal.js';

export interface BacktestConfig {
  strategyId: string;
  versionId: string;
  symbol: string;
  exchange: 'kucoin' | 'binance';
  startDate: Date;
  endDate: Date;
  initialCapitalUSD: number;
  parameters: Record<string, unknown>;
  makerFeePct: number;   // Ex: 0.1
  takerFeePct: number;   // Ex: 0.1
}

export interface BacktestResult {
  backtestId: string;
  strategyId: string;
  config: BacktestConfig;
  metrics: {
    totalReturnUSD: number;
    totalReturnPct: number;
    annualizedReturnPct: number;
    sharpeRatio: number;
    sortinoRatio: number;
    maxDrawdownPct: number;
    maxDrawdownDurationDays: number;
    winRate: number;
    avgWinUSD: number;
    avgLossUSD: number;
    profitFactor: number;           // totalWins / totalLosses
    calmarRatio: number;            // annualized_return / max_drawdown
    totalTrades: number;
    avgHoldingPeriodHours: number;
    bestTradeUSD: number;
    worstTradeUSD: number;
  };
  trades: BacktestTrade[];
  equityCurve: { timestamp: Date; equityUSD: number }[];
  completedAt: Date;
  passed: boolean;        // true se atende critérios mínimos de publicação
  failureReasons: string[];
}

interface BacktestTrade {
  entryIndex: number;
  exitIndex: number;
  side: 'long' | 'short';
  entryPrice: number;
  exitPrice: number;
  size: number;
  pnlUSD: number;
  pnlPct: number;
  fees: number;
  exitReason: 'tp' | 'sl' | 'signal' | 'end_of_data';
}

// Critérios mínimos para publicação no marketplace
const PUBLICATION_CRITERIA = {
  minSharpeRatio: 0.5,
  maxDrawdownPct: 30,
  minWinRate: 40,
  minTotalTrades: 50,
  minBacktestDays: 90
};

export class BacktestEngine {
  async run(config: BacktestConfig, strategy: CompiledStrategy): Promise<BacktestResult> {
    const klines = await this.fetchHistoricalData(config);
    const trades: BacktestTrade[] = [];
    let equity = config.initialCapitalUSD;
    let peak = equity;
    let maxDD = 0;
    const equityCurve: BacktestResult['equityCurve'] = [];

    for (let i = 50; i < klines.length; i++) {  // 50 candles de warm-up
      const signal = strategy.onCandle(klines.slice(0, i + 1), config.parameters);

      if (signal?.action === 'enter' && trades.every(t => !t.exitIndex)) {
        // Registrar entrada
        // ... lógica de simulação de trade
      }

      // Atualizar equity curve
      equityCurve.push({ timestamp: klines[i].timestamp, equityUSD: equity });
      peak = Math.max(peak, equity);
      const dd = ((peak - equity) / peak) * 100;
      maxDD = Math.max(maxDD, dd);
    }

    const metrics = this.calculateMetrics(trades, config, maxDD);
    const passed = this.validateCriteria(metrics);

    return {
      backtestId: crypto.randomUUID(),
      strategyId: config.strategyId,
      config,
      metrics,
      trades,
      equityCurve,
      completedAt: new Date(),
      passed: passed.passed,
      failureReasons: passed.reasons
    };
  }

  private validateCriteria(metrics: BacktestResult['metrics']): { passed: boolean; reasons: string[] } {
    const reasons: string[] = [];

    if (metrics.sharpeRatio < PUBLICATION_CRITERIA.minSharpeRatio)
      reasons.push(`Sharpe ratio ${metrics.sharpeRatio.toFixed(2)} < ${PUBLICATION_CRITERIA.minSharpeRatio}`);

    if (metrics.maxDrawdownPct > PUBLICATION_CRITERIA.maxDrawdownPct)
      reasons.push(`Max drawdown ${metrics.maxDrawdownPct.toFixed(1)}% > ${PUBLICATION_CRITERIA.maxDrawdownPct}%`);

    if (metrics.winRate < PUBLICATION_CRITERIA.minWinRate)
      reasons.push(`Win rate ${metrics.winRate.toFixed(1)}% < ${PUBLICATION_CRITERIA.minWinRate}%`);

    if (metrics.totalTrades < PUBLICATION_CRITERIA.minTotalTrades)
      reasons.push(`Apenas ${metrics.totalTrades} trades (mínimo ${PUBLICATION_CRITERIA.minTotalTrades})`);

    return { passed: reasons.length === 0, reasons };
  }

  private calculateMetrics(trades: BacktestTrade[], config: BacktestConfig, maxDD: number) {
    const wins = trades.filter(t => t.pnlUSD > 0);
    const losses = trades.filter(t => t.pnlUSD < 0);
    const days = Math.ceil(
      (config.endDate.getTime() - config.startDate.getTime()) / 86400000
    );

    return {
      totalReturnUSD: trades.reduce((s, t) => s + t.pnlUSD, 0),
      totalReturnPct: (trades.reduce((s, t) => s + t.pnlUSD, 0) / config.initialCapitalUSD) * 100,
      annualizedReturnPct: 0, // TODO: fórmula CAGR
      sharpeRatio: this.calcSharpe(trades),
      sortinoRatio: this.calcSortino(trades),
      maxDrawdownPct: maxDD,
      maxDrawdownDurationDays: 0, // TODO
      winRate: trades.length > 0 ? (wins.length / trades.length) * 100 : 0,
      avgWinUSD: wins.length > 0 ? wins.reduce((s, t) => s + t.pnlUSD, 0) / wins.length : 0,
      avgLossUSD: losses.length > 0 ? losses.reduce((s, t) => s + t.pnlUSD, 0) / losses.length : 0,
      profitFactor: losses.reduce((s,t) => s + Math.abs(t.pnlUSD), 0) > 0
        ? wins.reduce((s,t) => s + t.pnlUSD, 0) / Math.abs(losses.reduce((s,t) => s + t.pnlUSD, 0))
        : 0,
      calmarRatio: maxDD > 0 ? (trades.reduce((s,t) => s+t.pnlUSD,0)/config.initialCapitalUSD*100/(days/365)) / maxDD : 0,
      totalTrades: trades.length,
      avgHoldingPeriodHours: 0, // TODO
      bestTradeUSD: Math.max(...trades.map(t => t.pnlUSD), 0),
      worstTradeUSD: Math.min(...trades.map(t => t.pnlUSD), 0)
    };
  }

  private calcSharpe(trades: BacktestTrade[]): number {
    if (trades.length < 2) return 0;
    const returns = trades.map(t => t.pnlPct / 100);
    const avg = returns.reduce((a, b) => a + b, 0) / returns.length;
    const std = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - avg, 2), 0) / returns.length);
    // Sharpe anualizado (assumindo ~252 trades/ano para daily)
    return std > 0 ? (avg / std) * Math.sqrt(252) : 0;
  }

  private calcSortino(trades: BacktestTrade[]): number {
    const returns = trades.map(t => t.pnlPct / 100);
    const avg = returns.reduce((a, b) => a + b, 0) / returns.length;
    const negReturns = returns.filter(r => r < 0);
    const downStd = negReturns.length > 0
      ? Math.sqrt(negReturns.reduce((sum, r) => sum + r * r, 0) / negReturns.length)
      : 0;
    return downStd > 0 ? (avg / downStd) * Math.sqrt(252) : 0;
  }

  private async fetchHistoricalData(config: BacktestConfig): Promise<OHLCV[]> {
    // TODO: Integrar com KuCoin historical klines ou provider de dados (Polygon.io etc)
    throw new Error('Not implemented');
  }
}
```

---

## 6. Revenue Share

```typescript
// src/strategies/revenue-share.service.ts

export class RevenueShareService {
  private readonly PLATFORM_TAKE_RATE = 0.30; // Plataforma fica com 30%
  private readonly CREATOR_SHARE = 0.70;       // Criador recebe 70%

  async processSubscriptionPayment(params: {
    subscriptionId: string;
    strategyId: string;
    amountUSD: number;
  }): Promise<void> {
    const strategy = await this.strategyRepo.findById(params.strategyId);
    if (!strategy || strategy.pricing.type === 'free') return;

    const creatorAmount = params.amountUSD * this.CREATOR_SHARE;
    const platformAmount = params.amountUSD * this.PLATFORM_TAKE_RATE;

    await Promise.all([
      this.walletService.credit({
        userId: strategy.creatorId,
        amountUSD: creatorAmount,
        type: 'strategy_revenue',
        metadata: { subscriptionId: params.subscriptionId, strategyId: params.strategyId }
      }),
      this.db.revenue_events.insertOne({
        strategyId: params.strategyId,
        creatorId: strategy.creatorId,
        subscriptionId: params.subscriptionId,
        totalAmountUSD: params.amountUSD,
        creatorAmountUSD: creatorAmount,
        platformAmountUSD: platformAmount,
        processedAt: new Date()
      })
    ]);

    logger.info({
      event: 'revenue_share_processed',
      strategyId: params.strategyId,
      creatorId: strategy.creatorId,
      creatorAmount
    });
  }
}
```

---

## 7. Checklist de Implementação

- [ ] Migrar `UserStrategy`, `StrategyBotInstance`, `StrategyTrade` de placeholder para schemas reais MongoDB
- [ ] Coleções MongoDB: `strategies`, `strategy_versions`, `strategy_subscriptions`, `strategy_trades`, `backtest_results`, `revenue_events`
- [ ] Índices: `strategies.creatorId`, `strategies.category`, `strategy_subscriptions.userId+strategyId`
- [ ] Engine de backtesting com dados históricos reais (mínimo 1 ano)
- [ ] Critérios mínimos de publicação validados obrigatoriamente antes de publicar
- [ ] Código de estratégia encriptado em repouso (AES-256)
- [ ] Versionamento semântico com changelog obrigatório
- [ ] Revenue share automático via Stripe Connect ou carteira interna
- [ ] Performance tracking em tempo real por instância de bot
- [ ] Teardown de instância quando usuário cancela assinatura
- [ ] Métricas de marketplace: subscriptions ativas, top estratégias, receita por criador

---

## 8. Critérios de Validação Final

| Critério | Aprovação |
|---|---|
| Nenhuma estratégia publicada sem backtesting aprovado | 100% enforcement |
| Revenue share processado em < 24h após pagamento | Automático via webhook |
| Código de estratégia nunca exposto ao comprador | Verificado por security audit |
| Performance real correlaciona com backtesting | Desvio < 20% esperado |
| Teardown de instância após cancelamento | Em < 5 minutos |
