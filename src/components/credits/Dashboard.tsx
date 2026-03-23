/**
 * Dashboard Component (Example Integration)
 * Shows how to integrate all credit components together
 * Demonstrates full UI/UX flow with modals, tooltips, and gamification
 */

import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import CreditMonitor from './CreditMonitor';
import BotCard from './BotCard';
import AffiliatePanel from './AffiliatePanel';
import useCredits from '@/hooks/useCredits';
import { AlertCircle, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface DashboardProps {
  userId?: string;
  onNavigate?: (path: string) => void;
}

// Mock bot data (in real app, this would come from API)
const MOCK_BOTS = [
  {
    id: 'bot-1',
    name: 'BTC Long Strategy',
    pair: 'BTC/USDT',
    isRunning: true,
    isActiveSlot: true,
    balance: 2500.5,
    profit: 520.25,
    profitPercentage: 20.8,
    swapCount: 1,
  },
  {
    id: 'bot-2',
    name: 'ETH Grid Trading',
    pair: 'ETH/USDT',
    isRunning: false,
    isActiveSlot: false,
    balance: 1250.0,
    profit: 125.0,
    profitPercentage: 10.0,
    swapCount: 0,
  },
  {
    id: 'bot-3',
    name: 'Alt-Coin Momentum',
    pair: 'SOL/USDT',
    isRunning: false,
    isActiveSlot: false,
    balance: 500.0,
    profit: -25.0,
    profitPercentage: -5.0,
    swapCount: 2,
  },
];

// Mock affiliate data
const MOCK_AFFILIATE = {
  referralCode: 'REF123ABC456XYZ',
  referralLink: 'https://protrader-ea.com/ref/REF123ABC456XYZ',
  referredUsersCount: 8,
  commissionEarned: 125.5,
  tier: 'silver' as const,
  nextTierAt: 15,
};

export const Dashboard: React.FC<DashboardProps> = ({
  userId,
  onNavigate,
}) => {
  const {
    credits,
    isLoadingCredits,
    error: creditsError,
    startBot,
    stopBot,
    updateConfig,
    upgradePlan,
  } = useCredits();

  const [activeTab, setActiveTab] = useState('bots');

  // Find running bot
  const runningBot = MOCK_BOTS.find((b) => b.isRunning);

  if (isLoadingCredits) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Carregando dados de créditos...</p>
        </div>
      </div>
    );
  }

  if (!credits) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-red-900">Erro ao carregar créditos</h3>
            <p className="text-sm text-red-800 mt-1">
              {creditsError || 'Não foi possível carregar suas informações de crédito.'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">
          Gerencie seus robôs e créditos de ativação
        </p>
      </div>

      {/* Credit Monitor - Always Visible */}
      <div className="sticky top-6 z-10">
        <CreditMonitor
          plan={credits.plan}
          activationCredits={credits.activationCredits}
          activationCreditsUsed={credits.activationCreditsUsed}
          activationCreditsRemaining={credits.activationCreditsRemaining}
          activeBotsCount={credits.activeBotsCount}
          onUpgradeClick={() => onNavigate?.('/upgrade')}
        />
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="bots">Robôs ({MOCK_BOTS.length})</TabsTrigger>
          <TabsTrigger value="affiliate">Referência</TabsTrigger>
          <TabsTrigger value="history">Histórico</TabsTrigger>
        </TabsList>

        {/* Bots Tab */}
        <TabsContent value="bots" className="space-y-4">
          {/* Warning if no credits */}
          {credits.activationCreditsRemaining === 0 && (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold text-yellow-900">
                  Você não tem créditos disponíveis
                </p>
                <p className="text-sm text-yellow-800 mt-1">
                  Atualize seu plano para ativar novos robôs e continuar operando.
                </p>
                <Button
                  onClick={() => onNavigate?.('/upgrade')}
                  size="sm"
                  className="mt-3 bg-yellow-600 hover:bg-yellow-700"
                >
                  Atualizar Plano →
                </Button>
              </div>
            </div>
          )}

          {/* Bots Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {MOCK_BOTS.map((bot) => (
              <BotCard
                key={bot.id}
                botId={bot.id}
                botName={bot.name}
                tradingPair={bot.pair}
                isRunning={bot.isRunning}
                isActiveSlot={bot.isActiveSlot}
                balance={bot.balance}
                profit={bot.profit}
                profitPercentage={bot.profitPercentage}
                swapCount={bot.swapCount}
                activationCreditsRemaining={
                  credits.activationCreditsRemaining
                }
                otherRunningBot={
                  runningBot && runningBot.id !== bot.id
                    ? {
                        id: runningBot.id,
                        name: runningBot.name,
                        pair: runningBot.pair,
                      }
                    : undefined
                }
                onStart={async (botId) => {
                  await startBot(botId);
                }}
                onStop={async (botId) => {
                  await stopBot(botId);
                }}
                onConfigUpdate={async (botId, config) => {
                  await updateConfig({ botId, config });
                }}
                onViewDetails={(botId) => {
                  onNavigate?.(`/bots/${botId}`);
                }}
              />
            ))}

            {/* Add New Bot Card */}
            <div
              onClick={() => onNavigate?.('/bots/new')}
              className="border-2 border-dashed border-gray-300 rounded-lg p-6 flex items-center justify-center cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors"
            >
              <div className="text-center">
                <Plus className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="font-semibold text-gray-900">Criar Novo Robô</p>
                <p className="text-sm text-gray-600 mt-1">
                  Configure um novo bot de trading
                </p>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Affiliate Tab */}
        <TabsContent value="affiliate" className="space-y-4">
          <AffiliatePanel
            referralCode={MOCK_AFFILIATE.referralCode}
            referralLink={MOCK_AFFILIATE.referralLink}
            referredUsersCount={MOCK_AFFILIATE.referredUsersCount}
            commissionEarned={MOCK_AFFILIATE.commissionEarned}
            tier={MOCK_AFFILIATE.tier}
            nextTierAt={MOCK_AFFILIATE.nextTierAt}
            onShareClick={() => {
              // Handle share
              const text = `Junte-se a mim no Crypto Trade Hub! Use meu código: ${MOCK_AFFILIATE.referralCode}`;
              if (navigator.share) {
                navigator.share({
                  title: 'Crypto Trade Hub',
                  text,
                  url: MOCK_AFFILIATE.referralLink,
                });
              }
            }}
          />
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4">
          <div className="p-6 bg-gray-50 border border-gray-200 rounded-lg text-center">
            <p className="text-gray-600">
              Histórico de transações será exibido aqui
            </p>
            <p className="text-sm text-gray-500 mt-2">
              (Integração pendente com backend)
            </p>
          </div>
        </TabsContent>
      </Tabs>

      {/* Bottom Tips */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="font-semibold text-blue-900">💡 Dica: Ative o Bot</p>
          <p className="text-sm text-blue-800 mt-2">
            Ativar um novo robô consome 1 crédito. Reativações são grátis.
          </p>
        </div>
        <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
          <p className="font-semibold text-purple-900">🔄 Dica: Swaps</p>
          <p className="text-sm text-purple-800 mt-2">
            2 primeiros swaps por mês são grátis. Depois, 1 crédito cada.
          </p>
        </div>
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="font-semibold text-green-900">🎯 Dica: Singleton</p>
          <p className="text-sm text-green-800 mt-2">
            Apenas 1 robô pode rodar por vez. Usar ativação smart do sistema.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
