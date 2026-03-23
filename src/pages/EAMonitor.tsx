/**
 * EAMonitor — Painel de monitoramento em tempo real do PRICEPRO SaaS
 *
 * Exibe:
 *  - Estado global do sistema (FSM)
 *  - Telemetria do EA ativo
 *  - Cards de estratégias registradas (4 EAs) com botões de ativação
 *  - Botão de desativação
 *  - Audit log dos últimos 50 eventos
 *
 * Atualização automática a cada 5 segundos.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Clock,
  DollarSign,
  Layers,
  Loader2,
  Link2,
  Monitor,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Shield,
  TrendingDown,
  TrendingUp,
  Wifi,
  WifiOff,
  X,
  Zap,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import {
  type ActivationResponse,
  type AuditLogEntry,
  type SystemStateResponse,
  type EATelemetry,
  STRATEGY_REGISTRY,
  activateStrategy,
  deactivateStrategy,
  getAuditLog,
  getSystemState,
  eaStatusColor,
  eaStatusLabel,
  formatUptime,
  stateColor,
  stateLabel,
  timeframeColor,
} from '@/services/strategyManagerService';
import {
  type EAAccountInfo,
  type EAPosition,
  type EALiveTelemetry,
  type EAUpdateMessage,
  connectEAAccount,
  listEAAccounts,
} from '@/services/eaMonitorService';

// ─────────────────────────────────────────────────────────────────────────────
// Componentes de badge reutilizáveis
// ─────────────────────────────────────────────────────────────────────────────

function Badge({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${className}`}
    >
      {children}
    </span>
  );
}

function SystemStateBadge({ state }: { state: string }) {
  const colorMap: Record<string, string> = {
    IDLE: 'bg-slate-700/50 text-slate-300 border-slate-600/50',
    ACTIVE: 'bg-green-600/20 text-green-300 border-green-500/40',
    TRANSITION_STATE: 'bg-yellow-600/20 text-yellow-300 border-yellow-500/40',
    CLOSING_POSITIONS: 'bg-orange-600/20 text-orange-300 border-orange-500/40',
    SAFE_TO_SWITCH: 'bg-blue-600/20 text-blue-300 border-blue-500/40',
    ACTIVATING_NEW_STRATEGY: 'bg-purple-600/20 text-purple-300 border-purple-500/40',
  };
  const cls = colorMap[state] ?? 'bg-slate-700/50 text-slate-300 border-slate-600/50';
  return <Badge className={cls}>{stateLabel(state)}</Badge>;
}

function AuditLevelBadge({ level }: { level: string }) {
  const colorMap: Record<string, string> = {
    INFO: 'bg-blue-600/20 text-blue-300 border-blue-500/30',
    WARNING: 'bg-yellow-600/20 text-yellow-300 border-yellow-500/30',
    ERROR: 'bg-red-600/20 text-red-300 border-red-500/30',
    CRITICAL: 'bg-red-700/30 text-red-200 border-red-500/50',
    SUCCESS: 'bg-green-600/20 text-green-300 border-green-500/30',
  };
  const cls =
    colorMap[(level ?? '').toUpperCase()] ??
    'bg-slate-600/20 text-slate-300 border-slate-500/30';
  return <Badge className={cls}>{level ?? '—'}</Badge>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Painel de métricas (helper)
// ─────────────────────────────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  valueClass = 'text-white',
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon?: React.ElementType;
  valueClass?: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
        {Icon && <Icon size={12} />}
        {label}
      </div>
      <div className={`text-xl font-bold ${valueClass}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Formatar timestamp
// ─────────────────────────────────────────────────────────────────────────────

function fmt(ts: string | null | undefined): string {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return ts;
  }
}

function fmtPnl(value: number | undefined | null): string {
  if (value == null) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${value.toFixed(2)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────────────────────

export default function EAMonitor() {
  const { toast } = useToast();

  // ── Strategy Manager state ─────────────────────────────────────────────
  const [systemState, setSystemState] = useState<SystemStateResponse | null>(null);
  const [telemetry, setTelemetry] = useState<EATelemetry | null>(null);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activating, setActivating] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // ── MT4/MT5 Account Connection state ──────────────────────────────────
  const [accounts, setAccounts] = useState<EAAccountInfo[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [liveTelemetry, setLiveTelemetry] = useState<EALiveTelemetry | null>(null);
  const [livePositions, setLivePositions] = useState<EAPosition[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [showConnectForm, setShowConnectForm] = useState(false);
  const [showApiKey, setShowApiKey] = useState<string | null>(null);
  const [connectForm, setConnectForm] = useState({
    account_id: '',
    account_name: '',
    server: '',
    broker: '',
  });
  const [connecting, setConnecting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // ── Strategy Manager fetch ─────────────────────────────────────────────────

  const fetchAll = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      const [state, log] = await Promise.all([
        getSystemState(),
        getAuditLog(50),
      ]);
      setSystemState(state);
      setAuditLog(log.entries ?? []);
      setLastRefresh(new Date());
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro ao carregar dados';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // ── auto refresh strategy manager ─────────────────────────────────────────

  useEffect(() => {
    fetchAll(false);
    const id = setInterval(() => fetchAll(true), 5000);
    return () => clearInterval(id);
  }, [fetchAll]);

  // ── Load connected EA accounts on mount ───────────────────────────────────

  useEffect(() => {
    listEAAccounts()
      .then((accs) => {
        setAccounts(accs);
        // Auto-select the first connected account
        const connected = accs.find((a) => a.connected);
        if (connected && !selectedAccountId) {
          setSelectedAccountId(connected.account_id);
        }
      })
      .catch(() => { /* non-fatal */ });
  }, []);

  // ── WebSocket connection for real-time EA telemetry ────────────────────────

  useEffect(() => {
    if (!selectedAccountId) {
      setWsConnected(false);
      setLiveTelemetry(null);
      setLivePositions([]);
      return;
    }

    const token = localStorage.getItem('access_token') ?? '';
    const wsBase = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsBase}//${wsHost}/ws/ea/${selectedAccountId}?token=${encodeURIComponent(token)}`;

    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let unmounted = false;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!unmounted) setWsConnected(true);
      };

      ws.onmessage = (ev) => {
        if (unmounted) return;
        try {
          const msg: EAUpdateMessage = JSON.parse(ev.data);
          if (msg.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }));
            return;
          }
          if ((msg.type === 'ea_update' || msg.type === 'ea_snapshot') && msg.telemetry) {
            setLiveTelemetry(msg.telemetry);
            setLivePositions(msg.positions ?? []);
            // Bridge live telemetry into the EATelemetry type expected by render sections
            setTelemetry({
              strategy_id: msg.telemetry.strategy_id || selectedAccountId,
              magic_number: msg.telemetry.magic_number ?? 0,
              status: (msg.telemetry.status as any) ?? 'RUNNING',
              manager_state_local: msg.telemetry.manager_state_local ?? 'RUNNING',
              permitted: msg.telemetry.permitted,
              kill_switch_active: msg.telemetry.kill_switch_active,
              open_positions: msg.telemetry.open_positions,
              open_orders: msg.telemetry.open_orders,
              unrealized_pnl: msg.telemetry.unrealized_pnl,
              realized_pnl_today: msg.telemetry.realized_pnl_today,
              floating_drawdown: msg.telemetry.floating_drawdown,
              max_drawdown_today: msg.telemetry.max_drawdown_today,
              account_balance: msg.telemetry.account_balance,
              account_equity: msg.telemetry.account_equity,
              heartbeat: msg.telemetry.heartbeat,
              uptime_seconds: msg.telemetry.uptime_seconds,
              last_trade_open: msg.telemetry.last_trade_open ?? undefined,
              last_trade_close: msg.telemetry.last_trade_close ?? undefined,
            });
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = (ev) => {
        if (unmounted) return;
        setWsConnected(false);
        // Auto-reconnect after 4s unless intentional close
        if (ev.code !== 1000 && ev.code !== 4001 && ev.code !== 4002 && ev.code !== 4003) {
          reconnectTimer = setTimeout(() => { if (!unmounted) connect(); }, 4000);
        }
      };

      ws.onerror = () => {
        setWsConnected(false);
      };
    };

    connect();

    return () => {
      unmounted = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close(1000, 'component unmounted');
      wsRef.current = null;
    };
  }, [selectedAccountId]);

  // ── MT4/MT5 Account connect handler ───────────────────────────────────────

  const handleConnect = async () => {
    if (!/^\d{3,20}$/.test(connectForm.account_id)) {
      toast({ title: 'Número de conta inválido', description: 'Digite apenas dígitos (3-20 chars).', variant: 'destructive' });
      return;
    }
    setConnecting(true);
    try {
      const res = await connectEAAccount({
        account_id: connectForm.account_id,
        account_name: connectForm.account_name || undefined,
        server: connectForm.server || undefined,
        broker: connectForm.broker || undefined,
      });
      setShowApiKey(res.api_key);
      setShowConnectForm(false);
      setSelectedAccountId(res.account_id);
      // Refresh accounts list
      const updatedAccounts = await listEAAccounts();
      setAccounts(updatedAccounts);
      toast({ title: '✅ Conta registrada!', description: 'Configure o EA com o api_key exibido abaixo.' });
    } catch (err) {
      toast({
        title: 'Erro ao registrar conta',
        description: err instanceof Error ? err.message : 'Erro desconhecido',
        variant: 'destructive',
      });
    } finally {
      setConnecting(false);
    }
  };

  // ── ações ──────────────────────────────────────────────────────────────────

  const handleActivate = async (stratId: string, name: string) => {
    if (activating) return;
    setActivating(stratId);
    try {
      const res: ActivationResponse = await activateStrategy(stratId);
      if (res.success) {
        toast({
          title: `✅ Estratégia Ativada`,
          description: `${name} foi ativada com sucesso.`,
        });
        await fetchAll(true);
      } else {
        toast({
          title: 'Falha na Ativação',
          description: res.message ?? 'Verifique o backend.',
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Erro de Conexão',
        description: err instanceof Error ? err.message : 'Verifique o backend.',
        variant: 'destructive',
      });
    } finally {
      setActivating(null);
    }
  };

  const handleDeactivate = async () => {
    if (deactivating) return;
    setDeactivating(true);
    try {
      const res: ActivationResponse = await deactivateStrategy();
      if (res.success) {
        toast({ title: '⏹️ Sistema Desativado', description: res.message });
        setTelemetry(null);
        await fetchAll(true);
      } else {
        toast({
          title: 'Falha na Desativação',
          description: res.message,
          variant: 'destructive',
        });
      }
    } catch (err) {
      toast({
        title: 'Erro de Conexão',
        description: err instanceof Error ? err.message : 'Verifique o backend.',
        variant: 'destructive',
      });
    } finally {
      setDeactivating(false);
    }
  };

  // ── render helpers ─────────────────────────────────────────────────────────

  const isIdle = !systemState || systemState.system_state === 'IDLE';
  const inTransition =
    systemState?.system_state === 'TRANSITION_STATE' ||
    systemState?.system_state === 'CLOSING_POSITIONS' ||
    systemState?.system_state === 'SAFE_TO_SWITCH' ||
    systemState?.system_state === 'ACTIVATING_NEW_STRATEGY';

  const activeStratId = systemState?.active_strategy ?? null;

  // ─────────────────────────────────────────────────────────────────────────
  // Loading / Error states
  // ─────────────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
        <Loader2 className="animate-spin text-green-400" size={40} />
        <p className="text-slate-400">Carregando EA Monitor…</p>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Página principal
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 p-6 text-white">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-green-500/30 bg-green-600/20 p-3">
            <Monitor className="text-green-400" size={22} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">EA Monitor</h1>
            <p className="text-sm text-slate-400">
              PRICEPRO SaaS — Painel de Controle em Tempo Real
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-slate-500">
              Atualizado: {lastRefresh.toLocaleTimeString('pt-BR')}
            </span>
          )}
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            Atualizar
          </button>
          <button
            onClick={handleDeactivate}
            disabled={isIdle || deactivating || inTransition}
            className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-600/20 px-4 py-2 text-sm text-red-300 transition hover:bg-red-600/30 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {deactivating ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <PowerOff size={14} />
            )}
            Desativar Sistema
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-600/10 px-4 py-3 text-sm text-red-300">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {/* ── MT4/MT5 Account Connection Panel ─────────────────────────────── */}
      <div className="mb-6 rounded-2xl border border-blue-500/20 bg-white/5 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-300">
            <Link2 size={15} className="text-blue-400" />
            Contas MT4/MT5 Conectadas
            {wsConnected && (
              <span className="flex items-center gap-1 text-xs font-normal text-green-400">
                <Wifi size={11} /> Transmitindo dados ao vivo
              </span>
            )}
          </div>
          <button
            onClick={() => { setShowConnectForm((v) => !v); setShowApiKey(null); }}
            className="flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-600/20 px-3 py-1.5 text-xs text-blue-300 transition hover:bg-blue-600/30"
          >
            <Plus size={13} />
            Conectar Conta MT4/MT5
          </button>
        </div>

        {/* Connect form */}
        {showConnectForm && (
          <div className="mb-4 rounded-xl border border-white/10 bg-white/5 p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-300">Registrar nova conta</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs text-slate-400">Nº da Conta MT4/MT5 *</label>
                <input
                  type="text"
                  placeholder="ex: 1234567"
                  value={connectForm.account_id}
                  onChange={(e) => setConnectForm((f) => ({ ...f, account_id: e.target.value.replace(/\D/g, '') }))}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Nome amigável</label>
                <input
                  type="text"
                  placeholder="ex: Minha conta IC Markets"
                  value={connectForm.account_name}
                  onChange={(e) => setConnectForm((f) => ({ ...f, account_name: e.target.value }))}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Servidor</label>
                <input
                  type="text"
                  placeholder="ex: ICMarkets-Live04"
                  value={connectForm.server}
                  onChange={(e) => setConnectForm((f) => ({ ...f, server: e.target.value }))}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Corretora</label>
                <input
                  type="text"
                  placeholder="ex: IC Markets"
                  value={connectForm.broker}
                  onChange={(e) => setConnectForm((f) => ({ ...f, broker: e.target.value }))}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500/50 focus:outline-none"
                />
              </div>
            </div>
            <div className="mt-3 flex gap-2">
              <button
                onClick={handleConnect}
                disabled={connecting || !connectForm.account_id}
                className="flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-600/20 px-4 py-2 text-sm text-green-300 hover:bg-green-600/30 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {connecting ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                Registrar
              </button>
              <button
                onClick={() => setShowConnectForm(false)}
                className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-400 hover:bg-white/10"
              >
                <X size={13} /> Cancelar
              </button>
            </div>
          </div>
        )}

        {/* API key reveal after connect */}
        {showApiKey && (
          <div className="mb-4 rounded-xl border border-yellow-500/30 bg-yellow-600/10 p-4">
            <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-yellow-300">
              <Shield size={14} /> Configure o EA com esta api_key
            </h4>
            <p className="mb-2 text-xs text-slate-400">
              Cole este valor no parâmetro <code className="text-yellow-400">EA_API_KEY</code> do Expert Advisor no MetaEditor:
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-lg border border-yellow-500/20 bg-white/5 px-3 py-2 font-mono text-xs text-yellow-200 break-all">
                {showApiKey}
              </code>
              <button
                onClick={() => { navigator.clipboard?.writeText(showApiKey); toast({ title: 'Copiado!', duration: 1500 }); }}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs transition hover:bg-white/10"
              >
                Copiar
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              ⚠️ Guarde em local seguro — esta chave não pode ser recuperada depois.
            </p>
          </div>
        )}

        {/* Account list */}
        {accounts.length > 0 ? (
          <div className="space-y-2">
            {accounts.map((acc) => (
              <div
                key={acc.account_id}
                onClick={() => setSelectedAccountId(acc.account_id)}
                className={`flex cursor-pointer items-center justify-between rounded-xl border p-3 transition-all ${
                  selectedAccountId === acc.account_id
                    ? 'border-blue-500/40 bg-blue-600/10'
                    : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/8'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`h-2.5 w-2.5 rounded-full ${acc.connected ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,.8)]' : 'bg-slate-600'}`} />
                  <div>
                    <div className="text-sm font-medium text-white">{acc.account_name || `Conta ${acc.account_id}`}</div>
                    <div className="text-xs text-slate-400">{acc.broker || '—'} · {acc.server || '—'} · #{acc.account_id}</div>
                  </div>
                </div>
                <div className="text-right text-xs text-slate-400">
                  <div>Saldo: <span className="text-white font-medium">${acc.balance.toFixed(2)}</span></div>
                  <div>{acc.positions_count} posição(ões)</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-center text-xs text-slate-500 py-3">
            Nenhuma conta MT4/MT5 conectada. Clique em "Conectar Conta MT4/MT5" para começar.
          </p>
        )}
      </div>

      {/* ── Live Positions Table (from WebSocket) ────────────────────────── */}
      {livePositions.length > 0 && (
        <div className="mb-6 rounded-2xl border border-cyan-500/20 bg-white/5 p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300">
            <BarChart3 size={15} className="text-cyan-400" />
            Posições Abertas — {selectedAccountId}
            <span className="ml-auto rounded-full bg-cyan-600/20 px-2.5 py-0.5 text-xs text-cyan-300">
              {livePositions.length} posição(ões)
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs text-slate-500">
                  <th className="pb-2 pr-4">Símbolo</th>
                  <th className="pb-2 pr-4">Tipo</th>
                  <th className="pb-2 pr-4">Lote</th>
                  <th className="pb-2 pr-4">Abertura</th>
                  <th className="pb-2 pr-4">Atual</th>
                  <th className="pb-2 pr-4">SL/TP</th>
                  <th className="pb-2">P&L</th>
                </tr>
              </thead>
              <tbody>
                {livePositions.map((pos) => (
                  <tr key={pos.id} className="border-b border-white/5 transition hover:bg-white/5">
                    <td className="py-2 pr-4 font-mono text-slate-200">{pos.symbol}</td>
                    <td className={`py-2 pr-4 font-semibold ${pos.type === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>{pos.type}</td>
                    <td className="py-2 pr-4 text-slate-300">{pos.volume}</td>
                    <td className="py-2 pr-4 font-mono text-slate-300">{pos.open_price}</td>
                    <td className="py-2 pr-4 font-mono text-slate-200">{pos.current_price}</td>
                    <td className="py-2 pr-4 text-xs text-slate-400">{pos.sl || '—'} / {pos.tp || '—'}</td>
                    <td className={`py-2 font-semibold ${pos.profit >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                      {pos.profit >= 0 ? '+' : ''}${pos.profit.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Estado do Sistema ─────────────────────────────────────────────── */}
      <div className="mb-6 rounded-2xl border border-white/10 bg-white/5 p-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Zap size={15} className="text-yellow-400" />
          Estado do Sistema
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard
            label="Estado FSM"
            value={
              systemState ? (
                <SystemStateBadge state={systemState.system_state} />
              ) : (
                '—'
              )
            }
            icon={Activity}
          />
          <MetricCard
            label="Estratégia Ativa"
            value={systemState?.active_strategy ?? 'Nenhuma'}
            valueClass={
              systemState?.active_strategy ? 'text-green-300' : 'text-slate-400'
            }
            icon={Layers}
          />
          <MetricCard
            label="Última Troca"
            value={fmt(systemState?.last_switch)}
            icon={Clock}
            valueClass="text-sm text-slate-300"
          />
          <MetricCard
            label="Uptime do Gerenciador"
            value={formatUptime(systemState?.uptime_seconds)}
            sub={
              systemState?.uptime_seconds != null
                ? `${systemState.uptime_seconds}s`
                : undefined
            }
            icon={Power}
          />
        </div>
      </div>

      {/* ── Telemetria do EA Ativo ────────────────────────────────────────── */}
      {telemetry ? (
        <div className="mb-6 rounded-2xl border border-green-500/20 bg-white/5 p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-300">
              <Activity size={15} className="text-green-400" />
              Telemetria — {telemetry.strategy_id}
              <span className="ml-2">
                <Badge
                  className={`border ${eaStatusColor(telemetry.status)
                    .replace('text-', 'border-')
                    .replace('-400', '-500/40')
                    .replace('-300', '-500/40')
                    .replace('-500', '-500/40')} bg-slate-700/30 ${eaStatusColor(telemetry.status)}`}
                >
                  {eaStatusLabel(telemetry.status)}
                </Badge>
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              {Date.now() - new Date(telemetry.heartbeat).getTime() < 15000 ? (
                <span className="flex items-center gap-1 text-green-400">
                  <Wifi size={12} /> Heartbeat OK
                </span>
              ) : (
                <span className="flex items-center gap-1 text-red-400">
                  <WifiOff size={12} /> Heartbeat Atrasado
                </span>
              )}
              <span className="text-slate-500">{fmt(telemetry.heartbeat)}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            <MetricCard
              label="Posições Abertas"
              value={telemetry.open_positions}
              icon={BarChart3}
              valueClass={
                telemetry.open_positions > 0 ? 'text-blue-300' : 'text-slate-400'
              }
            />
            <MetricCard
              label="Ordens Abertas"
              value={telemetry.open_orders}
              icon={Layers}
            />
            <MetricCard
              label="PnL Flutuante"
              value={fmtPnl(telemetry.unrealized_pnl)}
              icon={
                (telemetry.unrealized_pnl ?? 0) >= 0 ? TrendingUp : TrendingDown
              }
              valueClass={
                (telemetry.unrealized_pnl ?? 0) >= 0
                  ? 'text-green-300'
                  : 'text-red-300'
              }
            />
            <MetricCard
              label="PnL Realizado Hoje"
              value={fmtPnl(telemetry.realized_pnl_today)}
              icon={DollarSign}
              valueClass={
                (telemetry.realized_pnl_today ?? 0) >= 0
                  ? 'text-green-300'
                  : 'text-red-300'
              }
            />
            <MetricCard
              label="Saldo"
              value={`$${telemetry.account_balance?.toFixed(2) ?? '—'}`}
              icon={DollarSign}
            />
            <MetricCard
              label="Equidade"
              value={`$${telemetry.account_equity?.toFixed(2) ?? '—'}`}
              icon={DollarSign}
            />
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricCard
              label="Magic Number"
              value={telemetry.magic_number}
              icon={Shield}
              valueClass="text-slate-300 text-base"
            />
            <MetricCard
              label="Kill Switch"
              value={
                telemetry.kill_switch_active ? (
                  <span className="text-red-400">ATIVO</span>
                ) : (
                  <span className="text-green-400">Off</span>
                )
              }
              icon={AlertTriangle}
            />
            <MetricCard
              label="Permissão"
              value={
                telemetry.permitted ? (
                  <span className="flex items-center gap-1 text-green-400">
                    <CheckCircle2 size={14} /> Permitido
                  </span>
                ) : (
                  <span className="text-red-400">Bloqueado</span>
                )
              }
            />
            <MetricCard
              label="Uptime do EA"
              value={formatUptime(telemetry.uptime_seconds)}
              sub={`${telemetry.uptime_seconds}s`}
              icon={Clock}
            />
          </div>
        </div>
      ) : !isIdle ? (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-yellow-500/20 bg-yellow-600/10 p-5 text-sm text-yellow-300">
          <Loader2 size={16} className="animate-spin" />
          Aguardando telemetria do EA ativo…
        </div>
      ) : null}

      {/* ── Registry de Estratégias ───────────────────────────────────────── */}
      <div className="mb-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
          <Layers size={18} className="text-blue-400" />
          Estratégias Disponíveis
        </h2>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {STRATEGY_REGISTRY.map((strat) => {
            const isActive = activeStratId === strat.id;
            const isLoading = activating === strat.id;

            return (
              <div
                key={strat.id}
                className={`relative overflow-hidden rounded-2xl border p-5 transition-all ${
                  isActive
                    ? 'border-green-500/40 bg-green-600/10'
                    : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/8'
                }`}
              >
                {isActive && (
                  <div className="absolute right-3 top-3">
                    <Badge className="border-green-500/40 bg-green-600/20 text-green-300">
                      <CheckCircle2 size={10} /> Ativo
                    </Badge>
                  </div>
                )}

                <div className="mb-3 flex items-center gap-2">
                  <span
                    className={`rounded-md border px-2 py-0.5 text-xs font-bold ${timeframeColor(strat.timeframe)}`}
                  >
                    {strat.timeframe}
                  </span>
                </div>

                <h3 className="mb-1 font-semibold leading-tight">
                  {strat.display_name}
                </h3>
                <p className="mb-4 text-xs text-slate-400 line-clamp-3">
                  {strat.description}
                </p>

                <div className="mb-4 space-y-1 text-xs text-slate-500">
                  <div className="flex justify-between">
                    <span>Magic</span>
                    <span className="font-mono text-slate-300">
                      {strat.magic_number}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Versão</span>
                    <span className="text-slate-300">v{strat.version}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Shutdown timeout</span>
                    <span className="text-slate-300">
                      {strat.safe_shutdown_timeout_s}s
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleActivate(strat.id, strat.display_name)}
                  disabled={isActive || isLoading || !!activating || inTransition}
                  className={`flex w-full items-center justify-center gap-2 rounded-xl py-2 text-sm font-semibold transition-all ${
                    isActive
                      ? 'cursor-default border border-green-500/30 bg-green-600/20 text-green-300'
                      : 'border border-blue-500/30 bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 disabled:cursor-not-allowed disabled:opacity-40'
                  }`}
                >
                  {isLoading ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : isActive ? (
                    <CheckCircle2 size={14} />
                  ) : (
                    <ChevronRight size={14} />
                  )}
                  {isActive ? 'Ativo' : 'Ativar'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Audit Log ────────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
          <Shield size={18} className="text-purple-400" />
          Audit Log
          <span className="ml-2 text-xs font-normal text-slate-500">
            Últimas {auditLog.length} entradas
          </span>
        </h2>

        {auditLog.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            Nenhum evento registrado.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs text-slate-500">
                  <th className="pb-2 pr-4">Timestamp</th>
                  <th className="pb-2 pr-4">Nível</th>
                  <th className="pb-2 pr-4">Evento</th>
                  <th className="pb-2">Detalhes</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map((entry, i) => (
                  <tr
                    key={i}
                    className="border-b border-white/5 transition hover:bg-white/5"
                  >
                    <td className="py-2 pr-4 font-mono text-xs text-slate-400">
                      {fmt(entry.timestamp)}
                    </td>
                    <td className="py-2 pr-4">
                      <AuditLevelBadge level={entry.level ?? '—'} />
                    </td>
                    <td className="py-2 pr-4 text-slate-200">
                      {entry.event ?? '—'}
                    </td>
                    <td className="py-2 max-w-[260px] truncate text-xs text-slate-500">
                      {entry.data
                        ? JSON.stringify(entry.data).slice(0, 120)
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
