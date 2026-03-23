import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { 
  Mail, Lock, Loader, Eye, EyeOff, ArrowRight, Shield, 
  Zap, TrendingUp, ChevronRight, Sparkles, CheckCircle2, XCircle
} from 'lucide-react';
import { useAuthStore } from '../context/AuthContext';
import { useLanguage } from '@/hooks/use-language';
import { RetroGrid } from '@/components/ui/retro-grid';

export default function Login() {
  const navigate = useNavigate();
  const { login, googleLogin, isLoading, error: authError, clearError } = useAuthStore();
  const { t } = useLanguage();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailValid, setEmailValid] = useState<boolean | null>(null);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [loginSuccess, setLoginSuccess] = useState(false);
  const [showEmailSuggestions, setShowEmailSuggestions] = useState(false);
  const [emailHistory, setEmailHistory] = useState<string[]>([]);

  // Carregar histórico de emails ao montar o componente
  useEffect(() => {
    const savedEmails = localStorage.getItem('tradehub_email_history');
    if (savedEmails) {
      try {
        setEmailHistory(JSON.parse(savedEmails));
      } catch {
        setEmailHistory([]);
      }
    }
  }, []);

  // Carregar email salvo ao montar o componente
  useEffect(() => {
    const savedEmail = localStorage.getItem('tradehub_saved_email');
    const wasRemembered = localStorage.getItem('tradehub_remember_me');
    if (savedEmail && wasRemembered === 'true') {
      setEmail(savedEmail);
      setRememberMe(true);
      validateEmail(savedEmail);
    }
  }, []);

  // Limpar erro ao digitar
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const validateEmail = (value: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    setEmailValid(value.length > 0 ? emailRegex.test(value) : null);
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEmail(value);
    validateEmail(value);
    if (error) setError('');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    clearError?.();

    try {
      await login(email, password);
      
      // Salvar email no histórico
      const updatedHistory = [email, ...emailHistory.filter(e => e !== email)].slice(0, 5);
      localStorage.setItem('tradehub_email_history', JSON.stringify(updatedHistory));
      
      // Salvar email se "Lembrar-me" estiver marcado
      if (rememberMe) {
        localStorage.setItem('tradehub_saved_email', email);
        localStorage.setItem('tradehub_remember_me', 'true');
      } else {
        localStorage.removeItem('tradehub_saved_email');
        localStorage.setItem('tradehub_remember_me', 'false');
      }
      
      setLoginSuccess(true);
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch (err: any) {
      // Handle 2FA redirect
      if (err.requires2FA) {
        navigate('/2fa-verify', { state: { tempToken: err.pendingToken, email } });
        return;
      }
      setError(err.message || t('login.errorLogin'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleError = (error: any) => {
    console.error('[GoogleLogin] ❌ Erro do Google:', error);
    
    // Capturar diferentes tipos de erros
    let errorMsg = 'Erro ao fazer login com Google';
    
    if (error?.error === 'invalid_client') {
      errorMsg = 'Cliente não configurado corretamente. Contate o suporte.';
      console.error('[GoogleLogin] 💡 DICA: Verificar Client ID no console do Google Cloud');
    } else if (error?.error === 'popup_closed_by_user') {
      errorMsg = 'Login cancelado pelo usuário';
    } else if (error?.error === 'network_error') {
      errorMsg = 'Erro de conexão. Verifique sua internet.';
    } else if (error?.message) {
      errorMsg = error.message;
    }
    
    setError(errorMsg);
    console.error('[GoogleLogin] Mensagem final:', errorMsg);
  };

  const handleGoogleSuccess = async (credentialResponse: any) => {
    setError('');
    setIsSubmitting(true);
    
    console.log('[GoogleLogin] ✓ Resposta recebida do Google');

    try {
      // Decodificar o JWT do Google (sem validar assinatura no frontend)
      console.log('[GoogleLogin] Decodificando JWT...');
      const base64Url = credentialResponse.credential.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      
      const payload = JSON.parse(jsonPayload);
      console.log('[GoogleLogin] ✓ JWT Decodificado:', {
        email: payload.email,
        name: payload.name,
        sub: payload.sub?.substring(0, 10) + '...'
      });
      
      console.log('[GoogleLogin] Enviando para backend...');
      await googleLogin(
        credentialResponse.credential,
        payload.email,
        payload.name
      );
      
      console.log('[GoogleLogin] ✅ Login bem-sucedido!');
      setLoginSuccess(true);
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch (err: any) {
      const errorMsg = err.message || 'Erro ao fazer login com Google';
      console.error('[GoogleLogin] ❌ Erro:', errorMsg);
      setError(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loginSuccess) {
    return (
      <div className="min-h-screen bg-surface-base flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-6 rounded-xl bg-semantic-profit/10 flex items-center justify-center">
            <CheckCircle2 className="w-8 h-8 text-semantic-profit" />
          </div>
          <h2 className="font-display text-xl font-semibold text-content-primary mb-2">{t('login.loginSuccess')}</h2>
          <p className="text-sm text-content-secondary">{t('login.redirecting')}</p>
          <div className="mt-6">
            <Loader className="w-5 h-5 text-brand-primary animate-spin mx-auto" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-base flex">

      {/* Left Side — Branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center px-16 xl:px-24 border-r border-edge-subtle relative overflow-hidden">
        <RetroGrid angle={65} />
        <div className="relative z-10 space-y-10">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md bg-brand-primary flex items-center justify-center">
              <Zap className="w-5 h-5 text-surface-base" />
            </div>
            <div>
              <h1 className="font-display font-bold text-xl text-content-primary">TradeHub</h1>
              <p className="text-xs text-content-muted">{t('login.tradingAutomated')}</p>
            </div>
          </div>

          {/* Tagline */}
          <div className="space-y-3">
            <h2 className="font-display font-bold text-4xl text-content-primary leading-tight tracking-tight">
              {t('login.tagline').split('\n').map((line: string, i: number) => <span key={i}>{line}<br /></span>)}
            </h2>
            <p className="text-base text-content-secondary leading-relaxed max-w-sm">
              {t('login.taglineDesc')}
            </p>
          </div>

          {/* Features */}
          <div className="space-y-3">
            {[
              { icon: TrendingUp, text: t('login.feature1'), color: 'text-semantic-profit' },
              { icon: Shield,     text: t('login.feature2'),    color: 'text-brand-primary' },
              { icon: Sparkles,   text: t('login.feature3'), color: 'text-content-secondary' },
            ].map((feature, index) => (
              <div key={index} className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-md bg-surface-hover border border-edge-subtle flex items-center justify-center flex-shrink-0">
                  <feature.icon className={`w-4 h-4 ${feature.color}`} />
                </div>
                <span className="text-sm text-content-body">{feature.text}</span>
              </div>
            ))}
          </div>

          {/* Stats */}
          <div className="flex gap-8 pt-6 border-t border-edge-subtle">
            {[
              { value: '10K+',  label: t('login.tradersActive') },
              { value: '$50M+', label: t('login.monthlyVolume') },
              { value: '99.9%', label: t('login.uptime') },
            ].map((stat, index) => (
              <div key={index}>
                <div className="font-mono font-semibold text-2xl text-content-primary tabular-nums">{stat.value}</div>
                <div className="text-xs text-content-muted mt-0.5">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Side — Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-sm space-y-6">
          {/* Mobile Header */}
          <div className="lg:hidden flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-md bg-brand-primary flex items-center justify-center">
              <Zap className="w-4 h-4 text-surface-base" />
            </div>
            <h1 className="font-display font-bold text-lg text-content-primary">TradeHub</h1>
          </div>

          {/* Form Header */}
          <div>
            <h2 className="font-display font-semibold text-2xl text-content-primary">{t('login.title')}</h2>
            <p className="text-sm text-content-secondary mt-1">{t('login.subtitle')}</p>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-4">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-content-secondary uppercase tracking-widest flex items-center gap-2">
                <Mail className="w-3.5 h-3.5" />
                {t('login.email')}
              </label>
              <div className="relative">
                <input
                  type="email"
                  value={email}
                  onChange={handleEmailChange}
                  onFocus={() => { setFocusedField('email'); setShowEmailSuggestions(true); }}
                  onBlur={() => { setFocusedField(null); setTimeout(() => setShowEmailSuggestions(false), 200); }}
                  placeholder={t('login.emailPlaceholder')}
                  className={`w-full px-3.5 py-3 bg-surface-hover border rounded-lg text-sm text-content-primary placeholder:text-content-muted focus:outline-none transition-all duration-150 ${
                    focusedField === 'email'
                      ? 'border-brand-primary ring-2 ring-brand-primary/15'
                      : emailValid === false
                        ? 'border-semantic-loss/50'
                        : emailValid === true
                          ? 'border-semantic-profit/50'
                          : 'border-edge-default'
                  }`}
                  disabled={isSubmitting}
                  required
                />
                {emailValid !== null && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {emailValid
                      ? <CheckCircle2 className="w-4 h-4 text-semantic-profit" />
                      : <XCircle className="w-4 h-4 text-semantic-loss" />
                    }
                  </div>
                )}
                {showEmailSuggestions && !email && emailHistory.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-surface-overlay border border-edge-subtle rounded-lg overflow-hidden z-10">
                    {emailHistory.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => { setEmail(suggestion); validateEmail(suggestion); setShowEmailSuggestions(false); }}
                        className="w-full px-3.5 py-2.5 text-left text-sm text-content-body hover:bg-surface-hover transition-colors flex items-center gap-2 border-b border-edge-subtle last:border-0"
                      >
                        <Mail className="w-3.5 h-3.5 text-content-muted flex-shrink-0" />
                        <span className="truncate">{suggestion}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-content-secondary uppercase tracking-widest flex items-center gap-2">
                  <Lock className="w-3.5 h-3.5" />
                  {t('login.password')}
                </label>
                <Link to="/forgot-password" className="text-xs text-brand-primary hover:text-brand-primary/80 transition-colors">
                  {t('login.forgotPassword')}
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); if (error) setError(''); }}
                  onFocus={() => setFocusedField('password')}
                  onBlur={() => setFocusedField(null)}
                  placeholder="••••••••"
                  className={`w-full px-3.5 py-3 pr-10 bg-surface-hover border rounded-lg text-sm text-content-primary placeholder:text-content-muted focus:outline-none transition-all duration-150 ${
                    focusedField === 'password'
                      ? 'border-brand-primary ring-2 ring-brand-primary/15'
                      : 'border-edge-default'
                  }`}
                  disabled={isSubmitting}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-content-muted hover:text-content-secondary transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Error */}
            {(error || authError) && (
              <div className="flex items-start gap-2.5 p-3 rounded-lg bg-semantic-loss/8 border border-semantic-loss/25">
                <XCircle className="w-4 h-4 text-semantic-loss flex-shrink-0 mt-0.5" />
                <span className="text-sm text-semantic-loss">{error || authError}</span>
              </div>
            )}

            {/* Remember Me */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-edge-default bg-surface-hover text-brand-primary focus:ring-brand-primary/30 cursor-pointer"
              />
              <span className="text-sm text-content-secondary">{t('login.rememberMe')}</span>
            </label>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting || isLoading || !emailValid}
              className="w-full py-3 px-4 bg-brand-primary hover:bg-brand-primary/90 disabled:bg-surface-active disabled:cursor-not-allowed text-surface-base font-semibold rounded-lg text-sm transition-all duration-150 flex items-center justify-center gap-2 group"
            >
              {isSubmitting || isLoading ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" />
                  <span>{t('login.loggingIn')}</span>
                </>
              ) : (
                <>
                  <span>{t('login.loginButton')}</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-edge-subtle" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-surface-base text-content-muted">{t('common.continueWith')}</span>
            </div>
          </div>

          {/* Google */}
          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              text="signin_with"
              shape="pill"
              theme="filled_black"
              size="large"
              width={320}
            />
          </div>

          {/* Sign Up */}
          <p className="text-center text-sm text-content-secondary">
            {t('login.noAccount')}{' '}
            <Link to="/signup" className="text-brand-primary hover:text-brand-primary/80 font-medium transition-colors inline-flex items-center gap-1">
              {t('login.signupLink')}
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </p>

          {/* Footer */}
          <p className="text-center text-xs text-content-muted">
            {t('login.termsText')}{' '}
            <Link to="/terms" className="text-content-secondary hover:text-content-primary transition-colors">
              {t('login.termsOfUse')}
            </Link>{' '}
            {t('login.and')}{' '}
            <Link to="/privacy" className="text-content-secondary hover:text-content-primary transition-colors">
              {t('login.privacy')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

