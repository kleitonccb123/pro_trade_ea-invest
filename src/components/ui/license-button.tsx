/**
 * License-Gated Button Component
 * 
 * A button that shows different states based on license status.
 * Shows lock icon and tooltip when feature is not available.
 */

import { forwardRef, ReactNode } from 'react';
import { Lock, Crown } from 'lucide-react';
import { Button, ButtonProps } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useFeatureGate, useLicense } from '@/hooks/use-license';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface LicenseButtonProps extends ButtonProps {
  feature: 'start_bot' | 'copy_trading' | 'advanced_analytics' | 'telegram_alerts';
  children: ReactNode;
  showUpgradeOnClick?: boolean;
  hideWhenLocked?: boolean;
  lockedText?: string;
}

export const LicenseButton = forwardRef<HTMLButtonElement, LicenseButtonProps>(
  ({ 
    feature, 
    children, 
    showUpgradeOnClick = true,
    hideWhenLocked = false,
    lockedText,
    className,
    onClick,
    disabled,
    ...props 
  }, ref) => {
    const { allowed, reason } = useFeatureGate(feature);
    const { loading } = useLicense();
    const navigate = useNavigate();

    if (hideWhenLocked && !allowed && !loading) {
      return null;
    }

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      if (!allowed && showUpgradeOnClick) {
        e.preventDefault();
        navigate('/pricing');
        return;
      }
      onClick?.(e);
    };

    const isLocked = !allowed && !loading;

    if (isLocked) {
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                ref={ref}
                disabled
                className={cn(
                  "opacity-70 cursor-not-allowed",
                  className
                )}
                {...props}
              >
                <Lock className="w-4 h-4 mr-2" />
                {lockedText || children}
              </Button>
            </TooltipTrigger>
            <TooltipContent 
              side="top" 
              className="bg-slate-900 border-slate-700 max-w-xs"
            >
              <div className="flex items-start gap-2">
                <Crown className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium text-white">Recurso Premium</p>
                  <p className="text-xs text-slate-400 mt-1">{reason}</p>
                  {showUpgradeOnClick && (
                    <button 
                      onClick={() => navigate('/pricing')}
                      className="text-xs text-blue-400 hover:text-blue-300 mt-2 underline"
                    >
                      Ver planos disponíveis →
                    </button>
                  )}
                </div>
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    }

    return (
      <Button
        ref={ref}
        className={className}
        onClick={handleClick}
        disabled={disabled || loading}
        {...props}
      >
        {children}
      </Button>
    );
  }
);

LicenseButton.displayName = 'LicenseButton';

/**
 * Simple wrapper to show/hide content based on license
 */
export function LicenseGate({ 
  feature, 
  children, 
  fallback 
}: { 
  feature: 'start_bot' | 'copy_trading' | 'advanced_analytics' | 'telegram_alerts';
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { allowed } = useFeatureGate(feature);
  const { loading } = useLicense();

  if (loading) {
    return null;
  }

  if (!allowed) {
    return <>{fallback}</> || null;
  }

  return <>{children}</>;
}

/**
 * Badge to show current plan
 */
export function PlanBadge({ className }: { className?: string }) {
  const { plan, loading } = useLicense();
  
  if (loading) {
    return (
      <span className={cn(
        "px-2 py-1 text-xs font-medium rounded bg-slate-700 text-slate-400 animate-pulse",
        className
      )}>
        ...
      </span>
    );
  }

  const planStyles: Record<string, string> = {
    free: 'bg-slate-700 text-slate-300',
    starter: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
    pro: 'bg-purple-500/20 text-purple-400 border border-purple-500/30',
    business: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  };

  const planName = plan?.plan_type || 'free';
  const style = planStyles[planName] || planStyles.free;

  return (
    <span className={cn(
      "px-2 py-1 text-xs font-medium rounded capitalize",
      style,
      className
    )}>
      {planName === 'free' ? 'Gratuito' : planName}
      {plan?.days_remaining && plan.days_remaining <= 7 && (
        <span className="ml-1 text-yellow-400">({plan.days_remaining}d)</span>
      )}
    </span>
  );
}
