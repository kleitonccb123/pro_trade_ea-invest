import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  CandlestickChart,
  ReferenceLine
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Zap,
  Clock,
  Target,
  BarChart3
} from 'lucide-react';
import { useTradingWebSocket } from '@/hooks/use-websocket';
import { ActivationCreditsDisplay } from './ActivationCreditsDisplay';
import { cn } from '@/lib/utils';

interface Trade {
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  timestamp: number;
  filled_qty?: number;
  avg_price?: number;
}

interface KlineData {
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  open_time: number;
  close_time: number;
  closed: boolean;
}

export function LiveTradingDashboard() {
  const { isConnected, trades, klineData, robotStatus } = useTradingWebSocket('dashboard');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTCUSDT');
  const [chartData, setChartData] = useState<any[]>([]);
  
  // Transform kline data for chart
  useEffect(() => {
    const symbolKlines = klineData
      .filter(k => k.symbol === selectedSymbol)
      .sort((a, b) => a.open_time - b.open_time)
      .slice(-50) // Last 50 candles
      .map(k => ({
        time: new Date(k.open_time).toLocaleTimeString(),
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
        volume: k.volume
      }));
    
    setChartData(symbolKlines);
  }, [klineData, selectedSymbol]);

  // Get active robots
  const activeRobots = Object.values(robotStatus).filter(r => 
    r.status.startsWith('running')
  );
  
  // Calculate metrics
  const liveRobots = activeRobots.filter(r => r.status === 'running_live').length;
  const simulationRobots = activeRobots.filter(r => r.status === 'running_simulation').length;
  const recentTrades = trades.slice(0, 10);
  
  // Calculate P&L
  const totalPnl = recentTrades.reduce((sum, trade) => {
    // Simplified P&L calculation - in real scenario this would be more complex
    return sum + (trade.side === 'BUY' ? -trade.avg_price * trade.filled_qty : trade.avg_price * trade.filled_qty);
  }, 0);

  return (
    <div className="space-y-6">
      {/* Status Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-3 h-3 rounded-full animate-pulse",
            isConnected ? "bg-success" : "bg-destructive"
          )} />
          <span className="text-sm font-medium">
            {isConnected ? 'Conectado em tempo real' : 'Desconectado'}
          </span>
          <Badge variant={isConnected ? 'default' : 'destructive'}>
            {activeRobots.length} robôs ativos
          </Badge>
        </div>
        
        <div className="text-xs text-muted-foreground">
          Última atualização: {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* Activation Credits Display */}
      <ActivationCreditsDisplay />

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="glass-card">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold font-mono text-success">{liveRobots}</div>
                <div className="text-xs text-muted-foreground">Live Trading</div>
              </div>
              <Zap className="h-5 w-5 text-success" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-card">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold font-mono text-primary">{simulationRobots}</div>
                <div className="text-xs text-muted-foreground">Simulação</div>
              </div>
              <Target className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-card">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold font-mono">{trades.length}</div>
                <div className="text-xs text-muted-foreground">Total Trades</div>
              </div>
              <Activity className="h-5 w-5 text-accent" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="glass-card">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className={cn(
                  "text-2xl font-bold font-mono",
                  totalPnl >= 0 ? "text-success" : "text-destructive"
                )}>
                  {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
                </div>
                <div className="text-xs text-muted-foreground">P&L Total</div>
              </div>
              <DollarSign className={cn(
                "h-5 w-5",
                totalPnl >= 0 ? "text-success" : "text-destructive"
              )} />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Price Chart */}
        <Card className="lg:col-span-2 glass-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              <span>Gráfico em Tempo Real</span>
              <Badge variant="outline">{selectedSymbol}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis 
                    dataKey="time" 
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={10}
                  />
                  <YAxis 
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={10}
                    domain={['dataMin - 10', 'dataMax + 10']}
                  />
                  <Tooltip 
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px'
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="close" 
                    stroke="hsl(var(--primary))" 
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Recent Trades */}
        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              <span>Trades Recentes</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-80 overflow-y-auto">
              {recentTrades.length > 0 ? (
                <div className="space-y-1">
                  {recentTrades.map((trade, index) => (
                    <div key={index} className="flex items-center justify-between p-3 hover:bg-muted/20">
                      <div className="flex items-center gap-2">
                        <Badge 
                          variant={trade.side === 'BUY' ? 'default' : 'destructive'}
                          className="text-xs px-1.5"
                        >
                          {trade.side}
                        </Badge>
                        <span className="font-mono text-xs">{trade.symbol}</span>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-sm">
                          ${(trade.avg_price || trade.price).toFixed(2)}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(trade.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 text-center text-muted-foreground">
                  <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Aguardando trades...</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Active Robots */}
      {activeRobots.length > 0 && (
        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              <span>Robôs Ativos</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {activeRobots.map((robot) => (
                <div key={robot.instance_id} className="p-4 rounded-lg border border-border/50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">Instance #{robot.instance_id}</span>
                    <Badge 
                      className={cn(
                        "text-xs",
                        robot.status === 'running_live' ? 'badge-success' : 'badge-primary'
                      )}
                    >
                      {robot.status === 'running_live' ? 'Live' : 'Sim'}
                    </Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <div>Símbolo: {robot.symbol}</div>
                    <div>Modo: {robot.mode}</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}