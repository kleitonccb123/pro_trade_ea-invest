# 🔧 Guia de Troubleshooting: Autenticação e Estratégias

## Problemas Comuns e Soluções

---

## 1️⃣ Erro: "ImportError: cannot import name 'get_current_user'"

### Sintoma:
```
ImportError: cannot import name 'get_current_user' from 'app.auth.router'
```

### Causa:
Código ainda está tentando importar de `router.py` em vez de `dependencies.py`

### Solução:
```python
# ❌ ERRADO (antiga)
from app.auth.router import get_current_user

# ✅ CORRETO (nova)
from app.auth.dependencies import get_current_user
```

### Arquivos que precisam ser verificados:
- `backend/app/strategies/router.py` (linha ~8)
- `backend/app/notifications/router.py` (linha ~12)
- `backend/app/trading/router.py` (linha ~10)
- `backend/app/main.py` (linha ~20)

---

## 2️⃣ Erro: "TypeError: object dict can't be used in 'await' expression"

### Sintoma:
```
TypeError: object dict can't be used in 'await' expression
app/auth/dependencies.py, line XX in get_current_user
```

### Causa:
Está usando `get_db()` que retorna **sync** client, mas tentando usar `await`

### Solução:

#### Verificar tipo de database:
```bash
# Check backend/.env
grep -i "DATABASE_URL" .env

# Se for MongoDB Atlas ou local:
# DATABASE_URL=mongodb+srv://...  → Motor (async)
# DATABASE_URL=mongodb://localhost → Motor (async)
```

#### O código ja está correto em dependencies.py:
```python
# ✅ Está usando await corretamente
db = get_db()
user = await db["users"].find_one({"_id": ObjectId(user_id)})
```

#### Se ainda der erro, verificar get_db():
```python
# Em backend/app/core/database.py
from motor.motor_asyncio import AsyncClient, AsyncDatabase

_mongodb_client: Optional[AsyncClient] = None  # ← Motor é async
_mongodb_db: Optional[AsyncDatabase] = None

def get_db() -> AsyncDatabase:
    return _mongodb_db  # ← Retorna AsyncDatabase
```

---

## 3️⃣ Erro: "401 Unauthorized - Missing or invalid token format"

### Sintoma:
```json
{
  "detail": "Missing or invalid token format"
}
```

### Causa:
- Token não foi enviado no header
- Formato não é "Bearer <token>"

### Solução:

#### Verificar se token está sendo enviado:
```bash
# ❌ ERRADO: Sem header
curl http://localhost:8000/api/strategies/my

# ✅ CORRETO: Com Authorization header
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
     http://localhost:8000/api/strategies/my
```

#### Verificar formato do token:
```bash
# ❌ ERRADO
Authorization: eyJ0eXAiOiJKV1QiLCJhbGc...  # Sem "Bearer"

# ❌ ERRADO
Authorization: Token eyJ0eXAiOiJKV1QiLCJhbGc...  # "Token" em vez de "Bearer"

# ✅ CORRETO
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...  # Com "Bearer "
```

---

## 4️⃣ Erro: "401 Unauthorized - Invalid or expired token"

### Sintoma:
```json
{
  "detail": "Invalid or expired token"
}
```

### Causa:
- Token foi alterado/corrompido
- Token expirou
- Assinatura não bate

### Solução:

#### Obter novo token:
```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email":"user@test.com",
    "password":"password123"
  }'

# 2. Copia access_token da resposta

# 3. Usa token fresco
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/strategies/my
```

#### Verificar expiração:
```bash
# Decodificar JWT (não verifica assinatura, só visualiza)
# Online: https://jwt.io
# CLI:
python -c "
import json
import base64
token = 'eyJ0eXAiOiJKV1QiLCJhbGc...'
parts = token.split('.')
payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
print(json.dumps(payload, indent=2))
"
```

#### Check if token expired:
```python
# Em backend/app/auth/service.py
from datetime import datetime
from jose import JWTError, jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
            # jwt.decode automaticamente valida exp
        )
        return payload
    except JWTError as e:
        print(f"Token error: {e}")  # Verá "token expired" se expirou
        raise
```

---

## 5️⃣ Erro: "404 Not Found - User not found"

### Sintoma:
```json
{
  "detail": "User not found"
}
```

### Causa:
- Token é válido, MAS usuário não existe no banco
- Usuário foi deletado do banco mas token ainda é válido

### Solução:

#### Verificar se usuário existe:
```bash
# Verificar usuário no MongoDB
mongosh "mongodb://localhost:27017"
> use crypto_trade_hub
> db.users.findOne({ email: "user@test.com" })

# Se retornar null: usuário não existe
# Solução: fazer login novamente para recriar usuário
```

#### Recriar usuário:
```bash
# 1. Deletar token (será inválido)
# 2. Fazer signup/login novamente
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email":"user@test.com",
    "password":"password123"
  }'

# 3. Usar novo token
```

---

## 6️⃣ Erro: "403 Forbidden - Você não tem permissão"

### Sintoma:
```json
{
  "detail": "Você não tem permissão para visualizar esta estratégia."
}
```

### Causa:
- Estratégia é privada (is_public: false)
- Você não é o dono

### Solução:

#### Verificar proprietário:
```bash
# No MongoDB:
mongosh "mongodb://localhost:27017"
> use crypto_trade_hub
> db.strategies.findOne({ _id: ObjectId("...") })

# Verifica o campo user_id
# Compara com seu user_id (do token)
```

#### Testar com proprietário correto:
```bash
# 1. Login como dono original
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email":"alice@test.com",
    "password":"pass123"
  }' | jq -r '.access_token')

# 2. Agora consegue acessar
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/strategies/507f1f77bcf86cd799439011

# ✅ Retorna 200 (sucesso) e estratégia
```

---

## 7️⃣ Erro: "422 Unprocessable Entity - Validation error"

### Sintoma:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "name"],
      "msg": "ensure this value has at least 1 characters"
    }
  ]
}
```

### Causa:
- Dados enviados no body não validam contra modelo Pydantic
- Campo obrigatório ausente
- Tipo de dado errado

### Solução:

#### Verificar modelo esperado:
```bash
# Para POST /submit, espera StrategySubmitRequest:
{
  "name": "string",  # ← Obrigatório
  "description": "string",  # ← Opcional
  "parameters": {},  # ← Obrigatório (objeto)
  "is_public": false  # ← Opcional (default: false)
}

# ❌ ERRADO:
{
  "name": "",  # Vazio!
  "parameters": "invalid"  # Deveria ser objeto!
}

# ✅ CORRETO:
{
  "name": "Média Móvel",
  "description": "Estratégia de média móvel",
  "parameters": {"short": 9, "long": 21},
  "is_public": false
}
```

#### Testar com cURL:
```bash
TOKEN="..." # Seu token

curl -X POST http://localhost:8000/api/strategies/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Minha Estratégia",
    "description":"Uma estratégia simples",
    "parameters":{"key":"value"},
    "is_public":false
  }'

# Deve retornar: 201 Created com a estratégia criada
```

---

## 8️⃣ Erro: "Rotas estáticas não estão funcionando"

### Sintoma:
```
GET /api/strategies/my → Retorna uma estratégia específica (errado)
GET /api/strategies/public/list → Não encontrado (errado)
```

### Causa:
Rotas estão em ordem errada (dinâmicas antes de estáticas)

### Solução:

#### Verificar ordem em router.py:
```python
# Linha de cada rota (use grep):
# grep -n "@router\." backend/app/strategies/router.py

# Deve estar NESTA ordem:
# 22: @router.get("/public/list")  ← PRIMEIRO
# 44: @router.get("/my")           ← SEGUNDO
# 68: @router.post("/submit")      ← TERCEIRO
# 109: @router.get("/{strategy_id}")  ← DEPOIS (dinâmica)
# 151: @router.put("/{strategy_id}")
# 213: @router.delete("/{strategy_id}")
```

#### Se estiver fora de ordem:
```bash
# Verificar visualmente em:
# backend/app/strategies/router.py

# Procure pelos comentários:
# # 1. GET /public/list
# # 2. GET /my
# # 3. POST /submit
# # 4. GET /{strategy_id}
# etc.

# Se não estiverem nesta ordem, o arquivo precisa ser reordenado
```

---

## 9️⃣ Erro: "Pydantic ValidationError com _id"

### Sintoma:
```
ValidationError: 1 validation error for StrategyResponse
_id
  Extra inputs are not permitted [type=extra_forbidden, input_value={'_id': Object...}]
```

### Causa:
Modelo não tem `populate_by_name=True` ou alias configurado

### Solução:

#### Verificar model_config:
```python
# Em backend/app/strategies/models.py
class StrategyResponse(BaseModel):
    id: str = Field(alias="_id")  # ← Alias configurado
    
    model_config = {
        "populate_by_name": True,  # ← OBRIGATÓRIO
        "from_attributes": True
    }

# Sem model_config, Pydantic nega "_id"
```

#### Verificar uso correto:
```python
# ✅ CORRETO: MongoDB retorna _id, Pydantic converte para id
mongo_doc = {"_id": ObjectId("..."), "name": "..."}
strategy = StrategyResponse(**mongo_doc)
print(strategy.id)  # "..." (string, convertida)

# Se quiser JSON com "_id":
response = strategy.model_dump(by_alias=True)
# {"_id": "...", "name": "..."}
```

---

## 🔟 Erro: "Circular import detected"

### Sintoma:
```
ImportError: cannot import name 'X' from partially initialized module 'app.auth.router'
```

### Causa:
- `router.py` importava de `dependencies.py`
- `dependencies.py` importava de `router.py`
- Circular loop

### Solução:
✅ **JÁ RESOLVIDO**: Criamos `dependencies.py` separado

```python
# Antes (circular):
# router.py → dependencies.py → router.py ❌

# Depois (linear):
# dependencies.py ← strategies/router.py ✅
# dependencies.py ← notifications/router.py ✅
# dependencies.py ← trading/router.py ✅
```

---

## 🧪 Teste Rápido: Validar Tudo

### Script de teste:
```bash
#!/bin/bash

echo "1. Testando importação de dependencies..."
python -c "from app.auth.dependencies import get_current_user; print('✅ OK')" || echo "❌ ERRO"

echo "2. Testando modelos..."
python -c "from app.strategies.models import StrategyResponse; print('✅ OK')" || echo "❌ ERRO"

echo "3. Testando router..."
python -c "from app.strategies.router import router; print('✅ OK')" || echo "❌ ERRO"

echo "4. Testando app..."
python -c "from app import main; print('✅ OK')" || echo "❌ ERRO"

echo "5. Testando rotas..."
python test_route_order.py 2>/dev/null | grep "✅ /public/list" && echo "✅ Rotas em ordem correta" || echo "❌ Rotas fora de ordem"
```

### Executar:
```bash
cd backend
bash test_everything.sh  # ou chmod +x + ./test_everything.sh
```

---

## 📞 Obter Logs para Debug

### Ativar logging detalhado:
```bash
# Em backend/.env, adicionar:
APP_LOG_LEVEL=DEBUG

# Ou alterar em backend/app/core/logging_config.py:
logging.basicConfig(level=logging.DEBUG)  # ← Antes era INFO
```

### Ver logs do servidor:
```bash
# Backend rodando com logs
cd backend
python -u run_server.py 2>&1 | grep -E "ERROR|DEBUG|auth|strategy"

# -u = unbuffered output
# 2>&1 = redireciona stderr para stdout
# grep = filtra apenas logs relevantes
```

### Ver logs de um request específico:
```bash
# Terminal 1: Backend com verbose logging
python -u run_server.py

# Terminal 2: Fazer request
curl -v -H "Authorization: Bearer invalid" \
     http://localhost:8000/api/strategies/my 2>&1

# -v = verbose (mostra headers)
# 2>&1 = captura stderr também
```

---

## 🆘 Pedir Ajuda

Se ainda não funcionar, colete:

```bash
# 1. Versão do Python
python --version

# 2. Pacotes instalados
pip list | grep -E "fastapi|pydantic|motor"

# 3. Logs de erro (últimas 50 linhas)
python run_server.py 2>&1 | tail -50

# 4. Estado do banco
mongosh "mongodb://localhost:27017" \
  -e "db.users.countDocuments()" \
  -e "db.strategies.countDocuments()"

# 5. Teste de imports
python -c "
from app.auth.dependencies import get_current_user
from app.strategies.models import StrategyResponse
from app.strategies.router import router
print('✅ All imports OK')
"
```

---

**Status: ✅ Troubleshooting completo pronto**

Se encontrar outro erro não listado, consulte logs com `-u` flag para debug detalhado.
