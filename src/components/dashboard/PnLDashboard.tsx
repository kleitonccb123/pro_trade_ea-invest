/**
 * PnLDashboard - Dashboard de PnL e Auditoria
 * 
 * Features:
 * - PnL Total, Diário, Semanal
 * - Gráfico de evolução (recharts)
 * - Badge de System Health (Circuit Breaker status)
 * - Fórmula: PnL = Σ(Vendas) - Σ(Compras) - Fees
 */

import { useState, useEffect, useCallback } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Activity, AlertCircle, RefreshCw, Wallet, BarChart3, Shield } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart, ReferenceLine } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import useApi, { CircuitBreakerStatus } from '@/hooks/useApi';

// ============== TYPES ==============

interface PnLSummary {
  total_pnl: number;
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  total_buys: number;
  total_sells: number;
  total_fees: number;
  realized_pnl: number;
  unrealized_pnl: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  best_trade: number;
  worst_trade: number;
  avg_trade: number;
}

interface PnLDataPoint {
  timestamp: string;
  pnl: number;
  cumulative_pnl: number;
  balance: number;
}

interface SystemHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  circuit_breaker: CircuitBreakerStatus;
  services: {
    database: boolean;
    exchange_api: boolean;
    redis: boolean;
  };
  uptime: number;
}

// ============== COMPONENT ==============

export default function PnLDashboard() {
  const api = useApi();
  
  // State
  const [summary, setSummary] = useState<PnLSummary | null>(null);
  const [chartData, setChartData] = useState<PnLDataPoint[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeframe, setTimeframe] = useState<'24h' | '7d' | '30d' | 'all'>('24h');

  // Fetch PnL data
  const fetchPnLData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [summaryData, historyData, healthData] = await Promise.all([
        api.get<PnLSummary>('/audit/pnl/summary'),
        api.get<PnLDataPoint[]>(`/audit/pnl/history?timeframe=${timeframe}`),
        api.get<SystemHealthResponse>('/health/detailed').catch(() => null),
      ]);

      setSummary(summaryData);
      setChartData(historyData);
      if (healthData) {
        setSystemHealth(healthData);
      }
    } catch (err: any) {
      console.error('Failed to fetch PnL data:', err);
      setError(err.message || 'Falha ao carregar dados de PnL');
      
      // Use mock data for demo
      setSummary(getMockSummary());
      setChartData(getMockChartData());
    } finally {
      setLoading(false);
    }
  }, [api, timeframe]);

  useEffect(() => {
    fetchPnLData();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchPnLData, 30000);
    return () => clearInterval(interval);
  }, [fetchPnLData]);

  // ============== HELPERS ==============

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    const formatted = (value * 100).toFixed(2);
    return `${value >= 0 ? '+' : ''}${formatted}%`;
  };

  const getSystemHealthBadge = () => {
    if (!systemHealth && !api.circuitBreakerStatus) {
      return (
        <Badge className="bg-slate-600">
          <Activity className="w-3 h-3 mr-1" />
          Desconhecido
        </Badge>
      );
    }

    const cbStatus = api.circuitBreakerStatus || systemHealth?.circuit_breaker;

    if (cbStatus?.state === 'OPEN') {
      return (
        <Badge className="bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse">
          <AlertCircle className="w-3 h-3 mr-1" />
          Circuit Breaker OPEN
        </Badge>
      );
    }

    if (cbStatus?.state === 'HALF_OPEN') {
      return (
        <Badge className="bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
          <Activity className="w-3 h-3 mr-1" />
          Recuperando...
        </Badge>
      );
    }

    if (systemHealth?.status === 'healthy') {
      return (
        <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          <Shield className="w-3 h-3 mr-1" />
          Operando
        </Badge>
      );
    }

    if (systemHealth?.status === 'degraded') {
      return (
        <Badge className="bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
          <Activity className="w-3 h-3 mr-1" />
          Degradado
        </Badge>
      );
    }

    return (
      <Badge className="bg-emerald-500/20 text-emerald-400">
        <Shield className="w-3 h-3 mr-1" />
        Operando
      </Badge>
    );
  };

  // ============== MOCK DATA (fallback) ==============

  const getMockSummary = (): PnLSummary => ({
    total_pnl: 12547.32,
    daily_pnl: 234.56,
    weekly_pnl: 1832.45,
    monthly_pnl: 8921.33,
    total_buys: 45678.90,
    total_sells: 58102.45,
    total_fees: 123.77,
    realized_pnl: 12299.78,
    unrealized_pnl: 247.54,
    win_count: 156,
    loss_count: 72,
    win_rate: 0.684,
    best_trade: 2156.78,
    worst_trade: -543.21,
    avg_trade: 55.12,
  });

  const getMockChartData = (): PnLDataPoint[] => {
    const data: PnLDataPoint[] = [];
    const now = new Date();
    let cumulative = 10000;

    for (let i = 23; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 3600000);
      const pnl = (Math.random() - 0.4) * 200;
      cumulative += pnl;
      
      data.push({
        timestamp: time.toISOString(),
        pnl: pnl,
        cumulative_pnl: cumulative - 10000,
        balance: cumulative,
      });
    }
    
    return data;
  };

  // ============== RENDER ==============

  if (loading && !summary) {
    return <PnLDashboardSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Header with System Health */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-500" />
            Análise de Performance
          </h2>
          <p className="text-sm text-slate-400">
            PnL = Σ(Vendas) - Σ(Compras) - Fees
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {getSystemHealthBadge()}
          <Button
            variant="ghost"
            size="icon"
            onClick={fetchPnLData}
            disabled={loading}
            className="hover:bg-white/5"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert className="bg-yellow-500/10 border-yellow-500/30">
          <AlertCircle className="h-4 w-4 text-yellow-500" />
          <AlertTitle className="text-yellow-400">Usando dados de demonstração</AlertTitle>
          <AlertDescription className="text-yellow-400/70">{error}</AlertDescription>
        </Alert>
      )}

      {/* PnL Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total PnL */}
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-slate-400">PnL Total</p>
                  <p className={`text-2xl font-bold ${summary.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(summary.total_pnl)}
                  </p>
                </div>
                <div className={`p-2 rounded-lg ${summary.total_pnl >= 0 ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
                  {summary.total_pnl >= 0 ? (
                    <TrendingUp className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <TrendingDown className="w-5 h-5 text-red-400" />
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Realizado: {formatCurrency(summary.realized_pnl)}
              </p>
            </CardContent>
          </Card>

          {/* Daily PnL */}
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-slate-400">PnL Hoje</p>
                  <p className={`text-2xl font-bold ${summary.daily_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(summary.daily_pnl)}
                  </p>
                </div>
                <div className={`p-2 rounded-lg ${summary.daily_pnl >= 0 ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
                  <DollarSign className={`w-5 h-5 ${summary.daily_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`} />
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Semana: {formatCurrency(summary.weekly_pnl)}
              </p>
            </CardContent>
          </Card>

          {/* Win Rate */}
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-slate-400">Taxa de Acerto</p>
                  <p className="text-2xl font-bold text-blue-400">
                    {(summary.win_rate * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="p-2 rounded-lg bg-blue-500/20">
                  <Activity className="w-5 h-5 text-blue-400" />
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                {summary.win_count}W / {summary.loss_count}L
              </p>
            </CardContent>
          </Card>

          {/* Fees */}
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-slate-400">Total de Fees</p>
                  <p className="text-2xl font-bold text-orange-400">
                    {formatCurrency(summary.total_fees)}
                  </p>
                </div>
                <div className="p-2 rounded-lg bg-orange-500/20">
                  <Wallet className="w-5 h-5 text-orange-400" />
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Compras: {formatCurrency(summary.total_buys)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Chart Section */}
      <Card className="bg-slate-900/50 border-slate-800">
        <CardHeader className="pb-2">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <CardTitle className="text-lg text-white">Evolução do Saldo</CardTitle>
              <CardDescription>Últimas {timeframe === '24h' ? '24 horas' : timeframe === '7d' ? '7 dias' : '30 dias'}</CardDescription>
            </div>
            <Tabs value={timeframe} onValueChange={(v) => setTimeframe(v as any)}>
              <TabsList className="bg-slate-800">
                <TabsTrigger value="24h" className="text-xs data-[state=active]:bg-blue-600">24H</TabsTrigger>
                <TabsTrigger value="7d" className="text-xs data-[state=active]:bg-blue-600">7D</TabsTrigger>
                <TabsTrigger value="30d" className="text-xs data-[state=active]:bg-blue-600">30D</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis 
                  dataKey="timestamp" 
                  stroke="#64748b"
                  fontSize={10}
                  tickFormatter={(value) => {
                    const date = new Date(value);
                    return timeframe === '24h' 
                      ? date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
                      : date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
                  }}
                />
                <YAxis 
                  stroke="#64748b" 
                  fontSize={10}
                  tickFormatter={(value) => `$${value.toLocaleString()}`}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1e293b', 
                    border: '1px solid #334155',
                    borderRadius: '8px',
                  }}
                  labelFormatter={(value) => new Date(value).toLocaleString('pt-BR')}
                  formatter={(value: number) => [formatCurrency(value), 'Saldo']}
                />
                <ReferenceLine y={10000} stroke="#64748b" strokeDasharray="5 5" />
                <Area 
                  type="monotone" 
                  dataKey="balance" 
                  stroke="#10b981" 
                  fill="url(#pnlGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Trade Stats */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6 text-center">
              <p className="text-sm text-slate-400">Melhor Trade</p>
              <p className="text-xl font-bold text-emerald-400">{formatCurrency(summary.best_trade)}</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6 text-center">
              <p className="text-sm text-slate-400">Pior Trade</p>
              <p className="text-xl font-bold text-red-400">{formatCurrency(summary.worst_trade)}</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6 text-center">
              <p className="text-sm text-slate-400">Média por Trade</p>
              <p className={`text-xl font-bold ${summary.avg_trade >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {formatCurrency(summary.avg_trade)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// Skeleton loading state
function PnLDashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <Skeleton className="h-8 w-48 bg-slate-800" />
        <Skeleton className="h-6 w-24 bg-slate-800" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="bg-slate-900/50 border-slate-800">
            <CardContent className="pt-6">
              <Skeleton className="h-4 w-20 bg-slate-800 mb-2" />
              <Skeleton className="h-8 w-28 bg-slate-800" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="bg-slate-900/50 border-slate-800">
        <CardContent className="pt-6">
          <Skeleton className="h-[300px] w-full bg-slate-800" />
        </CardContent>
      </Card>
    </div>
  );
}

export { PnLDashboard };
