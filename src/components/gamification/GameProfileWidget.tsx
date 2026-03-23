/**
 * GameProfileWidget — Painel de perfil gamificado (Design System v2)
 *
 * Layout moderno alinhado com o design-system do SaaS.
 * Dados 100% backend:
 *  - TradePoints, Level, XP, Streak, Robôs, Lucro Vitalício
 *  - Plano ativo (via plan-store)
 *  - Status de conexão com backend (/api/health)
 *
 * Sem Baú Diário — removido por decisão de produto.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bot,
  ChevronDown,
  Flame,
  Loader2,
  Signal,
  SignalZero,
  Sparkles,
  Star,
  TrendingUp,
  Trophy,
  Zap,
} from 'lucide-react';
import { NumberAnimator } from './NumberAnimator';
import { useGamification, useGamificationProgress } from '@/hooks/use-gamification';
import { useAuthStore } from '@/context/AuthContext';
import { usePlanStore } from '@/stores/plan-store';

/* ── Limite de robôs por plano (espelha plan_config.py) ───────────────────── */
const PLAN_MAX_ROBOTS: Record<string, number> = {
  enterprise: 999, black: 999, superuser: 999,
  quant: 15, pro_plus: 8, pro: 5,
  starter: 3, free: 0,
};

/* ── Cores por plano ──────────────────────────────────────────────────────── */
const PLAN_ACCENT: Record<string, { ring: string; text: string; bg: string; glow: string }> = {
  black:      { ring: 'ring-amber-500/40',  text: 'text-amber-400',  bg: 'bg-amber-500/10',  glow: 'shadow-[0_0_20px_-6px_rgba(245,158,11,0.35)]' },
  enterprise: { ring: 'ring-amber-500/40',  text: 'text-amber-400',  bg: 'bg-amber-500/10',  glow: 'shadow-[0_0_20px_-6px_rgba(245,158,11,0.35)]' },
  superuser:  { ring: 'ring-red-500/40',    text: 'text-red-400',    bg: 'bg-red-500/10',    glow: 'shadow-[0_0_20px_-6px_rgba(239,68,68,0.35)]' },
  quant:      { ring: 'ring-emerald-500/40',   text: 'text-emerald-400',   bg: 'bg-emerald-500/10',   glow: 'shadow-[0_0_20px_-6px_rgba(35,200,130,0.30)]' },
  pro_plus:   { ring: 'ring-violet-500/40', text: 'text-violet-400', bg: 'bg-violet-500/10', glow: 'shadow-[0_0_20px_-6px_rgba(139,92,246,0.30)]' },
  pro:        { ring: 'ring-purple-500/40', text: 'text-purple-400', bg: 'bg-purple-500/10', glow: 'shadow-[0_0_20px_-6px_rgba(168,85,247,0.30)]' },
};
const DEFAULT_ACCENT = { ring: 'ring-brand-primary/30', text: 'text-brand-primary', bg: 'bg-brand-primary/10', glow: '' };

/* ── Backend health check (ping a cada 30 s) ─────────────────────────────── */
function useBackendStatus(): boolean | null {
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const res = await fetch('/api/health', { method: 'GET', signal: AbortSignal.timeout(4000) });
        if (mounted) setOnline(res.ok);
      } catch {
        if (mounted) setOnline(false);
      }
    };
    check();
    const id = setInterval(check, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);
  return online;
}

/* ══════════════════════════════════════════════════════════════════════════════
   Component
   ══════════════════════════════════════════════════════════════════════════ */
export const GameProfileWidget: React.FC = () => {
  const { profile, loading, error } = useGamification();
  const progress = useGamificationProgress(profile);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isHydrated = useAuthStore((s) => s.isHydrated);
  const { plan, planDisplay, daysRemaining, isActive } = usePlanStore();
  const backendOnline = useBackendStatus();
  const [expanded, setExpanded] = useState(false);

  // Plano
  const maxRobots = PLAN_MAX_ROBOTS[plan ?? 'starter'] ?? 20;
  const robotsLabel = maxRobots >= 999 ? '∞' : String(maxRobots);
  const isPaid = plan && plan !== 'starter' && plan !== 'free';
  const accent = useMemo(() => PLAN_ACCENT[plan ?? ''] ?? DEFAULT_ACCENT, [plan]);

  /* ── Loading skeleton ─────────────────────────────────────────────────── */
  if (!isHydrated || loading || (isAuthenticated && !profile && !error)) {
    return (
      <div className="w-full rounded-xl bg-surface-raised border border-edge-subtle p-8 flex items-center justify-center gap-3">
        <Loader2 className="w-5 h-5 text-brand-primary animate-spin" />
        <span className="text-sm text-content-secondary">Carregando perfil…</span>
      </div>
    );
  }

  /* ── Not authenticated ────────────────────────────────────────────────── */
  if (!isAuthenticated) {
    return (
      <div className="w-full rounded-xl bg-surface-raised border border-edge-subtle p-5 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-surface-hover border border-edge-subtle flex items-center justify-center">
          <Trophy className="w-5 h-5 text-content-muted" />
        </div>
        <div>
          <p className="text-sm font-semibold text-content-secondary">Arena de Lucros</p>
          <p className="text-xs text-content-muted">Faça login para acessar seu perfil</p>
        </div>
      </div>
    );
  }

  /* ── Error / no profile ───────────────────────────────────────────────── */
  if (error || !profile) {
    return (
      <div className="w-full rounded-xl bg-surface-raised border border-edge-subtle p-5 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-surface-hover border border-edge-subtle flex items-center justify-center">
          <SignalZero className="w-5 h-5 text-semantic-loss" />
        </div>
        <div>
          <p className="text-sm font-semibold text-content-secondary">Arena de Lucros</p>
          <p className="text-xs text-semantic-loss/70">Falha ao carregar perfil</p>
        </div>
      </div>
    );
  }

  /* ── Render ───────────────────────────────────────────────────────────── */
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="w-full"
    >
      <div
        className={
          'relative rounded-xl bg-surface-raised border border-edge-subtle overflow-hidden ' +
          'ring-1 ' + accent.ring + ' ' + accent.glow + ' ' +
          'transition-shadow duration-300 hover:shadow-raised'
        }
      >
        {/* ── Top accent line ───────────────────────────────────────────── */}
        <div className="h-[2px] w-full bg-gradient-to-r from-transparent via-brand-primary/60 to-transparent" />

        <div className="p-5 space-y-5">

          {/* ═══════ Header Row ═══════════════════════════════════════════ */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Icon */}
              <div className={'w-10 h-10 rounded-lg flex items-center justify-center border border-edge-subtle ' + accent.bg}>
                <Trophy className={'w-5 h-5 ' + accent.text} />
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-display font-bold text-content-primary tracking-tight">
                    Arena de Lucros
                  </h3>
                  {isPaid && (
                    <span className={'inline-flex items-center gap-1 text-2xs font-bold px-2 py-0.5 rounded-full border ' + accent.bg + ' ' + accent.text + ' border-current/20 tracking-widest uppercase'}>
                      {planDisplay}
                    </span>
                  )}
                </div>
                <p className="text-2xs text-content-muted mt-0.5">
                  Nível {progress.level} · {profile.trade_points.toLocaleString('pt-BR')} pts
                </p>
              </div>
            </div>

            {/* Right side: backend status + expand */}
            <div className="flex items-center gap-3">
              {backendOnline !== null && (
                <div className="flex items-center gap-1.5" title={backendOnline ? 'API conectada' : 'API offline'}>
                  {backendOnline ? (
                    <Signal className="w-3.5 h-3.5 text-semantic-profit" />
                  ) : (
                    <SignalZero className="w-3.5 h-3.5 text-semantic-loss" />
                  )}
                  <span className={'text-2xs font-medium ' + (backendOnline ? 'text-semantic-profit' : 'text-semantic-loss')}>
                    {backendOnline ? 'Online' : 'Offline'}
                  </span>
                </div>
              )}

              <button
                onClick={() => setExpanded(!expanded)}
                className="p-1.5 rounded-md hover:bg-surface-hover text-content-muted hover:text-content-secondary transition-colors"
                aria-label={expanded ? 'Recolher' : 'Expandir'}
              >
                <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.25 }}>
                  <ChevronDown className="w-4 h-4" />
                </motion.div>
              </button>
            </div>
          </div>

          {/* ═══════ XP Progress Bar ═════════════════════════════════════ */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-2xs font-medium text-content-muted uppercase tracking-wider">Experiência</span>
              <span className="text-2xs font-mono text-content-muted">
                {profile.current_xp} / {profile.xp_for_next_level} XP
              </span>
            </div>
            <div className="relative h-1.5 rounded-full bg-surface-hover overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progress.xpPercent}%` }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
                className="h-full rounded-full bg-gradient-to-r from-brand-primary to-brand-alt"
              />
            </div>
            <p className="text-2xs text-content-muted">
              {Math.round(progress.xpPercent)}% até Nível {progress.level + 1}
            </p>
          </div>

          {/* ═══════ Stats Grid ══════════════════════════════════════════ */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* Points */}
            <StatCard icon={<Sparkles className="w-4 h-4" />} label="Trade Points" iconColor="text-amber-400" borderColor="border-amber-500/20">
              <NumberAnimator value={profile.trade_points} glowColor="gold" decimals={0} />
            </StatCard>

            {/* Level */}
            <StatCard icon={<Star className="w-4 h-4" />} label="Nível" iconColor="text-violet-400" borderColor="border-violet-500/20">
              <span>{progress.level}</span>
            </StatCard>

            {/* Robots */}
            <StatCard icon={<Bot className="w-4 h-4" />} label="Robôs" iconColor="text-brand-primary" borderColor="border-brand-primary/20">
              <span>
                {progress.botsUnlocked}
                <span className="text-content-muted font-normal text-sm">/{robotsLabel}</span>
              </span>
            </StatCard>

            {/* Streak */}
            <StatCard icon={<Flame className="w-4 h-4" />} label="Streak" iconColor="text-orange-400" borderColor="border-orange-500/20">
              <span className="flex items-baseline gap-1">
                {progress.streakDays}
                {progress.streakDays >= 3 && (
                  <Zap className="w-3 h-3 text-orange-400 inline-block" />
                )}
              </span>
            </StatCard>
          </div>

          {/* ═══════ Expanded: extra info ════════════════════════════════ */}
          <AnimatePresence>
            {expanded && (
              <motion.div
                key="expanded"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25, ease: 'easeInOut' }}
                className="overflow-hidden"
              >
                <div className="pt-4 border-t border-edge-subtle space-y-3">
                  {/* Lifetime profit */}
                  <div className="flex items-center justify-between p-3 rounded-lg bg-surface-hover/50 border border-edge-subtle">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-semantic-profit" />
                      <span className="text-xs font-medium text-content-secondary">Lucro Vitalício</span>
                    </div>
                    <span className="text-lg font-display font-bold text-semantic-profit">
                      $ <NumberAnimator value={profile.lifetime_profit} decimals={2} glowColor="emerald" />
                    </span>
                  </div>

                  {/* Plan info row */}
                  {isPaid && (
                    <div className="flex items-center justify-between p-3 rounded-lg bg-surface-hover/50 border border-edge-subtle">
                      <div className="flex items-center gap-2">
                        <div className={'w-2 h-2 rounded-full ' + (isActive ? 'bg-semantic-profit animate-pulse' : 'bg-semantic-loss')} />
                        <span className="text-xs font-medium text-content-secondary">
                          Plano {planDisplay}
                        </span>
                      </div>
                      <span className="text-xs text-content-muted">
                        {daysRemaining != null
                          ? `${daysRemaining} dia${daysRemaining !== 1 ? 's' : ''} restante${daysRemaining !== 1 ? 's' : ''}`
                          : isActive ? 'Ativo' : 'Inativo'}
                      </span>
                    </div>
                  )}

                  {/* Robots unlocked list hint */}
                  {profile.unlocked_robots.length > 0 && (
                    <div className="flex items-center gap-2 px-3">
                      <Bot className="w-3.5 h-3.5 text-content-muted" />
                      <span className="text-2xs text-content-muted">
                        Robôs ativos: {profile.unlocked_robots.slice(0, 5).join(', ')}
                        {profile.unlocked_robots.length > 5 && ` +${profile.unlocked_robots.length - 5}`}
                      </span>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
};

/* ── StatCard subcomponent ───────────────────────────────────────────────── */
interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  iconColor: string;
  borderColor: string;
  children: React.ReactNode;
}

function StatCard({ icon, label, iconColor, borderColor, children }: StatCardProps) {
  return (
    <div className={'p-3 rounded-lg bg-surface-hover/40 border ' + borderColor + ' space-y-1'}>
      <div className="flex items-center gap-1.5">
        <span className={iconColor}>{icon}</span>
        <span className="text-2xs font-semibold text-content-muted uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-xl font-display font-black text-content-primary leading-none">
        {children}
      </p>
    </div>
  );
}

export default GameProfileWidget;
