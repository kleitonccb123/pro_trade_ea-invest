import React from 'react';
import { GlowCard } from '@/components/ui/spotlight-card';
import { Zap, TrendingUp, Shield, Cpu } from 'lucide-react';

export function RobotStrategyCards() {
  const strategies = [
    {
      name: 'Momentum Bot',
      description: 'Captura tendências de preço em tempo real',
      icon: TrendingUp,
      color: 'blue' as const,
      stats: {
        winRate: '72%',
        riskLevel: 'Médio'
      }
    },
    {
      name: 'Grid Trading',
      description: 'Lucro com flutuações de preço',
      icon: Zap,
      color: 'purple' as const,
      stats: {
        winRate: '85%',
        riskLevel: 'Baixo'
      }
    },
    {
      name: 'Risk Shield',
      description: 'Proteção automática de portfólio',
      icon: Shield,
      color: 'green' as const,
      stats: {
        winRate: '95%',
        riskLevel: 'Muito Baixo'
      }
    },
    {
      name: 'AI Predictor',
      description: 'Análise preditiva com Machine Learning',
      icon: Cpu,
      color: 'orange' as const,
      stats: {
        winRate: '68%',
        riskLevel: 'Alto'
      }
    }
  ];

  return (
    <div className="w-full py-12 px-4">
      <div className="mb-12">
        <h2 className="text-3xl font-bold text-white mb-2">Robôs de Trading</h2>
        <p className="text-gray-400">Estratégias automatizadas para maximizar seus ganhos</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
        {strategies.map((strategy) => {
          const Icon = strategy.icon;
          return (
            <GlowCard
              key={strategy.name}
              glowColor={strategy.color}
              size="md"
              className="hover:shadow-xl transition-all duration-300 group"
            >
              <div className="flex flex-col h-full justify-between">
                <div className="space-y-3">
                  <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      {strategy.name}
                    </h3>
                    <p className="text-sm text-gray-400 mt-1">
                      {strategy.description}
                    </p>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/10 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-400">Taxa de Acerto</span>
                    <span className="text-sm font-semibold text-green-400">
                      {strategy.stats.winRate}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-400">Risco</span>
                    <span className="text-xs px-2 py-1 rounded-full bg-white/10 text-white">
                      {strategy.stats.riskLevel}
                    </span>
                  </div>
                </div>
              </div>
            </GlowCard>
          );
        })}
      </div>
    </div>
  );
}

export default RobotStrategyCards;
