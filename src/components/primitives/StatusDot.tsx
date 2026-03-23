/**
 * StatusDot — indicador de status circular com significado semântico
 *
 * Variantes com significado fixo — nunca use cores arbitrárias:
 *   active   → verde (robô rodando, connected, online)
 *   paused   → amarelo (pausado, warning, atenção)
 *   inactive → cinza (parado, offline, disabled)
 *   error    → vermelho (erro, falha crítica)
 *
 * A prop `pulse` ativa o anel de ping para status "ao vivo".
 * Use pulse=true APENAS em robôs ativamente em execução — nunca em cards ou decoração.
 *
 * Uso:
 *   <StatusDot status="active" pulse />           → verde pulsante (robô em execução)
 *   <StatusDot status="inactive" />               → cinza estático (parado)
 *   <StatusDot status="error" size="md" />        → vermelho médio
 *   <StatusDot status="active" label="Online" />  → ponto + texto
 */
import React from 'react';
import { cn } from '@/lib/utils';

type DotStatus = 'active' | 'paused' | 'inactive' | 'error';

interface StatusDotProps {
  status: DotStatus;
  /** Ativa anel de ping (§8.3 — apenas em robôs ativos em execução). Default: false */
  pulse?: boolean;
  /** xs: 6px | sm: 8px (default) | md: 10px */
  size?: 'xs' | 'sm' | 'md';
  /** Label ao lado do dot */
  label?: string;
  className?: string;
}

const colorMap: Record<DotStatus, string> = {
  active:   'bg-semantic-profit',
  paused:   'bg-semantic-warning',
  inactive: 'bg-content-muted',
  error:    'bg-semantic-loss',
};

const pulseColorMap: Record<DotStatus, string> = {
  active:   'rgba(16, 185, 129, 0.35)',
  paused:   'rgba(245, 158, 11, 0.35)',
  inactive: 'transparent',
  error:    'rgba(239, 68, 68, 0.35)',
};

const sizeMap: Record<NonNullable<StatusDotProps['size']>, string> = {
  xs: 'w-1.5 h-1.5',
  sm: 'w-2 h-2',
  md: 'w-2.5 h-2.5',
};

const labelColorMap: Record<DotStatus, string> = {
  active:   'text-semantic-profit',
  paused:   'text-semantic-warning',
  inactive: 'text-content-muted',
  error:    'text-semantic-loss',
};

export function StatusDot({
  status,
  pulse = false,
  size = 'sm',
  label,
  className,
}: StatusDotProps) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 flex-shrink-0', className)}>
      <span
        className={cn(
          'inline-block rounded-full flex-shrink-0',
          sizeMap[size],
          colorMap[status],
          // Ping via CSS class (§8.3) — só quando pulse=true
          pulse && 'status-active',
        )}
        style={
          pulse
            ? ({ '--ping-color': pulseColorMap[status] } as React.CSSProperties)
            : undefined
        }
      />
      {label && (
        <span className={cn('text-xs font-medium', labelColorMap[status])}>
          {label}
        </span>
      )}
    </span>
  );
}
