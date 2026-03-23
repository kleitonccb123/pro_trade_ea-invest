import { useState } from 'react';
import { X, ChevronRight, Bot, TrendingUp, Shield, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const steps = [
  {
    icon: Bot,
    title: 'Robôs de Trading',
    description: 'Configure robôs automatizados para operar 24/7. Escolha estratégias predefinidas ou personalize conforme seu perfil.',
    color: 'primary',
  },
  {
    icon: TrendingUp,
    title: 'Análise Inteligente',
    description: 'Receba análises geradas por IA com indicadores técnicos e projeções de mercado em tempo real.',
    color: 'success',
  },
  {
    icon: Shield,
    title: 'Segurança Primeiro',
    description: 'Sua segurança é prioridade. Usamos criptografia de ponta e nunca temos acesso aos seus fundos.',
    color: 'warning',
  },
  {
    icon: Zap,
    title: 'Pronto para Começar',
    description: 'Conecte sua exchange, configure seu primeiro robô e comece a automatizar seus trades!',
    color: 'accent',
  },
];

export function OnboardingModal({ isOpen, onClose }: OnboardingModalProps) {
  const [currentStep, setCurrentStep] = useState(0);

  if (!isOpen) return null;

  const step = steps[currentStep];
  const isLastStep = currentStep === steps.length - 1;

  const handleNext = () => {
    if (isLastStep) {
      onClose();
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleSkip = () => {
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-background/90 backdrop-blur-md" />
      
      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg glass-card p-8 m-4 animate-scale-in">
        {/* Skip button */}
        <button 
          onClick={handleSkip}
          className="absolute top-4 right-4 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Pular
        </button>

        {/* Progress */}
        <div className="flex gap-2 mb-8">
          {steps.map((_, index) => (
            <div 
              key={index}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors",
                index <= currentStep ? "bg-primary" : "bg-muted"
              )}
            />
          ))}
        </div>

        {/* Icon */}
        <div className={cn(
          "w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6",
          step.color === 'primary' && "bg-primary/20",
          step.color === 'success' && "bg-success/20",
          step.color === 'warning' && "bg-warning/20",
          step.color === 'accent' && "bg-accent/20"
        )}>
          <step.icon className={cn(
            "w-10 h-10",
            step.color === 'primary' && "text-primary",
            step.color === 'success' && "text-success",
            step.color === 'warning' && "text-warning",
            step.color === 'accent' && "text-accent"
          )} />
        </div>

        {/* Content */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-foreground mb-3">{step.title}</h2>
          <p className="text-muted-foreground">{step.description}</p>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          {currentStep > 0 && (
            <Button 
              variant="outline" 
              onClick={() => setCurrentStep(currentStep - 1)}
              className="flex-1 border-border"
            >
              Voltar
            </Button>
          )}
          <Button 
            onClick={handleNext}
            className={cn(
              "bg-gradient-primary text-primary-foreground hover:opacity-90",
              currentStep === 0 && "w-full",
              currentStep > 0 && "flex-1"
            )}
          >
            {isLastStep ? 'Começar' : 'Próximo'}
            {!isLastStep && <ChevronRight className="w-4 h-4 ml-1" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
