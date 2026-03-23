/**
 * usePriceTick — detecta mudança de preço e retorna direção do tick
 *
 * Uso:
 *   const tick = usePriceTick(price);
 *   <span className={cn('font-mono', tick === 'up' && 'text-semantic-profit', tick === 'down' && 'text-semantic-loss')}>{price}</span>
 *
 * Para o componente pronto com estilos aplicados, use <LivePrice> de:
 *   import { LivePrice } from '@/components/primitives/LivePrice'
 *
 * O tick dura 500ms e volta para null automaticamente.
 */
import { useState, useEffect, useRef } from 'react';

export type PriceTick = 'up' | 'down' | null;

export function usePriceTick(value: number, duration = 500): PriceTick {
  const [tick, setTick] = useState<PriceTick>(null);
  const prevValue = useRef(value);

  useEffect(() => {
    if (value !== prevValue.current) {
      setTick(value > prevValue.current ? 'up' : 'down');
      prevValue.current = value;

      const timer = setTimeout(() => setTick(null), duration);
      return () => clearTimeout(timer);
    }
  }, [value, duration]);

  return tick;
}
