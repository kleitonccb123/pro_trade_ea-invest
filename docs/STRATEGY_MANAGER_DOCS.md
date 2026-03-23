# Strategy Manager — Documentação Técnica Completa

**Sistema:** Crypto Trade Hub — Automated Trading SaaS  
**Versão:** 1.0  
**Data:** 2026-02-27  
**Classificação:** Interno / Desenvolvimento

---

## Índice

1. [Visão Arquitetural](#1-visão-arquitetural)
2. [Máquina de Estados](#2-máquina-de-estados)
3. [Fluxo de Troca de Estratégia](#3-fluxo-de-troca-de-estratégia)
4. [Diagramas Lógicos](#4-diagramas-lógicos)
5. [Regras de Segurança](#5-regras-de-segurança)
6. [Pseudocódigo do Strategy Manager](#6-pseudocódigo-do-strategy-manager)
7. [API Interna do Strategy Manager](#7-api-interna-do-strategy-manager)
8. [Logs e Auditoria](#8-logs-e-auditoria)
9. [Tratamento de Erros e Falhas](#9-tratamento-de-erros-e-falhas)
10. [Boas Práticas de Implementação](#10-boas-práticas-de-implementação)
11. [Checklist de Implementação](#11-checklist-de-implementação)

---

## 1. Visão Arquitetural

### 1.1 Princípio Central

O sistema adota o modelo **Single Active Strategy (SAS)**. Em qualquer momento, somente **uma estratégia** pode estar no estado `ACTIVE`. Toda tentativa de ativar uma segunda estratégia aciona o processo controlado de troca (Strategy Switch), que é atômico, auditável e seguro.

### 1.2 Componentes do Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        STRATEGY MANAGER                         │
│                                                                 │
│  ┌───────────────┐    ┌──────────────────┐    ┌─────────────┐  │
│  │  Global Lock  │    │  State Machine   │    │ Audit Logger│  │
│  │  (Mutex/Redis)│    │  (FSM Controller)│    │ (Append-only│  │
│  └───────────────┘    └──────────────────┘    └─────────────┘  │
│                                                                 │
│  ┌───────────────┐    ┌──────────────────┐    ┌─────────────┐  │
│  │Position Closer│    │  Order Canceller │    │Context Reset│  │
│  │  (Exchange    │    │  (Exchange API)  │    │ (Memory /   │  │
│  │   API)        │    │                  │    │  Cache)     │  │
│  └───────────────┘    └──────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────┐       ┌──────────────────┐    ┌───────────────┐
│  Exchange   │       │  Strategy Pool   │    │   Database    │
│  WebSocket  │       │  (IDLE Registry) │    │  (Events/Log) │
└─────────────┘       └──────────────────┘    └───────────────┘
```

### 1.3 Responsabilidades por Camada

| Camada | Componente | Responsabilidade |
|---|---|---|
| **Controle** | Global Lock | Garantir exclusão mútua na ativação de estratégias |
| **Controle** | State Machine | Gerenciar transições de estado válidas |
| **Execução** | Position Closer | Fechar posições abertas via API da exchange |
| **Execução** | Order Canceller | Cancelar ordens pendentes via API da exchange |
| **Execução** | Context Reset | Limpar memória, caches e estado do bot anterior |
| **Observabilidade** | Audit Logger | Registrar todos os eventos de ciclo de vida |
| **Persistência** | Database | Persistir estado, histórico de trocas e logs |

---

## 2. Máquina de Estados

### 2.1 Definição dos Estados

| Estado | Código | Descrição |
|---|---|---|
| Ocioso | `IDLE` | Nenhuma estratégia ativa. Sistema aguardando ativação. |
| Ativo | `ACTIVE` | Uma estratégia está rodando normalmente. |
| Transição | `TRANSITION_STATE` | Troca de estratégia foi solicitada. Novas entradas bloqueadas. |
| Encerrando Posições | `CLOSING_POSITIONS` | Sistema fechando ativamente posições e ordens abertas. |
| Seguro para Trocar | `SAFE_TO_SWITCH` | Risco = 0. Contexto pode ser limpo com segurança. |
| Ativando Nova | `ACTIVATING_NEW_STRATEGY` | Nova estratégia sendo inicializada e registrada. |

### 2.2 Diagrama de Transição de Estados

```
                          ┌──────────────────────────────────┐
                          │                                  │
                          ▼                                  │
                       ┌──────┐                             │
                  ┌───►│ IDLE │◄────────────────────────┐   │
                  │    └──────┘                          │   │
                  │        │                             │   │
                  │   [activate()]                       │   │
                  │        │                             │   │
                  │        ▼                             │   │
                  │    ┌────────┐                        │   │
         [stop()] │   │ ACTIVE │──────────────────┐     │   │
                  │    └────────┘                  │     │   │
                  │        │                       │     │   │
                  │   [switch_strategy()]          │     │   │
                  │        │                  [switch_strategy()]
                  │        ▼                       │     │   │
                  │  ┌──────────────────┐          │     │   │
                  │  │ TRANSITION_STATE │◄─────────┘     │   │
                  │  └──────────────────┘                │   │
                  │        │                             │   │
                  │   [begin_close()]                    │   │
                  │        │                             │   │
                  │        ▼                             │   │
                  │  ┌────────────────────┐              │   │
                  │  │ CLOSING_POSITIONS  │              │   │
                  │  └────────────────────┘              │   │
                  │        │                             │   │
                  │   [all_closed()]                     │   │
                  │        │                             │   │
                  │        ▼                             │   │
                  │  ┌─────────────────┐                 │   │
                  │  │ SAFE_TO_SWITCH  │                 │   │
                  │  └─────────────────┘                 │   │
                  │        │                             │   │
                  │   [activate_new()]                   │   │
                  │        │                             │   │
                  │        ▼                             │   │
                  │  ┌──────────────────────────────┐    │   │
                  │  │ ACTIVATING_NEW_STRATEGY      │────┘   │
                  │  └──────────────────────────────┘        │
                  │                                          │
                  └──────────────────────────────────────────┘
                            [activate_done() / error()]
```

### 2.3 Transições Válidas

| De | Para | Gatilho | Condição Obrigatória |
|---|---|---|---|
| `IDLE` | `ACTIVE` | `activate()` | Nenhuma estratégia ativa |
| `ACTIVE` | `TRANSITION_STATE` | `switch_strategy()` | Lock global obtido |
| `TRANSITION_STATE` | `CLOSING_POSITIONS` | `begin_close()` | Entradas bloqueadas |
| `CLOSING_POSITIONS` | `SAFE_TO_SWITCH` | `all_closed()` | Posições=0, Ordens=0, Risco=0 |
| `SAFE_TO_SWITCH` | `ACTIVATING_NEW_STRATEGY` | `activate_new()` | Contexto limpo |
| `ACTIVATING_NEW_STRATEGY` | `ACTIVE` | `activate_done()` | Nova estratégia inicializada |
| `ACTIVATING_NEW_STRATEGY` | `IDLE` | `error()` | Falha na inicialização |
| `ACTIVE` | `IDLE` | `stop()` | Encerramento voluntário sem troca |

### 2.4 Transições Proibidas (Guardrails)

| De | Para | Motivo do Bloqueio |
|---|---|---|
| `ACTIVE` | `ACTIVE` | Violação de Single Strategy Mode |
| `CLOSING_POSITIONS` | `ACTIVE` | Posições ainda abertas |
| `TRANSITION_STATE` | `ACTIVE` | Troca em andamento |
| Qualquer | `ACTIVE` | Lock global não obtido |

---

## 3. Fluxo de Troca de Estratégia

### 3.1 Visão Macro

```
USUÁRIO solicita ativação de Estratégia B
          │
          ▼
┌─────────────────────┐
│  ETAPA 1 — BLOQUEIO │
│  • Adquire lock     │
│  • Bloqueia entradas│
│  • Estado: TRANSITION│
└─────────────────────┘
          │
          ▼
┌──────────────────────────┐
│  ETAPA 2 — ENCERRAMENTO  │
│  • Fecha posições abertas│
│  • Cancela ordens        │
│  • Encerra websockets    │
│  • Para timers/workers   │
└──────────────────────────┘
          │
          ▼
┌────────────────────────────────────────┐
│  ETAPA 3 — VERIFICAÇÃO DE RISCO ZERO   │
│  • posições_abertas == 0?              │
│  • ordens_pendentes == 0?              │
│  • exposição == 0?                     │
│  • risco_total == 0?                   │
│  • confirmação da exchange recebida?   │
│                                        │
│  NÃO → aguarda / retenta / timeout     │
│  SIM → avança para ETAPA 4             │
└────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────┐
│  ETAPA 4 — LIMPEZA         │
│  • Remove estado da memória│
│  • Limpa caches            │
│  • Reseta variáveis        │
│  • Libera recursos         │
└────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────┐
│  ETAPA 5 — ATIVAÇÃO SEGURA          │
│  • Inicia nova estratégia           │
│  • Registra evento em log auditável │
│  • ACTIVE_STRATEGY = Estratégia B   │
└─────────────────────────────────────┘
```

### 3.2 Detalhamento da Etapa 2 — Encerramento Automático

```
ENCERRAMENTO AUTOMÁTICO
        │
        ├──► [1] block_new_entries(strategy_id)
        │         Impede novas ordens de abertura
        │
        ├──► [2] close_all_positions(strategy_id)
        │         Para cada posição aberta:
        │           • Detecta direção (LONG/SHORT)
        │           • Emite ordem de mercado oposta
        │           • Aguarda confirmação de fill
        │           • Registra PnL de encerramento
        │
        ├──► [3] cancel_all_orders(strategy_id)
        │         Para cada ordem pendente:
        │           • Emite CANCEL via API da exchange
        │           • Aguarda confirmação de cancelamento
        │           • Remove da fila de monitoramento
        │
        ├──► [4] terminate_websockets(strategy_id)
        │         • Fecha conexões de mercado ativas
        │         • Remove listeners de preço/execução
        │         • Fecha conexão de user-data stream
        │
        └──► [5] stop_timers_and_workers(strategy_id)
                  • Para threads/coroutines do bot
                  • Cancela jobs agendados
                  • Aguarda finalização graceful (timeout: 30s)
```

### 3.3 Detalhamento da Etapa 3 — Verificação de Risco Zero

```
VERIFICAÇÃO DE RISCO ZERO (polling ou event-driven)
        │
        ├──► query_exchange_positions() → lista vazia?
        ├──► query_exchange_orders()    → lista vazia?
        ├──► calculate_exposure()      → valor == 0?
        ├──► calculate_total_risk()    → valor == 0?
        └──► exchange_confirmation()   → ACK recebido?
                │
          ┌─────┴──────┐
          │            │
         SIM           NÃO
          │            │
          │       ┌────▼──────────────────────────────┐
          │       │ retries < MAX_RETRIES?             │
          │       │   SIM → aguarda RETRY_INTERVAL     │
          │       │   NÃO → emite ALERT + retorna      │
          │       │         WAITING_POSITIONS_CLOSE     │
          │       └────────────────────────────────────┘
          │
          ▼
     Estado: SAFE_TO_SWITCH
```

---

## 4. Diagramas Lógicos

### 4.1 Diagrama de Sequência — Troca Bem-Sucedida

```
Usuário     StrategyManager    ExchangeAPI     AuditLogger    Database
   │               │                │               │             │
   │──activate(B)──►               │               │             │
   │               │──acquire_lock()               │             │
   │               │──block_entries(A)             │             │
   │               │──setState(TRANSITION)         │             │
   │               │               │               │             │
   │               │──close_positions(A)──────────►│             │
   │               │◄──positions_closed()──────────│             │
   │               │──cancel_orders(A)────────────►│             │
   │               │◄──orders_cancelled()──────────│             │
   │               │──stop_ws_workers(A)           │             │
   │               │──setState(CLOSING_POSITIONS)  │             │
   │               │               │               │             │
   │               │──verify_zero_risk()──────────►│             │
   │               │◄──risk_confirmed_zero()────────│             │
   │               │──setState(SAFE_TO_SWITCH)     │             │
   │               │               │               │             │
   │               │──clear_context(A)             │             │
   │               │               │               │             │
   │               │──init_strategy(B)             │             │
   │               │──setState(ACTIVATING)         │             │
   │               │               │               │             │
   │               │────────────────────────────────│──log(B_activated)
   │               │               │               │──────────────►│
   │               │──setState(ACTIVE)             │             │
   │               │──release_lock()               │             │
   │◄──success(B)──│               │               │             │
```

### 4.2 Diagrama de Sequência — Troca Recusada (Risco Ativo)

```
Usuário     StrategyManager    ExchangeAPI
   │               │                │
   │──activate(B)──►               │
   │               │──acquire_lock()
   │               │──check_risk()─────────────────►│
   │               │◄──risk: POSITIONS_OPEN─────────│
   │               │
   │               │  risco ativo → recusar troca
   │               │
   │◄──status: WAITING_POSITIONS_CLOSE
   │               │──release_lock()
```

### 4.3 Diagrama de Componentes — Anti Rapid Switching

```
┌──────────────────────────────────────────────────────────────┐
│                    ANTI-RAPID-SWITCHING GATE                  │
│                                                              │
│  Requisição de ativação                                      │
│        │                                                     │
│        ▼                                                     │
│  ┌────────────────────────────────────────────┐              │
│  │ last_switch_time + MIN_SWITCH_INTERVAL      │              │
│  │         > now()?                           │              │
│  └────────────────────────────────────────────┘              │
│        │                    │                                │
│       SIM                  NÃO                               │
│        │                    │                                │
│        ▼                    ▼                                │
│  REJECT (429)          ┌──────────────────────────┐          │
│  "TOO_SOON"            │ has_active_risk()?        │          │
│                        └──────────────────────────┘          │
│                               │            │                 │
│                              SIM          NÃO                │
│                               │            │                 │
│                               ▼            ▼                 │
│                        REJECT (409)   PROCEED TO SWITCH      │
│                        "WAITING_      PIPELINE               │
│                         POSITIONS_                           │
│                         CLOSE"                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Regras de Segurança

### 5.1 Single Strategy Enforcement

| Regra | Mecanismo | Nível de Garantia |
|---|---|---|
| Uma estratégia ativa por vez | Global Mutex / Redis Lock | Sistema |
| Ativação requer lock | `acquire_lock()` bloqueante | Sistema |
| Lock libera apenas após ativação ou erro | Finally block garantido | Código |
| Estado persistido em DB | Escritas atômicas | Dados |

### 5.2 Atomicidade da Troca

A operação de troca deve ser tratada como uma **transação lógica** com semântica de tudo-ou-nada:

```
BEGIN_SWITCH_TRANSACTION
  ├── LOCK (exclusivo, timeout configurável)
  ├── BLOCK_ENTRIES
  ├── CLOSE_POSITIONS       ─┐
  ├── CANCEL_ORDERS          ├── grupo atômico:
  ├── STOP_WORKERS           │   qualquer falha aqui
  ├── VERIFY_ZERO_RISK       │   aciona ROLLBACK
  ├── CLEAR_CONTEXT         ─┘   ou ALERT_STUCK
  ├── ACTIVATE_NEW
  └── COMMIT (UNLOCK + LOG + DB_UPDATE)
```

**Em caso de falha irrecuperável:**
- Manter a estratégia anterior em estado `IDLE` (sem risco aberto)
- Nunca ativar a nova estratégia com posições remanescentes
- Emitir alerta crítico para o operador
- Aguardar intervenção manual se necessário

### 5.3 Prevenção de Race Conditions

```
PROBLEMA:           Dois requests simultâneos de ativação
SOLUÇÃO:            Lock global com semântica de exclusão mútua

PROBLEMA:           Verificação de risco retorna falso negativo
SOLUÇÃO:            Dupla verificação: cache interno + exchange API

PROBLEMA:           Worker não finaliza dentro do timeout
SOLUÇÃO:            SIGTERM → aguarda 30s → SIGKILL → log FORCED_KILL

PROBLEMA:           Falha de rede durante close_positions
SOLUÇÃO:            Retry com backoff exponencial + circuit breaker

PROBLEMA:           Estado inconsistente após crash
SOLUÇÃO:            Recovery procedure no startup: verificar DB state
```

### 5.4 Configurações de Segurança Recomendadas

```python
SECURITY_CONFIG = {
    # Tempo mínimo entre trocas de estratégia (segundos)
    "MIN_SWITCH_INTERVAL_SECONDS": 60,

    # Timeout para encerrar workers gracefully (segundos)
    "WORKER_GRACEFUL_SHUTDOWN_SECONDS": 30,

    # Máximo de tentativas de verificação de risco zero
    "MAX_RISK_CHECK_RETRIES": 20,

    # Intervalo entre verificações de risco (segundos)
    "RISK_CHECK_INTERVAL_SECONDS": 3,

    # Timeout total do processo de troca (segundos)
    "SWITCH_TOTAL_TIMEOUT_SECONDS": 300,

    # Timeout para aquisição de lock (segundos)
    "LOCK_ACQUIRE_TIMEOUT_SECONDS": 10,

    # TTL do lock no Redis (segundos) — evita lock morto
    "LOCK_TTL_SECONDS": 360,
}
```

---

## 6. Pseudocódigo do Strategy Manager

### 6.1 Classe Principal

```python
class StrategyManager:
    """
    Gerenciador central de estratégias.
    Garante Single Active Strategy Mode com troca segura e atômica.
    """

    def __init__(self, exchange_client, db, audit_logger, config):
        self.exchange       = exchange_client
        self.db             = db
        self.logger         = audit_logger
        self.config         = config
        self.lock           = GlobalLock("strategy_manager", ttl=config.LOCK_TTL_SECONDS)
        self.state          = self._restore_state_from_db()
        self.active_strategy = self._restore_active_strategy()
        self.last_switch_ts = self._restore_last_switch_ts()

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL: Ativar estratégia (nova ou primeira)
    # ------------------------------------------------------------------
    def activate_strategy(self, new_strategy_id: str, requested_by: str) -> ActivationResult:

        # [GATE 1] Anti-rapid-switching
        elapsed = now() - self.last_switch_ts
        if elapsed < self.config.MIN_SWITCH_INTERVAL_SECONDS:
            return ActivationResult.REJECTED("TOO_SOON", wait=self.config.MIN_SWITCH_INTERVAL_SECONDS - elapsed)

        # [GATE 2] Já é a estratégia ativa
        if self.active_strategy == new_strategy_id and self.state == State.ACTIVE:
            return ActivationResult.REJECTED("ALREADY_ACTIVE")

        # [GATE 3] Adquirir lock global (bloqueante com timeout)
        acquired = self.lock.acquire(timeout=self.config.LOCK_ACQUIRE_TIMEOUT_SECONDS)
        if not acquired:
            return ActivationResult.REJECTED("LOCK_UNAVAILABLE")

        try:
            if self.state == State.IDLE:
                return self._activate_first_strategy(new_strategy_id, requested_by)
            elif self.state == State.ACTIVE:
                return self._switch_strategy(new_strategy_id, requested_by)
            else:
                return ActivationResult.REJECTED("SYSTEM_IN_TRANSITION", state=self.state)

        except Exception as e:
            self.logger.critical("SWITCH_UNHANDLED_ERROR", strategy=new_strategy_id, error=str(e))
            self._emergency_safe_state()
            raise

        finally:
            self.lock.release()

    # ------------------------------------------------------------------
    # Ativar primeira estratégia (estado IDLE)
    # ------------------------------------------------------------------
    def _activate_first_strategy(self, strategy_id: str, requested_by: str) -> ActivationResult:
        self._set_state(State.ACTIVATING_NEW_STRATEGY)

        try:
            self._do_activate(strategy_id)
            self._set_state(State.ACTIVE)
            self.active_strategy = strategy_id
            self.last_switch_ts  = now()

            self.logger.info("STRATEGY_ACTIVATED", {
                "strategy_id":  strategy_id,
                "requested_by": requested_by,
                "previous":     None,
                "timestamp":    now_iso(),
            })

            return ActivationResult.SUCCESS(strategy_id)

        except Exception as e:
            self._set_state(State.IDLE)
            self.logger.error("ACTIVATION_FAILED", strategy=strategy_id, error=str(e))
            raise

    # ------------------------------------------------------------------
    # Trocar estratégia (estado ACTIVE → [pipeline] → ACTIVE)
    # ------------------------------------------------------------------
    def _switch_strategy(self, new_strategy_id: str, requested_by: str) -> ActivationResult:
        previous_strategy = self.active_strategy

        # ETAPA 1 — BLOQUEIO
        self._set_state(State.TRANSITION_STATE)
        self._block_new_entries(previous_strategy)
        self.logger.info("SWITCH_INITIATED", {
            "from":         previous_strategy,
            "to":           new_strategy_id,
            "requested_by": requested_by,
            "timestamp":    now_iso(),
        })

        # ETAPA 2 — ENCERRAMENTO
        self._set_state(State.CLOSING_POSITIONS)
        self._close_all_positions(previous_strategy)
        self._cancel_all_orders(previous_strategy)
        self._terminate_websockets(previous_strategy)
        self._stop_timers_and_workers(previous_strategy)

        # ETAPA 3 — VERIFICAÇÃO DE RISCO ZERO
        zero_risk = self._verify_zero_risk(previous_strategy)
        if not zero_risk:
            self.logger.warning("SWITCH_ABORTED_RISK_ACTIVE", strategy=previous_strategy)
            self._set_state(State.IDLE)  # posições já foram fechadas; IDLE é seguro
            return ActivationResult.REJECTED("WAITING_POSITIONS_CLOSE")

        self._set_state(State.SAFE_TO_SWITCH)
        self.logger.info("RISK_ZERO_CONFIRMED", strategy=previous_strategy)

        # ETAPA 4 — LIMPEZA DE CONTEXTO
        self._clear_strategy_context(previous_strategy)

        # ETAPA 5 — ATIVAÇÃO SEGURA
        self._set_state(State.ACTIVATING_NEW_STRATEGY)
        try:
            self._do_activate(new_strategy_id)
            self._set_state(State.ACTIVE)
            self.active_strategy = new_strategy_id
            self.last_switch_ts  = now()

            self.logger.info("STRATEGY_SWITCHED", {
                "from":         previous_strategy,
                "to":           new_strategy_id,
                "requested_by": requested_by,
                "timestamp":    now_iso(),
            })

            return ActivationResult.SUCCESS(new_strategy_id)

        except Exception as e:
            self._set_state(State.IDLE)
            self.logger.error("NEW_STRATEGY_ACTIVATION_FAILED", {
                "strategy": new_strategy_id,
                "error":    str(e),
            })
            raise

    # ------------------------------------------------------------------
    # Encerramento de posições com retry
    # ------------------------------------------------------------------
    def _close_all_positions(self, strategy_id: str):
        positions = self.exchange.get_open_positions(strategy_id)

        for position in positions:
            side      = "SELL" if position.direction == "LONG" else "BUY"
            max_tries = self.config.MAX_RISK_CHECK_RETRIES

            for attempt in range(1, max_tries + 1):
                try:
                    order = self.exchange.market_order(
                        symbol   = position.symbol,
                        side     = side,
                        quantity = position.quantity,
                        reduce_only = True,
                    )
                    self.logger.info("POSITION_CLOSED", {
                        "position_id": position.id,
                        "order_id":    order.id,
                        "pnl":         position.unrealized_pnl,
                    })
                    break
                except ExchangeError as e:
                    if attempt == max_tries:
                        self.logger.critical("POSITION_CLOSE_FAILED", position=position.id, error=str(e))
                        raise
                    sleep(backoff(attempt))

    # ------------------------------------------------------------------
    # Cancelamento de ordens com retry
    # ------------------------------------------------------------------
    def _cancel_all_orders(self, strategy_id: str):
        orders = self.exchange.get_open_orders(strategy_id)

        for order in orders:
            for attempt in range(1, self.config.MAX_RISK_CHECK_RETRIES + 1):
                try:
                    self.exchange.cancel_order(order.id)
                    self.logger.info("ORDER_CANCELLED", order_id=order.id)
                    break
                except ExchangeError as e:
                    if attempt == self.config.MAX_RISK_CHECK_RETRIES:
                        self.logger.critical("ORDER_CANCEL_FAILED", order=order.id, error=str(e))
                        raise
                    sleep(backoff(attempt))

    # ------------------------------------------------------------------
    # Verificação de risco zero (polling com retries)
    # ------------------------------------------------------------------
    def _verify_zero_risk(self, strategy_id: str) -> bool:
        for attempt in range(self.config.MAX_RISK_CHECK_RETRIES):
            positions = self.exchange.get_open_positions(strategy_id)
            orders    = self.exchange.get_open_orders(strategy_id)
            exposure  = self.exchange.get_exposure(strategy_id)

            if len(positions) == 0 and len(orders) == 0 and exposure == 0:
                return True

            self.logger.debug("RISK_CHECK_PENDING", {
                "attempt":          attempt + 1,
                "open_positions":   len(positions),
                "open_orders":      len(orders),
                "exposure":         exposure,
            })

            sleep(self.config.RISK_CHECK_INTERVAL_SECONDS)

        return False

    # ------------------------------------------------------------------
    # Limpeza de contexto da estratégia anterior
    # ------------------------------------------------------------------
    def _clear_strategy_context(self, strategy_id: str):
        # Remove dados em memória
        self.active_strategy_instance = None

        # Limpa caches relacionados
        cache.delete_pattern(f"strategy:{strategy_id}:*")

        # Reseta variáveis de execução
        self.db.execute(
            "UPDATE strategies SET runtime_state = NULL WHERE id = ?",
            [strategy_id]
        )

        self.logger.info("CONTEXT_CLEARED", strategy=strategy_id)

    # ------------------------------------------------------------------
    # Parada de workers com graceful shutdown
    # ------------------------------------------------------------------
    def _stop_timers_and_workers(self, strategy_id: str):
        workers = self.active_workers.get(strategy_id, [])

        for worker in workers:
            worker.request_stop()

        deadline = now() + self.config.WORKER_GRACEFUL_SHUTDOWN_SECONDS

        for worker in workers:
            remaining = deadline - now()
            if remaining > 0:
                worker.join(timeout=remaining)
            if worker.is_alive():
                worker.force_kill()
                self.logger.warning("WORKER_FORCE_KILLED", worker=worker.name)

        self.active_workers.pop(strategy_id, None)
        self.logger.info("ALL_WORKERS_STOPPED", strategy=strategy_id)

    # ------------------------------------------------------------------
    # Ativação efetiva da estratégia
    # ------------------------------------------------------------------
    def _do_activate(self, strategy_id: str):
        strategy_class  = StrategyRegistry.get(strategy_id)
        strategy_config = self.db.get_strategy_config(strategy_id)
        instance        = strategy_class(self.exchange, strategy_config)

        instance.start()

        self.active_strategy_instance = instance
        self.active_workers[strategy_id] = instance.get_workers()
        self.db.update_active_strategy(strategy_id)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    def _set_state(self, new_state: State):
        old_state   = self.state
        self.state  = new_state
        self.db.update_system_state(new_state)
        self.logger.debug("STATE_TRANSITION", {"from": old_state, "to": new_state})

    def _block_new_entries(self, strategy_id: str):
        if self.active_strategy_instance:
            self.active_strategy_instance.block_entries()

    def _terminate_websockets(self, strategy_id: str):
        if self.active_strategy_instance:
            self.active_strategy_instance.close_connections()

    def _emergency_safe_state(self):
        """Coloca o sistema em estado seguro após erro não tratado."""
        self._set_state(State.IDLE)
        self.active_strategy = None

    def _restore_state_from_db(self) -> State:
        """Recupera estado persistido para sobreviver a restarts."""
        saved = self.db.get_system_state()
        # Se o sistema reiniciou no meio de uma transição, vai para IDLE
        if saved in (State.TRANSITION_STATE, State.CLOSING_POSITIONS, State.ACTIVATING_NEW_STRATEGY):
            return State.IDLE
        return saved or State.IDLE
```

### 6.2 Enum de Estados

```python
from enum import Enum

class State(str, Enum):
    IDLE                    = "IDLE"
    ACTIVE                  = "ACTIVE"
    TRANSITION_STATE        = "TRANSITION_STATE"
    CLOSING_POSITIONS       = "CLOSING_POSITIONS"
    SAFE_TO_SWITCH          = "SAFE_TO_SWITCH"
    ACTIVATING_NEW_STRATEGY = "ACTIVATING_NEW_STRATEGY"
```

### 6.3 Resultado de Ativação

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ActivationResult:
    success:    bool
    strategy:   Optional[str]
    status:     str
    detail:     Optional[str] = None
    wait_secs:  Optional[int] = None

    @classmethod
    def SUCCESS(cls, strategy_id: str) -> "ActivationResult":
        return cls(success=True, strategy=strategy_id, status="ACTIVATED")

    @classmethod
    def REJECTED(cls, reason: str, **kwargs) -> "ActivationResult":
        return cls(success=False, strategy=None, status=reason, **kwargs)
```

---

## 7. API Interna do Strategy Manager

### 7.1 Endpoints REST Sugeridos

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/strategies/{id}/activate` | Solicitar ativação de estratégia |
| `POST` | `/api/strategies/deactivate` | Parar estratégia ativa (ir para IDLE) |
| `GET` | `/api/strategies/active` | Retornar estratégia ativa atual |
| `GET` | `/api/strategies/state` | Retornar estado do sistema |
| `GET` | `/api/strategies/switch-status` | Status de troca em andamento |

### 7.2 Schemas de Resposta

```json
// POST /api/strategies/{id}/activate — Sucesso
{
  "success": true,
  "status": "ACTIVATED",
  "strategy_id": "grid_usdt_v2",
  "activated_at": "2026-02-27T14:32:00Z"
}

// POST /api/strategies/{id}/activate — Risco Ativo
{
  "success": false,
  "status": "WAITING_POSITIONS_CLOSE",
  "open_positions": 3,
  "open_orders": 7,
  "retry_after_seconds": 15
}

// POST /api/strategies/{id}/activate — Muito Cedo
{
  "success": false,
  "status": "TOO_SOON",
  "wait_seconds": 43
}

// GET /api/strategies/state
{
  "system_state": "ACTIVE",
  "active_strategy": "grid_usdt_v2",
  "last_switch": "2026-02-27T14:32:00Z",
  "uptime_seconds": 3672
}
```

---

## 8. Logs e Auditoria

### 8.1 Eventos Obrigatórios de Log

| Evento | Momento | Nível | Campos Obrigatórios |
|---|---|---|---|
| `STRATEGY_ACTIVATED` | Ativação bem-sucedida | INFO | strategy_id, requested_by, previous, timestamp |
| `STRATEGY_DEACTIVATED` | Desativação | INFO | strategy_id, reason, timestamp |
| `SWITCH_INITIATED` | Início da troca | INFO | from, to, requested_by, timestamp |
| `POSITION_CLOSED` | Posição encerrada | INFO | position_id, order_id, pnl |
| `ORDER_CANCELLED` | Ordem cancelada | INFO | order_id |
| `RISK_ZERO_CONFIRMED` | Risco = 0 verificado | INFO | strategy_id, timestamp |
| `CONTEXT_CLEARED` | Contexto limpo | INFO | strategy_id |
| `STRATEGY_SWITCHED` | Troca concluída | INFO | from, to, requested_by, timestamp |
| `STATE_TRANSITION` | Mudança de estado | DEBUG | from, to |
| `SWITCH_ABORTED_RISK_ACTIVE` | Troca abortada | WARNING | strategy_id |
| `WORKER_FORCE_KILLED` | Worker morto forçado | WARNING | worker_name |
| `POSITION_CLOSE_FAILED` | Falha crítica | CRITICAL | position_id, error |
| `SWITCH_UNHANDLED_ERROR` | Erro não tratado | CRITICAL | strategy_id, error |

### 8.2 Formato de Log Estruturado

```json
{
  "timestamp":   "2026-02-27T14:32:00.123Z",
  "level":       "INFO",
  "event":       "STRATEGY_SWITCHED",
  "user_id":     "usr_abc123",
  "session_id":  "sess_xyz789",
  "data": {
    "from":         "scalper_btc_v1",
    "to":           "grid_usdt_v2",
    "requested_by": "usr_abc123",
    "duration_ms":  4821
  },
  "system_state": "ACTIVE",
  "host":         "trading-node-01"
}
```

### 8.3 Retenção e Imutabilidade

- Logs de auditoria devem ser **append-only** (nunca editáveis)
- Retenção mínima recomendada: **90 dias**
- Armazenar em tabela separada com índice em `event` e `timestamp`
- Considerar exportação para sistema SIEM ou S3 para compliance

---

## 9. Tratamento de Erros e Falhas

### 9.1 Matriz de Falhas

| Cenário de Falha | Ação do Sistema | Estado Final |
|---|---|---|
| Falha ao fechar posição (rede) | Retry com backoff exponencial (N tentativas) | CLOSING_POSITIONS → retenta |
| Timeout total excedido | Alerta crítico + aguarda intervenção | CLOSING_POSITIONS (stuck) |
| Falha ao iniciar nova estratégia | Rollback para IDLE + log | IDLE |
| Worker não finaliza no timeout | Force kill + log WARNING | Continua pipeline |
| Lock não adquirido | Rejeitar request + log | Estado inalterado |
| Crash/restart durante troca | Restaurar para IDLE via DB recovery | IDLE |

### 9.2 Recovery Procedure no Startup

```python
def startup_recovery(self):
    """
    Executar sempre que o StrategyManager iniciar.
    Garante estado consistente após crashes.
    """
    state = self.db.get_system_state()

    if state in (State.TRANSITION_STATE,
                 State.CLOSING_POSITIONS,
                 State.ACTIVATING_NEW_STRATEGY):

        # Sistema reiniciou no meio de uma troca
        self.logger.warning("STARTUP_RECOVERY", {"state_found": state})

        # Verificar se ainda há risco ativo
        has_risk = self._check_any_active_risk()

        if has_risk:
            # Tentar fechar posições remanescentes
            self._close_all_positions(self.active_strategy)

        # Ir para IDLE independentemente
        self._set_state(State.IDLE)
        self.active_strategy = None
        self.db.clear_active_strategy()

        self.logger.info("STARTUP_RECOVERY_COMPLETE", state="IDLE")
```

---

## 10. Boas Práticas de Implementação

### 10.1 Lock Global

- Usar **Redis SETNX** com TTL para lock distribuído em ambientes multi-instância
- Nunca usar variável de instância Python como único mecanismo de lock
- Implementar renovação automática de lock (lock heartbeat) para operações longas
- TTL do lock deve ser maior que o timeout total da troca

### 10.2 Idempotência

- Operações de cancel e close devem ser idempotentes
- Verificar se posição/ordem já está fechada antes de emitir novo comando
- Tratar respostas `ORDER_NOT_FOUND` como sucesso (já foi cancelada)

### 10.3 Separação de Contexto

- Cada estratégia deve operar em namespace isolado no cache
- Variáveis de estado nunca devem ser compartilhadas entre estratégias
- Usar prefixo `strategy:{id}:` em todas as chaves de cache e fila

### 10.4 Observabilidade

- Expor métricas via endpoint `/metrics` (Prometheus-compatible):
  - `strategy_switches_total` (counter)
  - `strategy_active_duration_seconds` (gauge)
  - `switch_duration_seconds` (histogram)
  - `open_positions_at_switch` (histogram)
- Configurar alertas para:
  - Estado `CLOSING_POSITIONS` com duração > 120s
  - Evento `POSITION_CLOSE_FAILED`
  - Evento `SWITCH_UNHANDLED_ERROR`

### 10.5 Testes Recomendados

| Tipo de Teste | Cenário |
|---|---|
| Unitário | Transições válidas e inválidas da FSM |
| Unitário | Rejeição de dupla ativação simultânea |
| Integração | Troca completa com mock de exchange |
| Integração | Recovery após restart no meio de troca |
| Carga | 100 requests de ativação concorrentes (apenas 1 deve passar) |
| Caos | Kill do processo durante `CLOSING_POSITIONS` |

---

## 11. Checklist de Implementação

### Fase 1 — Fundação

- [ ] Implementar enum `State` com todos os 6 estados
- [ ] Implementar `GlobalLock` com Redis SETNX + TTL
- [ ] Implementar `_set_state()` com persistência em DB
- [ ] Implementar `startup_recovery()` para reinicializações

### Fase 2 — Pipeline de Encerramento

- [ ] Implementar `_block_new_entries()` na interface da estratégia
- [ ] Implementar `_close_all_positions()` com retry e backoff
- [ ] Implementar `_cancel_all_orders()` com retry e backoff
- [ ] Implementar `_terminate_websockets()`
- [ ] Implementar `_stop_timers_and_workers()` com graceful shutdown

### Fase 3 — Verificação e Ativação

- [ ] Implementar `_verify_zero_risk()` com polling e dupla verificação
- [ ] Implementar `_clear_strategy_context()`
- [ ] Implementar `_do_activate()` com registro de workers
- [ ] Implementar `ActivationResult` com todos os códigos de status

### Fase 4 — Segurança e Observabilidade

- [ ] Implementar Anti-Rapid-Switching gate
- [ ] Implementar `AuditLogger` com todos os eventos obrigatórios
- [ ] Configurar métricas Prometheus
- [ ] Configurar alertas críticos
- [ ] Implementar endpoint `GET /api/strategies/state`

### Fase 5 — Testes e Validação

- [ ] Testes unitários da FSM (cobertura > 90%)
- [ ] Testes de integração com mock de exchange
- [ ] Teste de concorrência (100 requests simultâneos)
- [ ] Teste de recovery após crash
- [ ] Revisão de segurança: nenhuma double-activation possível

---

*Documentação gerada para uso interno — Crypto Trade Hub SaaS*  
*Versão 1.0 — 2026-02-27*
