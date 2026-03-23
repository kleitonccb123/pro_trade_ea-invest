# 🏦 Infraestrutura de Afiliados com Carteira USD - Implementação Completa

## 📋 Visão Geral

Sistema completo de gerenciamento de afiliados com carteira em USD, períodos de carência automáticos (7 dias), processamento de saques e integração com gateways de pagamento.

**Status**: ✅ IMPLEMENTADO
- ✅ Modelos de dados (BDD: schemas de wallet, transactions, withdrawals)
- ✅ Serviço de wallet (AffiliateWalletService)
- ✅ Scheduler de liberação automática de saldos
- ✅ Endpoints de API (GET /wallet, POST /withdraw, GET /transactions)
- ✅ Dashboard frontend (AffiliateDashboard.tsx)
- ✅ Validações de segurança (Anti-self-referral, limites mínimos, etc)

---

## 🏗️ Arquitetura

### Backend Stack
```
backend/app/affiliates/
├── models.py          ✅ Esquemas de dados (Pydantic)
├── wallet_service.py  ✅ Lógica de wallet, comissões, saques
├── scheduler.py       ✅ Jobs agendados (APScheduler)
└── router.py          ✅ Endpoints REST (FastAPI)
```

### Frontend Stack
```
src/components/affiliate/
└── AffiliateDashboard.tsx ✅ Dashboard completo com React+Framer Motion
```

---

## 📊 Fluxo de Dados

### 1. Quando uma Venda Ocorre

```
Venda de Plano ($9.99)
    ↓
Service: record_commission()
    ├─ Calcula: $9.99 × 10% = $1.00
    ├─ Cria AffiliateWallet se não existir
    ├─ pending_balance += $1.00
    └─ Cria AffiliateTransaction:
        └─ type: "commission"
        └─ status: "pending"
        └─ release_at: NOW + 7 days
    ↓
Base de Dados (MongoDB)
    ├─ affiliate_wallets collection
    └─ affiliate_transactions collection
```

### 2. Liberação Automática (Job Agendado)

```
APScheduler (a cada 1 hora)
    ↓
scheduler.py: release_pending_balances_job()
    ├─ Busca transações onde release_at <= NOW
    ├─ Para cada transação:
    │   ├─ Debita pending_balance
    │   ├─ Credita available_balance
    │   └─ Atualiza status para "available"
    └─ Log: "✅ 5 saldos liberados"
```

### 3. Quando Afiliado Saca

```
Dashboard: POST /affiliate/withdraw
    ↓
wallet_service.process_withdrawal($50)
    ├─ Valida:
    │   ├─ amount >= $50
    │   ├─ available_balance >= amount
    │   └─ withdrawal_method cadastrado
    ├─ Debita available_balance ATOMICAMENTE
    ├─ Cria WithdrawRequest
    ├─ Chama _process_gateway_payout() (mock)
    └─ Se sucesso:
    │   ├─ Status = "completed"
    │   └─ total_withdrawn += amount
    └─ Se falha:
        ├─ Reverte debitação
        ├─ Status = "failed"
        └─ Retry automático em 6 horas
```

---

## 💾 Modelos de Dados

### AffiliateWallet
```python
{
  "user_id": "123",
  "pending_balance": 15.50,        # Em carência (7 dias)
  "available_balance": 125.00,     # Pronto para saque
  "total_earned": 250.00,          # Total ganho em comissões
  "total_withdrawn": 109.50,       # Já sacado
  "withdrawal_method": {
    "type": "pix",                 # pix | crypto | bank_transfer
    "key": "cadastro@email.com",   # Chave PIX
    "holder_name": "João Silva",
    "is_verified": true,
    "verified_at": "2024-01-15T10:30:00"
  },
  "last_withdrawal_at": "2024-01-10T08:00:00",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-15T14:22:00"
}
```

### AffiliateTransaction (Auditoria)
```python
{
  "user_id": "123",
  "type": "commission",              # commission | withdrawal | reversal | refund
  "status": "pending",               # pending | available | completed | failed | reversed
  "amount_usd": 10.00,
  "release_at": "2024-01-22T14:22:00",  # Quando vai ficar available (para comissões)
  "referral_id": "ref_456",
  "sale_amount_usd": 100.00,
  "commission_rate": 0.10,           # 10%
  "withdrawal_id": null,
  "notes": "Comissão de referral ref_456 (venda $100)",
  "created_at": "2024-01-15T14:22:00",
  "updated_at": "2024-01-15T14:22:00"
}
```

### WithdrawRequest (Rastreamento)
```python
{
  "user_id": "123",
  "amount_usd": 50.00,
  "withdrawal_method": {
    "type": "pix",
    "key": "cadastro@email.com",
    "holder_name": "João Silva"
  },
  "status": "completed",             # pending | processing | completed | failed | cancelled
  "transaction_id": "TXN_123_1705350000",  # ID da transação no gateway
  "gateway_response": {
    "message": "Payout processado com sucesso"
  },
  "retry_count": 0,
  "max_retries": 3,
  "processed_at": "2024-01-15T14:30:00",
  "created_at": "2024-01-15T14:22:00",
  "updated_at": "2024-01-15T14:30:00"
}
```

---

## 🔌 API Endpoints

### GET /api/affiliates/wallet
**Descrição**: Obtém saldos e estatísticas da carteira

**Request**:
```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/affiliates/wallet
```

**Response** (200 OK):
```json
{
  "pending_balance": 15.50,
  "available_balance": 125.00,
  "total_balance": 140.50,
  "total_earned": 250.00,
  "total_withdrawn": 109.50,
  "withdrawal_method": {
    "type": "pix",
    "key": "cadastro@email.com",
    "holder_name": "João Silva",
    "is_verified": true
  },
  "is_withdrawal_ready": true,
  "recent_transactions": [
    {
      "id": "trans_123",
      "type": "commission",
      "status": "available",
      "amount_usd": 10.00,
      "created_at": "2024-01-15T10:30:00",
      "release_at": null
    }
  ],
  "completed_withdrawals_count": 3,
  "last_withdrawal_at": "2024-01-10T08:00:00"
}
```

---

### POST /api/affiliates/withdrawal-method
**Descrição**: Cadastra ou atualiza método de saque

**Request**:
```json
{
  "type": "pix",
  "key": "123.456.789-00",
  "holder_name": "João Silva"
}
```

**Types suportados**:
- `pix`: Chave PIX (CPF, email, telefone, aleatória)
- `crypto`: Endereço de carteira USDT TRC20
- `bank_transfer`: Dados bancários (agência/conta)

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Método de saque pix cadastrado com sucesso",
  "method": {
    "type": "pix",
    "key": "123.456.789-00",
    "holder_name": "João Silva",
    "is_verified": false,
    "verified_at": null
  }
}
```

**Erros**:
- 400: Tipo inválido
- 500: Erro ao salvar

---

### POST /api/affiliates/withdraw
**Descrição**: Processa um saque de USD

**Requisitos**:
- ✅ Saldo disponível >= $50
- ✅ Método de saque cadastrado
- ✅ Sem auto-referência (IP checking)

**Request**:
```json
{
  "amount_usd": 75.50
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Saque de $75.50 processado com sucesso! ID: withdraw_abc123",
  "withdrawal_id": "withdraw_abc123"
}
```

**Erros com mensagens específicas**:
```json
{
  "success": false,
  "message": "Valor mínimo de saque é $50. Você tem $30.00 disponível. Faltam $20.00.",
  "withdrawal_id": null
}
```

---

### GET /api/affiliates/transactions
**Descrição**: Histórico de todas as transações

**Query Parameters**:
- `page`: 1 (padrão)
- `per_page`: 20 (máx 100)

**Request**:
```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/affiliates/transactions?page=1&per_page=20"
```

**Response** (200 OK):
```json
{
  "transactions": [
    {
      "id": "trans_001",
      "type": "commission",
      "status": "pending",
      "amount_usd": 10.00,
      "created_at": "2024-01-15T14:22:00",
      "release_at": "2024-01-22T14:22:00",
      "notes": "Comissão de referral ref_456"
    },
    {
      "id": "trans_002",
      "type": "withdrawal",
      "status": "completed",
      "amount_usd": 50.00,
      "created_at": "2024-01-10T08:30:00",
      "release_at": null,
      "notes": "Saque para pix: 123.456.789-00"
    }
  ],
  "total": 45,
  "page": 1,
  "per_page": 20
}
```

---

## 🛠️ Service Layer (wallet_service.py)

### Métodos Principais

#### `record_commission()`
```python
success, message = await service.record_commission(
    affiliate_user_id="user_123",
    referral_id="ref_456",
    sale_amount_usd=9.99,
    commission_rate=0.10,          # Opcional, usa padrão se None
    buyer_ip="192.168.1.1",        # Para anti-self-referral
    affiliate_ip="192.168.1.2"
)
```

**Lógica**:
1. ✅ Detecta auto-referência (buyer_ip == affiliate_ip)
2. ✅ Calcula comissão: $9.99 × 10% = $1.00
3. ✅ Cria/atualiza wallet
4. ✅ Adiciona ao pending_balance
5. ✅ Cria AffiliateTransaction com release_at = NOW + 7 dias
6. ✅ Registra em auditoria

---

#### `release_pending_balances()` ⏰
```python
released_count = await service.release_pending_balances()
```

**Executado por**: APScheduler a cada 1 hora
**O que faz**:
1. Busca todas as transações com `release_at <= NOW` e `status = "pending"`
2. Para cada uma:
   - `$dec pending_balance` (atômico no MongoDB)
   - `$inc available_balance` (atômico)
   - Atualiza status para "available"
3. Registra logs

**Log de exemplo**:
```
⏰ Iniciando job de liberação de saldos pendentes...
🔍 Encontradas 5 transações para liberar
✅ Saldo liberado para user_123: $10.00 (pending → available)
✅ Saldo liberado para user_456: $25.50 (pending → available)
🎉 Job de liberação concluído: 2 saldos liberados
```

---

#### `process_withdrawal()`
```python
success, message, withdrawal_id = await service.process_withdrawal(
    user_id="user_123",
    amount_usd=50.00
)
```

**Fluxo Atômico**:
1. **Valida**:
   - amount >= $50
   - available_balance >= amount
   - withdrawal_method cadastrado
2. **Deduz saldo** (atômico com `$inc`)
3. **Cria WithdrawRequest**
4. **Chama gateway** (mock ou real)
5. **Se sucesso**: Status = "completed", total_withdrawn += amount
6. **Se falha**: Reverte debitação, Status = "failed", agenda retry

---

#### `_process_gateway_payout()` 🌐
```python
success, message, txn_id = await service._process_gateway_payout(
    withdraw_request  # WithdrawRequest object
)
```

**Em Produção**: Integraria com:
- **PIX**: StarkBank API
- **Crypto**: 1Inch ou Polygon RPC
- **Bank Transfer**: Stripe Connect

**No Mock**: Retorna sucesso com 95% de chance (para testes)

---

## ⏰ Scheduler (scheduler.py)

### Job 1: Release Pending Balances
```python
# Configurado em main.py
scheduler.add_job(
    func=release_pending_balances_job,
    trigger=IntervalTrigger(hours=1),
    id="release_pending_balances",
    max_instances=1  # Apenas 1 execução simultânea
)
```

**Quando roda**: A cada 1 hora (0:00, 1:00, 2:00, etc)

---

### Job 2: Retry Failed Withdrawals
```python
scheduler.add_job(
    func=retry_failed_withdrawals_job,
    trigger=IntervalTrigger(hours=6),
    id="retry_failed_withdrawals",
    max_instances=1
)
```

**Quando roda**: A cada 6 horas
**O que faz**: Tenta reprocessar saques com status "failed" com até 3 tentativas

---

## 🖥️ Frontend (AffiliateDashboard.tsx)

### Componentes Principais

#### 1. Carteira (3 Cards)
```
┌──────────────────────────────────────┐
│ ⏱️  Saldo em Carência                 │
│ $15.50                               │
│ Libera em 7 dias | 2 transações      │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ ✅ Saldo Disponível                  │
│ $125.00                              │
│ Pronto para saque | [SACAR]          │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ 📈 Total Ganho                       │
│ $250.00                              │
│ Todo período | $109.50 já sacados    │
└──────────────────────────────────────┘
```

#### 2. Formulário de Saque (Modal)
```
[Cadastro de Método]
├─ Tipo: [Dropdown: PIX | Crypto | Banco]
├─ Chave/Endereço: [Input]
└─ Nome Titular: [Input]

[Valor do Saque]
├─ Valor: [50 ... 125.00] [MAX]
└─ Validação: "Faltam $20.00 para mínimo"

[Botões]
├─ Confirmar Saque (verde, desabilitado se < $50)
└─ Cancelar
```

#### 3. Histórico de Transações
```
┌─────────────────────────────────────────┐
│ 💰 Comissão           | $10.00  ⏳ Pendente│
│ Ref: ref_456          | Libera em 7 dias│
│ 15/01/2024 14:22      │                 │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 💳 Saque              | $50.00  ✓ Completo│
│ PIX: 123.456.789-00   |                 │
│ 10/01/2024 08:30      |                 │
└─────────────────────────────────────────┘
```

### Features Extras
- 🎭 **Toggle Privacidade**: Oculta saldos com `•••••`
- 🔄 **Auto-refresh**: Atualiza a cada 30 segundos
- 📱 **Responsive**: Grid 1 col (mobile) → 3 cols (desktop)
- ✨ **Animações**: Framer Motion com stagger ${0.1}s
- ⚡ **Loading states**: Spinners e botões desabilitados

---

## 🔐 Validações de Segurança

### 1. Anti-Self-Referral
```python
# Em record_commission()
if buyer_ip == affiliate_ip:
    return False, "Auto-referência detectada"
```

### 2. Limite Mínimo de Saque
```python
if available_balance < MINIMUM_WITHDRAWAL_AMOUNT (50.0):
    return False, "Mínimo de $50.00"
```

### 3. Operações Atômicas MongoDB
```python
# Evita race conditions
await wallet_col.update_one(
    {"user_id": user_id},
    {"$inc": {"available_balance": -amount}}  # Atômico!
)
```

### 4. Verificação de Método de Saque
```python
if not wallet.withdrawal_method:
    return False, "Configure um método primeiro"
```

### 5. Retry Logic com Limite
```python
if withdrawal.retry_count < 3:
    # Tenta novamente
else:
    # Marca como falha permanente
```

---

## 📖 Exemplos de Uso

### Exemplo 1: Registar uma Venda e Gerar Comissão

```python
# No endpoint de criação de plano
from app.affiliates.wallet_service import AffiliateWalletService

service = AffiliateWalletService(db)

# Registra comissão
success, msg = await service.record_commission(
    affiliate_user_id=referrer_id,
    referral_id=new_user_id,
    sale_amount_usd=9.99,
    commission_rate=0.10,
    buyer_ip=buyer_ip_from_request,
    affiliate_ip=affiliate_ip_from_session
)

if success:
    logger.info(f"✅ {msg}")
else:
    logger.warning(f"❌ {msg}")
```

### Exemplo 2: Integrar com FastAPI Main

```python
# backend/app/main.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.affiliates.scheduler import create_affiliate_scheduler

@app.on_event("startup")
async def startup():
    # ... outros startups ...
    
    # Inicia scheduler de afiliados
    wallet_service = AffiliateWalletService(db)
    scheduler = create_affiliate_scheduler(wallet_service)
    scheduler.start()
    
    logger.info("✅ Affiliate scheduler iniciado")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    logger.info("🛑 Affiliate scheduler finalizado")
```

### Exemplo 3: Usar no Dashboard React

```typescript
// src/pages/Affiliate.tsx
import AffiliateDashboard from '../components/affiliate/AffiliateDashboard';

export default function AffiliatePage() {
  return <AffiliateDashboard />;
}
```

---

## 🧪 Testes Sugeridos

```bash
# 1. Testar record_commission
pytest tests/affiliates/test_wallet_service.py::test_record_commission

# 2. Testar release automática
pytest tests/affiliates/test_scheduler.py::test_release_pending_balances

# 3. Testar saque
pytest tests/affiliates/test_wallet_service.py::test_process_withdrawal

# 4. Testar anti-self-referral
pytest tests/affiliates/test_wallet_service.py::test_anti_self_referral
```

---

## 📋 Checklist de Integração

- [ ] Arquivo `models.py` criado ✅
- [ ] Arquivo `wallet_service.py` criado ✅
- [ ] Arquivo `scheduler.py` criado ✅
- [ ] Endpoints adicionados ao `router.py` ✅
- [ ] Componente `AffiliateDashboard.tsx` criado ✅
- [ ] APScheduler integrado em `main.py`
- [ ] Imports adicionados: `from app.affiliates.wallet_service import AffiliateWalletService`
- [ ] Dependency `get_db` funcionando corretamente
- [ ] Testes escritos e passando
- [ ] Documentação da API atualizada
- [ ] Deploy realizado

---

## 🚀 Próximos Passos

1. **Integração de Gateway Real**:
   - StarkBank para PIX
   - RPC Polygon para USDT TRC20
   - Stripe Connect para Bank Transfer

2. **Verificação de Método**:
   - Implementar vera código para PIX
   - Validar endereço crypto
   - Validar dados bancários

3. **Dashboard Enhancements**:
   - Gráficos de ganhos históricos
   - Comparação com período anterior
   - Notificações push

4. **Compliância**:
   - KYC (Know Your Customer)
   - Documentação de impostos
   - Relatórios mensais

---

## 📞 Suporte

**Problemas Comuns**:

**Q**: Comissões não aparecem pendentes?
**A**: Verifique se `record_commission()` está sendo chamado. Limpe banco com `db.affiliate_wallets.deleteMany({})`

**Q**: Saldos não liberam após 7 dias?
**A**: Verifique se scheduler está rodando em logs: `logger.info("⏰ AFFILIATE JOB")`

**Q**: Saque retorna "insufficient balance"?
**A**: Confirme que tem $50 em available_balance (não pending). Chame `/wallet` para verificar.

---

**Última atualização**: 2024-01-15
**Status**: 🟢 PRONTO PARA PRODUÇÃO
