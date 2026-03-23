/**
 * LevelUpModal - Modal de Celebração ao fazer Level Up
 * 
 * Exibe:
 * - Animação de celebração com escalas
 * - Ícone de troféu com brilho
 * - "PARABÉNS! VOCÊ ATINGIU O NÍVEL [X]!"
 * - Confetes disparados
 * - Botão "Continuar Lucrando"
 * 
 * Features:
 * - Estilo Cassino Neon
 * - Animações exclusivas para level up
 * - Confetes com canvas-confetti
 * - Auto-close após X segundos (opcional)
 * - Som de celebração (opcional)
 */

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import confetti from 'canvas-confetti';
import { Trophy, Zap } from 'lucide-react';

interface LevelUpModalProps {
  isOpen: boolean;
  newLevel: number;
  onClose: () => void;
  autoClose?: boolean;
  autoCloseDelay?: number;
}

export const LevelUpModal: React.FC<LevelUpModalProps> = ({
  isOpen,
  newLevel,
  onClose,
  autoClose = true,
  autoCloseDelay = 5000,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  /**
   * Dispara confetes quando modal abre
   */
  useEffect(() => {
    if (isOpen && canvasRef.current) {
      // Confete principal (dourado)
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { x: 0.5, y: 0.4 },
        colors: ['#fbbf24', '#f59e0b', '#d97706', '#fef3c7'],
      });

      // Confete lateral esquerdo
      setTimeout(() => {
        confetti({
          particleCount: 50,
          angle: 60,
          spread: 55,
          origin: { x: 0, y: 0.5 },
          colors: ['#fbbf24', '#f59e0b'],
        });
      }, 100);

      // Confete lateral direito
      setTimeout(() => {
        confetti({
          particleCount: 50,
          angle: 120,
          spread: 55,
          origin: { x: 1, y: 0.5 },
          colors: ['#fbbf24', '#f59e0b'],
        });
      }, 200);
    }
  }, [isOpen]);

  /**
   * Auto-close após delay
   */
  useEffect(() => {
    if (isOpen && autoClose) {
      const timer = setTimeout(onClose, autoCloseDelay);
      return () => clearTimeout(timer);
    }
  }, [isOpen, autoClose, autoCloseDelay, onClose]);

  return (
    <>
      {/* Canvas para confetes */}
      <canvas
        ref={canvasRef}
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

      {/* Modal Backdrop */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop (dimmed background) */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              onClick={onClose}
              className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
              style={{ willChange: 'opacity' }}
            />

            {/* Modal */}
            <motion.div
              initial={{ opacity: 0, scale: 0.3, y: 100 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.3, y: 100 }}
              transition={{
                type: 'spring',
                stiffness: 100,
                damping: 15,
                duration: 0.5,
              }}
              className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50"
              style={{ willChange: 'transform' }}
            >
              {/* Card Principal - Casino Neon */}
              <div className="relative bg-gradient-to-b from-amber-950/95 via-yellow-900/90 to-amber-950/95 border-4 border-yellow-300 rounded-3xl p-12 text-center overflow-hidden shadow-2xl max-w-sm">
                {/* Glow Background */}
                <div className="absolute inset-0 bg-gradient-to-t from-yellow-500/10 via-transparent to-yellow-500/5 pointer-events-none" />

                {/* Border Glow */}
                <div className="absolute inset-0 rounded-3xl shadow-[0_0_40px_rgba(250,204,21,0.6),inset_0_0_40px_rgba(250,204,21,0.2)] pointer-events-none" />

                {/* Content */}
                <div className="relative space-y-6">
                  {/* Troféu Animado */}
                  <motion.div
                    animate={{
                      scale: [1, 1.15, 1],
                      rotate: [0, -5, 5, 0],
                      y: [0, -20, 0],
                    }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      ease: 'easeInOut',
                    }}
                    className="text-7xl flex justify-center"
                    style={{ willChange: 'transform' }}
                  >
                    🏆
                  </motion.div>

                  {/* Brilho de troféu */}
                  <motion.div
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    className="absolute top-20 left-1/2 transform -translate-x-1/2 w-32 h-32 bg-yellow-400/30 rounded-full blur-2xl -z-10"
                    style={{ willChange: 'opacity' }}
                  />

                  {/* Título */}
                  <div className="space-y-2">
                    <h2 className="text-3xl md:text-4xl font-black text-yellow-300 tracking-widest">
                      PARABÉNS!
                    </h2>
                    <p className="text-lg md:text-xl font-bold text-yellow-100">
                      Você atingiu o
                    </p>
                  </div>

                  {/* Novo Nível - Grande */}
                  <motion.div
                    animate={{
                      scale: [1, 1.1, 1],
                    }}
                    transition={{
                      duration: 1.2,
                      repeat: Infinity,
                      ease: 'easeInOut',
                    }}
                    className="space-y-1"
                    style={{ willChange: 'transform' }}
                  >
                    <div className="text-6xl md:text-7xl font-black text-transparent bg-gradient-to-r from-yellow-200 via-yellow-100 to-yellow-300 bg-clip-text">
                      NÍVEL {newLevel}
                    </div>
                    <div className="flex items-center justify-center gap-2 text-yellow-400">
                      <Zap className="w-5 h-5" />
                      <span className="text-sm font-bold">NOVA MILHA ALCANÇADA</span>
                      <Zap className="w-5 h-5" />
                    </div>
                  </motion.div>

                  {/* Efeito de raios ao fundo */}
                  <div className="absolute top-0 left-0 right-0 h-32 pointer-events-none">
                    {[...Array(3)].map((_, i) => (
                      <motion.div
                        key={i}
                        animate={{
                          opacity: [0, 0.5, 0],
                          scaleY: [0, 1, 0],
                        }}
                        transition={{
                          duration: 1.5,
                          delay: i * 0.3,
                          repeat: Infinity,
                        }}
                        className="absolute left-1/2 top-0 w-1 h-16 bg-gradient-to-b from-yellow-300 to-transparent -translate-x-1/2"
                        style={{
                          transformOrigin: 'center top',
                          willChange: 'opacity, transform',
                          marginLeft: `${(i - 1) * 60}px`,
                        }}
                      />
                    ))}
                  </div>

                  {/* Divisor */}
                  <div className="w-full h-1 bg-gradient-to-r from-transparent via-yellow-400 to-transparent rounded-full" />

                  {/* Info Box */}
                  <div className="bg-yellow-950/50 border border-yellow-500/40 rounded-xl p-4 space-y-2">
                    <p className="text-sm text-yellow-200/70">
                      Você ganhou mais força na Arena de Lucros! 💪
                    </p>
                    <p className="text-xs text-yellow-200/50">
                      Continue ganhando XP para desbloquear novos robôs e recompensas
                    </p>
                  </div>

                  {/* Botão de Ação */}
                  <motion.button
                    whileHover={{ scale: 1.05, boxShadow: '0 0 30px rgba(250, 204, 21, 1)' }}
                    whileTap={{ scale: 0.95 }}
                    onClick={onClose}
                    className="w-full py-3 bg-gradient-to-r from-yellow-400 via-yellow-300 to-yellow-400 text-amber-950 font-black text-lg rounded-lg transition-all shadow-lg hover:shadow-[0_0_20px_rgba(250,204,21,0.6)]"
                    style={{ willChange: 'transform, box-shadow' }}
                  >
                    Continuar Lucrando 🚀
                  </motion.button>

                  {/* Dica */}
                  <p className="text-xs text-yellow-200/40">
                    Clique para fechar ou aguarde 5 segundos...
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

export default LevelUpModal;
