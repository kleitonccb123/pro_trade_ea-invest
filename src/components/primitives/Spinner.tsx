/**
 * Spinner — indicador de loading inline
 *
 * Uso em botão:
 *   <button disabled={loading}>
 *     {loading && <Spinner size="sm" className="mr-2" />}
 *     {loading ? 'Salvando...' : 'Salvar'}
 *   </button>
 *
 * Uso autônomo (loading de componente menor):
 *   <Spinner size="md" />
 */
import React from 'react';
import { cn } from '@/lib/utils';

interface SpinnerProps {
  /** sm: 14px (inline), md: 18px (card), lg: 24px (page section) */
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** Cor do arco — default: brand.primary */
  color?: 'brand' | 'profit' | 'loss' | 'muted';
}

const sizeMap: Record<NonNullable<SpinnerProps['size']>, string> = {
  sm: 'w-3.5 h-3.5 border-[1.5px]',
  md: 'w-[18px] h-[18px] border-2',
  lg: 'w-6 h-6 border-2',
};

const colorMap: Record<NonNullable<SpinnerProps['color']>, string> = {
  brand:  'border-brand-primary/20 border-t-brand-primary',
  profit: 'border-semantic-profit/20 border-t-semantic-profit',
  loss:   'border-semantic-loss/20   border-t-semantic-loss',
  muted:  'border-edge-strong/30     border-t-content-secondary',
};

export function Spinner({ size = 'sm', color = 'brand', className }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Carregando"
      className={cn(
        'inline-block rounded-full animate-spin flex-shrink-0',
        sizeMap[size],
        colorMap[color],
        className
      )}
      style={{ animationDuration: '650ms' }}
    />
  );
}
