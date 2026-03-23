# 🔴 O QUE AINDA FALTA — CRYPTO TRADE HUB
> **Data:** 11 de março de 2026  
> **Base:** PENDENCIAS_E_BACKLOG.md após conclusão de PEND-01 a PEND-10  
> **Total implementado:** 537 testes passando (342 unit backend + 28 new analytics unit + 23 education integration + 144 other integration + 20 frontend) | 12/16 PENDs concluídos

---

## RESUMO

| Prioridade | Itens | Esforço |
|------------|-------|---------|
| 🟡 Média | 0 itens | — |
| 🟢 Baixa | 4 itens (PEND-13..16) | 2-3 semanas |
| **Total** | **4 PENDs** | **1-3 semanas** |

---

## 🟡 PRIORIDADE MÉDIA

---

### ✅ PEND-09 | 2FA BACKUP CODES — CONCLUÍDO (11/03/2026)
**Status:** ✅ Implementado  
**Testes:** 37 novos (27 unit + 10 integration) — todos passando

**O que foi feito:**
- ✅ Backend: `TwoFactorAuthService` já possuía backup codes (10 codes, formato XXXX-XXXX, criptografados, single-use)
- ✅ Backend: Adicionada invalidação de sessão (`revoke_all_sessions`) ao ativar/desativar 2FA
- ✅ Frontend: `AuthContext.login()` agora detecta `requires_2fa: true` e redireciona para `/2fa-verify`
- ✅ Frontend: Rota `/2fa-verify` adicionada em `App.tsx` com `TwoFactorVerify` component
- ✅ Frontend: `TwoFactorVerify.tsx` corrigido — usa endpoint correto `/auth/2fa/complete` (TOTP + backup codes)
- ✅ Frontend: `Login.tsx` trata erro `requires2FA` e navega para `/2fa-verify` com `tempToken`
- ✅ Frontend: `Settings.tsx` conectado às APIs 2FA (setup, disable, regenerar backup codes)
- ✅ i18n: Chaves traduzidas em pt/en/es/fr (twoFactorEnabled, disable2FATitle, regenerateBackupCodes, etc.)

---

### ✅ PEND-10 | SAQUE PIX PARA AFILIADOS — CONCLUÍDO (11/03/2026)
**Status:** ✅ Implementado  
**Testes:** 35 novos (21 unit + 14 integration) — todos passando

**O que foi feito:**
- ✅ Backend: corrigido bug `$dec` → `$inc` em `wallet_service.py` (2 locais)
- ✅ Backend: adicionado `process_withdrawal(user_id, amount_usd)` — valida saldo ≥ $50, verifica método PIX, cria `WithdrawRequest`, debita saldo, registra transação
- ✅ Backend: adicionado `get_wallet_stats(user_id)` — retorna `WalletResponse` completo (saldos, método, transações recentes, contagem de saques)
- ✅ Backend: `POST /affiliates/withdraw` e `GET /affiliates/wallet` conectados às novas funções
- ✅ Backend: validação de chave PIX (CPF/CNPJ/Email/Telefone/Aleatória) via enum no model
- ✅ Frontend: aba "Wallet" adicionada em `Affiliate.tsx` (4ª aba)
- ✅ Frontend: cards de saldo (disponível / pendente / total sacado)
- ✅ Frontend: dialog para configurar método de saque PIX (tipo + chave + titular)
- ✅ Frontend: dialog para solicitar saque com validação de mínimo $50
- ✅ Frontend: tabela de histórico de transações com status
- ✅ API client: `setWithdrawalMethod()` e `getTransactions()` adicionados em `api.ts`
- ✅ i18n: 42 novas chaves em pt/en/es/fr (wallet, saque, método, status, etc.)

---

### ✅ PEND-11 | MÓDULO DE EDUCAÇÃO COMPLETO — CONCLUÍDO (11/03/2026)
**Status:** ✅ Implementado  
**Testes:** 50 novos (27 unit + 23 integration) — todos passando

**Backend:**
- ✅ Endpoint `GET /education/courses/{id}/player` — retorna `{embed_url, provider, video_id, original_url}` (detecta YouTube/Vimeo automaticamente)
- ✅ `GET /education/courses/{id}/lessons/{lid}/quiz` — retorna quiz sem `correct_index` (seguro para cliente)
- ✅ `POST /education/courses/{id}/lessons/{lid}/quiz` — submete respostas, retorna score, passed, review completo
- ✅ `GET /education/courses/{id}/certificate` — emite/retorna certificado; `?format=pdf` gera PDF (ReportLab)
- ✅ `GET /education/courses/{id}/progress` — % de conclusão, aulas concluídas, datas
- ✅ Modelos: `QuizQuestion`, `QuizCreate`, `Quiz`, `QuizSubmission`, `QuizAttempt`, `Certificate`
- ✅ Repository: `create_quiz`, `get_quiz_by_lesson`, `record_quiz_attempt`, `get_latest_quiz_attempt`, `issue_certificate`, `get_certificate`, `get_course_progress`
- ✅ Service: `extract_video_embed`, `score_quiz_attempt`, `generate_certificate_hash`, `generate_certificate_pdf`
- ✅ Bugfix em `database.py`: `MockCollection.find_one` com `sort`, `find_one_and_update`, segurança em `insert_one`/`insert_many`
- ✅ Bugfix em `repository.py`: serialize methods usam cópia rasa (não mutam `_mock_data`)

**Frontend (`src/pages/EducationHub.tsx`):**
- ✅ Player iframe YouTube/Vimeo com detecção automática de provedor
- ✅ Componente de Quiz: exibição de perguntas, seleção de resposta, submit, resultado com review, retry
- ✅ Barra de progresso visual (já existia — conectada ao enrollment.progress_percent)
- ✅ Banner de certificado ao concluir 100% + botão "Baixar Certificado" (abre PDF em nova aba)
- ✅ Bugfix: código JSX órfão removido; `handleSelectLesson` carrega quiz para todas as aulas

---

### ✅ PEND-12 | ANALYTICS POR ESTRATÉGIA E BOT — CONCLUÍDO (11/03/2026)
**Status:** ✅ Implementado  
**Testes:** 45 novos (28 unit + 17 integration) — todos passando

**Backend (`backend/app/analytics/`):**
- ✅ `compute_strategy_metrics(trades, initial_balance)` em `advanced_metrics.py` — agrupa por `strategy_name`, retorna métricas completas + `bot_ids` por grupo, ordenado por `total_pnl` desc
- ✅ `compute_heatmap(trades)` — matriz 7×24 de avg PnL por dia-da-semana × hora-do-dia
- ✅ `compute_correlation_matrix(trades)` — matriz Pearson N×N de retornos diários entre bots
- ✅ `_pearson(x, y)` helper — Pearson R padrão (retorna 0.0 se variância nula ou n<2)
- ✅ Schemas: `StrategyMetricsItem`, `HeatmapCell`, `HeatmapResponse`, `CorrelationMatrixResponse` em `schemas.py`
- ✅ `GET /analytics/by-strategy` — lista de métricas por estratégia
- ✅ `GET /analytics/heatmap` — `HeatmapResponse` com 168 células
- ✅ `GET /analytics/correlation` — `CorrelationMatrixResponse` com bots + matrix
- ✅ `GET /analytics/advanced-metrics?strategy=…` — filtro por estratégia nos endpoints existentes

**Frontend (`src/pages/PerformanceDashboard.tsx`):**
- ✅ Tabs shadcn/ui: Overview / Por Estratégia / Heatmap / Correlação
- ✅ Tab "Overview": KPIs existentes + equity curve + win rate por período + tabela de bots
- ✅ Tab "Por Estratégia": tabela com 14 colunas (P&L, Win%, Sharpe, MDD, PF, Calmar, etc.)
- ✅ Tab "Heatmap": grade 7×24 colorida (verde=positivo, vermelho=negativo) com labels Mon-Sun / 0-23
- ✅ Tab "Correlação": matriz N×N com interpolação azul(-1)→branco(0)→vermelho(+1)
- ✅ Filtro de estratégia adicionado à barra de filtros
- ✅ 5 fetches paralelos no `fetchData` (advanced-metrics, bot-comparison, by-strategy, heatmap, correlation)

**Testes:**
- ✅ Unit (`test_analytics_service.py`): 28 novos — `TestComputeStrategyMetrics` (6), `TestComputeHeatmap` (6), `TestComputeCorrelationMatrix` (7 incluindo `_pearson`)
- ✅ Integration (`test_analytics_endpoints.py`): 17 novos — `TestByStrategyEndpoint` (4), `TestHeatmapEndpoint` (3), `TestCorrelationEndpoint` (3) + re-use dos 10 existentes

---

## 🟢 PRIORIDADE BAIXA

---

### ✅ PEND-13 | INTEGRAÇÃO METATRADER (EA MONITOR) — CONCLUÍDO (12/03/2026)
**Status:** ✅ Implementado  
**Testes:** 9 novos integration tests (`test_ea_monitor_endpoints.py`)

**Backend (`backend/app/ea_monitor/`):**
- ✅ `router.py` — WebSocket `/ws/ea/{account_id}` com JWT auth via `?token=`, snapshot on connect, 30s ping keepalive, auto-remove dead connections
- ✅ `POST /ea/connect` — registra conta MT4/MT5, gera `api_key` (32-char hex), idempotente para o mesmo usuário
- ✅ `POST /ea/{account_id}/update` — EA envia telemetria via `X-EA-Key` header, broadcast async para todos os subscribers WebSocket
- ✅ `GET /ea/accounts` — lista contas do usuário autenticado
- ✅ `GET /ea/{account_id}/positions` — retorna posições em tempo real do registro em memória
- ✅ `DELETE /ea/{account_id}` — desregistra conta (403 se não for o dono)
- ✅ Registrado em `main.py` com dois routers: `ea_monitor_router` e `ea_monitor_ws_router`

**Frontend:**
- ✅ `src/services/eaMonitorService.ts` — tipos + `connectEAAccount`, `listEAAccounts`, `getEAPositions`
- ✅ `EAMonitor.tsx` — formulário de conexão MT4/MT5, seletor de contas, status WebSocket (Wifi/WifiOff), exibição de api_key, tabela de posições ao vivo, bridge `EALiveTelemetry → EATelemetry` para seção de telemetria existente
- ✅ `src/App.tsx` — rota `/ea-monitor` adicionada (protegida por `ProtectedRoute`)

---

### ✅ PEND-14 | MARKETPLACE DE ROBÔS GAMIFICADO — CONCLUÍDO (12/03/2026)
**Status:** ✅ Implementado  
**Testes:** 14 novos integration tests (`test_marketplace_robots_endpoints.py`)

**Backend (`backend/app/marketplace/`):**
- ✅ `robots_router.py` — `POST /marketplace/robots/{id}/purchase`: chama `GameProfileService.unlock_robot_logic`, grava audit em `robot_purchases`, retorna `PurchaseResponse` com `performance_preview`
- ✅ `GET /marketplace/robots/{id}/performance` — 30 dias determinísticos (seed hash do `robot_id`) com fallback para `robot_rankings`; retorna `total_return_pct`, `win_rate`, `max_drawdown_pct`, 30 `PerformanceDataPoint`
- ✅ `POST /marketplace/robots/{id}/review` — verifica ownership em `game_profiles.unlocked_robots`, upsert em `robot_reviews` (1 review por usuário por robô), rating 1-5
- ✅ `GET /marketplace/robots/{id}/reviews` — lista reviews mascarando `user_id` (LGPD), retorna `avg_rating`
- ✅ Registrado em `main.py`

**Frontend:**
- ✅ `RobotsGameMarketplace.tsx` — `handleConfirmUnlock` chama `POST /marketplace/robots/{id}/purchase` antes do hook legacy; abre modal de Performance+Review após compra bem-sucedida com preview de 14 dias e formulário 1-5 estrelas
- ✅ `handleRobotInfo` busca performance ao abrir info modal de robô já desbloqueado
- ✅ Modal de Performance+Review: mini-gráfico de barras (14 dias), 3 métricas-chave, formulário de avaliação com estrelas interativas e campo de comentário

---

### PEND-15 | SIMULAÇÃO DE CENÁRIOS (PROJEÇÕES)
**Status:** ✅ CONCLUÍDO

**O que foi implementado:**
- [x] `POST /analytics/simulate/montecarlo` — GBM com N trajetórias configuráveis (`backend/app/analytics/router.py`)
- [x] Schemas `MonteCarloRequest`, `MonteCarloPathPoint`, `MonteCarloResponse` (`backend/app/analytics/schemas.py`)
- [x] Resposta com P10/P50/P50 calculados por percentil em cada passo mensal
- [x] Frontend: sliders para capital ($1k–$1M), retorno mensal (-20%–+50%), horizonte (1–60 m), volatilidade (5%–100%), N simulações (100–10000)
- [x] Gráfico `LineChart` (Recharts) com três curvas P10 / P50 / P90 sobre meses
- [x] Card de sumário: P10/P50/P90 finais + probabilidade de lucro
- [x] 12 testes de integração: happy path (6), validação (5), autenticação (1)

**Arquivos alterados:**
- `backend/app/analytics/schemas.py` — adicionados schemas Monte Carlo
- `backend/app/analytics/router.py` — endpoint `POST /simulate/montecarlo`
- `src/pages/Projections.tsx` — seção Monte Carlo com sliders + `LineChart`
- `backend/tests/integration/test_montecarlo_endpoints.py` — 12 testes (criado)

---

### PEND-16 | STRATEGIES PAGE IMPROVED
**Status:** ✅ CONCLUÍDO

**Decisão tomada:** manter `StrategiesPageImproved.tsx` como página principal de estratégias (é um superset com tabs all/my/public/top).

**O que foi implementado:**
- [x] Rota `/strategies` → `StrategiesPageImproved` já registrada em `src/App.tsx`
- [x] Rota `/strategies/legacy` → `PublicStrategies` mantida como fallback
- [x] Sidebar: link `sidebar.myStrategies` atualizado de `/my-strategies` para `/strategies` (`src/components/layout/Sidebar.tsx`)
- [x] Sidebar: link `sidebar.eaMonitor` adicionado para `/ea-monitor` (PEND-13 bonus)

**Arquivos alterados:**
- `src/components/layout/Sidebar.tsx` — navItems atualizados

---

## MÓDULOS BACKEND — ITENS PENDENTES POR MÓDULO

```
backend/app/auth/
  ✅ 2FA backup codes (PEND-09 — concluído)
  ✅ Invalidação de sessão ao ativar/desativar 2FA (PEND-09 — concluído)

backend/app/analytics/
  ✅ Filtros por estratégia individual (PEND-12 concluído)
  ✅ Analytics por estratégia individual (PEND-12 concluído)
  ✅ Heatmap por hora/dia da semana (PEND-12 concluído)
  ✅ Correlação entre bots (PEND-12 concluído)

backend/app/notifications/
  ❌ Alertas de preço em tempo real (threshold configurável por usuário)

backend/app/education/
  ✅ Embeds YouTube/Vimeo (PEND-11 — concluído)
  ✅ Certificados PDF de conclusão (PEND-11 — concluído)
  ✅ Quizzes e avaliações (PEND-11 — concluído)

backend/app/affiliates/
  ✅ Saque PIX (PEND-10 — concluído)
  ✅ Aba Wallet frontend com dialogs PIX (PEND-10 — concluído)
  ❌ Relatório fiscal de comissões (backlog)
  ❌ Anti-fraude referral com device fingerprint (backlog)
```

---

## PÁGINAS FRONTEND — ITENS PENDENTES

| Página | Problema | PEND |
|--------|----------|------|
| `EAMonitor.tsx` | ✅ WebSocket real, formulário MT4/MT5, tabela de posições | PEND-13 ✅ |
| `RobotsGameMarketplace.tsx` | ✅ Fluxo de compra, preview de performance, review | PEND-14 ✅ |
| `Projections.tsx` | ✅ Simulador Monte Carlo com GBM, sliders, gráfico P10/P50/P90 | PEND-15 ✅ |
| `StrategiesPageImproved.tsx` | ✅ Rota /strategies registrada, link no Sidebar atualizado | PEND-16 ✅ |
| `PerformanceDashboard.tsx` | ✅ Tabs: Overview/Por Estratégia/Heatmap/Correlação | PEND-12 ✅ |

---

## INFRAESTRUTURA — ITENS PENDENTES

| Item | Status | Ação |
|------|--------|------|
| Secrets Management | ⚠️ Apenas env vars | Migrar para HashiCorp Vault ou AWS Secrets Manager |
| Structured Logging | ⚠️ Parcial | Configurar Sentry DSN em produção |
| Database Consolidation | ⚠️ MongoDB + SQLite | Migrar SQLite restante para MongoDB |
| Monitoring/Alerting | ❌ Ausente | Prometheus + Grafana ou Datadog |
| Testes E2E | ❌ Ausente | Playwright para fluxos críticos (login → trade → export) |
| Load testing (Locust) | ❌ Ausente | Cenários de carga em endpoints críticos |

---

## ORDEM DE IMPLEMENTAÇÃO SUGERIDA

```
Sprint A — Segurança (✅ CONCLUÍDO)
  └── PEND-09: 2FA Backup Codes ✅

Sprint B — Monetização (✅ CONCLUÍDO)
  └── PEND-10: Saque PIX Afiliados ✅

Sprint C — Produto (1-2 semanas)
  ├── PEND-11: Educação completa (quiz + certificado + embed)
  └── ✅ PEND-12: Analytics por estratégia + heatmap (concluído)

Sprint D — Nice-to-Have (2 semanas)
  ├── ✅ PEND-13: MetaTrader EA Monitor (concluído)
  ├── ✅ PEND-14: Marketplace de Robôs (concluído)
  ├── ✅ PEND-15: Monte Carlo Projeções (concluído)
  └── ✅ PEND-16: StrategiesPageImproved (concluído)
```

---

*Gerado em 11 de março de 2026 | Atualizado após conclusão de PEND-13, PEND-14, PEND-15, PEND-16 — Sprint D 100% concluída*
