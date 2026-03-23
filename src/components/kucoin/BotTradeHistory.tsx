/**
 * Tabela de histórico de trades de um bot específico.
 * Endpoint: GET /api/trading/bots/{instance_id}/trades?page=1&limit=20
 * Atualiza automaticamente a cada 30 segundos.
 */
import { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';
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

interface TradeSummary {
  total_trades: number;
  closed_trades: number;
  total_pnl_usdt: number;
  win_rate: number;
  total_fees_usdt: number;
}

interface BotTradeHistoryProps {
  instanceId: string | null;
}

export function BotTradeHistory({ instanceId }: BotTradeHistoryProps) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<TradeSummary | null>(null);

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
          aria-label="Atualizar"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Sumário */}
      {summary && (
        <div className="grid grid-cols-4 gap-px bg-edge-subtle border-b border-edge-subtle">
          {[
            {
              label: 'P&L Total',
              value: `${(summary.total_pnl_usdt ?? 0) >= 0 ? '+' : ''}${(summary.total_pnl_usdt ?? 0).toFixed(2)} USDT`,
              positive: (summary.total_pnl_usdt ?? 0) >= 0,
            },
            {
              label: 'Win Rate',
              value: `${(summary.win_rate ?? 0).toFixed(1)}%`,
              positive: (summary.win_rate ?? 0) >= 50,
            },
            {
              label: 'Trades',
              value: `${summary.closed_trades}/${summary.total_trades}`,
              positive: undefined,
            },
            {
              label: 'Fees Pagas',
              value: `${(summary.total_fees_usdt ?? 0).toFixed(4)} USDT`,
              positive: undefined,
            },
          ].map((stat) => (
            <div key={stat.label} className="px-4 py-3 bg-surface-raised">
              <p className="text-xs text-content-muted">{stat.label}</p>
              <p className={cn(
                'text-sm font-bold font-mono mt-0.5',
                stat.positive === true  ? 'text-emerald-400' :
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
                  <td className={cn(
                    'px-4 py-3 text-right font-mono font-semibold',
                    t.pnl_net_usdt == null ? 'text-content-muted' :
                    t.pnl_net_usdt >= 0    ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    {t.pnl_net_usdt == null
                      ? '—'
                      : `${t.pnl_net_usdt >= 0 ? '+' : ''}${t.pnl_net_usdt.toFixed(2)}`}
                  </td>
                  <td className={cn(
                    'px-4 py-3 text-right font-mono text-xs',
                    t.roi_pct == null ? 'text-content-muted' :
                    t.roi_pct >= 0   ? 'text-emerald-400' : 'text-red-400'
                  )}>
                    {t.roi_pct == null
                      ? '—'
                      : `${t.roi_pct >= 0 ? '+' : ''}${t.roi_pct.toFixed(2)}%`}
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
