# 🗺️ MAPA DE INTEGRAÇÕES - Crypto Trade Hub

Visualização de como tudo está conectado (ou não) no sistema.

---

## 1️⃣ ARQUITETURA GERAL

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            USUÁRIO FINAL                                  │
│                        (Navegador Web)                                    │
└─────────────────────────────┬─────────────────────────────────────────────┘
                              │
                ┌─────────────┴──────────────┐
                │                            │
                ▼                            ▼
        ┌──────────────┐            ┌──────────────┐
        │   Frontend   │            │   Browser    │
        │  React 18.3  │            │Storage(LS)   │
        │ TypeScript   │───────────►│- access_token
        │              │            │- refresh_token
        └──────┬───────┘            │- user_data
               │                    └──────────────┘
               │ HTTP REST + WebSocket
               │
               ▼
        ┌──────────────────────────────────────────┐
        │          Backend (FastAPI)               │
        │        Python 3.11 + Pydantic v2         │
        │                                          │
        │  ├─ Authentication Router (/api/auth)   │
        │  ├─ Bot Router (/api/bots)              │
        │  ├─ Strategy Router (/api/strategies)   │
        │  ├─ Trading Router (/api/trading)       │
        │  ├─ Analytics Router (/api/analytics)   │
        │  ├─ Gamification Router (/api/game*)    │
        │  └─ ... (12 módulos total)              │
        │                                          │
        └──────┬───────────────────────────────────┘
               │
        ┌──────┴──────────────────────┐
        │                             │
        ▼                             ▼
    ┌────────────────┐        ┌──────────────────┐
    │   MongoDB      │        │   Redis Cache    │
    │   Atlas/Local  │        │   (Sessions,     │
    │                │        │    Ratings)      │
    │ Collections:   │        └──────────────────┘
    │ • users        │
    │ • bots         │
    │ • strategies   │
    │ • trades       │
    │ • game_profiles│◄─  ⚠️ PRECISA CRIAR
    │ • daily_chests │◄─  ⚠️ PRECISA CRIAR
    └────────────────┘
```

---

## 2️⃣ FLUXO DE AUTENTICAÇÃO

```
┌─────────────────┐
│  Login.tsx      │
│  Email + Pass   │
└────────┬────────┘
         │ POST /api/auth/login
         ▼
┌────────────────────────────┐
│  auth/router.py            │
│  @router.post("/login")    │
│  • Valida email/senha      │
│  • Compara bcrypt hash     │
│  • Gera JWT tokens         │
└────────┬───────────────────┘
         │ Response: {
         │   access_token,
         │   refresh_token,
         │   user: { id, email, name }
         │ }
         ▼
┌────────────────────────────┐
│  AuthContext.tsx           │
│  (Zustand Store)           │
│  • setTokens()             │
│  • setUser()               │
│  • isAuthenticated = true  │
└────────┬───────────────────┘
         │ Salva em localStorage
         │
         ▼
┌────────────────────────────┐
│  Próximos Requests         │
│  Header: Authorization:    │
│  Bearer {access_token}     │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────────────┐
│  useApi Hook (Interceptor)         │
│  • Adiciona Authorization header   │
│  • Renews token se expirado        │
│  • Redirect /login se 401          │
└────────────────────────────────────┘
```

---

## 3️⃣ FLUXO GAMIFICAÇÃO (ATUAL VS ESPERADO)

### ❌ ATUAL - Problema: Dados em localStorage, API não integrada

```
┌──────────────────────────┐
│  RobotsGameMarketplace   │
│  .tsx (Page)             │
└────────┬─────────────────┘
         │
         ├─────────────────────────────────────┐
         │                                     │
         ▼                                     ▼
┌──────────────────────┐            ┌─────────────────────────┐
│ GameProfileWidget    │            │ localStorage            │
│ (Mostra pontos/XP)   │            │ • game_cooldown apenas  │
│ (MOCK DATA)          │            │ • Dados não persistem!  │
└──────────────────────┘            └─────────────────────────┘
         │
         ├─ DailyChestButton
         │  • localStorage check cooldown
         │  ❌ NÃO CHAMA API
         │  ❌ Rewards não deduzem pontos
         │
         ├─ RobotMarketplaceCard (x20)
         │  • Mock data hardcoded
         │  └─ LockedRobotModal
         │     ❌ POST /unlock NÃO INTEGRADO
         │     ❌ Validação de plano falta
         │     ❌ Transação de pontos falta
         │
         └─ Top 3 Ranking
            ❌ seed_robots.py mockado
            ❌ Não atualiza com dados reais
```

### ✅ ESPERADO - Integração Completa

```
┌──────────────────────────────────────────────────────────────┐
│          RobotsGameMarketplace.tsx (Page)                   │
│                                                              │
│  useEffect(() => {                                          │
│    GET /api/gamification/game-profile  ◄─── API REAL ✅    │
│    GET /api/gamification/robots/ranking ◄── API REAL ✅    │
│  }, [])                                                     │
└──────────┬───────────────────────────────────────────────────┘
           │
    ┌──────┴──────────────────────────────────────────┐
    │                                                  │
    ▼                                                  ▼
┌──────────────────────┐                  ┌────────────────────────┐
│ GameProfileWidget    │                  │  Backend:              │
│ • Carrega pontos     │                  │  GET /game-profile     │
│  via API ✅          │                  │  ├─ Query MongoDB      │
│ • Mostra XP real     │                  │  ├─ Valida user        │
│ • Atualiza após ação │                  │  └─ Returns GameProfile
└──────────────────────┘                  └────────────────────────┘
    │
    ├─ DailyChestButton
    │  • POST /daily-chest/open ✅ (API real)
    │  ├─ Validação 24h cooldown no servidor
    │  ├─ Gera rewards dinâmicos
    │  ├─ Atualiza MongoDB
    │  └─ Retorna GameProfile com novos pontos
    │
    ├─ RobotMarketplaceCard (x20)
    │  • Dados de seed_robots (ainda mock, mas OK)
    │  │
    │  └─ LockedRobotModal
    │     • POST /api/gamification/robots/{id}/unlock ✅
    │     ├─ Validar plano (free=0, pro=5, etc)
    │     ├─ Verificar pontos suficientes
    │     ├─ Deduzir pontos (TRANSAÇÃO!)
    │     ├─ Add robot_id a user.bots_unlocked
    │     ├─ Atualizar MongoDB
    │     └─ Retorna sucesso + novo GameProfile
    │
    └─ Top 3 Ranking
       • GET /api/gamification/robots/ranking
       ├─ Query MongoDB robot_rankings
       ├─ Ordena por profit_15d
       ├─ Retorna top 3
       └─ Mostra com badges (🥇 🥈 🥉)
```

---

## 4️⃣ TABELA: PÁGINA vs ENDPOINT BACKEND

| Página | Componente | HTTP | Endpoint | Status | Notas |
|--------|-----------|------|----------|--------|-------|
| `/robots` | RobotsGameMarketplace | GET | `/api/gamification/game-profile` | ⚠️ Mock | Precisa GET real |
| `/robots` | GameProfileWidget | - | - | ✅ | Apenas exibe |
| `/robots` | DailyChestButton | POST | `/api/gamification/daily-chest/open` | ❌ | Que se integre! |
| `/robots` | RobotCard | GET | `/api/gamification/robots/ranking` | ⚠️ Mock | Dados são seed fixo |
| `/robots` | LockedRobotModal | POST | `/api/gamification/robots/{id}/unlock` | ❌ | Não existe! |
| `/leaderboard` | LeaderboardPage | GET | `/api/gamification/leaderboard` | ❌ | Falta criar |
| `/profile` | ProfilePage | GET | `/api/gamification/my-profile` | ❌ | Falta criar |

---

## 5️⃣ FLUXO DE DADOS: DAILY CHEST COMPLETO

### Cenário: User abre Daily Chest

```
1️⃣ FRONTEND (RobotsGameMarketplace.tsx)
   ├─ User clica em DailyChestButton
   └─ DailyChestButton.tsx:
      └─ onClick() →  POST /api/gamification/daily-chest/open
         ├─ Header: Authorization: Bearer <token>
         ├─ Body: {}
         └─ Loading = true

2️⃣ NETWORK
   ├─ Request vai para: http://localhost:8000/api/gamification/daily-chest/open
   └─ Backend recebe na router.py

3️⃣ BACKEND (gamification/router.py)
   ├─ @router.post("/daily-chest/open")
   ├─ Valida token via Depends(get_current_user)
   │  (auth/dependencies.py decodifica JWT)
   │
   ├─ Chama GameProfileService.open_daily_chest(user_id)
   │  ├─ Busca GameProfile em MongoDB
   │  ├─ Valida: last_opened_at > 24h atrás?
   │  ├─ Se NÃO: Retorna erro + tempo restante ❌
   │  │
   │  └─ Se SIM: ✅
   │     ├─ Gera rewards aleatórios
   │     │  ├─ XP: 10 + (5 × level)
   │     │  └─ Pontos: 50 + (100 × level)
   │     │
   │     ├─ Atualiza GameProfile MongoDB
   │     │  ├─ trade_points += points_reward
   │     │  ├─ current_xp += xp_reward
   │     │  ├─ total_xp += xp_reward
   │     │  ├─ daily_chest_streak += 1
   │     │  ├─ last_daily_chest_opened = now
   │     │  └─ Check level-up?
   │     │     ├─ Se current_xp >= xp_needed
   │     │     └─ level += 1, current_xp -= xp_needed
   │     │
   │     ├─ Cria DailyChest log
   │     │  ├─ user_id = current_user['_id']
   │     │  ├─ xp_reward = 25
   │     │  ├─ points_reward = 200
   │     │  ├─ opened_at = now
   │     │  └─ Salva em MongoDB
   │     │
   │     └─ Retorna Response:
   │        {
   │          "success": true,
   │          "game_profile": { ...atualizado... },
   │          "chest_reward": {
   │            "xp_reward": 25,
   │            "points_reward": 200,
   │            "level_up": false
   │          }
   │        }

4️⃣ NETWORK (Response volta)
   └─ Frontend recebe JSON response

5️⃣ FRONTEND (DailyChestButton.tsx)
   ├─ Response.success = true ✅
   ├─ Mostra confetti animation 🎉
   │
   ├─ Atualiza GameProfileWidget
   │  ├─ setGameProfile(response.game_profile)
   │  ├─ trade_points = 200 (novo)
   │  ├─ level = 5 (se fez level-up)
   │
   ├─ Mostra toast:
   │  "🎁 Baú aberto! +200 pontos +25 XP"
   │
   ├─ Desabilita botão por 24h
   │  └─ localStorage: next_chest_available = timestamp (24h futura)
   │
   └─ Loading = false

6️⃣ PRÓXIMA VEZ (dentro de 24h)
   ├─ User retorna para /robots
   ├─ DailyChestButton mostra countdown ⏱️
   │  └─ "Próximo baú em: 18h 32m"
   │
   └─ Botão desabilizado até countdown = 0
```

---

## 6️⃣ FLUXO DE DADOS: UNLOCK ROBÔ

### Cenário: User desbloqueia "Volatility Dragon" (500 pts)

```
1️⃣ FRONTEND (RobotsGameMarketplace.tsx)
   └─ RobotMarketplaceCard (Volatility Dragon)
      └─ onClick() → LockedRobotModal openDialog()

2️⃣ MODAL (LockedRobotModal.tsx)
   ├─ Mostra: "Volatility Dragon"
   ├─ Preço: 500 TradePoints
   ├─ Pontos atuais: 1200 (o suficiente ✅)
   │
   └─ User clica "Desbloquear"
      └─ POST /api/gamification/robots/bot_001/unlock
         ├─ Header: Authorization: Bearer <token>
         ├─ Body: { robot_id: "bot_001" }
         └─ Loading = true

3️⃣ BACKEND (gamification/router.py)
   ├─ @router.post("/robots/{robot_id}/unlock")
   ├─ Valida token → current_user
   │
   ├─ Valida robot_id existe?
   │  └─ Se NÃO: Return 404 ❌
   │
   ├─ Busca GameProfile(current_user)
   │  └─ Se NÃO: Return 404 ❌
   │
   ├─ VALIDAÇÃO DE PLANO (novo!)
   │  ├─ Checa user.license_type
   │  ├─ Free: max_bots = 0
   │  ├─ Pro: max_bots = 5
   │  ├─ Quant: max_bots = 10
   │  │
   │  └─ Count bots desbloqueados
   │     └─ Se >= max_bots: Return 403 ❌
   │        "Upgrade seu plano para desbloquear mais"
   │
   ├─ VALIDAÇÃO DE PONTOS
   │  ├─ robot_unlock_cost = 500
   │  ├─ user.trade_points = 1200
   │  │
   │  └─ Se pontos < custo: Return 402 ❌
   │     "Pontos insuficientes. Você precisa de 500 pontos"
   │
   ├─ ✅ TUDO OK - EXECUTAR TRANSAÇÃO
   │  │
   │  ├─ TRANSAÇÃO MONGODB (para evitar race condition)
   │  │  │
   │  │  ├─ Passo 1: Deduzir pontos
   │  │  │  └─ game_profiles.update({
   │  │  │      _id: user_id,
   │  │  │      trade_points: {$gte: 500}
   │  │  │    }, {
   │  │  │      $inc: { trade_points: -500 },
   │  │  │      $set: { updated_at: now }
   │  │  │    })
   │  │  │
   │  │  ├─ Passo 2: Adicionar robot à lista
   │  │  │  └─ game_profiles.update({
   │  │  │      _id: user_id
   │  │  │    }, {
   │  │  │      $push: { bots_unlocked: "bot_001" },
   │  │  │      $inc: { bots_unlocked_count: 1 }
   │  │  │    })
   │  │  │
   │  │  └─ Se algum falhar: ROLLBACK ↩️
   │  │     └─ Ambos falham ou nenhum
   │  │
   │  │
   │  ├─ Log de auditoria
   │  │  └─ audit.insert({
   │  │      user_id, action: "robot_unlock",
   │  │      robot_id, cost: 500, timestamp: now
   │  │    })
   │  │
   │  └─ Retorna Response:
   │     {
   │       "success": true,
   │       "message": "Robô desbloqueado com sucesso!",
   │       "game_profile": {
   │         "trade_points": 700,  ← 1200 - 500
   │         "bots_unlocked": 3,
   │         ...
   │       },
   │       "unlocked_robot": {
   │         "id": "bot_001",
   │         "name": "Volatility Dragon",
   │         ...
   │       }
   │     }

4️⃣ FRONTEND (LockedRobotModal.tsx)
   ├─ Response.success = true ✅
   │
   ├─ Mostra confetti 🎉
   ├─ Toast: "✅ Robô desbloqueado! Você agora tem acesso ao Volatility Dragon"
   │
   ├─ Atualiza GameProfileWidget
   │  └─ trade_points: 700 (novo, -500)
   │
   ├─ Atualiza card de robô
   │  ├─ is_locked = false
   │  └─ Mostra "DESBLOQUEADO ✅"
   │
   └─ Fecha modal

5️⃣ PERSISTÊNCIA
   ├─ MongoDB salvo ✅
   ├─ Dados persistem no reload ✅
   ├─ Próximo login carrega dados reais ✅
```

---

## 7️⃣ MATRIZ DE DEPENDÊNCIAS

```
          Frontend     Backend      Database    Externas
          ────────     ───────      ────────    ────────

Login  → AuthContext → auth/router → users     → Google OAuth
        → useApi      → JWT          collection
        
Dashboard → Dashboard → analytics   → trades   → TradingView
                        /router      collection  (gráficos)

RobotsGame → GameProfile → gamification/ → game_profiles → Mock data
            Widget        router           (NOVO!)
                                           
            → Daily       → gamification/ → daily_chests  (NOVO!)
              Chest         router
              Button
              
            → Robot       → gamification/ → robot_rankings
              Card Modal    router         (NOVO!)

MyStrategies → Strategy → strategies/ → strategies → N/A
              cards       router        collection

Licenses  → License    → license/ → users → Stripe (FALTA!)
            buttons      router     license
                                    (sub-doc)

Affiliate → Affiliate → affiliates/ → affiliates → N/A
            dashboard   router        collection
```

---

## 8️⃣ CHECKLIST DE INTEGRAÇÃO

### Backend
- [ ] GameProfile collection criada no MongoDB
- [ ] dailyChests collection criada
- [ ] robot_rankings collection criada
- [ ] POST /daily-chest/open implementado com transação
- [ ] POST /robots/{id}/unlock implementado com validação
- [ ] GET /leaderboard implementado
- [ ] APScheduler job atualiza rankings a cada 6h
- [ ] Validação de plano integrada nos endpoints
- [ ] Rate limiting configurado

### Frontend
- [ ] GET /game-profile chamado em useEffect
- [ ] POST /daily-chest/open chamado no handler
- [ ] POST /unlock chamado no modal
- [ ] Atualizações de estado refletem API response
- [ ] Erros tratados com mensagens amigáveis
- [ ] Transições suaves entre estados loading/success/error
- [ ] localStorage não sobrescreve API data

### Integração End-to-End
- [ ] Usuário faz login
- [ ] Página carrega game profile via API
- [ ] Abre daily chest → atualiza
- [ ] Desbloqueia robô → verifica pontos
- [ ] Reload não perde dados
- [ ] Outro user não vê dados first user

---

## 🎯 PRÓXIMAS AÇÕES

1. **Implementar BD:** Migrations MongoDB para game_profiles
2. **Backend:** POST /unlock e /daily-chest
3. **Frontend:** GET e updates via API
4. **Testes:** E2E login → unlock → reload → dados persistem
5. **Deploy:** Quando todos ✅ estiverem completos

