/**
 * NumberAnimator - Componente para animar números como slot machine
 * 
 * Exibe números com animação suave e efeito de "rolagem" como em uma slot machine.
 * Ideal para exibir pontos, XP, lucros, etc.
 */

import React from 'react';
import CountUp from 'react-countup';

interface NumberAnimatorProps {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  duration?: number;
  className?: string;
  glowColor?: 'gold' | 'emerald' | 'purple' | 'cyan';
}

const glowColorMap = {
  gold: 'text-yellow-400 drop-shadow-[0_0_10px_rgba(250,204,21,0.5)]',
  emerald: 'text-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.5)]',
  purple: 'text-purple-500 drop-shadow-[0_0_10px_rgba(168,85,247,0.5)]',
  cyan: 'text-emerald-400 drop-shadow-[0_0_10px_rgba(35,200,130,0.5)]',
};

export const NumberAnimator: React.FC<NumberAnimatorProps> = ({
  value,
  prefix = '',
  suffix = '',
  decimals = 0,
  duration = 1.5,
  className = '',
  glowColor = 'gold',
}) => {
  return (
    <span className={`${className} ${glowColorMap[glowColor]} font-bold`}>
      {prefix}
      <CountUp
        end={value}
        decimals={decimals}
        duration={duration}
        separator=","
        preserveValue={true}
      />
      {suffix}
    </span>
  );
};

export default NumberAnimator;
