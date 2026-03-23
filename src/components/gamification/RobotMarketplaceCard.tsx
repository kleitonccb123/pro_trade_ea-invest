/**
 * RobotMarketplaceCard - Card individual de robo estrategico
 * Visual redesenhado: gradientes vibrantes, hierarquia clara, so botoes clicaveis
 */

import React from 'react';
import { motion } from 'framer-motion';
import {
  Lock,
  Flame,
  Zap,
  TrendingUp,
  BarChart2,
  Star,
  Rocket,
  ShieldCheck,
} from 'lucide-react';
import { NumberAnimator } from './NumberAnimator';

interface RobotCardData {
  id: string;
  name: string;
  creator: string;
  country: string;
  strategy: string;
  rank: number;
  medal?: string;
  is_locked: boolean;
  is_on_fire: boolean;
  unlock_cost: number;
  profit_15d: number;
  profit_7d: number;
  profit_24h: number;
  win_rate: number;
  total_trades: number;
}

interface RobotMarketplaceCardProps {
  robot: RobotCardData;
  onUnlock?: (robotId: string) => void;
  onInfo?: (robotId: string) => void;
  onActivate?: (robotId: string) => void;
  planLimitReached?: boolean;
}

const STRATEGY_META: Record<string, { label: string; color: string; bg: string; border: string }> = {
  grid:     { label: 'GRID',     color: '#ffffff', bg: 'rgba(255,255,255,0.08)', border: 'rgba(35,200,130,0.25)' },
  rsi:      { label: 'RSI',      color: '#ffffff', bg: 'rgba(255,255,255,0.08)', border: 'rgba(35,200,130,0.25)' },
  macd:     { label: 'MACD',     color: '#ffffff', bg: 'rgba(255,255,255,0.08)', border: 'rgba(35,200,130,0.25)' },
  dca:      { label: 'DCA',      color: '#ffffff', bg: 'rgba(255,255,255,0.08)', border: 'rgba(35,200,130,0.25)' },
  combined: { label: 'COMBINED', color: '#ffffff', bg: 'rgba(255,255,255,0.08)', border: 'rgba(35,200,130,0.25)' },
};

const MEDAL_CONFIG: Record<string, { emoji: string; borderColor: string; glowColor: string }> = {
  '??': { emoji: '??', borderColor: 'rgba(250,204,21,0.50)', glowColor: 'rgba(250,204,21,0.15)' },
  '??': { emoji: '??', borderColor: 'rgba(209,213,219,0.40)', glowColor: 'rgba(209,213,219,0.08)' },
  '??': { emoji: '??', borderColor: 'rgba(251,146,60,0.40)',  glowColor: 'rgba(251,146,60,0.08)' },
};

export const RobotMarketplaceCard: React.FC<RobotMarketplaceCardProps> = ({
  robot,
  onUnlock,
  onActivate,
  planLimitReached,
}) => {
  const meta = STRATEGY_META[robot.strategy] ?? STRATEGY_META.grid;
  const medalCfg = robot.medal ? MEDAL_CONFIG[robot.medal] : null;
  const winRatePct = Math.min(100, Math.max(0, robot.win_rate));

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -6, transition: { duration: 0.25 } }}
      className="relative h-full select-none"
    >
      {/* Glow border on hover */}
      <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${meta.gradient} opacity-0 group-hover:opacity-100 transition-opacity blur-xl`} />

      {/* Card */}
      <div className={`relative h-full flex flex-col rounded-2xl border overflow-hidden
        ${medalCfg ? medalCfg.border : 'border-slate-700/60'}
        bg-slate-900/90 backdrop-blur-md transition-all duration-300
        hover:border-opacity-80 group`}
      >

        {/* Top stripe — KuCoin green */}
        <div className="h-1 w-full" style={{ background: '#23C882' }} />

        {/* Floating badges */}
        {robot.is_locked && (
          <motion.div
            className="absolute -top-2 -right-2 z-20 rounded-full p-2"
            style={{ background: '#23C882' }}
          >
            <Lock className="w-4 h-4 text-[#0B0E11]" />
          </motion.div>
        )}
        {robot.is_on_fire && !robot.is_locked && (
          <motion.div
            className="absolute -top-2 -left-2 z-20 rounded-full p-2"
            style={{ background: '#23C882' }}
          >
            <Flame className="w-4 h-4 text-[#0B0E11]" />
          </motion.div>
        )}

        {/* Body */}
        <div className="flex flex-col flex-1 p-4 gap-3">

          {/* Header row: medal + rank */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {robot.medal && (
                <span className="text-2xl leading-none">{robot.medal}</span>
              )}
              {robot.is_on_fire && !robot.medal && (
                <span className="flex items-center gap-1 text-xs font-bold text-slate-400 tracking-wide">
                  <Flame className="w-3 h-3" style={{ color: '#23C882' }} /> TOP
                </span>
              )}
              {robot.is_on_fire && robot.medal && (
                <span className="text-xs font-bold text-slate-400">🔥</span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${meta.bg} ${meta.accent} uppercase tracking-wider`}>
                {meta.label}
              </span>
              <span className="text-[10px] font-bold text-slate-500 bg-slate-800/60 px-2 py-0.5 rounded-full">
                #{robot.rank}
              </span>
            </div>
          </div>

          {/* Name */}
          <div>
            <h3 className="font-black text-white text-base leading-tight line-clamp-1">{robot.name}</h3>
          </div>

          {/* Creator */}
          <div className="flex items-center gap-2 bg-slate-800/50 border border-slate-700/40 rounded-xl px-3 py-2">
            <span className="text-base">{robot.country}</span>
            <div className="min-w-0">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">Criador</p>
              <p className="text-xs font-semibold text-slate-200 truncate">{robot.creator}</p>
            </div>
            <ShieldCheck className="w-3.5 h-3.5 ml-auto flex-shrink-0" style={{ color: '#23C882' }} />
          </div>

          {/* Profit highlight — KuCoin green */}
          <div
            className="rounded-xl p-3 flex items-center justify-between"
            style={{ background: 'rgba(35,200,130,0.07)', border: '1px solid rgba(35,200,130,0.15)' }}
          >
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1" style={{ color: 'rgba(35,200,130,0.75)' }}>
                <TrendingUp className="w-3 h-3" /> Lucro 15D
              </p>
              <p className="text-2xl font-black leading-tight mt-0.5" style={{ color: '#23C882' }}>
                $<NumberAnimator value={robot.profit_15d} decimals={0} glowColor="emerald" />
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">24h</p>
              <p className="text-sm font-bold" style={{ color: '#23C882' }}>+${robot.profit_24h?.toFixed(0) ?? '—'}</p>
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div className="flex items-center gap-1 mb-1">
                <BarChart2 className="w-3 h-3" style={{ color: '#23C882' }} />
                <p className="text-[10px] text-slate-400 uppercase tracking-wider">Win Rate</p>
              </div>
              <p className="text-sm font-black" style={{ color: '#23C882' }}>{robot.win_rate}%</p>
              {/* Mini bar — KuCoin green */}
              <div className="mt-1.5 h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${winRatePct}%`, background: 'linear-gradient(90deg, #23C882, #1aad73)' }}
                />
              </div>
            </div>
            <div className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div className="flex items-center gap-1 mb-1">
                <Zap className="w-3 h-3 text-slate-400" />
                <p className="text-[10px] text-slate-400 uppercase tracking-wider">Trades</p>
              </div>
              <p className="text-sm font-black text-white">{robot.total_trades}</p>
              <p className="text-[10px] text-slate-500 mt-1.5">executados</p>
            </div>
          </div>

          {/* CTA Button */}
          <div className="mt-auto pt-1">
            {robot.is_locked ? (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={(e) => { e.stopPropagation(); onUnlock?.(robot.id); }}
                className="w-full py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 text-white transition-all duration-200 border"
                style={{ background: 'rgba(35,200,130,0.12)', border: '1px solid rgba(35,200,130,0.40)', color: '#ffffff' }}
              >
                <Lock className="w-4 h-4" style={{ color: '#23C882' }} />
                Desbloquear
                <span className="flex items-center gap-0.5 px-2 py-0.5 rounded text-xs" style={{ background: 'rgba(35,200,130,0.20)', color: '#23C882', fontWeight: '600' }}>
                  {robot.unlock_cost}<Star className="w-3 h-3 fill-current" />
                </span>
              </motion.button>
            ) : (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={(e) => { e.stopPropagation(); onActivate?.(robot.id); }}
                className="w-full py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 text-white transition-all duration-200 border"
                style={{ background: '#23C882', border: '1px solid #23C882', color: '#0B0E11' }}
              >
                <Rocket className="w-4 h-4" />
                {'Ativar Rob\u00f4'}
              </motion.button>
            )}
          </div>

        </div>
      </div>
    </motion.div>
  );
};

export default RobotMarketplaceCard;
