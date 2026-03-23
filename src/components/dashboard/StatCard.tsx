import { ReactNode, useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, ChevronRight, Sparkles, WifiOff } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useConnectionStatus } from '@/hooks/useConnectionStatus';

interface StatCardProps {
  title: string;
  value: string;
  change?: number;
  icon: ReactNode;
  className?: string;
  onClick?: () => void;
  description?: string;
  isLoading?: boolean;
  isOffline?: boolean;
}

export function StatCard({
  title,
  value,
  change,
  icon,
  className,
  onClick,
  description,
  isLoading = false,
  isOffline = false
}: StatCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [prevValue, setPrevValue] = useState(value);
  const [isAnimating, setIsAnimating] = useState(false);
  const { connectionStatus } = useConnectionStatus();

  // Determine if card should show offline state
  const shouldShowOffline = isOffline || (!connectionStatus.isOnline && connectionStatus.websocketState !== 'connected');

  useEffect(() => {
    if (prevValue !== value) {
      setIsAnimating(true);
      const timer = setTimeout(() => setIsAnimating(false), 600);
      return () => clearTimeout(timer);
    }
  }, [value, prevValue]);

  const isPositive = change && change > 0;
  const isNegative = change && change < 0;

  // Loading state with skeleton
  if (isLoading) {
    return (
      <div
        className={cn(
          "stat-card border border-white/5 bg-gradient-to-br from-card/60 to-card/30 backdrop-blur-sm",
          "rounded-2xl p-6",
          className
        )}
      >
        <div className="flex items-start justify-between mb-4">
          <Skeleton className="w-12 h-12 rounded-xl" />
          <Skeleton className="w-16 h-6 rounded-full" />
        </div>
        <Skeleton className="h-4 w-24 mb-2" />
        <Skeleton className="h-8 w-20 mb-3" />
        <Skeleton className="h-3 w-32" />
      </div>
    );
  }

  // Offline state
  if (shouldShowOffline) {
    return (
      <div
        className={cn(
          "stat-card border border-red-500/20 bg-gradient-to-br from-red-500/5 to-red-500/10 backdrop-blur-sm",
          "rounded-2xl p-6 relative overflow-hidden",
          className
        )}
      >
        {/* Offline overlay */}
        <div className="absolute inset-0 bg-red-500/5 flex items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-red-400">
            <WifiOff className="w-6 h-6" />
            <span className="text-xs font-medium">Offline</span>
          </div>
        </div>

        {/* Dimmed content */}
        <div className="opacity-40">
          <div className="flex items-start justify-between mb-4">
            <div className={cn(
              "w-12 h-12 rounded-xl bg-gradient-to-br from-primary/15 to-accent/10",
              "border border-white/10 flex items-center justify-center",
              "shadow-lg shadow-primary/5 relative overflow-hidden"
            )}>
              {icon}
            </div>
            <div className="flex items-center gap-2">
              {change !== undefined && (
                <div className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold opacity-50",
                  isPositive && "bg-success/25 text-success border border-success/30",
                  isNegative && "bg-destructive/25 text-destructive border border-destructive/30",
                  !isPositive && !isNegative && "bg-muted/30 text-muted-foreground border border-white/5"
                )}>
                  {isPositive && <TrendingUp className="w-3.5 h-3.5" />}
                  {isNegative && <TrendingDown className="w-3.5 h-3.5" />}
                  {!isPositive && !isNegative && <Sparkles className="w-3.5 h-3.5" />}
                  <span>{isPositive ? '+' : ''}{change.toFixed(1)}%</span>
                </div>
              )}
            </div>
          </div>

          <p className="text-sm text-muted-foreground mb-2 font-medium">{title}</p>
          <p className="text-3xl font-bold text-foreground font-mono mb-3">
            {value}
          </p>

          {description && (
            <p className="text-xs text-muted-foreground/60 flex items-center gap-1.5 mb-2">
              <span className="w-1 h-1 rounded-full bg-white/20" />
              {description}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div 
      className={cn(
        "stat-card group cursor-pointer border border-white/5 bg-gradient-to-br from-card/60 to-card/30 backdrop-blur-sm",
        "rounded-2xl p-6 transition-all duration-300",
        "hover:border-white/15 hover:from-card/80 hover:to-card/40",
        onClick && "hover:scale-[1.02] hover:shadow-lg hover:shadow-primary/10",
        className
      )}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={cn(
          "w-12 h-12 rounded-xl bg-gradient-to-br from-primary/15 to-accent/10",
          "border border-white/10 flex items-center justify-center",
          "group-hover:from-primary/25 group-hover:to-accent/15",
          "transition-all duration-300 shadow-lg shadow-primary/5 relative overflow-hidden"
        )}>
          <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          {icon}
        </div>
        <div className="flex items-center gap-2">
          {change !== undefined && (
            <div className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold",
              "transition-all duration-300",
              isPositive && "bg-success/25 text-success border border-success/30",
              isNegative && "bg-destructive/25 text-destructive border border-destructive/30",
              !isPositive && !isNegative && "bg-muted/30 text-muted-foreground border border-white/5"
            )}>
              {isPositive && <TrendingUp className="w-3.5 h-3.5" />}
              {isNegative && <TrendingDown className="w-3.5 h-3.5" />}
              {!isPositive && !isNegative && <Sparkles className="w-3.5 h-3.5" />}
              <span>{isPositive ? '+' : ''}{change.toFixed(1)}%</span>
            </div>
          )}
          {onClick && (
            <ChevronRight className={cn(
              "w-4 h-4 text-muted-foreground transition-all duration-300",
              isHovered ? "opacity-100 translate-x-1" : "opacity-0"
            )} />
          )}
        </div>
      </div>

      <p className="text-sm text-muted-foreground mb-2 font-medium">{title}</p>
      <p className={cn(
        "text-3xl font-bold text-foreground font-mono mb-3 transition-all duration-300",
        isAnimating && "scale-105 text-primary"
      )}>
        {value}
      </p>

      {description && (
        <p className="text-xs text-muted-foreground/60 flex items-center gap-1.5 mb-2">
          <span className="w-1 h-1 rounded-full bg-white/20" />
          {description}
        </p>
      )}

      {/* Small progress bar indicator */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-primary/30 via-accent/30 to-transparent rounded-b-2xl opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );
}
