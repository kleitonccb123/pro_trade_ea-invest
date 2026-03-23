/**
 * BotStartButton Component
 * Start button with credit validation, singleton warnings, and loading states
 * Integrated credit checking and visual feedback
 */

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import {
  AlertCircle,
  Play,
  Pause,
  Zap,
  Lock,
  Clock,
  RotateCcw,
  CheckCircle2,
} from 'lucide-react';
import ConfettiExplosion from 'react-confetti-explosion';

interface BotStartButtonProps {
  botId: string;
  botName: string;
  botPair: string;
  isRunning: boolean;
  isActiveSlot: boolean;
  swapCount: number;
  activationCreditsRemaining: number;
  otherRunningBot?: {
    id: string;
    name: string;
    pair: string;
  };
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  onSingletonWarning?: (otherBot: any) => void;
  showSkeletonAnimation?: boolean;
}

export const BotStartButton: React.FC<BotStartButtonProps> = ({
  botId,
  botName,
  botPair,
  isRunning,
  isActiveSlot,
  swapCount,
  activationCreditsRemaining,
  otherRunningBot,
  onStart,
  onStop,
  onSingletonWarning,
  showSkeletonAnimation = false,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canStart = activationCreditsRemaining > 0 && !isLoading;
  const hasJustActivated = isActiveSlot && !isRunning;

  const handleStart = async () => {
    // Trigger singleton warning if another bot is running
    if (otherRunningBot && onSingletonWarning) {
      onSingletonWarning(otherRunningBot);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await onStart();
      setShowConfetti(true);
      setTimeout(() => setShowConfetti(false), 2500);

      // Auto-close error after success
      setTimeout(() => setError(null), 3000);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Erro ao iniciar robô. Tente novamente.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    setError(null);

    try {
      await onStop();
      setTimeout(() => setError(null), 3000);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Erro ao parar robô. Tente novamente.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (showSkeletonAnimation) {
    return (
      <div className="loader-animation w-full">
        <div className="relative w-full overflow-hidden rounded-lg h-10 bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200 bg-[length:200%_100%] animate-pulse" />
      </div>
    );
  }

  // If running: show STOP button
  if (isRunning) {
    return (
      <TooltipProvider>
        <div className="space-y-2 w-full">
          {/* Active Status Badge */}
          <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
            <CheckCircle2 className="w-4 h-4 text-green-600 animate-pulse" />
            <span className="text-xs font-semibold text-green-900">
              {botName} está operando ({botPair})
            </span>
          </div>

          {/* Swaps Info */}
          {swapCount > 0 && (
            <div className="text-xs text-gray-600 px-3 py-1">
              {swapCount < 2
                ? `📊 ${2 - swapCount} swap(s) grátis restante(s)`
                : `⚡ Próximos swaps custarão 1 crédito cada`}
            </div>
          )}

          {/* Stop Button */}
          <Button
            onClick={handleStop}
            disabled={isLoading}
            variant="destructive"
            size="sm"
            className="w-full"
          >
            {isLoading ? (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Parando...
              </div>
            ) : (
              <>
                <Pause className="w-4 h-4 mr-2" />
                Parar Robô
              </>
            )}
          </Button>

          {error && (
            <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">
              {error}
            </div>
          )}
        </div>
      </TooltipProvider>
    );
  }

  // If inactive slot and credits available: show START button
  return (
    <TooltipProvider>
      <div className="space-y-2 w-full">
        {/* Confetti Animation */}
        {showConfetti && <ConfettiExplosion particleCount={30} />}

        {/* Status Messages */}
        {!isActiveSlot && activationCreditsRemaining === 0 && (
          <div className="flex items-start gap-2 p-2 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-red-800">
              <p className="font-semibold">Sem créditos</p>
              <p>Você precisa de 1 crédito para ativar este robô</p>
            </div>
          </div>
        )}

        {hasJustActivated && (
          <div className="flex items-start gap-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
            <Clock className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-blue-800">
              <p className="font-semibold">Slot ativo</p>
              <p>Robô pronto para iniciar operações</p>
            </div>
          </div>
        )}

        {otherRunningBot && (
          <div className="flex items-start gap-2 p-2 bg-yellow-50 border border-yellow-200 rounded-lg">
            <AlertCircle className="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-yellow-800">
              <p className="font-semibold">⚠️ Outro robô em operação</p>
              <p>
                {otherRunningBot.name} ({otherRunningBot.pair}) será desligado
              </p>
            </div>
          </div>
        )}

        {/* Start Button */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              onClick={handleStart}
              disabled={isLoading || !canStart}
              variant={isActiveSlot ? 'default' : 'secondary'}
              size="sm"
              className={`w-full ${
                !canStart ? 'opacity-60 cursor-not-allowed' : ''
              } ${
                isActiveSlot
                  ? 'bg-green-600 hover:bg-green-700'
                  : 'bg-gray-400 hover:bg-gray-500'
              }`}
            >
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Iniciando...
                </div>
              ) : !isActiveSlot ? (
                <>
                  <Lock className="w-4 h-4 mr-2" />
                  Ativar Slot ({activationCreditsRemaining} crédito)
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Iniciar Robô
                </>
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {!canStart && activationCreditsRemaining === 0 && (
              <div className="text-xs">
                <p className="font-semibold">Sem créditos disponíveis</p>
                <p>Atualize seu plano para continuar</p>
              </div>
            )}
            {isActiveSlot && (
              <div className="text-xs">
                <p className="font-semibold">Robô pronto!</p>
                <p>Clique para iniciar operações</p>
              </div>
            )}
            {!isActiveSlot && canStart && (
              <div className="text-xs">
                <p className="font-semibold">Ativar este robô</p>
                <p>Consumirá 1 crédito do seu plano</p>
              </div>
            )}
          </TooltipContent>
        </Tooltip>

        {/* Swap Status */}
        {isActiveSlot && (
          <div className="text-xs text-gray-600 px-3 py-1">
            {swapCount < 2
              ? `${2 - swapCount} de 2 swaps grátis`
              : `Swaps: ${swapCount} realizados`}
          </div>
        )}

        {error && (
          <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">
            {error}
          </div>
        )}
      </div>
    </TooltipProvider>
  );
};

export default BotStartButton;
