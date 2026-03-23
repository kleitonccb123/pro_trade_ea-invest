/**
 * use-leaderboard.ts — React Query hook for the real trading leaderboard (DOC_06).
 *
 * Fetches from GET /api/gamification/leaderboard/trading
 * with automatic 5-minute refresh and auth token injection.
 *
 * Usage:
 *   const { data, isLoading, error } = useLeaderboard(30);
 *   const { data: myPos }            = useMyTradingPosition();
 */

import { useQuery } from '@tanstack/react-query';
import { authService } from '@/services/authService';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface TradingLeaderboardEntry {
  rank_position:   number;
  display_name:    string;
  avatar_url?:     string | null;
  robot_name?:     string | null;
  pair?:           string | null;
  roi_pct:         number;
  win_rate:        number;
  total_pnl_usdt:  number;
  profit_factor:   number;
  total_trades:    number;
  total_fees_usdt: number;
  composite_score: number;
}

export interface TradingLeaderboardResponse {
  entries:     TradingLeaderboardEntry[];
  total:       number;
  period_days: number;
  computed_at: string | null;
  user_rank:   TradingLeaderboardEntry | null;
  message?:    string;
}

export interface MyTradingPosition {
  ranked:          boolean;
  message?:        string;
  rank_position?:  number;
  display_name?:   string;
  roi_pct?:        number;
  win_rate?:       number;
  total_pnl_usdt?: number;
  profit_factor?:  number;
  total_trades?:   number;
  composite_score?: number;
  pair?:           string | null;
  robot_name?:     string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const API_BASE_URL   = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const STALE_TIME_MS  = 5 * 60 * 1000;   // 5 min — matches Redis TTL
const REFETCH_MS     = 5 * 60 * 1000;   // auto-refresh every 5 min

// ── Fetcher helper ────────────────────────────────────────────────────────────

async function fetchWithAuth(url: string): Promise<Response> {
  const token = authService.getAccessToken();
  const res   = await fetch(url, {
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`[${res.status}] ${msg}`);
  }
  return res;
}

// ── useLeaderboard ────────────────────────────────────────────────────────────

/**
 * Fetch the real trading leaderboard.
 *
 * @param periodDays - Ranking window in days (7–90). Default: 30.
 * @param limit      - Max entries to display (10–100). Default: 50.
 */
export function useLeaderboard(
  periodDays: number = 30,
  limit: number = 50,
) {
  const token = authService.getAccessToken();

  return useQuery<TradingLeaderboardResponse, Error>({
    queryKey:       ['leaderboard', 'trading', periodDays, limit],
    queryFn:        async () => {
      const res  = await fetchWithAuth(
        `${API_BASE_URL}/api/gamification/leaderboard/trading?period=${periodDays}&limit=${limit}`,
      );
      return res.json() as Promise<TradingLeaderboardResponse>;
    },
    staleTime:      STALE_TIME_MS,
    refetchInterval: REFETCH_MS,
    enabled:        !!token,
    retry:          2,
  });
}

// ── useMyTradingPosition ──────────────────────────────────────────────────────

/**
 * Fetch only the authenticated user's position in the trading ranking.
 */
export function useMyTradingPosition() {
  const token = authService.getAccessToken();

  return useQuery<MyTradingPosition, Error>({
    queryKey:       ['leaderboard', 'my-position'],
    queryFn:        async () => {
      const res = await fetchWithAuth(
        `${API_BASE_URL}/api/gamification/leaderboard/my-position`,
      );
      return res.json() as Promise<MyTradingPosition>;
    },
    staleTime:      STALE_TIME_MS,
    refetchInterval: REFETCH_MS,
    enabled:        !!token,
    retry:          2,
  });
}
