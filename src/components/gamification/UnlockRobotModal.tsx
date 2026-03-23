/**
 * UnlockRobotModal - Modal de Desbloqueio de Robô
 * 
 * Exibe:
 * - Confirmação de desbloqueio com custo em TradePoints
 * - Animação de cadeado abrindo (Padlock)
 * - Ícone do robô
 * - Preço em neon amarelo
 * - Botões: Confirmar e Cancelar
 * 
 * Features:
 * - Estilo Cassino Neon (dark + neon borders)
 * - Animação de cadeado abrindo com Framer Motion
 * - Status de loading durante chamada API
 * - Feedback com sons opcional
 * - Layout responsive
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, LockOpen, X, AlertCircle } from 'lucide-react';

interface UnlockRobotModalProps {
  isOpen: boolean;
  robotId: string;
  robotName: string;
  robotType: 'elite' | 'common';
  unlockCost: number;
  currentBalance: number;
  onConfirm: (robotId: string) => Promise<void>;
  onClose: () => void;
}

/**
 * Componente Modal para desbloquear robô
 * 
 * @param isOpen - Se o modal está visível
 * @param robotId - ID do robô a desbloquear
 * @param robotName - Nome exibido do robô
 * @param robotType - Tipo: 'elite' (1500 pts) ou 'common' (500 pts)
 * @param unlockCost - Custo em TradePoints
 * @param currentBalance - Saldo atual do usuário
 * @param onConfirm - Callback ao confirmar desbloquear
 * @param onClose - Callback ao fechar modal
 */
export const UnlockRobotModal: React.FC<UnlockRobotModalProps> = ({
  isOpen,
  robotId,
  robotName,
  robotType,
  unlockCost,
  currentBalance,
  onConfirm,
  onClose,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Determina se tem saldo suficiente
  const hasEnoughBalance = currentBalance >= unlockCost;
  const shortage = unlockCost - currentBalance;

  /**
   * Manipula confirmação de desbloqueio
   */
  const handleConfirm = async () => {
    if (!hasEnoughBalance) {
      setError(`Você precisa de ${shortage} pontos a mais`);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Chama callback na prop (que faz a chamada API)
      await onConfirm(robotId);

      // Fecha modal após sucesso (sucesso tratado no hook)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Erro ao desbloquear';
      console.error('[UnlockRobotModal] Erro:', err);
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Canvas para efeitos visuais futuros */}
      {/* Modal Backdrop */}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              onClick={onClose}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
              style={{ willChange: 'opacity' }}
            />

            {/* Modal */}
            <motion.div
              initial={{ opacity: 0, scale: 0.5, y: 100 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.5, y: 100 }}
              transition={{
                type: 'spring',
                stiffness: 120,
                damping: 20,
                duration: 0.4,
              }}
              className="fixed inset-0 flex items-center justify-center z-50 px-3 sm:px-4 py-4 sm:py-6"
              style={{ willChange: 'transform' }}
            >
              {/* Card Principal - Casino Neon */}
              <div className="relative bg-gradient-to-b from-slate-900/98 via-slate-800/98 to-slate-900/98 border-2 border-purple-500/60 rounded-xl sm:rounded-2xl p-4 sm:p-6 text-center overflow-hidden shadow-2xl w-full max-w-xs sm:max-w-sm max-h-[95vh] overflow-y-auto">
                {/* Glow Background */}
                <div className="absolute inset-0 bg-gradient-to-t from-purple-500/15 via-transparent to-purple-500/10 pointer-events-none" />

                {/* Neon Border Glow */}
                <div className="absolute inset-0 rounded-2xl shadow-[0_0_30px_rgba(168,85,247,0.6),inset_0_0_30px_rgba(168,85,247,0.15)] pointer-events-none" />

                {/* Close Button */}
                <button
                  onClick={onClose}
                  disabled={isLoading}
                  className="absolute top-3 right-3 sm:top-4 sm:right-4 z-10 text-gray-300 hover:text-purple-400 hover:bg-purple-500/10 p-1 sm:p-1.5 rounded-lg disabled:opacity-50 transition-all duration-200"
                  aria-label="Fechar modal"
                >
                  <X className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>

                {/* Content */}
                <div className="relative space-y-3 sm:space-y-4">
                  {/* Cadeado Animado */}
                  <motion.div
                    animate={{
                      scale: [1, 1.12, 1],
                      rotate: [0, -8, 8, 0],
                    }}
                    transition={{
                      duration: 1.8,
                      repeat: Infinity,
                      ease: 'easeInOut',
                    }}
                    className="text-4xl sm:text-5xl flex justify-center"
                    style={{ willChange: 'transform' }}
                  >
                    {hasEnoughBalance ? (
                      <motion.span
                        animate={{ y: [-5, 5, -5] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      >
                        🔓
                      </motion.span>
                    ) : (
                      <motion.span animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity }}>
                        🔒
                      </motion.span>
                    )}
                  </motion.div>

                  {/* Brilho de cadeado */}
                  <motion.div
                    animate={{ opacity: [0.3, 0.7, 0.3] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    className="absolute top-10 sm:top-12 left-1/2 transform -translate-x-1/2 w-16 sm:w-20 h-16 sm:h-20 bg-purple-400/30 rounded-full blur-2xl -z-10"
                    style={{ willChange: 'opacity' }}
                  />

                  {/* Tipo de Robô */}
                  <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="inline-block"
                  >
                    <span className={`text-xs font-bold px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-full border-2 ${
                      robotType === 'elite' 
                        ? 'bg-yellow-500/20 text-yellow-300 border-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.3)]' 
                        : 'bg-blue-500/20 text-blue-300 border-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.3)]'
                    }`}>
                      {robotType === 'elite' ? '👑 ELITE' : '⚙️ COMUM'}
                    </span>
                  </motion.div>

                  {/* Nome do Robô */}
                  <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                    className="space-y-0.5 sm:space-y-1"
                  >
                    <p className="text-xs sm:text-xs text-purple-300/70 font-semibold uppercase tracking-wide">Desbloquear Robô</p>
                    <h2 className="text-lg sm:text-2xl font-black text-white tracking-wider drop-shadow-lg">
                      {robotName}
                    </h2>
                  </motion.div>

                  {/* Divisor */}
                  <motion.div
                    animate={{ scaleX: [0.8, 1, 0.8] }}
                    transition={{ duration: 2.5, repeat: Infinity }}
                    className="h-0.5 bg-gradient-to-r from-transparent via-purple-500 to-transparent rounded-full"
                  />

                  {/* Custo em Destaque */}
                  <motion.div
                    animate={{
                      scale: [1, 1.08, 1],
                    }}
                    transition={{
                      duration: 1.2,
                      repeat: Infinity,
                      ease: 'easeInOut',
                    }}
                    className="bg-gradient-to-br from-slate-700/60 to-slate-800/60 border-2 border-purple-500/50 rounded-lg p-3 sm:p-4 space-y-2"
                    style={{ willChange: 'transform' }}
                  >
                    <p className="text-xs text-purple-300/80 font-bold uppercase tracking-wide">Custo do Desbloqueio</p>
                    <div className="text-3xl sm:text-4xl font-black text-transparent bg-gradient-to-r from-yellow-300 via-yellow-200 to-yellow-300 bg-clip-text">
                      {unlockCost} PTS
                    </div>
                    <div className="pt-2 border-t border-purple-500/30">
                      <p className="text-xs sm:text-sm text-purple-200/70 flex items-center justify-center gap-1">
                        <span className="text-xs">Saldo:</span>
                        <span className={`font-bold ${hasEnoughBalance ? 'text-emerald-400' : 'text-red-400'}`}>
                          {currentBalance} PTS
                        </span>
                      </p>
                    </div>
                  </motion.div>

                  {/* Aviso de Saldo Insuficiente */}
                  {!hasEnoughBalance && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-red-950/50 border-2 border-red-500/60 rounded-lg p-3 flex gap-2 items-start"
                    >
                      <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                      <div className="text-left">
                        <p className="text-xs font-bold text-red-300 mb-0.5">⚠️ Saldo Insuficiente!</p>
                        <p className="text-xs text-red-200/80">
                          Faltam <span className="font-bold text-red-400">{shortage} PTS</span>
                        </p>
                      </div>
                    </motion.div>
                  )}

                  {/* Erro */}
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-red-900/30 border border-red-500/50 rounded-lg p-2.5"
                    >
                      <p className="text-xs text-red-300">❌ {error}</p>
                    </motion.div>
                  )}

                  {/* Mensagem Confirmação */}
                  <div className="bg-purple-950/50 border border-purple-500/40 rounded-lg p-3">
                    <p className="text-xs text-purple-100 leading-relaxed">
                      Deseja desbloquear <span className="font-bold text-purple-300">{robotName}</span> por{' '}
                      <span className="font-bold text-yellow-300">{unlockCost}</span> pontos?
                    </p>
                    <p className="text-xs text-purple-200/50 mt-1.5">
                      Esta ação é permanente.
                    </p>
                  </div>

                  {/* Botões de Ação */}
                  <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-2 sm:pt-3">
                    {/* Cancelar */}
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={onClose}
                      disabled={isLoading}
                      className="flex-1 py-2.5 sm:py-3 bg-slate-700/80 hover:bg-slate-600/80 text-gray-200 font-bold text-xs sm:text-sm rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed border border-slate-600"
                    >
                      Cancelar
                    </motion.button>

                    {/* Confirmar */}
                    <motion.button
                      whileHover={hasEnoughBalance ? { scale: 1.05, boxShadow: '0 0 30px rgba(168, 85, 247, 1)' } : {}}
                      whileTap={hasEnoughBalance ? { scale: 0.95 } : {}}
                      onClick={handleConfirm}
                      disabled={isLoading || !hasEnoughBalance}
                      className={`flex-1 py-2.5 sm:py-3 text-xs sm:text-sm font-bold rounded-lg transition-all flex items-center justify-center gap-2 border-2 ${
                        hasEnoughBalance
                          ? 'bg-gradient-to-r from-purple-600 via-purple-500 to-purple-600 text-white hover:shadow-[0_0_20px_rgba(168,85,247,0.8)] border-purple-400'
                          : 'bg-gray-700/60 text-gray-400 cursor-not-allowed border-gray-600'
                      }`}
                      style={{ willChange: isLoading ? 'auto' : 'transform, box-shadow' }}
                    >
                      {isLoading ? (
                        <>
                          <motion.span
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity }}
                          >
                            ⏳
                          </motion.span>
                          <span className="hidden sm:inline">Desbloqueando...</span>
                          <span className="sm:hidden">...</span>
                        </>
                      ) : (
                        <>
                          🔓 <span className="hidden sm:inline">Desbloquear</span>
                        </>
                      )}
                    </motion.button>
                  </div>

                  {/* Dica */}
                  <p className="text-xs text-purple-200/40 text-center">
                    {hasEnoughBalance 
                      ? 'Clique para confirmar' 
                      : 'Complete tarefas para ganhar pontos'}
                  </p>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
};

export default UnlockRobotModal;
