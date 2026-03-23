import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { TrendingUp, TrendingDown, Activity, Calendar, DollarSign, Percent } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatDetailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  value: string;
  change?: number;
  type: 'balance' | 'profit' | 'robots' | 'trades';
}

const mockData = {
  balance: {
    history: [
      { date: '01/02', value: 'Aguardando dados...' },
    ],
    breakdown: [
      { name: 'Carregando...', value: '--', percent: 0 },
    ]
  },
  profit: {
    history: [
      { date: '01/02', value: 'Sem dados ainda' },
    ],
    stats: {
      totalTrades: 0,
      winRate: '--',
      avgProfit: '--',
      bestDay: '--',
      worstDay: '--'
    }
  },
  robots: {
    list: [
      { name: 'BTC Scalper', status: 'active', profit: '+$1,245.00' },
      { name: 'ETH Swing', status: 'active', profit: '+$890.50' },
      { name: 'SOL Grid', status: 'active', profit: '+$456.30' },
      { name: 'DOGE Hunter', status: 'paused', profit: '-$120.00' },
      { name: 'BNB Momentum', status: 'paused', profit: '+$375.50' },
    ]
  },
  trades: {
    recent: [
      { pair: 'BTC/USDT', type: 'BUY', amount: '$500.00', profit: '+$45.30', time: '2 min atrás' },
      { pair: 'ETH/USDT', type: 'SELL', amount: '$350.00', profit: '+$28.50', time: '15 min atrás' },
      { pair: 'SOL/USDT', type: 'BUY', amount: '$200.00', profit: '-$12.00', time: '32 min atrás' },
      { pair: 'BTC/USDT', type: 'SELL', amount: '$1,000.00', profit: '+$89.00', time: '1h atrás' },
      { pair: 'BNB/USDT', type: 'BUY', amount: '$150.00', profit: '+$18.20', time: '2h atrás' },
    ],
    stats: {
      today: 23,
      week: 156,
      month: 1247,
      avgVolume: '$425.00'
    }
  }
};

export function StatDetailModal({ open, onOpenChange, title, value, change, type }: StatDetailModalProps) {
  const isPositive = change && change > 0;
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg bg-card border-border">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span>{title}</span>
            {change !== undefined && (
              <span className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium",
                isPositive ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive"
              )}>
                {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {isPositive ? '+' : ''}{change}%
              </span>
            )}
          </DialogTitle>
          <DialogDescription className="text-3xl font-bold font-mono text-foreground">
            {value}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {type === 'balance' && (
            <>
              <div className="glass-card p-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                  <Percent className="w-4 h-4" /> Distribuição por Ativo
                </h4>
                <div className="space-y-3">
                  {mockData.balance.breakdown.map((item, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-primary" style={{ opacity: 1 - i * 0.2 }} />
                        <span className="text-sm text-foreground">{item.name}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-mono text-foreground">{item.value}</span>
                        <span className="text-xs text-muted-foreground ml-2">({item.percent}%)</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="glass-card p-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                  <Calendar className="w-4 h-4" /> Histórico Recente
                </h4>
                <div className="space-y-2">
                  {mockData.balance.history.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{item.date}</span>
                      <span className="font-mono text-foreground">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {type === 'profit' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Taxa de Acerto</p>
                  <p className="text-xl font-bold text-success">{mockData.profit.stats.winRate}</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Lucro Médio</p>
                  <p className="text-xl font-bold text-foreground">{mockData.profit.stats.avgProfit}</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Melhor Dia</p>
                  <p className="text-xl font-bold text-success">{mockData.profit.stats.bestDay}</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Pior Dia</p>
                  <p className="text-xl font-bold text-destructive">{mockData.profit.stats.worstDay}</p>
                </div>
              </div>
              <div className="glass-card p-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Lucro Diário</h4>
                <div className="space-y-2">
                  {mockData.profit.history.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-muted-foreground">{item.date}</span>
                      <span className={cn("font-mono", item.value.startsWith('+') ? "text-success" : "text-destructive")}>
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {type === 'robots' && (
            <div className="glass-card p-4">
              <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4" /> Status dos Robôs
              </h4>
              <div className="space-y-3">
                {mockData.robots.list.map((robot, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-muted/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-2 h-2 rounded-full",
                        robot.status === 'active' ? "bg-success animate-pulse" : "bg-muted-foreground"
                      )} />
                      <span className="text-sm text-foreground">{robot.name}</span>
                    </div>
                    <span className={cn(
                      "text-sm font-mono",
                      robot.profit.startsWith('+') ? "text-success" : "text-destructive"
                    )}>
                      {robot.profit}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {type === 'trades' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Hoje</p>
                  <p className="text-xl font-bold text-foreground">{mockData.trades.stats.today}</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Esta Semana</p>
                  <p className="text-xl font-bold text-foreground">{mockData.trades.stats.week}</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Este Mês</p>
                  <p className="text-xl font-bold text-foreground">{mockData.trades.stats.month}</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-xs text-muted-foreground">Volume Médio</p>
                  <p className="text-xl font-bold text-foreground">{mockData.trades.stats.avgVolume}</p>
                </div>
              </div>
              <div className="glass-card p-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                  <DollarSign className="w-4 h-4" /> Operações Recentes
                </h4>
                <div className="space-y-2">
                  {mockData.trades.recent.map((trade, i) => (
                    <div key={i} className="flex items-center justify-between p-2 bg-muted/30 rounded-lg text-sm">
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          trade.type === 'BUY' ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive"
                        )}>
                          {trade.type}
                        </span>
                        <span className="text-foreground">{trade.pair}</span>
                      </div>
                      <span className={cn(
                        "font-mono",
                        trade.profit.startsWith('+') ? "text-success" : "text-destructive"
                      )}>
                        {trade.profit}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
