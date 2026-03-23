/**
 * DailyChestButton - Botão para abrir o baú diário
 * 
 * Funcionalidades:
 * - Abre baú uma vez por dia (24h cooldown)
 * - Mostra recompensa ganha (XP + Pontos + Streak)
 * - Dispara confetes ao ganhar
 * - Countdown automático
 * ✨ NOVO: Integrado com API real via useGamification + useDailyChestStatus
 */

import React, { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import confetti from 'canvas-confetti';
import { Gift, Flame, Clock, Loader2 } from 'lucide-react';
import { useGamification, useDailyChestStatus } from '@/hooks/use-gamification';
import { useApi } from '@/hooks/useApi';
import { useToast } from '@/hooks/use-toast';

interface DailyChestReward {
  xp_reward: number;
  points_reward: number;
  streak_count: number;
}

export const DailyChestButton: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { profile, refetch } = useGamification();
  const { post } = useApi();
  const { toast } = useToast();
  
  const [isLoading, setIsLoading] = useState(false);
  const [reward, setReward] = useState<DailyChestReward | null>(null);
  const [showRewardPopup, setShowRewardPopup] = useState(false);

  // Hook para verificar status do baú diário
  const { canOpen, timeRemaining } = useDailyChestStatus(profile);

  const triggerConfetti = () => {
    if (canvasRef.current) {
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { x: 0.5, y: 0.5 },
      });
    }
  };

  const handleOpenChest = async () => {
    if (!canOpen || isLoading || !profile) return;

    setIsLoading(true);
    try {
      // Chamar POST /api/gamification/daily-chest/open
      const response = await post('/api/gamification/daily-chest/open', {}) as any;

      if (response?.data) {
        const chestReward = response.data;
        
        setReward({
          xp_reward: chestReward.xp_reward || 0,
          points_reward: chestReward.points_reward || 0,
          streak_count: chestReward.streak_count || 0,
        });

        setShowRewardPopup(true);
        triggerConfetti();

        // Disparar toast de sucesso
        toast({
          title: '🎁 Parabéns!',
          description: `+${chestReward.points_reward} Pontos e +${chestReward.xp_reward} XP!`,
          duration: 3000,
        });

        // Atualizar profile após abertura
        await refetch();

        // Auto fechar após 3s
        setTimeout(() => {
          setShowRewardPopup(false);
        }, 3000);
      }
    } catch (error: any) {
      console.error('❌ Erro ao abrir baú:', error);
      
      // Mostrar erro ao usuário
      const errorMsg = error?.response?.data?.detail || 'Erro ao abrir baú';
      toast({
        title: 'Erro',
        description: errorMsg,
        variant: 'destructive',
        duration: 3000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <canvas ref={canvasRef} style={{ position: 'fixed', top: 0, left: 0, pointerEvents: 'none' }} />

      {/* Daily Chest Button */}
      <motion.button
        whileHover={canOpen && !isLoading ? { scale: 1.08 } : {}}
        whileTap={canOpen && !isLoading ? { scale: 0.95 } : {}}
        onClick={handleOpenChest}
        disabled={!canOpen || isLoading}
        className={`relative p-5 rounded-xl font-bold transition-all overflow-hidden group min-w-[160px] ${
          !canOpen
            ? 'opacity-60 cursor-not-allowed'
            : 'cursor-pointer hover:shadow-[0_0_30px_rgba(250,204,21,0.4)]'
        }`}
      >
        {/* Gradient Background */}
        <div
          className={`absolute inset-0 rounded-xl transition-all ${
            !canOpen
              ? 'bg-gradient-to-r from-slate-600 to-slate-700'
              : 'bg-gradient-to-r from-yellow-500 via-amber-500 to-orange-500'
          }`}
          style={{ willChange: 'background' }}
        />

        {/* Glow Effect */}
        {canOpen && (
          <motion.div
            animate={{ opacity: [0.4, 0.8, 0.4] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute inset-0 rounded-xl bg-gradient-to-r from-yellow-400/30 to-transparent"
            style={{ willChange: 'opacity' }}
          />
        )}

        {/* Content */}
        <div className="relative flex flex-col items-center gap-1 text-sm">
          {!canOpen && timeRemaining ? (
            <>
              <Clock className="w-4 h-4" />
              <span className="text-xs font-semibold">
                {String(timeRemaining.hours).padStart(2, '0')}:{String(timeRemaining.minutes).padStart(2, '0')}:{String(timeRemaining.seconds).padStart(2, '0')}
              </span>
            </>
          ) : isLoading ? (
            <>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                style={{ willChange: 'transform' }}
              >
                <Loader2 className="w-5 h-5" />
              </motion.div>
              <span className="text-xs font-semibold">Abrindo...</span>
            </>
          ) : (
            <>
              <motion.div
                animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.1, 1] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                style={{ willChange: 'transform' }}
              >
                <Gift className="w-5 h-5" />
              </motion.div>
              <span className="text-xs font-semibold">Baú Diário</span>
            </>
          )}
        </div>
      </motion.button>

      {/* Reward Popup */}
      <AnimatePresence>
        {showRewardPopup && reward && (
          <motion.div
            initial={{ opacity: 0, scale: 0.5, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.5, y: 20 }}
            className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50"
            style={{ willChange: 'transform' }}
          >
            <motion.div
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 0.5 }}
              className="relative bg-gradient-to-b from-yellow-950/90 to-amber-950/90 border-2 border-yellow-400 rounded-2xl p-8 text-center backdrop-blur-xl shadow-2xl
                drop-shadow-[0_0_30px_rgba(250,204,21,0.6)]"
              style={{ willChange: 'transform' }}
            >
              {/* Celebrate Icon */}
              <motion.div
                animate={{ scale: [1, 1.15, 1] }}
                transition={{ duration: 0.6, repeat: Infinity, ease: 'easeInOut' }}
                className="text-6xl mb-4"
                style={{ willChange: 'scale' }}
              >
                🎁
              </motion.div>

              <h3 className="text-2xl font-black text-yellow-400 mb-2">
                Parabéns!
              </h3>

              {/* Rewards Grid */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                {/* XP Reward */}
                <div className="bg-purple-500/20 border border-purple-500/40 rounded-lg p-3">
                  <p className="text-xs text-purple-200 mb-1 uppercase font-semibold">XP Ganho</p>
                  <p className="text-xl font-black text-purple-400">
                    +{reward.xp_reward}
                  </p>
                </div>

                {/* Points Reward */}
                <div className="bg-yellow-500/20 border border-yellow-500/40 rounded-lg p-3">
                  <p className="text-xs text-yellow-200 mb-1 uppercase font-semibold">Pontos</p>
                  <p className="text-xl font-black text-yellow-400">
                    +{reward.points_reward}
                  </p>
                </div>
              </div>

              {/* Streak */}
              <div className="flex items-center justify-center gap-2 text-sm bg-emerald-500/20 border border-emerald-500/40 rounded-lg p-3">
                <Flame className="w-5 h-5 text-orange-400" />
                <span className="font-semibold text-emerald-300">
                  Streak: {reward.streak_count} dias
                </span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default DailyChestButton;
