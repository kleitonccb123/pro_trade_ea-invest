/**
 * LockedRobotModal - Modal para robôs bloqueados
 * 
 * Exibe:
 * - Cadeado grande e brilhante
 * - Informações sobre o robô
 * - Custo de desbloqueio
 * - Botões de ação (Desbloquear com Pontos / Upgrade Plano)
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Lock,
  Zap,
  CreditCard,
  TrendingUp,
  Flame,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from '@/components/ui/dialog';
import { MicroTransactionNotification } from './MicroTransactionNotification';

interface RobotInfo {
  id: string;
  name: string;
  creator?: string;
  country?: string;
  strategy: string;
  description: string;
  unlock_cost: number;
  profit_15d: number;
  profit_7d: number;
  profit_24h: number;
  win_rate: number;
  total_trades: number;
  is_on_fire: boolean;
}

interface LockedRobotModalProps {
  robot: RobotInfo | null;
  isOpen: boolean;
  onClose: () => void;
  userTradePoints: number;
  onUnlockWithPoints?: (robotId: string) => Promise<void>;
  onUpgradePlan?: () => void;
}

export const LockedRobotModal: React.FC<LockedRobotModalProps> = ({
  robot,
  isOpen,
  onClose,
  userTradePoints,
  onUnlockWithPoints,
  onUpgradePlan,
}) => {
  const [isUnlocking, setIsUnlocking] = React.useState(false);
  const [unlocked, setUnlocked] = React.useState(false);
  const [showMicroNotification, setShowMicroNotification] = React.useState(false);
  const [licenseError, setLicenseError] = React.useState<{
    type: 'license_required' | 'plan_limit_reached',
    currentPlan: string,
    limit?: number,
    unlockedCount?: number,
  } | null>(null);

  if (!robot) return null;

  const canUnlock = userTradePoints >= robot.unlock_cost;
  const pointsShortfall = robot.unlock_cost - userTradePoints;

  const handleUnlock = async () => {
    if (!canUnlock || !onUnlockWithPoints) return;

    setIsUnlocking(true);
    setLicenseError(null);
    try {
      // Animação de desbloqueio
      setUnlocked(true);
      
      // Aguardar um pouco para ver a animação
      await new Promise(resolve => setTimeout(resolve, 800));
      
      await onUnlockWithPoints(robot.id);
      
      // Fechar após a animação
      await new Promise(resolve => setTimeout(resolve, 500));
      onClose();
    } catch (error: any) {
      console.error('Erro ao desbloquear:', error);
      setUnlocked(false);
      
      // 🔒 Verifica se é erro de licença
      const errorDetail = error?.response?.data?.detail;
      if (typeof errorDetail === 'object' && errorDetail?.error) {
        if (errorDetail.error === 'license_required') {
          setLicenseError({
            type: 'license_required',
            currentPlan: errorDetail.current_plan || 'START',
          });
        } else if (errorDetail.error === 'plan_limit_reached') {
          setLicenseError({
            type: 'plan_limit_reached',
            currentPlan: errorDetail.current_plan || 'START',
            limit: errorDetail.limit,
            unlockedCount: errorDetail.unlocked_count,
          });
        }
      }
    } finally {
      setIsUnlocking(false);
    }
  };

  const strategyIcons: Record<string, string> = {
    grid: '📊',
    rsi: '📈',
    macd: '🔄',
    dca: '💧',
    combined: '⚡',
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 border border-amber-500/20 shadow-[0_0_50px_-10px_rgba(251,146,60,0.2)] p-0 overflow-hidden flex items-center justify-center">
        <DialogClose className="absolute right-4 top-4 z-10 text-slate-400 hover:text-slate-200" />

        {/* Unlock Success Overlay */}
        <AnimatePresence>
          {unlocked && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-gradient-to-b from-emerald-500/20 to-transparent rounded-lg flex items-center justify-center flex-col gap-4 z-50"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 100 }}
                className="text-7xl drop-shadow-lg"
              >
                ✨
              </motion.div>
              <motion.h3
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="text-3xl font-black text-emerald-400 text-center"
              >
                Desbloqueado!
              </motion.h3>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="relative space-y-6 p-8">
          {/* Header Section */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center space-y-4"
          >
            {/* Lock Icon */}
            <motion.div
              animate={{
                scale: unlocked ? 0.5 : 1,
                opacity: unlocked ? 0 : 1,
              }}
              transition={{
                duration: unlocked ? 0.6 : 0.3,
                repeat: unlocked ? 0 : Infinity,
              }}
              className={`text-6xl mx-auto w-fit drop-shadow-[0_0_20px_rgba(251,146,60,0.8)] ${
                unlocked ? 'pointer-events-none' : ''
              }`}
              style={{ willChange: unlocked ? 'auto' : 'opacity, scale' }}
            >
              {unlocked ? '✨' : '🔒'}
            </motion.div>

            {/* Robot Title */}
            <div className="space-y-2">
              <h2 className="text-3xl md:text-4xl font-black bg-gradient-to-r from-amber-400 to-orange-400 bg-clip-text text-transparent">
                {robot.name}
              </h2>
              <div className="flex items-center justify-center gap-2 text-slate-400">
                <span className="text-sm">{strategyIcons[robot.strategy]}</span>
                <span className="uppercase font-bold tracking-wider">{robot.strategy}</span>
              </div>
            </div>

            {/* Creator Card */}
            {robot.creator && robot.country && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="flex items-center justify-center gap-3 p-4 rounded-xl bg-gradient-to-r from-slate-800/50 to-slate-800/30 border border-slate-700/50 max-w-sm mx-auto"
              >
                <span className="text-3xl">{robot.country}</span>
                <div className="text-left border-l border-slate-600 pl-3">
                  <p className="text-xs text-slate-400 uppercase tracking-wide">Criador</p>
                  <p className="font-bold text-slate-100 text-sm">{robot.creator}</p>
                </div>
              </motion.div>
            )}

            {/* ON FIRE Badge */}
            {robot.is_on_fire && (
              <motion.div
                animate={{ opacity: [0.8, 1, 0.8] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                className="flex items-center justify-center gap-2 text-orange-400 font-bold px-4 py-2 rounded-full bg-orange-500/10 border border-orange-500/30 w-fit mx-auto"
                style={{ willChange: 'opacity' }}
              >
                <Flame className="w-4 h-4" />
                <span className="text-sm">PERFORMANCE ARDENTE!</span>
              </motion.div>
            )}
          </motion.div>

          {/* Stats Grid - Responsive */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-3"
          >
          {/* 15D Profit */}
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/15 transition-colors">
              <p className="text-xs text-emerald-200/60 mb-1 font-semibold uppercase tracking-tight">
                Lucro 15D
              </p>
              <p className="text-lg md:text-xl font-black text-emerald-400">
                ${robot.profit_15d.toFixed(0)}
              </p>
            </div>

            {/* Win Rate */}
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/15 transition-colors">
              <p className="text-xs text-emerald-200/60 mb-1 font-semibold uppercase tracking-tight">
                Taxa Vitória
              </p>
              <p className="text-lg md:text-xl font-black text-emerald-400">
                {robot.win_rate.toFixed(1)}%
              </p>
            </div>

            {/* 7D Profit */}
            <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 hover:bg-yellow-500/15 transition-colors">
              <p className="text-xs text-yellow-200/60 mb-1 font-semibold uppercase tracking-tight">
                Lucro 7D
              </p>
              <p className="text-lg md:text-xl font-black text-yellow-400">
                ${robot.profit_7d.toFixed(0)}
              </p>
            </div>

            {/* Total Trades */}
            <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/15 transition-colors">
              <p className="text-xs text-purple-200/60 mb-1 font-semibold uppercase tracking-tight">
                Operações
              </p>
              <p className="text-lg md:text-xl font-black text-purple-400">
                {robot.total_trades}
              </p>
            </div>
          </motion.div>

          {/* 🔒 LICENSE ERROR STATE */}
          {licenseError && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 }}
              className="relative p-6 rounded-xl border-2 border-red-500/50 bg-red-500/5 text-center space-y-4 overflow-hidden"
            >
              <motion.div
                animate={{ opacity: [0.5, 0.8, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute inset-0 bg-gradient-to-r from-red-500/10 to-transparent"
              />

              <div className="relative space-y-3">
                <p className="text-sm text-red-200/70 uppercase font-bold tracking-wider">
                  🔒 Acesso Restrito ao Plano
                </p>
                
                {licenseError.type === 'license_required' && (
                  <div className="space-y-2">
                    <p className="text-lg font-bold text-red-300">
                      Seu plano {licenseError.currentPlan} não permite desbloqueio de robôs
                    </p>
                    <p className="text-xs text-red-200/80">
                      Faça upgrade para PRO ou superior para começar a desbloquear robôs estratégicos
                    </p>
                    
                    {/* Plan Comparison */}
                    <div className="mt-4 space-y-2 text-left bg-slate-950/50 p-3 rounded-lg border border-slate-700/50">
                      <div className="flex justify-between text-xs">
                        <span className="text-red-300">Seu Plano ({licenseError.currentPlan}):</span>
                        <span className="font-bold">0 robôs</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-emerald-300">Plano PRO:</span>
                        <span className="font-bold">5 robôs</span>
                      </div>
                    </div>
                  </div>
                )}

                {licenseError.type === 'plan_limit_reached' && (
                  <div className="space-y-2">
                    <p className="text-lg font-bold text-red-300">
                      Limite de Plano Atingido
                    </p>
                    <p className="text-xs text-red-200/80">
                      Você desbloqueou {licenseError.unlockedCount} de {licenseError.limit} robôs permitidos no plano {licenseError.currentPlan}
                    </p>
                    
                    {/* Plan Comparison */}
                    <div className="mt-4 space-y-2 text-left bg-slate-950/50 p-3 rounded-lg border border-slate-700/50">
                      <div className="flex justify-between text-xs">
                        <span className="text-yellow-300">Seu Plano ({licenseError.currentPlan}):</span>
                        <span className="font-bold">{licenseError.unlockedCount}/{licenseError.limit} robôs</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-emerald-300">Plano PREMIUM:</span>
                        <span className="font-bold">15 robôs</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* NORMAL UNLOCK STATE (shown only if no license error) */}
          {!licenseError && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 }}
              className="relative p-6 rounded-xl border-2 border-amber-500/50 bg-amber-500/5 text-center space-y-4 overflow-hidden"
            >
              {/* Animated Background */}
              <motion.div
                animate={{ opacity: [0.5, 0.8, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute inset-0 bg-gradient-to-r from-amber-500/10 to-transparent"
              />

              <div className="relative space-y-3">
                <p className="text-sm text-amber-200/70 uppercase font-bold tracking-wider">
                  Custo para Desbloquear
                </p>
                <div className="flex items-center justify-center gap-3 flex-wrap">
                  <Lock className="w-8 h-8 text-amber-400 drop-shadow-lg" />
                  <span className="text-4xl md:text-5xl font-black text-amber-400">
                    {robot.unlock_cost}
                  </span>
                  <span className="text-2xl md:text-3xl">⭐</span>
                </div>
                <p className="text-xs text-amber-200/60 uppercase tracking-wider">TradePoints</p>
              </div>

              {/* Points Status */}
              {!canUnlock && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="relative bg-red-500/20 border border-red-500/40 rounded-lg p-4 text-red-200"
                >
                  <p className="text-sm font-bold mb-1">⚠️ Pontos Insuficientes</p>
                  <p className="text-xs mb-2">
                    Você precisa de <span className="font-bold text-red-300">{pointsShortfall}</span> pontos a mais
                  </p>
                  <button
                    onClick={() => setShowMicroNotification(true)}
                    className="w-full py-2 px-3 rounded-lg bg-yellow-500/20 border border-yellow-500/40 text-yellow-200 text-xs font-semibold hover:bg-yellow-500/30 transition-colors flex items-center justify-center gap-1.5"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    Compra Rápida de Pontos
                  </button>
                </motion.div>
              )}

              {canUnlock && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="relative bg-emerald-500/20 border border-emerald-500/40 rounded-lg p-4 text-emerald-200"
                >
                  <p className="text-sm font-bold mb-1">✓ Você tem pontos suficientes!</p>
                  <p className="text-xs">
                    Saldo após: <span className="font-bold text-emerald-300">{(userTradePoints - robot.unlock_cost).toLocaleString()} ⭐</span>
                  </p>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* Action Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="space-y-3"
          >
            {/* License Error State: Show Upgrade Button */}
            {licenseError ? (
              <>
                <motion.button
                  whileHover={{ scale: 1.02, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={onUpgradePlan}
                  className="w-full py-4 rounded-xl font-bold text-base transition-all flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-400 hover:to-green-500 text-slate-950 shadow-lg drop-shadow-[0_0_15px_rgba(52,211,153,0.6)]"
                >
                  🚀
                  <span>Assinar Plano PRO</span>
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={onClose}
                  className="w-full py-2 rounded-lg font-semibold text-sm text-slate-400 hover:text-slate-300 transition-colors hover:bg-slate-800/30"
                >
                  ✕ Fechar
                </motion.button>
              </>
            ) : (
              <>
                {/* Normal State: Show Unlock Buttons */}
                <motion.button
                  whileHover={canUnlock && !isUnlocking && !unlocked ? { scale: 1.02, y: -2 } : {}}
                  whileTap={canUnlock && !isUnlocking && !unlocked ? { scale: 0.98 } : {}}
                  onClick={handleUnlock}
                  disabled={!canUnlock || isUnlocking || unlocked}
                  className={`w-full py-3 md:py-4 rounded-xl font-bold text-sm md:text-base transition-all flex items-center justify-center gap-2
                    ${
                      canUnlock && !isUnlocking && !unlocked
                        ? 'bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-400 hover:to-green-500 text-slate-950 shadow-lg drop-shadow-[0_0_15px_rgba(52,211,153,0.6)]'
                        : 'bg-gradient-to-r from-slate-600 to-slate-700 text-slate-300 cursor-not-allowed opacity-70'
                    }`}
                >
                  {isUnlocking || unlocked ? (
                    <>
                      <motion.div
                        animate={{ rotate: 180 }}
                        transition={{ duration: 1.2, repeat: Infinity, ease: 'linear', repeatType: 'reverse' }}
                        style={{ willChange: 'transform' }}
                      >
                        <Zap className="w-5 h-5" />
                      </motion.div>
                      <span>{unlocked ? '✓ Desbloqueado!' : 'Desbloqueando...'}</span>
                    </>
                  ) : (
                    <>
                      <Lock className="w-5 h-5" />
                      <span>Desbloquear com Pontos</span>
                    </>
                  )}
                </motion.button>

                {/* Secondary Button: Upgrade Plan */}
                <motion.button
                  whileHover={!isUnlocking && !unlocked ? { scale: 1.02, y: -2 } : {}}
                  whileTap={!isUnlocking && !unlocked ? { scale: 0.98 } : {}}
                  onClick={onUpgradePlan}
                  disabled={isUnlocking || unlocked}
                  className={`w-full py-3 md:py-4 rounded-xl font-bold text-sm md:text-base transition-all flex items-center justify-center gap-2
                    ${
                      !isUnlocking && !unlocked
                        ? 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg drop-shadow-[0_0_15px_rgba(147,103,255,0.6)]'
                        : 'bg-gradient-to-r from-slate-600 to-slate-700 text-slate-300 cursor-not-allowed opacity-70'
                    }`}
                >
                  <CreditCard className="w-5 h-5" />
                  <span>Upgrade do Plano</span>
                </motion.button>

                {/* Close Button */}
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={onClose}
                  className="w-full py-2 rounded-lg font-semibold text-sm text-slate-400 hover:text-slate-300 transition-colors hover:bg-slate-800/30"
                >
                  ✕ Fechar
                </motion.button>
              </>
            )}
          </motion.div>
        </div>

        {/* Micro Transaction Notification */}
        <MicroTransactionNotification
          visible={showMicroNotification && !canUnlock}
          shortage={pointsShortfall}
          currentBalance={userTradePoints}
          unlockCost={robot.unlock_cost}
          robotId={robot.id}
          robotName={robot.name}
          onClose={() => setShowMicroNotification(false)}
          onPurchaseAndUnlock={(result) => {
            if (result.robotUnlocked) {
              setUnlocked(true);
              setShowMicroNotification(false);
              setTimeout(() => onClose(), 1500);
            }
          }}
        />
      </DialogContent>
    </Dialog>
  );
};

export default LockedRobotModal;
