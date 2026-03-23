# 🧪 Guia de Testes - KuCoin Integration

## 🚀 Quick Start (5 minutos)

### 1️⃣ Teste de Criptografia

```bash
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.core.encryption
```

**Esperado:**
```
✅ Teste 1 passou: my-secret-api-key-12345... → encriptado → ✓
✅ Teste 2 passou: KuCoin (3 campos) → encriptados → ✓
✅ Teste 3 passou: Validação de entrada vazia ✓
🎉 Todos os testes de criptografia passaram!
```

---

### 2️⃣ Iniciar Servidores

**Terminal 1: Backend**
```bash
cd backend
.\.venv\Scripts\Activate.ps1
python run_server.py
```

Esperar por:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Terminal 2: Frontend**
```bash
npm run dev
```

Esperar por:
```
  VITE v5... ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  Press q to quit.
```

---

### 3️⃣ Login na Aplicação

1. Abrir http://localhost:5173
2. Clicar em "Login" ou "Signup"
3. Usar credenciais de teste ou criar conta
4. Esperar redirecionamento para `/dashboard`

---

### 4️⃣ Navegar para KuCoin

1. URL: http://localhost:5173/kucoin
2. Você verá o formulário com 4 campos

---

## 📝 Teste Manual (Com Dados Reais)

### Cenário 1: Conectar com Dados Válidos

1. Preencher formulário:
   ```
   API Key: 63d6ff48c50c8b7e85f55d3f (minimo 10)
   API Secret: c8a6b7e9-1f3a-4b5c-8d9e-0f1a2b3c4d5e (minimo 20)
   API Passphrase: myPassword123 (minimo 6)
   Modo Sandbox: ✓ ATIVADO
   ```

2. Clicar "Conectar KuCoin"

3. **Esperado:**
   - Notificação verde: "✅ KuCoin Conectada com Sucesso!"
   - Formulário desaparece
   - Mostra status: "KuCoin Conectada ✅"
   - Botão "Desconectar KuCoin"

4. **DevTools Verificação:**
   - F12 → Network
   - Procurar POST `/api/trading/kucoin/connect`
   - Status: 200 ou 201 ✓
   - Response:
     ```json
     {
       "id": "...",
       "user_id": "...",
       "is_active": true,
       "is_sandbox": true,
       "created_at": "2024-02-05T10:30:00Z"
     }
     ```
   - **NÃO contém:** api_secret, api_passphrase ✓

---

### Cenário 2: Validação de Input (Erro)

1. Tentar preencher com dados inválidos:
   ```
   API Key: abc (MENOS de 10 caracteres) ❌
   ```

2. Clicar "Conectar KuCoin"

3. **Esperado:**
   - Mensagem de erro abaixo do campo
   - Botão "Conectar" desativado (disabled)
   - Nenhuma requisição HTTP é enviada

---

### Cenário 3: Desconectar

1. Estando conectado, clicar "Desconectar KuCoin"

2. **Esperado:**
   - Confirmação: "Tem certeza que deseja desconectar KuCoin?"
   - Se OK:
     - Dados são deletados do MongoDB
     - Formulário reaparece vazio
     - Pode conectar novamente

---

## 🔍 Teste de Segurança

### Teste 1: Secrets Não Aparecem na Response

```bash
# Com curl
curl -X POST http://localhost:8000/api/trading/kucoin/connect \
  -H "Authorization: Bearer seu_token_aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "test_key_1234567890",
    "api_secret": "test_secret_1234567890abcd",
    "api_passphrase": "testpass123",
    "is_sandbox": true
  }'
```

**Verificar Response:**
- ✅ Contém: id, user_id, is_active, is_sandbox, created_at
- ❌ NÃO contém: api_secret, api_passphrase, api_key_enc

---

### Teste 2: Dados Encriptados no MongoDB

1. Conectar pelo formulário
2. Abrir MongoDB Atlas / MongoDB Compass
3. Verificar collection: `trading_credentials`
4. Verificar documento criado:
   ```json
   {
     "api_key_enc": "gAAAAABl_...",    // Encriptado com Fernet
     "api_secret_enc": "gAAAAABl_...", // Encriptado com Fernet
     "api_passphrase_enc": "gAAAAABl_..." // Encriptado com Fernet
   }
   ```

5. **Verificação:** Tente copiar `api_secret_enc` e descriptografar (vai falhar sem ENCRYPTION_KEY) ✓

---

### Teste 3: ACL (User Isolation)

1. Login com User A
2. Conectar KuCoin
3. Logout

4. Login com User B
5. Acessar `/kucoin`
6. **Esperado:** Formulário vazio (não vê credenciais de User A)

7. GET `/api/trading/kucoin/status` com User B:
   - Response: `{"connected": false, ...}`

8. Logout User B

9. Login com User A novamente
10. GET `/api/trading/kucoin/status`:
    - Response: `{"connected": true, ...}` ✓

---

## 🌐 Teste de Endpoints (Postman)

### Setup no Postman

1. Criar variável `auth_token`:
   - Copy token do localStorage após login
   - Ou use o token da response do login endpoint

2. Criar requests:

### Request 1: Conectar

```
Method: POST
URL: http://localhost:8000/api/trading/kucoin/connect
Headers:
  - Authorization: Bearer {{auth_token}}
  - Content-Type: application/json
Body (raw):
{
  "api_key": "63d6ff48c50c8b7e85f55d3f",
  "api_secret": "c8a6b7e9-1f3a-4b5c-8d9e-0f1a2b3c4d5e",
  "api_passphrase": "myPassword123",
  "is_sandbox": true
}
```

**Esperado:** 200/201

---

### Request 2: Verificar Status

```
Method: GET
URL: http://localhost:8000/api/trading/kucoin/status
Headers:
  - Authorization: Bearer {{auth_token}}
```

**Esperado:** 
```json
{
  "connected": true,
  "status": "success",
  "exchange_info": {
    "exchange": "KuCoin",
    "mode": "sandbox"
  }
}
```

---

### Request 3: Atualizar

```
Method: PUT
URL: http://localhost:8000/api/trading/kucoin/update
Headers:
  - Authorization: Bearer {{auth_token}}
  - Content-Type: application/json
Body:
{
  "is_active": true,
  "is_sandbox": false
}
```

**Esperado:** 200 com response atualizado

---

### Request 4: Desconectar

```
Method: DELETE
URL: http://localhost:8000/api/trading/kucoin/disconnect
Headers:
  - Authorization: Bearer {{auth_token}}
```

**Esperado:** 200
```json
{
  "status": "success",
  "message": "Credenciais KuCoin desconectadas com sucesso"
}
```

---

## 🐛 Troubleshooting

### Erro: "ENCRYPTION_KEY not in .env"

**Solução:**
```bash
# Gerar chave
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Adicionar ao .env
ENCRYPTION_KEY=resultado_da_linha_acima

# Reiniciar backend
```

---

### Erro: "Invalid token" ao descriptografar

**Causas:**
1. ENCRYPTION_KEY mudou
2. Dados foram corrompidos
3. Token inválido

**Solução:** 
- Usuário reconecta (novo documento criado)
- Ou restaurar ENCRYPTION_KEY anterior

---

### Erro: "401 Unauthorized"

**Causa:** Token JWT inválido ou expirado

**Solução:**
```bash
# Login novamente
# Copy novo token do localStorage
# Usar no Authorization header
```

---

### Erro: "MongoDB connection refused"

**Solução:**
```bash
# Verificar se MongoDB está rodando
# No .env, mudar OFFLINE_MODE=false para true se offline
# Ou usar local: DATABASE_URL=mongodb://localhost:27017
```

---

## ✅ Checklist de Testes

- [ ] Teste de criptografia (python -m app.core.encryption)
- [ ] Backend iniciando sem erros
- [ ] Frontend carregando sem erros
- [ ] Login funcionando
- [ ] Formulário KuCoin acessível
- [ ] Validação frontend (campo inválido)
- [ ] POST /kucoin/connect com dados válidos
- [ ] Response sem api_secret
- [ ] Dados encriptados no MongoDB
- [ ] GET /kucoin/status retorna connected=true
- [ ] Modo Sandbox toggle funciona
- [ ] PUT /kucoin/update funciona
- [ ] DELETE /kucoin/disconnect funciona
- [ ] ACL funciona (User A não vê credenciais de User B)
- [ ] Error handling (sem token, token inválido)
- [ ] Notificações (sucesso, erro, confirmação)

---

## 🚀 Status

**Tudo pronto para usar!** 

Próximo passo: Implementar trading real com KuCoin SDK
```python
client = Client(api_key=..., secret=..., passphrase=..., sandbox=True)
balance = client.get_account_balance()
```

---

**Data:** 5 Fevereiro 2026
**Status:** ✅ IMPLEMENTADO E TESTÁVEL
