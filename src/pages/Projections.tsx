import { useState, useEffect } from 'react';
import { TrendingUp, AlertTriangle, Calendar, Loader2, PlayCircle, Sigma } from 'lucide-react';
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { apiCall } from '@/services/apiClient';

const coins = [
  { value: 'BTC', label: 'Bitcoin (BTC)', geckoId: 'bitcoin' },
  { value: 'ETH', label: 'Ethereum (ETH)', geckoId: 'ethereum' },
  { value: 'SOL', label: 'Solana (SOL)', geckoId: 'solana' },
  { value: 'BNB', label: 'BNB (BNB)', geckoId: 'binancecoin' },
  { value: 'XRP', label: 'Ripple (XRP)', geckoId: 'ripple' },
];

const periods = [
  { value: '7', label: '7 dias' },
  { value: '30', label: '30 dias' },
  { value: '90', label: '90 dias' },
];

// Monthly return assumptions for the three scenarios
const SCENARIO_MONTHLY = { pessimistic: -0.15, neutral: 0.05, optimistic: 0.30 };

const generateProjectionData = (basePrice: number, days: number) => {
  if (basePrice === 0) return [];
  const dailyRates = {
    pessimistic: Math.pow(1 + SCENARIO_MONTHLY.pessimistic, 1 / 30) - 1,
    neutral: Math.pow(1 + SCENARIO_MONTHLY.neutral, 1 / 30) - 1,
    optimistic: Math.pow(1 + SCENARIO_MONTHLY.optimistic, 1 / 30) - 1,
  };
  return Array.from({ length: days + 1 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() + i);
    return {
      date: date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
      pessimistic: Math.round(basePrice * Math.pow(1 + dailyRates.pessimistic, i)),
      neutral: Math.round(basePrice * Math.pow(1 + dailyRates.neutral, i)),
      optimistic: Math.round(basePrice * Math.pow(1 + dailyRates.optimistic, i)),
    };
  });
};

interface SimResult {
  paths: { month: number; p10: number; p50: number; p90: number }[];
  final_p10: number;
  final_p50: number;
  final_p90: number;
  prob_profit_pct: number;
  initial_capital: number;
  n_simulations: number;
  horizon_months: number;
}

export default function Projections() {
  const [selectedCoin, setSelectedCoin] = useState('BTC');
  const [selectedPeriod, setSelectedPeriod] = useState('30');
  const [currentPrice, setCurrentPrice] = useState(0);
  const [loadingPrice, setLoadingPrice] = useState(false);
  const [priceError, setPriceError] = useState(false);

  // Monte Carlo state
  const [simCapital, setSimCapital] = useState(10000);
  const [simMonthlyReturn, setSimMonthlyReturn] = useState(5);
  const [simHorizon, setSimHorizon] = useState(12);
  const [simVolatility, setSimVolatility] = useState(20);
  const [simN, setSimN] = useState(1000);
  const [simRunning, setSimRunning] = useState(false);
  const [simResult, setSimResult] = useState<SimResult | null>(null);
  const [simError, setSimError] = useState('');

  useEffect(() => {
    const coin = coins.find(c => c.value === selectedCoin);
    if (!coin) return;
    setLoadingPrice(true);
    setPriceError(false);
    fetch(
      `https://api.coingecko.com/api/v3/simple/price?ids=${coin.geckoId}&vs_currencies=usd`,
      { signal: AbortSignal.timeout(8000) }
    )
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => {
        const price = data?.[coin.geckoId]?.usd ?? 0;
        setCurrentPrice(price);
      })
      .catch(() => setPriceError(true))
      .finally(() => setLoadingPrice(false));
  }, [selectedCoin]);

  const runSimulation = async () => {
    setSimRunning(true);
    setSimError('');
    try {
      const response = await apiCall('/analytics/simulate/montecarlo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          initial_capital: simCapital,
          monthly_return_pct: simMonthlyReturn,
          annual_volatility_pct: simVolatility,
          horizon_months: simHorizon,
          n_simulations: simN,
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail ?? `HTTP ${response.status}`);
      }
      const data: SimResult = await response.json();
      setSimResult(data);
    } catch (e: unknown) {
      setSimError(e instanceof Error ? e.message : 'Falha ao executar simulação.');
    } finally {
      setSimRunning(false);
    }
  };

  const days = parseInt(selectedPeriod);
  const projectionData = generateProjectionData(currentPrice, days);
  const lastData = projectionData[projectionData.length - 1] ?? { pessimistic: 0, neutral: 0, optimistic: 0 };

  const scenarios = [
    { name: 'Pessimista', color: 'destructive', price: lastData.pessimistic, change: currentPrice > 0 ? (((lastData.pessimistic - currentPrice) / currentPrice) * 100).toFixed(1) : '0.0' },
    { name: 'Neutro', color: 'warning', price: lastData.neutral, change: currentPrice > 0 ? (((lastData.neutral - currentPrice) / currentPrice) * 100).toFixed(1) : '0.0' },
    { name: 'Otimista', color: 'success', price: lastData.optimistic, change: currentPrice > 0 ? (((lastData.optimistic - currentPrice) / currentPrice) * 100).toFixed(1) : '0.0' },
  ];


  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
          <TrendingUp className="w-8 h-8 text-primary" />
          Projeção de Preços
        </h1>
        <p className="text-muted-foreground">Cenários de preço baseados em modelos estatísticos</p>
      </div>

      {/* Disclaimer */}
      <div className="glass-card p-4 border-warning/30 bg-warning/5">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-warning">Aviso de Risco</p>
            <p className="text-sm text-muted-foreground">
              Projeções são estimativas baseadas em dados históricos e modelos estatísticos. 
              O mercado de criptomoedas é altamente volátil e resultados passados não garantem resultados futuros.
              Nunca invista mais do que pode perder.
            </p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="glass-card p-6">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label className="text-sm text-muted-foreground mb-2 block">Selecionar Moeda</label>
            <Select value={selectedCoin} onValueChange={setSelectedCoin}>
              <SelectTrigger className="bg-muted/50 border-border h-12">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                {coins.map((coin) => (
                  <SelectItem key={coin.value} value={coin.value}>{coin.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1">
            <label className="text-sm text-muted-foreground mb-2 block flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              Período de Projeção
            </label>
            <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
              <SelectTrigger className="bg-muted/50 border-border h-12">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                {periods.map((period) => (
                  <SelectItem key={period.value} value={period.value}>{period.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Current price and scenarios */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <p className="text-sm text-muted-foreground mb-1">Preço Atual</p>
          {loadingPrice ? (
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground mt-1" />
          ) : priceError ? (
            <p className="text-sm text-destructive">Indisponível</p>
          ) : (
            <p className="text-2xl font-mono font-bold text-foreground">
              ${currentPrice.toLocaleString()}
            </p>
          )}
          <p className="text-xs text-muted-foreground mt-1">via CoinGecko</p>
        </div>
        {scenarios.map((scenario) => (
          <div key={scenario.name} className="glass-card p-4">
            <p className="text-sm text-muted-foreground mb-1">{scenario.name}</p>
            <p className="text-xl font-mono font-bold text-foreground">
              {currentPrice > 0 ? `$${scenario.price.toLocaleString()}` : '—'}
            </p>
            <p className={cn(
              "text-sm font-mono",
              parseFloat(scenario.change) >= 0 ? "text-success" : "text-destructive"
            )}>
              {currentPrice > 0 ? `${parseFloat(scenario.change) >= 0 ? '+' : ''}${scenario.change}%` : '—'}
            </p>
          </div>
        ))}
      </div>

      {/* Chart */}
      <div className="glass-card p-6">
        <h3 className="text-lg font-semibold text-foreground mb-6">
          Projeção para os próximos {selectedPeriod} dias
        </h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={projectionData}>
              <defs>
                <linearGradient id="colorOptimistic" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(142 76% 45%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(142 76% 45%)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorNeutral" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(38 92% 50%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(38 92% 50%)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorPessimistic" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(0 72% 51%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(0 72% 51%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 18%)" />
              <XAxis 
                dataKey="date" 
                axisLine={false}
                tickLine={false}
                tick={{ fill: 'hsl(215 20% 55%)', fontSize: 12 }}
              />
              <YAxis 
                axisLine={false}
                tickLine={false}
                tick={{ fill: 'hsl(215 20% 55%)', fontSize: 12 }}
                tickFormatter={(value) => `$${value.toLocaleString()}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(222 47% 10%)',
                  border: '1px solid hsl(217 33% 18%)',
                  borderRadius: '8px',
                  color: 'hsl(210 40% 98%)',
                }}
                formatter={(value: number, name: string) => [
                  `$${value.toLocaleString()}`,
                  name === 'optimistic' ? 'Otimista' : name === 'neutral' ? 'Neutro' : 'Pessimista'
                ]}
              />
              <Legend 
                formatter={(value) => 
                  value === 'optimistic' ? 'Otimista' : value === 'neutral' ? 'Neutro' : 'Pessimista'
                }
              />
              <Area
                type="monotone"
                dataKey="optimistic"
                stroke="hsl(142 76% 45%)"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorOptimistic)"
              />
              <Area
                type="monotone"
                dataKey="neutral"
                stroke="hsl(38 92% 50%)"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorNeutral)"
              />
              <Area
                type="monotone"
                dataKey="pessimistic"
                stroke="hsl(0 72% 51%)"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorPessimistic)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Monte Carlo Simulator ─────────────────────────── */}
      <div className="glass-card p-6 space-y-6">
        <div className="flex items-center gap-3">
          <Sigma className="w-6 h-6 text-primary" />
          <div>
            <h3 className="text-lg font-semibold text-foreground">Simulador Monte Carlo</h3>
            <p className="text-sm text-muted-foreground">
              Simula N trajetórias de portfólio via Movimento Browniano Geométrico e exibe os percentis P10 / P50 / P90
            </p>
          </div>
        </div>

        {/* Parameter sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Capital */}
          <div>
            <label className="text-sm text-muted-foreground flex justify-between">
              <span>Capital Inicial</span>
              <span className="font-mono text-foreground">${simCapital.toLocaleString()}</span>
            </label>
            <input
              type="range" min={1000} max={1000000} step={1000}
              value={simCapital}
              onChange={e => setSimCapital(Number(e.target.value))}
              className="w-full mt-2 accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>$1 000</span><span>$1 000 000</span>
            </div>
          </div>

          {/* Monthly return */}
          <div>
            <label className="text-sm text-muted-foreground flex justify-between">
              <span>Retorno Mensal Esperado</span>
              <span className={cn('font-mono', simMonthlyReturn >= 0 ? 'text-success' : 'text-destructive')}>
                {simMonthlyReturn >= 0 ? '+' : ''}{simMonthlyReturn}%
              </span>
            </label>
            <input
              type="range" min={-20} max={50} step={1}
              value={simMonthlyReturn}
              onChange={e => setSimMonthlyReturn(Number(e.target.value))}
              className="w-full mt-2 accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>-20%</span><span>+50%</span>
            </div>
          </div>

          {/* Horizon */}
          <div>
            <label className="text-sm text-muted-foreground flex justify-between">
              <span>Horizonte</span>
              <span className="font-mono text-foreground">{simHorizon} meses</span>
            </label>
            <input
              type="range" min={1} max={60} step={1}
              value={simHorizon}
              onChange={e => setSimHorizon(Number(e.target.value))}
              className="w-full mt-2 accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>1 mês</span><span>60 meses</span>
            </div>
          </div>

          {/* Volatility */}
          <div>
            <label className="text-sm text-muted-foreground flex justify-between">
              <span>Volatilidade Anual</span>
              <span className="font-mono text-foreground">{simVolatility}%</span>
            </label>
            <input
              type="range" min={5} max={100} step={1}
              value={simVolatility}
              onChange={e => setSimVolatility(Number(e.target.value))}
              className="w-full mt-2 accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>5%</span><span>100%</span>
            </div>
          </div>

          {/* N simulations */}
          <div>
            <label className="text-sm text-muted-foreground flex justify-between">
              <span>Nº de Simulações</span>
              <span className="font-mono text-foreground">{simN.toLocaleString()}</span>
            </label>
            <input
              type="range" min={100} max={10000} step={100}
              value={simN}
              onChange={e => setSimN(Number(e.target.value))}
              className="w-full mt-2 accent-primary"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>100</span><span>10 000</span>
            </div>
          </div>

          {/* Run button */}
          <div className="flex items-end">
            <button
              onClick={runSimulation}
              disabled={simRunning}
              className="w-full h-10 rounded-lg bg-primary text-primary-foreground font-medium flex items-center justify-center gap-2 hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {simRunning ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Simulando…</>
              ) : (
                <><PlayCircle className="w-4 h-4" /> Executar Simulação</>
              )}
            </button>
          </div>
        </div>

        {/* Error */}
        {simError && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-destructive">
            {simError}
          </div>
        )}

        {/* Results */}
        {simResult && (
          <div className="space-y-4">
            {/* Summary stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 bg-muted/30 rounded-lg">
                <p className="text-xs text-muted-foreground">P10 final (Pessimista)</p>
                <p className="text-lg font-mono font-bold text-destructive">
                  ${simResult.final_p10.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <p className="text-xs text-muted-foreground">P50 final (Mediana)</p>
                <p className="text-lg font-mono font-bold text-warning">
                  ${simResult.final_p50.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <p className="text-xs text-muted-foreground">P90 final (Otimista)</p>
                <p className="text-lg font-mono font-bold text-success">
                  ${simResult.final_p90.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg">
                <p className="text-xs text-muted-foreground">Prob. de Lucro</p>
                <p className={cn(
                  'text-lg font-mono font-bold',
                  simResult.prob_profit_pct >= 50 ? 'text-success' : 'text-destructive'
                )}>
                  {simResult.prob_profit_pct.toFixed(1)}%
                </p>
              </div>
            </div>

            {/* Chart */}
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={simResult.paths} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(217 33% 18%)" />
                  <XAxis
                    dataKey="month"
                    axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(215 20% 55%)', fontSize: 12 }}
                    label={{ value: 'Mês', position: 'insideBottom', offset: -2, fill: 'hsl(215 20% 55%)', fontSize: 11 }}
                  />
                  <YAxis
                    axisLine={false} tickLine={false}
                    tick={{ fill: 'hsl(215 20% 55%)', fontSize: 11 }}
                    tickFormatter={(v: number) => `$${v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v}`}
                    width={55}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(222 47% 10%)',
                      border: '1px solid hsl(217 33% 18%)',
                      borderRadius: '8px',
                      color: 'hsl(210 40% 98%)',
                    }}
                    formatter={(value: number, name: string) => [
                      `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                      name === 'p10' ? 'P10 (Pessimista)' : name === 'p50' ? 'P50 (Mediana)' : 'P90 (Otimista)',
                    ]}
                    labelFormatter={v => `Mês ${v}`}
                  />
                  <Legend
                    formatter={(value: string) =>
                      value === 'p10' ? 'P10 (Pessimista)' : value === 'p50' ? 'P50 (Mediana)' : 'P90 (Otimista)'
                    }
                  />
                  <Line type="monotone" dataKey="p90" stroke="hsl(142 76% 45%)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="p50" stroke="hsl(38 92% 50%)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="p10" stroke="hsl(0 72% 51%)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <p className="text-xs text-muted-foreground">
              Baseado em {simResult.n_simulations.toLocaleString()} trajetórias · Horizonte de {simResult.horizon_months} meses · Modelo GBM
            </p>
          </div>
        )}
      </div>

      {/* Methodology */}
      <div className="glass-card p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">Metodologia</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-muted-foreground">
          <div className="p-4 bg-muted/30 rounded-lg">
            <p className="font-medium text-destructive mb-2">Cenário Pessimista</p>
            <p>Considera alta volatilidade negativa, baixo volume e sentimento bearish do mercado.</p>
          </div>
          <div className="p-4 bg-muted/30 rounded-lg">
            <p className="font-medium text-warning mb-2">Cenário Neutro</p>
            <p>Baseado na média histórica de volatilidade e tendências de mercado atuais.</p>
          </div>
          <div className="p-4 bg-muted/30 rounded-lg">
            <p className="font-medium text-success mb-2">Cenário Otimista</p>
            <p>Considera entrada de capital institucional, alta demanda e sentimento bullish.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
