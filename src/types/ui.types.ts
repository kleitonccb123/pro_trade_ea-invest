/**
 * ui.types.ts — tipos de interface e componentes
 *
 * Tipos para props de componentes, estados de UI e configurações visuais.
 * Não contém tipos de API ou de domínio de negócio.
 */

// ── Variantes de tamanho padrão (consistente em todo o design system) ──
export type SizeVariant = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

// ── Variante de cor semântica financeira ──
export type SemanticColor =
  | 'profit'
  | 'loss'
  | 'warning'
  | 'info'
  | 'brand'
  | 'neutral';

// ── Status de robô / operação ──
export type RobotStatus = 'active' | 'paused' | 'inactive' | 'error';

// ── Status de operação/trade ──
export type TradeStatus = 'open' | 'closed' | 'cancelled' | 'pending';

// ── Direção de preço (para tick) ──
export type PriceTick = 'up' | 'down' | null;

// ── Estado assíncrono padrão ──
export type AsyncState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

// ── Dados do período ──
export type TimePeriod = '1h' | '4h' | '1d' | '7d' | '30d' | 'all';

// ── Ação de toast/notificação ──
export interface ToastAction {
  label: string;
  onClick: () => void;
}

// ── Opções de formatação de preço ──
export interface PriceFormatOptions {
  currency?: string;
  decimals?: number;
  compact?: boolean;
}

// ── Props base para componentes compostos ──
export interface BaseComponentProps {
  className?: string;
  children?: React.ReactNode;
}

// ── Coluna de tabela genérica ──
export interface TableColumn<T> {
  key: keyof T | string;
  label: string;
  sortable?: boolean;
  align?: 'left' | 'center' | 'right';
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}
