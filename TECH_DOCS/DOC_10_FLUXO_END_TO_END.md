# DOC 10 — Fluxo Completo do Usuário (End-to-End)

> **Nível:** Produção | **Escopo:** Do cadastro ao primeiro trade real  
> **Objetivo:** Validação completa do sistema integrado — este doc é o teste de aceitação final

---

## 1. OBJETIVO

Documentar o fluxo completo integrado de ponta a ponta, identificando cada ponto de integração, os dados que transitam e os critérios de sucesso/falha em cada etapa.

Este documento serve como:
- Guia de QA e testes de integração
- Onboarding de novos desenvolvedores
- Checklist de validação pré-produção

---

## 2. VISÃO GERAL DO FLUXO

```
[1] Cadastro/Login
        │
        ▼
[2] Conectar KuCoin API
        │
        ▼
[3] Acessar /robots
        │
        ▼
[4] Desbloquear Robô (pontos ou upgrade)
        │
        ▼
[5] Configurar e Ativar Robô
        │
        ▼
[6] Bot Executa Trades em Tempo Real
        │
        ▼
[7] Monitorar Performance no Dashboard
        │
        ▼
[8] Ver Posição no Ranking
        │
        ▼
[9] Parar Robô
        │
        ▼
[10] Histórico e PnL Final
```

---

## 3. ETAPA 1 — CADASTRO E LOGIN

### Fluxo

```
Usuário → POST /api/auth/register
  Body: { email, password, display_name }
  
Validações:
  ✓ Email único (índice unique no MongoDB)
  ✓ Password min 8 chars, 1 número, 1 maiúscula
  ✓ Rate limit: 5 registros/hora por IP

Resposta OK:
  { user_id, access_token (JWT 15min), refresh_token (JWT 7d) }

Erros possíveis:
  409 → Email já cadastrado
  422 → Validação falhou
  429 → Rate limit
```

### Estado após etapa 1

```
MongoDB users:
  { _id, email, display_name, plan: "free", created_at }

localStorage (frontend):
  auth-storage: { access_token, refresh_token, user }

Redirect:
  → /dashboard (verifica KuCoin na próxima etapa)
```

---

## 4. ETAPA 2 — CONECTAR API KUCOIN

### Fluxo

```
Dashboard detecta: localStorage['kucoin_connected'] !== 'true'
  → Exibe <KuCoinOnboarding />

Usuário preenche: API Key, API Secret, API Passphrase

Frontend → POST /api/trading/kucoin/connect
  Headers: Authorization: Bearer <token>
  Body: { api_key, api_secret, api_passphrase }

Backend:
  1. Descriptografar credenciais (Fernet)
  2. Testar conexão real: GET /api/v1/accounts (KuCoin)
  3. Se OK → salvar criptografado no MongoDB
  4. Retornar { connected: true, ... }

Frontend:
  → localStorage.setItem('kucoin_connected', 'true')
  → Redirecionar para o dashboard principal
```

### Pré-requisitos na KuCoin (usuário deve configurar)

- API Key com permissões: **Trade + General** (sem Withdraw)
- IP Whitelist: IP do servidor de produção
- Passphrase definida no momento da criação

### Estado após etapa 2

```
MongoDB trading_credentials:
  { user_id, api_key_enc, api_secret_enc, api_passphrase_enc, is_active: true }

localStorage:
  kucoin_connected: "true"
```

---

## 5. ETAPA 3 — ACESSAR /ROBOTS

### Estado atual vs esperado

```
Atual (BUG):
  ✗ 20 robots hardcoded (mock)
  ✗ Botão "Ativar" não faz nada
  ✗ Ranking API sem autenticação

Esperado (após implementar os docs 1-9):
  ✓ Robots carregados do catálogo real
  ✓ Desbloqueados marcados com badge
  ✓ Botão "Ativar" abre ActivateRobotModal
  ✓ Ranking carregado da API autenticada
```

### Dados necessários do backend

```python
# GET /api/gamification/profile
{
  "unlocked_robots": ["bot_001", "bot_004"],
  "trade_points": 2500,
  "level": 7,
  "xp": 3200,
}

# GET /api/gamification/leaderboard
{ "entries": [...], "user_rank": {...} }
```

---

## 6. ETAPA 4 — DESBLOQUEAR ROBÔ

### Fluxo via TradePoints

```
Usuário clica em robô bloqueado → LockedRobotModal

Opção 1 (pontos):
  POST /api/gamification/unlock-robot
  Body: { robot_id, method: "points" }
  Backend:
    → Verificar saldo (trade_points >= custo_do_robot)
    → Deduzir pontos
    → Adicionar robot_id em gamification_profiles.unlocked_robots
    → Retornar { success: true, new_balance }

Opção 2 (upgrade de plano):
  → Redirecionar para /pricing
```

### Custo sugerido por tier

| Tier do Robô | Custo em TradePoints |
|---|---|
| Common | 500 |
| Uncommon | 1,500 |
| Rare | 4,000 |
| Epic | 10,000 |
| Legendary | 25,000 |

---

## 7. ETAPA 5 — CONFIGURAR E ATIVAR ROBÔ

### Fluxo

```
Usuário clica "Ativar" no RobotMarketplaceCard
→ Abre ActivateRobotModal com campos:
    Par:           BTC-USDT (dropdown dos pares permitidos)
    Capital:       500 USDT (slider min=10, max=saldo_disponível)
    Timeframe:     1h (opções limitadas pelo plano)
    Stop Loss:     5% (slider 0.5-30%)
    Take Profit:   15% (deve ser > stop loss)

Usuário confirma → POST /api/trading/bots/start

Backend (em sequência, conforme DOC 03):
  1. Verificar robô desbloqueado
  2. Verificar limite do plano  
  3. Verificar credenciais KuCoin
  4. GET /api/v1/accounts → checar saldo USDT ≥ capital
  5. Criar user_bot_instances com status: "pending"
  6. RPUSH bot:commands → engine

Frontend recebe:
  { bot_instance_id: "abc123", status: "starting", estimated_start_seconds: 5 }

→ Exibir toast "Robô iniciando..."
→ Redirecionar para /dashboard com aba de bots ativos
→ Polling GET /api/trading/bots até status === "running"
```

### Timeline de inicialização

```
t=0s    POST /bots/start → instância criada (status: pending)
t=1s    Engine lê command do Redis
t=2s    Engine cria BotWorker
t=3s    BotWorker conecta WebSocket KuCoin
t=4s    BotWorker subscribe ticker e orders
t=5s    Status atualizado para "running" no MongoDB
t=5s    Frontend polling detecta "running" → exibe "Ativo" 🟢
```

---

## 8. ETAPA 6 — BOT EXECUTA TRADES

### Loop interno do BotWorker (por candle)

```
1. Aguardar nova vela fechada (WebSocket ticker)
2. Buscar histórico de candles (REST)
3. Calcular indicadores (RSI, BB, EMA, etc.)
4. Gerar sinal: BUY | SELL | HOLD
5. Verificar Kill Switch (Redis)
6. Se BUY e sem posição aberta:
     → GET /api/v1/accounts → verificar saldo
     → POST /api/v1/orders (market, funds=capital_usdt)
     → Salvar TradeRecord com status: open
     → Atualizar user_bot_instances.current_position
7. Se posição aberta, verificar risco (DOC 07):
     → check_position_exit(entry_price, current_price)
     → Se STOP acionado: POST /api/v1/orders (sell market)
     → Calcular PnL (DOC 05)
     → Atualizar TradeRecord com status: closed
     → record_trade_result() → verificar daily_drawdown
8. Log estruturado de cada ação
9. Snapshots de performance a cada 1h
```

### Exemplo de ciclo completo BTC-USDT/1h

```
14:00  Candle fecha. RSI=28 (oversold). Sinal: BUY
       Capital: 1000 USDT
       Preço entrada: $43,250
       Ordem executada: compra 0.02309 BTC (fee ≈ $1.00)
       
15:00  Candle fecha. Preço: $44,500. PnL não-real.: +$28.87 (+2.89%)
16:00  Candle fecha. Preço: $45,100. PnL não-real.: +$42.72 (+4.27%)
17:00  Candle fecha. Preço: $46,200. Take profit atingido!
       Ordem de venda executada: $44.00 - $1.00 fee = PnL líquido +$42.00

Resultado:
  Entrada: $43,250 × 0.02309 = $998.99 USDT
  Saída:   $46,200 × 0.02309 = $1,067.76 USDT
  Fee total: $2.00 USDT
  PnL líquido: +$66.77 USDT (+6.68%)
  Duração: 3 horas
```

---

## 9. ETAPA 7 — MONITORAMENTO NO DASHBOARD

### Dados exibidos em tempo real

```tsx
// Polling a cada 30s ou WebSocket (se implementado)

Aba "Meus Robôs":
┌─────────────────────────────────────────────────┐
│ 🤖 Volatility Dragon       ● ATIVO              │
│ Par: BTC-USDT | Capital: 1,000 USDT            │
│ PnL Realizado:  +$66.77 (6.68%)  ✅            │
│ PnL Não-Real.:  +$12.30 (em aberto)  🟡        │
│ Win Rate: 68% | Trades: 12 | Fees: $8.40       │
│ Uptime: 3d 4h | Última ação: 2h atrás          │
│                                        [⏹ Parar]│
└─────────────────────────────────────────────────┘
```

---

## 10. ETAPA 8 — VER POSIÇÃO NO RANKING

```
GET /api/gamification/leaderboard?period=30
Headers: Authorization: Bearer <token>

Resposta:
{
  entries: [
    { rank: 1, display_name: "TradeMaster", roi_pct: 23.4, win_rate: 71.2, ... },
    { rank: 2, display_name: "Você", roi_pct: 18.7, win_rate: 68.5, ... },
    ...
  ],
  user_rank: { rank: 2, roi_pct: 18.7, ... },
  period_days: 30
}
```

---

## 11. ETAPA 9 — PARAR ROBÔ

```
POST /api/trading/bots/{bot_instance_id}/stop

Engine recebe comando:
  1. Cancelar todas as ordens abertas (DELETE /api/v1/orders)
  2. Se tem posição aberta: fechar a mercado
  3. Calcular PnL final
  4. Atualizar status: stopped
  5. Registrar motivo: "manual_stop"
  6. Desconectar WebSocket

Frontend:
  → Polling detecta status: stopped
  → Exibir resumo final da sessão
```

---

## 12. ETAPA 10 — HISTÓRICO E PNL FINAL

```
GET /api/trading/bots/{bot_instance_id}/trades?page=1&limit=50

Resposta:
{
  trades: [
    {
      entry_timestamp: "2024-01-15T14:00:00Z",
      exit_timestamp:  "2024-01-15T17:00:00Z",
      pair: "BTC-USDT",
      entry_price: 43250,
      exit_price: 46200,
      pnl_net_usdt: 66.77,
      roi_pct: 6.68,
      exit_reason: "take_profit",
      holding_minutes: 180,
      total_fees_usdt: 2.00,
    },
    // ...
  ],
  total_trades: 12,
  summary: {
    total_pnl_usdt: 142.50,
    win_rate: 68.0,
    avg_holding_minutes: 195,
    total_fees_usdt: 18.40,
    roi_pct: 14.25,
    max_drawdown_pct: 3.2,
  }
}
```

---

## 13. MATRIZ DE INTEGRAÇÃO — ONDE CADA DOC SE APLICA

| Etapa | DOC 01 | DOC 02 | DOC 03 | DOC 04 | DOC 05 | DOC 06 | DOC 07 | DOC 08 |
|---|---|---|---|---|---|---|---|---|
| 2 — KuCoin Connect | | | | ✓ signing | | | | ✓ logs |
| 5 — Ativar Bot | ✓ engine | ✓ DB schema | ✓ endpoint | ✓ saldo | | | | ✓ audit |
| 6 — Executar | ✓ worker | ✓ trades DB | | ✓ WS+REST | ✓ PnL | | ✓ risk | ✓ metrics |
| 7 — Monitorar | | ✓ snapshots | | | ✓ display | | ✓ alerts | ✓ health |
| 8 — Ranking | | | | | ✓ ROI/WR | ✓ leaderboard | | |
| 9 — Parar | ✓ graceful | ✓ status | ✓ stop EP | ✓ cancel ord | ✓ final PnL | | ✓ kill sw | ✓ audit |

---

## 14. TESTES END-TO-END OBRIGATÓRIOS

### Happy Path

```python
# test_e2e_full_flow.py

async def test_complete_user_journey():
    # 1. Registrar usuário
    user = await register_user("test@example.com", "Pass123!")
    assert user["access_token"]

    # 2. Conectar KuCoin (sandbox)
    conn = await connect_kucoin(user["token"], SANDBOX_CREDS)
    assert conn["connected"] == True

    # 3. Verificar unlock de robô
    await unlock_robot(user["token"], "bot_001", method="points")
    profile = await get_gamification_profile(user["token"])
    assert "bot_001" in profile["unlocked_robots"]

    # 4. Ativar robô
    bot = await start_bot(user["token"], {
        "robot_id": "bot_001",
        "pair": "BTC-USDT",
        "capital_usdt": 50,
        "stop_loss_pct": 5,
        "take_profit_pct": 10
    })
    assert bot["status"] == "starting"

    # 5. Aguardar inicialização
    await asyncio.sleep(10)
    status = await get_bot_status(user["token"], bot["bot_instance_id"])
    assert status["status"] == "running"

    # 6. Simular trade (sandbox/mock)
    await simulate_price_movement(pair="BTC-USDT", direction="up", pct=12)
    await asyncio.sleep(5)

    # 7. Verificar trade registrada
    trades = await get_bot_trades(user["token"], bot["bot_instance_id"])
    assert len(trades) >= 1
    assert trades[0]["pnl_net_usdt"] > 0  # Take profit acionado

    # 8. Parar bot
    stop = await stop_bot(user["token"], bot["bot_instance_id"])
    assert stop["message"]

    # 9. Verificar histórico
    history = await get_bot_trades(user["token"], bot["bot_instance_id"])
    assert all(t["status"] == "closed" for t in history)
```

### Edge Cases

```python
async def test_insufficient_balance():
    # Tentar ativar bot com capital > saldo
    response = await start_bot(token, {"capital_usdt": 99999, ...})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "insufficient_balance"

async def test_stop_loss_triggers():
    # Simular queda de preço acima do stop loss
    await simulate_price_movement("BTC-USDT", "down", pct=7)  # SL=5%
    await asyncio.sleep(5)
    status = await get_bot_status(token, bot_id)
    assert status["status"] == "running"  # Bot ainda rodando
    trades = await get_bot_trades(token, bot_id)
    assert trades[-1]["exit_reason"] == "stop_loss"

async def test_kucoin_disconnect_resumes():
    # Simular desconexão do WS e verificar reconexão
    await kill_ws_connection(bot_id)
    await asyncio.sleep(15)
    status = await get_bot_status(token, bot_id)
    assert status["status"] == "running"  # Reconectou
```

---

## 15. CHECKLIST FINAL DE PRODUÇÃO

### Segurança
- [ ] Credenciais KuCoin sempre criptografadas no DB (Fernet)
- [ ] JWT com idade curta (15min) + refresh token seguro
- [ ] Rate limiting em todos os endpoints públicos
- [ ] CORS configurado apenas para domínios autorizados
- [ ] Variáveis sensíveis via ENV, nunca hardcoded

### Funcional
- [ ] Cadastro → KuCoin → Desbloquear → Ativar → Trade → Parar funciona end-to-end
- [ ] PnL calculado corretamente após fees
- [ ] Stop loss e take profit acionados no preço correto
- [ ] Daily drawdown para o bot e notifica o usuário
- [ ] Ranking exibe dados reais com dados dos últimos 30d

### Infraestrutura
- [ ] MongoDB com Replica Set (failover automático)
- [ ] Redis persistido (appendonly yes)
- [ ] Health checks em todos os containers
- [ ] Deploy zero-downtime configurado
- [ ] Backups automáticos do MongoDB (diário)

### Observabilidade
- [ ] Logs JSON em todas as ações financeiras
- [ ] Prometheus coletando métricas
- [ ] Grafana dashboard com alertas
- [ ] Alertas Telegram para eventos críticos
- [ ] Audit log imutável para compliance
