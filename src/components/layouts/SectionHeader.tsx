/**
 * SectionHeader — título de seção + ação opcional
 *
 * Uso:
 *   <SectionHeader title="Robôs Ativos" action={<Button size="sm">+ Novo</Button>} />
 *   <SectionHeader title="Histórico" description="Últimas 100 operações" />
 */
import React from 'react';
import { cn } from '@/lib/utils';

interface SectionHeaderProps {
  title: string;
  description?: string;
  /** Elemento à direita — Button, Badge, Link etc. */
  action?: React.ReactNode;
  className?: string;
  /** 'sm' para headers internos de card, 'md' (default) para seções de página */
  size?: 'sm' | 'md';
}

export function SectionHeader({ title, description, action, className, size = 'md' }: SectionHeaderProps) {
  const isSmall = size === 'sm';

  return (
    <div className={cn('flex items-center justify-between', isSmall ? 'mb-4' : 'mb-6', className)}>
      <div className="min-w-0">
        <h2
          className={cn(
            'font-display font-semibold text-content-primary tracking-tight leading-tight',
            isSmall ? 'text-base' : 'text-xl'
          )}
        >
          {title}
        </h2>
        {description && (
          <p className="mt-0.5 text-xs text-content-secondary font-sans">{description}</p>
        )}
      </div>

      {action && (
        <div className="flex-shrink-0 ml-4">
          {action}
        </div>
      )}
    </div>
  );
}
