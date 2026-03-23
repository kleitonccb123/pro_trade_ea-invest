import { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useDashboardWS } from '@/hooks/use-dashboard-ws';
import { ArrowUpRight, ArrowDownRight, Eye, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { OperationDetailModal } from '@/components/modals/OperationDetailModal';

interface Operation {
  id: string;
  pair: string;
  type: 'buy' | 'sell';
  amount: number;
  price: number;
  profit: number;
  date: string;
  robot: string;
}

const INITIAL_OPERATIONS: Operation[] = [
  { id: '1', pair: 'BTC/USDT', type: 'buy', amount: 0.05, price: 42350.0, profit: 125.5, date: '2024-01-27 14:32', robot: 'Scalper Pro' },
  { id: '2', pair: 'ETH/USDT', type: 'sell', amount: 1.2, price: 2280.0, profit: -45.2, date: '2024-01-27 13:15', robot: 'Grid Bot' },
  { id: '3', pair: 'SOL/USDT', type: 'buy', amount: 10, price: 98.5, profit: 78.3, date: '2024-01-27 12:45', robot: 'Trend Follower' },
];

export function RecentOperations() {
  const [selectedOperation, setSelectedOperation] = useState<Operation | null>(null);
  const [ops, setOps] = useState<Operation[]>(INITIAL_OPERATIONS);

  const { lastMessage } = useDashboardWS();

  useEffect(() => {
    if (!lastMessage) return;
    try {
      const msg = lastMessage as any;
      if (msg.type === 'trade_executed') {
        const d = msg.data || {};
        const newOp: Operation = {
          id: d.order_id || String(Date.now()),
          pair: d.symbol || 'BTC/USDT',
          type: (d.side || 'buy') as 'buy' | 'sell',
          amount: Number(d.amount || d.qty || 0),
          price: Number(d.price || 0),
          profit: 0,
          date: new Date().toLocaleString(),
          robot: d.bot_name || 'Remote Bot',
        };
        setOps((prev) => [newOp, ...prev].slice(0, 20));
      }
    } catch (e) {
      // ignore
    }
  }, [lastMessage]);

  return (
    <div className="glass-card p-4 lg:p-6">
      <div className="flex items-center justify-between mb-4 lg:mb-6">
        <h3 className="text-base lg:text-lg font-semibold text-foreground">Últimas Operações</h3>
        <button className="text-sm text-primary hover:underline">Ver todas</button>
      </div>
      
      {/* Mobile card view */}
      <div className="lg:hidden space-y-3">
        <AnimatePresence>
          {ops.map((op) => (
            <motion.div
              layout
              key={op.id}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0, margin: 0, padding: 0 }}
              onClick={() => setSelectedOperation(op)}
              className="p-4 bg-muted/30 rounded-xl border border-border/50 hover:border-primary/30 transition-all cursor-pointer group"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">{op.pair}</span>
                  <span className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
                    op.type === 'buy' ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive"
                  )}>
                    {op.type === 'buy' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {op.type === 'buy' ? 'Compra' : 'Venda'}
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{op.robot}</p>
                  <p className="text-xs text-muted-foreground">{op.date}</p>
                </div>
                <span className={cn(
                  "font-mono font-semibold text-lg",
                  op.profit >= 0 ? "text-success" : "text-destructive"
                )}>
                  {op.profit >= 0 ? '+' : ''}${Math.abs(op.profit).toFixed(2)}
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Desktop table view */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Par</th>
              <th>Tipo</th>
              <th>Quantidade</th>
              <th>Preço</th>
              <th>Lucro/Perda</th>
              <th>Robô</th>
              <th>Data</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {ops.map((op) => (
              <tr 
                key={op.id} 
                className="cursor-pointer hover:bg-primary/5"
                onClick={() => setSelectedOperation(op)}
              >
                <td className="font-medium text-foreground">{op.pair}</td>
                <td>
                  <span className={cn(
                    "inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium",
                    op.type === 'buy' ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive"
                  )}>
                    {op.type === 'buy' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {op.type === 'buy' ? 'Compra' : 'Venda'}
                  </span>
                </td>
                <td className="font-mono">{op.amount}</td>
                <td className="font-mono">${op.price.toLocaleString()}</td>
                <td>
                  <span className={cn(
                    "font-mono font-medium",
                    op.profit >= 0 ? "text-success" : "text-destructive"
                  )}>
                    {op.profit >= 0 ? '+' : ''}{op.profit.toFixed(2)}
                  </span>
                </td>
                <td className="text-muted-foreground">{op.robot}</td>
                <td className="text-muted-foreground text-xs">{op.date}</td>
                <td>
                  <Eye className="w-4 h-4 text-muted-foreground hover:text-primary transition-colors" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Operation Detail Modal */}
      <OperationDetailModal
        open={selectedOperation !== null}
        onOpenChange={(open) => !open && setSelectedOperation(null)}
        operation={selectedOperation ? {
          ...selectedOperation,
          entryPrice: selectedOperation.price * 0.98,
          exitPrice: selectedOperation.price,
          duration: '2h 34min',
          fees: selectedOperation.price * selectedOperation.amount * 0.001,
          notes: 'Operação executada conforme estratégia definida.',
        } : undefined}
      />
    </div>
  );
}
