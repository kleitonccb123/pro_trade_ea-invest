import React, { useEffect, useMemo, useState } from 'react';
import { useDashboardWS } from '@/hooks/use-dashboard-ws';
import PriceSparkline from './PriceSparkline';

type PairState = {
  symbol: string;
  price: number | null;
  change: string;
  flash?: 'up' | 'down' | null;
};

export default function KuCoinLiveWidget() {
  const { lastMessage, isConnected } = useDashboardWS() as any;

  const defaultPairs = useMemo(() => [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'KCS/USDT',
  ], []);

  const [pairs, setPairs] = useState<Record<string, PairState & { prices?: number[] }>>(() => {
    const map: Record<string, PairState & { prices?: number[] }> = {};
    defaultPairs.forEach(s => map[s] = { symbol: s, price: null, change: '0.00%', flash: null, prices: [] });
    return map;
  });

  // Listen for MARKET_TICKER messages
  useEffect(() => {
    if (!lastMessage) return;
    try {
      const msg = lastMessage as any;
      if (msg.type === 'MARKET_TICKER' || msg.type === 'ticker' || msg.type === 'ticker_update') {
        const data = msg.data || {};
        const symbol = (data.symbol || data.pair || '').replace('-', '/');
        if (!symbol) return;

        setPairs(prev => {
          const current = prev[symbol] ?? { symbol, price: null, change: '0.00%', flash: null };
          const newPrice = Number(data.price ?? data.last ?? data.close ?? current.price ?? 0);
          const oldPrice = current.price ?? newPrice;
          const direction = newPrice > oldPrice ? 'up' : (newPrice < oldPrice ? 'down' : null);
          const pct = data.change_percent ?? data.percent ?? null;
          const change = pct != null ? `${Number(pct).toFixed(2)}%` : current.change;

          const nextPrices = (current.prices || []).slice(-29).concat(newPrice);
          const next = {
            ...prev,
            [symbol]: { symbol, price: newPrice, change, flash: direction, prices: nextPrices }
          };

          // clear flash after short delay
          if (direction) {
            setTimeout(() => {
              setPairs(p => ({ ...(p), [symbol]: { ...(p[symbol] || {}), flash: null } }));
            }, 600);
          }

          return next;
        });
      }
    } catch (e) {
      // ignore
    }
  }, [lastMessage]);

  return (
    <div className="glass-card p-4 h-[420px] overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">KuCoin Live</h3>
        <div className="text-xs muted">{isConnected ? 'Live' : 'Offline'}</div>
      </div>

      <div className="space-y-2">
        {Object.values(pairs).map(p => {
          const neonStyle: React.CSSProperties = p.flash === 'up' ? { background: 'rgba(0,192,135,0.06)', boxShadow: '0 0 10px rgba(0,192,135,0.12)' } : p.flash === 'down' ? { background: 'rgba(255,77,79,0.06)', boxShadow: '0 0 10px rgba(255,77,79,0.12)' } : {};

          return (
            <div
              key={p.symbol}
              style={neonStyle}
              className={`flex items-center justify-between gap-3 p-2 rounded-md transition-colors duration-200 hover:brightness-[1.05]`}>
            <div className="flex items-center gap-3">
              <div>
                <div className="text-sm font-medium">{p.symbol}</div>
                <div className="text-xs muted">Last 30m</div>
              </div>
              <div>
                {/* Sparkline */}
                <div style={{ width: 100, height: 28 }}>
                  {typeof window !== 'undefined' ? (
                    <PriceSparkline data={p.prices || []} width={100} height={28} positive={Boolean(p.prices && p.prices[0] ? (p.price != null && p.price >= p.prices[0]) : true)} />
                  ) : null}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono">{p.price != null ? `$${p.price.toLocaleString()}` : '—'}</div>
              <div className={p.change.startsWith('+') ? 'text-success text-xs' : 'text-danger text-xs'}>{p.change}</div>
            </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
