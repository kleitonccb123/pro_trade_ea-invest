# Sistema de Créditos de Ativação e Limites de Troca

## 📋 Visão Geral

Este documento descreve a implementação do novo sistema de **Créditos de Ativação** e **Limites de Troca** para o Crypto Trade Hub.

### Objetivos

1. **Monetização Justa**: Usuários entendem que "Crédito" é valioso
2. **Estabilidade de Servidor**: Evita uso indiscriminado de recursos
3. **Prevenção de Erros**: Balance Guard valida saldos antes de executar
4. **Segurança Jurídica**: Kill Switch garante controle em caso de incidentes

---

## 🎟️ Sistema de Créditos de Ativação

### Conceito

Cada usuário recebe um número de **Créditos de Ativação** baseado no seu plano:

```
Starter   → 1 crédito
Pro       → 5 créditos
Premium   → 15 créditos
Enterprise → Customizável
```

### Regra Principal

- **Primeira Ativação de um Bot**: Consome **1 crédito**
- **Reativações Posteriores**: Não consomem créditos adicionais
- **Limite Hard**: Máximo de robots em "slot ativo" = créditos disponíveis

### Modelos Atualizados

#### User Model (`app/users/model.py`)

```python
class User(BaseModel):
    # ... campos existentes ...
    
    # 🎟️ SISTEMA DE CRÉDITOS DE ATIVAÇÃO
    activation_credits: int = Field(
        default=1,
        description="Créditos de ativação disponíveis"
    )
    activation_credits_used: int = Field(
        default=0,
        description="Créditos já utilizados"
    )
    
    @property
    def activation_credits_remaining(self) -> int:
        """Créditos disponíveis."""
        return max(0, self.activation_credits - self.activation_credits_used)
```

#### Bot Model (`app/bots/model.py`)

```python
class Bot(BaseModel):
    # ... campos existentes ...
    
    # 🎟️ SISTEMA DE CRÉDITOS E LIMITES DE TROCA
    is_active_slot: bool = Field(
        default=False,
        description="Indica se bot está no slot ativo"
    )
    activation_credits_used: int = Field(
        default=0,
        description="Créditos consumidos por este bot"
    )
    swap_count: int = Field(
        default=0,
        description="Número de trocas/reconfigurations (até 2 gratuitas)"
    )
    swap_history: List[SwapHistory] = Field(
        default_factory=list,
        description="Histórico de trocas"
    )
    last_run_timestamp: Optional[datetime] = Field(
        default=None,
        description="Última execução bem-sucedida"
    )
```

---

## 🤖 Regra de Execução Única (Singleton)

### Conceito

**Apenas 1 bot pode estar `is_running: True` por vez** para cada usuário.

### Implementação

Quando o usuário tenta iniciar o **Bot B** enquanto o **Bot A** está rodando:

1. Sistema detecta que **Bot A** está em execução
2. Executa **graceful_stop** automático no **Bot A**
3. Inicia **Bot B**

### Endpoint: `/bots/{id}/start`

```bash
POST /bots/bot-id-123/start
Authorization: Bearer TOKEN
Content-Type: application/json

{
  "api_key": "kucoin_api_key",
  "api_secret": "kucoin_secret",
  "exchange": "kucoin"
}
```

**Response (202 Accepted)**:

```json
{
  "status": "started",
  "instance_id": "inst-456",
  "bot_id": "bot-id-123",
  "mode": "live",
  "activation": {
    "credits_consumed": 1,
    "credits_remaining": 4,
    "previous_bot_stopped": true
  }
}
```

**Erros Possíveis**:

- **402 Payment Required**: Insuficientes créditos de ativação
- **400 Bad Request**: Balance Guard falhou (saldo insuficiente)
- **404 Not Found**: Bot não encontrado

---

## 🔄 Sistema de Remanejamento (Swap Limit)

### Conceito

Usuários podem modificar a **estratégia/configuração** de um bot até **2 vezes gratuitamente**. A partir da 3ª alteração, consome **1 crédito** por swap.

### Limites

| Swap # | Free? | Custa |
|--------|-------|-------|
| 1      | ✅    | -     |
| 2      | ✅    | -     |
| 3      | ❌    | 1 crédito |
| 4      | ❌    | 1 crédito |
| N      | ❌    | 1 crédito |

### Endpoint: `PUT /bots/{bot_id}/config`

```bash
PUT /bots/bot-id-123/config
Authorization: Bearer TOKEN
Content-Type: application/json

{
  "amount": 1500.0,
  "stop_loss": 3.0,
  "take_profit": 15.0,
  "strategy": "DCA Strategy",
  "timeframe": "1h"
}
```

**Response (200 OK)**:

```json
{
  "updated": true,
  "bot_id": "bot-id-123",
  "swap_info": {
    "swap_number": 3,
    "was_free": false,
    "credits_consumed": 1,
    "credits_remaining": 4
  },
  "message": "✅ Config updated. Swap #3 (PAID)"
}
```

**Erros Possíveis**:

- **402 Payment Required**: Insuficientes créditos para swap pago
- **404 Not Found**: Bot não encontrado
- **403 Forbidden**: Bot não pertence ao usuário

### Endpoint: `GET /bots/{bot_id}/swap-status`

```bash
GET /bots/bot-id-123/swap-status
Authorization: Bearer TOKEN
```

**Response**:

```json
{
  "bot_id": "bot-id-123",
  "swap_count": 5,
  "free_swaps_used": 2,
  "free_swaps_remaining": 0,
  "next_swap": {
    "is_free": false,
    "will_cost_credits": 1
  },
  "swap_history": [
    {
      "timestamp": "2026-02-11T10:30:00Z",
      "change_type": "strategy_change",
      "credit_charged": true
    }
  ]
}
```

---

## 💰 Balance Guard

### Conceito

Antes de **iniciar qualquer bot para live trading**, o sistema valida:

1. Saldo mínimo está disponível na Exchange
2. Saldo >= Order Size configurada

### Validações

```python
# Order Size = 1000 USDT
# Saldo disponível = 500 USDT

# ❌ FALHA: Saldo insuficiente
```

### Implementação (`app/services/balance_guard.py`)

```python
await BalanceGuard.validate_before_start(
    user_id=user_id,
    bot_id=bot_id,
    api_key=api_key,
    api_secret=api_secret,
    exchange="kucoin"
)
```

### Erros Prevenidos

- ❌ `"Minimum Order Amount"` na KuCoin
- ❌ Tentativa de order com 0.0001 saldo
- ❌ Configs inconsistentes entre bot e exchange

---

## 🔴 Kill Switch Global

### Conceito

**Circuit breaker** de segurança para **desativar todos os bots** de um usuário instantaneamente em caso de:

- 🚨 Suspeita de hack (API Key comprometida)
- 🚨 Erro crítico no sistema
- 🚨 Investigação de fraude
- 🚨 Violação de política

### Endpoints

#### Ativar Kill Switch

```bash
POST /bots/admin/kill-switch/activate/{user_id}
Authorization: Bearer ADMIN_TOKEN
Content-Type: application/json

{
  "reason": "API key compromise suspected"
}
```

**Response**:

```json
{
  "status": "activated",
  "kill_switch": {
    "activated": true,
    "bots_stopped": 3,
    "bots_deactivated": 0,
    "timestamp": "2026-02-11T10:30:00Z",
    "audit_id": "audit-789"
  },
  "message": "🔴 Kill Switch activated for user xxx. All bots stopped."
}
```

#### Desativar Kill Switch

```bash
POST /bots/admin/kill-switch/deactivate/{user_id}
Authorization: Bearer ADMIN_TOKEN
```

#### Verificar Status

```bash
GET /bots/admin/kill-switch/status/{user_id}
Authorization: Bearer TOKEN
```

**Response**:

```json
{
  "user_id": "user-456",
  "kill_switch_active": false,
  "recent_activations": [
    {
      "timestamp": "2026-02-11T10:30:00Z",
      "reason": "API key compromise suspected",
      "triggered_by": "admin@example.com",
      "bots_affected": 3
    }
  ]
}
```

### Auditoria

Cada ativação de Kill Switch é registrada em `audit_logs`:

```json
{
  "event_type": "kill_switch_activated",
  "user_id": ObjectId("..."),
  "bots_affected": 3,
  "reason": "API key compromise suspected",
  "triggered_by": "admin@example.com",
  "timestamp": ISODate("2026-02-11T10:30:00Z"),
  "severity": "critical"
}
```

---

## 🔧 Services

### ActivationManager (`app/services/activation_manager.py`)

Gerencia toda a lógica de créditos:

```python
# Validar que pode ativar
validation = await ActivationManager.validate_activation(user_id, bot_id)

# Ativar bot (com graceful stop automático)
await ActivationManager.activate_bot(user_id, bot_id)

# Validar swap
swap_validation = await ActivationManager.validate_swap(user_id, bot_id)

# Registrar swap no histórico
await ActivationManager.record_swap(
    user_id, bot_id, old_config, new_config
)

# Fazer upgrade de plano
await ActivationManager.upgrade_plan(user_id, "premium")
```

### BalanceGuard (`app/services/balance_guard.py`)

Valida saldo na Exchange:

```python
# Verificar saldo
result = await BalanceGuard.check_balance(
    user_id, bot_id, api_key, api_secret, "kucoin"
)

# Validar antes de start
await BalanceGuard.validate_before_start(
    user_id, bot_id, api_key, api_secret, "kucoin"
)
```

### KillSwitch (`app/services/kill_switch.py`)

Controle de emergência:

```python
# Ativar Kill Switch
await KillSwitch.activate_for_user(user_id, reason="hack detected")

# Desativar
await KillSwitch.deactivate_for_user(user_id)

# Verificar status
is_active = await KillSwitch.is_active(user_id)

# Histórico
history = await KillSwitch.get_history(user_id, limit=10)
```

---

## 📊 Endpoints de Perfil

### Visualizar Créditos

```bash
GET /auth/profile/activation-credits
Authorization: Bearer TOKEN
```

**Response**:

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

---

## 🚀 Migração de Dados

### Script: `scripts/migrate_activation_system.py`

Adiciona campos necessários aos usuários e bots existentes.

#### Usar com DRY-RUN

```bash
cd backend
python scripts/migrate_activation_system.py --dry-run
```

Simula a migração e mostra o que será modificado.

#### Aplicar Migração

```bash
python scripts/migrate_activation_system.py
```

Faz as alterações no banco de dados:

- Para cada usuário: Adiciona `activation_credits` baseado em seu plano
- Para cada bot: Adiciona campos `is_active_slot`, `swap_count`, etc.

**Output Esperado**:

```
============================================================
MIGRATING USERS: Adding activation credits...
============================================================
Found 42 users without activation_credits field
  ✅ User john@example.com: PRO = 5 credits
  ✅ User jane@example.com: STARTER = 1 credit
  ... Processed 42 users
✅ Users migration complete: 42/42 updated

============================================================
MIGRATING BOTS: Adding swap history and slot fields...
============================================================
Found 156 bots needing migration
  ✅ Bot "DCA Strategy": Updated with 4 fields
  ... Processed 156 bots
✅ Bots migration complete: 156/156 updated

============================================================
MIGRATION SUMMARY
============================================================
Users updated: 42
Bots updated: 156
✅ Migration completed successfully!
============================================================
```

---

## 📈 Fluxo Completo: Iniciar um Bot

```
1. User clica em "START BOT"
   ↓
2. Frontend envia POST /bots/{id}/start
   ↓
3. Sistema valida:
   ├─ ✅ Usuario autenticado?
   ├─ ✅ Bot pertence ao usuário?
   ├─ ✅ Tem créditos disponíveis?
   └─ ✅ Saldo exchange suficiente?
   ↓
4. Se bot anterior está rodando:
   ├─ Executa graceful_stop automático
   └─ libera slot
   ↓
5. Ativa novo bot:
   ├─ is_active_slot = True
   ├─ is_running = True
   ├─ Consome 1 crédito (se primeira vez)
   └─ Registra timestamp
   ↓
6. Retorna resposta 200/202 com status
```

---

## 📈 Fluxo: Atualizar Configuração

```
1. User edita config do bot
   ↓
2. Frontend envia PUT /bots/{id}/config
   ↓
3. Sistema valida:
   ├─ Quantas vezes já foi modificado?
   ├─ É a 1ª ou 2ª vez? (FREE)
   └─ É a 3ª+ vez? (CUSTA 1 CRÉDITO)
   ↓
4. Se custa crédito:
   ├─ Valida se tem créditos disponíveis
   └─ Se não, retorna 402 Payment Required
   ↓
5. Registra swap no histórico:
   ├─ old_config
   ├─ new_config
   ├─ timestamp
   └─ credit_charged: True/False
   ↓
6. Consome crédito (se aplicável)
   ↓
7. Atualiza config do bot
   ↓
8. Retorna 200 OK com status do swap
```

---

## 🔐 Segurança

### Validações Implementadas

1. **Owner Check**: Garante que apenas proprietário pode gerenciar bot
2. **Credit Balance**: Valida saldo de créditos antes de ativar
3. **Exchange API Validation**: Verifica credenciais antes de usar
4. **Graceful Degradation**: Erros não afetam outros botcripts
5. **Audit Trail**: Todos os eventos críticos são registrados

### Erros HTTP Padronizados

| Código | Significado | Exemplo |
|--------|------------|---------|
| 200    | ✅ Sucesso | Bot iniciado |
| 202    | ⏳ Aceito | Processando async |
| 400    | ❌ Entrada inválida | Balance insuficiente |
| 402    | 💳 Pagamento necessário | Crédito insuficiente |
| 403    | 🔒 Acesso negado | Bot não é seu |
| 404    | 🚫 Não encontrado | Bot não existe |
| 500    | ⚠️ Erro interno | Erro no servidor |

---

## 📝 Exemplos Completos

### Exemplo 1: Usuário Starter tenta ativar 2º bot

```
Usuario tem: 1 crédito (Starter)
1º bot: Gasta 1 crédito → 0 créditos restantes
Tenta 2º bot: ERRO 402 Payment Required

Solução: Upgrade para Pro (5 créditos)
```

### Exemplo 2: Usuário faz 5 mudanças em um bot

```
Swap 1: FREE ✅
Swap 2: FREE ✅
Swap 3: CUSTA 1 crédito ❌ (se tiver)
Swap 4: CUSTA 1 crédito ❌ (se tiver)
Swap 5: CUSTA 1 crédito ❌ (se tiver)

Custo total: 3 créditos para 5 swaps
```

### Exemplo 3: Kill Switch ativado

```
Admin detecta: API Key "bot-user@example.com" foi comprometida

POST /bots/admin/kill-switch/activate/bot-user@example.com

Resultado:
- Bot A (DCA): PARADO ⏹️
- Bot B (RSI): PARADO ⏹️
- Bot C (Grid): PARADO ⏹️

Evento auditado: severity=CRITICAL
Máquina do Bot: Não consegue mais receber comandos

User é notificado: "Seu Kill Switch foi ativado por razões de segurança"
```

---

## 🔄 Fluxo de Upgrade de Plano

```
Usuário tem: Starter (1 crédito, 0 usado)
Upgrade para: Pro (5 créditos)

Resultado:
├─ activation_credits = 5
├─ activation_credits_used = 0 (mantém)
├─ activation_credits_remaining = 5 (novo)
└─ Pode ativar mais 5 bots
```

---

## 🧪 Testes

### Teste Manual com cURL

```bash
# 1. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'

# Salva TOKEN

# 2. Visualizar créditos
curl -X GET http://localhost:8000/auth/profile/activation-credits \
  -H "Authorization: Bearer $TOKEN"

# 3. Iniciar bot
curl -X POST http://localhost:8000/bots/bot-123/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "kucoin_key",
    "api_secret": "kucoin_secret",
    "exchange": "kucoin"
  }'

# 4. Atualizar config (2º swap - ainda é free)
curl -X PUT http://localhost:8000/bots/bot-123/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 2000,
    "stop_loss": 5
  }'

# 5. Visualizar status de swaps
curl -X GET http://localhost:8000/bots/bot-123/swap-status \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📚 Referencias de Código

| Arquivo | Descrição |
|---------|-----------|
| `app/users/model.py` | User model com activation_credits |
| `app/bots/model.py` | Bot model com swap system |
| `app/services/activation_manager.py` | Lógica principal de créditos |
| `app/services/balance_guard.py` | Validação de saldo |
| `app/services/kill_switch.py` | Controle de emergência |
| `app/bots/router.py` | Endpoints /bots/* e kill-switch |
| `app/auth/router.py` | GET /profile/activation-credits |
| `backend/scripts/migrate_activation_system.py` | Migration script |

---

## ✅ Checklist de Implementação

- [x] Atualizar modelo User com activation_credits
- [x] Atualizar modelo Bot com swap_history e campos relacionados
- [x] Criar ActivationManager service
- [x] Criar BalanceGuard service
- [x] Criar KillSwitch service
- [x] Atualizar endpoint POST /bots/{id}/start com validações
- [x] Criar endpoint PUT /bots/{bot_id}/config
- [x] Criar endpoint GET /bots/{bot_id}/swap-status
- [x] Criar endpoints de Kill Switch (/admin/kill-switch/*)
- [x] Criar endpoint GET /auth/profile/activation-credits
- [x] Criar migration script
- [] Adicionar testes unitários
- [ ] Adicionar testes de integração
- [ ] Documentar em frontend
- [ ] Release notes

---

## 📞 Suporte

Para dúvidas ou problemas com a implementação:

1. Verificar logs em `backend_stderr.log`
2. Executar migration com `--dry-run` para validar
3. Verificar auditoria em `db.audit_logs`
4. Contatar time de engenharia

---

**Data de Implementação**: Fevereiro 2026
**Versão**: 1.0.0
**Status**: ✅ Pronto para Produção
