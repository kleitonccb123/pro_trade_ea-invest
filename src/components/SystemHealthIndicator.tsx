/**
 * System Health Indicator Component
 * 
 * Shows real-time system health status with visual feedback.
 */

import { useState, useEffect } from 'react';
import { Activity, Database, Server, Wifi, WifiOff, AlertCircle, CheckCircle } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { Badge } from '@/components/ui/badge';
import { systemApi, SystemHealth } from '@/lib/api';
import { useSystemHealthWebSocket } from '@/hooks/use-websocket';
import { cn } from '@/lib/utils';

interface SystemHealthIndicatorProps {
  variant?: 'minimal' | 'compact' | 'detailed';
  className?: string;
}

export function SystemHealthIndicator({ variant = 'compact', className }: SystemHealthIndicatorProps) {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // WebSocket for real-time updates
  const { health: wsHealth, isConnected: wsConnected } = useSystemHealthWebSocket();

  // Fetch initial health
  useEffect(() => {
    fetchHealth();
    // Poll every 30 seconds as fallback
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  // Update from WebSocket
  useEffect(() => {
    if (wsConnected && wsHealth.status !== 'unknown') {
      setHealth(prev => prev ? {
        ...prev,
        status: wsHealth.status as 'healthy' | 'degraded' | 'unhealthy',
        database: { status: wsHealth.database ? 'ok' : 'error' },
        bots_running: wsHealth.botsRunning,
        circuit_breaker_open: wsHealth.circuitBreakerOpen,
      } : null);
    }
  }, [wsHealth, wsConnected]);

  const fetchHealth = async () => {
    try {
      const data = await systemApi.getHealth();
      setHealth(data);
      setError(false);
    } catch (err) {
      console.error('Failed to fetch system health:', err);
      setError(true);
      // Try simple ping as fallback
      try {
        await systemApi.ping();
        setHealth({
          status: 'healthy',
          database: { status: 'ok' },
          exchanges: { binance: { status: 'unknown' } },
          bots_running: 0,
          circuit_breaker_open: false,
          uptime_seconds: 0,
        });
      } catch {
        setHealth(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'healthy':
      case 'ok':
        return 'bg-emerald-500';
      case 'degraded':
        return 'bg-yellow-500';
      case 'unhealthy':
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-slate-500';
    }
  };

  const getStatusIcon = () => {
    if (loading) {
      return <Activity className="w-4 h-4 text-slate-400 animate-pulse" />;
    }
    if (error || !health) {
      return <WifiOff className="w-4 h-4 text-red-400" />;
    }
    switch (health.status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case 'degraded':
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case 'unhealthy':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Activity className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusText = () => {
    if (loading) return 'Verificando...';
    if (error || !health) return 'Desconectado';
    switch (health.status) {
      case 'healthy':
        return 'Sistema Ativo';
      case 'degraded':
        return 'Degradado';
      case 'unhealthy':
        return 'Com Problemas';
      default:
        return 'Desconhecido';
    }
  };

  // Minimal variant - just a dot
  if (variant === 'minimal') {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={cn("cursor-pointer", className)}>
              <div className={cn(
                "w-2 h-2 rounded-full",
                loading ? "bg-slate-500 animate-pulse" : getStatusColor(health?.status),
                health?.status === 'healthy' && "shadow-lg shadow-emerald-500/50 animate-pulse"
              )} />
            </div>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="bg-slate-900 border-slate-700">
            <p>{getStatusText()}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Compact variant - dot + text
  if (variant === 'compact') {
    return (
      <HoverCard>
        <HoverCardTrigger asChild>
          <div className={cn(
            "flex items-center gap-2 px-3 py-2 bg-slate-800 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors cursor-pointer",
            className
          )}>
            <div className={cn(
              "w-2 h-2 rounded-full",
              loading ? "bg-slate-500 animate-pulse" : getStatusColor(health?.status),
              health?.status === 'healthy' && "shadow-lg shadow-emerald-500/50 animate-pulse"
            )} />
            <span className="text-xs text-slate-400 font-medium">{getStatusText()}</span>
          </div>
        </HoverCardTrigger>
        <HoverCardContent side="bottom" align="end" className="w-64 bg-slate-900 border-slate-700">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-white">Status do Sistema</h4>
              <Badge variant={health?.status === 'healthy' ? 'outline' : 'destructive'} className="text-xs">
                {health?.status || 'unknown'}
              </Badge>
            </div>
            
            {health && (
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-slate-400">
                    <Database className="w-3 h-3" />
                    Banco de Dados
                  </span>
                  <span className={health.database?.status === 'ok' ? 'text-emerald-400' : 'text-red-400'}>
                    {health.database?.status === 'ok' ? '✓ Online' : '✗ Offline'}
                  </span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-slate-400">
                    <Server className="w-3 h-3" />
                    Robôs Ativos
                  </span>
                  <span className="text-white font-medium">{health.bots_running}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-slate-400">
                    <Wifi className="w-3 h-3" />
                    WebSocket
                  </span>
                  <span className={wsConnected ? 'text-emerald-400' : 'text-yellow-400'}>
                    {wsConnected ? '✓ Conectado' : '○ Polling'}
                  </span>
                </div>

                {health.circuit_breaker_open && (
                  <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/30 rounded text-yellow-400">
                    ⚠️ Circuit Breaker Ativo
                  </div>
                )}
              </div>
            )}
          </div>
        </HoverCardContent>
      </HoverCard>
    );
  }

  // Detailed variant - full card
  return (
    <div className={cn(
      "p-4 rounded-xl border bg-slate-800/50 border-slate-700",
      className
    )}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold flex items-center gap-2">
          {getStatusIcon()}
          Status do Sistema
        </h3>
        <Badge variant={health?.status === 'healthy' ? 'outline' : 'destructive'}>
          {health?.status || 'unknown'}
        </Badge>
      </div>

      {health && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Database className="w-3 h-3" />
              Database
            </div>
            <p className={cn(
              "font-medium",
              health.database?.status === 'ok' ? 'text-emerald-400' : 'text-red-400'
            )}>
              {health.database?.status === 'ok' ? 'Online' : 'Offline'}
            </p>
          </div>

          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Server className="w-3 h-3" />
              Robôs
            </div>
            <p className="font-medium text-white">{health.bots_running} ativos</p>
          </div>

          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Wifi className="w-3 h-3" />
              Binance
            </div>
            <p className={cn(
              "font-medium",
              health.exchanges?.binance?.status === 'ok' ? 'text-emerald-400' : 'text-yellow-400'
            )}>
              {health.exchanges?.binance?.status === 'ok' ? 'Conectado' : 'Verificando'}
            </p>
          </div>

          <div className="bg-slate-900/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
              <Activity className="w-3 h-3" />
              Uptime
            </div>
            <p className="font-medium text-white">
              {health.uptime_seconds ? `${Math.floor(health.uptime_seconds / 3600)}h` : 'N/A'}
            </p>
          </div>
        </div>
      )}

      {health?.circuit_breaker_open && (
        <div className="mt-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <p className="text-sm text-yellow-400">
            ⚠️ Circuit Breaker ativo - Sistema em modo de proteção
          </p>
        </div>
      )}
    </div>
  );
}
