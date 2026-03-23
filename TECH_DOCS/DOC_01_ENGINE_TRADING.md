# DOC 01 — Arquitetura de Engine de Trading

> **Nível:** Produção | **Stack:** FastAPI + AsyncIO + APScheduler + KuCoin API  
> **Prioridade:** Crítica — sem isso, nenhum robô opera de verdade

---

## 1. OBJETIVO

Criar um serviço de execução de estratégias de trading completamente separado da camada de API HTTP. A engine deve:

- Executar múltiplas estratégias simultaneamente (um worker por robô ativo)
- Ser tolerante a falhas — crash de um robô não derruba outros
- Persistir estado de execução — sobreviver a reinicializações
- Ser observável — logs, métricas, health checks por robô
- Ser escalável horizontalmente — múltiplas instâncias da engine

---

## 2. PROBLEMA ATUAL

```
Estado atual:
API HTTP (FastAPI)
    └── Recebe chamadas do frontend
    └── Salva credenciais KuCoin
    └── NÃO executa nenhuma estratégia
    └── NÃO conecta WebSocket da KuCoin
    └── Dados de robôs = mock estático
```

O botão "Ativar" no frontend não chama nenhum endpoint funcional de execução. Não existe processo rodando estratégias de trading no servidor.

---

## 3. ARQUITETURA PROPOSTA

### 3.1 Separação de Responsabilidades

```
┌─────────────────────────────────────────────────────────────────┐
│                        PROCESSO DA API                          │
│  FastAPI (uvicorn)                                              │
│  ├── Auth, perfil, gamificação                                  │
│  ├── CRUD de robôs (start/stop/status)                         │
│  ├── WebSocket de telemetria → frontend                         │
│  └── NÃO executa ordens — apenas orquestra                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │  MongoDB (estado compartilhado)
                           │  + Redis (filas e locks)
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    PROCESSO DA ENGINE                            │
│  bot_engine.py (processo separado)                             │
│  ├── BotOrchestrator — gerencia workers ativos                  │
│  ├── BotWorker (1 por robô ativo) — loop de estratégia         │
│  ├── KuCoinClient — wrapper da API KuCoin com retry            │
│  ├── RiskEngine — stop loss, drawdown, kill switch             │
│  └── PnLCalculator — atualiza lucros em tempo real             │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Comunicação API ↔ Engine

```
API                     Redis                    Engine
 │                        │                        │
 │── LPUSH bot:commands ──►│                        │
 │   {"action":"start",   │                        │
 │    "bot_id":"abc123"}  │                        │
 │                        │◄── BRPOP bot:commands ──│
 │                        │                        │
 │                        │──── processa ──────────►│
 │                        │                        │── executa KuCoin
 │                        │                        │── atualiza MongoDB
 │◄── MongoDB watch ───────────────────────────────│
 │   (change streams)     │                        │
```

### 3.3 Estrutura de Processos em Produção

```bash
# Processo 1 — API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Processo 2 — Engine (separado, mesmo servidor ou pod diferente)
python -m app.engine.main

# Processo 3 — Scheduler (recalcula ranking, snapshots diários)
python -m app.engine.scheduler
```

---

## 4. ESTRUTURA DE PASTAS

```
backend/
├── app/
│   ├── api/                    # Rotas HTTP (existente)
│   │   └── trading/
│   │       └── router.py
│   │
│   ├── engine/                 # ← NOVO — Engine de trading
│   │   ├── __init__.py
│   │   ├── main.py             # Entry point do processo da engine
│   │   ├── orchestrator.py     # BotOrchestrator — gerencia workers
│   │   ├── worker.py           # BotWorker — execução de uma instância
│   │   ├── scheduler.py        # APScheduler — tarefas periódicas
│   │   ├── state_manager.py    # Persistência de estado no Redis/MongoDB
│   │   │
│   │   ├── strategies/         # Implementações de estratégias
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # StrategyBase (ABC)
│   │   │   ├── grid.py         # Grid Trading
│   │   │   ├── rsi.py          # RSI Strategy
│   │   │   ├── macd.py         # MACD Strategy
│   │   │   ├── dca.py          # DCA Strategy
│   │   │   └── combined.py     # Combined Strategy
│   │   │
│   │   └── exchange/
│   │       ├── kucoin_client.py    # Client KuCoin com retry
│   │       ├── kucoin_ws.py        # WebSocket KuCoin
│   │       └── order_manager.py    # Gestão de ordens abertas
│   │
│   ├── risk/                   # ← NOVO — Risk management
│   │   ├── engine.py
│   │   ├── kill_switch.py
│   │   └── limits.py
│   │
│   └── shared/
│       ├── redis_client.py     # Conexão Redis singleton
│       └── events.py           # Event bus interno
```

---

## 5. IMPLEMENTAÇÃO: BotOrchestrator

```python
# backend/app/engine/orchestrator.py

import asyncio
import logging
from typing import Dict
from app.engine.worker import BotWorker
from app.shared.redis_client import get_redis
from app.core.database import get_db

logger = logging.getLogger("engine.orchestrator")


class BotOrchestrator:
    """
    Responsável por:
    - Iniciar/parar BotWorkers
    - Processar comandos vindos da API (via Redis)
    - Reiniciar workers que crasharam
    - Health check contínuo
    """

    def __init__(self):
        self._workers: Dict[str, BotWorker] = {}   # bot_instance_id → BotWorker
        self._tasks: Dict[str, asyncio.Task] = {}   # bot_instance_id → asyncio.Task
        self._running = False

    async def start(self):
        """Entry point principal do processo da engine."""
        self._running = True
        logger.info("🚀 BotOrchestrator iniciando...")

        # Carregar instâncias que estavam ativas antes de um possível crash
        await self._restore_active_bots()

        # Processar comandos da API e fazer health check em paralelo
        await asyncio.gather(
            self._command_listener(),
            self._health_monitor(),
        )

    async def _restore_active_bots(self):
        """Ao iniciar, reativa robôs que estavam marcados como 'running' no banco."""
        db = get_db()
        active_instances = await db["user_bot_instances"].find(
            {"status": "running"}
        ).to_list(length=None)

        logger.info(f"🔄 Restaurando {len(active_instances)} robôs ativos...")
        for instance in active_instances:
            await self._start_worker(str(instance["_id"]), instance)

    async def _command_listener(self):
        """
        Fica ouvindo a fila Redis 'bot:commands'.
        Comandos: start | stop | pause | resume
        """
        redis = await get_redis()
        logger.info("👂 Aguardando comandos na fila bot:commands...")

        while self._running:
            try:
                # Blocking pop com timeout de 5s para não travar indefinidamente
                result = await redis.brpop("bot:commands", timeout=5)
                if result:
                    _, payload = result
                    await self._handle_command(json.loads(payload))
            except Exception as e:
                logger.error(f"❌ Erro no command_listener: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _handle_command(self, command: dict):
        action = command.get("action")
        bot_id = command.get("bot_instance_id")

        logger.info(f"📨 Comando recebido: {action} para bot {bot_id}")

        if action == "start":
            db = get_db()
            instance = await db["user_bot_instances"].find_one({"_id": ObjectId(bot_id)})
            if instance:
                await self._start_worker(bot_id, instance)

        elif action == "stop":
            await self._stop_worker(bot_id, reason="user_request")

        elif action == "pause":
            if bot_id in self._workers:
                await self._workers[bot_id].pause()

        elif action == "resume":
            if bot_id in self._workers:
                await self._workers[bot_id].resume()

    async def _start_worker(self, bot_id: str, instance: dict):
        if bot_id in self._workers:
            logger.warning(f"⚠️ Worker {bot_id} já está em execução")
            return

        worker = BotWorker(instance)
        self._workers[bot_id] = worker

        # Cada worker roda em sua própria task asyncio
        task = asyncio.create_task(
            self._run_worker_with_supervision(bot_id, worker),
            name=f"bot-worker-{bot_id}"
        )
        self._tasks[bot_id] = task
        logger.info(f"✅ Worker iniciado para bot {bot_id}")

    async def _run_worker_with_supervision(self, bot_id: str, worker: BotWorker):
        """
        Supervisiona o worker e trata crashes.
        Política: retentar 3x com backoff exponencial antes de marcar como erro.
        """
        retries = 0
        max_retries = 3

        while retries <= max_retries:
            try:
                await worker.run()
                break  # Saiu normalmente (stop solicitado)
            except Exception as e:
                retries += 1
                logger.error(
                    f"💥 Worker {bot_id} crashou (tentativa {retries}/{max_retries}): {e}",
                    exc_info=True
                )

                if retries > max_retries:
                    logger.critical(f"🚨 Worker {bot_id} excedeu tentativas. Marcando como erro.")
                    await self._mark_bot_error(bot_id, str(e))
                    break

                # Backoff: 5s, 15s, 45s
                wait_time = 5 * (3 ** (retries - 1))
                await asyncio.sleep(wait_time)

        # Cleanup
        self._workers.pop(bot_id, None)
        self._tasks.pop(bot_id, None)

    async def _stop_worker(self, bot_id: str, reason: str = "unknown"):
        if bot_id not in self._workers:
            logger.warning(f"⚠️ Worker {bot_id} não encontrado para parar")
            return

        await self._workers[bot_id].stop(reason=reason)

    async def _health_monitor(self):
        """A cada 30s verifica se todos os workers esperados estão rodando."""
        while self._running:
            await asyncio.sleep(30)
            db = get_db()
            expected = await db["user_bot_instances"].find(
                {"status": "running"}
            ).to_list(length=None)

            for inst in expected:
                bot_id = str(inst["_id"])
                if bot_id not in self._workers:
                    logger.warning(f"⚠️ Worker {bot_id} sumiu! Reiniciando...")
                    await self._start_worker(bot_id, inst)

    async def _mark_bot_error(self, bot_id: str, error_msg: str):
        db = get_db()
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)},
            {"$set": {
                "status": "error",
                "error_message": error_msg,
                "stopped_at": datetime.utcnow()
            }}
        )
```

---

## 6. IMPLEMENTAÇÃO: BotWorker

```python
# backend/app/engine/worker.py

import asyncio
import logging
from datetime import datetime
from app.engine.strategies.base import StrategyBase
from app.engine.strategies import get_strategy
from app.engine.exchange.kucoin_client import KuCoinClient
from app.risk.engine import RiskEngine

logger = logging.getLogger("engine.worker")


class BotWorker:
    """
    Executa UMA instância de robô em loop contínuo.
    
    Responsabilidades:
    - Instanciar a estratégia correta baseada no tipo do robô
    - Loop de execução: obter dados de mercado → calcular sinal → executar ordem
    - Delegar ao RiskEngine antes de cada ordem
    - Persistir trades e P&L após cada execução
    - Responder a sinais de stop/pause
    """

    def __init__(self, instance: dict):
        self.instance = instance
        self.bot_id = str(instance["_id"])
        self.user_id = instance["user_id"]
        self.robot_id = instance["robot_id"]
        self.config = instance["configuration"]  # par, capital, timeframe, etc.

        self._running = False
        self._paused = False
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Começa como "não pausado"

        # Componentes
        self.exchange = KuCoinClient(
            api_key=instance["decrypted_api_key"],
            api_secret=instance["decrypted_api_secret"],
            api_passphrase=instance["decrypted_api_passphrase"],
        )
        self.strategy: StrategyBase = get_strategy(
            strategy_type=instance["robot_type"],
            config=self.config
        )
        self.risk_engine = RiskEngine(
            bot_id=self.bot_id,
            user_id=self.user_id,
            config=self.config
        )

    async def run(self):
        """Loop principal de execução."""
        self._running = True
        logger.info(f"▶️ BotWorker {self.bot_id} iniciando execução")

        await self._update_status("running")

        try:
            # Iniciar WebSocket para preço em tempo real
            async with self.exchange.ws_price_feed(self.config["pair"]) as price_stream:
                async for tick in price_stream:
                    if self._stop_event.is_set():
                        break

                    # Aguardar se pausado
                    await self._pause_event.wait()

                    try:
                        await self._execute_cycle(tick)
                    except Exception as e:
                        logger.error(f"❌ Erro no ciclo bot {self.bot_id}: {e}", exc_info=True)
                        await self._log_error(str(e))
                        # Continua rodando — não propaga exceção

        finally:
            self._running = False
            await self._update_status("stopped")
            logger.info(f"⏹️ BotWorker {self.bot_id} encerrado")

    async def _execute_cycle(self, tick: dict):
        """Um ciclo de decisão: dados → sinal → validação de risco → ordem."""
        current_price = tick["price"]
        timestamp = tick["timestamp"]

        # 1. Obter histórico de candles para a estratégia
        candles = await self.exchange.get_klines(
            symbol=self.config["pair"],
            interval=self.config["timeframe"],
            limit=200
        )

        # 2. Calcular sinal da estratégia
        signal = await self.strategy.calculate(candles, current_price)
        # signal: {"action": "buy"|"sell"|"hold", "quantity": float, "reason": str}

        if signal["action"] == "hold":
            return

        # 3. Verificar limites de risco ANTES de enviar
        risk_ok, risk_reason = await self.risk_engine.check(
            action=signal["action"],
            quantity=signal["quantity"],
            current_price=current_price
        )
        if not risk_ok:
            logger.warning(f"🛑 Ordem bloqueada por risco: {risk_reason}")
            await self._log_risk_block(risk_reason)
            return

        # 4. Executar ordem na KuCoin
        order_result = await self.exchange.place_market_order(
            symbol=self.config["pair"],
            side=signal["action"],
            quantity=signal["quantity"],
        )

        # 5. Persistir trade
        await self._persist_trade(order_result, signal)

        # 6. Atualizar P&L
        await self._update_pnl(order_result)

    async def stop(self, reason: str = "unknown"):
        """Para o worker graciosamente — cancela ordens abertas antes."""
        logger.info(f"🛑 Parando worker {self.bot_id} — motivo: {reason}")

        # Cancelar ordens abertas na KuCoin
        try:
            await self.exchange.cancel_all_orders(symbol=self.config["pair"])
        except Exception as e:
            logger.error(f"Erro ao cancelar ordens: {e}")

        self._stop_event.set()
        await self._update_status("stopped", stop_reason=reason)

    async def pause(self):
        self._pause_event.clear()
        await self._update_status("paused")

    async def resume(self):
        self._pause_event.set()
        await self._update_status("running")

    async def _update_status(self, status: str, **kwargs):
        from app.core.database import get_db
        db = get_db()
        update = {"status": status, "last_heartbeat": datetime.utcnow(), **kwargs}
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(self.bot_id)},
            {"$set": update}
        )

    async def _persist_trade(self, order_result: dict, signal: dict):
        from app.core.database import get_db
        db = get_db()
        trade_doc = {
            "bot_instance_id": self.bot_id,
            "user_id": self.user_id,
            "robot_id": self.robot_id,
            "exchange_order_id": order_result["orderId"],
            "symbol": self.config["pair"],
            "side": signal["action"],
            "quantity": order_result["dealFunds"],
            "price": order_result["dealPrice"],
            "fee": order_result["fee"],
            "strategy_reason": signal["reason"],
            "executed_at": datetime.utcnow(),
            "status": "filled",
        }
        await db["bot_trades"].insert_one(trade_doc)

    async def _update_pnl(self, order_result: dict):
        # Delegado ao PnLCalculator (DOC 05)
        from app.engine.pnl_calculator import PnLCalculator
        await PnLCalculator.update(
            bot_id=self.bot_id,
            trade=order_result
        )

    async def _log_error(self, error_msg: str):
        from app.core.database import get_db
        db = get_db()
        await db["bot_execution_logs"].insert_one({
            "bot_instance_id": self.bot_id,
            "level": "ERROR",
            "message": error_msg,
            "timestamp": datetime.utcnow()
        })

    async def _log_risk_block(self, reason: str):
        from app.core.database import get_db
        db = get_db()
        await db["bot_execution_logs"].insert_one({
            "bot_instance_id": self.bot_id,
            "level": "RISK_BLOCK",
            "message": reason,
            "timestamp": datetime.utcnow()
        })
```

---

## 7. ENTRY POINT DA ENGINE

```python
# backend/app/engine/main.py

import asyncio
import logging
import signal
from app.engine.orchestrator import BotOrchestrator
from app.core.database import connect_to_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("engine.main")


async def main():
    logger.info("🔧 Inicializando Engine de Trading...")

    # Conectar banco
    await connect_to_db()

    orchestrator = BotOrchestrator()

    # Graceful shutdown ao receber SIGTERM/SIGINT
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(orchestrator.shutdown())
        )

    try:
        await orchestrator.start()
    except Exception as e:
        logger.critical(f"💥 Engine crashou: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. ESTRATÉGIA BASE (CONTRATO)

```python
# backend/app/engine/strategies/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TradingSignal:
    action: str           # "buy" | "sell" | "hold"
    quantity: float       # Quantidade em USDT
    price_limit: Optional[float] = None  # Para ordens limit
    reason: str = ""      # Motivo legível para logging


class StrategyBase(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.pair = config["pair"]
        self.capital = config["capital_usdt"]
        self.timeframe = config.get("timeframe", "1h")

    @abstractmethod
    async def calculate(self, candles: list, current_price: float) -> TradingSignal:
        """
        Recebe candles históricos e preço atual.
        Retorna o sinal de trading.
        Nunca deve lançar exceção — retornar TradingSignal(action='hold') em caso de dúvida.
        """
        ...

    @abstractmethod
    async def on_order_filled(self, order: dict):
        """Callback chamado quando uma ordem é executada. Atualiza estado interno."""
        ...

    @abstractmethod
    def get_state(self) -> dict:
        """Retorna estado serializável para persistência."""
        ...

    @abstractmethod
    def restore_state(self, state: dict):
        """Restaura estado após restart."""
        ...
```

---

## 9. DIAGRAMA DE FLUXO COMPLETO

```
Frontend: clicar "Ativar"
         │
         ▼
POST /api/trading/bots/start
         │
         ├── Validar saldo KuCoin
         ├── Criar user_bot_instances (status: pending)
         ├── Descriptografar credenciais
         ├── LPUSH "bot:commands" {"action":"start", "bot_instance_id":"xxx"}
         └── Retornar {bot_id, status: "starting"}
                   │
                   ▼
         Redis Queue "bot:commands"
                   │
                   ▼
         BotOrchestrator._command_listener()
                   │
                   ├── Instanciar BotWorker
                   └── asyncio.create_task(worker.run())
                             │
                             ▼
                    BotWorker.run() — loop infinito
                             │
                    KuCoin WS (price feed)
                             │
                    _execute_cycle(tick)
                             │
                    ├── get_klines()
                    ├── strategy.calculate()
                    ├── risk_engine.check()
                    ├── exchange.place_order()
                    ├── _persist_trade()
                    └── _update_pnl()
                             │
                    MongoDB (bot_trades, bot_instances)
                             │
                    API WebSocket → Frontend (telemetria)
```

---

## 10. TRATAMENTO DE ERROS

| Cenário | Comportamento |
|---|---|
| KuCoin API offline | Retry com backoff exponencial (3 tentativas) |
| Ordem rejeitada (saldo insuficiente) | Log + parar robô + notificar usuário |
| WebSocket desconectado | Reconectar automaticamente em até 30s |
| Estratégia lança exceção | Log + continuar no próximo ciclo (não para o robô) |
| Risk engine bloqueia | Log + não enviar ordem + continuar |
| MongoDB offline | Engine para de persistir mas continua operando por 60s, depois para |
| Crash não tratado do worker | Supervisão: 3x retry com backoff 5s/15s/45s |
| SIGTERM do SO | Cancelar todas as ordens abertas → parar graciosamente |

---

## 11. CONSIDERAÇÕES DE SEGURANÇA

- Credenciais da KuCoin descriptografadas **em memória** — nunca persistidas em plain text
- Cada worker acessa apenas credenciais do seu próprio usuário
- Validação de `user_id` antes de qualquer operação na KuCoin
- Rate limit da KuCoin respeitado por usuário (não globalmente)
- Ordens sempre vinculadas ao `bot_instance_id` para auditoria

---

## 12. CONSIDERAÇÕES DE PERFORMANCE

- Um `asyncio.Task` por robô — não um thread por robô
- Até 500 robôs simultâneos em um único processo asyncio (estimativa conservadora)
- Para >500 robôs: escalar horizontalmente — ver DOC 09
- Candles cacheados por 60s no Redis para evitar chamadas redundantes à KuCoin
- WebSocket compartilhado por symbol, não por robô

---

## 13. CHECKLIST DE IMPLEMENTAÇÃO

- [ ] Criar `backend/app/engine/` com estrutura de pastas
- [ ] Implementar `KuCoinClient` com retry (ver DOC 04)
- [ ] Implementar `StrategyBase` e pelo menos `GridStrategy`
- [ ] Implementar `BotWorker` com loop WS
- [ ] Implementar `BotOrchestrator` com fila Redis
- [ ] Configurar Redis (`REDIS_URL` no `.env`)
- [ ] Criar `docker-compose.yml` com serviço `engine`
- [ ] Endpoint `POST /api/trading/bots/start` (ver DOC 03)
- [ ] Testes de integração: iniciar/parar/crashar worker
- [ ] Health check endpoint para a engine

---

## 14. CRITÉRIOS DE ACEITE

- [ ] Worker inicia dentro de 5s após comando "start"
- [ ] Worker reinicia automaticamente após crash sem intervenção humana
- [ ] Ao receber SIGTERM, cancela todas as ordens abertas antes de encerrar
- [ ] Dois workers do mesmo usuário nunca acessam a mesma posição simultaneamente
- [ ] Logs estruturados com `bot_instance_id`, `user_id`, `timestamp` em cada linha
- [ ] Engine sobrevive a restart do MongoDB por até 60s sem perder dados
- [ ] 100% das ordens executadas persistidas em `bot_trades`
