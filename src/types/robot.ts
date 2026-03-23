/**
 * Tipos e interfaces relacionados aos robôs de trading
 */

export interface Robot {
  id: string;
  name: string;
  description: string;
  strategy: string; // 'Scalping' | 'Grid Trading' | 'DCA' | 'Trend Following' | 'Arbitrage' | 'Momentum' | etc.
  exchange: string; // ID da exchange (ex: 'binance', 'okx', 'bybit')
  pair: string; // Par de trading (ex: 'BTC/USDT')
  status: 'active' | 'paused' | 'stopped';
  profit: number; // Percentual de lucro/prejuízo
  trades: number; // Total de trades executados
  winRate: number; // Taxa de acerto em %
  runtime: string; // Tempo de execução (ex: '15d 8h')
  amount: number; // Valor investido em USD
  stopLoss: number; // Stop loss em %
  takeProfit: number; // Take profit em %
  riskLevel: 'low' | 'medium' | 'high';
  timeframe: string; // Timeframe das operações (1m, 5m, 15m, 1h, etc.)
  indicators: string[]; // Lista de indicadores técnicos utilizados
  maxDrawdown: number; // Drawdown máximo em %
  sharpeRatio: number; // Índice Sharpe
  createdAt: string; // Data de criação (ISO string)
  lastUpdated: string; // Última atualização (ISO string)
  isLive: boolean; // Se está conectado ao trading real
  apiConnected: boolean; // Se a API da Binance está conectada
  advancedSettings?: TrendGridSettings; // Configurações específicas do TrendGridProtector
}

// Interface específica para o TrendGridProtector
export interface TrendGridSettings {
  // Filtros de Entrada
  enableMovingAverage: boolean;
  movingAveragePeriod: number;
  movingAverageType: 'SMA' | 'EMA' | 'WMA' | 'SMMA';
  useRSI: boolean;
  rsiOversold: number;
  rsiOverbought: number;
  useCandleStrength: boolean;
  minimumCandleBody: number; // %
  useVolume: boolean;
  minimumVolumeRatio: number;
  useAdaptiveRange: boolean;
  rangePeriod: number;
  rangeMultiplier: number;
  
  // Sistema de Grid/Proteções
  enableProtections: boolean;
  maxProtections: number;
  timeBetweenProtections: number; // segundos
  protectionDistances: number[]; // pontos
  protectionVolumes: number[]; // volumes
  
  // Gestão Financeira
  dailyGoal: number; // USD
  dailyLossLimit: number; // USD
  emergencyDrawdown: number; // %
  
  // Scalper
  enableScalper: boolean;
  scalperInterval: number; // segundos
  
  // Filtros Avançados
  useCandleMaturity: boolean;
  maturitySeconds: number;
  breakoutMinDistance: number; // pontos
  
  // SL/TP em USD
  stopLossUSD: number;
  takeProfitUSD: number;
  
  // Estados de Controle
  dailyBlocked: boolean;
  emergencyBlocked: boolean;
  protectionsOpened: number;
}

export interface RobotConfiguration {
  name: string;
  description: string;
  strategy: string;
  pair: string;
  amount: number;
  stopLoss: number;
  takeProfit: number;
  riskLevel: 'low' | 'medium' | 'high';
  timeframe: string;
  indicators: string[];
  binanceApiKey?: string;
  binanceApiSecret?: string;
}

export interface RobotPerformance {
  robotId: string;
  currentBalance: number;
  totalPnL: number;
  dailyPnL: number;
  weeklyPnL: number;
  monthlyPnL: number;
  totalTrades: number;
  profitableTrades: number;
  lossingTrades: number;
  avgTradeProfit: number;
  avgTradeLoss: number;
  largestWin: number;
  largestLoss: number;
  consecutiveWins: number;
  consecutiveLosses: number;
  maxDrawdown: number;
  currentDrawdown: number;
  sharpeRatio: number;
  sortinoRatio: number;
  calmarRatio: number;
  lastTradeAt?: string;
  totalFees: number;
}

export interface TradingSignal {
  robotId: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  signal: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL';
  confidence: number; // 0-100
  price: number;
  timestamp: string;
  indicators: Record<string, number>;
  reason: string;
}

export interface RobotLog {
  id: string;
  robotId: string;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
  message: string;
  data?: Record<string, any>;
}

// Enums para facilitar o uso
export enum RobotStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  STOPPED = 'stopped'
}

export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high'
}

export enum TradingStrategy {
  SCALPING = 'Scalping',
  GRID_TRADING = 'Grid Trading',
  DCA = 'DCA (Dollar Cost Average)',
  TREND_FOLLOWING = 'Trend Following',
  ARBITRAGE = 'Arbitrage',
  MOMENTUM = 'Momentum',
  MEAN_REVERSION = 'Mean Reversion',
  BREAKOUT = 'Breakout',
  SWING_TRADING = 'Swing Trading',
  ALGORITHMIC = 'Algorithmic'
}

export enum Timeframe {
  ONE_MINUTE = '1m',
  FIVE_MINUTES = '5m',
  FIFTEEN_MINUTES = '15m',
  THIRTY_MINUTES = '30m',
  ONE_HOUR = '1h',
  FOUR_HOURS = '4h',
  ONE_DAY = '1d',
  ONE_WEEK = '1w'
}

// Indicadores técnicos disponíveis
export enum TechnicalIndicator {
  RSI = 'RSI',
  MACD = 'MACD',
  BOLLINGER_BANDS = 'Bollinger Bands',
  SMA = 'SMA',
  EMA = 'EMA',
  STOCH = 'Stochastic',
  WILLIAMS_R = 'Williams %R',
  ADX = 'ADX',
  CCI = 'CCI',
  ROC = 'ROC',
  VOLUME = 'Volume',
  VOLUME_PROFILE = 'Volume Profile',
  SUPPORT_RESISTANCE = 'Support/Resistance',
  FIBONACCI = 'Fibonacci',
  ICHIMOKU = 'Ichimoku',
  PRICE_SPREAD = 'Price Spread',
  LIQUIDITY = 'Liquidity'
}