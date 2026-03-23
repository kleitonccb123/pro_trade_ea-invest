/**
 * WalletPage — Carteira KuCoin
 *
 * Visualmente exibe os dados da conta KuCoin do usuário.
 * Toda a lógica financeira, ordens e execução são responsabilidade da KuCoin.
 * Este componente apenas consome a API KuCoin via proxy backend autenticado.
 */

import { useEffect, useState, useCallback } from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Link2,
  Link2Off,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  ArrowUpRight,
  ArrowDownRight,
  Coins,
  BarChart3,
  Clock,
  Shield,
  Loader2,
  Plus,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { authService } from '@/services/authService';

/* ─────────────────────────────────────── Types ─── */
interface KuCoinBalance {
  currency: string;
  balance: string;
  available: string;
  holds: string;
  usdValue?: number;
}

interface KuCoinAccountSummary {
  totalBalance: number;
  totalAvailable: number;
  totalHolds: number;
  change24h: number;
  change24hPct: number;
  balances: KuCoinBalance[];
}

interface KuCoinTrade {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  size: number;
  funds: number;
  fee: number;
  feeCurrency: string;
  createdAt: number;
}

interface ConnectionStatus {
  connected: boolean;
  mode?: string;
}

/* ─────────────────────────────────────── Helpers ─── */
const fmtUSD = (v: number) =>
  v.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 });

const fmtNum = (v: number, decimals = 4) =>
  v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const KUCOIN_COLORS: Record<string, string> = {
  BTC: '#F7931A',
  ETH: '#627EEA',
  USDT: '#26A17B',
  KCS: '#23C882',
  SOL: '#9945FF',
  BNB: '#F3BA2F',
  XRP: '#00AAE4',
  ADA: '#0033AD',
  DOT: '#E6007A',
  MATIC: '#8247E5',
};

const currencyColor = (c: string) => KUCOIN_COLORS[c] ?? '#848E9C';

/* ─────────────────────────────────────── Mock data (offline fallback) ─── */
const MOCK_SUMMARY: KuCoinAccountSummary = {
  totalBalance: 0,
  totalAvailable: 0,
  totalHolds: 0,
  change24h: 0,
  change24hPct: 0,
  balances: [],
};

const MOCK_TRADES: KuCoinTrade[] = [];

/* ─────────────────────────────────────── Component ─── */
export default function WalletPage() {
  const navigate = useNavigate();
  const [connection, setConnection] = useState<ConnectionStatus | null>(null);
  const [summary, setSummary] = useState<KuCoinAccountSummary | null>(null);
  const [trades, setTrades] = useState<KuCoinTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [hideBalance, setHideBalance] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  /* ── fetch helpers ── */
  const getToken = () => authService.getAccessToken();

  const fetchConnectionStatus = useCallback(async () => {
    try {
      const token = getToken();
      if (!token) return;
      const res = await fetch('http://localhost:8000/api/trading/kucoin/status', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setConnection(data);
        return data.connected as boolean;
      }
    } catch {
      setConnection({ connected: false });
    }
    return false;
  }, []);

  const fetchAccountData = useCallback(async () => {
    try {
      const token = getToken();
      if (!token) return;

      const [balanceRes, tradesRes] = await Promise.allSettled([
        fetch('http://localhost:8000/api/trading/kucoin/balance', {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch('http://localhost:8000/api/trading/kucoin/trades?limit=20', {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (balanceRes.status === 'fulfilled' && balanceRes.value.ok) {
        const data = await balanceRes.value.json();
        setSummary(data);
      } else {
        setSummary(MOCK_SUMMARY);
      }

      if (tradesRes.status === 'fulfilled' && tradesRes.value.ok) {
        const data = await tradesRes.value.json();
        setTrades(data?.trades ?? data ?? []);
      } else {
        setTrades(MOCK_TRADES);
      }

      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError('Não foi possível carregar os dados da KuCoin');
      setSummary(MOCK_SUMMARY);
      setTrades(MOCK_TRADES);
    }
  }, []);

  const load = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    else setLoading(true);
    const connected = await fetchConnectionStatus();
    if (connected) await fetchAccountData();
    setLoading(false);
    setRefreshing(false);
  }, [fetchConnectionStatus, fetchAccountData]);

  useEffect(() => { load(); }, [load]);

  /* ── auto-refresh every 30s ── */
  useEffect(() => {
    const interval = setInterval(() => load(true), 30_000);
    return () => clearInterval(interval);
  }, [load]);

  /* ─────────────────────────────────────── Render helpers ─── */
  const isConnected = connection?.connected ?? false;

  if (loading) {
    return (
      <div className="w-full flex items-center justify-center py-24">
        <div className="text-center space-y-3">
          <Loader2 className="w-8 h-8 text-emerald-400 animate-spin mx-auto" />
          <p className="text-slate-400 text-sm">Carregando carteira...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl" style={{ background: 'rgba(35,200,130,0.1)', border: '1px solid rgba(35,200,130,0.2)' }}>
            <Wallet className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Carteira KuCoin</h1>
            <p className="text-slate-400 text-sm">
              Saldos e histórico diretamente da sua conta KuCoin
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-slate-500 hidden md:block">
              Atualizado: {lastUpdated.toLocaleTimeString('pt-BR')}
            </span>
          )}
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 border border-slate-700/60 rounded-lg hover:border-emerald-500/40 hover:text-emerald-400 transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Atualizar
          </button>
          <button
            onClick={() => navigate('/kucoin')}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 rounded-lg hover:bg-emerald-600/30 transition-all"
          >
            <Shield className="w-4 h-4" />
            API Keys
          </button>
        </div>
      </div>

      {/* ── Not connected banner ── */}
      {!isConnected && (
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-8 text-center">
          <div className="mx-auto w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
            style={{ background: 'rgba(35,200,130,0.08)', border: '1px solid rgba(35,200,130,0.15)' }}>
            <Link2Off className="w-6 h-6 text-slate-400" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">KuCoin não conectada</h3>
          <p className="text-slate-400 text-sm max-w-sm mx-auto mb-6">
            Conecte sua conta KuCoin com API Key para visualizar saldos e histórico de negociações em tempo real.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => navigate('/kucoin')}
              className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-sm font-semibold rounded-lg shadow-lg shadow-emerald-500/20 transition-all"
            >
              <Plus className="w-4 h-4" />
              Conectar KuCoin
            </button>
            <a
              href="https://www.kucoin.com/account/api"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 px-5 py-2.5 border border-slate-600/50 text-slate-300 text-sm rounded-lg hover:border-emerald-500/40 hover:text-emerald-400 transition-all"
            >
              <ExternalLink className="w-4 h-4" />
              Criar API Key na KuCoin
            </a>
          </div>
          <p className="text-xs text-slate-500 mt-4">
            Permissões necessárias: <span className="text-slate-400">Leitura geral</span> — nenhuma permissão de saque é necessária
          </p>
        </div>
      )}

      {/* ── Connected: content ── */}
      {isConnected && (
        <>
          {/* Connection badge */}
          <div className="flex items-center gap-2 text-xs">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full"
              style={{ background: 'rgba(35,200,130,0.1)', border: '1px solid rgba(35,200,130,0.2)' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-400 font-medium">
                KuCoin conectada — Modo {connection?.mode === 'sandbox' ? 'Teste (Sandbox)' : 'Produção'}
              </span>
            </span>
            <span className="text-slate-500">Os dados são fornecidos diretamente pela KuCoin</span>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-3 p-4 bg-red-900/20 border border-red-500/40 rounded-xl text-red-300 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* ── Total balance card ── */}
          <div className="rounded-xl p-6"
            style={{ background: 'linear-gradient(135deg, rgba(35,200,130,0.08) 0%, rgba(11,14,17,0.6) 100%)', border: '1px solid rgba(35,200,130,0.15)' }}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm text-slate-400">Saldo Total</p>
                  <button onClick={() => setHideBalance(v => !v)} className="text-slate-500 hover:text-slate-300 transition-colors">
                    {hideBalance ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <p className="text-4xl font-bold text-white tracking-tight">
                  {hideBalance ? '••••••' : fmtUSD(summary?.totalBalance ?? 0)}
                </p>
                <div className="flex items-center gap-2 mt-2">
                  {(summary?.change24hPct ?? 0) >= 0 ? (
                    <span className="flex items-center gap-1 text-sm text-emerald-400">
                      <ArrowUpRight className="w-4 h-4" />
                      +{fmtUSD(summary?.change24h ?? 0)} ({(summary?.change24hPct ?? 0).toFixed(2)}%) hoje
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-sm text-red-400">
                      <ArrowDownRight className="w-4 h-4" />
                      {fmtUSD(summary?.change24h ?? 0)} ({(summary?.change24hPct ?? 0).toFixed(2)}%) hoje
                    </span>
                  )}
                </div>
              </div>
              <div className="text-right hidden md:block">
                <p className="text-xs text-slate-500 mb-1">Disponível</p>
                <p className="text-lg font-semibold text-white">
                  {hideBalance ? '••••' : fmtUSD(summary?.totalAvailable ?? 0)}
                </p>
                <p className="text-xs text-slate-500 mt-2">Em ordens</p>
                <p className="text-base font-medium text-slate-300">
                  {hideBalance ? '••••' : fmtUSD(summary?.totalHolds ?? 0)}
                </p>
              </div>
            </div>

            {/* Mini stats row */}
            <div className="grid grid-cols-3 gap-4 mt-6 pt-5 border-t border-slate-700/40">
              <div>
                <p className="text-xs text-slate-500 mb-0.5">Ativos</p>
                <p className="text-sm font-semibold text-white">
                  {summary?.balances.filter(b => parseFloat(b.balance) > 0).length ?? 0}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-0.5">Maior posição</p>
                <p className="text-sm font-semibold text-white">
                  {summary?.balances.sort((a, b) => (b.usdValue ?? 0) - (a.usdValue ?? 0))[0]?.currency ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-0.5">Fonte de dados</p>
                <a href="https://www.kucoin.com" target="_blank" rel="noopener noreferrer"
                  className="text-sm font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1">
                  KuCoin <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>

          {/* ── Balances grid ── */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Coins className="w-4 h-4 text-emerald-400" />
                Saldos por Ativo
              </h2>
              <a href="https://www.kucoin.com/assets/overview" target="_blank" rel="noopener noreferrer"
                className="text-xs text-slate-400 hover:text-emerald-400 flex items-center gap-1 transition-colors">
                Ver na KuCoin <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            {(summary?.balances.filter(b => parseFloat(b.balance) > 0) ?? []).length === 0 ? (
              <div className="rounded-xl border border-slate-700/50 bg-slate-800/20 p-10 text-center">
                <Coins className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">Nenhum saldo disponível</p>
                <p className="text-slate-500 text-xs mt-1">
                  Seus saldos aparecerão aqui assim que a KuCoin retornar os dados
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {summary!.balances
                  .filter(b => parseFloat(b.balance) > 0)
                  .sort((a, b) => (b.usdValue ?? 0) - (a.usdValue ?? 0))
                  .map(bal => {
                    const color = currencyColor(bal.currency);
                    const pct = summary!.totalBalance > 0
                      ? ((bal.usdValue ?? 0) / summary!.totalBalance) * 100
                      : 0;
                    return (
                      <div key={bal.currency}
                        className="rounded-xl p-4 border border-slate-700/40 bg-slate-800/30 hover:border-emerald-500/20 transition-all group">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                              style={{ background: `${color}22`, border: `1px solid ${color}44`, color }}>
                              {bal.currency.slice(0, 2)}
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-white">{bal.currency}</p>
                              <p className="text-[10px] text-slate-500">{pct.toFixed(1)}% do portfolio</p>
                            </div>
                          </div>
                          {bal.usdValue !== undefined && (
                            <p className="text-sm font-semibold text-white">
                              {hideBalance ? '•••' : fmtUSD(bal.usdValue)}
                            </p>
                          )}
                        </div>
                        <div className="space-y-1.5">
                          <div className="flex justify-between text-xs">
                            <span className="text-slate-500">Saldo</span>
                            <span className="text-slate-300">{hideBalance ? '•••' : fmtNum(parseFloat(bal.balance))}</span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-slate-500">Disponível</span>
                            <span className="text-emerald-400">{hideBalance ? '•••' : fmtNum(parseFloat(bal.available))}</span>
                          </div>
                          {parseFloat(bal.holds) > 0 && (
                            <div className="flex justify-between text-xs">
                              <span className="text-slate-500">Em ordens</span>
                              <span className="text-amber-400">{hideBalance ? '•••' : fmtNum(parseFloat(bal.holds))}</span>
                            </div>
                          )}
                        </div>
                        {/* Progress bar */}
                        <div className="mt-3 h-1 rounded-full bg-slate-700/50 overflow-hidden">
                          <div className="h-full rounded-full transition-all"
                            style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>

          {/* ── Recent trades ── */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400" />
                Histórico Recente
              </h2>
              <a href="https://www.kucoin.com/orders/trade" target="_blank" rel="noopener noreferrer"
                className="text-xs text-slate-400 hover:text-emerald-400 flex items-center gap-1 transition-colors">
                Ver tudo na KuCoin <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="rounded-xl border border-slate-700/50 bg-slate-800/20 overflow-hidden">
              {trades.length === 0 ? (
                <div className="p-10 text-center">
                  <BarChart3 className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-400 text-sm">Nenhuma negociação recente</p>
                  <p className="text-slate-500 text-xs mt-1">As negociações realizadas na KuCoin aparecerão aqui</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700/40">
                        <th className="text-left px-4 py-3 text-xs text-slate-500 font-medium">Par</th>
                        <th className="text-left px-4 py-3 text-xs text-slate-500 font-medium">Lado</th>
                        <th className="text-right px-4 py-3 text-xs text-slate-500 font-medium">Preço</th>
                        <th className="text-right px-4 py-3 text-xs text-slate-500 font-medium">Qtd</th>
                        <th className="text-right px-4 py-3 text-xs text-slate-500 font-medium">Total</th>
                        <th className="text-right px-4 py-3 text-xs text-slate-500 font-medium">Data</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/30">
                      {trades.map(trade => (
                        <tr key={trade.id} className="hover:bg-slate-700/20 transition-colors">
                          <td className="px-4 py-3 text-white font-medium">{trade.symbol}</td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${
                              trade.side === 'buy'
                                ? 'bg-emerald-500/15 text-emerald-400'
                                : 'bg-red-500/15 text-red-400'
                            }`}>
                              {trade.side === 'buy'
                                ? <TrendingUp className="w-3 h-3" />
                                : <TrendingDown className="w-3 h-3" />}
                              {trade.side === 'buy' ? 'Compra' : 'Venda'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right text-slate-300">{fmtUSD(trade.price)}</td>
                          <td className="px-4 py-3 text-right text-slate-300">{fmtNum(trade.size, 6)}</td>
                          <td className="px-4 py-3 text-right text-white font-medium">{fmtUSD(trade.funds)}</td>
                          <td className="px-4 py-3 text-right text-slate-500 text-xs">
                            {new Date(trade.createdAt).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* ── Disclaimer ── */}
          <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-800/20 border border-slate-700/30">
            <Shield className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-slate-500 leading-relaxed">
              Os dados exibidos são obtidos diretamente da{' '}
              <a href="https://www.kucoin.com" target="_blank" rel="noopener noreferrer" className="text-emerald-500 hover:underline">KuCoin</a>{' '}
              via API de leitura. Este painel é apenas visual — todas as transações, custódia de ativos e execução de ordens são de responsabilidade exclusiva da KuCoin.
              Nenhum ativo é custodiado por esta plataforma.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
