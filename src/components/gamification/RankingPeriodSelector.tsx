/**
 * RankingPeriodSelector - Popup para selecionar período de ranking
 * 
 * Permite ao usuário alternar entre:
 * - Top 10 - Últimas 24 horas
 * - Top 10 - Última semana
 * - Top 10 - Último mês
 * 
 * Atualiza dinamicamente os dados dos robôs na página
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, TrendingUp, Calendar, X } from 'lucide-react';

interface PeriodOption {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  period: 'daily' | 'weekly' | 'monthly';
}

interface RankingPeriodSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectPeriod: (period: 'daily' | 'weekly' | 'monthly') => void;
  currentPeriod?: 'daily' | 'weekly' | 'monthly';
}

export function RankingPeriodSelector({
  isOpen,
  onClose,
  onSelectPeriod,
  currentPeriod = 'monthly',
}: RankingPeriodSelectorProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<string>(currentPeriod);

  const periodOptions: PeriodOption[] = [
    {
      id: 'daily',
      label: 'Top 10 - Últimas 24 Horas',
      description: 'Robôs com melhor desempenho do dia',
      icon: <Clock className="w-5 h-5" />,
      period: 'daily',
    },
    {
      id: 'weekly',
      label: 'Top 10 - Última Semana',
      description: 'Robôs com melhor desempenho dos últimos 7 dias',
      icon: <TrendingUp className="w-5 h-5" />,
      period: 'weekly',
    },
    {
      id: 'monthly',
      label: 'Top 10 - Último Mês',
      description: 'Robôs com melhor desempenho dos últimos 15 dias',
      icon: <Calendar className="w-5 h-5" />,
      period: 'monthly',
    },
  ];

  const handleSelectPeriod = (period: 'daily' | 'weekly' | 'monthly') => {
    setSelectedPeriod(period);
    onSelectPeriod(period);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Content */}
            <div className="bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-700/50 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
              {/* Header */}
              <div className="relative px-6 py-6 border-b border-slate-700/30 bg-gradient-to-r from-slate-900/50 to-slate-950/50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center">
                      <TrendingUp className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white">Período de Ranking</h2>
                      <p className="text-xs text-slate-400">Selecione o período para visualizar</p>
                    </div>
                  </div>
                  <button
                    onClick={onClose}
                    className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5 text-slate-400" />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="p-6 space-y-3">
                {periodOptions.map((option) => (
                  <motion.button
                    key={option.id}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleSelectPeriod(option.period)}
                    className={`w-full p-4 rounded-lg border-2 transition-all text-left ${
                      selectedPeriod === option.period
                        ? 'border-yellow-400 bg-yellow-400/10 shadow-lg shadow-yellow-400/20'
                        : 'border-slate-600/50 bg-slate-800/30 hover:border-yellow-400/50 hover:bg-slate-800/50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`mt-1 ${
                          selectedPeriod === option.period
                            ? 'text-yellow-400'
                            : 'text-slate-400 group-hover:text-yellow-400'
                        }`}
                      >
                        {option.icon}
                      </div>
                      <div className="flex-1">
                        <p className="font-semibold text-white">{option.label}</p>
                        <p className="text-sm text-slate-400">{option.description}</p>
                      </div>
                      <motion.div
                        animate={{
                          scale: selectedPeriod === option.period ? 1 : 0,
                        }}
                        className="flex-shrink-0 w-5 h-5 rounded-full bg-yellow-400 flex items-center justify-center"
                      >
                        <div className="w-2 h-2 rounded-full bg-slate-950" />
                      </motion.div>
                    </div>
                  </motion.button>
                ))}
              </div>

              {/* Footer */}
              <div className="px-6 py-4 border-t border-slate-700/30 bg-slate-950/50 flex gap-3">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={onClose}
                  className="flex-1 px-4 py-2 rounded-lg border border-slate-600 text-slate-300 font-medium hover:bg-slate-800/50 transition-colors"
                >
                  Cancelar
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={onClose}
                  className="flex-1 px-4 py-2 rounded-lg bg-gradient-to-r from-yellow-400 to-orange-500 text-slate-950 font-bold hover:from-yellow-300 hover:to-orange-400 transition-all shadow-lg shadow-yellow-400/20"
                >
                  Aplicar
                </motion.button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
