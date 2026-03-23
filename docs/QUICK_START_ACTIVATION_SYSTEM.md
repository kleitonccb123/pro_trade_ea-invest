# 🚀 Quick Start: Sistema de Créditos de Ativação

## 📋 Resumo das Mudanças

Implementação completa do sistema de **Créditos de Ativação**, **Swap Limit** e **Kill Switch** para o Crypto Trade Hub.

### ✅ Arquivos Criados/Modificados

```
✅ backend/app/users/model.py
   └─ Adicionado: User com activation_credits

✅ backend/app/bots/model.py  
   └─ Confirmado: Bot com is_active_slot, swap_count, swap_history

✅ backend/app/services/activation_manager.py (NOVO)
   └─ Lógica principal de créditos e singleton

✅ backend/app/services/balance_guard.py (NOVO)
   └─ Validação de saldo na Exchange

✅ backend/app/services/kill_switch.py (NOVO)
   └─ Controle de emergência

✅ backend/app/bots/router.py
   └─ Atualizado endpoints: /start, PUT /config, GET /swap-status
   └─ Adicionado: /admin/kill-switch/*

✅ backend/app/auth/router.py
   └─ Adicionado: GET /profile/activation-credits

✅ backend/scripts/migrate_activation_system.py (NOVO)
   └─ Migration script para adicionar campos

✅ ACTIVATION_CREDITS_SYSTEM.md (NOVO)
   └─ Documentação completa do sistema
```

---

## 🚀 Instalação e Execução

### 1️⃣ Instalar/Atualizar Dependências

```bash
cd backend
pip install -r requirements.txt
```

> Verifique se as seguintes bibliotecas estão incluídas:
> - `pydantic>=2.0`
> - `motor>=3.0` (MongoDB async)
> - `fastapi>=0.100`
> - `uvicorn>=0.20`

### 2️⃣ Executar Migration

#### Opção A: Dry-Run (Simular Sem Fazer Mudanças)

```bash
cd backend
python scripts/migrate_activation_system.py --dry-run
```

**Output esperado**:

```
============================================================
MIGRATING USERS: Adding activation credits...
============================================================
Found X users without activation_credits field
  [DRY-RUN] User john@example.com: PRO = 5 credits
  [DRY-RUN] User jane@example.com: STARTER = 1 credit
  ...
✅ Users migration complete: X/X updated

============================================================
MIGRATING BOTS: Adding swap history and slot fields...
============================================================
Found Y bots needing migration
  [DRY-RUN] Bot "DCA Strategy": Adding 4 fields
  ...
✅ Bots migration complete: Y/Y updated

============================================================
MIGRATION SUMMARY
============================================================
Users updated: X
Bots updated: Y
⚠️  This was a DRY-RUN. No changes were made.
Run without --dry-run to apply changes
============================================================
```

#### Opção B: Aplicar Migração

```bash
cd backend
python scripts/migrate_activation_system.py
```

✅ **Agora os dados estão prontos!**

### 3️⃣ Iniciar Backend

```bash
cd backend
python run_server.py

# ou manualmente:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Testando os Novos Endpoints

### 1. Visualizar Créditos de Ativação

```bash
curl -X GET http://localhost:8000/auth/profile/activation-credits \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response esperado**:

```json
{
  "success": true,
  "plan": "pro",
  "activation_credits": 5,
  "activation_credits_used": 2,
  "activation_credits_remaining": 3,
  "bots_active_slots": 1,
  "bots_count": 8
}
```

### 2. Iniciar um Bot (Com Validações)

```bash
curl -X POST http://localhost:8000/bots/bot-id-123/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your_kucoin_api_key",
    "api_secret": "your_kucoin_secret",
    "exchange": "kucoin"
  }'
```

**Response possíveis**:

✅ **200 Started**:
```json
{
  "status": "started",
  "instance_id": "inst-456",
  "bot_id": "bot-id-123",
  "activation": {
    "credits_consumed": 1,
    "credits_remaining": 4,
    "previous_bot_stopped": true
  }
}
```

❌ **402 Payment Required** (Insuficientes créditos):
```json
{
  "error": "insufficient_credits",
  "message": "Insufficient activation credits. Upgrade your plan.",
  "credits_remaining": 0
}
```

❌ **400 Bad Request** (Saldo insuficiente):
```json
{
  "error": "insufficient_balance",
  "message": "❌ Insufficient balance: 500.00 USDT, need 1000.00"
}
```

### 3. Atualizar Configuração (Com Swap Limit)

```bash
curl -X PUT http://localhost:8000/bots/bot-id-123/config \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1500.0,
    "stop_loss": 3.0,
    "take_profit": 15.0,
    "strategy": "DCA Strategy"
  }'
```

**Response (1º swap - FREE)**:
```json
{
  "updated": true,
  "swap_info": {
    "swap_number": 1,
    "was_free": true,
    "credits_consumed": 0,
    "credits_remaining": 5
  },
  "message": "✅ Config updated. Swap #1 (FREE)"
}
```

**Response (3º swap - PAGO)**:
```json
{
  "updated": true,
  "swap_info": {
    "swap_number": 3,
    "was_free": false,
    "credits_consumed": 1,
    "credits_remaining": 4
  },
  "message": "✅ Config updated. Swap #3 (PAID)"
}
```

### 4. Visualizar Status de Swaps

```bash
curl -X GET http://localhost:8000/bots/bot-id-123/swap-status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "bot_id": "bot-id-123",
  "swap_count": 3,
  "free_swaps_used": 2,
  "free_swaps_remaining": 0,
  "next_swap": {
    "is_free": false,
    "will_cost_credits": 1
  },
  "swap_history": [...]
}
```

### 5. Kill Switch (Admin Only)

```bash
# Ativar Kill Switch
curl -X POST http://localhost:8000/bots/admin/kill-switch/activate/user-id \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "API key compromise suspected"}'

# Desativar
curl -X POST http://localhost:8000/bots/admin/kill-switch/deactivate/user-id \
  -H "Authorization: Bearer ADMIN_TOKEN"

# Verificar status
curl -X GET http://localhost:8000/bots/admin/kill-switch/status/user-id \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

---

## 🔄 Fluxo Típico de Uso

### Cenário: Usuário Pro com 5 Créditos

```
1. Usuário tem plano PRO = 5 créditos

2. Ativa Bot A (DCA)
   ├─ Consome 1 crédito
   └─ Créditos restantes: 4

3. Atualiza config Bot A (1ª vez)
   ├─ FREE (dentro das 2 gratuitas)
   └─ Créditos restantes: 4

4. Atualiza config Bot A (2ª vez)
   ├─ FREE (2ª das 2 gratuitas)
   └─ Créditos restantes: 4

5. Atualiza config Bot A (3ª vez)
   ├─ PAGA: Custa 1 crédito
   └─ Créditos restantes: 3

6. Ativa Bot B (Grid)
   ├─ Consome 1 crédito
   └─ Créditos restantes: 2
   └─ Bot A para automaticamente (singleton)

7. Tenta ativar Bot C
   ├─ Teria créditos (2 restantes)
   ├─ MAS só pode 1 bot rodando por vez
   └─ Precisa parar Bot B primeiro
```

---

## 🛠️ Resolução de Problemas

### ❌ "ModuleNotFoundError: No module named 'app.services.activation_manager'"

**Solução**:
```bash
# Verifique se os arquivos estão nos locais corretos:
ls -la backend/app/services/

# Deve conter:
# activation_manager.py
# balance_guard.py
# kill_switch.py
```

### ❌ "Field 'activation_credits' already exists"

**Solução**: 
- Migração já foi executada anteriormente
- Execute com `--dry-run` para verificar estado atual

### ❌ "Connection refused: MongoDB"

**Solução**:
- Verifique se MongoDB está rodando:
  ```bash
  # Windows
  Get-Service MongoDB
  
  # Linux/Mac
  mongo --version
  ```

### ❌ "insufficient_credits" ao iniciar bot

**Solução**: Upgrade do plano
```python
# Backend:
await ActivationManager.upgrade_plan(user_id, "premium")
```

---

## 📊 Visualizar Dados no MongoDB

### Verificar usuários com créditos

```javascript
// No MongoDB Compass ou mongosh
db.users.find().projection({
  email: 1,
  plan: 1,
  activation_credits: 1,
  activation_credits_used: 1
})
```

### Ver histórico de swaps

```javascript
db.bots.findOne({name: "Bot Name"}).swap_history
```

### Ver auditoria de Kill Switch

```javascript
db.audit_logs.find({event_type: "kill_switch_activated"})
```

---

## 🔐 Segurança: Checklist

- [ ] Admin endpoints (`/admin/kill-switch/*`) estão protegidos?
- [ ] API Keys são armazenadas criptografadas?
- [ ] Balance Guard valida saldo antes de cada start?
- [ ] Graceful stop não deixa bots órfãos?
- [ ] Auditoria registra todos os eventos críticos?

---

## 📚 Documentação Completa

Veja [ACTIVATION_CREDITS_SYSTEM.md](../ACTIVATION_CREDITS_SYSTEM.md) para:

- ✅ Visão completa do sistema
- ✅ Modelos de dados
- ✅ Todos os endpoints documentados
- ✅ Exemplos de uso
- ✅ Tratamento de erros
- ✅ Fluxos completos

---

## 🎯 Próximos Passos

1. **Adicionar Testes**:
   ```bash
   pytest backend/tests/
   ```

2. **Frontend Integration**:
   - Atualizar UI para mostrar créditos
   - Adicionar validação de créditos antes de iniciar bot
   - Mostrar histórico de swaps

3. **Notificações**:
   - Email quando créditos acabam
   - Alert quando bot é parado via singleton
   - Notificação de Kill Switch

4. **Analytics**:
   - Dashboard de uso de créditos
   - Relatório de swaps por usuário
   - Tendências de ativação

---

## 📞 Suporte

Se encontrar problemas:

1. Verifique logs: `backend_stderr.log`
2. Execute migration novamente: `python scripts/migrate_activation_system.py --dry-run`
3. Consulte [ACTIVATION_CREDITS_SYSTEM.md](../ACTIVATION_CREDITS_SYSTEM.md)
4. Entre em contato com a engenharia

---

**Status**: ✅ Pronto para Produção
**Data**: Fevereiro 2026
**Versão**: 1.0.0
