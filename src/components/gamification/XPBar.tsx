/**
 * XPBar - Barra de Experiência Animada
 * 
 * Mostra:
 * - Barra de progresso animada (0-100%)
 * - Texto: "XP: [Atual] / [Necessário]"
 * - Percentual de progresso para próximo nível
 * - Estilo Neon com brilho dourado
 * 
 * Features:
 * - Animação suave com framer-motion
 * - Segue updates de XP em tempo real
 * - Detecta level-up e mostra transição
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

interface XPBarProps {
  currentXp: number;
  totalXp: number;
  xpForNextLevel: number;
  level: number;
  showLabel?: boolean;
  animated?: boolean;
  glowIntensity?: 'low' | 'medium' | 'high';
  compact?: boolean;
}

export const XPBar: React.FC<XPBarProps> = ({
  currentXp,
  totalXp,
  xpForNextLevel,
  level,
  showLabel = true,
  animated = true,
  glowIntensity = 'high',
  compact = false,
}) => {
  /**
   * Calcula percentual de progresso para próximo nível
   * Usa a diferença entre XP necessário para current e next level
   */
  const calculateProgress = useMemo(() => {
    // Total necessário para CHEGAR a próximo nível acumulado
    const totalXpThisLevel = totalXp;
    const totalXpNextLevel = totalXp + xpForNextLevel;
    
    if (totalXpNextLevel === totalXpThisLevel) return 0;
    
    const progress = ((currentXp - totalXpThisLevel) / xpForNextLevel) * 100;
    return Math.min(100, Math.max(0, progress));
  }, [currentXp, totalXp, xpForNextLevel]);

  /**
   * Define cor do glow baseado em intensidade
   */
  const glowColor = {
    low: 'rgba(250, 204, 21, 0.2)',
    medium: 'rgba(250, 204, 21, 0.4)',
    high: 'rgba(250, 204, 21, 0.6)',
  }[glowIntensity];

  /**
   * Classe da barra baseado em tamanho
   */
  const barHeight = compact ? 'h-1.5' : 'h-2';
  const containerPadding = compact ? 'p-0 space-y-1' : 'space-y-2';
  const textSize = compact ? 'text-xs' : 'text-sm';

  return (
    <div className={`w-full ${containerPadding}`}>
      {/* Label com info */}
      {showLabel && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <motion.div
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
              style={{ willChange: 'transform' }}
            >
              <Sparkles className={`${compact ? 'w-3 h-3' : 'w-4 h-4'} text-yellow-400`} />
            </motion.div>
            <span className={`${textSize} font-semibold text-yellow-200/70 uppercase`}>
              Experiência
            </span>
          </div>
          <span className={`${textSize} font-mono text-yellow-200/50`}>
            {currentXp} / {xpForNextLevel}
          </span>
        </div>
      )}

      {/* Barra de progresso */}
      <div className={`relative ${barHeight} rounded-full overflow-hidden bg-yellow-950/30 border border-yellow-500/20`}>
        {/* Efeito de brilho */}
        <motion.div
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
          className={`absolute inset-0 rounded-full`}
          style={{
            background: `radial-gradient(circle, ${glowColor}, transparent)`,
            willChange: 'opacity',
          }}
        />

        {/* Barra de preenchimento (animada) */}
        {animated ? (
          <motion.div
            layout
            layoutId="xp-bar-fill"
            initial={{ width: '0%' }}
            animate={{ width: `${calculateProgress}%` }}
            transition={{
              type: 'spring',
              stiffness: 50,
              damping: 20,
              duration: 0.6,
            }}
            className="h-full bg-gradient-to-r from-yellow-400 to-yellow-300 shadow-[0_0_15px_rgba(250,204,21,0.8)]"
            style={{ willChange: 'width' }}
          />
        ) : (
          <div
            className="h-full bg-gradient-to-r from-yellow-400 to-yellow-300 shadow-[0_0_15px_rgba(250,204,21,0.8)]"
            style={{ width: `${calculateProgress}%` }}
          />
        )}

        {/* Indicador de movimento (shimmer) */}
        {animated && (
          <motion.div
            animate={{
              x: ['-100%', '100%'],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'linear',
            }}
            className="absolute inset-y-0 w-1/4 bg-gradient-to-r from-transparent via-white/20 to-transparent"
            style={{ willChange: 'transform' }}
          />
        )}
      </div>

      {/* Percentual de progresso (opcional) */}
      {showLabel && !compact && (
        <p className="text-xs text-yellow-200/50">
          {Math.round(calculateProgress)}% até Nível {level + 1}
        </p>
      )}
    </div>
  );
};

export default XPBar;
