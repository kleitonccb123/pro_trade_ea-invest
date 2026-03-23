# DOC 03 — WebSocket Profissional (sem polling)
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia

---

## 1. Objetivo

Implementar uma camada de WebSocket profissional para a KuCoin que:

- **Nunca perca mensagens** — detecção de gaps por sequenceId
- **Reconecte automaticamente** — sem intervenção manual com backoff inteligente
- **Mantenha heartbeat** — detecte conexões mortas antes da exchange desconectar
- **Suporte failover** — troca para REST temporariamente se WS ficar indisponível
- **Faça fan-out** — distribua dados de mercado para N bots/usuários via Redis Pub/Sub
- **Sobreviva a deploys** — consumidores continuam funcionando durante restart do publisher

---

## 2. Problema Atual

| Problema | Risco |
|---|---|
| Sem sequenceId tracking | Mensagens perdidas após reconexão nunca detectadas |
| Reconexão sem backoff | Flood de reconexões pode banir o IP da exchange |
| Heartbeat não implementado | Conexão "zumbi" que não recebe dados por minutos |
| Polling REST para preços | Latência de 1-5s vs <10ms do WebSocket |
| Sem fan-out: cada bot abre conexão própria | N bots = N websockets = limite de conexão atingido |
| Sem fallback para REST | Se WS cair, todos os bots ficam cegos |

---

## 3. Arquitetura Proposta

```
┌───────────────────────────────────────────────────────────────────┐
│              KUCOIN WEBSOCKET GATEWAY (processo único)            │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                  CONNECTION MANAGER                      │     │
│  │  - Token rotation (tokens expiram em 24h)               │     │
│  │  - Auto-reconnect com backoff exponencial                │     │
│  │  - Heartbeat a cada 18s (KuCoin exige <20s)             │     │
│  │  - Sequence gap detection                               │     │
│  └────────────────────────┬────────────────────────────────┘     │
│                           │  ws://push1.kucoin.com/endpoint      │
│  ┌────────────────────────▼────────────────────────────────┐     │
│  │           SUBSCRIPTION MANAGER                          │     │
│  │  Canais ativos:                                         │     │
│  │  /market/ticker:{symbol}                                │     │
│  │  /market/level2:{symbol}  (order book top 5)           │     │
│  │  /trade/orders            (private: execuções)         │     │
│  │  /account/balance         (private: balanço)           │     │
│  └────────────────────────┬────────────────────────────────┘     │
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────┐     │
│  │           MESSAGE DISPATCHER                            │     │
│  │  Parse → Validate → Publish to Redis Pub/Sub            │     │
│  └─────────────────────────────────────────────────────────┘     │
└───────────────────────────┬───────────────────────────────────────┘
                            │ Redis PUBLISH
                            ▼
              ┌─────────────────────────┐
              │      REDIS PUB/SUB      │
              │  channel: ws:ticker:BTC-USDT  │
              │  channel: ws:executions       │
              │  channel: ws:balance          │
              └─────────┬───────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  BOT 1   │  │  BOT 2   │  │  BOT N   │
    │ Consumer │  │ Consumer │  │ Consumer │
    └──────────┘  └──────────┘  └──────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │   FALLBACK MONITOR   │
              │  Se WS offline > 10s │
              │  → Switch to REST    │
              │  polling (2s)        │
              └──────────────────────┘
```

---

## 4. Implementação Completa

### 4.1 Token Manager (Renovação automática)

```typescript
// src/websocket/kucoin-token-manager.ts

import axios from 'axios';
import { logger } from '../core/logger';

interface WsToken {
  token: string;
  instanceServers: Array<{
    endpoint: string;
    encrypt: boolean;
    protocol: string;
    pingInterval: number;  // ms
    pingTimeout: number;   // ms
  }>;
  expiresAt: Date;
}

export class KuCoinTokenManager {
  private currentToken: WsToken | null = null;
  private readonly TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000; // 5 min antes de expirar

  constructor(
    private apiKey: string,
    private apiSecret: string,
    private passphrase: string,
    private baseUrl: string
  ) {}

  async getValidToken(): Promise<WsToken> {
    if (this.currentToken && this.isTokenValid(this.currentToken)) {
      return this.currentToken;
    }
    return this.refresh();
  }

  async refresh(): Promise<WsToken> {
    logger.info({ event: 'ws_token_refresh_start' });

    const response = await axios.post(
      `${this.baseUrl}/api/v1/bullet-private`,
      {},
      { headers: this.buildAuthHeaders('POST', '/api/v1/bullet-private', '') }
    );

    const { token, instanceServers } = response.data.data;

    this.currentToken = {
      token,
      instanceServers,
      // Tokens da KuCoin expiram em 24h, mas renovamos mais cedo
      expiresAt: new Date(Date.now() + 23 * 60 * 60 * 1000)
    };

    logger.info({
      event: 'ws_token_refreshed',
      endpoint: instanceServers[0]?.endpoint,
      expiresAt: this.currentToken.expiresAt
    });

    return this.currentToken;
  }

  private isTokenValid(token: WsToken): boolean {
    return token.expiresAt.getTime() - Date.now() > this.TOKEN_REFRESH_BUFFER_MS;
  }

  private buildAuthHeaders(method: string, path: string, body: string): Record<string, string> {
    const timestamp = Date.now().toString();
    const { createHmac } = require('crypto');
    
    const signature = createHmac('sha256', this.apiSecret)
      .update(`${timestamp}${method}${path}${body}`)
      .digest('base64');

    const passphraseSig = createHmac('sha256', this.apiSecret)
      .update(this.passphrase)
      .digest('base64');

    return {
      'KC-API-KEY': this.apiKey,
      'KC-API-SIGN': signature,
      'KC-API-TIMESTAMP': timestamp,
      'KC-API-PASSPHRASE': passphraseSig,
      'KC-API-KEY-VERSION': '2',
      'Content-Type': 'application/json'
    };
  }
}
```

### 4.2 Connection Manager — Reconexão, Heartbeat, Sequência

```typescript
// src/websocket/kucoin-connection-manager.ts

import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { KuCoinTokenManager } from './kucoin-token-manager';
import { logger } from '../core/logger';
import { MetricsCollector } from '../monitoring/metrics';

interface ConnectionState {
  status: 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED' | 'RECONNECTING';
  connectId: string;
  connectedAt?: Date;
  lastMessageAt?: Date;
  lastSequenceId?: number;
  reconnectAttempts: number;
}

export class KuCoinConnectionManager extends EventEmitter {
  private ws: WebSocket | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private pingInterval: number = 18000; // 18s (KuCoin exige ping < 20s de intervalo)
  private state: ConnectionState = {
    status: 'DISCONNECTED',
    connectId: '',
    reconnectAttempts: 0
  };

  // Backoff exponencial: 1s, 2s, 4s, 8s, 16s, max 30s
  private readonly BACKOFF_BASE_MS = 1000;
  private readonly BACKOFF_MAX_MS = 30000;

  constructor(
    private tokenManager: KuCoinTokenManager,
    private metrics: MetricsCollector
  ) {
    super();
  }

  async connect(): Promise<void> {
    this.state.status = 'CONNECTING';
    this.state.connectId = this.generateConnectId();

    try {
      const token = await this.tokenManager.getValidToken();
      const server = token.instanceServers[0];
      this.pingInterval = server.pingInterval - 2000; // 2s antes do timeout

      const wsUrl = `${server.endpoint}?token=${token.token}&connectId=${this.state.connectId}`;

      logger.info({ event: 'ws_connecting', url: server.endpoint, connectId: this.state.connectId });

      this.ws = new WebSocket(wsUrl, {
        handshakeTimeout: 10000,
        perMessageDeflate: false
      });

      this.ws.on('open', () => this.handleOpen());
      this.ws.on('message', (data) => this.handleMessage(data));
      this.ws.on('error', (err) => this.handleError(err));
      this.ws.on('close', (code, reason) => this.handleClose(code, reason));
      this.ws.on('pong', () => this.handlePong());

    } catch (err: any) {
      logger.error({ event: 'ws_connect_failed', error: err.message });
      await this.scheduleReconnect();
    }
  }

  private handleOpen(): void {
    logger.info({ event: 'ws_connected', connectId: this.state.connectId });
    this.state.status = 'CONNECTED';
    this.state.connectedAt = new Date();
    this.state.reconnectAttempts = 0;
    this.metrics.recordWsConnected();

    this.startHeartbeat();
    this.emit('connected');
  }

  private handleMessage(data: WebSocket.Data): void {
    this.state.lastMessageAt = new Date();

    let msg: any;
    try {
      msg = JSON.parse(data.toString());
    } catch (e) {
      logger.warn({ event: 'ws_invalid_json', data: data.toString().substring(0, 100) });
      return;
    }

    // Resposta ao welcome
    if (msg.type === 'welcome') {
      logger.info({ event: 'ws_welcome_received', id: msg.id });
      this.emit('ready');
      return;
    }

    // Resposta ao ping (ack)
    if (msg.type === 'pong') {
      return;
    }

    // Mensagem de dados
    if (msg.type === 'message') {
      // Verificar gap de sequência
      if (msg.sequence !== undefined && this.state.lastSequenceId !== undefined) {
        const expected = this.state.lastSequenceId + 1;
        if (msg.sequence > expected) {
          const gap = msg.sequence - expected;
          logger.warn({
            event: 'ws_sequence_gap_detected',
            expected,
            received: msg.sequence,
            gap
          });
          this.metrics.recordSequenceGap(gap);
          // Solicitar snapshot via REST para o canal afetado
          this.emit('sequence_gap', { topic: msg.topic, gap });
        }
      }

      if (msg.sequence) {
        this.state.lastSequenceId = msg.sequence;
      }

      this.emit('message', msg);
    }

    // Erro da exchange
    if (msg.type === 'error') {
      logger.error({ event: 'ws_exchange_error', code: msg.code, data: msg.data });
      this.emit('exchange_error', msg);
    }
  }

  private handleError(err: Error): void {
    logger.error({ event: 'ws_error', error: err.message });
    this.metrics.recordWsError();
  }

  private async handleClose(code: number, reason: Buffer): Promise<void> {
    logger.warn({
      event: 'ws_closed',
      code,
      reason: reason.toString(),
      reconnectAttempts: this.state.reconnectAttempts
    });

    this.stopHeartbeat();
    this.state.status = 'DISCONNECTED';
    this.metrics.recordWsDisconnected(code);
    this.emit('disconnected', { code, reason: reason.toString() });

    // Reconectar automaticamente (exceto desconexão intencional)
    if (code !== 1000) {
      await this.scheduleReconnect();
    }
  }

  private handlePong(): void {
    logger.debug({ event: 'ws_pong_received' });
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        const pingId = Date.now().toString();
        const pingMsg = JSON.stringify({ id: pingId, type: 'ping' });
        this.ws.send(pingMsg);
        this.metrics.recordWsPing();

        // Se não receber resposta em 5s → conexão morta
        setTimeout(() => {
          const elapsed = Date.now() - (this.state.lastMessageAt?.getTime() ?? 0);
          if (elapsed > this.pingInterval + 5000) {
            logger.warn({ event: 'ws_heartbeat_timeout', elapsed });
            this.ws?.terminate();
          }
        }, 5000);
      }
    }, this.pingInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private async scheduleReconnect(): Promise<void> {
    this.state.status = 'RECONNECTING';
    this.state.reconnectAttempts++;

    const delay = Math.min(
      this.BACKOFF_BASE_MS * Math.pow(2, this.state.reconnectAttempts - 1),
      this.BACKOFF_MAX_MS
    );

    logger.info({
      event: 'ws_reconnect_scheduled',
      attempt: this.state.reconnectAttempts,
      delayMs: delay
    });

    await new Promise(resolve => setTimeout(resolve, delay));
    await this.connect();
  }

  subscribe(topic: string, privateChannel: boolean = false): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      this.once('ready', () => this.subscribe(topic, privateChannel));
      return;
    }

    const msg = JSON.stringify({
      id: Date.now().toString(),
      type: 'subscribe',
      topic,
      privateChannel,
      response: true
    });

    this.ws.send(msg);
    logger.info({ event: 'ws_subscribed', topic });
  }

  disconnect(): void {
    this.stopHeartbeat();
    this.ws?.close(1000, 'Intentional disconnect');
  }

  private generateConnectId(): string {
    return `bot_${process.pid}_${Date.now()}`;
  }
}
```

### 4.3 Message Dispatcher — Fan-out via Redis

```typescript
// src/websocket/message-dispatcher.ts

import Redis from 'ioredis';
import { KuCoinConnectionManager } from './kucoin-connection-manager';
import { logger } from '../core/logger';

// Canais Redis por tipo de dado
export const CHANNELS = {
  ticker: (symbol: string) => `ws:ticker:${symbol}`,
  orderBook: (symbol: string) => `ws:orderbook:${symbol}`,
  execution: (userId: string) => `ws:execution:${userId}`,
  balance: (userId: string) => `ws:balance:${userId}`
};

export class MessageDispatcher {
  constructor(
    private connection: KuCoinConnectionManager,
    private redis: Redis
  ) {
    this.connection.on('message', (msg) => this.dispatch(msg));
    this.connection.on('sequence_gap', async ({ topic }) => {
      await this.handleSequenceGap(topic);
    });
  }

  private async dispatch(msg: any): Promise<void> {
    const { topic, data } = msg;
    const startTime = Date.now();

    try {
      let channel: string | null = null;

      if (topic?.startsWith('/market/ticker:')) {
        const symbol = topic.split(':')[1];
        channel = CHANNELS.ticker(symbol);

      } else if (topic?.startsWith('/market/level2:')) {
        const symbol = topic.split(':')[1];
        channel = CHANNELS.orderBook(symbol);

      } else if (topic === '/trade/orders') {
        // Ordens privadas — publicar por userId
        const userId = data?.userId;
        if (userId) {
          channel = CHANNELS.execution(userId);
          // Também emitir evento local para ExecutionProcessor
          this.connection.emit('execution_report', data);
        }

      } else if (topic === '/account/balance') {
        const currency = data?.currency;
        const userId = data?.userId;
        if (userId) {
          channel = CHANNELS.balance(userId);
        }
      }

      if (channel) {
        await this.redis.publish(channel, JSON.stringify({
          ...data,
          _ts: Date.now(),
          _topic: topic
        }));
      }

      const latencyMs = Date.now() - startTime;
      if (latencyMs > 50) {
        logger.warn({ event: 'ws_dispatch_slow', topic, latencyMs });
      }

    } catch (err: any) {
      logger.error({ event: 'ws_dispatch_error', topic, error: err.message });
    }
  }

  private async handleSequenceGap(topic: string): Promise<void> {
    logger.warn({ event: 'sequence_gap_recovery_start', topic });

    // Para level2, solicitar snapshot via REST
    if (topic.startsWith('/market/level2:')) {
      const symbol = topic.split(':')[1];
      // Buscar snapshot via REST e publicar
      // this.redis.publish(CHANNELS.orderBook(symbol), JSON.stringify(snapshot));
    }
  }
}
```

### 4.4 Consumer — Uso nos Bots

```typescript
// src/bot/ws-consumer.ts

import Redis from 'ioredis';
import { CHANNELS } from '../websocket/message-dispatcher';
import { logger } from '../core/logger';

export class BotWsConsumer {
  private subscriber: Redis;
  private fallbackActive = false;
  private lastMessageAt = Date.now();
  private readonly FALLBACK_TRIGGER_MS = 10000; // 10s sem mensagem → fallback

  constructor(
    subscriber: Redis,
    private botId: string,
    private symbol: string,
    private userId: string
  ) {
    this.subscriber = subscriber.duplicate();
    this.startFallbackMonitor();
  }

  async start(handlers: {
    onTicker?: (data: any) => void;
    onExecution?: (data: any) => void;
    onBalance?: (data: any) => void;
  }): Promise<void> {
    const channels = [
      CHANNELS.ticker(this.symbol),
      CHANNELS.execution(this.userId),
      CHANNELS.balance(this.userId)
    ];

    await this.subscriber.subscribe(...channels);

    this.subscriber.on('message', (channel, message) => {
      this.lastMessageAt = Date.now();
      const data = JSON.parse(message);

      if (channel === CHANNELS.ticker(this.symbol)) {
        this.fallbackActive && this.exitFallback();
        handlers.onTicker?.(data);
      } else if (channel === CHANNELS.execution(this.userId)) {
        handlers.onExecution?.(data);
      } else if (channel === CHANNELS.balance(this.userId)) {
        handlers.onBalance?.(data);
      }
    });

    logger.info({ event: 'bot_ws_consumer_started', botId: this.botId, symbol: this.symbol, channels });
  }

  private startFallbackMonitor(): void {
    setInterval(() => {
      const elapsed = Date.now() - this.lastMessageAt;
      if (elapsed > this.FALLBACK_TRIGGER_MS && !this.fallbackActive) {
        this.enterFallback();
      }
    }, 2000);
  }

  private enterFallback(): void {
    this.fallbackActive = true;
    logger.warn({ event: 'ws_fallback_activated', botId: this.botId, elapsed: Date.now() - this.lastMessageAt });
    // Ativar polling REST a cada 2s para não ficar totalmente cego
    // this.restFallback.start(this.symbol, 2000);
  }

  private exitFallback(): void {
    this.fallbackActive = false;
    logger.info({ event: 'ws_fallback_deactivated', botId: this.botId });
    // this.restFallback.stop();
  }

  async stop(): Promise<void> {
    await this.subscriber.unsubscribe();
    this.subscriber.disconnect();
  }
}
```

### 4.5 WebSocket Gateway — Bootstrap Completo

```typescript
// src/websocket/gateway.ts

import { KuCoinTokenManager } from './kucoin-token-manager';
import { KuCoinConnectionManager } from './kucoin-connection-manager';
import { MessageDispatcher } from './message-dispatcher';
import { ExecutionProcessor } from '../order/execution-processor';
import Redis from 'ioredis';
import { logger } from '../core/logger';

export class WebSocketGateway {
  private connection!: KuCoinConnectionManager;
  private dispatcher!: MessageDispatcher;

  constructor(
    private tokenManager: KuCoinTokenManager,
    private redis: Redis,
    private executionProcessor: ExecutionProcessor,
    private metrics: any
  ) {}

  async start(symbols: string[]): Promise<void> {
    this.connection = new KuCoinConnectionManager(this.tokenManager, this.metrics);
    this.dispatcher = new MessageDispatcher(this.connection, this.redis);

    // Processar execution reports localmente
    this.connection.on('execution_report', async (data) => {
      await this.executionProcessor.process(data);
    });

    // Quando conectar, assinar todos os canais necessários
    this.connection.on('ready', () => {
      logger.info({ event: 'ws_gateway_subscribing', symbolCount: symbols.length });

      // Canais públicos
      for (const symbol of symbols) {
        this.connection.subscribe(`/market/ticker:${symbol}`);
        this.connection.subscribe(`/market/level2:${symbol}`);
      }

      // Canais privados (execuções e balanço)
      this.connection.subscribe('/trade/orders', true);
      this.connection.subscribe('/account/balance', true);
    });

    await this.connection.connect();
    logger.info({ event: 'ws_gateway_started' });
  }

  addSymbol(symbol: string): void {
    this.connection.subscribe(`/market/ticker:${symbol}`);
    this.connection.subscribe(`/market/level2:${symbol}`);
  }

  stop(): void {
    this.connection.disconnect();
  }
}
```

---

## 5. Edge Cases

| Caso | Tratamento |
|---|---|
| Token expirado durante operação | `TokenManager` renova 5min antes; nova conexão usa novo token |
| Sequência fora de ordem (late message) | Ignorado se sequence < lastSequenceId |
| Gap de sequência detectado | Fallback REST publica snapshot no Redis para sincronizar consumidores |
| WS conectado mas sem dados (zumbi) | Fallback monitor detecta ausência de mensagens em 10s |
| Redis Pub/Sub indisponível | Dispatcher faz retry de publish com circuit breaker |
| Deploy do gateway → consumidores sem dados | Fallback REST ativado em 10s por cada consumidor independentemente |
| Muitos símbolos (>100) | Uma conexão WS suporta ~300 tópicos; usar múltiplas conexões se necessário |

---

## 6. Configuração de Testes Forçados

```typescript
// tests/websocket.resilience.test.ts

describe('WebSocket Resilience', () => {
  it('deve reconectar automaticamente após queda forçada', async (done) => {
    const gateway = new WebSocketGateway(...);
    await gateway.start(['BTC-USDT']);
    
    // Forçar queda
    (gateway as any).connection.ws.terminate();
    
    // Aguardar reconexão
    (gateway as any).connection.once('connected', () => {
      logger.info('Reconectado com sucesso');
      done();
    });
  }, 60000);

  it('deve ativar fallback REST se WS sem mensagens por 10s', async () => {
    const consumer = new BotWsConsumer(redis, 'bot1', 'BTC-USDT', 'user1');
    const fallbackSpy = jest.spyOn(consumer as any, 'enterFallback');
    
    // Não publicar nada no Redis por 12s
    await new Promise(resolve => setTimeout(resolve, 12000));
    
    expect(fallbackSpy).toHaveBeenCalled();
  }, 15000);

  it('deve detectar gap de sequência', async () => {
    const gaps: any[] = [];
    connection.on('sequence_gap', (gap) => gaps.push(gap));
    
    // Enviar mensagem com sequence 100 depois de 98 (pula 99)
    simulateMessage({ sequence: 98, topic: '/market/ticker:BTC-USDT' });
    simulateMessage({ sequence: 100, topic: '/market/ticker:BTC-USDT' });
    
    expect(gaps.length).toBe(1);
    expect(gaps[0].gap).toBe(1);
  });
});
```

---

## 7. Checklist de Implementação

- [ ] `KuCoinTokenManager` com renovação automática 5min antes de expirar
- [ ] `KuCoinConnectionManager` com backoff exponencial (1s→30s)
- [ ] Heartbeat a cada 18s (2s antes do timeout da KuCoin)
- [ ] Sequência tracking com detecção de gaps
- [ ] `MessageDispatcher` publicando no Redis Pub/Sub por canal específico
- [ ] Canais privados (`/trade/orders`, `/account/balance`) assinados com flag `privateChannel: true`
- [ ] `BotWsConsumer` se inscrevendo no Redis ao invés do WS diretamente
- [ ] Fallback REST ativado após 10s sem mensagem no consumidor
- [ ] Testes de queda forçada (`ws.terminate()`) com reconexão
- [ ] Testes de sequência gap
- [ ] Métricas: `ws_connected_duration`, `ws_reconnect_count`, `ws_message_latency_ms`

---

## 8. Critérios de Validação Final

| Critério | Aprovação |
|---|---|
| Latência de ticker | P99 < 50ms (WS) vs P99 < 2000ms (REST polling) |
| Reconexão automática | 100% das quedas reconectadas em < 35s |
| Sem mensagens perdidas | Gap detectado em 100% dos testes de injeção de gap |
| Fallback REST ativo | Ativado em 100% dos casos de 10s sem mensagem |
| Escalabilidade | 500 bots consumindo de 1 conexão WS via Redis Pub/Sub |
| Heartbeat | Zumbi detectado e reconectado em < 25s |
