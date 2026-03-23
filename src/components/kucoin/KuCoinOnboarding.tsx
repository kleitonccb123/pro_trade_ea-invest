import React, { useState } from 'react';
import {
  AlertCircle, Play, Check, ChevronRight, Zap, Shield,
  TrendingUp, Award, AlertTriangle, Lock, Key, ExternalLink, Loader2,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { useLanguage } from '@/hooks/use-language';
import { authService } from '@/services/authService';

interface KuCoinOnboardingProps {
  onCredentialsAdded?: () => void;
}

type DialogStep = 'account-check' | 'api-form' | null;

export function KuCoinOnboarding({ onCredentialsAdded }: KuCoinOnboardingProps) {
  const { t } = useLanguage();
  const [dialogStep, setDialogStep] = useState<DialogStep>(null);
  const [formData, setFormData] = useState({ api_key: '', api_secret: '', api_passphrase: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleContinue = () => setDialogStep('account-check');

  const handleHasAccount = (has: boolean) => {
    if (has) setDialogStep('api-form');
    else window.open('https://www.kucoin.com/ucenter/signup', '_blank');
  };

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const token = authService.getAccessToken();
      if (!token) throw new Error(t('dashboard.onboarding.tokenNotFound'));

      const verify = await fetch('http://localhost:8000/api/trading/auth/verify', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (verify.status === 401) throw new Error(t('dashboard.onboarding.tokenExpired'));
      if (!verify.ok) throw new Error(t('dashboard.onboarding.authError'));

      const res = await fetch('http://localhost:8000/api/trading/kucoin/connect', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      const data = await res.json();
      if (!res.ok || data.status === 'error')
        throw new Error(data.message || data.detail || t('dashboard.onboarding.connectError'));

      setDialogStep(null);
      setFormData({ api_key: '', api_secret: '', api_passphrase: '' });
      onCredentialsAdded?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dashboard.onboarding.unknownError'));
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { icon: Zap,        title: t('dashboard.onboarding.featureApi'),       desc: t('dashboard.onboarding.featureApiDesc') },
    { icon: TrendingUp, title: t('dashboard.onboarding.featureRates'),     desc: t('dashboard.onboarding.featureRatesDesc') },
    { icon: Shield,     title: t('dashboard.onboarding.featureSecurity'),  desc: t('dashboard.onboarding.featureSecurityDesc') },
    { icon: Award,      title: t('dashboard.onboarding.featureReliable'),  desc: t('dashboard.onboarding.featureReliableDesc') },
  ];

  const steps = [
    t('dashboard.onboarding.step1'),
    t('dashboard.onboarding.step2'),
    t('dashboard.onboarding.step3'),
    t('dashboard.onboarding.step4'),
    t('dashboard.onboarding.step5'),
  ];

  return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center p-6">
      <div className="max-w-xl w-full space-y-5">

        {/* Logotipo */}
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center">
            <Zap className="h-5 w-5 text-brand-primary" />
          </div>
          <div>
            <h1 className="font-display font-bold text-lg text-content-primary leading-tight">{t('dashboard.onboarding.appTitle')}</h1>
            <p className="text-[11px] text-content-muted">{t('dashboard.onboarding.appSubtitle')}</p>
          </div>
        </div>

        {/* Título */}
        <div>
          <h2 className="font-display font-bold text-2xl text-content-primary">{t('dashboard.onboarding.title')}</h2>
          <p className="text-sm text-content-secondary mt-1">
            {t('dashboard.onboarding.subtitle')}
          </p>
        </div>

        {/* Aviso */}
        <div className="flex items-start gap-3 p-4 rounded-xl bg-semantic-warning/6 border border-semantic-warning/20">
          <AlertTriangle className="h-4 w-4 text-semantic-warning flex-shrink-0 mt-0.5" />
          <p className="text-sm text-content-secondary">
            {t('dashboard.onboarding.warningText')}{' '}
            <strong className="text-content-primary font-semibold">{t('dashboard.onboarding.exclusively')}</strong> {t('dashboard.onboarding.withKuCoin')}{' '}
            <strong className="text-content-primary font-semibold">KuCoin</strong>. {t('dashboard.onboarding.needActiveAccount')}
          </p>
        </div>

        {/* Features */}
        <div className="grid sm:grid-cols-2 gap-2.5">
          {features.map(({ icon: Icon, title, desc }, i) => (
            <div key={i} className="flex items-start gap-3 p-4 rounded-xl bg-surface-raised border border-edge-subtle hover:border-edge-default transition-colors duration-150">
              <div className="w-8 h-8 rounded-lg bg-surface-hover border border-edge-subtle flex items-center justify-center flex-shrink-0">
                <Icon className="h-4 w-4 text-content-secondary" />
              </div>
              <div>
                <p className="text-sm font-semibold text-content-primary">{title}</p>
                <p className="text-xs text-content-muted mt-0.5 leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Passos */}
        <div className="bg-surface-raised border border-edge-subtle rounded-xl p-5">
          <p className="text-[11px] font-semibold text-content-secondary uppercase tracking-widest mb-4 flex items-center gap-2">
            <Play className="h-3.5 w-3.5" />
            {t('dashboard.onboarding.howToGetCredentials')}
          </p>
          <div className="space-y-2.5">
            {steps.map((step, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="w-5 h-5 rounded-full bg-brand-primary/10 border border-brand-primary/20 text-brand-primary text-[11px] font-mono font-bold flex items-center justify-center flex-shrink-0">
                  {i + 1}
                </span>
                <span className="text-sm text-content-secondary">{step}</span>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <button
          onClick={handleContinue}
          type="button"
          className="w-full py-3.5 px-6 bg-brand-primary hover:bg-brand-primary/90 active:bg-brand-primary/80 text-surface-base font-semibold text-sm rounded-xl transition-colors duration-150 flex items-center justify-center gap-2 group"
        >
          {t('dashboard.onboarding.startNow')}
          <ChevronRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform duration-150" />
        </button>

        <p className="text-center text-xs text-content-muted">
          {t('dashboard.onboarding.encryptedNotice')}
        </p>
      </div>

      {/* Dialog — Tem conta? */}
      <Dialog open={dialogStep === 'account-check'} onOpenChange={(o) => !o && setDialogStep(null)}>
        <DialogContent className="max-w-sm bg-surface-overlay border border-edge-default rounded-2xl shadow-xl p-0">
          <div className="p-7 space-y-6">
            <DialogHeader className="space-y-4">
              <div className="w-11 h-11 rounded-xl bg-semantic-warning/10 border border-semantic-warning/20 flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-semantic-warning" />
              </div>
              <div>
                <DialogTitle className="font-display font-bold text-xl text-content-primary leading-snug">
                  {t('dashboard.onboarding.hasAccountTitle')}
                </DialogTitle>
                <DialogDescription className="text-sm text-content-secondary mt-1.5 leading-relaxed">
                  {t('dashboard.onboarding.hasAccountDesc')}
                </DialogDescription>
              </div>
            </DialogHeader>

            <div className="space-y-2.5">
              <button
                onClick={() => handleHasAccount(true)}
                type="button"
                className="w-full flex items-center gap-3 py-3.5 px-4 rounded-xl bg-semantic-profit/10 hover:bg-semantic-profit/15 active:bg-semantic-profit/20 border border-semantic-profit/25 text-semantic-profit font-semibold text-sm transition-colors duration-150"
              >
                <div className="w-6 h-6 rounded-full bg-semantic-profit/20 flex items-center justify-center flex-shrink-0">
                  <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                </div>
                {t('dashboard.onboarding.yesHaveAccount')}
              </button>

              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-edge-subtle" />
                <span className="text-[11px] font-medium text-content-muted uppercase tracking-widest">{t('common.or') || 'ou'}</span>
                <div className="flex-1 h-px bg-edge-subtle" />
              </div>

              <button
                onClick={() => handleHasAccount(false)}
                type="button"
                className="w-full flex items-center gap-3 py-3.5 px-4 rounded-xl bg-surface-hover hover:bg-surface-active border border-edge-default text-content-primary font-semibold text-sm transition-colors duration-150"
              >
                <ChevronRight className="h-4 w-4 text-content-muted flex-shrink-0" />
                {t('dashboard.onboarding.noCreateAccount')}
              </button>
            </div>

            <div className="pt-4 border-t border-edge-subtle text-center space-y-1">
              <p className="text-xs text-content-muted inline-flex items-center gap-1.5 justify-center">
                <ExternalLink className="h-3 w-3" />
                {t('dashboard.onboarding.redirectNotice')}
              </p>
              <p className="text-xs text-content-muted">{t('dashboard.onboarding.quickRegistration')}</p>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog — Formulário API */}
      <Dialog open={dialogStep === 'api-form'} onOpenChange={(o) => !o && setDialogStep(null)}>
        <DialogContent className="max-w-sm bg-surface-overlay border border-edge-default rounded-2xl shadow-xl p-0 max-h-[90vh] overflow-y-auto">
          <div className="p-7 space-y-6">
            <DialogHeader className="space-y-4">
              <div className="w-11 h-11 rounded-xl bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center">
                <Shield className="h-5 w-5 text-brand-primary" />
              </div>
              <div>
                <DialogTitle className="font-display font-bold text-xl text-content-primary leading-snug">
                  {t('dashboard.onboarding.connectTitle')}
                </DialogTitle>
                <DialogDescription className="text-sm text-content-secondary mt-1.5 leading-relaxed">
                  {t('dashboard.onboarding.connectDesc')}
                </DialogDescription>
              </div>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-semantic-loss/8 border border-semantic-loss/25">
                  <AlertCircle className="h-4 w-4 text-semantic-loss flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-semantic-loss leading-snug">{error}</p>
                </div>
              )}

              {[
                { label: 'API Key',        icon: Key,  name: 'api_key',        type: 'text',     ph: '5c20aeda4f27f10001abc1a4' },
                { label: 'API Secret',     icon: Lock, name: 'api_secret',     type: 'password', ph: t('dashboard.onboarding.apiSecretPh') },
                { label: 'API Passphrase', icon: Lock, name: 'api_passphrase', type: 'password', ph: t('dashboard.onboarding.passphrasePh') },
              ].map(({ label, icon: Icon, name, type, ph }) => (
                <div key={name} className="space-y-1.5">
                  <label className="text-[11px] font-semibold text-content-secondary uppercase tracking-widest flex items-center gap-1.5">
                    <Icon className="h-3 w-3" />
                    {label}
                  </label>
                  <input
                    type={type}
                    name={name}
                    value={formData[name as keyof typeof formData]}
                    onChange={handleFormChange}
                    placeholder={ph}
                    required
                    className="w-full px-3.5 py-2.5 bg-surface-hover border border-edge-default rounded-xl text-sm text-content-primary placeholder:text-content-muted font-mono focus:outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/15 transition-all duration-150"
                  />
                </div>
              ))}

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-3.5 px-4 bg-brand-primary hover:bg-brand-primary/90 active:bg-brand-primary/80 disabled:opacity-50 disabled:cursor-not-allowed text-surface-base font-semibold text-sm rounded-xl transition-colors duration-150 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t('dashboard.onboarding.connecting')}
                  </>
                ) : (
                  t('dashboard.onboarding.connectButton')
                )}
              </button>
            </form>

            <div className="pt-4 border-t border-edge-subtle text-center space-y-2">
              <p className="text-xs text-content-muted inline-flex items-center gap-1.5 justify-center">
                <Lock className="h-3 w-3" />
                {t('dashboard.onboarding.dataEncrypted')}
              </p>
              <a
                href="https://www.kucoin.com/support/360017058491"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-brand-primary hover:text-brand-primary/80 transition-colors inline-flex items-center gap-1"
              >
                {t('dashboard.onboarding.needHelp')}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}