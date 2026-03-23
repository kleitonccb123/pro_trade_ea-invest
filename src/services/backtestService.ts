/**
 * Backtest Service
 * API calls for the backtesting engine
 */

import { apiGet, apiPost } from './apiClient';

// ── Types ────────────────────────────────────────────────────────────────────

export interface BacktestRunParams {
  strategy_id: string;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  short_period: number;
  long_period: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  maker_fee_pct?: number;
  taker_fee_pct?: number;
}

export interface BacktestTrade {
  entry_index: number;
  exit_index: number;
  side: string;
  entry_price: number;
  exit_price: number;
  size: number;
  pnl_usd: number;
  pnl_pct: number;
  fees_usd: number;
  exit_reason: string;
}

export interface BacktestMetrics {
  total_return_usd: number;
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  max_drawdown_duration_days: number;
  win_rate: number;
  avg_win_usd: number;
  avg_loss_usd: number;
  profit_factor: number;
  calmar_ratio: number;
  total_trades: number;
  avg_holding_period_hours: number;
  best_trade_usd: number;
  worst_trade_usd: number;
}

export interface EquityCurvePoint {
  timestamp: string;
  equity_usd: number;
}

export interface BacktestResult {
  backtest_id: string;
  strategy_id: string;
  version_id: string;
  config: {
    strategy_id: string;
    symbol: string;
    initial_capital_usd: number;
    start_ts: number;
    end_ts: number;
    parameters: Record<string, number>;
  };
  metrics: BacktestMetrics;
  trades: BacktestTrade[];
  equity_curve: EquityCurvePoint[];
  buy_hold_curve: EquityCurvePoint[];
  buy_hold_return_pct: number;
  passed: boolean;
  failure_reasons: string[];
  completed_at: string;
}

export interface BacktestSummary {
  backtest_id: string;
  strategy_id: string;
  symbol: string;
  initial_capital: number;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  buy_hold_return_pct: number;
  passed: boolean;
  completed_at: string;
}

// ── API calls ────────────────────────────────────────────────────────────────

export async function getAvailableSymbols(): Promise<string[]> {
  const data = await apiGet<{ symbols: string[] }>('/api/backtest/symbols');
  return data.symbols;
}

export async function runBacktest(params: BacktestRunParams): Promise<BacktestResult> {
  return apiPost<BacktestResult>('/api/backtest/run', params);
}

export async function getBacktestResult(backtestId: string): Promise<BacktestResult> {
  return apiGet<BacktestResult>(`/api/backtest/${backtestId}`);
}

export async function listStrategyBacktests(
  strategyId: string,
  limit = 10
): Promise<BacktestSummary[]> {
  const data = await apiGet<{ results: BacktestSummary[] }>(
    `/api/backtest/strategy/${strategyId}?limit=${limit}`
  );
  return data.results;
}

export const backtestService = {
  getAvailableSymbols,
  runBacktest,
  getBacktestResult,
  listStrategyBacktests,
};
