/**
 * KillSwitch Component - Botão de Pânico para Emergências
 * 
 * Features:
 * - Mostra status atual (robôs ativos)
 * - Confirmação dupla antes de executar
 * - Opção de fechar posições a mercado
 * - Feedback visual durante execução
 */

import { useState, useEffect } from 'react';
import { 
  AlertTriangle, Power, Loader2, CheckCircle2, 
  XCircle, ShieldAlert, Bot, AlertOctagon
} from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import useApi from '@/hooks/useApi';

interface EmergencyStatus {
  active_bots: number;
  open_positions: number;
  kill_switch_available: boolean;
  last_emergency: string | null;
}

interface KillSwitchResult {
  success: boolean;
  message: string;
  bots_stopped: number;
  positions_closed: number;
  errors: string[];
  executed_at: string;
}

interface KillSwitchButtonProps {
  variant?: 'default' | 'compact' | 'header';
  onExecuted?: () => void;
}

export function KillSwitchButton({ variant = 'default', onExecuted }: KillSwitchButtonProps) {
  const api = useApi();
  const { toast } = useToast();
  
  const [status, setStatus] = useState<EmergencyStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<KillSwitchResult | null>(null);
  const [closePositions, setClosePositions] = useState(false);
  const [reason, setReason] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  // Fetch status periodicamente
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // A cada 30s
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const data = await api.get<EmergencyStatus>('/api/emergency/status');
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch emergency status:', err);
    }
  };

  const handleExecuteKillSwitch = async () => {
    if (confirmText !== 'CONFIRMAR') {
      toast({
        title: 'Confirmação Necessária',
        description: 'Digite CONFIRMAR para executar o Kill Switch',
        variant: 'destructive'
      });
      return;
    }

    setExecuting(true);
    setResult(null);

    try {
      const data = await api.post<KillSwitchResult>('/api/emergency/kill-switch', {
        close_positions: closePositions,
        confirm: true,
        reason: reason || 'Acionado manualmente pelo usuário'
      });

      setResult(data);
      
      if (data.success) {
        toast({
          title: '🛑 Kill Switch Executado',
          description: data.message,
        });
        onExecuted?.();
      } else {
        toast({
          title: 'Kill Switch Executado com Erros',
          description: `${data.errors.length} erro(s) ocorreram`,
          variant: 'destructive'
        });
      }

      // Atualizar status
      fetchStatus();
      
    } catch (err: any) {
      toast({
        title: 'Erro ao Executar Kill Switch',
        description: err.message,
        variant: 'destructive'
      });
    } finally {
      setExecuting(false);
    }
  };

  const resetDialog = () => {
    setResult(null);
    setClosePositions(false);
    setReason('');
    setConfirmText('');
  };

  // Render compacto para header
  if (variant === 'compact' || variant === 'header') {
    return (
      <AlertDialog open={isOpen} onOpenChange={(open) => {
        setIsOpen(open);
        if (!open) resetDialog();
      }}>
        <AlertDialogTrigger asChild>
          <Button
            variant="ghost"
            size={variant === 'header' ? 'sm' : 'default'}
            className={`text-red-500 hover:text-red-400 hover:bg-red-500/10 ${
              status?.active_bots && status.active_bots > 0 ? 'animate-pulse' : ''
            }`}
          >
            <Power className="w-4 h-4 mr-1" />
            {variant === 'default' && 'Kill Switch'}
            {status?.active_bots ? (
              <Badge variant="outline" className="ml-1 text-xs border-red-500/30 text-red-400">
                {status.active_bots}
              </Badge>
            ) : null}
          </Button>
        </AlertDialogTrigger>
        <KillSwitchDialogContent
          status={status}
          executing={executing}
          result={result}
          closePositions={closePositions}
          setClosePositions={setClosePositions}
          reason={reason}
          setReason={setReason}
          confirmText={confirmText}
          setConfirmText={setConfirmText}
          onExecute={handleExecuteKillSwitch}
          onClose={() => {
            setIsOpen(false);
            resetDialog();
          }}
        />
      </AlertDialog>
    );
  }

  // Render padrão (card completo)
  return (
    <Card className="bg-slate-900 border-red-500/30">
      <CardHeader className="pb-3">
        <CardTitle className="text-white flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-red-500" />
          Parada de Emergência
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status */}
        <div className="flex items-center justify-between p-3 bg-slate-800 rounded-lg">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-slate-400" />
            <span className="text-slate-300">Robôs Ativos</span>
          </div>
          <Badge className={status?.active_bots && status.active_bots > 0 
            ? 'bg-emerald-500/20 text-emerald-400' 
            : 'bg-slate-700 text-slate-400'
          }>
            {status?.active_bots ?? '-'}
          </Badge>
        </div>

        {/* Aviso */}
        <Alert className="bg-red-500/10 border-red-500/30">
          <AlertTriangle className="h-4 w-4 text-red-500" />
          <AlertDescription className="text-red-400 text-sm">
            O Kill Switch para TODOS os robôs imediatamente. 
            Use apenas em emergências.
          </AlertDescription>
        </Alert>

        {/* Botão */}
        <AlertDialog open={isOpen} onOpenChange={(open) => {
          setIsOpen(open);
          if (!open) resetDialog();
        }}>
          <AlertDialogTrigger asChild>
            <Button
              variant="destructive"
              className="w-full bg-red-600 hover:bg-red-700"
              disabled={!status?.active_bots || status.active_bots === 0}
            >
              <Power className="w-5 h-5 mr-2" />
              Ativar Kill Switch
            </Button>
          </AlertDialogTrigger>
          <KillSwitchDialogContent
            status={status}
            executing={executing}
            result={result}
            closePositions={closePositions}
            setClosePositions={setClosePositions}
            reason={reason}
            setReason={setReason}
            confirmText={confirmText}
            setConfirmText={setConfirmText}
            onExecute={handleExecuteKillSwitch}
            onClose={() => {
              setIsOpen(false);
              resetDialog();
            }}
          />
        </AlertDialog>

        {/* Último uso */}
        {status?.last_emergency && (
          <p className="text-xs text-slate-500 text-center">
            Último uso: {new Date(status.last_emergency).toLocaleString('pt-BR')}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// Dialog Content separado para reuso
function KillSwitchDialogContent({
  status,
  executing,
  result,
  closePositions,
  setClosePositions,
  reason,
  setReason,
  confirmText,
  setConfirmText,
  onExecute,
  onClose
}: {
  status: EmergencyStatus | null;
  executing: boolean;
  result: KillSwitchResult | null;
  closePositions: boolean;
  setClosePositions: (v: boolean) => void;
  reason: string;
  setReason: (v: string) => void;
  confirmText: string;
  setConfirmText: (v: string) => void;
  onExecute: () => void;
  onClose: () => void;
}) {
  // Mostrar resultado após execução
  if (result) {
    return (
      <AlertDialogContent className="bg-slate-900 border-slate-800">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-white flex items-center gap-2">
            {result.success ? (
              <>
                <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                Kill Switch Executado
              </>
            ) : (
              <>
                <XCircle className="w-6 h-6 text-amber-500" />
                Executado com Avisos
              </>
            )}
          </AlertDialogTitle>
        </AlertDialogHeader>

        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-slate-800 rounded-lg text-center">
              <p className="text-3xl font-bold text-red-400">{result.bots_stopped}</p>
              <p className="text-sm text-slate-400">Robôs Parados</p>
            </div>
            <div className="p-4 bg-slate-800 rounded-lg text-center">
              <p className="text-3xl font-bold text-amber-400">{result.positions_closed}</p>
              <p className="text-sm text-slate-400">Posições Fechadas</p>
            </div>
          </div>

          {result.errors.length > 0 && (
            <Alert className="bg-amber-500/10 border-amber-500/30">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <AlertDescription className="text-amber-400 text-sm">
                <p className="font-medium mb-1">{result.errors.length} erro(s):</p>
                <ul className="list-disc pl-4 space-y-1">
                  {result.errors.map((error, i) => (
                    <li key={i}>{error}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          <p className="text-sm text-slate-400 text-center">
            Executado em: {new Date(result.executed_at).toLocaleString('pt-BR')}
          </p>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose} className="bg-slate-800 border-slate-700">
            Fechar
          </AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    );
  }

  // Dialog de confirmação
  return (
    <AlertDialogContent className="bg-slate-900 border-slate-800">
      <AlertDialogHeader>
        <AlertDialogTitle className="text-white flex items-center gap-2">
          <AlertOctagon className="w-6 h-6 text-red-500" />
          Confirmar Kill Switch
        </AlertDialogTitle>
        <AlertDialogDescription className="text-slate-400">
          Esta ação irá <strong className="text-red-400">PARAR IMEDIATAMENTE</strong> todos 
          os seus robôs de trading. Esta ação é irreversível.
        </AlertDialogDescription>
      </AlertDialogHeader>

      <div className="space-y-4 py-4">
        {/* Status atual */}
        <div className="p-3 bg-slate-800 rounded-lg flex items-center justify-between">
          <span className="text-slate-400">Robôs que serão parados:</span>
          <Badge className="bg-red-500/20 text-red-400 text-lg px-3">
            {status?.active_bots ?? 0}
          </Badge>
        </div>

        {/* Opção fechar posições */}
        <div className="flex items-start space-x-3 p-3 bg-amber-500/10 rounded-lg border border-amber-500/30">
          <Checkbox
            id="closePositions"
            checked={closePositions}
            onCheckedChange={(checked) => setClosePositions(checked as boolean)}
            className="mt-1"
          />
          <div>
            <Label htmlFor="closePositions" className="text-amber-400 font-medium">
              Fechar todas as posições a mercado
            </Label>
            <p className="text-xs text-amber-400/70 mt-1">
              ⚠️ CUIDADO: Pode causar slippage significativo em mercados voláteis!
            </p>
          </div>
        </div>

        {/* Motivo */}
        <div className="space-y-2">
          <Label className="text-slate-400">Motivo (opcional)</Label>
          <Textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Ex: Mercado muito volátil, erro no robô..."
            className="bg-slate-800 border-slate-700 resize-none"
            rows={2}
          />
        </div>

        {/* Confirmação */}
        <div className="space-y-2">
          <Label className="text-red-400">
            Digite <strong>CONFIRMAR</strong> para executar:
          </Label>
          <input
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
            placeholder="CONFIRMAR"
            className="w-full p-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-center font-mono tracking-widest"
          />
        </div>
      </div>

      <AlertDialogFooter>
        <AlertDialogCancel 
          onClick={onClose}
          className="bg-slate-800 border-slate-700"
        >
          Cancelar
        </AlertDialogCancel>
        <Button
          onClick={onExecute}
          disabled={executing || confirmText !== 'CONFIRMAR'}
          className="bg-red-600 hover:bg-red-700"
        >
          {executing ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Executando...
            </>
          ) : (
            <>
              <Power className="w-4 h-4 mr-2" />
              Executar Kill Switch
            </>
          )}
        </Button>
      </AlertDialogFooter>
    </AlertDialogContent>
  );
}

export default KillSwitchButton;
