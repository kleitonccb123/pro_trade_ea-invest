# O Que Falta para o Sistema Funcionar de Verdade

> Status atual: UI e backend existem, mas **não estão conectados**. O robô ativa visualmente mas não executa nenhuma ordem real na KuCoin.

---

## Resumo Executivo

| Camada | Status | Descrição |
|---|---|---|
| Frontend — Banner do Robô | ✅ Funcionando | Exibe par, TP, SL, investimento, timeframe |
| Frontend — Gráfico em tempo real | ❌ Não integrado | `KuCoinNativeChart.tsx` existe mas não está no Dashboard |
| Backend — API de credenciais | ✅ Funcionando | Salva e valida chaves KuCoin |
| Backend — Motor de trading | ❌ Desligado | Engine é processo separado, precisa de Redis |
| Backend — Criação de bot | ❌ Não conectado | `BotConfigModal` salva no `localStorage` mas nunca envia ao backend |
| Backend — Execução de ordens | ❌ Não ativado | Endpoints existem mas nunca são chamados |
| Frontend — Histórico de trades | ❌ Não exibido | Componente não está no Dashboard |
| Frontend — P&L ao vivo | ❌ Não conectado | WebSocket do bot existe no backend mas não no frontend |
| Frontend — Desativar robô | ❌ Não implementado | Nenhum botão de parar no Dashboard |

---

## Problema 1 — Gráfico em Tempo Real Não Está no Dashboard

### O que existe
- `src/components/kucoin/KuCoinNativeChart.tsx` — gráfico de velas (candlestick) completo com WebSocket KuCoin, média móvel de 20 períodos, marcadores de entrada/saída
- Conecta ao WebSocket público da KuCoin (`wss://push-testing.kucoin.com`) via `bulletToken`

### O que falta
- Adicionar `<KuCoinNativeChart symbol={activeBotConfig.pair} />` dentro de `KuCoinDashboard.tsx`, passando o par configurado pelo robô

### Arquivo a alterar
- `src/components/kucoin/KuCoinDashboard.tsx` — inserir o componente logo abaixo do banner "Robô Ativo"

### Grau de dificuldade: 🟡 Médio
> O componente existe e funciona isolado. É só renderizá-lo passando o par correto (ex: `"BTC/USDT"` baseado no `activeBotConfig.pair`).

---

## Problema 2 — Ativação do Robô Não Cria Bot no Backend

### O que existe
- `BotConfigModal.tsx` salva a config em `localStorage` e navega para o Dashboard
- `backend/app/bots/router.py` — endpoint `POST /bots` cria um bot real no MongoDB

### O que falta
Ao clicar em "Ativar e ir para o Dashboard", o `BotConfigModal` precisa chamar o backend **antes** de navegar:

```ts
// Chamada que está faltando em BotConfigModal.tsx
const response = await apiPost('/bots', {
  name: config.robotName,
  strategy: config.robotStrategy,
  symbol: config.pair,          // ex: "BTC-USDT"
  investment_usdt: config.investmentUsdt,
  take_profit_pct: config.takeProfitPct,
  stop_loss_pct: config.stopLossPct,
  timeframe: config.timeframe,
  max_trades_per_day: config.maxTradesPerDay,
});
// Salvar o bot_id no localStorage para uso futuro
localStorage.setItem('active_bot_id', response.id);
```

### Arquivo a alterar
- `src/components/gamification/BotConfigModal.tsx` — função `handleActivate()`

### Grau de dificuldade: 🟡 Médio

---

## Problema 3 — Motor de Trading (Engine) Não Está Rodando

### O que existe
- `backend/app/engine/main.py` — motor completo que lê comandos do Redis e gerencia `BotWorker`
- `backend/app/engine/orchestrator.py` — orquestra vários bots simultaneamente
- `backend/app/engine/worker.py` — worker individual que executa a estratégia

### O que falta
O motor **não sobe junto com o servidor FastAPI**. Ele é um processo separado e requer:

1. **Redis rodando**: `docker run -d -p 6379:6379 redis:alpine`
2. **Variável de ambiente**: `REDIS_URL=redis://localhost:6379`
3. **Processo separado na engine**:
   ```bash
   cd backend
   python -m app.engine.main
   ```

### Impacto
Sem o motor rodando, nenhum bot executa ordens, mesmo que esteja criado no banco de dados.

### Grau de dificuldade: 🔴 Alto
> Requer Redis instalado e um processo extra sempre aberto além do servidor FastAPI.

---

## Problema 4 — P&L ao Vivo Não Aparece no Dashboard

### O que existe
- `backend/app/bots/router.py` — WebSocket `GET /bots/{bot_id}/pnl/stream` emite P&L em tempo real
- Backend calcula lucro/prejuízo por trade em tempo real

### O que falta
Frontend precisa conectar ao WebSocket do bot ativo:

```ts
// Hook que precisa ser criado ou usado no KuCoinDashboard.tsx
const ws = new WebSocket(`ws://localhost:8000/bots/${activeBotId}/pnl/stream`);
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  // Exibir: data.pnl_total, data.pnl_pct, data.trades_count
};
```

### Arquivo a alterar
- `src/components/kucoin/KuCoinDashboard.tsx` — adicionar painel "P&L do Robô" com valores ao vivo

### Grau de dificuldade: 🟡 Médio

---

## Problema 5 — Sem Botão para Desativar o Robô

### O que existe
- `backend/app/bots/router.py` — endpoint `PATCH /bots/{bot_id}/stop` para parar um bot
- `KillSwitchButton.tsx` — componente de emergência já existe

### O que falta
No banner "Robô Ativo" no Dashboard, um botão "Parar Robô" que:
1. Chame `PATCH /bots/{bot_id}/stop` no backend
2. Remova `active_bot_config` e `active_bot_id` do `localStorage`
3. Esconda o banner

### Arquivo a alterar
- `src/components/kucoin/KuCoinDashboard.tsx` — botão "Parar" no final do banner ativo

### Grau de dificuldade: 🟢 Fácil

---

## Problema 6 — Histórico de Trades Não Está Visível

### O que existe
- `backend/app/trading/bots_history_router.py` — endpoint de histórico de trades por bot
- MongoDB guarda cada ordem executada

### O que falta
Tabela de trades no Dashboard mostrando: data, par, tipo (compra/venda), preço, quantidade, resultado.

### Arquivo a alterar
- `src/components/kucoin/KuCoinDashboard.tsx` — nova seção abaixo do portfólio

### Grau de dificuldade: 🟢 Fácil

---

## Problema 7 — Redis Não Está Configurado no `.env`

### O que existe
- `backend/app/shared/redis_client.py` — cliente Redis já implementado
- `backend/app/services/redis_manager.py` — gerenciador de WebSockets via Redis

### O que falta
Arquivo `.env` na pasta `backend/` com:
```env
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=           # deixar vazio se sem senha
```

Sem esse .env, a importação do redis_manager falha silenciosamente em alguns módulos.

### Grau de dificuldade: 🟢 Fácil

---

## Ordem de Prioridade para Deixar Funcional

```
FASE 1 — Visual (sem necessidade de Redis)
  1. Integrar KuCoinNativeChart no Dashboard      ← 30 min
  2. Adicionar botão "Parar Robô" no banner       ← 20 min
  3. Mostrar histórico de trades                  ← 45 min

FASE 2 — Backend conectado (sem Redis ainda)
  4. BotConfigModal chama POST /bots              ← 30 min
  5. Dashboard exibe P&L via polling HTTP         ← 30 min

FASE 3 — Motor real (requer Redis)
  6. Instalar e configurar Redis                  ← 15 min
  7. Rodar python -m app.engine.main              ← 5 min
  8. Conectar P&L via WebSocket                   ← 45 min
```

---

## Checklist Final

- [ ] `KuCoinNativeChart` renderizado no Dashboard com o par do robô ativo
- [ ] `BotConfigModal` chama `POST /bots` antes de navegar
- [ ] Banner "Robô Ativo" tem botão "Parar Robô"
- [ ] Redis instalado e rodando na porta 6379
- [ ] Variável `REDIS_URL` no `.env` do backend
- [ ] Motor `python -m app.engine.main` rodando como processo separado
- [ ] P&L ao vivo conectado via WebSocket
- [ ] Histórico de trades exibido no Dashboard

---

## Arquitetura de Processos Necessária (Modo Produção)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend Vite  │    │  Backend FastAPI │    │  Engine Python  │
│  porta 8081     │◄──►│  porta 8000     │◄──►│  processo sep.  │
└─────────────────┘    └────────┬────────┘    └────────┬────────┘
                                │                       │
                        ┌───────▼───────────────────────▼──────┐
                        │            Redis :6379                │
                        │   (fila de comandos + PnL stream)     │
                        └───────────────────────────────────────┘
                                        │
                                ┌───────▼───────┐
                                │   MongoDB     │
                                │   (dados)     │
                                └───────────────┘
```

Atualmente apenas **Frontend** e **Backend FastAPI** estão rodando. **Redis** e **Engine** estão ausentes.
