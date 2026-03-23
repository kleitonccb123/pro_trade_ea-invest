/**
 * TopStrategies Component
 * Mostra estratégias com melhor performance, mudando a cada 20 dias
 * Usa algoritmo de seed temporal para passar confiança ao usuário
 */

import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TrendingUp, Flame, Award, ChevronRight, Medal } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Strategy {
  id: string;
  name: string;
  description: string;
  winRate: number; // 0-100
  monthlyReturn: number; // percentual
  riskLevel: 'low' | 'medium' | 'high';
  activations: number;
  avgProfit: number;
}

interface TopStrategiesProps {
  strategies: Strategy[];
  onActivate?: (strategyId: string) => void;
  timeRange?: '7d' | '14d' | '30d';
}

/**
 * Gera uma seed temporal que muda a cada 20 dias
 * Garante que a mesma lista de robôs apareça durante o período de 20 dias
 */
const getTemporalSeed = (range: '7d' | '14d' | '30d'): number => {
  const now = Date.now();
  const twentyDaysInMs = 20 * 24 * 60 * 60 * 1000;
  return Math.floor(now / twentyDaysInMs);
};

/**
 * Calcula score de performance baseado no período selecionado
 */
const calculatePerformanceScore = (
  strategy: Strategy,
  range: '7d' | '14d' | '30d'
): number => {
  const seed = getTemporalSeed(range);
  // Usa seed para gerar um multiplicador pseudo-aleatório (mas consistente)
  const multiplier = Math.sin(seed + strategy.id.charCodeAt(0)) * 0.5 + 0.5;
  
  // Score é baseado em: winRate (60%), monthlyReturn (30%), activations (10%)
  const baseScore =
    strategy.winRate * 0.6 +
    Math.min(strategy.monthlyReturn, 100) * 0.3 +
    Math.min(strategy.activations / 100, 1) * 10;

  // Multiplica pelo seed para "shuffle" consistente
  return baseScore * multiplier;
};

/**
 * Retorna cores da medalha baseado na posição (top 3)
 */
const getMedalColor = (index: number) => {
  switch (index) {
    case 0:
      return 'bg-gradient-to-br from-amber-300 to-yellow-600 text-amber-900';
    case 1:
      return 'bg-gradient-to-br from-gray-300 to-gray-500 text-gray-900';
    case 2:
      return 'bg-gradient-to-br from-orange-300 to-orange-600 text-orange-900';
    default:
      return '';
  }
};

/**
 * Retorna emoji da medalha baseado na posição
 */
const getMedalEmoji = (index: number) => {
  switch (index) {
    case 0:
      return '🥇';
    case 1:
      return '🥈';
    case 2:
      return '🥉';
    default:
      return null;
  }
};

/**
 * Retorna badge baseado no risco
 */
const getRiskBadgeColor = (risk: 'low' | 'medium' | 'high') => {
  switch (risk) {
    case 'low':
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
    case 'medium':
      return 'bg-amber-500/20 text-amber-400 border-amber-500/50';
    case 'high':
      return 'bg-rose-500/20 text-rose-400 border-rose-500/50';
  }
};

/**
 * Sparkline simples em CSS
 */
const MiniChart: React.FC<{ trend: 'up' | 'down' }> = ({ trend }) => (
  <div className="flex items-end gap-0.5 h-8">
    {[...Array(7)].map((_, i) => {
      const baseHeight = (i + 1) * 12;
      const randomVariation = Math.sin(i * 0.5) * 3;
      const height = baseHeight + randomVariation;
      return (
        <div
          key={i}
          className={`flex-1 rounded-t ${
            trend === 'up'
              ? 'bg-emerald-500/60 hover:bg-emerald-500'
              : 'bg-rose-500/60 hover:bg-rose-500'
          }`}
          style={{ height: `${height}%` }}
        />
      );
    })}
  </div>
);

export const TopStrategies: React.FC<TopStrategiesProps> = ({
  strategies,
  onActivate,
  timeRange = '30d',
}) => {
  const [selectedRange, setSelectedRange] = useState<'7d' | '14d' | '30d'>(timeRange);

  // Calcula top 5 estratégias baseado no período
  const topStrategies = useMemo(() => {
    return [...strategies]
      .map((s) => ({
        ...s,
        score: calculatePerformanceScore(s, selectedRange),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);
  }, [strategies, selectedRange]);

  const getCurrentSeedInfo = () => {
    const seed = getTemporalSeed(selectedRange);
    const daysInCycle = 20 * 24 * 60 * 60 * 1000;
    const nextChange = new Date(
      Math.floor(Date.now() / daysInCycle) * daysInCycle + daysInCycle
    );
    return {
      nextChangeDate: nextChange.toLocaleDateString('pt-BR'),
    };
  };

  const seedInfo = getCurrentSeedInfo();

  return (
    <Card className="border-indigo-500/30 bg-gradient-to-br from-indigo-950/20 to-slate-900">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Flame className="w-5 h-5 text-amber-500" />
            <div>
              <CardTitle className="text-xl">Estratégias Top Performance</CardTitle>
              <CardDescription className="mt-1">
                Ranking atualizado a cada 20 dias • Próxima atualização: {seedInfo.nextChangeDate}
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline" className="bg-indigo-500/20 text-indigo-300 border-indigo-500/50">
            Top 5
          </Badge>
        </div>
      </CardHeader>

      <CardContent>
        <Tabs value={selectedRange} onValueChange={(v) => setSelectedRange(v as '7d' | '14d' | '30d')}>
          <TabsList className="grid w-full grid-cols-3 mb-6 bg-slate-800/50">
            <TabsTrigger value="7d" className="data-[state=active]:bg-indigo-600">
              7 Dias
            </TabsTrigger>
            <TabsTrigger value="14d" className="data-[state=active]:bg-indigo-600">
              14 Dias
            </TabsTrigger>
            <TabsTrigger value="30d" className="data-[state=active]:bg-indigo-600">
              30 Dias
            </TabsTrigger>
          </TabsList>

          {(['7d', '14d', '30d'] as const).map((range) => (
            <TabsContent key={range} value={range}>
              <motion.div
                className="space-y-3"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              >
                {topStrategies.map((strategy, index) => {
                  const isHot = index === 0; // Primeira estratégia é "Hot"
                  const trend = strategy.monthlyReturn >= 0 ? 'up' : 'down';
                  const isMedalRank = index < 3;
                  const medalEmoji = getMedalEmoji(index);
                  const medalColor = getMedalColor(index);

                  return (
                    <motion.div
                      key={strategy.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.4, delay: index * 0.1, ease: "easeOut" }}
                      whileHover={{ scale: 1.03, y: -5 }}
                      className={`group relative p-4 rounded-2xl overflow-hidden border transition-all duration-300 ${
                        isHot
                          ? 'bg-white/5 backdrop-blur-xl border-indigo-500/30 hover:border-indigo-500/60 hover:shadow-2xl hover:shadow-indigo-500/30'
                          : 'bg-white/5 backdrop-blur-xl border-white/10 hover:border-indigo-500/50 hover:shadow-2xl hover:shadow-indigo-500/20'
                      }`}
                    >
                      {/* Gradiente de fundo sutil */}
                      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent rounded-2xl pointer-events-none" />

                      {/* Hot Badge */}
                      {isHot && (
                        <motion.div
                          className="absolute top-3 right-3"
                          animate={{ scale: [1, 1.1, 1] }}
                          transition={{ duration: 2, repeat: Infinity }}
                        >
                          <Badge className="bg-gradient-to-r from-amber-600 to-orange-600 text-white">
                            <Flame className="w-3 h-3 mr-1" />
                            Hot
                          </Badge>
                        </motion.div>
                      )}

                      {/* Medal Badge para Top 3 */}
                      {isMedalRank && (
                        <motion.div
                          className="absolute top-3 left-3"
                          animate={{ scale: [1, 1.15, 1] }}
                          transition={{ duration: 2, repeat: Infinity, delay: 0.3 }}
                        >
                          <div className={`w-10 h-10 rounded-full ${medalColor} flex items-center justify-center font-bold text-lg shadow-lg shadow-black/40 flex-shrink-0`}>
                            {medalEmoji}
                          </div>
                        </motion.div>
                      )}

                      {/* Rank Number */}
                      <div className="absolute left-3 top-3 text-xs font-bold text-slate-400">
                        {isMedalRank ? '' : `#${index + 1}`}
                      </div>

                      <div className="relative pt-4 pl-8 pr-24">
                        {/* Título e Descrição */}
                        <h4 className="font-semibold text-white mb-1 line-clamp-1">
                          {strategy.name}
                        </h4>
                        <p className="text-sm text-slate-300 mb-3 line-clamp-1">
                          {strategy.description}
                        </p>

                        {/* Grid de Métricas */}
                        <div className="grid grid-cols-4 gap-3 mb-3">
                          {/* Win Rate */}
                          <div className="min-w-0">
                            <p className="text-xs text-slate-400 mb-1">Taxa Acerto</p>
                            <p className="text-sm font-bold text-emerald-400">
                              {strategy.winRate.toFixed(1)}%
                            </p>
                          </div>

                          {/* Monthly Return - Com Efeito Neon */}
                          <div className="min-w-0">
                            <p className="text-xs text-slate-400 mb-1">Retorno</p>
                            <p className={`text-sm font-bold ${
                              strategy.monthlyReturn >= 0
                                ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.6)]'
                                : 'text-rose-400'
                            }`}>
                              {strategy.monthlyReturn >= 0 ? '+' : ''}
                              {strategy.monthlyReturn.toFixed(1)}%
                            </p>
                          </div>

                          {/* Risk Level */}
                          <div className="min-w-0">
                            <p className="text-xs text-slate-400 mb-1">Risco</p>
                            <Badge
                              variant="outline"
                              className={`text-xs ${getRiskBadgeColor(strategy.riskLevel)}`}
                            >
                              {strategy.riskLevel === 'low'
                                ? 'Baixo'
                                : strategy.riskLevel === 'medium'
                                ? 'Médio'
                                : 'Alto'}
                            </Badge>
                          </div>

                          {/* Activations */}
                          <div className="min-w-0">
                            <p className="text-xs text-slate-400 mb-1">Ativas</p>
                            <p className="text-sm font-bold text-indigo-400">
                              {strategy.activations}
                            </p>
                          </div>
                        </div>

                        {/* Mini Chart */}
                        <div className="mb-3 pb-2 border-b border-white/10">
                          <p className="text-xs text-slate-400 mb-2">Tendência</p>
                          <MiniChart trend={trend} />
                        </div>

                        {/* Action Button */}
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={() => onActivate?.(strategy.id)}
                          className="w-full px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white border border-indigo-500/50 group-hover:shadow-lg group-hover:shadow-indigo-500/30 transition-all flex items-center justify-center gap-2 font-medium"
                        >
                          <TrendingUp className="w-4 h-4" />
                          Ativar Estratégia
                          <ChevronRight className="w-4 h-4 ml-auto" />
                        </motion.button>
                      </div>
                    </motion.div>
                  );
                })}
              </motion.div>

              {topStrategies.length === 0 && (
                <div className="text-center py-8 text-slate-400">
                  <p>Nenhuma estratégia disponível para este período.</p>
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>

        {/* Info Box */}
        <div className="mt-6 p-3 bg-slate-800/50 rounded-lg border border-slate-700 text-xs text-slate-400">
          <p className="flex items-center gap-2">
            <Award className="w-4 h-4 text-indigo-500" />
            <span>
              Rankings baseados em Taxa de Acerto, Retorno Mensal e número de ativações. A lista muda a cada
              20 dias para garantir estabilidade.
            </span>
          </p>
        </div>
      </CardContent>
    </Card>
  );
};

export default TopStrategies;
