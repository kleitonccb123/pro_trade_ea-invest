import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Bot, 
  Play, 
  Pause, 
  Square, 
  TrendingUp, 
  TrendingDown, 
  Activity,
  DollarSign,
  Zap,
  Wifi,
  WifiOff
} from 'lucide-react';
import { BinanceConfigModal } from './BinanceConfigModal';
import { useTradingWebSocket } from '@/hooks/use-websocket';
import { botsApi } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Robot {
  id: number;
  name: string;
  symbol: string;
  status: 'stopped' | 'running_simulation' | 'running_live' | 'paused';
  profit?: number;
  trades?: number;
  winRate?: number;
  instance_id?: number;
}

interface RobotCardProps {
  robot: Robot;
  onUpdate: () => void;
}

export function RobotCardNew({ robot, onUpdate }: RobotCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const { robotStatus, isConnected: wsConnected } = useTradingWebSocket('robots');
  
  // Get real-time status from WebSocket
  const liveStatus = robot.instance_id ? robotStatus[robot.instance_id] : null;
  const currentStatus = liveStatus?.status || robot.status;
  const isRunning = currentStatus.startsWith('running');
  const isLive = currentStatus === 'running_live';
  const isPaused = currentStatus === 'paused';

  const handleStart = async (binanceConfig: any) => {
    setIsLoading(true);
    try {
      await botsApi.start(robot.id, binanceConfig);
      onUpdate();
    } catch (error) {
      console.error('Failed to start robot:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const handlePause = async () => {
    setIsLoading(true);
    try {
      await botsApi.pause(robot.instance_id || robot.id);
      onUpdate();
    } catch (error) {
      console.error('Failed to pause robot:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    try {
      await botsApi.stop(robot.instance_id || robot.id);
      onUpdate();
    } catch (error) {
      console.error('Failed to stop robot:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = () => {
    switch (currentStatus) {
      case 'running_live': return 'badge-success';
      case 'running_simulation': return 'badge-primary';
      case 'paused': return 'badge-warning';
      default: return 'badge-neutral';
    }
  };

  const getStatusText = () => {
    switch (currentStatus) {
      case 'running_live': return isLive && liveStatus?.testnet ? 'Live (Testnet)' : 'Live Trading';
      case 'running_simulation': return 'Simulação';
      case 'paused': return 'Pausado';
      default: return 'Parado';
    }
  };

  return (
    <Card className={cn(
      "glass-card transition-all duration-300 hover:shadow-lg",
      isRunning && "ring-1 ring-primary/30",
      isLive && "glow-success"
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "p-2 rounded-xl transition-all duration-300",
              isRunning 
                ? (isLive ? "bg-success/20 text-success" : "bg-primary/20 text-primary") 
                : "bg-muted text-muted-foreground"
            )}>
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-display font-bold text-lg leading-none">{robot.name}</h3>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-sm text-muted-foreground font-mono">{robot.symbol}</span>
                {wsConnected ? (
                  <Wifi className="h-3 w-3 text-success" />
                ) : (
                  <WifiOff className="h-3 w-3 text-muted-foreground" />
                )}
              </div>
            </div>
          </div>
          
          <Badge className={cn("text-xs font-semibold", getStatusColor())}>
            {getStatusText()}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Performance Metrics */}
        {isRunning && (
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <div className="flex items-center justify-center gap-1">
                <DollarSign className="h-3 w-3 text-muted-foreground" />
                <span className={cn(
                  "font-mono text-sm font-bold",
                  (robot.profit || 0) >= 0 ? "text-success" : "text-destructive"
                )}>
                  {(robot.profit || 0) >= 0 ? '+' : ''}{(robot.profit || 0).toFixed(2)}%
                </span>
              </div>
              <div className="text-xs text-muted-foreground">Profit</div>
            </div>
            
            <div className="text-center">
              <div className="flex items-center justify-center gap-1">
                <Activity className="h-3 w-3 text-muted-foreground" />
                <span className="font-mono text-sm font-bold">{robot.trades || 0}</span>
              </div>
              <div className="text-xs text-muted-foreground">Trades</div>
            </div>
            
            <div className="text-center">
              <div className="flex items-center justify-center gap-1">
                {(robot.winRate || 0) >= 50 ? (
                  <TrendingUp className="h-3 w-3 text-success" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-destructive" />
                )}
                <span className="font-mono text-sm font-bold">{(robot.winRate || 0).toFixed(0)}%</span>
              </div>
              <div className="text-xs text-muted-foreground">Win Rate</div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {!isRunning ? (
            <BinanceConfigModal
              robotName={robot.name}
              robotSymbol={robot.symbol}
              onStart={handleStart}
              isStarting={isLoading}
            />
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handlePause}
                disabled={isLoading || isPaused}
                className="flex-1 gap-2"
              >
                <Pause className="h-3 w-3" />
                {isPaused ? 'Pausado' : 'Pausar'}
              </Button>
              
              <Button
                variant="destructive"
                size="sm"
                onClick={handleStop}
                disabled={isLoading}
                className="flex-1 gap-2"
              >
                <Square className="h-3 w-3" />
                Parar
              </Button>
            </>
          )}
        </div>

        {/* Live Trading Indicator */}
        {isLive && (
          <div className="flex items-center gap-2 p-2 rounded-lg bg-success/10 border border-success/20">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <Zap className="h-3 w-3 text-success" />
            </div>
            <span className="text-xs text-success font-medium">
              Operando ao vivo na Binance {liveStatus?.testnet ? '(Testnet)' : ''}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}