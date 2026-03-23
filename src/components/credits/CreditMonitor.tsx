/**
 * CreditMonitor Component - Action Bar
 * Displays current credit balance, plan status, and emergency kill switch
 * Shows activation credits, usage, and plan information
 */

import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Coins, TrendingUp, AlertCircle, Lock, Power, Zap } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface CreditMonitorProps {
  plan?: 'starter' | 'pro' | 'premium';
  activationCredits?: number;
  activationCreditsUsed?: number;
  activationCreditsRemaining?: number;
  activeBotsCount?: number;
  maxActiveBots?: number;
  onUpgradeClick?: () => void;
  onKillSwitch?: () => void;
  isKillSwitchLoading?: boolean;
}

const PLAN_CONFIG = {
  starter: {
    label: 'Starter',
    totalCredits: 1,
    color: 'bg-blue-100 text-blue-800',
    borderColor: 'border-blue-300',
    accentColor: 'text-blue-600',
  },
  pro: {
    label: 'Pro',
    totalCredits: 5,
    color: 'bg-purple-100 text-purple-800',
    borderColor: 'border-purple-300',
    accentColor: 'text-purple-600',
  },
  premium: {
    label: 'Premium',
    totalCredits: 15,
    color: 'bg-amber-100 text-amber-800',
    borderColor: 'border-amber-300',
    accentColor: 'text-amber-600',
  },
};

export const CreditMonitor: React.FC<CreditMonitorProps> = ({
  plan = 'starter',
  activationCredits = 1,
  activationCreditsUsed = 0,
  activationCreditsRemaining = 1,
  activeBotsCount = 0,
  maxActiveBots = 3,
  onUpgradeClick,
  onKillSwitch,
  isKillSwitchLoading = false,
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [showKillDialog, setShowKillDialog] = useState(false);
  const config = PLAN_CONFIG[plan] || PLAN_CONFIG.starter;
  const progressPercentage = (activationCreditsUsed / activationCredits) * 100;
  const botsPercentage = (activeBotsCount / maxActiveBots) * 100;

  const getStatusMessage = () => {
    if (activationCreditsRemaining === 0) {
      return 'Sem créditos disponíveis';
    }
    if (activationCreditsRemaining === 1) {
      return 'Apenas 1 crédito restante';
    }
    return `${activationCreditsRemaining} créditos disponíveis`;
  };

  const getWarningStatus = () => {
    if (activationCreditsRemaining === 0) return 'danger';
    if (activationCreditsRemaining <= 2) return 'warning';
    return 'success';
  };

  return (
    <TooltipProvider>
      <Card className={`border-l-4 ${config.borderColor} bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 shadow-lg`}>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 flex-1">
              <div className={`p-2 rounded-lg ${config.color}`}>
                <Coins className={`w-5 h-5 ${config.accentColor}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <CardTitle className="text-lg">Painel de Controle</CardTitle>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Badge className={config.color} variant="secondary">
                        {config.label}
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="font-semibold mb-2">Seu Plano: {config.label}</p>
                      <ul className="text-xs space-y-1">
                        <li>✓ {config.totalCredits} créditos/mês</li>
                        <li>✓ Ativar novo robô = 1 crédito</li>
                        <li>✓ Reativar robô = Grátis</li>
                        <li>✓ Swaps: 2 grátis + 1 crédito cada</li>
                      </ul>
                    </TooltipContent>
                  </Tooltip>
                </div>
                <CardDescription className="text-sm">
                  {getStatusMessage()}
                </CardDescription>
              </div>
            </div>

            {/* Kill Switch Button */}
            {activeBotsCount > 0 && (
              <div className="flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      onClick={() => setShowKillDialog(true)}
                      disabled={isKillSwitchLoading}
                      variant="destructive"
                      size="sm"
                      className="bg-red-600/80 hover:bg-red-700 text-white animate-pulse"
                    >
                      <Power className="w-4 h-4 mr-2" />
                      Kill Switch
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Desativar TODOS os robôs instantaneamente</p>
                  </TooltipContent>
                </Tooltip>
              </div>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Credits Progress */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-slate-300">Créditos de Ativação</span>
              <span className={`text-sm font-bold ${config.accentColor}`}>
                {activationCreditsUsed} / {activationCredits}
              </span>
            </div>
            <Progress
              value={progressPercentage}
              className="h-2"
            />
          </div>

          {/* Bots Progress */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <span className="text-sm font-medium text-slate-300">Slots de Ativação</span>
              </div>
              <span className="text-sm font-bold text-amber-400">
                {activeBotsCount} / {maxActiveBots}
              </span>
            </div>
            <Progress
              value={botsPercentage}
              className="h-2"
            />
          </div>

          {/* Status Alert */}
          {activationCreditsRemaining <= 2 && (
            <div className={`flex items-start gap-2 p-3 rounded-lg border ${
              activationCreditsRemaining === 0
                ? 'bg-red-950/40 border-red-700/50'
                : 'bg-yellow-950/40 border-yellow-700/50'
            }`}>
              <AlertCircle
                className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                  activationCreditsRemaining === 0
                    ? 'text-red-500'
                    : 'text-yellow-500'
                }`}
              />
              <div className="text-xs">
                <p className="font-semibold text-slate-100">
                  {activationCreditsRemaining === 0
                    ? 'Créditos Esgotados'
                    : 'Poucos Créditos'}
                </p>
                <p className="text-slate-400 mt-1">
                  {activationCreditsRemaining === 0
                    ? 'Atualize seu plano para continuar ativando novos robôs.'
                    : `Apenas ${activationCreditsRemaining} crédito(s) restante(s).`}
                </p>
              </div>
            </div>
          )}

          {/* Expandable Details */}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="w-full text-left text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors py-2 flex items-center gap-1"
          >
            {showDetails ? '▼' : '▶'} {showDetails ? 'Menos' : 'Ver'} detalhes
          </button>

          {showDetails && (
            <div className="space-y-3 pt-3 border-t border-slate-700">
              {/* Plan Benefits */}
              <div className="space-y-2 bg-slate-800/50 p-3 rounded-lg">
                <p className="text-xs font-semibold text-slate-300">
                  Benefícios do Plano {config.label}:
                </p>
                <ul className="space-y-1 text-xs text-slate-400">
                  <li className="flex items-center gap-2">
                    <span className="text-emerald-500">✓</span>
                    <strong>Ativar novo robô:</strong> 1 crédito
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-emerald-500">✓</span>
                    <strong>Reativar robô:</strong> Grátis
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-emerald-500">✓</span>
                    <strong>2 primeiros swaps:</strong> Grátis/mês
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-emerald-500">✓</span>
                    <strong>Swaps adicionais:</strong> 1 crédito cada
                  </li>
                </ul>
              </div>

              {/* Upgrade Suggestion */}
              {activationCreditsRemaining <= activationCredits / 2 && (
                <Button
                  onClick={onUpgradeClick}
                  className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold shadow-lg"
                >
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Atualizar Plano
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Kill Switch Confirmation Dialog */}
      <AlertDialog open={showKillDialog} onOpenChange={setShowKillDialog}>
        <AlertDialogContent className="bg-slate-800 border-slate-700">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-400">
              <Power className="w-5 h-5 inline mr-2" />
              Ativar Kill Switch?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação desativará TODOS os {activeBotsCount} robô{activeBotsCount !== 1 ? 's' : ''} ativo{activeBotsCount !== 1 ? 's' : ''} imediatamente.
              Você poderá reativá-los depois sem custo de crédito.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogCancel className="bg-slate-700 hover:bg-slate-600 text-white border-slate-600">
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              onKillSwitch?.();
              setShowKillDialog(false);
            }}
            disabled={isKillSwitchLoading}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isKillSwitchLoading ? 'Desativando...' : 'Desativar Tudo'}
          </AlertDialogAction>
        </AlertDialogContent>
      </AlertDialog>
    </TooltipProvider>
  );
};

export default CreditMonitor;
