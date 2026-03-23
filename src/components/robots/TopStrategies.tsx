'use client';

import { Robot } from '@/types/robot';
import { Lock, Unlock, Loader, TrendingUp, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useState, useMemo, memo } from 'react';
import { useRankedStrategies } from '@/hooks/useRankedStrategies';

interface TopStrategiesProps {
  robots?: (Robot & { profit?: number; winRate?: number })[];
  onCardClick?: (robot: Robot) => void;
}

const PERIOD_FILTERS = [
  { label: '7 dias', value: '7d', multiplier: 1 },
  { label: '15 dias', value: '15d', multiplier: 1.8 },
  { label: '30 dias', value: '30d', multiplier: 3.5 },
];

// Memoized Card Component for better performance
const StrategyCard = memo(({
  strategy,
  onCardClick,
  unlockedCards
}: {
  strategy: any;
  onCardClick: (strategy: any) => void;
  unlockedCards: Set<string>;
}) => {
  return (
    <div
      onClick={() => onCardClick(strategy)}
      className="group cursor-pointer"
      style={{ willChange: 'transform' }}
    >
      {/* Card Container */}
      <div className="relative h-full overflow-hidden rounded-2xl backdrop-blur-sm bg-gradient-to-br from-slate-800/40 to-slate-900/20 border border-cyan-500/20 hover:border-cyan-500/40 shadow-lg hover:shadow-cyan-500/10 transition-all duration-200"
           style={{ willChange: 'transform, box-shadow' }}>
        
        {/* Content Container */}
        <div className="relative z-5 h-full flex flex-col p-5">
          
          {/* Header */}
          <div className="mb-4 pb-4 border-b border-slate-700/50">
            <div className="flex items-start justify-between mb-2">
              <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">
                #{strategy.rank}
              </span>
              <span className="text-xs font-semibold text-slate-400 bg-slate-800/50 px-2 py-1 rounded">
                {strategy.pair}
              </span>
            </div>
            <h3 className="text-sm font-bold text-white line-clamp-2 leading-tight">
              {strategy.name}
            </h3>
          </div>

          {/* Body - Metrics */}
          <div className="flex-1 space-y-3 mb-4">
            {/* Profit Display */}
            <div className="p-3 rounded-lg bg-gradient-to-r from-emerald-600/20 to-emerald-700/10 border border-emerald-500/30">
              <div className="flex justify-between items-end">
                <span className="text-xs text-emerald-400 font-semibold uppercase">Lucro</span>
                <span className="text-lg font-bold text-emerald-300">
                  +${strategy.profit_adjusted?.toLocaleString() || '0'}
                </span>
              </div>
            </div>

            {/* Win Rate Display */}
            <div className="p-3 rounded-lg bg-gradient-to-r from-blue-600/20 to-blue-700/10 border border-blue-500/30">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-blue-400 font-semibold uppercase">Taxa de Acerto</span>
                <span className="text-sm font-bold text-blue-300">{strategy.winRate}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-blue-400 to-cyan-400 transition-all duration-500 ease-out"
                  style={{ width: `${strategy.winRate || 0}%` }}
                />
              </div>
            </div>
          </div>

          {/* Footer - Action Button */}
          <button
            className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-cyan-600/30 to-blue-600/30 border border-cyan-500/50 hover:border-cyan-500/70 text-cyan-300 hover:text-cyan-200 font-semibold text-xs uppercase transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group/btn"
            disabled={strategy.isLocked && !unlockedCards.has(strategy.id)}
          >
            <span>Detalhes</span>
            <ChevronRight className="w-3 h-3 group-hover/btn:translate-x-0.5 transition-transform" />
          </button>
        </div>

        {/* Lock Overlay - Optimized */}
        {strategy.isLocked && !unlockedCards.has(strategy.id) && (
          <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-[1px] z-20 rounded-2xl flex items-center justify-center overflow-hidden"
               style={{ willChange: 'opacity' }}>
            {/* Minimal Glow - Static */}
            <div className="absolute inset-0 bg-amber-500/10 blur-xl" />

            {/* Lock Icon Container - Minimal Animation */}
            <div className="relative z-10">
              {/* Static Ring */}
              <div className="absolute inset-0 w-12 h-12 border border-amber-400/30 rounded-full" />

              {/* Main Lock Icon - Minimal Bounce */}
              <div className="relative w-12 h-12 flex items-center justify-center">
                <motion.div
                  animate={{
                    y: [0, -1, 0]
                  }}
                  transition={{
                    duration: 3,
                    repeat: Infinity,
                    ease: 'easeInOut'
                  }}
                  className="relative"
                  style={{ willChange: 'transform' }}
                >
                  <Lock className="w-6 h-6 text-amber-200" strokeWidth={2} />
                </motion.div>
              </div>
            </div>

            {/* Static Text */}
            <div className="absolute bottom-6 left-0 right-0 text-center">
              <p className="text-xs font-bold text-amber-300 uppercase tracking-wider">
                🔒 Bloqueado
              </p>
              <p className="text-xs text-amber-200/70 mt-1">
                Clique para desbloquear
              </p>
            </div>
          </div>
        )}

        {/* Unlock Animation - Simplified */}
        {strategy.isLocked && unlockedCards.has(strategy.id) && (
          <motion.div
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            transition={{ delay: 0.8, duration: 0.2 }}
            className="absolute inset-0 bg-slate-950/40 z-20 rounded-2xl flex items-center justify-center overflow-hidden"
            style={{ willChange: 'opacity' }}
          >
            {/* Simple Flash */}
            <motion.div
              initial={{ scale: 0, opacity: 1 }}
              animate={{ scale: 1.5, opacity: 0 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="absolute inset-0 bg-emerald-400/30 rounded-2xl"
              style={{ willChange: 'transform, opacity' }}
            />

            {/* Unlock Icon - Simplified */}
            <motion.div
              initial={{ scale: 0, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="relative z-20"
              style={{ willChange: 'transform' }}
            >
              <div className="bg-emerald-500 p-2 rounded-full">
                <Unlock className="w-6 h-6 text-white" strokeWidth={2} />
              </div>
            </motion.div>

            {/* Success Text - Static */}
            <div className="absolute bottom-6 left-0 right-0 text-center z-20">
              <p className="text-sm font-bold text-emerald-300 uppercase tracking-wider">
                ✨ Desbloqueado!
              </p>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
});

StrategyCard.displayName = 'StrategyCard';

export function TopStrategies({ robots = [], onCardClick }: TopStrategiesProps) {
  const [selectedPeriod, setSelectedPeriod] = useState('15d');
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [unlockedCards, setUnlockedCards] = useState<Set<string>>(new Set());
  const { strategies: apiStrategies, loading, error } = useRankedStrategies();
  
  // Usar dados da API se disponível
  const allStrategies = useMemo(() => {
    if (apiStrategies && apiStrategies.length > 0) {
      return apiStrategies.map(s => ({
        ...s,
        id: s.id || `strat_${Math.random()}`,
      }));
    }
    return robots.map((r, i) => ({
      id: r.id || `robot_${i}`,
      name: r.name || '',
      pair: r.pair || 'N/A',
      profit: r.profit || 0,
      winRate: r.winRate || 0,
      status: 'ACTIVE',
      rank: i + 1,
    }));
  }, [apiStrategies, robots]);
  
  // Multiplicador de período
  const periodMultiplier = PERIOD_FILTERS.find(p => p.value === selectedPeriod)?.multiplier || 1;
  
  // Grid unificada de 20 estratégias
  const strategyGrid = useMemo(() => {
    return [...allStrategies]
      .sort((a, b) => (b.profit || 0) - (a.profit || 0))
      .slice(0, 20)
      .map((strategy, index) => ({
        ...strategy,
        profit_adjusted: Math.round((strategy.profit || 0) * periodMultiplier),
        rank: index + 1,
        isLocked: true, // TODO: Implementar lógica real de licença/desbloqueio
      }));
  }, [allStrategies, periodMultiplier]);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.03,
        delayChildren: 0.1
      }
    }
  };

  const cardVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.2, ease: 'easeOut' }
    },
    hover: {
      y: -4,
      transition: { duration: 0.15 }
    },
    exit: { opacity: 0, y: -10, transition: { duration: 0.15 } }
  };

  const handleCardClick = (strategy: any) => {
    setSelectedCardId(strategy.id);
    if (strategy.isLocked) {
      // Disparar animação de desbloqueio
      setUnlockedCards(prev => {
        const newSet = new Set(prev);
        newSet.add(strategy.id);
        return newSet;
      });
      console.log('Desbloqueando:', strategy.name);
    } else {
      onCardClick?.(strategy);
    }
  };

  return (
    <div className="mb-12 relative">
      {/* Header da Seção */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-xl blur-lg opacity-75" />
              <div className="relative p-3 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 backdrop-blur-xl rounded-xl border border-cyan-500/30">
                <TrendingUp className="w-6 h-6 text-cyan-400 drop-shadow-lg" />
              </div>
            </div>
            <div>
              <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-300 via-blue-400 to-purple-400">
                Marketplace de Estratégias
              </h2>
              <p className="text-slate-400 text-sm mt-1">
                {loading ? 'Carregando estratégias...' : 'Descubra as melhores estratégias de trading'}
              </p>
            </div>
          </div>

          {/* Period Filter Tabs */}
          <motion.div 
            className="flex gap-2 bg-slate-900/40 backdrop-blur-xl p-1 rounded-lg border border-slate-700/50"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            {PERIOD_FILTERS.map((period) => (
              <motion.button
                key={period.value}
                onClick={() => setSelectedPeriod(period.value)}
                className={`px-4 py-2 rounded-md text-sm font-semibold transition-all whitespace-nowrap ${
                  selectedPeriod === period.value
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-lg shadow-cyan-500/30'
                    : 'text-slate-400 hover:text-white'
                }`}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                disabled={loading}
              >
                {period.label}
              </motion.button>
            ))}
          </motion.div>
        </div>
      </motion.div>

      {/* Loading State */}
      {loading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex justify-center items-center py-20"
        >
          <div className="text-center">
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity }}>
              <Loader className="w-8 h-8 text-cyan-500 mx-auto mb-3" />
            </motion.div>
            <p className="text-slate-400 text-sm">Carregando estratégias...</p>
          </div>
        </motion.div>
      )}

      {/* Error State */}
      {error && !loading && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-lg bg-red-900/20 border border-red-500/50 text-red-400 text-sm mb-8"
        >
          ⚠️ {error}
        </motion.div>
      )}

      {/* Main Grid */}
      {!loading && (
        <motion.div 
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          <AnimatePresence>
            {strategyGrid.map((strategy) => (
              <motion.div
                key={strategy.id}
                variants={cardVariants}
                whileHover="hover"
                exit="exit"
              >
                <StrategyCard
                  strategy={strategy}
                  onCardClick={handleCardClick}
                  unlockedCards={unlockedCards}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Empty State */}
      {!loading && strategyGrid.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="py-20 text-center"
        >
          <p className="text-slate-400 text-sm">Nenhuma estratégia disponível no momento</p>
        </motion.div>
      )}

      {/* Footer Info */}
      {!loading && strategyGrid.length > 0 && (
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="mt-10 p-4 rounded-lg bg-slate-900/40 border border-slate-700/50 text-center text-sm text-slate-400"
        >
          <p>💡 Clique nos cards bloqueados para desbloqueá-los e acessar os detalhes das estratégias.</p>
        </motion.div>
      )}
    </div>
  );
}
