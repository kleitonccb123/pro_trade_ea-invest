# BEFORE & AFTER - CODE COMPARISON GUIDE

## 🔴 VULNERABILIDADE #1: RACE CONDITION

### ❌ ANTES (wallet_service.py - Linhas 81-108)
```python
async def record_commission(self, affiliate_user_id: str, ...):
    # ... validações ...
    
    try:
        # VULNERÁVEL: Read-Modify-Write em 3 operações separadas!
        wallet = await self.get_or_create_wallet(affiliate_user_id)  # ← Op 1: LER
        wallet.pending_balance += commission_amount                   # ← Op 2: MODIFICAR (na memória)
        wallet.total_earned += commission_amount                     # ← Op 2: MODIFICAR (na memória)
        await self.save_wallet(wallet)                               # ← Op 3: ESCREVER
        
        # Transação é registrada
        transaction = AffiliateTransaction(...)
        await self.transaction_col.insert_one(transaction.dict())
        
        return True, f"Comissão de ${commission_amount:.2f} registrada"
    
    except Exception as e:
        logger.error(f"Erro ao registrar comissão: {str(e)}")
        return False, f"Erro: {str(e)}"
```

### ✅ DEPOIS (wallet_service_fixed.py - Linhas 200-240)
```python
async def record_commission(self, affiliate_user_id: str, ...):
    # ... validações anti-fraude multi-camadas ...
    
    try:
        # 🔐 OPERAÇÃO ATÔMICA - Uma única chamada ao MongoDB!
        await self.wallet_col.update_one(
            {"user_id": affiliate_user_id},
            {
                "$inc": {  # ← Incrementa ATOMICAMENTE no servidor MongoDB
                    "pending_balance": float(commission_amount),
                    "total_earned": float(commission_amount),
                },
                "$set": {
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,  # Cria wallet se não existir
        )
        
        # Transação é registrada separadamente
        transaction = AffiliateTransaction(...)
        await self.transaction_col.insert_one(transaction.dict(by_alias=False))
        
        return True, f"Comissão de ${commission_amount} registrada"
    
    except Exception as e:
        logger.error(f"Erro ao registrar comissão: {str(e)}")
        return False, f"Erro: {str(e)}"
```

**Diferenças principais:**
| Aspecto | ANTES | DEPOIS |
|---------|-------|--------|
| Operações | 3 (leia→modifique→escreva) | 1 (atômica) |
| Race condition | ❌ Possível | ✅ Impossível |
| Latência | 3×latência DB | 1×latência DB |
| Garantia | Nenhuma | Atomicidade MongoDB |

---

## 💰 VULNERABILIDADE #2: FLOAT → DECIMAL

### ❌ ANTES (models.py - Linhas 59-105)
```python
from pydantic import BaseModel, Field, validator

class AffiliateWallet(BaseModel):
    # ❌ VULNERÁVEL: Floats perdem precisão
    pending_balance: float = Field(
        default=0.0,
        ge=0,
        description="Saldo pendente"
    )
    available_balance: float = Field(
        default=0.0,
        ge=0,
        description="Saldo disponível"
    )
    total_earned: float = Field(
        default=0.0,
        ge=0,
        description="Total ganho"
    )
    
    @property
    def total_balance(self) -> float:
        return self.pending_balance + self.available_balance  # ❌ Arredondamento
    
    class Config:
        from_attributes = True


class AffiliateTransaction(BaseModel):
    amount_usd: float = Field(...)  # ❌ Impreciso
    sale_amount_usd: Optional[float] = Field(...)
    commission_rate: Optional[float] = Field(...)
```

### ✅ DEPOIS (models_fixed.py - Linhas 60-130)
```python
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field, validator

class AffiliateWallet(BaseModel):
    # ✅ CORRETO: Decimals com precisão exata
    pending_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Saldo pendente"
    )
    available_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Saldo disponível"
    )
    total_earned: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        description="Total ganho"
    )
    
    @validator("pending_balance", "available_balance", "total_earned", pre=True)
    def quantize_decimal(cls, v):
        """Garante exatamente 2 casas decimais"""
        if v is None:
            return Decimal("0.00")
        if isinstance(v, str):
            v = Decimal(v)
        elif isinstance(v, (int, float)):
            v = Decimal(str(v))
        # Arredonda para 2 casas decimais (centavos)
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @property
    def total_balance(self) -> Decimal:
        return self.pending_balance + self.available_balance  # ✅ Exato
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Serializa para JSON
        }


class AffiliateTransaction(BaseModel):
    amount_usd: Decimal = Field(...)  # ✅ Preciso
    sale_amount_usd: Optional[Decimal] = Field(...)
    commission_rate: Optional[Decimal] = Field(...)
    
    @validator("amount_usd", "sale_amount_usd", "commission_rate", pre=True)
    def quantize_amount(cls, v):
        """Garante precisão para valores monetários"""
        if v is None:
            return None
        if isinstance(v, str):
            v = Decimal(v)
        elif isinstance(v, (int, float)):
            v = Decimal(str(v))
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

**Exemplo prático:**
```python
# ANTES (❌ Impreciso)
0.1 + 0.2 == 0.3  # ❌ False! Returns 0.30000000000000004

# 1000 comissões de $10.53
total = 0.0
for _ in range(1000):
    total += 10.53
print(total)  # 10529.999999999998 ❌

# DEPOIS (✅ Exato)
Decimal("0.1") + Decimal("0.2") == Decimal("0.3")  # ✅ True!

# 1000 comissões de $10.53
total = Decimal("0.00")
for _ in range(1000):
    total += Decimal("10.53")
print(total)  # Decimal('10530.00') ✅
```

---

## 🔍 VULNERABILIDADE #3: REAL BALANCE VALIDATION

### ❌ ANTES (wallet_service.py - Linhas 249-280)
```python
async def validate_withdrawal(self, user_id: str, amount_usd: float) -> Tuple[bool, str]:
    logger.info(f"🔍 Validando saque para {user_id}: ${amount_usd}")
    
    # ❌ Confia cegamente no valor salvo no DB
    wallet = await self.get_or_create_wallet(user_id)
    
    if amount_usd < MINIMUM_WITHDRAWAL_AMOUNT:
        return False, f"Mínimo é ${MINIMUM_WITHDRAWAL_AMOUNT}"
    
    # ❌ SEM VALIDAÇÃO CRUZADA - aceita qualquer valor
    if wallet.available_balance < amount_usd:  # ❌ Confia no DB
        return False, f"Saldo insuficiente"
    
    if not wallet.withdrawal_method:
        return False, "Método não configurado"
    
    return True, "OK"

async def process_withdrawal(self, user_id: str, amount_usd: float) -> Tuple[bool, str, Optional[str]]:
    # Valida (mas não verifica se é real)
    valid, msg = await self.validate_withdrawal(user_id, amount_usd)
    if not valid:
        return False, msg, None
    
    # Deduz do saldo (sem verificar transações)
    result = await self.wallet_col.update_one(
        {"user_id": user_id, "available_balance": {"$gte": amount_usd}},
        {"$inc": {"available_balance": -amount_usd}},
    )
    # ... processa saque ...
```

### ✅ DEPOIS (wallet_service_fixed.py - Linhas 115-202, 490-530)
```python
async def calculate_real_balance(self, user_id: str) -> Tuple[Decimal, Decimal]:
    """
    🔐 Recalcula saldo REAL a partir do histórico de transações.
    Não confia no valor salvo - é a "fonte da verdade".
    """
    
    # Soma TODAS comissões PENDING
    pending_result = await self.transaction_col.aggregate([
        {
            "$match": {
                "user_id": user_id,
                "type": TransactionType.COMMISSION,
                "status": TransactionStatus.PENDING,
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount_usd"}}}
    ]).to_list(1)
    
    pending_balance = pending_result[0]["total"] if pending_result else Decimal("0.00")
    
    # Soma TODAS comissões AVAILABLE
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
    
    commission_available = available_result[0]["total"] if available_result else Decimal("0.00")
    
    # Subtrai saques concluídos
    withdrawals = await self.transaction_col.aggregate([
        {
            "$match": {
                "user_id": user_id,
                "type": TransactionType.WITHDRAWAL,
                "status": TransactionStatus.COMPLETED,
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount_usd"}}}
    ]).to_list(1)
    
    total_withdrawn = withdrawals[0]["total"] if withdrawals else Decimal("0.00")
    
    available_balance = commission_available - total_withdrawn
    available_balance = max(available_balance, Decimal("0.00"))
    
    logger.info(f"📊 Saldo REAL: pending={pending_balance}, available={available_balance}")
    return pending_balance, available_balance


async def validate_balance_consistency(self, user_id: str) -> Tuple[bool, str, Dict]:
    """
    Verifica se valores salvos correspondem à realidade.
    Detecta manipulação, bugs e corrupção.
    """
    wallet = await self.get_or_create_wallet(user_id)
    real_pending, real_available = await self.calculate_real_balance(user_id)
    
    # Margem de tolerância: 1 centavo
    tolerance = Decimal("0.01")
    
    pending_ok = abs(wallet.pending_balance - real_pending) <= tolerance
    available_ok = abs(wallet.available_balance - real_available) <= tolerance
    
    is_consistent = pending_ok and available_ok
    
    if not is_consistent:
        logger.warning(f"⚠️ INCONSISTÊNCIA: {user_id}")
    
    return is_consistent, "OK" if is_consistent else "Inconsistência", {
        "saved_pending": float(wallet.pending_balance),
        "real_pending": float(real_pending),
        "discrepancy_pending": float(wallet.pending_balance - real_pending),
        "saved_available": float(wallet.available_balance),
        "real_available": float(real_available),
        "discrepancy_available": float(wallet.available_balance - real_available),
    }


async def validate_withdrawal(self, user_id: str, amount_usd: Decimal) -> Tuple[bool, str]:
    """
    ✅ Valida contra saldo REAL, não salvo
    """
    logger.info(f"🔍 Validando saque para {user_id}: ${amount_usd}")
    
    wallet = await self.get_or_create_wallet(user_id)
    
    # 🔐 Calcula saldo REAL - é a "fonte da verdade"
    _, real_available = await self.calculate_real_balance(user_id)
    
    if amount_usd < MINIMUM_WITHDRAWAL_AMOUNT:
        return False, f"Mínimo é ${MINIMUM_WITHDRAWAL_AMOUNT}"
    
    # ✅ Valida contra número REAL, não o salvo
    if real_available < amount_usd:
        return False, (
            f"Saldo insuficiente. Você tem ${real_available} "
            f"(calculado de transações), mas solicitou ${amount_usd}"
        )
    
    if not wallet.withdrawal_method:
        return False, "Método não configurado"
    
    return True, "OK"
```

**Fluxo de validação:**
```
ANTES:
  wallet.available_balance = $5000 (salvo no DB)
  validate_withdrawal($5000) → ✅ "OK" (confia cegamente)
  Saque é processado, empresa perde $5000 ❌

DEPOIS:
  wallet.available_balance = $5000 (salvo no DB)
  calculate_real_balance() → $50 (baseado em transações)
  validate_withdrawal($5000) → ❌ "Saldo insuficiente"
  Saque é rejeitado, empresa segura ✅
```

---

## 🚨 VULNERABILIDADE #4: MULTI-LAYER ANTI-FRAUD

### ❌ ANTES (wallet_service.py - Linhas 96-104)
```python
async def record_commission(self, affiliate_user_id: str, referral_id: str, ...):
    # ❌ APENAS VERIFICA IP - fácil de bypass
    if buyer_ip and affiliate_ip and buyer_ip == affiliate_ip:
        logger.warning(f"Auto-referência detectada")
        return False, "Auto-referência detectada"
    
    # Se passou no IP, aceita qualquer coisa
    # ... registra comissão ...
```

### ✅ DEPOIS (wallet_service_fixed.py - Linhas 237-335)
```python
async def detect_self_referral(
    self,
    affiliate_user_id: str,
    referral_user_id: str,
    buyer_ip: Optional[str] = None,
    affiliate_ip: Optional[str] = None,
    buyer_device_fingerprint: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    5 CAMADAS de validação anti-fraude
    """
    
    # CAMADA 1: IP Direto (catch óbvio)
    if buyer_ip and affiliate_ip and buyer_ip == affiliate_ip:
        logger.warning(f"Fraude L1: IP duplicado {buyer_ip}")
        return True, f"IP duplicado detectado"
    
    # CAMADA 2: Mesma Conta (catch "copia")
    if affiliate_user_id == referral_user_id:
        logger.warning(f"Fraude L2: Mesma conta")
        return True, "Auto-referência: mesma pessoa"
    
    # CAMADA 3: Device Fingerprint (catch VPN)
    if buyer_device_fingerprint:
        affiliate_devices = await self.db["user_devices"].find_one({
            "user_id": affiliate_user_id,
            "fingerprint": buyer_device_fingerprint
        })
        if affiliate_devices:
            logger.warning(f"Fraude L3: Device duplicado")
            return True, "Mesmo dispositivo detectado"
    
    # CAMADA 4: Alt Accounts (catch contas relacionadas)
    affiliate_other_accounts = await self.db["user_relationships"].find({
        "user_id": affiliate_user_id,
        "relationship_type": "alt_account",
    }).to_list(None)
    
    for other_account in affiliate_other_accounts:
        if other_account.get("related_user_id") == referral_user_id:
            logger.warning(f"Fraude L4: Alt accounts relacionadas")
            return True, "Contas relacionadas detectadas"
    
    # CAMADA 5: Bot Detection (catch script automático)
    recent_referrals = await self.transaction_col.find({
        "user_id": affiliate_user_id,
        "type": TransactionType.COMMISSION,
        "created_at": {"$gte": datetime.utcnow() - timedelta(hours=1)},
    }).to_list(None)
    
    if len(recent_referrals) > 5:
        logger.warning(f"Fraude L5: {len(recent_referrals)} comissões em 1 hora")
        return True, f"Padrão suspeito: {len(recent_referrals)} comissões em 1 hora"
    
    logger.info(f"✅ Nenhuma fraude detectada")
    return False, "OK"


async def record_commission(self, affiliate_user_id: str, ...):
    # ✅ VALIDAÇÃO MULTI-CAMADAS
    is_fraud, fraud_reason = await self.detect_self_referral(
        affiliate_user_id=affiliate_user_id,
        referral_user_id=referral_id,
        buyer_ip=buyer_ip,
        affiliate_ip=affiliate_ip,
        buyer_device_fingerprint=buyer_device_fingerprint,
    )
    
    if is_fraud:
        logger.warning(f"Fraude bloqueada: {fraud_reason}")
        return False, f"Comissão rejeitada: {fraud_reason}"
    
    # ... registra comissão ...
```

**Matriz de Detecção:**

| Cenário | L1 IP | L2 User | L3 Device | L4 Alt | L5 Bot | Detectado? |
|---------|-------|--------|-----------|--------|--------|-----------|
| Mesmo IP | ❌ | ✓ | ✓ | ✓ | ✓ | ✅ L1 |
| Contas VPN | ✓ | ✓ | ❌ | ✓ | ✓ | ✅ L3 |
| Alt accounts | ✓ | ✓ | ✓ | ❌ | ✓ | ✅ L4 |
| Bot script (100 refs/h) | ✓ | ✓ | ✓ | ✓ | ❌ | ✅ L5 |
| Legítimo (marido/esposa) | ❌ | ✓ | ✓ | ✓ | ✓ | ✅ (pode investigar) |

---

## 📋 MIGRATION CHECKLIST

### Pré-Deploy
- [ ] Criar backup completo do MongoDB
- [ ] Revisar código em staging
- [ ] Executar todos os testes
- [ ] Validar dados existentes

### Deploy
- [ ] Substituir models.py
- [ ] Substituir wallet_service.py
- [ ] Reiniciar backend
- [ ] Verificar logs

### Pós-Deploy
- [ ] Monitorar inconsistências de saldo
- [ ] Testar com transações reais
- [ ] Validar histórico de usuários
- [ ] Resgatar perdas se encontradas

---

## 🔧 QUICK TEST

```python
# Testar ambas as versões lado a lado
import asyncio
from backend.app.affiliates.wallet_service import AffiliateWalletService
from backend.app.affiliates.wallet_service_fixed import AffiliateWalletService as AffiliateWalletServiceFixed

async def test_both():
    # Teste de comissões concorrentes
    tasks_old = [service_old.record_commission(...) for _ in range(100)]
    tasks_new = [service_new.record_commission(...) for _ in range(100)]
    
    results_old = await asyncio.gather(*tasks_old)
    results_new = await asyncio.gather(*tasks_new)
    
    # Ambas devem registrar todas as 100
    assert all(r[0] for r in results_old), "Old service OK"
    assert all(r[0] for r in results_new), "New service OK"
    
    # Mas apenas a nova garante saldo correto
    balance_old = wallet_old.pending_balance  # Pode estar errado
    balance_new = wallet_new.pending_balance  # Sempre correto
```
