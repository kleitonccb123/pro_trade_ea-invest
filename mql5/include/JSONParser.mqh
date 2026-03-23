//+------------------------------------------------------------------+
//| JSONParser.mqh — Parser JSON minimalista para MQL5               |
//| Crypto Trade Hub — SaaS Strategy Manager                         |
//| Versão: 1.0 | DOC-STRAT-02                                       |
//|                                                                  |
//| Extrai valores de campos de JSON usando busca de string simples. |
//| Não suporta arrays aninhados ou objetos profundos.               |
//| Para produção com estruturas complexas, usar JAson.mqh (MQL5 MQ) |
//+------------------------------------------------------------------+

#property strict

//─────────────────────────────────────────────────────────────────────────────
// Extrai o valor string de um campo JSON.
// Exemplo: {"manager_state":"ACTIVE"} → ParseJSONString(json,"manager_state") → "ACTIVE"
//─────────────────────────────────────────────────────────────────────────────
string ParseJSONString(const string json, const string key)
{
    string search = "\"" + key + "\"";
    int pos = StringFind(json, search);
    if (pos < 0) return "";

    pos += StringLen(search);

    // avança até ':'
    while (pos < StringLen(json) && StringGetCharacter(json, pos) != ':')
        pos++;
    pos++;  // pula ':'

    // avança espaços
    while (pos < StringLen(json) && StringGetCharacter(json, pos) == ' ')
        pos++;

    // verifica se é string (começa com '"')
    if (pos >= StringLen(json) || StringGetCharacter(json, pos) != '"')
        return "";

    pos++;  // pula '"' de abertura
    int start = pos;

    while (pos < StringLen(json) && StringGetCharacter(json, pos) != '"')
        pos++;

    return StringSubstr(json, start, pos - start);
}

//─────────────────────────────────────────────────────────────────────────────
// Extrai o valor bool de um campo JSON.
// Suporta true/false (minúsculo, padrão JSON).
//─────────────────────────────────────────────────────────────────────────────
bool ParseJSONBool(const string json, const string key)
{
    string search = "\"" + key + "\"";
    int pos = StringFind(json, search);
    if (pos < 0) return false;

    pos += StringLen(search);

    // avança até ':'
    while (pos < StringLen(json) && StringGetCharacter(json, pos) != ':')
        pos++;
    pos++;

    // avança espaços
    while (pos < StringLen(json) && StringGetCharacter(json, pos) == ' ')
        pos++;

    if (pos + 4 <= StringLen(json) && StringSubstr(json, pos, 4) == "true")
        return true;

    return false;
}

//─────────────────────────────────────────────────────────────────────────────
// Extrai o valor inteiro de um campo JSON.
//─────────────────────────────────────────────────────────────────────────────
long ParseJSONInt(const string json, const string key)
{
    string search = "\"" + key + "\"";
    int pos = StringFind(json, search);
    if (pos < 0) return 0;

    pos += StringLen(search);

    // avança até ':'
    while (pos < StringLen(json) && StringGetCharacter(json, pos) != ':')
        pos++;
    pos++;

    // avança espaços
    while (pos < StringLen(json) && StringGetCharacter(json, pos) == ' ')
        pos++;

    int start = pos;
    // coleta dígitos (incluindo sinal negativo)
    if (pos < StringLen(json) && StringGetCharacter(json, pos) == '-')
        pos++;

    while (pos < StringLen(json))
    {
        ushort ch = StringGetCharacter(json, pos);
        if (ch >= '0' && ch <= '9')
            pos++;
        else
            break;
    }

    if (pos == start) return 0;
    return StringToInteger(StringSubstr(json, start, pos - start));
}

//─────────────────────────────────────────────────────────────────────────────
// Extrai o valor double de um campo JSON.
//─────────────────────────────────────────────────────────────────────────────
double ParseJSONDouble(const string json, const string key)
{
    string search = "\"" + key + "\"";
    int pos = StringFind(json, search);
    if (pos < 0) return 0.0;

    pos += StringLen(search);

    while (pos < StringLen(json) && StringGetCharacter(json, pos) != ':')
        pos++;
    pos++;

    while (pos < StringLen(json) && StringGetCharacter(json, pos) == ' ')
        pos++;

    int start = pos;
    if (pos < StringLen(json) && StringGetCharacter(json, pos) == '-')
        pos++;

    bool has_dot = false;
    while (pos < StringLen(json))
    {
        ushort ch = StringGetCharacter(json, pos);
        if (ch >= '0' && ch <= '9')
            pos++;
        else if (ch == '.' && !has_dot)
        {
            has_dot = true;
            pos++;
        }
        else
            break;
    }

    if (pos == start) return 0.0;
    return StringToDouble(StringSubstr(json, start, pos - start));
}
