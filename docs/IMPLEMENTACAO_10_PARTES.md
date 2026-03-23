# Guia de Implementação — 10 Partes Executáveis

> **Premissa crítica:** O sistema tem backend e frontend bem estruturados, mas **nenhuma conexão entre eles** para o fluxo de trading real. Cada parte abaixo é independente e pode ser executada na ordem indicada.

---

## PARTE 1 — Integrar o Gráfico em Tempo Real no Dashboard

**O que falta:** `KuCoinNativeChart.tsx` existe (357 linhas, WebSocket KuCoin, candlestick, MA20) mas nunca é renderizado no `KuCoinDashboard.tsx`.

**Problema crítico no componente atual:** ele usa `symbol = 'BTC/USDT'` com barra, mas a `activeBotConfig.pair` usa `'BTC-USDT'` com hífen. Precisamos converter.

### Arquivo: `src/components/kucoin/KuCoinDashboard.tsx`

Localize a linha do import de `Bot` (já existe) e adicione o import do chart:

```tsx
// ADICIONAR junto dos outros imports no topo do arquivo
import KuCoinNativeChart from '@/components/kucoin/KuCoinNativeChart';
```

Agora localize o bloco do banner "Robô Ativo" (após `{activeBotConfig && (`) e adicione o gráfico **logo abaixo** do banner, antes do header:

```tsx
        {/* ── Gráfico em Tempo Real ─────────────────────────────────── */}
        {activeBotConfig && (
          <div className="rounded-xl overflow-hidden border border-edge-subtle">
            <div className="px-4 py-3 bg-surface-raised border-b border-edge-subtle flex items-center gap-2">
              <BarChart2 size={15} className="text-emerald-400" />
              <span className="text-sm font-semibold text-content-primary">
                Gráfico ao Vivo —{' '}
                <span className="text-emerald-400 font-mono">
                  {activeBotConfig.pair.replace('-', '/')}
                </span>
              </span>
              <span className="ml-auto text-xs text-content-muted font-mono">
                TF: {activeBotConfig.timeframe}
              </span>
            </div>
            <KuCoinNativeChart
              symbol={activeBotConfig.pair.replace('-', '/')}
            />
          </div>
        )}
```

> Coloque esse bloco **entre** o banner do robô e o header "Dashboard KuCoin".

### Verificação

Acesse o Dashboard após ativar um robô. O gráfico de velas deve aparecer imediatamente abaixo do banner "Robô Ativo", com WebSocket conectando à KuCoin automaticamente.

---

## PARTE 2 — BotConfigModal Registra o Bot no Backend

**O que falta:** `handleActivate()` em `BotConfigModal.tsx` só faz `localStorage.setItem` e `navigate`. Nunca cria o bot no banco de dados.

**Endpoint real:** `POST /bots` (requer auth JWT, subscription ativa).

### Arquivo: `src/components/gamification/BotConfigModal.tsx`

Adicione o import do apiClient no topo:

```tsx
// ADICIONAR junto dos outros imports
import { apiCall } from '@/services/apiClient';
```

Substitua a função `handleActivate` inteira:

```tsx
  const handleActivate = async () => {
    if (!validate()) return;

    setActivating(true);
    try {
      const config: BotConfig = {
        robotId: robot.id,
        robotName: robot.name,
        robotStrategy: robot.strategy,
        pair,
        investmentUsdt: parseFloat(investment),
        takeProfitPct: parseFloat(takeProfit),
        stopLossPct: parseFloat(stopLoss),
        timeframe,
        maxTradesPerDay: parseInt(maxTrades, 10),
        activatedAt: new Date().toISOString(),
      };

      // ── 1. Criar bot no backend ──────────────────────────────────────
      let botId: string | null = null;
      try {
        const res = await apiCall('/bots', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: config.robotName,
            symbol: config.pair,       // ex: "BTC-USDT"
            config: {
              investment_usdt: config.investmentUsdt,
              take_profit_pct: config.takeProfitPct,
              stop_loss_pct: config.stopLossPct,
              timeframe: config.timeframe,
              max_trades_per_day: config.maxTradesPerDay,
              strategy: config.robotStrategy,
            },
          }),
        });

        if (res.ok) {
          const data = await res.json();
          botId = data.id;
          localStorage.setItem('active_bot_id', botId!);
          console.log('[BotConfig] Bot criado no backend:', botId);
        } else {
          // 402 = sem créditos, 403 = plano insuficiente
          const err = await res.json().catch(() => ({}));
          const msg = err?.detail?.message || err?.detail || 'Erro ao criar bot no servidor';
          setErrors({ general: `Backend: ${msg}` });
          return;
        }
      } catch (networkErr) {
        // Falha de rede: salva só no localStorage e avisa
        console.warn('[BotConfig] Backend indisponível, modo offline:', networkErr);
        setErrors({ general: 'Servidor offline. O robô será registrado localmente.' });
        // Não retorna — continua com modo offline
      }

      // ── 2. Persistir config localmente ──────────────────────────────
      localStorage.setItem('active_bot_config', JSON.stringify(config));

      await new Promise((r) => setTimeout(r, 600));

      onClose();
      navigate('/dashboard');
    } finally {
      setActivating(false);
    }
  };
```

Adicione também um display de erro geral no formulário (antes do botão de ativar):

```tsx
              {/* ADICIONAR antes do botão de Ativar */}
              {errors.general && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-950/40 border border-yellow-500/30 text-sm text-yellow-300">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  {errors.general}
                </div>
              )}
```

---

## PARTE 3 — Iniciar a Execução do Bot (POST /bots/{id}/start)

**O que falta:** Criar o bot (Parte 2) não inicia a execução. É preciso chamar `POST /bots/{id}/start` logo após.

**Atenção crítica:** Este endpoint exige créditos de ativação (`ActivationManager`) e subscription ativa. Se o plano for `free`, vai retornar `403`.

### Arquivo: `src/components/gamification/BotConfigModal.tsx`

Dentro de `handleActivate`, após salvar `botId`, adicione:

```tsx
      // ── 3. Iniciar execução do bot ───────────────────────────────────
      if (botId) {
        try {
          const startRes = await apiCall(`/bots/${botId}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // Sem body = modo simulação (sem credenciais KuCoin reais)
            // Para modo live, passar as credenciais KuCoin aqui
          });

          if (!startRes.ok) {
            const startErr = await startRes.json().catch(() => ({}));
            // 402 = sem créditos de ativação
            if (startRes.status === 402) {
              setErrors({
                general: `Sem créditos de ativação. Restantes: ${startErr?.detail?.credits_remaining ?? 0}`,
              });
              return;
            }
            console.warn('[BotConfig] Start falhou:', startErr);
          } else {
            const startData = await startRes.json();
            localStorage.setItem('active_instance_id', startData.instance_id || '');
            console.log('[BotConfig] Bot iniciado:', startData);
          }
        } catch (e) {
          console.warn('[BotConfig] Erro ao iniciar bot (modo offline):', e);
        }
      }
```

**Modo Live (com credenciais KuCoin reais):** Para operar com dinheiro real, o body do `POST /bots/{id}/start` deve conter:

```json
{
  "api_key": "SUA_API_KEY",
  "api_secret": "SEU_SECRET",
  "api_passphrase": "SUA_PASSPHRASE",
  "testnet": false
}
```

Para buscar as credenciais salvas e passá-las no start:

```tsx
      // Buscar credenciais salvas
      const credsRes = await apiCall('/user/settings/exchanges');
      if (credsRes.ok) {
        const creds = await credsRes.json();
        const kucoin = creds.find((c: any) => c.exchange === 'kucoin');
        if (kucoin?.connected) {
          // O backend já tem as credenciais descriptografadas internamente
          // Passar só a flag exchange ao start
          body = JSON.stringify({ exchange: 'kucoin', testnet: false });
        }
      }
```

---

## PARTE 4 — Botão "Parar Robô" no Banner do Dashboard

**O que falta:** Não há como parar o robô pela interface. O endpoint `POST /bots/{id}/stop` existe.

**Nota:** O endpoint usa `/bots/{instance_id}/stop` onde `instance_id` é o ID retornado pelo `start`, não o ID do bot.

### Arquivo: `src/components/kucoin/KuCoinDashboard.tsx`

Substitua o final do banner "Robô Ativo" (o `<div>` com o badge "Operando"):

```tsx
            {/* Substituir o div do badge "Operando" por este: */}
            <div className="sm:ml-auto flex-shrink-0 flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-xs font-semibold text-emerald-300">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
                </span>
                Operando
              </span>
              <button
                onClick={handleStopBot}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950/40 border border-red-500/30 text-xs font-semibold text-red-400 hover:bg-red-900/50 hover:border-red-400/50 transition-all"
              >
                <Square size={12} className="fill-red-400" />
                Parar Robô
              </button>
            </div>
```

Adicione o import de `Square` e `useCallback` no topo:

```tsx
import { ..., Square } from 'lucide-react'; // adicionar Square
```

Adicione a função `handleStopBot` dentro do componente `KuCoinDashboard`, antes do `return`:

```tsx
  const handleStopBot = async () => {
    const instanceId = localStorage.getItem('active_instance_id');
    const botId = localStorage.getItem('active_bot_id');

    // Tenta parar no backend
    const idToStop = instanceId || botId;
    if (idToStop) {
      try {
        await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/bots/${idToStop}/stop`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });
      } catch (e) {
        console.warn('[Dashboard] Erro ao parar bot no backend:', e);
      }
    }

    // Limpa localStorage independente do resultado
    localStorage.removeItem('active_bot_config');
    localStorage.removeItem('active_bot_id');
    localStorage.removeItem('active_instance_id');

    // Recarrega para esconder o banner
    window.location.reload();
  };
```

**Para não usar `window.location.reload()`** (melhor UX), passe um callback do Dashboard para o KuCoinDashboard:

```tsx
// Em Dashboard.tsx: adicionar prop
const handleBotStopped = () => setActiveBotConfig(null);

// Passar para KuCoinDashboard:
<KuCoinDashboard
  accessToken={accessToken}
  activeBotConfig={activeBotConfig}
  onBotStop={handleBotStopped}
/>

// Em KuCoinDashboard.tsx: adicionar na interface e usar:
interface KuCoinDashboardProps {
  accessToken: string;
  activeBotConfig?: BotConfig | null;
  onBotStop?: () => void;
}
// Chamar onBotStop?.() em vez de window.location.reload()
```

---

## PARTE 5 — Painel de P&L ao Vivo via WebSocket

**O que falta:** Backend tem WebSocket em `GET /bots/{bot_id}/pnl/stream` que emite updates a cada 2 segundos. Frontend nunca conecta.

### Arquivo: `src/hooks/use-bot-pnl.ts` (CRIAR NOVO)

```ts
/**
 * Hook para consumir o stream de P&L de um bot via WebSocket.
 * Reconecta automaticamente em caso de queda.
 */
import { useEffect, useState, useRef } from 'react';
import { authService } from '@/services/authService';

export interface BotPnL {
  state: string;
  total_pnl: number;
  total_pnl_percent: number;
  total_trades: number;
  winning_trades: number;
  win_rate: number;
  current_position: any | null;
  last_trade: any | null;
  started_at: string | null;
}

const WS_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace('http://', 'ws://')
  .replace('https://', 'wss://');

export function useBotPnL(botId: string | null) {
  const [pnl, setPnL] = useState<BotPnL | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!botId) return;

    const connect = () => {
      const token = authService.getAccessToken();
      const url = `${WS_BASE}/bots/${botId}/pnl/stream?token=${token}`;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'pnl_update' && msg.data) {
            setPnL(msg.data);
          }
        } catch {}
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconectar após 5 segundos
        retryRef.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      wsRef.current?.close();
      if (retryRef.current) clearTimeout(retryRef.current);
    };
  }, [botId]);

  return { pnl, connected };
}
```

### Arquivo: `src/components/kucoin/KuCoinDashboard.tsx`

Adicione import do hook e um painel de P&L abaixo do banner do robô:

```tsx
// No topo — imports
import { useBotPnL } from '@/hooks/use-bot-pnl';

// Dentro do componente KuCoinDashboard
const activeBotId = localStorage.getItem('active_bot_id');
const { pnl, connected: pnlConnected } = useBotPnL(activeBotConfig ? activeBotId : null);
```

Adicione o painel de P&L logo abaixo do banner do robô:

```tsx
        {/* ── Painel P&L do Robô ────────────────────────────────────── */}
        {activeBotConfig && pnl && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* P&L Total */}
            <div className="bg-surface-raised border border-edge-subtle rounded-lg p-4">
              <p className="text-xs text-content-muted mb-1">P&L Total</p>
              <p className={`text-2xl font-bold font-mono ${pnl.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {pnl.total_pnl >= 0 ? '+' : ''}{pnl.total_pnl.toFixed(2)} USDT
              </p>
              <p className={`text-xs mt-1 ${pnl.total_pnl_percent >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {pnl.total_pnl_percent >= 0 ? '+' : ''}{pnl.total_pnl_percent.toFixed(2)}%
              </p>
            </div>
            {/* Total de Trades */}
            <div className="bg-surface-raised border border-edge-subtle rounded-lg p-4">
              <p className="text-xs text-content-muted mb-1">Total Trades</p>
              <p className="text-2xl font-bold font-mono text-content-primary">{pnl.total_trades}</p>
              <p className="text-xs text-content-muted mt-1">{pnl.winning_trades} vencedores</p>
            </div>
            {/* Win Rate */}
            <div className="bg-surface-raised border border-edge-subtle rounded-lg p-4">
              <p className="text-xs text-content-muted mb-1">Win Rate</p>
              <p className={`text-2xl font-bold font-mono ${pnl.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400'}`}>
                {pnl.win_rate.toFixed(1)}%
              </p>
            </div>
            {/* Status */}
            <div className="bg-surface-raised border border-edge-subtle rounded-lg p-4">
              <p className="text-xs text-content-muted mb-1">Status Engine</p>
              <p className={`text-sm font-semibold ${pnl.state === 'running' ? 'text-emerald-400' : 'text-yellow-400'}`}>
                {pnl.state === 'running' ? '● Executando' : `● ${pnl.state}`}
              </p>
              <p className="text-xs text-content-muted mt-1">
                {pnlConnected ? 'Ao vivo' : 'Reconectando...'}
              </p>
            </div>
          </div>
        )}
```

---

## PARTE 6 — Tabela de Histórico de Trades

**O que falta:** Endpoint `GET /api/trading/bots/{bot_instance_id}/trades` existe e retorna dados paginados. Nunca é chamado no frontend.

### Arquivo: `src/components/kucoin/BotTradeHistory.tsx` (CRIAR NOVO)

```tsx
/**
 * Tabela de histórico de trades de um bot específico.
 * Endpoint: GET /api/trading/bots/{instance_id}/trades?page=1&limit=20
 */
import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Clock, RefreshCw } from 'lucide-react';
import { apiCall } from '@/services/apiClient';
import { cn } from '@/lib/utils';

interface Trade {
  trade_id: string;
  pair: string;
  entry_timestamp: string;
  exit_timestamp: string | null;
  entry_price: number;
  exit_price: number | null;
  capital_usdt: number;
  pnl_net_usdt: number | null;
  roi_pct: number | null;
  exit_reason: string | null;
  holding_minutes: number | null;
  total_fees_usdt: number;
  status: string;
}

interface BotTradeHistoryProps {
  instanceId: string | null;
}

export function BotTradeHistory({ instanceId }: BotTradeHistoryProps) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<any>(null);

  const fetchTrades = async () => {
    if (!instanceId) return;
    setLoading(true);
    try {
      const res = await apiCall(`/api/trading/bots/${instanceId}/trades?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setTrades(data.trades || []);
        setSummary(data.summary || null);
      }
    } catch (e) {
      console.error('[TradeHistory] Erro:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrades();
    // Atualizar a cada 30 segundos
    const interval = setInterval(fetchTrades, 30_000);
    return () => clearInterval(interval);
  }, [instanceId]);

  if (!instanceId) return null;

  return (
    <div className="bg-surface-raised border border-edge-subtle rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-edge-subtle">
        <span className="font-semibold text-sm text-content-primary">
          Histórico de Trades do Robô
        </span>
        <button
          onClick={fetchTrades}
          disabled={loading}
          className="text-content-muted hover:text-content-secondary transition-colors"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Sumário */}
      {summary && (
        <div className="grid grid-cols-4 gap-px bg-edge-subtle border-b border-edge-subtle">
          {[
            { label: 'P&L Total', value: `${summary.total_pnl_usdt >= 0 ? '+' : ''}${summary.total_pnl_usdt?.toFixed(2)} USDT`, positive: summary.total_pnl_usdt >= 0 },
            { label: 'Win Rate', value: `${summary.win_rate?.toFixed(1)}%`, positive: summary.win_rate >= 50 },
            { label: 'Trades', value: `${summary.closed_trades}/${summary.total_trades}` },
            { label: 'Fees Pagas', value: `${summary.total_fees_usdt?.toFixed(4)} USDT` },
          ].map((stat) => (
            <div key={stat.label} className="px-4 py-3 bg-surface-raised">
              <p className="text-xs text-content-muted">{stat.label}</p>
              <p className={cn('text-sm font-bold font-mono mt-0.5',
                stat.positive === true ? 'text-emerald-400' :
                stat.positive === false ? 'text-red-400' :
                'text-content-primary'
              )}>
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Tabela */}
      {trades.length === 0 ? (
        <div className="py-12 text-center text-content-muted text-sm">
          {loading ? 'Carregando...' : 'Nenhum trade executado ainda.'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-edge-subtle text-xs text-content-muted">
                <th className="px-4 py-3 text-left">Par</th>
                <th className="px-4 py-3 text-right">Entrada</th>
                <th className="px-4 py-3 text-right">Saída</th>
                <th className="px-4 py-3 text-right">P&L</th>
                <th className="px-4 py-3 text-right">ROI</th>
                <th className="px-4 py-3 text-right">Duração</th>
                <th className="px-4 py-3 text-left">Motivo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-edge-subtle">
              {trades.map((t) => (
                <tr key={t.trade_id} className="hover:bg-surface-active/30 transition-colors">
                  <td className="px-4 py-3 font-mono font-medium">{t.pair}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-content-secondary">
                    ${t.entry_price?.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-content-secondary">
                    {t.exit_price ? `$${t.exit_price?.toLocaleString()}` : '—'}
                  </td>
                  <td className={cn('px-4 py-3 text-right font-mono font-semibold',
                    t.pnl_net_usdt == null ? 'text-content-muted' :
                    t.pnl_net_usdt >= 0 ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    {t.pnl_net_usdt == null ? '—' : `${t.pnl_net_usdt >= 0 ? '+' : ''}${t.pnl_net_usdt.toFixed(2)}`}
                  </td>
                  <td className={cn('px-4 py-3 text-right font-mono text-xs',
                    t.roi_pct == null ? 'text-content-muted' :
                    t.roi_pct >= 0 ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    {t.roi_pct == null ? '—' : `${t.roi_pct >= 0 ? '+' : ''}${t.roi_pct.toFixed(2)}%`}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-content-muted font-mono">
                    {t.holding_minutes == null ? '—' : `${t.holding_minutes}min`}
                  </td>
                  <td className="px-4 py-3 text-xs text-content-muted">
                    {t.exit_reason ?? (t.status === 'open' ? '⏳ Aberto' : '—')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

### Adicionar ao `KuCoinDashboard.tsx`

```tsx
// Import no topo
import { BotTradeHistory } from '@/components/kucoin/BotTradeHistory';

// Dentro do componente, buscar o instanceId
const activeBotInstanceId = localStorage.getItem('active_instance_id');

// Adicionar no JSX, ao final da seção principal (após o portfólio):
{activeBotConfig && (
  <BotTradeHistory instanceId={activeBotInstanceId} />
)}
```

---

## PARTE 7 — Configurar Redis (Sem Docker, Modo Desenvolvimento)

**Diagnóstico crítico:** O sistema já tem `MockRedis` em `backend/app/shared/redis_client.py`. Se `REDIS_URL` não estiver definido, ele usa mock automático — **o motor falha silenciosamente**.

### Opção A — Sem instalar nada (MockRedis — apenas simulação local)

O `MockRedis` já funciona para desenvolvimento sem Redis real. Basta não definir `REDIS_URL` no `.env`.

**Limitação:** P&L via WebSocket entre Engine e API não funciona em modo mock — cada processo tem sua própria memória.

### Opção B — Redis via Chocolatey (Windows, sem Docker)

```powershell
# 1. Instalar Chocolatey (se não tiver)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 2. Instalar Redis
choco install redis-64

# 3. Iniciar Redis
redis-server

# 4. Testar (em outro terminal)
redis-cli ping
# Esperado: PONG
```

### Opção C — Redis via Docker (recomendado para produção)

```powershell
# Requer Docker Desktop instalado
docker run -d --name redis-trading -p 6379:6379 redis:7-alpine
```

### Arquivo: `backend/.env`

```env
# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=

# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=crypto_trade_hub

# JWT
SECRET_KEY=sua-chave-secreta-muito-longa-aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# KuCoin
KUCOIN_ENCRYPTION_KEY=chave-de-32-bytes-para-criptografar

# App
APP_MODE=development
```

---

## PARTE 8 — Rodar o Motor de Trading (Engine)

**Contexto:** A Engine é um processo Python separado. Ela lê a fila Redis e gerencia os `BotWorkers`. Sem ela, bots são criados no banco mas nunca executam ordens.

### Verificação prévia

```powershell
# No terminal com venv ativado:
cd backend

# Verificar se Redis está acessível:
python -c "import asyncio; from app.shared.redis_client import get_redis; asyncio.run(get_redis())" 
```

### Iniciar o motor

```powershell
# Terminal 1 — Backend FastAPI (já rodando pela task do VS Code)
# Terminal 2 — Engine (novo terminal)

cd C:\Users\CLIENTE\Downloads\crypto-trade-hub-main\crypto-trade-hub-main\backend
.venv\Scripts\activate
python -m app.engine.main
```

**Log esperado:**
```
2026-03-03 10:00:00 [INFO] engine.main — 🔧 Inicializando Engine de Trading...
2026-03-03 10:00:00 [INFO] engine.main — ✅ Banco de dados conectado
2026-03-03 10:00:00 [INFO] engine.main — ✅ Redis conectado
2026-03-03 10:00:00 [INFO] engine.main — 🔧 Engine ID: engine-1234 | Capacity: 50 bots
```

### Se a Engine falhar ao iniciar

**Erro: `ModuleNotFoundError: No module named 'app'`**
```powershell
# Solução: rodar de dentro da pasta backend/
cd backend
python -m app.engine.main
```

**Erro: `ConnectionRefusedError: Redis connection refused`**
```powershell
# Redis não está rodando. Iniciar Redis primeiro:
redis-server  # ou docker start redis-trading
```

**Erro: `SubscriptionRequired`**
O usuário não tem plano ativo. O motor verifica `app.auth.subscription.verificar_assinatura_ativa` antes de ativar bots.

### Adicionar task no VS Code

Adicione em `.vscode/tasks.json`:

```json
{
  "label": "Trading Engine",
  "type": "shell",
  "command": "cd backend; python -m app.engine.main",
  "isBackground": true,
  "problemMatcher": []
}
```

---

## PARTE 9 — Validar Credenciais Antes de Ativar Robô

**Problema crítico de UX:** Usuário ativa um robô sem ter configurado as credenciais KuCoin. Vai para o Dashboard, o banner aparece, mas nenhuma ordem é executada. Sem feedback de erro.

### Verificação no `BotConfigModal.tsx`

Adicione verificação no início de `handleActivate`:

```tsx
  const handleActivate = async () => {
    if (!validate()) return;

    setActivating(true);
    try {
      // ── 0. Verificar se credenciais KuCoin estão configuradas ────────
      const kuCoinConnected = localStorage.getItem('kucoin_connected') === 'true';
      if (!kuCoinConnected) {
        // Verificar no backend
        try {
          const credRes = await apiCall('/user/settings/exchanges');
          if (credRes.ok) {
            const creds = await credRes.json();
            const kucoin = creds.find((c: any) => c.exchange === 'kucoin' && c.connected);
            if (!kucoin) {
              setErrors({
                general: '⚠️ Configure suas credenciais KuCoin em Configurações antes de ativar um robô.',
              });
              setActivating(false);
              return;
            }
            localStorage.setItem('kucoin_connected', 'true');
          }
        } catch {
          // Falha de rede: avisa mas continua
          setErrors({ general: 'Não foi possível verificar credenciais. Continuando...' });
        }
      }

      // ... resto do handleActivate
```

### Verificação visual no Marketplace

Em `RobotsGameMarketplace.tsx`, antes de abrir o `BotConfigModal`, adicione um toast de aviso se `kucoin_connected !== 'true'`:

```tsx
  const handleActivateRobot = (robotId: string) => {
    if (localStorage.getItem('kucoin_connected') !== 'true') {
      // Mostrar aviso — use o sistema de toast do projeto
      console.warn('Credenciais KuCoin não configuradas');
      // TODO: toast('Configure suas credenciais em Configurações primeiro')
    }
    // ... resto do handler
  };
```

---

## PARTE 10 — Checklist de Produção e Variáveis de Ambiente

### Variáveis obrigatórias para produção

```env
# === SEGURANÇA ===
SECRET_KEY=gerar-com: python -c "import secrets; print(secrets.token_hex(32))"
KUCOIN_ENCRYPTION_KEY=gerar-com: python -c "import secrets; print(secrets.token_hex(16))"
# A chave de criptografia deve ter exatamente 32 chars (AES-256)

# === BANCO DE DADOS ===
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DB_NAME=crypto_trade_hub_prod

# === REDIS ===
REDIS_URL=redis://:senha@redis-host:6379
REDIS_PASSWORD=senha-forte-aqui

# === URLS ===
FRONTEND_URL=https://seu-dominio.com
API_BASE_URL=https://api.seu-dominio.com

# === GOOGLE OAUTH (opcional) ===
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# === PLANOS ===
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Variáveis no Frontend

Crie `src/.env.production`:
```env
VITE_API_URL=https://api.seu-dominio.com
VITE_WS_URL=wss://api.seu-dominio.com
```

Crie `src/.env.development` (já funciona por padrão):
```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### Checklist final antes de ir para produção

```
INFRAESTRUTURA
  [x] Frontend Vite rodando (porta 8081)
  [x] Backend FastAPI rodando (porta 8000)
  [ ] Redis rodando e acessível
  [ ] Motor (python -m app.engine.main) rodando como serviço
  [ ] MongoDB com índices criados (engine/migrations.py)

FRONTEND
  [x] Parte 1: KuCoinNativeChart no Dashboard com par do robô
  [x] Parte 2: BotConfigModal chama POST /bots
  [x] Parte 3: POST /bots/{id}/start após criação
  [x] Parte 4: Botão "Parar Robô" no banner
  [x] Parte 5: Painel P&L ao vivo (WebSocket)
  [x] Parte 6: Tabela de histórico de trades
  [ ] Parte 9: Validação de credenciais antes de ativar

BACKEND
  [ ] REDIS_URL no .env
  [ ] KUCOIN_ENCRYPTION_KEY com exatamente 32 chars
  [ ] Parte 7: Redis configurado e testado
  [ ] Parte 8: Engine iniciada e conectada ao Redis

SEGURANÇA
  [ ] SECRET_KEY gerada aleatoriamente (não hardcoded)
  [ ] CORS restrito ao domínio de produção
  [ ] Credenciais KuCoin criptografadas no banco (já implementado)
  [ ] HTTPS em produção (ngrok, nginx, ou serviço cloud)

OPCIONAL MAS RECOMENDADO
  [ ] Supervisord ou PM2 para manter Engine rodando
  [ ] Alertas de email quando bot para inesperadamente
  [ ] Limite de perda diária configurável por usuário
```

### Comandos para gerar chaves seguras

```powershell
# SECRET_KEY (FastAPI JWT)
python -c "import secrets; print(secrets.token_hex(32))"

# KUCOIN_ENCRYPTION_KEY (AES-256, deve ter 32 bytes)
python -c "import secrets; print(secrets.token_bytes(16).hex())"
# ATENÇÃO: use os primeiros 32 chars do output acima
```

### Ordem de inicialização correta

```powershell
# 1. Redis
redis-server

# 2. Backend FastAPI
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Engine (processo separado)
cd backend
python -m app.engine.main

# 4. Frontend
npx vite --port 8081
```

---

## Resumo — Tempo Estimado por Parte

| Parte | Descrição | Tempo |
|---|---|---|
| 1 | Gráfico tempo real no Dashboard | 20 min |
| 2 | BotConfigModal → POST /bots | 25 min |
| 3 | POST /bots/{id}/start + créditos | 30 min |
| 4 | Botão "Parar Robô" | 15 min |
| 5 | P&L ao vivo via WebSocket | 40 min |
| 6 | Tabela histórico de trades | 35 min |
| 7 | Configurar Redis | 15 min |
| 8 | Rodar motor de trading | 10 min |
| 9 | Validar credenciais antes de ativar | 20 min |
| 10 | Checklist de produção + .env | 30 min |
| **Total** | | **~4 horas** |
