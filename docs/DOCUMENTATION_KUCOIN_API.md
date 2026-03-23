# KuCoin API Integration

Documento técnico sobre como o Crypto Trade Hub se integra à API REST da KuCoin,
quais endpoints são chamados, o que é extraído, normalizado, e o estado atual de cada
componente crítico após as correções implementadas.

> **Implementação:** sem SDKs de terceiros (CCXT); comunicação direta via HTTP.
> Todo o código vive em `backend/app/exchanges/kucoin/`.

---

## 1. Autenticação

Toda requisição privada exige assinatura **HMAC-SHA256**.

| Header | Conteúdo |
|---|---|
| `KC-API-KEY` | Chave de API do usuário |
| `KC-API-SIGN` | HMAC-SHA256 sobre `timestamp + method + path + body` |
| `KC-API-TIMESTAMP` | Unix ms |
| `KC-API-PASSPHRASE` | Passphrase criptografada com o secret |

Implementado em `KuCoinRawClient._get_auth_headers` / `_generate_signature`.

Variáveis de ambiente (`.env.production.example`):

```text
KUCOIN_API_KEY=
KUCOIN_API_SECRET=
KUCOIN_API_PASSPHRASE=
KUCOIN_SANDBOX=true
```

---

## 2. Rate Limiting — Corrigido

### Antes (incorreto)

```python
# Limites estáticos fixos por endpoint — não segue o modelo real da KuCoin
self.limits = {
    "GET /api/v1/accounts": 10,
    "POST /api/v1/orders": 100,
}
```

### Depois — `KuCoinRateLimitManager`

A KuCoin usa **Resource Pool com janela de 30 segundos** e devolve o estado
real em cada resposta HTTP:

| Header de resposta | Significado |
|---|---|
| `gw-ratelimit-limit` | Quota total da janela |
| `gw-ratelimit-remaining` | Requisições restantes |
| `gw-ratelimit-reset` | Milissegundos até reset |

```python
class KuCoinRateLimitManager:
    def update_from_headers(self, headers: dict) -> None:
        self.limit     = int(headers.get("gw-ratelimit-limit",     self.limit))
        self.remaining = int(headers.get("gw-ratelimit-remaining", self.remaining))
        self.reset_ms  = int(headers.get("gw-ratelimit-reset",     self.reset_ms))

    async def wait_if_needed(self) -> None:
        if self.remaining <= 0:
            wait_s = max(self.reset_ms / 1000, 0.5)
            await asyncio.sleep(wait_s)
            self.remaining = self.limit   # reset pessimista
```

O método `_make_request` chama `update_from_headers()` após **cada** resposta,
mantendo o manager sempre sincronizado com a KuCoin.

**Arquivo:** `backend/app/exchanges/kucoin/client.py` — classe `KuCoinRateLimitManager`

---

## 3. Endpoints Utilizados

### Conta

| Método Python | Endpoint KuCoin | Dados extraídos |
|---|---|---|
| `get_accounts()` | `GET /api/v1/accounts` | id, currency, type |
| `get_account(id)` | `GET /api/v1/accounts/{id}` | objeto completo |
| `get_account_balance` | `GET /api/v1/accounts/{id}/balances` | available, holds, total |

### Ordens (Spot)

| Método Python | Endpoint KuCoin | Notas |
|---|---|---|
| `place_market_order` | `POST /api/v1/orders` | type=market |
| `place_limit_order` | `POST /api/v1/orders` | type=limit, GTC |
| `cancel_order` | `DELETE /api/v1/orders/{id}` | |
| `get_order` | `GET /api/v1/orders/{id}` | Apenas em fallback |
| `get_order_by_client_oid` | `GET /api/v1/order/client-order/{oid}` | Verificação de idempotência |
| `get_orders` | `GET /api/v1/orders` | |

### TP/SL — Implementado

| Método Python | Endpoint KuCoin | Tipo |
|---|---|---|
| `place_oco_order` | `POST /api/v3/oco/order` | Spot — OCO (TP + SL simultâneos) |
| `place_futures_order_with_sl_tp` | `POST /api/v1/orders` (Futures host) | Futures — `stop`, `stopPrice`, `reduceOnly` |

**OCO Spot** coloca TP via limite e SL via stop-limit que se cancelam mutuamente.

**Futures** usa campos nativos:

```json
{
  "stop": "down",
  "stopPrice": "45000",
  "reduceOnly": true
}
```

### Market Data

| Método Python | Endpoint KuCoin | Formato |
|---|---|---|
| `get_ticker(symbol)` | `GET /api/v1/market/orderbook/level1` | bid/ask/last/high/low/volume |
| `get_klines` | `GET /api/v1/market/candles` | array 6 strings: ts, o, c, h, l, v |
| `get_trades` | `GET /api/v1/market/histories` | trades recentes |

> Market data em tempo real agora passa pelo **WebSocketManager** (sem polling REST).

---

## 4. Idempotência — Implementado

### Problema anterior

O `clientOid` era gerado internamente mas **não era persistido no banco antes do envio**.
Um retry após falha de rede criava ordem duplicada.

### Solução implementada

**1.** `OrderService.create_order()` persiste `status=PENDING` no banco **antes**
de qualquer request à KuCoin.

**2.** O `clientOid` é passado ao `OrderManager` via `pre_persisted_client_oid`.

**3.** O novo endpoint `get_order_by_client_oid` verifica na KuCoin se a ordem já
chegou antes de um retry:

```python
# Antes de enviar:
client_oid = str(uuid.uuid4())
await db.orders.insert({"client_oid": client_oid, "status": "PENDING", ...})

# Retry seguro — sem criar ordem duplicada:
existing = await kucoin_client.get_order_by_client_oid(client_oid)
if existing:
    return existing
```

**Arquivo:** `backend/app/exchanges/kucoin/client.py` — `get_order_by_client_oid`

---

## 5. WebSocket Manager — Implementado (arquivo novo)

**Arquivo:** `backend/app/exchanges/kucoin/websocket_manager.py`

Substitui o polling REST por canais WebSocket em tempo real.

### Canais suportados

| Canal KuCoin | Dados | Uso |
|---|---|---|
| `/market/ticker:{symbol}` | Preco, bid/ask em tempo real | Bots, dashboard |
| `/market/candles:{symbol}_{interval}` | OHLCV em tempo real | Graficos |
| `/spotMarket/tradeOrders` | Execucoes privadas (auth) | Atualizar status de ordens |

### Arquitetura

```
KuCoin WebSocket
      |
KuCoinWebSocketManager
      |
Event Dispatcher (callbacks assincronos)
      |
TradingEngine / Frontend (SSE / Redis pub-sub)
```

### Funcionalidades

- Snapshot inicial via REST; incrementais via WebSocket
- Reconexao automatica com backoff exponencial (ate 10 tentativas)
- Heartbeat/Ping a cada 20 s (KuCoin exige menos de 30 s)
- Suporte a multiplos simbolos simultaneos
- Callback para execution reports (elimina 2o request REST por ordem)

### Inicializacao

```python
# startup da aplicacao
ws_manager = init_ws_manager(
    api_key=settings.KUCOIN_API_KEY,
    api_secret=settings.KUCOIN_API_SECRET,
    passphrase=settings.KUCOIN_PASSPHRASE,
)
ws_manager.on_ticker("BTC-USDT", on_btc_price)
ws_manager.on_order_execution(order_manager.on_ws_execution)
await ws_manager.start()
```

---

## 6. OrderManager — Reforcado

**Arquivo:** `backend/app/trading/order_manager.py`

### Melhorias implementadas

| Funcionalidade | Status |
|---|---|
| Fila interna com deduplication | Ja existia |
| Retry com backoff exponencial | Ja existia |
| clientOid como idempotencia REST | Ja existia |
| Lock por simbolo (race condition) | NOVO |
| Callback WS execution report | NOVO |
| `pre_persisted_client_oid` | NOVO |

### Lock por simbolo

Evita que dois sinais simultaneos sobre o mesmo simbolo gerem ordens duplicadas:

```python
sym_lock = await self._get_symbol_lock(symbol)
async with sym_lock:
    # apenas 1 ordem por simbolo executa por vez
    result = await self._execute_market_order(...)
```

### Eliminacao do 2o request REST

O `OrderManager` aceita updates via WebSocket pelo metodo `on_ws_execution(event)`:

```python
# registrar no startup
ws_manager.on_order_execution(order_manager.on_ws_execution)
# a partir dai: nenhum GET /orders/{id} necessario apos POST
```

---

## 7. RiskManager — Reforcado

**Arquivo:** `backend/app/trading/risk_manager.py`

### Parametros de `RiskConfig`

| Parametro | Default | Descricao |
|---|---|---|
| `max_leverage` | 10x | Alavancagem maxima |
| `max_position_size` | $100.000 | Valor maximo por posicao |
| `max_loss_per_trade` | $1.000 | Perda maxima com SL |
| `max_daily_loss` | $5.000 | Perda diaria maxima |
| `max_drawdown_pct` | 20% | Drawdown sobre pico de balanco |
| `max_open_positions` | 10 | Posicoes simultaneas (global) |
| `max_position_per_symbol` | 1 | Posicoes por simbolo |
| `cooldown_after_loss_s` | 60 s | Pausa automatica apos loss |
| `kill_switch_on_daily_loss` | True | Para bots ao atingir limite diario |

### Funcionalidades novas

**Cooldown pos-loss:**

```python
risk_manager.register_loss(user_id)      # ativa cooldown de 60s
risk_manager.is_in_cooldown(user_id)     # True enquanto no periodo
```

**Drawdown:**

```python
risk_manager.update_peak_balance(user_id, balance)
ok, err = risk_manager.check_drawdown(user_id, current_balance)
```

**Kill-switch:**

```python
risk_manager.activate_kill_switch(user_id)    # para todas as operacoes
risk_manager.deactivate_kill_switch(user_id)  # reativa (acao manual admin)
```

**Posicoes por simbolo:**

```python
risk_manager.register_open_position(user_id, "BTC-USDT")
risk_manager.close_position(user_id, "BTC-USDT")
# validate_order() bloqueia se max_position_per_symbol for atingido
```

---

## 8. Camada de Normalizacao

O JSON bruto da KuCoin usa numeros como strings e timestamps em ms.
O `normalizer.py` converte para tipos Python seguros:

| Raw KuCoin | Tipo normalizado | Modelo |
|---|---|---|
| `"available"`, `"holds"`, `"balance"` | `Decimal` | `NormalizedBalance` |
| `"price"`, `"size"`, `"dealSize"`, `"fee"` | `Decimal` | `NormalizedOrder` |
| `"createdAt"` (ms int) | `datetime` UTC | Todos |
| Array `[ts, o, c, h, l, v]` | `NormalizedCandle` | Candles |
| `"isActive"`, `"cancelExist"` | `OrderStatus` enum | Ordens |

---

## 9. Performance — Corrigido

### Antes

```
POST /api/v1/orders        → 1o request REST
GET  /api/v1/orders/{id}   → 2o request REST (polling para status)
```

Dobrava o consumo de rate limit e aumentava latencia.

### Depois

```
POST /api/v1/orders        → 1 unico request REST
Execution Report (WS)      → atualizacao instantanea via canal privado
```

Configuracao no startup:

```python
ws_manager.on_order_execution(order_manager.on_ws_execution)
```

---

## 10. Dados Extraidos e Uso no Sistema

| Dado | Origem KuCoin | Uso |
|---|---|---|
| Saldos | `/api/v1/accounts` | Dashboard, calculo de fundos |
| Status de ordens | WS `/spotMarket/tradeOrders` | PnL, rastreamento, creditos |
| Preco atual | WS `/market/ticker` | Bots, validacao de entrada |
| Candles OHLCV | WS `/market/candles` | Graficos, analise |
| Historico trades | `/api/v1/market/histories` | Analytics |

---

## 11. Avaliacao Tecnica Atualizada

| Dimensao | Antes | Depois |
|---|---|---|
| Rate Limiting | Estatico/incorreto | Header-based, pool real |
| Idempotencia | clientOid sem persist | Persist PENDING antes |
| TP/SL | Nao implementado | OCO Spot + Futures nativo |
| WebSocket | Ausente (polling REST) | Ticker, Candles, Orders |
| Race condition | Strategy direto ao Engine | Lock por simbolo |
| Risk Manager | Basico | Drawdown, cooldown, kill-switch |
| Performance | 2 requests por ordem | 1 REST + WS execution report |
| Beta privada | Pronto | Pronto |
| Producao com capital real | Nao | Sim (apos testes de integracao) |

---

## 12. Arquivos Modificados / Criados

| Arquivo | O que mudou |
|---|---|
| `backend/app/exchanges/kucoin/client.py` | `KuCoinRateLimitManager`, `place_oco_order`, `place_futures_order_with_sl_tp`, `get_order_by_client_oid`, `rate_limit_status` |
| `backend/app/exchanges/kucoin/websocket_manager.py` | **Arquivo novo** — WebSocket completo |
| `backend/app/trading/risk_manager.py` | `RiskConfig` estendido, cooldown, drawdown, kill-switch, posicoes por simbolo |
| `backend/app/trading/order_manager.py` | Lock por simbolo, `on_ws_execution`, `pre_persisted_client_oid` |

---

## 13. Proximos Passos (Pos-Beta)

| Item | Prioridade |
|---|---|
| Registrar `ws_manager.on_order_execution(order_manager.on_ws_execution)` no startup | Obrigatorio |
| Instalar pacote `websockets` (`pip install websockets`) | Obrigatorio |
| Testes de integracao do WebSocket com sandbox KuCoin | Obrigatorio |
| Sistema de lock distribuido Redis (multi-instancia) | Importante (escala) |
| Reconciliacao periodica de balanco (cron) | Importante (confiabilidade) |
| PositionManager persistido em banco | Importante (confiabilidade) |

---

## 14. Correcoes WebSocket - Sessao 2026-02-23

Sete pontos criticos foram corrigidos em `websocket_manager.py`.

### Fix 1 - Re-subscribe completo apos reconexao

**Problema:** Subscricoes adicionadas dinamicamente apos `start()` eram perdidas ao reconectar.

**Solucao:** `_active_topics: Dict[str, bool]` mantem registry permanente de todos os topicos
(False = publico, True = privado). `_subscribe_all()` reutiliza o registry inteiro em toda
reconexao, incluindo topicos dinamicos.

### Fix 2 - Snapshot REST inicial de candles

**Problema:** Sem snapshot, o grafico comecava vazio e exibia apenas velas novas.

**Solucao:** `_fetch_all_snapshots()` chamado em `_connect()` antes de qualquer subscribe WS.
Busca `GET /api/v1/market/candles` e dispara evento `candle_snapshot` com ate 200 velas
historicas ordenadas cronologicamente. `add_candle_subscription()` tambem busca snapshot
antes de subscrever.

### Fix 3 - Watchdog de conexao zumbi

**Problema:** Socket podia ficar preso sem receber mensagens (comum em cloud) sem ativar reconexao.

**Solucao:** `_last_message_ts` atualizado a cada mensagem no `_recv_loop`. Task paralela
`_watchdog_loop()` checa a cada 10 s: se `elapsed > 40 s`, fecha o socket e dispara reconexao.

### Fix 4 - Execution report completo

**Problema:** `_parse_order_execution` usava apenas `filledSize`, causando calculo incorreto
de execucoes parciais, fees e PnL.

**Solucao:** Campos adicionados ao evento `order_execution`:

| Campo | Fonte KuCoin | Uso |
|---|---|---|
| `match_size` | `matchSize` | Volume desta execucao (evento match) |
| `liquidity` | `liquidity` | maker / taker para calculo de fee |
| `trade_id` | `tradeId` | Reconciliacao de PnL real |
| `market` | interno | spot / futures |

### Fix 5 - Lock em subscribes dinamicos

**Problema:** `_lock` estava declarado mas nunca usado. Chamadas simultaneas geravam subscribe
duplicado ou corrupcao do registry.

**Solucao:** `add_ticker_subscription`, `add_candle_subscription` e
`add_futures_orders_subscription` usam `async with self._lock` em toda operacao de
verificacao + registro + envio.

### Fix 6 - Retry com delay em caso de 429 no token

**Problema:** `_get_ws_token` nao tratava rate limit no endpoint `/bullet-public`.

**Solucao:** Loop de ate 5 tentativas com backoff exponencial (5 -> 10 -> 20 -> 40 -> 60 s).
Detecta HTTP 429 via `resp.status_code` + header `Retry-After` e JSON code `429000`.

### Fix 7 - Suporte ao canal Futures

**Problema:** Apenas `/spotMarket/tradeOrders` era suportado.

**Solucao:** Novo metodo `on_futures_order_execution(callback)` e `add_futures_orders_subscription()`.
`_dispatch()` roteia `/contractMarket/tradeOrders` para `_futures_order_callbacks`.
`init_ws_manager()` aceita `subscribe_futures_orders=True`.

### Resumo das mudancas

| Ponto | Antes | Depois |
|---|---|---|
| Re-subscribe pos-reconexao | Parcial (perdia dinamicos) | Total (registry permanente) |
| Snapshot inicial | Ausente | REST antes do WS |
| Conexao zumbi | Nao detectada | Watchdog a cada 10 s |
| Execution report | filledSize apenas | matchSize, liquidity, tradeId |
| Subscribe dinamico | Sem lock | asyncio.Lock atomico |
| 429 no token | Sem tratamento | Retry com backoff ate 60 s |
| Futures | Nao suportado | Canal /contractMarket/tradeOrders |

---

## 15. Componentes Exchange-Grade - Sessao 2026-02-23 (Parte 2)

Seis componentes criticos para producao com capital real foram implementados.

### 1. ReconciliationJob

**Arquivo:** `backend/app/trading/reconciliation.py`

**Problema:** WebSocket pode dropar eventos. Ordens ficam OPEN no banco sem terem sido preenchidas.

**Solucao:** Job periodico (padrao 90 s) que:
1. GET /api/v1/orders?status=active (KuCoin)
2. Query banco: status IN (PENDING, OPEN)
3. Para cada divergencia: busca estado real via GET /orders/{id}, corrige banco, registra no ImmutableJournal

**Uso no startup:**
`python
job = ReconciliationJob(kucoin_client, db, journal, interval_s=90)
await job.start()
`

**Obrigatorio para capital real.** Sem isso, dependencia 100% do WS.

---

### 2. PositionManager

**Arquivo:** `backend/app/trading/position_manager.py`

**Problema:** Sem persistencia, restart do servidor = perda total do estado de posicoes.

**O que persiste (colecao MongoDB: positions):**
- Preco medio ponderado (recalculado a cada execution report match)
- Fees acumuladas por posicao
- PnL realizado ao fechar
- PnL nao realizado com preco atual de mercado

**Principais metodos:**
| Metodo | Descricao |
|---|---|
| `open_position()` | Cria registro com status=open |
| `apply_execution(event)` | Atualiza avg_price + fees via WS execution report |
| `close_position(exit_price)` | Calcula PnL realizado e fecha |
| `unrealized_pnl(current_price)` | PnL instantaneo nao realizado |
| `count_open_by_symbol()` | Contagem para limite RiskManager |

---

### 3. RedisRateLimitManager

**Arquivo:** `backend/app/exchanges/kucoin/redis_rate_limiter.py`

**Problema:** Cada instancia/worker tem rate limiter em memory -> 429 massivo em multi-instancia.

**Solucao:** Estado de rate limit no Redis (compartilhado entre todos os workers):
- `update_from_headers()` -> grava remaining/reset_ms no Redis com TTL baseado no reset KuCoin
- `wait_if_needed()` -> bloqueia se remaining <= 0 (consultando Redis)
- Fallback gracioso se Redis indisponivel (limite conservador de 5 req)
- Pipeline Redis para writes atomicos

**Chaves Redis:** `kucoin:rl:remaining`, `kucoin:rl:limit`, `kucoin:rl:reset_ms`

**Requisito:** `pip install redis[asyncio]`

---

### 4. ExchangeHealthMonitor (Circuit Breaker)

**Arquivo:** `backend/app/trading/circuit_breaker.py`

**Problema:** Exchange com erros -> sistema continua tentando -> cascata de prejuizo.

**Estados:**
- `CLOSED` -> normal, monitora taxa de erro
- `OPEN` -> bloqueia novos trades (lanca `CircuitOpenError`)
- `HALF_OPEN` -> apos timeout, permite 1 request de teste

**Parametros defaults:** 5 falhas consecutivas ou 50% de erro na janela de 60 s -> OPEN. Timeout de 60 s para HALF_OPEN.

**Integrado ao TradingEngine:** `_guard_trade()` chama `circuit.pre_request()` antes de qualquer ordem.

**Uso como decorator:**
`python
@monitor.guard
async def place_order(...):
    ...
`

---

### 5. Kill-Switch no TradingEngine

**Arquivo modificado:** `backend/app/trading/engine.py`

**Problema:** Kill-switch existia no RiskManager mas nao bloqueava execucao via admin API ou bot secundario.

**Solucao:** Metodo `_guard_trade(user_id)` executado no nivel mais alto, antes de qualquer request a exchange:
1. Verifica `risk_manager.is_kill_switched(user_id)` -> lanca `PermissionError`
2. Verifica circuit breaker -> lanca `CircuitOpenError`

Hierarquia garantida: kill-switch human > circuit breaker > validacao de risco > envio.

**Inicializacao com guards:**
`python
engine = TradingEngine(
    kucoin_client=client,
    account_id=account_id,
    circuit_breaker=circuit_breaker,
    risk_manager=risk_manager,
)
`

---

### 6. ImmutableJournal

**Arquivo:** `backend/app/trading/immutable_journal.py`

**Problema:** Logs de ordem/execucao sao mutaveis; sem trilha forense; incompativel com compliance.

**Garantias:**
- Colecao MongoDB append-only (nenhum update/delete na classe)
- Hash encadeado SHA256: cada entrada inclui hash da anterior
- `verify_chain()` recomputa toda a cadeia e detecta adulteracao

**Tipos de evento padronizados:**
| Constante | Uso |
|---|---|
| `EVENT_ORDER_PLACED` | Toda ordem enviada |
| `EVENT_EXECUTION_REPORT` | Todo match WS |
| `EVENT_RISK_CHANGE` | Alteracao de config de risco |
| `EVENT_KILL_SWITCH_ON/OFF` | Ativacao/desativacao |
| `EVENT_RECONCILIATION_FIX` | Correcao pelo ReconciliationJob |
| `EVENT_CIRCUIT_OPEN/CLOSE` | Transicao do circuit breaker |

---

### Arquivos Criados/Modificados (Sessao 2)

| Arquivo | Status |
|---|---|
| `backend/app/trading/reconciliation.py` | Novo |
| `backend/app/trading/position_manager.py` | Novo |
| `backend/app/exchanges/kucoin/redis_rate_limiter.py` | Novo |
| `backend/app/trading/circuit_breaker.py` | Novo |
| `backend/app/trading/immutable_journal.py` | Novo |
| `backend/app/trading/engine.py` | Modificado: `_guard_trade`, imports, `__init__` |

### Checklist pre-producao com capital real

| Item | Obrigatorio |
|---|---|
| ReconciliationJob registrado no startup | Sim |
| PositionManager integrado ao OrderManager | Sim |
| Redis disponivel (para RedisRateLimitManager) | Sim |
| Circuit breaker passado ao TradingEngine | Sim |
| ImmutableJournal inicializado no startup | Sim |
| Testes de falha simulada (429, 500, reconexao) | Sim |
| `pip install redis[asyncio]` | Sim |
| Indice MongoDB em positions.user_id + positions.symbol | Recomendado |
| Indice MongoDB TTL em immutable_journal (retencao) | Recomendado |
