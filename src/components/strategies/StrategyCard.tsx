/**
 * StrategyCard Component (Improved)
 * Card refatorado com design ultra-moderno, métricas visuais e integração backend
 * Features: animations, real-time stats, clone, performance charts, etc
 */

import React from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  TrendingUp,
  MoreVertical,
  Eye,
  EyeOff,
  Edit2,
  Trash2,
  Zap,
  Copy,
  Share2,
  Info,
  BarChart3,
  Activity,
  Target,
  Shield,
  Flame,
  Clock,
  DollarSign,
} from 'lucide-react';
import { useState } from 'react';

interface StrategyCardProps {
  id: string;
  name: string;
  description: string;
  isPublic: boolean;
  isActive: boolean;
  winRate?: number;
  monthlyReturn?: number;
  riskLevel?: 'low' | 'medium' | 'high';
  swapsUsed?: number;
  maxSwaps?: number;
  activationsUsed?: number;
  maxActivations?: number;
  createdAt?: string;
  totalTrades?: number;
  totalProfit?: number;
  drawdown?: number;
  sharpeRatio?: number;
  successRate?: number;
  avgWin?: number;
  avgLoss?: number;
  onActivate?: (id: string) => void;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
  onToggleVisibility?: (id: string) => void;
  onClone?: (id: string) => void;
  onShare?: (id: string) => void;
}

const getRiskColor = (risk: 'low' | 'medium' | 'high') => {
  switch (risk) {
    case 'low':
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
    case 'medium':
      return 'bg-amber-500/20 text-amber-400 border-amber-500/50';
    case 'high':
      return 'bg-rose-500/20 text-rose-400 border-rose-500/50';
  }
};

const getRiskGradient = (risk?: 'low' | 'medium' | 'high') => {
  switch (risk) {
    case 'low':
      return 'from-emerald-900/40 to-emerald-600/20';
    case 'medium':
      return 'from-amber-900/40 to-amber-600/20';
    case 'high':
      return 'from-rose-900/40 to-rose-600/20';
    default:
      return 'from-slate-900/40 to-slate-600/20';
  }
};

const getPerformanceColor = (value?: number) => {
  if (!value) return 'text-slate-400';
  if (value >= 10) return 'text-emerald-400';
  if (value >= 0) return 'text-emerald-400';
  return 'text-rose-400';
};

const formatProfit = (value?: number) => {
  if (!value) return 'N/A';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
};

// Performance indicator bar component
const PerformanceBar: React.FC<{ value: number; max?: number; label: string }> = ({ value, max = 100, label }) => {
  const percentage = Math.min((value / max) * 100, 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-xs font-medium text-slate-300">{label}</span>
        <span className="text-xs font-bold text-slate-300">{percentage.toFixed(0)}%</span>
      </div>
      <div className="w-full h-1.5 bg-slate-700/50 rounded-full overflow-hidden border border-slate-600/30">
        <div
          className={`h-full transition-all duration-500 rounded-full ${
            percentage <= 50
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-600'
              : percentage <= 80
              ? 'bg-gradient-to-r from-amber-500 to-amber-600'
              : 'bg-gradient-to-r from-rose-500 to-rose-600'
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

export const StrategyCard: React.FC<StrategyCardProps> = ({
  id,
  name,
  description,
  isPublic,
  isActive,
  winRate,
  monthlyReturn,
  riskLevel = 'medium',
  swapsUsed = 0,
  maxSwaps = 2,
  activationsUsed = 0,
  maxActivations = 1,
  createdAt,
  totalTrades = 0,
  totalProfit = 0,
  drawdown = 0,
  sharpeRatio = 0,
  successRate = 0,
  avgWin = 0,
  avgLoss = 0,
  onActivate,
  onEdit,
  onDelete,
  onToggleVisibility,
  onClone,
  onShare,
}) => {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const swapPercentage = (swapsUsed / maxSwaps) * 100;
  const activationPercentage = (activationsUsed / maxActivations) * 100;
  const hasSwapsRemaining = swapsUsed < maxSwaps;

  const handleCopyId = () => {
    navigator.clipboard.writeText(id);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <>
      <Card className={`
        group h-full flex flex-col
        border-slate-700 
        bg-gradient-to-br ${getRiskGradient(riskLevel)}
        overflow-hidden
        hover:border-emerald-500/50 transition-all duration-300 
        hover:shadow-2xl hover:shadow-emerald-500/20
        hover:scale-[1.01]
        relative
      `}>
        {/* Premium Decoration */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-gradient-to-tr from-emerald-500/10 to-transparent rounded-full blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

        {/* Status Badge */}
        {isActive && (
          <div className="absolute top-4 right-4 z-10">
            <div className="relative">
              <div className="absolute inset-0 bg-emerald-400 rounded-full blur-sm animate-pulse" />
              <Badge className="relative bg-emerald-600 text-white border-emerald-400 shadow-lg shadow-emerald-500/50">
                <Activity className="w-3 h-3 mr-1 animate-pulse" />
                Ativa
              </Badge>
            </div>
          </div>
        )}

        {/* Header com Gradient */}
        <CardHeader className="pb-4 relative z-10">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <CardTitle className="text-xl font-bold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent truncate">
                  {name}
                </CardTitle>
              </div>
              <CardDescription className="line-clamp-2 text-slate-400 text-sm">
                {description || 'Estratégia de trading automático'}
              </CardDescription>
            </div>

            {/* Menu Actions */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 h-9 w-9 text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors"
                >
                  <MoreVertical className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="bg-slate-800 border-slate-700 w-48 shadow-xl">
                <DropdownMenuItem
                  onClick={() => setShowDetailsDialog(true)}
                  className="text-slate-300 hover:text-white hover:bg-slate-700 cursor-pointer"
                >
                  <Info className="w-4 h-4 mr-2" />
                  Detalhes Completos
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => onEdit?.(id)}
                  className="text-slate-300 hover:text-white hover:bg-slate-700 cursor-pointer"
                >
                  <Edit2 className="w-4 h-4 mr-2" />
                  Editar
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => onClone?.(id)}
                  className="text-slate-300 hover:text-white hover:bg-slate-700 cursor-pointer"
                >
                  <Copy className="w-4 h-4 mr-2" />
                  Clonar
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => onShare?.(id)}
                  className="text-slate-300 hover:text-white hover:bg-slate-700 cursor-pointer"
                >
                  <Share2 className="w-4 h-4 mr-2" />
                  Compartilhar
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => onToggleVisibility?.(id)}
                  className="text-slate-300 hover:text-white hover:bg-slate-700 cursor-pointer"
                >
                  {isPublic ? (
                    <>
                      <EyeOff className="w-4 h-4 mr-2" />
                      Privado
                    </>
                  ) : (
                    <>
                      <Eye className="w-4 h-4 mr-2" />
                      Público
                    </>
                  )}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => setShowDeleteDialog(true)}
                  className="text-rose-400 hover:text-rose-300 hover:bg-rose-900/20 cursor-pointer"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Deletar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardHeader>

        {/* Content - Main Metrics */}
        <CardContent className="flex-1 space-y-4 relative z-10">
          {/* Status Badges */}
          <div className="flex gap-2 flex-wrap">
            <Badge
              variant="outline"
              className={`text-xs font-semibold ${
                isPublic
                  ? 'bg-green-900/40 text-green-300 border-green-600 hover:bg-green-900/50'
                  : 'bg-yellow-900/40 text-yellow-300 border-yellow-600 hover:bg-yellow-900/50'
              }`}
            >
              {isPublic ? '🌐 Público' : '🔒 Privado'}
            </Badge>
            {riskLevel && (
              <Badge
                variant="outline"
                className={`text-xs font-semibold ${getRiskColor(riskLevel)}`}
              >
                {riskLevel === 'low'
                  ? '🟢 Baixo Risco'
                  : riskLevel === 'medium'
                  ? '🟡 Médio Risco'
                  : '🔴 Alto Risco'}
              </Badge>
            )}
          </div>

          {/* Key Metrics Grid - 2x2 */}
          <div className="grid grid-cols-2 gap-2">
            {winRate !== undefined && (
              <div className="p-3 bg-gradient-to-br from-blue-900/20 to-blue-700/10 rounded-lg border border-blue-600/30 hover:border-blue-500/50 transition-colors">
                <div className="flex items-center gap-2 mb-1">
                  <BarChart3 className="w-4 h-4 text-blue-400" />
                  <p className="text-xs text-slate-400">Taxa Acerto</p>
                </div>
                <p className="text-2xl font-bold text-blue-300">{winRate.toFixed(1)}%</p>
              </div>
            )}
            {monthlyReturn !== undefined && (
              <div className={`p-3 bg-gradient-to-br rounded-lg border transition-colors ${
                monthlyReturn >= 0
                  ? 'from-emerald-900/20 to-emerald-700/10 border-emerald-600/30 hover:border-emerald-500/50'
                  : 'from-rose-900/20 to-rose-700/10 border-rose-600/30 hover:border-rose-500/50'
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <p className="text-xs text-slate-400">Retorno Mensal</p>
                </div>
                <p className={`text-2xl font-bold ${getPerformanceColor(monthlyReturn)}`}>
                  {formatProfit(monthlyReturn)}
                </p>
              </div>
            )}
            {totalProfit !== undefined && totalProfit !== 0 && (
              <div className={`p-3 bg-gradient-to-br rounded-lg border transition-colors ${
                totalProfit >= 0
                  ? 'from-emerald-900/20 to-emerald-700/10 border-emerald-600/30 hover:border-emerald-500/50'
                  : 'from-rose-900/20 to-rose-700/10 border-rose-600/30 hover:border-rose-500/50'
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                  <p className="text-xs text-slate-400">Lucro Total</p>
                </div>
                <p className={`text-2xl font-bold ${getPerformanceColor(totalProfit)}`}>
                  {formatProfit(totalProfit)}
                </p>
              </div>
            )}
            {totalTrades !== undefined && totalTrades > 0 && (
              <div className="p-3 bg-gradient-to-br from-violet-900/20 to-violet-700/10 rounded-lg border border-violet-600/30 hover:border-violet-500/50 transition-colors">
                <div className="flex items-center gap-2 mb-1">
                  <Target className="w-4 h-4 text-violet-400" />
                  <p className="text-xs text-slate-400">Total Trades</p>
                </div>
                <p className="text-2xl font-bold text-violet-300">{totalTrades}</p>
              </div>
            )}
          </div>

          {/* Advanced Metrics - Collapsible */}
          {(sharpeRatio !== undefined || drawdown !== undefined || avgWin !== undefined) && (
            <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/50 space-y-2">
              <p className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Métricas Avançadas</p>
              <div className="grid grid-cols-3 gap-2 text-center">
                {sharpeRatio !== undefined && (
                  <div>
                    <p className="text-xs text-slate-400">Sharpe</p>
                    <p className="text-sm font-bold text-emerald-400">{sharpeRatio.toFixed(2)}</p>
                  </div>
                )}
                {drawdown !== undefined && drawdown > 0 && (
                  <div>
                    <p className="text-xs text-slate-400">Max Drawdown</p>
                    <p className="text-sm font-bold text-rose-400">{drawdown.toFixed(2)}%</p>
                  </div>
                )}
                {successRate !== undefined && (
                  <div>
                    <p className="text-xs text-slate-400">Sucesso</p>
                    <p className="text-sm font-bold text-emerald-400">{successRate.toFixed(1)}%</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Usage Indicators */}
          <div className="space-y-3 pt-2 border-t border-slate-700/50">
            {/* Swaps Indicator */}
            <PerformanceBar
              value={swapsUsed}
              max={maxSwaps}
              label={`Swaps ${swapsUsed}/${maxSwaps}`}
            />

            {/* Activation Indicator */}
            <PerformanceBar
              value={activationsUsed}
              max={maxActivations}
              label={`Ativações ${activationsUsed}/${maxActivations}`}
            />

            {!hasSwapsRemaining && (
              <p className="text-xs text-slate-400 flex items-center gap-1 px-2 py-1 bg-slate-800/50 rounded">
                <Flame className="w-3 h-3" />
                Próximos swaps custarão 1 crédito
              </p>
            )}
          </div>

          {/* Creation Date */}
          {createdAt && (
            <p className="text-xs text-slate-500 flex items-center gap-1 pt-2 border-t border-slate-700/50">
              <Clock className="w-3 h-3" />
              Criado em {new Date(createdAt).toLocaleDateString('pt-BR')}
            </p>
          )}
        </CardContent>

        {/* Footer Actions - Premium */}
        <div className="px-6 py-4 border-t border-slate-700 bg-gradient-to-r from-slate-900/80 to-slate-800/80 backdrop-blur-sm rounded-b-lg space-y-2">
          <Button
            onClick={() => isActive ? null : onActivate?.(id)}
            disabled={isActive}
            className={`w-full font-semibold transition-all ${
              isActive
                ? 'bg-emerald-600/50 text-emerald-300 cursor-default'
                : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-500/30 hover:shadow-emerald-500/50'
            }`}
          >
            <Zap className="w-4 h-4 mr-2" />
            {isActive ? 'Estratégia Ativa' : 'Ativar Estratégia'}
          </Button>
        </div>
      </Card>

      {/* Details Dialog */}
      <AlertDialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
        <AlertDialogContent className="bg-gradient-to-br from-slate-800 to-slate-900 border-slate-700 max-w-2xl max-h-[80vh] overflow-y-auto">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl text-white flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-emerald-400" />
              {name} - Detalhes Completos
            </AlertDialogTitle>
          </AlertDialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Description */}
            <div>
              <h4 className="text-sm font-semibold text-slate-300 mb-2">Descrição</h4>
              <p className="text-slate-400">{description}</p>
            </div>

            {/* All Metrics */}
            <div className="grid grid-cols-2 gap-4">
              {winRate !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Taxa de Acerto</p>
                  <p className="text-xl font-bold text-blue-400">{winRate.toFixed(2)}%</p>
                </div>
              )}
              {monthlyReturn !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Retorno Mensal</p>
                  <p className={`text-xl font-bold ${getPerformanceColor(monthlyReturn)}`}>
                    {formatProfit(monthlyReturn)}
                  </p>
                </div>
              )}
              {totalTrades !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Total de Trades</p>
                  <p className="text-xl font-bold text-violet-400">{totalTrades}</p>
                </div>
              )}
              {totalProfit !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Lucro Total</p>
                  <p className={`text-xl font-bold ${getPerformanceColor(totalProfit)}`}>
                    {formatProfit(totalProfit)}
                  </p>
                </div>
              )}
              {sharpeRatio !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Índice de Sharpe</p>
                  <p className="text-xl font-bold text-cyan-400">{sharpeRatio.toFixed(2)}</p>
                </div>
              )}
              {drawdown !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Máximo Drawdown</p>
                  <p className="text-xl font-bold text-rose-400">{drawdown.toFixed(2)}%</p>
                </div>
              )}
              {successRate !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Taxa de Sucesso</p>
                  <p className="text-xl font-bold text-emerald-400">{successRate.toFixed(2)}%</p>
                </div>
              )}
              {avgWin !== undefined && (
                <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">Ganho Médio</p>
                  <p className="text-xl font-bold text-emerald-400">{formatProfit(avgWin)}</p>
                </div>
              )}
            </div>

            {/* ID Copy */}
            <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
              <p className="text-xs text-slate-400 mb-2">ID da Estratégia</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-sm text-slate-300 bg-slate-900/50 px-2 py-1 rounded font-mono">
                  {id}
                </code>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCopyId}
                  className="border-slate-600"
                >
                  {isCopied ? 'Copiado!' : 'Copiar'}
                </Button>
              </div>
            </div>
          </div>

          <AlertDialogCancel className="bg-slate-700 hover:bg-slate-600 text-white border-slate-600">
            Fechar
          </AlertDialogCancel>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="bg-slate-800 border-slate-700">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">Deletar Estratégia?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação não pode ser desfeita. A estratégia "{name}" será permanentemente deletada.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogCancel className="bg-slate-700 hover:bg-slate-600 text-white border-slate-600">
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              onDelete?.(id);
              setShowDeleteDialog(false);
            }}
            className="bg-rose-600 hover:bg-rose-700 text-white"
          >
            Deletar
          </AlertDialogAction>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default StrategyCard;
