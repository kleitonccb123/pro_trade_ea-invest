import React, { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, ArrowUpRight, ArrowDownLeft, BarChart2, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MarketData {
  symbol: string;
  lastPrice: string;
  priceChangePercent: string;
  volume: string;
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];

export function MarketPulse() {
  const [data, setData] = useState<MarketData[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchData = async () => {
    try {
      const response = await fetch('https://api.binance.com/api/v3/ticker/24hr');
      const allData = await response.json();
      const filtered = allData.filter((item: any) => SYMBOLS.includes(item.symbol));
      setData(filtered);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching market data:', error);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Card className="glass-card border-white/5 bg-gradient-to-br from-slate-900/90 to-black overflow-hidden shadow-2xl">
      <CardHeader className="pb-2 px-4 bg-white/[0.02] border-b border-white/5">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-500 flex items-center gap-2">
            <Globe className="w-3 h-3 text-blue-500" />
            Market Monitor
          </CardTitle>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-[9px] font-black uppercase tracking-widest text-blue-500/80">Live Feed</span>
          </div>
        </div>
      </CardHeader>
      
      {/* The Requested "Professional Animation" Ticker - Compact Style for Right Side */}
      <div className="bg-black py-3 border-b border-white/5 overflow-hidden group">
        <div className="flex whitespace-nowrap animate-ticker-sidebar group-hover:pause-ticker">
          {[...data, ...data].map((item, idx) => {
            const isPositive = parseFloat(item.priceChangePercent) >= 0;
            return (
              <div key={`${item.symbol}-${idx}`} className="inline-flex items-center gap-3 px-6 border-r border-white/10">
                <span className="text-[10px] font-black font-mono text-white/50">{item.symbol.replace('USDT', '')}</span>
                <span className="text-xs font-bold font-mono text-white">${parseFloat(item.lastPrice).toLocaleString()}</span>
                <span className={cn(
                  "text-[10px] font-black font-mono",
                  isPositive ? "text-emerald-500" : "text-red-500"
                )}>
                  {isPositive ? '▲' : '▼'}{Math.abs(parseFloat(item.priceChangePercent)).toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <CardContent className="p-4 space-y-2">
        {data.map((item) => {
          const isPositive = parseFloat(item.priceChangePercent) >= 0;
          return (
            <div 
              key={item.symbol}
              className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.05] transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center",
                  isPositive ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"
                )}>
                  {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                </div>
                <div>
                  <h4 className="font-bold text-xs text-white group-hover:text-blue-400 transition-colors">{item.symbol.replace('USDT', '')}</h4>
                  <p className="text-[9px] text-slate-600 font-black uppercase tracking-tighter">Binance</p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-mono text-xs font-bold text-white">${parseFloat(item.lastPrice).toLocaleString()}</p>
                <div className={isPositive ? "text-emerald-500/80" : "text-red-500/80"}>
                   <span className="text-[10px] font-bold">{isPositive ? '+' : ''}{item.priceChangePercent}%</span>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>

      <style>{`
        @keyframes ticker-sidebar {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-ticker-sidebar {
          animation: ticker-sidebar 20s linear infinite;
        }
        .pause-ticker:hover {
          animation-play-state: paused;
        }
      `}</style>
    </Card>
  );
}
