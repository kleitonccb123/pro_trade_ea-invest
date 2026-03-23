# DOC 09 — Multi-Exchange Architecture
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia

---

## 1. Objetivo

Projetar uma camada de abstração `ExchangeAdapter` que permita ao sistema suportar múltiplas exchanges (KuCoin, Binance, OKX) com:

- Interface unificada independente de API específica
- Rate limiting independente por exchange
- Failover automático entre exchanges
- WebSocket unificado independente de formato por exchange
- Normalização de modelos (Order, Position, Balance) para formato interno único
- Onboarding de nova exchange em < 1 sprint

---

## 2. Problema Atual

| Gap | Impacto |
|---|---|
| KuCoin hardcoded em toda a stack | Impossível adicionar Binance sem refatoração massiva |
| Binance implementada só no frontend | Backend completamente KuCoin-only |
| Rate limits diferentes por exchange | Sem controle, Binance tem limites diferentes de KuCoin |
| Formatos de resposta incompatíveis | `clientOid` (KuCoin) vs `clientOrderId` (Binance) |
| WebSocket com formato específico por exchange | Impossível fazer fan-out multi-exchange |

---

## 3. Interface `ExchangeAdapter`

```typescript
// src/exchanges/exchange-adapter.interface.ts

import { Decimal } from 'decimal.js';

// ── MODELOS NORMALIZADOS INTERNOS ────────────────────────────────

export interface NormalizedOrder {
  id: string;               // orderId da exchange
  clientOrderId: string;    // clientOid / clientOrderId
  symbol: string;           // Sempre no formato "BTC-USDT"
  side: 'buy' | 'sell';
  type: 'limit' | 'market' | 'stop' | 'stop_limit';
  status: 'pending' | 'open' | 'partially_filled' | 'filled' | 'cancelled' | 'rejected';
  size: Decimal;
  filledSize: Decimal;
  price: Decimal | null;
  avgFillPrice: Decimal | null;
  fee: Decimal;
  feeCurrency: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface NormalizedBalance {
  currency: string;
  available: Decimal;
  total: Decimal;
  locked: Decimal;
  updatedAt: Date;
}

export interface NormalizedPosition {
  symbol: string;
  side: 'long' | 'short';
  size: Decimal;
  entryPrice: Decimal;
  markPrice: Decimal;
  liquidationPrice: Decimal | null;
  unrealizedPnl: Decimal;
  leverage: number;
  marginType: 'isolated' | 'cross';
  createdAt: Date;
}

export interface PlaceOrderParams {
  clientOrderId: string;    // Gerado internamente (idempotência)
  symbol: string;           // "BTC-USDT"
  side: 'buy' | 'sell';
  type: 'limit' | 'market';
  size: Decimal;
  price?: Decimal;
  timeInForce?: 'GTC' | 'IOC' | 'FOK';
  reduceOnly?: boolean;
  postOnly?: boolean;
  stopPrice?: Decimal;
}

export interface TpSlParams {
  orderId: string;          // Ordem principal que originou o TP/SL
  symbol: string;
  side: 'buy' | 'sell';
  size: Decimal;
  tpPrice: Decimal;
  slPrice: Decimal;
  tpOrderType: 'limit' | 'market';
  slOrderType: 'limit' | 'market';
}

export interface MarketData {
  symbol: string;
  bestBid: Decimal;
  bestAsk: Decimal;
  lastPrice: Decimal;
  volume24h: Decimal;
  priceChange24hPct: Decimal;
  timestamp: Date;
}

// ── INTERFACE PRINCIPAL ───────────────────────────────────────────

export interface ExchangeAdapter {
  readonly exchangeId: 'kucoin' | 'binance' | 'okx';
  readonly displayName: string;
  readonly supportsFutures: boolean;
  readonly supportsNativeTpSl: boolean;  // KuCoin Futures sim, KuCoin Spot não

  // Conectividade
  isConnected(): boolean;
  getServerTime(): Promise<Date>;

  // Ordens Spot
  placeSpotOrder(params: PlaceOrderParams): Promise<NormalizedOrder>;
  cancelOrder(symbol: string, orderId: string): Promise<boolean>;
  getOrder(symbol: string, orderId: string): Promise<NormalizedOrder>;
  getOpenOrders(symbol?: string): Promise<NormalizedOrder[]>;

  // Ordens Futures (opcional)
  placeFuturesOrder?(params: PlaceOrderParams): Promise<NormalizedOrder>;
  placeTpSl?(params: TpSlParams): Promise<{ tpOrderId: string; slOrderId: string }>;
  getPositions?(): Promise<NormalizedPosition[]>;

  // Saldo
  getBalances(): Promise<NormalizedBalance[]>;
  getBalance(currency: string): Promise<NormalizedBalance>;

  // Dados de mercado
  getTicker(symbol: string): Promise<MarketData>;
  getOrderBook(symbol: string, depth?: number): Promise<{ bids: [Decimal, Decimal][]; asks: [Decimal, Decimal][] }>;
  getKlines(symbol: string, interval: string, limit: number): Promise<OHLCV[]>;

  // Informações de símbolo
  getSymbolInfo(symbol: string): Promise<SymbolInfo>;
  getSupportedSymbols(): Promise<string[]>;

  // WebSocket
  subscribeOrderUpdates(callback: (order: NormalizedOrder) => void): () => void;
  subscribeTicker(symbol: string, callback: (data: MarketData) => void): () => void;
  subscribeExecutions(callback: (order: NormalizedOrder) => void): () => void;
}
```

---

## 4. Implementação KuCoin Adapter

```typescript
// src/exchanges/kucoin/kucoin.adapter.ts

import { ExchangeAdapter, PlaceOrderParams, NormalizedOrder } from '../exchange-adapter.interface';
import { KuCoinRestClient } from './rest-client';
import { Decimal } from 'decimal.js';

export class KuCoinAdapter implements ExchangeAdapter {
  readonly exchangeId = 'kucoin' as const;
  readonly displayName = 'KuCoin';
  readonly supportsFutures = true;
  readonly supportsNativeTpSl = true;  // Apenas em Futures

  constructor(private client: KuCoinRestClient) {}

  async placeSpotOrder(params: PlaceOrderParams): Promise<NormalizedOrder> {
    // Mapeia formato interno → formato KuCoin
    const payload = {
      clientOid: params.clientOrderId,  // KuCoin usa "clientOid"
      symbol: params.symbol.replace('-', '-'),  // KuCoin usa "BTC-USDT"
      side: params.side,
      type: params.type,
      size: params.size.toFixed(8),
      price: params.price?.toFixed(8),
      timeInForce: params.timeInForce ?? 'GTC'
    };

    const response = await this.client.post('/api/v1/orders', payload);

    // Mapeia resposta KuCoin → formato interno normalizado
    return this.normalizeOrder(response.data);
  }

  private normalizeOrder(raw: any): NormalizedOrder {
    return {
      id: raw.orderId,
      clientOrderId: raw.clientOid,
      symbol: raw.symbol,
      side: raw.side,
      type: raw.type,
      status: this.mapStatus(raw.isActive, raw.cancelExist, raw.dealSize, raw.size),
      size: new Decimal(raw.size),
      filledSize: new Decimal(raw.dealSize ?? '0'),
      price: raw.price ? new Decimal(raw.price) : null,
      avgFillPrice: raw.dealFunds && raw.dealSize && parseFloat(raw.dealSize) > 0
        ? new Decimal(raw.dealFunds).div(new Decimal(raw.dealSize))
        : null,
      fee: new Decimal(raw.fee ?? '0'),
      feeCurrency: raw.feeCurrency ?? 'USDT',
      createdAt: new Date(raw.createdAt),
      updatedAt: new Date(raw.updatedAt ?? raw.createdAt)
    };
  }

  private mapStatus(isActive: boolean, cancelExist: boolean, dealSize: string, size: string): NormalizedOrder['status'] {
    if (cancelExist && !parseFloat(dealSize)) return 'cancelled';
    if (!isActive && parseFloat(dealSize) >= parseFloat(size)) return 'filled';
    if (!isActive && parseFloat(dealSize) > 0) return 'partially_filled';
    if (isActive && parseFloat(dealSize) > 0) return 'partially_filled';
    if (isActive) return 'open';
    return 'cancelled';
  }

  // ... outros métodos do adapter
}
```

### 4.1 Skeleton do Binance Adapter

```typescript
// src/exchanges/binance/binance.adapter.ts

export class BinanceAdapter implements ExchangeAdapter {
  readonly exchangeId = 'binance' as const;
  readonly displayName = 'Binance';
  readonly supportsFutures = true;
  readonly supportsNativeTpSl = false;

  async placeSpotOrder(params: PlaceOrderParams): Promise<NormalizedOrder> {
    // Binance usa "clientOrderId" ao invés de "clientOid"
    // Binance usa "BTCUSDT" ao invés de "BTC-USDT"
    const binanceSymbol = params.symbol.replace('-', '');

    const payload = {
      symbol: binanceSymbol,
      side: params.side.toUpperCase(),
      type: params.type.toUpperCase(),
      quantity: params.size.toFixed(8),
      price: params.price?.toFixed(8),
      timeInForce: params.timeInForce ?? 'GTC',
      newClientOrderId: params.clientOrderId
    };

    const response = await this.client.post('/api/v3/order', payload);
    return this.normalizeOrder(response);
  }

  private normalizeOrder(raw: any): NormalizedOrder {
    return {
      id: raw.orderId.toString(),
      clientOrderId: raw.clientOrderId,
      symbol: this.toInternalSymbol(raw.symbol),  // "BTCUSDT" → "BTC-USDT"
      side: raw.side.toLowerCase() as 'buy' | 'sell',
      type: raw.type.toLowerCase() as NormalizedOrder['type'],
      status: this.mapStatus(raw.status),
      size: new Decimal(raw.origQty),
      filledSize: new Decimal(raw.executedQty),
      price: raw.price !== '0.00000000' ? new Decimal(raw.price) : null,
      avgFillPrice: raw.avgPrice !== '0.00000000' ? new Decimal(raw.avgPrice) : null,
      fee: new Decimal('0'), // Binance não retorna fee neste endpoint
      feeCurrency: 'BNB',
      createdAt: new Date(raw.transactTime),
      updatedAt: new Date(raw.updateTime ?? raw.transactTime)
    };
  }

  private mapStatus(binanceStatus: string): NormalizedOrder['status'] {
    const map: Record<string, NormalizedOrder['status']> = {
      'NEW': 'open',
      'PARTIALLY_FILLED': 'partially_filled',
      'FILLED': 'filled',
      'CANCELED': 'cancelled',
      'REJECTED': 'rejected',
      'EXPIRED': 'cancelled'
    };
    return map[binanceStatus] ?? 'pending';
  }

  private toInternalSymbol(binanceSymbol: string): string {
    // Heurística para converter BTCUSDT → BTC-USDT
    const quotes = ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB'];
    for (const quote of quotes) {
      if (binanceSymbol.endsWith(quote)) {
        return `${binanceSymbol.slice(0, -quote.length)}-${quote}`;
      }
    }
    return binanceSymbol;
  }
}
```

---

## 5. ExchangeRegistry

```typescript
// src/exchanges/exchange-registry.ts

import { ExchangeAdapter } from './exchange-adapter.interface';
import { KuCoinAdapter } from './kucoin/kucoin.adapter';
import { BinanceAdapter } from './binance/binance.adapter';

export class ExchangeRegistry {
  private adapters = new Map<string, ExchangeAdapter>();

  register(adapter: ExchangeAdapter): void {
    this.adapters.set(adapter.exchangeId, adapter);
  }

  get(exchangeId: string): ExchangeAdapter {
    const adapter = this.adapters.get(exchangeId);
    if (!adapter) throw new Error(`Exchange não suportada: ${exchangeId}`);
    return adapter;
  }

  getAll(): ExchangeAdapter[] {
    return Array.from(this.adapters.values());
  }

  getSupportedIds(): string[] {
    return Array.from(this.adapters.keys());
  }
}

// Bootstrap
export function buildRegistry(): ExchangeRegistry {
  const registry = new ExchangeRegistry();
  registry.register(new KuCoinAdapter(/* ... */));
  // registry.register(new BinanceAdapter(/* ... */)); // Habilitar quando pronto
  return registry;
}
```

---

## 6. Rate Limiting por Exchange

```typescript
// src/exchanges/rate-limiter.ts

/**
 * Limites por exchange (requests por segundo)
 * KuCoin: 180 req/min para endpoints públicos, 50 req/10s para private
 * Binance: 1200 req/min para ordem, 10 ordens/seg
 */
const EXCHANGE_LIMITS: Record<string, { requestsPerSec: number; ordersPerSec: number }> = {
  kucoin:  { requestsPerSec: 20, ordersPerSec: 10 },
  binance: { requestsPerSec: 20, ordersPerSec: 10 },
  okx:     { requestsPerSec: 20, ordersPerSec: 10 }
};

export class ExchangeRateLimiter {
  private buckets = new Map<string, TokenBucket>();

  async throttle(exchangeId: string, endpoint: 'public' | 'private' | 'order'): Promise<void> {
    const key = `${exchangeId}:${endpoint}`;
    if (!this.buckets.has(key)) {
      const limits = EXCHANGE_LIMITS[exchangeId] ?? { requestsPerSec: 10, ordersPerSec: 5 };
      const rate = endpoint === 'order' ? limits.ordersPerSec : limits.requestsPerSec;
      this.buckets.set(key, new TokenBucket(rate, rate));
    }

    await this.buckets.get(key)!.acquire();
  }
}

class TokenBucket {
  private tokens: number;
  private lastRefill: number;

  constructor(private capacity: number, private refillRatePerSec: number) {
    this.tokens = capacity;
    this.lastRefill = Date.now();
  }

  async acquire(): Promise<void> {
    this.refill();
    if (this.tokens >= 1) {
      this.tokens--;
      return;
    }
    // Esperar pelo próximo token
    const waitMs = (1 / this.refillRatePerSec) * 1000;
    await new Promise(r => setTimeout(r, waitMs));
    return this.acquire();
  }

  private refill(): void {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;
    const newTokens = elapsed * this.refillRatePerSec;
    this.tokens = Math.min(this.capacity, this.tokens + newTokens);
    this.lastRefill = now;
  }
}
```

---

## 7. Checklist de Implementação

- [ ] Interface `ExchangeAdapter` implementada com todos os métodos definidos
- [ ] `KuCoinAdapter` completo (já funcional, apenas refatorar para interface)
- [ ] `BinanceAdapter` skeleton criado com normalização de símbolos
- [ ] `ExchangeRegistry` singleton injetado via DI
- [ ] Rate limiting independente por `exchangeId` + tipo de endpoint
- [ ] Símbolo interno sempre em formato "BASE-QUOTE" (ex: "BTC-USDT")
- [ ] Testes de normalização para KuCoin e Binance com mocks
- [ ] Adapters testáveis sem conexão com exchange (injeção de cliente HTTP mockável)
- [ ] Documentação de como adicionar nova exchange (max 40h de trabalho)
- [ ] Circuit breaker por exchange (não contaminar outras exchanges)

---

## 8. Critérios de Validação Final

| Critério | Aprovação |
|---|---|
| Order Model normalizado identico entre KuCoin/Binance | 100% dos campos mapeados |
| Adicionar nova exchange | < 200 linhas de código novo |
| Rate limits não excedidos em produção | 0 HTTP 429 em 30 dias |
| Circuit breaker isolado por exchange | Falha Binance não afeta KuCoin |
| Testes de adapter | 100% cobertura de normalização |
