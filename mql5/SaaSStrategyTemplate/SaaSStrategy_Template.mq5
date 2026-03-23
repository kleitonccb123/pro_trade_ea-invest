//+------------------------------------------------------------------+
//| SaaSStrategy_Template.mq5                                        |
//| SaaS Strategy Module — Template Universal                        |
//| Baseado na integração PRICEPRO_MONEY-EA (DOC-STRAT-01..10)       |
//| Versão: 1.0 | Crypto Trade Hub                                   |
//|                                                                  |
//| COMO USAR                                                        |
//|   1. Copiar este arquivo para mql5/<NOME_EA>/                    |
//|   2. Renomear para <NOME_EA>_SaaS.mq5                            |
//|   3. Preencher as 3 constantes na seção CONFIGURAÇÃO abaixo      |
//|   4. Implementar ExecuteStrategy() com a lógica de trading       |
//|   5. Registrar strategy_id + magic_number no MongoDB             |
//|   6. Adicionar entry em BOT_MAGIC_NUMBERS (strategy_manager.py)  |
//|   7. Adicionar entry em STRATEGY_REGISTRY (strategy_registry.py) |
//|                                                                  |
//| Arquivos gerados em runtime:                                     |
//|   control.json  C:\MT5_Control\<user>\<strategy_id>\            |
//|   state.json    C:\MT5_Control\<user>\<strategy_id>\            |
//+------------------------------------------------------------------+

#property copyright "Crypto Trade Hub"
#property version   "1.00"
#property strict

// ─── Includes ─────────────────────────────────────────────────────────────────
// Copiar os dois includes do diretório mql5/include/ para o projeto
#include "..\include\JSONParser.mqh"
#include "..\include\SaaSControlReader.mqh"

// ─────────────────────────────────────────────────────────────────────────────
// CONFIGURAÇÃO OBRIGATÓRIA — preencher por estratégia
// Não reutilizar magic numbers. Ver tabela em PRICEPRO_SAAS_INTEGRATION.md
// ─────────────────────────────────────────────────────────────────────────────
#define STRATEGY_ID   "template_strategy_v1"   // ID único registrado no MongoDB
#define MAGIC_NUMBER  20240000                  // Magic number exclusivo (YYYYMMNN)

// ID do usuário — preenchido pelo operador ao instalar o EA
input string InpUserId = "replace_with_user_id";   // USER ID (backend)

// Fallback local de emergência (manter false em produção)
input bool   InpEmergencyLocal = false;

// ─────────────────────────────────────────────────────────────────────────────
// ESTADO GLOBAL DE CONTROLE
// Estes globals são compartilhados com SaaSControlReader.mqh que define:
//   g_permitted, g_kill_switch, g_emergency_stop, g_manager_state,
//   g_last_sequence, g_control_last_read,
//   g_daily_loss_limit, g_daily_loss_current, g_max_drawdown_pct, g_cooldown_until
//   CONTROL_FILE_PATH
// ─────────────────────────────────────────────────────────────────────────────

// ── Handshake (DOC-STRAT-09) ─────────────────────────────────────────────────
bool     g_handshake_done      = false;
bool     g_handshake_sent      = false;
datetime g_handshake_start     = 0;
int      g_handshake_timeout_s = 30;

// ── Anti-rapid-switch local (DOC-STRAT-07) ────────────────────────────────────
bool     g_switch_in_progress  = false;
datetime g_switch_blocked_until = 0;

// ── Uptime + state write (DOC-STRAT-05) ──────────────────────────────────────
datetime g_uptime_start        = 0;
datetime g_state_last_write    = 0;

// ── Caminho do arquivo de estado ─────────────────────────────────────────────
string   STATE_FILE_PATH       = "";

// ─────────────────────────────────────────────────────────────────────────────
// FSM — Enumeração dos estados (espelha StrategyState no backend Python)
// ─────────────────────────────────────────────────────────────────────────────
enum EManagerState
{
    STATE_IDLE,
    STATE_ACTIVE,
    STATE_TRANSITION_STATE,
    STATE_CLOSING_POSITIONS,
    STATE_SAFE_TO_SWITCH,
    STATE_ACTIVATING_NEW_STRATEGY
};

EManagerState ParseManagerState(string s)
{
    if (s == "ACTIVE")                  return STATE_ACTIVE;
    if (s == "TRANSITION_STATE")        return STATE_TRANSITION_STATE;
    if (s == "CLOSING_POSITIONS")       return STATE_CLOSING_POSITIONS;
    if (s == "SAFE_TO_SWITCH")          return STATE_SAFE_TO_SWITCH;
    if (s == "ACTIVATING_NEW_STRATEGY") return STATE_ACTIVATING_NEW_STRATEGY;
    return STATE_IDLE;
}

// ─────────────────────────────────────────────────────────────────────────────
// CICLO DE VIDA
// ─────────────────────────────────────────────────────────────────────────────

int OnInit()
{
    InitControlPaths(InpUserId, STRATEGY_ID);
    STATE_FILE_PATH = "C:\\MT5_Control\\" + InpUserId + "\\" + STRATEGY_ID + "\\state.json";

    g_uptime_start    = TimeCurrent();
    g_handshake_done  = false;
    g_handshake_sent  = false;
    g_permitted       = false;

    Print("[", STRATEGY_ID, "] Inicializando. User=", InpUserId,
          " Magic=", MAGIC_NUMBER);

    WriteStateReport("READY");
    g_handshake_sent  = true;
    g_handshake_start = TimeCurrent();
    Print("[", STRATEGY_ID, "] Estado READY gravado. Aguardando handshake do backend...");

    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
    Print("[", STRATEGY_ID, "] Desinicializando (motivo=", reason, "). Executando SafeShutdown...");
    g_permitted = false;
    CancelAllMyOrders();
    CloseAllMyPositions();
    WriteStateReport("OFFLINE");
    Print("[", STRATEGY_ID, "] EA encerrado. Estado OFFLINE gravado.");
}

// ─────────────────────────────────────────────────────────────────────────────
// TICK PRINCIPAL — guards + handshake + FSM dispatcher
// ─────────────────────────────────────────────────────────────────────────────
void OnTick()
{
    // ── GUARD 1: Handshake obrigatório (DOC-STRAT-09) ────────────────────────
    if (!g_handshake_done)
    {
        CheckHandshake();
        return;
    }

    // ── GUARD 2: Atualiza estado de controle (DOC-STRAT-02) ──────────────────
    ReadControlFile();

    // ── GUARD 3: Telemetria periódica (DOC-STRAT-05) ─────────────────────────
    WriteStateReport();

    // ── GUARD 4: Anti-rapid-switch local (DOC-STRAT-07) ──────────────────────
    if (g_switch_in_progress && TimeCurrent() < g_switch_blocked_until)
    {
        if (g_manager_state == "ACTIVE")
        {
            Print("[", STRATEGY_ID, "] Bloqueio anti-rapid-switch ativo. ACTIVE ignorado.");
            return;
        }
    }
    if (g_switch_in_progress
        && g_manager_state == "ACTIVE"
        && TimeCurrent() >= g_switch_blocked_until)
    {
        g_switch_in_progress = false;
        Print("[", STRATEGY_ID, "] Bloqueio anti-rapid-switch expirado. Trading retomado.");
    }

    // ── GUARD 5: Kill switch e emergency stop (DOC-STRAT-08) ─────────────────
    if (g_kill_switch)   { SafeShutdown(); return; }
    if (g_emergency_stop){ SafeShutdown(); return; }

    // ── FSM Dispatcher (DOC-STRAT-04) ────────────────────────────────────────
    switch (ParseManagerState(g_manager_state))
    {
        case STATE_IDLE:
            // Parado. Nenhuma execução.
            return;

        case STATE_ACTIVE:
            // Verificações de permissão e risco antes de qualquer entrada
            if (!g_permitted) return;
            if (g_switch_in_progress) return;
            ExecuteStrategy();
            break;

        case STATE_TRANSITION_STATE:
            // Bloqueia novas entradas (DOC-STRAT-07): sem fechar posições ainda
            if (!g_switch_in_progress)
            {
                g_switch_in_progress   = true;
                g_switch_blocked_until = TimeCurrent() + 120;
                g_permitted            = false;
                Print("[", STRATEGY_ID, "] Troca detectada — entradas bloqueadas por 120s.");
            }
            break;

        case STATE_CLOSING_POSITIONS:
            // SafeShutdown() a cada tick até risco zero (DOC-STRAT-03)
            g_permitted = false;
            if (CountMyPositions() > 0 || OrdersTotal() > 0)
                SafeShutdown();
            else
                WriteStateReport("SAFE_TO_SWITCH");
            break;

        case STATE_SAFE_TO_SWITCH:
        case STATE_ACTIVATING_NEW_STRATEGY:
            // Passivo — backend controla o que vem a seguir
            break;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// IMPLEMENTAR AQUI — Lógica de trading da estratégia
// ─────────────────────────────────────────────────────────────────────────────
void ExecuteStrategy()
{
    // ── IsRiskAcceptable antes de qualquer ordem (DOC-STRAT-08) ──────────────
    if (!IsRiskAcceptable()) return;

    //
    // ─── TODO: Inserir lógica original de trading deste EA aqui ─────────────
    //
    // Não chamar esta função diretamente — usar o dispatcher em OnTick().
    // Nunca remover as guards de risco acima.
    //
}

// ─────────────────────────────────────────────────────────────────────────────
// HANDSHAKE (DOC-STRAT-09)
// ─────────────────────────────────────────────────────────────────────────────
void CheckHandshake()
{
    // Timeout de handshake — bloqueia EA definitivamente até reinício
    if (TimeCurrent() - g_handshake_start > g_handshake_timeout_s)
    {
        Print("[", STRATEGY_ID, "] ERRO: Handshake timeout (", g_handshake_timeout_s,
              "s). EA não autorizado. Reinicie após resolver o backend.");
        g_permitted = false;
        WriteStateReport("HANDSHAKE_TIMEOUT");
        return;
    }

    ReadControlFile();

    if (g_permitted && g_manager_state == "ACTIVE")
    {
        g_handshake_done = true;
        Print("[", STRATEGY_ID, "] Handshake concluído | Magic=", MAGIC_NUMBER, " | Trading habilitado.");
        WriteStateReport("RUNNING");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// RISK MANAGER (DOC-STRAT-08)
// ─────────────────────────────────────────────────────────────────────────────
bool IsRiskAcceptable()
{
    // Prioridade 1 — Kill switch: fecha tudo, sem exceção
    if (g_kill_switch)
    {
        Print("[", STRATEGY_ID, "] Kill switch ativo — nenhuma entrada permitida.");
        return false;
    }

    // Prioridade 2 — Emergency stop: SafeShutdown() imediato
    if (g_emergency_stop)
    {
        Print("[", STRATEGY_ID, "] Emergency stop ativo — executando SafeShutdown().");
        SafeShutdown();
        return false;
    }

    // Prioridade 3 — Daily loss limit: bloqueia novas entradas
    if (g_daily_loss_limit > 0.0 && g_daily_loss_current <= -g_daily_loss_limit)
    {
        Print("[", STRATEGY_ID, "] Daily loss limit atingido: ",
              g_daily_loss_current, " / ", -g_daily_loss_limit, " — sem novas entradas.");
        return false;
    }

    // Prioridade 4 — Max drawdown %: bloqueia novas entradas
    if (g_max_drawdown_pct > 0.0)
    {
        double balance = AccountInfoDouble(ACCOUNT_BALANCE);
        if (balance > 0.0)
        {
            double equity       = AccountInfoDouble(ACCOUNT_EQUITY);
            double drawdown_pct = ((balance - equity) / balance) * 100.0;
            if (drawdown_pct >= g_max_drawdown_pct)
            {
                Print("[", STRATEGY_ID, "] Max drawdown atingido: ", drawdown_pct,
                      "% >= limite ", g_max_drawdown_pct, "% — sem novas entradas.");
                return false;
            }
        }
    }

    // Prioridade 5 — Cooldown após loss: pausa temporária
    if (StringLen(g_cooldown_until) > 0)
    {
        Print("[", STRATEGY_ID, "] Cooldown ativo até ", g_cooldown_until, " — sem entradas.");
        return false;
    }

    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// SAFE SHUTDOWN (DOC-STRAT-03)
// ─────────────────────────────────────────────────────────────────────────────
bool SafeShutdown()
{
    Print("[", STRATEGY_ID, "] SafeShutdown() iniciado — bloqueando novas entradas.");
    g_permitted = false;

    CancelAllMyOrders();
    CloseAllMyPositions();

    Sleep(500);
    int remaining = CountMyPositions();

    if (remaining > 0)
    {
        Print("[", STRATEGY_ID, "] AVISO SafeShutdown: ainda há ", remaining, " posição(ões) abertas.");
        WriteStateReport("SHUTDOWN_PENDING");
        return false;
    }

    Print("[", STRATEGY_ID, "] SafeShutdown concluído. Risco = ZERO.");
    WriteStateReport("SHUTDOWN_COMPLETE");
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// STATE REPORT (DOC-STRAT-05)
// ─────────────────────────────────────────────────────────────────────────────
void WriteStateReport(string forced_status = "")
{
    if (forced_status == "" && TimeCurrent() - g_state_last_write < 5)
        return;
    g_state_last_write = TimeCurrent();

    int    open_pos   = CountMyPositions();
    double unrealized = CalculateUnrealizedPnL();
    double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
    int    uptime     = (int)(TimeCurrent() - g_uptime_start);
    string status     = forced_status != "" ? forced_status
                                            : (g_permitted ? "RUNNING" : "PAUSED");

    string state_str = ""
        + "{\"strategy_id\":\"" + STRATEGY_ID + "\","
        + "\"magic_number\":" + IntegerToString(MAGIC_NUMBER) + ","
        + "\"status\":\"" + status + "\","
        + "\"manager_state_local\":\"" + g_manager_state + "\","
        + "\"permitted\":" + (g_permitted ? "true" : "false") + ","
        + "\"kill_switch_active\":" + (g_kill_switch ? "true" : "false") + ","
        + "\"open_positions\":" + IntegerToString(open_pos) + ","
        + "\"open_orders\":" + IntegerToString(OrdersTotal()) + ","
        + "\"unrealized_pnl\":" + DoubleToString(unrealized, 2) + ","
        + "\"account_balance\":" + DoubleToString(balance, 2) + ","
        + "\"account_equity\":" + DoubleToString(equity, 2) + ","
        + "\"heartbeat\":\"" + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) + "\","
        + "\"uptime_seconds\":" + IntegerToString(uptime)
        + "}";

    int h = FileOpen(STATE_FILE_PATH, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if (h == INVALID_HANDLE)
    {
        Print("[", STRATEGY_ID, "] ERRO: Não foi possível gravar state.json em: ", STATE_FILE_PATH);
        return;
    }
    FileWriteString(h, state_str);
    FileClose(h);
}

// ─────────────────────────────────────────────────────────────────────────────
// FILTROS POR MAGIC NUMBER (DOC-STRAT-06)
// ─────────────────────────────────────────────────────────────────────────────

int CountMyPositions()
{
    int n = 0;
    for (int i = 0; i < PositionsTotal(); i++)
        if (PositionGetTicket(i) > 0 && PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
            n++;
    return n;
}

double CalculateUnrealizedPnL()
{
    double total = 0.0;
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (!PositionSelectByIndex(i)) continue;
        if (PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
            total += PositionGetDouble(POSITION_PROFIT);
    }
    return total;
}

bool CloseAllMyPositions()
{
    bool all_ok = true;
    for (int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if (!PositionSelectByIndex(i)) continue;
        if (PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;

        ulong  ticket = (ulong)PositionGetInteger(POSITION_TICKET);
        string symbol = PositionGetString(POSITION_SYMBOL);
        double volume = PositionGetDouble(POSITION_VOLUME);
        ENUM_POSITION_TYPE tipo = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        MqlTradeRequest req = {};
        MqlTradeResult  res = {};
        req.action    = TRADE_ACTION_DEAL;
        req.position  = ticket;
        req.symbol    = symbol;
        req.volume    = volume;
        req.type      = (tipo == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
        req.price     = (tipo == POSITION_TYPE_BUY)
                        ? SymbolInfoDouble(symbol, SYMBOL_BID)
                        : SymbolInfoDouble(symbol, SYMBOL_ASK);
        req.deviation = 20;
        req.magic     = MAGIC_NUMBER;
        req.comment   = "STRATEGY_SWITCH";

        if (!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
        {
            Print("[", STRATEGY_ID, "] Falha ao fechar #", ticket, " retcode=", res.retcode);
            all_ok = false;
        }
        else
            Print("[", STRATEGY_ID, "] Posição fechada: #", ticket, " sym=", symbol, " vol=", volume);
    }
    return all_ok;
}

void CancelAllMyOrders()
{
    for (int i = OrdersTotal() - 1; i >= 0; i--)
    {
        ulong ticket = OrderGetTicket(i);
        if (ticket == 0) continue;
        if (OrderGetInteger(ORDER_MAGIC) != MAGIC_NUMBER) continue;

        MqlTradeRequest req = {};
        MqlTradeResult  res = {};
        req.action = TRADE_ACTION_REMOVE;
        req.order  = ticket;

        if (!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
            Print("[", STRATEGY_ID, "] Falha ao cancelar ordem #", ticket, " retcode=", res.retcode);
        else
            Print("[", STRATEGY_ID, "] Ordem cancelada: #", ticket);
    }
}
