/**
 * PercentBadge — badge de variação percentual com cor semântica automática
 *
 * Regra: todo percentual de P&L, variação de preço ou delta deve usar este componente.
 *
 * Uso:
 *   <PercentBadge value={2.45} />     → badge verde "+2.45%"
 *   <PercentBadge value={-1.2} />     → badge vermelho "-1.20%"
 *   <PercentBadge value={0} />        → badge neutro "0.00%"
 *   <PercentBadge value={5.1} size="sm" showIcon={false} />
 */
import React from 'react';
import { TrendingDown, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PercentBadgeProps {
  value: number;
  /** Casas decimais. Default: 2. */
  decimals?: number;
  /** Mostrar ícone TrendingUp/Down. Default: true. */
  showIcon?: boolean;
  /** sm = text-xs (padrão) | md = text-sm */
  size?: 'sm' | 'md';
  className?: string;
}

export function PercentBadge({
  value,
  decimals = 2,
  showIcon = true,
  size = 'sm',
  className,
}: PercentBadgeProps) {
  const positive = value > 0;
  const negative = value < 0;
  const label = `${positive ? '+' : ''}${value.toFixed(decimals)}%`;

  const textSize = size === 'md' ? 'text-sm' : 'text-xs';
  const iconSize = size === 'md' ? 12 : 10;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono font-medium tabular-nums',
        'border transition-colors',
        textSize,
        positive && 'bg-semantic-profit/12 text-semantic-profit border-semantic-profit/25',
        negative && 'bg-semantic-loss/12 text-semantic-loss border-semantic-loss/25',
        !positive && !negative && 'bg-surface-hover text-content-secondary border-edge-subtle',
        className,
      )}
    >
      {showIcon && positive && <TrendingUp size={iconSize} />}
      {showIcon && negative && <TrendingDown size={iconSize} />}
      {label}
    </span>
  );
}
