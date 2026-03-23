/**
 * BotCard Component (Updated)
 * Enhanced bot card showing credit status, swap count, and activation state
 * Full integration with credit system
 */

import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Zap,
  AlertCircle,
  MoreVertical,
  ExternalLink,
} from 'lucide-react';
import BotStartButton from './BotStartButton';
import SwapConfirmationModal from './SwapConfirmationModal';
import SingletonActivationModal from './SingletonActivationModal';
import { Button } from '@/components/ui/button';

interface BotCardProps {
  botId: string;
  botName: string;
  tradingPair: string;
  isRunning: boolean;
  isActiveSlot: boolean;
  balance: number;
  profit: number;
  profitPercentage: number;
  swapCount: number;
  activationCreditsRemaining: number;
  otherRunningBot?: {
    id: string;
    name: string;
    pair: string;
  };
  chartData?: Array<{ time: string; pnl: number }>;
  onStart: (botId: string) => Promise<void>;
  onStop: (botId: string) => Promise<void>;
  onConfigUpdate: (botId: string, config: any) => Promise<void>;
  onViewDetails?: (botId: string) => void;
}

const mockChartData = [
  { time: '00:00', pnl: 0 },
  { time: '04:00', pnl: 150 },
  { time: '08:00', pnl: 200 },
  { time: '12:00', pnl: 180 },
  { time: '16:00', pnl: 320 },
  { time: '20:00', pnl: 450 },
  { time: '24:00', pnl: 520 },
];

export const BotCard: React.FC<BotCardProps> = ({
  botId,
  botName,
  tradingPair,
  isRunning,
  isActiveSlot,
  balance,
  profit,
  profitPercentage,
  swapCount,
  activationCreditsRemaining,
  otherRunningBot,
  chartData = mockChartData,
  onStart,
  onStop,
  onConfigUpdate,
  onViewDetails,
}) => {
  const [showSwapModal, setShowSwapModal] = useState(false);
  const [showSingletonModal, setShowSingletonModal] = useState(false);
  const [selectedConfig, setSelectedConfig] = useState<any>(null);

  const isFreeSwap = swapCount < 2;
  const isProfitable = profit >= 0;

  const handleConfigClick = () => {
    setSelectedConfig({}); // Would be filled with actual config
    setShowSwapModal(true);
  };

  const handleSwapConfirm = async () => {
    if (selectedConfig && onConfigUpdate) {
      await onConfigUpdate(botId, selectedConfig);
      setShowSwapModal(false);
    }
  };

  const handleStartClick = async () => {
    if (otherRunningBot) {
      setShowSingletonModal(true);
    } else {
      await onStart(botId);
    }
  };

  const handleSingletonConfirm = async () => {
    await onStart(botId);
    setShowSingletonModal(false);
  };

  return (
    <>
      <Card className="overflow-hidden hover:shadow-lg transition-shadow">
        {/* Header */}
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <CardTitle className="text-lg">{botName}</CardTitle>
                {isRunning && (
                  <Badge variant="default" className="bg-green-600">
                    ◆ Ativo
                  </Badge>
                )}
                {!isRunning && isActiveSlot && (
                  <Badge variant="secondary">Pronto</Badge>
                )}
                {!isActiveSlot && (
                  <Badge variant="outline">Inativo</Badge>
                )}
              </div>
              <CardDescription>{tradingPair}</CardDescription>
            </div>
            <Button variant="ghost" size="sm">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Key Metrics */}
          <div className="grid grid-cols-3 gap-3">
            {/* Balance */}
            <div className="p-2 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-800 font-semibold">Saldo</p>
              <p className="text-lg font-bold text-blue-900">
                ${balance.toFixed(2)}
              </p>
            </div>

            {/* Profit */}
            <div className={`p-2 rounded-lg ${
              isProfitable ? 'bg-green-50' : 'bg-red-50'
            }`}>
              <p className={`text-xs font-semibold ${
                isProfitable ? 'text-green-800' : 'text-red-800'
              }`}>
                PnL
              </p>
              <div className="flex items-center gap-1">
                <p className={`text-lg font-bold ${
                  isProfitable ? 'text-green-900' : 'text-red-900'
                }`}>
                  ${profit.toFixed(2)}
                </p>
                {isProfitable ? (
                  <TrendingUp className="w-4 h-4 text-green-600" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-red-600" />
                )}
              </div>
            </div>

            {/* Return % */}
            <div className={`p-2 rounded-lg ${
              isProfitable ? 'bg-purple-50' : 'bg-orange-50'
            }`}>
              <p className={`text-xs font-semibold ${
                isProfitable ? 'text-purple-800' : 'text-orange-800'
              }`}>
                Return
              </p>
              <p className={`text-lg font-bold ${
                isProfitable ? 'text-purple-900' : 'text-orange-900'
              }`}>
                {profitPercentage.toFixed(1)}%
              </p>
            </div>
          </div>

          {/* Swap Status Alert */}
          {isActiveSlot && swapCount >= 2 && (
            <div className="flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded-lg">
              <Zap className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-amber-900">
                <p className="font-semibold">⚡ Próximos swaps custam crédito</p>
                <p className="text-amber-800">
                  Você realizou {swapCount} swaps. Alterações adicionais custarão
                  1 crédito cada.
                </p>
              </div>
            </div>
          )}

          {/* Chart Preview */}
          {isRunning && (
            <div className="h-40 bg-gray-50 rounded-lg border border-gray-200">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" style={{ fontSize: '11px' }} />
                  <YAxis style={{ fontSize: '11px' }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="pnl"
                    stroke="#3b82f6"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2">
            <div className="flex-1">
              <BotStartButton
                botId={botId}
                botName={botName}
                botPair={tradingPair}
                isRunning={isRunning}
                isActiveSlot={isActiveSlot}
                swapCount={swapCount}
                activationCreditsRemaining={activationCreditsRemaining}
                otherRunningBot={otherRunningBot}
                onStart={() => handleStartClick()}
                onStop={() => onStop(botId)}
                showSkeletonAnimation={false}
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={onViewDetails ? () => onViewDetails(botId) : undefined}
              className="flex-shrink-0"
            >
              <ExternalLink className="w-4 h-4" />
            </Button>
          </div>

          {/* Config Update Button (visible for active slot) */}
          {isActiveSlot && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleConfigClick}
              className="w-full"
            >
              ⚙️ Editar Configuração
              {!isFreeSwap && <Zap className="w-3 h-3 ml-2" />}
            </Button>
          )}

          {/* Pro-tip */}
          {isActiveSlot && !isRunning && (
            <div className="p-2 bg-blue-50 text-xs text-blue-900 rounded-lg">
              💡 Bot pronto. Clique em "Iniciar Robô" para começar a operar.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Swap Confirmation Modal */}
      <SwapConfirmationModal
        isOpen={showSwapModal}
        onClose={() => setShowSwapModal(false)}
        onConfirm={handleSwapConfirm}
        swapCount={swapCount}
        activationCreditsRemaining={activationCreditsRemaining}
        botName={botName}
        changesSummary={`Atualizando pair para ${tradingPair}`}
      />

      {/* Singleton Activation Modal */}
      {otherRunningBot && (
        <SingletonActivationModal
          isOpen={showSingletonModal}
          onClose={() => setShowSingletonModal(false)}
          onConfirm={handleSingletonConfirm}
          currentBotName={otherRunningBot.name}
          currentBotPair={otherRunningBot.pair}
          newBotName={botName}
          newBotPair={tradingPair}
          costCredit={1}
          activationCreditsRemaining={activationCreditsRemaining}
        />
      )}
    </>
  );
};

export default BotCard;
