/**
 * Auth Callback Page
 * 
 * Processa o redirect do Google OAuth e salva os tokens
 * This page is loaded after Google redirects back with tokens in URL params
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../context/AuthContext';
import { Loader, CheckCircle2, AlertCircle, Zap } from 'lucide-react';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setToken, setUser } = useAuthStore();
  
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Processando login...');
  const [errorDetails, setErrorDetails] = useState('');

  useEffect(() => {
    const processCallback = async () => {
      try {
        // Extrair parâmetros da URL
        const accessToken = searchParams.get('access_token');
        const refreshToken = searchParams.get('refresh_token');
        const userId = searchParams.get('user_id');
        const email = searchParams.get('email');
        const success = searchParams.get('success');
        const error = searchParams.get('error');

        console.log('[AuthCallback] Parâmetros recebidos:', {
          accessToken: !!accessToken,
          refreshToken: !!refreshToken,
          userId,
          email,
          success,
          error
        });

        // Verificar se houve erro
        if (error) {
          setStatus('error');
          const detail = searchParams.get('detail');
          setMessage('❌ Erro ao fazer login com Google');
          setErrorDetails(`${error}${detail ? `: ${detail}` : ''}`);
          console.error('[AuthCallback] Erro do Google OAuth:', error, detail);
          return;
        }

        // Verificar se recebeu sucesso
        if (success !== 'true' || !accessToken || !refreshToken) {
          setStatus('error');
          setMessage('❌ Dados incompletos recebidos');
          setErrorDetails('Não foram recebidos tokens necessários');
          console.error('[AuthCallback] Dados incompletos:', {
            success,
            hasAccessToken: !!accessToken,
            hasRefreshToken: !!refreshToken
          });
          return;
        }

        // Salvar tokens no localStorage via authService
        const authService = require('../services/authService').default;
        authService.setAccessToken(accessToken);
        authService.setRefreshToken(refreshToken);

        // Atualizar estado do AuthContext
        setToken(accessToken, refreshToken);

        // Salvar dados do usuário se disponíveis
        if (userId && email) {
          setUser({
            id: userId,
            email: email,
            name: searchParams.get('name') || '',
            plan: searchParams.get('plan') || 'free',
            credits: parseInt(searchParams.get('credits') || '5')
          });

          // Salvar também no localStorage
          localStorage.setItem('user_data', JSON.stringify({
            id: userId,
            email: email,
            name: searchParams.get('name') || '',
            avatar: searchParams.get('avatar') || ''
          }));
        }

        // Disparar evento de login bem-sucedido (para sincronizar outras abas)
        window.dispatchEvent(new CustomEvent('authSuccess', { 
          detail: { 
            token: accessToken,
            user: { id: userId, email }
          }
        }));

        setStatus('success');
        setMessage('✅ Login realizado com sucesso!');

        // Aguardar 2 segundos e redirecionar para dashboard
        setTimeout(() => {
          console.log('[AuthCallback] Redirecionando para dashboard...');
          navigate('/dashboard', { replace: true });
        }, 2000);

      } catch (err) {
        console.error('[AuthCallback] Erro ao processar callback:', err);
        setStatus('error');
        setMessage('❌ Erro ao processar autenticação');
        setErrorDetails(err instanceof Error ? err.message : String(err));
      }
    };

    processCallback();
  }, [searchParams, navigate, setToken, setUser]);

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center relative overflow-hidden">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(30,41,82,0.2)_1px,transparent_1px),linear-gradient(90deg,rgba(30,41,82,0.2)_1px,transparent_1px)] bg-[size:60px_60px]"></div>
        <div className="absolute top-0 left-0 w-full h-full">
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px] animate-pulse"></div>
          <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-indigo-600/10 rounded-full blur-[100px] animate-pulse delay-1000"></div>
        </div>
      </div>

      {/* Content */}
      <div className="relative z-10 w-full max-w-md px-6">
        <div className="bg-slate-900/80 backdrop-blur-lg border border-slate-800/50 rounded-2xl p-12 shadow-2xl shadow-blue-500/10">
          {/* Logo */}
          <div className="flex justify-center mb-8">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600 flex items-center justify-center shadow-2xl shadow-blue-500/30">
              <Zap className="w-8 h-8 text-white" />
            </div>
          </div>

          {/* Status Content */}
          <div className="text-center space-y-4">
            {status === 'loading' && (
              <>
                <div className="flex justify-center mb-6">
                  <Loader className="w-12 h-12 text-blue-500 animate-spin" />
                </div>
                <h2 className="text-2xl font-bold text-white">Processando Login</h2>
                <p className="text-slate-400 text-lg">{message}</p>
              </>
            )}

            {status === 'success' && (
              <>
                <div className="flex justify-center mb-6">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center">
                    <CheckCircle2 className="w-10 h-10 text-emerald-500 animate-pulse" />
                  </div>
                </div>
                <h2 className="text-2xl font-bold text-emerald-400">{message}</h2>
                <p className="text-slate-400">Redirecionando para dashboard...</p>
              </>
            )}

            {status === 'error' && (
              <>
                <div className="flex justify-center mb-6">
                  <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
                    <AlertCircle className="w-10 h-10 text-red-500" />
                  </div>
                </div>
                <h2 className="text-2xl font-bold text-red-400">{message}</h2>
                {errorDetails && (
                  <p className="text-slate-400 text-sm break-words">{errorDetails}</p>
                )}
                <div className="mt-8 pt-6 border-t border-slate-700">
                  <button
                    onClick={() => navigate('/login')}
                    className="w-full px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium rounded-lg transition-all duration-200 shadow-lg shadow-blue-500/20"
                  >
                    Voltar para Login
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Debug Info (development only) */}
          {import.meta.env.DEV && (
            <div className="mt-8 pt-6 border-t border-slate-700">
              <details className="text-xs text-slate-500">
                <summary className="cursor-pointer hover:text-slate-400">
                  Debug Info
                </summary>
                <pre className="mt-4 p-3 bg-slate-950 rounded border border-slate-800 overflow-auto max-h-32">
                  {JSON.stringify({
                    status,
                    hasAccessToken: !!searchParams.get('access_token'),
                    hasRefreshToken: !!searchParams.get('refresh_token'),
                    userId: searchParams.get('user_id'),
                    email: searchParams.get('email'),
                    timestamp: new Date().toISOString()
                  }, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
