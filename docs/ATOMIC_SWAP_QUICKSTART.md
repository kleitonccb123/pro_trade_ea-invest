# 🚀 ATOMIC SWAP - Quick Start Guide

**TL;DR:** Sistema automático que garante apenas 1 bot opera por vez, cancelando ordens órfãs antes de iniciar novo bot. Usa Redis locking + polling da exchange.

---

## 🎯 No Dia a Dia (Como Desenvolvedor)

### Iniciar um Bot (Usuário clica "Start")
```python
# Automático via endpoint!
POST /api/bots/{bot_id}/start

# Response:
{
    "success": true,
    "bot_id": "bot_123",
    "atomic_swap": {
        "previous_bot_id": "old_bot_456",
        "cancelled_orders": 3
    }
}
```

Tudo é feito automaticamente. Nada especial para fazer.

---

### Verificar se Sistema Está Preso (DEBUG)
```python
from app.services.redis_manager import redis_manager

# Está alguém dentro do lock?
is_locked = await redis_manager.is_locked(f"lock:bot:start:{user_id}")

if is_locked:
    print("⏳ Outro processo está iniciando um bot")
else:
    print("✅ Prontinho para iniciar novo bot")
```

---

### Logs para Auditoria
```bash
# Procure no backend log:
tail -f backend.log | grep "atomic_swap\|prepare_for_new_strategy\|cancel_all_orders"

# Você verá:
# [10:15:23] 🔄 Preparando troca de estratégia...
# [10:15:23] 🤖 Robô ativo encontrado: bot_456
# [10:15:24] ✅ Canceladas 5 ordens
# [10:15:24] ✅ Swap atômico completo!
```

---

## 🔧 Componentes Principais

### 1. Redis Locking (Mutex Distribuído)
```python
# Dentro de redis_manager.py
await redis_manager.acquire_lock("lock:bot:start:user123")  # Bloqueia
# ... fazer coisa crítica ...
await redis_manager.release_lock("lock:bot:start:user123")  # Desbloqueia
```

**Quando usar:**
- Qualquer operação que não pode ser executada 2x simultaneamente
- Exemplo: inicializar conexão com exchange, escrever em arquivo crítico

**Não é preciso usar manualmente** - endpoint já cuida disso!

---

### 2. Cancelamento de Ordens (Exchange Service)
```python
# Dentro de exchange_service.py
cancel_result = await exchange_service.cancel_all_orders(
    symbol="BTC/USDT",
    max_retries=3
)

if cancel_result["success"]:
    print(f"✅ {cancel_result['cancelled_count']} ordens canceladas")
else:
    print(f"❌ {cancel_result['error']}")
```

**Retorna:**
```python
{
    "success": bool,
    "cancelled_count": int,
    "remaining_orders": int,
    "message": str,
    "error": str | None
}
```

---

### 3. Preparação de Estratégia (Service)
```python
# Dentro de bots/service.py
result = await bot_service.prepare_for_new_strategy(user_id)

if result["success"]:
    print(f"✅ Pronto! {result['cancelled_orders']} ordens limpas")
else:
    print(f"❌ Erro: {result['error']}")
```

**O que faz:**
1. Busca bot ativo
2. Muda para "switching"
3. Cancela TODAS ordens
4. Muda para "idle"

---

## 📋 Checklist: Adicionar Nova Exchange

Se adicionar Kraken/Binance no futuro:

```python
# 1. Em exchange_service.py, adicione novo exchange:
if exchange_name == "kraken":
    self.exchange = ccxt.kraken({...})

# 2. Adicione método cancel_all_orders (faz automaticamente!)
# CCXT já oferece fetch_open_orders() para todas exchanges

# 3. Teste manualmente:
import asyncio
from app.services.exchange_service import exchange_service

async def test():
    result = await exchange_service.cancel_all_orders("BTC/USD")
    print(result)

asyncio.run(test())

# 4. Pronto! Novo exchange funciona com swap atômico
```

---

## 🆘 Troubleshooting

### "429 Too Many Requests"
```
Significado: Outro processo está iniciando bot
Solução: Aguarde 5 segundos e tente novamente
Código: HTTPException status_code=429
```

### "Falha ao desativar robô anterior"
```
Significado: Não conseguiu cancelar todas as ordens
Solução: Cancele manualmente na exchange e tente novamente
Logs: Procure por "cancel_all_orders" no backend log
```

### "Order not found" durante cancelamento
```
Significado: Ordem já foi cancelada/executada (normal!)
Solução: Sistema retorna True (objetivo alcançado)
Logs: Você verá "⚠️ Ordem não encontrada (possivelmente já executada)"
```

### Redis não conecta
```
Erro: "Failed to initialize Redis"
Solução:
1. Verifique se Redis está rodando: redis-cli PING
2. Verifique URL em REDIS_URL env var
3. Verifique firewall/acesso
```

---

## 🧪 Teste de Carga (Simular 100 Cliques)

```python
import asyncio
import httpx

async def test_100_starts():
    async with httpx.AsyncClient() as client:
        tasks = []
        
        for i in range(100):
            task = client.post(
                "http://localhost:8000/api/bots/bot_123/start",
                headers={"Authorization": f"Bearer {token}"}
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r.status_code == 200)
        too_many = sum(1 for r in results if r.status_code == 429)
        errors = sum(1 for r in results if r.status_code >= 500)
        
        print(f"✅ Sucesso: {success_count}")
        print(f"⏳ Too Many (lock): {too_many}")
        print(f"❌ Erros: {errors}")
        
        # Esperado: ~1 sucesso, ~99 Too Many

asyncio.run(test_100_starts())
```

---

## 🔍 Monitorar em Tempo Real

```bash
# Terminal 1: Veja logs do backend em tempo real
tail -f backend.log | grep -i "atomic\|lock"

# Terminal 2: Faça múltiplas requisições
for i in {1..10}; do
  curl -X POST \
    http://localhost:8000/api/bots/bot_123/start \
    -H "Authorization: Bearer $TOKEN" &
done

# Resultado esperado em Terminal 1:
# [10:15:23] 🔓 Lock adquirido: lock:bot:start:user_123
# [10:15:23] 🔄 Preparando troca...
# [10:15:24] ✅ Canceladas 5 ordens
# [10:15:24] 🔐 Lock liberado: lock:bot:start:user_123
```

---

## 📚 Arquivo de Referência Completa

Para entender **TODO** sobre o sistema:

👉 **ATOMIC_SWAP_IMPLEMENTATION.md** (documento técnico 100% cobertura)

---

## 🚨 Nunca Fazer

❌ **Não cancele a lock manualmente**
```python
# NÃO FAÇA ISSO:
await redis_client.delete("lock:bot:start:user123")  # Breaks everything!

# DEIXE EXPIRAR AUTOMATICAMENTE (5s) ou use:
await redis_manager.release_lock("lock:bot:start:user123")  # ✅ Certo
```

❌ **Não inicie 2 bots do mesmo usuário simultaneamente**
```python
# Endpoint já prevent isso! Sistema vai rejeitar com 429
```

❌ **Não ignore erros de cancelamento**
```python
# Quando cancel_all_orders retorna success=false,
# NUNCA inicie novo bot!
# Isso é exatamente o que endpoint faz (fail-fast)
```

---

## 💡 Pro Tips

1. **Consulte logs primeiro** - 90% dos problemas você vê no log
2. **Use `is_locked()` para debug** - diz se sistema está travado
3. **Aumenpause pequeno antes de retry** - exchange precisa processar
4. **Estude o fluxo visual** - ATOMIC_SWAP_CHANGES.md tem ASCII art

---

## 📞 Quick Links

| Recurso | Local |
|---------|-------|
| **Documentação Completa** | `ATOMIC_SWAP_IMPLEMENTATION.md` |
| **Lista de Mudanças** | `ATOMIC_SWAP_CHANGES.md` |
| **Endpoint Código** | `backend/app/bots/execution_router.py` (linhas ~71-200) |
| **Service Função** | `backend/app/bots/service.py` (linhas ~310-470) |
| **Redis Locking** | `backend/app/services/redis_manager.py` (linhas ~150-270) |
| **Exchange Cancel** | `backend/app/services/exchange_service.py` (linhas ~92-200) |

---

**Status:** ✅ Pronto para Produção
**Última Atualização:** 11 Fevereiro 2026

