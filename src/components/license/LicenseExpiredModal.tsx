/**
 * License Expired Modal - Modal de Licença Expirada
 * 
 * Exibido automaticamente quando API retorna 403 com error: "license_expired"
 * Oferece upgrade para planos Pro/Enterprise
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Crown, AlertTriangle, Rocket, X, Check, Zap } from 'lucide-react';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle,
  DialogDescription 
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface LicenseExpiredModalProps {
  isOpen: boolean;
  onClose: () => void;
  expiredAt?: string | null;
  currentPlan?: string;
}

export function LicenseExpiredModal({ 
  isOpen, 
  onClose, 
  expiredAt,
  currentPlan = 'free'
}: LicenseExpiredModalProps) {
  const navigate = useNavigate();
  const [selectedPlan, setSelectedPlan] = useState<'pro' | 'enterprise'>('pro');

  const handleUpgrade = () => {
    navigate(`/planos?highlight=${selectedPlan}`);
    onClose();
  };

  const handleActivateTrial = async () => {
    // Implementar ativação de trial
    navigate('/planos?trial=true');
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-slate-900 border-slate-800 text-white max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-full bg-amber-500/20">
              <AlertTriangle className="w-6 h-6 text-amber-500" />
            </div>
            <div>
              <DialogTitle className="text-xl">Licença Expirada</DialogTitle>
              <DialogDescription className="text-slate-400">
                {expiredAt 
                  ? `Sua licença expirou em ${new Date(expiredAt).toLocaleDateString('pt-BR')}`
                  : 'Sua licença expirou'
                }
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Alert */}
          <div className="p-4 bg-amber-500/10 rounded-lg border border-amber-500/30">
            <p className="text-amber-400 text-sm">
              Para continuar usando os robôs de trading e recursos avançados, 
              atualize seu plano ou ative um trial gratuito.
            </p>
          </div>

          {/* Plans Quick View */}
          <div className="grid grid-cols-2 gap-4">
            {/* Pro Plan */}
            <button
              onClick={() => setSelectedPlan('pro')}
              className={`p-4 rounded-lg border text-left transition-all ${
                selectedPlan === 'pro'
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-slate-700 bg-slate-800 hover:border-slate-600'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-5 h-5 text-blue-500" />
                <span className="font-semibold">Pro</span>
                {selectedPlan === 'pro' && (
                  <Check className="w-4 h-4 text-blue-500 ml-auto" />
                )}
              </div>
              <p className="text-2xl font-bold text-white">R$ 49,90</p>
              <p className="text-xs text-slate-400">/mês</p>
              <ul className="mt-3 space-y-1 text-xs text-slate-400">
                <li>✓ 10 robôs simultâneos</li>
                <li>✓ Todas estratégias</li>
                <li>✓ Alertas Telegram/Discord</li>
              </ul>
            </button>

            {/* Enterprise Plan */}
            <button
              onClick={() => setSelectedPlan('enterprise')}
              className={`p-4 rounded-lg border text-left transition-all ${
                selectedPlan === 'enterprise'
                  ? 'border-purple-500 bg-purple-500/10'
                  : 'border-slate-700 bg-slate-800 hover:border-slate-600'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Crown className="w-5 h-5 text-purple-500" />
                <span className="font-semibold">Enterprise</span>
                {selectedPlan === 'enterprise' && (
                  <Check className="w-4 h-4 text-purple-500 ml-auto" />
                )}
              </div>
              <p className="text-2xl font-bold text-white">R$ 199,90</p>
              <p className="text-xs text-slate-400">/mês</p>
              <ul className="mt-3 space-y-1 text-xs text-slate-400">
                <li>✓ 100 robôs simultâneos</li>
                <li>✓ Suporte dedicado</li>
                <li>✓ SLA 99.9%</li>
              </ul>
            </button>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-3">
            <Button
              onClick={handleUpgrade}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              <Rocket className="w-4 h-4 mr-2" />
              Fazer Upgrade para {selectedPlan === 'pro' ? 'Pro' : 'Enterprise'}
            </Button>

            {currentPlan === 'free' && (
              <Button
                variant="outline"
                onClick={handleActivateTrial}
                className="w-full border-slate-700"
              >
                Ativar Trial Gratuito de 7 dias
              </Button>
            )}

            <Button
              variant="ghost"
              onClick={onClose}
              className="w-full text-slate-400"
            >
              Continuar com Plano Limitado
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default LicenseExpiredModal;
