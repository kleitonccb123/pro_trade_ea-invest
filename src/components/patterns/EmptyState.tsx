/**
 * EmptyState — estado vazio elegante com orientação ao usuário
 *
 * Uso:
 *   <EmptyState
 *     title="Nenhum robô ativo"
 *     description="Ative um robô para ver os dados aqui."
 *     icon={<Bot size={20} />}
 *     action={<Button size="sm">Criar robô</Button>}
 *   />
 */
import React from 'react';
import { BarChart2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title: string;
  description?: string;
  /** Ícone — default: BarChart2 */
  icon?: React.ReactNode;
  /** CTA — Button, Link etc. */
  action?: React.ReactNode;
  /** py-16 (default) | py-8 (compacto) */
  size?: 'default' | 'compact';
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  size = 'default',
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        size === 'default' ? 'py-16' : 'py-8',
        className
      )}
    >
      {/* Ícone */}
      <div className="w-11 h-11 rounded-lg bg-surface-hover border border-edge-subtle flex items-center justify-center mb-4 text-content-muted">
        {icon ?? <BarChart2 size={20} />}
      </div>

      {/* Título */}
      <h3 className="font-display font-semibold text-lg text-content-primary mb-1 tracking-tight">
        {title}
      </h3>

      {/* Descrição */}
      {description && (
        <p className="text-sm text-content-secondary max-w-xs mb-5 leading-relaxed">
          {description}
        </p>
      )}

      {/* Ação */}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

/**
 * ErrorState — estado de erro com ação de recuperação
 *
 * Uso:
 *   <ErrorState
 *     title="Falha ao carregar dados"
 *     message="Verifique sua conexão e tente novamente."
 *     onRetry={fetchData}
 *   />
 */
interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Algo deu errado',
  message,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12 text-center', className)}>
      {/* Ícone de erro */}
      <div className="w-10 h-10 rounded-lg bg-semantic-loss/10 border border-semantic-loss/20 flex items-center justify-center mb-4">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-semantic-loss"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>

      <h3 className="font-display font-semibold text-base text-content-primary mb-1 tracking-tight">
        {title}
      </h3>
      <p className="text-sm text-content-secondary max-w-sm mb-4 leading-relaxed">{message}</p>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="text-sm font-medium text-brand-primary hover:text-brand-primary/75 transition-colors"
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}
