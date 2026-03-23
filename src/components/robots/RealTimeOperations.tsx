import { useState, useEffect, useCallback } from 'react';
import { TrendingUp, TrendingDown, AlertCircle, Check, X, Zap, PauseCircle, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Robot } from '@/types/robot';
import { useDashboardWS } from '@/hooks/use-dashboard-ws';
import { API_BASE_URL } from '@/config/constants';

interface RealTimeOperation {
  id: string;
  type: 'buy' | 'sell' | 'error' | 'info';
  pair: string;
  price: number;
  amount: number;
  timestamp: Date;
  status: 'pending' | 'completed' | 'failed';
  profit?: number;
}

interface RealTimeOperationsProps {
  robot: Robot | null;
  isRunning: boolean;
  onToggle: (running: boolean) => void;
}

export function RealTimeOperations({ robot, isRunning, onToggle }: RealTimeOperationsProps) {
  const [operations, setOperations] = useState<RealTimeOperation[]>([]);
  const { lastMessage } = useDashboardWS();

  const [stats, setStats] = useState({
    totalOperations: 0,
    todayOperations: 0,
    successRate: 0,
    totalProfit: 0,
    todayProfit: 0,
  });

  // Fetch real stats from API on mount and periodically
  const fetchStats = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      const res = await fetch(`${API_BASE_URL}/api/analytics/dashboard/summary`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setStats({
          totalOperations: data.total_trades ?? 0,
          todayOperations: data.today_trades ?? 0,
          successRate: data.win_rate ?? 0,
          totalProfit: data.total_pnl ?? 0,
          todayProfit: data.today_pnl ?? 0,
        });
      }
    } catch (err) {
      console.warn('[RealTimeOperations] Failed to fetch stats:', err);
    }
  }, []);

  // Fetch initial operations history
  const fetchHistory = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token || !robot) return;
      const res = await fetch(`${API_BASE_URL}/api/bots/${robot.id}/trades?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const trades = await res.json();
        const mapped: RealTimeOperation[] = (Array.isArray(trades) ? trades : []).map((t: any) => ({
          id: t._id || t.id || String(Date.now()),
          type: (t.side || 'buy').toLowerCase() as 'buy' | 'sell',
          pair: t.symbol || t.pair || 'BTC/USDT',
          price: t.price || t.executed_price || 0,
          amount: t.quantity || t.executed_quantity || 0,
          timestamp: new Date(t.created_at || t.timestamp || Date.now()),
          status: t.status === 'filled' ? 'completed' : t.status === 'failed' ? 'failed' : 'pending',
          profit: t.pnl ?? undefined,
        }));
        setOperations(mapped);
      }
    } catch (err) {
      console.warn('[RealTimeOperations] Failed to fetch history:', err);
    }
  }, [robot]);

  useEffect(() => {
    fetchStats();
    fetchHistory();
    const interval = setInterval(fetchStats, 30000); // Refresh stats every 30s
    return () => clearInterval(interval);
  }, [fetchStats, fetchHistory]);

  // Process real WebSocket messages for live trade updates
  useEffect(() => {
    if (!lastMessage) return;
    try {
      const data = typeof lastMessage === 'string' ? JSON.parse(lastMessage) : (lastMessage as any)?.data ?? lastMessage;
      const msg = typeof data === 'string' ? JSON.parse(data) : data;

      if (msg.type === 'trade' || msg.type === 'trade_update' || msg.type === 'bot_trade') {
        const trade = msg.data || msg;
        const newOp: RealTimeOperation = {
          id: trade.id || trade._id || String(Date.now()),
          type: (trade.side || 'buy').toLowerCase() as 'buy' | 'sell',
          pair: trade.symbol || trade.pair || 'BTC/USDT',
          price: trade.price || trade.executed_price || 0,
          amount: trade.quantity || trade.executed_quantity || 0,
          timestamp: new Date(trade.timestamp || trade.created_at || Date.now()),
          status: trade.status === 'filled' ? 'completed' : trade.status === 'failed' ? 'failed' : 'pending',
          profit: trade.pnl ?? undefined,
        };
        setOperations((prev) => [newOp, ...prev.slice(0, 49)]);

        // Update local stats on completed sell
        if (newOp.status === 'completed' && newOp.type === 'sell' && newOp.profit) {
          setStats((prev) => ({
            ...prev,
            totalOperations: prev.totalOperations + 1,
            todayOperations: prev.todayOperations + 1,
            totalProfit: prev.totalProfit + (newOp.profit || 0),
            todayProfit: prev.todayProfit + (newOp.profit || 0),
          }));
        }
      }
    } catch {
      // Ignore non-trade messages
    }
  }, [lastMessage]);

  if (!robot) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p>Selecione um robô para ver operações em tempo real</p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-4">
      {/* Header Compacto */}
      <div className="bg-slate-800/50 border border-slate-700/30 rounded-lg p-4 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-yellow-400 animate-pulse' : 'bg-slate-500'}`}></div>
            <span className={`text-xs font-bold uppercase ${isRunning ? 'text-yellow-300' : 'text-slate-400'}`}>
              {isRunning ? '🔴 OPERANDO' : '⏸️ PARADO'}
            </span>
          </div>
          <span className="text-xs px-2 py-1 rounded-full bg-slate-700/50 border border-slate-600 text-slate-300">
            {robot.status.toUpperCase()}
          </span>
        </div>
        <button
          onClick={() => onToggle(!isRunning)}
          className={`w-full py-2.5 px-4 rounded-lg font-semibold text-sm transition-all duration-200 flex items-center justify-center gap-2 ${
            isRunning
              ? 'bg-red-600 hover:bg-red-500 text-white'
              : 'bg-yellow-500 hover:bg-yellow-400 text-black'
          }`}
        >
          {isRunning ? (
            <>
              <PauseCircle className="w-4 h-4" />
              <span className="hidden sm:inline">PAUSAR</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              <span className="hidden sm:inline">INICIAR</span>
            </>
          )}
        </button>
      </div>

      {/* Stats Grid - Compacto */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {/* Lucro Total */}
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-lg p-3 backdrop-blur-sm">
          <p className="text-xs text-slate-400 font-medium mb-1">Lucro</p>
          <p className="text-lg font-bold text-yellow-400">${stats.totalProfit.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</p>
        </div>

        {/* Lucro Hoje */}
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-lg p-3 backdrop-blur-sm">
          <p className="text-xs text-slate-400 font-medium mb-1">Hoje</p>
          <p className="text-lg font-bold text-emerald-400">${stats.todayProfit.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</p>
        </div>

        {/* Taxa de Acerto */}
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-lg p-3 backdrop-blur-sm">
          <p className="text-xs text-slate-400 font-medium mb-1">Taxa Acerto</p>
          <p className="text-lg font-bold text-cyan-400">{stats.successRate.toFixed(1)}%</p>
        </div>

        {/* Operações Hoje */}
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-lg p-3 backdrop-blur-sm">
          <p className="text-xs text-slate-400 font-medium mb-1">Operações</p>
          <p className="text-lg font-bold text-violet-400">{stats.todayOperations}</p>
        </div>

        {/* Total */}
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-lg p-3 backdrop-blur-sm col-span-2 lg:col-span-1">
          <p className="text-xs text-slate-400 font-medium mb-1">Total</p>
          <p className="text-lg font-bold text-slate-300">{stats.totalOperations}</p>
        </div>
      </div>

      {/* Histórico Simples */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-bold text-slate-300 flex items-center gap-2">
            <span>📋</span>
            Histórico de Operações
          </h4>
          <span className="text-xs px-2 py-1 rounded-full bg-yellow-500/20 border border-yellow-500/30 text-yellow-300">
            {operations.length} ops
          </span>
        </div>
        
        <div className="bg-slate-900/50 border border-slate-700/30 rounded-lg p-3 max-h-64 overflow-y-auto backdrop-blur-sm">
          <div className="space-y-2">
            {operations.length === 0 ? (
              <div className="text-center py-6 text-slate-500 text-sm">
                <p>Nenhuma operação realizada</p>
              </div>
            ) : (
              operations.map((op) => (
                <div
                  key={op.id}
                  className={`flex items-center justify-between p-2.5 rounded-md border text-xs ${
                    op.type === 'buy'
                      ? 'bg-emerald-500/10 border-emerald-500/20'
                      : op.type === 'sell'
                        ? 'bg-red-500/10 border-red-500/20'
                        : 'bg-yellow-500/10 border-yellow-500/20'
                  }`}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className={`font-bold ${
                      op.type === 'buy'
                        ? 'text-emerald-300'
                        : op.type === 'sell'
                          ? 'text-red-300'
                          : 'text-yellow-300'
                    }`}>
                      {op.type === 'buy' ? '🟢' : op.type === 'sell' ? '🔴' : '⚠️'}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-slate-300 truncate">{op.pair}</p>
                      <p className="text-slate-500 text-xs">{op.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</p>
                    </div>
                  </div>
                  <div className="text-right ml-2">
                    <p className="font-bold text-slate-300">${op.price.toFixed(2)}</p>
                    {op.profit && <p className="text-emerald-400 text-xs">+${op.profit.toFixed(2)}</p>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
