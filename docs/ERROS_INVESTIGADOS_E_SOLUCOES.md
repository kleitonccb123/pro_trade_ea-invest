# 🔴 RELATÓRIO COMPLETO DE ERROS — CryptoTradeHub Gamification
> Investigação realizada em 03/03/2026 | Backend FastAPI + SQLite | Frontend React/Vite

---

## 🚨 ERRO #1 — Custo do Robô: Frontend exibe 500 PTS, Backend cobra 1500 PTS

### Sintoma
Modal mostra **500 PTS** para Volatility Dragon (bot_001), mas ao confirmar aparece:
> "Saldo insuficiente. Você precisa de 1000 pontos a mais. (Saldo: 500)"

Isso revela que o backend está cobrando **1500 PTS** (elite), mas o frontend exibiu **500 PTS** (common).

### Causa Raiz
**Dupla definição de custo desincronizada:**

| Onde | Valor |
|------|-------|
| `src/pages/RobotsGameMarketplace.tsx` linha 78 | `unlock_cost: 500` |
| `backend/app/gamification/service.py` linha 35 | `'elite': 1500` |

O backend ignora o custo do frontend. `ELITE_ROBOTS = ['bot_001', 'bot_002', 'bot_003']` → sempre cobra 1500 para esses IDs.

O modal passa `unlockCost={selectedRobotForUnlock.unlock_cost}` → usa o valor da memória local (500), não consulta o backend antes de exibir.

### Arquivos Afetados
- `src/pages/RobotsGameMarketplace.tsx` (linhas 78, 95, 112 — bot_001/002/003)
- `backend/app/gamification/service.py` (linha 35)

### ✅ Solução
Alinhar os custos. Opção A (recomendada): atualizar o frontend para refletir os custos reais do backend:

```tsx
// src/pages/RobotsGameMarketplace.tsx
{ id: 'bot_001', unlock_cost: 1500, ... },  // era 500 → era ERRADO
{ id: 'bot_002', unlock_cost: 1500, ... },  // era 550 → era ERRADO
{ id: 'bot_003', unlock_cost: 1500, ... },  // era 600 → era ERRADO
```

Ou Opção B: manter 500 para todos e remover a distinção elite/comum no backend:
```python
# backend/app/gamification/service.py
ROBOT_UNLOCK_COST = { 'elite': 500, 'common': 500 }
```

---

## 🚨 ERRO #2 — Perfis de Gamificação se perdem ao reiniciar o servidor

### Sintoma
Após reiniciar o backend, o usuário perde:
- Todos os TradePoints acumulados
- Todos os robôs desbloqueados
- Histórico de streaks e conquistas

### Causa Raiz
A collection `game_profiles` usa `MockCollection` (dicionário em memória Python), **não SQLite nem MongoDB**. Ao reiniciar o processo, a RAM é liberada e todos os dados somem.

Confirmado nos logs:
```json
{"logger": "app.core.database", "event": "? MOCK SEARCH in game_profiles: query={'user_id': '847ea8ac-...'}"}
{"logger": "app.core.database", "event": "? MOCK NOT FOUND in game_profiles"}
```

Toda vez que o perfil não é encontrado, `get_or_create_profile()` cria um novo do zero (0 pontos, sem robôs desbloqueados).

### Arquivos Afetados
- `backend/app/core/database.py` — `MockCollection` class
- `backend/app/gamification/service.py` — `get_or_create_profile()`, `_get_collection()`

### ✅ Solução
Migrar `game_profiles` para SQLite (assim como `users` foi migrado). Criar tabela:

```sql
CREATE TABLE IF NOT EXISTS game_profiles (
    user_id TEXT PRIMARY KEY,
    trade_points INTEGER DEFAULT 500,
    level INTEGER DEFAULT 1,
    total_xp INTEGER DEFAULT 0,
    unlocked_robots TEXT DEFAULT '[]',  -- JSON array
    bots_unlocked INTEGER DEFAULT 0,
    daily_chest_streak INTEGER DEFAULT 0,
    last_daily_chest_opened TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

Adicionar `SQLiteGameProfileCollection` em `database.py` similar ao `SQLiteUserCollection` existente, e registrá-la no `MockDatabaseWithSQLite.__getitem__` para a chave `"game_profiles"`.

---

## 🟡 ERRO #3 — `strategy_manager_state` nunca persiste

### Sintoma
Nos logs, a cada chamada ao Strategy Manager:
```json
{"logger": "app.core.database", "event": "? MOCK NOT FOUND in strategy_manager_state"}
```

Estado do Strategy Manager sempre reseta ao recarregar a página.

### Causa Raiz
Mesma raiz do Erro #2: `strategy_manager_state` também usa `MockCollection`. Qualquer configuração salva existe apenas na sessão atual do servidor.

### Arquivos Afetados
- `backend/app/core/database.py`
- `backend/app/routers/strategy_manager.py` (ou similar)

### ✅ Solução
Mesma abordagem do Erro #2: criar tabela SQLite `strategy_manager_state` com JSON blob para persistir estado por usuário.

---

## 🟡 ERRO #4 — Codificação UTF-8 corrompida no router.py

### Sintoma
O arquivo `backend/app/gamification/router.py` contém caracteres garrafados em strings/comentários:
```python
"Desbloquear RobÃ´ com TradePoints"
"route /robots/{robot_id}/unlock"
"ðŸŽ® Gamification"
"LicenÃ§a insuficiente"
```

### Causa Raiz
O arquivo foi salvo/editado com encoding Latin-1 (Windows-1252) mas o Python o lê como UTF-8, resultando em double-encoding de caracteres acentuados e emojis.

### Efeito
- Logs e documentação da API (Swagger UI) mostram texto ilegível
- Potencial crash se alguma string corrompida for processada como bytes

### Arquivos Afetados
- `backend/app/gamification/router.py` (múltiplas linhas)

### ✅ Solução
Abrir o arquivo com encoding correto e re-salvar como UTF-8:
```powershell
$content = Get-Content -Path "backend/app/gamification/router.py" -Encoding Default
$content | Set-Content -Path "backend/app/gamification/router.py" -Encoding UTF8
```
Ou corrigir manualmente as strings corrompidas mais críticas.

---

## 🟡 ERRO #5 — Plano `free`/`starter` bloqueia 100% dos robôs (max_robots = 0)

### Sintoma (resolvido parcialmente)
Antes da correção aplicada nesta sessão, qualquer usuário recebia:
> "Upgrade necessário! Seu plano FREE não permite desbloqueio de robôs"

mesmo tendo plano BLACK ativo no banco de dados.

### Causa Raiz (RESOLVIDA)
`_get_user_license()` em `service.py` usava `ObjectId(user_id)` diretamente. No modo SQLite, o `user_id` é um UUID (ex: `847ea8ac-c138-4bdd-b589-0d07e4c878e9` — 36 chars), mas `ObjectId()` só aceita strings hex de 24 chars. A exceção era capturada silenciosamente retornando `plan: 'free', max_robots: 0`.

### Fix Aplicado
```python
# backend/app/gamification/service.py — _get_user_license()
try:
    query_id = ObjectId(user_id)
except Exception:
    query_id = user_id  # fallback para UUID string (SQLite)
user_doc = await db["users"].find_one({"_id": query_id})
```

### Status: ✅ CORRIGIDO — Confirmado nos logs:
```
ObjectId failed, using raw string query_id=847ea8ac-...
find_one result: found=True, plan=black
plan=enterprise (raw=black), max_robots=999
```

---

## 🔵 ERRO #6 — IDs de Robôs inconsistentes entre frontend e backend

### Sintoma
Testes de API no backend usaram IDs como `RSI_MASTER`, mas o frontend define IDs como `bot_005` (RSI Hunter Elite). O backend aceita qualquer string como robot_id sem validação.

### Causa Raiz
Não existe validação de ID de robô no backend. A lista canônica de IDs está apenas no frontend (`mockRobots` no RobotsGameMarketplace.tsx).

### Efeito
Um usuário pode "desbloquear" um robô com ID inventado (ex: `FAKE_BOT_999`) que não existe no marketplace — consumindo pontos sem benefício real.

### Arquivos Afetados
- `backend/app/gamification/service.py` — `unlock_robot_logic()` (sem lista de IDs válidos)
- `backend/app/gamification/router.py` — endpoint `/robots/{robot_id}/unlock`

### ✅ Solução
Adicionar validação de IDs no backend:
```python
# backend/app/gamification/service.py
VALID_ROBOT_IDS = {
    'bot_001', 'bot_002', 'bot_003', 'bot_004', 'bot_005',
    'bot_006', 'bot_007', 'bot_008', 'bot_009', 'bot_010',
    'bot_011', 'bot_012', 'bot_013', 'bot_014', 'bot_015',
    'bot_016', 'bot_017', 'bot_018', 'bot_019', 'bot_020',
}

# No início de unlock_robot_logic():
if robot_id not in VALID_ROBOT_IDS:
    return {
        'success': False,
        'error': 'invalid_robot',
        'message': f'Robô {robot_id} não existe no marketplace.',
    }
```

---

## 🔵 ERRO #7 — Encoding do banco de dados: `plan = 'black'` mas config retorna `'starter'` para aliases desconhecidos

### Sintoma
Se o banco tiver um plano com typo (ex: `blakc`, `BLACK`), `resolve_plan_key()` retorna `'starter'` silenciosamente.

### Causa Raiz
```python
# backend/app/core/plan_config.py
PLAN_ALIASES = {"black": "enterprise", "start": "starter", ...}
def resolve_plan_key(key: str) -> str:
    return PLAN_ALIASES.get(key.lower(), key)  # fallback para o próprio key
```
Se o alias não existe, retorna o key original. Depois `get_plan_config()` também falha silenciosamente e retorna config padrão.

### ✅ Solução
Adicionar log de aviso quando um plano desconhecido é recebido:
```python
def resolve_plan_key(key: str) -> str:
    resolved = PLAN_ALIASES.get(key.lower(), key.lower())
    if resolved not in PLAN_CONFIG:
        logger.warning(f"⚠️ Plano desconhecido: '{key}' → usando 'starter'")
        return 'starter'
    return resolved
```

---

## 📊 RESUMO DE PRIORIDADES

| # | Erro | Gravidade | Status | Impacto |
|---|------|-----------|--------|---------|
| 1 | Custo do robô: 500 vs 1500 PTS | 🔴 CRÍTICO | ✅ CORRIGIDO | Frontend alinhado: bot_001/002/003 → 1500 PTS |
| 2 | game_profiles em memória (dados somem) | 🔴 CRÍTICO | ✅ CORRIGIDO | SQLite: tabela `game_profiles` + `SQLiteGameProfileCollection` |
| 3 | strategy_manager_state não persiste | 🟡 MÉDIO | ✅ CORRIGIDO | SQLite: tabela `strategy_manager_state` + collection wrapper |
| 4 | UTF-8 corrompido em router.py | 🟡 MÉDIO | ✅ CORRIGIDO | Arquivo restaurado do VS Code history e mantido UTF-8 |
| 5 | Plano FREE bloqueando BLACK | 🔴 CRÍTICO | ✅ CORRIGIDO | ObjectId try/except fallback em `_get_user_license()` |
| 6 | IDs de robôs sem validação | 🔵 BAIXO | ✅ CORRIGIDO | `VALID_ROBOT_IDS` + validação em `unlock_robot_logic()` |
| 7 | Silêncio em planos com typo | 🔵 BAIXO | ✅ CORRIGIDO | `logger.warning()` em `resolve_plan_key()` para planos desconhecidos |

---

## 🚀 PLANO DE AÇÃO RECOMENDADO

1. **AGORA**: Corrigir custos dos robôs elite no frontend (Erro #1) — 5 min
2. **HOJE**: Migrar `game_profiles` para SQLite (Erro #2) — 2-3h
3. **HOJE**: Adicionar validação de robot_id (Erro #6) — 30 min
4. **AMANHÃ**: Migrar `strategy_manager_state` para SQLite (Erro #3) — 2h
5. **AMANHÃ**: Corrigir encoding do router.py (Erro #4) — 30 min
