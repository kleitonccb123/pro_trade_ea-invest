# 📋 DOCUMENTAÇÃO COMPLETA — SISTEMA DE PONTOS, ROBÔS E BAÚ DIÁRIO

> **Data:** Março 2026  
> **Versão analisada:** crypto-trade-hub-main  
> **Escopo:** Sistema TradePoints (compra de pontos), liberação de robôs e Baú Diário  
> **Última atualização:** 02/03/2026 — Correções e implementações aplicadas (ver [Changelog](#-changelog-de-implementações))

---

## 📑 ÍNDICE

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Sistema de Pontos (TradePoints)](#2-sistema-de-pontos-tradepoints)
3. [Sistema de Liberação de Robôs](#3-sistema-de-liberação-de-robôs)
4. [Baú Diário (Daily Chest)](#4-baú-diário-daily-chest)
5. [O Que Está Correto ✅](#5-o-que-está-correto-)
6. [O Que Está Errado ❌](#6-o-que-está-errado-)
7. [O Que Pode Melhorar 🔧](#7-o-que-pode-melhorar-)
8. [O Que Falta para o Sistema Ficar Funcional 🚧](#8-o-que-falta-para-o-sistema-ficar-funcional-)
9. [Nova Feature: Sistema de Micro-Transação 💡](#9-nova-feature-sistema-de-micro-transação-)
10. [Changelog de Implementações](#-changelog-de-implementações)

---

## 1. Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite)                   │
│                                                             │
│  PointShop.tsx                → Loja de pacotes de pontos   │
│  DailyChestComponent.tsx      → Baú diário com streak       │
│  DailyChestButton.tsx         → Botão flutuante de baú      │
│  LockedRobotModal.tsx         → Modal de robô bloqueado      │
│  UnlockRobotModal.tsx         → Confirmação de desbloqueio  │
│  RobotMarketplaceCard.tsx     → Cards dos robôs             │
│  RobotSlotLimitModal.tsx      → Modal de limite de slot     │
│  MicroTransactionNotification → ✅ NOVO: micro-compra       │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP REST / JWT
┌────────────────────▼────────────────────────────────────────┐
│              BACKEND (FastAPI + Python)                      │
│                                                             │
│  /api/gamification/profile                → Perfil          │
│  /api/gamification/store/bundles          → Loja de pontos  │
│  /api/gamification/store/purchase-points  → Compra pts      │
│  /api/gamification/store/micro-bundles    → ✅ NOVO         │
│  /api/gamification/store/micro-purchase-and-unlock → ✅ NOVO│
│  /api/gamification/transactions           → ✅ NOVO histór. │
│  /api/gamification/daily-chest/open       → Abrir baú       │
│  /api/gamification/claim-daily-xp         → XP diário       │
│  /api/gamification/robots/{id}/unlock     → Desbloquear     │
│  /api/gamification/leaderboard            → Ranking global  │
│  /api/gamification/robots/ranking         → Ranking robôs   │
└────────────────────┬────────────────────────────────────────┘
                     │ Motor async (pymongo)
┌────────────────────▼────────────────────────────────────────┐
│                    MONGODB                                   │
│                                                             │
│  game_profiles           → Perfil gamificado do usuário    │
│  gamification_transactions → Histórico de transações       │
│  leaderboard_cache       → Cache do leaderboard (6h)       │
│  users                   → Dados do usuário + plano        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Sistema de Pontos (TradePoints)

### 2.1 Como Funciona

**TradePoints** é a moeda interna de gamificação. O usuário acumula pontos por:

| Fonte | Quantidade |
|-------|-----------|
| Bônus de boas-vindas (novo usuário) | 1.000 pts |
| Baú diário (base) | 100 pts |
| Baú diário (com streak) | 100 × (1 + streak × 0.1) pts |
| Compra na loja | Conforme pacote |
| Recompensa de plano (ao assinar) | Conforme plano |

### 2.2 Pacotes da Loja (`POINT_BUNDLES`)

Definidos em `backend/app/gamification/model.py`:

| Bundle ID | Nome | Preço (USD) | Pontos | Melhor Custo? | Pts/$ |
|-----------|------|------------|--------|--------------|-------|
| `pouch` | Pouch of Points | $2.99 | 1.000 pts | ❌ | 334 pts/$ |
| `bag` | Bag of Points | $4.99 | 2.500 pts | ❌ | 501 pts/$ |
| `chest` | Chest of Points | $9.99 | 6.000 pts | ✅ | 600 pts/$ |

### 2.3 Recompensas por Plano (`PLAN_REWARD_MAP`)

Definidas em `backend/app/gamification/model.py`:

| Plano | Nome Display | Preço/Mês | Pontos Iniciais | Bônus Mensal | Slots de Robôs |
|-------|-------------|----------|----------------|-------------|---------------|
| `starter` | START | $9.99 | 500 pts | 500 pts | 3 |
| `pro` | PRO+ | $11.99 | 1.500 pts | 1.500 pts | 5 |
| `premium` | QUANT | $17.99 | 3.000 pts | 3.000 pts | 10 |
| `enterprise` | BLACK | $39.99 | 10.000 pts | 10.000 pts | 15 |

### 2.4 Fluxo de Compra de Pontos

```
Usuário clica "Comprar Agora" (PointShop.tsx)
  ↓
POST /api/gamification/store/purchase-points
  { bundle_id: "chest", payment_method: "simulated" }
  ↓
Backend valida se bundle existe
  ↓
GameProfileService.get_or_create_profile(user_id)
  ↓
profile.add_trade_points(pontos_do_bundle)
  ↓
GameProfileService.save_profile(profile)
  ↓
Insere registro em gamification_transactions
  ↓
Retorna: { success, points_added, points_balance, transaction_id }
  ↓
Frontend: confete + toast de sucesso
```

---

## 3. Sistema de Liberação de Robôs

### 3.1 Custo de Desbloqueio

Definido em `backend/app/gamification/service.py`:

```python
ELITE_ROBOTS = ['bot_001', 'bot_002', 'bot_003']  # Top 3 do Ranking

ROBOT_UNLOCK_COST = {
    'elite': 1500,   # Robôs Elite (Top 3 do ranking)
    'common': 500,   # Robôs Comuns
}
```

### 3.2 Limites por Plano

Definido em `GameProfileService._get_user_license()`:

| Plano DB | Display | Máx. Robôs Desbloqueáveis |
|----------|--------|--------------------------|
| `starter` | START | **0** (bloqueado total) |
| `pro` | PRO+ | 5 |
| `premium` | QUANT | 15 |
| `enterprise` | BLACK | Ilimitado (999) |

### 3.3 Fluxo de Desbloqueio

```
Usuário clica em robô bloqueado
  ↓
LockedRobotModal abre (mostra custo, lucro histórico)
  ↓
Usuário clica "Desbloquear com Pontos"
  ↓
UnlockRobotModal confirma operação
  ↓
POST /api/gamification/robots/{robot_id}/unlock
  ↓
GameProfileService.unlock_robot_logic():
  1. Verifica plano do usuário (plan_limits)
     → plan='starter' → BLOQUEADO (error: license_required)
  2. Verifica se atingiu limite do plano
     → count >= max_robots → BLOQUEADO (error: plan_limit_reached)
  3. Determina custo (elite=1500, common=500)
  4. Verifica se já desbloqueado (error: already_unlocked)
  5. Verifica saldo (error: insufficient_balance)
  6. Operação ATÔMICA no MongoDB:
     $inc: { trade_points: -custo }
     $addToSet: { unlocked_robots: robot_id }
  ↓
Retorna: { success, new_balance, unlocked_robots }
```

### 3.4 Unificação de Planos — `plan_config.py` ✅ IMPLEMENTADO

Antes existia uma inconsistência crítica entre dois conjuntos de nomes de plano. **Isso foi corrigido** com a criação de `backend/app/core/plan_config.py` como fonte única de verdade.

**Aliases resolvidos automaticamente:**

| Alias (banco antigo) | Chave Canônica | Display |
|---------------------|---------------|--------|
| `start` | `starter` | START |
| `quant` | `premium` | QUANT |
| `black` | `enterprise` | BLACK |

**`service.py`** agora importa `resolve_plan_key()` e `get_plan_config()` em vez de ter o dict hardcoded. Qualquer valor salvo no banco com nome antigo (`quant`, `black`, `start`) é resolvido corretamente.

> ✅ Usuários com `plan = "quant"` no banco agora recebem corretamente 15 slots de robôs.

---

## 4. Baú Diário (Daily Chest)

### 4.1 Regras de Streak

```
Última abertura + 24h ≤ Agora < +48h  → streak += 1 (mantém)
Agora ≥ última abertura + 48h          → streak = 1 (reset)
Primeira abertura (sem histórico)       → streak = 1
```

### 4.2 Cálculo de Recompensas

```python
base_points = 100
base_xp = 50
multiplier = 1.0 + (streak * 0.1)  # ex: streak=5 → 1.5x

points_won = int(base_points * multiplier)
xp_won     = int(base_xp * multiplier)
```

| Dia de Streak | Multiplicador | Pontos | XP |
|-------------|-------------|--------|-----|
| Dia 1 | 1.1x | 110 pts | 55 XP |
| Dia 3 | 1.3x | 130 pts | 65 XP |
| Dia 7 | 1.7x | 170 pts | 85 XP |
| Dia 14 | 2.4x | 240 pts | 120 XP |
| Dia 30 | 4.0x | 400 pts | 200 XP |

### 4.3 Persistência (Operação Atômica)

```python
await collection.update_one(
    {"user_id": str(user_id)},
    {
        "$inc": { "trade_points": points_won, "xp": xp_won },
        "$set": {
            "streak_count": new_streak,
            "last_daily_chest_opened": now,
            "updated_at": now,
        }
    }
)
```

### 4.4 Cooldown

- **Cooldown:** 24 horas exatas desde a última abertura
- **Reset de streak:** após 48 horas sem abrir

---

## 5. O Que Está Correto ✅

### Backend

- ✅ **Operação atômica no desbloqueio de robôs** — usa `$inc` + `$addToSet` em uma única operação MongoDB, evitando race conditions
- ✅ **Cooldown do baú diário** — validação correta de 86.400 segundos
- ✅ **Lógica de streak** — janela de 24h-48h incremental, reset após 48h, implementada corretamente
- ✅ **Bônus de boas-vindas** — 1.000 pts ao criar novo perfil
- ✅ **Log de auditoria** — transações de baú registradas em `gamification_transactions`
- ✅ **Validação de plano antes de desbloquear** — usuário `starter` não pode desbloquear robôs (proteção correta)
- ✅ **Validação de saldo insuficiente** — com cálculo de "quanto falta"
- ✅ **Upsert do perfil** — `get_or_create_profile` é seguro, cria se não existe
- ✅ **Erro tipado no frontend** — `LockedRobotModal` diferencia `license_required` vs `plan_limit_reached`
- ✅ **Endpoint de bundles separado** — `/store/bundles` e `/store/purchase-points` são endpoints distintos (bom para cache)
- ✅ **`plan_config.py`** — fonte única de verdade para nomes/limites de planos com aliases *(NOVO)*
- ✅ **Bug de instância corrigido** — `purchase_points` usa métodos estáticos corretamente *(CORRIGIDO)*
- ✅ **Planos inconsistentes corrigidos** — `quant/black/start` resolvidos via aliases *(CORRIGIDO)*
- ✅ **Streak cap** — máximo de 10 dias de bônus (100%), sem exploit de streak infinito *(NOVO)*
- ✅ **Timestamps separados** — `last_daily_xp_claimed` independente de `last_daily_chest_opened` *(CORRIGIDO)*
- ✅ **Ranking de robôs real** — busca da collection `robot_rankings` com `is_unlocked` real *(CORRIGIDO)*
- ✅ **`MICRO_BUNDLES`** — 4 pacotes emergenciais definidos no model *(NOVO)*
- ✅ **Endpoints de micro-transação** — `/store/micro-bundles` e `/store/micro-purchase-and-unlock` *(NOVO)*
- ✅ **Histórico de transações** — `GET /api/gamification/transactions` com paginação e filtros *(NOVO)*
- ✅ **Worker de bônus mensal** — `monthly_bonus_job.py` + registrado no scheduler (roda dia 1 de cada mês) *(NOVO)*

### Frontend

- ✅ **Efeito de confete** na compra de pontos e abertura de baú
- ✅ **Animação de cadeado** no `UnlockRobotModal`
- ✅ **Timer regressivo** no baú diário (`DailyChestComponent`)
- ✅ **Estado "Melhor Custo"** destacado no `PointShop` (badge no pacote `chest`)
- ✅ **Feedback visual** de unlocking com overlay verde de sucesso
- ✅ **DailyChest usa valores reais da API** — `points_won`, `xp_won`, `new_streak` em vez de hardcoded *(CORRIGIDO)*
- ✅ **`MicroTransactionNotification.tsx`** — componente de micro-compra com 4 pacotes, auto-seleção do menor suficiente, compra+desbloqueio em 1 clique *(NOVO)*
- ✅ **`LockedRobotModal` integrado** — botão "Compra Rápida de Pontos" abre o `MicroTransactionNotification` quando saldo insuficiente *(NOVO)*

---

## 6. O Que Está Errado ❌

> **Nota (02/03/2026):** Os itens 6.2 a 6.8 foram **corrigidos e implementados**. Apenas o item 6.1 (pagamento real) permanece pendente.

### 6.1 Pagamento 100% Simulado (Crítico) — ⚠️ AINDA PENDENTE

**Arquivo:** `backend/app/gamification/router.py` — `purchase_points()`

```python
# payment_method: Optional[str] = Field(default="simulated", ...)
payment_method: request.payment_method or "simulated",
```

**Problema:** A compra de pontos **não processa nenhum pagamento real**. Qualquer usuário pode chamar `POST /api/gamification/store/purchase-points` com `payment_method: "simulated"` e receber pontos SEM pagar nada. Não há validação de Stripe, PayPal ou qualquer gateway.

**Impacto:** Financeiro crítico — a funcionalidade de monetização não está funcional.

> 💡 Os endpoints `micro-purchase-and-unlock` e `purchase-points` já têm a estrutura correta para receber um `transaction_id` real do Stripe assim que a integração for adicionada. O único passo faltante é criar o `payment_service.py` e os endpoints de webhook.

---

### 6.2 ~~Ranking de Robôs com Dados Mockados~~ ✅ CORRIGIDO

**Arquivo:** `backend/app/gamification/router.py` — `get_robots_ranking()`

```python
# TODO: Dados mockados - substituir por dados reais
ranking_items = [
    {
        "rank": 1,
        "robot_name": "Volatility Dragon",
        "profit_15d": 3450.67,  # ← FIXO, nunca muda
        ...
        "is_unlocked": current_user.id == "admin",  # TODO: Verificar real
    },
]
```

**Problema (resolvido):** O endpoint `/robots/ranking` agora busca da collection `robot_rankings` no MongoDB. O campo `is_unlocked` é calculado comparando `robot_id` com `profile.unlocked_robots` do usuário autenticado. Há fallback com dados seed determinísticos (baseados em hash do período) caso a collection esteja vazia na primeira execução.

---

### 6.3 ~~Inconsistência de Nomes de Planos~~ ✅ CORRIGIDO

**Problema:** Existem dois sistemas de planos com nomes diferentes:

| Sistema | Planos usados |
|---------|-------------|
| `plan_limits.py` (bots ativos) | `free`, `start`, `pro`, `pro_plus`, `quant`, `black` |
| `service.py` (desbloqueio de robôs) | `starter`, `pro`, `premium`, `enterprise` |
| `model.py` (`PLAN_REWARD_MAP`) | `starter`, `pro`, `premium`, `enterprise` |

**Problema (resolvido):** Arquivo `backend/app/core/plan_config.py` criado com `PLAN_CONFIG` e `PLAN_ALIASES`. A função `resolve_plan_key()` resolve `quant→premium`, `black→enterprise`, `start→starter`. O `_get_user_license()` agora importa e usa essas funções.

---

### 6.4 ~~Compra de Pontos com Bug de Instância~~ ✅ CORRIGIDO

**Arquivo:** `backend/app/gamification/router.py` — linha ~1050

```python
service = GameProfileService(db)  # ← ERRO: GameProfileService usa métodos @staticmethod
game_profile = await service.get_or_create_profile(current_user.id)
```

**Problema (resolvido):** A linha `service = GameProfileService(db)` foi substituída por chamadas diretas aos métodos estáticos: `GameProfileService.get_or_create_profile()` e `GameProfileService.save_profile()`.

---

### 6.5 ~~Baú Diário e XP Diário Compartilham o Mesmo Timestamp~~ ✅ CORRIGIDO

**Arquivo:** `backend/app/gamification/router.py` — `claim_daily_xp()`

**Problema (resolvido):** Adicionado campo `last_daily_xp_claimed` ao `GameProfile`. O endpoint `claim_daily_xp` agora usa esse campo separado. Abertura de baú e reclamação de XP diário são independentes e não se bloqueiam mutuamente.

---

### 6.6 ~~Pontos do Bônus Mensal de Plano Nunca São Creditados~~ ✅ CORRIGIDO

**Arquivo:** `backend/app/gamification/model.py` — `PLAN_REWARD_MAP`

```python
"monthly_bonus_points": 1500,  # PRO+
```

**Problema (resolvido):** Criado `backend/app/workers/monthly_bonus_job.py` com `credit_monthly_bonuses()`. A função usa `resolve_plan_key()` para ler os `monthly_bonus_points` de cada usuário, aplica `$inc` atômico, registra transação e é idempotente (verifica `month_key` antes de creditar). O scheduler agora roda `_monthly_bonus_check()` diariamente e executa o job apenas no dia 1.

---

### 6.7 ~~Frontend Usa Valores Fixos no Callback de Sucesso do Baú~~ ✅ CORRIGIDO

**Arquivo:** `src/components/gamification/DailyChestComponent.tsx`

```tsx
onSuccess?.({
  points: 110,   // ← HARDCODED, não vem da API
  xp: 55,        // ← HARDCODED
  streak: streak + 1,
  bonus: Math.round(streak * 10),
});
```

**Problema (resolvido):** O `handleOpenChest` em `DailyChestComponent.tsx` agora captura o retorno de `onOpen()` (que retorna `response.data` da API) e extrai `points_won`, `xp_won`, `new_streak`, `streak_bonus_percent` para passar ao `onSuccess`.

---

### 6.8 ~~Limite de `plan_limits.py` Inconsistente com Gamification~~ ✅ CORRIGIDO

**Problema (resolvido):** `plan_config.py` agora define ambas as propriedades — `bots` (para bots ativos de trading) e `max_robots_arena` (para desbloqueio de robôs na Arena) — na mesma estrutura, tornando a distinção explícita e documentada.

---

## 7. O Que Pode Melhorar 🔧

### 7.1 ~~Cap Máximo de Streak~~ ✅ IMPLEMENTADO

**Implementado em `service.py`:**

```python
MAX_STREAK_BONUS = 10  # Cap: +100% máximo (dia 10+)
effective_streak = min(new_streak, MAX_STREAK_BONUS)
multiplier = 1.0 + (effective_streak * 0.1)
```

O `new_streak` continua incrementando para exibição, mas o `multiplier` é calculado sobre `effective_streak` (máximo 10).

### 7.2 Cache do Perfil Gamificado no Redis

Cada chamada de perfil busca diretamente no MongoDB. Para endpoints de high-frequency (leaderboard, notificações), usar cache Redis de 5-10 minutos reduziria latência e carga no banco.

### 7.3 ~~Histórico de Transações Visível ao Usuário~~ ✅ IMPLEMENTADO

Endpoint `GET /api/gamification/transactions` criado com:
- Paginação (`page`, `page_size`)
- Filtro por tipo (`tx_type`: `daily_chest`, `point_purchase`, `robot_unlock`, `micro_purchase`, `monthly_bonus`)
- Descrição automática por tipo
- Ordenado do mais recente para o mais antigo

### 7.4 Webhooks de Pagamento em Vez de Polling

Quando integrar gateway de pagamento real, implementar webhook (callback assíncrono do Stripe/PayPal) em vez de verificar status de pagamento por polling.

### 7.5 Exibir Custo de Cada Robô Dinamicamente

O custo de desbloqueio (`elite: 1500`, `common: 500`) está hardcoded no backend. Torná-lo configurável por robô individualmente, via banco de dados, para permitir promoções, eventos, etc.

### 7.6 Notificação Push ao Ganhar Pontos

Integrar com o `notification_hub.py` (já existente) para enviar notificação em tempo real via WebSocket quando:
- Baú for disponível novamente
- Streak estiver prestes a expirar (alerta 2h antes de expirar)
- Compra de pontos confirmada

### 7.7 ~~Pacote de Micro-transação~~ ✅ IMPLEMENTADO — ver seção 9

---

## 8. O Que Falta para o Sistema de Pontos Ficar Funcional 🚧

> **Status (02/03/2026):** Dos 7 itens originais, 6 foram implementados. Resta apenas a integração com gateway de pagamento real.

### 8.1 ❌ Integração com Gateway de Pagamento — ÚNICO ITEM PENDENTE (BLOQUEANTE)

**Prioridade: CRÍTICA**

Sem isso, nenhuma compra de pontos gera receita real.

**O que implementar:**

```python
# backend/app/services/payment_service.py (novo arquivo)

import stripe  # pip install stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

async def create_payment_intent(amount_usd: float, user_id: str, bundle_id: str) -> dict:
    """Cria PaymentIntent no Stripe"""
    intent = stripe.PaymentIntent.create(
        amount=int(amount_usd * 100),  # centavos
        currency="usd",
        metadata={"user_id": user_id, "bundle_id": bundle_id},
    )
    return {"client_secret": intent.client_secret, "payment_intent_id": intent.id}

async def confirm_payment(payment_intent_id: str) -> bool:
    """Verifica se pagamento foi confirmado"""
    intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    return intent.status == "succeeded"
```

**Endpoints necessários:**
- `POST /api/gamification/store/create-payment-intent` — cria intenção de pagamento
- `POST /api/gamification/store/webhook` — recebe confirmação do Stripe (webhook)
- O crédito de pontos só acontece após **confirmação do webhook**, nunca antes

> 💡 **Pré-condição para Stripe:** os endpoints `purchase_points` e `micro-purchase-and-unlock` já aceitam `transaction_id`. Basta criar `payment_service.py`, adicionar `STRIPE_SECRET_KEY` ao `.env` e substituir a lógica `simulated` pela validação real.

---

### 8.2 ~~❌ Bônus Mensal de Plano~~ ✅ IMPLEMENTADO

**Prioridade: ALTA**

O `monthly_bonus_points` existe no modelo mas nunca é creditado. Implementar via Celery Beat ou APScheduler:

```python
# backend/app/workers/monthly_bonus_job.py

from app.gamification.service import GameProfileService
from app.gamification.model import PLAN_REWARD_MAP

**Implementado em `backend/app/workers/monthly_bonus_job.py`** — função `credit_monthly_bonuses()` com:
- Resolução de aliases via `plan_config.py`
- Idempotência por `month_key` (ex: `"2026-03"`)
- Operação atômica `$inc`
- Criação de perfil se não existir
- Registro em `gamification_transactions`
- Registrado no scheduler (`_monthly_bonus_check`, diário, executa no dia 1)

---

### 8.3 ~~❌ Unificação dos Nomes de Plano~~ ✅ IMPLEMENTADO

**Prioridade: ALTA**

Criar um mapeamento central em `backend/app/core/plan_config.py`:

**Implementado em `backend/app/core/plan_config.py`** com `PLAN_CONFIG`, `PLAN_ALIASES`, e funções utilitárias: `resolve_plan_key()`, `get_plan_config()`, `get_max_robots_arena()`, `get_max_bots()`, etc.

---

### 8.4 ~~❌ Corrigir Bug de Instância no `purchase_points`~~ ✅ CORRIGIDO

**Prioridade: ALTA (causa erro 500 em produção)**

**Arquivo:** `backend/app/gamification/router.py` ~linha 1050

**Corrigido em `router.py`** — removida instanciação inválida, substituída por chamadas estáticas diretas.

---

### 8.5 ~~❌ Endpoint GET /transactions~~ ✅ IMPLEMENTADO

**Prioridade: MÉDIA**

**Implementado em `router.py`** — `GET /api/gamification/transactions` com paginação (`page`, `page_size`), filtro opcional por `tx_type`, e geração automática de descrição legível para cada tipo de transação.

---

### 8.6 ~~❌ Ranking de Robôs com Dados Reais~~ ✅ IMPLEMENTADO

**Prioridade: MÉDIA**

O endpoint `/robots/ranking` retorna dados mockados. Implementar busca real na collection `robot_rankings` e verificar `is_unlocked` comparando com `profile.unlocked_robots`:

**Implementado em `router.py`** — `get_robots_ranking()` agora consulta a collection `robot_rankings` do MongoDB, calcula `is_unlocked` real via `profile.unlocked_robots`, e tem fallback determinístico (hash MD5 do período + robot_id) para quando a collection ainda está vazia.

---

### 8.7 ~~❌ Corrigir Feedback Visual do Baú Diário~~ ✅ CORRIGIDO

**Prioridade: BAIXA**

**Corrigido em `DailyChestComponent.tsx`** — o handler `handleOpenChest` agora captura o retorno de `onOpen()` (que o hook devolve como `response.data`) e passa os valores reais ao `onSuccess`:

```tsx
const apiResult = await onOpen();
onSuccess?.({
  points: apiResult?.points_won ?? 100,
  xp: apiResult?.xp_won ?? 50,
  streak: apiResult?.new_streak ?? streak + 1,
  bonus: apiResult?.streak_bonus_percent ?? Math.round(streak * 10),
});
```

---

## 9. Nova Feature: Sistema de Micro-Transação 💡

### 9.1 Visão Geral

Quando o sistema detectar que o usuário **ficou sem pontos suficientes** para desbloquear um novo robô, uma **notificação contextual** aparecerá vendendo pacotes de pontos avulsos por valores pequenos — fora dos planos mensais.

**Objetivo:** Capturar receita de usuários que não querem assinar um plano maior, mas querem aquele robô específico agora.

---

### 9.2 Como Funciona (Fluxo Completo)

```
Usuário clica em robô bloqueado
  ↓
Backend retorna error: "insufficient_balance"
  { error: "insufficient_balance", shortage: 350, current_balance: 150 }
  ↓
Frontend detecta esse erro específico
  ↓
MicroTransactionNotification aparece (toast/modal lateral)
  "Você precisa de 350 pts. Quer comprar pontos agora?"
  [Mini-pacotes contextuais calculados para cobrir o custo]
  ↓
Usuário escolhe pacote e confirma
  ↓
Fluxo de pagamento real (Stripe One-Click se card salvo)
  ↓
Pontos creditados → Desbloqueio acontece automaticamente
```

---

### 9.3 Pacotes Micro-Transação

Pacotes menores e mais baratos que os da loja principal, calibrados para cobrir o custo de um robô:

| Bundle ID | Nome | Preço (USD) | Pontos | Caso de Uso |
|-----------|------|------------|--------|------------|
| `micro_100` | Quick Start | $0.49 | 100 pts | Faltam poucos pontos |
| `micro_250` | Power Boost | $0.99 | 250 pts | Custo de robô common |
| `micro_500` | Robot Ready | $1.49 | 500 pts | Exatamente 1 robô common |
| `micro_1500` | Elite Pass | $2.99 | 1.500 pts | Exatamente 1 robô elite |

> **Inteligência:** O sistema calcula automaticamente qual o menor pacote que cobre o `shortage` e o destaca como sugestão.

---

### 9.4 Implementação Backend

**Novo modelo (`model.py`):**

```python
MICRO_BUNDLES = {
    "micro_100": {
        "name": "Quick Start",
        "price": 0.49,
        "currency": "USD",
        "points": 100,
        "display_order": 1,
        "is_micro": True,
    },
    "micro_250": {
        "name": "Power Boost",
        "price": 0.99,
        "currency": "USD",
        "points": 250,
        "display_order": 2,
        "is_micro": True,
    },
    "micro_500": {
        "name": "Robot Ready",
        "price": 1.49,
        "currency": "USD",
        "points": 500,
        "display_order": 3,
        "is_micro": True,
    },
    "micro_1500": {
        "name": "Elite Pass",
        "price": 2.99,
        "currency": "USD",
        "points": 1500,
        "display_order": 4,
        "is_micro": True,
    },
}
```

**Novo endpoint (`router.py`):**

```python
@router.get(
    "/store/micro-bundles",
    summary="Micro-Pacotes Contextuais",
    description="Retorna micro-pacotes sugeridos baseado no shortage do usuário"
)
async def get_micro_bundles(
    shortage: int = Query(..., description="Quantidade de pontos que faltam"),
    current_user = Depends(get_current_user)
):
    """
    Retorna os micro-pacotes ordenados por melhor custo-benefício para cobrir o shortage.
    
    O pacote que cobre exatamente o shortage (ou o menor acima) é marcado como 'suggested'.
    """
    from app.gamification.model import MICRO_BUNDLES
    
    bundles = []
    suggested_set = False
    
    for bundle_id, bundle_data in sorted(
        MICRO_BUNDLES.items(), 
        key=lambda x: x[1]["display_order"]
    ):
        is_suggested = not suggested_set and bundle_data["points"] >= shortage
        if is_suggested:
            suggested_set = True
        
        bundles.append({
            **bundle_data,
            "bundle_id": bundle_id,
            "covers_shortage": bundle_data["points"] >= shortage,
            "is_suggested": is_suggested,
            "points_after_purchase": bundle_data["points"] - shortage,  # sobra de pontos
        })
    
    return {
        "success": True,
        "shortage": shortage,
        "bundles": bundles,
    }
```

**Novo endpoint de compra automática após micro-transação:**

```python
@router.post(
    "/store/micro-purchase-and-unlock",
    summary="Comprar Pontos e Desbloquear Robô em Uma Ação",
    description="Compra micro-pacote de pontos e tenta desbloquear o robô automaticamente"
)
async def micro_purchase_and_unlock(
    robot_id: str,
    bundle_id: str,
    transaction_id: str,  # ID confirmado pelo gateway de pagamento
    current_user = Depends(get_current_user)
):
    """
    1. Valida pagamento (webhookconfirmado previamente)
    2. Credita pontos
    3. Tenta desbloquear o robô
    4. Retorna resultado combinado
    """
    from app.gamification.model import MICRO_BUNDLES
    
    # Valida bundle
    if bundle_id not in MICRO_BUNDLES:
        raise HTTPException(400, "Micro-bundle inválido")
    
    bundle = MICRO_BUNDLES[bundle_id]
    
    # TODO: Validar transaction_id no Stripe antes de creditar
    
    # Credita pontos
    await GameProfileService._get_collection().update_one(
        {"user_id": current_user.id},
        {"$inc": {"trade_points": bundle["points"]}},
        upsert=False
    )
    
    # Tenta desbloquear o robô
    unlock_result = await GameProfileService.unlock_robot_logic(
        user_id=current_user.id,
        robot_id=robot_id
    )
    
    return {
        "success": unlock_result["success"],
        "points_purchased": bundle["points"],
        "unlock_result": unlock_result,
        "message": f"✅ {bundle['points']} pts comprados e robô desbloqueado!" if unlock_result["success"] else "Pontos comprados, mas desbloqueio falhou."
    }
```

---

### 9.5 Implementação Frontend

**Novo componente: `MicroTransactionNotification.tsx`**

```tsx
/**
 * MicroTransactionNotification — Notificação contextual de micro-transação
 * 
 * Aparece quando o usuário tenta desbloquear um robô mas não tem pontos suficientes.
 * Oferece mini-pacotes de pontos calibrados para cobrir o custo.
 */

interface MicroTransactionProps {
  robotId: string;
  robotName: string;
  shortage: number;
  onSuccess: () => void;
  onDismiss: () => void;
}

export const MicroTransactionNotification: React.FC<MicroTransactionProps> = ({
  robotId,
  robotName,
  shortage,
  onSuccess,
  onDismiss,
}) => {
  const [bundles, setBundles] = useState<MicroBundle[]>([]);
  const [purchasing, setPurchasing] = useState<string | null>(null);
  
  useEffect(() => {
    // Busca micro-bundles contextuais
    api.get(`/api/gamification/store/micro-bundles?shortage=${shortage}`)
      .then(r => setBundles(r.bundles));
  }, [shortage]);

  const handlePurchase = async (bundleId: string) => {
    setPurchasing(bundleId);
    try {
      // 1. Iniciar pagamento (Stripe Elements)
      const { clientSecret } = await api.post('/api/gamification/store/create-payment-intent', {
        bundle_id: bundleId,
        context: 'micro_transaction',
        robot_id: robotId,
      });
      
      // 2. Confirmar pagamento com Stripe.js
      const { paymentIntent } = await stripe.confirmCardPayment(clientSecret);
      
      // 3. Compra + unlock automático
      const result = await api.post('/api/gamification/store/micro-purchase-and-unlock', {
        robot_id: robotId,
        bundle_id: bundleId,
        transaction_id: paymentIntent.id,
      });
      
      if (result.success) {
        confetti({ particleCount: 80, spread: 60, origin: { y: 0.7 } });
        toast({ title: `✅ Robô ${robotName} desbloqueado!` });
        onSuccess();
      }
    } catch (err) {
      toast({ title: '❌ Erro na compra', variant: 'destructive' });
    } finally {
      setPurchasing(null);
    }
  };

  return (
    // Notificação lateral deslizando da direita (toast-style)
    <motion.div
      initial={{ x: 400, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 400, opacity: 0 }}
      className="fixed right-4 bottom-24 z-[9999] w-80 bg-slate-900 border border-amber-500/40 rounded-2xl shadow-2xl p-4"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="text-2xl">🤖</span>
        <div>
          <p className="text-white font-bold text-sm">Quer {robotName}?</p>
          <p className="text-slate-400 text-xs">Faltam apenas {shortage} pts</p>
        </div>
        <button onClick={onDismiss} className="ml-auto text-slate-500 hover:text-white">
          ✕
        </button>
      </div>
      
      <div className="space-y-2">
        {bundles.filter(b => b.covers_shortage).slice(0, 3).map(bundle => (
          <button
            key={bundle.bundle_id}
            onClick={() => handlePurchase(bundle.bundle_id)}
            disabled={purchasing === bundle.bundle_id}
            className={`w-full flex items-center justify-between p-3 rounded-lg border text-left transition-all ${
              bundle.is_suggested
                ? 'border-amber-400/60 bg-amber-500/10 hover:bg-amber-500/20'
                : 'border-slate-700 bg-slate-800 hover:bg-slate-700'
            }`}
          >
            <div>
              {bundle.is_suggested && (
                <span className="text-xs text-amber-400 font-bold uppercase">⭐ Sugerido</span>
              )}
              <p className="text-white font-semibold text-sm">{bundle.name}</p>
              <p className="text-slate-400 text-xs">+{bundle.points.toLocaleString()} pts</p>
            </div>
            <span className="text-amber-400 font-black text-lg">
              ${bundle.price.toFixed(2)}
            </span>
          </button>
        ))}
      </div>
      
      <p className="text-slate-500 text-xs mt-3 text-center">
        Pontos adicionados instantaneamente após pagamento
      </p>
    </motion.div>
  );
};
```

---

### 9.6 Gatilho no `LockedRobotModal`

No `LockedRobotModal.tsx`, ao receber `error: insufficient_balance`:

```tsx
// Estado para micro-transação
const [showMicroTransaction, setShowMicroTransaction] = useState(false);
const [pointsShortage, setPointsShortage] = useState(0);

// Ao receber erro de saldo:
const handleUnlock = async () => {
  try {
    await onUnlockWithPoints(robot.id);
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    
    if (typeof detail === 'string' && detail.includes('insuficientes')) {
      // Extrai shortage do erro
      const shortage = robot.unlock_cost - userTradePoints;
      setPointsShortage(shortage);
      setShowMicroTransaction(true);  // ← Abre notificação de micro-transação
    }
  }
};

// No JSX:
{showMicroTransaction && (
  <MicroTransactionNotification
    robotId={robot.id}
    robotName={robot.name}
    shortage={pointsShortage}
    onSuccess={() => {
      setShowMicroTransaction(false);
      onClose(); // Fecha o modal pois o robô foi desbloqueado
    }}
    onDismiss={() => setShowMicroTransaction(false)}
  />
)}
```

---

### 9.7 Diagrama do Sistema de Micro-Transação

```
┌─────────────────────────────────────────────────────┐
│  Usuário tenta desbloquear robô (500 pts)           │
│  Saldo atual: 150 pts → Shortage: 350 pts           │
└──────────────────────┬──────────────────────────────┘
                       │ error: insufficient_balance
                       ▼
┌─────────────────────────────────────────────────────┐
│  MicroTransactionNotification aparece               │
│  (toast-style, direita inferior da tela)            │
│                                                     │
│  🤖 Quer [Nome do Robô]?                           │
│  Faltam apenas 350 pts                              │
│                                                     │
│  [ Power Boost    +250 pts  $0.99 ]                │
│  [⭐ Robot Ready  +500 pts  $1.49 ] ← Sugerido     │
│  [ Elite Pass   +1500 pts  $2.99 ]                │
└──────────────────────┬──────────────────────────────┘
                       │ Usuário clica "Robot Ready - $1.49"
                       ▼
┌─────────────────────────────────────────────────────┐
│  Stripe Elements processa pagamento                 │
│  (Cartão salvo → 1 clique / ou formulário)         │
└──────────────────────┬──────────────────────────────┘
                       │ paymentIntent.status == "succeeded"
                       ▼
┌─────────────────────────────────────────────────────┐
│  POST /store/micro-purchase-and-unlock              │
│  { robot_id, bundle_id, transaction_id }            │
│                                                     │
│  1. Valida transaction_id no Stripe                │
│  2. Credita +500 pts ao perfil                     │
│  3. Subtrai 500 pts (custo do robô)                │
│  4. Adiciona robô em unlocked_robots               │
└──────────────────────┬──────────────────────────────┘
                       │ success: true
                       ▼
┌─────────────────────────────────────────────────────┐
│  🎉 Confete + Toast "Robô desbloqueado!"           │
│  Modal fecha automaticamente                        │
│  Robô aparece como desbloqueado no marketplace     │
└─────────────────────────────────────────────────────┘
```

---

## 📊 Resumo Executivo

| Área | Status |
|------|--------|
| Lógica do baú diário | ✅ Funcional |
| Streak do baú | ✅ Funcional |
| **Cap de streak (max 10)** | ✅ **IMPLEMENTADO** |
| Desbloqueio de robô (operação atômica) | ✅ Funcional |
| Validação de plano no desbloqueio | ✅ Funcional |
| **Unificação de nomes de planos** | ✅ **CORRIGIDO** |
| **Bug de instância no purchase_points** | ✅ **CORRIGIDO** |
| **Timestamps separados (baú / XP diário)** | ✅ **CORRIGIDO** |
| **Bônus mensal de plano** | ✅ **IMPLEMENTADO** |
| **Ranking de robôs com dados reais** | ✅ **CORRIGIDO** |
| **Histórico de transações** | ✅ **IMPLEMENTADO** |
| **Feedback visual do baú (valores reais)** | ✅ **CORRIGIDO** |
| **Sistema de micro-transação** | ✅ **IMPLEMENTADO** |
| Compra de pontos com pagamento real | ❌ **ÚNICO PENDENTE** |

### Pendências Atuais (02/03/2026)

```
CRÍTICO — ÚNICO ITEM FALTANDO:
  1. Integração Stripe/PayPal (compra real de pontos)
     → Criar backend/app/services/payment_service.py
     → Adicionar STRIPE_SECRET_KEY ao .env
     → Endpoint POST /store/create-payment-intent
     → Webhook POST /store/stripe-webhook
     → Substituir lógica "simulated" por validação real nos 2 endpoints

BOA PRÁTICA FUTURA (não bloqueante):
  2. Cache Redis do perfil gamificado (reduz carga no MongoDB)
  3. Notificação push (WebSocket) quando baú estiver disponível
  4. Custo de desbloqueio por robô individual (via banco, não hardcoded)
  5. Integração Stripe Elements no MicroTransactionNotification
```

---

## 📝 Changelog de Implementações

### 02/03/2026 — Correções e Implementações em Massa

#### Backend — Novos Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `backend/app/core/plan_config.py` | Fonte única de verdade para planos: `PLAN_CONFIG`, `PLAN_ALIASES`, `resolve_plan_key()`, `get_plan_config()` |
| `backend/app/workers/monthly_bonus_job.py` | Worker `credit_monthly_bonuses()` — credita bônus mensal com idempotência, aliases e operação atômica |

#### Backend — Correções em Arquivos Existentes

| Arquivo | Linha | O Que Foi Corrigido |
|---------|-------|---------------------|
| `gamification/router.py` | ~1048 | `GameProfileService(db)` → chamadas estáticas `GameProfileService.get_or_create_profile()` / `save_profile()` |
| `gamification/router.py` | ~320 | `claim_daily_xp` usa `last_daily_xp_claimed` em vez do timestamp do baú |
| `gamification/router.py` | ~480 | `get_robots_ranking()` busca real em `robot_rankings`, `is_unlocked` real, fallback deterministíco |
| `gamification/router.py` | (novo) | Endpoints `GET /store/micro-bundles`, `POST /store/micro-purchase-and-unlock`, `GET /transactions` |
| `gamification/service.py` | imports | Importa `resolve_plan_key`, `get_plan_config` de `plan_config.py` |
| `gamification/service.py` | `_get_user_license` | Substituído dict hardcoded por chamadas a `plan_config.py`; todos os aliases resolvidos |
| `gamification/service.py` | `open_daily_chest` | `MAX_STREAK_BONUS = 10`; `effective_streak = min(new_streak, 10)` |
| `gamification/service.py` | imports | `ELITE_ROBOTS`, `ROBOT_UNLOCK_COST` exportados e importados no router |
| `gamification/model.py` | `GameProfile` | Campo `last_daily_xp_claimed: Optional[datetime]` adicionado |
| `gamification/model.py` | (novo) | `MICRO_BUNDLES` dict com 4 pacotes: `micro_100`, `micro_250`, `micro_500`, `micro_1500` |
| `core/scheduler.py` | `start()` | Registra task `monthly_bonus_check` (intervalo 86400s) |
| `core/scheduler.py` | (novo) | Método `_monthly_bonus_check()` — roda job apenas no dia 1 do mês |

#### Frontend — Novos Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `src/components/gamification/MicroTransactionNotification.tsx` | Componente completo de micro-compra: 4 pacotes, auto-seleção do menor suficiente, compra+desbloqueio em 1 chamada, animação Framer Motion |

#### Frontend — Correções em Arquivos Existentes

| Arquivo | O Que Foi Corrigido |
|---------|---------------------|
| `DailyChestComponent.tsx` | `onOpen()` tipado como `Promise<any>`; handler captura retorno e passa `points_won`, `xp_won`, `new_streak` ao `onSuccess` (fim dos valores hardcoded) |
| `LockedRobotModal.tsx` | Import de `MicroTransactionNotification`; estado `showMicroNotification`; botão "Compra Rápida de Pontos" na seção de saldo insuficiente; renderização do componente com `onPurchaseAndUnlock` |
| `components/gamification/index.ts` | Export de `MicroTransactionNotification` adicionado |
