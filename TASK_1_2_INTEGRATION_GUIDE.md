# 🔗 INTEGRAÇÃO TASK 1.1 + TASK 1.2

**Data:** Março 23, 2026  
**Objetivo:** Mostrar como TradingExecutor (Task 1.1) usa validate_order_executable (Task 1.2)

---

## 📊 ARQUITETURA INTEGRADA

```
┌─────────────────────────────────────────────────────────────┐
│                    Bot Strategy Signal                       │
│                    (compra 0.1 BTC @ 42000)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         TradingExecutor (Task 1.1)                           │
│         ┌────────────────────────────────────────────┐      │
│         │ execute_market_order()                     │      │
│         ├────────────────────────────────────────────┤      │
│         │ Step 1: Validação Pré-Trade               │      │
│         │ ────────────────────────────────────────   │      │
│         │  └─→ _validate_order()                    │      │
│         │      └─→ [AQUI USA TASK 1.2]              │      │
│         │          validate_order_executable()      │      │
│         │                                            │      │
│         │  Resultado:                                │      │
│         │  • (True, None) → Continua (Step 2)      │      │
│         │  • (False, "error") → Retorna erro       │      │
│         │                                            │      │
│         ├────────────────────────────────────────────┤      │
│         │ Step 2: Persistência (pending)            │      │
│         │ Step 3: Execução na Exchange              │      │
│         │ Step 4: Monitoramento                     │      │
│         │ Step 5: Sincronização                     │      │
│         └────────────────────────────────────────────┘      │
└────────────────┬─────────────────────────────────────────────┘
                 ▼
        ✓ Ordem executada com sucesso
        ou
        ✗ Erro de validação (bloqueado em Step 1)
```

---

## 💾 FLUXO DE CÓDIGO

### Atual (Task 1.1)

```python
# backend/app/trading/executor.py

class TradingExecutor:
    async def _validate_order(self, symbol: str, side: str, quantity: Decimal):
        """
        Validação pré-trade (Step 1 do pipeline)
        
        Chamadas:
        1. RiskManager checks (existente)
        2. PreTradeValidator checks (existente)
        3. ❌ FALTA: Validação com exchange real
        """
        
        # RiskManager
        valid, reason = self.risk_manager.check_can_trade(...)
        if not valid:
            raise ValidationFailedError(reason)
        
        # PreTradeValidator (genérico)
        validator = PreTradeValidator()
        result = validator.validate_order(...)
        if not result.valid:
            raise ValidationFailedError(result.errors[0])
        
        # ❌ AQUI ESTAVA FALTANDO: Validação com saldo REAL
```

### Novo (Task 1.2 Integrada)

```python
# backend/app/trading/executor.py
# ATUALIZADO para usar Task 1.2

from app.trading.pre_trade_validation import validate_order_executable

class TradingExecutor:
    async def _validate_order(self, symbol: str, side: str, quantity: Decimal):
        """
        Validação pré-trade (Step 1 do pipeline)
        
        Chamadas:
        1. RiskManager checks (existente)
        2. PreTradeValidator checks (existente)
        3. ✅ NOVO: validate_order_executable (Task 1.2)
           └─→ Valida saldo REAL
           └─→ Integra com todos os sistemas
        """
        
        # RiskManager
        valid, reason = self.risk_manager.check_can_trade(...)
        if not valid:
            raise ValidationFailedError(reason)
        
        # PreTradeValidator (genérico)
        validator = PreTradeValidator()
        result = validator.validate_order(...)
        if not result.valid:
            raise ValidationFailedError(result.errors[0])
        
        # ✅ NOVO: Task 1.2 — Validação profunda com exchange
        is_valid, error = await validate_order_executable(
            user_id=self.user_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            current_price=None  # Pega automaticamente
        )
        
        if not is_valid:
            raise ValidationFailedError(f"Pre-trade validation failed: {error}")
    
    async def execute_market_order(self, symbol: str, side: str, quantity: Decimal):
        """Fluxo completo com Task 1.2 integrada."""
        
        # 1. Validação (usa Task 1.2)
        await self._validate_order(symbol, side, quantity)
        
        # 2-5. Resto do fluxo (persistência, execução, monitoramento, sync)
        # ...
```

---

## 🔄 SEQUÊNCIA DE CHAMADAS

```
User chama: executor.execute_market_order("BTC-USDT", "BUY", 0.1)

┌─────────────────────────────────────────────────────────┐
│ execute_market_order()                                   │
│ └─→ _validate_order()                                   │
│     ├─→ RiskManager.check_can_trade()                  │
│     │   ├─→ is_user_killed?                            │
│     │   ├─→ is_in_cooldown?                            │
│     │   └─→ daily_loss_limit?                          │
│     │                                                   │
│     ├─→ PreTradeValidator.validate_order()            │
│     │   ├─→ _adjust_quantity()                         │
│     │   ├─→ _validate_order_size()                     │
│     │   ├─→ _validate_notional()                       │
│     │   └─→ _validate_balance()                        │
│     │                                                   │
│     └─→ validate_order_executable()  ← TASK 1.2      │
│         ├─→ CredentialsRepository.get_credentials()    │
│         ├─→ KuCoinClient.get_account_balance()        │
│         ├─→ get_market_info_from_ccxt()               │
│         ├─→ Validate qty (min/max)                     │
│         ├─→ Validate balance (BUY/SELL)              │
│         ├─→ Validate notional minimum                  │
│         ├─→ RiskManager checks (kill-switch, cooldown) │
│         └─→ Return (True/False, message)              │
│                                                        │
│ Se passou em todas as 3 camadas:                      │
│ └─→ _persist_pending_order()                         │
│ └─→ _place_at_exchange()                            │
│ └─→ _monitor_until_filled()                         │
│ └─→ _sync_to_database()                             │
│                                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 MUDANÇAS NECESSÁRIAS EM executor.py

### Arquivo: `backend/app/trading/executor.py`

**Adições necessárias:**

#### 1. Import

```python
# Adicionar no topo do arquivo:

from app.trading.pre_trade_validation import validate_order_executable
```

#### 2. Atualizar método `_validate_order()`

```python
async def _validate_order(self, symbol: str, side: str, quantity: Decimal):
    """
    Valida se ordem pode ser executada.
    
    Agora com 3 camadas de validação:
    1. RiskManager (kill-switch, cooldown, daily loss)
    2. PreTradeValidator (genérico, precision, etc)
    3. validate_order_executable (saldo REAL, market info, risk limits)
    """
    
    # ✓ Camada 1: RiskManager
    valid, reason = self.risk_manager.check_can_trade(symbol, side, quantity)
    if not valid:
        logger.warning(f"RiskManager rejected: {reason}")
        raise ValidationFailedError(reason)
    
    # ✓ Camada 2: PreTradeValidator (genérico)
    validator = PreTradeValidator()
    market_info = await get_market_info_from_ccxt(symbol, self.client.exchange)
    balance = await get_balance_for_currency(
        symbol.split("/")[0] if side == "SELL" else symbol.split("/")[1],
        self.client.exchange
    )
    
    result = validator.validate_order(
        side=OrderSide(side.lower()),
        quantity=quantity,
        price=await get_last_price(symbol, self.client.exchange),
        market=market_info,
        balance=balance,
        is_market_order=True
    )
    
    if not result.valid:
        logger.warning(f"PreTradeValidator rejected: {result.errors}")
        raise ValidationFailedError(result.errors[0])
    
    # ✓ Camada 3: Task 1.2 — Validação com exchange REAL
    is_valid, error_msg = await validate_order_executable(
        user_id=self.user_id,
        symbol=symbol,
        side=side.upper(),
        quantity=quantity,
        current_price=None  # Pega automaticamente
    )
    
    if not is_valid:
        logger.warning(f"validate_order_executable rejected: {error_msg}")
        raise ValidationFailedError(f"Pre-trade validation failed: {error_msg}")
    
    logger.info(f"✓ Order validation passed: {symbol} {side} {quantity}")
```

---

## 🧪 TESTE DE INTEGRAÇÃO

### Como Testar

```bash
# 1. Rodar testes de Task 1.2 primeiro
pytest backend/tests/unit/test_pre_trade_validation_task_1_2.py -v
# ✅ 16 testes passam

# 2. Atualizar executor.py com as mudanças acima

# 3. Rodar testes de Task 1.1
pytest backend/tests/unit/test_trading_executor.py -v
# ✅ Testes ainda devem passar (precisam dos mocks atualizados)

# 4. Rodar testes de integração com testnet
pytest backend/tests/integration/test_trading_executor_testnet.py -v -s
# ✅ Verifica com exchange REAL
```

---

## 🔐 O QUE TASK 1.2 MUDA

### Antes (sem Task 1.2)

```python
# executor.py validava:
✓ Kill-switch (RiskManager)
✓ Daily loss limit (RiskManager)
✓ Precision/min max (PreTradeValidator)
✗ Saldo REAL (não validava!)
✗ Info real do mercado (não validava!)
✗ Limite de posições (não validava!)
```

### Depois (com Task 1.2)

```python
# executor.py + validate_order_executable agora validam:
✓ Kill-switch (RiskManager)
✓ Daily loss limit (RiskManager)
✓ Precision/min max (PreTradeValidator)
✓ Saldo REAL (validate_order_executable)  ← NOVO
✓ Info real do mercado (validate_order_executable)  ← NOVO
✓ Limite de posições (validate_order_executable)  ← NOVO
✓ Credenciais (validate_order_executable)  ← NOVO
```

---

## 📊 IMPACTO NA EXECUÇÃO

### Cenário 1: Ordem Válida

```
User: Comprar 0.1 BTC @ 42000
Saldo: 5 BTC, 50000 USDT
Kill-switch: Off
Cooldown: Off
Max posições: 10 (tem 2 abertas)

┌─────────────────────────────────────────┐
│ Resultado: ✅ EXECUTA                   │
│                                         │
│ Todas as 3 camadas passaram:           │
│ • RiskManager: OK                       │
│ • PreTradeValidator: OK                 │
│ • validate_order_executable: OK         │
│                                         │
│ Prossegue para persistência & execução │
└─────────────────────────────────────────┘
```

### Cenário 2: Sem Saldo (Detectado por Task 1.2)

```
User: Comprar 0.1 BTC @ 42000  (custa ~4242 USDT)
Saldo: 5 BTC, 100 USDT          (insuficiente!)
Kill-switch: Off
Cooldown: Off

┌─────────────────────────────────────────┐
│ Resultado: ❌ REJEITA                   │
│                                         │
│ • RiskManager: ✅ OK                    │
│ • PreTradeValidator: ✅ OK              │
│ • validate_order_executable: ❌ FALHOU  │
│   └─→ "Saldo insuficiente em USDT"     │
│                                         │
│ Erro retornado ao usuário sem ver      │
│ a ordem posta na exchange              │
└─────────────────────────────────────────┘
```

### Cenário 3: Kill-Switch Ativo (Já detectado, mas agora com validação extra)

```
User: Qualquer ordem
Kill-switch: ON (ativado por admin)

┌─────────────────────────────────────────┐
│ Resultado: ❌ REJEITA                   │
│                                         │
│ • RiskManager: ❌ FALHOU                │
│   └─→ "Kill-switch ativo"              │
│                                         │
│ Task 1.2 also checks:                  │
│ • validate_order_executable: ❌ FALHOU  │
│   └─→ "Kill-switch ativo"              │
│                                         │
│ Double check → Mais seguro              │
└─────────────────────────────────────────┘
```

---

## 💡 BENEFÍCIOS DA INTEGRAÇÃO

### 1. Segurança em Camadas

```
3 camadas independentes = 3x menos chance de bug passar
```

### 2. Validação Real

```
Não é simulação — Task 1.2 valida contra saldo REAL
```

### 3. Auditability

```
Cada validação loga seus resultados para auditoria
```

### 4. User Friendly

```
Erros claros: "Saldo insuficiente em USDT"
Não expõe internals: Não loga API keys
```

---

## ✅ CHECKLIST DE INTEGRAÇÃO

- [ ] 1. Adicionar import em executor.py
- [ ] 2. Atualizar método `_validate_order()`
- [ ] 3. Rodar testes de Task 1.2
- [ ] 4. Rodar testes de Task 1.1
- [ ] 5. Testar manualmente com ordem real
- [ ] 6. Validar logs (sem secrets)
- [ ] 7. Code review
- [ ] 8. Deploy staging
- [ ] 9. Deploy production

---

## 🚀 PRÓXIMAS TAREFAS

### Hoje (2-3 horas)
- [ ] Integrar Task 1.2 em executor.py
- [ ] Atualizar testes de executor
- [ ] Testar com testnet

### Amanhã (1-2 horas)
- [ ] Code review
- [ ] Task 1.3 (BotsService)

### Semana que vem
- [ ] Task 2.x (Segurança)

---

## 📞 COMO REVERTIR SE NECESSÁRIO

Se algo der errado:

```bash
# 1. Revert executor.py mudanças
git checkout backend/app/trading/executor.py

# 2. Remover import de Task 1.2
# (volta para validação sem saldo REAL)

# 3. O sistema continua funcionando
# (mas sem validação profunda)
```

---

**Task 1.2 está pronto para ser integrado em Task 1.1** ✅

*Próximo passo: Atualizar executor.py e testar*
