import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface RiskWarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAccept: () => void;
}

export function RiskWarningModal({ isOpen, onClose, onAccept }: RiskWarningModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative z-10 w-full max-w-md glass-card p-6 m-4 animate-scale-in border-warning/30">
        {/* Close button */}
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-muted transition-colors"
        >
          <X className="w-5 h-5 text-muted-foreground" />
        </button>

        {/* Icon */}
        <div className="w-16 h-16 rounded-2xl bg-warning/20 flex items-center justify-center mx-auto mb-6">
          <AlertTriangle className="w-8 h-8 text-warning" />
        </div>

        {/* Content */}
        <div className="text-center mb-6">
          <h2 className="text-xl font-bold text-foreground mb-2">Aviso de Risco</h2>
          <p className="text-muted-foreground">
            O mercado de criptomoedas é altamente volátil e envolve riscos significativos. 
            Você pode perder parte ou todo o seu investimento.
          </p>
        </div>

        <ul className="space-y-3 mb-6 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-warning mt-2 flex-shrink-0" />
            Nunca invista mais do que pode perder
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-warning mt-2 flex-shrink-0" />
            Resultados passados não garantem resultados futuros
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-warning mt-2 flex-shrink-0" />
            Robôs de trading podem ter perdas
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-warning mt-2 flex-shrink-0" />
            Faça sua própria pesquisa antes de investir
          </li>
        </ul>

        {/* Actions */}
        <div className="flex gap-3">
          <Button 
            variant="outline" 
            onClick={onClose}
            className="flex-1 border-border"
          >
            Voltar
          </Button>
          <Button 
            onClick={onAccept}
            className="flex-1 bg-warning text-warning-foreground hover:bg-warning/90"
          >
            Entendi os Riscos
          </Button>
        </div>
      </div>
    </div>
  );
}
