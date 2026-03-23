/**
 * Component: ActivationCreditsDisplay
 * 
 * Shows real-time user activation credits with:
 * - Total credits available
 * - Credits used
 * - Credits remaining
 * - Plan tier
 * - Automatic sync every 30 seconds
 */

import { useActivationCredits } from '@/hooks/use-activation-credits';
import { Zap, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ActivationCreditsDisplayProps {
  className?: string;
  compact?: boolean;
}

export function ActivationCreditsDisplay({ className, compact = false }: ActivationCreditsDisplayProps) {
  const { data, loading, error, refresh, lastUpdated } = useActivationCredits();

  if (!data) {
    return (
      <Card className={cn('glass-card border-white/5 bg-gradient-to-br from-card/60 to-card/30', className)}>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Zap className="w-5 h-5 text-yellow-400" />
            Créditos de Ativação
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">Carregando...</p>
        </CardContent>
      </Card>
    );
  }

  const creditsPercentage = (data.activationCreditsRemaining / data.activationCredits) * 100;
  const isLow = creditsPercentage < 25;
  const isCritical = creditsPercentage === 0;

  if (compact) {
    // Compact display for dashboard header
    return (
      <div className={cn(
        'flex items-center gap-3 px-4 py-2 rounded-lg',
        'bg-gradient-to-r from-yellow-500/10 via-orange-500/5 to-transparent',
        'border border-yellow-500/20 backdrop-blur-sm',
        className
      )}>
        <Zap className="w-5 h-5 text-yellow-400 animate-pulse-glow" />
        <div className="flex flex-col min-w-[120px]">
          <span className="text-xs text-muted-foreground uppercase tracking-wide font-semibold">Créditos</span>
          <span className={cn(
            "text-sm font-bold",
            isCritical ? 'text-red-400' : isLow ? 'text-orange-400' : 'text-emerald-400'
          )}>
            {data.activationCreditsRemaining} / {data.activationCredits}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">{data.plan.toUpperCase()}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={refresh}
          disabled={loading}
          className="ml-auto h-6 w-6 p-0"
        >
          <RefreshCw className={cn(
            'w-3 h-3',
            loading && 'animate-spin'
          )} />
        </Button>
      </div>
    );
  }

  // Full card display
  return (
    <Card className={cn('glass-card border-white/5 bg-gradient-to-br from-card/60 to-card/30', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-yellow-500/20 border border-yellow-500/30 flex items-center justify-center">
              <Zap className="w-5 h-5 text-yellow-400" />
            </div>
            <div>
              <CardTitle className="text-lg">Créditos de Ativação</CardTitle>
              <CardDescription className="text-xs mt-1">
                Plano: {data.plan.charAt(0).toUpperCase() + data.plan.slice(1)}
              </CardDescription>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={refresh}
            disabled={loading}
            className="h-8 w-8 p-0"
          >
            <RefreshCw className={cn(
              'w-4 h-4',
              loading && 'animate-spin'
            )} />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-destructive">
            ⚠️ {error}
          </div>
        )}

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Disponíveis</span>
            <span className={cn(
              'font-bold',
              isCritical ? 'text-red-400' : isLow ? 'text-orange-400' : 'text-emerald-400'
            )}>
              {data.activationCreditsRemaining} / {data.activationCredits}
            </span>
          </div>
          
          <div className="relative h-2 bg-white/5 rounded-full overflow-hidden border border-white/10">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-300',
                isCritical ? 'bg-red-500' :
                isLow ? 'bg-orange-500' :
                'bg-gradient-to-r from-emerald-500 to-teal-500'
              )}
              style={{ width: `${Math.max(0, creditsPercentage)}%` }}
            />
          </div>
        </div>

        {/* Usage Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-white/5 border border-white/5">
            <p className="text-xs text-muted-foreground mb-1">Utilizados</p>
            <p className="font-bold text-sm">{data.activationCreditsUsed}</p>
          </div>
          <div className="p-3 rounded-lg bg-white/5 border border-white/5">
            <p className="text-xs text-muted-foreground mb-1">Bots Ativos</p>
            <p className="font-bold text-sm">{data.activeBotsCount} / {data.maxActiveBots}</p>
          </div>
        </div>

        {/* Warning Messages */}
        {isCritical && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
            <p className="text-xs font-bold text-red-400 mb-1">⚠️ Sem créditos</p>
            <p className="text-xs text-red-300">Você não pode ativar novos robôs. Considere fazer upgrade.</p>
          </div>
        )}

        {isLow && !isCritical && (
          <div className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/30">
            <p className="text-xs font-bold text-orange-400 mb-1">⚡ Créditos baixos</p>
            <p className="text-xs text-orange-300">Considere fazer upgrade do plano para mais ativações.</p>
          </div>
        )}

        {/* Last Updated */}
        {lastUpdated && (
          <p className="text-xs text-muted-foreground text-center">
            Atualizado há {Math.round((Date.now() - lastUpdated.getTime()) / 1000)}s
          </p>
        )}
      </CardContent>
    </Card>
  );
}
