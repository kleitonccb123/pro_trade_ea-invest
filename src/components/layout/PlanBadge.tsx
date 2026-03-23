/**
 * PlanBadge — Card elegante de plano ativo no header
 *
 * Exibe: ícone do plano + nome + dias restantes (se disponível)
 * Cores automáticas por plano (black, premium, pro, starter…)
 * Clicável → navega para /billing
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Clock, Zap } from 'lucide-react';
import { usePlanStore } from '@/stores/plan-store';
import { useAuthStore } from '@/context/AuthContext';
import { cn } from '@/lib/utils';

export function PlanBadge() {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const {
    plan,
    planDisplay,
    isActive,
    isExpired,
    expiringSoon,
    daysRemaining,
    isLoading,
    fetch: fetchPlan,
  } = usePlanStore();

  // Busca ao montar e revalida a cada 5 minutos
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchPlan();
    const id = setInterval(fetchPlan, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [isAuthenticated, fetchPlan]);

  // Não exibir durante loading inicial ou para plano free/starter sem ativação
  if (!isAuthenticated || isLoading) return null;
  if ((plan === 'free' || plan === 'starter') && !isExpired) return null;

  // ── Visual dinâmico por estado ──────────────────────────────────────────
  const isPaid       = isActive || isExpired;
  const isBlack      = plan === 'black' || plan === 'enterprise';
  const isPremium    = plan === 'premium' || plan === 'quant';
  const isPro        = plan === 'pro' || plan === 'pro_plus';

  const gradientCls = isExpired
    ? 'from-red-950/60 to-red-900/40 border-red-600/40'
    : isBlack
    ? 'from-yellow-950/60 via-stone-900/50 to-yellow-950/40 border-yellow-700/50'
    : isPremium
    ? 'from-cyan-950/60 to-teal-900/40 border-cyan-500/40'
    : isPro
    ? 'from-purple-950/60 to-indigo-900/40 border-purple-500/40'
    : 'from-slate-800/60 to-slate-900/40 border-slate-600/40';

  const textCls = isExpired
    ? 'text-red-400'
    : isBlack
    ? 'text-yellow-300'
    : isPremium
    ? 'text-cyan-300'
    : isPro
    ? 'text-purple-300'
    : 'text-slate-400';

  const dotCls = isExpired
    ? 'bg-red-500'
    : isBlack
    ? 'bg-yellow-400'
    : isPremium
    ? 'bg-cyan-400'
    : isPro
    ? 'bg-purple-400'
    : 'bg-slate-500';

  const glowCls = isBlack
    ? 'shadow-yellow-900/40'
    : isPremium
    ? 'shadow-cyan-900/40'
    : isPro
    ? 'shadow-purple-900/40'
    : '';

  // ── Texto de dias ───────────────────────────────────────────────────────
  const daysLabel =
    isExpired
      ? 'Expirado'
      : daysRemaining === null
      ? 'Ativo'
      : daysRemaining === 0
      ? 'Último dia'
      : `${daysRemaining}d`;

  return (
    <button
      onClick={() => navigate('/billing')}
      title={
        isExpired
          ? 'Assinatura expirada — clique para renovar'
          : `Plano ${planDisplay} ativo${daysRemaining !== null ? ` · ${daysRemaining} dias restantes` : ''}`
      }
      className={cn(
        'group flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border',
        'bg-gradient-to-r transition-all duration-200 cursor-pointer',
        'hover:brightness-110 active:scale-95',
        'shadow-sm',
        gradientCls,
        glowCls
      )}
    >
      {/* Status dot */}
      <span className="relative flex h-2 w-2 flex-shrink-0">
        {isActive && !isExpired && (
          <span
            className={cn(
              'animate-ping absolute inline-flex h-full w-full rounded-full opacity-60',
              dotCls
            )}
          />
        )}
        <span className={cn('relative inline-flex rounded-full h-2 w-2', dotCls)} />
      </span>

      {/* Plan label */}
      <span className={cn('text-xs font-bold tracking-wider leading-none', textCls)}>
        {planDisplay}
      </span>

      {/* Separator */}
      <span className={cn('text-xs opacity-40 leading-none', textCls)}>·</span>

      {/* Days / status */}
      <span
        className={cn(
          'flex items-center gap-0.5 text-xs font-medium leading-none',
          expiringSoon && !isExpired ? 'text-amber-400' : textCls
        )}
      >
        {expiringSoon && !isExpired && (
          <Clock className="w-3 h-3 text-amber-400" />
        )}
        {daysLabel}
      </span>
    </button>
  );
}
