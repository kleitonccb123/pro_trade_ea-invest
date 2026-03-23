# DOC 02 — Modelo de Banco para Robôs Ativos

> **Nível:** Produção | **Banco:** MongoDB  
> **Prioridade:** Crítica — estrutura base para toda execução

---

## 1. OBJETIVO

Definir o esquema completo de coleções MongoDB para suportar robôs ativos em produção, incluindo:
- Controle de instâncias de robôs por usuário
- Histórico de trades executados
- Snapshots de performance
- Logs de execução estruturados
- Índices otimizados para queries de ranking e P&L
- Controle de concorrência com locks distribuídos

---

## 2. PROBLEMA ATUAL

O projeto tentou salvar credenciais KuCoin em `trading_credentials`. Não existe nenhuma collection para:
- Instâncias de robôs rodando
- Histórico de trades reais
- Performance acumulada
- Logs de estratégia

---

## 3. COLEÇÕES NECESSÁRIAS

### 3.1 `user_bot_instances` — Instâncias ativas de robôs

```javascript
{
  "_id": ObjectId("..."),                    // ID único da instância
  "user_id": "abc123",                       // FK do usuário
  "robot_id": "bot_001",                     // ID do robô do marketplace
  "robot_name": "Volatility Dragon",         // Nome (desnormalizado para display)
  "robot_type": "grid",                      // Tipo de estratégia
  
  // Configuração da instância (imutável após criação)
  "configuration": {
    "pair": "BTC-USDT",                      // Par de trading KuCoin
    "capital_usdt": 500.00,                  // Capital alocado
    "timeframe": "1h",                       // Timeframe das velas
    "stop_loss_pct": 5.0,                    // Stop loss em %
    "take_profit_pct": 15.0,                 // Take profit em %
    "max_daily_loss_usdt": 50.0,             // Perda diária máxima
    "strategy_params": {                      // Parâmetros específicos da estratégia
      "grid_levels": 10,
      "grid_spacing_pct": 1.0,
      "rsi_period": 14,
      "rsi_oversold": 30,
      "rsi_overbought": 70
    }
  },
  
  // Estado de execução (mutável)
  "status": "running",                        // pending|running|paused|stopped|error
  "stop_reason": null,                        // motivo do stop se aplicável
  "error_message": null,                      // mensagem de erro se status=error
  
  // Métricas de P&L (atualizadas após cada trade)
  "metrics": {
    "total_pnl_usdt": 127.45,               // P&L realizado total
    "unrealized_pnl_usdt": 12.30,           // P&L não realizado (posições abertas)
    "total_trades": 48,                      // Total de trades executados
    "winning_trades": 31,                    // Trades vencedores
    "losing_trades": 17,                     // Trades perdedores
    "win_rate": 64.58,                       // Win rate em %
    "largest_win_usdt": 45.20,              // Maior ganho único
    "largest_loss_usdt": -28.10,            // Maior perda única
    "total_fees_paid_usdt": 3.84,           // Total de taxas pagas
    "max_drawdown_pct": 8.2,               // Drawdown máximo registrado
    "sharpe_ratio": 1.34,                   // Calculado nos snapshots diários
    "profit_factor": 1.87,                  // (Ganhos totais) / (Perdas totais)
    "initial_capital_usdt": 500.00,         // Capital inicial (para calcular ROI)
    "current_capital_usdt": 627.45,        // Capital atual
  },
  
  // Controle de tempo
  "started_at": ISODate("2026-02-10T14:00:00Z"),
  "stopped_at": null,
  "last_heartbeat": ISODate("2026-02-26T10:15:30Z"),  // Atualizado pelo worker
  "last_trade_at": ISODate("2026-02-26T09:55:00Z"),
  
  // Segurança — referência às credenciais (nunca plain text aqui)
  "credentials_id": ObjectId("..."),        // FK para trading_credentials
  
  // Estado interno da estratégia (serializado para restart)
  "strategy_state": {
    "open_orders": ["order_id_1", "order_id_2"],
    "last_signal": "buy",
    "grid_current_level": 4,
    // ... específico por estratégia
  },

  "created_at": ISODate("2026-02-10T14:00:00Z"),
  "updated_at": ISODate("2026-02-26T10:15:30Z")
}
```

**Índices:**
```javascript
// Busca rápida por usuário e status (query mais comum)
db.user_bot_instances.createIndex({ "user_id": 1, "status": 1 })

// Busca por robô específico (para ranking)
db.user_bot_instances.createIndex({ "robot_id": 1, "status": 1 })

// Heartbeat monitor (identificar workers mortos)
db.user_bot_instances.createIndex(
  { "last_heartbeat": 1 },
  { expireAfterSeconds: null }  // Não expira — apenas para queries
)

// Constraint: um usuário não pode ter duas instâncias do mesmo robô rodando
db.user_bot_instances.createIndex(
  { "user_id": 1, "robot_id": 1, "status": 1 },
  { unique: true, partialFilterExpression: { "status": { $in: ["running", "pending", "paused"] } } }
)
```

---

### 3.2 `bot_trades` — Histórico de trades executados

```javascript
{
  "_id": ObjectId("..."),

  // Identificação
  "bot_instance_id": ObjectId("..."),       // FK para user_bot_instances
  "user_id": "abc123",                       // Desnormalizado para queries diretas
  "robot_id": "bot_001",                     // Desnormalizado
  
  // Dados da ordem na KuCoin
  "exchange_order_id": "5bd6e9286d99522a52e458de",
  "exchange": "kucoin",
  "symbol": "BTC-USDT",
  "side": "buy",                             // buy | sell
  "order_type": "market",                    // market | limit
  
  // Execução
  "requested_quantity": 0.001234,           // BTC solicitado
  "executed_quantity": 0.001234,            // BTC realmente executado
  "executed_price": 48750.50,              // Preço médio de execução
  "total_usdt": 60.18,                     // Total em USDT (qty × price)
  "fee_usdt": 0.048,                       // Taxa em USDT
  "fee_currency": "USDT",
  "slippage_pct": 0.012,                   // Slippage vs preço de mercado no momento
  
  // P&L (calculado para ordens de venda)
  "realized_pnl_usdt": null,               // null para compras; valor para vendas
  "matched_buy_order_id": null,            // ID da compra correspondente (FIFO)
  
  // Contexto da estratégia
  "strategy_reason": "RSI oversold (28.4), EMA bounce confirmado",
  "market_price_at_signal": 48740.00,     // Preço quando o sinal foi gerado
  "signal_timestamp": ISODate("..."),
  
  // Status
  "status": "filled",                      // pending | filled | cancelled | rejected
  "executed_at": ISODate("2026-02-26T09:55:00Z"),
  "created_at": ISODate("2026-02-26T09:54:58Z"),
  
  // Raw response da exchange (para auditoria completa)
  "exchange_response": { ... }             // JSON completo da KuCoin
}
```

**Índices:**
```javascript
// Histórico por instância (mais usado)
db.bot_trades.createIndex({ "bot_instance_id": 1, "executed_at": -1 })

// Histórico por usuário (dashboard)
db.bot_trades.createIndex({ "user_id": 1, "executed_at": -1 })

// Busca por order_id da exchange (reconciliação)
db.bot_trades.createIndex({ "exchange_order_id": 1 }, { unique: true })

// Cálculo de P&L por período (ranking)
db.bot_trades.createIndex({ "robot_id": 1, "executed_at": -1, "realized_pnl_usdt": 1 })

// TTL: logs de trade nunca expiram (dado financeiro regulatório)
// Recomendação: manter por 7 anos
```

---

### 3.3 `bot_performance_snapshots` — Snapshots diários

```javascript
{
  "_id": ObjectId("..."),
  
  "bot_instance_id": ObjectId("..."),
  "robot_id": "bot_001",
  "user_id": "abc123",
  
  // Período
  "snapshot_date": ISODate("2026-02-26T00:00:00Z"),  // Início do dia UTC
  "snapshot_type": "daily",                            // daily | weekly | ranking_15d
  
  // Métricas do período
  "period_pnl_usdt": 45.67,              // P&L só deste dia
  "period_trades": 8,
  "period_win_rate": 75.0,
  "period_fees_usdt": 0.73,
  
  // Métricas acumuladas até este snapshot
  "cumulative_pnl_usdt": 127.45,
  "cumulative_trades": 48,
  "cumulative_win_rate": 64.58,
  "max_drawdown_pct": 8.2,
  "sharpe_ratio": 1.34,
  "profit_factor": 1.87,
  
  // Capital
  "capital_start_usdt": 582.00,          // Capital no início do dia
  "capital_end_usdt": 627.67,            // Capital no final do dia
  "roi_pct": 7.85,                       // ROI sobre capital inicial da instância
  
  "created_at": ISODate("2026-02-27T00:05:00Z")  // Criado pelo scheduler à meia-noite
}
```

**Índices:**
```javascript
// Snapshot mais recente por instância
db.bot_performance_snapshots.createIndex(
  { "bot_instance_id": 1, "snapshot_date": -1 }
)

// Ranking por robô em período (query intensiva — coberta pelo índice)
db.bot_performance_snapshots.createIndex(
  { "robot_id": 1, "snapshot_date": -1, "period_pnl_usdt": -1 }
)

// Garantir único snapshot por bot por dia
db.bot_performance_snapshots.createIndex(
  { "bot_instance_id": 1, "snapshot_date": 1, "snapshot_type": 1 },
  { unique: true }
)
```

---

### 3.4 `bot_execution_logs` — Logs estruturados por robô

```javascript
{
  "_id": ObjectId("..."),
  
  "bot_instance_id": ObjectId("..."),
  "user_id": "abc123",
  
  "level": "INFO",                         // DEBUG | INFO | WARNING | ERROR | RISK_BLOCK | CRITICAL
  "category": "strategy",                  // strategy | order | risk | system | ws
  "message": "RSI signal gerado: oversold (28.4) → ordem BUY",
  
  "metadata": {                            // Dados contextuais
    "price": 48740.00,
    "rsi_value": 28.4,
    "signal_strength": 0.85,
    "order_id": null
  },
  
  "timestamp": ISODate("2026-02-26T09:54:58Z")
}
```

**Índices:**
```javascript
// Logs recentes por instância (UI)
db.bot_execution_logs.createIndex({ "bot_instance_id": 1, "timestamp": -1 })

// TTL: logs expiram em 30 dias para não inflar o banco
db.bot_execution_logs.createIndex(
  { "timestamp": 1 },
  { expireAfterSeconds: 2592000 }  // 30 dias
)

// Busca por erros (alertas)
db.bot_execution_logs.createIndex(
  { "level": 1, "timestamp": -1 },
  { partialFilterExpression: { "level": { $in: ["ERROR", "CRITICAL"] } } }
)
```

---

### 3.5 `bot_locks` — Controle de concorrência distribuída

```javascript
{
  "_id": "lock:bot:abc123:BTC-USDT",      // lock_key único
  "bot_instance_id": "...",
  "acquired_at": ISODate("..."),
  "expires_at": ISODate("...")            // TTL de segurança
}
```

**Índices:**
```javascript
// TTL automático para remover locks expirados
db.bot_locks.createIndex(
  { "expires_at": 1 },
  { expireAfterSeconds: 0 }
)
```

---

## 4. MODELOS PYDANTIC (FastAPI)

```python
# backend/app/engine/models.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class BotStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class BotConfiguration(BaseModel):
    pair: str = Field(..., pattern=r"^[A-Z]+-[A-Z]+$")  # ex: BTC-USDT
    capital_usdt: float = Field(..., gt=10.0, le=100000.0)
    timeframe: str = Field("1h", pattern=r"^(1m|5m|15m|1h|4h|1d)$")
    stop_loss_pct: float = Field(5.0, ge=0.5, le=50.0)
    take_profit_pct: float = Field(15.0, ge=1.0, le=200.0)
    max_daily_loss_usdt: float = Field(50.0, gt=0)
    strategy_params: Dict[str, Any] = Field(default_factory=dict)


class BotMetrics(BaseModel):
    total_pnl_usdt: float = 0.0
    unrealized_pnl_usdt: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    largest_win_usdt: float = 0.0
    largest_loss_usdt: float = 0.0
    total_fees_paid_usdt: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    initial_capital_usdt: float = 0.0
    current_capital_usdt: float = 0.0


class UserBotInstance(BaseModel):
    id: Optional[str] = None
    user_id: str
    robot_id: str
    robot_name: str
    robot_type: str
    configuration: BotConfiguration
    status: BotStatus = BotStatus.PENDING
    stop_reason: Optional[str] = None
    error_message: Optional[str] = None
    metrics: BotMetrics = Field(default_factory=BotMetrics)
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    credentials_id: str = ""
    strategy_state: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BotTrade(BaseModel):
    id: Optional[str] = None
    bot_instance_id: str
    user_id: str
    robot_id: str
    exchange_order_id: str
    exchange: str = "kucoin"
    symbol: str
    side: str        # buy | sell
    order_type: str  # market | limit
    requested_quantity: float
    executed_quantity: float
    executed_price: float
    total_usdt: float
    fee_usdt: float
    fee_currency: str = "USDT"
    slippage_pct: float = 0.0
    realized_pnl_usdt: Optional[float] = None
    matched_buy_order_id: Optional[str] = None
    strategy_reason: str = ""
    market_price_at_signal: float = 0.0
    signal_timestamp: Optional[datetime] = None
    status: str = "filled"
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    exchange_response: Dict[str, Any] = Field(default_factory=dict)
```

---

## 5. REPOSITORY PATTERN

```python
# backend/app/engine/repository.py

from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from app.core.database import get_db
from app.engine.models import UserBotInstance, BotStatus


class BotInstanceRepository:

    @staticmethod
    async def create(instance: UserBotInstance) -> str:
        db = get_db()
        doc = instance.dict(exclude={"id"})
        doc["started_at"] = datetime.utcnow()
        result = await db["user_bot_instances"].insert_one(doc)
        return str(result.inserted_id)

    @staticmethod
    async def get_by_id(bot_id: str) -> Optional[dict]:
        db = get_db()
        return await db["user_bot_instances"].find_one({"_id": ObjectId(bot_id)})

    @staticmethod
    async def get_active_by_user(user_id: str) -> List[dict]:
        db = get_db()
        return await db["user_bot_instances"].find(
            {"user_id": user_id, "status": {"$in": ["running", "paused", "pending"]}}
        ).to_list(length=None)

    @staticmethod
    async def update_metrics(bot_id: str, metrics_update: dict):
        db = get_db()
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)},
            {"$set": {f"metrics.{k}": v for k, v in metrics_update.items()},
             "$set": {"updated_at": datetime.utcnow()}}
        )

    @staticmethod
    async def acquire_lock(bot_id: str, symbol: str, ttl_seconds: int = 30) -> bool:
        """
        Tenta adquirir lock para evitar ordens duplicadas simultâneas.
        Retorna True se conseguiu o lock, False se já estava travado.
        """
        db = get_db()
        lock_key = f"lock:bot:{bot_id}:{symbol}"
        expires_at = datetime.utcnow().replace(second=datetime.utcnow().second + ttl_seconds)
        try:
            await db["bot_locks"].insert_one({
                "_id": lock_key,
                "bot_instance_id": bot_id,
                "acquired_at": datetime.utcnow(),
                "expires_at": expires_at
            })
            return True
        except Exception:
            # DuplicateKeyError — lock já existe
            return False

    @staticmethod
    async def release_lock(bot_id: str, symbol: str):
        db = get_db()
        lock_key = f"lock:bot:{bot_id}:{symbol}"
        await db["bot_locks"].delete_one({"_id": lock_key})

    @staticmethod
    async def check_duplicate_robot(user_id: str, robot_id: str) -> bool:
        """Verifica se usuário já tem esse robô rodando."""
        db = get_db()
        existing = await db["user_bot_instances"].find_one({
            "user_id": user_id,
            "robot_id": robot_id,
            "status": {"$in": ["running", "pending", "paused"]}
        })
        return existing is not None
```

---

## 6. MIGRATIONS (CRIAÇÃO DOS ÍNDICES)

```python
# backend/app/engine/migrations.py

async def create_indexes():
    db = get_db()

    # user_bot_instances
    col = db["user_bot_instances"]
    await col.create_index([("user_id", 1), ("status", 1)])
    await col.create_index([("robot_id", 1), ("status", 1)])
    await col.create_index([("last_heartbeat", 1)])
    await col.create_index(
        [("user_id", 1), ("robot_id", 1), ("status", 1)],
        unique=True,
        partialFilterExpression={"status": {"$in": ["running", "pending", "paused"]}}
    )

    # bot_trades
    col = db["bot_trades"]
    await col.create_index([("bot_instance_id", 1), ("executed_at", -1)])
    await col.create_index([("user_id", 1), ("executed_at", -1)])
    await col.create_index([("exchange_order_id", 1)], unique=True)
    await col.create_index([("robot_id", 1), ("executed_at", -1), ("realized_pnl_usdt", -1)])

    # bot_performance_snapshots
    col = db["bot_performance_snapshots"]
    await col.create_index([("bot_instance_id", 1), ("snapshot_date", -1)])
    await col.create_index([("robot_id", 1), ("snapshot_date", -1), ("period_pnl_usdt", -1)])
    await col.create_index(
        [("bot_instance_id", 1), ("snapshot_date", 1), ("snapshot_type", 1)],
        unique=True
    )

    # bot_execution_logs
    col = db["bot_execution_logs"]
    await col.create_index([("bot_instance_id", 1), ("timestamp", -1)])
    await col.create_index(
        [("timestamp", 1)],
        expireAfterSeconds=2592000  # 30 dias
    )
    await col.create_index(
        [("level", 1), ("timestamp", -1)],
        partialFilterExpression={"level": {"$in": ["ERROR", "CRITICAL"]}}
    )

    # bot_locks
    col = db["bot_locks"]
    await col.create_index([("expires_at", 1)], expireAfterSeconds=0)
```

---

## 7. CONTROLE DE CONCORRÊNCIA

### Race Condition: Dois ciclos do mesmo robô executando simultaneamente

**Cenário problemático:**
```
Ciclo 1: RSI oversold detectado → calculando quantidade
Ciclo 2: RSI oversold detectado → calculando quantidade
Ciclo 1: place_order(BUY 0.001 BTC) ✅
Ciclo 2: place_order(BUY 0.001 BTC) ← ORDEM DUPLICADA ❌
```

**Solução: Lock por bot_id + symbol:**
```python
async def _execute_cycle(self, tick: dict):
    # Tentar adquirir lock (TTL 30s = timeout de segurança)
    lock_acquired = await BotInstanceRepository.acquire_lock(
        self.bot_id, self.config["pair"], ttl_seconds=30
    )
    if not lock_acquired:
        logger.debug(f"Ciclo pulado — lock não disponível para {self.bot_id}")
        return

    try:
        # Executar o ciclo com segurança
        await self._do_execute_cycle(tick)
    finally:
        await BotInstanceRepository.release_lock(self.bot_id, self.config["pair"])
```

---

## 8. CHECKLIST

- [ ] Criar coleções e índices via `create_indexes()` no startup
- [ ] Adicionar `BotInstanceRepository` com todos os métodos
- [ ] `exchange_order_id` com índice único (evitar trades duplicados)
- [ ] Lock TTL configurado corretamente no índice `bot_locks`
- [ ] Pydantic models com validações (capital > 10 USDT, par no formato correto)
- [ ] Testes unitários do repository com banco de test

---

## 9. CRITÉRIOS DE ACEITE

- [ ] Constraint impede dois robôs iguais do mesmo usuário ativos simultaneamente
- [ ] Lock impede ordens duplicadas — testado com 2 workers simultâneos
- [ ] TTL de 30 dias em `bot_execution_logs` funcionando (verificar com MongoDB explain)
- [ ] Índice de ranking (`robot_id + snapshot_date + pnl`) com query time < 50ms para 10k snapshots
- [ ] `exchange_order_id` único — inserção duplicada gera `DuplicateKeyError` tratado
