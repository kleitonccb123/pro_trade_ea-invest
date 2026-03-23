import React, { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface TickerData {
  symbol: string;
  lastPrice: string;
  priceChangePercent: string;
}

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];

interface CryptoTickerProps {
  compact?: boolean;
  vertical?: boolean;
}

export function CryptoTicker({ compact, vertical }: CryptoTickerProps) {
  const [data, setData] = useState<TickerData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPrices = async () => {
    try {
      const response = await fetch('https://api.binance.com/api/v3/ticker/24hr');
      const allData = await response.json();
      const filtered = allData.filter((item: any) => SYMBOLS.includes(item.symbol));
      const sorted = SYMBOLS.map(s => filtered.find((f: any) => f.symbol === s)).filter(Boolean);
      setData(sorted as TickerData[]);
      setLoading(false);
    } catch (error) {
      console.error('Erro ao buscar preços Binance:', error);
    }
  };

  useEffect(() => {
    fetchPrices();
    const interval = setInterval(fetchPrices, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && data.length === 0) {
    return (
      <div className={cn(
        "flex items-center justify-center",
        vertical ? "h-full w-20" : "h-10"
      )}>
        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
      </div>
    );
  }

  // Vertical ticker for left sidebar
  if (vertical) {
    const displayItems = [...data, ...data, ...data];
    return (
      <div className="h-full w-20 bg-gradient-to-b from-slate-900 via-black to-slate-900 border-r border-white/5 overflow-hidden relative">
        <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-slate-900 to-transparent z-10 pointer-events-none" />
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-slate-900 to-transparent z-10 pointer-events-none" />
        
        <div className="animate-ticker-vertical py-4">
          {displayItems.map((item, idx) => {
            const isPositive = parseFloat(item.priceChangePercent) >= 0;
            const symbolClean = item.symbol.replace('USDT', '');
            
            return (
              <div 
                key={`${item.symbol}-${idx}`}
                className="flex flex-col items-center justify-center py-5 border-b border-white/5"
              >
                <span className="text-[10px] font-black text-slate-500 tracking-widest mb-1">
                  {symbolClean}
                </span>
                <span className="text-xs font-bold text-white font-mono">
                  ${parseFloat(item.lastPrice).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                <div className={cn(
                  "flex items-center gap-0.5 text-[9px] font-black mt-1",
                  isPositive ? "text-emerald-400" : "text-red-400"
                )}>
                  <span>{isPositive ? '▲' : '▼'}</span>
                  <span>{Math.abs(parseFloat(item.priceChangePercent)).toFixed(1)}%</span>
                </div>
              </div>
            );
          })}
        </div>

        <style>{`
          @keyframes ticker-vertical {
            0% { transform: translateY(0); }
            100% { transform: translateY(-33.33%); }
          }
          .animate-ticker-vertical {
            animation: ticker-vertical 20s linear infinite;
          }
          .animate-ticker-vertical:hover {
            animation-play-state: paused;
          }
        `}</style>
      </div>
    );
  }

  // Horizontal ticker
  const displayItems = [...data, ...data, ...data, ...data];

  return (
    <div className={cn(
      "overflow-hidden flex items-center group relative select-none",
      compact ? "h-10 bg-[#0a0f18] border-y border-white/5" : "h-12 bg-black border-y border-white/5"
    )}>
      <div className="absolute left-0 top-0 bottom-0 w-16 bg-gradient-to-r from-black to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-black to-transparent z-10 pointer-events-none" />
      
      <div className="flex whitespace-nowrap animate-ticker-horizontal group-hover:pause-animation">
        {displayItems.map((item, idx) => {
          const isPositive = parseFloat(item.priceChangePercent) >= 0;
          const symbolClean = item.symbol.replace('USDT', '');
          
          return (
            <div 
              key={`${item.symbol}-${idx}`}
              className="flex items-center gap-4 px-8 border-r border-white/10"
            >
              <span className="text-white font-mono font-black text-sm">{symbolClean}</span>
              <span className="text-white font-mono text-sm font-bold">
                ${parseFloat(item.lastPrice).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <div className={cn(
                "flex items-center gap-1 font-mono text-xs font-black px-2 py-0.5 rounded",
                isPositive ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
              )}>
                <span>{isPositive ? '▲' : '▼'}</span>
                <span>{Math.abs(parseFloat(item.priceChangePercent)).toFixed(2)}%</span>
              </div>
            </div>
          );
        })}
      </div>

      <style>{`
        @keyframes ticker-horizontal {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-ticker-horizontal {
          animation: ticker-horizontal 35s linear infinite;
        }
        .pause-animation:hover {
          animation-play-state: paused;
        }
      `}</style>
    </div>
  );
}
