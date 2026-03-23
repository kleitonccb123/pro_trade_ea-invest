# 📖 GUIA DE USO — TradingExecutor

**Data:** Março 23, 2026  
**Versão:** 1.0 (Beta)  
**Status:** ✅ Pronto para testes

---

## ÍNDICE

1. [Visão Geral](#1-visão-geral)
2. [Instalação & Setup](#2-instalação--setup)
3. [Uso Básico](#3-uso-básico)
4. [Fluxo Completo de Operação](#4-fluxo-completo-de-operação)
5. [Tratamento de Erros](#5-tratamento-de-erros)
6. [Exemplos Práticos](#6-exemplos-práticos)
7. [API Reference](#7-api-reference)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. VISÃO GERAL

`TradingExecutor` é a classe central que orquestra todo o fluxo de trading:

```
Usuário/Bot
    ↓
TradingExecutor
    ├─ 1. Validação pré-trade
    ├─ 2. Persistência idempotente
    ├─ 3. Execução no exchange
    ├─ 4. Monitoramento até fill
    └─ 5. Sincronização no BD
    ↓
Ordem preenchida & sincronizada
```

### Características Principais

✅ **Idempotência garantida**: Mesma ordem não é executada 2x  
✅ **Persistência antes de envio**: Sem perda de dados  
✅ **Monitoramento automático**: Até para ordem ser preenchida  
✅ **Sincronização**: Status no banco = status real na exchange  
✅ **Trata falhas de rede**: Com polling inteligente  
✅ **Limite de segurança**: Kill-switch, daily limits, etc  

---

## 2. INSTALAÇÃO & SETUP

### Pré-requisitos

```bash
# Python 3.10+
python --version

# Dependências já instaladas (requirements.txt):
# - fastapi
# - motor (MongoDB async)
# - python-kucoin
# - pydantic
```

### Estrutura de arquivos

```
backend/
├── app/
│   ├── trading/
│   │   ├── executor.py          ← Classe principal (NOVO)
│   │   ├── executor_example.py  ← Endpoints FastAPI (NOVO)
│   │   ├── credentials_repository.py
│   │   ├── pre_trade_validation.py
│   │   ├── risk_manager.py
│   │   └── idempotency_store.py
│   ├── exchanges/
│   │   └── kucoin/
│   │       ├── client.py        ← KuCoin raw client
│   │       └── normalizer.py
│   └── ...
├── tests/
│   └── unit/
│       └── test_trading_executor.py  ← Testes (NOVO)
```

### Integração em main.py

```python
# backend/app/main.py

from app.trading.executor_example import router as executor_router

# Registrar router
app.include_router(executor_router)
```

---

## 3. USO BÁSICO

### Exemplo Minimal

```python
from app.trading.executor import TradingExecutor
from decimal import Decimal

# 1. Criar executor
executor = TradingExecutor(
    user_id="user_123",
    exchange="kucoin",
    testnet=True  # Usar testnet para testes
)

# 2. Inicializar (conecta com credenciais do usuário)
await executor.initialize()

# 3. Executar ordem
order = await executor.execute_market_order(
    symbol="BTC-USDT",
    side="buy",
    quantity=Decimal("0.1")
)

# 4. Resultado
print(f"Order ID: {order['_id']}")
print(f"Status: {order['status']}")  # "filled"
print(f"Filled Price: {order['filled_price']}")

# 5. Limpeza (opcional)
await executor.close()
```

### Output esperado

```
✅ TradingExecutor inicializado para user=user_123, exchange=kucoin, testnet=True
🔄 Inicializando TradingExecutor para user user_123...
✅ Ping bem-sucedido. Server time: 1234567890
✅ Account ID obtido: 6234c685234c..._trading
✅ TradingExecutor inicializado com sucesso
🚀 Iniciando execução de ordem: BUY 0.1 BTC-USDT (user=user_123)
  [1/5] Validando ordem...
  ✅ Validação OK
  [2/5] Persistindo ordem no banco...
  ✅ Ordem persistida: 507f1f77bcf86cd799439011
  [3/5] Enviando ordem para exchange...
  ✅ Ordem enviada. Exchange ID: oid_xxxxx
  [4/5] Monitorando até preenchimento (max 60s)...
  Tentativa 1/60: Status=OPEN, Filled=0/0.1
  Tentativa 2/60: Status=OPEN, Filled=0/0.1
  Tentativa 3/60: Status=FILLED, Filled=0.1/0.1
  ✅ Ordem preenchida em 3 tentativas
  [5/5] Sincronizando resultado no banco...
  ✅ Sincronização completa
✅ ORDEM EXECUTADA COM SUCESSO: BUY 0.1 BTC-USDT @ 42000.50
```

---

## 4. FLUXO COMPLETO DE OPERAÇÃO

### Passo a Passo

#### Passo 1: Instanciar

```python
executor = TradingExecutor(
    user_id="user_123",        # ID do usuário dono da ordem
    exchange="kucoin",         # "kucoin" (Binance em breve)
    testnet=True,              # True = sandbox, False = mainnet
    max_monitoring_time=60,    # Máx segundos para monitorar
    polling_interval=1.0       # Intervalo entre polls (segundos)
)
```

#### Passo 2: Inicializar

```python
await executor.initialize()
```

O que acontece internamente:
1. Obter credenciais criptografadas do MongoDB
2. Descriptografar (Fernet)
3. Criar cliente KuCoin com as credenciais
4. Fazer test ping
5. Obter account_id
6. Guardar em `executor.credentials`

#### Passo 3: Executar Ordem

```python
order = await executor.execute_market_order(
    symbol="BTC-USDT",
    side="buy",
    quantity=Decimal("0.1"),
    take_profit=Decimal("45000"),    # Opcional
    stop_loss=Decimal("40000")       # Opcional
)
```

O que acontece internamente:
1. Validação (saldo, limites, risco)
2. Persiste no MongoDB com `client_oid` idempotente
3. Envia para KuCoin
4. Atualiza banco com `exchange_order_id`
5. Poll até FILLED (máx 60 tentativas × 1s = 60s)
6. Sincroniza resultado (filled_price, filled_quantity, etc)

#### Passo 4: Usar Resultado

```python
# Acessar dados
print(order["_id"])              # ObjectId da ordem no banco
print(order["exchange_order_id"]) # ID na KuCoin
print(order["filled_price"])      # Preço de execução
print(order["filled_quantity"])   # Quantidade preenchida
print(order["status"])            # "filled"
```

---

## 5. TRATAMENTO DE ERROS

### Erros Esperadoss

```python
from app.trading.executor import (
    ValidationFailedError,      # Validação pré-trade falhou
    InsufficientBalanceError,   # Saldo insuficiente
    ExchangeTimeoutError,       # Não preencheu em tempo
    OrderExecutionError         # Erro genérico
)

try:
    order = await executor.execute_market_order(...)
    
except ValidationFailedError as e:
    print(f"❌ Validação falhou: {e}")
    # Usuario pode: aumentar saldo, reduzir quantidade
    
except InsufficientBalanceError as e:
    print(f"❌ Saldo insuficiente: {e}")
    # Usuario precisa: depositar mais
    
except ExchangeTimeoutError as e:
    print(f"❌ Timeout: {e}")
    # Usuario pode: retentar, ou verificar manualmente na KuCoin
    
except OrderExecutionError as e:
    print(f"❌ Erro na execução: {e}")
    # Erro genérico - verificar logs
```

### Recuperação

```python
# Se falhar, a ordem NÃO foi perdida!
# Está no banco com status "pending" ou "failed"

# Verificar depois
order_from_db = await db.trading_orders.find_one({
    "_id": order["_id"]
})

print(order_from_db["status"])  # "pending" | "failed"
print(order_from_db["error"])   # Mensagem de erro
```

---

## 6. EXEMPLOS PRÁTICOS

### Exemplo 1: Executar Ordem Simples

```python
async def buy_bitcoin():
    executor = TradingExecutor("user_123", "kucoin", testnet=True)
    await executor.initialize()
    
    order = await executor.execute_market_order(
        symbol="BTC-USDT",
        side="buy",
        quantity=Decimal("0.05")
    )
    
    print(f"✅ Comprei BTC a {order['filled_price']}")

asyncio.run(buy_bitcoin())
```

### Exemplo 2: Executar com Tratamento de Erro

```python
async def smart_order():
    executor = TradingExecutor("user_123", "kucoin", testnet=True)
    
    try:
        await executor.initialize()
        
        order = await executor.execute_market_order(
            symbol="ETH-USDT",
            side="sell",
            quantity=Decimal("1.0")
        )
        
        print(f"✅ Vendi ETH a {order['filled_price']}")
        return order
        
    except ValidationFailedError as e:
        print(f"❌ Validação: {e}")
        return None
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None
    finally:
        await executor.close()

order = asyncio.run(smart_order())
```

### Exemplo 3: Usar via HTTP API

```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }' > /tmp/auth.json

TOKEN=$(jq -r '.access_token' /tmp/auth.json)

# 2. Executar ordem
curl -X POST http://localhost:8000/api/trading/execute/market-order \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC-USDT",
    "side": "buy",
    "quantity": 0.1
  }'

# Response:
# {
#   "id": "507f1f77bcf86cd799439011",
#   "status": "filled",
#   "filled_price": 42000.50,
#   ...
# }
```

### Exemplo 4: Pelo Frontend

```typescript
// src/hooks/useExecuteOrder.ts

import { useCallback } from 'react';
import axios from 'axios';

export function useExecuteOrder() {
  const executeMarketOrder = useCallback(async (symbol, side, quantity) => {
    const token = localStorage.getItem('access_token');
    
    const response = await axios.post(
      'http://localhost:8000/api/trading/execute/market-order',
      {
        symbol,
        side,
        quantity: parseFloat(quantity)
      },
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
    
    return response.data;
  }, []);
  
  return { executeMarketOrder };
}

// Uso em componente
function OrderForm() {
  const { executeMarketOrder } = useExecuteOrder();
  
  const handleSubmit = async () => {
    const order = await executeMarketOrder('BTC-USDT', 'buy', '0.1');
    console.log('✅ Ordem:', order);
  };
  
  return <button onClick={handleSubmit}>Comprar 0.1 BTC</button>;
}
```

---

## 7. API REFERENCE

### `TradingExecutor.__init__()`

```python
TradingExecutor(
    user_id: str,              # ID do usuário
    exchange: str = "kucoin",  # Exchange
    testnet: bool = True,      # Usar testnet?
    max_monitoring_time: int = 60,     # Max segundos
    polling_interval: float = 1.0      # Intervalo
)
```

### `TradingExecutor.initialize()`

```python
await executor.initialize() -> None

# Raises:
#   PermissionError: Sem credenciais
#   KuCoinAPIError: Falha ao conectar
```

### `TradingExecutor.execute_market_order()`

```python
await executor.execute_market_order(
    symbol: str,                          # "BTC-USDT"
    side: str,                            # "buy" | "sell"
    quantity: Decimal,                    # 0.1
    take_profit: Optional[Decimal] = None,
    stop_loss: Optional[Decimal] = None
) -> Dict[str, Any]

# Returns:
#   {
#     "_id": ObjectId,
#     "status": "filled",
#     "filled_price": Decimal,
#     "filled_quantity": Decimal,
#     ...
#   }

# Raises:
#   ValidationFailedError
#   InsufficientBalanceError
#   ExchangeTimeoutError
#   OrderExecutionError
```

### `TradingExecutor.get_account_balance()`

```python
balances = await executor.get_account_balance() -> Dict[str, Decimal]

# Returns:
#   {
#     "BTC": Decimal("0.5"),
#     "USDT": Decimal("1000"),
#     "ETH": Decimal("2.5")
#   }
```

---

## 8. TROUBLESHOOTING

### ❌ "Sem credenciais KuCoin configuradas"

**Causa:** Usuário não conectou a KuCoin  
**Solução:**

```bash
curl -X POST http://localhost:8000/api/trading/kucoin/connect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "...",
    "api_secret": "...",
    "api_passphrase": "..."
  }'
```

### ❌ "Saldo insuficiente"

**Causa:** Usuário não tem saldo  
**Solução:**

```python
# Verificar saldo antes
balance = await executor.get_account_balance()
print(balance)

# Se testnet, usar KuCoin sandbox faucet:
# https://sandbox.kucoin.com/
```

### ❌ "Ordem não preencheu em 60s"

**Causa:** Mercado está vazio ou muito ilíquido  
**Solução:**

```python
# 1. Tentar com limite, não mercado
# (Implementar execute_limit_order em futuro)

# 2. Reduzir quantidade

# 3. Verificar manualmente na KuCoin
```

### ❌ "Kill-switch ativo"

**Causa:** Usuário perdeu muito hoje  
**Solução:**

```python
# Admin desativa kill-switch
await RiskManager.deactivate_kill_switch("user_123")
```

---

## TODO (Futuro)

- [ ] Implementar `execute_limit_order()`
- [ ] WebSocket real-time monitoring (ao invés de polling)
- [ ] Take-profit/Stop-loss automáticos
- [ ] Ordens condicionais
- [ ] Suporte a Binance
- [ ] Histórico de preços para análise
- [ ] Alerts em email/SMS

---

**Questionário?** Verifique a seção "Troubleshooting" ou abra uma issue.
