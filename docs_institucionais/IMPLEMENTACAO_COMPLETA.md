# IMPLEMENTAÇÃO COMPLETA — CRYPTO TRADE HUB
## Documentação Técnica Institucional (DOC-01 a DOC-10)

> **Versão:** 1.0  
> **Data:** Julho 2025  
> **DOC-09:** Descartado (marcado como inútil pelo responsável técnico)  
> **Status geral:** ✅ Todos os 9 documentos implementados com sucesso

---

## ÍNDICE

1. [Visão Geral do Sistema](#visão-geral-do-sistema)  
2. [DOC-01 — Execução Segura de Ordens](#doc-01--execução-segura-de-ordens)  
3. [DOC-02 — Take Profit / Stop Loss Atômico](#doc-02--take-profit--stop-loss-atômico)  
4. [DOC-03 — WebSocket Gateway Profissional](#doc-03--websocket-gateway-profissional)  
5. [DOC-04 — Proteção contra Race Conditions](#doc-04--proteção-contra-race-conditions)  
6. [DOC-05 — Risk Manager Institucional](#doc-05--risk-manager-institucional)  
7. [DOC-06 — Monitoramento e Observabilidade](#doc-06--monitoramento-e-observabilidade)  
8. [DOC-07 — Gateway de Pagamento e Licenciamento](#doc-07--gateway-de-pagamento-e-licenciamento)  
9. [DOC-08 — Marketplace de Estratégias](#doc-08--marketplace-de-estratégias)  
10. [DOC-10 — Checklist Final Institucional](#doc-10--checklist-final-institucional)  
11. [Bloqueadores Absolutos Resolvidos](#bloqueadores-absolutos-resolvidos)  
12. [Collections MongoDB e Índices](#collections-mongodb-e-índices)  
13. [Variáveis de Ambiente](#variáveis-de-ambiente)  
14. [Como Executar](#como-executar)  

---

## VISÃO GERAL DO SISTEMA

| Camada | Tecnologia |
|--------|-----------|
| API | FastAPI (Python 3.14) |
| Banco de dados | MongoDB (motor async) |
| Cache / Locks | Redis |
| Exchange | KuCoin REST + WebSocket |
| Pagamentos | Perfect Pay (Brasil) — HMAC-SHA256 |
| Criptografia | Fernet AES-256 |
| Observabilidade | Prometheus `/metrics` |
| Rate Limiting | Redis por userId/IP |
| Ambiente | `.venv` na raiz do workspace |

### Principio de Proteção
Todos os blocos de inicialização em `main.py` usam `try/except` isolados — **falha em um DOC nunca aborta o startup da aplicação**.

---

## DOC-01 — Execução Segura de Ordens

### Objetivo
Garantir que ordens enviadas à KuCoin sejam **idempotentes**, com **backoff exponencial** e sem resubmissão após erros terminais.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/trading/execution_engine.py` | Motor principal de execução de ordens |
| `backend/app/trading/reconciliation.py` | Serviço de reconciliação periódica |
| `backend/app/trading/audit_log.py` | Log de auditoria hash-chained imutável |

### Comportamentos-Chave

- **`clientOid`** gerado via SHA-256 do par `(botId, symbol, timestamp)` — garante unicidade por tentativa sem colisão
- **Idempotência Redis:** `SET NX EX 900` no `clientOid` — segunda chamada com mesmo ID retorna order existente sem enviar para KuCoin
- **Backoff exponencial:** 500 ms → 1 s → 2 s → 4 s → 8 s (máx 5 tentativas)
- **`TERMINAL_ERROR_CODES`:** códigos KuCoin (ex: 400100, 400200) que **nunca** fazem retry (saldo insuficiente, par inválido)
- **Reconciliação:** `ReconciliationService` roda a cada 60 s — ordens com status `PENDING` por > 2 min são consultadas via REST e atualizadas
- **Audit Log:** cada trade grava `prev_hash` → cadeia SHA-256 imutável (adulteração detectável)

### Fluxo de Execução
```
Signal → clientOid(SHA-256) → Redis NX check
         ↓ já existe        ↓ novo
     retorna order        envia KuCoin
         existente       ↙ erro terminal?
                       sim → abandona
                       não → backoff retry
                         ↓ sucesso
                      grava MongoDB + audit_log
```

---

## DOC-02 — Take Profit / Stop Loss Atômico

### Objetivo
Gerenciar TP/SL de forma **atômica** — nunca deixar ordens órfãs se a posição for fechada por outro canal.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/trading/tpsl/spot_manager.py` | Criação e cancelamento atômico de TP/SL |
| `backend/app/trading/tpsl/partial_fill_handler.py` | Reajuste de TP/SL em preenchimento parcial |
| `backend/app/trading/tpsl/orphan_guardian.py` | Guardian de ordens órfãs (roda a cada 5 min) |
| `backend/app/trading/execution_processor.py` | Integração com motor de execução |

### Comportamentos-Chave

- **Lock Redis** (`lock:tpsl:{orderId}`) antes de cancelar o par TP/SL — evita duplo cancelamento
- **PartialFillHandler:** quando `filledQty < totalQty`, recalcula TP e SL proporcionalmente e reemite
- **OrphanGuardian:** busca no MongoDB ordens TP/SL cujo `parentOrderId` não existe mais ativo — cancela via REST KuCoin automaticamente
- Par TP/SL armazenado em MongoDB com referência cruzada ao `parentOrderId`

---

## DOC-03 — WebSocket Gateway Profissional

### Objetivo
Conexão WebSocket com a KuCoin com **renovação automática de token**, **reconexão com backoff** e **fan-out via Redis Pub/Sub**.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/websocket/ws_gateway.py` | Gateway WebSocket completo |

### Comportamentos-Chave

| Mecanismo | Detalhe |
|-----------|---------|
| **Renovação de token** | Renova 5 min antes do vencimento (token KuCoin tem vida útil de 30 min) |
| **Backoff de reconexão** | 1 s → 2 s → 4 s → … → 30 s (máx 10 tentativas) |
| **Heartbeat** | Ping a cada 18 s (KuCoin espera a cada 20 s) |
| **Gap detection** | Se `sequence` do evento > `last_seq + 1` → dispara snapshot REST para preencher lacuna |
| **Redis Pub/Sub** | Publica eventos no canal `ws:market:{symbol}` → múltiplos workers consomem sem conexão duplicada à KuCoin |
| **Fallback REST** | Após 10 s offline, busca snapshot do orderbook via REST |

---

## DOC-04 — Proteção contra Race Conditions

### Objetivo
Garantir que sinais concorrentes para o mesmo bot **nunca** causem ordens duplicadas ou saldo negativo.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/core/redis_lock.py` | Lock distribuído com Lua script atômico |
| `backend/app/trading/signal_processor.py` | Processador de sinais com locks duplos |

### Mecanismo de Lock (Lua)

```lua
-- Liberação atômica: só libera se o token for do dono
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

### Fluxo de Locks

```
Sinal recebido
  → ACQUIRE lock:bot:{botId}      (evita dupla execução do mesmo bot)
  → ACQUIRE lock:balance:{userId} (evita saldo negativo concorrente)
  → pré-flight: verifica saldo
  → envia ordem KuCoin
  → persiste orderId no MongoDB
  → XACK no Redis Stream
  → RELEASE ambos os locks
```

- **Redis Streams consumer group:** ordens enfileiradas em `stream:orders` — consumer group garante "at-least-once" com XACK apenas após persistência
- Lock com TTL obrigatório → nunca fica preso em caso de crash

---

## DOC-05 — Risk Manager Institucional

### Objetivo
Bloquear **qualquer** ordem que viole limites de risco antes de enviá-la à exchange.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/risk/risk_manager.py` | Avaliador de risco em tempo real |
| `backend/app/risk/audit_log.py` | Audit log de decisões de risco (hash-chained) |
| `backend/app/risk/volatility_indexer.py` | Índice de volatilidade em tempo real |

### Regras de Risco

| Regra | Comportamento |
|-------|--------------|
| **MaxDailyLoss** | Se perda diária acumulada ≥ limite → bloqueia novas ordens até reset |
| **MaxDrawdown** | Se drawdown corrente ≥ limite → entra em cooldown configurável |
| **Kill-Switch** | Flag Redis `kill:{userId}` → propaga em < 2 s para todos os workers |
| **ConsecutiveLoss** | 5 perdas seguidas → bot é morto automaticamente |
| **Volatilidade** | Score > 85/100 → bloqueia abertura de novas posições |
| **Closing orders** | Ordens de fechamento **sempre aprovadas** (nunca bloqueadas pelo Risk) |
| **Reset diário** | Contadores zerados à meia-noite UTC |

### Integração
`RiskManager.evaluate(order)` é chamado em **TODA** ordem antes do envio — recusa retorna `RiskDecision(approved=False, reason=...)` e registra no `RiskAuditLog`.

---

## DOC-06 — Monitoramento e Observabilidade

### Objetivo
Expor saúde do sistema via endpoint padronizado e métricas Prometheus para alertas operacionais.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/health/service.py` | HealthCheckService com score ponderado |
| `backend/app/main.py` | Endpoint `/metrics` Prometheus registrado |

### Score de Saúde

| Componente | Peso |
|-----------|------|
| Redis | 40% |
| MongoDB | 40% |
| KuCoin API | 20% |

- Score 0–100; Redis offline → status `unhealthy` independente do score total
- Endpoint `GET /health` retorna JSON com breakdown por componente
- Endpoint `GET /metrics` expõe métricas no formato Prometheus (contadores, latências)

---

## DOC-07 — Gateway de Pagamento e Licenciamento

### Objetivo
Integração completa com **Perfect Pay** (Brasil), sistema de planos by-user com grace period e feature gating.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/licensing/exceptions.py` | Exceções tipadas de licença |
| `backend/app/licensing/features.py` | `PLAN_FEATURES`, `require_feature()`, `require_plan()` |
| `backend/app/licensing/__init__.py` | Exports do pacote |
| `backend/app/licensing/schemas.py` | Schemas com `in_grace_period`, `grace_until` |
| `backend/app/licensing/service.py` | Serviço por-usuário (MongoDB + Redis) — REESCRITO |
| `backend/app/licensing/client.py` | Bypass de dev REMOVIDO |
| `backend/app/routers/billing.py` | Webhook Perfect Pay com idempotência |
| `backend/app/core/config.py` | Variáveis de plano, encryption key, take rate |

### Hierarquia de Planos

```
free → basic → pro → enterprise
```

### Grace Period

| Evento | Grace Period |
|--------|-------------|
| `canceled` | 3 dias |
| `rejected` | 3 dias |
| `refunded` | Imediato (downgrade direto) |
| `chargeback` | Imediato + flag fraude |

### Segurança

- Webhook validado via **HMAC-SHA256** no campo `token`
- Idempotência: `webhook_events` collection com índice único `(event_id)`
- `LicensingService`: erro no MongoDB → lança `LicenseCheckError` — **nunca** retorna `plan="Premium"` por omissão
- Bypass de desenvolvimento `plan="Premium"` foi **removido** do `licensing/client.py`

### Feature Gating (uso nas rotas)

```python
# Proteger rota por feature
@router.post("/strategies")
async def create(license=Depends(require_feature("marketplace"))):
    ...

# Proteger rota por plano mínimo
@router.post("/backtest")
async def backtest(license=Depends(require_plan("pro"))):
    ...
```

---

## DOC-08 — Marketplace de Estratégias

### Objetivo
Marketplaceonde criadores publicam estratégias de trading (código criptografado), assinantes pagam, e a plataforma retém 30% do revenue.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/strategies/model.py` | Modelos Pydantic completos (era só `pass`) |
| `backend/app/strategies/backtest.py` | BacktestEngine com métricas institucionais |
| `backend/app/strategies/marketplace.py` | MarketplaceService com AES-256 |
| `backend/app/strategies/marketplace_router.py` | 12 endpoints FastAPI |

### Modelos Principais

- `UserStrategy` — estratégia com código criptografado, versões, métricas públicas
- `StrategyVersion` — histórico de versões com hash de integridade
- `StrategyBotInstance` — instância alocada para um assinante
- `StrategyTrade` — trade executado pela instância
- `StrategySubscription` — assinatura de um usuário a uma estratégia
- `StrategyPricing` — modelo de preço (mensal/anual/por-trade)

### Backtest (publicação obrigatória)

| Métrica | Critério mínimo |
|---------|----------------|
| Sharpe Ratio | ≥ 0.5 |
| Max Drawdown | ≤ 30% |
| Win Rate | ≥ 40% |
| Nº de Trades | ≥ 50 |
| Período histórico | ≥ 90 dias |

Dados via **KuCoin REST API** público (klines). Resultados persistidos na collection `backtest_results`.

### Criptografia AES-256

- Código da estratégia criptografado com **Fernet** no momento da criação
- Chave: `STRATEGY_ENCRYPTION_KEY` (env var, 32 bytes base64url)
- Listagens e endpoints públicos **nunca** expõem o campo `versions` (projection MongoDB exclui)
- Código só decriptado no worker que executa o bot, via chave interna

### Revenue Share

| Parte | % |
|-------|---|
| Criador | 70% |
| Plataforma | 30% |

Processamento idempotente via `revenue_events` collection.

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/marketplace/` | Listar estratégias publicadas |
| POST | `/strategies` | Criar nova estratégia |
| POST | `/strategies/{id}/backtest` | Executar backtest |
| GET | `/backtest/{id}` | Resultado do backtest |
| POST | `/strategies/{id}/publish` | Publicar (requer `passed=True`) |
| POST | `/strategies/{id}/subscribe` | Assinar estratégia |
| DELETE | `/strategies/{id}/subscribe` | Cancelar assinatura |
| POST | `/strategies/{id}/instances` | Criar instância de bot |
| GET | `/strategies/{id}/instances` | Listar instâncias |
| GET | `/creator/dashboard` | Dashboard do criador |
| POST | `/internal/revenue-share` | Processar revenue (oculto no schema) |

---

## DOC-10 — Checklist Final Institucional

### Objetivo
Rate limiting por usuário, migração de índices MongoDB idempotente, e `.env.example` completo.

### Arquivos Criados / Modificados

| Arquivo | Papel |
|--------|-------|
| `backend/app/core/middleware_rate_limit.py` | `UserRateLimitMiddleware` |
| `backend/migrations/001_create_indexes.py` | 35+ índices idempotentes |
| `backend/migrations/__init__.py` | Package marker |
| `backend/.env.example` | Todas as env vars documentadas |

### Rate Limiting

| Tipo | Limite | Janela |
|------|--------|--------|
| Usuário autenticado (userId do JWT) | 100 req | 60 s |
| IP anônimo | 30 req | 60 s |

- Backend principal: **Redis** (`INCR` + `EXPIRE`)
- Fallback: dicionário in-memory (quando Redis indisponível)
- Headers retornados: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`
- Resposta `429 Too Many Requests` com `Retry-After` em segundos

### Migrations

Script idempotente que cria **35+ índices** para todas as collections do sistema:

```bash
# Executar uma vez na implantação (ou CI/CD)
python backend/migrations/001_create_indexes.py
```

Collections cobertas: `orders`, `bots`, `users`, `tpsl_pairs`, `reconciliation`, `trade_audit_log`, `risk_decisions`, `risk_audit_log`, `licenses`, `webhook_events`, `license_audit`, `strategies`, `subscriptions`, `bot_instances`, `strategy_trades`, `backtest_results`, `revenue_events`, `creator_wallets`, `_migrations`.

---

## BLOQUEADORES ABSOLUTOS RESOLVIDOS

| # | Bloqueador | Solução |
|---|-----------|---------|
| **6.1** | Dev bypass `plan="Premium"` hardcoded em `licensing/client.py` | Removido — `plan="free"` é o default seguro |
| **7.1** | Código de estratégia exposto em plaintext | AES-256 Fernet em criação; projection MongoDB exclui `versions` |
| **2.1** | Lock Redis liberável por qualquer processo | Lua script atômico: só libera se token == owner |
| **3.1** | RiskManager não chamado em todas as ordens | `evaluate()` chamado ANTES de qualquer envio à KuCoin |
| **6.2** | Webhook Perfect Pay sem validação HMAC | Validação HMAC-SHA256 no campo `token` obrigatória |

---

## COLLECTIONS MONGODB E ÍNDICES

| Collection | Índices Principais |
|----------|-------------------|
| `orders` | `clientOid` (unique), `botId+status`, `userId+createdAt` |
| `bots` | `userId`, `status` |
| `tpsl_pairs` | `parentOrderId` (unique), `userId+status` |
| `reconciliation` | `status+createdAt` |
| `trade_audit_log` | `botId+timestamp`, `prev_hash` |
| `risk_decisions` | `userId+createdAt`, `botId+approved` |
| `risk_audit_log` | `userId+timestamp`, `prev_hash` |
| `licenses` | `userId` (unique), `plan+expiresAt` |
| `webhook_events` | `event_id` (unique) |
| `license_audit` | `userId+action+timestamp` |
| `strategies` | `creatorId`, `published+rating`, `tags` (text) |
| `subscriptions` | `userId+strategyId` (unique), `strategyId+active` |
| `bot_instances` | `subscriptionId`, `userId+active` |
| `backtest_results` | `strategyId+createdAt`, `passed` |
| `revenue_events` | `event_id` (unique), `strategyId+month` |
| `creator_wallets` | `userId` (unique) |

---

## VARIÁVEIS DE AMBIENTE

Todas as variáveis documentadas em `backend/.env.example`. Resumo das críticas:

### Core
```env
MONGODB_URL=mongodb://localhost:27017
DB_NAME=cryptotrade
REDIS_URL=redis://localhost:6379
SECRET_KEY=<jwt-secret-256-bits>
```

### KuCoin
```env
KUCOIN_API_KEY=
KUCOIN_API_SECRET=
KUCOIN_API_PASSPHRASE=
KUCOIN_BASE_URL=https://api.kucoin.com
```

### Perfect Pay (DOC-07)
```env
PERFECT_PAY_WEBHOOK_SECRET=<hmac-secret>
PERFECT_PAY_PLAN_MAP_JSON={"PRODUTO_A":"pro","PRODUTO_B":"enterprise"}
GRACE_PERIOD_DAYS=3
```

### Marketplace (DOC-08)
```env
STRATEGY_ENCRYPTION_KEY=<fernet-key-base64url-32bytes>
MARKETPLACE_PLATFORM_TAKE_RATE=0.30
```

### Rate Limiting (DOC-10)
```env
RATE_LIMIT_USER=100
RATE_LIMIT_IP=30
RATE_LIMIT_WINDOW_SEC=60
```

### Observabilidade (DOC-06)
```env
PROMETHEUS_ENABLED=true
HEALTH_CHECK_INTERVAL_SEC=30
```

---

## COMO EXECUTAR

### 1. Pré-requisitos
```bash
# Dependências Python
pip install -r backend/requirements.txt

# Serviços externos
docker-compose up -d redis mongodb
```

### 2. Configurar ambiente
```bash
cp backend/.env.example backend/.env
# Editar backend/.env com valores reais
```

### 3. Rodar migrations (uma vez)
```bash
python backend/migrations/001_create_indexes.py
```

### 4. Iniciar backend
```bash
# Via task do workspace
# "Backend Server" → cd backend; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Ou manualmente
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Iniciar frontend
```bash
# Via task do workspace
# "Frontend Server" → npx vite --port 8081 --host 0.0.0.0
```

### 6. Verificar saúde
```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

---

## ORDEM DE INICIALIZAÇÃO (main.py)

```
startup_event()
  │
  ├─ DOC-01: ExecutionEngine + ReconciliationService + AuditLog
  ├─ DOC-02: TpslSpotManager + PartialFillHandler + OrphanGuardian
  ├─ DOC-03: WsGateway (token renewal + backoff + pub/sub)
  ├─ DOC-04: RedisLock injetado no OrderManager + OrderQueueConsumer
  ├─ DOC-05: RiskManager + VolatilityIndexer
  ├─ DOC-06: HealthCheckService + Prometheus
  ├─ DOC-07: LicensingService + 3 MongoDB indexes
  ├─ DOC-08: MarketplaceService + 10 MongoDB indexes
  └─ DOC-10: UserRateLimitMiddleware (registrado via add_middleware)

Todos em try/except isolados → falha individual não aborta startup
```

---

## ARQUITETURA DE SEGURANÇA (RESUMO)

```
Requisição HTTP
  → UserRateLimitMiddleware (DOC-10)   429 se exceder limite
  → JWT Authentication
  → require_feature() / require_plan() (DOC-07)
  → RiskManager.evaluate() (DOC-05)    bloqueia ordem de risco
  → RedisLock (DOC-04)                 evita race condition
  → ExecutionEngine (DOC-01)           idempotência + backoff
  → KuCoin API
  → AuditLog (DOC-01/05)               imutável hash-chained
```

---

*Documento gerado após conclusão de todos os DOCs institucionais (exceto DOC-09, descartado).*
