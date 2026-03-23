/**
 * api.types.ts — tipos de resposta da API
 *
 * Tipos para requests/responses da API backend e KuCoin.
 * Baseados no schema atual do backend FastAPI.
 */

// ── Wrapper de resposta padrão do backend ──
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ── Erros ──
export interface ApiError {
  detail: string;
  code?: string;
  field?: string;
}

// ── Auth ──
export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: 'bearer';
  expires_in?: number;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
  avatar?: string;
  plan: 'free' | 'starter' | 'pro' | 'enterprise';
  is_admin: boolean;
  created_at: string;
  kucoin_configured: boolean;
}

// ── KuCoin ──
export interface KuCoinTicker {
  symbol: string;
  last: string;
  changeRate: string;
  changePrice: string;
  high: string;
  low: string;
  vol: string;
  volValue: string;
  buy: string;
  sell: string;
  time: number;
}

export interface KuCoinBalance {
  currency: string;
  balance: string;
  available: string;
  holds: string;
}

// ── Portfolio ──
export interface PortfolioSummary {
  total_value_usdt: number;
  daily_pnl: number;
  daily_pnl_percent: number;
  total_pnl: number;
  total_pnl_percent: number;
  active_robots: number;
  total_robots: number;
  open_positions: number;
  win_rate: number;
}

// ── Trade / Operação ──
export interface Trade {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  price: number;
  quantity: number;
  value: number;
  fee: number;
  pnl?: number;
  pnl_percent?: number;
  status: 'open' | 'closed' | 'cancelled';
  opened_at: string;
  closed_at?: string;
  robot_id?: string;
  strategy?: string;
}

// ── WebSocket ──
export interface WsMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: number;
}
