# DOC 07 — Risk Management Engine

> **Nível:** Produção | **Escopo:** Stop Loss, Drawdown, Kill Switch, Circuit Breakers  
> **Prioridade:** Crítica — sem isso, um bug pode zerar o saldo do usuário

---

## 1. OBJETIVO

Implementar o módulo de gerenciamento de risco que protege o capital do usuário de:
- Perdas únicas excessivas (stop loss por trade)
- Perdas acumuladas no dia (drawdown diário)
- Comportamento errático do bot (burst de erros)
- Exchange offline ou preço indisponível (circuit breaker)
- Posições abertas por tempo demais (time-based exit)

---

## 2. HIERARQUIA DE PROTEÇÕES

```
Nível 1 (Por Trade):
    └── Stop Loss fixo           → fechar posição se preço cai X%
    └── Take Profit              → realizar lucro se sobe Y%
    └── Trailing Stop            → mover stop conforme preço sobe
    └── Max holding time         → fechar se dentro de N horas mesmo neutro

Nível 2 (Por Sessão do Bot):
    └── Daily drawdown limit     → parar bot se perde Z% no dia
    └── Consecutive loss limit   → parar após N perdas seguidas
    └── Error burst protection   → parar após M erros em T segundos

Nível 3 (Kill Switch):
    └── Emergency stop           → parar TODOS os bots do usuário
    └── Admin kill               → parar bots de todos os usuários
    └── Exchange connectivity    → parar se KuCoin indisponível por X min
```

---

## 3. MÓDULO PRINCIPAL

```python
# backend/app/risk/manager.py

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

logger = logging.getLogger("risk.manager")


class StopReason(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    MAX_HOLDING_TIME = "max_holding_time"
    DAILY_DRAWDOWN = "daily_drawdown"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    ERROR_BURST = "error_burst"
    EXCHANGE_OFFLINE = "exchange_offline"
    MANUAL_STOP = "manual_stop"
    EMERGENCY_KILL = "emergency_kill"


@dataclass
class RiskConfig:
    """Parâmetros configuráveis por instância de bot."""
    # Por trade
    stop_loss_pct: float = 5.0        # Fechar se queda >= 5%
    take_profit_pct: float = 15.0     # Fechar se alta >= 15%
    trailing_stop_pct: Optional[float] = None   # None = desabilitado
    max_holding_hours: int = 48       # Fechar após 48h independente

    # Por sessão
    max_daily_drawdown_pct: float = 10.0   # Parar bot se -10% no dia
    max_consecutive_losses: int = 5        # Parar após 5 perdas seguidas
    max_error_burst: int = 10             # Parar após 10 erros em 1 minuto

    @classmethod
    def from_instance(cls, instance: dict) -> "RiskConfig":
        cfg = instance.get("configuration", {})
        return cls(
            stop_loss_pct=cfg.get("stop_loss_pct", 5.0),
            take_profit_pct=cfg.get("take_profit_pct", 15.0),
            trailing_stop_pct=cfg.get("trailing_stop_pct"),
            max_holding_hours=cfg.get("max_holding_hours", 48),
            max_daily_drawdown_pct=cfg.get("max_daily_loss_pct", 10.0),
            max_consecutive_losses=cfg.get("max_consecutive_losses", 5),
            max_error_burst=cfg.get("max_error_burst", 10),
        )


class RiskManager:
    def __init__(self, config: RiskConfig, bot_instance_id: str):
        self.config = config
        self.bot_instance_id = bot_instance_id

        # Estado de sessão
        self._daily_start_capital: Optional[float] = None
        self._daily_losses = 0.0
        self._consecutive_losses = 0
        self._error_timestamps: list = []

        # Trailing stop state
        self._trailing_peak_price: Optional[float] = None

    # ── Nível 1: Proteção por Trade ────────────────────────────────────────

    def check_position_exit(
        self,
        entry_price: float,
        current_price: float,
        entry_timestamp: datetime
    ) -> Optional[StopReason]:
        """
        Avalia se a posição aberta deve ser fechada agora.
        Retorna o motivo ou None se pode continuar.
        """
        # Calcular variação
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Stop Loss
        if pnl_pct <= -self.config.stop_loss_pct:
            logger.warning(
                f"[{self.bot_instance_id}] STOP LOSS acionado: "
                f"PnL={pnl_pct:.2f}% (limite={-self.config.stop_loss_pct}%)"
            )
            return StopReason.STOP_LOSS

        # Take Profit
        if pnl_pct >= self.config.take_profit_pct:
            logger.info(
                f"[{self.bot_instance_id}] TAKE PROFIT atingido: "
                f"PnL={pnl_pct:.2f}%"
            )
            return StopReason.TAKE_PROFIT

        # Trailing Stop
        if self.config.trailing_stop_pct is not None:
            result = self._check_trailing_stop(current_price)
            if result:
                return result

        # Max Holding Time
        hours_open = (datetime.utcnow() - entry_timestamp).total_seconds() / 3600
        if hours_open >= self.config.max_holding_hours:
            logger.warning(
                f"[{self.bot_instance_id}] MAX HOLDING TIME: {hours_open:.1f}h"
            )
            return StopReason.MAX_HOLDING_TIME

        return None  # Continuar na posição

    def _check_trailing_stop(self, current_price: float) -> Optional[StopReason]:
        """Atualiza o pico e verifica se o preço caiu do pico além do trailing %."""
        if self._trailing_peak_price is None or current_price > self._trailing_peak_price:
            self._trailing_peak_price = current_price
            return None

        drop_from_peak = ((self._trailing_peak_price - current_price) / self._trailing_peak_price) * 100
        if drop_from_peak >= self.config.trailing_stop_pct:
            logger.warning(
                f"[{self.bot_instance_id}] TRAILING STOP: "
                f"pico={self._trailing_peak_price:.4f}, atual={current_price:.4f}, "
                f"queda={drop_from_peak:.2f}%"
            )
            return StopReason.TRAILING_STOP

        return None

    # ── Nível 2: Proteção de Sessão ────────────────────────────────────────

    def init_daily_session(self, current_capital: float):
        """Chamado ao iniciar o bot ou à meia-noite UTC."""
        self._daily_start_capital = current_capital
        self._daily_losses = 0.0
        self._consecutive_losses = 0
        logger.info(f"[{self.bot_instance_id}] Nova sessão diária: capital={current_capital:.4f} USDT")

    def record_trade_result(self, pnl_net_usdt: float) -> Optional[StopReason]:
        """
        Registra resultado de trade fechada.
        Retorna StopReason se o bot deve parar, None se pode continuar.
        """
        if pnl_net_usdt < 0:
            self._daily_losses += abs(pnl_net_usdt)
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # Checar drawdown diário
        if self._daily_start_capital and self._daily_start_capital > 0:
            daily_drawdown_pct = (self._daily_losses / self._daily_start_capital) * 100
            if daily_drawdown_pct >= self.config.max_daily_drawdown_pct:
                logger.critical(
                    f"[{self.bot_instance_id}] DAILY DRAWDOWN LIMIT: "
                    f"{daily_drawdown_pct:.2f}% (limite={self.config.max_daily_drawdown_pct}%)"
                )
                return StopReason.DAILY_DRAWDOWN

        # Checar perdas consecutivas
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            logger.critical(
                f"[{self.bot_instance_id}] CONSECUTIVE LOSSES: "
                f"{self._consecutive_losses} seguidas"
            )
            return StopReason.CONSECUTIVE_LOSSES

        return None

    def record_error(self) -> Optional[StopReason]:
        """
        Registra um erro de execução. Retorna STOP se houver burst.
        """
        now = datetime.utcnow()
        self._error_timestamps.append(now)

        # Manter apenas erros do último minuto
        cutoff = now - timedelta(minutes=1)
        self._error_timestamps = [t for t in self._error_timestamps if t >= cutoff]

        if len(self._error_timestamps) >= self.config.max_error_burst:
            logger.critical(
                f"[{self.bot_instance_id}] ERROR BURST: "
                f"{len(self._error_timestamps)} erros no último minuto"
            )
            return StopReason.ERROR_BURST

        return None
```

---

## 4. INTEGRAÇÃO NO BOTWORKER

```python
# Dentro do BotWorker:

class BotWorker:
    def __init__(self, instance: dict):
        # ...
        self.risk = RiskManager(
            config=RiskConfig.from_instance(instance),
            bot_instance_id=str(instance["_id"])
        )

    async def _tick(self, current_price: float):
        """Loop principal do bot — executado a cada candle."""

        # Se tem posição aberta, checar saída por risco
        if self._open_position:
            stop_reason = self.risk.check_position_exit(
                entry_price=self._open_position.entry_price,
                current_price=current_price,
                entry_timestamp=self._open_position.entry_timestamp
            )
            if stop_reason:
                await self._force_close_position(reason=stop_reason)
                return

        # Processar sinal da estratégia normalmente
        signal = await self.strategy.analyze(current_price)
        # ...

    async def _on_trade_closed(self, pnl_net_usdt: float):
        """Chamado após cada trade ser fechada."""
        stop_reason = self.risk.record_trade_result(pnl_net_usdt)
        if stop_reason:
            logger.critical(f"Bot {self._instance_id} parando por risco: {stop_reason}")
            await self._stop_bot(reason=stop_reason)

    async def _handle_error(self, error: Exception):
        stop_reason = self.risk.record_error()
        logger.error(f"Erro no bot {self._instance_id}: {error}")
        if stop_reason:
            await self._stop_bot(reason=stop_reason)
```

---

## 5. KILL SWITCH GLOBAL

```python
# backend/app/risk/kill_switch.py

GLOBAL_KILL_KEY = "kill_switch:global"
USER_KILL_PREFIX = "kill_switch:user:"


class KillSwitchService:
    def __init__(self, redis, db):
        self.redis = redis
        self.db = db

    async def check_should_stop(self, bot_instance_id: str, user_id: str) -> Optional[StopReason]:
        """Verificado a cada tick pelo BotWorker."""
        # Kill switch global (admin)
        if await self.redis.exists(GLOBAL_KILL_KEY):
            return StopReason.EMERGENCY_KILL

        # Kill switch por usuário
        if await self.redis.exists(f"{USER_KILL_PREFIX}{user_id}"):
            return StopReason.EMERGENCY_KILL

        return None

    async def trigger_user_kill_switch(self, user_id: str, reason: str):
        """Para todos os bots de um usuário imediatamente."""
        await self.redis.setex(f"{USER_KILL_PREFIX}{user_id}", 3600, reason)
        # Enviar comando de stop para cada bot ativo do usuário
        active_bots = await self.db["user_bot_instances"].find(
            {"user_id": user_id, "status": {"$in": ["running", "paused"]}}
        ).to_list(length=50)
        for bot in active_bots:
            await self.redis.lpush("bot:commands", json.dumps({
                "action": "stop",
                "bot_instance_id": str(bot["_id"]),
                "user_id": user_id,
                "reason": "kill_switch"
            }))
        logger.critical(f"Kill switch ativado para usuário {user_id}: {reason}")

    async def trigger_global_kill_switch(self, admin_id: str, reason: str):
        """Para TODOS os bots da plataforma — usar apenas em emergência."""
        await self.redis.setex(GLOBAL_KILL_KEY, 86400, reason)
        await self.redis.lpush("bot:commands", json.dumps({
            "action": "stop_all",
            "reason": f"global_kill: {reason}"
        }))
        logger.critical(f"⚠️ KILL SWITCH GLOBAL ativado por admin {admin_id}: {reason}")
```

---

## 6. ENDPOINT DE EMERGÊNCIA (ADMIN)

```python
@router.post("/admin/kill-switch/{user_id}", dependencies=[Depends(require_admin)])
async def trigger_user_kill_switch(user_id: str, reason: str = Body(...)):
    ks = KillSwitchService(redis=await get_redis(), db=get_db())
    await ks.trigger_user_kill_switch(user_id, reason)
    return {"message": f"Kill switch ativado para {user_id}"}


@router.post("/admin/kill-switch/global", dependencies=[Depends(require_admin)])
async def trigger_global_kill_switch(
    reason: str = Body(...),
    current_user: dict = Depends(get_current_user)
):
    ks = KillSwitchService(redis=await get_redis(), db=get_db())
    await ks.trigger_global_kill_switch(str(current_user["_id"]), reason)
    return {"message": "Kill switch GLOBAL ativado"}
```

---

## 7. CHECKLIST

- [ ] `RiskManager` instanciado por `BotWorker` com config da instância
- [ ] Stop loss verificado a cada tick (não apenas a cada candle)
- [ ] Take profit verificado a cada tick
- [ ] Trailing stop opcional, configurável por instância
- [ ] Max holding time para posições "presas"
- [ ] Daily drawdown limit reinicia à meia-noite UTC
- [ ] Consecutive losses encerra o bot e notifica usuário
- [ ] Error burst previne loops de erros infinitos
- [ ] Kill switch por usuário via Redis (resposta < 1 tick)
- [ ] Kill switch global apenas para admins
- [ ] Todos os stops registrados em `bot_execution_logs` com reason
- [ ] Usuário recebe notificação quando bot para por risco
