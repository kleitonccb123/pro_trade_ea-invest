/**
 * DailyChestComponent - Baú Diário com Sistema de Streaks Avançado
 * 
 * Features:
 * - Estado: Disponível (brilhando) ou Aguardando (timer regressivo)
 * - Animação de abertura com tremor e explosão de moedas
 * - Feedback visual de streak com bônus
 * - Tooltip com próxima disponibilidade
 * - Som opcional de "clink" de moedas
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Gift, Lock, Sparkles } from 'lucide-react';
import confetti from 'canvas-confetti';

interface DailyChestComponentProps {
  canOpen: boolean;
  timeRemaining?: {
    hours: number;
    minutes: number;
    seconds: number;
  } | null;
  streak: number;
  isLoading?: boolean;
  onOpen: () => Promise<any>;
  onSuccess?: (reward: { points: number; xp: number; streak: number; bonus: number }) => void;
}

export const DailyChestComponent: React.FC<DailyChestComponentProps> = ({
  canOpen,
  timeRemaining,
  streak,
  isLoading = false,
  onOpen,
  onSuccess,
}) => {
  const [isOpening, setIsOpening] = useState(false);
  const [showReward, setShowReward] = useState(false);
  const [rewardData, setRewardData] = useState<any>(null);

  /**
   * Handel click para abrir baú
   */
  const handleOpenChest = async () => {
    if (!canOpen || isLoading || isOpening) return;

    try {
      setIsOpening(true);

      // Animação: tremor do baú
      await new Promise(resolve => setTimeout(resolve, 300));

      // Chama API e captura resposta com valores reais
      const apiResult = await onOpen();

      // Confetes
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { x: 0.5, y: 0.4 },
        colors: ['#fbbf24', '#fcd34d', '#f59e0b', '#d97706'],
      });

      // Anima moedas subindo
      setShowReward(true);
      setTimeout(() => {
        setShowReward(false);
      }, 2000);

      // Usa valores REAIS da API em vez de hardcoded
      const rewardPoints = apiResult?.points_won ?? apiResult?.points_reward ?? 100;
      const rewardXp = apiResult?.xp_won ?? apiResult?.xp_reward ?? 50;
      const rewardStreak = apiResult?.new_streak ?? streak + 1;
      const rewardBonus = apiResult?.streak_bonus_percent ?? Math.round(streak * 10);

      onSuccess?.({
        points: rewardPoints,
        xp: rewardXp,
        streak: rewardStreak,
        bonus: rewardBonus,
      });
    } catch (error) {
      console.error('[DailyChest] Erro ao abrir:', error);
    } finally {
      setIsOpening(false);
    }
  };

  /**
   * Formata tempo regressivo
   */
  const formatTime = () => {
    if (!timeRemaining) return '00:00:00';
    const { hours, minutes, seconds } = timeRemaining;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(
      2,
      '0'
    )}:${String(seconds).padStart(2, '0')}`;
  };

  return (
    <div className="relative inline-block">
      {/* Canvas para confetes */}
      <canvas
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 9999,
        }}
      />

      {/* Tooltip - Próxima Disponibilidade */}
      {!canOpen && timeRemaining && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute -top-16 left-1/2 transform -translate-x-1/2 bg-slate-900/95 border border-yellow-500/30 text-yellow-200 text-xs px-3 py-2 rounded whitespace-nowrap z-50 pointer-events-none"
        >
          ⏰ Próximo em {formatTime()}
        </motion.div>
      )}

      {/* Baú - Disponível */}
      {canOpen && (
        <motion.button
          animate={{
            scale: [1, 1.08, 1],
            y: [0, -8, 0],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          onClick={handleOpenChest}
          disabled={isLoading || isOpening}
          className="relative p-4 rounded-2xl overflow-hidden group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          style={{ willChange: 'transform' }}
        >
          {/* Background Gradient */}
          <div className="absolute inset-0 bg-gradient-to-br from-yellow-500 via-amber-500 to-orange-600 opacity-20" />

          {/* Brilho Neon */}
          <motion.div
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="absolute inset-0 bg-gradient-to-br from-yellow-400/30 via-transparent to-transparent rounded-2xl"
            style={{ willChange: 'opacity' }}
          />

          {/* Border Glow */}
          <div className="absolute inset-0 rounded-2xl border-2 border-yellow-400/50 shadow-[0_0_20px_rgba(250,204,21,0.5)]" />

          {/* Content */}
          <div className="relative flex flex-col items-center gap-2 z-10">
            {/* Ícone do Baú */}
            <motion.div
              animate={{
                rotate: [0, -5, 5, 0],
                scale: [1, 1.1, 1],
              }}
              transition={{
                duration: 1.8,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
              className="text-4xl flex items-center justify-center"
              style={{ willChange: 'transform' }}
            >
              🎁
            </motion.div>

            {/* Texto */}
            <div className="text-center">
              <p className="text-xs font-bold text-yellow-300 uppercase tracking-wider">
                Baú Diário
              </p>
              <p className="text-[10px] text-yellow-200/70">Clique para abrir</p>
            </div>

            {/* Streak Badge */}
            {streak > 0 && (
              <motion.div
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ duration: 1.2, repeat: Infinity }}
                className="flex items-center gap-1 text-xs font-bold text-orange-300 bg-orange-900/40 px-2 py-1 rounded-full border border-orange-500/30"
              >
                <span>🔥 {streak}</span>
              </motion.div>
            )}
          </div>
        </motion.button>
      )}

      {/* Baú - Aguardando (Bloqueado) */}
      {!canOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="relative p-4 rounded-2xl overflow-hidden"
        >
          {/* Background */}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-600 via-slate-700 to-slate-800 opacity-40" />

          {/* Brilho Atenuado */}
          <motion.div
            animate={{ opacity: [0.2, 0.4, 0.2] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="absolute inset-0 bg-slate-500/20"
            style={{ willChange: 'opacity' }}
          />

          {/* Border */}
          <div className="absolute inset-0 rounded-2xl border-2 border-slate-500/30" />

          {/* Content */}
          <div className="relative flex flex-col items-center gap-2 z-10">
            {/* Ícone Bloqueado */}
            <div className="text-4xl opacity-50">🔒</div>

            {/* Timer Grande */}
            <div className="text-center">
              <p className="text-sm font-black text-slate-300 tabular-nums">
                {formatTime()}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">Próximo baú</p>
            </div>

            {/* Streak Passado */}
            {streak > 0 && (
              <div className="flex items-center gap-1 text-xs text-slate-300">
                <span>🔥 Ofensiva: {streak} dias</span>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Animação de Abertura - Tremor */}
      <AnimatePresence>
        {isOpening && (
          <motion.div
            initial={{ scale: 1 }}
            animate={{
              scale: [1, 1.05, 0.95, 1.02, 0.98, 1],
              rotate: [0, -2, 2, -1, 1, 0],
            }}
            exit={{ scale: 1 }}
            transition={{ duration: 0.4 }}
            className="absolute inset-0 rounded-2xl border-2 border-yellow-300 pointer-events-none"
          />
        )}
      </AnimatePresence>

      {/* Moedas Voando */}
      <AnimatePresence>
        {showReward && (
          <>
            {[...Array(8)].map((_, i) => (
              <motion.div
                key={i}
                initial={{
                  opacity: 1,
                  x: 0,
                  y: 0,
                }}
                animate={{
                  opacity: 0,
                  x: Math.cos((i / 8) * Math.PI * 2) * 100,
                  y: -150 + Math.random() * 50,
                }}
                transition={{
                  duration: 1.5,
                  ease: 'easeOut',
                }}
                className="absolute top-1/2 left-1/2 pointer-events-none"
              >
                {i % 2 === 0 ? (
                  <span className="text-2xl">💰</span>
                ) : (
                  <span className="text-2xl">⭐</span>
                )}
              </motion.div>
            ))}
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

export default DailyChestComponent;
