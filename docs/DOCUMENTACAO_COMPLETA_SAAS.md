# 📘 DOCUMENTAÇÃO COMPLETA — CRYPTO TRADE HUB SaaS

> **Versão da API:** 2.0.0 | **Stack Principal:** React 18 + FastAPI + MongoDB + Redis
> **Data da documentação:** Fevereiro de 2026

---

## 🧭 ÍNDICE

1. [Visão Geral do Produto](#1-visão-geral-do-produto)
2. [Stack Tecnológica](#2-stack-tecnológica)
3. [Arquitetura do Sistema](#3-arquitetura-do-sistema)
4. [O Que o Sistema Já Faz](#4-o-que-o-sistema-já-faz)
   - 4.1 [Autenticação & Segurança](#41-autenticação--segurança)
   - 4.2 [Dashboard Interativo](#42-dashboard-interativo)
   - 4.3 [Robôs de Trading (Bots)](#43-robôs-de-trading-bots)
   - 4.4 [Sistema de Estratégias](#44-sistema-de-estratégias)
   - 4.5 [Integração KuCoin](#45-integração-kucoin)
   - 4.6 [Sistema de Gamificação (TradePoints Arena)](#46-sistema-de-gamificação-tradepoints-arena)
   - 4.7 [Sistema de Afiliados](#47-sistema-de-afiliados)
   - 4.8 [Módulo Educacional](#48-módulo-educacional)
   - 4.9 [Analytics & Relatórios](#49-analytics--relatórios)
   - 4.10 [Notificações em Tempo Real](#410-notificações-em-tempo-real)
   - 4.11 [Sistema de Licenças e Planos](#411-sistema-de-licenças-e-planos)
   - 4.12 [Sistema Anti-Fraude (7 Camadas)](#412-sistema-anti-fraude-7-camadas)
   - 4.13 [Chat em Tempo Real](#413-chat-em-tempo-real)
   - 4.14 [Painel Admin](#414-painel-admin)
   - 4.15 [Sistema de Créditos de Ativação](#415-sistema-de-créditos-de-ativação)
   - 4.16 [Workers & Filas de Tarefas](#416-workers--filas-de-tarefas)
   - 4.17 [Configurações do Usuário](#417-configurações-do-usuário)
5. [Estrutura de Arquivos do Projeto](#5-estrutura-de-arquivos-do-projeto)
6. [API — Endpoints Disponíveis](#6-api--endpoints-disponíveis)
7. [Modelos de Dados Principais](#7-modelos-de-dados-principais)
8. [Planos Disponíveis e Limites](#8-planos-disponíveis-e-limites)
9. [Sistema de Afiliados — Fluxo Completo](#9-sistema-de-afiliados--fluxo-completo)
10. [O Que Está Faltando / Em Desenvolvimento](#10-o-que-está-faltando--em-desenvolvimento)
11. [Roadmap Futuro Sugerido](#11-roadmap-futuro-sugerido)
12. [Como Iniciar o Projeto (Dev)](#12-como-iniciar-o-projeto-dev)
13. [Variáveis de Ambiente (`.env`)](#13-variáveis-de-ambiente-env)
14. [Riscos e Pontos Críticos Identificados](#14-riscos-e-pontos-críticos-identificados)

---

## 1. Visão Geral do Produto

**Crypto Trade Hub** é uma plataforma SaaS completa de automação de trading de criptomoedas. Ela permite que usuários criem, configurem e monitorem **robôs de trading automatizados (bots)** integrados a exchanges reais, com interface web moderna, sistema de gamificação, programa de afiliados e um hub educacional.

### Propósito

| Público-alvo | Propósito |
|---|---|
| Traders iniciantes | Aprender trading com robôs pré-configurados e cursos |
| Traders intermediários | Criar estratégias customizadas e monitorar performance |
| Traders avançados | API completa, estratégias complexas, analytics detalhado |
| Gestores / Empresas | Plano Enterprise com white-label e suporte dedicado |

### Diferenciais Competitivos

- **Gamificação integrada**: TradePoints, XP, níveis, ranking quinzenal
- **Sistema de afiliados multinível**: 4 tiers com comissões progressivas (10% a 25%)
- **Hub educacional**: Cursos e videoaulas dentro da plataforma
- **Segurança multicamadas**: 7 camadas de anti-fraude, atomic swaps, kill-switch de emergência
- **Real-time total**: WebSocket para preços, notificações e chat

---

## 2. Stack Tecnológica

### Frontend

| Tecnologia | Versão | Função |
|---|---|---|
| React | 18.x | Framework UI principal |
| TypeScript | 5.x | Tipagem estática |
| Vite | 5.x | Build tool e dev server |
| TailwindCSS | 3.x | Estilização utilitária |
| ShadcnUI | Latest | Componentes de UI |
| TanStack Query | 5.x | Cache, sincronização e fetching |
| Axios | 1.x | Cliente HTTP com interceptors |
| Recharts | 2.x | Gráficos e visualizações |
| React Router DOM | 6.x | Roteamento SPA |
| Lucide React | Latest | Ícones |
| Sonner / Toaster | Latest | Notificações toast |

### Backend

| Tecnologia | Versão | Função |
|---|---|---|
| Python | 3.10+ | Linguagem principal |
| FastAPI | 0.100+ | Framework API REST |
| Uvicorn | Latest | Servidor ASGI |
| SQLAlchemy | 2.x | ORM (legado, migração em progresso) |
| Alembic | Latest | Migrations SQL |
| MongoDB (Motor) | Latest | Banco principal (NoSQL async) |
| Redis | 7.x | Cache, rate limiting, filas |
| Pydantic | v2 | Validação de dados |
| JWT (python-jose) | Latest | Tokens de autenticação |
| Google OAuth2 | Latest | Login social |
| Celery / Task Queue | Custom | Workers em background |
| Groq AI | Latest | IA integrada |
| Google Vision API | Latest | Processamento de imagem |

### Infraestrutura

| Componente | Ferramenta |
|---|---|
| Containerização | Docker + Docker Compose |
| Reverse Proxy | Nginx |
| Banco de dados SQL | SQLite (dev) / PostgreSQL (prod) |
| Banco NoSQL | MongoDB Atlas |
| Cache / Pub-Sub | Redis |
| CI/CD | GitHub Actions (`.github/`) |
| Monitoramento | Resource Monitor interno |

---

## 3. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                        USUÁRIO FINAL                        │
└────────────────────┬────────────────────────────────────────┘
                     │  HTTPS
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     NGINX (Reverse Proxy)                   │
│         /api → Backend :8000  |  / → Frontend :8081         │
└────────┬───────────────────────────────────┬────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────┐                ┌─────────────────────────┐
│  BACKEND        │                │  FRONTEND               │
│  FastAPI :8000  │◄──WebSocket───►│  React/Vite :8081       │
│                 │                │                         │
│  Módulos:       │                │  Páginas:               │
│  - Auth         │                │  - Dashboard            │
│  - Bots         │                │  - Robots               │
│  - Strategies   │                │  - Strategies           │
│  - Trading      │                │  - Plans                │
│  - Analytics    │                │  - Affiliate            │
│  - Gamification │                │  - Education            │
│  - Affiliates   │                │  - Settings             │
│  - Education    │                │  - KuCoin Connect       │
│  - Chat         │                │  - Projections          │
│  - Licensing    │                └─────────────────────────┘
│  - Notifications│
│  - Anti-Fraud   │
└────────┬────────┘
         │
    ┌────┴────────────────────────┐
    │                             │
    ▼                             ▼
┌──────────┐             ┌─────────────┐
│ MongoDB  │             │    Redis    │
│ (dados   │             │ (cache,     │
│ usuário, │             │  rate-limit,│
│ bots,    │             │  filas,     │
│ trades)  │             │  pub-sub)   │
└──────────┘             └─────────────┘
         │
         ▼
┌──────────────────────────┐
│  KuCoin Exchange API     │
│  - REST API              │
│  - WebSocket streams     │
└──────────────────────────┘
```

### Fluxo de Requisição Padrão

```
Cliente → Nginx → FastAPI Middleware (CSP, CORS, Rate Limit) 
→ Router → Service → Repository → MongoDB/Redis → Response
```

---

## 4. O Que o Sistema Já Faz

### 4.1 Autenticação & Segurança

**Status: ✅ Implementado e funcional**

O sistema possui um sistema de autenticação completo e robusto:

#### Login Tradicional
- Cadastro com e-mail + senha (hash bcrypt)
- Login com retorno de **JWT access token + refresh token**
- Validação de e-mail com regex RFC 5322
- Rate limiting: **5 requests/minuto por IP** no endpoint de login

#### Google OAuth 2.0
- Botão "Login com Google" no frontend
- Fluxo completo: Frontend → Google → Backend callback → Token JWT
- Validação blindada do ID Token com 5 etapas:
  1. Verificação do `GOOGLE_CLIENT_ID`
  2. Validação da assinatura criptográfica
  3. Validação do `issuer`
  4. Extração dos dados do usuário
  5. Validação de campos obrigatórios
- Criação automática de conta caso o e-mail não exista
- Configuração completa de CSP (Content Security Policy) para o Google OAuth

#### Autenticação de Dois Fatores (2FA)
- Router dedicado: `app.auth.two_factor_router`
- TOTP (Time-based One-Time Password)
- QR Code para configuração com apps autenticadores

#### Gerenciamento de Sessão
- Refresh token com rotação
- Endpoint `GET /api/me` para dados do usuário logado
- Dependência `get_current_user` injetada em todos os endpoints protegidos
- Middleware de autenticação global

#### Segurança Complementar
- Headers de segurança via middleware CSP
- Rate limiting por endpoint (5/min auth, 60/min trading, 120/min queries)
- Proteção CORS configurável por ambiente
- Validação de senhas fortes

---

### 4.2 Dashboard Interativo

**Status: ✅ Implementado**

O dashboard principal (`Dashboard.tsx`) apresenta:

- **Saldo total** em USD em tempo real
- **Lucro/Prejuízo** acumulado (P&L)
- **Número de trades** realizados
- **Win rate** dos bots ativos
- **Gráficos** de performance histórica (Recharts)
- **Status de bots** ativos e parados
- **Notificações** pendentes
- **Indicador de saúde** do sistema (`SystemHealthIndicator`)
- **Kill Switch** de emergência (`KillSwitchButton`) para parar todos os bots

---

### 4.3 Robôs de Trading (Bots)

**Status: ✅ Implementado — core funcional**

Esta é a feature central da plataforma. Cada bot é um agente de trading automatizado configurável.

#### Bot Model — Propriedades

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | ID único MongoDB |
| `user_id` | string | Dono do bot (obrigatório) |
| `name` | string | Nome do bot |
| `strategy` | string | Estratégia em uso |
| `exchange` | string | Exchange conectada (binance/kucoin) |
| `pair` | string | Par de trading (ex: BTC/USDT) |
| `status` | enum | idle / running / paused / stopped / switching |
| `profit` | float | Lucro acumulado em USD |
| `trades` | int | Total de trades realizados |
| `win_rate` | float | Taxa de acerto (%) |
| `max_drawdown` | float | Maior perda máxima |
| `sharpe_ratio` | float | Índice de Sharpe |
| `swap_count` | int | Número de reconfigurações realizadas |

#### Configuração do Bot (BotConfig)

```json
{
  "amount": 1000.0,
  "stop_loss": 5.0,
  "take_profit": 10.0,
  "risk_level": "medium",
  "timeframe": "5m",
  "indicators": ["RSI", "MACD"],
  "strategy": "Custom Strategy"
}
```

#### Estados do Bot (BotState)

```
idle → running → paused → stopped
         ↕
      switching  (estado de transição durante atomic swap)
```

#### Páginas Frontend de Robôs

| Página | Arquivo | Função |
|---|---|---|
| Visão geral dos bots | `CryptoRobots.tsx` | Lista e gestão de todos os bots |
| Página detalhada | `RobotsPage.tsx` | Detalhes de um bot individual |
| Marketplace gamificado | `RobotsGameMarketplace.tsx` | Robôs com apresentação de jogo |
| Robôs com glowcard | `Robots.tsx` | UI com efeito de brilho (GlowCard) |

#### Funcionalidades dos Bots

- Criar novo bot com parâmetros customizados
- Iniciar / parar bot individualmente
- Monitorar performance em tempo real via WebSocket
- Atomic Swap de configuração (troca segura sem perda de estado)
- Histórico de trocas de configuração (`SwapHistory`)
- Limite de slots ativos por plano
- Sistema de créditos para ativação (ver seção 4.15)

---

### 4.4 Sistema de Estratégias

**Status: ⚠️ Parcialmente implementado (migração MongoDB pendente)**

#### O que existe

- `StrategyStatus`: draft → testing → published → archived
- Motor de estratégias: `strategy_engine.py`
- Repositório e schemas definidos
- Páginas de frontend:
  - `MyStrategies.tsx` — estratégias do usuário
  - `PublicStrategies.tsx` — estratégias públicas/mercado
  - `StrategySubmission.tsx` — submissão de nova estratégia
  - `StrategyBuilder.tsx` — construtor visual de estratégias
  - `StrategiesPage.tsx` / `StrategiesPageImproved.tsx`

#### Estratégias suportadas (configuráveis)

- RSI + MACD (padrão)
- Médias Móveis (MA Cross)
- Bollinger Bands
- Estratégias customizadas via builder

#### O que NÃO está funcionando ainda

- Model `UserStrategy`, `StrategyBotInstance`, `StrategyTrade` são placeholders — marcados com `# TODO: Migrar para MongoDB schemas`
- Marketplace de compra/venda de estratégias não está funcional
- Backtesting histórico não implementado

---

### 4.5 Integração KuCoin

**Status: ✅ Implementado com múltiplas camadas**

A integração com a exchange KuCoin é a mais avançada do sistema.

#### Componentes da Integração

| Arquivo | Função |
|---|---|
| `client.py` | Cliente REST KuCoin (HMAC auth, todas as rotas) |
| `websocket_manager.py` | Gerenciador de WebSocket para preços em tempo real |
| `redis_rate_limiter.py` | Rate limiter baseado em Redis para respeitar limites da API |
| `normalizer.py` | Normaliza dados da KuCoin para formato padrão interno |
| `models.py` | Modelos de dados específicos KuCoin |

#### Funcionalidades KuCoin

- Conexão com credenciais API (Key + Secret + Passphrase)
- Consulta de balanço real
- Listagem de mercados e pares disponíveis
- Execução de ordens (market e limit)
- Streaming de preços via WebSocket
- Rate limiting inteligente para evitar banida
- Normalização para formato padrão (exchange-agnostic)

#### Página Frontend

- `KuCoinConnection.tsx` — tela de conexão e configuração das chaves API
- `KuCoinDashboard.tsx` — dashboard específico para dados KuCoin
- `KuCoinNativeChart.tsx` — gráfico nativo com dados KuCoin
- `KuCoinOnboarding.tsx` — guia de onboarding para conectar a exchange

---

### 4.6 Sistema de Gamificação (TradePoints Arena)

**Status: ✅ Implementado — sistema completo**

O sistema de gamificação é um diferencial importante da plataforma, tornando o trading mais engajante.

#### TradePoints (Moeda de Gamificação)

- Cada usuário começa com **1.000 TradePoints** (bônus de boas-vindas)
- Pontos são ganhos ao: realizar trades, abrir baús diários, subir de nível
- Pontos podem ser usados para: desbloquear robôs, comprar funcionalidades

#### Sistema de XP e Níveis

```
Fórmula XP para próximo nível: XP = 100 × (nível_atual + 1)²

Nível  1 →  2: 400 XP necessário
Nível  5 →  6: 3.600 XP necessário
Nível 10 → 11: 12.100 XP necessário
...até nível 100
```

| Propriedade | Descrição |
|---|---|
| `level` | Nível atual (1–100) |
| `xp` | XP acumulado total |
| `trade_points` | Saldo de pontos |
| `unlocked_robots` | Lista de robôs desbloqueados |
| `lifetime_profit` | Lucro total histórico em USD |

#### Baú Diário (Daily Chest)

- Um baú por dia disponível ao usuário
- Recompensa: XP + TradePoints (variável)
- Sistema de streak: dias consecutivos aumentam recompensa
- `streak_count` rastreia dias seguidos abrindo o baú

#### Ranking de Robôs (RobotRanking)

- Ranking por quinzena (período de 15 dias)
- Robôs são rankeados por performance (lucro, win rate, sharpe)
- Recompensas para os top robôs de cada quinzena

#### Frontend Gamificação

- `RobotsGameMarketplace.tsx` — marketplace com visual de jogo
- Sistema de XP exibido no perfil
- Animações de confete (`Fireworks.tsx`) em eventos especiais

---

### 4.7 Sistema de Afiliados

**Status: ✅ Implementado — sistema multinível completo**

#### Estrutura do Sistema

Cada usuário recebe um **código de afiliado único** (8 caracteres, baseado em hash SHA-256 do user_id + salt).

#### Tiers de Afiliado

| Tier | Indicações Mínimas | Comissão |
|---|---|---|
| 🥉 Bronze | 0+ | 10% |
| 🥈 Silver | 10+ | 15% |
| 🥇 Gold | 50+ | 20% |
| 💎 Platinum | 100+ | 25% |

#### Fluxo de Referral

```
1. Usuário A compartilha link: https://app.cryptotradehub.com?ref=A3X9K2M7
2. Novo usuário B clica no link → cookie de referral salvo
3. Usuário B se cadastra → sistema atribui B como indicado de A
4. B compra licença → A recebe comissão automática (10–25%)
```

#### Funcionalidades

- Geração automática de código ao cadastro
- Tracking de referrals via cookie persistente
- Cálculo automático de comissões sobre vendas de licenças
- Relatório de indicados e comissões
- Histórico de pagamentos de comissões
- Página dedicada: `Affiliate.tsx`

#### Collections MongoDB

- `users` — campo `affiliate_code` e `referred_by`
- `referrals` — registro de cada indicação
- `affiliate_commissions` — registro de cada comissão

---

### 4.8 Módulo Educacional

**Status: ✅ Implementado — estrutura completa**

#### Hierarquia de Conteúdo

```
Course (Curso)
  └── Lesson (Aula)
        └── LessonType: video | text | quiz | exercise
```

#### Modelos

| Modelo | Campos Principais |
|---|---|
| `Course` | name, description, level, status, lessons[] |
| `Lesson` | title, content, type, duration, order |
| `CourseProgress` | user_id, course_id, completed_lessons, progress_% |
| `CourseEnrollment` | user_id, course_id, enrolled_at, completed_at |

#### Níveis de Curso (CourseLevel)

- `beginner` — Iniciante
- `intermediate` — Intermediário
- `advanced` — Avançado

#### Status de Curso (CourseStatus)

- `draft` — Em produção
- `published` — Publicado e acessível
- `archived` — Arquivado

#### Páginas Frontend

- `EducationHub.tsx` — Hub central de educação
- `VideoAulas.tsx` — Galeria de videoaulas

#### Integrações AI

- **Groq AI** integrado no backend para geração de conteúdo educacional
- **Google Vision API** para processamento de capturas de tela / análise de gráficos

---

### 4.9 Analytics & Relatórios

**Status: ✅ Implementado — router e serviços ativos**

#### Métricas Disponíveis

| Métrica | Descrição |
|---|---|
| P&L (Profit & Loss) | Lucro/prejuízo por período |
| Win Rate | Taxa de trades vencedores |
| Sharpe Ratio | Retorno ajustado ao risco |
| Max Drawdown | Maior perda consecutiva |
| Trade Count | Total de operações |
| Avg Trade Duration | Duração média dos trades |
| Best/Worst Trade | Melhor e pior operação |
| ROI por Bot | Retorno por robô individual |

#### Relatórios

- Relatório diário / semanal / mensal
- Exportação de dados (JSON)
- Gráficos históricos (Recharts no frontend)
- Projeções de mercado: `Projections.tsx` — cenários pessimista, neutro e otimista

#### Validação e Auditoria

- `validation_router` — Validação pré-trade (limites, precisão decimal)
- `audit_router` — Auditoria de todas as operações de trading
- Histórico imutável de P&L
- Balance Audit completo com 7 métodos de verificação

---

### 4.10 Notificações em Tempo Real

**Status: ✅ Implementado via WebSocket**

#### Sistema de Notificações

- WebSocket endpoint dedicado: `ws_notifications_router`
- Notificações persistidas no MongoDB (`app.notifications.models`)
- `NotificationCenter.tsx` — componente de notificações no frontend
- `NotificationSettings.tsx` — configurações de notificação por tipo
- `PriceAlertManager.tsx` — alertas de preço configuráveis

#### Tipos de Notificação

| Tipo | Quando dispara |
|---|---|
| Trade executado | Bot realizou uma operação |
| Stop Loss atingido | Bot atingiu limite de perda |
| Take Profit atingido | Bot atingiu meta de lucro |
| Bot parado | Bot parou por erro ou limite |
| Alerta de preço | Preço atingiu valor configurado |
| Level up | Usuário subiu de nível (gamificação) |
| Baú diário disponível | Baú diário pronto para abrir |
| Sistema | Avisos de manutenção / emergência |

#### Conexão Real-Time

- `ConnectionStatusIndicator.tsx` — indicador de status da conexão WS
- Reconexão automática em caso de queda
- Pub/Sub via Redis para broadcast a múltiplos clientes

---

### 4.11 Sistema de Licenças e Planos

**Status: ✅ Implementado com caching inteligente**

#### Planos Disponíveis

| Plano | Bots | Trades/dia | Estratégias | Exchanges |
|---|---|---|---|---|
| **Free** | 1 | 10 | Básicas | KuCoin |
| **Starter** | 3 | 50 | Básicas + 3 custom | KuCoin |
| **Pro** | 10 | 500 | Todas | KuCoin + Binance |
| **Enterprise** | Ilimitado | Ilimitado | Todas + White Label | Todas |

#### Features por Plano (flags)

```
basic_dashboard       ← Free+
manual_trading        ← Free+
basic_analytics       ← Free+
advanced_analytics    ← Starter+
telegram_alerts       ← Starter+
discord_alerts        ← Starter+
api_access            ← Pro+
priority_support      ← Pro+
custom_strategies     ← Pro+
white_label           ← Enterprise
dedicated_support     ← Enterprise
custom_integration    ← Enterprise
sla_99_9              ← Enterprise
```

#### Validação de Licença

```python
# LicensingService com cache inteligente
1. Primeiro verifica cache local (TTL configurável)
2. Se expirado → busca no servidor de licenças remoto
3. Se remoto falhar e cache válido → usa cache
4. Se tudo falhar → DEV BYPASS: retorna Premium (ambiente de desenvolvimento)
```

#### Página

- `Planos.tsx` — página de planos com toggle mensal/anual, badge do plano atual e botão de upgrade
- `Licenses.tsx` — gerenciamento de licenças

---

### 4.12 Sistema Anti-Fraude (7 Camadas)

**Status: ✅ Implementado — documentação ANTI_FRAUD_7_LAYERS_REFERENCE.md**

As 7 camadas de proteção implementadas:

| Camada | Proteção |
|---|---|
| 1 | Validação de saldo antes de qualquer trade |
| 2 | Locks atômicos (sem race conditions) usando Redis |
| 3 | Precisão decimal com `Decimal` Python (sem float errors) |
| 4 | Auditoria de balanço em cada operação |
| 5 | Detecção de padrões suspeitos (wash trading, etc.) |
| 6 | Rate limiting por usuário e IP |
| 7 | Kill Switch global de emergência |

#### Atomic Swap

- Troca de configuração de bot sem estado inconsistente
- Estado `switching` durante transição
- Rollback automático em caso de falha
- Documentado em: `ATOMIC_SWAP_IMPLEMENTATION.md`

#### Kill Switch

- Endpoint admin para parar TODOS os bots imediatamente
- `KillSwitchButton.tsx` no dashboard para acesso rápido
- Logs de auditoria de quem acionou e quando

---

### 4.13 Chat em Tempo Real

**Status: ✅ Router implementado**

- `app.chat` — módulo de chat
- WebSocket para mensagens em tempo real
- Histórico de mensagens persistido
- Frontend: integrado no dashboard

---

### 4.14 Painel Admin

**Status: ✅ Funcional — acesso restrito**

#### Funcionalidades Admin

- Visualizar todos os usuários
- Alterar planos e licenças manualmente
- Forçar reset de senha
- Ver logs de sistema
- Acionar Kill Switch global
- Auditar balanços de qualquer usuário
- Criar usuários admin (`create_admin_user.py`)

#### Scripts de Admin (raiz do projeto)

| Script | Função |
|---|---|
| `fix_admin.py` | Corrige permissões de admin |
| `reset_admin.py` | Reseta senha do admin |
| `check_admin.py` | Verifica status do admin |
| `create_admin_user.py` | Cria novo usuário admin |

---

### 4.15 Sistema de Créditos de Ativação

**Status: ✅ Implementado**

- Cada bot ativo consome **créditos de ativação** do usuário
- Primeiras **2 trocas** de configuração de bot são **gratuitas**
- A partir da 3ª troca → consome crédito
- `swap_count` rastreia número de trocas por bot
- `activation_credits_used` rastreia consumo total
- Documentado em: `ACTIVATION_CREDITS_SYSTEM.md`

---

### 4.16 Workers & Filas de Tarefas

**Status: ✅ Implementado**

- `app.workers.task_queue` — sistema de filas de tarefas
- `start_worker.py` — inicializa os workers
- `robot_data_updater.py` — atualiza dados dos robôs periodicamente
- `start_robot_updater.py` — serviço de atualização contínua
- Redis como broker das filas
- `core.scheduler` — agendador de tarefas recorrentes

#### Tarefas Rodando em Background

| Tarefa | Frequência | Função |
|---|---|---|
| Atualização de dados de robôs | Contínua | Sincroniza métricas dos bots |
| Verificação de stop loss/take profit | A cada tick | Monitora limites |
| Ranking quinzenal | A cada quinzena | Recalcula ranking de robôs |
| Limpeza de sessões expiradas | Diária | Remove tokens inválidos |
| Resource monitor | Contínuo | Monitora uso de CPU/memória |

---

### 4.17 Configurações do Usuário

**Status: ✅ Implementado — página completa**

Página `Settings.tsx` com:

- Alterar nome, email, avatar
- Seletor de avatar (`AvatarSelector.tsx`, `AvatarSelectorModal.tsx`)
- Alterar senha
- Configurar chaves API de exchanges
- Preferências de notificação
- Configurações de idioma (`LanguageSelector.tsx`)
- Habilitar/desabilitar 2FA
- Vincular conta Google
- Configurações de tema (dark/light)

---

## 5. Estrutura de Arquivos do Projeto

```
crypto-trade-hub/
├── backend/
│   ├── app/
│   │   ├── affiliate/          # Módulo de afiliados (v1)
│   │   ├── affiliates/         # Módulo de afiliados (v2 - atual)
│   │   ├── analytics/          # Analytics e métricas
│   │   ├── auth/               # Autenticação JWT + Google OAuth + 2FA
│   │   ├── bots/               # Robôs de trading
│   │   ├── chat/               # Chat em tempo real
│   │   ├── core/               # Configurações, DB, segurança, scheduler
│   │   ├── education/          # Cursos e videoaulas
│   │   ├── exchanges/
│   │   │   └── kucoin/         # Cliente KuCoin completo
│   │   ├── gamification/       # TradePoints, XP, ranking
│   │   ├── licensing/          # Validação de licenças/planos
│   │   ├── middleware/         # CSP, CORS, rate limit
│   │   ├── models/             # Modelos de banco SQL (legado)
│   │   ├── notifications/      # Sistema de notificações
│   │   ├── real_time/          # Endpoints de teste real-time
│   │   ├── routers/            # Roteadores legados
│   │   ├── security/           # Anti-fraude e validações
│   │   ├── services/           # Redis manager e outros serviços
│   │   ├── strategies/         # Motor de estratégias
│   │   ├── trading/            # Trading, auditoria, kill switch
│   │   ├── users/              # Perfil de usuário
│   │   ├── websockets/         # WebSocket handlers
│   │   ├── workers/            # Filas e workers
│   │   └── main.py             # Ponto de entrada da API
│   ├── alembic/                # Migrations SQL
│   ├── tests/                  # Testes backend
│   └── requirements.txt
│
├── src/                        # Frontend React
│   ├── components/
│   │   ├── affiliate/          # Componentes de afiliados
│   │   ├── auth/               # Componentes de autenticação
│   │   ├── charts/             # Gráficos customizados
│   │   ├── credits/            # Componentes de créditos
│   │   ├── dashboard/          # Componentes do dashboard
│   │   ├── exchange/           # Componentes de exchange
│   │   ├── gamification/       # Componentes de gamificação
│   │   ├── kucoin/             # Componentes KuCoin
│   │   ├── layout/             # Layout principal (sidebar, header)
│   │   ├── license/            # Componentes de licença
│   │   ├── modals/             # Modais reutilizáveis
│   │   ├── robots/             # Componentes de robôs
│   │   ├── strategies/         # Componentes de estratégias
│   │   └── ui/                 # ShadcnUI components
│   ├── pages/                  # Páginas da aplicação
│   ├── hooks/                  # Custom React hooks
│   ├── services/               # Serviços de API (axios)
│   ├── context/                # React context providers
│   ├── types/                  # TypeScript types/interfaces
│   └── utils/                  # Utilitários
│
├── docker-compose.yml          # Stack de desenvolvimento
├── docker-compose.prod.yml     # Stack de produção
├── nginx.conf                  # Config Nginx dev
├── nginx.prod.conf             # Config Nginx prod
├── .env                        # Variáveis de ambiente
└── vite.config.ts              # Config Vite
```

---

## 6. API — Endpoints Disponíveis

### Base URL: `http://localhost:8000`

### Autenticação

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `/api/auth/register` | Criar conta |
| POST | `/api/auth/login` | Login + retorno de tokens |
| POST | `/api/auth/logout` | Invalidar sessão |
| POST | `/api/auth/refresh` | Renovar access token |
| GET | `/api/auth/google` | Iniciar fluxo Google OAuth |
| GET | `/api/auth/google/callback` | Callback Google OAuth |
| POST | `/api/auth/2fa/enable` | Ativar 2FA |
| POST | `/api/auth/2fa/verify` | Verificar código TOTP |
| GET | `/api/me` | Dados do usuário autenticado |

### Bots

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/bots` | Listar bots do usuário |
| POST | `/api/bots` | Criar novo bot |
| GET | `/api/bots/{id}` | Detalhe de um bot |
| PUT | `/api/bots/{id}` | Atualizar configuração |
| DELETE | `/api/bots/{id}` | Remover bot |
| POST | `/api/bots/{id}/start` | Iniciar bot |
| POST | `/api/bots/{id}/stop` | Parar bot |
| POST | `/api/bots/{id}/execute` | Forçar execução de ciclo |

### Estratégias

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/strategies` | Listar estratégias do usuário |
| POST | `/api/strategies` | Criar estratégia |
| GET | `/api/strategies/public` | Estratégias públicas |
| PUT | `/api/strategies/{id}` | Atualizar estratégia |
| DELETE | `/api/strategies/{id}` | Remover estratégia |

### Trading

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/trading/history` | Histórico de trades |
| GET | `/api/trading/audit` | Log de auditoria |
| POST | `/api/trading/validate` | Validação pré-trade |
| POST | `/api/trading/kill-switch` | Kill switch de emergência |

### Analytics

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/analytics/summary` | Resumo de performance |
| GET | `/api/analytics/pnl` | P&L por período |
| GET | `/api/analytics/bots` | Performance por bot |

### Gamificação

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/gamification/profile` | Perfil de gamificação |
| POST | `/api/gamification/daily-chest` | Abrir baú diário |
| GET | `/api/gamification/ranking` | Ranking de robôs |

### Afiliados

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/affiliates/code` | Obter código de afiliado |
| GET | `/api/affiliates/referrals` | Listar indicados |
| GET | `/api/affiliates/commissions` | Listar comissões |
| GET | `/api/affiliates/stats` | Estatísticas do afiliado |

### Educação

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/education/courses` | Listar cursos |
| GET | `/api/education/courses/{id}` | Detalhe do curso |
| POST | `/api/education/enroll` | Matricular em curso |
| PUT | `/api/education/progress` | Atualizar progresso |

### Licenças

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/license` | Licença atual do usuário |
| GET | `/api/license/plans` | Planos disponíveis |
| POST | `/api/license/upgrade` | Solicitar upgrade de plano |

### Notificações

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/notifications` | Listar notificações |
| PUT | `/api/notifications/{id}/read` | Marcar como lida |
| WS | `/ws/notifications` | Stream de notificações |

---

## 7. Modelos de Dados Principais

### User (MongoDB)

```json
{
  "_id": "ObjectId",
  "email": "user@example.com",
  "name": "Nome Usuário",
  "password_hash": "bcrypt_hash",
  "google_id": "google_sub",
  "avatar_url": "https://...",
  "is_admin": false,
  "is_active": true,
  "affiliate_code": "A3X9K2M7",
  "referred_by": "user_id_do_pai",
  "license_type": "pro",
  "license_expires_at": "2027-01-01T00:00:00Z",
  "two_factor_enabled": false,
  "two_factor_secret": null,
  "created_at": "2026-01-01T00:00:00Z",
  "last_login": "2026-02-24T10:00:00Z"
}
```

### Bot (MongoDB)

```json
{
  "_id": "ObjectId",
  "user_id": "user_object_id",
  "name": "BTC Scalper",
  "strategy": "RSI + MACD",
  "exchange": "kucoin",
  "pair": "BTC/USDT",
  "status": "running",
  "is_running": true,
  "config": {
    "amount": 1000.0,
    "stop_loss": 5.0,
    "take_profit": 10.0,
    "risk_level": "medium",
    "timeframe": "5m",
    "indicators": ["RSI", "MACD"]
  },
  "profit": 245.50,
  "trades": 142,
  "win_rate": 67.5,
  "max_drawdown": 8.2,
  "sharpe_ratio": 1.45,
  "swap_count": 1,
  "activation_credits_used": 1,
  "is_active_slot": true,
  "created_at": "2026-01-15T00:00:00Z"
}
```

### GameProfile (MongoDB)

```json
{
  "_id": "ObjectId",
  "user_id": "user_object_id",
  "trade_points": 2850,
  "level": 12,
  "xp": 15420,
  "unlocked_robots": ["bot_001", "bot_007"],
  "lifetime_profit": 4200.00,
  "last_daily_chest_opened": "2026-02-24T08:00:00Z",
  "streak_count": 7,
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

## 8. Planos Disponíveis e Limites

```
┌──────────────────┬──────────┬──────────┬──────────┬────────────────┐
│ Feature          │   Free   │ Starter  │   Pro    │  Enterprise    │
├──────────────────┼──────────┼──────────┼──────────┼────────────────┤
│ Bots ativos      │    1     │    3     │    10    │   Ilimitado    │
│ Trades/dia       │    10    │    50    │   500    │   Ilimitado    │
│ Exchanges        │  KuCoin  │  KuCoin  │  KuCoin  │    Todas       │
│                  │          │          │ +Binance │                │
│ Estratégias      │ Básicas  │ +3custom │  Todas   │ Todas+WL       │
│ Analytics        │  Básico  │ Avançado │ Avançado │   Full         │
│ Alertas Telegram │    ✗     │    ✓     │    ✓     │     ✓          │
│ Alertas Discord  │    ✗     │    ✓     │    ✓     │     ✓          │
│ API Access       │    ✗     │    ✗     │    ✓     │     ✓          │
│ Suporte          │ E-mail   │ E-mail   │Priority  │  Dedicado      │
│ SLA              │    -     │    -     │    -     │   99.9%        │
│ White Label      │    ✗     │    ✗     │    ✗     │     ✓          │
│ Custom Integr.   │    ✗     │    ✗     │    ✗     │     ✓          │
└──────────────────┴──────────┴──────────┴──────────┴────────────────┘
```

---

## 9. Sistema de Afiliados — Fluxo Completo

```
Usuário A (Afiliado)
        │
        │  Compartilha link
        │  cryptotradehub.com?ref=A3X9K2M7
        ▼
Usuário B (Novo usuário)
        │
        │  1. Clica no link → cookie "ref=A3X9K2M7" salvo por 30 dias
        │  2. Se cadastra na plataforma
        │  3. Backend detecta cookie → cria registro em "referrals"
        │  4. Usuário B atribuído ao Usuário A como indicado
        ▼
Usuário B compra plano Pro ($99/mês)
        │
        │  Sistema calcula comissão:
        │  - A tem 5 indicados → Tier Bronze → 10%
        │  - Comissão = $99 × 10% = $9,90
        ▼
Usuário A recebe $9,90 em créditos/wallet de afiliado
```

---

## 10. O Que Está Faltando / Em Desenvolvimento

### 🔴 Crítico — Não Funcional

| Item | Situação | Impacto |
|---|---|---|
| **Strategy Model (MongoDB)** | Placeholder com `# TODO` | Estratégias não são persistidas corretamente |
| **Gateway de Pagamento** | Não implementado | Usuários não podem comprar planos reais |
| **Execução de Trades Real** | Simulado/mock | Robôs não executam trades reais nas exchanges |
| **Backtesting de Estratégias** | Não implementado | Não é possível testar estratégia com dados históricos |

### 🟡 Parcial — Incompleto

| Item | Situação | O Que Falta |
|---|---|---|
| **Integração Binance** | Frontend tem `BinanceTrading.tsx` | Backend sem cliente Binance completo |
| **White Label (Enterprise)** | Mencionado nos planos | Nenhum sistema de white-label implementado |
| **2FA — UI Frontend** | Router backend existe | Interface de configuração 2FA no frontend incompleta |
| **Marketplace de Estratégias** | Páginas existem | Lógica de compra/venda ausente |
| **Wallet de Afiliados** | Service existe | Frontend de saque de comissões ausente |
| **Sistema Multi-idioma** | Parcialmente iniciado | Apenas alguns textos traduzidos |
| **Push Notifications (Mobile)** | Não implementado | Sem suporte a PWA notifications |

### 🟢 Funcional mas Precisa de Melhoria

| Item | Situação | Melhoria Necessária |
|---|---|---|
| **Gráficos de Performance** | Recharts básico | Gráficos mais sofisticados tipo TradingView |
| **Education Hub** | Estrutura existe | Conteúdo real precisa ser cadastrado |
| **Sistema de Chat** | Router implementado | UI de chat incompleta/pouco visível |
| **Resource Monitor** | Implementado | Falta painel de monitoramento para admin |
| **Documentação OpenAPI** | Swagger configurado | Vários endpoints sem docstrings |
| **Testes Automatizados** | Alguns testes existem | Cobertura baixa, principalmente no frontend |

### 🔵 Backlog — Não Iniciado

| Item | Prioridade Sugerida |
|---|---|
| App mobile (React Native / PWA) | Alta |
| Integração com Bybit | Média |
| Integração com OKX | Média |
| Social trading (copiar bot de outro usuário) | Alta |
| Alertas via Telegram Bot | Média |
| Alertas via Discord Webhook | Média |
| Dashboard de afiliados completo com gráficos | Alta |
| Sistema de suporte in-app (tickets) | Média |
| Auditoria fiscal (exportar para IR) | Baixa |

---

## 11. Roadmap Futuro Sugerido

### Fase 1 — Estabilização (1–2 meses)
1. ✅ Migrar `UserStrategy`, `StrategyBotInstance`, `StrategyTrade` para MongoDB schemas reais
2. ✅ Implementar gateway de pagamento (Stripe ou Hotmart)
3. ✅ Completar UI de 2FA no frontend
4. ✅ Completar wallet de comissões do afiliado (saques)
5. ✅ Testes de integração para fluxos críticos (login, criar bot, comprar plano)

### Fase 2 — Crescimento (2–4 meses)
1. Integração completa com Binance (backend)
2. Backtesting de estratégias com dados históricos
3. Marketplace de estratégias funcionando (comprar/vender)
4. Dashboard de afiliados com gráficos e histórico completo
5. Alertas Telegram e Discord funcionais

### Fase 3 — Expansão (4–6 meses)
1. Social trading — copiar robôs de outros usuários
2. PWA / App mobile
3. Integração com exchanges adicionais (Bybit, OKX)
4. White label para Enterprise
5. IA para sugestão de estratégias (Groq AI expandido)

### Fase 4 — Enterprise (6–12 meses)
1. Multi-tenancy para white label
2. Relatório fiscal (exportação para IR)
3. API pública documentada para integrações externas
4. SLA 99.9% com monitoramento ativo
5. Suporte a múltiplas moedas fiat

---

## 12. Como Iniciar o Projeto (Dev)

### Pré-requisitos

```
- Node.js >= 18.x
- Python >= 3.10
- Redis (rodando na porta 6379)
- MongoDB (Atlas ou local na porta 27017)
```

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt

# Configurar variáveis
cp .env.example .env
# Editar .env com suas configurações

# Iniciar servidor
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
# Na raiz do projeto
npm install
cp .env.example .env.local
# Editar .env.local

npx vite --port 8081 --host 0.0.0.0
```

### Via Docker (Recomendado)

```bash
# Dev
docker-compose up -d

# Prod
docker-compose -f docker-compose.prod.yml up -d
```

### Criar Usuário Admin

```bash
cd backend
python create_admin_user.py
# ou
python fix_admin.py
```

---

## 13. Variáveis de Ambiente (`.env`)

### Backend (`backend/.env`)

```env
# ===== BANCO DE DADOS =====
DATABASE_URL=sqlite:///./trading.db           # Dev: SQLite
# DATABASE_URL=postgresql+asyncpg://...       # Prod: PostgreSQL
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/cryptohub
MONGODB_DB_NAME=cryptohub

# ===== REDIS =====
REDIS_URL=redis://localhost:6379

# ===== SEGURANÇA =====
SECRET_KEY=sua-chave-secreta-muito-longa-e-aleatoria
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ===== GOOGLE OAUTH =====
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-seu-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
FRONTEND_REDIRECT_URI=http://localhost:8081/auth-callback

# ===== EXCHANGE APIs =====
KUCOIN_API_KEY=sua-kucoin-api-key
KUCOIN_API_SECRET=seu-kucoin-secret
KUCOIN_PASSPHRASE=sua-kucoin-passphrase

# ===== AI =====
GROQ_API_KEY=sua-groq-api-key
GOOGLE_VISION_API_KEY=sua-vision-api-key

# ===== LICENCIAMENTO =====
LICENSING_SERVER_URL=https://license.seudominio.com
LICENSING_CACHE_TTL=3600

# ===== APP =====
APP_MODE=development   # development | production
CORS_ORIGINS=http://localhost:8081,http://localhost:3000
```

### Frontend (`.env.local`)

```env
VITE_API_BASE=http://localhost:8000
VITE_WS_BASE=ws://localhost:8000
VITE_GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
VITE_APP_NAME=Crypto Trade Hub
VITE_APP_VERSION=2.0.0
```

---

## 14. Riscos e Pontos Críticos Identificados

### 🔴 Risco Alto

| Risco | Descrição | Mitigação Sugerida |
|---|---|---|
| **Sem pagamento real** | Planos existem mas nenhum processador de pagamento está integrado | Integrar Stripe ou Hotmart urgentemente |
| **Modelos Placeholder** | `UserStrategy` e `StrategyTrade` são classes vazias | Migrar para schemas MongoDB reais |
| **Dev bypass de licença** | Em falha de fetch, retorna Premium para todos | Remover em produção, usar licença free por padrão |
| **Execução simulada** | Bots não executam trades reais | Deixar isso explicitamente claro na UI para usuários |

### 🟡 Risco Médio

| Risco | Descrição |
|---|---|
| **Dois módulos de afiliados** | `app/affiliate` e `app/affiliates` coexistem (duplicidade) |
| **SQLAlchemy + MongoDB juntos** | Migração incompleta, ainda há código SQL legado |
| **Cópia de routers** | `router_old.py` e `MyStrategies.backup.tsx` indicam código não limpo |
| **Rate limiter não testado em produção** | Pode ser permissivo demais ou restritivo |
| **Google OAuth pode falhar** | Sem GOOGLE_CLIENT_ID configurado, servidor não inicia |

### 🟢 Boas Práticas Já Presentes

- Logs estruturados com `logging` do Python
- Pydantic v2 para validação rigorosa
- Locking atômico via Redis para race conditions
- Decimal Python para precisão financeira
- Health check endpoint disponível
- Dockerfile e docker-compose para fácil deploy
- Alembic para migrations controladas
- Testes automatizados começando a ser escritos

---

*Documentação gerada em: Fevereiro de 2026*
*Versão do sistema: Crypto Trade Hub API v2.0.0*
*Para atualizações: revisar `backend/app/main.py` (routers registrados) e `src/pages/` (páginas do frontend)*
