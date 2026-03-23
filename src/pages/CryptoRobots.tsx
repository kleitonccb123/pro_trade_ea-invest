import { useState, useEffect } from 'react';
import { ArrowLeft, Plus, Bot, Filter, DollarSign, ExternalLink, Bitcoin, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { RobotCard } from '@/components/robots/RobotCard';
import { RobotConfigModal } from '@/components/robots/RobotConfigModal';
import { TrendGridDetails } from '@/components/robots/TrendGridDetails';
import { ActiveRobotModal } from '@/components/modals/ActiveRobotModal';
import { ExchangeManager } from '@/components/exchange/ExchangeManager';
import { BrokerSignupModal } from '@/components/modals/BrokerSignupModal';
import { Robot } from '@/types/robot';
import { getExchangeById, CRYPTO_EXCHANGE } from '@/lib/exchanges';

const cryptoRobots: Robot[] = [
  {
    id: 'crypto-1',
    name: 'Bitcoin Scalper Pro',
    description: 'Robô especializado em scalping de Bitcoin com análise técnica avançada',
    strategy: 'Scalping + EMA',
    exchange: 'binance', // Exchange de cripto configurada
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
    advancedSettings: {
      enableMovingAverage: true,
      movingAveragePeriod: 21,
      movingAverageType: 'EMA',
      useRSI: true,
      rsiOversold: 30,
      rsiOverbought: 70,
      useCandleStrength: true,
      minimumCandleBody: 50.0,
      useVolume: true,
      minimumVolumeRatio: 1.2,
      useAdaptiveRange: true,
      rangePeriod: 14,
      rangeMultiplier: 1.5,
      enableProtections: true,
      maxProtections: 5,
      timeBetweenProtections: 30,
      protectionDistances: [10, 20, 30],
      protectionVolumes: [1, 2, 3],
      dailyGoal: 100,
      dailyLossLimit: 50,
      emergencyDrawdown: 10,
      enableScalper: true,
      scalperInterval: 60,
      useCandleMaturity: true,
      maturitySeconds: 10,
      breakoutMinDistance: 5,
      stopLossUSD: 50,
      takeProfitUSD: 100,
      dailyBlocked: false,
      emergencyBlocked: false,
      protectionsOpened: 0,
    },
  },
  {
    id: 'crypto-2',
    name: 'Ethereum DCA Master',
    description: 'Estratégia DCA (Dollar Cost Average) otimizada para Ethereum',
    strategy: 'DCA + Trend',
    exchange: 'binance',
    pair: 'ETHUSDT',
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
    advancedSettings: {
      enableMovingAverage: true,
      movingAveragePeriod: 50,
      movingAverageType: 'EMA',
      useRSI: false,
      rsiOversold: 30,
      rsiOverbought: 70,
      useCandleStrength: false,
      minimumCandleBody: 50.0,
      useVolume: true,
      minimumVolumeRatio: 1.0,
      useAdaptiveRange: false,
      rangePeriod: 14,
      rangeMultiplier: 1.0,
      enableProtections: false,
      maxProtections: 3,
      timeBetweenProtections: 60,
      protectionDistances: [15, 30],
      protectionVolumes: [1, 2],
      dailyGoal: 200,
      dailyLossLimit: 100,
      emergencyDrawdown: 15,
      enableScalper: false,
      scalperInterval: 120,
      useCandleMaturity: false,
      maturitySeconds: 15,
      breakoutMinDistance: 10,
      stopLossUSD: 100,
      takeProfitUSD: 200,
      dailyBlocked: false,
      emergencyBlocked: false,
      protectionsOpened: 0,
    },
  },
  {
    id: 'crypto-3',
    name: 'Altcoin Grid Trader',
    description: 'Sistema de grid trading para altcoins com alta volatilidade',
    strategy: 'Grid Trading',
    exchange: 'binance',
    pair: 'ADAUSDT',
    status: 'stopped',
    profit: 0,
    trades: 0,
    winRate: 0,
    runtime: '0h 0m',
    amount: 2000,
    stopLoss: 8,
    takeProfit: 12,
    riskLevel: 'high',
    timeframe: '5m',
    indicators: ['Bollinger Bands', 'Volume', 'ATR'],
    maxDrawdown: 0,
    sharpeRatio: 0,
    createdAt: '2026-02-02T00:00:00Z',
    lastUpdated: '2026-02-02T00:00:00Z',
    isLive: false,
    apiConnected: true,
    advancedSettings: {
      enableMovingAverage: false,
      movingAveragePeriod: 20,
      movingAverageType: 'SMA',
      useRSI: false,
      rsiOversold: 30,
      rsiOverbought: 70,
      useCandleStrength: false,
      minimumCandleBody: 50.0,
      useVolume: true,
      minimumVolumeRatio: 2.0,
      useAdaptiveRange: true,
      rangePeriod: 20,
      rangeMultiplier: 2.0,
      enableProtections: true,
      maxProtections: 8,
      timeBetweenProtections: 20,
      protectionDistances: [5, 10, 15, 20],
      protectionVolumes: [0.5, 1, 1.5, 2],
      dailyGoal: 150,
      dailyLossLimit: 75,
      emergencyDrawdown: 8,
      enableScalper: true,
      scalperInterval: 30,
      useCandleMaturity: true,
      maturitySeconds: 5,
      breakoutMinDistance: 3,
      stopLossUSD: 75,
      takeProfitUSD: 150,
      dailyBlocked: false,
      emergencyBlocked: false,
      protectionsOpened: 0,
    },
  },
];

export default function CryptoRobots() {
  const navigate = useNavigate();
  const [selectedRobot, setSelectedRobot] = useState<Robot | null>(null);
  const [activeRobot, setActiveRobot] = useState<Robot | null>(null);
  const [showTrendGrid, setShowTrendGrid] = useState(false);
  const [showExchangeManager, setShowExchangeManager] = useState(false);
  const [showBrokerModal, setShowBrokerModal] = useState(false);

  // Show broker signup modal for new users
  useEffect(() => {
    const hasSeenBrokerModal = localStorage.getItem('crypto-broker-modal-seen');
    if (!hasSeenBrokerModal) {
      const timer = setTimeout(() => {
        setShowBrokerModal(true);
        localStorage.setItem('crypto-broker-modal-seen', 'true');
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleRobotSelect = (robot: Robot) => {
    if (robot.status === 'active') {
      setActiveRobot(robot);
    } else {
      setSelectedRobot(robot);
    }
  };

  const handleConfigSave = (config: any) => {
    console.log('Saving crypto robot config:', config);
    setSelectedRobot(null);
  };

  const totalProfit = cryptoRobots.reduce((sum, robot) => sum + robot.profit, 0);
  const activeRobots = cryptoRobots.filter(robot => robot.status === 'active').length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/robots')}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4" />
            Voltar
          </Button>
          
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-yellow-500 flex items-center justify-center">
                <Bitcoin className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground">Robôs de Criptomoedas</h1>
                <p className="text-sm text-muted-foreground">Trading automatizado para Bitcoin, Ethereum e Altcoins</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowExchangeManager(true)}
            className="flex items-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            Exchanges
          </Button>
          
          <Button
            size="sm"
            onClick={() => setSelectedRobot({} as Robot)}
            className="flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Novo Robô
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-success/20 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Lucro Total</p>
              <p className="text-2xl font-bold text-success">
                ${totalProfit.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Robôs Ativos</p>
              <p className="text-2xl font-bold text-foreground">{activeRobots}/{cryptoRobots.length}</p>
            </div>
          </div>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
              <Bitcoin className="w-5 h-5 text-orange-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Exchanges</p>
              <p className="text-2xl font-bold text-foreground">2</p>
            </div>
          </div>
        </div>
      </div>

      {/* Robots Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {cryptoRobots.map((robot) => (
          <RobotCard
            key={robot.id}
            robot={robot}
            onConfigure={() => setSelectedRobot(robot)}
            onToggle={() => handleRobotSelect(robot)}
            onExpand={() => setActiveRobot(robot)}
          />
        ))}
      </div>

      {/* Modals */}
      {selectedRobot && (
        <RobotConfigModal
          robot={selectedRobot.id ? selectedRobot : null}
          isOpen={!!selectedRobot}
          onClose={() => setSelectedRobot(null)}
          onSave={handleConfigSave}
          marketType="crypto"
        />
      )}

      {activeRobot && (
        <ActiveRobotModal
          robot={activeRobot}
          isOpen={!!activeRobot}
          onClose={() => setActiveRobot(null)}
          onUpdateRobot={(updatedRobot) => console.log('Robot updated:', updatedRobot)}
          onStop={() => setActiveRobot(null)}
        />
      )}

      {showExchangeManager && (
        <Dialog open={showExchangeManager} onOpenChange={setShowExchangeManager}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>Gerenciar Exchanges - Cripto</DialogTitle>
            </DialogHeader>
            <ExchangeManager marketType="crypto" />
          </DialogContent>
        </Dialog>
      )}

      {showTrendGrid && cryptoRobots[0] && (
        <Dialog open={showTrendGrid} onOpenChange={setShowTrendGrid}>
          <DialogContent className="max-w-4xl">
            <TrendGridDetails
              robot={cryptoRobots[0]}
              onToggle={() => {}}
              onConfigure={() => setSelectedRobot(cryptoRobots[0])}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* Broker Signup Modal */}
      <BrokerSignupModal
        open={showBrokerModal}
        onOpenChange={setShowBrokerModal}
      />
    </div>
  );
}