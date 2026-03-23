import { useState, useEffect } from 'react';
import { RefreshCw, Wallet, TrendingUp, TrendingDown, Eye, EyeOff, Copy, Check, AlertCircle, BarChart2, Zap, Bot, Target, ShieldAlert, Clock, Activity, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from '@/hooks/use-language';
import type { BotConfig } from '@/components/gamification/BotConfigModal';
import KuCoinNativeChart from '@/components/kucoin/KuCoinNativeChart';
import { useBotPnL } from '@/hooks/use-bot-pnl';
import { BotTradeHistory } from '@/components/kucoin/BotTradeHistory';

interface KuCoinAccount {
  subUserId: string;
  subName: string;
  remarks: string;
  accountType: string;
}

interface KuCoinBalance {
  id: string;
  currency: string;
  type: string;
  balance: string;
  available: string;
  holds: string;
}

interface KuCoinDashboardProps {
  accessToken: string;
  activeBotConfig?: BotConfig | null;
  onBotStop?: () => void;
}

// ── Skeleton de card KPI ─────────────────────────────────────────────────
function MetricSkeleton() {
  return (
    <div className="bg-surface-raised border border-edge-subtle rounded-lg p-6 animate-pulse">
      <div className="flex justify-between mb-4">
        <div className="h-3 bg-surface-active rounded w-24" />
        <div className="h-4 w-4 bg-surface-active rounded" />
      </div>
      <div className="h-8 bg-surface-active rounded w-32 mb-2" />
      <div className="h-3 bg-surface-active rounded w-20" />
    </div>
  );
}

// ── Card de KPI reutilizável ─────────────────────────────────────────────
function MetricCard({
  title,
  value,
  sub,
  icon,
  valueClass,
  action,
}: {
  title: string;
  value: string;
  sub?: string;
  icon?: React.ReactNode;
  valueClass?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="group bg-surface-raised border border-edge-subtle rounded-lg p-6 relative overflow-hidden transition-all duration-200 hover:border-edge-default">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium text-content-secondary uppercase tracking-widest">
          {title}
        </span>
        <div className="flex items-center gap-2 text-content-muted">
          {icon}
          {action}
        </div>
      </div>
      <p className={cn('font-mono font-semibold text-3xl tabular-nums tracking-tight', valueClass ?? 'text-content-primary')}>
        {value}
      </p>
      {sub && <p className="text-xs text-content-muted mt-2">{sub}</p>}
      {/* Linha de accent no hover */}
      <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand-primary/0 group-hover:bg-brand-primary/40 transition-all duration-300" />
    </div>
  );
}

export function KuCoinDashboard({ accessToken, activeBotConfig, onBotStop }: KuCoinDashboardProps) {
  const { t } = useLanguage();
  const [account, setAccount] = useState<KuCoinAccount | null>(null);
  const [balances, setBalances] = useState<KuCoinBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showBalances, setShowBalances] = useState(true);
  const [copied, setCopied] = useState<string | null>(null);

  const fetchKuCoinData = async () => {
    try {
      setRefreshing(true);
      setError(null);

      const accountResponse = await fetch('http://localhost:8000/api/trading/kucoin/account', {
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
      }).catch(err => { throw new Error(`${t('dashboard.networkErrorAccount')}: ${err.message}`); });

      if (accountResponse.ok) {
        const accountData = await accountResponse.json();
        if (accountData.status !== 'error') setAccount(accountData);
      }

      const balanceResponse = await fetch('http://localhost:8000/api/trading/kucoin/balances', {
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
      }).catch(err => { throw new Error(`${t('dashboard.networkErrorBalances')}: ${err.message}`); });

      if (balanceResponse.ok) {
        const balanceData = await balanceResponse.json();
        if (balanceData.status !== 'error') {
          setBalances(Array.isArray(balanceData) ? balanceData : (balanceData.balances || []));
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dashboard.loadError'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchKuCoinData(); }, [accessToken]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const totalBalance     = balances.reduce((sum, b) => sum + parseFloat(b.balance   || '0'), 0);
  const availableBalance = balances.reduce((sum, b) => sum + parseFloat(b.available || '0'), 0);
  const holdBalance      = balances.reduce((sum, b) => sum + parseFloat(b.holds     || '0'), 0);
  const activeBalances   = balances.filter(b => parseFloat(b.balance || '0') > 0);

  const mask = (v: string) => showBalances ? v : '••••••';

  // ── P&L em Tempo Real ───────────────────────────────────────────────────
  const activeBotId = localStorage.getItem('active_bot_id');
  const activeBotInstanceId = localStorage.getItem('active_instance_id');
  const { pnl, connected: pnlConnected } = useBotPnL(activeBotConfig ? activeBotId : null);

  // ── Parar Robô ──────────────────────────────────────────────────────────
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

    // Callback ou reload
    if (onBotStop) {
      onBotStop();
    } else {
      window.location.reload();
    }
  };

  // ── Loading skeleton ─────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-surface-base p-6 md:p-8">
        <div className="max-w-[1600px] mx-auto space-y-6">
          <div className="h-8 bg-surface-raised rounded w-48 animate-pulse" />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <MetricSkeleton />
            <MetricSkeleton />
            <MetricSkeleton />
          </div>
          <div className="h-64 bg-surface-raised border border-edge-subtle rounded-lg animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-base">
      <div className="max-w-[1600px] mx-auto px-6 py-8 space-y-6">

        {/* ── Robô Ativo Banner ─────────────────────────────────────── */}
        {activeBotConfig && (
          <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-emerald-950/60 to-slate-900/80 border border-emerald-500/30">
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 h-10 w-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <Bot size={20} className="text-emerald-400" />
              </div>
              <div>
                <p className="text-xs text-emerald-400 font-semibold uppercase tracking-widest">Robô Ativo</p>
                <p className="text-base font-bold text-white">{activeBotConfig.robotName}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3 sm:ml-4">
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-edge-subtle">
                <Activity size={13} className="text-content-muted" />
                <span className="text-xs text-content-secondary">Par:</span>
                <span className="text-xs font-bold text-white font-mono">{activeBotConfig.pair}</span>
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-edge-subtle">
                <Target size={13} className="text-emerald-400" />
                <span className="text-xs text-content-secondary">TP:</span>
                <span className="text-xs font-bold text-emerald-400">{activeBotConfig.takeProfitPct}%</span>
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-edge-subtle">
                <ShieldAlert size={13} className="text-red-400" />
                <span className="text-xs text-content-secondary">SL:</span>
                <span className="text-xs font-bold text-red-400">{activeBotConfig.stopLossPct}%</span>
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-edge-subtle">
                <Wallet size={13} className="text-blue-400" />
                <span className="text-xs text-content-secondary">Invest:</span>
                <span className="text-xs font-bold text-blue-400">${activeBotConfig.investmentUsdt} USDT</span>
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-edge-subtle">
                <Clock size={13} className="text-content-muted" />
                <span className="text-xs text-content-secondary">TF:</span>
                <span className="text-xs font-bold text-white">{activeBotConfig.timeframe}</span>
              </div>
            </div>
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
          </div>
        )}

        {/* ── Gráfico em Tempo Real ─────────────────────────────────────── */}
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

        {/* ── Painel P&L ao Vivo ───────────────────────────────────────── */}
        {activeBotConfig && (
          <div className="rounded-xl border border-border-subtle bg-surface-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-semantic-profit" />
                <span className="text-sm font-semibold text-content-primary">P&amp;L em Tempo Real</span>
              </div>
              <span className={cn(
                'text-xs px-2 py-0.5 rounded-full font-medium',
                pnlConnected
                  ? 'bg-semantic-profit/10 text-semantic-profit'
                  : 'bg-surface-hover text-content-muted'
              )}>
                {pnlConnected ? '● Conectado' : '○ Reconectando…'}
              </span>
            </div>

            {pnl ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {/* P&L Total */}
                <div className="rounded-lg bg-surface-hover p-3">
                  <p className="text-xs text-content-muted mb-1">P&amp;L Total</p>
                  <p className={cn(
                    'text-lg font-bold font-mono',
                    pnl.total_pnl >= 0 ? 'text-semantic-profit' : 'text-semantic-loss'
                  )}>
                    {pnl.total_pnl >= 0 ? '+' : ''}{pnl.total_pnl.toFixed(4)} USDT
                  </p>
                  <p className={cn(
                    'text-xs font-mono',
                    pnl.total_pnl_percent >= 0 ? 'text-semantic-profit' : 'text-semantic-loss'
                  )}>
                    {pnl.total_pnl_percent >= 0 ? '+' : ''}{pnl.total_pnl_percent.toFixed(2)}%
                  </p>
                </div>

                {/* Total de Trades */}
                <div className="rounded-lg bg-surface-hover p-3">
                  <p className="text-xs text-content-muted mb-1">Trades</p>
                  <p className="text-lg font-bold text-content-primary">{pnl.total_trades}</p>
                  <p className="text-xs text-content-secondary">
                    {pnl.winning_trades} vencedores
                  </p>
                </div>

                {/* Win Rate */}
                <div className="rounded-lg bg-surface-hover p-3 col-span-2 sm:col-span-1">
                  <p className="text-xs text-content-muted mb-1">Win Rate</p>
                  <p className={cn(
                    'text-lg font-bold',
                    pnl.win_rate >= 50 ? 'text-semantic-profit' : 'text-semantic-loss'
                  )}>
                    {pnl.win_rate.toFixed(1)}%
                  </p>
                  <div className="mt-1 h-1.5 rounded-full bg-surface-card overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-500',
                        pnl.win_rate >= 50 ? 'bg-semantic-profit' : 'bg-semantic-loss'
                      )}
                      style={{ width: `${Math.min(100, pnl.win_rate)}%` }}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-16 text-content-muted text-sm">
                <span className="animate-pulse">Aguardando dados do bot…</span>
              </div>
            )}
          </div>
        )}

        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="font-display font-bold text-3xl text-content-primary tracking-tight">
              {t('dashboard.kucoinTitle')}
            </h1>
            {account && (
              <div className="flex items-center gap-2 mt-1">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-semantic-profit opacity-40" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-semantic-profit" />
                </span>
                <span className="text-sm text-content-secondary">
                  {t('dashboard.connectedAs')}{' '}
                  <span className="text-content-primary font-medium">
                    {account.subName || t('dashboard.mainAccount')}
                  </span>
                </span>
              </div>
            )}
          </div>

          <button
            onClick={fetchKuCoinData}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-raised border border-edge-default text-sm font-medium text-content-primary hover:border-brand-primary/50 hover:text-brand-primary transition-all duration-150 disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
            {t('dashboard.refresh')}
          </button>
        </div>

        {/* ── Alerta de erro ───────────────────────────────────────── */}
        {error && (
          <div className="flex items-start gap-3 p-4 rounded-lg bg-semantic-loss/8 border border-semantic-loss/25">
            <AlertCircle className="h-4 w-4 text-semantic-loss flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-semantic-loss">{t('dashboard.errorLoadingData')}</p>
              <p className="text-xs text-content-secondary mt-1">{error}</p>
            </div>
            <button
              onClick={fetchKuCoinData}
              className="ml-auto text-xs font-medium text-brand-primary hover:text-brand-primary/80 transition-colors flex-shrink-0"
            >
              {t('dashboard.tryAgain')}
            </button>
          </div>
        )}

        {/* ── KPIs ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricCard
            title={t('dashboard.kpiTotalBalance')}
            value={mask(totalBalance.toFixed(2))}
            sub={t('dashboard.kpiAllCoins')}
            icon={<Wallet size={16} />}
            action={
              <button
                onClick={() => setShowBalances(!showBalances)}
                className="text-content-muted hover:text-content-secondary transition-colors"
                aria-label={t('dashboard.showHideBalances')}
              >
                {showBalances ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            }
          />
          <MetricCard
            title={t('dashboard.kpiAvailable')}
            value={mask(availableBalance.toFixed(2))}
            sub={t('dashboard.kpiReadyToTrade')}
            icon={<TrendingUp size={16} className="text-semantic-profit" />}
            valueClass="text-semantic-profit"
          />
          <MetricCard
            title={t('dashboard.kpiOnHold')}
            value={mask(holdBalance.toFixed(2))}
            sub={t('dashboard.kpiAwaitingProcessing')}
            icon={<TrendingDown size={16} className="text-semantic-warning" />}
            valueClass={holdBalance > 0 ? 'text-semantic-warning' : 'text-content-primary'}
          />
        </div>

        {/* ── Portfólio + Info ─────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Moedas ativas */}
          <div className="lg:col-span-2 bg-surface-raised border border-edge-subtle rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-edge-subtle">
              <div className="flex items-center gap-2">
                <Wallet size={16} className="text-content-muted" />
                <span className="font-display font-semibold text-sm text-content-primary">
                  {t('dashboard.portfolio')}
                </span>
              </div>
              <span className="text-xs font-mono text-content-muted tabular-nums">
                {activeBalances.length} {activeBalances.length === 1 ? t('dashboard.coin') : t('dashboard.coins')}
              </span>
            </div>

            {activeBalances.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center px-6">
                <div className="w-10 h-10 rounded-lg bg-surface-hover flex items-center justify-center mb-3">
                  <BarChart2 size={18} className="text-content-muted" />
                </div>
                <p className="text-sm font-medium text-content-primary mb-1">{t('dashboard.noCoinsBalance')}</p>
                <p className="text-xs text-content-secondary max-w-xs">
                  {t('dashboard.depositNotice')}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-edge-subtle">
                {activeBalances.map((balance) => (
                  <div
                    key={balance.id}
                    className="flex items-center gap-4 px-6 py-3 hover:bg-surface-hover transition-colors"
                  >
                    {/* Avatar */}
                    <div className="w-8 h-8 rounded-md bg-brand-primary/10 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-brand-primary">
                        {balance.currency.charAt(0).toUpperCase()}
                      </span>
                    </div>

                    {/* Nome + tipo */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-content-primary">{balance.currency.toUpperCase()}</p>
                      <p className="text-2xs text-content-muted capitalize">{balance.type}</p>
                    </div>

                    {/* Saldos */}
                    <div className="text-right">
                      <p className="font-mono text-sm font-semibold text-content-primary tabular-nums">
                        {showBalances ? parseFloat(balance.balance).toFixed(8) : '••••••••'}
                      </p>
                      {parseFloat(balance.holds) > 0 && showBalances && (
                        <p className="font-mono text-2xs text-semantic-warning tabular-nums">
                          Hold: {parseFloat(balance.holds).toFixed(8)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Painel lateral */}
          <div className="space-y-4">

            {/* Informações da Conta */}
            <div className="bg-surface-raised border border-edge-subtle rounded-lg p-6 space-y-4">
              <h3 className="text-xs font-medium text-content-secondary uppercase tracking-widest">
                {t('dashboard.accountInfo')}
              </h3>

              {account ? (
                <>
                  <div>
                    <p className="text-2xs text-content-muted mb-1">{t('dashboard.accountType')}</p>
                    <p className="text-sm font-semibold text-content-primary capitalize">
                      {account.accountType || 'Trading'}
                    </p>
                  </div>
                  <div>
                    <p className="text-2xs text-content-muted mb-1">{t('dashboard.subAccountId')}</p>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-content-body truncate flex-1">
                        {account.subUserId}
                      </span>
                      <button
                        onClick={() => handleCopy(account.subUserId, 'id')}
                        className="text-content-muted hover:text-content-secondary transition-colors flex-shrink-0"
                      >
                        {copied === 'id'
                          ? <Check size={14} className="text-semantic-profit" />
                          : <Copy size={14} />
                        }
                      </button>
                    </div>
                  </div>
                  {account.remarks && (
                    <div>
                      <p className="text-2xs text-content-muted mb-1">{t('dashboard.remarks')}</p>
                      <p className="text-xs text-content-body">{account.remarks}</p>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-content-muted">{t('dashboard.noInfoAvailable')}</p>
              )}

              <div className="pt-4 border-t border-edge-subtle space-y-2">
                <p className="text-2xs text-content-muted uppercase tracking-widest mb-3">{t('dashboard.status')}</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-content-secondary">{t('dashboard.apiKucoin')}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-semantic-profit opacity-50" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-semantic-profit" />
                    </span>
                    <span className="text-xs text-semantic-profit font-medium">{t('dashboard.connected')}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-content-secondary">{t('dashboard.sync')}</span>
                  <span className="text-xs text-brand-primary font-medium">{t('dashboard.syncActive')}</span>
                </div>
              </div>
            </div>

            {/* Ações Rápidas */}
            <div className="bg-surface-raised border border-edge-subtle rounded-lg p-6 space-y-3">
              <h3 className="text-xs font-medium text-content-secondary uppercase tracking-widest">
                {t('dashboard.quickActions')}
              </h3>
              <button className="w-full flex items-center gap-3 px-4 py-2.5 rounded-md bg-surface-hover hover:bg-surface-active border border-edge-subtle text-sm font-medium text-content-primary transition-all duration-150 text-left">
                <BarChart2 size={15} className="text-content-muted" />
                {t('dashboard.viewCharts')}
              </button>
              <button className="w-full flex items-center gap-3 px-4 py-2.5 rounded-md bg-brand-primary/10 hover:bg-brand-primary/15 border border-brand-primary/20 text-sm font-medium text-brand-primary transition-all duration-150 text-left">
                <Zap size={15} />
                {t('dashboard.makeTrade')}
              </button>
              <button className="w-full flex items-center gap-3 px-4 py-2.5 rounded-md bg-surface-hover hover:bg-surface-active border border-edge-subtle text-sm font-medium text-content-primary transition-all duration-150 text-left">
                <Bot size={15} className="text-content-muted" />
                {t('dashboard.configureBot')}
              </button>
            </div>
          </div>
        </div>

        {/* ── Histórico de Trades ───────────────────────────────────── */}
        {activeBotConfig && (
          <BotTradeHistory instanceId={activeBotInstanceId} />
        )}

        {/* ── Rodapé ───────────────────────────────────────────────── */}
        <div className="flex items-center justify-center pt-2 border-t border-edge-subtle">
          <p className="text-2xs text-content-muted">
            {t('dashboard.dataSource')}
          </p>
        </div>

      </div>
    </div>
  );
}
