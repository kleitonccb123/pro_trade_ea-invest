import React from 'react';
import { GlowCard } from '@/components/ui/spotlight-card';
import { TrendingUp, Zap, Shield, Cpu, BarChart3, ArrowUpRight, ArrowDownRight, Lock } from 'lucide-react';
import { Robot } from '@/types/robot';

interface RobotGlowGridProps {
  robots?: (Robot & { country?: string; description?: string; activeUsers?: number })[];
  onRobotSelect?: (robot: Robot) => void;
}

export function RobotGlowGrid({ robots = [], onRobotSelect }: RobotGlowGridProps) {
  const getGlowColor = (status: string): 'blue' | 'purple' | 'green' | 'red' | 'orange' => {
    switch (status) {
      case 'active':
        return 'green';
      case 'paused':
        return 'orange';
      case 'error':
        return 'red';
      case 'stopped':
        return 'purple';
      default:
        return 'blue';
    }
  };

  const getStatusIcon = (strategy: string) => {
    if (strategy.includes('Scalp')) return <TrendingUp className="w-6 h-6" />;
    if (strategy.includes('DCA')) return <BarChart3 className="w-6 h-6" />;
    if (strategy.includes('Grid')) return <Zap className="w-6 h-6" />;
    if (strategy.includes('Trend')) return <Shield className="w-6 h-6" />;
    return <Cpu className="w-6 h-6" />;
  };

  if (robots.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Nenhum robô disponível</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 py-8">
      {robots.map((robot) => (
        <div
          key={robot.id}
          onClick={() => onRobotSelect?.(robot)}
          className="cursor-pointer group"
        >
          <GlowCard
            glowColor={getGlowColor(robot.status)}
            size="md"
            className="h-full transition-all duration-300 overflow-hidden hover:shadow-2xl relative"
          >
            {/* Lock Overlay */}
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 backdrop-blur-[1px] group-hover:bg-black/30 transition-all rounded-xl">
              <div className="bg-slate-900/90 p-3 rounded-full border border-yellow-500/50 shadow-lg shadow-yellow-500/20 animate-pulse">
                <Lock className="w-6 h-6 text-yellow-500" />
              </div>
            </div>
            <div className="flex flex-col h-full justify-between gap-4">
              {/* Header Section */}
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center group-hover:from-blue-500/30 group-hover:to-purple-500/30 transition-all border border-blue-400/30 group-hover:border-blue-400/50">
                    <div className="text-blue-300">{getStatusIcon(robot.strategy)}</div>
                  </div>
                  <div className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${
                    robot.status === 'active' 
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-400/30' :
                    robot.status === 'paused' 
                      ? 'bg-amber-500/10 text-amber-400 border-amber-400/30' :
                    'bg-slate-500/10 text-slate-400 border-slate-400/30'
                  }`}>
                    {robot.status}
                  </div>
                </div>
                
                <div>
                  <h3 className="text-base font-bold text-white group-hover:text-blue-300 transition-colors line-clamp-2">
                    {robot.name}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1.5 line-clamp-2">
                    {robot.description || robot.strategy}
                  </p>
                </div>
              </div>

              {/* Main Metrics */}
              <div className="space-y-2.5 bg-white/[0.02] rounded-lg p-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500 font-medium uppercase tracking-wide">Par Trading</span>
                  <span className="text-sm font-semibold text-blue-300">{robot.pair}</span>
                </div>
                
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500 font-medium uppercase tracking-wide">Lucro</span>
                  <div className="flex items-center gap-1">
                    {robot.profit >= 0 ? (
                      <ArrowUpRight className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <ArrowDownRight className="w-4 h-4 text-red-400" />
                    )}
                    <span className={`text-sm font-bold ${robot.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      ${Math.abs(robot.profit).toFixed(2)}
                    </span>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Taxa Acerto</p>
                    <p className="text-sm font-bold text-white">{robot.winRate.toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1">Trades</p>
                    <p className="text-sm font-bold text-white">{robot.trades}</p>
                  </div>
                </div>
              </div>

              {/* Timeframe Footer */}
              <div className="pt-3 border-t border-white/5 flex items-center justify-between">
                <span className="text-xs text-slate-500 uppercase tracking-wide font-medium">Timeframe</span>
                <span className="text-xs px-2.5 py-1 rounded-md bg-slate-700/30 border border-slate-600/30 text-slate-300 font-semibold">
                  {robot.timeframe || '1h'}
                </span>
              </div>
            </div>
          </GlowCard>
        </div>
      ))}
    </div>
  );
}

export default RobotGlowGrid;
