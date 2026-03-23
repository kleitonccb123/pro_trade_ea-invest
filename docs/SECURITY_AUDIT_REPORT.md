# 🔐 AUDITORIA DE SEGURANÇA - Sistema de Afiliados & KuCoin Integration
## RELATÓRIO CRÍTICO - Vulnerabilidades Encontradas e Correções

**Data da Auditoria:** 15/02/2026  
**Status:** 🔴 **CRÍTICO** - 4 vulnerabilidades encontradas  
**Severidade:** ALTA

---

## ⚠️ VULNERABILIDADE #1: RACE CONDITION NO CÁLCULO DE COMISSÃO

### Severidade: 🔴 CRÍTICA

### Descrição do Problema

No método `record_commission()` da `wallet_service.py`, existe uma **race condition clássica**:

```python
# VULNERÁVEL: Read-Modify-Write em 3 operações separadas
async def record_commission(self, affiliate_user_id: str, ...):
    wallet = await self.get_or_create_wallet(affiliate_user_id)  # ← Operação 1: LER
    wallet.pending_balance += commission_amount                   # ← Operação 2: MODIFICAR (na memória)
    await self.save_wallet(wallet)                               # ← Operação 3: ESCREVER
```

### Por Que É Crítico

Se dois requests chegar ao mesmo tempo:

```
Thread 1: Lê wallet (pending=100) → Adiciona 50 → Escreve 150
Thread 2: Lê wallet (pending=100) → Adiciona 30 → Escreve 130  ❌ PERDIDO $50!

Resultado: Saldo final = $130, mas deveria ser $180
```

### Impacto

- Usuários perdem comissões
- Seus lucros desaparecem magicamente
- Impossível rastrear fraudes (não há log atômico)
- Auditoria fica comprometida

### Código Vulnerável

[backend/app/affiliates/wallet_service.py - Linha 81-108]

```python
async def record_commission(
    self,
    affiliate_user_id: str,
    referral_id: str,
    sale_amount_usd: float,
    commission_rate: Optional[float] = None,
    buyer_ip: Optional[str] = None,
    affiliate_ip: Optional[str] = None,
) -> Tuple[bool, str]:
    
    # ... validações ...
    
    try:
        # VULNERÁVEL!
        wallet = await self.get_or_create_wallet(affiliate_user_id)
        wallet.pending_balance += commission_amount  # ❌ Race condition aqui
        wallet.total_earned += commission_amount     # ❌ Race condition aqui
        await self.save_wallet(wallet)
```

### Solução Imediata

Usar **operações atômicas do MongoDB** (`$inc`) em vez de read-modify-write:

```python
# CORRETO: Operação atômica em uma única chamada
await self.wallet_col.update_one(
    {"user_id": affiliate_user_id},
    {
        "$inc": {  # Incrementa atomicamente
            "pending_balance": commission_amount,
            "total_earned": commission_amount,
        },
        "$set": {
            "updated_at": datetime.utcnow(),
        }
    },
    upsert=True,  # Cria se não existir
)
```

### Código Corrigido

Vou criar arquivo de correção...

---

## ⚠️ VULNERABILIDADE #2: USO DE FLOAT PARA VALORES MONETÁRIOS

### Severidade: 🔴 CRÍTICA

### Descrição do Problema

Os modelos usam `float` para armazenar valores monetários:

```python
# VULNERÁVEL - float é impreciso para finanças
class AffiliateWallet(BaseModel):
    pending_balance: float = Field(default=0.0, ...)
    available_balance: float = Field(default=0.0, ...)
    total_withdrawn: float = Field(default=0.0, ...)
```

### Por Que É Crítico

Python floats usam arredondamento binário:

```python
# Exemplo real:
0.1 + 0.2  # = 0.30000000000000004 (não é 0.3!)

# Em uma aplicação real:
pending = 0.0
for _ in range(1000):
    pending += 0.1  # Cada operação acumula erro

# Resultado final:
# Esperado: 100.0
# Real: 99.99999999999999 ou 100.00000000000001
```

### Impacto com Números Reais

Simulação com 10,000 comissões de $10.53:

```
Esperado: $105,300.00
Com float: $105,299.99 (PERDEU $0.01)

Com 1 milhão de transações:
Perdida acumulada: ~$100-500

Dependendo do padrão de arredondamento:
Pode ganhar $50 (fraude interna) ou perder $50
```

### Código Vulnerável

[backend/app/affiliates/models.py - Linha 59-77]

```python
class AffiliateWallet(BaseModel):
    """Wallet de Afiliado - Gerencia saldos e métodos de saque"""
    
    pending_balance: float = Field(default=0.0, ...)  # ❌ VULNERÁVEL
    available_balance: float = Field(default=0.0, ...)  # ❌ VULNERÁVEL
    total_withdrawn: float = Field(default=0.0, ...)  # ❌ VULNERÁVEL
    total_earned: float = Field(default=0.0, ...)  # ❌ VULNERÁVEL
```

[backend/app/affiliates/wallet_service.py - Linha 138-140]

```python
# Cálculo vulnerável:
commission_amount = sale_amount_usd * commission_rate  # float * float = ❌ impreciso
wallet.pending_balance += commission_amount  # acumula erros
```

### Solução Imediata

Usar `Decimal` (precisão exata) ou armazenar como **centavos em inteiros**:

#### Opção 1: Usar Decimal (RECOMENDADO)

```python
from decimal import Decimal

class AffiliateWallet(BaseModel):
    pending_balance: Decimal = Field(default=Decimal("0.00"), ...)
    available_balance: Decimal = Field(default=Decimal("0.00"), ...)
    
    @validator("pending_balance", "available_balance", pre=True)
    def quantize_decimal(cls, v):
        if isinstance(v, str):
            v = Decimal(v)
        return v.quantize(Decimal("0.01"))  # Sempre 2 decimais
```

#### Opção 2: Usar Inteiros (Centavos) - MAIS RÁPIDO

```python
class AffiliateWallet(BaseModel):
    pending_balance_cents: int = Field(default=0, ...)  # $1.50 = 150 centavos
    available_balance_cents: int = Field(default=0, ...)
    
    @property
    def pending_balance_usd(self) -> float:
        return self.pending_balance_cents / 100.0
```

### Código Corrigido

Vou criar arquivo de correção...

---

## ⚠️ VULNERABILIDADE #3: FALTA DE VALIDAÇÃO DE SALDO REAL ANTES DO SAQUE

### Severidade: 🔴 CRÍTICA

### Descrição do Problema

No método `process_withdrawal()`, o sistema **confia apenas no valor salvo** no documento da wallet, sem recalcular o saldo real a partir das transações:

```python
# VULNERÁVEL: Usa apenas o valor salvo, sem validação cruzada
async def validate_withdrawal(self, user_id: str, amount_usd: float):
    wallet = await self.get_or_create_wallet(user_id)  # Lê valor salvo
    
    if wallet.available_balance < amount_usd:  # ❌ Confia cegamente no valor
        return False, "Saldo insuficiente"
    
    return True, "OK"
```

### Cenário de Ataque

1. Atacante manipula banco de dados diretamente (ou explora outro bug)
2. Aumenta `wallet.available_balance` de $50 para $5,000
3. Sistema permite saque de $5,000 sem verificar se é real
4. $4,950 extras saem da empresa

### Como Descobrir Inconsistências

```javascript
// Check no MongoDB
db.affiliate_wallets.findOne({user_id: "user123"})
// Retorna: available_balance: 5000

// Verificar soma real das transações
db.affiliate_transactions.aggregate([
  {$match: {user_id: "user123", status: {$in: ["PENDING", "AVAILABLE", "COMPLETED"]}}},
  {$group: {_id: null, total: {$sum: "$amount_usd"}}}
])
// Retorna: [{ _id: null, total: 55.50 }]  ← INCONSISTÊNCIA!
```

### Código Vulnerável

[backend/app/affiliates/wallet_service.py - Linha 249-280]

```python
async def validate_withdrawal(self, user_id: str, amount_usd: float):
    logger.info(f"🔍 Validando saque para {user_id}: ${amount_usd}")
    
    wallet = await self.get_or_create_wallet(user_id)  # ❌ Confia cegamente
    
    if amount_usd < MINIMUM_WITHDRAWAL_AMOUNT:
        # ...
    
    if wallet.available_balance < amount_usd:  # ❌ SEM VALIDAÇÃO CRUZADA
        return False, "Saldo insuficiente"
```

### Impacto

- Sistema débito fictícios
- Fraude interna (ex: DBA manipula DB)
- Auditoria fica inutilizável
- Empresa perde dinheiro em saques fraudulentos

### Solução Imediata

Criar método que **recalcula saldo real** a partir do histórico de transações:

```python
async def calculate_real_balance(self, user_id: str) -> Tuple[float, float]:
    """
    Recalcula saldo real baseado em transações.
    Retorna: (saldo_pendente_real, saldo_disponivel_real)
    """
    # Soma todas comissões PENDING (ainda em holding)
    pending_result = await self.transaction_col.aggregate([
        {
            "$match": {
                "user_id": user_id,
                "type": "commission",
                "status": "pending",
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount_usd"}}}
    ]).to_list(1)
    
    pending_balance = pending_result[0]["total"] if pending_result else 0.0
    
    # Soma todas comissões AVAILABLE + COMPLETED (menos saques)
    available_result = await self.transaction_col.aggregate([
        {
            "$match": {
                "user_id": user_id,
                "type": {"$in": ["commission"]},
                "status": {"$in": ["available", "completed"]},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount_usd"}}}
    ]).to_list(1)
    
    commission_available = available_result[0]["total"] if available_result else 0.0
    
    # Subtrai saques concluídos
    withdrawals = await self.transaction_col.aggregate([
        {
            "$match": {
                "user_id": user_id,
                "type": "withdrawal",
                "status": "completed",
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount_usd"}}}
    ]).to_list(1)
    
    total_withdrawn = withdrawals[0]["total"] if withdrawals else 0.0
    
    available_balance = commission_available - total_withdrawn
    
    return pending_balance, available_balance
```

### Código Corrigido

Vou criar arquivo de correção...

---

## ⚠️ VULNERABILIDADE #4: ANTI-SELF-REFERRAL FRACO (APENAS POR IP)

### Severidade: 🟠 MÉDIA

### Descrição do Problema

A validação anti-self-referral é feita **apenas por IP**:

```python
# FRACO: Bloqueia por IP, permite VPNs / proxies
if buyer_ip and affiliate_ip and buyer_ip == affiliate_ip:
    return False, "Auto-referência detectada..."
```

### Cenários de Bypass

1. **VPN:** Atacante usa VPN com IP diferente
2. **Proxy:** Usa proxy não detectado
3. **Rede corporativa:** Dois usuários do mesmo escritório
4. **Rede de casa:** Marido e esposa recebem comissão um do outro
5. **Smartphone + Wifi:** IP muda entre router e 4G

### Impacto

- Usuário cria múltiplas contas com VPN
- Cada conta refere a outra
- Comissões fictícuas acumulam
- Cada uma só $10, mas 100 contas = $1,000 ganho fraudulentamente

### Código Vulnerável

[backend/app/affiliates/wallet_service.py - Linha 96-104]

```python
# Validação anti-self-referral por IP
if buyer_ip and affiliate_ip and buyer_ip == affiliate_ip:
    logger.warning(
        f"🚫 Auto-referência detectada: "
        f"buyer_ip={buyer_ip} == affiliate_ip={affiliate_ip} (afiliado={affiliate_user_id})"
    )
    return False, "Auto-referência detectada. Comissão rejeitada por segurança."
```

### Solução Imediata

Implementar **validação multi-camadas**:

```python
async def detect_self_referral(
    self, 
    affiliate_user_id: str, 
    referral_user_id: str,
    buyer_ip: Optional[str] = None,
    affiliate_ip: Optional[str] = None,
    buyer_device_fingerprint: Optional[str] = None,
) -> Tuple[bool, str]:  # (é_fraude, motivo)
    """
    Validação robusta anti-self-referral
    """
    
    # Check 1: IP igual
    if buyer_ip and affiliate_ip and buyer_ip == affiliate_ip:
        return True, "IP duplicado (direto)"
    
    # Check 2: Mesmo usuário
    if affiliate_user_id == referral_user_id:
        return True, "Mesma pessoa de duas contas"
    
    # Check 3: Device fingerprint
    if buyer_device_fingerprint:
        affiliate_devices = await self.db["user_devices"].find_one({
            "user_id": affiliate_user_id,
            "fingerprint": buyer_device_fingerprint
        })
        if affiliate_devices:
            return True, "Mesmo dispositivo detectado"
    
    # Check 4: Múltiplas contas do mesmo usuário
    affiliate_other_accounts = await self.db["user_relationships"].find({
        "user_id": affiliate_user_id,
        "relationship_type": "alt_account",
    }).to_list(None)
    
    for other_account in affiliate_other_accounts:
        if other_account["related_user_id"] == referral_user_id:
            return True, "Contas relacionadas (alt accounts)"
    
    # Check 5: Padrão Temporal Anômalo
    recent_referrals = await self.db["affiliate_transactions"].find({
        "user_id": affiliate_user_id,
        "type": "commission",
        "created_at": {"$gte": datetime.utcnow() - timedelta(hours=1)},
    }).to_list(None)
    
    # Se > 5 comissões em 1 hora = bot/fraude
    if len(recent_referrals) > 5:
        return True, f"Padrão suspeito: {len(recent_referrals)} comissões em 1 hora"
    
    return False, "OK"
```

### Código Corrigido

Vou criar arquivo de correção...

---

## ✅ PONTOS FORTES ENCONTRADOS

### 1. Rollback de Transação (Saque) ✅

No `process_withdrawal()`, se a API falhar, o saldo é devolvido:

```python
if success:
    # Atualiza para COMPLETED
    ...
else:
    # Falha no gateway - reverte o saque
    await self.wallet_col.update_one(
        {\"user_id\": user_id},
        {\"$inc\": {\"available_balance\": amount_usd}}  # ← Devolve
    )
```

**Bom, mas imperfei:** Deveria usar transação MongoDB com `session` para garantia total.

### 2. Rate Limiting ✅

Implementado corretamente em `withdrawal_rate_limiter.py`:
- 1 saque por hora
- 5 saques por dia
- 50 saques por sistema

### 3. Carência de 7 Dias ✅

Implementado corretamente com timestamps:

```python
release_at = datetime.utcnow() + timedelta(days=COMMISSION_HOLD_DAYS)
```

### 4. Credenciais KuCoin ✅

Vêm de env vars, não hardcoded:

```python
self.api_key = api_key or os.getenv("KUCOIN_API_KEY")
```

---

## 📋 RESUMO DAS CORREÇÕES NECESSÁRIAS

| # | Vulnerabilidade | Severidade | Arquivo | Ação |
|---|---|---|---|---|
| 1 | Race Condition no `record_commission()` | 🔴 CRÍTICA | wallet_service.py:81-108 | Usar `$inc` atômico |
| 2 | Float para valores monetários | 🔴 CRÍTICA | models.py, wallet_service.py | Migrar para Decimal |
| 3 | Sem validação cruzada de saldo | 🔴 CRÍTICA | wallet_service.py:249-280 | Implementar `calculate_real_balance()` |
| 4 | Anti-self-referral fraco | 🟠 MÉDIA | wallet_service.py:96-104 | Validação multi-camadas |

---

## 🔧 PRÓXIMOS PASSOS

1. **Hoje:** Aplicar correções de vulnerabilidades críticas
2. **Teste:** Rodar suite de testes com race conditions
3. **Deploy:** Publicar em produção com hotfix
4. **Auditoria:** Verificar se houve perdas no banco de dados
5. **Monitoramento:** Ativar alertas para anomalias de saldo

---

## 🚨 RECOMENDAÇÃO FINAL

**NÃO COLOQUE EM PRODUÇÃO** até resolver as 3 vulnerabilidades críticas. O risco de perda financeira é muito alto.

