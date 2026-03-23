/**
 * SingletonActivationModal Component
 * Warns user that activating this bot will deactivate another one
 * Displays which bot will be stopped and what pair it trades
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
import { AlertTriangle, RotateCcw, Zap } from 'lucide-react';

interface SingletonActivationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  currentBotName: string;
  currentBotPair: string;
  newBotName: string;
  newBotPair: string;
  costCredit?: number;
  activationCreditsRemaining?: number;
}

export const SingletonActivationModal: React.FC<
  SingletonActivationModalProps
> = ({
  isOpen,
  onClose,
  onConfirm,
  currentBotName,
  currentBotPair,
  newBotName,
  newBotPair,
  costCredit = 1,
  activationCreditsRemaining = 0,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUnderstanding, setIsUnderstanding] = useState(false);

  const hasEnoughCredits = activationCreditsRemaining > 0;

  const handleConfirm = async () => {
    if (!hasEnoughCredits) {
      setError(
        'Você não possui créditos suficientes para ativar um novo robô.'
      );
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
          : 'Erro ao ativar robô. Tente novamente.'
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
            <AlertTriangle className="w-5 h-5 text-orange-600" />
            <AlertDialogTitle>Desligar Robô Anterior</AlertDialogTitle>
          </div>
        </AlertDialogHeader>

        <div className="space-y-4 py-4">
          {/* Explanation */}
          <div className="p-3 bg-orange-50 rounded-lg border border-orange-200">
            <p className="text-sm text-orange-900">
              O Crypto Trade Hub permite apenas <strong>1 robô rodando por vez</strong>.
              Ativar um novo desligará o anterior automaticamente.
            </p>
          </div>

          {/* Current Bot (will be stopped) */}
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-700">
              ↓ Será desligado
            </p>
            <div className="p-3 bg-red-50 rounded-lg border border-red-200">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="font-semibold text-red-900">{currentBotName}</p>
                  <p className="text-xs text-red-800">{currentBotPair}</p>
                </div>
                <RotateCcw className="w-5 h-5 text-red-600 flex-shrink-0" />
              </div>
              <p className="text-xs text-red-800 mt-2">
                ⏸️ Estado será preservado. Você pode reativá-lo depois gratuitamente.
              </p>
            </div>
          </div>

          {/* Arrow / Transition */}
          <div className="flex justify-center py-2">
            <div className="text-center text-gray-400">
              <div className="text-2xl">↓</div>
              <p className="text-xs font-semibold">Transição</p>
            </div>
          </div>

          {/* New Bot (will be activated) */}
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-700">
              ↑ Será ativado
            </p>
            <div className="p-3 bg-green-50 rounded-lg border border-green-200">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="font-semibold text-green-900">{newBotName}</p>
                  <p className="text-xs text-green-800">{newBotPair}</p>
                </div>
                <Zap className="w-5 h-5 text-green-600 flex-shrink-0" />
              </div>
              <p className="text-xs text-green-800 mt-2">
                ✓ Começará a operar imediatamente.
              </p>
            </div>
          </div>

          {/* Credit Cost */}
          {costCredit > 0 && (
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-start gap-2">
                <Zap className="w-4 h-4 text-blue-600 flex-shrink-0 mt-1" />
                <div className="flex-1">
                  <p className="text-xs font-semibold text-blue-900">
                    Custo: {costCredit} Crédito
                  </p>
                  <p className="text-xs text-blue-800 mt-1">
                    Você possui{' '}
                    <strong>
                      {activationCreditsRemaining} crédito(s) disponível(is)
                    </strong>
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Understanding Checkbox */}
          <label className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors">
            <input
              type="checkbox"
              checked={isUnderstanding}
              onChange={(e) => setIsUnderstanding(e.target.checked)}
              className="w-4 h-4 mt-1 rounded border-gray-300"
            />
            <span className="text-xs text-gray-700">
              Entendo que o robô <strong>{currentBotName}</strong> será desligado
              e que não posso ter 2 robôs rodando simultaneamente.
            </span>
          </label>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-50 rounded-lg border border-red-200">
              <p className="text-xs text-red-800">
                <strong>❌ Erro:</strong> {error}
              </p>
            </div>
          )}

          {/* Pro Tip */}
          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-xs text-blue-900">
              💡 <strong>Dica:</strong> Você pode pausar qualquer robô a qualquer
              hora sem custo. Basta clicar em "Pausar".
            </p>
          </div>
        </div>

        <AlertDialogDescription className="text-center text-xs text-gray-500">
          Esta ação não pode ser desfeita. O robô anterior será parado imediatamente.
        </AlertDialogDescription>

        <div className="flex gap-3">
          <AlertDialogCancel disabled={isLoading || !isUnderstanding}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={
              isLoading ||
              !isUnderstanding ||
              !hasEnoughCredits
            }
            className={`${
              !hasEnoughCredits || !isUnderstanding
                ? 'opacity-50 cursor-not-allowed'
                : ''
            }`}
          >
            {isLoading ? (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Processando...
              </div>
            ) : (
              `✓ Confirmar & Desligar ${currentBotName}`
            )}
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default SingletonActivationModal;
