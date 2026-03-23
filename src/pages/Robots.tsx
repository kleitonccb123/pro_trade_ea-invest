import { useState, useEffect } from 'react';
import { Plus, Bot, Filter, DollarSign, ExternalLink, Bitcoin, Globe, Zap, TrendingUp, Building2, BarChart3, Cpu, Shield, Gauge, Smartphone, Code } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { RobotTypeModal } from '@/components/modals/RobotTypeModal';
import { BrokerSignupModal } from '@/components/modals/BrokerSignupModal';
import { BotAnalytics } from '@/components/robots/BotAnalytics';
import { Robot } from '@/types/robot';
import { cn } from '@/lib/utils';
import { useLanguage } from '@/hooks/use-language';

export default function Robots() {
  const { t } = useLanguage();
  const [showRobotTypeModal, setShowRobotTypeModal] = useState(false);
  const [showBrokerModal, setShowBrokerModal] = useState(false);
  const [selectedMarketType, setSelectedMarketType] = useState<'crypto'>('crypto');

  // Auto-open modal when component mounts
  useEffect(() => {
    setShowRobotTypeModal(true);
  }, []);

  const handleBrokerModalOpen = (marketType: 'crypto') => {
    setSelectedMarketType(marketType);
    setShowBrokerModal(true);
  };

  const stats = {
    cryptoActive: 1,
    cryptoProfit: 4379.77,
    totalRobots: 7,
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-primary/10 overflow-hidden">
      {/* Premium Animated Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        {/* Primary Gradient Blob */}
        <div className="absolute top-20 left-10 w-72 h-72 bg-gradient-to-br from-primary/20 to-primary/0 rounded-full blur-3xl animate-pulse"></div>
        
        {/* Secondary Gradient Blob */}
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-gradient-to-tl from-accent/15 to-secondary/5 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
        
        {/* Accent Accent Blob */}
        <div className="absolute top-1/3 right-1/3 w-64 h-64 bg-gradient-to-bl from-accent/10 to-transparent rounded-full blur-3xl animate-float"></div>
        
        {/* Grid Pattern Overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(190,95,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(190,95,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px] opacity-50"></div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 p-6 md:p-8 space-y-16">
        
        {/* Hero Section - Premium Modern */}
        <div className="text-center space-y-8 pt-8 animate-fade-up">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-card border-primary/40">
            <Zap className="w-4 h-4 text-primary animate-pulse-glow" />
            <span className="text-sm font-semibold text-primary">{t('robots.smartTrading')}</span>
          </div>
          
          <div className="space-y-4">
            <h1 className="text-6xl md:text-7xl font-black leading-tight tracking-tighter">
              <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent animate-gradient-shift" style={{ backgroundSize: '200% auto' }}>
                {t('robots.tradingRobots')}
              </span>
              <br />
              <span className="bg-gradient-to-r from-accent via-primary to-accent bg-clip-text text-transparent animate-gradient-shift" style={{ backgroundSize: '200% auto', animationDelay: '1s' }}>
                {t('robots.intelligent')}
              </span>
            </h1>
          </div>
          
          <p className="text-lg md:text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            {t('robots.descriptionFull')} 
            <span className="text-primary font-semibold"> {t('robots.bestMoments')}</span> {t('robots.ofTheMarket')}
          </p>


        </div>

        {/* Premium Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {/* Card 1 - Active Robots */}
          <div className="group relative p-8 rounded-2xl overflow-hidden hover-lift border border-primary/40 hover:border-primary/70 bg-gradient-to-br from-slate-900/90 via-slate-900/95 to-black/95 backdrop-blur-xl shadow-[0_0_40px_-10px_rgba(0,200,255,0.3),0_20px_40px_-15px_rgba(0,0,0,0.8),inset_0_1px_0_0_rgba(255,255,255,0.05)] hover:shadow-[0_0_50px_-5px_rgba(0,200,255,0.5),0_25px_50px_-10px_rgba(0,0,0,0.9),inset_0_1px_0_0_rgba(255,255,255,0.08)] transition-all duration-300">
            <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-bl from-primary/20 to-transparent rounded-full blur-3xl -mr-20 -mt-20 group-hover:scale-150 transition-transform duration-500"></div>
            <div className="relative space-y-4">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center group-hover:scale-110 group-hover:rotate-6 transition-all">
                  <Bitcoin className="w-6 h-6 text-white" />
                </div>
                <span className="text-xs font-bold text-primary bg-primary/20 px-3 py-1 rounded-full">{t('robots.activeBadge')}</span>
              </div>
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground font-medium">{t('robots.activeRobots')}</p>
                <p className="text-4xl font-black text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">{stats.cryptoActive}</p>
              </div>
              <p className="text-sm text-success font-bold pt-2">+${stats.cryptoProfit.toLocaleString()}</p>
            </div>
          </div>

          {/* Card 2 - Total Profit */}
          <div className="group relative p-8 rounded-2xl overflow-hidden hover-lift border border-success/40 hover:border-success/70 bg-gradient-to-br from-slate-900/90 via-slate-900/95 to-black/95 backdrop-blur-xl shadow-[0_0_40px_-10px_rgba(52,211,153,0.3),0_20px_40px_-15px_rgba(0,0,0,0.8),inset_0_1px_0_0_rgba(255,255,255,0.05)] hover:shadow-[0_0_50px_-5px_rgba(52,211,153,0.5),0_25px_50px_-10px_rgba(0,0,0,0.9),inset_0_1px_0_0_rgba(255,255,255,0.08)] transition-all duration-300">
            <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-bl from-success/20 to-transparent rounded-full blur-3xl -mr-20 -mt-20 group-hover:scale-150 transition-transform duration-500"></div>
            <div className="relative space-y-4">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-success to-emerald-500 flex items-center justify-center group-hover:scale-110 group-hover:rotate-6 transition-all">
                  <TrendingUp className="w-6 h-6 text-white" />
                </div>
                <span className="text-xs font-bold text-success bg-success/20 px-3 py-1 rounded-full">+31.8%</span>
              </div>
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground font-medium">{t('robots.totalProfit')}</p>
                <p className="text-4xl font-black text-transparent bg-gradient-to-r from-success to-emerald-400 bg-clip-text">${stats.cryptoProfit.toLocaleString()}</p>
              </div>
              <p className="text-sm text-success font-bold pt-2">{t('robots.thisMonth')}</p>
            </div>
          </div>

          {/* Card 3 - Total Robots */}
          <div className="group relative p-8 rounded-2xl overflow-hidden hover-lift border border-accent/40 hover:border-accent/70 bg-gradient-to-br from-slate-900/90 via-slate-900/95 to-black/95 backdrop-blur-xl shadow-[0_0_40px_-10px_rgba(168,85,247,0.3),0_20px_40px_-15px_rgba(0,0,0,0.8),inset_0_1px_0_0_rgba(255,255,255,0.05)] hover:shadow-[0_0_50px_-5px_rgba(168,85,247,0.5),0_25px_50px_-10px_rgba(0,0,0,0.9),inset_0_1px_0_0_rgba(255,255,255,0.08)] transition-all duration-300">
            <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-bl from-accent/20 to-transparent rounded-full blur-3xl -mr-20 -mt-20 group-hover:scale-150 transition-transform duration-500"></div>
            <div className="relative space-y-4">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent to-violet-500 flex items-center justify-center group-hover:scale-110 group-hover:rotate-6 transition-all">
                  <Bot className="w-6 h-6 text-white" />
                </div>
                <span className="text-xs font-bold text-accent bg-accent/20 px-3 py-1 rounded-full">{t('robots.totalBadge')}</span>
              </div>
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground font-medium">{t('robots.availableRobots')}</p>
                <p className="text-4xl font-black text-transparent bg-gradient-to-r from-accent to-violet-400 bg-clip-text">{stats.totalRobots}</p>
              </div>
              <p className="text-sm text-accent font-bold pt-2">{stats.cryptoActive} {t('robots.inOperation')}</p>
            </div>
          </div>
        </div>

        {/* Bot Analytics Section */}
        <div className="space-y-8 animate-fade-up delay-100">
          <div className="text-center space-y-3">
            <h2 className="text-4xl md:text-5xl font-black flex items-center justify-center gap-3">
              <BarChart3 className="w-10 h-10 text-primary animate-float" />
              <span className="text-transparent bg-gradient-to-r from-primary via-accent to-cyan-400 bg-clip-text">{t('robots.performanceRealtime')}</span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              {t('robots.performanceRealtimeDesc')}
            </p>
          </div>
          <BotAnalytics />
        </div>

        {/* Market Selection - Premium Card */}
        <div className="space-y-8">
          <div className="text-center space-y-3 animate-fade-up delay-200">
            <h2 className="text-4xl md:text-5xl font-black text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">{t('robots.selectMarket')}</h2>
            <p className="text-lg text-muted-foreground">{t('robots.advancedTrading')}</p>
          </div>

          <div className="grid md:grid-cols-1 gap-6 max-w-2xl mx-auto">
            <div 
              onClick={() => setShowRobotTypeModal(true)}
              className={cn(
                "group cursor-pointer p-12 rounded-2xl border transition-all duration-300 hover-lift overflow-hidden relative bg-gradient-to-br from-slate-900/90 via-slate-900/95 to-black/95 backdrop-blur-xl",
                "border-orange-500/40 hover:border-orange-500/70 shadow-[0_0_50px_-10px_rgba(249,115,22,0.4),0_25px_50px_-15px_rgba(0,0,0,0.8),inset_0_1px_0_0_rgba(255,255,255,0.05)] hover:shadow-[0_0_60px_-5px_rgba(249,115,22,0.6),0_30px_60px_-10px_rgba(0,0,0,0.9),inset_0_1px_0_0_rgba(255,255,255,0.1)]"
              )}
            >
              <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-orange-500/20 to-transparent rounded-full blur-3xl -mr-48 -mt-48 group-hover:scale-125 transition-transform duration-500"></div>
              
              <div className="relative space-y-8 z-10">
                <div className="flex items-center justify-between">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-orange-500 to-yellow-500 flex items-center justify-center group-hover:scale-125 group-hover:-rotate-12 transition-all duration-300 shadow-lg shadow-orange-500/30">
                    <Bitcoin className="w-10 h-10 text-white" />
                  </div>
                  <div className="text-right space-y-2">
                    <p className="text-xs font-bold text-orange-600 bg-orange-500/30 px-4 py-2 rounded-full inline-block border border-orange-500/50">{t('robots.popularBadge')}</p>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <h3 className="text-3xl font-black text-white group-hover:text-orange-400 transition-colors">
                    {t('robots.cryptocurrencies')}
                  </h3>
                  <p className="text-muted-foreground leading-relaxed text-base">
                    {t('robots.cryptoDesc')}
                  </p>
                  
                  <div className="flex flex-wrap items-center gap-4 pt-6">
                    <div className="flex items-center gap-3 text-sm bg-gradient-to-r from-success/20 to-emerald-500/10 text-success px-4 py-3 rounded-xl font-bold border border-success/30">
                      <TrendingUp className="w-4 h-4" />
                      {t('robots.avgProfit')}
                    </div>
                    <div className="flex items-center gap-3 text-sm bg-gradient-to-r from-primary/20 to-cyan-500/10 text-primary px-4 py-3 rounded-xl font-bold border border-primary/30">
                      <Bot className="w-4 h-4" />
                      {stats.totalRobots} {t('robots.activeRobotsCount')}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Features Section - Premium Grid */}
        <div className="space-y-12">
          <div className="text-center space-y-3 animate-fade-up delay-300">
            <h2 className="text-4xl md:text-5xl font-black text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">{t('robots.features')}</h2>
            <p className="text-lg text-muted-foreground">{t('robots.featuresDesc')}</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
            {[
              {
                icon: Zap,
                titleKey: 'robots.instantExecution',
                descKey: 'robots.instantExecutionDesc',
                color: 'from-blue-600 to-cyan-500',
                accent: 'blue'
              },
              {
                icon: TrendingUp,
                titleKey: 'robots.performance',
                descKey: 'robots.performanceDesc',
                color: 'from-green-600 to-emerald-500',
                accent: 'green'
              },
              {
                icon: Cpu,
                titleKey: 'robots.aiPowered',
                descKey: 'robots.aiPoweredDesc',
                color: 'from-purple-600 to-pink-500',
                accent: 'purple'
              },
              {
                icon: Shield,
                titleKey: 'robots.riskManagement',
                descKey: 'robots.riskManagementDesc',
                color: 'from-orange-600 to-red-500',
                accent: 'orange'
              },
              {
                icon: Gauge,
                titleKey: 'robots.automated',
                descKey: 'robots.automatedDesc',
                color: 'from-violet-600 to-purple-500',
                accent: 'violet'
              },
              {
                icon: Smartphone,
                titleKey: 'robots.mobileMonitoring',
                descKey: 'robots.mobileMonitoringDesc',
                color: 'from-indigo-600 to-blue-500',
                accent: 'indigo'
              }
            ].map((feature, idx) => {
              const Icon = feature.icon;
              return (
                <div 
                  key={idx}
                  className="group p-8 rounded-2xl border border-border/40 hover:border-primary/70 transition-all duration-300 hover-lift overflow-hidden relative animate-fade-up bg-gradient-to-br from-slate-900/90 via-slate-900/95 to-black/95 backdrop-blur-xl shadow-[0_0_30px_-8px_rgba(0,200,255,0.2),0_15px_35px_-10px_rgba(0,0,0,0.7),inset_0_1px_0_0_rgba(255,255,255,0.05)] hover:shadow-[0_0_40px_-5px_rgba(0,200,255,0.4),0_20px_45px_-8px_rgba(0,0,0,0.8),inset_0_1px_0_0_rgba(255,255,255,0.08)]"
                  style={{ animationDelay: `${100 * (idx + 1)}ms` }}
                >
                  <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-${feature.accent}-500/20 to-transparent rounded-full blur-3xl -mr-16 -mt-16 group-hover:scale-150 transition-transform duration-500 pointer-events-none`}></div>
                  
                  <div className="relative space-y-4 z-10">
                    <div className={cn(
                      "w-14 h-14 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-120 group-hover:-rotate-6 transition-all duration-300 shadow-lg",
                      `bg-gradient-to-br ${feature.color}`
                    )}>
                      <Icon className="w-7 h-7 text-white" />
                    </div>
                    <h3 className="font-bold text-foreground text-lg group-hover:text-primary transition-colors">{t(feature.titleKey)}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{t(feature.descKey)}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* CTA Section - Premium Final Call */}
        <div className="mt-16 mb-12 rounded-3xl bg-gradient-to-br from-slate-900/95 via-slate-900/98 to-black/95 backdrop-blur-xl border border-primary/50 p-12 md:p-16 text-center space-y-8 relative overflow-hidden group hover-lift animate-fade-up delay-500 shadow-[0_0_80px_-15px_rgba(0,200,255,0.4),0_30px_60px_-15px_rgba(0,0,0,0.9),inset_0_1px_0_0_rgba(255,255,255,0.05)] hover:shadow-[0_0_100px_-10px_rgba(0,200,255,0.6),0_40px_70px_-10px_rgba(0,0,0,1),inset_0_1px_0_0_rgba(255,255,255,0.08)]">
          {/* Animated Background */}
          <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-primary/10 via-accent/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
          <div className="absolute -top-32 -right-32 w-96 h-96 bg-gradient-to-bl from-primary/30 to-transparent rounded-full blur-3xl group-hover:scale-125 transition-transform duration-500"></div>
          
          <div className="relative z-10 space-y-6">
            <h2 className="text-5xl font-black text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">{t('robots.readyToStart')}</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
              {t('robots.readyDesc')}
              <span className="text-primary font-bold"> {t('robots.youAreNext')}</span>
            </p>
            <button
              onClick={() => setShowRobotTypeModal(true)}
              className="inline-block px-10 py-5 text-lg font-bold rounded-xl bg-gradient-to-r from-primary to-accent text-white hover:shadow-2xl hover:shadow-primary/50 transition-all duration-300 transform group-hover:scale-105 border border-primary/50"
            >
              <Plus className="w-5 h-5 inline mr-2" />
              {t('robots.createPremiumRobot')}
            </button>
          </div>
        </div>
      </div>

      {/* Modals */}
      <RobotTypeModal
        open={showRobotTypeModal}
        onOpenChange={setShowRobotTypeModal}
      />

      <BrokerSignupModal
        open={showBrokerModal}
        onOpenChange={setShowBrokerModal}
      />
    </div>
  );
}
