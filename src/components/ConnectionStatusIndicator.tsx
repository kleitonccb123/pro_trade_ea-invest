import React from 'react';
import { Wifi, WifiOff, RefreshCw, AlertTriangle } from 'lucide-react';
import { useConnectionStatus } from '@/hooks/useConnectionStatus';
import { cn } from '@/lib/utils';

interface ConnectionStatusIndicatorProps {
  className?: string;
  showText?: boolean;
  compact?: boolean;
}

export function ConnectionStatusIndicator({
  className,
  showText = true,
  compact = false
}: ConnectionStatusIndicatorProps) {
  const { connectionStatus } = useConnectionStatus();

  const getStatusInfo = () => {
    if (!connectionStatus.isOnline) {
      return {
        icon: WifiOff,
        text: 'Offline',
        color: 'text-red-500',
        bgColor: 'bg-red-500/10',
        borderColor: 'border-red-500/30',
        description: 'Sem conexão com a internet'
      };
    }

    switch (connectionStatus.websocketState) {
      case 'connected':
        return {
          icon: Wifi,
          text: 'Conectado',
          color: 'text-emerald-500',
          bgColor: 'bg-emerald-500/10',
          borderColor: 'border-emerald-500/30',
          description: 'Conexão ativa'
        };
      case 'connecting':
        return {
          icon: RefreshCw,
          text: 'Conectando...',
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-500/10',
          borderColor: 'border-yellow-500/30',
          description: 'Estabelecendo conexão'
        };
      case 'reconnecting':
        return {
          icon: RefreshCw,
          text: `Reconectando... (${connectionStatus.reconnectAttempts})`,
          color: 'text-orange-500',
          bgColor: 'bg-orange-500/10',
          borderColor: 'border-orange-500/30',
          description: 'Tentando reconectar'
        };
      case 'failed':
        return {
          icon: AlertTriangle,
          text: 'Falha na Conexão',
          color: 'text-red-500',
          bgColor: 'bg-red-500/10',
          borderColor: 'border-red-500/30',
          description: 'Não foi possível conectar'
        };
      default:
        return {
          icon: WifiOff,
          text: 'Desconectado',
          color: 'text-gray-500',
          bgColor: 'bg-gray-500/10',
          borderColor: 'border-gray-500/30',
          description: 'Conexão perdida'
        };
    }
  };

  const statusInfo = getStatusInfo();
  const Icon = statusInfo.icon;

  if (compact) {
    return (
      <div
        className={cn(
          "flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium",
          statusInfo.bgColor,
          statusInfo.color,
          statusInfo.borderColor,
          "border",
          className
        )}
        title={statusInfo.description}
      >
        <Icon
          className={cn(
            "w-3 h-3",
            connectionStatus.websocketState === 'connecting' ||
            connectionStatus.websocketState === 'reconnecting'
              ? "animate-spin"
              : ""
          )}
        />
        {showText && <span>{statusInfo.text}</span>}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg border",
        statusInfo.bgColor,
        statusInfo.borderColor,
        className
      )}
    >
      <Icon
        className={cn(
          "w-4 h-4",
          statusInfo.color,
          connectionStatus.websocketState === 'connecting' ||
          connectionStatus.websocketState === 'reconnecting'
            ? "animate-spin"
            : ""
        )}
      />
      <div className="flex flex-col">
        <span className={cn("text-sm font-medium", statusInfo.color)}>
          {statusInfo.text}
        </span>
        {showText && (
          <span className="text-xs text-muted-foreground">
            {statusInfo.description}
          </span>
        )}
      </div>
    </div>
  );
}