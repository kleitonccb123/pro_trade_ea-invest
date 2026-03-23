import { useState } from 'react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ExternalLink, Star, Shield, Zap, TrendingUp, Gift, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface BrokerSignupModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BrokerSignupModal({ open, onOpenChange }: BrokerSignupModalProps) {
  const [hoveredBroker, setHoveredBroker] = useState<string | null>(null);

  const exchanges = [
    {
      id: 'kucoin',
      name: 'KuCoin',
      description: 'Exchange de criptomoedas segura e confiável',
      logo: '🟢',
      signupLink: 'https://www.kucoin.com/ucenter/signup',
      features: ['Taxas competitivas', 'Mais de 600 moedas', 'Trading 24/7', 'App mobile'],
      bonus: 'Até 50 USDT de bônus',
      rating: 4.7,
      gradient: 'from-emerald-500 to-teal-500',
      verified: true,
    },
  ];

  const handleSignup = (signupLink: string, exchangeName: string) => {
    console.log(`User clicked signup for ${exchangeName}`);
    window.open(signupLink, '_blank', 'noopener,noreferrer');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl p-0 overflow-hidden bg-background/95 backdrop-blur-xl border border-border/50">
        <div className="relative">
          {/* Background gradient */}
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-secondary/5" />
          
          {/* Header */}
          <div className="relative p-8 text-center border-b border-border/30">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-4">
              <Shield className="w-4 h-4 text-emerald-500" />
              <span className="text-sm font-medium text-emerald-500">KuCoin - Exchange Verificada</span>
            </div>
            
            <h2 className="text-3xl font-bold bg-gradient-to-r from-emerald-500 to-teal-500 bg-clip-text text-transparent mb-2">
              Conectar KuCoin
            </h2>
            <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
              Comece a usar os robôs de trading agora
            </p>
          </div>

          {/* Exchanges Grid */}
          <div className="relative p-8">
            <div className="flex justify-center mb-8">
              {exchanges.map((exchange) => (
                <div
                  key={exchange.id}
                  className={cn(
                    "group relative p-6 rounded-2xl border cursor-pointer transition-all duration-300 ease-out max-w-md w-full",
                    "bg-card/60 backdrop-blur-sm hover:bg-card/80 border-border/50 hover:border-primary/50",
                    "hover:scale-105 hover:shadow-2xl hover:shadow-primary/10",
                    hoveredBroker === exchange.id && "scale-105 shadow-2xl shadow-primary/20 border-primary/50"
                  )}
                  onMouseEnter={() => setHoveredBroker(exchange.id)}
                  onMouseLeave={() => setHoveredBroker(null)}
                >
                  {/* Background gradient */}
                  <div className={cn(
                    "absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-10 transition-opacity duration-300 bg-gradient-to-br",
                    exchange.gradient
                  )} />
                  
                  {/* Verified badge */}
                  {exchange.verified && (
                    <div className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-success flex items-center justify-center shadow-lg">
                      <CheckCircle className="w-5 h-5 text-white" />
                    </div>
                  )}

                  {/* Logo and header */}
                  <div className="relative space-y-4">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-12 h-12 rounded-xl flex items-center justify-center text-2xl transition-all duration-300 bg-gradient-to-br",
                        exchange.gradient,
                        "group-hover:scale-110 group-hover:rotate-3"
                      )}>
                        {exchange.logo}
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                          {exchange.name}
                        </h3>
                        <div className="flex items-center gap-1">
                          <Star className="w-4 h-4 text-yellow-500 fill-current" />
                          <span className="text-sm text-muted-foreground">{exchange.rating}</span>
                        </div>
                      </div>
                    </div>

                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {exchange.description}
                    </p>

                    {/* Features */}
                    <div className="space-y-2">
                      {exchange.features.map((feature, index) => (
                        <div
                          key={feature}
                          className={cn(
                            "flex items-center gap-2 text-sm transition-all duration-300",
                            "transform translate-x-0 group-hover:translate-x-1"
                          )}
                          style={{ transitionDelay: `${index * 50}ms` }}
                        >
                          <div className={cn(
                            "w-1.5 h-1.5 rounded-full bg-gradient-to-r flex-shrink-0",
                            exchange.gradient
                          )} />
                          <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                            {feature}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Bonus */}
                    <div className={cn(
                      "p-3 rounded-lg border transition-all duration-300 bg-gradient-to-r",
                      exchange.gradient,
                      "bg-opacity-10 border-opacity-30 group-hover:bg-opacity-20"
                    )}>
                      <div className="flex items-center gap-2">
                        <Gift className="w-4 h-4 text-primary" />
                        <span className="text-sm font-medium text-foreground">{exchange.bonus}</span>
                      </div>
                    </div>

                    {/* CTA Button */}
                    <Button
                      onClick={() => handleSignup(exchange.signupLink, exchange.name)}
                      className={cn(
                        "w-full mt-4 bg-gradient-to-r text-white font-medium transition-all duration-300",
                        exchange.gradient,
                        "hover:scale-105 hover:shadow-lg group-hover:shadow-xl"
                      )}
                    >
                      <span>Cadastrar Grátis</span>
                      <ExternalLink className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            {/* Benefits Section */}
            <div className="bg-card/30 rounded-2xl p-6 border border-border/30">
              <div className="text-center mb-6">
                <h3 className="text-xl font-bold text-foreground mb-2">
                  Por que escolher nossas parcerias?
                </h3>
                <p className="text-muted-foreground">
                  Trabalhamos apenas com exchanges confiáveis e regulamentadas
                </p>
              </div>

              <div className="grid md:grid-cols-4 gap-6">
                <div className="text-center space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center mx-auto">
                    <Shield className="w-5 h-5 text-emerald-500" />
                  </div>
                  <h4 className="font-semibold text-foreground">Segurança</h4>
                  <p className="text-xs text-muted-foreground">
                    Todas regulamentadas e auditadas
                  </p>
                </div>

                <div className="text-center space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-teal-500/20 flex items-center justify-center mx-auto">
                    <Zap className="w-5 h-5 text-teal-500" />
                  </div>
                  <h4 className="font-semibold text-foreground">Rapidez</h4>
                  <p className="text-xs text-muted-foreground">
                    Execução instantânea de ordens
                  </p>
                </div>

                <div className="text-center space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-emerald-600/20 flex items-center justify-center mx-auto">
                    <TrendingUp className="w-5 h-5 text-emerald-600" />
                  </div>
                  <h4 className="font-semibold text-foreground">Baixas Taxas</h4>
                  <p className="text-xs text-muted-foreground">
                    Spreads competitivos do mercado
                  </p>
                </div>

                <div className="text-center space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-teal-600/20 flex items-center justify-center mx-auto">
                    <Gift className="w-5 h-5 text-teal-600" />
                  </div>
                  <h4 className="font-semibold text-foreground">Bônus</h4>
                  <p className="text-xs text-muted-foreground">
                    Ofertas exclusivas para novos usuários
                  </p>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="text-center mt-6 pt-4 border-t border-border/30">
              <p className="text-xs text-muted-foreground">
                🔒 Conexão segura • ✅ Cadastro gratuito • 🎁 Bônus limitado
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onOpenChange(false)}
                className="mt-3 text-muted-foreground hover:text-foreground"
              >
                Pular por agora
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
