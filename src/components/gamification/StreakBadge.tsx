/**
 * StreakBadge - Indicador Visual de Ofensiva (Streak)
 * 
 * Features:
 * - Ícone de fogo 🔥 animado
 * - Exibe número de dias consecutivos
 * - Tooltip com informações de bônus
 * - Animação pulsante quando streak alto
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Flame } from 'lucide-react';

interface StreakBadgeProps {
  streak: number;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const StreakBadge: React.FC<StreakBadgeProps> = ({
  streak,
  showLabel = true,
  size = 'md',
  className = '',
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  if (streak === 0) return null;

  // Calcula bônus baseado em streak
  const bonusPercent = streak * 10;
  const isHighStreak = streak >= 5;

  // Tamanhos
  const sizes = {
    sm: { badge: 'px-2 py-1 text-xs', flame: 'w-3 h-3', number: 'text-sm' },
    md: { badge: 'px-3 py-1.5 text-sm', flame: 'w-4 h-4', number: 'text-base' },
    lg: { badge: 'px-4 py-2 text-base', flame: 'w-5 h-5', number: 'text-lg' },
  };

  const sizeConfig = sizes[size];

  return (
    <div className={`relative inline-block ${className}`} onMouseEnter={() => setShowTooltip(true)} onMouseLeave={() => setShowTooltip(false)}>
      {/* Tooltip */}
      {showTooltip && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          className="absolute -top-20 left-1/2 transform -translate-x-1/2 z-50 bg-slate-900/95 border border-orange-500/50 rounded-lg p-3 whitespace-nowrap text-xs text-orange-100 pointer-events-none"
        >
          <div className="font-bold">🔥 Ofensiva: {streak} dias</div>
          <div className="text-orange-200/70">Bônus: +{bonusPercent}% de recompensas</div>
          <div className="text-orange-200/50 mt-1">
            {streak < 5 ? `Faltam ${5 - streak} dias para +50%!` : '🎉 Máximo bônus!'}
          </div>
        </motion.div>
      )}

      {/* Badge Principal */}
      <motion.div
        animate={isHighStreak ? { scale: [1, 1.1, 1] } : {}}
        transition={
          isHighStreak
            ? {
                duration: 1.2,
                repeat: Infinity,
                ease: 'easeInOut',
              }
            : {}
        }
        className={`
          ${sizeConfig.badge}
          inline-flex items-center gap-1.5
          bg-gradient-to-r from-orange-500 to-red-600
          text-white font-bold rounded-full
          border border-orange-300/50
          shadow-lg
          ${isHighStreak ? 'shadow-[0_0_15px_rgba(234,88,12,0.6)]' : ''}
          cursor-help
          transition-shadow
          hover:shadow-[0_0_20px_rgba(234,88,12,0.8)]
        `}
        style={{
          willChange: isHighStreak ? 'transform' : 'auto',
        }}
      >
        {/* Chama Animada */}
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            rotate: [0, 5, -5, 0],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          style={{ willChange: 'transform' }}
        >
          🔥
        </motion.div>

        {/* Número de Dias */}
        <span className={sizeConfig.number}>{streak}</span>

        {/* Texto Opcional */}
        {showLabel && streak < 5 && (
          <span className="text-[10px] opacity-75">dias</span>
        )}

        {/* Indicador de Alto Streak */}
        {isHighStreak && (
          <motion.span
            animate={{ opacity: [1, 0.7, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="text-[10px] ml-1"
          >
            ✨
          </motion.span>
        )}
      </motion.div>

      {/* Brilho de Fundo para Alto Streak */}
      {isHighStreak && (
        <motion.div
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="absolute inset-0 rounded-full bg-orange-500/20 blur-lg -z-10"
          style={{ willChange: 'opacity' }}
        />
      )}

      {/* Bônus Indicator */}
      {streak > 0 && (
        <div className="absolute top-0 right-0 translate-x-2 -translate-y-2">
          <motion.div
            animate={{ scale: [1, 1.15, 1] }}
            transition={{
              duration: 0.8,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
            className="bg-yellow-400 text-orange-900 text-[10px] font-black px-1.5 py-0.5 rounded-full"
            style={{ willChange: 'transform' }}
          >
            +{bonusPercent}%
          </motion.div>
        </div>
      )}
    </div>
  );
};

export default StreakBadge;
