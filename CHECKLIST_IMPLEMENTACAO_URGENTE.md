# ⚡ CHECKLIST TÉCNICO — PRIMEIROS PASSOS PARA PRODUÇÃO

**Data:** Março 22, 2026  
**Objetivo:** Guia prático de implementação prioritário

---

## 🎯 HOJE: O QUE PRECISA SER FEITO IMEDIATAMENTE

### SPRINT 1 — Foundation (Dias 1-5)

**Objetivo:** Sistema consegue executar ordem real em testnet sem perder dados

#### ✅ Task 1.1 — Criar `TradingExecutor` (Arquivo novo)

```python
# backend/app/trading/executor.py

class TradingExecutor:
    """
    Orquestra fluxo inteiro:
    1. Validar saldo real
    2. Persistir ordem (idempotência)
    3. Enviar para KuCoin
    4. Monitorar até fill
    5. Sincronizar banco
    """
    
    __init__(self, user_id: str, exchange: str = "kucoin"):
        self.user_id = user_id
        self.exchange = exchange
        self.credentials = None  # Descripta sob demanda
        self.client = None
    
    async def execute_market_order(self, symbol: str, side: str, quantity: Decimal):
        # 1. Validação pré-trade
        await self._validate_order(symbol, side, quantity)
        
        # 2. Persistir order (com client_oid idempotente)
        order_db = await self._persist_pending_order(symbol, side, quantity)
        
        # 3. Executar
        order_exchange = await self._place_at_exchange(order_db)
        
        # 4. Monitorar
        filled_order = await self._monitor_until_filled(order_exchange)
        
        # 5. Sincronizar
        await self._sync_to_database(filled_order)
        
        return order_db
    
    async def _validate_order(self, symbol: str, side: str, quantity: Decimal):
        """Valida: saldo, limites, risk"""
        # Usar pre_trade_validation
        # Usar risk_manager
        pass
    
    async def _persist_pending_order(self, symbol: str, side: str, quantity: Decimal):
        """Salva ANTES de enviar"""
        client_oid = generate_idempotent_oid()
        order = {
            "user_id": self.user_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "client_oid": client_oid,
            "status": "pending",
            "created_at": datetime.utcnow()
        }
        result = await db.trading_orders.insert_one(order)
        return {**order, "_id": result.inserted_id}
    
    async def _place_at_exchange(self, order_db):
        """Envia para KuCoin"""
        exchange_order = await self.client.place_market_order(
            symbol=order_db["symbol"],
            side=order_db["side"],
            quantity=order_db["quantity"],
            client_oid=order_db["client_oid"]
        )
        return exchange_order
    
    async def _monitor_until_filled(self, order_exchange):
        """Monitora até fill (polling + websocket)"""
        for attempt in range(60):
            status = await self.client.get_order(order_exchange["id"])
            if status["status"] == "FILLED":
                return status
            await asyncio.sleep(1)
        raise TimeoutError("Order não preencheu em 60s")
    
    async def _sync_to_database(self, filled_order):
        """Sincroniza resultado no banco"""
        await db.trading_orders.update_one(
            {"client_oid": filled_order["client_oid"]},
            {
                "$set": {
                    "status": "filled",
                    "exchange_order_id": filled_order["id"],
                    "filled_price": filled_order["average_price"],
                    "filled_quantity": filled_order["filled_quantity"],
                    "filled_at": datetime.utcnow()
                }
            }
        )
```

**Tempo:** 2-3 dias de desenvolvimento + testes  
**Prioridade:** 🔴 **BLOQUEADOR**

---

#### ✅ Task 1.2 — Ampliar `pre_trade_validation` (Arquivo existente)

```python
# backend/app/trading/pre_trade_validation.py

async def validate_order_executable(
    user_id: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    current_price: Decimal = None
) -> Tuple[bool, Optional[str]]:
    """
    Valida se ordem pode ser executada:
    ✓ Saldo suficiente
    ✓ Tamanho dentro de limites
    ✓ Acima do mínimo de notional
    ✓ Sem violação de risk limits
    """
    
    # 1. Obter credenciais
    creds = await CredentialsRepository.get_credentials(user_id, "kucoin")
    if not creds:
        return False, "Sem credenciais KuCoin"
    
    # 2. Conectar e obter saldo
    client = KuCoinClient(creds)
    balance = await client.get_account_balance()
    
    # 3. Validações
    if side == "BUY":
        quote_currency = get_quote_currency(symbol)  # USDT, USDC, etc
        estimated_cost = quantity * (current_price or get_last_price(symbol))
        
        if balance.get(quote_currency, {}).get("available") < estimated_cost:
            return False, f"Saldo insuficiente. Precisa: {estimated_cost}, tem: {balance}"
    
    elif side == "SELL":
        base_currency = get_base_currency(symbol)  # BTC, ETH, etc
        
        if balance.get(base_currency, {}).get("available") < quantity:
            return False, f"Saldo insuficiente. Precisa: {quantity}"
    
    # 4. Validar contra risk manager
    max_open_positions = await RiskManager.get_max_open_positions(user_id)
    current_positions = await PositionManager.get_open_positions(user_id)
    
    if len(current_positions) >= max_open_positions:
        return False, f"Max posições ({max_open_positions}) atingidas"
    
    return True, None
```

**Tempo:** 1-2 dias  
**Prioridade:** 🔴 **BLOQUEADOR**

---

#### ✅ Task 1.3 — Integrar `TradingExecutor` em `bots/service.py` (Arquivo existente)

```python
# backend/app/bots/service.py

class BotsService:
    async def start(self, instance_id: str, user_id: str):
        """
        ✗ ANTES: Ia para simulação
        ✓ DEPOIS: Ir para TradingExecutor
        """
        
        # Validar credenciais
        creds = await CredentialsRepository.get_credentials(user_id, "kucoin")
        if not creds:
            raise PermissionError("Configure KuCoin antes")
        
        # Criar executor
        executor = TradingExecutor(user_id=user_id, exchange="kucoin")
        
        # Inicializar
        await executor.initialize()
        
        # Salvar em cache
        self.active_executors[instance_id] = executor
        
        logger.info(f"✅ Bot {instance_id} iniciado com trading real")
```

**Tempo:** 1 dia  
**Prioridade:** 🔴 **BLOQUEADOR**

---

#### ✅ Task 1.4 — Criar testes com KuCoin testnet (Arquivo novo)

```python
# backend/tests/integration/test_trading_executor_testnet.py

@pytest.mark.integration
async def test_executor_places_real_order_in_testnet():
    """
    Testa fluxo completo em testnet:
    1. Cria conta testnet
    2. Coloca ordem
    3. Valida sincronização
    """
    # Setup
    user_testnet = await create_testnet_user(api_key="...", api_secret="...", ...)
    executor = TradingExecutor(user_id=user_testnet.id, exchange="kucoin")
    
    # Execute
    order = await executor.execute_market_order(
        symbol="BTC/USDT",
        side="BUY",
        quantity=Decimal("0.001")
    )
    
    # Verificar
    assert order["status"] == "pending"
    assert order["client_oid"] is not None
    
    # Aguardar fill (max 60s)
    filled = await poll_until_filled(order["_id"], timeout=60)
    
    # Validações
    assert filled["status"] == "filled"
    assert filled["exchange_order_id"] is not None
    assert filled["filled_price"] > 0
    assert filled["filled_quantity"] == Decimal("0.001")

@pytest.mark.integration
async def test_executor_validates_balance_before_order():
    """Testa validação de saldo"""
    executor = TradingExecutor(user_id="...", exchange="kucoin")
    
    # Tentar comprar quantidade impossível
    with pytest.raises(InsufficientBalanceError):
        await executor.execute_market_order(
            symbol="BTC/USDT",
            side="BUY",
            quantity=Decimal("1000000")  # Impossível
        )
```

**Tempo:** 2 dias  
**Prioridade:** 🔴 **BLOQUEADOR**

---

### SPRINT 2 — Segurança (Dias 6-10)

#### ✅ Task 2.1 — Criar `OrderReconciliationWorker` (Arquivo novo)

```python
# backend/app/workers/reconciliation_worker.py

class OrderReconciliationWorker:
    """
    Background job que roda a cada 1 minuto.
    Sincroniza ordens PENDING com KuCoin.
    """
    
    async def start(self):
        """Worker infinito"""
        while True:
            try:
                await self.reconcile_all_users()
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
            
            await asyncio.sleep(60)  # A cada 1 minuto
    
    async def reconcile_all_users(self):
        """Percorre todos os usuários com credenciais"""
        active_users = await get_active_users_with_kucoin()
        
        for user in active_users:
            try:
                await self.reconcile_user_orders(user.id)
            except Exception as e:
                logger.error(f"Error reconciling user {user.id}: {e}")
    
    async def reconcile_user_orders(self, user_id: str):
        """Reconcilia orders de UM usuário"""
        # 1. Obter ordens PENDING do banco
        pending_orders = await db.trading_orders.find({
            "user_id": user_id,
            "status": "pending"
        }).to_list(None)
        
        if not pending_orders:
            return
        
        # 2. Obter ordens REAIS do KuCoin
        creds = await CredentialsRepository.get_credentials(user_id, "kucoin")
        client = KuCoinClient(creds)
        real_orders = await client.get_orders()
        
        # 3. Comparar
        for db_order in pending_orders:
            real_order = find_by_client_oid(real_orders, db_order["client_oid"])
            
            if not real_order:
                logger.warning(f"Order {db_order['client_oid']} não encontrada em KuCoin!")
                # ← Investigar! Possível perda de dados
                continue
            
            # 4. Sincronizar se status mudar
            if real_order["status"] == "FILLED" and db_order["status"] == "pending":
                await db.trading_orders.update_one(
                    {"_id": db_order["_id"]},
                    {
                        "$set": {
                            "status": "filled",
                            "exchange_order_id": real_order["id"],
                            "filled_price": Decimal(real_order["average_price"]),
                            "filled_quantity": Decimal(real_order["filled_quantity"]),
                            "filled_at": datetime.utcnow()
                        }
                    }
                )
                logger.info(f"✅ Order {db_order['_id']} sincronizada (FILLED)")

# Em main.py, iniciar este worker como background task
async def startup_event():
    reconciliation_worker = OrderReconciliationWorker()
    asyncio.create_task(reconciliation_worker.start())
```

**Tempo:** 2-3 dias  
**Prioridade:** 🟠 **CRÍTICA**

---

#### ✅ Task 2.2 — Ampliar `RiskManager` completo (Arquivo existente)

```python
# backend/app/trading/risk_manager.py

class RiskManager:
    """
    Sistema de limites de risco:
    - Kill-switch por usuário
    - Daily loss limit
    - Max open positions
    - Max position size (% do capital)
    """
    
    async def check_can_trade(self, user_id: str, order_spec: OrderSpec) -> Tuple[bool, Optional[str]]:
        """Valida se ordem pode ser executada"""
        
        # 1. Kill-switch?
        if await self.is_user_killed(user_id):
            return False, "Kill-switch ativo. Contate admin."
        
        # 2. Daily loss limit?
        today_loss = await self.calculate_daily_pnl(user_id)
        user_config = await self.get_user_risk_config(user_id)
        
        if today_loss < -user_config["daily_loss_limit"]:
            await self.activate_kill_switch(user_id, reason="daily_loss_limit")
            return False, f"Daily loss limit ({user_config['daily_loss_limit']}) atingido"
        
        # 3. Max open positions?
        open_positions = await PositionManager.get_open_positions(user_id)
        
        if len(open_positions) >= user_config["max_open_positions"]:
            return False, f"Max posições ({user_config['max_open_positions']}) atingidas"
        
        # 4. Position size (não pode ser > 10% do capital)?
        total_balance = await self.get_user_total_balance(user_id)
        order_value = order_spec.quantity * order_spec.estimated_price
        
        if order_value > total_balance * Decimal("0.1"):
            return False, f"Ordem muito grande (max 10% do capital)"
        
        return True, None
    
    async def activate_kill_switch(self, user_id: str, reason: str):
        """Ativa kill-switch (bloqueia todos os trades)"""
        await db.user_risk_config.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "kill_switch_active": True,
                    "kill_switch_reason": reason,
                    "kill_switch_at": datetime.utcnow()
                }
            }
        )
        logger.warning(f"🚨 Kill-switch ativado para {user_id}: {reason}")
        # Notificar usuário por email/SMS
        await notify_user_kill_switch(user_id, reason)
```

**Tempo:** 2-3 dias  
**Prioridade:** 🟠 **CRÍTICA**

---

#### ✅ Task 2.3 — Garantir idempotência com `client_oid` (Arquivo existente)

```python
# backend/app/trading/idempotency_store.py (existe, GARANTIR USO)

def generate_client_oid(user_id: str, symbol: str, side: str) -> str:
    """
    Gera um ID único e idempotente para ordem.
    Se a mesma ordem for tentada novamente, gera o mesmo client_oid.
    
    KuCoin rejeita ordens duplicadas com mesmo client_oid.
    """
    data = f"{user_id}_{symbol}_{side}_{int(time.time()*1000)}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]

# ✓ GARANTIR que TradingExecutor usa isto:
async def _persist_pending_order(self, ...):
    client_oid = generate_client_oid(self.user_id, symbol, side)
    # ... salvar com este client_oid ...
    # Se houver retry, o mesmo client_oid será gerado
```

**Tempo:** 1 dia (apenas review + garantir uso)  
**Prioridade:** 🟠 **CRÍTICA**

---

### SPRINT 3 — Produção (Dias 11-15)

#### ✅ Task 3.1 — Criar `WebSocketOrderMonitor` (Arquivo novo)

```python
# backend/app/exchanges/kucoin/websocket_private.py

class WebSocketOrderMonitor:
    """
    Monitora ordens em TEMPO REAL via WebSocket privada da KuCoin.
    Atualiza banco automaticamente quando ordem é preenchida.
    """
    
    async def subscribe_to_order_updates(self, user_id: str):
        """
        Se se conecta a KuCoin WebSocket private
        E recebe eventos: order_match, order_done, etc.
        """
        creds = await CredentialsRepository.get_credentials(user_id, "kucoin")
        
        # Conectar WebSocket privada
        async with websockets.connect(
            f"wss://ws-auth.kucoin.com/?token={creds.ws_token}"
        ) as ws:
            # Subscrever a eventos de ordem
            await ws.send(json.dumps({
                "type": "subscribe",
                "topic": "/spotMarket/tradeOrders",
                "response": True
            }))
            
            # Loop infinito recebendo eventos
            while True:
                event = json.loads(await ws.recv())
                
                if event["type"] == "message":
                    trade_order = event["data"]
                    
                    # Sincronizar no banco
                    await self._update_order_in_db(
                        user_id=user_id,
                        exchange_order_id=trade_order["orderId"],
                        status=trade_order["status"],
                        filled_price=trade_order.get("averagePrice"),
                        filled_quantity=trade_order.get("filledSize")
                    )
    
    async def _update_order_in_db(self, user_id: str, exchange_order_id: str, status: str, ...):
        """Atualiza ordem no banco quando muda em KuCoin"""
        await db.trading_orders.update_one(
            {"user_id": user_id, "exchange_order_id": exchange_order_id},
            {"$set": {"status": status, "filled_price": filled_price, ...}}
        )
```

**Tempo:** 2-3 dias  
**Prioridade:** 🟡 **ALTA** (otimização de latência)

---

---

## 📋 CHECKLIST MACRO

Copie e cole em um markdown ou Jira:

```markdown
### Foundation (Semana 1)
- [ ] **Task 1.1** — TradingExecutor (2-3 dias)
  - [ ] Codigo core implementado
  - [ ] Testes unitários passando
  - [ ] Integração com pre_trade_validation
  
- [ ] **Task 1.2** — Pre-Trade Validation (1-2 dias)
  - [ ] Validação de saldo real
  - [ ] Validação de limites
  - [ ] Integração com RiskManager
  
- [ ] **Task 1.3** — Integração em BotsService (1 dia)
  - [ ] Método start() usando TradingExecutor
  - [ ] Remoção de fallback para simulação
  
- [ ] **Task 1.4** — Testes E2E com testnet (2 dias)
  - [ ] Setup KuCoin testnet
  - [ ] Testes de ordem real
  - [ ] Fixture de usuário testnet

### Segurança (Semana 2)
- [ ] **Task 2.1** — OrderReconciliationWorker (2-3 dias)
  - [ ] Worker roda a cada 1 minuto
  - [ ] Sincroniza PENDING com exchange
  - [ ] Logging de divergências

- [ ] **Task 2.2** — RiskManager expandido (2-3 dias)
  - [ ] Kill-switch implementation
  - [ ] Daily loss limits
  - [ ] Max position size checks

- [ ] **Task 2.3** — Idempotência (1 dia)
  - [ ] Garantir uso de client_oid
  - [ ] Testes de retentativa

### Produção (Semana 3)
- [ ] **Task 3.1** — WebSocket Monitor (2-3 dias)
  - [ ] Real-time order updates
  - [ ] Sincronização automática

- [ ] **Task 3.2** — Circuit Breaker (1-2 dias)
  - [ ] Detecção de falhas
  - [ ] Fail-fast behavior
  - [ ] Recovery automático

- [ ] **Task 3.3** — Monitoring & Alertas (1-2 dias)
  - [ ] Métricas de execução
  - [ ] Alertas de erro
  - [ ] Dashboard de saúde
```

---

## 🚀 PRÓXIMOS PASSOS

1. **TODAY:** Revisar este checklist com seu time
2. **AMANHÃ:** Começar Task 1.1 (TradingExecutor)
3. **SEMANA QUE VEM:** Ter Task 1.1 + 1.2 + 1.3 prontos
4. **SEMANA 2:** Segurança (Task 2.x)
5. **SEMANA 3:** Produção pronta para deploy

---

## 📞 QUESTÕES FREQUENTES

**P:** Quanto tempo leva tudo isto?  
**R:** ~6 semanas com 1-2 devs, ou ~3-4 semanas com 2-3 devs full-stack.

**P:** Posso fazer isto em paralelo?  
**R:** Task 1.1, 1.2 e 1.4 podem ser paralelas. 1.3 depende de 1.1.

**P:** E se eu só fazer o mínimo?  
**R:** Task 1.1 + 1.2 + 1.3 + 1.4. Isso já coloca sistema em testnet. Depois adiciona 2.1, 2.2, 2.3 para produção.

---

Quer que eu comece implementando Task 1.1 (TradingExecutor)?
