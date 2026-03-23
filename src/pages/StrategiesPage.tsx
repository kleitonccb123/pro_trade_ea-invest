/**
 * StrategiesPage.tsx - Página Refatorada de Estratégias
 * 
 * Layout:
 * 1. CreditMonitor Sticky no topo (ação bar)
 * 2. TopStrategies (carrossel de top performance)
 * 3. Abas para: Todas as Estratégias, Meus Robôs, Rankings
 * 4. Cards refatorados com design moderno
 */

import React, { useEffect, useState } from 'react';
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
import { Plus, Search, Filter, GripHorizontal, AlertCircle } from 'lucide-react';
import CreditMonitor from '@/components/credits/CreditMonitor';
import TopStrategies from '@/components/strategies/TopStrategies';
import StrategyCard from '@/components/strategies/StrategyCard';
import { API_BASE_URL } from '@/config/constants';
import { authService } from '@/services/authService';

// Types
interface Strategy {
  id: string;
  name: string;
  description: string;
  winRate: number;
  monthlyReturn: number;
  riskLevel: 'low' | 'medium' | 'high';
  isPublic: boolean;
  isActive: boolean;
  isMyStrategy: boolean;
  activations: number;
  avgProfit: number;
  swapsUsed?: number;
  maxSwaps?: number;
  createdAt: string;
}

interface UserCredits {
  plan: 'starter' | 'pro' | 'premium';
  activationCredits: number;
  activationCreditsUsed: number;
  activationCreditsRemaining: number;
  activeBotsCount: number;
  maxActiveBots: number;
}

const StrategiesPage: React.FC = () => {
  // State
  const [activeTab, setActiveTab] = useState<'all' | 'my' | 'rankings'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [riskFilter, setRiskFilter] = useState<'all' | 'low' | 'medium' | 'high'>('all');
  const [sortBy, setSortBy] = useState<'name' | 'winRate' | 'return'>('winRate');
  const [loading, setLoading] = useState(false);
  const [isKillSwitchLoading, setIsKillSwitchLoading] = useState(false);

  // Mock Data - Substituir por chamadas reais à API
  const [userCredits, setUserCredits] = useState<UserCredits>({
    plan: 'pro',
    activationCredits: 5,
    activationCreditsUsed: 2,
    activationCreditsRemaining: 3,
    activeBotsCount: 2,
    maxActiveBots: 5,
  });

  const [allStrategies, setAllStrategies] = useState<Strategy[]>([
    {
      id: '1',
      name: 'Grid Trading 24/7',
      description: 'Estratégia de grid trading contínuo com rebalanceamento automático',
      winRate: 78.5,
      monthlyReturn: 12.3,
      riskLevel: 'low',
      isPublic: true,
      isActive: true,
      isMyStrategy: true,
      activations: 342,
      avgProfit: 145.60,
      swapsUsed: 1,
      maxSwaps: 2,
      createdAt: '2024-01-15',
    },
    {
      id: '2',
      name: 'DCA Plus Momentum',
      description: 'Dollar Cost Averaging com gatilho de momentum para maximize gains',
      winRate: 65.2,
      monthlyReturn: 8.7,
      riskLevel: 'low',
      isPublic: true,
      isActive: false,
      isMyStrategy: false,
      activations: 215,
      avgProfit: 98.30,
      createdAt: '2024-02-01',
    },
    {
      id: '3',
      name: 'Swing Trader Pro',
      description: 'Identifica swing points com análise técnica avançada',
      winRate: 72.1,
      monthlyReturn: 15.8,
      riskLevel: 'medium',
      isPublic: true,
      isActive: true,
      isMyStrategy: false,
      activations: 289,
      avgProfit: 187.45,
      createdAt: '2024-01-28',
    },
    {
      id: '4',
      name: 'Dynamic Hedging',
      description: 'Proteção automática de posições com correlação dinâmica',
      winRate: 55.3,
      monthlyReturn: 22.5,
      riskLevel: 'high',
      isPublic: false,
      isActive: false,
      isMyStrategy: true,
      activations: 45,
      avgProfit: 312.78,
      swapsUsed: 2,
      maxSwaps: 2,
      createdAt: '2024-02-08',
    },
  ]);

  // Load data on mount
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // Fetch user activations from backend
        const token = await authService.getAccessToken();
        const activationsResponse = await fetch(`${API_BASE_URL}/me/activations`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (activationsResponse.ok) {
          const creditsData = await activationsResponse.json();
          setUserCredits({
            plan: creditsData.plan,
            activationCredits: creditsData.activationCredits,
            activationCreditsUsed: creditsData.activationCreditsUsed,
            activationCreditsRemaining: creditsData.activationCreditsRemaining,
            activeBotsCount: creditsData.activeBotsCount,
            maxActiveBots: creditsData.maxActiveBots,
          });
        } else {
          console.warn('[⚠] Failed to fetch activation data, using defaults');
        }

        // TODO: Fetch strategies from backend when endpoint is available
        // const strategiesResponse = await fetch(`${API_BASE_URL}/api/strategies`);
        // if (strategiesResponse.ok) {
        //   const stratData = await strategiesResponse.json();
        //   setAllStrategies(stratData);
        // }
      } catch (error) {
        console.error('[✗] Error loading activation data:', error);
        // Keep the mock data as fallback
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // Filters e Sorting
  const filteredStrategies = allStrategies.filter((strategy) => {
    const matchesSearch =
      strategy.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      strategy.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRisk = riskFilter === 'all' || strategy.riskLevel === riskFilter;
    const matchesTab =
      activeTab === 'all' ||
      (activeTab === 'my' && strategy.isMyStrategy) ||
      (activeTab === 'rankings' && strategy.isPublic);

    return matchesSearch && matchesRisk && matchesTab;
  });

  const sortedStrategies = [...filteredStrategies].sort((a, b) => {
    if (sortBy === 'name') {
      return a.name.localeCompare(b.name);
    } else if (sortBy === 'winRate') {
      return b.winRate - a.winRate;
    } else if (sortBy === 'return') {
      return b.monthlyReturn - a.monthlyReturn;
    }
    return 0;
  });

  // Handlers
  const handleActivateStrategy = async (strategyId: string) => {
    // TODO: Implementar lógica real
    console.log('Ativar estratégia:', strategyId);
  };

  const handleKillSwitch = async () => {
    setIsKillSwitchLoading(true);
    try {
      // TODO: Chamar API para desativar todos os bots
      await new Promise((resolve) => setTimeout(resolve, 1000));
      // Simular update
      setUserCredits((prev) => ({ ...prev, activeBotsCount: 0 }));
    } finally {
      setIsKillSwitchLoading(false);
    }
  };

  const handleUpgrade = () => {
    // TODO: Redirecionar para página de planos
    console.log('Upgrade clicked');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
      {/* Sticky Header com CreditMonitor */}
      <div className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-slate-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <CreditMonitor
            plan={userCredits.plan}
            activationCredits={userCredits.activationCredits}
            activationCreditsUsed={userCredits.activationCreditsUsed}
            activationCreditsRemaining={userCredits.activationCreditsRemaining}
            activeBotsCount={userCredits.activeBotsCount}
            maxActiveBots={userCredits.maxActiveBots}
            onUpgradeClick={handleUpgrade}
            onKillSwitch={handleKillSwitch}
            isKillSwitchLoading={isKillSwitchLoading}
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* TopStrategies Carousel */}
        <TopStrategies
          strategies={allStrategies.filter((s) => s.isPublic)}
          onActivate={handleActivateStrategy}
          timeRange="30d"
        />

        {/* Estratégias Section */}
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-white">Estratégias de Trading</h2>
              <p className="text-slate-400 mt-1">
                Gerenciar e ativar suas estratégias de trading automático
              </p>
            </div>
            <Button className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold">
              <Plus className="w-4 h-4 mr-2" />
              Nova Estratégia
            </Button>
          </div>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
            <TabsList className="bg-slate-800/50 border border-slate-700">
              <TabsTrigger
                value="all"
                className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white"
              >
                Todas as Estratégias ({allStrategies.length})
              </TabsTrigger>
              <TabsTrigger
                value="my"
                className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white"
              >
                Meus Robôs ({allStrategies.filter((s) => s.isMyStrategy).length})
              </TabsTrigger>
              <TabsTrigger
                value="rankings"
                className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white"
              >
                Comunidade ({allStrategies.filter((s) => s.isPublic && !s.isMyStrategy).length})
              </TabsTrigger>
            </TabsList>

            {/* Filters and Sort */}
            <div className="flex gap-3 flex-wrap mt-6">
              {/* Search */}
              <div className="flex-1 min-w-xs relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <Input
                  placeholder="Buscar estratégias..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 bg-slate-800 border-slate-700 text-white placeholder-slate-500"
                />
              </div>

              {/* Risk Filter */}
              <Select value={riskFilter} onValueChange={(v) => setRiskFilter(v as typeof riskFilter)}>
                <SelectTrigger className="w-40 bg-slate-800 border-slate-700 text-white">
                  <Filter className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Risco" />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700">
                  <SelectItem value="all">Todos os Riscos</SelectItem>
                  <SelectItem value="low">Baixo Risco</SelectItem>
                  <SelectItem value="medium">Médio Risco</SelectItem>
                  <SelectItem value="high">Alto Risco</SelectItem>
                </SelectContent>
              </Select>

              {/* Sort */}
              <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
                <SelectTrigger className="w-40 bg-slate-800 border-slate-700 text-white">
                  <GripHorizontal className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Ordenar por" />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700">
                  <SelectItem value="winRate">Taxa de Acerto</SelectItem>
                  <SelectItem value="return">Retorno Mensal</SelectItem>
                  <SelectItem value="name">Nome (A-Z)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Grid de Estratégias */}
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mt-6">
              {loading ? (
                <div className="col-span-full text-center py-12">
                  <div className="inline-block">
                    <div className="w-12 h-12 border-4 border-slate-600 border-t-indigo-500 rounded-full animate-spin"></div>
                    <p className="text-slate-400 mt-4">Carregando estratégias...</p>
                  </div>
                </div>
              ) : sortedStrategies.length === 0 ? (
                <div className="col-span-full flex flex-col items-center justify-center py-12 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-slate-400 mb-4">Nenhuma estratégia encontrada</p>
                  <Button className="bg-indigo-600 hover:bg-indigo-700">
                    <Plus className="w-4 h-4 mr-2" />
                    Criar Primeira Estratégia
                  </Button>
                </div>
              ) : (
                sortedStrategies.map((strategy) => (
                  <StrategyCard
                    key={strategy.id}
                    {...strategy}
                    onActivate={handleActivateStrategy}
                    onEdit={() => console.log('Edit:', strategy.id)}
                    onDelete={() => console.log('Delete:', strategy.id)}
                    onToggleVisibility={() => console.log('Toggle:', strategy.id)}
                  />
                ))
              )}
            </div>

            {/* Empty State for each tab */}
            {!loading && sortedStrategies.length === 0 && activeTab === 'my' && (
              <div className="col-span-full text-center py-12">
                <p className="text-slate-400 mb-4">Você ainda não criou nenhuma estratégia</p>
              </div>
            )}
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default StrategiesPage;
