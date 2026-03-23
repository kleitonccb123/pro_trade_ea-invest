/**
 * API_REFERENCE.md
 * 
 * Guia de Referência Rápida para APIs de Estratégias
 */

# API Reference - Sistema de Estratégias

## Base URL
```
Backend: http://127.0.0.1:8000
Frontend: http://localhost:5173
API Routes: /api/strategies
```

## 1. Listar Estratégias Públicas

### GET /api/strategies/public/list

**Autenticação:** ❌ Não requerida

**Parâmetros:**
- Nenhum

**Response (200 OK):**
```json
{
  "strategies": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "Estratégia Momentum",
      "description": "Segue momentum de 15 minutos",
      "user_id": "507f1f77bcf86cd799439010",
      "parameters": {
        "timeframe": "15m",
        "threshold": 0.02
      },
      "is_public": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Frontend Usage:**
```typescript
const { fetchPublicStrategies } = useStrategies();
const strategies = await fetchPublicStrategies();
```

---

## 2. Minhas Estratégias

### GET /api/strategies/my

**Autenticação:** ✅ Bearer Token Requerida

**Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

**Parâmetros:**
- Nenhum

**Response (200 OK):**
```json
{
  "strategies": [
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "Minha Estratégia",
      "description": "Estratégia pessoal",
      "user_id": "507f1f77bcf86cd799439010",
      "parameters": { ... },
      "is_public": false,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Erros:**
- `401 Unauthorized` - Token inválido ou ausente
- `500 Internal Server Error` - Erro ao buscar em MongoDB

**Frontend Usage:**
```typescript
const { strategies, fetchStrategies } = useStrategies();
useEffect(() => {
  fetchStrategies();
}, [fetchStrategies]);
```

---

## 3. Criar Estratégia

### POST /api/strategies/submit

**Autenticação:** ✅ Bearer Token Requerida

**Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Estratégia Nova",
  "description": "Descrição da estratégia",
  "parameters": {
    "timeframe": "15m",
    "threshold": 0.02,
    "custom_param": "any_value"
  },
  "is_public": true
}
```

**Validações:**
- `name` - Obrigatório, string, min 3 max 100
- `description` - Opcional, string, max 1000
- `parameters` - Obrigatório, objeto JSON
- `is_public` - Obrigatório, boolean

**Response (201 Created):**
```json
{
  "id": "507f1f77bcf86cd799439012",
  "name": "Estratégia Nova",
  "description": "Descrição da estratégia",
  "user_id": "507f1f77bcf86cd799439010",
  "parameters": { ... },
  "is_public": true,
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

**Erros:**
- `401 Unauthorized` - Token inválido
- `400 Bad Request` - Validação falhou
- `500 Internal Server Error` - Erro ao salvar

**Error Response (400):**
```json
{
  "detail": "1 validation error for StrategySubmitRequest\nname\n  String should have at least 3 characters"
}
```

**Frontend Usage:**
```typescript
const { createStrategy } = useStrategies();

const handleCreate = async (formData) => {
  await createStrategy({
    name: "Nova Estratégia",
    description: "Descrição",
    parameters: { timeframe: "15m" },
    is_public: true
  });
};
```

---

## 4. Atualizar Estratégia

### PUT /api/strategies/{strategy_id}

**Autenticação:** ✅ Bearer Token Requerida

**Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: application/json
```

**URL Parameters:**
- `strategy_id` - Obrigatório, ObjectId

**Request Body:**
```json
{
  "name": "Estratégia Atualizada",
  "description": "Descrição atualizada",
  "parameters": { ... },
  "is_public": false
}
```

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Estratégia Atualizada",
  "description": "Descrição atualizada",
  "user_id": "507f1f77bcf86cd799439010",
  "parameters": { ... },
  "is_public": false,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:30:00Z"
}
```

**Erros:**
- `401 Unauthorized` - Token inválido
- `403 Forbidden` - Não é o dono (ACL)
- `404 Not Found` - Estratégia não existe
- `400 Bad Request` - Validação falhou

**Frontend Usage:**
```typescript
const { updateStrategy } = useStrategies();

await updateStrategy(strategyId, {
  name: "Nova Nome",
  description: "Nova descrição",
  parameters: { ... },
  is_public: true
});
```

---

## 5. Deletar Estratégia

### DELETE /api/strategies/{strategy_id}

**Autenticação:** ✅ Bearer Token Requerida

**Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

**URL Parameters:**
- `strategy_id` - Obrigatório, ObjectId

**Response (200 OK):**
```json
{
  "message": "Estratégia deletada com sucesso",
  "deleted_id": "507f1f77bcf86cd799439011"
}
```

**Erros:**
- `401 Unauthorized` - Token inválido
- `403 Forbidden` - Não é o dono (ACL)
- `404 Not Found` - Estratégia não existe

**Frontend Usage:**
```typescript
const { deleteStrategy } = useStrategies();

await deleteStrategy(strategyId);
// Mostra confirmação antes de deletar no componente
```

---

## 6. Alternar Público/Privado

### POST /api/strategies/{strategy_id}/toggle-public

**Autenticação:** ✅ Bearer Token Requerida

**Headers:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

**URL Parameters:**
- `strategy_id` - Obrigatório, ObjectId

**Request Body:**
```json
{
  "is_public": true
}
```

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "Estratégia",
  "description": "...",
  "user_id": "507f1f77bcf86cd799439010",
  "parameters": { ... },
  "is_public": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:45:00Z"
}
```

**Erros:**
- `401 Unauthorized` - Token inválido
- `403 Forbidden` - Não é o dono
- `404 Not Found` - Estratégia não existe

**Frontend Usage:**
```typescript
const { toggleVisibility } = useStrategies();

await toggleVisibility(strategyId);
// Muda estado de is_public no backend
```

---

## 📋 Validações

### StrategySubmitRequest (Body Validation)

```python
{
  "name": str = Field(..., min_length=3, max_length=100),
  "description": Optional[str] = Field(default=None, max_length=1000),
  "parameters": dict = Field(default_factory=dict),
  "is_public": bool = Field(default=False)
}
```

### StrategyResponse (Database Model)

```python
{
  "id": str,  # ObjectId convertida para string
  "name": str,
  "description": Optional[str],
  "user_id": str,
  "parameters": dict,
  "is_public": bool,
  "created_at": datetime,
  "updated_at": datetime
}
```

---

## 🔐 Autenticação

### Bearer Token

Todas as requisições autenticadas precisam do header:
```
Authorization: Bearer <token_jwt>
```

**Formato do Token:**
- Tipo: JWT
- Alg: HS256 (HMAC com SHA-256)
- Issuer: Validado contra `GOOGLE_OAUTH_ISSUER`
- Expiração: Validada

**Onde obter o token:**
- Login com Google OAuth
- Armazenado em `localStorage.getItem('access_token')`
- Automaticamente adicionado pelo interceptor (axios)

### Exemplo de Decodificação (sem validação)

```bash
# Terminal
echo "eyJ0eXAiOiJKV1QiLCJhbGc..." | jq '.' 2>/dev/null | base64 -d

# Ou acesse: https://jwt.io (copie o token)
```

---

## 📊 Status Codes

| Code | Significado | Exemplo |
|------|-------------|---------|
| 200 | OK | GET bem-sucedido, atualização bem-sucedida |
| 201 | Created | POST bem-sucedido, estratégia criada |
| 400 | Bad Request | Validação falhou, payload inválido |
| 401 | Unauthorized | Token ausente ou inválido |
| 403 | Forbidden | Não tem permissão (ACL) |
| 404 | Not Found | Recurso não existe |
| 500 | Server Error | Erro no backend/MongoDB |

---

## 🧪 Exemplos cURL

### 1. Listar Públicas (sem auth)
```bash
curl -X GET http://127.0.0.1:8000/api/strategies/public/list
```

### 2. Minhas Estratégias (com auth)
```bash
TOKEN="eyJ0eXAi..."
curl -X GET http://127.0.0.1:8000/api/strategies/my \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Criar Estratégia
```bash
TOKEN="eyJ0eXAi..."
curl -X POST http://127.0.0.1:8000/api/strategies/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste",
    "description": "Test",
    "parameters": {"tf": "15m"},
    "is_public": true
  }'
```

### 4. Deletar Estratégia
```bash
TOKEN="eyJ0eXAi..."
STRATEGY_ID="507f1f77bcf86cd799439011"
curl -X DELETE http://127.0.0.1:8000/api/strategies/$STRATEGY_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🔍 Debugging

### Verificar Token no DevTools

1. Abra DevTools (F12)
2. Vá para Application → LocalStorage
3. Procure por `access_token`
4. Copie o valor
5. Cole em https://jwt.io
6. Verifique payload

### Verificar Requisição no DevTools

1. Abra DevTools (F12)
2. Vá para Network
3. Faça uma ação (criar, deletar, etc)
4. Procure pela requisição POST/DELETE
5. Vá para Headers
6. Verifique se tem `Authorization: Bearer ...`
7. Vá para Response
8. Verifique se é JSON válido

### Verificar Logs do Backend

```bash
# Terminal onde backend roda
# Você verá logs tipo:

INFO:     127.0.0.1:54321 - "GET /api/strategies/public/list HTTP/1.1" 200 OK
DEBUG:    User 507f1f77bcf86cd799439010 fetched strategies
ERROR:    user_id not found in token payload
```

---

## 📝 Notas Importantes

1. **CORS:** Backend precisa ter `allow_origins=["http://localhost:5173", "http://127.0.0.1:3000"]`
2. **MongoDB:** Estratégias são armazenadas em coleção `strategies`
3. **ACL:** `user_id` é extraído do JWT, nunca do request body
4. **Timestamps:** Automáticos, setados no backend (não envie cliente)
5. **Armazenamento:** localStorage via Zustand/AuthContext

---

## 🚀 Próximas APIs

Após estratégias, implementar:
- [ ] Binance API Keys (AES encryption)
- [ ] Trading/Backtest
- [ ] Analytics
- [ ] Notifications
- [ ] Webhooks

---

**Referência Completa!** 📚

Para mais detalhes, veja os arquivos:
- `backend/app/strategies/router.py` - Implementação backend
- `src/hooks/useStrategies.ts` - Hook frontend
- `src/types/strategy.ts` - Tipos TypeScript
