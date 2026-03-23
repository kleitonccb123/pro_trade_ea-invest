// Tipos genéricos para suporte a múltiplas exchanges
export interface Exchange {
  id: string;
  name: string;
  displayName: string;
  logo: string;
  supportedFeatures: ExchangeFeature[];
  apiEndpoints: {
    rest: string;
    websocket: string;
  };
  fees: {
    maker: number;
    taker: number;
  };
  pairs: string[];
  isActive: boolean;
  type: 'crypto';
}

export type ExchangeFeature = 
  | 'spot_trading'
  | 'futures_trading' 
  | 'margin_trading'
  | 'options_trading'
  | 'staking'
  | 'lending'
  | 'nft'
  | 'p2p'
  | 'api_trading'
  | 'websocket'
  | 'advanced_orders';

export interface ExchangeCredentials {
  exchangeId: string;
  apiKey: string;
  apiSecret: string;
  passphrase?: string; // Para OKX, KuCoin, etc.
  sandbox?: boolean;
}

export interface UniversalOrder {
  id: string;
  exchangeOrderId: string;
  exchange: string;
  symbol: string;
  side: 'buy' | 'sell';
  type: 'market' | 'limit' | 'stop' | 'stop_limit';
  amount: number;
  price?: number;
  stopPrice?: number;
  status: 'pending' | 'open' | 'filled' | 'cancelled' | 'rejected';
  filled: number;
  remaining: number;
  cost: number;
  fee: number;
  timestamp: string;
  lastTradeTimestamp?: string;
}

export interface UniversalBalance {
  exchange: string;
  asset: string;
  free: number;
  locked: number;
  total: number;
  usdValue?: number;
}

export interface UniversalTicker {
  exchange: string;
  symbol: string;
  last: number;
  bid: number;
  ask: number;
  change: number;
  changePercent: number;
  volume: number;
  high: number;
  low: number;
  timestamp: string;
}

export interface ExchangeConnection {
  exchange: Exchange;
  credentials: ExchangeCredentials;
  isConnected: boolean;
  lastPing?: string;
  error?: string;
}

// Configurações específicas por exchange
export interface ExchangeConfig {
  binance: {
    testnet: boolean;
    recvWindow: number;
  };
  okx: {
    demo: boolean;
    passphrase: string;
  };
  bybit: {
    testnet: boolean;
    recv_window: number;
  };
  kucoin: {
    sandbox: boolean;
    passphrase: string;
  };
  coinbase: {
    sandbox: boolean;
  };
  kraken: {
    otp?: string;
  };
}