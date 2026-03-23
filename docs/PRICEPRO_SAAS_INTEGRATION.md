# PRICEPRO_MONEY-EA — Integração ao SaaS Strategy Manager
## Documentação Técnica de Adaptação — 10 Etapas

**Sistema:** Crypto Trade Hub — Automated Trading SaaS  
**Componente:** Strategy Manager (Single Active Strategy Mode)  
**Módulo:** PRICEPRO_MONEY-EA → SaaS Strategy Module  
**Versão do Documento:** 1.0  
**Data:** 2026-02-27  
**Classificação:** Interno / Engenharia de Estratégias  

---

## Sumário

| # | Documento | Escopo |
|---|---|---|
| [DOC-STRAT-01](#doc-strat-01--padronização-da-estratégia) | Padronização da Estratégia | Converter EA em Strategy Module SaaS-compatível |
| [DOC-STRAT-02](#doc-strat-02--controle-externo-de-ativação) | Controle Externo de Ativação | Remover dependência do input local e aceitar comandos remotos |
| [DOC-STRAT-03](#doc-strat-03--modo-safe-shutdown) | Modo SAFE SHUTDOWN | Implementar encerramento seguro obrigatório |
| [DOC-STRAT-04](#doc-strat-04--integração-com-strategy-manager) | Integração com Strategy Manager | Responder corretamente a cada estado do FSM |
| [DOC-STRAT-05](#doc-strat-05--sincronização-de-estado) | Sincronização de Estado | Reportar posições, lucro e drawdown ao backend |
| [DOC-STRAT-06](#doc-strat-06--isolamento-por-magic-number) | Isolamento por Magic Number | Garantir controle exclusivo das próprias posições |
| [DOC-STRAT-07](#doc-strat-07--bloqueio-anti-rapid-switch) | Bloqueio Anti-Rapid-Switch | Bloquear reabertura durante troca de estratégia |
| [DOC-STRAT-08](#doc-strat-08--integração-com-risk-manager) | Integração com Risk Manager | Respeitar Kill Switch, Daily Loss e Emergency Stop |
| [DOC-STRAT-09](#doc-strat-09--handshake-de-ativação) | Handshake de Ativação | Protocolo correto StrategyManager → EA Ready → Trading Enabled |
| [DOC-STRAT-10](#doc-strat-10--padrão-universal-de-estratégias) | Padrão Universal de Estratégias | Template reutilizável para futuros robôs |

---

---

## DOC-STRAT-01 — Padronização da Estratégia

### Objetivo

Transformar o PRICEPRO_MONEY-EA de um Expert Advisor autônomo em um **Strategy Module** controlado pelo SaaS, obedecendo ao contrato de interface definido pela camada `strategy_base.py` do sistema.

---

### 1.1 Problema com EA Autônomo

O PRICEPRO_MONEY-EA, em sua forma original, opera como uma unidade independente:
- Decisão de entrada controlada apenas pelo input `AtivarEA = true/false`
- Sem comunicação com o backend sobre estado operacional
- Sem protocolo de encerramento seguro
- Sem awareness de que outra estratégia pode estar ativa em paralelo

Isso cria o risco de **dois robôs simultâneos** abrindo posições conflitantes, e impossibilita a troca controlada de estratégia.

---

### 1.2 Estrutura Exigida pelo SaaS

Todo módulo de estratégia registrado no SaaS deve expor os seguintes contratos:

```
StrategyModule
├── strategy_id         → identificador único (ex: "pricepro_money_v1")
├── magic_number        → ID numérico exclusivo para controle de posições no MT5
├── on_tick()           → lógica de entrada/saída (só executa quando PERMITTED = true)
├── safe_shutdown()     → encerramento seguro (fechamento + confirmação zero-risco)
├── get_state_report()  → snapshot: posições abertas, drawdown, lucro, status
├── on_command()        → recebe comandos externos: ACTIVATE, DEACTIVATE, EMERGENCY_STOP
└── heartbeat()         → pulso periódico confirmando que o módulo está vivo
```

---

### 1.3 Mapeamento do PRICEPRO para o Contrato

| Elemento Original | Adaptação Necessária |
|---|---|
| `input bool AtivarEA` | Substituído por `bool PERMITTED` controlado externamente via Named Pipe ou arquivo de controle |
| Lógica de entrada em `OnTick()` | Envolver em `if (!PERMITTED) return;` |
| Sem encerramento programado | Implementar `SafeShutdown()` completo |
| Sem reporte de estado | Implementar `WriteStateReport()` periódico |
| Magic Number fixo ou ausente | Definir `MAGIC_NUMBER = 20240001` exclusivo por estratégia |
| Sem handshake de início | Implementar protocolo de registro no backend antes de operar |

---

### 1.4 Representação no Backend Python

O backend mapeia cada estratégia como um documento MongoDB. O PRICEPRO deve ter um documento de registro com as seguintes fields obrigatórias:

```python
# Documento de registro do PRICEPRO_MONEY-EA no MongoDB
{
    "_id": ObjectId("..."),
    "user_id": "<user_id>",
    "strategy_id": "pricepro_money_v1",
    "display_name": "PRICEPRO MONEY",
    "magic_number": 20240001,
    "is_running": False,
    "is_active_slot": False,
    "status": "stopped",          # stopped | running | error | shutdown
    "runtime_state": None,        # preenchido durante execução
    "last_started": None,
    "last_heartbeat": None,
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}
```

Esse documento é o que o `StrategyManager.activate_strategy()` consulta via `_StateStore.bot_exists()` e atualiza via `mark_bot_running()` / `mark_bot_stopped()`.

---

### 1.5 Checklist DOC-STRAT-01

- [ ] Definir `strategy_id` único para o PRICEPRO (`"pricepro_money_v1"`)
- [ ] Definir `magic_number` exclusivo e imutável
- [ ] Registrar documento no MongoDB com campos obrigatórios
- [ ] Remover autonomia de ativação do EA (input `AtivarEA` não pode ser a única guarda)
- [ ] Implementar os 6 contratos do módulo de estratégia

---

---

## DOC-STRAT-02 — Controle Externo de Ativação

### Objetivo

Substituir o input local `AtivarEA = true/false` por um mecanismo de controle remoto que permita ao backend Python ativar e desativar o EA sem intervenção humana na plataforma MT5.

---

### 2.1 Mecanismos Disponíveis

O MT5 não expõe uma API de entrada de comandos externos por padrão. O controle remoto deve ser implementado via um dos três mecanismos abaixo:

| Mecanismo | Latência | Complexidade | Uso Recomendado |
|---|---|---|---|
| **Arquivo de Controle** (JSON em disco) | Baixa (~200ms) | Simples | Ambiente local, desenvolvimento |
| **Named Pipe (Windows)** | Muito baixa (~10ms) | Média | Produção, mesmo servidor |
| **WebSocket / HTTP polling** | Variável | Alta | Produção distribuída |

Para este sistema (backend Python + MT5 no mesmo host ou LAN), o mecanismo recomendado é o **arquivo de controle JSON**.

---

### 2.2 Estrutura do Arquivo de Controle

O backend grava um arquivo JSON em um caminho acordado. O EA lê esse arquivo a cada tick.

**Caminho no backend:**
```
C:\MT5_Control\<user_id>\pricepro_money_v1\control.json
```

**Estrutura do arquivo:**
```json
{
    "command": "ACTIVATE",
    "permitted": true,
    "kill_switch": false,
    "emergency_stop": false,
    "risk_limit_daily_loss": 500.00,
    "manager_state": "ACTIVE",
    "issued_at": "2026-02-27T14:00:00Z",
    "issued_by": "strategy_manager",
    "sequence": 42
}
```

**Campos obrigatórios:**

| Campo | Tipo | Descrição |
|---|---|---|
| `command` | string | `ACTIVATE`, `DEACTIVATE`, `EMERGENCY_STOP`, `SAFE_SHUTDOWN` |
| `permitted` | bool | Se `true`, o EA pode abrir novas entradas |
| `kill_switch` | bool | Se `true`, fecha tudo imediatamente, nenhuma nova ordem |
| `manager_state` | string | Estado atual do Strategy Manager |
| `sequence` | int | Número de sequência para detectar arquivo desatualizado |

---

### 2.3 Implementação MQL5 — Leitura do Arquivo de Controle

```mql5
// ─── Variáveis globais de controle ───────────────────────────────────────────
string   CONTROL_FILE_PATH = "C:\\MT5_Control\\" + USER_ID + "\\pricepro_money_v1\\control.json";
bool     g_permitted       = false;   // permissão para operar
bool     g_kill_switch     = false;   // kill switch global
string   g_manager_state   = "IDLE";  // estado do Strategy Manager
int      g_last_sequence   = -1;      // evita reprocessar arquivo antigo
datetime g_control_last_read = 0;

// ─── Leitura do arquivo de controle (chamada em OnTick) ──────────────────────
bool ReadControlFile()
{
    // Lê no máximo uma vez por segundo para evitar I/O excessivo
    if (TimeCurrent() - g_control_last_read < 1)
        return true;

    g_control_last_read = TimeCurrent();

    int handle = FileOpen(CONTROL_FILE_PATH, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if (handle == INVALID_HANDLE)
    {
        Print("[PRICEPRO] AVISO: Arquivo de controle não encontrado. Operação bloqueada.");
        g_permitted   = false;
        g_kill_switch = true;
        return false;
    }

    string content = "";
    while (!FileIsEnding(handle))
        content += FileReadString(handle);
    FileClose(handle);

    // Parse simples dos campos críticos
    // Em produção, usar biblioteca JSON como JAson.mqh
    int seq = (int)ParseJSONInt(content, "sequence");
    if (seq <= g_last_sequence)
    {
        Print("[PRICEPRO] Arquivo de controle não atualizado (seq=" + IntegerToString(seq) + "). Mantendo estado anterior.");
        return true;
    }

    g_last_sequence   = seq;
    g_permitted       = ParseJSONBool(content, "permitted");
    g_kill_switch     = ParseJSONBool(content, "kill_switch");
    g_manager_state   = ParseJSONString(content, "manager_state");

    Print("[PRICEPRO] Controle atualizado | permitted=" + (string)g_permitted
          + " | kill_switch=" + (string)g_kill_switch
          + " | manager_state=" + g_manager_state
          + " | seq=" + IntegerToString(seq));

    return true;
}

// ─── Guarda principal em OnTick ───────────────────────────────────────────────
void OnTick()
{
    ReadControlFile();

    // Primeira guarda: kill switch ou não permitido
    if (g_kill_switch || !g_permitted)
        return;

    // Segunda guarda: manager não está em estado ACTIVE
    if (g_manager_state != "ACTIVE")
        return;

    // ─── Lógica original do PRICEPRO a partir daqui ──────────────────────────
    ExecuteStrategy();
}
```

---

### 2.4 Escrita do Arquivo pelo Backend Python

```python
# backend/app/services/ea_controller.py

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class EAController:
    """
    Grava o arquivo de controle que o EA PRICEPRO lê via FileOpen no MT5.
    """

    BASE_PATH = Path("C:/MT5_Control")

    def __init__(self, user_id: str, strategy_id: str):
        self.user_id     = user_id
        self.strategy_id = strategy_id
        self._seq        = 0
        self._path       = self.BASE_PATH / user_id / strategy_id / "control.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, payload: dict):
        self._seq += 1
        payload["sequence"]  = self._seq
        payload["issued_at"] = datetime.now(timezone.utc).isoformat()
        payload["issued_by"] = "strategy_manager"
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def activate(self, manager_state: str = "ACTIVE"):
        self._write({
            "command":       "ACTIVATE",
            "permitted":     True,
            "kill_switch":   False,
            "emergency_stop": False,
            "manager_state": manager_state,
        })

    def deactivate(self, manager_state: str = "IDLE"):
        self._write({
            "command":       "DEACTIVATE",
            "permitted":     False,
            "kill_switch":   False,
            "emergency_stop": False,
            "manager_state": manager_state,
        })

    def emergency_stop(self):
        self._write({
            "command":       "EMERGENCY_STOP",
            "permitted":     False,
            "kill_switch":   True,
            "emergency_stop": True,
            "manager_state": "CLOSING_POSITIONS",
        })

    def safe_shutdown(self):
        self._write({
            "command":       "SAFE_SHUTDOWN",
            "permitted":     False,
            "kill_switch":   False,
            "emergency_stop": False,
            "manager_state": "CLOSING_POSITIONS",
        })
```

---

### 2.5 Checklist DOC-STRAT-02

- [ ] Campo `AtivarEA` mantido apenas como fallback de emergência local
- [ ] EA lê `control.json` a cada tick com debounce de 1 segundo
- [ ] Backend escreve `control.json` via `EAController` antes de mudar estado do FSM
- [ ] Arquivo ausente = operação bloqueada (fail-safe)
- [ ] Campo `sequence` impede reprocessamento de arquivo obsoleto

---

---

## DOC-STRAT-03 — Modo SAFE SHUTDOWN

### Objetivo

Implementar a função `SafeShutdown()` que garante que, quando acionada, o EA encerra toda exposição de risco antes de confirmar que o sistema pode prosseguir com a troca de estratégia.

---

### 3.1 Contrato da Função

`SafeShutdown()` deve:

1. **Desativar novas entradas** — setar `g_permitted = false` imediatamente
2. **Cancelar todas as ordens pendentes** do magic number deste EA
3. **Fechar todas as posições abertas** do magic number deste EA
4. **Confirmar risco zero** — verificar que `PositionsTotal()` retorna 0 para este magic
5. **Gravar relatório de encerramento** no arquivo de estado
6. **Retornar** `true` se risco zero confirmado, `false` se ainda há posições abertas

---

### 3.2 Implementação MQL5

```mql5
// ─── SafeShutdown — encerramento seguro obrigatório ──────────────────────────
bool SafeShutdown()
{
    Print("[PRICEPRO] SafeShutdown() iniciado — bloqueando novas entradas.");
    g_permitted = false;  // bloqueia novas entradas imediatamente

    // ── PASSO 1: Cancelar todas as ordens pendentes deste magic ──────────────
    int total_orders = OrdersTotal();
    for (int i = total_orders - 1; i >= 0; i--)
    {
        ulong ticket = OrderGetTicket(i);
        if (ticket == 0) continue;

        if (OrderGetInteger(ORDER_MAGIC) != MAGIC_NUMBER) continue;

        MqlTradeRequest  req  = {};
        MqlTradeResult   res  = {};
        req.action = TRADE_ACTION_REMOVE;
        req.order  = ticket;

        bool ok = OrderSend(req, res);
        if (!ok || res.retcode != TRADE_RETCODE_DONE)
            Print("[PRICEPRO] AVISO: Falha ao cancelar ordem #", ticket, " retcode=", res.retcode);
        else
            Print("[PRICEPRO] Ordem pendente cancelada: #", ticket);
    }

    // ── PASSO 2: Fechar todas as posições abertas deste magic ─────────────────
    int total_pos = PositionsTotal();
    for (int i = total_pos - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if (ticket == 0) continue;

        if (PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;

        string symbol = PositionGetString(POSITION_SYMBOL);
        double volume = PositionGetDouble(POSITION_VOLUME);
        ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        MqlTradeRequest  req  = {};
        MqlTradeResult   res  = {};
        req.action    = TRADE_ACTION_DEAL;
        req.position  = ticket;
        req.symbol    = symbol;
        req.volume    = volume;
        req.deviation = 20;
        req.magic     = MAGIC_NUMBER;
        req.comment   = "SAFE_SHUTDOWN";
        req.type      = (pos_type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
        req.price     = (pos_type == POSITION_TYPE_BUY)
                        ? SymbolInfoDouble(symbol, SYMBOL_BID)
                        : SymbolInfoDouble(symbol, SYMBOL_ASK);

        bool ok = OrderSend(req, res);
        if (!ok || res.retcode != TRADE_RETCODE_DONE)
            Print("[PRICEPRO] AVISO: Falha ao fechar posição #", ticket, " retcode=", res.retcode);
        else
            Print("[PRICEPRO] Posição fechada: #", ticket, " vol=", volume, " sym=", symbol);
    }

    // ── PASSO 3: Confirmar risco zero ─────────────────────────────────────────
    Sleep(500); // aguarda processamento da exchange

    int remaining = CountMyPositions();
    if (remaining > 0)
    {
        Print("[PRICEPRO] AVISO SafeShutdown: ainda há ", remaining, " posição(ões) abertas.");
        WriteStateReport("SHUTDOWN_PENDING", remaining);
        return false;
    }

    // ── PASSO 4: Confirmar encerramento completo ──────────────────────────────
    Print("[PRICEPRO] SafeShutdown concluído. Risco = ZERO.");
    WriteStateReport("SHUTDOWN_COMPLETE", 0);
    return true;
}

// ─── Contador de posições deste magic ────────────────────────────────────────
int CountMyPositions()
{
    int count = 0;
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (PositionGetTicket(i) > 0 && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
            count++;
    }
    return count;
}
```

---

### 3.3 Loop de Shutdown com Retry

Na prática, ordens de fechamento podem rejeitar por preço fora do mercado (requote). O loop com retry garante persistência:

```mql5
// Chamado pelo gerenciador interno enquanto manager_state == "CLOSING_POSITIONS"
void OnTick()
{
    ReadControlFile();

    if (g_manager_state == "CLOSING_POSITIONS" || g_manager_state == "TRANSITION_STATE")
    {
        if (CountMyPositions() > 0 || OrdersTotal() > 0)
        {
            SafeShutdown();  // tenta fechar a cada tick até limpar
        }
        else
        {
            // Posições zeradas — notificar backend
            WriteStateReport("SAFE_TO_SWITCH", 0);
        }
        return;  // não processa lógica de entrada enquanto fechando
    }

    if (!g_permitted || g_kill_switch) return;
    if (g_manager_state != "ACTIVE")  return;

    ExecuteStrategy();
}
```

---

### 3.4 Checklist DOC-STRAT-03

- [ ] `SafeShutdown()` cancela ordens separado do fechamento de posições
- [ ] Fecha posições por magic number, nunca posições de outros robôs
- [ ] Retry automático a cada tick enquanto estado for `CLOSING_POSITIONS`
- [ ] Confirma risco zero antes de gravar `SHUTDOWN_COMPLETE`
- [ ] `WriteStateReport()` atualiza arquivo de estado que o backend monitoriza

---

---

## DOC-STRAT-04 — Integração com Strategy Manager

### Objetivo

Definir como o PRICEPRO_MONEY-EA responde a cada um dos seis estados da máquina de estados do `StrategyManager`, garantindo comportamento determinístico e sem ambiguidade.

---

### 4.1 Mapeamento de Comportamentos por Estado

| Estado do Manager | O que o EA deve fazer |
|---|---|
| `IDLE` | Não operar. `g_permitted = false`. Nenhuma ordem, nenhum trade. |
| `ACTIVE` | Operar normalmente. `g_permitted = true`. Executar `ExecuteStrategy()`. |
| `TRANSITION_STATE` | Bloquear novas entradas imediatamente. Posições já abertas permanecem abertas por ora. |
| `CLOSING_POSITIONS` | Executar `SafeShutdown()` a cada tick até risco zero. |
| `SAFE_TO_SWITCH` | EA parado. Nenhuma ação. Backend controla o que vem a seguir. |
| `ACTIVATING_NEW_STRATEGY` | EA parado (se for o anterior). Novo EA aguarda confirmação via handshake. |

---

### 4.2 Diagrama de Comportamento do EA por Estado

```
Manager State          EA Behavior
──────────────         ──────────────────────────────────────────
IDLE               →   Parado. Nenhuma execução.
                            │
                       [activate()]
                            │
ACTIVE             →   ExecuteStrategy() habilitado
                            │
                       [switch() triggered]
                            │
TRANSITION_STATE   →   Bloqueia novas entradas imediatamente
                       Mantém posições abertas
                            │
                       [begin_close()]
                            │
CLOSING_POSITIONS  →   SafeShutdown() loop a cada tick
                       Cancela ordens → Fecha posições → Confirma
                            │
                       [all_closed()]
                            │
SAFE_TO_SWITCH     →   EA inativo. Risco = 0 confirmado.
                            │
                       [activate_new()]
                            │
ACTIVATING_NEW_STRATEGY →  Novo EA aguarda handshake
                            │
                       [handshake OK]
                            │
ACTIVE             →   Novo EA ExecuteStrategy() habilitado
```

---

### 4.3 Implementação MQL5 — Dispatcher de Estado

```mql5
void OnTick()
{
    ReadControlFile();  // atualiza g_manager_state

    switch (ParseManagerState(g_manager_state))
    {
        case STATE_IDLE:
            // Parado. Não faz nada.
            return;

        case STATE_ACTIVE:
            if (g_kill_switch) { SafeShutdown(); return; }
            if (!g_permitted)  return;
            ExecuteStrategy();
            break;

        case STATE_TRANSITION_STATE:
            // Bloqueia novas entradas, mantém posições
            g_permitted = false;
            // Não fecha ainda: espera CLOSING_POSITIONS
            break;

        case STATE_CLOSING_POSITIONS:
            g_permitted = false;
            if (CountMyPositions() > 0 || OrdersTotal() > 0)
                SafeShutdown();
            else
                WriteStateReport("SAFE_TO_SWITCH", 0);
            break;

        case STATE_SAFE_TO_SWITCH:
            // Nada a fazer. Backend controla.
            break;

        case STATE_ACTIVATING_NEW_STRATEGY:
            // Este EA está sendo desativado ou o novo está esperando.
            // Não operar.
            break;
    }
}

// ─── Parser de estado ─────────────────────────────────────────────────────────
enum EManagerState {
    STATE_IDLE,
    STATE_ACTIVE,
    STATE_TRANSITION_STATE,
    STATE_CLOSING_POSITIONS,
    STATE_SAFE_TO_SWITCH,
    STATE_ACTIVATING_NEW_STRATEGY
};

EManagerState ParseManagerState(string state)
{
    if (state == "ACTIVE")                  return STATE_ACTIVE;
    if (state == "TRANSITION_STATE")        return STATE_TRANSITION_STATE;
    if (state == "CLOSING_POSITIONS")       return STATE_CLOSING_POSITIONS;
    if (state == "SAFE_TO_SWITCH")          return STATE_SAFE_TO_SWITCH;
    if (state == "ACTIVATING_NEW_STRATEGY") return STATE_ACTIVATING_NEW_STRATEGY;
    return STATE_IDLE;
}
```

---

### 4.4 Checklist DOC-STRAT-04

- [ ] EA responde a todos os 6 estados do FSM
- [ ] Dispatcher implementado como switch/case sem lógica ambígua
- [ ] `TRANSITION_STATE` bloqueia entradas mas não fecha posições ainda
- [ ] `CLOSING_POSITIONS` executa `SafeShutdown()` em loop até confirmação
- [ ] `SAFE_TO_SWITCH` e `ACTIVATING_NEW_STRATEGY` mantêm EA completamente passivo

---

---

## DOC-STRAT-05 — Sincronização de Estado

### Objetivo

Definir como o PRICEPRO_MONEY-EA reporta ao backend seu estado operacional em tempo real: posições abertas, lucro/prejuízo, drawdown e status geral.

---

### 5.1 Arquivo de Estado

O EA grava um arquivo JSON de estado a cada N segundos (padrão: 5s). O backend monitora esse arquivo para saber se o EA está vivo e em conformidade.

**Caminho:**
```
C:\MT5_Control\<user_id>\pricepro_money_v1\state.json
```

**Estrutura:**
```json
{
    "strategy_id":          "pricepro_money_v1",
    "magic_number":         20240001,
    "status":               "RUNNING",
    "manager_state_local":  "ACTIVE",
    "permitted":            true,
    "kill_switch_active":   false,
    "open_positions":       2,
    "open_orders":          0,
    "unrealized_pnl":       125.30,
    "realized_pnl_today":   340.00,
    "floating_drawdown":    -42.10,
    "max_drawdown_today":   -120.00,
    "account_balance":      10500.00,
    "account_equity":       10625.30,
    "last_trade_open":      "2026-02-27T13:45:00Z",
    "last_trade_close":     "2026-02-27T12:30:00Z",
    "heartbeat":            "2026-02-27T14:00:05Z",
    "uptime_seconds":       3600
}
```

---

### 5.2 Implementação MQL5

```mql5
datetime g_last_state_write  = 0;
int      g_uptime_start      = (int)TimeCurrent();

void WriteStateReport(string status = "", int forced_positions = -1)
{
    // Escreve a cada 5 segundos ou quando forçado
    if (status == "" && TimeCurrent() - g_last_state_write < 5)
        return;

    g_last_state_write = TimeCurrent();

    int    open_pos     = (forced_positions >= 0) ? forced_positions : CountMyPositions();
    double unrealized   = CalculateUnrealizedPnL();
    double realized     = CalculateRealizedPnLToday();
    double balance      = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity       = AccountInfoDouble(ACCOUNT_EQUITY);
    double drawdown     = equity - balance;
    string current_time = TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS);
    int    uptime       = (int)(TimeCurrent() - g_uptime_start);

    string state_str = ""
        + "{\"strategy_id\":\"pricepro_money_v1\","
        + "\"magic_number\":" + IntegerToString(MAGIC_NUMBER) + ","
        + "\"status\":\"" + (status != "" ? status : (g_permitted ? "RUNNING" : "PAUSED")) + "\","
        + "\"manager_state_local\":\"" + g_manager_state + "\","
        + "\"permitted\":" + (g_permitted ? "true" : "false") + ","
        + "\"kill_switch_active\":" + (g_kill_switch ? "true" : "false") + ","
        + "\"open_positions\":" + IntegerToString(open_pos) + ","
        + "\"open_orders\":" + IntegerToString(OrdersTotal()) + ","
        + "\"unrealized_pnl\":" + DoubleToString(unrealized, 2) + ","
        + "\"realized_pnl_today\":" + DoubleToString(realized, 2) + ","
        + "\"floating_drawdown\":" + DoubleToString(drawdown, 2) + ","
        + "\"account_balance\":" + DoubleToString(balance, 2) + ","
        + "\"account_equity\":" + DoubleToString(equity, 2) + ","
        + "\"heartbeat\":\"" + current_time + "\","
        + "\"uptime_seconds\":" + IntegerToString(uptime)
        + "}";

    string state_path = STATE_FILE_PATH;
    int handle = FileOpen(state_path, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if (handle == INVALID_HANDLE)
    {
        Print("[PRICEPRO] ERRO: Não foi possível gravar state.json");
        return;
    }
    FileWriteString(handle, state_str);
    FileClose(handle);
}
```

---

### 5.3 Leitura pelo Backend Python

```python
# backend/app/services/ea_monitor.py

import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta


class EAStateMonitor:
    """
    Monitoriza o arquivo state.json escrito pelo EA MT5.
    Usado pelo StrategyManager para confirmar que o EA está vivo
    e que o risco chegou a zero durante CLOSING_POSITIONS.
    """

    BASE_PATH = Path("C:/MT5_Control")
    HEARTBEAT_TIMEOUT_SECONDS = 30  # EA morto se sem heartbeat por 30s

    def __init__(self, user_id: str, strategy_id: str):
        self._path = self.BASE_PATH / user_id / strategy_id / "state.json"

    def read_state(self) -> dict:
        if not self._path.exists():
            return {"status": "UNREACHABLE", "open_positions": -1}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {"status": "PARSE_ERROR", "open_positions": -1}

    def is_alive(self) -> bool:
        state = self.read_state()
        heartbeat_str = state.get("heartbeat")
        if not heartbeat_str:
            return False
        try:
            hb = datetime.fromisoformat(heartbeat_str.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - hb).total_seconds()
            return age < self.HEARTBEAT_TIMEOUT_SECONDS
        except Exception:
            return False

    def is_risk_zero(self) -> bool:
        """Retorna True se o EA confirmou risco zero (usado em CLOSING_POSITIONS)."""
        state   = self.read_state()
        status  = state.get("status", "")
        pos     = state.get("open_positions", -1)
        orders  = state.get("open_orders", -1)
        return (
            status in ("SAFE_TO_SWITCH", "SHUTDOWN_COMPLETE")
            or (pos == 0 and orders == 0)
        )

    async def wait_for_risk_zero(self, timeout_seconds: int = 120) -> bool:
        """Aguarda até o EA confirmar risco zero ou timeout."""
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while asyncio.get_event_loop().time() < deadline:
            if self.is_risk_zero():
                return True
            await asyncio.sleep(2)
        return False
```

---

### 5.4 Integração com o `StrategyManager.activate_strategy()`

No fluxo de troca de estratégia, o backend chama `wait_for_risk_zero()` antes de prosseguir para `SAFE_TO_SWITCH`:

```python
# Dentro do pipeline de switch do StrategyManager
monitor = EAStateMonitor(self.user_id, active_strategy_id)
risk_zero = await monitor.wait_for_risk_zero(timeout_seconds=120)

if not risk_zero:
    await self._log.error(AuditEvent.SWITCH_ABORTED_RISK_ACTIVE, {
        "reason": "EA não confirmou risco zero dentro do timeout"
    })
    return ActivationResult.rejected("RISK_NOT_ZERO", "EA não fechou posições dentro do prazo.")
```

---

### 5.5 Checklist DOC-STRAT-05

- [ ] `WriteStateReport()` chamada a cada 5 segundos em `OnTick()`
- [ ] `WriteStateReport("SAFE_TO_SWITCH", 0)` chamada quando posições zerarem
- [ ] Backend monitora `state.json` via `EAStateMonitor`
- [ ] `is_alive()` detecta EA morto ou travado
- [ ] `wait_for_risk_zero()` usado no pipeline de switch com timeout de 120s

---

---

## DOC-STRAT-06 — Isolamento por Magic Number

### Objetivo

Garantir que o PRICEPRO_MONEY-EA controle **exclusivamente** as posições e ordens que ele mesmo abriu, sem interferir em posições de outros robôs ou do usuário manual.

---

### 6.1 Por Que Magic Number é Crítico

Em um ambiente onde múltiplos robôs podem ter sido executados anteriormente (e posições remanescentes podem existir), sem isolamento por magic number o EA pode:
- Fechar posições abertas por outro robô
- Calcular drawdown incluindo trades de outras estratégias
- Relatório de estado incorreto (posições falsas)

---

### 6.2 Definição do Magic Number

O magic number do PRICEPRO deve ser:
- **Único** no universo de estratégias do SaaS
- **Imutável** — nunca muda entre versões menores do EA
- **Documentado** no registro MongoDB da estratégia

```mql5
// ─── Magic number exclusivo para PRICEPRO MONEY ──────────────────────────────
#define MAGIC_NUMBER 20240001
// Convenção: YYYYMMNN onde NN é o número sequencial da estratégia
// 2024 = ano de criação, 0001 = primeiro EA registrado
```

**Tabela de Magic Numbers reservados:**

| Estratégia | Magic Number |
|---|---|
| PRICEPRO_MONEY-EA | `20240001` |
| (próxima estratégia) | `20240002` |
| (grid trader) | `20240003` |

---

### 6.3 Funções de Filtro por Magic Number

Todas as operações de listagem, fechamento e contagem devem filtrar por magic number:

```mql5
// ─── Fecha SOMENTE posições com este magic number ─────────────────────────────
bool CloseAllMyPositions()
{
    bool all_ok = true;
    for (int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if (!PositionSelectByIndex(i)) continue;
        if (PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;  // FILTRO

        ulong  ticket   = PositionGetInteger(POSITION_TICKET);
        string symbol   = PositionGetString(POSITION_SYMBOL);
        double volume   = PositionGetDouble(POSITION_VOLUME);
        ENUM_POSITION_TYPE tipo = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        MqlTradeRequest req = {};
        MqlTradeResult  res = {};
        req.action   = TRADE_ACTION_DEAL;
        req.position = ticket;
        req.symbol   = symbol;
        req.volume   = volume;
        req.type     = (tipo == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
        req.price    = (tipo == POSITION_TYPE_BUY)
                       ? SymbolInfoDouble(symbol, SYMBOL_BID)
                       : SymbolInfoDouble(symbol, SYMBOL_ASK);
        req.deviation = 20;
        req.magic     = MAGIC_NUMBER;
        req.comment   = "STRATEGY_SWITCH";

        if (!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
        {
            Print("[PRICEPRO] Falha ao fechar #", ticket, " retcode=", res.retcode);
            all_ok = false;
        }
    }
    return all_ok;
}

// ─── Cancela SOMENTE ordens pendentes com este magic number ──────────────────
void CancelAllMyOrders()
{
    for (int i = OrdersTotal() - 1; i >= 0; i--)
    {
        ulong ticket = OrderGetTicket(i);
        if (ticket == 0) continue;
        if (OrderGetInteger(ORDER_MAGIC) != MAGIC_NUMBER) continue;  // FILTRO

        MqlTradeRequest req = {};
        MqlTradeResult  res = {};
        req.action = TRADE_ACTION_REMOVE;
        req.order  = ticket;
        OrderSend(req, res);
    }
}

// ─── PnL não realizado SOMENTE das posições deste magic ──────────────────────
double CalculateUnrealizedPnL()
{
    double total = 0.0;
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (!PositionSelectByIndex(i)) continue;
        if (PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;  // FILTRO
        total += PositionGetDouble(POSITION_PROFIT);
    }
    return total;
}
```

---

### 6.4 Verificação no Backend

O campo `magic_number` no documento MongoDB da estratégia deve ser usado para validação de consistência:

```python
# Verifica se o magic number no state.json bate com o registrado no banco
state   = monitor.read_state()
ea_magic = state.get("magic_number")
db_magic = bot_doc.get("magic_number")

if ea_magic != db_magic:
    await audit.error(AuditEvent.SWITCH_ABORTED_RISK_ACTIVE, {
        "reason": f"Magic number mismatch: EA={ea_magic} DB={db_magic}"
    })
    raise ValueError("Magic number mismatch — EA incorreto conectado")
```

---

### 6.5 Checklist DOC-STRAT-06

- [ ] `MAGIC_NUMBER = 20240001` definido como constante imutável
- [ ] Todas as funções de iteração filtram por `POSITION_MAGIC == MAGIC_NUMBER`
- [ ] Contagem de posições para risk check usa o filtro
- [ ] Backend valida magic number do state.json contra registro no banco
- [ ] Tabela de magic numbers mantida e documentada para evitar colisões

---

---

## DOC-STRAT-07 — Bloqueio Anti-Rapid-Switch

### Objetivo

Impedir que o PRICEPRO_MONEY-EA reabra trades durante o processo de troca de estratégia, e que o próprio backend não permita uma segunda troca antes do intervalo mínimo de segurança.

---

### 7.1 Duas Camadas de Proteção

O bloqueio é implementado em **duas camadas independentes**:

| Camada | Onde | Mecanismo |
|---|---|---|
| **Camada 1 — Backend** | `StrategyManager.activate_strategy()` | `MIN_SWITCH_INTERVAL_SECONDS = 60` |
| **Camada 2 — EA** | `OnTick()` no MT5 | Estado `g_manager_state != "ACTIVE"` bloqueia execução |

---

### 7.2 Camada 1: Backend — Gate Anti-Rapid-Switch

Já implementado no `StrategyManager`:

```python
# Já existente em strategy_manager.py — GATE 1
elapsed = time.time() - (last_switch_ts or 0)
if last_switch_ts and elapsed < self._config["MIN_SWITCH_INTERVAL_SECONDS"]:
    wait = int(self._config["MIN_SWITCH_INTERVAL_SECONDS"] - elapsed)
    return ActivationResult.rejected(
        "TOO_SOON",
        f"Minimum interval between strategy switches not elapsed.",
        wait_seconds=wait,
    )
```

Este gate rejeita a segunda solicitação de ativação caso o intervalo mínimo de 60 segundos não tenha passado. Isso, por si só, não é suficiente — o EA precisa ter sua própria proteção.

---

### 7.3 Camada 2: EA — Bloqueio Local de Reentrada

```mql5
// ─── Flag de bloqueio de reentrada ───────────────────────────────────────────
bool     g_switch_in_progress = false;
datetime g_switch_blocked_until = 0;

// Chamado quando manager_state muda de ACTIVE para TRANSITION_STATE
void OnSwitchDetected()
{
    g_switch_in_progress  = true;
    g_permitted           = false;
    g_switch_blocked_until = TimeCurrent() + 120;  // bloqueio local de 2 minutos

    Print("[PRICEPRO] Troca de estratégia detectada — entradas bloqueadas até ",
          TimeToString(g_switch_blocked_until));
}

// ─── Guarda em OnTick ─────────────────────────────────────────────────────────
void OnTick()
{
    ReadControlFile();

    // Detectar transição para estado de switch
    if (g_manager_state == "TRANSITION_STATE" && !g_switch_in_progress)
        OnSwitchDetected();

    // Bloqueio temporal local (mesmo que o arquivo de controle seja atualizado tarde)
    if (g_switch_in_progress && TimeCurrent() < g_switch_blocked_until)
    {
        if (g_manager_state == "ACTIVE")
        {
            // Proteção: manager voltou para ACTIVE mas ainda dentro do bloqueio local
            Print("[PRICEPRO] Bloqueio local ativo. Ignorando ACTIVE prematuro.");
            return;
        }
    }

    // Liberar bloqueio local somente quando o backend confirmar ACTIVE E timeout local expirar
    if (g_switch_in_progress
        && g_manager_state == "ACTIVE"
        && TimeCurrent() >= g_switch_blocked_until)
    {
        g_switch_in_progress = false;
        Print("[PRICEPRO] Bloqueio local expirado. Operação normal retomada.");
    }

    if (!g_permitted || g_switch_in_progress || g_kill_switch) return;
    if (g_manager_state != "ACTIVE") return;

    ExecuteStrategy();
}
```

---

### 7.4 Cenário de Proteção

```
Tick 1:  manager_state = "ACTIVE"     → ExecuteStrategy() ✓
Tick 2:  manager_state = "ACTIVE"     → ExecuteStrategy() ✓
Tick 3:  manager_state = "TRANSITION" → OnSwitchDetected(), g_permitted=false ✗
Tick 4:  manager_state = "CLOSING"    → SafeShutdown() loop
...
         [posições fechadas]
Tick N:  manager_state = "ACTIVE"     → g_switch_in_progress ainda ativo (bloqueio local)
                                         NÃO executa estratégia ✗
Tick N+60: bloqueio local expirou     → ExecuteStrategy() ✓
```

---

### 7.5 Checklist DOC-STRAT-07

- [ ] Gate de 60s no backend (já implementado no `StrategyManager`)
- [ ] Flag `g_switch_in_progress` no EA ativada ao detectar `TRANSITION_STATE`
- [ ] Bloqueio local de 120s no EA, independente do arquivo de controle
- [ ] EA não retoma ExecuteStrategy() apenas com ACTIVE: exige timeout local expirado
- [ ] Log impresso ao detectar e ao liberar o bloqueio

---

---

## DOC-STRAT-08 — Integração com Risk Manager

### Objetivo

Ensinar o PRICEPRO_MONEY-EA a respeitar os sinais de Risk Manager vindos do SaaS: Kill Switch global, Daily Loss limit, e Emergency Stop.

---

### 8.1 Campos de Risco no Arquivo de Controle

O arquivo `control.json` já inclui os campos de risco relevantes:

```json
{
    "permitted":              true,
    "kill_switch":            false,
    "emergency_stop":         false,
    "daily_loss_limit":       500.00,
    "daily_loss_current":     120.50,
    "max_drawdown_pct":       20.0,
    "cooldown_until":         null
}
```

---

### 8.2 Implementação MQL5 — Respeitar Limites de Risco

```mql5
double g_daily_loss_limit   = 500.0;
double g_daily_loss_current = 0.0;
double g_max_drawdown_pct   = 20.0;
string g_cooldown_until     = "";

// Atualizar variáveis de risco ao ler o arquivo de controle
void ReadRiskLimitsFromControl(string content)
{
    g_daily_loss_limit   = ParseJSONDouble(content, "daily_loss_limit");
    g_daily_loss_current = ParseJSONDouble(content, "daily_loss_current");
    g_max_drawdown_pct   = ParseJSONDouble(content, "max_drawdown_pct");
    g_cooldown_until     = ParseJSONString(content, "cooldown_until");
}

// Verificação de risco antes de qualquer entrada
bool IsRiskAcceptable()
{
    // Kill switch — prioridade máxima
    if (g_kill_switch)
    {
        Print("[PRICEPRO] Kill switch ativo — sem entradas.");
        return false;
    }

    // Emergency stop
    if (ParseJSONBool(FileReadAll(CONTROL_FILE_PATH), "emergency_stop"))
    {
        Print("[PRICEPRO] Emergency stop ativo — executando SafeShutdown().");
        SafeShutdown();
        return false;
    }

    // Daily loss limit atingido
    if (g_daily_loss_limit > 0 && g_daily_loss_current <= -g_daily_loss_limit)
    {
        Print("[PRICEPRO] Daily loss limit atingido: ", g_daily_loss_current,
              " / ", -g_daily_loss_limit, " — sem novas entradas.");
        return false;
    }

    // Cooldown ativo
    if (g_cooldown_until != "" && g_cooldown_until != "null")
    {
        // Comparar timestamp (simplificado — em produção usar conversão adequada)
        Print("[PRICEPRO] Cooldown ativo até ", g_cooldown_until, " — sem entradas.");
        return false;
    }

    return true;
}

// Integrar na guarda principal
void ExecuteStrategy()
{
    if (!IsRiskAcceptable()) return;

    // ─── Lógica original do PRICEPRO a partir daqui ──────────────────────
    // ... código de análise e abertura de ordens ...
}
```

---

### 8.3 Acionamento do Kill Switch pelo Backend

No `RiskManager` Python, quando `kill_switch_on_daily_loss=True` e o limite é atingido:

```python
# backend/app/trading/risk_manager.py (extensão)
async def trigger_kill_switch(self, user_id: str, reason: str, ea_controller: EAController):
    """Aciona kill switch: bloqueia EA + fecha posições via SaaS."""
    self._kill_switched.add(user_id)
    
    # 1. Atualiza arquivo de controle do EA imediatamente
    ea_controller.emergency_stop()
    
    # 2. Muda estado do StrategyManager
    await _StateStore.save(user_id, {
        "state":      StrategyState.CLOSING_POSITIONS,
        "kill_reason": reason,
    })
    
    logger.critical(f"🚨 KILL SWITCH ativado para user={user_id} reason={reason}")
```

---

### 8.4 Hierarquia de Prioridade de Risco

```
Kill Switch         → Prioridade 1 (fecha tudo, sem exceção)
Emergency Stop      → Prioridade 2 (SafeShutdown imediato)
Daily Loss Limit    → Prioridade 3 (bloqueia novas entradas)
Max Drawdown %      → Prioridade 4 (bloqueia novas entradas)
Cooldown After Loss → Prioridade 5 (pausa temporária)
```

---

### 8.5 Checklist DOC-STRAT-08

- [ ] `IsRiskAcceptable()` chamada antes de `ExecuteStrategy()`, nunca depois
- [ ] Kill switch tem prioridade sobre qualquer outra lógica
- [ ] Emergency stop aciona `SafeShutdown()` imediatamente
- [ ] Daily loss lido do arquivo de controle, nunca calculado localmente de forma isolada
- [ ] RiskManager Python atualiza controle.json ao acionar kill switch

---

---

## DOC-STRAT-09 — Handshake de Ativação

### Objetivo

Definir o protocolo completo de handshake que garante que o PRICEPRO_MONEY-EA só começa a operar após confirmação mútua entre backend e EA — nunca por impulso.

---

### 9.1 Fluxo Completo do Handshake

```
USUÁRIO            BACKEND (StrategyManager)       EA (MT5)
   │                        │                         │
   │── activate("pricepro")─►│                         │
   │                        │                         │
   │               [Gate 1: anti-rapid-switch]        │
   │               [Gate 2: já ativo?]                │
   │               [Gate 3: em transição?]            │
   │               [Gate 4: bot existe?]              │
   │                        │                         │
   │               [Adquire lock por usuário]         │
   │                        │                         │
   │               State → ACTIVATING_NEW_STRATEGY    │
   │                        │                         │
   │                        │─── Escreve control.json ►│
   │                        │    command: ACTIVATE     │
   │                        │    permitted: false      │
   │                        │    (aguarda handshake)   │
   │                        │                         │
   │                        │◄── Lê control.json ─────│
   │                        │                         │
   │                        │    EA verifica:          │
   │                        │    - magic number válido │
   │                        │    - sequência correta   │
   │                        │    - estado compatível   │
   │                        │                         │
   │                        │◄── Grava state.json ────│
   │                        │    status: "READY"       │
   │                        │    magic_number: 20240001│
   │                        │                         │
   │                [Backend lê state.json]            │
   │                [Valida magic number]              │
   │                [Confirma status = READY]          │
   │                        │                         │
   │                [mark_bot_running()]               │
   │                        │                         │
   │                        │─── Escreve control.json ►│
   │                        │    permitted: true       │
   │                        │    manager_state: ACTIVE │
   │                        │                         │
   │                State → ACTIVE                    │
   │                        │                         │
   │◄── ActivationResult.ok─│                         │
   │                        │                         │
   │                                    │             │
   │                         EA lê permitted=true     │
   │                         ExecuteStrategy() ✓      │
```

---

### 9.2 Implementação MQL5 — Fase de Handshake

```mql5
bool g_handshake_done    = false;
bool g_handshake_sent    = false;
int  g_handshake_timeout = 30;  // segundos
datetime g_handshake_start = 0;

// Chamado quando EA é carregado (OnInit) e quando recebe ACTIVATE
void InitHandshake()
{
    g_handshake_done  = false;
    g_handshake_sent  = false;
    g_permitted       = false;
    g_handshake_start = TimeCurrent();

    Print("[PRICEPRO] Handshake iniciado. Aguardando confirmação do backend...");

    // Escrever estado READY para o backend confirmar
    WriteStateReportWithStatus("READY");
    g_handshake_sent = true;
}

// Verificar handshake a cada tick
void CheckHandshake()
{
    if (g_handshake_done) return;

    // Timeout de handshake
    if (TimeCurrent() - g_handshake_start > g_handshake_timeout)
    {
        Print("[PRICEPRO] ERRO: Handshake timeout. EA não autorizado a operar.");
        g_permitted = false;
        WriteStateReportWithStatus("HANDSHAKE_TIMEOUT");
        return;
    }

    // Verificar se backend confirmou via control.json
    ReadControlFile();

    if (g_permitted && g_manager_state == "ACTIVE")
    {
        g_handshake_done = true;
        Print("[PRICEPRO] Handshake concluído. Trading habilitado.");
        WriteStateReportWithStatus("RUNNING");
    }
}

// Integração no OnTick
void OnTick()
{
    if (!g_handshake_done)
    {
        CheckHandshake();
        return;  // não executa estratégia até handshake concluído
    }

    ReadControlFile();
    // ... dispatcher de estados ...
    ExecuteStrategy();
}
```

---

### 9.3 Implementação Backend — Confirmação de Handshake

```python
# Dentro do pipeline de ativação do StrategyManager
async def _complete_handshake(self, user_id: str, bot_id: str, strategy_id: str) -> bool:
    """
    Aguarda o EA confirmar READY, valida magic number,
    e então envia o sinal final de ACTIVATE com permitted=true.
    """
    monitor     = EAStateMonitor(user_id, strategy_id)
    controller  = EAController(user_id, strategy_id)
    deadline    = asyncio.get_event_loop().time() + 30  # 30s timeout

    # Fase 1: Enviar ACTIVATE com permitted=false (espera handshake)
    controller.activate_pending()  # permitted=false, manager_state=ACTIVATING_NEW_STRATEGY

    # Fase 2: Aguardar EA gravar READY
    while asyncio.get_event_loop().time() < deadline:
        state = monitor.read_state()
        if state.get("status") == "READY":
            # Fase 3: Validar magic number
            if state.get("magic_number") != BOT_MAGIC_NUMBERS[strategy_id]:
                await self._log.error(AuditEvent.ACTIVATION_FAILED, {
                    "reason": "Magic number mismatch no handshake"
                })
                return False

            # Fase 4: Confirmar ativação — permitted=true
            controller.activate(manager_state="ACTIVE")
            await self._log.info(AuditEvent.STRATEGY_ACTIVATED, {
                "strategy_id": strategy_id,
                "handshake":   "SUCCESS"
            })
            return True

        await asyncio.sleep(1)

    # Timeout
    await self._log.error(AuditEvent.ACTIVATION_FAILED, {
        "reason": "Handshake timeout — EA não respondeu em 30s"
    })
    return False
```

---

### 9.4 Checklist DOC-STRAT-09

- [ ] EA não opera antes de handshake concluído (`g_handshake_done = false`)
- [ ] EA grava `READY` no state.json ao ser carregado
- [ ] Backend aguarda `READY` com timeout de 30s
- [ ] Backend valida magic number durante handshake
- [ ] Somente após validação o backend envia `permitted=true`
- [ ] Timeout de handshake bloqueia EA definitivamente até reinício

---

---

## DOC-STRAT-10 — Padrão Universal de Estratégias

### Objetivo

Definir o template reutilizável que todo futuro robô deve seguir para ser compatível com o SaaS Strategy Manager sem precisar redocumentar a integração.

---

### 10.1 Template MQL5 — SaaS Strategy Module Base

```mql5
//+------------------------------------------------------------------+
//| SaaS Strategy Module — Template Universal                        |
//| Baseado na integração PRICEPRO_MONEY-EA                          |
//| Versão: 1.0 | Compatível com: Crypto Trade Hub                   |
//+------------------------------------------------------------------+

#property copyright "Crypto Trade Hub"
#property version   "1.00"
#property strict

// ─── CONFIGURAÇÃO OBRIGATÓRIA — preencher por estratégia ─────────────────────
#define STRATEGY_ID    "template_strategy_v1"   // ID único registrado no SaaS
#define MAGIC_NUMBER   20240000                  // Magic number exclusivo
#define USER_ID        "replace_with_user_id"   // Injetado pelo backend

// ─── Caminhos dos arquivos de controle ───────────────────────────────────────
string CONTROL_FILE_PATH = "C:\\MT5_Control\\" + USER_ID + "\\" + STRATEGY_ID + "\\control.json";
string STATE_FILE_PATH   = "C:\\MT5_Control\\" + USER_ID + "\\" + STRATEGY_ID + "\\state.json";

// ─── Estado global de controle ───────────────────────────────────────────────
bool   g_permitted            = false;
bool   g_kill_switch          = false;
bool   g_emergency_stop       = false;
string g_manager_state        = "IDLE";
int    g_last_sequence        = -1;
bool   g_handshake_done       = false;
bool   g_switch_in_progress   = false;
datetime g_switch_blocked_until = 0;
datetime g_control_last_read  = 0;
datetime g_state_last_write   = 0;
int    g_uptime_start         = 0;

// ─── Inicialização ────────────────────────────────────────────────────────────
int OnInit()
{
    g_uptime_start    = (int)TimeCurrent();
    g_handshake_done  = false;
    g_permitted       = false;

    Print("[", STRATEGY_ID, "] Inicializando. Aguardando handshake...");
    WriteStateReport("READY");

    return INIT_SUCCEEDED;
}

// ─── Desinicialização ─────────────────────────────────────────────────────────
void OnDeinit(const int reason)
{
    SafeShutdown();
    WriteStateReport("OFFLINE");
    Print("[", STRATEGY_ID, "] Desinicializado. Motivo: ", reason);
}

// ─── Tick principal ───────────────────────────────────────────────────────────
void OnTick()
{
    // 1. Handshake obrigatório
    if (!g_handshake_done) { CheckHandshake(); return; }

    // 2. Atualiza estado de controle
    ReadControlFile();
    WriteStateReport();  // periódico (debounce interno)

    // 3. Anti-rapid-switch local
    if (g_switch_in_progress && TimeCurrent() < g_switch_blocked_until) return;
    if (g_switch_in_progress && g_manager_state == "ACTIVE"
        && TimeCurrent() >= g_switch_blocked_until)
        g_switch_in_progress = false;

    // 4. Dispatcher de estado
    switch (ParseManagerState(g_manager_state))
    {
        case STATE_IDLE:
            return;

        case STATE_ACTIVE:
            if (g_kill_switch || g_emergency_stop) { SafeShutdown(); return; }
            if (!g_permitted) return;
            if (!IsRiskAcceptable()) return;
            ExecuteStrategy();  // ← IMPLEMENTAR AQUI
            break;

        case STATE_TRANSITION_STATE:
            if (!g_switch_in_progress)
            {
                g_switch_in_progress  = true;
                g_switch_blocked_until = TimeCurrent() + 120;
                g_permitted           = false;
            }
            break;

        case STATE_CLOSING_POSITIONS:
            g_permitted = false;
            if (CountMyPositions() > 0 || OrdersTotal() > 0)
                SafeShutdown();
            else
                WriteStateReport("SAFE_TO_SWITCH");
            break;

        case STATE_SAFE_TO_SWITCH:
        case STATE_ACTIVATING_NEW_STRATEGY:
            break;  // passivo
    }
}

// ─── IMPLEMENTAR AQUI: lógica de trading ─────────────────────────────────────
void ExecuteStrategy()
{
    // TODO: Colocar a lógica de entrada/saída aqui.
    // Não chamar esta função diretamente — usar o dispatcher acima.
}

// ─── Contrato: SafeShutdown ───────────────────────────────────────────────────
bool SafeShutdown()
{
    g_permitted = false;
    CancelAllMyOrders();
    CloseAllMyPositions();
    Sleep(500);
    int remaining = CountMyPositions();
    WriteStateReport(remaining == 0 ? "SAFE_TO_SWITCH" : "SHUTDOWN_PENDING");
    return remaining == 0;
}

// ─── Handshake ───────────────────────────────────────────────────────────────
void CheckHandshake()
{
    ReadControlFile();
    if (g_permitted && g_manager_state == "ACTIVE")
    {
        g_handshake_done = true;
        WriteStateReport("RUNNING");
        Print("[", STRATEGY_ID, "] Handshake OK. Trading habilitado.");
    }
}

// ─── State Report ─────────────────────────────────────────────────────────────
void WriteStateReport(string forced_status = "")
{
    if (forced_status == "" && TimeCurrent() - g_state_last_write < 5) return;
    g_state_last_write = TimeCurrent();

    string status   = forced_status != "" ? forced_status : (g_permitted ? "RUNNING" : "PAUSED");
    string content  = ""
        + "{\"strategy_id\":\"" + STRATEGY_ID + "\","
        + "\"magic_number\":" + IntegerToString(MAGIC_NUMBER) + ","
        + "\"status\":\"" + status + "\","
        + "\"manager_state_local\":\"" + g_manager_state + "\","
        + "\"permitted\":" + (g_permitted ? "true" : "false") + ","
        + "\"kill_switch_active\":" + (g_kill_switch ? "true" : "false") + ","
        + "\"open_positions\":" + IntegerToString(CountMyPositions()) + ","
        + "\"open_orders\":" + IntegerToString(OrdersTotal()) + ","
        + "\"unrealized_pnl\":" + DoubleToString(CalculateUnrealizedPnL(), 2) + ","
        + "\"account_balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ","
        + "\"account_equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ","
        + "\"heartbeat\":\"" + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) + "\","
        + "\"uptime_seconds\":" + IntegerToString((int)(TimeCurrent() - g_uptime_start))
        + "}";

    int h = FileOpen(STATE_FILE_PATH, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if (h != INVALID_HANDLE) { FileWriteString(h, content); FileClose(h); }
}

// ─── Funções utilitárias (copiar para cada EA) ───────────────────────────────
int CountMyPositions()
{
    int n = 0;
    for (int i = 0; i < PositionsTotal(); i++)
        if (PositionGetTicket(i) > 0 && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER) n++;
    return n;
}

double CalculateUnrealizedPnL()
{
    double t = 0;
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (!PositionSelectByIndex(i)) continue;
        if (PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
            t += PositionGetDouble(POSITION_PROFIT);
    }
    return t;
}

void CloseAllMyPositions()  { /* ver DOC-STRAT-06 seção 6.3 */ }
void CancelAllMyOrders()    { /* ver DOC-STRAT-06 seção 6.3 */ }
bool IsRiskAcceptable()     { /* ver DOC-STRAT-08 seção 8.2 */ }
void ReadControlFile()      { /* ver DOC-STRAT-02 seção 2.3 */ }
```

---

### 10.2 Template Python — Strategy Module Backend

```python
# backend/app/bots/pricepro_money_module.py

"""
PRICEPRO_MONEY — Strategy Module KuCoin SaaS

Encapsula o comportamento do EA para o Strategy Manager backend.
Cada método aqui tem correspondência direta no EA MT5.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class StrategyStatus:
    strategy_id:       str
    magic_number:      int
    status:            str           # READY | RUNNING | PAUSED | SAFE_TO_SWITCH | OFFLINE
    open_positions:    int
    open_orders:       int
    unrealized_pnl:    float
    account_balance:   float
    account_equity:    float
    heartbeat:         Optional[datetime]
    uptime_seconds:    int
    manager_state_local: str


class SaaSStrategyModule(ABC):
    """
    Interface base para todo Strategy Module registrado no SaaS.
    PRICEPRO_MONEY e futuros robôs devem herdar desta classe.
    """

    @property
    @abstractmethod
    def strategy_id(self) -> str: ...

    @property
    @abstractmethod
    def magic_number(self) -> int: ...

    @abstractmethod
    async def activate(self) -> bool:
        """Inicia o módulo e aguarda handshake do EA."""
        ...

    @abstractmethod
    async def deactivate(self) -> bool:
        """Desativa o módulo graciosamente (sem fechar posições)."""
        ...

    @abstractmethod
    async def safe_shutdown(self, timeout_seconds: int = 120) -> bool:
        """Inicia SafeShutdown e aguarda confirmação de risco zero."""
        ...

    @abstractmethod
    def get_status(self) -> StrategyStatus:
        """Retorna snapshot atual do estado operacional."""
        ...

    @abstractmethod
    async def is_alive(self) -> bool:
        """Retorna True se o EA está respondendo (heartbeat recente)."""
        ...

    @abstractmethod
    async def is_risk_zero(self) -> bool:
        """Retorna True se não há posições ou ordens abertas."""
        ...


class PriceProMoneyModule(SaaSStrategyModule):
    """Implementação concreta do PRICEPRO_MONEY-EA como SaaS Module."""

    def __init__(self, user_id: str):
        self._user_id   = user_id
        self._controller = EAController(user_id, "pricepro_money_v1")
        self._monitor    = EAStateMonitor(user_id, "pricepro_money_v1")

    @property
    def strategy_id(self) -> str: return "pricepro_money_v1"

    @property
    def magic_number(self) -> int: return 20240001

    async def activate(self) -> bool:
        self._controller.activate_pending()
        return await self._wait_for_handshake(timeout_seconds=30)

    async def deactivate(self) -> bool:
        self._controller.deactivate()
        return True

    async def safe_shutdown(self, timeout_seconds: int = 120) -> bool:
        self._controller.safe_shutdown()
        return await self._monitor.wait_for_risk_zero(timeout_seconds)

    def get_status(self) -> StrategyStatus:
        raw = self._monitor.read_state()
        return StrategyStatus(
            strategy_id=raw.get("strategy_id", self.strategy_id),
            magic_number=raw.get("magic_number", self.magic_number),
            status=raw.get("status", "UNREACHABLE"),
            open_positions=raw.get("open_positions", -1),
            open_orders=raw.get("open_orders", -1),
            unrealized_pnl=raw.get("unrealized_pnl", 0.0),
            account_balance=raw.get("account_balance", 0.0),
            account_equity=raw.get("account_equity", 0.0),
            heartbeat=None,
            uptime_seconds=raw.get("uptime_seconds", 0),
            manager_state_local=raw.get("manager_state_local", "UNKNOWN"),
        )

    async def is_alive(self) -> bool:
        return self._monitor.is_alive()

    async def is_risk_zero(self) -> bool:
        return self._monitor.is_risk_zero()

    async def _wait_for_handshake(self, timeout_seconds: int) -> bool:
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while asyncio.get_event_loop().time() < deadline:
            state = self._monitor.read_state()
            if state.get("status") == "READY":
                self._controller.activate(manager_state="ACTIVE")
                return True
            await asyncio.sleep(1)
        return False
```

---

### 10.3 Checklist Universal — Novo EA no SaaS

Antes de registrar qualquer novo EA no sistema, verificar:

**Configuração Básica:**
- [ ] `STRATEGY_ID` único no sistema, registrado no MongoDB
- [ ] `MAGIC_NUMBER` único, documentado na tabela de magic numbers
- [ ] Documento de registro criado no MongoDB com todos os campos obrigatórios

**Contratos Implementados:**
- [ ] `ReadControlFile()` — lê control.json a cada tick com debounce
- [ ] `WriteStateReport()` — grava state.json a cada 5s e em eventos críticos
- [ ] `SafeShutdown()` — cancela ordens, fecha posições, confirma zero
- [ ] `CheckHandshake()` — aguarda confirmação do backend antes de operar
- [ ] `IsRiskAcceptable()` — verifica kill switch, daily loss, cooldown

**Filtro por Magic Number:**
- [ ] `CountMyPositions()` filtra por MAGIC_NUMBER
- [ ] `CloseAllMyPositions()` filtra por MAGIC_NUMBER
- [ ] `CancelAllMyOrders()` filtra por MAGIC_NUMBER
- [ ] `CalculateUnrealizedPnL()` filtra por MAGIC_NUMBER

**Comportamento por Estado:**
- [ ] `IDLE` → parado
- [ ] `ACTIVE` → operando com todas as guardas
- [ ] `TRANSITION_STATE` → bloqueia entradas, ativa bloqueio local
- [ ] `CLOSING_POSITIONS` → SafeShutdown() loop
- [ ] `SAFE_TO_SWITCH` → passivo
- [ ] `ACTIVATING_NEW_STRATEGY` → passivo

**Módulo Backend:**
- [ ] Herda de `SaaSStrategyModule`
- [ ] Implementa todos os métodos abstratos
- [ ] Registrado no `StrategyManager` como módulo ativável

---

### 10.4 Registro de Estratégias no Sistema

```python
# backend/app/services/strategy_registry.py

STRATEGY_REGISTRY = {
    "pricepro_money_v1": {
        "class":        PriceProMoneyModule,
        "magic_number": 20240001,
        "display_name": "PRICEPRO MONEY",
        "version":      "1.0",
        "min_switch_interval_s": 60,
        "safe_shutdown_timeout_s": 120,
        "handshake_timeout_s": 30,
    },
    # Adicionar futuras estratégias aqui:
    # "grid_scalper_v1": { ... }
}


def get_strategy_module(strategy_id: str, user_id: str) -> SaaSStrategyModule:
    """Factory de módulos de estratégia."""
    entry = STRATEGY_REGISTRY.get(strategy_id)
    if not entry:
        raise ValueError(f"Estratégia '{strategy_id}' não registrada no SaaS.")
    return entry["class"](user_id)
```

---

---

## Apêndice — Visão Geral da Arquitetura de Integração

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CRYPTO TRADE HUB — SaaS Layer                        │
│                                                                         │
│  Frontend (React)                                                       │
│      │ ativar estratégia                                                │
│      ▼                                                                  │
│  StrategyManager                                                        │
│  ├── GATE 1: Anti-Rapid-Switch (60s)                                    │
│  ├── GATE 2: Já ativo?                                                  │
│  ├── GATE 3: Em transição?                                              │
│  ├── GATE 4: Bot existe?                                                │
│  ├── Lock por usuário (asyncio.Lock)                                    │
│  │                                                                      │
│  ├── EAController ──────────────────────► control.json (disco)          │
│  │       write: SAFE_SHUTDOWN / ACTIVATE                                │
│  │                                                                      │
│  ├── EAStateMonitor ◄───────────────────── state.json (disco)           │
│  │       read: READY / SAFE_TO_SWITCH / heartbeat                       │
│  │                                                                      │
│  ├── RiskManager                                                        │
│  │       kill_switch | daily_loss | cooldown                            │
│  │                                                                      │
│  └── AuditLogger → MongoDB (strategy_audit_log TTL 90d)                 │
│                                                                         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ Arquivo JSON (disco local ou rede)
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                 MetaTrader 5 — PRICEPRO_MONEY-EA                        │
│                                                                         │
│  OnTick()                                                               │
│  ├── ReadControlFile()   → lê control.json                              │
│  ├── WriteStateReport()  → grava state.json                             │
│  ├── CheckHandshake()    → handshake antes de operar                    │
│  ├── Dispatcher FSM      → comportamento por estado                     │
│  ├── SafeShutdown()      → fecha por MAGIC_NUMBER=20240001              │
│  ├── IsRiskAcceptable()  → kill switch | daily loss | cooldown          │
│  └── ExecuteStrategy()   → lógica PRICEPRO (somente se ACTIVE + READY) │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Apêndice — Tabela de Magic Numbers do Sistema

| Estratégia | Magic Number | Status |
|---|---|---|
| PRICEPRO_MONEY-EA | `20240001` | Ativo |
| *(reservado)* | `20240002` | — |
| *(reservado)* | `20240003` | — |

---

## Apêndice — Eventos de Auditoria Gerados pela Integração

| Evento | Quando é Gerado |
|---|---|
| `STRATEGY_ACTIVATED` | Handshake concluído, EA operando |
| `STRATEGY_DEACTIVATED` | EA desativado graciosamente |
| `SWITCH_INITIATED` | Troca de estratégia solicitada |
| `POSITION_CLOSED` | Posição fechada durante `CLOSING_POSITIONS` |
| `ORDER_CANCELLED` | Ordem pendente cancelada |
| `RISK_ZERO_CONFIRMED` | `state.json` confirmou 0 posições |
| `CONTEXT_CLEARED` | Contexto do EA anterior limpo |
| `STRATEGY_SWITCHED` | Nova estratégia ativa com sucesso |
| `SWITCH_ABORTED_RISK_ACTIVE` | Timeout sem confirmação de risco zero |
| `ACTIVATION_FAILED` | Handshake falhou ou magic number inválido |
| `WORKER_FORCE_KILLED` | EA não respondeu, forçado encerramento |
| `RISK_CHECK_PENDING` | Aguardando zeragem de posições |

---

*Documento gerado em 2026-02-27 — Crypto Trade Hub Engineering*  
*Classificação: Interno / Engenharia de Estratégias*
