# 🏗️ ARQUITETURA: Autenticação e Estratégias

## Fluxo de Autenticação

```
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND (React)                                                │
│                                                                 │
│ 1. Login com email/senha ou Google                             │
│ 2. Recebe: access_token, refresh_token                         │
│ 3. Armazena em Zustand store                                   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ HTTP POST /api/auth/login
                 │ Body: { email, password }
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)                                               │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ app/auth/router.py                                          ││
│ │ @router.post("/login")                                      ││
│ │   → Valida email/senha                                      ││
│ │   → Gera JWT tokens                                         ││
│ │   → Retorna: { access_token, refresh_token }               ││
│ └─────────────────────────────────────────────────────────────┘│
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Retorna tokens
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND (React)                                                │
│ authStore.login(token)  ← Armazena token                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Próximo request (ex: GET /strategies/my)
                 │ Header: Authorization: Bearer {access_token}
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)                                               │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ app/auth/dependencies.py ← DEPENDÊNCIA CENTRALIZADA        ││
│ │                                                             ││
│ │ async def get_current_user(authorization: str = Header):  ││
│ │   1. Extrai token do header Authorization: Bearer          ││
│ │   2. Decodifica JWT (valida assinatura, expiração)        ││
│ │   3. Busca usuário no MongoDB com Motor (async)           ││
│ │   4. Retorna dict do usuário                              ││
│ │   5. Se erro: lança HTTPException (401, 404, 500)        ││
│ └─────────────────────────────────────────────────────────────┘│
│                        ▲                                        │
│                        │                                        │
│          Usado por TODOS estes routers:                        │
│          • app/strategies/router.py (via Depends)            │
│          • app/notifications/router.py (via Depends)         │
│          • app/trading/router.py (via Depends)               │
│          • app/main.py (endpoint /me)                        │
│                                                                │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ get_current_user retorna user dict
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ STRATEGY ENDPOINTS (exemplo GET /my)                            │
│                                                                 │
│ @router.get("/my")                                              │
│ async def get_my_strategies(                                    │
│     current_user: dict = Depends(get_current_user)            │
│ ):                                                              │
│   db = get_db()                                                │
│   strategies = db["strategies"].find({                         │
│       "user_id": str(current_user["_id"])  ← Do token!       │
│   })                                                            │
│   return strategies                                             │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Retorna: [{ id, name, is_public, ... }]
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND (React)                                                │
│ Exibe lista de estratégias do usuário                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Estrutura de Modelos (Pydantic v2)

```
┌──────────────────────────────────────────────────────┐
│ ENTRADA (StrategySubmitRequest)                      │
├──────────────────────────────────────────────────────┤
│ • name: str                                          │
│ • description: Optional[str]                         │
│ • parameters: Dict[str, Any]                         │
│ • is_public: bool                                    │
└────────────────┬─────────────────────────────────────┘
                 │
      POST /api/strategies/submit
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│ ARMAZENA NO BANCO (StrategyInDB)                     │
├──────────────────────────────────────────────────────┤
│ _id: ObjectId       ← MongoDB cria                   │
│ name: str                                            │
│ description: Optional[str]                           │
│ parameters: Dict                                     │
│ user_id: str        ← Extraído do token!            │
│ is_public: bool                                      │
│ created_at: datetime                                 │
│ updated_at: datetime                                 │
└────────────────┬─────────────────────────────────────┘
                 │
      GET /api/strategies/my
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│ RETORNA PARA API (StrategyResponse)                  │
├──────────────────────────────────────────────────────┤
│ JSON Response (via FastAPI):                         │
│ {                                                    │
│   "id": "507f1f77bcf86cd799439011",   ← _id aliased!│
│   "name": "Média Móvel",                             │
│   "description": "...",                              │
│   "parameters": {...},                               │
│   "user_id": "user123",                              │
│   "is_public": false,                                │
│   "created_at": "2026-02-05T10:30:00",              │
│   "updated_at": "2026-02-05T10:30:00"               │
│ }                                                    │
└──────────────────────────────────────────────────────┘

O alias "_id" ↔ "id" funciona transparentemente
graças ao model_config = { "populate_by_name": True }
```

---

## Ordem de Processamento de Rotas

```
Requisição: GET /api/strategies/my

FastAPI processa NESTA ORDEM:
┌─────────────────────────────────────────────────────┐
│ 1️⃣  GET  /public/list                               │
│     Match? "my" == "public/list"? NÃO               │
├─────────────────────────────────────────────────────┤
│ 2️⃣  GET  /my                                        │
│     Match? "my" == "my"? SIM! ✅                     │
│     Executa: get_my_strategies()                    │
└─────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────

Requisição: GET /api/strategies/507f1f77bcf86cd799439011

FastAPI processa NESTA ORDEM:
┌─────────────────────────────────────────────────────┐
│ 1️⃣  GET  /public/list                               │
│     Match? "507f..." == "public/list"? NÃO          │
├─────────────────────────────────────────────────────┤
│ 2️⃣  GET  /my                                        │
│     Match? "507f..." == "my"? NÃO                   │
├─────────────────────────────────────────────────────┤
│ 3️⃣  POST /submit                                    │
│     Match? GET != POST? NÃO                         │
├─────────────────────────────────────────────────────┤
│ 4️⃣  GET  /{strategy_id}                             │
│     Match? "507f..." == "{strategy_id}"? SIM! ✅    │
│     Executa: get_strategy(strategy_id="507f...")   │
└─────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────

Requisição: GET /api/strategies/public/list

FastAPI processa NESTA ORDEM:
┌─────────────────────────────────────────────────────┐
│ 1️⃣  GET  /public/list                               │
│     Match? "public/list" == "public/list"? SIM! ✅  │
│     Executa: get_public_strategies()                │
└─────────────────────────────────────────────────────┘

RESULTADO: ✅ Ordem correta evita conflitos!
```

---

## Fluxo de Segurança (ACL Pattern)

```
┌──────────────────────────────────────────────────┐
│ CLIENTE A                                        │
│ Token: user_id = "alice_123"                    │
│ Request: DELETE /api/strategies/strategy_xyz    │
└────────────┬─────────────────────────────────────┘
             │
             │ Validado em dependencies.py
             │ current_user._id = "alice_123"
             │
             ▼
┌──────────────────────────────────────────────────┐
│ BACKEND: delete_strategy()                       │
│                                                  │
│ strategies_col.delete_one({                      │
│     "_id": ObjectId("strategy_xyz"),             │
│     "user_id": "alice_123"  ← ACL: Só deleta    │
│ })                              se user_id ok!  │
│                                                  │
│ Resultado: deleted_count = 0                     │
│            (estratégia não pertence a alice)     │
│                                                  │
│ Resposta: 403 Forbidden                          │
└────────────┬─────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────┐
│ CLIENTE A                                        │
│ Recebe: 403 "Você não tem permissão"            │
│ ✅ Seguro! Não conseguiu deletar a strategy_xyz │
└──────────────────────────────────────────────────┘

─────────────────────────────────────────────────

VS. Se a estratégia FOSSE de alice_123:

┌──────────────────────────────────────────────────┐
│ CLIENTE A                                        │
│ Token: user_id = "alice_123"                    │
│ Request: DELETE /api/strategies/strategy_abc    │
│ (estratégia que alice criou)                    │
└────────────┬─────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────┐
│ BACKEND: delete_strategy()                       │
│                                                  │
│ strategies_col.delete_one({                      │
│     "_id": ObjectId("strategy_abc"),             │
│     "user_id": "alice_123"  ← Match! ✅          │
│ })                                               │
│                                                  │
│ Resultado: deleted_count = 1                     │
│            (deletado com sucesso)                │
│                                                  │
│ Resposta: 204 No Content                         │
└────────────┬─────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────┐
│ CLIENTE A                                        │
│ Recebe: 204 (sucesso)                           │
│ strategy_abc foi deletada ✅                     │
└──────────────────────────────────────────────────┘
```

---

## Arquivo de Dependência: Visão Geral

```
backend/app/auth/dependencies.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_current_user(authorization: str = Header(None)) -> dict:
    │
    ├─ 1. VALIDAÇÃO DO HEADER
    │  ├─ if not authorization: HTTPException(401)
    │  └─ if not authorization.startswith("Bearer "): HTTPException(401)
    │
    ├─ 2. EXTRAÇÃO DO TOKEN
    │  └─ token = authorization.replace("Bearer ", "")
    │
    ├─ 3. DECODIFICAÇÃO JWT
    │  ├─ payload = auth_service.decode_token(token)
    │  ├─ [Valida assinatura]
    │  ├─ [Valida expiração]
    │  └─ [Valida claims (iss, sub, etc)]
    │
    ├─ 4. EXTRAÇÃO DE USER_ID
    │  ├─ user_id = payload.get("sub")
    │  └─ if not user_id: HTTPException(401)
    │
    ├─ 5. BUSCA NO BANCO (ASYNC)
    │  ├─ db = get_db()
    │  ├─ user = await db["users"].find_one({
    │  │           "_id": ObjectId(user_id)
    │  │       })
    │  └─ [Motor driver: async/await]
    │
    ├─ 6. VALIDAÇÃO DE EXISTÊNCIA
    │  ├─ if not user: HTTPException(404)
    │  └─ [User não encontrado no banco]
    │
    ├─ 7. LOGGING
    │  └─ logger.debug(f"✓ User authenticated: {user['email']}")
    │
    └─ 8. RETORNO
       └─ return user  ← Disponível em todos os endpoints que usam Depends()
```

---

## Diagrama de Dependências (Import Graph)

```
┌──────────────────────────────────────────────────────────────┐
│ app/strategies/router.py                                     │
│                                                              │
│ from app.auth.dependencies import get_current_user  ✅      │
│ from app.strategies.models import StrategyResponse  ✅       │
│ from app.core.database import get_db  ✅                    │
└──────────────────────────────────────────────────────────────┘
          ↑
          │
          │ Depends(get_current_user)
          │
┌─────────┴──────────────────────────────────────────────────┐
│ app/auth/dependencies.py                                   │
│                                                            │
│ from app.core.database import get_db  ✅                  │
│ from app.auth import service as auth_service  ✅           │
└─────────┬──────────────────────────────────────────────────┘
          │
          ├─→ app/core/database.py (get_db)
          │
          ├─→ app/auth/service.py (decode_token)
          │
          ├─→ fastapi.Header (dependency injection)
          │
          └─→ bson.ObjectId (validação de ID)

✅ SEM IMPORTAÇÕES CIRCULARES!
```

---

## Checklist de Implementação

```
AUTENTICAÇÃO
┌─────────────────────────────────────────────┐
│ ✅ dependencies.py criado e funcional       │
│ ✅ Função é async (compatível com Motor)    │
│ ✅ Trata erros 401, 404, 500                │
│ ✅ Logging estruturado                      │
│ ✅ Type hints completos                     │
│ ✅ Headers validados                        │
│ ✅ JWT decodificado e validado              │
│ ✅ User buscado no MongoDB (await)          │
│ ✅ Sem importações circulares                │
│ ✅ Documentação clara                       │
└─────────────────────────────────────────────┘

MODELOS
┌─────────────────────────────────────────────┐
│ ✅ Pydantic v2 (model_config)               │
│ ✅ Field(alias="_id") em modelos com _id    │
│ ✅ populate_by_name = True                  │
│ ✅ from_attributes = True                   │
│ ✅ StrategySubmitRequest                    │
│ ✅ StrategyInDB                             │
│ ✅ StrategyResponse                         │
│ ✅ StrategyListItem                         │
│ ✅ Sem json_encoders (v2 nativa)            │
│ ✅ Documentação                             │
└─────────────────────────────────────────────┘

ROTAS
┌─────────────────────────────────────────────┐
│ ✅ /public/list (rota 1)                    │
│ ✅ /my (rota 2)                             │
│ ✅ /submit (rota 3)                         │
│ ✅ /{strategy_id} GET (rota 4)              │
│ ✅ /{strategy_id} PUT (rota 5)              │
│ ✅ /{strategy_id} DELETE (rota 6)           │
│ ✅ /{strategy_id}/toggle-public (rota 7)    │
│ ✅ Ordem correta (estáticas primeiro)       │
│ ✅ Sem conflitos                            │
│ ✅ Documentação e comentários               │
└─────────────────────────────────────────────┘

IMPORTS
┌─────────────────────────────────────────────┐
│ ✅ strategies/router.py                     │
│ ✅ notifications/router.py                  │
│ ✅ trading/router.py                        │
│ ✅ main.py                                  │
│ ✅ Todos usam dependencies.py               │
│ ✅ Sem duplicação                           │
│ ✅ Sem conflitos                            │
└─────────────────────────────────────────────┘
```

---

## Resultado Final

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  ✅ ARQUITETURA DE AUTENTICAÇÃO CENTRALIZADA        │
│                                                      │
│  • Dependência única: app/auth/dependencies.py      │
│  • Modelos Pydantic v2: modelo com alias            │
│  • Rotas em ordem correta: estáticas → dinâmicas    │
│                                                      │
│  🔒 SEGURANÇA                                       │
│  • Token validado em cada request                   │
│  • ACL via MongoDB query filter                     │
│  • user_id nunca é confiado no body                │
│  • Sem importações circulares                       │
│                                                      │
│  🚀 PRONTO PARA INTEGRAÇÃO COM FRONTEND             │
│                                                      │
└──────────────────────────────────────────────────────┘
```
