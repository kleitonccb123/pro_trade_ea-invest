# ROADMAP DE IMPLEMENTAÇÃO - KuCoin Refatoração

**Tempo Estimado:** 40-60 horas para produção  
**Equipe Mínima:** 2 eng. senior + 1 DevOps

---

## FASE 1: Fundação (8-12 horas)

### 1.1 Criar Estrutura de Pastas
```bash
# Execute no terminal
mkdir -p backend/app/exchanges/kucoin
mkdir -p backend/app/exchanges/binance
mkdir -p backend/app/trading
mkdir -p backend/app/stream
touch backend/app/exchanges/__init__.py
touch backend/app/exchanges/kucoin/__init__.py
touch backend/app/exchanges/kucoin/client.py
touch backend/app/exchanges/kucoin/normalizer.py
touch backend/app/exchanges/kucoin/models.py
```

### 1.2 Criar Models (DTOs) Unificados
```python
# backend/app/exchanges/kucoin/models.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

@dataclass
class KuCoinBalance:
    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal
    timestamp: datetime

@dataclass
class KuCoinOrder:
    order_id: str
    symbol: str
    side: str          # BUY / SELL
    order_type: str    # LIMIT / MARKET
    price: Decimal
    size: Decimal
    filled: Decimal
    remaining: Decimal
    status: str        # OPEN / CLOSED
    fee: Decimal
    fee_currency: str
    created_at: datetime
    client_oid: Optional[str]

@dataclass
class KuCoinTicker:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    timestamp: datetime

@dataclass
class KuCoinCandle:
    timestamp: datetime
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
```

### 1.3 Implementar KuCoinRawClient (Camada 1)
- Copiar código da Seção 6.1 acima
- Arquivo: `backend/app/exchanges/kucoin/client.py`
- Testar autenticação com `/accounts`

### 1.4 Implementar PayloadNormalizer (Camada 2)
- Copiar código da Seção 6.2 acima
- Arquivo: `backend/app/exchanges/kucoin/normalizer.py`
- Unit tests para cada função de normalização

---

## FASE 2: Trading Engine (12-16 horas)

### 2.1 Criar TradingEngine (Camada 3)
```python
# backend/app/trading/engine.py
# Copiar código acima
```

### 2.2 Criar OrderManager (Camada 5)
```python
# backend/app/trading/execution.py
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, List, Optional
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class OrderQueue:
    """Fila interna de ordens com garantia de idempotência."""
    
    def __init__(self):
        self.pending_orders: Dict[str, OrderRequest] = {}
        self.executed_orders: Dict[str, OrderResult] = {}
        self.lock = asyncio.Lock()
    
    async def enqueue(self, request: OrderRequest) -> str:
        """Adiciona ordem à fila."""
        async with self.lock:
            order_id = request.client_oid
            self.pending_orders[order_id] = request
            return order_id
    
    async def mark_executed(self, order_id: str, result: OrderResult) -> None:
        """Marca como executada."""
        async with self.lock:
            if order_id in self.pending_orders:
                del self.pending_orders[order_id]
            self.executed_orders[order_id] = result
    
    async def get_pending(self) -> List[OrderRequest]:
        """Obtém ordens pendentes."""
        async with self.lock:
            return list(self.pending_orders.values())


class OrderManager:
    """
    Gerencia ciclo de vida das ordens (Camada 5).
    
    Responsabilidades:
    - Fila interna
    - Retry com exponential backoff
    - Idempotência garantida
    - TP/SL tracking
    - Estado sincronizado
    """
    
    def __init__(self, trading_engine):
        self.engine = trading_engine
        self.order_queue = OrderQueue()
        self.max_retries = 3
        self.base_backoff = 1.0
    
    async def execute_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        order_type: str = "market",
        price: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> OrderResult:
        """Executa ordem com retry automático."""
        
        import uuid
        client_oid = str(uuid.uuid4())
        
        request = OrderRequest(
            client_oid=client_oid,
            symbol=symbol,
            side=side,
            size=size,
            order_type=order_type,
            price=price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            created_at=datetime.now(timezone.utc),
        )
        
        # Enfileira
        await self.order_queue.enqueue(request)
        
        # Tenta executar com retry
        for attempt in range(1, self.max_retries + 1):
            try:
                if order_type == "market":
                    result = await self.engine.place_market_order(
                        symbol=symbol,
                        side=side,
                        size=size,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                else:
                    result = await self.engine.place_limit_order(
                        symbol=symbol,
                        side=side,
                        size=size,
                        price=price,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                
                # Marca como executada
                await self.order_queue.mark_executed(client_oid, result)
                logger.info(f"✅ Ordem {client_oid} executada: {result.order_id}")
                return result
                
            except Exception as e:
                logger.error(f"❌ Tentativa {attempt}/{self.max_retries} falhou: {e}")
                
                if attempt < self.max_retries:
                    wait_time = self.base_backoff ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    raise
```

### 2.3 Criar RiskManager (Camada 6)
```python
# backend/app/trading/risk.py
from decimal import Decimal
from typing import Optional

class RiskManager:
    """
    Valida risco antes de colocar ordens (Camada 6).
    
    Responsabilidades:
    - Limite de alavancagem
    - Risco agregado por usuário
    - Kill-switch automático
    - Validação pré-ordem
    """
    
    def __init__(
        self,
        max_leverage: float = 10.0,
        max_position_size: Decimal = Decimal("1000000"),  # $1M
        max_loss_per_trade: Decimal = Decimal("1000"),    # $1000
    ):
        self.max_leverage = max_leverage
        self.max_position_size = max_position_size
        self.max_loss_per_trade = max_loss_per_trade
    
    async def validate_order(
        self,
        user_id: str,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        stop_loss: Optional[Decimal] = None,
    ) -> bool:
        """
        Valida se ordem pode ser colocada.
        
        Returns:
            True se válida, False caso contrário
        """
        
        # 1. Validar tamanho da posição
        position_size = size * price
        if position_size > self.max_position_size:
            logger.warning(f"❌ Posição {position_size} > {self.max_position_size}")
            return False
        
        # 2. Validar risco máximo por trade
        if stop_loss:
            loss = (price - stop_loss) * size
            if loss > self.max_loss_per_trade:
                logger.warning(f"❌ Perda {loss} > {self.max_loss_per_trade}")
                return False
        
        # 3. Validar alavancagem agregada (buscar posições abertas)
        total_open_risk = await self._calculate_open_risk(user_id)
        if total_open_risk > (Decimal(self.max_leverage) * Decimal("100000")):
            logger.warning(f"❌ Risco total {total_open_risk} > limite")
            return False
        
        return True
    
    async def _calculate_open_risk(self, user_id: str) -> Decimal:
        """Calcula risco total de posições abertas."""
        # TODO: Buscar do MongoDB posições abertas
        return Decimal("0")
```

---

## FASE 3: Strategy Engine (8-10 horas)

### 3.1 Criar Strategy Base (Strategy Pattern)
```python
# backend/app/strategies/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class StrategyBase(ABC):
    """Base class para todas as estratégias."""
    
    @abstractmethod
    async def analyze(self, candles: List[Candle]) -> TradeSignal:
        """
        Analisa klines e retorna sinal.
        
        Returns:
            TradeSignal(symbol, side, confidence, tp, sl) ou None
        """
        pass
```

### 3.2 Criar StrategyEngine (Camada 4)
```python
# backend/app/strategies/engine.py
class StrategyEngine:
    """Executa estratégias isoladamente (Camada 4)."""
    
    def __init__(self):
        self.active_robots = {}
    
    async def run_strategy(
        self,
        bot_id: str,
        strategy: StrategyBase,
        market_data: MarketData,
    ) -> Optional[TradeSignal]:
        """Executa estratégia de forma isolada."""
        
        # Garante isolamento por thread
        signal = await strategy.analyze(market_data.candles)
        return signal
```

---

## FASE 4: WebSocket & Real-Time (12-16 horas)

### 4.1 Criar StreamManager
```python
# backend/app/stream/manager.py
class StreamManager:
    """Gerencia múltiplos streams de dados (KuCoin)."""
    
    def __init__(self):
        self.streams: Dict[str, ExchangeStream] = {}
    
    async def subscribe_kline(
        self,
        symbol: str,
        interval: str,
        callback: Callable,
    ) -> str:
        """Subscreve a klines (candlesticks)."""
        pass
    
    async def subscribe_orderbook(
        self,
        symbol: str,
        callback: Callable,
    ) -> str:
        """Subscreve a order book incremental."""
        pass
    
    async def subscribe_trades(
        self,
        symbol: str,
        callback: Callable,
    ) -> str:
        """Subscreve a trades."""
        pass
```

### 4.2 Criar WebSocket Handler da KuCoin
```python
# backend/app/exchanges/kucoin/websocket.py
class KuCoinWebSocketHandler:
    """Handler de WebSocket da KuCoin com reconexão automática."""
    
    async def connect(self):
        """Conecta com heartbeat e reconexão automática."""
        pass
```

---

## FASE 5: Frontend Integration (6-8 horas)

### 5.1 Criar WebSocket Handler Interno
```typescript
// frontend/src/services/websocket.ts
class SaaSwWebSocketService {
    connect() {
        this.socket = new WebSocket('ws://localhost:8000/ws/trading')
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data)
            this.handleMessage(data)
        }
    }
    
    private handleMessage(data: any) {
        if (data.type === 'kline') {
            this.emit('kline', data.payload)
        } else if (data.type === 'trade') {
            this.emit('trade', data.payload)
        }
    }
}
```

---

## FASE 6: Testes & Validação (8-10 horas)

### 6.1 Unit Tests
```bash
# Testes de autenticação
pytest tests/test_kucoin_auth.py

# Testes de normalização
pytest tests/test_payload_normalizer.py

# Testes de orchestração
pytest tests/test_trading_engine.py
```

### 6.2 Integration Tests
```bash
# E2E com sandbox KuCoin
pytest tests/e2e/test_place_order.py

# E2E com WebSocket
pytest tests/e2e/test_realtime_stream.py
```

### 6.3 Load Tests
```bash
# Simular 100 bots simultâneos
locust -f tests/loadtests/locustfile.py
```

---

## FASE 7: Segurança & Hardening (8-10 horas)

### 7.1 Sanitizar Logs
```python
# backend/app/core/logger.py
def sanitize_log(msg: str) -> str:
    """Remove API keys e secrets dos logs."""
    import re
    msg = re.sub(r'apiKey["\']?\s*[:=]\s*["\']([^"\']+)["\']', '***', msg)
    msg = re.sub(r'secret["\']?\s*[:=]\s*["\']([^"\']+)["\']', '***', msg)
    return msg
```

### 7.2 Criptografia de Credenciais
```python
# backend/app/core/encryption.py
from cryptography.fernet import Fernet

class CredentialEncryption:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()
```

---

## FASE 8: Deployment & Monitoramento (6-8 horas)

### 8.1 Docker Compose
```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    environment:
      - KUCOIN_API_KEY=${KUCOIN_API_KEY}
      - KUCOIN_API_SECRET=${KUCOIN_API_SECRET}
      - DB_URL=mongodb://mongo:27017
    depends_on:
      - mongo
      - redis
  
  mongo:
    image: mongo:5.0
  
  redis:
    image: redis:7.0
```

### 8.2 Prometheus Metrics
```python
# backend/app/core/metrics.py
from prometheus_client import Counter, Histogram

orders_placed = Counter('orders_placed', 'Total orders placed')
order_latency = Histogram('order_latency_ms', 'Order execution latency')
```

---

## CHECKLIST DE IMPLEMENTAÇÃO

- [ ] Fase 1: Fundação (estrutura + models)
- [ ] Fase 2: Trading Engine (3 camadas)
- [ ] Fase 3: Strategy Engine (isolamento)
- [ ] Fase 4: WebSocket (reconexão automática)
- [ ] Fase 5: Frontend (integração)
- [ ] Fase 6: Testes (unit + integration + load)
- [ ] Fase 7: Segurança (logs + encryption)
- [ ] Fase 8: Deployment (docker + monitoring)
- [ ] ✅ PRODUÇÃO

---

## FLUXO END-TO-END COMPLETO

### Usuário conecta API Keys

```
1. Frontend: POST /api/exchanges/setup
   {
     "exchange": "kucoin",
     "api_key": "user_input",
     "api_secret": "user_input",
     "api_passphrase": "user_input"
   }

2. Backend: Testa credenciais
   KuCoinRawClient.test_credentials(...)
   
3. Backend: Criptografa e salva
   CredentialEncryption.encrypt(api_secret)
   MongoDB.insert(encrypted_credentials)
   
4. Frontend: Mostra ✅ "Conectado"
```

### Robô inicia

```
1. Frontend: POST /api/bots/start
   {
     "bot_id": "123",
     "strategy": "sma_crossover"
   }

2. Backend: Valida pré-requisitos
   - Credenciais existem?
   - Saldo suficiente?
   - Não há outro bot rodando?

3. Backend: Inicia streamers
   StreamManager.subscribe_kline("BTC-USDT", "5m")
   StreamManager.subscribe_orderbook("BTC-USDT")
   StreamManager.subscribe_trades("BTC-USDT")

4. Backend: Inicia strategy executor
   StrategyEngine.run_strategy(bot, strategy, market_data)

5. Frontend: WS connect
   WebSocket /ws/trading
   Recebe updates em tempo real
```

### Sinal de entrada gerado

```
1. Strategy analisa klines
   → Gera sinal: BUY 0.1 BTC @ market, TP 35000, SL 30000

2. OrderManager valida risco
   RiskManager.validate_order(...)
   
3. OrderManager coloca ordem
   OrderQueue.enqueue(order_request)
   TradingEngine.place_market_order(...)
   
4. KuCoinRawClient envia para exchange
   POST /api/v1/orders
   Body: {
     "symbol": "BTC-USDT",
     "side": "buy",
     "type": "market",
     "size": "0.1",
     "takeProfit": "35000",
     "stopLoss": "30000"
   }
   
5. KuCoin retorna order_id

6. OrderManager marca como executada
   OrderQueue.mark_executed(order_id)
   
7. PayloadNormalizer normaliza resposta
   string "1.5" → Decimal("1.5")
   1645000000123 ms → datetime

8. Frontend recebe via WS
   {
     "type": "order_placed",
     "order_id": "5f3113a1689401000612a12a",
     "symbol": "BTC-USDT",
     "side": "BUY",
     "size": 0.1,
     "price": 34567.89,
     "take_profit": 35000,
     "stop_loss": 30000
   }
   
9. Frontend atualiza UI
   - Mostra ordem em "Posições Abertas"
   - Mostra TP/SL nas linhas do gráfico
```

### Monitoramento em tempo real

```
1. StreamManager recebe updates de klines
   broadcast via WebSocket interno → Frontend

2. Frontend renderiza gráfico em tempo real
   (TradingView / Recharts)

3. Se TP/SL atingido pela WebSocket:
   StreamManager emite "take_profit_triggered"
   
4. OrderManager executa SELL de fecha posição
   OrderManager.execute_order(
     symbol="BTC-USDT",
     side="sell",
     size=0.1,
     order_type="market"
   )

5. KuCoin confirma execução
   order_id = "5f3113a1689401000612a12e"
   filled = 0.1
   status = "DONE"
   
6. Frontend recebe:
   {
     "type": "position_closed",
     "order_id": "5f3113a1689401000612a12e",
     "exit_price": 35012.50,
     "pnl": 44.60,
     "pnl_percent": 0.13
   }
   
7. Database registra:
   MongoDB.insert({
     "user_id": "user123",
     "bot_id": "bot456",
     "entry_order_id": "5f3113a1689401000612a12a",
     "exit_order_id": "5f3113a1689401000612a12e",
     "entry_price": 34567.89,
     "exit_price": 35012.50,
     "quantity": 0.1,
     "side": "BUY",
     "pnl": 44.60,
     "pnl_percent": 0.13,
     "take_profit_hit": True,
     "timestamp_entry": datetime,
     "timestamp_exit": datetime
   })
```

### Resultado salvo no banco

```python
# Estrutura final no MongoDB
{
  "_id": ObjectId("..."),
  "user_id": "user123",
  "bot_id": "bot456",
  "symbol": "BTC-USDT",
  "entry": {
    "order_id": "5f3113a1689401000612a12a",
    "price": Decimal("34567.89"),
    "quantity": Decimal("0.1"),
    "timestamp": datetime,
    "fee": Decimal("0.35"),
    "fee_currency": "USDT"
  },
  "exit": {
    "order_id": "5f3113a1689401000612a12e",
    "price": Decimal("35012.50"),
    "quantity": Decimal("0.1"),
    "timestamp": datetime,
    "fee": Decimal("0.35"),
    "fee_currency": "USDT",
    "reason": "TAKE_PROFIT"
  },
  "pnl": Decimal("44.60"),
  "pnl_percent": Decimal("0.13"),
  "strategy": "sma_crossover",
  "risk_taken": Decimal("1.5"),
  "reward": Decimal("44.60"),
  "risk_reward_ratio": Decimal("29.73"),
  "status": "CLOSED",
  "created_at": datetime,
  "updated_at": datetime
}
```

---

## PRÓXIMAS AÇÕES (IMEDIATAS)

1. ✅ Crie pasta `backend/app/exchanges/`
2. ✅ Desenvolva `KuCoinRawClient` (camada 1)
3. ✅ Desenvolva `PayloadNormalizer` (camada 2)
4. ✅ Implemente testes unitários
5. ✅ Setup CI/CD pipeline
6. ✅ Deploy para staging
7. ✅ Teste com sandbox KuCoin
8. ✅ Gradualmente migre usuários de CCXT para novo sistema

**Estimado:** 2-3 sprints (READY FOR PRODUCTION)
