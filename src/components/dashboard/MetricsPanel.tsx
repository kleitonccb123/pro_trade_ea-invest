import { ReactNode, useState } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown, Zap } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface MetricItem {
  label: string;
  value: string | number;
  change?: number;
  icon?: ReactNode;
  color?: 'success' | 'warning' | 'accent' | 'primary' | 'destructive';
}

interface MetricsPanelProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  metrics: MetricItem[];
  expandable?: boolean;
  onMetricClick?: (metric: MetricItem) => void;
  className?: string;
}

const colorClasses = {
  success: 'text-emerald-400 bg-emerald-500/10',
  warning: 'text-amber-400 bg-amber-500/10',
  accent: 'text-purple-400 bg-purple-500/10',
  primary: 'text-brand-primary bg-brand-primary/10',
  destructive: 'text-red-400 bg-red-500/10',
};

export function MetricsPanel({
  title,
  description,
  icon,
  metrics,
  expandable = false,
  onMetricClick,
  className,
}: MetricsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(!expandable);

  return (
    <Card className={cn(
      'glass-card border-white/5 bg-gradient-to-br from-card/60 to-card/30 overflow-hidden',
      className
    )}>
      <CardHeader className={cn("pb-3", expandable && "cursor-pointer")} onClick={() => expandable && setIsExpanded(!isExpanded)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {icon && (
              <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                {icon}
              </div>
            )}
            <div>
              <CardTitle className="text-lg">{title}</CardTitle>
              {description && (
                <CardDescription className="text-xs mt-1">{description}</CardDescription>
              )}
            </div>
          </div>
          {expandable && (
            <ChevronDown className={cn(
              "w-4 h-4 text-muted-foreground transition-transform",
              isExpanded && "rotate-180"
            )} />
          )}
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="space-y-2">
          {metrics.map((metric, idx) => (
            <div
              key={idx}
              onClick={() => onMetricClick?.(metric)}
              className={cn(
                "flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/5",
                "hover:bg-white/10 hover:border-white/10 transition-all",
                onMetricClick && "cursor-pointer"
              )}
            >
              <div className="flex items-center gap-3 flex-1">
                {metric.icon && (
                  <div className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center text-sm',
                    metric.color && colorClasses[metric.color]
                  )}>
                    {metric.icon}
                  </div>
                )}
                <span className="text-sm text-muted-foreground">{metric.label}</span>
              </div>
              <div className="flex items-center gap-3">
                {metric.change !== undefined && (
                  <span className={cn(
                    'text-xs font-semibold px-2 py-1 rounded-full',
                    metric.change > 0 ? 'text-emerald-400 bg-emerald-500/10' : 'text-red-400 bg-red-500/10'
                  )}>
                    {metric.change > 0 ? '+' : ''}{metric.change.toFixed(1)}%
                  </span>
                )}
                <span className="text-sm font-bold text-white">{metric.value}</span>
              </div>
            </div>
          ))}
        </CardContent>
      )}
    </Card>
  );
}
