/**
 * format — utilitários centralizados de formatação financeira
 *
 * REGRA: nunca use .toFixed() ou .toLocaleString() diretamente no JSX.
 * Sempre passe por estas funções para garantir consistência.
 *
 * Uso:
 *   formatPrice(42308.50)                   → "42,308.50"
 *   formatPrice(42308.50, { currency: '$' }) → "$42,308.50"
 *   formatPercent(2.45)                      → "+2.45%"
 *   formatPercent(-1.2, { sign: false })     → "1.20%"
 *   formatVolume(1_500_000)                  → "1.50M"
 *   formatDate(new Date(), 'long')           → "24 fev. 2026"
 */

// ─────────────────────────────────────────────────────────────────────────────
// Preço / valor monetário
// ─────────────────────────────────────────────────────────────────────────────
interface FormatPriceOptions {
  /** Símbolo de moeda prefixado — ex: '$', 'R$'. Omitir para só número. */
  currency?: string;
  /** Casas decimais. Default: 2 */
  decimals?: number;
  /** Abreviar grandes valores (K, M, B). Default: false */
  compact?: boolean;
}

export function formatPrice(
  value: number,
  options: FormatPriceOptions = {},
): string {
  const { currency, decimals = 2, compact = false } = options;

  if (compact) {
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
    if (value >= 1_000_000)     return `${(value / 1_000_000).toFixed(2)}M`;
    if (value >= 1_000)         return `${(value / 1_000).toFixed(2)}K`;
  }

  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);

  return currency ? `${currency}${formatted}` : formatted;
}

// ─────────────────────────────────────────────────────────────────────────────
// Percentual
// ─────────────────────────────────────────────────────────────────────────────
interface FormatPercentOptions {
  /** Incluir sinal + em valores positivos. Default: true */
  sign?: boolean;
  /** Casas decimais. Default: 2 */
  decimals?: number;
}

export function formatPercent(
  value: number,
  options: FormatPercentOptions = {},
): string {
  const { sign = true, decimals = 2 } = options;
  const absStr = Math.abs(value).toFixed(decimals);
  if (!sign) return `${absStr}%`;
  if (value > 0)  return `+${absStr}%`;
  if (value < 0)  return `-${absStr}%`;
  return `${absStr}%`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Volume / quantidade de tokens
// ─────────────────────────────────────────────────────────────────────────────
export function formatVolume(value: number, decimals = 2): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(decimals)}B`;
  if (value >= 1_000_000)     return `${(value / 1_000_000).toFixed(decimals)}M`;
  if (value >= 1_000)         return `${(value / 1_000).toFixed(decimals)}K`;
  return value.toFixed(decimals);
}

// ─────────────────────────────────────────────────────────────────────────────
// Data / hora
// ─────────────────────────────────────────────────────────────────────────────
type DateFormat = 'short' | 'long' | 'time' | 'datetime' | 'relative';

export function formatDate(
  date: string | number | Date,
  format: DateFormat = 'short',
): string {
  const d = new Date(date);

  if (isNaN(d.getTime())) return '—';

  switch (format) {
    case 'short':
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' });
    case 'long':
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });
    case 'time':
      return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    case 'datetime':
      return d.toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: '2-digit',
        hour: '2-digit', minute: '2-digit',
      });
    case 'relative': {
      const diff = Date.now() - d.getTime();
      const mins  = Math.floor(diff / 60_000);
      const hours = Math.floor(diff / 3_600_000);
      const days  = Math.floor(diff / 86_400_000);
      if (mins  < 1)   return 'agora';
      if (mins  < 60)  return `${mins}m atrás`;
      if (hours < 24)  return `${hours}h atrás`;
      if (days  < 30)  return `${days}d atrás`;
      return formatDate(d, 'long');
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Par de trading
// ─────────────────────────────────────────────────────────────────────────────
/** "BTCUSDT" → "BTC/USDT" */
export function formatTradingPair(symbol: string): string {
  const quoteAssets = ['USDT', 'BTC', 'ETH', 'BNB', 'BUSD'];
  for (const quote of quoteAssets) {
    if (symbol.toUpperCase().endsWith(quote)) {
      const base = symbol.slice(0, -quote.length).toUpperCase();
      return `${base}/${quote}`;
    }
  }
  return symbol.toUpperCase();
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
/** Trunca endereço/ID longo: "0x1234...abcd" */
export function truncateId(id: string, start = 6, end = 4): string {
  if (id.length <= start + end + 3) return id;
  return `${id.slice(0, start)}...${id.slice(-end)}`;
}
