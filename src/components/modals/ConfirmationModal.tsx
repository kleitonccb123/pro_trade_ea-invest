import { X, CheckCircle, AlertCircle, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

type ConfirmationType = 'success' | 'warning' | 'danger';

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  type?: ConfirmationType;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
}

export function ConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  type = 'warning',
  title,
  message,
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
}: ConfirmationModalProps) {
  if (!isOpen) return null;

  const icons = {
    success: <CheckCircle className="w-8 h-8 text-success" />,
    warning: <AlertCircle className="w-8 h-8 text-warning" />,
    danger: <XCircle className="w-8 h-8 text-destructive" />,
  };

  const iconBgs = {
    success: 'bg-success/20',
    warning: 'bg-warning/20',
    danger: 'bg-destructive/20',
  };

  const buttonStyles = {
    success: 'bg-success text-success-foreground hover:bg-success/90',
    warning: 'bg-warning text-warning-foreground hover:bg-warning/90',
    danger: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative z-10 w-full max-w-sm glass-card p-6 m-4 animate-scale-in">
        {/* Close button */}
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-muted transition-colors"
        >
          <X className="w-5 h-5 text-muted-foreground" />
        </button>

        {/* Icon */}
        <div className={`w-16 h-16 rounded-2xl ${iconBgs[type]} flex items-center justify-center mx-auto mb-4`}>
          {icons[type]}
        </div>

        {/* Content */}
        <div className="text-center mb-6">
          <h2 className="text-lg font-bold text-foreground mb-2">{title}</h2>
          <p className="text-muted-foreground">{message}</p>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button 
            variant="outline" 
            onClick={onClose}
            className="flex-1 border-border"
          >
            {cancelText}
          </Button>
          <Button 
            onClick={onConfirm}
            className={`flex-1 ${buttonStyles[type]}`}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  );
}
