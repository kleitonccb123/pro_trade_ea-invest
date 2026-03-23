import React, { useState } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Power, WifiOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useConnectionStatus } from '@/hooks/useConnectionStatus';

interface DailyProfitProps {
  dailyProfit: number;
  dailyTrades: number;
  onActivateRobot?: () => void;
  onDeactivateRobot?: () => void;
  isLoading?: boolean;
  robotActive?: boolean;
  isOffline?: boolean;
}

export default function DailyProfitCard({
  dailyProfit,
  dailyTrades,
  onActivateRobot,
  onDeactivateRobot,
  isLoading = false,
  robotActive = false,
  isOffline = false,
}: DailyProfitProps) {
  const [showDetails, setShowDetails] = useState(false);
  const { connectionStatus } = useConnectionStatus();

  // Determine if card should show offline state
  const shouldShowOffline = isOffline || (!connectionStatus.isOnline && connectionStatus.websocketState !== 'connected');

  const profitColor = dailyProfit >= 0 ? 'text-emerald-400' : 'text-red-400';
  const profitBg = dailyProfit >= 0 ? 'bg-emerald-500/10' : 'bg-red-500/10';
  const profitBorder = dailyProfit >= 0 ? 'border-emerald-500/30' : 'border-red-500/30';

  const formattedProfit = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(dailyProfit);

  // Loading state with skeleton
  if (isLoading) {
    return (
      <Card className="glass-card border border-white/5 bg-gradient-to-br from-card/60 to-card/30">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="w-5 h-5 rounded" />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-4 w-16" />
          </div>
          <Skeleton className="h-10 w-full" />
          <div className="flex gap-2">
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-8 w-20" />
          </div>
        </CardContent>
      </Card>
    );
  }

  // Offline state
  if (shouldShowOffline) {
    return (
      <Card className="glass-card border border-red-500/20 bg-gradient-to-br from-red-500/5 to-red-500/10 relative overflow-hidden">
        {/* Offline overlay */}
        <div className="absolute inset-0 bg-red-500/5 flex items-center justify-center z-10">
          <div className="flex flex-col items-center gap-2 text-red-400">
            <WifiOff className="w-6 h-6" />
            <span className="text-xs font-medium">Offline</span>
          </div>
        </div>

        {/* Dimmed content */}
        <div className="opacity-40">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-primary" />
                Lucro Hoje
              </CardTitle>
              {dailyProfit >= 0 ? (
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              ) : (
                <TrendingDown className="w-5 h-5 text-red-400" />
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <div className={`text-3xl font-bold font-mono ${profitColor}`}>
                {formattedProfit}
              </div>
              <div className="text-sm text-muted-foreground">
                {dailyTrades} trades hoje
              </div>
            </div>
            <Button
              variant={robotActive ? "destructive" : "default"}
              size="sm"
              className="w-full"
              disabled
            >
              <Power className="w-4 h-4 mr-2" />
              {robotActive ? 'Parar Robô' : 'Iniciar Robô'}
            </Button>
          </CardContent>
        </div>
      </Card>
    );
  }

  return (
    <Card className={`glass-card border ${profitBorder} bg-gradient-to-br ${profitBg} from-card/60 to-card/30`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-primary" />
            Lucro Hoje
          </CardTitle>
          {dailyProfit >= 0 ? (
            <TrendingUp className="w-5 h-5 text-emerald-400" />
          ) : (
            <TrendingDown className="w-5 h-5 text-red-400" />
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <p className={`text-3xl font-bold ${profitColor}`}>{formattedProfit}</p>
          <p className="text-xs text-muted-foreground">
            {dailyTrades} operação{dailyTrades !== 1 ? 's' : ''} realizada{dailyTrades !== 1 ? 's' : ''}
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Meta Diária</span>
            <span className="font-medium">$100</span>
          </div>
          <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden border border-white/10">
            <div
              className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
              style={{ width: `${Math.min((dailyProfit / 100) * 100, 100)}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={() => {
              onActivateRobot?.();
            }}
            disabled={isLoading || robotActive}
            className="bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-700 hover:to-emerald-600 text-white font-semibold text-sm rounded-lg h-9 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Power className="w-3.5 h-3.5 mr-1.5" />
            Ativar
          </Button>
          <Button
            onClick={() => {
              onDeactivateRobot?.();
            }}
            disabled={isLoading || !robotActive}
            className="bg-gradient-to-r from-red-600 to-red-500 hover:from-red-700 hover:to-red-600 text-white font-semibold text-sm rounded-lg h-9 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Power className="w-3.5 h-3.5 mr-1.5" />
            Desativar
          </Button>
        </div>

        <div className="p-3 rounded-lg bg-white/5 border border-white/10">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Status do Robô</span>
            <span className={`text-xs font-bold ${robotActive ? 'text-emerald-400' : 'text-red-400'}`}>
              {robotActive ? '🟢 Ativo' : '🔴 Inativo'}
            </span>
          </div>
        </div>

        {showDetails && (
          <div className="pt-3 border-t border-white/10 space-y-2">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Taxa de Acerto:</span>
              <span className="text-white font-medium">75%</span>
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Melhor Trade:</span>
              <span className="text-emerald-400 font-medium">+$45.30</span>
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Pior Trade:</span>
              <span className="text-red-400 font-medium">-$12.50</span>
            </div>
          </div>
        )}

        <button
          onClick={() => setShowDetails(!showDetails)}
          className="w-full text-xs text-primary hover:text-primary/80 font-medium transition-colors"
        >
          {showDetails ? 'Ocultar' : 'Ver'} Detalhes
        </button>
      </CardContent>
    </Card>
  );
}
