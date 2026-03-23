# ⚡ LISTA EXECUTIVA - O QUE FALTA

**Documento:** Priorização de tarefas para produção  
**Data:** 15/02/2026  
**Urgência:** CRÍTICA

---

## 📋 FALTA IMPLEMENTAR (25 itens)

### 🔴 CRÍTICO (Bloqueia deploy) - 10 itens

#### Backend (5)

- [ ] **1. Migrations MongoDB para GameProfile**
  - Collection: `game_profiles`
  - Campos: id, user_id, trade_points, level, xp, bots_unlocked, streak
  - Índices: user_id, created_at
  - **Estimativa:** 2h
  - **Arquivo:** `backend/app/gamification/migrations.py` (novo)

- [ ] **2. Seed GameProfile ao signup**
  - No `/api/auth/register`, criar GameProfile inicial
  - trade_points padrão: 500 (regalo boas-vindas)
  - **Estimativa:** 1h
  - **Arquivo:** `backend/app/auth/router.py` (modificar)

- [ ] **3. POST /api/gamification/robots/{robot_id}/unlock**
  - Validar pontos suficientes
  - Deduzir pontos (⚠️ com transação!)
  - Adicionar robot_id à lista de desbloqueados
  - Retornar GameProfile atualizado
  - **Estimativa:** 3h
  - **Arquivo:** `backend/app/gamification/router.py` (adicionar endpoint)

- [ ] **4. POST /api/gamification/daily-chest/open com backend**
  - Validar last_opened > 24h atrás
  - Gerar rewards baseado em level
  - Incrementar streak
  - Salvar em MongoDB
  - **Estimativa:** 2h
  - **Arquivo:** `backend/app/gamification/router.py` (modificar)

- [ ] **5. Job agendado: Atualizar RobotRanking**
  - APScheduler job a cada 6 horas
  - Recalcular profit_15d, win_rate, etc
  - Usar dados reais (integrar com app/bots ou app/trading)
  - **Estimativa:** 3h
  - **Arquivo:** `backend/app/core/scheduler.py` (adicionar job)

#### Frontend (5)

- [ ] **6. GET /api/gamification/game-profile em useEffect**
  - Chamar ao renderizar RobotsGameMarketplace
  - Salvar em componente state
  - Atualizar após ações (unlock, chest aberto)
  - **Estimativa:** 1h
  - **Arquivo:** `src/pages/RobotsGameMarketplace.tsx` (modificar)

- [ ] **7. POST /api/gamification/robots/{id}/unlock**
  - Integrar com LockedRobotModal
  - Validar resposta da API
  - Mostrar erro se falhar
  - Atualizar GameProfile local após sucesso
  - **Estimativa:** 2h
  - **Arquivo:** `src/components/gamification/LockedRobotModal.tsx` (modificar)

- [ ] **8. POST /api/gamification/daily-chest/open real**
  - Chamar endpoint real (não localStorage)
  - Remover cooldown timer localStorage
  - Mostrar confetti + toast de rewards
  - Atualizar GameProfileWidget
  - **Estimativa:** 2h
  - **Arquivo:** `src/components/gamification/DailyChestButton.tsx` (modificar)

- [ ] **9. Validação de plano antes de unlock**
  - Integrar useLicense() hook
  - Free: não pode desbloquear nada
  - Pro: máximo 3 (teste com 3 primeiros)
  - Mostrar mensagem: "Upgrade para desbloquear"
  - **Estimativa:** 1.5h
  - **Arquivo:** `src/components/gamification/RobotMarketplaceCard.tsx` (modificar)

- [ ] **10. Rate limiting no cliente (antes de chamar API)**
  - DailyChestButton: disable por 24h após abrir
  - Unlock: máximo 1 requisição ativa
  - Mostrar spinners durante loading
  - **Estimativa:** 1h
  - **Arquivo:** `src/components/gamification/*` (múltiplos)

---

### ⚠️ IMPORTANTE (1 semana) - 8 itens

#### Backend (4)

- [ ] **11. GET /api/gamification/leaderboard**
  - Retorna top 100 users by trade_points
  - Campos: rank, user_name, points, level, avg_win_rate
  - Paginação optional (limit, offset)
  - Cache Redis: TTL 1 hora
  - **Estimativa:** 3h
  - **Arquivo:** `backend/app/gamification/router.py`

- [ ] **12. GET /api/gamification/stats (dashboard admin)**
  - total_users
  - total_points_distributed
  - average_level
  - % opened_chest_today
  - most_unlocked_robot
  - **Estimativa:** 2h
  - **Arquivo:** `backend/app/gamification/router.py`

- [ ] **13. Integração trade real → game_points**
  - Quando `app/bots/service.py` executa trade com lucro
  - Disparar evento/callback
  - Adicionar X% do lucro como trade_points
  - Exemplo: +$100 lucro = +50 pontos
  - **Estimativa:** 4h
  - **Arquivo:** `backend/app/bots/service.py`, `backend/app/gamification/service.py`

- [ ] **14. Script migração de usuários antigos**
  - Para cada user na collection users
  - Criar GameProfile inicial
  - Seed: 500 pontos + level 1
  - Log execução
  - **Estimativa:** 2h
  - **Arquivo:** `scripts/migrate_game_profiles.py` (novo)

#### Frontend (4)

- [ ] **15. Página /leaderboard**
  - GET /api/gamification/leaderboard
  - Tabela ou cards com ranking
  - Destacar próprio position
  - Filtros: All time, 7d, 30d
  - **Estimativa:** 4h
  - **Arquivo:** `src/pages/Leaderboard.tsx` (novo)

- [ ] **16. Seção /profile melhorada**
  - Mostrar GameProfile detalhado
  - Histórico de Daily Chests abertos (últimos 30 dias)
  - Robôs desbloqueados com badges
  - Achievements/conquistas
  - **Estimativa:** 4h
  - **Arquivo:** `src/pages/Profile.tsx` (novo ou modificar Settings)

- [ ] **17. Sistema de Achievements/Badges**
  - Define 10-15 achievements (1º robô, nível 5, streak 7, etc)
  - Backend: Detectar quando atingir
  - Frontend: Toast + badge visual
  - Armazenar em MongoDB
  - **Estimativa:** 5h
  - **Arquivo:** `backend/app/gamification/achievements.py` (novo), front components

- [ ] **18. Sistema de Quests/Missões**
  - 5-10 quests simples (trade 10x, ganhe $10, etc)
  - Backend: Track progress
  - Frontend: UI para aceitar e completar
  - Rewards em pontos/XP
  - **Estimativa:** 6h
  - **Arquivo:** `backend/app/gamification/quests.py`, frontend components

---

### 📝 MENOR (2 semanas) - 7 itens

- [ ] **19. WebSocket para notificações real-time**
  - Broadcast: novo leader, achievement unlocked
  - Sync entre abas do navegador
  - **Estimativa:** 4h
  - **Arquivo:** `backend/app/websockets/`, frontend listeners

- [ ] **20. Integração com pagamento (Stripe/PagSeguro)**
  - Licenses.tsx → gateway real
  - Webhook de confirmação
  - Auto-add bonus pontos para plano pago
  - **Estimativa:** 8h
  - **Arquivo:** `backend/app/licensing/`, frontend checkout

- [ ] **21. Referral/Affiliate com bonus pontos**
  - Link único por user
  - Quando novo signup via link: +100 pontos referrer
  - **Estimativa:** 3h
  - **Arquivo:** `backend/app/affiliates/`

- [ ] **22. Data reais do RobotRanking**
  - Conectar com histórico de trades reais
  - Ao invés de seed_robots.py mockado
  - Ranking dinâmico baseado em performance
  - **Estimativa:** 5h
  - **Arquivo:** `backend/app/gamification/service.py`

- [ ] **23. Testes automáticos**
  - Unit tests: GameProfileService, mutations
  - Integration tests: API endpoints
  - E2E: Login → Unlock → Check persist
  - **Estimativa:** 6h
  - **Arquivo:** `tests/test_gamification_*.py`

- [ ] **24. Documentação Swagger**
  - Schemas para GameProfile, DailyChest, Robot
  - Exemplos de request/response
  - Descrições de campos
  - **Estimativa:** 2h
  - **Arquivo:** `backend/app/gamification/router.py` (adicionar docstrings)

- [ ] **25. Melhorias UX/Animações**
  - Level up animation melhorada
  - Particles more polished
  - Responsividade mobile
  - Tradução PT-BR completa
  - **Estimativa:** 4h
  - **Arquivo:** múltiplos componentes

---

## 📊 RESUMO DE ESFORÇO

| Categoria | Itens | Horas | Semanas |
|-----------|-------|-------|---------|
| Crítico | 10 | ~20h | ~2.5 dias |
| Importante | 8 | ~32h | ~1 semana |
| Menor | 7 | ~38h | ~1.5 semanas |
| **TOTAL** | **25** | **~90h** | **~4 semanas** |

---

## 🎯 FASE-POR-FASE DETALHADA

### ✅ FASE 1: PERSISTÊNCIA CRÍTICA (2-3 dias)
```
Prioridade:  Ítens 1-5 (backend) + 6-8 (frontend)
Objetivo:    Dados persistem no banco e API é chamada
Deliveráves: 
  - ✅ Tabelas MongoDB criadas
  - ✅ Endpoints /unlock e /daily-chest operando
  - ✅ Frontend carrega dados via API
  - ✅ Testes manuais ok
```

### ✅ FASE 2: VALIDAÇÕES & SEGURANÇA (2-3 dias)
```
Prioridade:  Itens 9-10 + rate limits
Objetivo:    Validar permissões, plano, frequência
Deliveráves:
  - ✅ Plano validation funcionando
  - ✅ Transações + rollback no MongoDB
  - ✅ Rate limiting implementado
  - ✅ Sem data leakage entre users
```

### ✅ FASE 3: FEATURES IMPORTANTES (1 semana)
```
Prioridade:  Itens 11-18
Objetivo:    Leaderboard, achievements, quests
Deliveráves:
  - ✅ GET /leaderboard ativo
  - ✅ Página /leaderboard rendendo
  - ✅ 10 achievements configurados
  - ✅ 5 quests básicas funcionando
```

### ✅ FASE 4: INTEGRAÇÃO COMPLETA (1.5 semanas)
```
Prioridade:  Itens 19-25
Objetivo:    WebSocket, pagamento, testes, docs
Deliveráves:
  - ✅ Notificações real-time
  - ✅ Pagamento integrado
  - ✅ Testes > 80% cobertura
  - ✅ Docs Swagger complete
  - ✅ Mobile responsivo
```

---

## 🚀 COMO COMEÇAR AGORA

### Dia 1 (Backend)
```bash
# 1. Criar migrations MongoDB
cd backend/app/gamification
# Criar arquivo migrations.py com collection schema

# 2. Update dependencies se precisar
pip install pymongo motor

# 3. Atualizar router para POST endpoints reais
cp router.py router.py.backup
# Editar router.py, implementar lógica de validação
```

### Dia 2 (Frontend)
```bash
# 1. Atualizar RobotsGameMarketplace.tsx
# Adicionar useEffect que chama GET /game-profile

# 2. Integrar POST /unlock em LockedRobotModal
# Substituir mock por chamada real

# 3. Testar fluxo: Frontend → API → MongoDB → Frontend
```

### Dia 3 (Testes)
```bash
# 1. Teste manual do fluxo completo
# 2. Check MongoDB documents foram criados
# 3. Validar autorização (outro usuário não vê dados)
# 4. Testes de erro (pontos insuficientes, etc)
```

---

## 📌 CHECKLIST PRÉ-DEPLOY

- [ ] Migrations MongoDB rodada com sucesso
- [ ] Todos endpoints retornam 200 em happy path
- [ ] Validações de plano funcionando (free não desbloqueia)
- [ ] Transações de pontos com rollback em erro
- [ ] Frontend carrega GameProfile ao abrir página
- [ ] Daily Chest cooldown respeitado (24h)
- [ ] Unlock persiste (reload da página, dados continuam)
- [ ] Rate limiting ativo
- [ ] Sem data leakage (user A não vê dados user B)
- [ ] Logging de todas transações de pontos
- [ ] Testes automatizados: >80% cobertura
- [ ] Docs Swagger atualizada
- [ ] Mobile testing feito (responsive)

---

## ⚠️ RISCOS CONHECIDOS

1. **Transações MongoDB sem suporte em free tier**
   - Solução: Usar transactions replicas ou sugarcoat
   
2. **Race condition: 2 daily chests no mesmo segundo**
   - Solução: Database lock com timestamp check
   
3. **Ranking recalculado muito frequente (cpu)**
   - Solução: Cache Redis com TTL vs job agendado

4. **Frontend offline: dados não salvam**
   - Solução: Queue local com IndexedDB + sync ao voltar online

5. **Pagamento não confirma: bonus pontos duplicados**
   - Solução: Webhook idempotent + unique payment IDs

---

## 📞 NEXT STEPS

1. **Próxima reunião:** Discutir prioridades (crítico só ou + importante também?)
2. **Task assignment:** Quem trabalha backend vs frontend?
3. **Timeline:** Quando precisa estar pronto? (MVP vs full release)
4. **Database:** Confirmar MongoDB Atlas access + credenciais
5. **Testing:** Ambiente de teste separado de produção?

---

**Status:** Uma análise e roadmap completo está em `ANALISE_COMPLETA_SISTEMA.md`.

