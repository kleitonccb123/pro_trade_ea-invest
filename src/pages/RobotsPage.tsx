import { useState, useEffect, useCallback } from 'react';
import { Grid3x3, X, Menu, ChevronDown, Plus, Settings, Lock, Unlock, Loader2, RefreshCw, AlertCircle, TrendingUp, Zap, Target, Coins } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import RegistrationModal from '@/components/robots/RegistrationModal';
import { APIConfigModal } from '@/components/robots/APIConfigModal';
import { RealTimeOperations } from '@/components/robots/RealTimeOperations';
import { RobotGlowGrid } from '@/components/ui/robot-glow-grid';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Robot } from '@/types/robot';
import { botsApi } from '@/lib/api';
import { DailyChestButton } from '@/components/gamification/DailyChestButton';

// Mock data as fallback when API is unavailable
const FALLBACK_ROBOTS: (Robot & { country?: string; description?: string })[] = [
  {
    id: 'crypto-1',
    name: '🇺🇸 Bitcoin Scalper Pro',
    description: 'Robô especializado em scalping de Bitcoin com análise técnica avançada',
    strategy: 'Scalping + EMA',
    exchange: 'binance',
    pair: 'BTC/USDT',
    status: 'active',
    profit: 2547.32,
    trades: 1234,
    winRate: 68.5,
    runtime: '24h 15m',
    amount: 5000,
    stopLoss: 2,
    takeProfit: 3,
    riskLevel: 'medium',
    timeframe: '1m',
    indicators: ['EMA 21', 'EMA 50', 'RSI', 'Volume', 'MACD'],
    maxDrawdown: 5.2,
    sharpeRatio: 2.1,
    createdAt: '2026-01-15T00:00:00Z',
    lastUpdated: '2026-02-02T00:00:00Z',
    isLive: true,
    apiConnected: true,
    advancedSettings: {},
    country: 'usa',
  },
  {
    id: 'crypto-2',
    name: '🇯🇵 Ethereum DCA Master',
    description: 'Estratégia DCA (Dollar Cost Average) otimizada para Ethereum',
    strategy: 'DCA + Trend',
    exchange: 'binance',
    pair: 'ETH/USDT',
    status: 'stopped',
    profit: 1832.45,
    trades: 456,
    winRate: 72.3,
    runtime: '0h 0m',
    amount: 3000,
    stopLoss: 5,
    takeProfit: 8,
    riskLevel: 'low',
    timeframe: '1h',
    indicators: ['SMA 200', 'EMA 50', 'Bollinger Bands', 'Volume'],
    maxDrawdown: 3.8,
    sharpeRatio: 1.8,
    createdAt: '2026-01-20T00:00:00Z',
    lastUpdated: '2026-02-01T00:00:00Z',
    isLive: false,
    apiConnected: true,
    advancedSettings: {},
    country: 'japan',
  },
  {
    id: 'crypto-3',
    name: '🇧🇷 Altcoin Hunter',
    description: 'Busca automática de altcoins em alta com análise de volume',
    strategy: 'Volume + Momentum',
    exchange: 'binance',
    pair: 'Various',
    status: 'active',
    profit: 892.33,
    trades: 234,
    winRate: 61.2,
    runtime: '12h 30m',
    amount: 2000,
    stopLoss: 8,
    takeProfit: 15,
    riskLevel: 'high',
    timeframe: '5m',
    indicators: ['Volume', 'RSI', 'MACD', 'ATR'],
    maxDrawdown: 8.5,
    sharpeRatio: 1.3,
    createdAt: '2026-02-01T00:00:00Z',
    lastUpdated: '2026-02-02T00:00:00Z',
    isLive: true,
    apiConnected: false,
    advancedSettings: {},
    country: 'br',
  },
];

// Transform API response to Robot type
const transformBotToRobot = (bot: any): Robot & { country?: string; description?: string } => {
  // Determine status from state
  const getStatus = (state: string): 'active' | 'paused' | 'stopped' => {
    if (state === 'running') return 'active';
    if (state === 'paused') return 'paused';
    return 'stopped';
  };
  
  return {
    id: String(bot.id || bot._id),
    name: bot.name || 'Unnamed Bot',
    description: bot.description || `Trading bot for ${bot.symbol || 'crypto'}`,
    strategy: bot.config?.strategy || 'Custom Strategy',
    exchange: bot.config?.exchange || 'binance',
    pair: bot.symbol || 'BTC/USDT',
    status: getStatus(bot.state || 'stopped'),
    profit: bot.performance?.total_pnl || 0,
    trades: bot.performance?.total_trades || 0,
    winRate: bot.performance?.win_rate || 0,
    runtime: bot.runtime || '0h 0m',
    amount: bot.config?.amount || 1000,
    stopLoss: bot.config?.stop_loss || 5,
    takeProfit: bot.config?.take_profit || 10,
    riskLevel: bot.config?.risk_level || 'medium',
    timeframe: bot.config?.timeframe || '5m',
    indicators: bot.config?.indicators || ['RSI', 'MACD'],
    maxDrawdown: bot.performance?.max_drawdown || 0,
    sharpeRatio: bot.performance?.sharpe_ratio || 0,
    createdAt: bot.created_at || new Date().toISOString(),
    lastUpdated: bot.updated_at || new Date().toISOString(),
    isLive: bot.is_live || false,
    apiConnected: bot.api_connected || false,
    advancedSettings: bot.advanced_settings || {},
    country: bot.country,
  };
};

export default function RobotsPage() {
  const [selectedRobot, setSelectedRobot] = useState<Robot | null>(null);
  const [showUnlockAnimation, setShowUnlockAnimation] = useState(false);
  const [unlockingStage, setUnlockingStage] = useState<'locked' | 'unlocking' | 'unlocked'>('locked');
  const [showAPIModal, setShowAPIModal] = useState(false);
  const [showRealTime, setShowRealTime] = useState(false);
  const [robotRunning, setRobotRunning] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterBy, setFilterBy] = useState<'all' | 'active' | 'stopped'>('all');
  const [exchangeRegistered, setExchangeRegistered] = useState<boolean | null>(null);
  const [showRegistrationModal, setShowRegistrationModal] = useState(true);
  
  // API state
  const [robots, setRobots] = useState<(Robot & { country?: string; description?: string })[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isUsingFallback, setIsUsingFallback] = useState(false);

  // Fetch robots from API
  const fetchRobots = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const [botsData, instancesData] = await Promise.all([
        botsApi.list().catch(() => []),
        botsApi.getInstances().catch(() => [])
      ]);
      
      // Merge bots with their instances
      const mergedBots = botsData.map((bot: any) => {
        const instance = instancesData.find((inst: any) => inst.bot_id === bot.id);
        return {
          ...bot,
          state: instance?.state || 'stopped',
          last_heartbeat: instance?.last_heartbeat,
        };
      });
      
      if (mergedBots.length > 0) {
        const transformedRobots = mergedBots.map(transformBotToRobot);
        setRobots(transformedRobots);
        setIsUsingFallback(false);
      } else {
        // Use fallback data if no bots from API
        console.log('No bots from API, using fallback data');
        setRobots(FALLBACK_ROBOTS);
        setIsUsingFallback(true);
      }
    } catch (err: any) {
      console.error('Failed to fetch robots:', err);
      setError('Não foi possível carregar os robôs. Usando dados de demonstração.');
      setRobots(FALLBACK_ROBOTS);
      setIsUsingFallback(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchRobots();
  }, [fetchRobots]);

  const filteredRobots = robots.filter((robot) => {
    const matchesSearch = robot.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter =
      filterBy === 'all' || (filterBy === 'active' && robot.status === 'active') || (filterBy === 'stopped' && robot.status === 'stopped');
    return matchesSearch && matchesFilter;
  });

  const handleSelectRobot = (robot: Robot) => {
    setSelectedRobot(robot);
    // Logic: All strategies are locked by default
    setShowUnlockAnimation(true);
    setUnlockingStage('locked');
    
    // Auto-play the addictive animation
    setTimeout(() => setUnlockingStage('unlocking'), 1000);
    setTimeout(() => setUnlockingStage('unlocked'), 2500);
  };



  return (
    <div className="min-h-screen bg-slate-950 overflow-hidden">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <style>{`
          @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
          }
          .robots-bg {
            background: linear-gradient(-45deg, #0f172a, #1e293b, #0f172a, #1e293b);
            background-size: 400% 400%;
            animation: gradientShift 15s ease infinite;
          }
        `}</style>
        <div className="absolute inset-0 robots-bg opacity-40"></div>
        <div className="absolute inset-0 bg-[linear-gradient(rgba(30,41,82,0.15)_1px,transparent_1px),linear-gradient(90deg,rgba(30,41,82,0.15)_1px,transparent_1px)] bg-[size:80px_80px]"></div>
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/8 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-600/8 rounded-full blur-3xl"></div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 px-4 sm:px-6 lg:px-8 py-8 space-y-8 max-w-7xl mx-auto">
        {/* Ultra Modern Header */}
        <div className="space-y-6">
          <div className="backdrop-blur-xl bg-gradient-to-r from-slate-900/40 to-slate-800/40 border border-slate-700/30 rounded-2xl p-8 shadow-2xl">
            {/* Header Top */}
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-6">
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-3">
                  <div className="text-5xl">🤖</div>
                  <div>
                    <h1 className="text-4xl font-black bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                      Estratégias de Trading
                    </h1>
                    <p className="text-slate-400 text-lg mt-1">Robôs de IA com desempenho premium</p>
                  </div>
                </div>
              </div>
              <div className="flex gap-3 items-center">
                <DailyChestButton />
                <Button
                  onClick={fetchRobots}
                  disabled={isLoading}
                  className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold px-6 py-3 rounded-xl flex items-center gap-2 shadow-lg hover:shadow-xl hover:shadow-blue-500/20 transition-all group"
                >
                  {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <RefreshCw className="w-5 h-5 group-hover:rotate-180 transition-transform duration-500" />
                  )}
                  Atualizar
                </Button>
              </div>
            </div>

            {/* Stats Bar */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="backdrop-blur-md bg-slate-800/30 border border-slate-700/50 rounded-lg p-4 hover:bg-slate-800/50 transition-all">
                <p className="text-xs text-slate-500 mb-1">Total de Robôs</p>
                <p className="text-2xl font-black text-blue-400">{robots.length}</p>
              </div>
              <div className="backdrop-blur-md bg-slate-800/30 border border-slate-700/50 rounded-lg p-4 hover:bg-slate-800/50 transition-all">
                <p className="text-xs text-slate-500 mb-1">Ativos</p>
                <p className="text-2xl font-black text-emerald-400">{robots.filter(r => r.status === 'active').length}</p>
              </div>
              <div className="backdrop-blur-md bg-slate-800/30 border border-slate-700/50 rounded-lg p-4 hover:bg-slate-800/50 transition-all">
                <p className="text-xs text-slate-500 mb-1">Lucro Total</p>
                <p className="text-2xl font-black text-green-400">${robots.reduce((a, r) => a + (r.profit || 0), 0).toFixed(0)}</p>
              </div>
              <div className="backdrop-blur-md bg-slate-800/30 border border-slate-700/50 rounded-lg p-4 hover:bg-slate-800/50 transition-all">
                <p className="text-xs text-slate-500 mb-1">Taxa de Sucesso</p>
                <p className="text-2xl font-black text-purple-400">{(robots.reduce((a, r) => a + (r.winRate || 0), 0) / Math.max(robots.length, 1)).toFixed(1)}%</p>
              </div>
            </div>
          </div>
        </div>

        {/* Error/Info Alert */}
        {(error || isUsingFallback) && (
          <div className="backdrop-blur-lg bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-center gap-3 shadow-lg">
            <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
            <p className="text-yellow-400">
              {error || 'Exibindo dados de demonstração. Configure a API para ver seus robôs reais.'}
            </p>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-32">
            <div className="text-center space-y-6">
              <div className="w-16 h-16 mx-auto rounded-full border-4 border-slate-700 border-t-blue-500 animate-spin"></div>
              <p className="text-slate-300 text-lg font-medium">Carregando suas estratégias...</p>
            </div>
          </div>
        )}

        {/* Content (when not loading) */}
        {!isLoading && (
          <>
            {/* Controls Bar */}
            <div className="backdrop-blur-xl bg-slate-900/40 border border-slate-700/30 rounded-2xl p-6 shadow-lg">
              <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center">
                <div className="flex-1">
                  <div className="relative group">
                    <input
                      placeholder="🔍 Buscar robôs, pares, estratégias..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-full h-11 pl-11 pr-4 rounded-xl bg-slate-800/40 border border-slate-600/40 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all duration-300"
                    />
                    <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">🔎</span>
                  </div>
                </div>
                
                <div className="flex gap-2 flex-wrap">
                  {(['all', 'active', 'stopped'] as const).map((filter) => (
                    <Button
                      key={filter}
                      onClick={() => setFilterBy(filter)}
                      className={`px-4 py-2 rounded-lg font-medium transition-all capitalize ${
                        filterBy === filter
                          ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20'
                          : 'bg-slate-800/40 hover:bg-slate-800/60 text-slate-300 border border-slate-700/30'
                      }`}
                    >
                      {filter === 'all' ? 'Todos' : filter === 'active' ? 'Ativos' : 'Parados'}
                    </Button>
                  ))}
                </div>
              </div>
            </div>

            {/* Portfolio/Bag Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-3 pb-4 border-b border-slate-700/50">
                <div className="text-3xl">💰</div>
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-white">Seu Portfólio de Robôs</h2>
                  <p className="text-sm text-slate-400">Ganhos e performance de suas estratégias</p>
                </div>
              </div>

              {/* Portfolio Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Total Earnings */}
                <div className="backdrop-blur-xl bg-gradient-to-br from-emerald-500/10 to-green-500/10 border border-emerald-500/30 rounded-xl p-6 hover:border-emerald-500/50 transition-all group cursor-pointer">
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center group-hover:bg-emerald-500/30 transition-all">
                      <Coins className="w-6 h-6 text-emerald-400" />
                    </div>
                    <TrendingUp className="w-5 h-5 text-emerald-400" />
                  </div>
                  <p className="text-sm text-slate-400 mb-1">Ganhos Totais</p>
                  <p className="text-3xl font-black text-emerald-400">${robots.reduce((a, r) => a + (r.profit || 0), 0).toFixed(2)}</p>
                  <p className="text-xs text-emerald-500/70 mt-3">+{robots.filter(r => r.profit > 0).length} robôs lucrativos</p>
                </div>

                {/* Active Now */}
                <div className="backdrop-blur-xl bg-gradient-to-br from-blue-500/10 to-indigo-500/10 border border-blue-500/30 rounded-xl p-6 hover:border-blue-500/50 transition-all group cursor-pointer">
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center group-hover:bg-blue-500/30 transition-all">
                      <Zap className="w-6 h-6 text-blue-400" />
                    </div>
                    <div className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></div>
                  </div>
                  <p className="text-sm text-slate-400 mb-1">Robôs Ativos</p>
                  <p className="text-3xl font-black text-blue-400">{robots.filter(r => r.status === 'active').length}</p>
                  <p className="text-xs text-blue-500/70 mt-3">Operando neste momento</p>
                </div>

                {/* Win Rate */}
                <div className="backdrop-blur-xl bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-xl p-6 hover:border-purple-500/50 transition-all group cursor-pointer">
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center group-hover:bg-purple-500/30 transition-all">
                      <Target className="w-6 h-6 text-purple-400" />
                    </div>
                    <TrendingUp className="w-5 h-5 text-purple-400" />
                  </div>
                  <p className="text-sm text-slate-400 mb-1">Taxa de Sucesso Média</p>
                  <p className="text-3xl font-black text-purple-400">{(robots.reduce((a, r) => a + (r.winRate || 0), 0) / Math.max(robots.length, 1)).toFixed(1)}%</p>
                  <p className="text-xs text-purple-500/70 mt-3">Acurácia combinada</p>
                </div>
              </div>
            </div>

            {/* Top 10 Strategies Section - Robots Grid */}
            <div className="space-y-4">
              <div className="flex items-center gap-3 pb-4 border-b border-slate-700/50">
                <div className="text-2xl">⭐</div>
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-white">Todas as Estratégias ({filteredRobots.length})</h2>
                  <p className="text-sm text-slate-400">Gerencie e monitore seus robôs</p>
                </div>
              </div>

              {filteredRobots.length === 0 ? (
                <div className="backdrop-blur-lg bg-slate-900/30 border border-slate-700/30 rounded-xl p-12 text-center">
                  <p className="text-slate-400 text-lg">Nenhum robô encontrado</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredRobots.map((robot) => (
                    <div
                      key={robot.id}
                      onClick={() => handleSelectRobot(robot)}
                      className="backdrop-blur-xl bg-gradient-to-br from-slate-800/40 to-slate-900/40 border border-slate-700/40 rounded-xl p-6 hover:border-slate-600/60 hover:bg-gradient-to-br hover:from-slate-800/60 hover:to-slate-900/50 transition-all duration-300 cursor-pointer group hover:shadow-2xl hover:shadow-blue-500/10 transform hover:scale-105"
                    >
                      {/* Header */}
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <h3 className="text-white font-bold text-lg group-hover:text-blue-300 transition-colors line-clamp-2">{robot.name}</h3>
                          <p className="text-slate-400 text-sm mt-1">{robot.pair}</p>
                        </div>
                        <div className={`w-3 h-3 rounded-full flex-shrink-0 ${robot.status === 'active' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`}></div>
                      </div>

                      {/* Strategy & Risk */}
                      <div className="flex gap-2 mb-4 flex-wrap">
                        <span className="text-xs px-2 py-1 rounded-lg bg-blue-500/20 text-blue-300">{robot.strategy}</span>
                        <span className={`text-xs px-2 py-1 rounded-lg ${
                          robot.riskLevel === 'low' ? 'bg-emerald-500/20 text-emerald-300' :
                          robot.riskLevel === 'medium' ? 'bg-yellow-500/20 text-yellow-300' :
                          'bg-red-500/20 text-red-300'
                        }`}>{robot.riskLevel}</span>
                      </div>

                      {/* Stats Grid */}
                      <div className="grid grid-cols-2 gap-3 mb-4 pb-4 border-t border-slate-700/30">
                        <div className="pt-3">
                          <p className="text-xs text-slate-500 mb-1">Lucro</p>
                          <p className={`font-bold text-sm ${robot.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            ${robot.profit?.toFixed(0) || 0}
                          </p>
                        </div>
                        <div className="pt-3">
                          <p className="text-xs text-slate-500 mb-1">Win Rate</p>
                          <p className="font-bold text-sm text-purple-400">{robot.winRate?.toFixed(1)}%</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 mb-1">Trades</p>
                          <p className="font-bold text-sm text-blue-400">{robot.trades}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 mb-1">Drawdown</p>
                          <p className="font-bold text-sm text-orange-400">{robot.maxDrawdown?.toFixed(1)}%</p>
                        </div>
                      </div>

                      {/* Action Button */}
                      <Button
                        className="w-full bg-gradient-to-r from-blue-600/40 to-indigo-600/40 hover:from-blue-600/60 hover:to-indigo-600/60 border border-blue-500/30 text-blue-200 font-medium rounded-lg transition-all"
                        onClick={() => handleSelectRobot(robot)}
                      >
                        Acessar Painel →
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {/* Real-Time Operations Modal - Fullscreen */}
        {selectedRobot && showRealTime && (
          <Dialog open={selectedRobot && showRealTime} onOpenChange={(open) => !open && setShowRealTime(false)}>
            <DialogContent className="max-w-7xl h-[90vh] overflow-y-auto bg-gradient-to-br from-background to-background/50">
              <DialogHeader className="sticky top-0 bg-gradient-to-r from-primary/20 to-accent/20 border-b border-primary/30 -m-6 mb-6 p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center">
                      <span className="text-2xl">🤖</span>
                    </div>
                    <div>
                      <DialogTitle className="text-2xl font-bold">{selectedRobot.name}</DialogTitle>
                      <p className="text-sm text-muted-foreground mt-1">{selectedRobot.pair} • {selectedRobot.strategy}</p>
                    </div>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => setShowRealTime(false)}>
                    <X className="w-6 h-6" />
                  </Button>
                </div>
              </DialogHeader>
              <div className="mt-6">
                <RealTimeOperations robot={selectedRobot} isRunning={robotRunning} onToggle={setRobotRunning} />
              </div>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* API Config Modal */}
      <APIConfigModal
        robot={selectedRobot}
        isOpen={showAPIModal}
        onClose={() => {
          setShowAPIModal(false);
          setShowRealTime(true);
        }}
        onConnect={(apiKey, apiSecret, apiPassword) => {
          console.log('Connected with API:', { apiKey, apiSecret, apiPassword });
          setShowAPIModal(false);
          setShowRealTime(true);
        }}
      />

      {/* Unlock Animation Dialog */}
      <Dialog open={showUnlockAnimation} onOpenChange={setShowUnlockAnimation}>
        <DialogContent className="sm:max-w-md bg-slate-900 border-slate-800 text-white flex flex-col items-center justify-center p-12 min-h-[400px]">
             
             {unlockingStage === 'locked' && (
                 <div className="flex flex-col items-center animate-in zoom-in duration-500">
                    <div className="w-40 h-40 rounded-full bg-slate-800/50 flex items-center justify-center mb-8 ring-1 ring-slate-700 shadow-2xl relative overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-br from-red-500/10 to-transparent"></div>
                        <Lock className="w-20 h-20 text-slate-400 drop-shadow-lg" />
                    </div>
                    <h2 className="text-3xl font-bold mb-3 tracking-tight">Estratégia Bloqueada</h2>
                    <p className="text-slate-400 text-center max-w-xs">
                        Esta é uma estratégia premium de alta performance.
                    </p>
                 </div>
             )}

             {unlockingStage === 'unlocking' && (
                 <div className="flex flex-col items-center">
                    <div className="w-40 h-40 rounded-full bg-yellow-500/10 flex items-center justify-center mb-8 ring-4 ring-yellow-500/20 shadow-[0_0_50px_rgba(234,179,8,0.2)] animate-pulse">
                        <Lock className="w-20 h-20 text-yellow-500 animate-bounce" />
                    </div>
                    <h2 className="text-3xl font-bold mb-3 text-yellow-500 animate-pulse">Acessando...</h2>
                 </div>
             )}

             {unlockingStage === 'unlocked' && (
                 <div className="flex flex-col items-center animate-in zoom-in duration-500">
                    <div className="w-40 h-40 rounded-full bg-emerald-500/10 flex items-center justify-center mb-8 ring-4 ring-emerald-500/20 shadow-[0_0_50px_rgba(16,185,129,0.3)]">
                        <Unlock className="w-20 h-20 text-emerald-500" />
                    </div>
                    <h2 className="text-3xl font-bold mb-3 text-emerald-400 bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-green-600">
                        Acesso Liberado!
                    </h2>
                    <p className="text-slate-400 text-center mb-8">
                        Prepare-se para operar com alta performance.
                    </p>
                    <Button 
                        onClick={() => {
                            setShowUnlockAnimation(false);
                            setShowRealTime(true); 
                        }}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-6 px-8 rounded-xl w-full text-lg shadow-lg hover:shadow-emerald-500/20 transition-all transform hover:scale-105"
                    >
                        Acessar Painel Agora
                    </Button>
                 </div>
             )}
        </DialogContent>
      </Dialog>

      {/* Registration Modal */}
      <RegistrationModal
        isOpen={showRegistrationModal}
        onClose={() => setShowRegistrationModal(false)}
        onAnswer={(hasAccount) => {
          setExchangeRegistered(hasAccount);
          setShowRegistrationModal(false);
        }}
      />
    </div>
  );
}
