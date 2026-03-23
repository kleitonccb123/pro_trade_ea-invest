/**
 * Typography Primitives — Pro Trader-EA Design System
 *
 * Regras:
 *  • Dados financeiros (preços, %, volumes) → MetricValue
 *  • Títulos de página                      → PageTitle
 *  • Títulos de card/seção                  → CardTitle
 *  • Label de seção (uppercase)             → SectionLabel
 *  • Body de texto                          → BodyText
 *  • Timestamp / metadado                   → Timestamp
 *
 * NUNCA use text-white / text-cyan-400 diretamente nos componentes de Pro Trader-EA.
 * Sempre derive de tokens semânticos (text-content-primary, etc.)
 */

import React from 'react';
import { cn } from '@/lib/utils';

// ─────────────────────────────────────────────────────────────────────────────
// MetricValue — preço, saldo, percentual, volume
// font-mono | tabular-nums slashed-zero | tracking-tight
// ─────────────────────────────────────────────────────────────────────────────
interface MetricValueProps {
  value: string;
  /** Verde — lucro, variação positiva */
  positive?: boolean;
  /** Vermelho — perda, variação negativa */
  negative?: boolean;
  /** text-xl (default) | text-2xl | text-3xl | text-4xl | text-5xl */
  size?: 'xl' | '2xl' | '3xl' | '4xl' | '5xl';
  className?: string;
}

const metricSizes: Record<NonNullable<MetricValueProps['size']>, string> = {
  xl:   'text-xl',
  '2xl':'text-2xl',
  '3xl':'text-3xl',
  '4xl':'text-4xl',
  '5xl':'text-5xl',
};

export function MetricValue({
  value,
  positive,
  negative,
  size = 'xl',
  className,
}: MetricValueProps) {
  return (
    <span
      className={cn(
        'font-mono font-semibold tracking-tight tabular-nums',
        metricSizes[size],
        positive  && 'text-semantic-profit',
        negative  && 'text-semantic-loss',
        !positive && !negative && 'text-content-primary',
        className
      )}
      style={{ fontVariantNumeric: 'tabular-nums slashed-zero' }}
    >
      {value}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PageTitle — H1 da página
// font-display | font-bold | text-3xl | tracking-tight
// ─────────────────────────────────────────────────────────────────────────────
interface PageTitleProps extends React.PropsWithChildren {
  className?: string;
  as?: 'h1' | 'h2';
}

export function PageTitle({ children, className, as: Tag = 'h1' }: PageTitleProps) {
  return (
    <Tag
      className={cn(
        'font-display font-bold text-3xl text-content-primary tracking-tight leading-tight',
        className
      )}
    >
      {children}
    </Tag>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CardTitle — Header de card / H3 equivalente
// font-display | font-semibold | text-xl | tracking-tight
// ─────────────────────────────────────────────────────────────────────────────
interface CardTitleProps extends React.PropsWithChildren {
  className?: string;
  as?: 'h2' | 'h3' | 'h4' | 'p' | 'span';
}

export function CardTitle({ children, className, as: Tag = 'h3' }: CardTitleProps) {
  return (
    <Tag
      className={cn(
        'font-display font-semibold text-xl text-content-primary tracking-tight',
        className
      )}
    >
      {children}
    </Tag>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SectionLabel — label de seção (uppercase, rastreado)
// font-sans | font-medium | text-xs | uppercase | tracking-widest
// ─────────────────────────────────────────────────────────────────────────────
interface SectionLabelProps extends React.PropsWithChildren {
  className?: string;
  as?: 'span' | 'p' | 'div' | 'label';
}

export function SectionLabel({ children, className, as: Tag = 'span' }: SectionLabelProps) {
  return (
    <Tag
      className={cn(
        'font-sans font-medium text-xs text-content-secondary uppercase tracking-widest',
        className
      )}
    >
      {children}
    </Tag>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// BodyText — corpo de texto padrão
// font-sans | font-regular | text-sm | leading-normal
// ─────────────────────────────────────────────────────────────────────────────
interface BodyTextProps extends React.PropsWithChildren {
  className?: string;
  as?: 'p' | 'span' | 'div';
  muted?: boolean;
}

export function BodyText({ children, className, as: Tag = 'p', muted = false }: BodyTextProps) {
  return (
    <Tag
      className={cn(
        'font-sans font-normal text-sm leading-normal',
        muted ? 'text-content-muted' : 'text-content-body',
        className
      )}
    >
      {children}
    </Tag>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Timestamp — horário, data, metadata de operação
// font-mono | font-normal | text-xs | text-content-muted
// ─────────────────────────────────────────────────────────────────────────────
interface TimestampProps extends React.PropsWithChildren {
  className?: string;
  as?: 'span' | 'time' | 'p';
  dateTime?: string;
}

export function Timestamp({ children, className, as: Tag = 'span', dateTime }: TimestampProps) {
  const props = Tag === 'time' ? { dateTime } : {};
  return (
    <Tag
      className={cn(
        'font-mono font-normal text-xs text-content-muted tabular-nums',
        className
      )}
      {...props}
    >
      {children}
    </Tag>
  );
}
