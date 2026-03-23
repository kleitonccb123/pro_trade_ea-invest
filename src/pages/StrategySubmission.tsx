import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, AlertCircle, Code, Send, Loader, ArrowLeft, Clock, User, Shield } from 'lucide-react';

interface SubmissionResponse {
  success: boolean;
  message: string;
  strategyId?: string;
  expiresAt?: string;
}

export function StrategySubmission() {
  const navigate = useNavigate();
  const [authorName, setAuthorName] = useState('');
  const [email, setEmail] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [strategyName, setStrategyName] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [validationStatus, setValidationStatus] = useState<'idle' | 'validating' | 'valid' | 'invalid'>('idle');
  const [validationError, setValidationError] = useState('');
  const [response, setResponse] = useState<SubmissionResponse | null>(null);

  const validateCode = async () => {
    if (!code.trim()) {
      setValidationStatus('invalid');
      setValidationError('Código não pode estar vazio');
      return;
    }

    setValidationStatus('validating');
    setValidationError('');

    try {
      const res = await fetch('http://localhost:8000/api/strategies/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });

      const data = await res.json();

      if (data.valid) {
        setValidationStatus('valid');
      } else {
        setValidationStatus('invalid');
        setValidationError(data.error || 'Código inválido');
      }
    } catch (error) {
      setValidationStatus('invalid');
      setValidationError('Erro ao validar código');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (validationStatus !== 'valid') {
      setValidationError('Por favor, valide o código primeiro');
      return;
    }

    if (!authorName.trim() || !strategyName.trim() || !email.trim() || !whatsapp.trim()) {
      setValidationError('Nome do autor, email, WhatsApp e nome da estratégia são obrigatórios');
      return;
    }

    setLoading(true);
    setResponse(null);

    try {
      const res = await fetch('http://localhost:8000/api/strategies/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          authorName,
          email,
          whatsapp,
          strategyName,
          code,
        }),
      });

      const data = await res.json();
      setResponse(data);

      if (data.success) {
        setAuthorName('');
        setEmail('');
        setWhatsapp('');
        setStrategyName('');
        setCode('');
        setValidationStatus('idle');
      }
    } catch (error) {
      setResponse({
        success: false,
        message: 'Erro ao enviar estratégia',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full">
      {/* Header */}
      <div className="mb-6 pb-6 border-b border-slate-700/50">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/strategies')}
            className="p-2 rounded-lg border border-slate-700 text-slate-400 hover:text-emerald-400 hover:border-emerald-500/50 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 via-emerald-300 to-teal-400 bg-clip-text text-transparent mb-1">
              Enviar Estratégia
            </h1>
            <p className="text-slate-400 text-sm">
              Submeta seu código Python para a comunidade. Válido por 50 dias.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Form */}
        <div className="lg:col-span-2">
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-6">
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Author Name */}
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-300">
                  Nome do Autor <span className="text-emerald-400">*</span>
                </label>
                <input
                  type="text"
                  value={authorName}
                  onChange={(e) => setAuthorName(e.target.value)}
                  placeholder="Seu nome completo"
                  className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 transition-all text-sm"
                  disabled={loading}
                />
              </div>

              {/* Grid: Email + WhatsApp */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-300">
                    Email <span className="text-emerald-400">*</span>
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="seu@email.com"
                    className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 transition-all text-sm"
                    disabled={loading}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-300">
                    WhatsApp <span className="text-emerald-400">*</span>
                  </label>
                  <input
                    type="tel"
                    value={whatsapp}
                    onChange={(e) => setWhatsapp(e.target.value)}
                    placeholder="+55 11 98765-4321"
                    className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 transition-all text-sm"
                    disabled={loading}
                  />
                </div>
              </div>

              {/* Strategy Name */}
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-300">
                  Nome da Estratégia <span className="text-emerald-400">*</span>
                </label>
                <input
                  type="text"
                  value={strategyName}
                  onChange={(e) => setStrategyName(e.target.value)}
                  placeholder="Ex: Scalper de Alta Volatilidade"
                  className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 transition-all text-sm"
                  disabled={loading}
                />
              </div>

              {/* Code Editor */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                    <Code className="w-4 h-4 text-emerald-400" />
                    Código Python <span className="text-emerald-400">*</span>
                  </label>
                  <button
                    type="button"
                    onClick={validateCode}
                    disabled={!code.trim() || validationStatus === 'validating' || loading}
                    className="text-xs px-3 py-1.5 bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 rounded-lg hover:bg-emerald-600/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed font-semibold"
                  >
                    {validationStatus === 'validating' ? (
                      <span className="flex items-center gap-1">
                        <Loader className="w-3 h-3 animate-spin" /> Validando...
                      </span>
                    ) : (
                      'Validar Código'
                    )}
                  </button>
                </div>

                <textarea
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder={`# Exemplo de estratégia\ndef calculate_signal(price, volume):\n    if volume > average_volume:\n        return 'BUY'\n    return 'SELL'`}
                  rows={10}
                  className="w-full px-4 py-3 bg-slate-900/80 border border-slate-600/50 rounded-lg text-emerald-300 placeholder-slate-600 font-mono text-xs focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/20 transition-all resize-none"
                  disabled={loading}
                />

                {/* Validation Status */}
                {validationStatus !== 'idle' && (
                  <div className={`flex items-center gap-3 p-3 rounded-lg border text-sm ${
                    validationStatus === 'valid'
                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                      : validationStatus === 'invalid'
                        ? 'bg-red-950/40 border-red-500/40 text-red-300'
                        : 'bg-slate-800/60 border-slate-600/40 text-slate-300'
                  }`}>
                    {validationStatus === 'valid' ? (
                      <><CheckCircle className="w-4 h-4 flex-shrink-0" /><span className="font-semibold">Código validado com sucesso!</span></>
                    ) : validationStatus === 'invalid' ? (
                      <><AlertCircle className="w-4 h-4 flex-shrink-0" /><span className="font-semibold">{validationError}</span></>
                    ) : (
                      <><Loader className="w-4 h-4 flex-shrink-0 animate-spin" /><span>Validando código...</span></>
                    )}
                  </div>
                )}
              </div>

              {/* Error */}
              {validationError && validationStatus !== 'invalid' && (
                <div className="flex items-center gap-2 p-3 bg-red-950/30 border border-red-500/40 rounded-lg text-red-300 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {validationError}
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={loading || validationStatus !== 'valid'}
                className="w-full py-3 px-6 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:from-slate-700 disabled:to-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
              >
                {loading ? (
                  <><Loader className="w-4 h-4 animate-spin" /><span>Enviando...</span></>
                ) : (
                  <><Send className="w-4 h-4" /><span>Enviar Estratégia</span></>
                )}
              </button>

              {/* Response */}
              {response && (
                <div className={`p-4 rounded-lg border flex items-start gap-3 ${
                  response.success
                    ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
                    : 'bg-red-950/30 border-red-500/40 text-red-300'
                }`}>
                  {response.success
                    ? <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    : <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  }
                  <div>
                    <p className="font-semibold text-sm">{response.message}</p>
                    {response.success && response.expiresAt && (
                      <p className="text-xs mt-1 opacity-80">
                        Válida até: {new Date(response.expiresAt).toLocaleDateString('pt-BR')}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </form>
          </div>
        </div>

        {/* Sidebar Info */}
        <div className="space-y-4">
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-emerald-500/10 rounded-lg">
                <CheckCircle className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-slate-200">Validação</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Seu código Python será validado automaticamente antes do envio. Certifique-se de que é executável e segue a estrutura esperada.
            </p>
          </div>

          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-teal-500/10 rounded-lg">
                <Clock className="w-5 h-5 text-teal-400" />
              </div>
              <h3 className="font-semibold text-slate-200">Duração</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Sua estratégia fica disponível por <span className="text-teal-300 font-medium">50 dias</span>. Após esse período é automaticamente removida.
            </p>
          </div>

          <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-slate-600/30 rounded-lg">
                <User className="w-5 h-5 text-slate-300" />
              </div>
              <h3 className="font-semibold text-slate-200">Identificação</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Seu nome será vinculado à estratégia na plataforma. Seja criativo e profissional na escolha do nome.
            </p>
          </div>

          <div className="bg-emerald-900/10 border border-emerald-600/20 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 bg-emerald-500/10 rounded-lg">
                <Shield className="w-5 h-5 text-emerald-400" />
              </div>
              <h3 className="font-semibold text-emerald-300">Boas práticas</h3>
            </div>
            <ul className="text-xs text-slate-400 space-y-1.5">
              <li className="flex items-start gap-1.5"><span className="text-emerald-400 mt-0.5">✓</span> Use nomes de função claros</li>
              <li className="flex items-start gap-1.5"><span className="text-emerald-400 mt-0.5">✓</span> Adicione comentários explicativos</li>
              <li className="flex items-start gap-1.5"><span className="text-emerald-400 mt-0.5">✓</span> Teste antes de enviar</li>
              <li className="flex items-start gap-1.5"><span className="text-red-400 mt-0.5">✗</span> Não inclua credenciais</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
