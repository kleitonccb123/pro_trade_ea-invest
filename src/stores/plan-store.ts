/**
 * plan-store.ts  —  Zustand store global do status de plano/assinatura
 *
 * Usado por qualquer componente via:
 *   const { plan, planDisplay, daysRemaining, isActive } = usePlanStore();
 *
 * Inicialização automática quando o usuário está autenticado (feita em AppLayout).
 */

import { create } from 'zustand';
import { authService } from '@/services/authService';

const API_BASE = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// ─── Mapeamento visual de plano ──────────────────────────────────────────────
export const PLAN_META: Record<
  string,
  { display: string; color: string; glow: string; icon: string }
> = {
  black:      { display: 'BLACK',  color: 'from-yellow-900/40 to-stone-900/60 border-yellow-600/50 text-yellow-300', glow: 'shadow-yellow-900/30', icon: '♠' },
  enterprise: { display: 'BLACK',  color: 'from-yellow-900/40 to-stone-900/60 border-yellow-600/50 text-yellow-300', glow: 'shadow-yellow-900/30', icon: '♠' },
  premium:    { display: 'QUANT',  color: 'from-emerald-900/40 to-teal-900/60 border-emerald-500/40 text-emerald-300',       glow: 'shadow-emerald-900/30',   icon: '◆' },
  pro_plus:   { display: 'PRO+',   color: 'from-violet-900/40 to-indigo-900/60 border-violet-500/40 text-violet-300', glow: 'shadow-violet-900/30', icon: '★' },
  pro:        { display: 'PRO',    color: 'from-purple-900/40 to-indigo-900/60 border-purple-500/40 text-purple-300', glow: 'shadow-purple-900/30', icon: '▲' },
  starter:    { display: 'START',  color: 'from-slate-800/40 to-slate-900/60 border-slate-600/40 text-slate-400',   glow: '',                     icon: '○' },
  free:       { display: 'FREE',   color: 'from-slate-800/40 to-slate-900/60 border-slate-600/40 text-slate-500',   glow: '',                     icon: '○' },
};

export function getPlanMeta(plan: string) {
  return PLAN_META[plan?.toLowerCase()] ?? PLAN_META['free'];
}

// ─── Tipos ───────────────────────────────────────────────────────────────────
export interface PlanStatus {
  plan: string;
  planDisplay: string;
  planIcon: string;
  planColor: string;
  isActive: boolean;
  isExpired: boolean;
  expiringSoon: boolean;
  daysRemaining: number | null;
  nextChargeDate: string | null;
  warningMessage: string | null;
  isLoading: boolean;
  lastFetched: number | null;
}

interface PlanStore extends PlanStatus {
  fetch: () => Promise<void>;
  clear: () => void;
}

const INITIAL: PlanStatus = {
  plan: 'free',
  planDisplay: 'FREE',
  planIcon: '○',
  planColor: PLAN_META['free'].color,
  isActive: false,
  isExpired: false,
  expiringSoon: false,
  daysRemaining: null,
  nextChargeDate: null,
  warningMessage: null,
  isLoading: false,
  lastFetched: null,
};

// Cache: evita re-fetch em menos de 3 minutos
const CACHE_MS = 3 * 60 * 1000;

// ─── Store ───────────────────────────────────────────────────────────────────
export const usePlanStore = create<PlanStore>((set, get) => ({
  ...INITIAL,

  fetch: async () => {
    const now = Date.now();
    const { lastFetched, isLoading } = get();
    if (isLoading) return;
    if (lastFetched && now - lastFetched < CACHE_MS) return;

    const token = authService.getAccessToken();
    if (!token) return;

    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/api/billing/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        set({ isLoading: false });
        return;
      }
      const data = await res.json();
      const meta = getPlanMeta(data.plan ?? 'free');
      set({
        plan:           data.plan ?? 'free',
        planDisplay:    data.plan_display ?? meta.display,
        planIcon:       meta.icon,
        planColor:      meta.color,
        isActive:       !!data.is_active,
        isExpired:      !!data.is_expired,
        expiringSoon:   !!data.expiring_soon,
        daysRemaining:  data.days_remaining ?? null,
        nextChargeDate: data.next_charge_date ?? null,
        warningMessage: data.warning_message ?? null,
        isLoading:      false,
        lastFetched:    now,
      });
    } catch {
      set({ isLoading: false });
    }
  },

  clear: () => set({ ...INITIAL }),
}));
