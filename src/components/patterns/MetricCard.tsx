/**
 * MetricCard — KPI card reutilizável (Nível 1 da hierarquia de dashboard)
 *
 * Uso:
 *   <MetricCard title="Saldo Total" value="$42,308.50" delta="+2.4%" deltaPositive />
 *   <MetricCard title="Robôs Ativos" value="7" icon={<Bot size={16} />} loading />
 */
import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { MetricCardSkeleton } from './Skeleton';

export interface MetricCardProps {
  /** Label superior em uppercase */
  title: string;
  /** Valor principal — string pré-formatada (use formatPrice/formatPercent) */
  value: string;
  /** Variação vs período anterior — ex: "+2.4%" */
  delta?: string;
  /**
   * true  → delta em verde (profit)
   * false → delta em vermelho (loss)
   * undefined → delta em cinza (neutro)
   */
  deltaPositive?: boolean;
  /** Ícone à direita do label superior */
  icon?: React.ReactNode;
  /** Sufixo após o valor — ex: "USDT", "%" */
  suffix?: string;
  /** Descrição ou contexto secundário */
  description?: string;
  /** Exibe skeleton enquanto dados carregam */
  loading?: boolean;
  /** Classe adicional no wrapper */
  className?: string;
  /** Callback ao clicar no card */
  onClick?: () => void;
}

export function MetricCard({
  title,
  value,
  delta,
  deltaPositive,
  icon,
  suffix,
  description,
  loading,
  className,
  onClick,
}: MetricCardProps) {
  if (loading) return <MetricCardSkeleton />;

  const isClickable = !!onClick;

  return (
    <div
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onClick={onClick}
      onKeyDown={isClickable ? (e) => e.key === 'Enter' && onClick?.() : undefined}
      className={cn(
        'bg-surface-raised border border-edge-subtle rounded-lg p-6',
        'relative overflow-hidden group',
        'transition-all duration-200',
        'hover:border-edge-default hover:shadow-card',
        isClickable && 'cursor-pointer',
        className
      )}
    >
      {/* Label superior */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium text-content-secondary uppercase tracking-widest">
          {title}
        </span>
        {icon && (
          <span className="text-content-muted group-hover:text-brand-primary transition-colors duration-200">
            {icon}
          </span>
        )}
      </div>

      {/* Valor principal */}
      <div className="flex items-end gap-2 mb-2">
        <span
          className="font-mono font-semibold text-3xl text-content-primary tabular-nums tracking-tight"
          style={{ fontVariantNumeric: 'tabular-nums slashed-zero' }}
        >
          {value}
        </span>
        {suffix && (
          <span className="font-mono text-sm text-content-secondary mb-0.5 pb-0.5">
            {suffix}
          </span>
        )}
      </div>

      {/* Delta / variação */}
      {delta && (
        <div
          className={cn(
            'flex items-center gap-1 text-sm font-medium font-mono tabular-nums',
            deltaPositive === true  && 'text-semantic-profit',
            deltaPositive === false && 'text-semantic-loss',
            deltaPositive === undefined && 'text-content-secondary'
          )}
        >
          {deltaPositive === true  && <TrendingUp size={13} />}
          {deltaPositive === false && <TrendingDown size={13} />}
          <span>{delta}</span>
          <span className="text-xs text-content-muted font-sans ml-1 font-normal">vs ontem</span>
        </div>
      )}

      {/* Descrição opcional */}
      {description && !delta && (
        <p className="text-xs text-content-muted mt-1">{description}</p>
      )}

      {/* Linha de accent inferior — aparece no hover */}
      <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand-primary/0 group-hover:bg-brand-primary/35 transition-all duration-300" />
    </div>
  );
}
