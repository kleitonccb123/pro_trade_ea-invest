//+------------------------------------------------------------------+
//| SaaSControlReader.mqh — Leitura do arquivo de controle do SaaS  |
//| Crypto Trade Hub — SaaS Strategy Manager                         |
//| Versão: 1.0 | DOC-STRAT-02                                       |
//|                                                                  |
//| Este include prover:                                             |
//|   • Variáveis globais de controle (g_permitted, g_kill_switch…)  |
//|   • ReadControlFile() — lê control.json com debounce de 1s       |
//|   • Leitura de campos de risco (daily_loss_limit, drawdown…)     |
//|                                                                  |
//| Uso no EA principal:                                             |
//|   #include "JSONParser.mqh"                                      |
//|   #include "SaaSControlReader.mqh"                               |
//|   // Antes de usar, definir:                                     |
//|   //   #define STRATEGY_ID  "pricepro_money_v1"                  |
//|   //   #define USER_ID      "user_abc123"                        |
//+------------------------------------------------------------------+

#property strict

// ─── Dependência ──────────────────────────────────────────────────────────────
#ifndef JSONPARSER_MQH_INCLUDED
    #define JSONPARSER_MQH_INCLUDED
    #include "JSONParser.mqh"
#endif

// ─── Variáveis globais de controle (DOC-STRAT-02 §2.3) ───────────────────────

// Permissão de entrada — True = EA pode abrir novas posições
bool     g_permitted            = false;

// Kill switch global — True = fechar tudo imediatamente, sem exceção
bool     g_kill_switch          = false;

// Emergency stop — True = aciona SafeShutdown() imediato
bool     g_emergency_stop       = false;

// Estado atual do StrategyManager no backend
string   g_manager_state        = "IDLE";

// Último número de sequência processado (evita reprocessar arquivo antigo)
int      g_last_sequence        = -1;

// Timestamp da última leitura de controle (debounce de 1s)
datetime g_control_last_read    = 0;

// ─── Variáveis de risco (DOC-STRAT-08 §8.2) ──────────────────────────────────

// Limite de perda diária em moeda da conta (0 = sem limite)
double   g_daily_loss_limit     = 0.0;

// Perda acumulada hoje conforme reportado pelo backend
double   g_daily_loss_current   = 0.0;

// Drawdown máximo permitido em % do balanço (0 = sem limite)
double   g_max_drawdown_pct     = 0.0;

// Cooldown até timestamp ISO8601 (string vazia = sem cooldown)
string   g_cooldown_until       = "";

// ─── Caminho do arquivo de controle ──────────────────────────────────────────
// Montado dinamicamente em InitControlPaths() para evitar concatenação em
// variável global inicializada (MQL5 não suporta inicializadores dinâmicos).
string   CONTROL_FILE_PATH      = "";


//─────────────────────────────────────────────────────────────────────────────
/// Inicializa o caminho do arquivo de controle.
/// Chame em OnInit() ANTES de qualquer ReadControlFile().
///
/// @param user_id       ID do usuário no backend (ex: "abc123")
/// @param strategy_id   ID da estratégia (ex: "pricepro_money_v1")
//─────────────────────────────────────────────────────────────────────────────
void InitControlPaths(const string user_id, const string strategy_id)
{
    CONTROL_FILE_PATH = "C:\\MT5_Control\\" + user_id + "\\" + strategy_id + "\\control.json";
    Print("[SaaS] Caminho de controle inicializado: ", CONTROL_FILE_PATH);
}


//─────────────────────────────────────────────────────────────────────────────
/// Lê o arquivo de controle gravado pelo backend Python (EAController).
/// Deve ser chamado no início de OnTick().
///
/// Debounce: lê no máximo uma vez por segundo para evitar I/O excessivo.
/// Fail-safe: se o arquivo não existir, bloqueia operação (g_permitted=false).
/// Anti-stale: ignora arquivos com sequência <= último processado.
///
/// @return true se leitura bem-sucedida (ou debounce ativo), false se erro
//─────────────────────────────────────────────────────────────────────────────
bool ReadControlFile()
{
    // ── Debounce: máximo 1 leitura por segundo ────────────────────────────────
    if (TimeCurrent() - g_control_last_read < 1)
        return true;

    g_control_last_read = TimeCurrent();

    // ── Validação do caminho ──────────────────────────────────────────────────
    if (StringLen(CONTROL_FILE_PATH) == 0)
    {
        Print("[SaaS] ERRO: CONTROL_FILE_PATH não inicializado. Chame InitControlPaths() em OnInit().");
        g_permitted   = false;
        g_kill_switch = true;
        return false;
    }

    // ── Abertura do arquivo ───────────────────────────────────────────────────
    // FILE_COMMON: busca na pasta comum do MT5 (MQL5/Files/Common), não na
    // pasta do EA. Necessário para o backend gravar fora do sandbox MT5.
    int handle = FileOpen(CONTROL_FILE_PATH, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);

    if (handle == INVALID_HANDLE)
    {
        // Arquivo ausente = fail-safe: bloqueia operação
        Print("[SaaS] AVISO: Arquivo de controle não encontrado em: ", CONTROL_FILE_PATH,
              " | Operação bloqueada (fail-safe).");
        g_permitted   = false;
        g_kill_switch = true;
        return false;
    }

    // ── Leitura do conteúdo completo ──────────────────────────────────────────
    string content = "";
    while (!FileIsEnding(handle))
        content += FileReadString(handle);
    FileClose(handle);

    if (StringLen(content) == 0)
    {
        Print("[SaaS] AVISO: Arquivo de controle está vazio. Mantendo estado anterior.");
        return false;
    }

    // ── Verificação de sequência (anti-stale) ─────────────────────────────────
    int seq = (int)ParseJSONInt(content, "sequence");
    if (seq <= g_last_sequence)
    {
        // Arquivo não foi atualizado pelo backend — manter estado anterior
        Print("[SaaS] Arquivo de controle não atualizado (seq=", seq,
              " <= last=", g_last_sequence, "). Mantendo estado.");
        return true;
    }

    // ── Parse dos campos de controle ──────────────────────────────────────────
    g_last_sequence   = seq;
    g_permitted       = ParseJSONBool(content, "permitted");
    g_kill_switch     = ParseJSONBool(content, "kill_switch");
    g_emergency_stop  = ParseJSONBool(content, "emergency_stop");
    g_manager_state   = ParseJSONString(content, "manager_state");

    // ── Parse dos campos de risco (DOC-STRAT-08) ──────────────────────────────
    double dl = ParseJSONDouble(content, "daily_loss_limit");
    if (dl > 0.0) g_daily_loss_limit = dl;

    double dc = ParseJSONDouble(content, "daily_loss_current");
    g_daily_loss_current = dc;

    double dd = ParseJSONDouble(content, "max_drawdown_pct");
    if (dd > 0.0) g_max_drawdown_pct = dd;

    string cu = ParseJSONString(content, "cooldown_until");
    if (cu != "null") g_cooldown_until = cu;
    else              g_cooldown_until = "";

    // ── Log de atualização ────────────────────────────────────────────────────
    Print("[SaaS] Controle atualizado"
          " | seq=",      seq,
          " | permitted=", (string)g_permitted,
          " | kill=",      (string)g_kill_switch,
          " | emer=",      (string)g_emergency_stop,
          " | state=",     g_manager_state);

    return true;
}
