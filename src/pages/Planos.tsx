/**
 * Planos Page - Página de Planos e Preços
 * 
 * Exibe todos os planos disponíveis com:
 * - Features de cada plano
 * - Preços mensais e anuais
 * - Botão de upgrade
 * - Badge de plano atual
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  Crown, Check, Zap, Rocket, Building2, 
  Loader2, AlertCircle, Sparkles, Clock,
  XCircle, Receipt, ChevronDown, ChevronUp
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import useApi from '@/hooks/useApi';

// ============== TYPES ==============

interface Plan {
  type: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  max_bots: number;
  max_trades_per_day: number;
  strategies: string[];
  exchanges: string[];
  features: string[];
}

interface MyPlan {
  license_type: string;
  license_name: string;
  license_expires_at: string | null;
  is_active: boolean;
  is_expired: boolean;
  days_remaining: number | null;
  max_bots: number;
  bots_used: number;
}

interface Invoice {
  sale_id: string;
  status: string;
  amount: number;
  currency: string;
  payment_method: string | null;
  product_name: string | null;
  created_at: string | null;
}

// ============== FEATURE LABELS ==============

const FEATURE_LABELS: Record<string, string> = {
  basic_dashboard: 'Dashboard básico',
  manual_trading: 'Trading manual',
  basic_analytics: 'Analytics básico',
  advanced_analytics: 'Analytics avançado',
  telegram_alerts: 'Alertas Telegram',
  discord_alerts: 'Alertas Discord',
  api_access: 'Acesso à API',
  priority_support: 'Suporte prioritário',
  custom_strategies: 'Estratégias customizadas',
  white_label: 'White label',
  dedicated_support: 'Suporte dedicado',
  custom_integration: 'Integração customizada',
  sla_99_9: 'SLA 99.9%'
};

// ============== COMPONENT ==============

export default function Planos() {
  const api = useApi();
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  
  const [plans, setPlans] = useState<Plan[]>([]);
  const [myPlan, setMyPlan] = useState<MyPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [showInvoices, setShowInvoices] = useState(false);
  const [canceling, setCanceling] = useState(false);
  
  const highlightPlan = searchParams.get('highlight');
  const showTrial = searchParams.get('trial') === 'true';

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [plansData, myPlanData] = await Promise.all([
        api.get<Plan[]>('/api/license/plans'),
        api.get<MyPlan>('/api/license/my-plan').catch(() => null)
      ]);
      
      setPlans(plansData || []);
      setMyPlan(myPlanData);
    } catch (err) {
      console.error('Failed to fetch plans:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async (planType: string) => {
    if (planType === 'free') return;
    setUpgrading(planType);
    // TradePoints por plano
    const tradePoints = {
      start: 1000,
      pro: 2500,
      quant: 5000,
      black: 15000
    };
    const planKey = planType.toLowerCase();
    const points = tradePoints[planKey] || 0;
    try {
      const result = await api.post<{ success: boolean; checkout_url?: string; message: string }>(
        '/api/license/upgrade',
        { plan: planType, billing_cycle: billingCycle, points_to_credit: points }
      );
      if (result.success && result.checkout_url) {
        toast({
          title: 'Redirecionando...',
          description: result.message
        });
        // window.location.href = result.checkout_url;
      } else {
        toast({
          title: 'Informação',
          description: result.message
        });
      }
    } catch (err: any) {
      toast({
        title: 'Erro',
        description: err.message,
        variant: 'destructive'
      });
    } finally {
      setUpgrading(null);
    }
  };

  const handleActivateTrial = async () => {
    setUpgrading('trial');
    try {
      const result = await api.post<{ success: boolean; message: string }>(
        '/api/license/activate-trial'
      );
      
      if (result.success) {
        toast({
          title: '🎉 Trial Ativado!',
          description: result.message
        });
        fetchData();
      }
    } catch (err: any) {
      toast({
        title: 'Erro',
        description: err.message,
        variant: 'destructive'
      });
    } finally {
      setUpgrading(null);
    }
  };

  const handleCancelSubscription = async () => {
    setCanceling(true);
    try {
      const result = await api.post<{ canceled: boolean; grace_until: string; message: string }>(
        '/api/billing/cancel',
        { reason: 'user_request' }
      );
      toast({
        title: 'Assinatura cancelada',
        description: result.message,
      });
      fetchData();
    } catch (err: any) {
      toast({
        title: 'Erro',
        description: err.message,
        variant: 'destructive',
      });
    } finally {
      setCanceling(false);
    }
  };

  const fetchInvoices = async () => {
    try {
      const data = await api.get<Invoice[]>('/api/billing/invoices');
      setInvoices(data || []);
    } catch {
      setInvoices([]);
    }
  };

  const toggleInvoices = () => {
    if (!showInvoices && invoices.length === 0) {
      fetchInvoices();
    }
    setShowInvoices(!showInvoices);
  };

  const getPrice = (plan: Plan) => {
    return billingCycle === 'yearly' ? plan.price_yearly : plan.price_monthly;
  };

  const getSavings = (plan: Plan) => {
    if (plan.price_monthly === 0) return 0;
    const yearlyTotal = plan.price_yearly;
    const monthlyTotal = plan.price_monthly * 12;
    return Math.round(((monthlyTotal - yearlyTotal) / monthlyTotal) * 100);
  };

  const getPlanIcon = (type: string) => {
    switch (type) {
      case 'pro': return <Zap className="w-6 h-6" />;
      case 'enterprise': return <Building2 className="w-6 h-6" />;
      default: return <Sparkles className="w-6 h-6" />;
    }
  };

  const getPlanColor = (type: string) => {
    switch (type) {
      case 'pro': return 'from-blue-600 to-cyan-600';
      case 'enterprise': return 'from-purple-600 to-pink-600';
      default: return 'from-slate-600 to-slate-500';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 py-12 px-4">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
            <Crown className="w-3 h-3 mr-1" />
            Planos e Preços
          </Badge>
          <h1 className="text-4xl font-bold text-white">
            Escolha o Plano Ideal para Você
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto">
            Potencialize seus trades com robôs automatizados, analytics avançados 
            e suporte dedicado.
          </p>
        </div>

        {/* Current Plan Info */}
        {myPlan && (
          <Alert className="bg-slate-900 border-slate-800">
            <Crown className="h-4 w-4 text-amber-500" />
            <AlertDescription className="text-slate-300">
              Você está no plano <strong>{myPlan.license_name}</strong>
              {myPlan.days_remaining !== null && (
                <span className="ml-2 text-slate-400">
                  ({myPlan.days_remaining} dias restantes)
                </span>
              )}
              {' • '}
              Usando {myPlan.bots_used}/{myPlan.max_bots} robôs
            </AlertDescription>
          </Alert>
        )}

        {/* Subscription Management */}
        {myPlan && myPlan.is_active && myPlan.license_type !== 'free' && (
          <Card className="bg-slate-900 border-slate-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg text-white flex items-center gap-2">
                <Receipt className="w-5 h-5 text-slate-400" />
                Gerenciar Assinatura
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={toggleInvoices}
                  className="border-slate-700 text-slate-300 hover:text-white"
                >
                  <Receipt className="w-4 h-4 mr-2" />
                  Histórico de Faturas
                  {showInvoices ? <ChevronUp className="w-4 h-4 ml-1" /> : <ChevronDown className="w-4 h-4 ml-1" />}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCancelSubscription}
                  disabled={canceling}
                  className="border-red-800/50 text-red-400 hover:text-red-300 hover:bg-red-950/30"
                >
                  {canceling ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <XCircle className="w-4 h-4 mr-2" />}
                  Cancelar Assinatura
                </Button>
              </div>

              {/* Invoices Table */}
              {showInvoices && (
                <div className="border border-slate-800 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-800/50">
                      <tr>
                        <th className="text-left px-4 py-2 text-slate-400 font-medium">Data</th>
                        <th className="text-left px-4 py-2 text-slate-400 font-medium">Produto</th>
                        <th className="text-left px-4 py-2 text-slate-400 font-medium">Método</th>
                        <th className="text-right px-4 py-2 text-slate-400 font-medium">Valor</th>
                        <th className="text-center px-4 py-2 text-slate-400 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="text-center py-6 text-slate-500">
                            Nenhuma fatura encontrada
                          </td>
                        </tr>
                      ) : (
                        invoices.map((inv) => (
                          <tr key={inv.sale_id} className="border-t border-slate-800">
                            <td className="px-4 py-2 text-slate-300">
                              {inv.created_at ? new Date(inv.created_at).toLocaleDateString('pt-BR') : '—'}
                            </td>
                            <td className="px-4 py-2 text-slate-300">{inv.product_name || '—'}</td>
                            <td className="px-4 py-2 text-slate-400 capitalize">{inv.payment_method || '—'}</td>
                            <td className="px-4 py-2 text-right text-white font-medium">
                              R$ {inv.amount.toFixed(2).replace('.', ',')}
                            </td>
                            <td className="px-4 py-2 text-center">
                              <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                                {inv.status === 'paid' ? 'Pago' : inv.status}
                              </Badge>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Trial Banner */}
        {(showTrial || myPlan?.license_type === 'free') && (
          <Card className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 border-blue-500/30">
            <CardContent className="flex items-center justify-between py-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-blue-500/20">
                  <Clock className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white">Experimente Grátis por 7 dias</h3>
                  <p className="text-sm text-slate-400">
                    Acesso completo ao plano Pro sem compromisso
                  </p>
                </div>
              </div>
              <Button
                onClick={handleActivateTrial}
                disabled={upgrading === 'trial'}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {upgrading === 'trial' ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Rocket className="w-4 h-4 mr-2" />
                )}
                Ativar Trial
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Billing Toggle */}
        <div className="flex items-center justify-center gap-4">
          <Label className={billingCycle === 'monthly' ? 'text-white' : 'text-slate-400'}>
            Mensal
          </Label>
          <Switch
            checked={billingCycle === 'yearly'}
            onCheckedChange={(checked) => setBillingCycle(checked ? 'yearly' : 'monthly')}
          />
          <Label className={billingCycle === 'yearly' ? 'text-white' : 'text-slate-400'}>
            Anual
            <Badge className="ml-2 bg-emerald-500/20 text-emerald-400">
              Economize até 33%
            </Badge>
          </Label>
        </div>

        {/* Plans Grid */}
        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const isCurrentPlan = myPlan?.license_type === plan.type;
            const isHighlighted = highlightPlan === plan.type || plan.type === 'pro';
            const savings = getSavings(plan);
              // TradePoints por plano
              const tradePoints = {
                start: 1000,
                pro: 2500,
                quant: 5000,
                black: 15000
              };
              const planKey = plan.type.toLowerCase();
              const points = tradePoints[planKey] || 0;
              const showGlow = planKey === 'pro' || planKey === 'black';
              const bestReward = planKey === 'pro';

            return (
              <Card
                key={plan.type}
                className={`relative overflow-hidden transition-all duration-300 ${
                  isHighlighted && !isCurrentPlan
                    ? 'border-blue-500 bg-slate-900 scale-105 shadow-xl shadow-blue-500/20'
                    : 'border-slate-800 bg-slate-900 hover:border-slate-700'
                }`}
              >
                {/* Popular Badge */}
                {plan.type === 'pro' && (
                  <div className="absolute top-0 right-0">
                    <Badge className="rounded-bl-lg rounded-tr-lg rounded-tl-none rounded-br-none bg-blue-600">
                      Mais Popular
                    </Badge>
                  </div>
                )}

                {/* Current Plan Badge */}
                {isCurrentPlan && (
                  <div className="absolute top-0 left-0">
                    <Badge className="rounded-br-lg rounded-tl-lg rounded-tr-none rounded-bl-none bg-emerald-600">
                      Plano Atual
                    </Badge>
                  </div>
                )}

                <CardHeader className="pt-8">
                  <div className={`w-12 h-12 rounded-lg flex items-center justify-center bg-gradient-to-br ${getPlanColor(plan.type)} mb-4`}>
                    {getPlanIcon(plan.type)}
                  </div>
                  <CardTitle className="text-2xl text-white">{plan.name}</CardTitle>
                  <CardDescription>{plan.description}</CardDescription>
                </CardHeader>

                <CardContent className="space-y-6">
                  {/* Price */}
                  <div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-bold text-white">
                        {getPrice(plan) === 0 ? 'Grátis' : `R$ ${getPrice(plan).toFixed(2).replace('.', ',')}`}
                      </span>
                      {getPrice(plan) > 0 && (
                        <span className="text-slate-400">
                          /{billingCycle === 'yearly' ? 'ano' : 'mês'}
                        </span>
                      )}
                    </div>
                    {billingCycle === 'yearly' && savings > 0 && (
                      <p className="text-sm text-emerald-400 mt-1">
                        Economia de {savings}% no plano anual
                      </p>
                    )}
                  </div>

                  {/* TradePoints Badge */}
                  <div
                    className={`mt-2 flex items-center justify-between`}
                  >
                    <div
                      className={`relative group flex items-center gap-2 px-3 py-1 rounded-lg border border-yellow-500/20 bg-yellow-500/10 transition-transform duration-200 ${showGlow ? 'shadow-[0_0_12px_2px_rgba(255,215,0,0.25)]' : ''}`}
                      style={{ fontWeight: 'bold' }}
                      tabIndex={0}
                      title="Use seus pontos para desbloquear robôs exclusivos ou reduzir taxas de operação."
                      onMouseEnter={e => e.currentTarget.classList.add('scale-110')}
                      onMouseLeave={e => e.currentTarget.classList.remove('scale-110')}
                    >
                      <span className={`flex items-center text-yellow-400 font-bold ${showGlow ? 'drop-shadow-[0_0_8px_gold]' : ''}`}>
                        <span className="mr-1">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 2l2.09 6.26L20 9.27l-5 4.87L16.18 21 12 17.77 7.82 21 9 14.14l-5-4.87 5.91-1.01L12 2z" stroke="#FFD700" strokeWidth="1.5" fill="#FFD700"/>
                          </svg>
                        </span>
                        BÔNUS: +{points.toLocaleString()} TradePoints
                      </span>
                      {bestReward && (
                        <span className="ml-2 px-2 py-0.5 rounded bg-yellow-400/20 text-yellow-300 text-xs font-semibold border border-yellow-400/30">
                          MELHOR RECOMPENSA
                        </span>
                      )}
                      {/* Tooltip */}
                      <span className="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-max bg-slate-900 border border-yellow-500/20 text-xs text-yellow-200 rounded-lg px-3 py-1 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                        Use seus pontos para desbloquear robôs exclusivos ou reduzir taxas de operação.
                      </span>
                    </div>
                  </div>

                  {/* Key Limits */}
                  <div className="p-4 bg-slate-800 rounded-lg space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">Robôs simultâneos</span>
                      <span className="text-white font-medium">{plan.max_bots}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">Trades/dia</span>
                      <span className="text-white font-medium">
                        {plan.max_trades_per_day.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">Estratégias</span>
                      <span className="text-white font-medium">
                        {plan.strategies.length}
                      </span>
                    </div>
                  </div>

                  {/* Features */}
                  <ul className="space-y-2">
                    {plan.features.slice(0, 6).map((feature) => (
                      <li key={feature} className="flex items-center gap-2 text-sm text-slate-300">
                        <Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                        {FEATURE_LABELS[feature] || feature}
                      </li>
                    ))}
                    {plan.features.length > 6 && (
                      <li className="text-sm text-slate-400">
                        + {plan.features.length - 6} mais recursos
                      </li>
                    )}
                  </ul>

                  {/* Exchanges */}
                  <div className="flex flex-wrap gap-1">
                    {plan.exchanges.map((exchange) => (
                      <Badge 
                        key={exchange} 
                        variant="outline" 
                        className="text-xs border-slate-700"
                      >
                        {exchange}
                      </Badge>
                    ))}
                  </div>

                  {/* CTA Button */}
                  <Button
                    onClick={() => handleUpgrade(plan.type)}
                    disabled={isCurrentPlan || upgrading === plan.type}
                    className={`w-full ${
                      plan.type === 'free'
                        ? 'bg-slate-700 hover:bg-slate-600'
                        : plan.type === 'pro'
                        ? 'bg-blue-600 hover:bg-blue-700'
                        : 'bg-purple-600 hover:bg-purple-700'
                    }`}
                  >
                    {upgrading === plan.type ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : null}
                    {isCurrentPlan 
                      ? 'Plano Atual' 
                      : plan.type === 'free' 
                        ? 'Downgrade'
                        : 'Fazer Upgrade'
                    }
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* FAQ */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-white">Dúvidas Frequentes</CardTitle>
          </CardHeader>
          <CardContent className="grid md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-white mb-2">Posso trocar de plano a qualquer momento?</h4>
              <p className="text-sm text-slate-400">
                Sim! Você pode fazer upgrade a qualquer momento. O valor será calculado proporcionalmente.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-white mb-2">O que acontece se minha licença expirar?</h4>
              <p className="text-sm text-slate-400">
                Seus robôs serão pausados automaticamente. Seus dados e configurações serão mantidos por 30 dias.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-white mb-2">Há garantia de reembolso?</h4>
              <p className="text-sm text-slate-400">
                Oferecemos garantia de 7 dias. Se não estiver satisfeito, devolvemos 100% do valor.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-white mb-2">Quais formas de pagamento são aceitas?</h4>
              <p className="text-sm text-slate-400">
                Aceitamos cartão de crédito, PIX e boleto bancário.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
