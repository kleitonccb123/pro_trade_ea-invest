import { Bot, PlayCircle, PauseCircle, Settings, TrendingUp, Clock, Maximize2, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { getExchangeById } from '@/lib/exchanges';

interface RobotCardProps {
  robot: {
    id: string;
    name: string;
    description: string;
    pair: string;
    exchange: string;
    status: 'active' | 'paused' | 'stopped';
    profit: number;
    trades: number;
    winRate: number;
    runtime: string;
    advancedSettings?: any;
  };
  onConfigure: () => void;
  onToggle: () => void;
  onExpand?: () => void;
}

export function RobotCard({ robot, onConfigure, onToggle, onExpand }: RobotCardProps) {
  const isActive = robot.status === 'active';
  const isPaused = robot.status === 'paused';

  return (
    <div className="glass-card p-6 hover:border-primary/30 transition-all duration-300">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-4">
          <div className={cn(
            "w-12 h-12 rounded-xl flex items-center justify-center",
            isActive ? "bg-primary/20" : "bg-muted"
          )}>
            <Bot className={cn("w-6 h-6", isActive ? "text-primary" : "text-muted-foreground")} />
          </div>
          <div>
            <h3 className="font-semibold text-foreground">{robot.name}</h3>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>{robot.pair}</span>
              <span>•</span>
              <div className="flex items-center gap-1">
                <ExternalLink className="w-3 h-3" />
                <span className="capitalize">{getExchangeById(robot.exchange)?.name || robot.exchange}</span>
              </div>
            </div>
          </div>
        </div>
        <div className={cn(
          "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium",
          isActive && "bg-success/20 text-success",
          isPaused && "bg-warning/20 text-warning",
          robot.status === 'stopped' && "bg-muted text-muted-foreground"
        )}>
          <div className={cn(
            "w-1.5 h-1.5 rounded-full",
            isActive && "bg-success",
            isPaused && "bg-warning",
            robot.status === 'stopped' && "bg-muted-foreground"
          )} />
          {isActive ? 'Ativo' : isPaused ? 'Pausado' : 'Parado'}
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-muted-foreground mb-4">{robot.description}</p>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center p-3 bg-muted/30 rounded-lg">
          <TrendingUp className={cn(
            "w-4 h-4 mx-auto mb-1",
            robot.profit >= 0 ? "text-success" : "text-destructive"
          )} />
          <p className={cn(
            "font-mono font-semibold",
            robot.profit >= 0 ? "text-success" : "text-destructive"
          )}>
            {robot.profit >= 0 ? '+' : ''}{robot.profit}%
          </p>
          <p className="text-xs text-muted-foreground">Lucro</p>
        </div>
        <div className="text-center p-3 bg-muted/30 rounded-lg">
          <p className="font-mono font-semibold text-foreground">{robot.trades}</p>
          <p className="text-xs text-muted-foreground">Trades</p>
        </div>
        <div className="text-center p-3 bg-muted/30 rounded-lg">
          <p className="font-mono font-semibold text-foreground">{robot.winRate}%</p>
          <p className="text-xs text-muted-foreground">Win Rate</p>
        </div>
      </div>

      {/* Runtime */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
        <Clock className="w-4 h-4" />
        <span>Tempo ativo: {robot.runtime}</span>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          onClick={onToggle}
          variant={isActive ? "outline" : "default"}
          className={cn(
            "flex-1",
            !isActive && "bg-gradient-primary text-primary-foreground hover:opacity-90"
          )}
        >
          {isActive ? (
            <>
              <PauseCircle className="w-4 h-4 mr-2" />
              Pausar
            </>
          ) : (
            <>
              <PlayCircle className="w-4 h-4 mr-2" />
              Ativar
            </>
          )}
        </Button>
        <Button
          onClick={onConfigure}
          variant="outline"
          className="border-border"
        >
          <Settings className="w-4 h-4" />
        </Button>
        {onExpand && (
          <Button
            onClick={onExpand}
            variant="ghost"
            className="border-border"
          >
            <Maximize2 className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
