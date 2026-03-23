import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Bot, ArrowRight, Zap, Shield, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BrokerSignupModal } from './BrokerSignupModal';

interface RobotTypeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RobotTypeModal({ open, onOpenChange }: RobotTypeModalProps) {
  const navigate = useNavigate();
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);
  const [showBrokerModal, setShowBrokerModal] = useState(false);

  const handleCryptoSelect = () => {
    onOpenChange(false);
    setShowBrokerModal(true);
  };

  const handleBrokerModalClose = () => {
    setShowBrokerModal(false);
    navigate('/robots/crypto');
  };

  const robotType = {
    id: 'crypto',
    title: 'Robôs de Criptomoedas',
    description: 'Trading automatizado para Bitcoin, Ethereum, Altcoins e mais. Opere 24/7 com estratégias inteligentes.',
    icon: Bot,
    gradient: 'from-orange-500 to-yellow-500',
    features: ['24/7 Trading', 'DCA Strategies', 'Grid Trading', 'Scalping', 'Trend Following', 'Risk Management'],
    stats: { active: 127, profit: '+34.2%' },
    onClick: handleCryptoSelect,
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl p-0 overflow-hidden bg-background/95 backdrop-blur-xl border border-border/50">
        <div className="relative">
          {/* Background gradient */}
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-secondary/5" />
          
          {/* Content */}
          <div className="relative p-8">
            <DialogHeader className="text-center mb-8">
              <DialogTitle className="text-3xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                Robôs de Trading
              </DialogTitle>
              <DialogDescription className="text-lg text-muted-foreground mt-2">
                Comece sua jornada de trading automatizado com criptomoedas
              </DialogDescription>
            </DialogHeader>

            <div
              className={cn(
                "group relative p-6 rounded-xl border cursor-pointer transition-all duration-300 ease-out",
                "bg-card/50 backdrop-blur-sm hover:bg-card/80 border-border/50 hover:border-primary/50",
                "hover:scale-[1.02] hover:shadow-2xl hover:shadow-primary/10",
                hoveredCard === robotType.id && "scale-[1.02] shadow-2xl shadow-primary/20"
              )}
              onClick={robotType.onClick}
              onMouseEnter={() => setHoveredCard(robotType.id)}
              onMouseLeave={() => setHoveredCard(null)}
            >
              {/* Background gradient */}
              <div className={cn(
                "absolute inset-0 rounded-xl opacity-0 group-hover:opacity-10 transition-opacity duration-300 bg-gradient-to-br",
                robotType.gradient
              )} />
              
              {/* Icon */}
              <div className="flex items-start gap-6">
                <div className={cn(
                  "w-16 h-16 rounded-xl flex items-center justify-center transition-all duration-300 bg-gradient-to-br shrink-0",
                  robotType.gradient,
                  "group-hover:scale-110 group-hover:rotate-3"
                )}>
                  <robotType.icon className="w-8 h-8 text-white" />
                </div>

                {/* Content */}
                <div className="flex-1 space-y-4">
                  <div>
                    <h3 className="text-xl font-semibold text-foreground group-hover:text-primary transition-colors">
                      {robotType.title}
                    </h3>
                    <p className="text-muted-foreground mt-2 leading-relaxed">
                      {robotType.description}
                    </p>
                  </div>

                  {/* Features */}
                  <div className="grid grid-cols-3 gap-2">
                    {robotType.features.map((feature, index) => (
                      <div
                        key={feature}
                        className={cn(
                          "flex items-center gap-2 text-sm transition-all duration-300",
                          "transform translate-x-0 group-hover:translate-x-1"
                        )}
                        style={{ transitionDelay: `${index * 50}ms` }}
                      >
                        <div className={cn(
                          "w-1.5 h-1.5 rounded-full bg-gradient-to-r",
                          robotType.gradient
                        )} />
                        <span className="text-muted-foreground group-hover:text-foreground">
                          {feature}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Stats */}
                  <div className="flex items-center justify-between pt-4 border-t border-border/50">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-success" />
                        <span className="text-sm font-medium text-success">
                          {robotType.stats.profit}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">
                          {robotType.stats.active} ativos
                        </span>
                      </div>
                    </div>
                    
                    <ArrowRight className={cn(
                      "w-5 h-5 transition-all duration-300 text-muted-foreground group-hover:text-primary",
                      "transform translate-x-0 group-hover:translate-x-1"
                    )} />
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom section */}
            <div className="mt-8 pt-6 border-t border-border/50">
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Shield className="w-4 h-4" />
                <span>Proteção de capital garantida com stop-loss automático</span>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>

      {/* Broker Signup Modal */}
      <BrokerSignupModal
        open={showBrokerModal}
        onOpenChange={handleBrokerModalClose}
      />
    </Dialog>
  );
}
