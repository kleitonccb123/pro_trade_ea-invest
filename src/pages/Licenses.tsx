import { useState } from 'react';
import { Check, X, Zap, Crown, Diamond, Infinity, Sparkles, Bolt, Shield, TrendingUp, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useLanguage } from '@/hooks/use-language';

interface Plan {
  id: string;
  planKey: string;
  name: string;
  description: string;
  price: number;
  strategies: number;
  featureCount: number;
  features: string[];
  icon: React.ReactNode;
  popular?: boolean;
  color: string;
  borderColor: string;
  badgeColor: string;
  howItWorks: string;
}

function buildFeatures(t: (k: string) => string, planKey: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => t(`licenses.plans.${planKey}.f${i + 1}`));
}

export default function Licenses() {
  const { t } = useLanguage();
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [selectedPlanInfo, setSelectedPlanInfo] = useState<Plan | null>(null);

  const plans: Plan[] = [
    {
      id: 'starter', planKey: 'starter', name: 'START',
      description: t('licenses.plans.starter.description'),
      price: 9.99, strategies: 3, featureCount: 7,
      icon: <Zap className="w-10 h-10" />,
      color: 'from-teal-500 to-emerald-600', borderColor: 'border-teal-500/30', badgeColor: 'bg-teal-500/20 text-teal-300',
      features: buildFeatures(t, 'starter', 7),
      howItWorks: t('licenses.plans.starter.howItWorks'),
    },
    {
      id: 'professional', planKey: 'pro', name: 'PRO+',
      description: t('licenses.plans.pro.description'),
      price: 11.99, strategies: 5, featureCount: 9, popular: true,
      icon: <Crown className="w-10 h-10" />,
      color: 'from-emerald-500 via-teal-500 to-emerald-700', borderColor: 'border-emerald-500/50', badgeColor: 'bg-emerald-500/30 text-emerald-200',
      features: buildFeatures(t, 'pro', 9),
      howItWorks: t('licenses.plans.pro.howItWorks'),
    },
    {
      id: 'advanced', planKey: 'quant', name: 'QUANT',
      description: t('licenses.plans.quant.description'),
      price: 17.99, strategies: 10, featureCount: 10,
      icon: <Diamond className="w-10 h-10" />,
      color: 'from-amber-400 to-orange-600', borderColor: 'border-amber-500/30', badgeColor: 'bg-amber-500/20 text-amber-300',
      features: buildFeatures(t, 'quant', 10),
      howItWorks: t('licenses.plans.quant.howItWorks'),
    },
    {
      id: 'elite', planKey: 'black', name: 'BLACK',
      description: t('licenses.plans.black.description'),
      price: 39.99, strategies: 20, featureCount: 11,
      icon: <Infinity className="w-10 h-10" />,
      color: 'from-zinc-700 via-zinc-900 to-black', borderColor: 'border-zinc-500/30', badgeColor: 'bg-white/10 text-white',
      features: buildFeatures(t, 'black', 11),
      howItWorks: t('licenses.plans.black.howItWorks'),
    },
  ];

  const handleUpgrade = (e: React.MouseEvent, planId: string) => {
    e.stopPropagation();
    // TODO: Integrar com sistema de pagamento
    console.log(`Upgrading to plan: ${planId}`);
    alert(`${t('licenses.redirectingCheckout')}: ${planId}`);
  };

  const getDiscountedPrice = (price: number) => {
    if (billingCycle === 'yearly') {
      return Math.round((price * 12 * 0.9 * 100) / 100) / 12;
    }
    return price;
  };

  const getYearlyPrice = (price: number) => {
    return Math.round(price * 12 * 0.9 * 100) / 100;
  };

  return (
    <div className="min-h-screen py-20 px-4 sm:px-6 lg:px-8" style={{ background: '#0B0E11' }}>
      {/* Animated background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-0 w-96 h-96 rounded-full blur-3xl animate-pulse" style={{ background: 'rgba(35,200,130,0.07)' }}></div>
        <div className="absolute bottom-20 right-0 w-96 h-96 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s', background: 'rgba(20,160,100,0.05)' }}></div>
        <div className="absolute top-1/2 left-1/2 w-72 h-72 rounded-full blur-3xl -translate-x-1/2" style={{ background: 'rgba(35,200,130,0.04)' }}></div>
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        {/* Header Section */}
        <div className="text-center mb-20">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 mb-6 px-4 py-2 rounded-full backdrop-blur-md animate-bounce" style={{ border: '1px solid rgba(35,200,130,0.3)', background: 'rgba(35,200,130,0.08)' }}>
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-bold text-emerald-300 uppercase tracking-tighter">{t('licenses.launchOffer')}</span>
          </div>
          
          {/* Main Title */}
          <h1 className="text-6xl sm:text-8xl font-black mb-6 leading-[0.9] tracking-tighter">
            <span className="bg-gradient-to-b from-white to-slate-400 bg-clip-text text-transparent">
              {t('licenses.dominateThe')}
            </span>
            <br />
            <span className="bg-gradient-to-r from-emerald-400 via-teal-400 to-emerald-500 bg-clip-text text-transparent">
              {t('licenses.cryptoMarket')}
            </span>
          </h1>
          
          <p className="text-xl text-slate-400 max-w-2xl mx-auto mb-12 font-medium leading-relaxed">
            {t('licenses.subtitle')} <span className="text-white font-bold italic underline decoration-emerald-500">{t('licenses.maxPower')}</span> {t('licenses.algoDesc')}
          </p>

          {/* Billing Cycle Toggle */}
          <div className="flex items-center justify-center gap-6 mb-4 flex-wrap">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={cn(
                'px-8 py-3 rounded-xl font-bold transition-all duration-300 text-base',
                billingCycle === 'monthly'
                  ? 'text-white shadow-lg scale-105'
                  : 'bg-slate-800/50 text-slate-300 hover:text-slate-100 hover:bg-slate-700/50 border border-slate-700'
              )}
              style={billingCycle === 'monthly' ? { background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)', boxShadow: '0 4px 20px rgba(35,200,130,0.35)' } : {}}
            >
              <Bolt className="inline w-4 h-4 mr-2" />
              {t('licenses.monthly')}
            </button>
            
            <div className="h-px w-6 bg-gradient-to-r from-slate-700 to-transparent"></div>
            
            <button
              onClick={() => setBillingCycle('yearly')}
              className={cn(
                'px-8 py-3 rounded-xl font-bold transition-all duration-300 text-base relative',
                billingCycle === 'yearly'
                  ? 'text-white shadow-lg scale-105'
                  : 'bg-slate-800/50 text-slate-300 hover:text-slate-100 hover:bg-slate-700/50 border border-slate-700'
              )}
              style={billingCycle === 'yearly' ? { background: 'linear-gradient(135deg, #1aaa6e 0%, #148a58 100%)', boxShadow: '0 4px 20px rgba(35,200,130,0.25)' } : {}}
            >
              <TrendingUp className="inline w-4 h-4 mr-2" />
              {t('licenses.yearly')}
              {billingCycle === 'yearly' && (
                <span className="absolute -top-3 -right-3 inline-block bg-gradient-to-r from-emerald-400 to-green-500 text-white text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap shadow-lg">
                  {t('licenses.save10')}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Plans Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-20">
          {plans.map((plan) => (
            <div
              key={plan.id}
              onClick={() => setSelectedPlanInfo(plan)}
              className={cn(
                'relative rounded-2xl transition-all duration-300 transform hover:scale-105 cursor-pointer flex flex-col',
                plan.popular
                  ? 'lg:scale-105 border-2 border-emerald-500/50 shadow-2xl shadow-emerald-500/20 bg-gradient-to-br from-slate-800/90 to-slate-900/50 backdrop-blur-xl'
                  : 'border border-slate-700/50 bg-slate-800/50 hover:bg-slate-800/70 hover:shadow-xl backdrop-blur-sm'
              )}
            >
              {/* Info Icon */}
              <div className="absolute top-4 right-4 text-slate-500 hover:text-emerald-400 opacity-60">
                <Info size={20} />
              </div>

              {/* Popular Badge */}
              {plan.popular && (
                <div className="absolute -top-5 left-1/2 transform -translate-x-1/2 z-20">
                  <div className="text-white text-[10px] font-black px-5 py-2 rounded-full shadow-lg whitespace-nowrap uppercase tracking-widest" style={{ background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)', border: '1px solid rgba(35,200,130,0.4)', boxShadow: '0 4px 16px rgba(35,200,130,0.3)' }}>
                    ⭐ {t('licenses.recommended')}
                  </div>
                </div>
              )}

              <div className="p-8 h-full flex flex-col">
                {/* Icon */}
                <div className={cn(
                  'w-20 h-20 rounded-3xl flex items-center justify-center mb-6 mx-auto text-white bg-gradient-to-br shadow-[0_0_30px_rgba(0,0,0,0.3)] border border-white/10 ring-4 ring-black/50',
                  plan.color
                )}>
                  {plan.icon}
                </div>

                {/* Title and Description */}
                <h3 className="text-3xl font-black text-white text-center mb-2 tracking-tighter uppercase">
                  {plan.name}
                </h3>
                <p className="text-[10px] text-slate-500 text-center mb-8 font-black uppercase tracking-widest leading-none">
                  {plan.description}
                </p>

                {/* Price */}
                <div className="text-center mb-8 bg-black/40 py-4 rounded-2xl border border-white/5">
  <span className="text-lg font-bold text-slate-500 mr-1 italic">USD $</span>
  <span className="text-6xl font-black text-white tracking-tighter">
    {getDiscountedPrice(plan.price).toFixed(2).split('.')[0]}
  </span>
  <span className="text-2xl font-black text-slate-500">
    .{getDiscountedPrice(plan.price).toFixed(2).split('.')[1]}
  </span>
  <p className="text-slate-500 text-[10px] font-black uppercase tracking-widest mt-1">
    {billingCycle === 'monthly'
      ? t('licenses.monthlyBilling')
      : `${t('licenses.yearlyTotal')}${getYearlyPrice(plan.price).toFixed(2)}`}
  </p>
                </div>

                {/* Strategies Count */}
                <div className="bg-white/5 rounded-2xl p-5 mb-8 text-center border border-white/10 group-hover:bg-white/10 transition-colors">
                  <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.2em] mb-2">{t('licenses.operatingPower')}</p>
                  <p className="text-4xl font-black text-white">
                    {plan.strategies} <span className="text-sm font-bold text-slate-500">{t('licenses.robotsUnit')}</span>
                  </p>
                </div>

                {/* CTA Button */}
                <Button
                  onClick={(e) => handleUpgrade(e, plan.id)}
                  className={cn(
                    'w-full mb-8 font-black py-6 rounded-2xl transition-all text-sm uppercase tracking-widest group relative overflow-hidden',
                    plan.popular
                      ? 'text-white hover:opacity-90'
                      : 'bg-white text-black hover:bg-slate-200 border-none'
                  )}
                  style={plan.popular ? { background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)', boxShadow: '0 10px 30px rgba(35,200,130,0.3)' } : {}}
                >
                  <span className="relative z-10">{plan.id === 'elite' ? t('licenses.blackAccess') : t('licenses.activateLicense')}</span>
                </Button>

                {/* Features List (truncated) */}
                <div className="space-y-4 mt-auto">
                  {plan.features.slice(0, 4).map((feature, idx) => (
                    <div key={idx} className="flex items-center gap-3">
                      <div className="flex-shrink-0">
                        <Check className="w-4 h-4 text-emerald-400" />
                      </div>
                      <span className="text-slate-400 text-xs font-bold leading-none tracking-tight">
                        {feature}
                      </span>
                    </div>
                  ))}
                  {plan.features.length > 4 && (
                    <p className="text-[10px] text-emerald-500 font-black text-center pt-2 uppercase tracking-widest">
                      {t('licenses.clickSeeAll')}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Comparison Table */}
        <div className="mb-20">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-black text-white mb-3">
              {t('licenses.fullComparison')}
            </h2>
            <p className="text-slate-400">{t('licenses.fullComparisonDesc')}</p>
          </div>

          <div className="overflow-x-auto">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl backdrop-blur-sm overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700/50">
                    <th className="px-8 py-4 text-left text-white font-bold">{t('licenses.resources')}</th>
                    {plans.map((plan) => (
                      <th
                        key={plan.id}
                        className="px-8 py-4 text-center text-white font-bold text-sm"
                      >
                        {plan.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  <tr className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-8 py-4 text-slate-300 font-semibold">{t('licenses.activeStrategies')}</td>
                    {plans.map((plan) => (
                      <td key={plan.id} className="px-8 py-4 text-center">
                        <span className="text-2xl font-black bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
                          {plan.strategies}
                        </span>
                      </td>
                    ))}
                  </tr>

                  <tr className="bg-slate-900/30 hover:bg-slate-900/50 transition-colors">
                    <td className="px-8 py-4 text-slate-300 font-semibold">{t('licenses.monthlyUnlock')}</td>
                    {plans.map((plan) => (
                      <td key={plan.id} className="px-8 py-4 text-center">
                        <Check className="w-6 h-6 text-emerald-400 mx-auto" />
                      </td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-8 py-4 text-slate-300 font-semibold">{t('licenses.support')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm">{t('licenses.supportEmail')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm">{t('licenses.supportPriority')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm">{t('licenses.support247')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm font-semibold text-emerald-400">{t('licenses.support247Premium')}</td>
                  </tr>

                  <tr className="bg-slate-900/30 hover:bg-slate-900/50 transition-colors">
                    <td className="px-8 py-4 text-slate-300 font-semibold">{t('licenses.history')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm">{t('licenses.days30')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm">{t('licenses.days90')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm">{t('licenses.unlimited')}</td>
                    <td className="px-8 py-4 text-center text-slate-300 text-sm">{t('licenses.unlimited')}</td>
                  </tr>

                  <tr className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-8 py-4 text-slate-300 font-semibold">{t('licenses.apiAccess')}</td>
                    <td className="px-8 py-4 text-center"><X className="w-6 h-6 text-red-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><X className="w-6 h-6 text-red-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><Check className="w-6 h-6 text-emerald-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><Check className="w-6 h-6 text-emerald-400 mx-auto" /></td>
                  </tr>

                  <tr className="bg-slate-900/30 hover:bg-slate-900/50 transition-colors">
                    <td className="px-8 py-4 text-slate-300 font-semibold">{t('licenses.backtestLabel')}</td>
                    <td className="px-8 py-4 text-center"><X className="w-6 h-6 text-red-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><X className="w-6 h-6 text-red-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><Check className="w-6 h-6 text-emerald-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><Check className="w-6 h-6 text-emerald-400 mx-auto" /></td>
                  </tr>

                  <tr className="hover:bg-slate-700/30 transition-colors">
                    <td className="px-8 py-4 text-slate-300 font-semibold">{t('licenses.multiExchange')}</td>
                    <td className="px-8 py-4 text-center"><X className="w-6 h-6 text-red-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><X className="w-6 h-6 text-red-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><X className="w-6 h-6 text-red-400 mx-auto" /></td>
                    <td className="px-8 py-4 text-center"><Check className="w-6 h-6 text-emerald-400 mx-auto" /></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* FAQ */}
        <div>
          <div className="text-center mb-12">
            <h2 className="text-4xl font-black text-white mb-3">
              {t('licenses.faq')}
            </h2>
            <p className="text-slate-400">{t('licenses.faqDesc')}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {[
              {
                icon: <Sparkles className="w-5 h-5" />,
                q: t('licenses.faq1Q'),
                a: t('licenses.faq1A'),
              },
              {
                icon: <Bolt className="w-5 h-5" />,
                q: t('licenses.faq2Q'),
                a: t('licenses.faq2A'),
              },
              {
                icon: <Shield className="w-5 h-5" />,
                q: t('licenses.faq3Q'),
                a: t('licenses.faq3A'),
              },
              {
                icon: <TrendingUp className="w-5 h-5" />,
                q: t('licenses.faq4Q'),
                a: t('licenses.faq4A'),
              },
            ].map((item, idx) => (
              <div
                key={idx}
                className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6 hover:bg-slate-800/70 transition-all duration-300 group hover:shadow-lg"
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className="text-emerald-400 group-hover:text-emerald-300 transition-colors">
                    {item.icon}
                  </div>
                  <h3 className="text-lg font-bold text-white group-hover:text-emerald-200 transition-colors">
                    {item.q}
                  </h3>
                </div>
                <p className="text-slate-400 text-sm leading-relaxed">
                  {item.a}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Plan Info Modal */}
        <Dialog open={!!selectedPlanInfo} onOpenChange={() => setSelectedPlanInfo(null)}>
          <DialogContent className="bg-[#0c1120] border-slate-800 text-white max-w-lg w-[95vw] max-h-[90vh] rounded-3xl p-0 overflow-y-auto shadow-2xl scrollbar-hide">
            {selectedPlanInfo && (
              <div className="flex flex-col">
                <div className={cn("h-32 flex items-center justify-center bg-gradient-to-br p-6", selectedPlanInfo.color)}>
                   <div className="w-20 h-20 bg-black/30 backdrop-blur-xl rounded-2xl border border-white/10 flex items-center justify-center shadow-2xl animate-in zoom-in-50 duration-500">
                    <div className="scale-110">{selectedPlanInfo.icon}</div>
                  </div>
                </div>

                <div className="p-6">
                  <DialogHeader className="mb-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <DialogTitle className="text-3xl font-black tracking-tighter uppercase text-white mb-1">
                          {selectedPlanInfo.name}
                        </DialogTitle>
                        <DialogDescription className="text-emerald-400 font-black uppercase tracking-widest text-[9px]">
                          {selectedPlanInfo.description}
                        </DialogDescription>
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-black text-white">R$ {getDiscountedPrice(selectedPlanInfo.price).toFixed(2)}</p>
                        <p className="text-[9px] text-slate-500 font-black uppercase tracking-widest">{t('licenses.perMonth')}</p>
                      </div>
                    </div>
                  </DialogHeader>

                  <div className="space-y-6">
                    <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4">
                      <h4 className="flex items-center gap-2 text-[9px] font-black uppercase tracking-[0.2em] text-slate-500 mb-3">
                        <Info className="w-3 h-3 text-emerald-500" /> {t('licenses.howPlanWorks')}
                      </h4>
                      <p className="text-slate-300 text-xs leading-relaxed font-bold italic border-l-2 border-emerald-500 pl-4">
                        "{selectedPlanInfo.howItWorks}"
                      </p>
                    </div>

                    <div>
                      <h4 className="flex items-center gap-2 text-[9px] font-black uppercase tracking-[0.2em] text-slate-500 mb-3">
                        <Sparkles className="w-3 h-3 text-emerald-500" /> {t('licenses.techArsenal')}
                      </h4>
                      <div className="grid grid-cols-1 gap-1.5">
                        {selectedPlanInfo.features.map((feature, idx) => (
                          <div key={idx} className="flex items-center gap-3 bg-white/[0.02] p-2.5 rounded-xl border border-white/5 group hover:bg-white/[0.05] transition-colors">
                            <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0 group-hover:bg-emerald-500/40 transition-colors">
                              <Check className="w-2.5 h-2.5 text-emerald-400" />
                            </div>
                            <span className="text-slate-200 text-[11px] font-bold leading-none">
                              {feature}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="mt-8 flex gap-3">
                    <Button 
                      variant="outline" 
                      onClick={() => setSelectedPlanInfo(null)}
                      className="flex-1 py-6 rounded-xl border-slate-700 bg-transparent text-slate-400 font-black uppercase tracking-widest text-[9px] hover:bg-white/5"
                    >
                      {t('licenses.back')}
                    </Button>
                    <Button 
                      onClick={(e) => {
                        handleUpgrade(e, selectedPlanInfo.id);
                        setSelectedPlanInfo(null);
                      }}
                      className={cn(
                        "flex-[2] py-6 rounded-xl font-black uppercase tracking-widest text-xs shadow-xl",
                        selectedPlanInfo.popular ? "text-white hover:opacity-90" : "bg-white text-black hover:bg-slate-200"
                      )}
                      style={selectedPlanInfo.popular ? { background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)', boxShadow: '0 4px 20px rgba(35,200,130,0.35)' } : {}}
                    >
                      {t('licenses.wantThisPlan')}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
