/**
 * StrategiesPage Improved - Modern UI with Full Backend Integration
 * Features: Real-time data, advanced filtering, performance charts, and more
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Plus,
  Search,
  Filter,
  TrendingUp,
  AlertCircle,
  RotateCcw,
  Zap,
  BarChart3,
  Trophy,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import CreditMonitor from '@/components/credits/CreditMonitor';
import StrategyCard from '@/components/strategies/StrategyCard';
import useStrategyMetrics from '@/hooks/useStrategyMetrics';
import { StrategyMetrics } from '@/services/strategyService';

const StrategiesPageImproved: React.FC = () => {
  const navigate = useNavigate();
  // State
  const [activeTab, setActiveTab] = useState<'all' | 'my' | 'public' | 'top'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [riskFilter, setRiskFilter] = useState<'all' | 'low' | 'medium' | 'high'>('all');
  const [sortBy, setSortBy] = useState<'name' | 'winRate' | 'return' | 'date'>('return');
  const [activeStrategyId, setActiveStrategyId] = useState<string | null>(null);

  // Hooks
  const {
    strategies,
    publicStrategies,
    topStrategies,
    loading,
    error,
    success,
    fetchStrategies,
    fetchPublicStrategies,
    fetchTopStrategies,
    deleteStrategy,
    toggleVisibility,
    cloneStrategy,
    activateStrategy,
    shareStrategy,
    clearError,
    clearSuccess,
  } = useStrategyMetrics();

  // Auto-fetch strategies on mount
  useEffect(() => {
    fetchStrategies();
    fetchPublicStrategies();
    fetchTopStrategies(5);
  }, []);

  // Filter and sort strategies
  const getFilteredStrategies = (data: StrategyMetrics[]): StrategyMetrics[] => {
    let filtered = data.filter((s) => {
      const matchesSearch =
        s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.description?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesRisk = riskFilter === 'all' || s.riskLevel === riskFilter;
      return matchesSearch && matchesRisk;
    });

    // Sort
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'winRate':
          return (b.winRate || 0) - (a.winRate || 0);
        case 'return':
          return (b.monthlyReturn || 0) - (a.monthlyReturn || 0);
        case 'date':
          return new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime();
        default:
          return 0;
      }
    });

    return filtered;
  };

  // Handlers
  const handleActivateStrategy = async (id: string) => {
    await activateStrategy(id);
    setActiveStrategyId(id);
  };

  const handleCloneStrategy = async (id: string) => {
    const cloned = await cloneStrategy(id);
    if (cloned) {
      console.log('Strategy cloned successfully:', cloned.name);
    }
  };

  const handleShareStrategy = async (id: string) => {
    const shareUrl = await shareStrategy(id);
    if (shareUrl) {
      navigator.clipboard.writeText(shareUrl);
      alert('Link copied to clipboard!');
    }
  };

  const handleDeleteStrategy = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this strategy?')) {
      await deleteStrategy(id);
    }
  };

  const handleToggleVisibility = async (id: string) => {
    await toggleVisibility(id);
  };

  const renderMetrics = (strategy: StrategyMetrics) => (
    <StrategyCard
      key={strategy.id}
      id={strategy.id}
      name={strategy.name}
      description={strategy.description}
      isPublic={strategy.isPublic}
      isActive={strategy.isActive}
      winRate={strategy.winRate}
      monthlyReturn={strategy.monthlyReturn}
      riskLevel={strategy.riskLevel}
      swapsUsed={strategy.swapsUsed}
      maxSwaps={strategy.maxSwaps}
      activationsUsed={strategy.activationsUsed}
      maxActivations={strategy.maxActivations}
      createdAt={strategy.createdAt}
      totalTrades={strategy.totalTrades}
      totalProfit={strategy.totalProfit}
      drawdown={strategy.drawdown}
      sharpeRatio={strategy.sharpeRatio}
      successRate={strategy.successRate}
      avgWin={strategy.avgWin}
      avgLoss={strategy.avgLoss}
      onActivate={() => handleActivateStrategy(strategy.id)}
      onEdit={() => console.log('Edit:', strategy.id)}
      onDelete={() => handleDeleteStrategy(strategy.id)}
      onToggleVisibility={() => handleToggleVisibility(strategy.id)}
      onClone={() => handleCloneStrategy(strategy.id)}
      onShare={() => handleShareStrategy(strategy.id)}
    />
  );

  const allStrategies = getFilteredStrategies(strategies);
  const publicFiltered = getFilteredStrategies(publicStrategies);
  const topFiltered = getFilteredStrategies(topStrategies);

  return (
    <div className="w-full">
      {/* Header */}
      <div className="mb-6 pb-6 border-b border-slate-700/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 via-emerald-300 to-teal-400 bg-clip-text text-transparent mb-1">
              Estratégias de Trading
            </h1>
            <p className="text-slate-400 text-sm">
              Gerencie, analise e compartilhe suas estratégias automáticas
            </p>
          </div>
          <Button
            onClick={() => navigate('/strategy/submit')}
            className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg border border-emerald-500/50">
            <Plus className="w-4 h-4 mr-2" />
            Nova Estratégia
          </Button>
        </div>
      </div>

      <div className="w-full space-y-6">
        {/* Alerts */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-600/50 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <p className="text-red-300 flex-1 text-sm">{error}</p>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-300 font-semibold ml-auto text-sm"
            >
              Dimissão
            </button>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 bg-emerald-900/20 border border-emerald-600/50 rounded-lg flex items-center gap-3">
            <Zap className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            <p className="text-emerald-300 text-sm flex-1">Operação realizada com sucesso!</p>
            <button
              onClick={clearSuccess}
              className="ml-auto text-emerald-400 hover:text-emerald-300 font-semibold"
            >
              ✕
            </button>
          </div>
        )}

        {/* Credit Monitor */}
        <div className="mb-4">
          <CreditMonitor />
        </div>

        {/* Controls */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            {/* Search */}
            <div className="relative md:col-span-2">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
              <Input
                placeholder="Procurar estratégias..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 bg-slate-800/40 border border-slate-700/50 text-white placeholder:text-slate-500 focus:border-emerald-500/50 focus:ring-emerald-500/20 transition-all"
              />
            </div>

            {/* Risk Filter */}
            <Select value={riskFilter} onValueChange={(value: any) => setRiskFilter(value)}>
              <SelectTrigger className="bg-slate-800/40 border border-slate-700/50 text-white focus:border-emerald-500/50">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Risco" />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="all">Todos os Riscos</SelectItem>
                <SelectItem value="low">🟢 Baixo Risco</SelectItem>
                <SelectItem value="medium">🟡 Médio Risco</SelectItem>
                <SelectItem value="high">🔴 Alto Risco</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort */}
            <Select value={sortBy} onValueChange={(value: any) => setSortBy(value)}>
              <SelectTrigger className="bg-slate-800/40 border border-slate-700/50 text-white focus:border-emerald-500/50">
                <TrendingUp className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Ordenar" />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="return">Retorno (Alto para Baixo)</SelectItem>
                <SelectItem value="winRate">Taxa de Acerto</SelectItem>
                <SelectItem value="name">Nome (A-Z)</SelectItem>
                <SelectItem value="date">Data (Mais Recentes)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-gradient-to-br from-emerald-900/10 to-emerald-800/5 rounded-lg border border-emerald-600/20 hover:border-emerald-500/40 transition-all">
              <p className="text-xs text-slate-400 mb-2 font-medium">Total Estratégias</p>
              <p className="text-3xl font-bold text-emerald-400">{strategies.length}</p>
            </div>
            <div className="p-4 bg-gradient-to-br from-teal-900/10 to-teal-800/5 rounded-lg border border-teal-600/20 hover:border-teal-500/40 transition-all">
              <p className="text-xs text-slate-400 mb-2 font-medium">Ativas Agora</p>
              <p className="text-3xl font-bold text-teal-400">
                {strategies.filter((s) => s.isActive).length}
              </p>
            </div>
            <div className="p-4 bg-gradient-to-br from-emerald-900/10 to-emerald-800/5 rounded-lg border border-emerald-600/20 hover:border-emerald-500/40 transition-all">
              <p className="text-xs text-slate-400 mb-2 font-medium">Públicas</p>
              <p className="text-3xl font-bold text-emerald-400">
                {strategies.filter((s) => s.isPublic).length}
              </p>
            </div>
            <div className="p-4 bg-gradient-to-br from-teal-900/10 to-teal-800/5 rounded-lg border border-teal-600/20 hover:border-teal-500/40 transition-all">
              <p className="text-xs text-slate-400 mb-2 font-medium">Retorno Médio</p>
              <p className="text-3xl font-bold text-teal-400">
                {strategies.length > 0
                  ? (
                      strategies.reduce((sum, s) => sum + (s.monthlyReturn || 0), 0) /
                      strategies.length
                    ).toFixed(2)
                  : '0'}
                %
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(value: any) => setActiveTab(value)} className="mt-8">
          <TabsList className="grid w-full grid-cols-4 bg-slate-800/30 border border-slate-700/50 p-1 rounded-lg">
            <TabsTrigger value="all" className="transition-all data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-emerald-500/20">
              Todas ({allStrategies.length})
            </TabsTrigger>
            <TabsTrigger value="my" className="transition-all data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-emerald-500/20">
              Minhas ({strategies.length})
            </TabsTrigger>
            <TabsTrigger value="public" className="transition-all data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-emerald-500/20">
              Públicas ({publicFiltered.length})
            </TabsTrigger>
            <TabsTrigger value="top" className="transition-all data-[state=active]:bg-emerald-600 data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-emerald-500/20 flex items-center gap-1">
              <Trophy className="w-4 h-4" />
              Top ({topFiltered.length})
            </TabsTrigger>
          </TabsList>

          {/* Tab: Todas */}
          <TabsContent value="all" className="space-y-6 mt-8">
            {allStrategies.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {allStrategies.map(renderMetrics)}
              </div>
            ) : (
              <div className="text-center py-12">
                <p className="text-slate-400 text-lg">Nenhuma estratégia encontrada</p>
              </div>
            )}
          </TabsContent>

          {/* Tab: Minhas Estratégias */}
          <TabsContent value="my" className="space-y-6 mt-8">
            {strategies.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {getFilteredStrategies(strategies).map(renderMetrics)}
              </div>
            ) : (
              <div className="text-center py-12">
                <p className="text-slate-400 text-lg">Você ainda não tem estratégias</p>
              </div>
            )}
          </TabsContent>

          {/* Tab: Públicas */}
          <TabsContent value="public" className="space-y-6 mt-8">
            {publicFiltered.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {publicFiltered.map(renderMetrics)}
              </div>
            ) : (
              <div className="text-center py-12">
                <p className="text-slate-400 text-lg">Nenhuma estratégia pública encontrada</p>
              </div>
            )}
          </TabsContent>

          {/* Tab: Top */}
          <TabsContent value="top" className="space-y-6 mt-8">
            {topFiltered.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {topFiltered.map((strategy, index) => (
                  <div key={strategy.id} className="relative">
                    <div className="absolute -top-4 -right-4 z-10 w-12 h-12 bg-gradient-to-br from-yellow-400 to-amber-500 rounded-full flex items-center justify-center shadow-lg">
                      <span className="text-white font-bold text-lg">#{index + 1}</span>
                    </div>
                    {renderMetrics(strategy)}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <p className="text-slate-400 text-lg">Nenhuma estratégia no top</p>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Loading State */}
        {loading && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="bg-slate-800 border border-emerald-600/30 rounded-lg p-8 shadow-2xl">
              <div className="animate-spin">
                <RotateCcw className="w-8 h-8 text-emerald-400" />
              </div>
              <p className="text-slate-300 mt-4 font-medium">Carregando estratégias...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default StrategiesPageImproved;
