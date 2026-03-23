/**
 * BacktestPage — Real backtesting with KuCoin historical data
 *
 * Features:
 *  - Strategy selector + parameter configuration form
 *  - Equity curve chart with buy-and-hold overlay
 *  - Metrics cards (Sharpe, Drawdown, Win Rate, etc.)
 *  - Detailed trade table
 *  - Backtest history for each strategy
 */

import React, { useEffect, useState, useMemo } from 'react';
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  TrendingUp, TrendingDown, BarChart3, Activity, Target,
  Shield, Clock, Loader2, Play, ChevronDown, ChevronUp,
  AlertTriangle, CheckCircle2, DollarSign, Percent,
} from 'lucide-react';
import { useLanguage } from '@/hooks/use-language';
import { useAuthStore } from '@/context/AuthContext';
import {
  BacktestResult, BacktestSummary, BacktestRunParams,
  runBacktest, getAvailableSymbols, listStrategyBacktests,
  getBacktestResult,
} from '@/services/backtestService';
import { getStrategies, StrategyMetrics } from '@/services/strategyService';
import { toast } from 'sonner';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatUSD(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}
function formatPct(n: number): string {
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

// ── Metric Card ──────────────────────────────────────────────────────────────

interface MetricProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: string;
  sub?: string;
}

const MetricCard: React.FC<MetricProps> = ({ label, value, icon, color = 'text-slate-300', sub }) => (
  <Card className="bg-slate-800/60 border-slate-700">
    <CardContent className="p-4 flex items-center gap-3">
      <div className="p-2 rounded-lg bg-slate-700/50">{icon}</div>
      <div>
        <p className="text-xs text-slate-400">{label}</p>
        <p className={`text-lg font-bold ${color}`}>{value}</p>
        {sub && <p className="text-xs text-slate-500">{sub}</p>}
      </div>
    </CardContent>
  </Card>
);

// ── Main Component ───────────────────────────────────────────────────────────

const BacktestPage: React.FC = () => {
  const { t } = useLanguage();

  // State — form
  const [strategies, setStrategies] = useState<StrategyMetrics[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [symbol, setSymbol] = useState('BTC-USDT');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [capital, setCapital] = useState(1000);
  const [shortPeriod, setShortPeriod] = useState(9);
  const [longPeriod, setLongPeriod] = useState(21);
  const [stopLoss, setStopLoss] = useState(5);
  const [takeProfit, setTakeProfit] = useState(10);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // State — results
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [history, setHistory] = useState<BacktestSummary[]>([]);
  const [activeTab, setActiveTab] = useState<'chart' | 'trades' | 'history'>('chart');

  // Default dates: last 6 months
  useEffect(() => {
    const end = new Date();
    const start = new Date();
    start.setMonth(start.getMonth() - 6);
    setStartDate(start.toISOString().split('T')[0]);
    setEndDate(end.toISOString().split('T')[0]);
  }, []);

  // Fetch strategies and symbols on mount
  useEffect(() => {
    getStrategies()
      .then(setStrategies)
      .catch(() => {});
    getAvailableSymbols()
      .then(setSymbols)
      .catch(() => setSymbols(['BTC-USDT', 'ETH-USDT', 'SOL-USDT']));
  }, []);

  // Load history when strategy changes
  useEffect(() => {
    if (!selectedStrategy) return;
    listStrategyBacktests(selectedStrategy)
      .then(setHistory)
      .catch(() => {});
  }, [selectedStrategy]);

  // ── Run backtest ────────────────────────────────────────────────────────

  const handleRun = async () => {
    if (!selectedStrategy) {
      toast.error(t('backtest.selectStrategy'));
      return;
    }
    setLoading(true);
    try {
      const params: BacktestRunParams = {
        strategy_id: selectedStrategy,
        symbol,
        start_date: startDate,
        end_date: endDate,
        initial_capital: capital,
        short_period: shortPeriod,
        long_period: longPeriod,
        stop_loss_pct: stopLoss,
        take_profit_pct: takeProfit,
      };
      const res = await runBacktest(params);
      setResult(res);
      setActiveTab('chart');
      // refresh history
      listStrategyBacktests(selectedStrategy).then(setHistory).catch(() => {});
      if (res.passed) {
        toast.success(t('backtest.passed'));
      } else {
        toast.warning(t('backtest.failed'));
      }
    } catch (err: any) {
      toast.error(err?.message || t('backtest.error'));
    } finally {
      setLoading(false);
    }
  };

  // ── Chart data ──────────────────────────────────────────────────────────

  const chartData = useMemo(() => {
    if (!result) return [];
    const eqMap = new Map(result.equity_curve.map(p => [p.timestamp, p.equity_usd]));
    const bhMap = new Map(result.buy_hold_curve.map(p => [p.timestamp, p.equity_usd]));
    const allTs = new Set([
      ...result.equity_curve.map(p => p.timestamp),
      ...result.buy_hold_curve.map(p => p.timestamp),
    ]);
    return Array.from(allTs).sort().map(ts => ({
      date: formatDate(ts),
      strategy: eqMap.get(ts) ?? null,
      buyHold: bhMap.get(ts) ?? null,
    }));
  }, [result]);

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 p-4 md:p-6 lg:p-8 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-cyan-400" />
            {t('backtest.title')}
          </h1>
          <p className="text-slate-400 text-sm mt-1">{t('backtest.subtitle')}</p>
        </div>
      </div>

      {/* ── Configuration Form ──────────────────────────────────────────── */}
      <Card className="bg-slate-800/60 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white text-lg">{t('backtest.config')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Row 1: Strategy + Symbol */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-slate-300">{t('backtest.strategy')}</Label>
              <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                  <SelectValue placeholder={t('backtest.selectStrategy')} />
                </SelectTrigger>
                <SelectContent>
                  {strategies.map(s => (
                    <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">{t('backtest.symbol')}</Label>
              <Select value={symbol} onValueChange={setSymbol}>
                <SelectTrigger className="bg-slate-700 border-slate-600 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {symbols.map(s => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Row 2: Dates + Capital */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label className="text-slate-300">{t('backtest.startDate')}</Label>
              <Input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="bg-slate-700 border-slate-600 text-white"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">{t('backtest.endDate')}</Label>
              <Input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                className="bg-slate-700 border-slate-600 text-white"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">{t('backtest.initialCapital')}</Label>
              <Input
                type="number"
                min={100}
                max={1000000}
                value={capital}
                onChange={e => setCapital(Number(e.target.value))}
                className="bg-slate-700 border-slate-600 text-white"
              />
            </div>
          </div>

          {/* Advanced parameters toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            {t('backtest.advancedParams')}
          </button>

          {showAdvanced && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700">
              <div className="space-y-2">
                <Label className="text-slate-400 text-xs">SMA {t('backtest.shortPeriod')}</Label>
                <Input
                  type="number" min={2} max={200}
                  value={shortPeriod} onChange={e => setShortPeriod(Number(e.target.value))}
                  className="bg-slate-700 border-slate-600 text-white h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-slate-400 text-xs">SMA {t('backtest.longPeriod')}</Label>
                <Input
                  type="number" min={5} max={500}
                  value={longPeriod} onChange={e => setLongPeriod(Number(e.target.value))}
                  className="bg-slate-700 border-slate-600 text-white h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-slate-400 text-xs">Stop Loss (%)</Label>
                <Input
                  type="number" min={0.5} max={50} step={0.5}
                  value={stopLoss} onChange={e => setStopLoss(Number(e.target.value))}
                  className="bg-slate-700 border-slate-600 text-white h-9"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-slate-400 text-xs">Take Profit (%)</Label>
                <Input
                  type="number" min={1} max={100} step={0.5}
                  value={takeProfit} onChange={e => setTakeProfit(Number(e.target.value))}
                  className="bg-slate-700 border-slate-600 text-white h-9"
                />
              </div>
            </div>
          )}

          {/* Run button */}
          <Button
            onClick={handleRun}
            disabled={loading || !selectedStrategy}
            className="w-full md:w-auto bg-cyan-600 hover:bg-cyan-500 text-white font-semibold"
          >
            {loading ? (
              <><Loader2 className="h-4 w-4 animate-spin mr-2" />{t('backtest.running')}</>
            ) : (
              <><Play className="h-4 w-4 mr-2" />{t('backtest.run')}</>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* ── Results ─────────────────────────────────────────────────────── */}
      {result && (
        <>
          {/* Status badge */}
          <div className="flex items-center gap-3">
            {result.passed ? (
              <Badge className="bg-emerald-600/20 text-emerald-400 border-emerald-500/30">
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                {t('backtest.criteriaPass')}
              </Badge>
            ) : (
              <Badge className="bg-red-600/20 text-red-400 border-red-500/30">
                <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                {t('backtest.criteriaFail')}
              </Badge>
            )}
            {result.failure_reasons.length > 0 && (
              <span className="text-xs text-slate-500">
                {result.failure_reasons.join(' · ')}
              </span>
            )}
          </div>

          {/* Metrics cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <MetricCard
              label={t('backtest.totalReturn')}
              value={formatPct(result.metrics.total_return_pct)}
              icon={<DollarSign className="h-4 w-4 text-cyan-400" />}
              color={result.metrics.total_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}
              sub={formatUSD(result.metrics.total_return_usd)}
            />
            <MetricCard
              label="Buy & Hold"
              value={formatPct(result.buy_hold_return_pct)}
              icon={<TrendingUp className="h-4 w-4 text-blue-400" />}
              color={result.buy_hold_return_pct >= 0 ? 'text-blue-400' : 'text-red-400'}
            />
            <MetricCard
              label={t('backtest.sharpe')}
              value={result.metrics.sharpe_ratio.toFixed(2)}
              icon={<Activity className="h-4 w-4 text-purple-400" />}
              color={result.metrics.sharpe_ratio >= 1 ? 'text-emerald-400' : result.metrics.sharpe_ratio >= 0.5 ? 'text-amber-400' : 'text-red-400'}
            />
            <MetricCard
              label={t('backtest.maxDrawdown')}
              value={`-${result.metrics.max_drawdown_pct.toFixed(2)}%`}
              icon={<TrendingDown className="h-4 w-4 text-red-400" />}
              color={result.metrics.max_drawdown_pct <= 10 ? 'text-emerald-400' : result.metrics.max_drawdown_pct <= 20 ? 'text-amber-400' : 'text-red-400'}
            />
            <MetricCard
              label={t('backtest.winRate')}
              value={`${result.metrics.win_rate.toFixed(1)}%`}
              icon={<Target className="h-4 w-4 text-emerald-400" />}
              color={result.metrics.win_rate >= 50 ? 'text-emerald-400' : 'text-amber-400'}
              sub={`${result.metrics.total_trades} trades`}
            />
            <MetricCard
              label={t('backtest.profitFactor')}
              value={result.metrics.profit_factor.toFixed(2)}
              icon={<Shield className="h-4 w-4 text-amber-400" />}
              color={result.metrics.profit_factor >= 1.5 ? 'text-emerald-400' : result.metrics.profit_factor >= 1 ? 'text-amber-400' : 'text-red-400'}
            />
          </div>

          {/* Secondary metrics row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              label="Sortino"
              value={result.metrics.sortino_ratio.toFixed(2)}
              icon={<Activity className="h-4 w-4 text-indigo-400" />}
              color="text-slate-200"
            />
            <MetricCard
              label="Calmar"
              value={result.metrics.calmar_ratio.toFixed(2)}
              icon={<BarChart3 className="h-4 w-4 text-teal-400" />}
              color="text-slate-200"
            />
            <MetricCard
              label={t('backtest.avgHolding')}
              value={`${result.metrics.avg_holding_period_hours.toFixed(0)}h`}
              icon={<Clock className="h-4 w-4 text-slate-400" />}
              color="text-slate-200"
            />
            <MetricCard
              label={t('backtest.bestWorst')}
              value={`${formatUSD(result.metrics.best_trade_usd)} / ${formatUSD(result.metrics.worst_trade_usd)}`}
              icon={<Percent className="h-4 w-4 text-slate-400" />}
              color="text-slate-200"
            />
          </div>

          {/* Tabs: Chart | Trades | History */}
          <div className="flex gap-2">
            {(['chart', 'trades', 'history'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? 'bg-cyan-600/20 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                {tab === 'chart' ? t('backtest.equityCurve') : tab === 'trades' ? t('backtest.tradeList') : t('backtest.history')}
              </button>
            ))}
          </div>

          {/* ── Equity Curve Chart ──────────────────────────────────────── */}
          {activeTab === 'chart' && (
            <Card className="bg-slate-800/60 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-cyan-400" />
                  {t('backtest.equityCurve')} — {result.config.symbol}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                  <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorStrategy" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorBH" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis
                      dataKey="date"
                      stroke="#64748b"
                      tick={{ fontSize: 11 }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      stroke="#64748b"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                      labelStyle={{ color: '#94a3b8' }}
                      formatter={(value: number, name: string) => [
                        formatUSD(value),
                        name === 'strategy' ? t('backtest.strategyLabel') : 'Buy & Hold',
                      ]}
                    />
                    <Legend />
                    <ReferenceLine
                      y={result.config.initial_capital_usd}
                      stroke="#475569"
                      strokeDasharray="4 4"
                      label={{ value: t('backtest.initialCapital'), fill: '#64748b', fontSize: 11 }}
                    />
                    <Area
                      type="monotone"
                      dataKey="strategy"
                      name={t('backtest.strategyLabel')}
                      stroke="#06b6d4"
                      strokeWidth={2}
                      fill="url(#colorStrategy)"
                    />
                    <Area
                      type="monotone"
                      dataKey="buyHold"
                      name="Buy & Hold"
                      stroke="#6366f1"
                      strokeWidth={1.5}
                      strokeDasharray="5 5"
                      fill="url(#colorBH)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* ── Trade Table ─────────────────────────────────────────────── */}
          {activeTab === 'trades' && (
            <Card className="bg-slate-800/60 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-base">
                  {t('backtest.tradeList')} ({result.trades.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-slate-700">
                      <TableHead className="text-slate-400">#</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.side')}</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.entry')}</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.exit')}</TableHead>
                      <TableHead className="text-slate-400">PnL ($)</TableHead>
                      <TableHead className="text-slate-400">PnL (%)</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.fees')}</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.exitReason')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.trades.map((trade, idx) => (
                      <TableRow key={idx} className="border-slate-700/50">
                        <TableCell className="text-slate-400 font-mono text-xs">{idx + 1}</TableCell>
                        <TableCell>
                          <Badge className={trade.side === 'long' ? 'bg-emerald-600/20 text-emerald-400' : 'bg-red-600/20 text-red-400'}>
                            {trade.side.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-slate-300 font-mono text-sm">
                          {formatUSD(trade.entry_price)}
                        </TableCell>
                        <TableCell className="text-slate-300 font-mono text-sm">
                          {formatUSD(trade.exit_price)}
                        </TableCell>
                        <TableCell className={`font-mono text-sm ${trade.pnl_usd >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {trade.pnl_usd >= 0 ? '+' : ''}{trade.pnl_usd.toFixed(2)}
                        </TableCell>
                        <TableCell className={`font-mono text-sm ${trade.pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {formatPct(trade.pnl_pct)}
                        </TableCell>
                        <TableCell className="text-slate-500 font-mono text-xs">
                          {formatUSD(trade.fees_usd)}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={
                            trade.exit_reason === 'tp' ? 'border-emerald-500/30 text-emerald-400' :
                            trade.exit_reason === 'sl' ? 'border-red-500/30 text-red-400' :
                            'border-slate-600 text-slate-400'
                          }>
                            {trade.exit_reason.toUpperCase()}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {result.trades.length === 0 && (
                  <p className="text-center text-slate-500 py-8">{t('backtest.noTrades')}</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* ── Backtest History ────────────────────────────────────────── */}
          {activeTab === 'history' && (
            <Card className="bg-slate-800/60 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-base">{t('backtest.history')}</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-slate-700">
                      <TableHead className="text-slate-400">{t('backtest.date')}</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.symbol')}</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.totalReturn')}</TableHead>
                      <TableHead className="text-slate-400">Buy & Hold</TableHead>
                      <TableHead className="text-slate-400">Sharpe</TableHead>
                      <TableHead className="text-slate-400">Drawdown</TableHead>
                      <TableHead className="text-slate-400">{t('backtest.winRate')}</TableHead>
                      <TableHead className="text-slate-400">Status</TableHead>
                      <TableHead className="text-slate-400" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.map(h => (
                      <TableRow key={h.backtest_id} className="border-slate-700/50 cursor-pointer hover:bg-slate-700/30"
                        onClick={async () => {
                          try {
                            const full = await getBacktestResult(h.backtest_id);
                            setResult(full);
                            setActiveTab('chart');
                          } catch { /* ignore */ }
                        }}
                      >
                        <TableCell className="text-slate-300 text-sm">{formatDate(h.completed_at)}</TableCell>
                        <TableCell className="text-slate-300 font-mono text-sm">{h.symbol}</TableCell>
                        <TableCell className={`font-mono text-sm ${h.total_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {formatPct(h.total_return_pct)}
                        </TableCell>
                        <TableCell className={`font-mono text-sm ${h.buy_hold_return_pct >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                          {formatPct(h.buy_hold_return_pct)}
                        </TableCell>
                        <TableCell className="text-slate-300 font-mono text-sm">{h.sharpe_ratio.toFixed(2)}</TableCell>
                        <TableCell className="text-red-400 font-mono text-sm">-{h.max_drawdown_pct.toFixed(1)}%</TableCell>
                        <TableCell className="text-slate-300 font-mono text-sm">{h.win_rate.toFixed(1)}%</TableCell>
                        <TableCell>
                          {h.passed ? (
                            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                          ) : (
                            <AlertTriangle className="h-4 w-4 text-amber-400" />
                          )}
                        </TableCell>
                        <TableCell className="text-cyan-400 text-xs">{t('backtest.view')}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {history.length === 0 && (
                  <p className="text-center text-slate-500 py-8">{t('backtest.noHistory')}</p>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Empty state when no result */}
      {!result && !loading && (
        <Card className="bg-slate-800/40 border-slate-700/50 border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <BarChart3 className="h-12 w-12 text-slate-600 mb-4" />
            <h3 className="text-lg font-medium text-slate-400">{t('backtest.emptyTitle')}</h3>
            <p className="text-sm text-slate-500 max-w-md mt-2">{t('backtest.emptyDesc')}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default BacktestPage;
