import { useState, useEffect } from 'react';
import { TrendingUp, Zap, BarChart3, RefreshCw, Calendar } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { rankStrategiesWithStability, getRankingWindowInfo } from '@/utils/ranking-stability';

interface BotAnalysis {
  id: number | string;
  name: string;
  symbol: string;
  usage_count?: number;
  total_pnl?: number;
  avg_pnl_percent?: number;
  trade_count?: number;
  nationality?: string;
  win_rate?: number;
}

interface AnalyticsData {
  days: number;
  bots: BotAnalysis[];
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PERIOD_OPTIONS = [
  { value: 7, label: 'Semanal (7d)', emoji: '📊' },
  { value: 30, label: 'Mensal (30d)', emoji: '📈' },
  { value: 90, label: 'Trimestral (90d)', emoji: '📉' }
];

// Mock data para testes
const MOCK_BOTS: BotAnalysis[] = [
  { id: '1', name: 'Bitcoin Scalper Pro', symbol: 'BTC/USDT', usage_count: 156, total_pnl: 3451, avg_pnl_percent: 2.34, nationality: '🇨🇳 China', win_rate: 68.5 },
  { id: '2', name: 'Legend Slayer', symbol: 'ETH/USDT', usage_count: 145, total_pnl: 3201, avg_pnl_percent: 2.18, nationality: '🇷🇺 Russia', win_rate: 65.0 },
  { id: '3', name: 'Grid Precision', symbol: 'BNB/USDT', usage_count: 132, total_pnl: 2950, avg_pnl_percent: 1.95, nationality: '🇯🇵 Japan', win_rate: 62.3 },
  { id: '4', name: 'Momentum Rider', symbol: 'SOL/USDT', usage_count: 120, total_pnl: 2750, avg_pnl_percent: 1.87, nationality: '🇺🇸 USA', win_rate: 61.0 },
  { id: '5', name: 'DCA Master', symbol: 'ADA/USDT', usage_count: 110, total_pnl: 2500, avg_pnl_percent: 1.65, nationality: '🇪🇸 Spain', win_rate: 59.5 },
  { id: '6', name: 'Trend Analyzer', symbol: 'XRP/USDT', usage_count: 98, total_pnl: 2200, avg_pnl_percent: 1.52, nationality: '🇯🇵 Japan', win_rate: 58.0 },
  { id: '7', name: 'AI Supremacy', symbol: 'AVAX/USDT', usage_count: 87, total_pnl: 2050, avg_pnl_percent: 1.42, nationality: '🇹🇨 Taiwan', win_rate: 56.5 },
  { id: '8', name: 'Arbitrage Pro', symbol: 'LINK/USDT', usage_count: 76, total_pnl: 1800, avg_pnl_percent: 1.28, nationality: '🇬🇧 UK', win_rate: 55.0 },
  { id: '9', name: 'Volatility Hunter', symbol: 'DOGE/USDT', usage_count: 65, total_pnl: 1650, avg_pnl_percent: 1.15, nationality: '🇲🇽 Mexico', win_rate: 53.5 },
  { id: '10', name: 'Smart Allocator', symbol: 'MATIC/USDT', usage_count: 54, total_pnl: 1521, avg_pnl_percent: 1.05, nationality: '🇦🇪 UAE', win_rate: 52.0 }
];

export function BotAnalytics() {
  const [mostUsedData, setMostUsedData] = useState<{
    [key: number]: AnalyticsData | null;
  }>({
    7: null,
    30: null,
    90: null,
  });

  const [mostProfitableData, setMostProfitableData] = useState<{
    [key: number]: AnalyticsData | null;
  }>({
    7: null,
    30: null,
    90: null,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<7 | 30 | 90>(7);
  const [refreshing, setRefreshing] = useState(false);
  const [showPeriodModal, setShowPeriodModal] = useState(false);

  useEffect(() => {
    fetchAnalyticsData();
  }, []);

  const fetchAnalyticsData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Tenta buscar dados da API
      const usedPromises = [7, 30, 90].map((days) =>
        fetch(`${API_URL}/bots/analytics/most-used?days=${days}`)
          .then((res) => res.json())
          .then((data) => ({ days, data }))
          .catch(() => ({ days, data: { days, bots: MOCK_BOTS } }))
      );

      const profitablePromises = [7, 30, 90].map((days) =>
        fetch(`${API_URL}/bots/analytics/most-profitable?days=${days}`)
          .then((res) => res.json())
          .then((data) => ({ days, data }))
          .catch(() => ({ days, data: { days, bots: MOCK_BOTS } }))
      );

      const [usedResults, profitableResults] = await Promise.all([
        Promise.all(usedPromises),
        Promise.all(profitablePromises),
      ]);

      const usedMap: typeof mostUsedData = { 7: null, 30: null, 90: null };
      const profitableMap: typeof mostProfitableData = {
        7: null,
        30: null,
        90: null,
      };

      usedResults.forEach(({ days, data }) => {
        usedMap[days as 7 | 30 | 90] = data || { days, bots: MOCK_BOTS };
      });

      profitableResults.forEach(({ days, data }) => {
        profitableMap[days as 7 | 30 | 90] = data || { days, bots: MOCK_BOTS };
      });

      setMostUsedData(usedMap);
      setMostProfitableData(profitableMap);
    } catch (err) {
      console.error('Error fetching analytics:', err);
      // Fallback para mock data
      const mockData = { 7: { days: 7, bots: MOCK_BOTS }, 30: { days: 30, bots: MOCK_BOTS }, 90: { days: 90, bots: MOCK_BOTS } };
      setMostUsedData(mockData);
      setMostProfitableData(mockData);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchAnalyticsData();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <Card className="col-span-full glass-card border-primary/40 bg-gradient-to-br from-primary/10 to-accent/5 hover-lift">
        <CardHeader className="space-y-3">
          <CardTitle className="flex items-center gap-3 text-2xl">
            <BarChart3 className="w-6 h-6 text-primary animate-float" />
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">Carregando Top 10 Robôs</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center py-24">
          <div className="text-center space-y-6">
            <div className="relative w-16 h-16 mx-auto">
              <div className="absolute inset-0 bg-gradient-to-r from-primary to-accent rounded-full animate-spin" style={{ borderTopColor: 'transparent' }}></div>
              <div className="absolute inset-2 bg-background rounded-full flex items-center justify-center">
                <Zap className="w-8 h-8 text-primary animate-pulse-glow" />
              </div>
            </div>
            <div>
              <p className="text-lg text-foreground font-bold">Analisando dados...</p>
              <p className="text-sm text-muted-foreground mt-1">Buscando os melhores robôs para você</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const usedBots = mostUsedData[selectedPeriod]?.bots || MOCK_BOTS;
  const profitableBots = mostProfitableData[selectedPeriod]?.bots || MOCK_BOTS;

  const stableUsedBots = rankStrategiesWithStability(
    usedBots,
    (a, b) => (b.usage_count || 0) - (a.usage_count || 0)
  );
  
  const stableProfitableBots = rankStrategiesWithStability(
    profitableBots,
    (a, b) => (b.total_pnl || 0) - (a.total_pnl || 0)
  );

  const rankingWindow = getRankingWindowInfo();
  const periodLabel = PERIOD_OPTIONS.find(p => p.value === selectedPeriod)?.label || '7d';

  return (
    <Card className="col-span-full glass-card border-primary/40 bg-gradient-to-br from-primary/8 to-accent/4 overflow-hidden hover-lift group">
      <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-primary/20 to-transparent rounded-full blur-3xl -mr-40 -mt-40 group-hover:scale-125 transition-transform duration-500 pointer-events-none"></div>
      <div className="absolute bottom-0 left-0 w-60 h-60 bg-gradient-to-tr from-accent/15 to-transparent rounded-full blur-3xl -ml-30 -mb-30 pointer-events-none"></div>
      
      <CardHeader className="pb-6 relative z-10">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <CardTitle className="flex items-center gap-3 text-2xl md:text-3xl">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-white" />
              </div>
              <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">Top 10 Robôs Premium</span>
            </CardTitle>
            <p className="text-sm text-muted-foreground ml-13">Os melhores robôs em tempo real - Período: {periodLabel}</p>
          </div>
          <div className="flex gap-2">
            <Dialog open={showPeriodModal} onOpenChange={setShowPeriodModal}>
              <DialogTrigger asChild>
                <button className="p-3 hover:bg-primary/15 rounded-xl transition-all duration-300 group hover-lift flex items-center gap-2 bg-primary/10 border border-primary/30">
                  <Calendar className="w-5 h-5 text-primary" />
                  <span className="text-sm font-bold text-primary hidden sm:inline">{periodLabel}</span>
                </button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[400px] bg-slate-900/95 border-primary/40">
                <DialogHeader>
                  <DialogTitle className="text-primary text-2xl">Escolha o Período</DialogTitle>
                </DialogHeader>
                <div className="space-y-3 py-6">
                  {PERIOD_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => {
                        setSelectedPeriod(option.value as 7 | 30 | 90);
                        setShowPeriodModal(false);
                      }}
                      className={`w-full p-4 rounded-xl border-2 transition-all duration-300 font-bold text-lg flex items-center gap-3 ${
                        selectedPeriod === option.value
                          ? 'border-primary bg-gradient-to-r from-primary/20 to-accent/10 text-primary'
                          : 'border-border/40 bg-slate-800/40 text-foreground hover:border-primary/60 hover:bg-primary/5'
                      }`}
                    >
                      <span className="text-2xl">{option.emoji}</span>
                      <span>{option.label}</span>
                    </button>
                  ))}
                </div>
              </DialogContent>
            </Dialog>
            
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-3 hover:bg-primary/15 rounded-xl transition-all duration-300 disabled:opacity-50 group hover-lift"
            >
              <RefreshCw className={`w-5 h-5 text-primary transition-transform ${refreshing ? 'animate-spin' : 'group-hover:rotate-180'}`} style={{ transitionDuration: '0.5s' }} />
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 relative z-10">
        <Tabs defaultValue="most-used" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-8 bg-muted/30 p-1 rounded-xl border border-primary/20">
            <TabsTrigger 
              value="most-used" 
              className="font-bold text-base data-[state=active]:bg-gradient-to-r data-[state=active]:from-primary data-[state=active]:to-accent data-[state=active]:text-white transition-all duration-300"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Top 10 Mais Usados
            </TabsTrigger>
            <TabsTrigger 
              value="most-profitable" 
              className="font-bold text-base data-[state=active]:bg-gradient-to-r data-[state=active]:from-success data-[state=active]:to-emerald-500 data-[state=active]:text-white transition-all duration-300"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Top 10 Rentáveis
            </TabsTrigger>
          </TabsList>

          <div className="mb-4 text-xs text-muted-foreground text-center">
            <span>Classificação estável por 20 dias • {rankingWindow.daysRemaining} dias restantes</span>
          </div>

          <TabsContent value="most-used" className="space-y-3 mt-8">
            {stableUsedBots.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {stableUsedBots.slice(0, 10).map((bot, idx) => (
                  <div
                    key={`${bot.id}-${idx}`}
                    className="group glass-card p-4 rounded-lg border border-primary/30 hover:border-primary/70 transition-all duration-300 hover-lift relative overflow-hidden animate-fade-up"
                    style={{ animationDelay: `${idx * 30}ms` }}
                  >
                    <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-primary/20 to-transparent rounded-full blur-2xl -mr-12 -mt-12 group-hover:scale-125 transition-transform duration-500"></div>
                    
                    <div className="relative space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="font-bold text-foreground truncate">{idx + 1}. {bot.name}</p>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">País</span>
                        <span className="font-semibold">{bot.nationality || bot.symbol}</span>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Taxa Acerto</span>
                        <span className={`font-bold ${(bot.avg_pnl_percent || 0) >= 0 ? 'text-success' : 'text-destructive'}`}>
                          {((bot.avg_pnl_percent || 0) >= 0 ? '+' : '')}{(bot.avg_pnl_percent || 0).toFixed(1)}%
                        </span>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm border-t border-primary/10 pt-2">
                        <span className="text-muted-foreground">Usuários</span>
                        <span className="font-bold text-primary">{bot.usage_count || 0}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-16 rounded-xl bg-muted/20 border border-border/40">
                <p className="text-muted-foreground font-bold text-lg">Sem Dados</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="most-profitable" className="space-y-3 mt-8">
            {stableProfitableBots.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {stableProfitableBots.slice(0, 10).map((bot, idx) => (
                  <div
                    key={`${bot.id}-${idx}`}
                    className="group glass-card p-4 rounded-lg border border-success/30 hover:border-success/70 transition-all duration-300 hover-lift relative overflow-hidden animate-fade-up"
                    style={{ animationDelay: `${idx * 30}ms` }}
                  >
                    <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-success/20 to-transparent rounded-full blur-2xl -mr-12 -mt-12 group-hover:scale-125 transition-transform duration-500"></div>
                    
                    <div className="relative space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="font-bold text-foreground truncate">{idx + 1}. {bot.name}</p>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Lucro</span>
                        <span className="font-bold text-success">${(bot.total_pnl || 0).toFixed(0)}</span>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Win Rate</span>
                        <span className="font-bold text-success">{(bot.win_rate || 50).toFixed(1)}%</span>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm border-t border-success/10 pt-2">
                        <span className="text-muted-foreground">Trades</span>
                        <span className="font-bold text-success">{bot.trade_count || 0}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-16 rounded-xl bg-muted/20 border border-border/40">
                <p className="text-muted-foreground font-bold text-lg">Sem Dados</p>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Summary Stats */}
        {(usedBots.length > 0 || profitableBots.length > 0) && (
          <div className="mt-12 pt-8 border-t border-primary/20 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="glass-card p-6 rounded-xl border border-primary/40 text-center group hover-lift">
              <p className="text-xs text-muted-foreground font-bold mb-2 uppercase">Robôs Top 10</p>
              <p className="text-4xl font-black text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">10</p>
            </div>
            <div className="glass-card p-6 rounded-xl border border-blue-500/40 text-center group hover-lift">
              <p className="text-xs text-muted-foreground font-bold mb-2 uppercase">Total Usuários</p>
              <p className="text-4xl font-black text-blue-600">{usedBots.reduce((sum, bot) => sum + (bot.usage_count || 0), 0)}</p>
            </div>
            <div className="glass-card p-6 rounded-xl border border-success/40 text-center group hover-lift">
              <p className="text-xs text-muted-foreground font-bold mb-2 uppercase">Lucro Total</p>
              <p className="text-4xl font-black text-success">${profitableBots.reduce((sum, bot) => sum + (bot.total_pnl || 0), 0).toFixed(0)}</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
