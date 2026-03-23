/**
 * PriceDisplay — exibe valor financeiro formatado com semântica de cor
 *
 * Regra: todo número financeiro na UI deve passar por este componente
 * ou por <LivePrice> (para dados em tempo real com tick).
 *
 * Uso:
 *   <PriceDisplay value={42308.50} currency="$" />
 *   <PriceDisplay value={-120.5} showSign size="lg" />
 *   <PriceDisplay value={0.00004821} decimals={8} currency="BTC" />
 */
import React from 'react';
import { cn } from '@/lib/utils';

interface PriceDisplayProps {
  value: number;
  /** Símbolo de moeda prefixado. Ex: '$'. Omitir para sufixo via `currency`. */
  prefix?: string;
  /** Sufixo de moeda. Ex: 'USDT', 'BTC'. Omitir para valor puro. */
  currency?: string;
  /** Casas decimais. Default: 2. Para cripto pequena, use 6-8. */
  decimals?: number;
  /** Tamanho visual. Default: 'md'. */
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  /**
   * Se true, aplica cor semântica:
   *   positivo → semantic-profit (verde)
   *   negativo → semantic-loss (vermelho)
   *   zero     → content-secondary (cinza)
   */
  showSign?: boolean;
  className?: string;
}

const sizeMap: Record<NonNullable<PriceDisplayProps['size']>, string> = {
  xs: 'text-xs',
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-xl',
  xl: 'text-3xl',
};

export function PriceDisplay({
  value,
  prefix,
  currency,
  decimals = 2,
  size = 'md',
  showSign = false,
  className,
}: PriceDisplayProps) {
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(value));

  const isPositive = value > 0;
  const isNegative = value < 0;

  return (
    <span
      className={cn(
        'font-mono font-semibold tabular-nums slashed-zero',
        sizeMap[size],
        showSign && isPositive && 'text-semantic-profit',
        showSign && isNegative && 'text-semantic-loss',
        showSign && !isPositive && !isNegative && 'text-content-secondary',
        !showSign && 'text-content-primary',
        className,
      )}
    >
      {prefix}
      {showSign && isPositive && '+'}
      {showSign && isNegative && '-'}
      {formatted}
      {currency && (
        <span className="text-content-secondary font-medium ml-1 text-[0.75em]">
          {currency}
        </span>
      )}
    </span>
  );
}
