/**
 * LivePrice — preço em tempo real com tick visual de alta/baixa
 *
 * Uso:
 *   <LivePrice price={ticker.last} decimals={2} />
 *   <LivePrice price={portfolio.totalValue} prefix="$" className="text-2xl font-bold" />
 *
 * Ao mudar o valor de `price`, o span pisca verde (alta) ou vermelho (baixa)
 * por 500ms e volta para a cor primária.
 */
import React from 'react';
import { cn } from '@/lib/utils';
import { usePriceTick } from '@/hooks/usePriceTick';

interface LivePriceProps {
  price: number;
  /** Casas decimais. Default: 2 */
  decimals?: number;
  /** Prefixo de moeda — ex: '$', 'R$'. Omitir para só número. */
  prefix?: string;
  /** Sufixo — ex: '%', ' USDT' */
  suffix?: string;
  /** Classes extras — tamanho, weight, etc. */
  className?: string;
  /** Duração do flash de tick em ms. Default: 500 */
  tickDuration?: number;
  /** Desativa o tick (útil para valores estáticos) */
  noTick?: boolean;
}

export function LivePrice({
  price,
  decimals = 2,
  prefix,
  suffix,
  className,
  tickDuration = 500,
  noTick = false,
}: LivePriceProps) {
  const tick = usePriceTick(noTick ? 0 : price, tickDuration);

  return (
    <span
      className={cn(
        // Base — monospace financeiro
        'font-mono font-semibold tabular-nums slashed-zero',
        // Transição suave de cor — 300ms ease-out (spec §8.6)
        'transition-colors duration-300 ease-out',
        // Tick state — neutro quando sem tick
        tick === 'up'   && !noTick && 'text-semantic-profit',
        tick === 'down' && !noTick && 'text-semantic-loss',
        (!tick || noTick)          && 'text-content-primary',
        className,
      )}
    >
      {prefix}{price.toFixed(decimals)}{suffix}
    </span>
  );
}
