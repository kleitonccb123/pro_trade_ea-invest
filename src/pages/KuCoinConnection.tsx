import React, { useState, useEffect } from 'react';
import {
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  Unlink,
  Key,
  Lock,
  ShieldCheck,
  Wallet,
  ExternalLink,
} from 'lucide-react';
import { authService } from '@/services/authService';

interface KuCoinFormData {
  api_key: string;
  api_secret: string;
  api_passphrase: string;
  is_sandbox: boolean;
}

interface ConnectionStatus {
  connected: boolean;
  status?: string;
  error?: string;
}

const KuCoinConnectionForm: React.FC = () => {
  const [formData, setFormData] = useState<KuCoinFormData>({
    api_key: '',
    api_secret: '',
    api_passphrase: '',
    is_sandbox: false,
  });

  const [showSecrets, setShowSecrets] = useState({
    api_secret: false,
    api_passphrase: false,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => { checkConnection(); }, []);

  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(false), 4000);
      return () => clearTimeout(t);
    }
  }, [success]);

  const checkConnection = async () => {
    try {
      const token = authService.getAccessToken();
      if (!token) return;
      const res = await fetch('http://localhost:8000/api/trading/kucoin/status', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        setIsConnected(data.connected);
      }
    } catch { /* silent */ }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const validateForm = (): boolean => {
    if (formData.api_key.length < 10) { setError('API Key deve ter pelo menos 10 caracteres'); return false; }
    if (formData.api_secret.length < 20) { setError('API Secret deve ter pelo menos 20 caracteres'); return false; }
    if (formData.api_passphrase.length < 6) { setError('Passphrase deve ter pelo menos 6 caracteres'); return false; }
    return true;
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validateForm()) return;
    setLoading(true);
    try {
      const token = authService.getAccessToken();
      if (!token) throw new Error('Não autenticado');
      const res = await fetch(`${API_BASE_URL}/kucoin/connect/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Erro ao conectar');
      }
      setSuccess(true);
      setFormData({ api_key: '', api_secret: '', api_passphrase: '', is_sandbox: false });
      await checkConnection();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao conectar KuCoin');
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('Tem certeza que deseja desconectar a KuCoin?')) return;
    setLoading(true);
    try {
      const token = authService.getAccessToken();
      if (!token) throw new Error('Não autenticado');
      const res = await fetch('http://localhost:8000/api/trading/kucoin/disconnect', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Erro ao desconectar');
      setSuccess(true);
      setIsConnected(false);
      await checkConnection();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao desconectar');
    } finally {
      setLoading(false);
    }
  };

  /* ── Input component ── */
  const FieldInput = ({
    name, label, placeholder, hint, icon: Icon, isPassword = false, passwordKey,
  }: {
    name: keyof KuCoinFormData; label: string; placeholder: string; hint: string;
    icon: React.ElementType; isPassword?: boolean; passwordKey?: 'api_secret' | 'api_passphrase';
  }) => (
    <div className="space-y-1.5">
      <label className="flex items-center gap-2 text-sm font-semibold text-white">
        <Icon className="w-3.5 h-3.5 text-emerald-400" />
        {label}
      </label>
      <div className="relative">
        <input
          type={isPassword && passwordKey && !showSecrets[passwordKey] ? 'password' : 'text'}
          name={name}
          value={formData[name] as string}
          onChange={handleInputChange}
          placeholder={placeholder}
          disabled={loading}
          required
          className="w-full px-4 py-3 pr-10 rounded-xl text-sm text-white placeholder-slate-500 outline-none transition-all"
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
          onFocus={e => { e.currentTarget.style.borderColor = 'rgba(35,200,130,0.5)'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(35,200,130,0.08)'; }}
          onBlur={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; e.currentTarget.style.boxShadow = 'none'; }}
        />
        {isPassword && passwordKey && (
          <button
            type="button"
            onClick={() => setShowSecrets(prev => ({ ...prev, [passwordKey]: !prev[passwordKey] }))}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
            tabIndex={-1}
          >
            {showSecrets[passwordKey] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
      <p className="text-xs text-slate-500 pl-1">{hint}</p>
    </div>
  );

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2.5 rounded-xl" style={{ background: 'rgba(35,200,130,0.1)', border: '1px solid rgba(35,200,130,0.2)' }}>
          <Wallet className="w-5 h-5 text-emerald-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Conectar KuCoin</h1>
          <p className="text-slate-400 text-sm">Configure suas credenciais de API para acesso à conta</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Main Form / Connected State ── */}
        <div className="lg:col-span-2">
          {isConnected ? (
            /* ── Connected card ── */
            <div className="rounded-2xl p-8 text-center"
              style={{ background: 'rgba(35,200,130,0.06)', border: '1px solid rgba(35,200,130,0.2)' }}>
              <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                style={{ background: 'rgba(35,200,130,0.12)', border: '2px solid rgba(35,200,130,0.3)' }}>
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
              </div>
              <h2 className="text-xl font-bold text-white mb-1">KuCoin Conectada</h2>
              <p className="text-emerald-400 text-sm mb-6">Suas credenciais estão ativas e encriptadas</p>

              {error && (
                <div className="flex items-center gap-2 p-3 mb-4 rounded-xl bg-red-900/20 border border-red-500/30 text-red-300 text-sm text-left">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {error}
                </div>
              )}

              <button
                onClick={handleDisconnect}
                disabled={loading}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-red-400 border border-red-500/30 rounded-xl bg-red-500/10 hover:bg-red-500/20 transition-all disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Unlink className="w-4 h-4" />}
                Desconectar KuCoin
              </button>
            </div>
          ) : (
            /* ── Form ── */
            <form onSubmit={handleConnect} className="rounded-2xl p-6 space-y-5"
              style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)' }}>

              {/* Error / Success */}
              {error && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-red-900/20 border border-red-500/30 text-red-300 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {error}
                </div>
              )}
              {success && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-900/20 border border-emerald-500/30 text-emerald-300 text-sm">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  Conectado com sucesso!
                </div>
              )}

              <FieldInput
                name="api_key" icon={Key}
                label="API Key"
                placeholder="Sua chave de API da KuCoin"
                hint="Mínimo 10 caracteres"
              />

              <FieldInput
                name="api_secret" icon={Lock}
                label="API Secret"
                placeholder="Sua chave secreta"
                hint="Mínimo 20 caracteres — encriptado com AES-256"
                isPassword passwordKey="api_secret"
              />

              <FieldInput
                name="api_passphrase" icon={ShieldCheck}
                label="API Passphrase"
                placeholder="Sua passphrase KuCoin"
                hint="Senha adicional criada no painel KuCoin — mínimo 6 caracteres"
                isPassword passwordKey="api_passphrase"
              />

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 text-sm font-bold text-white rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  background: loading ? 'rgba(35,200,130,0.4)' : 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)',
                  boxShadow: loading ? 'none' : '0 4px 20px rgba(35,200,130,0.3)',
                }}
              >
                {loading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Conectando...</>
                ) : (
                  <><CheckCircle2 className="w-4 h-4" /> Conectar KuCoin</>
                )}
              </button>

              <p className="text-xs text-slate-500 text-center">
                Credenciais encriptadas com Fernet (AES-256). Nunca armazenadas em texto plano.
              </p>
            </form>
          )}
        </div>

        {/* ── Sidebar info ── */}
        <div className="space-y-4">
          {/* How to get API keys */}
          <div className="rounded-2xl p-5 space-y-3"
            style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)' }}>
            <h3 className="text-sm font-semibold text-white">Como obter sua API Key</h3>
            <ol className="space-y-2 text-xs text-slate-400">
              <li className="flex gap-2"><span className="text-emerald-400 font-bold flex-shrink-0">1.</span>Acesse sua conta KuCoin</li>
              <li className="flex gap-2"><span className="text-emerald-400 font-bold flex-shrink-0">2.</span>Vá em Perfil → Gerenciamento de API</li>
              <li className="flex gap-2"><span className="text-emerald-400 font-bold flex-shrink-0">3.</span>Crie uma API Key com permissão de <strong className="text-slate-300">Leitura Geral</strong></li>
              <li className="flex gap-2"><span className="text-emerald-400 font-bold flex-shrink-0">4.</span>Defina sua Passphrase e copie o Secret</li>
            </ol>
            <a
              href="https://www.kucoin.com/account/api"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors mt-1"
            >
              <ExternalLink className="w-3 h-3" />
              Abrir gerenciamento de API
            </a>
          </div>

          {/* Permissions */}
          <div className="rounded-2xl p-5 space-y-3"
            style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)' }}>
            <h3 className="text-sm font-semibold text-white">Permissões necessárias</h3>
            <ul className="space-y-2 text-xs text-slate-400">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                Leitura Geral (obrigatório)
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-600 flex-shrink-0" />
                <span className="line-through opacity-50">Trading — não necessário</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500/60 flex-shrink-0" />
                <span className="opacity-70">Saque — nunca ative</span>
              </li>
            </ul>
          </div>

          {/* Security note */}
          <div className="rounded-2xl p-4"
            style={{ background: 'rgba(35,200,130,0.04)', border: '1px solid rgba(35,200,130,0.12)' }}>
            <p className="text-xs text-slate-400 leading-relaxed">
              Esta plataforma é <strong className="text-slate-300">somente leitura</strong>. Nenhuma ordem é executada aqui — toda operação ocorre diretamente na KuCoin.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KuCoinConnectionForm;
