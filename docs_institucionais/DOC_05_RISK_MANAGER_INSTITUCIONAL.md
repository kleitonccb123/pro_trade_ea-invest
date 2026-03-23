# DOC 05 — Risk Manager Institucional
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia

---

## 1. Objetivo

Implementar um Risk Manager multicamada que seja o **gatekeeper final de todas as ordens**, garantindo:

- Jamais exceder max loss diário por usuário ou por bot
- Jamais exceder max drawdown da conta
- Jamais abrir posição além do max position size absoluto
- Cooldown automático pós-série de perdas
- Kill-switch automático por volatilidade extrema (VIX de crypto)
- Controle global de plataforma (shutdown coordinado)
- Auditória imutável de todas as decisões do Risk Manager

---

## 2. Problema Atual

| Risco Não Controlado | Consequência Possível |
|---|---|
| Bot em loop de re-entrada após stop-loss | Perder 100% da conta em horas |
| Volatilidade extrema (crash/pump de 30%) | Slippage catastrófico, margin call |
| Usuário sem max position size | Uma ordem buy de $50.000 com $10.000 na conta (alavancagem incorreta) |
| N bots do usuário somam posição > limite | Limite individual respeitado, mas limite agregado violado |
| Drawdown não monitorado | Bot que ganhou $1000 e perdeu $800 ainda opera normalmente |
| Nenhum cooldown pós-perda | Bot tenta recuperar agressivamente → espiral de perdas |

---

## 3. Camadas de Risco

```
┌─────────────────────────────────────────────────────────────────┐
│                    HIERARQUIA DE CONTROLES                      │
│                                                                 │
│  CAMADA 1: PLATAFORMA GLOBAL                                   │
│  ├── Kill-switch global (shutdown emergencial)                 │
│  ├── Max volume diário total                                   │
│  └── Volatility index (VIX proxy de crypto)                   │
│                                                                 │
│  CAMADA 2: POR USUÁRIO                                        │
│  ├── Max loss diário em USD                                    │
│  ├── Max drawdown desde peak                                   │
│  ├── Max capital em risco simultâneo                           │
│  ├── Max posição por símbolo                                   │
│  └── Cooldown pós-perda (min)                                  │
│                                                                 │
│  CAMADA 3: POR BOT                                            │
│  ├── Max loss diário do bot                                    │
│  ├── Max posições abertas simultâneas                          │
│  ├── Max tamanho de ordem individual                           │
│  ├── Consecutivos stops antes de cooldown                      │
│  └── Kill automático por performance                           │
│                                                                 │
│  CAMADA 4: POR ORDEM                                          │
│  ├── Valida side vs posição atual (anti-side-flip acidental)   │
│  ├── Valida tamanho vs tick size e lot size                    │
│  ├── Valida preço vs spread máximo aceitável                   │
│  └── Valida liquidez do mercado (volume 24h mínimo)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Modelos de Dados

```typescript
// src/risk/models/risk-profile.model.ts

export interface UserRiskProfile {
  userId: string;
  version: number;

  // Limites USD
  maxDailyLossUSD: number;        // Ex: 500
  maxDrawdownPct: number;          // Ex: 20%  (do peak diário)
  maxCapitalAtRiskPct: number;     // Ex: 40%  (do saldo total)
  maxPositionSizeUSD: number;      // Ex: 2000 (por símbolo)
  maxAggregatedPositionUSD: number; // Ex: 5000 (todos os bots somados)

  // Cooldowns
  cooldownAfterLossMinutes: number;    // Ex: 30
  cooldownAfterConsecutiveLosses: number; // Ex: 3 perdas → 60min pause
  cooldownDurationMinutes: number;     // Ex: 60

  // Kill automático
  autoKillAfterLossBreaches: number;   // Ex: matar bot após 2 dias ruins
  plan: 'basic' | 'pro' | 'enterprise';
}

export interface BotRiskProfile {
  botId: string;
  userId: string;
  maxDailyLossUSD: number;
  maxOpenPositions: number;
  maxSingleOrderUSD: number;
  consecutiveLossLimit: number;  // Parar bot
}

export interface RiskState {
  // Estado diário do usuário (reset ao fim do dia UTC)
  userId: string;
  date: string;                    // "2025-01-21"
  dailyPnlUSD: number;             // Pode ser negativo
  peakDailyBalanceUSD: number;     // Para cálculo de drawdown
  currentDrawdownPct: number;      // (peak - current) / peak * 100
  capitalAtRiskUSD: number;        // Soma de todas posições abertas
  isInCooldown: boolean;
  cooldownUntil?: Date;
  consecutiveLosses: number;
  breachCount: number;             // Reset toda semana
}

export type RiskDecision = 
  | { approved: true }
  | { approved: false; reason: RiskRejectionReason; severity: 'warn' | 'block' | 'kill' };

export type RiskRejectionReason =
  | 'MAX_DAILY_LOSS_REACHED'
  | 'MAX_DRAWDOWN_REACHED'
  | 'MAX_CAPITAL_AT_RISK'
  | 'MAX_POSITION_SIZE'
  | 'COOLDOWN_ACTIVE'
  | 'BOT_KILLED'
  | 'MARKET_VOLATILITY_HIGH'
  | 'GLOBAL_KILL_SWITCH'
  | 'INSUFFICIENT_LIQUIDITY'
  | 'CONSECUTIVE_LOSSES_LIMIT';
```

---

## 5. Implementação do Risk Manager

```typescript
// src/risk/risk-manager.ts

import { Decimal } from 'decimal.js';
import Redis from 'ioredis';
import { UserRiskProfile, BotRiskProfile, RiskState, RiskDecision } from './models/risk-profile.model';
import { RiskRepository } from './risk-repository';
import { RiskAuditLog } from './risk-audit-log';
import { MarketVolatilityIndexer } from './volatility-indexer';
import { logger } from '../core/logger';

interface RiskEvaluationInput {
  userId: string;
  botId: string;
  symbol: string;
  side: 'buy' | 'sell';
  estimatedValueUSD: Decimal;    // Valor total em USD da ordem
  currentPositionUSD: Decimal;   // Posição atual em USD deste símbolo
}

export class RiskManager {
  constructor(
    private redis: Redis,
    private riskRepo: RiskRepository,
    private auditLog: RiskAuditLog,
    private volatilityIndexer: MarketVolatilityIndexer
  ) {}

  /**
   * GATE PRINCIPAL — chamado pelo PreflightChecker antes de TODA ordem.
   */
  async evaluate(input: RiskEvaluationInput): Promise<RiskDecision> {
    // ── CAMADA 1: KILL SWITCH GLOBAL ──────────────────────────────────
    const globalKill = await this.redis.get('risk:global:kill_switch');
    if (globalKill === '1') {
      return this.reject('GLOBAL_KILL_SWITCH', 'kill', input, 'Kill switch global ativo');
    }

    // ── CAMADA 1: VOLATILIDADE DO MERCADO ──────────────────────────────
    const volatility = await this.volatilityIndexer.getVolatilityScore(input.symbol);
    if (volatility > 85) {
      return this.reject('MARKET_VOLATILITY_HIGH', 'block', input,
        `Volatilidade extrema: score=${volatility}/100 para ${input.symbol}`);
    }

    const [userProfile, botProfile, riskState] = await Promise.all([
      this.riskRepo.getUserProfile(input.userId),
      this.riskRepo.getBotProfile(input.botId),
      this.getRiskState(input.userId)
    ]);

    // ── CAMADA 2: COOLDOWN ATIVO ───────────────────────────────────────
    if (riskState.isInCooldown && riskState.cooldownUntil && riskState.cooldownUntil > new Date()) {
      const remainingMinutes = Math.ceil(
        (riskState.cooldownUntil.getTime() - Date.now()) / 60_000
      );
      return this.reject('COOLDOWN_ACTIVE', 'block', input,
        `Cooldown ativo por ${remainingMinutes}min por sequência de perdas`);
    }

    // ── CAMADA 2: MAX LOSS DIÁRIO ──────────────────────────────────────
    if (riskState.dailyPnlUSD <= -userProfile.maxDailyLossUSD) {
      await this.activateCooldown(input.userId, riskState, userProfile, 'MAX_DAILY_LOSS');
      return this.reject('MAX_DAILY_LOSS_REACHED', 'block', input,
        `Daily loss atingido: PnL=${riskState.dailyPnlUSD.toFixed(2)} USD, limite=${-userProfile.maxDailyLossUSD} USD`);
    }

    // ── CAMADA 2: MAX DRAWDOWN ─────────────────────────────────────────
    if (riskState.currentDrawdownPct >= userProfile.maxDrawdownPct) {
      return this.reject('MAX_DRAWDOWN_REACHED', 'block', input,
        `Drawdown atingido: ${riskState.currentDrawdownPct.toFixed(2)}% >= limite ${userProfile.maxDrawdownPct}%`);
    }

    // ── CAMADA 2: MAX CAPITAL EM RISCO ─────────────────────────────────
    const accountBalance = await this.getAccountBalance(input.userId);
    const capitalAtRiskLimit = accountBalance * (userProfile.maxCapitalAtRiskPct / 100);
    const projectedCapital = riskState.capitalAtRiskUSD + input.estimatedValueUSD.toNumber();

    if (projectedCapital > capitalAtRiskLimit) {
      return this.reject('MAX_CAPITAL_AT_RISK', 'warn', input,
        `Capital em risco: projetado=${projectedCapital.toFixed(2)} USD, limite=${capitalAtRiskLimit.toFixed(2)} USD (${userProfile.maxCapitalAtRiskPct}% da conta)`);
    }

    // ── CAMADA 2: MAX POSITION SIZE ────────────────────────────────────
    const projectedPosition = input.currentPositionUSD.toNumber() + input.estimatedValueUSD.toNumber();
    if (projectedPosition > userProfile.maxPositionSizeUSD) {
      return this.reject('MAX_POSITION_SIZE', 'block', input,
        `Posição máxima: projetada=${projectedPosition.toFixed(2)} USD, limite=${userProfile.maxPositionSizeUSD} USD em ${input.symbol}`);
    }

    // ── CAMADA 3: CONSECUTIVE LOSSES DO BOT ───────────────────────────
    const botConsecutiveLosses = await this.getBotConsecutiveLosses(input.botId);
    if (botConsecutiveLosses >= botProfile.consecutiveLossLimit) {
      await this.killBot(input.botId, `${botConsecutiveLosses} perdas consecutivas`);
      return this.reject('CONSECUTIVE_LOSSES_LIMIT', 'kill', input,
        `Bot ${input.botId} morto após ${botConsecutiveLosses} perdas consecutivas`);
    }

    await this.auditLog.record({
      userId: input.userId,
      botId: input.botId,
      symbol: input.symbol,
      action: 'APPROVED',
      context: { riskState, volatility }
    });

    return { approved: true };
  }

  private reject(
    reason: any,
    severity: 'warn' | 'block' | 'kill',
    input: RiskEvaluationInput,
    details: string
  ): RiskDecision {
    logger.warn({ event: 'risk_rejected', reason, severity, ...input, details });
    this.auditLog.record({
      userId: input.userId,
      botId: input.botId,
      symbol: input.symbol,
      action: 'REJECTED',
      reason,
      severity,
      details
    }).catch(() => {});

    return { approved: false, reason, severity };
  }

  private async activateCooldown(
    userId: string,
    state: RiskState,
    profile: UserRiskProfile,
    trigger: string
  ): Promise<void> {
    const cooldownUntil = new Date(Date.now() + profile.cooldownDurationMinutes * 60_000);

    await this.riskRepo.updateRiskState(userId, {
      isInCooldown: true,
      cooldownUntil,
      breachCount: state.breachCount + 1
    });

    logger.warn({
      event: 'risk_cooldown_activated',
      userId,
      trigger,
      cooldownMinutes: profile.cooldownDurationMinutes,
      cooldownUntil
    });
  }

  async recordTradeClosed(params: {
    userId: string;
    botId: string;
    pnlUSD: number;
  }): Promise<void> {
    const { userId, botId, pnlUSD } = params;
    const state = await this.getRiskState(userId);

    const newDailyPnl = state.dailyPnlUSD + pnlUSD;
    const newPeak = Math.max(state.peakDailyBalanceUSD, state.peakDailyBalanceUSD + pnlUSD);
    const currentBalance = await this.getAccountBalance(userId);
    const drawdown = newPeak > 0 ? ((newPeak - currentBalance) / newPeak) * 100 : 0;

    let newConsecutiveLosses = pnlUSD < 0
      ? state.consecutiveLosses + 1
      : 0;

    await this.riskRepo.updateRiskState(userId, {
      dailyPnlUSD: newDailyPnl,
      peakDailyBalanceUSD: newPeak,
      currentDrawdownPct: drawdown,
      consecutiveLosses: newConsecutiveLosses
    });

    // Atualizar consecutive losses do bot
    if (pnlUSD < 0) {
      await this.redis.incr(`risk:bot:${botId}:consecutive_losses`);
      await this.redis.expire(`risk:bot:${botId}:consecutive_losses`, 86400);
    } else {
      await this.redis.del(`risk:bot:${botId}:consecutive_losses`);
    }

    logger.info({ event: 'risk_trade_recorded', userId, botId, pnlUSD, newDailyPnl, drawdown });
  }

  private async killBot(botId: string, reason: string): Promise<void> {
    await this.redis.set(`bot:kill:${botId}`, '1', 'EX', 86400 * 7); // 7 dias
    logger.error({ event: 'bot_killed_by_risk', botId, reason });
    // TODO: Emitir evento para notificar usuário via email/push
  }

  private async getRiskState(userId: string): Promise<RiskState> {
    const today = new Date().toISOString().slice(0, 10);
    return this.riskRepo.getOrCreateRiskState(userId, today);
  }

  private async getBotConsecutiveLosses(botId: string): Promise<number> {
    const val = await this.redis.get(`risk:bot:${botId}:consecutive_losses`);
    return parseInt(val ?? '0', 10);
  }

  private async getAccountBalance(userId: string): Promise<number> {
    const cached = await this.redis.get(`risk:balance_usd:${userId}`);
    return parseFloat(cached ?? '0');
  }
}
```

---

## 6. Volatility Indexer (Proxy de Crypto VIX)

```typescript
// src/risk/volatility-indexer.ts

import { KuCoinClient } from '../exchanges/kucoin/client';
import Redis from 'ioredis';
import { Decimal } from 'decimal.js';

/**
 * Calcula um índice de volatilidade intraday baseado em:
 * - ATR (Average True Range) como % do preço
 * - Volume spike (volume atual vs média de 7d)
 * - Spread bid/ask como % do meio-preço
 * 
 * Score de 0–100. Acima de 85 = risco extremo → bloquear novas entradas.
 */
export class MarketVolatilityIndexer {
  private readonly CACHE_TTL_SEC = 30;

  constructor(
    private kucoin: KuCoinClient,
    private redis: Redis
  ) {}

  async getVolatilityScore(symbol: string): Promise<number> {
    const cached = await this.redis.get(`volatility:${symbol}`);
    if (cached) return parseFloat(cached);

    const [klines, ticker] = await Promise.all([
      this.kucoin.getKlines(symbol, '1min', 20),  // Últimas 20 velas de 1min
      this.kucoin.getTicker(symbol)
    ]);

    const atrPct = this.calculateAtrPct(klines);
    const volumeSpike = this.calculateVolumeSpike(klines);
    const spreadPct = this.calculateSpreadPct(ticker);

    // Score ponderado
    const score = Math.min(100, (
      atrPct * 0.5 +    // ATR tem maior peso
      volumeSpike * 0.3 +
      spreadPct * 0.2
    ));

    await this.redis.setex(`volatility:${symbol}`, this.CACHE_TTL_SEC, score.toFixed(4));
    return score;
  }

  private calculateAtrPct(klines: any[]): number {
    // True Range = max(high-low, |high-prevClose|, |low-prevClose|)
    const trueRanges = klines.slice(1).map((kline, i) => {
      const prev = klines[i];
      const tr = Math.max(
        parseFloat(kline[3]) - parseFloat(kline[4]),           // high - low
        Math.abs(parseFloat(kline[3]) - parseFloat(prev[2])),  // |high - prevClose|
        Math.abs(parseFloat(kline[4]) - parseFloat(prev[2]))   // |low - prevClose|
      );
      return (tr / parseFloat(kline[2])) * 100; // Como % do preço
    });

    const atr = trueRanges.reduce((a, b) => a + b, 0) / trueRanges.length;
    // Normalizar: 0.1% ATR = score 10, 1% = score 100
    return Math.min(100, atr * 100);
  }

  private calculateVolumeSpike(klines: any[]): number {
    const volumes = klines.map((k: any) => parseFloat(k[5]));
    const avgVolume = volumes.slice(0, -1).reduce((a, b) => a + b, 0) / (volumes.length - 1);
    const currentVolume = volumes[volumes.length - 1];
    const ratio = avgVolume > 0 ? currentVolume / avgVolume : 1;
    // 2x volume = score 50, 4x = score 100
    return Math.min(100, (ratio - 1) * 33.3);
  }

  private calculateSpreadPct(ticker: any): number {
    const bid = parseFloat(ticker.bestBid);
    const ask = parseFloat(ticker.bestAsk);
    if (bid <= 0) return 0;
    const spread = ((ask - bid) / bid) * 100;
    // 0.1% spread = score 10, 1% spread = score 100
    return Math.min(100, spread * 100);
  }
}
```

---

## 7. Fórmulas Matemáticas

### Max Drawdown
$$\text{Drawdown} = \frac{\text{Peak Balance} - \text{Current Balance}}{\text{Peak Balance}} \times 100$$

### Kelly Criterion (Max Position Size Dinâmico)
$$f^* = \frac{W \cdot R - (1 - W)}{R}$$

Onde:
- $W$ = Taxa de acerto do bot (win rate)
- $R$ = Ratio médio ganho/perda (risk/reward ratio)
- $f^*$ = Fração ótima do capital a arriscar

### ATR (Average True Range)
$$TR_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$$
$$ATR = \frac{1}{n} \sum_{i=1}^{n} TR_i$$

### Volatility Score
$$V_{score} = \min\left(100, \; \frac{ATR\%}{P} \cdot 0.5 + \text{VolumeSpike} \cdot 0.3 + \text{Spread\%} \cdot 0.2\right) \times 100$$

---

## 8. Edge Cases Críticos

### 8.1 Peak Balance Negativo (conta com margin call)
```typescript
// Se currentBalance cair abaixo de 0 (posições negativas em futures)
const drawdown = newPeak > 0
  ? ((newPeak - currentBalance) / newPeak) * 100
  : 100; // Forçar 100% drawdown → trigger kill
```

### 8.2 Reset Diário Seguro
```typescript
// Job cron meia-noite UTC
async function dailyRiskReset(): Promise<void> {
  const users = await riskRepo.getUsersWithActiveStates();
  
  for (const userId of users) {
    const current = await riskRepo.getRiskState(userId);
    const newBalance = await kucoin.getTotalBalance(userId);
    
    // O "peak" do novo dia começa com o saldo atual
    await riskRepo.createRiskState(userId, {
      dailyPnlUSD: 0,
      peakDailyBalanceUSD: newBalance,
      currentDrawdownPct: 0,
      capitalAtRiskUSD: current.capitalAtRiskUSD, // Posições abertas persistem!
      isInCooldown: false,     // Reset cooldown diário
      consecutiveLosses: current.consecutiveLosses // NÃO reseta consecutivas
    });
  }
}
```

### 8.3 Multi-Bot Agregado
```typescript
// Verificar posição total do usuário em um símbolo (via Position Manager)
const allUserPositions = await positionManager.getByUserAndSymbol(userId, symbol);
const totalPositionUSD = allUserPositions.reduce(
  (sum, pos) => sum + Math.abs(pos.notionalUSD),
  0
);
// Usar totalPositionUSD no check de maxPositionSizeUSD
```

### 8.4 Cooldown Não Bloqueia Fechamentos
```typescript
// O Risk Manager deve SEMPRE permitir ordens de fechamento (side oposta à posição)
if (riskState.isInCooldown && side === existingPosition.closingSide) {
  return { approved: true }; // Permitir fechar posição mesmo em cooldown
}
```

---

## 9. Testes Obrigatórios

```typescript
describe('RiskManager', () => {
  describe('Max Daily Loss', () => {
    it('deve bloquear quando PnL diário atingir limite', async () => {
      await riskRepo.updateRiskState('user-001', { dailyPnlUSD: -500 });
      await profileRepo.save({ userId: 'user-001', maxDailyLossUSD: 500 });

      const result = await riskManager.evaluate(baseInput);

      expect(result.approved).toBe(false);
      expect((result as any).reason).toBe('MAX_DAILY_LOSS_REACHED');
    });
  });

  describe('Cooldown', () => {
    it('deve ativar cooldown após max daily loss', async () => {
      await simulateDailyLoss('user-001', 501);
      const state = await riskRepo.getRiskState('user-001');

      expect(state.isInCooldown).toBe(true);
      expect(state.cooldownUntil).toBeDefined();
      expect(state.cooldownUntil!.getTime()).toBeGreaterThan(Date.now());
    });

    it('deve permitir fechamento de posição durante cooldown', async () => {
      await setState({ isInCooldown: true, cooldownUntil: futureDate() });
      const result = await riskManager.evaluate({ ...baseInput, side: 'sell', hasOpenLong: true });
      expect(result.approved).toBe(true);
    });
  });

  describe('Volatility', () => {
    it('deve bloquear quando volatility score > 85', async () => {
      volatilityMock.getVolatilityScore.mockResolvedValue(90);
      const result = await riskManager.evaluate(baseInput);
      expect((result as any).reason).toBe('MARKET_VOLATILITY_HIGH');
    });
  });

  describe('Capital at Risk', () => {
    it('deve bloquear quando ordem projetada ultrapassar maxCapitalAtRiskPct', async () => {
      // Conta: $10.000, maxCapitalAtRiskPct: 40% = $4.000
      // Já em risco: $3.800, nova ordem: $300 → total $4.100 > $4.000
      await setState({ capitalAtRiskUSD: 3800 });
      const result = await riskManager.evaluate({ ...baseInput, estimatedValueUSD: new Decimal('300') });
      expect((result as any).reason).toBe('MAX_CAPITAL_AT_RISK');
    });
  });

  describe('Bot Kill', () => {
    it('deve matar bot após consecutiveLossLimit', async () => {
      await redis.set('risk:bot:bot-001:consecutive_losses', '5');
      await botProfileRepo.save({ botId: 'bot-001', consecutiveLossLimit: 5 });

      const result = await riskManager.evaluate(baseInput);

      expect((result as any).reason).toBe('CONSECUTIVE_LOSSES_LIMIT');
      expect((result as any).severity).toBe('kill');
      expect(await redis.get('bot:kill:bot-001')).toBe('1');
    });
  });
});
```

---

## 10. Checklist de Implementação

- [ ] `UserRiskProfile` persistido em MongoDB por usuário
- [ ] `BotRiskProfile` persistido por bot
- [ ] `RiskState` com chave composta `{userId}:{date}` para reset diário
- [ ] `RiskManager.evaluate()` chamado em TODA ordem (no PreflightChecker)
- [ ] `RiskManager.recordTradeClosed()` chamado em TODO fechamento de trade
- [ ] Cooldown não bloqueia ordens de fechamento
- [ ] `MarketVolatilityIndexer` com cache Redis 30s
- [ ] Kill-switch global via `risk:global:kill_switch` no Redis
- [ ] Kill de bot individual via `bot:kill:{botId}` no Redis
- [ ] Job cron diário (00:00 UTC) para reset de `RiskState`
- [ ] Job cron meia-noite para verificar bots mortos e notificar usuário
- [ ] `RiskAuditLog` imutável com hash encadeado para todas as decisões
- [ ] Interface de admin para visualizar risk states e forçar cooldowns
- [ ] Testes unitários com 100% cobertura dos cases de rejeição
- [ ] Testes de carga: 10.000 evaluations/s sem degradação

---

## 11. Critérios de Validação Final

| Critério | Valor Alvo |
|---|---|
| Zero orders acima do daily loss limit | 0 violações em 30 dias |
| Drawdown máximo observado | ≤ configurado no perfil |
| Tempo de evaluate() | P99 < 50ms |
| Cobertura de testes | ≥ 95% |
| Auditoria de todas as decisões | 100% rastreável |
| Kill-switch global ativa em < N segundos | < 2s para propagar a todos os workers |
| Zero falsos positivos em fechamentos | Closing orders nunca bloqueadas |
