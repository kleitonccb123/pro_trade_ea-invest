/**
 * EA Monitor Service — MetaTrader MT4/MT5 Integration API Client
 *
 * Endpoints:
 *   POST /ea/connect                    → Register MT4/MT5 account
 *   GET  /ea/accounts                   → List user's connected accounts
 *   GET  /ea/{account_id}/positions     → Live positions snapshot
 */

import { apiCall } from './apiClient';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface EAConnectRequest {
  account_id: string;   // MT4/MT5 account number (digits only)
  account_name?: string;
  server?: string;
  broker?: string;
}

export interface EAConnectResponse {
  account_id: string;
  api_key: string;
  message: string;
}

export interface EAAccountInfo {
  account_id: string;
  account_name: string;
  server: string;
  broker: string;
  connected: boolean;
  last_seen: string | null;
  balance: number;
  equity: number;
  positions_count: number;
}

export interface EAPosition {
  id: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  volume: number;
  open_price: number;
  current_price: number;
  sl: number;
  tp: number;
  profit: number;
  magic: number;
  comment: string;
  open_time: string;
}

export interface EAPositionsResponse {
  account_id: string;
  last_seen: string | null;
  balance: number;
  equity: number;
  positions: EAPosition[];
}

/** Telemetry payload received via WebSocket ea_update messages */
export interface EALiveTelemetry {
  strategy_id: string;
  magic_number: number;
  status: string;
  manager_state_local: string;
  permitted: boolean;
  kill_switch_active: boolean;
  open_positions: number;
  open_orders: number;
  unrealized_pnl: number;
  realized_pnl_today: number;
  floating_drawdown: number;
  max_drawdown_today: number;
  account_balance: number;
  account_equity: number;
  heartbeat: string;
  uptime_seconds: number;
  last_trade_open: string | null;
  last_trade_close: string | null;
}

/** Full ea_update WebSocket message */
export interface EAUpdateMessage {
  type: 'ea_update' | 'ea_snapshot' | 'ea_waiting' | 'ping' | 'pong';
  account_id?: string;
  timestamp?: string;
  telemetry?: EALiveTelemetry;
  positions?: EAPosition[];
  message?: string;
}

// ─── API functions ────────────────────────────────────────────────────────────

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/** POST /ea/connect — Register a MT4/MT5 account */
export async function connectEAAccount(req: EAConnectRequest): Promise<EAConnectResponse> {
  const res = await apiCall('/ea/connect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return json<EAConnectResponse>(res);
}

/** GET /ea/accounts — List this user's connected accounts */
export async function listEAAccounts(): Promise<EAAccountInfo[]> {
  const res = await apiCall('/ea/accounts');
  return json<EAAccountInfo[]>(res);
}

/** GET /ea/{account_id}/positions — Latest position snapshot */
export async function getEAPositions(accountId: string): Promise<EAPositionsResponse> {
  const res = await apiCall(`/ea/${accountId}/positions`);
  return json<EAPositionsResponse>(res);
}
