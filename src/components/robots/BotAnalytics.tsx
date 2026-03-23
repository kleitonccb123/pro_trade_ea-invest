import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Zap, BarChart3, RefreshCw, Calendar, Crown, Flame, Award, Target } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { rankStrategiesWithStability, getRankingWindowInfo } from '@/utils/ranking-stability';

interface BotAnalysis {
  id: number;
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
  { value: 7, label: 'Semanal (7d)', emoji: '📊', color: 'from-blue-500 to-cyan-500' },
  { value: 30, label: 'Mensal (30d)', emoji: '📈', color: 'from-purple-500 to-pink-500' },
  { value: 90, label: 'Trimestral (90d)', emoji: '📉', color: 'from-orange-500 to-red-500' }
];

const MEDAL_CONFIG = [
  { rank: 0, medal: '🥇', color: 'from-yellow-500 to-yellow-600', label: 'Campeão', glow: 'shadow-glow-yellow' },
  { rank: 1, medal: '🥈', color: 'from-slate-300 to-slate-400', label: 'Vice', glow: 'shadow-glow-slate' },
  { rank: 2, medal: '🥉', color: 'from-orange-600 to-orange-700', label: '3º Lugar', glow: 'shadow-glow-orange' }
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
      const usedPromises = [7, 30, 90].map((days) =>
        fetch(`${API_URL}/bots/analytics/most-used?days=${days}`)
          .then((res) => res.json())
          .then((data) => ({ days, data }))
      );

      const profitablePromises = [7, 30, 90].map((days) =>
        fetch(`${API_URL}/bots/analytics/most-profitable?days=${days}`)
          .then((res) => res.json())
          .then((data) => ({ days, data }))
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
        usedMap[days as 7 | 30 | 90] = data;
      });

      profitableResults.forEach(({ days, data }) => {
        profitableMap[days as 7 | 30 | 90] = data;
      });

      setMostUsedData(usedMap);
      setMostProfitableData(profitableMap);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
      console.error('Error fetching analytics:', err);
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
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">Carregando Análises Premium</span>
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

  if (error) {
    return (
      <Card className="col-span-full glass-card border-destructive/40 bg-gradient-to-br from-destructive/10 to-destructive/5">
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Erro ao Carregar Análises
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center py-16 gap-6">
          <div className="text-center space-y-3">
            <p className="text-destructive font-bold text-lg">Falha na Conexão</p>
            <p className="text-muted-foreground">Não conseguimos carregar os dados. Verifique sua conexão.</p>
          </div>
          <button
            onClick={handleRefresh}
            className="px-6 py-3 bg-gradient-to-r from-primary to-accent text-white rounded-lg hover:shadow-lg hover:shadow-primary/50 font-bold transition-all duration-300 flex items-center gap-2 hover-lift"
          >
            <RefreshCw className="w-4 h-4" />
            Tentar Novamente
          </button>
        </CardContent>
      </Card>
    );
  }

  const usedBots = mostUsedData[selectedPeriod]?.bots || [];
  const profitableBots = mostProfitableData[selectedPeriod]?.bots || [];

  // Apply 20-day ranking stability to ensure consistent display
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
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="space-y-2">
            <CardTitle className="flex items-center gap-3 text-2xl md:text-3xl">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20 group-hover:shadow-primary/40 transition-all">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <span className="bg-gradient-to-r from-primary via-accent to-cyan-400 bg-clip-text text-transparent">Top 10 Robôs Premium</span>
            </CardTitle>
            <div className="flex flex-wrap items-center gap-3 pl-0 text-sm text-muted-foreground">
              <span>📊 Análise em Tempo Real</span>
              <span className="text-xs opacity-50">•</span>
              <span>🎯 Período: <span className="font-bold text-primary">{periodLabel}</span></span>
              <span className="text-xs opacity-50">•</span>
              <span className="text-xs text-primary/70">{rankingWindow.daysRemaining} dias restantes nesta janela</span>
            </div>
          </div>
          
          <div className="flex gap-2 justify-end">
            {/* Period Selector */}
            <Dialog open={showPeriodModal} onOpenChange={setShowPeriodModal}>
              <DialogTrigger asChild>
                <button className="px-4 py-3 hover:bg-primary/15 rounded-xl transition-all duration-300 group hover:shadow-lg hover:shadow-primary/20 flex items-center gap-2 bg-primary/10 border border-primary/30 font-semibold text-sm text-primary">
                  <Calendar className="w-5 h-5" />
                  <span className="hidden sm:inline">{periodLabel}</span>
                </button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[450px] bg-slate-900/98 border-primary/40 backdrop-blur">
                <DialogHeader className="space-y-3">
                  <DialogTitle className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                    Selecione o Período
                  </DialogTitle>
                  <p className="text-sm text-muted-foreground">Escolha um período de análise para visualizar os dados</p>
                </DialogHeader>
                <div className="space-y-3 py-6">
                  {PERIOD_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => {
                        setSelectedPeriod(option.value as 7 | 30 | 90);
                        setShowPeriodModal(false);
                      }}
                      className={`w-full p-5 rounded-xl border-2 transition-all duration-300 font-bold text-lg flex items-center gap-4 group ${
                        selectedPeriod === option.value
                          ? `border-primary bg-gradient-to-r ${option.color} text-white shadow-lg shadow-primary/20`
                          : 'border-border/40 bg-slate-800/40 text-foreground hover:border-primary/60 hover:bg-slate-800/60'
                      }`}
                    >
                      <span className="text-3xl">{option.emoji}</span>
                      <div className="flex-1 text-left">
                        <p>{option.label}</p>
                        <p className={`text-xs ${selectedPeriod === option.value ? 'text-white/70' : 'text-muted-foreground'}`}>
                          {option.value === 7 && 'Últimos 7 dias'}
                          {option.value === 30 && 'Últimos 30 dias'}
                          {option.value === 90 && 'Últimos 90 dias'}
                        </p>
                      </div>
                      {selectedPeriod === option.value && (
                        <div className="text-2xl">✓</div>
                      )}
                    </button>
                  ))}
                </div>
              </DialogContent>
            </Dialog>
            
            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              title="Atualizar dados agora"
              className="px-4 py-3 hover:bg-primary/15 rounded-xl transition-all duration-300 disabled:opacity-50 hover:shadow-lg hover:shadow-primary/20 border border-primary/30 bg-primary/10 font-semibold"
            >
              <RefreshCw className={`w-5 h-5 text-primary transition-transform ${refreshing ? 'animate-spin' : 'group-hover:rotate-180'}`} style={{ transitionDuration: '0.5s' }} />
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 relative z-10">
          {/* Premium Tab List */}
          <TabsList className="grid w-full grid-cols-2 mb-8 bg-slate-800/50 p-1.5 rounded-xl border border-primary/20 shadow-lg">
            <TabsTrigger 
              value="most-used" 
              className="font-bold text-base data-[state=active]:bg-gradient-to-r data-[state=active]:from-primary data-[state=active]:to-cyan-500 data-[state=active]:text-white transition-all duration-300 data-[state=active]:shadow-lg data-[state=active]:shadow-primary/30"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Top 10 Mais Usados
            </TabsTrigger>
            <TabsTrigger 
              value="most-profitable" 
              className="font-bold text-base data-[state=active]:bg-gradient-to-r data-[state=active]:from-success data-[state=active]:to-emerald-500 data-[state=active]:text-white transition-all duration-300 data-[state=active]:shadow-lg data-[state=active]:shadow-success/30"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Top 10 Rentáveis
            </TabsTrigger>
          </TabsList>

          {/* Most Used Bots Tab */}
          <TabsContent value="most-used" className="space-y-4 mt-8">
            {stableUsedBots.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 auto-rows-max">
                {stableUsedBots.slice(0, 10).map((bot, idx) => {
                  const medalInfo = MEDAL_CONFIG[idx] || null;
                  const isMedalist = idx < 3;

                  return (
                    <div
                      key={`${bot.id}-${idx}`}
                      className={`group relative rounded-2xl transition-all duration-300 hover-lift overflow-hidden animate-slide-in-up ${
                        isMedalist
                          ? `glass-card p-5 border-2 bg-gradient-to-br from-slate-800/90 to-slate-900/90 hover:from-slate-800 hover:to-slate-800/80`
                          : `glass-card p-4 border border-primary/25 hover:border-primary/50 bg-slate-800/40 hover:bg-slate-800/60`
                      }`}
                      style={{ 
                        animationDelay: `${idx * 50}ms`,
                        '--medal-color-start': medalInfo?.color.split(' ')[1],
                        '--medal-color-end': medalInfo?.color.split(' ')[2]
                      } as React.CSSProperties}
                    >
                      {/* Enhanced glow effect */}
                      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${
                        isMedalist 
                          ? medalInfo?.color || 'from-primary/20 to-transparent'
                          : 'from-primary/15 to-transparent'
                      } rounded-full blur-3xl -mr-16 -mt-16 group-hover:scale-150 transition-transform duration-500 opacity-50 group-hover:opacity-70`}></div>
                      
                      <div className="relative z-10 space-y-3">
                        {/* Top Rank Section */}
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-muted-foreground font-bold uppercase tracking-widest mb-1 opacity-70">
                              {isMedalist ? medalInfo?.label : `#${idx + 1}`}
                            </p>
                            <p className="font-bold text-foreground truncate group-hover:text-primary transition-colors text-sm leading-tight line-clamp-2">
                              {bot.name}
                            </p>
                          </div>
                          {isMedalist && (
                            <div className="text-3xl animate-medal-bounce flex-shrink-0">
                              {medalInfo?.medal}
                            </div>
                          )}
                        </div>
                        
                        {/* Symbol with icon */}
                        <div className="flex items-center gap-2 px-2 py-1.5 bg-slate-700/40 rounded-lg border border-slate-600/30">
                          <span className="text-sm font-bold text-primary">📊</span>
                          <span className="text-xs font-semibold text-muted-foreground">{bot.symbol}</span>
                        </div>
                        
                        {/* Divider */}
                        <div className="h-px bg-gradient-to-r from-slate-700/0 via-slate-600/40 to-slate-700/0"></div>
                        
                        {/* Key Metrics */}
                        <div className="space-y-2">
                          {/* Usage Count - Primary metric */}
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground/80 flex items-center gap-1 font-medium">
                              <Target className="w-3 h-3 opacity-60" />
                              Execuções
                            </span>
                            <span className={`font-bold text-sm tabular-nums ${isMedalist ? 'text-yellow-400' : 'text-cyan-400'}`}>
                              {bot.usage_count || 0}
                            </span>
                          </div>
                          
                          {/* Win Rate / Accuracy */}
                          {((bot.avg_pnl_percent || 0) !== 0) && (
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground/80 flex items-center gap-1 font-medium">
                                <TrendingUp className="w-3 h-3 opacity-60" />
                                Taxa Acerto
                              </span>
                              <span className={`font-bold text-sm tabular-nums ${(bot.avg_pnl_percent || 0) >= 0 ? 'text-success' : 'text-destructive'}`}>
                                {((bot.avg_pnl_percent || 0) >= 0 ? '+' : '')}{(bot.avg_pnl_percent || 0).toFixed(1)}%
                              </span>
                            </div>
                          )}
                        </div>

                        {/* Top Destaque Badge */}
                        {isMedalist && (
                          <div className="mt-3 pt-3 border-t border-slate-600/40 flex items-center justify-center gap-1">
                            <span className="text-xs font-bold text-yellow-300 flex items-center gap-1">
                              <Flame className="w-3 h-3" />
                              Top Destaque
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-20 rounded-2xl bg-slate-800/30 border border-slate-700/40">
                <Zap className="w-16 h-16 mx-auto mb-4 opacity-30 text-muted-foreground" />
                <p className="text-muted-foreground font-bold text-lg">Sem Dados de Uso</p>
                <p className="text-sm text-muted-foreground mt-2">Nenhum robô executado nos últimos {selectedPeriod} dias</p>
              </div>
            )}
          </TabsContent>

          {/* Most Profitable Bots Tab */}
          <TabsContent value="most-profitable" className="space-y-4 mt-8">
            {stableProfitableBots.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 auto-rows-max">
                {stableProfitableBots.slice(0, 10).map((bot, idx) => {
                  const avgPnlPercent = bot.avg_pnl_percent || 0;
                  const medalInfo = MEDAL_CONFIG[idx] || null;
                  const isMedalist = idx < 3;
                  const profitValue = bot.total_pnl || 0;
                  const isProfit = profitValue >= 0;

                  return (
                    <div
                      key={`${bot.id}-${idx}`}
                      className={`group relative rounded-2xl transition-all duration-300 hover-lift overflow-hidden animate-slide-in-up ${
                        isMedalist
                          ? `glass-card p-5 border-2 bg-gradient-to-br from-slate-800/90 to-slate-900/90 hover:from-slate-800 hover:to-slate-800/80`
                          : `glass-card p-4 border border-success/25 hover:border-success/50 bg-slate-800/40 hover:bg-slate-800/60`
                      }`}
                      style={{ 
                        animationDelay: `${idx * 50}ms`,
                        '--medal-color-start': medalInfo?.color.split(' ')[1],
                        '--medal-color-end': medalInfo?.color.split(' ')[2]
                      } as React.CSSProperties}
                    >
                      {/* Enhanced glow effect */}
                      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${
                        isMedalist 
                          ? medalInfo?.color || 'from-success/20 to-transparent'
                          : 'from-success/15 to-transparent'
                      } rounded-full blur-3xl -mr-16 -mt-16 group-hover:scale-150 transition-transform duration-500 opacity-50 group-hover:opacity-70`}></div>
                      
                      <div className="relative z-10 space-y-3">
                        {/* Top Rank Section */}
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs text-muted-foreground font-bold uppercase tracking-widest mb-1 opacity-70">
                              {isMedalist ? medalInfo?.label : `#${idx + 1}`}
                            </p>
                            <p className="font-bold text-foreground truncate group-hover:text-success transition-colors text-sm leading-tight line-clamp-2">
                              {bot.name}
                            </p>
                          </div>
                          {isMedalist && (
                            <div className="text-3xl animate-medal-bounce flex-shrink-0">
                              {medalInfo?.medal}
                            </div>
                          )}
                        </div>
                        
                        {/* Symbol with icon */}
                        <div className="flex items-center gap-2 px-2 py-1.5 bg-slate-700/40 rounded-lg border border-slate-600/30">
                          <span className="text-sm font-bold text-success">💰</span>
                          <span className="text-xs font-semibold text-muted-foreground">{bot.symbol}</span>
                        </div>
                        
                        {/* Divider */}
                        <div className="h-px bg-gradient-to-r from-slate-700/0 via-slate-600/40 to-slate-700/0"></div>
                        
                        {/* Key Metrics */}
                        <div className="space-y-2">
                          {/* Total PnL */}
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground/80 flex items-center gap-1 font-medium">
                              <BarChart3 className="w-3 h-3 opacity-60" />
                              Lucro
                            </span>
                            <span className={`font-bold text-sm tabular-nums ${isProfit ? 'text-success' : 'text-destructive'}`}>
                              {isProfit ? '+' : ''}${Math.abs(profitValue).toFixed(0)}
                            </span>
                          </div>
                          
                          {/* Average PnL Percent */}
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground/80 flex items-center gap-1 font-medium">
                              <TrendingUp className="w-3 h-3 opacity-60" />
                              Retorno
                            </span>
                            <span className={`font-bold text-sm tabular-nums ${avgPnlPercent >= 0 ? 'text-success' : 'text-destructive'}`}>
                              {(avgPnlPercent >= 0 ? '+' : '')}{avgPnlPercent.toFixed(1)}%
                            </span>
                          </div>

                          {/* Trade Count */}
                          {(bot.trade_count || 0) > 0 && (
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground/80 flex items-center gap-1 font-medium">
                                <Award className="w-3 h-3 opacity-60" />
                                Ops
                              </span>
                              <span className="font-bold text-sm tabular-nums text-foreground">{bot.trade_count}</span>
                            </div>
                          )}
                        </div>

                        {/* Rentável Premium Badge */}
                        {isMedalist && isProfit && (
                          <div className="mt-3 pt-3 border-t border-slate-600/40 flex items-center justify-center gap-1">
                            <span className="text-xs font-bold text-yellow-300 flex items-center gap-1">
                              <Flame className="w-3 h-3" />
                              Premium
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-20 rounded-2xl bg-slate-800/30 border border-slate-700/40">
                <BarChart3 className="w-16 h-16 mx-auto mb-4 opacity-30 text-muted-foreground" />
                <p className="text-muted-foreground font-bold text-lg">Sem Dados de Rentabilidade</p>
                <p className="text-sm text-muted-foreground mt-2">Nenhuma operação fechada nos últimos {selectedPeriod} dias</p>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Premium Summary Stats */}
        {(usedBots.length > 0 || profitableBots.length > 0) && (
          <div className="mt-12 pt-8 border-t border-primary/20">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-6">📊 Resumo do Período</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Total Active Bots */}
              <div className="glass-card p-5 rounded-xl border border-primary/40 group hover-lift relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent group-hover:from-primary/10 transition-colors pointer-events-none"></div>
                <div className="relative space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground font-bold uppercase tracking-wider">Robôs Ativos</p>
                    <BarChart3 className="w-4 h-4 text-primary opacity-60" />
                  </div>
                  <p className="text-3xl font-black text-transparent bg-gradient-to-r from-primary to-cyan-400 bg-clip-text">
                    {usedBots.length}
                  </p>
                  <p className="text-xs text-muted-foreground">no período</p>
                </div>
              </div>

              {/* Total Executions */}
              <div className="glass-card p-5 rounded-xl border border-blue-500/40 group hover-lift relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent group-hover:from-blue-500/10 transition-colors pointer-events-none"></div>
                <div className="relative space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground font-bold uppercase tracking-wider">Execuções</p>
                    <Target className="w-4 h-4 text-blue-500 opacity-60" />
                  </div>
                  <p className="text-3xl font-black text-blue-500">
                    {usedBots.reduce((sum, bot) => sum + (bot.usage_count || 0), 0).toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">total no período</p>
                </div>
              </div>

              {/* Total Profit */}
              <div className="glass-card p-5 rounded-xl border border-success/40 group hover-lift relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-success/5 to-transparent group-hover:from-success/10 transition-colors pointer-events-none"></div>
                <div className="relative space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground font-bold uppercase tracking-wider">Lucro Acumulado</p>
                    <TrendingUp className="w-4 h-4 text-success opacity-60" />
                  </div>
                  <p className={`text-3xl font-black ${
                    profitableBots.reduce((sum, bot) => sum + (bot.total_pnl || 0), 0) >= 0
                      ? 'text-success'
                      : 'text-destructive'
                  }`}>
                    ${Math.abs(profitableBots.reduce((sum, bot) => sum + (bot.total_pnl || 0), 0)).toFixed(0)}
                  </p>
                  <p className="text-xs text-muted-foreground">rendimento líquido</p>
                </div>
              </div>

              {/* Average Performance */}
              <div className="glass-card p-5 rounded-xl border border-accent/40 group hover-lift relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent group-hover:from-accent/10 transition-colors pointer-events-none"></div>
                <div className="relative space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground font-bold uppercase tracking-wider">Taxa Média</p>
                    <Award className="w-4 h-4 text-accent opacity-60" />
                  </div>
                  <p className="text-3xl font-black text-accent">
                    {profitableBots.length > 0
                      ? (profitableBots.reduce((sum, bot) => sum + (bot.avg_pnl_percent || 0), 0) / profitableBots.length).toFixed(1)
                      : '0'}%
                  </p>
                  <p className="text-xs text-muted-foreground">taxa de retorno</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
