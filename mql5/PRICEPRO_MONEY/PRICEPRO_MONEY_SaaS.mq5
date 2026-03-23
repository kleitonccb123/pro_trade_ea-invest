//+------------------------------------------------------------------+
//| PRICEPRO_MONEY_SaaS.mq5                                          |
//| PRICEPRO_MONEY-EA — Versão integrada ao SaaS Strategy Manager    |
//| Crypto Trade Hub                                                 |
//| Versão: 1.8 | DOC-STRAT-02/03/04/05/06/07/08/09                  |
//|                                                                  |
//| Implementa:                                                      |
//|   DOC-STRAT-02 — Controle Externo de Ativação (control.json)     |
//|   DOC-STRAT-03 — Modo SAFE SHUTDOWN                              |
//|   DOC-STRAT-04 — Integração com Strategy Manager (FSM dispatcher)|
//|   DOC-STRAT-05 — Sincronização de Estado (state.json completo)   |
//|   DOC-STRAT-06 — Isolamento por Magic Number (filtros exclusivos) |
//|   DOC-STRAT-07 — Bloqueio Anti-Rapid-Switch (2 camadas)          |
//|   DOC-STRAT-08 — Integração com Risk Manager (kill/loss/cooldown) |
//|   DOC-STRAT-09 — Handshake de Ativação (READY → RUNNING)         |
//|                                                                  |
//| Arquivos de controle:                                            |
//|   Leitura: C:\MT5_Control\<user_id>\pricepro_money_v1\control.json  |
//|   Escrita: C:\MT5_Control\<user_id>\pricepro_money_v1\state.json    |
//+------------------------------------------------------------------+

#property copyright "Crypto Trade Hub"
#property version   "1.00"
#property strict

// ─── Includes ─────────────────────────────────────────────────────────────────
#include "..\include\JSONParser.mqh"
#include "..\include\SaaSControlReader.mqh"

// ─── Identificadores da estratégia (DOC-STRAT-01 / DOC-STRAT-06) ─────────────
#define STRATEGY_ID   "pricepro_money_v1"
#define MAGIC_NUMBER  20240001
// Convenção Magic Number: YYYYMMNN (2024 = ano de criação, 01 = seq. da estratégia)
// Tabela de magic numbers reservados — não reutilizar:
//   20240001 — PRICEPRO_MONEY-EA        (este EA)
//   20240002 — (próxima estratégia)
//   20240003 — (grid trader)

// ─── Inputs do EA ─────────────────────────────────────────────────────────────

// ID do usuário no backend — preenchido pelo operador ao instalar o EA
input string InpUserId        = "replace_with_user_id";   // USER ID (backend)

// Fallback de emergência LOCAL (DOC-STRAT-02 §2.5):
// Somente para uso em caso de falha total do backend enquanto o EA ainda está rodando.
// Em operação normal deve permanecer false.
input bool   InpEmergencyLocal = false;   // Fallback local de emergência

// ─── Estado global do handshake (DOC-STRAT-09) ───────────────────────────────
bool     g_handshake_done       = false;
bool     g_handshake_sent       = false;
datetime g_handshake_start      = 0;
int      g_handshake_timeout_s  = 30;

// ─── Estado do anti-rapid-switch local (DOC-STRAT-07) ────────────────────────
bool     g_switch_in_progress     = false;
datetime g_switch_blocked_until   = 0;

// ─── Tempo de início para uptime ─────────────────────────────────────────────
datetime g_uptime_start           = 0;
datetime g_state_last_write       = 0;

// ─── Telemetria de estado (DOC-STRAT-05) ─────────────────────────────────────
double   g_max_drawdown_today     = 0.0;  // pior drawdown flutuante do dia (sempre ≤ 0)
string   g_last_trade_open        = "";   // ISO timestamp da última abertura do dia
string   g_last_trade_close       = "";   // ISO timestamp do último fechamento do dia

// ─── Caminho do arquivo de estado ────────────────────────────────────────────
string   STATE_FILE_PATH          = "";

// ─── Enumeração dos estados do FSM (DOC-STRAT-04 §4.3) ───────────────────────
// Espelha exatamente o StrategyState do backend Python (strategy_manager.py)
enum EManagerState
{
    STATE_IDLE,                    // Parado — nenhuma execução
    STATE_ACTIVE,                  // Operação normal habilitada
    STATE_TRANSITION_STATE,        // Bloqueio de novas entradas; posições mantidas
    STATE_CLOSING_POSITIONS,       // SafeShutdown() loop até risco zero
    STATE_SAFE_TO_SWITCH,          // EA inativo; risco = 0 confirmado
    STATE_ACTIVATING_NEW_STRATEGY  // Aguarda handshake do novo (ou este EA desativado)
};

//─────────────────────────────────────────────────────────────────────────────
/// Converte a string recebida do control.json em EManagerState.
/// Qualquer estado desconhecido retorna STATE_IDLE (fail-safe).
//─────────────────────────────────────────────────────────────────────────────
EManagerState ParseManagerState(const string state)
{
    if (state == "ACTIVE")                  return STATE_ACTIVE;
    if (state == "TRANSITION_STATE")        return STATE_TRANSITION_STATE;
    if (state == "CLOSING_POSITIONS")       return STATE_CLOSING_POSITIONS;
    if (state == "SAFE_TO_SWITCH")          return STATE_SAFE_TO_SWITCH;
    if (state == "ACTIVATING_NEW_STRATEGY") return STATE_ACTIVATING_NEW_STRATEGY;
    return STATE_IDLE;  // "IDLE" e qualquer valor inesperado → fail-safe
}


//+------------------------------------------------------------------+
//| OnInit — Inicialização do EA                                     |
//+------------------------------------------------------------------+
int OnInit()
{
    // Inicializa caminhos de controle e estado
    InitControlPaths(InpUserId, STRATEGY_ID);
    STATE_FILE_PATH = "C:\\MT5_Control\\" + InpUserId + "\\" + STRATEGY_ID + "\\state.json";

    g_uptime_start    = TimeCurrent();
    g_handshake_done  = false;
    g_handshake_sent  = false;
    g_permitted       = false;

    Print("[PRICEPRO] Inicializando. User=", InpUserId,
          " Magic=", MAGIC_NUMBER,
          " Strategy=", STRATEGY_ID);

    // Primeira escrita de estado: notifica backend que EA está vivo
    WriteStateReport("READY");
    g_handshake_sent = true;
    g_handshake_start = TimeCurrent();
    Print("[PRICEPRO] Estado READY gravado. Aguardando handshake do backend...");

    return INIT_SUCCEEDED;
}


//+------------------------------------------------------------------+
//| OnDeinit — Desinicialização segura                               |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("[PRICEPRO] Desinicializando (motivo=", reason, "). Executando SafeShutdown...");

    g_permitted = false;
    CancelAllMyOrders();
    CloseAllMyPositions();

    WriteStateReport("OFFLINE");
    Print("[PRICEPRO] EA encerrado. Estado OFFLINE gravado.");
}


//+------------------------------------------------------------------+
//| OnTick — Controlador principal: guards + FSM dispatcher          |
//| DOC-STRAT-02 (controle) │ DOC-STRAT-03 (shutdown)               |
//| DOC-STRAT-04 (dispatcher FSM) │ DOC-STRAT-09 (handshake)        |
//+------------------------------------------------------------------+
void OnTick()
{
    // ── GUARD 1: Handshake obrigatório (DOC-STRAT-09) ────────────────────────
    // EA não executa nenhuma lógica até o backend confirmar READY → ACTIVE.
    if (!g_handshake_done)
    {
        CheckHandshake();
        return;
    }

    // ── GUARD 2: Lê arquivo de controle com debounce 1s (DOC-STRAT-02 §2.3) ──
    ReadControlFile();

    // ── GUARD 3: Grava estado periódico a cada 5s (DOC-STRAT-05) ─────────────
    WriteStateReport();

    // ── GUARD 4: Kill Switch — prioridade máxima (DOC-STRAT-08 §8.4 P1) ──────
    if (g_kill_switch || (InpEmergencyLocal && !g_permitted))
    {
        Print("[PRICEPRO] Kill switch ativo | SafeShutdown imediato.");
        SafeShutdown();
        return;
    }

    // ── GUARD 5: Emergency Stop (DOC-STRAT-08 §8.4 P2) ───────────────────────
    if (g_emergency_stop)
    {
        Print("[PRICEPRO] Emergency stop recebido | SafeShutdown imediato.");
        SafeShutdown();
        return;
    }

    // ── DISPATCHER FSM (DOC-STRAT-04 §4.3) ───────────────────────────────────
    // Cada case corresponde exatamente a um estado do StrategyState Python.
    switch (ParseManagerState(g_manager_state))
    {
        // ── IDLE: EA completamente parado — nenhuma execução ─────────────────
        case STATE_IDLE:
            return;

        // ── ACTIVE: Operação normal; anti-rapid-switch + permissão verificados ─
        case STATE_ACTIVE:
            // Guard kill switch no estado ACTIVE (redundante mas explícito)
            if (g_kill_switch) { SafeShutdown(); return; }

            // Anti-rapid-switch local (DOC-STRAT-07 §7.3)
            if (g_switch_in_progress)
            {
                if (TimeCurrent() < g_switch_blocked_until)
                {
                    // Backend voltou ACTIVE mas bloqueio local ainda vigora
                    Print("[PRICEPRO] Bloqueio anti-rapid-switch ativo. ACTIVE ignorado.");
                    return;
                }
                // Bloqueio expirado — retoma operação normal
                g_switch_in_progress = false;
                Print("[PRICEPRO] Bloqueio anti-rapid-switch expirado. Trading retomado.");
            }

            // Sem permissão explícita do backend → aguarda
            if (!g_permitted) return;

            // Tudo ok — executa a lógica de trading
            ExecuteStrategy();
            break;

        // ── TRANSITION_STATE: Bloqueia entradas; mantém posições abertas ──────
        case STATE_TRANSITION_STATE:
            // Ativa bloqueio local ao detectar a primeira vez (DOC-STRAT-07 §7.3)
            if (!g_switch_in_progress)
                OnSwitchDetected();
            // Não fecha posições ainda: aguarda CLOSING_POSITIONS
            break;

        // ── CLOSING_POSITIONS: SafeShutdown() loop até risco zero ─────────────
        case STATE_CLOSING_POSITIONS:
            g_permitted = false;
            if (CountMyPositions() > 0 || OrdersTotal() > 0)
                SafeShutdown();  // retry automático a cada tick (DOC-STRAT-03 §3.3)
            else
                WriteStateReport("SAFE_TO_SWITCH", 0);  // confirma risco zero ao backend
            break;

        // ── SAFE_TO_SWITCH: EA inativo, risco = 0 confirmado ─────────────────
        case STATE_SAFE_TO_SWITCH:
            // Nada a fazer. Backend controla o próximo passo.
            break;

        // ── ACTIVATING_NEW_STRATEGY: EA anterior parado ou novo aguarda ───────
        case STATE_ACTIVATING_NEW_STRATEGY:
            // Não operar. Handshake do novo EA em andamento.
            break;
    }
}


//+------------------------------------------------------------------+
//| OnSwitchDetected — Ativado ao detectar TRANSITION_STATE          |
//| (DOC-STRAT-07 §7.3 — Camada 2: Bloqueio Local de Reentrada)     |
//+------------------------------------------------------------------+
void OnSwitchDetected()
{
    g_switch_in_progress   = true;
    g_permitted            = false;
    g_switch_blocked_until = TimeCurrent() + 120;  // bloqueio local de 2 minutos

    Print("[PRICEPRO] Troca de estratégia detectada — entradas bloqueadas até ",
          TimeToString(g_switch_blocked_until, TIME_DATE | TIME_SECONDS));
}


//+------------------------------------------------------------------+
//| CheckHandshake — Verifica confirmação do backend (DOC-STRAT-09)  |
//+------------------------------------------------------------------+
void CheckHandshake()
{
    // Timeout de handshake
    if (TimeCurrent() - g_handshake_start > g_handshake_timeout_s)
    {
        Print("[PRICEPRO] ERRO: Handshake timeout (", g_handshake_timeout_s,
              "s). EA não autorizado a operar. Reinicie o EA após resolver o backend.");
        g_permitted = false;
        WriteStateReport("HANDSHAKE_TIMEOUT");
        return;
    }

    // Tenta ler o arquivo de controle para ver se backend respondeu
    ReadControlFile();

    if (g_permitted && g_manager_state == "ACTIVE")
    {
        g_handshake_done = true;
        Print("[PRICEPRO] Handshake concluído | Trading habilitado | Magic=", MAGIC_NUMBER);
        WriteStateReport("RUNNING");
    }
}


//+------------------------------------------------------------------+
//| ExecuteStrategy — Lógica de trading do PRICEPRO MONEY            |
//| TODO: Inserir a lógica original do PRICEPRO_MONEY-EA aqui        |
//+------------------------------------------------------------------+
void ExecuteStrategy()
{
    // ── IsRiskAcceptable antes de qualquer ordem (DOC-STRAT-08) ──────────────
    if (!IsRiskAcceptable()) return;

    //
    // ─── INÍCIO DA LÓGICA ORIGINAL DO PRICEPRO_MONEY-EA ─────────────────────
    //
    // Inserir aqui o código de análise de mercado, sinais de entrada
    // e gerenciamento de posições do PRICEPRO_MONEY-EA original.
    //
    // Nunca remover as guards acima (IsRiskAcceptable, g_permitted,
    // g_kill_switch, g_manager_state) — são o contrato com o SaaS.
    //
    // ─── FIM DA LÓGICA ORIGINAL ────────────────────────────────────────────
}


//+------------------------------------------------------------------+
//| IsRiskAcceptable — Verifica limites do Risk Manager (DOC-STRAT-08)|
//+------------------------------------------------------------------+
bool IsRiskAcceptable()
{
    // Prioridade 1 — Kill switch: fecha tudo, sem exceção
    if (g_kill_switch)
    {
        Print("[PRICEPRO] Kill switch ativo — nenhuma entrada permitida.");
        return false;
    }

    // Prioridade 2 — Emergency stop: SafeShutdown() imediato
    // Usa variável g_emergency_stop lida de control.json por ReadControlFile()
    // (nunca reler o arquivo aqui — evita I/O duplo por tick)
    if (g_emergency_stop)
    {
        Print("[PRICEPRO] Emergency stop ativo — executando SafeShutdown().");
        SafeShutdown();
        return false;
    }

    // Prioridade 3 — Daily loss limit: bloqueia novas entradas
    if (g_daily_loss_limit > 0.0 && g_daily_loss_current <= -g_daily_loss_limit)
    {
        Print("[PRICEPRO] Daily loss limit atingido: ",
              g_daily_loss_current, " / ", -g_daily_loss_limit, " — sem novas entradas.");
        return false;
    }

    // Prioridade 4 — Max drawdown %: bloqueia novas entradas
    if (g_max_drawdown_pct > 0.0)
    {
        double balance = AccountInfoDouble(ACCOUNT_BALANCE);
        if (balance > 0.0)
        {
            double drawdown_pct = (-g_max_drawdown_today / balance) * 100.0;
            if (drawdown_pct >= g_max_drawdown_pct)
            {
                Print("[PRICEPRO] Max drawdown atingido: ", drawdown_pct,
                      "% >= limite ", g_max_drawdown_pct, "% — sem novas entradas.");
                return false;
            }
        }
    }

    // Prioridade 5 — Cooldown após loss: pausa temporária
    if (StringLen(g_cooldown_until) > 0)
    {
        Print("[PRICEPRO] Cooldown ativo até ", g_cooldown_until, " — sem entradas.");
        return false;
    }

    return true;
}


//+------------------------------------------------------------------+
//| SafeShutdown — Encerramento seguro (DOC-STRAT-03)               |
//| Contrato:                                                        |
//|   1. Bloqueia novas entradas imediatamente                       |
//|   2. Cancela todas as ordens pendentes deste magic               |
//|   3. Fecha todas as posições abertas deste magic                 |
//|   4. Confirma risco zero (CountMyPositions() == 0)               |
//|   5. Grava relatório de estado (SHUTDOWN_COMPLETE / PENDING)     |
//|   6. Retorna true se risco zero, false se posições restantes     |
//+------------------------------------------------------------------+
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

        MqlTradeRequest req_o = {};
        MqlTradeResult  res_o = {};
        req_o.action = TRADE_ACTION_REMOVE;
        req_o.order  = ticket;

        bool ok_o = OrderSend(req_o, res_o);
        if (!ok_o || res_o.retcode != TRADE_RETCODE_DONE)
            Print("[PRICEPRO] AVISO: Falha ao cancelar ordem #", ticket,
                  " retcode=", res_o.retcode);
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

        string             symbol   = PositionGetString(POSITION_SYMBOL);
        double             volume   = PositionGetDouble(POSITION_VOLUME);
        ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        MqlTradeRequest req_p = {};
        MqlTradeResult  res_p = {};
        req_p.action    = TRADE_ACTION_DEAL;
        req_p.position  = ticket;
        req_p.symbol    = symbol;
        req_p.volume    = volume;
        req_p.deviation = 20;
        req_p.magic     = MAGIC_NUMBER;
        req_p.comment   = "SAFE_SHUTDOWN";
        req_p.type      = (pos_type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
        req_p.price     = (pos_type == POSITION_TYPE_BUY)
                          ? SymbolInfoDouble(symbol, SYMBOL_BID)
                          : SymbolInfoDouble(symbol, SYMBOL_ASK);

        bool ok_p = OrderSend(req_p, res_p);
        if (!ok_p || res_p.retcode != TRADE_RETCODE_DONE)
            Print("[PRICEPRO] AVISO: Falha ao fechar posição #", ticket,
                  " retcode=", res_p.retcode);
        else
            Print("[PRICEPRO] Posição fechada: #", ticket,
                  " vol=", volume, " sym=", symbol);
    }

    // ── PASSO 3: Aguardar processamento da exchange ───────────────────────────
    Sleep(500);

    // ── PASSO 4: Confirmar risco zero ─────────────────────────────────────────
    int remaining = CountMyPositions();
    if (remaining > 0)
    {
        Print("[PRICEPRO] AVISO SafeShutdown: ainda há ", remaining, " posição(ões) abertas.");
        WriteStateReport("SHUTDOWN_PENDING", remaining);
        return false;
    }

    // ── PASSO 5: Confirmar encerramento completo ──────────────────────────────
    Print("[PRICEPRO] SafeShutdown concluído. Risco = ZERO.");
    WriteStateReport("SHUTDOWN_COMPLETE", 0);
    return true;
}


//+------------------------------------------------------------------+
//| CountMyPositions — Conta posições deste magic (DOC-STRAT-06)    |
//+------------------------------------------------------------------+
int CountMyPositions()
{
    int count = 0;
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (PositionGetTicket(i) > 0 &&
            PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
            count++;
    }
    return count;
}


//+------------------------------------------------------------------+
//| CloseAllMyPositions — Fecha posições deste magic (DOC-STRAT-06) |
//+------------------------------------------------------------------+
bool CloseAllMyPositions()
{
    bool all_ok = true;
    for (int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if (!PositionSelectByIndex(i)) continue;
        if (PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;

        ulong  ticket  = PositionGetInteger(POSITION_TICKET);
        string symbol  = PositionGetString(POSITION_SYMBOL);
        double volume  = PositionGetDouble(POSITION_VOLUME);
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
        req.comment   = "SAFE_SHUTDOWN";

        if (!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
        {
            Print("[PRICEPRO] Falha ao fechar #", ticket, " retcode=", res.retcode);
            all_ok = false;
        }
        else
            Print("[PRICEPRO] Posição fechada: #", ticket, " vol=", volume, " sym=", symbol);
    }
    return all_ok;
}


//+------------------------------------------------------------------+
//| CancelAllMyOrders — Cancela ordens pendentes deste magic         |
//+------------------------------------------------------------------+
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
            Print("[PRICEPRO] Falha ao cancelar ordem #", ticket, " retcode=", res.retcode);
        else
            Print("[PRICEPRO] Ordem pendente cancelada: #", ticket);
    }
}


//+------------------------------------------------------------------+
//| CalculateUnrealizedPnL — PnL não realizado deste magic           |
//+------------------------------------------------------------------+
double CalculateUnrealizedPnL()
{
    double total = 0.0;
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (!PositionSelectByIndex(i)) continue;
        if (PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;
        total += PositionGetDouble(POSITION_PROFIT);
    }
    return total;
}


//+------------------------------------------------------------------+
//| CalculateRealizedPnLToday — PnL realizado hoje para este magic   |
//| Atualiza g_last_trade_open e g_last_trade_close como efeito col. |
//| (DOC-STRAT-05 §5.2)                                              |
//+------------------------------------------------------------------+
double CalculateRealizedPnLToday()
{
    double total = 0.0;

    // Reseta timestamps — serão preenchidos pela iteração abaixo
    g_last_trade_open  = "";
    g_last_trade_close = "";

    // Seleciona histórico desde a meia-noite UTC do dia corrente
    datetime day_start = (datetime)((long)TimeCurrent() - (long)TimeCurrent() % 86400);
    if (!HistorySelect(day_start, TimeCurrent()))
        return 0.0;

    int deals = HistoryDealsTotal();
    // Itera do mais recente para o mais antigo (captura o último first)
    for (int i = deals - 1; i >= 0; i--)
    {
        ulong ticket = HistoryDealGetTicket(i);
        if (ticket == 0) continue;
        if ((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != MAGIC_NUMBER) continue;

        ENUM_DEAL_ENTRY entry     = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
        datetime        deal_time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);

        // Converte para ISO-like: "YYYY-MM-DDTHH:MM:SS"
        string ts = TimeToString(deal_time, TIME_DATE | TIME_SECONDS);
        StringReplace(ts, ".", "-");
        StringReplace(ts, " ", "T");

        // Captura o timestamp mais recente de cada tipo
        if (entry == DEAL_ENTRY_IN && g_last_trade_open == "")
            g_last_trade_open = ts;
        if ((entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT) && g_last_trade_close == "")
            g_last_trade_close = ts;

        // Acumula PnL dos encerramentos
        if (entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT)
            total += HistoryDealGetDouble(ticket, DEAL_PROFIT);
    }
    return total;
}


//+------------------------------------------------------------------+
//| WriteStateReport — Grava state.json para o backend (DOC-STRAT-05)|
//| @param forced_status    Se não vazio, substitui o status derivado |
//| @param forced_positions Se >= 0, usa este valor para open_pos     |
//|                         (usado por SafeShutdown após fechar tudo) |
//+------------------------------------------------------------------+
void WriteStateReport(const string forced_status = "", const int forced_positions = -1)
{
    // Debounce: grava a cada 5 segundos ou quando forcado
    if (StringLen(forced_status) == 0 && TimeCurrent() - g_state_last_write < 5)
        return;

    g_state_last_write = TimeCurrent();

    // Usa contagem forçada (passada por SafeShutdown) ou conta em tempo real
    int    open_pos   = (forced_positions >= 0) ? forced_positions : CountMyPositions();
    double unrealized = CalculateUnrealizedPnL();
    double realized   = CalculateRealizedPnLToday();   // também atualiza g_last_trade_*
    double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
    double drawdown   = equity - balance;
    int    uptime     = (int)(TimeCurrent() - g_uptime_start);
    string ts         = TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS);
    // Normaliza para ISO-like (MT5 usa "YYYY.MM.DD HH:MM:SS")
    StringReplace(ts, ".", "-");
    StringReplace(ts, " ", "T");

    // Rastreia o pior drawdown flutuante do dia (sempre negativo ou zero)
    if (drawdown < g_max_drawdown_today)
        g_max_drawdown_today = drawdown;

    string status;
    if (StringLen(forced_status) > 0)
        status = forced_status;
    else if (g_kill_switch)
        status = "EMERGENCY_STOP";
    else if (!g_permitted)
        status = "PAUSED";
    else
        status = "RUNNING";

    string json = ""
        + "{"
        + "\"strategy_id\":\"" + STRATEGY_ID + "\","
        + "\"magic_number\":" + IntegerToString(MAGIC_NUMBER) + ","
        + "\"status\":\"" + status + "\","
        + "\"manager_state_local\":\"" + g_manager_state + "\","
        + "\"permitted\":" + (g_permitted ? "true" : "false") + ","
        + "\"kill_switch_active\":" + (g_kill_switch ? "true" : "false") + ","
        + "\"open_positions\":" + IntegerToString(open_pos) + ","
        + "\"open_orders\":" + IntegerToString(OrdersTotal()) + ","
        + "\"unrealized_pnl\":" + DoubleToString(unrealized, 2) + ","
        + "\"realized_pnl_today\":" + DoubleToString(realized, 2) + ","
        + "\"floating_drawdown\":" + DoubleToString(drawdown, 2) + ","
        + "\"max_drawdown_today\":" + DoubleToString(g_max_drawdown_today, 2) + ","
        + "\"last_trade_open\":\"" + g_last_trade_open + "\","
        + "\"last_trade_close\":\"" + g_last_trade_close + "\","
        + "\"account_balance\":" + DoubleToString(balance, 2) + ","
        + "\"account_equity\":" + DoubleToString(equity, 2) + ","
        + "\"heartbeat\":\"" + ts + "\","
        + "\"uptime_seconds\":" + IntegerToString(uptime)
        + "}";

    if (StringLen(STATE_FILE_PATH) == 0)
    {
        Print("[PRICEPRO] ERRO: STATE_FILE_PATH não inicializado.");
        return;
    }

    int handle = FileOpen(STATE_FILE_PATH, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
    if (handle == INVALID_HANDLE)
    {
        Print("[PRICEPRO] ERRO: Não foi possível gravar state.json em: ", STATE_FILE_PATH);
        return;
    }
    FileWriteString(handle, json);
    FileClose(handle);
}
