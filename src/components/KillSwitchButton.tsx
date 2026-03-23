/**
 * Kill Switch Button Component
 * 
 * Emergency button to stop all trading operations.
 * Shows current status and allows quick activation.
 */

import { useState, useEffect } from 'react';
import { AlertTriangle, Power, Loader2, ShieldAlert, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { killSwitchApi, KillSwitchStatus } from '@/lib/api';
import { useKillSwitchWebSocket } from '@/hooks/use-websocket';
import { cn } from '@/lib/utils';

interface KillSwitchButtonProps {
  variant?: 'header' | 'full';
  className?: string;
}

export function KillSwitchButton({ variant = 'header', className }: KillSwitchButtonProps) {
  const [status, setStatus] = useState<KillSwitchStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [reason, setReason] = useState('');
  const [cancelOrders, setCancelOrders] = useState(true);
  const [closePositions, setClosePositions] = useState(false);
  
  const { toast } = useToast();
  const { killSwitch: wsStatus, isConnected: wsConnected } = useKillSwitchWebSocket();

  // Fetch initial status
  useEffect(() => {
    fetchStatus();
  }, []);

  // Update from WebSocket — use primitive values as deps to avoid re-renders when object ref changes
  const wsIsActive = wsStatus.isActive;
  const wsActivatedAt = wsStatus.activatedAt;
  const wsActivatedBy = wsStatus.activatedBy;
  const wsReason = wsStatus.reason;
  const wsAffectedBots = wsStatus.affectedBots;
  const wsCancelledOrders = wsStatus.cancelledOrders;

  useEffect(() => {
    if (wsConnected && wsIsActive !== status?.is_active) {
      setStatus(prev => prev ? {
        ...prev,
        is_active: wsIsActive,
        activated_at: wsActivatedAt || undefined,
        activated_by: wsActivatedBy || undefined,
        reason: wsReason || undefined,
        affected_bots: wsAffectedBots,
        cancelled_orders: wsCancelledOrders,
      } : null);
    }
  }, [wsConnected, wsIsActive, wsActivatedAt, wsActivatedBy, wsReason, wsAffectedBots, wsCancelledOrders]);

  const fetchStatus = async () => {
    try {
      const data = await killSwitchApi.getStatus();
      setStatus(data);
    } catch (error) {
      console.error('Failed to fetch kill switch status:', error);
      // Default to inactive if can't fetch
      setStatus({ is_active: false, affected_bots: 0, cancelled_orders: 0 });
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async () => {
    setActivating(true);
    try {
      const result = await killSwitchApi.activate({
        reason: reason || 'Ativação manual de emergência',
        cancel_orders: cancelOrders,
        close_positions: closePositions,
      });

      if (result.success) {
        setStatus(result.status);
        toast({
          title: '🛑 Kill Switch Ativado',
          description: `${result.status.affected_bots} robôs parados, ${result.status.cancelled_orders} ordens canceladas.`,
          variant: 'destructive',
          duration: 10000,
        });
      }
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Falha ao ativar Kill Switch. Tente novamente.',
        variant: 'destructive',
      });
    } finally {
      setActivating(false);
      setShowConfirmDialog(false);
      setReason('');
    }
  };

  if (loading) {
    return (
      <div className={cn("flex items-center gap-2 px-3 py-2 bg-slate-800 rounded-lg", className)}>
        <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
        <span className="text-xs text-slate-400">Verificando...</span>
      </div>
    );
  }

  const isActive = status?.is_active || false;

  // Compact header variant
  if (variant === 'header') {
    return (
      <>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => !isActive && setShowConfirmDialog(true)}
                disabled={isActive}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg transition-all",
                  isActive 
                    ? "bg-red-500/20 border border-red-500/50 text-red-400 cursor-not-allowed" 
                    : "bg-slate-800 border border-slate-700 hover:border-red-500/50 hover:bg-red-500/10 text-slate-400 hover:text-red-400",
                  className
                )}
              >
                {isActive ? (
                  <>
                    <ShieldAlert className="w-4 h-4 text-red-500 animate-pulse" />
                    <span className="text-xs font-medium hidden sm:inline">EMERGÊNCIA</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" />
                    <span className="text-xs font-medium hidden sm:inline">Kill Switch</span>
                  </>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="bg-slate-900 border-slate-700">
              {isActive ? (
                <div className="text-center">
                  <p className="text-red-400 font-bold">Kill Switch Ativo</p>
                  <p className="text-xs text-slate-400">
                    {status?.affected_bots || 0} robôs parados
                  </p>
                  {status?.reason && (
                    <p className="text-xs text-slate-500 mt-1">Motivo: {status.reason}</p>
                  )}
                </div>
              ) : (
                <p className="text-slate-300">Clique para parar todas as operações</p>
              )}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {/* Confirmation Dialog */}
        <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
          <DialogContent className="bg-slate-900 border-red-500/30 max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-500">
                <AlertTriangle className="w-5 h-5" />
                Ativar Kill Switch de Emergência
              </DialogTitle>
              <DialogDescription className="text-slate-400">
                Esta ação irá parar imediatamente todas as operações de trading.
                Use apenas em casos de emergência real.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="reason" className="text-slate-300">
                  Motivo (opcional)
                </Label>
                <Textarea
                  id="reason"
                  placeholder="Descreva o motivo da ativação..."
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="cancelOrders"
                    checked={cancelOrders}
                    onCheckedChange={(checked) => setCancelOrders(checked as boolean)}
                  />
                  <Label htmlFor="cancelOrders" className="text-slate-300">
                    Cancelar todas as ordens pendentes
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="closePositions"
                    checked={closePositions}
                    onCheckedChange={(checked) => setClosePositions(checked as boolean)}
                  />
                  <Label htmlFor="closePositions" className="text-slate-300 text-red-400">
                    Fechar todas as posições abertas (⚠️ Cuidado!)
                  </Label>
                </div>
              </div>

              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-xs text-red-400">
                  <strong>Atenção:</strong> Uma vez ativado, o Kill Switch permanecerá ativo 
                  até ser desativado manualmente pelo administrador.
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowConfirmDialog(false)}
                className="border-slate-700"
              >
                Cancelar
              </Button>
              <Button
                variant="destructive"
                onClick={handleActivate}
                disabled={activating}
                className="bg-red-600 hover:bg-red-700"
              >
                {activating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Ativando...
                  </>
                ) : (
                  <>
                    <Power className="w-4 h-4 mr-2" />
                    Ativar Kill Switch
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  // Full card variant (for settings page)
  return (
    <div className={cn("p-6 rounded-xl border", 
      isActive ? "bg-red-500/10 border-red-500/30" : "bg-slate-800/50 border-slate-700",
      className
    )}>
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <h3 className="text-lg font-bold flex items-center gap-2">
            {isActive ? (
              <ShieldAlert className="w-5 h-5 text-red-500" />
            ) : (
              <ShieldCheck className="w-5 h-5 text-emerald-500" />
            )}
            Kill Switch de Emergência
          </h3>
          <p className="text-sm text-slate-400">
            {isActive 
              ? `Ativo desde ${new Date(status?.activated_at || '').toLocaleString()}`
              : 'Para todas as operações de trading instantaneamente'
            }
          </p>
        </div>
        
        <Badge variant={isActive ? "destructive" : "outline"}>
          {isActive ? '🔴 ATIVO' : '🟢 Pronto'}
        </Badge>
      </div>

      {isActive && status && (
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div className="bg-slate-900/50 rounded-lg p-3">
            <p className="text-xs text-slate-500">Robôs Afetados</p>
            <p className="text-xl font-bold text-red-400">{status.affected_bots}</p>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-3">
            <p className="text-xs text-slate-500">Ordens Canceladas</p>
            <p className="text-xl font-bold text-red-400">{status.cancelled_orders}</p>
          </div>
        </div>
      )}

      <div className="mt-4">
        <Button
          variant={isActive ? "outline" : "destructive"}
          onClick={() => setShowConfirmDialog(true)}
          disabled={isActive}
          className="w-full"
        >
          {isActive ? 'Kill Switch Já Ativo' : 'Ativar Kill Switch'}
        </Button>
      </div>
    </div>
  );
}
