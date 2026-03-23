/**
 * Strategy Manager Service
 *
 * Camada de acesso à API do Strategy Manager SaaS (DOC-STRAT-01..10).
 * Todos os endpoints exigem Bearer token (injetado automaticamente pelo apiCall).
 *
 * Endpoints cobertos:
 *   POST /api/strategy-manager/{bot_id}/activate
 *   POST /api/strategy-manager/deactivate
 *   GET  /api/strategy-manager/state
 *   GET  /api/strategy-manager/active
 *   GET  /api/strategy-manager/switch-status
 *   GET  /api/strategy-manager/audit-log
 */

import { apiCall } from './apiClient';

// ─────────────────────────────────────────────────────────────────────────────
// Tipos de resposta (espelham o backend)
// ─────────────────────────────────────────────────────────────────────────────

export type SystemState =
  | 'IDLE'
  | 'ACTIVE'
  | 'TRANSITION_STATE'
  | 'CLOSING_POSITIONS'
  | 'SAFE_TO_SWITCH'
  | 'ACTIVATING_NEW_STRATEGY';

export type EAStatus =
  | 'READY'
  | 'RUNNING'
  | 'PAUSED'
  | 'SAFE_TO_SWITCH'
  | 'SHUTDOWN_COMPLETE'
  | 'SHUTDOWN_PENDING'
  | 'OFFLINE'
  | 'HANDSHAKE_TIMEOUT'
  | 'UNREACHABLE'
  | 'PARSE_ERROR'
  | 'READ_ERROR';

/** Estado completo do sistema retornado por GET /state */
export interface SystemStateResponse {
  system_state:      SystemState;
  active_strategy:   string | null;
  previous_strategy: string | null;
  last_switch:       string | null;
  uptime_seconds:    number | null;
}

/** Estratégia ativa retornada por GET /active */
export interface ActiveStrategyResponse {
  active_strategy: string | null;
  system_state:    SystemState;
  last_switch:     string | null;
  uptime_seconds:  number | null;
}

/** Resultado de ativação/desativação */
export interface ActivationResponse {
  success:       boolean;
  strategy_id:   string | null;
  status:        string;
  message:       string;
  detail:        Record<string, unknown> | null;
  activated_at:  string | null;
}

/** Status de troca em progresso */
export interface SwitchStatusResponse {
  in_transition:     boolean;
  current_state:     SystemState;
  active_strategy:   string | null;
  previous_strategy: string | null;
}

/** Entrada do audit log */
export interface AuditLogEntry {
  timestamp: string | null;
  level:     string | null;
  event:     string | null;
  data:      Record<string, unknown> | null;
}

export interface AuditLogResponse {
  entries: AuditLogEntry[];
  total:   number;
}

/** Telemetria do EA lida do state.json via backend */
export interface EATelemetry {
  strategy_id:         string;
  magic_number:        number;
  status:              EAStatus;
  manager_state_local: string;
  permitted:           boolean;
  kill_switch_active:  boolean;
  open_positions:      number;
  open_orders:         number;
  unrealized_pnl:      number;
  realized_pnl_today?: number;
  floating_drawdown?:  number;
  max_drawdown_today?: number;
  last_trade_open?:    string;
  last_trade_close?:   string;
  account_balance:     number;
  account_equity:      number;
  heartbeat:           string;
  uptime_seconds:      number;
}

/** Estratégia registrada no STRATEGY_REGISTRY do backend */
export interface StrategyRegistryEntry {
  id:                     string;
  magic_number:           number;
  display_name:           string;
  version:                string;
  timeframe:              string;
  min_switch_interval_s:  number;
  safe_shutdown_timeout_s: number;
  handshake_timeout_s:    number;
  description:            string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Registry local (espelha STRATEGY_REGISTRY do backend + novos EAs)
// ─────────────────────────────────────────────────────────────────────────────

export const STRATEGY_REGISTRY: StrategyRegistryEntry[] = [
  {
    id:                     'pricepro_money_v1',
    magic_number:           20240001,
    display_name:           'PRICEPRO MONEY',
    version:                '1.0',
    timeframe:              'M15',
    min_switch_interval_s:  60,
    safe_shutdown_timeout_s: 120,
    handshake_timeout_s:    30,
    description:            'Clássico M15 — EMA 55 + RSI 9 retração (níveis 33/66). Balança risco/recompensa equilibrado.',
  },
  {
    id:                     'pricepro_h1_v1',
    magic_number:           20260001,
    display_name:           'PRICEPRO H1 – Trend Rider',
    version:                '1.0',
    timeframe:              'H1',
    min_switch_interval_s:  120,
    safe_shutdown_timeout_s: 180,
    handshake_timeout_s:    30,
    description:            'Tendência forte H1 — EMA 21 + RSI 14 impulso. Candle duplo confirmado. TP $25 / SL $15.',
  },
  {
    id:                     'pricepro_m30_v1',
    magic_number:           20260002,
    display_name:           'PRICEPRO M30 – Swing Balance',
    version:                '1.0',
    timeframe:              'M30',
    min_switch_interval_s:  90,
    safe_shutdown_timeout_s: 150,
    handshake_timeout_s:    30,
    description:            'Swing com reversão confirmada M30 — EMA 34 + RSI 9 retração + padrão de 2 candles. R:R 1.5.',
  },
  {
    id:                     'pricepro_m5_v1',
    magic_number:           20260004,
    display_name:           'PRICEPRO M5 – Scalper Pro',
    version:                '1.0',
    timeframe:              'M5',
    min_switch_interval_s:  30,
    safe_shutdown_timeout_s: 60,
    handshake_timeout_s:    30,
    description:            'Scalping alta frequência M5 — EMA dupla (20/50) + RSI 7. Spread filtrado. Máx 10 trades/dia.',
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Funções de API
// ─────────────────────────────────────────────────────────────────────────────

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/** GET /api/strategy-manager/state */
export async function getSystemState(): Promise<SystemStateResponse> {
  const res = await apiCall('/api/strategy-manager/state');
  return json<SystemStateResponse>(res);
}

/** GET /api/strategy-manager/active */
export async function getActiveStrategy(): Promise<ActiveStrategyResponse> {
  const res = await apiCall('/api/strategy-manager/active');
  return json<ActiveStrategyResponse>(res);
}

/** GET /api/strategy-manager/switch-status */
export async function getSwitchStatus(): Promise<SwitchStatusResponse> {
  const res = await apiCall('/api/strategy-manager/switch-status');
  return json<SwitchStatusResponse>(res);
}

/** POST /api/strategy-manager/{bot_id}/activate */
export async function activateStrategy(botId: string, note?: string): Promise<ActivationResponse> {
  const res = await apiCall(`/api/strategy-manager/${botId}/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note: note ?? null }),
  });
  return json<ActivationResponse>(res);
}

/** POST /api/strategy-manager/deactivate */
export async function deactivateStrategy(): Promise<ActivationResponse> {
  const res = await apiCall('/api/strategy-manager/deactivate', { method: 'POST' });
  return json<ActivationResponse>(res);
}

/** GET /api/strategy-manager/audit-log */
export async function getAuditLog(limit = 50): Promise<AuditLogResponse> {
  const res = await apiCall(`/api/strategy-manager/audit-log?limit=${limit}`);
  return json<AuditLogResponse>(res);
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers de UI
// ─────────────────────────────────────────────────────────────────────────────

export function stateColor(state: SystemState | string): string {
  const map: Record<string, string> = {
    IDLE:                    'text-slate-400',
    ACTIVE:                  'text-green-400',
    TRANSITION_STATE:        'text-yellow-400',
    CLOSING_POSITIONS:       'text-orange-400',
    SAFE_TO_SWITCH:          'text-blue-400',
    ACTIVATING_NEW_STRATEGY: 'text-purple-400',
  };
  return map[state] ?? 'text-slate-400';
}

export function stateLabel(state: SystemState | string): string {
  const map: Record<string, string> = {
    IDLE:                    'Ocioso',
    ACTIVE:                  'Ativo',
    TRANSITION_STATE:        'Em Transição',
    CLOSING_POSITIONS:       'Fechando Posições',
    SAFE_TO_SWITCH:          'Pronto p/ Troca',
    ACTIVATING_NEW_STRATEGY: 'Ativando Estratégia',
  };
  return map[state] ?? state;
}

export function eaStatusColor(status: EAStatus | string): string {
  const map: Record<string, string> = {
    READY:            'text-blue-400',
    RUNNING:          'text-green-400',
    PAUSED:           'text-yellow-400',
    SAFE_TO_SWITCH:   'text-emerald-400',
    SHUTDOWN_COMPLETE:'text-slate-400',
    SHUTDOWN_PENDING: 'text-orange-400',
    OFFLINE:          'text-slate-500',
    HANDSHAKE_TIMEOUT:'text-red-500',
    UNREACHABLE:      'text-red-400',
    PARSE_ERROR:      'text-red-400',
    READ_ERROR:       'text-red-400',
  };
  return map[status] ?? 'text-slate-400';
}

export function eaStatusLabel(status: EAStatus | string): string {
  const map: Record<string, string> = {
    READY:             'Pronto',
    RUNNING:           'Rodando',
    PAUSED:            'Pausado',
    SAFE_TO_SWITCH:    'Ok p/ Trocar',
    SHUTDOWN_COMPLETE: 'Desligado',
    SHUTDOWN_PENDING:  'Aguardando Fechamento',
    OFFLINE:           'Offline',
    HANDSHAKE_TIMEOUT: 'Timeout Handshake',
    UNREACHABLE:       'EA Inacessível',
    PARSE_ERROR:       'Erro de Leitura',
    READ_ERROR:        'Erro de Leitura',
  };
  return map[status] ?? status;
}

export function formatUptime(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function timeframeColor(tf: string): string {
  const map: Record<string, string> = {
    M5:  'bg-purple-600/20 text-purple-300 border-purple-500/30',
    M15: 'bg-blue-600/20 text-blue-300 border-blue-500/30',
    M30: 'bg-emerald-600/20 text-emerald-300 border-emerald-500/30',
    H1:  'bg-green-600/20 text-green-300 border-green-500/30',
  };
  return map[tf] ?? 'bg-slate-600/20 text-slate-300 border-slate-500/30';
}
