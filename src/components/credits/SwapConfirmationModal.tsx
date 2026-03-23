/**
 * SwapConfirmationModal Component
 * Displays warning when user wants to modify bot configuration
 * Warns about free swaps vs credit consumption
 */

import React, { useState } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import {
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Clock,
} from 'lucide-react';

interface SwapConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  swapCount: number;
  activationCreditsRemaining: number;
  botName: string;
  changesSummary?: string;
}

export const SwapConfirmationModal: React.FC<SwapConfirmationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  swapCount,
  activationCreditsRemaining,
  botName,
  changesSummary = 'sua configuração',
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isFreeSwap = swapCount < 2;
  const costCredit = !isFreeSwap;
  const hasEnoughCredits = activationCreditsRemaining > 0;
  const remainingFreeSwaps = 2 - swapCount;

  const handleConfirm = async () => {
    if (!hasEnoughCredits && costCredit) {
      setError('Você não possui créditos suficientes para fazer esta alteração.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Erro ao processar alteração. Tente novamente.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <div className="flex items-center gap-2">
            {costCredit ? (
              <AlertTriangle className="w-5 h-5 text-amber-600" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-green-600" />
            )}
            <AlertDialogTitle>
              {costCredit ? 'Custo de Crédito' : 'Swap Grátis'}
            </AlertDialogTitle>
          </div>
        </AlertDialogHeader>

        <div className="space-y-4 py-4">
          {/* Bot Name */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Robô:</span>
            <Badge variant="outline">{botName}</Badge>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-3 p-3 rounded-lg bg-gradient-to-r from-blue-50 to-blue-100 border border-blue-200">
            {isFreeSwap ? (
              <>
                <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0" />
                <div className="text-sm">
                  <p className="font-semibold text-green-900">
                    ✓ Swap Grátis
                  </p>
                  <p className="text-xs text-green-800">
                    Você ainda possui {remainingFreeSwaps === 1 ? '1 swap grátis' : `${remainingFreeSwaps} swaps grátis`} este mês
                  </p>
                </div>
              </>
            ) : !hasEnoughCredits ? (
              <>
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                <div className="text-sm">
                  <p className="font-semibold text-red-900">
                    ❌ Créditos Insuficientes
                  </p>
                  <p className="text-xs text-red-800">
                    Você precisa de 1 crédito para fazer esta alteração
                  </p>
                </div>
              </>
            ) : (
              <>
                <Zap className="w-5 h-5 text-amber-600 flex-shrink-0" />
                <div className="text-sm">
                  <p className="font-semibold text-amber-900">
                    ⚡ Consumirá 1 Crédito
                  </p>
                  <p className="text-xs text-amber-800">
                    Você tem {activationCreditsRemaining} crédito(s) disponível(is)
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Change Summary */}
          {changesSummary && (
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
              <p className="text-xs text-gray-600 font-semibold mb-1">
                Alterações
              </p>
              <p className="text-sm text-gray-800">{changesSummary}</p>
            </div>
          )}

          {/* Swap History */}
          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-start gap-2">
              <Clock className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs">
                <p className="font-semibold text-blue-900 mb-1">
                  Histórico de Swaps
                </p>
                <div className="space-y-1 text-blue-800">
                  <p>
                    • <strong>Swaps realizados:</strong> {swapCount} / ∞
                  </p>
                  <p>
                    • <strong>Swaps grátis:</strong> {swapCount < 2 ? 2 - swapCount : 0} / 2
                  </p>
                  {swapCount >= 2 && (
                    <p>
                      • <strong>Próximo custo:</strong> 1 crédito
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-50 rounded-lg border border-red-200">
              <p className="text-xs text-red-800">
                <strong>Erro:</strong> {error}
              </p>
            </div>
          )}

          {/* Pro Tip */}
          {isFreeSwap && remainingFreeSwaps === 1 && (
            <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-200">
              <p className="text-xs text-yellow-800">
                💡 <strong>Dica:</strong> Este é seu último swap grátis. Próximas alterações custarão 1 crédito cada.
              </p>
            </div>
          )}
        </div>

        <AlertDialogDescription className="text-center text-xs text-gray-500">
          Esta ação não pode ser desfeita. O robô será reconfigurado imediatamente.
        </AlertDialogDescription>

        <div className="flex gap-3">
          <AlertDialogCancel disabled={isLoading}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isLoading || !hasEnoughCredits}
            className={`${
              costCredit && hasEnoughCredits
                ? 'bg-amber-600 hover:bg-amber-700'
                : 'bg-green-600 hover:bg-green-700'
            } ${!hasEnoughCredits ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isLoading ? (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Processando...
              </div>
            ) : isFreeSwap ? (
              '✓ Confirmar Swap Grátis'
            ) : (
              `⚡ Consumir 1 Crédito e Confirmar`
            )}
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default SwapConfirmationModal;
