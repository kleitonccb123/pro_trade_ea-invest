/**
 * ForgotPassword — Recuperação de senha em 3 passos:
 *   1. Informar e-mail → recebe código OTP por email
 *   2. Confirmar código OTP de 6 dígitos
 *   3. Definir nova senha
 */

import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLanguage } from '@/hooks/use-language';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';

const API = (path: string) =>
  `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}${path}`;

async function apiPost(path: string, body: object) {
  const res = await fetch(API(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? 'Unknown error');
  return data;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-componente: input de OTP (6 caixinhas)
// ─────────────────────────────────────────────────────────────────────────────

function OTPInput({
  value,
  onChange,
  disabled,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  disabled?: boolean;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  const handleKey = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !value[i] && i > 0) {
      refs.current[i - 1]?.focus();
    }
  };

  const handleChange = (i: number, raw: string) => {
    const digit = raw.replace(/\D/g, '').slice(-1);
    const next = [...value];
    next[i] = digit;
    onChange(next);
    if (digit && i < 5) refs.current[i + 1]?.focus();
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!text) return;
    e.preventDefault();
    const next = [...value];
    text.split('').forEach((c, i) => { if (i < 6) next[i] = c; });
    onChange(next);
    const last = Math.min(text.length, 5);
    refs.current[last]?.focus();
  };

  return (
    <div className="flex justify-center gap-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={value[i] ?? ''}
          disabled={disabled}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKey(i, e)}
          onPaste={handlePaste}
          onFocus={(e) => e.target.select()}
          className={`w-12 h-14 text-center text-xl font-bold rounded-xl border-2 outline-none
            bg-slate-800/80 text-emerald-300 caret-emerald-400
            transition-all duration-150
            ${value[i] ? 'border-emerald-500 shadow-[0_0_12px_rgba(35,200,130,.35)]' : 'border-slate-600'}
            focus:border-emerald-400 focus:shadow-[0_0_14px_rgba(35,200,130,.4)]
            disabled:opacity-40 disabled:cursor-not-allowed`}
        />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────────────────────

type Step = 1 | 2 | 3 | 4; // 4 = sucesso

export default function ForgotPassword() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [step, setStep] = useState<Step>(1);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState<string[]>(Array(6).fill(''));
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [googleAccount, setGoogleAccount] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  const clearError = () => setError('');

  // ── Passo 1: solicitar OTP ─────────────────────────────────────────────────
  const handleRequestOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    if (!email.trim()) return setError(t('forgotPassword.errorEmailRequired'));

    setLoading(true);
    try {
      const res = await apiPost('/api/auth/forgot-password', { email });
      if (res.google_account) {
        setGoogleAccount(true);
        setError(res.message);
      } else {
        setStep(2);
        startCooldown();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('forgotPassword.errorSendCode'));
    } finally {
      setLoading(false);
    }
  };

  // ── Passo 2: verificar OTP ─────────────────────────────────────────────────
  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    const code = otp.join('');
    if (code.length < 6) return setError(t('forgotPassword.errorDigits'));

    setLoading(true);
    try {
      await apiPost('/api/auth/verify-otp', { email, otp: code });
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('forgotPassword.errorInvalidCode'));
    } finally {
      setLoading(false);
    }
  };

  // ── Passo 3: nova senha ────────────────────────────────────────────────────
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    if (newPassword.length < 6) return setError(t('forgotPassword.errorMinLength'));
    if (newPassword !== confirmPassword) return setError(t('forgotPassword.errorNoMatch'));

    setLoading(true);
    try {
      await apiPost('/api/auth/reset-password', {
        email,
        otp: otp.join(''),
        new_password: newPassword,
      });
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('forgotPassword.errorReset'));
    } finally {
      setLoading(false);
    }
  };

  // ── Reenviar OTP ───────────────────────────────────────────────────────────
  const startCooldown = () => {
    setResendCooldown(60);
    const id = setInterval(() => {
      setResendCooldown((c) => {
        if (c <= 1) { clearInterval(id); return 0; }
        return c - 1;
      });
    }, 1000);
  };

  const handleResend = async () => {
    if (resendCooldown > 0) return;
    clearError();
    setLoading(true);
    try {
      await apiPost('/api/auth/forgot-password', { email });
      setOtp(Array(6).fill(''));
      startCooldown();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('forgotPassword.errorResend'));
    } finally {
      setLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0a0f1e] flex items-center justify-center px-4">
      {/* Background glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-emerald-600/8 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Card */}
        <div className="rounded-2xl border border-white/10 bg-[#111827]/90 backdrop-blur-xl shadow-2xl p-8">

          {/* ── Passo 1: e-mail ─────────────────────────────────────────── */}
          {step === 1 && (
            <>
              <div className="mb-8 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl
                  bg-gradient-to-br from-blue-600/30 to-emerald-600/20 border border-blue-500/30">
                  <KeyRound className="text-emerald-400" size={24} />
                </div>
                <h1 className="text-2xl font-bold text-white">{t('forgotPassword.title')}</h1>
                <p className="mt-2 text-sm text-slate-400">
                  {t('forgotPassword.subtitle')}
                </p>
              </div>

              <form onSubmit={handleRequestOTP} className="space-y-5">
                <div>
                  <label className="mb-1.5 flex items-center gap-2 text-xs font-medium
                    uppercase tracking-widest text-slate-400">
                    <Mail size={12} /> {t('forgotPassword.email')}
                  </label>
                  <input
                    type="email"
                    autoFocus
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); clearError(); setGoogleAccount(false); }}
                    placeholder={t('forgotPassword.emailPlaceholder')}
                    className="w-full rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-3
                      text-sm text-white placeholder:text-slate-500 outline-none
                      focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                  />
                </div>

                {error && (
                  <div className={`rounded-xl border px-4 py-3 text-sm ${
                    googleAccount
                      ? 'border-yellow-500/30 bg-yellow-600/10 text-yellow-300'
                      : 'border-red-500/30 bg-red-600/10 text-red-300'
                  }`}>
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-xl
                    bg-gradient-to-r from-blue-600 to-emerald-600 py-3 text-sm font-semibold
                    text-white transition-all hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
                  {loading ? t('forgotPassword.sending') : t('forgotPassword.sendCode')}
                </button>
              </form>
            </>
          )}

          {/* ── Passo 2: código OTP ──────────────────────────────────────── */}
          {step === 2 && (
            <>
              <div className="mb-8 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl
                  bg-gradient-to-br from-emerald-600/30 to-blue-600/20 border border-emerald-500/30">
                  <ShieldCheck className="text-emerald-400" size={24} />
                </div>
                <h1 className="text-2xl font-bold text-white">{t('forgotPassword.confirmCodeTitle')}</h1>
                <p className="mt-2 text-sm text-slate-400">
                  {t('forgotPassword.codeSentTo')}
                </p>
                <p className="text-sm font-semibold text-emerald-400">{email}</p>
              </div>

              <form onSubmit={handleVerifyOTP} className="space-y-6">
                <OTPInput value={otp} onChange={setOtp} disabled={loading} />

                {error && (
                  <div className="rounded-xl border border-red-500/30 bg-red-600/10 px-4 py-3
                    text-sm text-red-300">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading || otp.join('').length < 6}
                  className="flex w-full items-center justify-center gap-2 rounded-xl
                    bg-gradient-to-r from-cyan-600 to-blue-600 py-3 text-sm font-semibold
                    text-white transition-all hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
                  {loading ? t('forgotPassword.verifying') : t('forgotPassword.confirmCode')}
                </button>

                <div className="text-center text-sm text-slate-500">
                  {t('forgotPassword.didntReceive')}{' '}
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resendCooldown > 0 || loading}
                    className="text-cyan-400 hover:text-cyan-300 transition disabled:opacity-40
                      inline-flex items-center gap-1"
                  >
                    <RefreshCw size={12} />
                    {resendCooldown > 0 ? `${t('forgotPassword.resendIn')} ${resendCooldown}s` : t('forgotPassword.resendCode')}
                  </button>
                </div>
              </form>
            </>
          )}

          {/* ── Passo 3: nova senha ──────────────────────────────────────── */}
          {step === 3 && (
            <>
              <div className="mb-8 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl
                  bg-gradient-to-br from-green-600/30 to-cyan-600/20 border border-green-500/30">
                  <Lock className="text-green-400" size={24} />
                </div>
                <h1 className="text-2xl font-bold text-white">{t('forgotPassword.newPasswordTitle')}</h1>
                <p className="mt-2 text-sm text-slate-400">
                  {t('forgotPassword.newPasswordSubtitle')}
                </p>
              </div>

              <form onSubmit={handleResetPassword} className="space-y-5">
                <div>
                  <label className="mb-1.5 flex items-center gap-2 text-xs font-medium
                    uppercase tracking-widest text-slate-400">
                    <Lock size={12} /> {t('forgotPassword.newPassword')}
                  </label>
                  <div className="relative">
                    <input
                      type={showPass ? 'text' : 'password'}
                      autoFocus
                      value={newPassword}
                      onChange={(e) => { setNewPassword(e.target.value); clearError(); }}
                      placeholder={t('forgotPassword.minChars')}
                      className="w-full rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-3 pr-10
                        text-sm text-white placeholder:text-slate-500 outline-none
                        focus:border-green-500 focus:ring-2 focus:ring-green-500/20 transition-all"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPass((s) => !s)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                    >
                      {showPass ? '🙈' : '👁️'}
                    </button>
                  </div>
                  {/* Barra de força */}
                  {newPassword.length > 0 && (
                    <div className="mt-2 flex gap-1">
                      {[1, 2, 3, 4].map((n) => (
                        <div key={n} className={`h-1 flex-1 rounded-full transition-colors ${
                          newPassword.length >= n * 2
                            ? n <= 2
                              ? 'bg-red-500'
                              : n === 3
                              ? 'bg-yellow-500'
                              : 'bg-green-500'
                            : 'bg-slate-700'
                        }`} />
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <label className="mb-1.5 flex items-center gap-2 text-xs font-medium
                    uppercase tracking-widest text-slate-400">
                    <Lock size={12} /> {t('forgotPassword.confirmPassword')}
                  </label>
                  <input
                    type={showPass ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); clearError(); }}
                    placeholder={t('forgotPassword.repeatPassword')}
                    className={`w-full rounded-xl border bg-slate-800/80 px-4 py-3
                      text-sm text-white placeholder:text-slate-500 outline-none transition-all
                      ${confirmPassword && confirmPassword === newPassword
                        ? 'border-green-500 focus:ring-2 focus:ring-green-500/20'
                        : 'border-slate-700 focus:border-green-500 focus:ring-2 focus:ring-green-500/20'
                      }`}
                  />
                </div>

                {error && (
                  <div className="rounded-xl border border-red-500/30 bg-red-600/10 px-4 py-3
                    text-sm text-red-300">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-xl
                    bg-gradient-to-r from-green-600 to-cyan-600 py-3 text-sm font-semibold
                    text-white transition-all hover:opacity-90 disabled:opacity-50"
                >
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <Lock size={16} />}
                  {loading ? t('forgotPassword.saving') : t('forgotPassword.resetPassword')}
                </button>
              </form>
            </>
          )}

          {/* ── Passo 4: sucesso ─────────────────────────────────────────── */}
          {step === 4 && (
            <div className="py-4 text-center">
              <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-full
                bg-green-600/20 border border-green-500/30">
                <CheckCircle2 className="text-green-400" size={40} />
              </div>
              <h1 className="text-2xl font-bold text-white">{t('forgotPassword.successTitle')}</h1>
              <p className="mt-3 text-sm text-slate-400">
                {t('forgotPassword.successMessage')}
              </p>
              <button
                onClick={() => navigate('/login')}
                className="mt-8 flex w-full items-center justify-center gap-2 rounded-xl
                  bg-gradient-to-r from-blue-600 to-cyan-600 py-3 text-sm font-semibold
                  text-white transition-all hover:opacity-90"
              >
                <ArrowRight size={16} />
                {t('forgotPassword.goToLogin')}
              </button>
            </div>
          )}

          {/* ── Voltar ───────────────────────────────────────────────────── */}
          {step !== 4 && (
            <div className="mt-6 text-center">
              {step === 1 ? (
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-sm text-slate-400
                    hover:text-white transition-colors"
                >
                  <ArrowLeft size={14} />
                  {t('forgotPassword.backToLogin')}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => { setStep((s) => (s - 1) as Step); clearError(); }}
                  className="inline-flex items-center gap-1.5 text-sm text-slate-400
                    hover:text-white transition-colors"
                >
                  <ArrowLeft size={14} />
                  {t('forgotPassword.back')}
                </button>
              )}
            </div>
          )}

          {/* ── Indicador de etapas ──────────────────────────────────────── */}
          {step < 4 && (
            <div className="mt-6 flex justify-center gap-2">
              {[1, 2, 3].map((s) => (
                <div key={s} className={`h-1.5 rounded-full transition-all duration-300 ${
                  s === step
                    ? 'w-8 bg-cyan-400'
                    : s < step
                    ? 'w-4 bg-cyan-600'
                    : 'w-4 bg-slate-700'
                }`} />
              ))}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
