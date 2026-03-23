import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authService } from '@/services/authService';
import { API_BASE_URL, AUTH_CONFIG } from '@/config/constants';

/**
 * Sync tokens with centralized authService
 * This ensures AuthContext and all other parts of the app use the same token storage.
 */
const saveTokensToStorage = (accessToken: string | null, refreshToken: string | null) => {
  authService.setTokens(accessToken, refreshToken);
};

const clearTokensFromStorage = () => {
  authService.clearTokens();
};

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface AuthStore {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isHydrated: boolean; // ✅ NOVA FLAG
  error: string | null;

  setUser: (user: User | null) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string) => Promise<void>;
  googleLogin: (idToken: string, email: string, name: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  clearError: () => void;
  handleCritical401: () => void;
  setHydrated: (value: boolean) => void; // ✅ NOVA ACTION
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: true, // Start as true until initial checkAuth is complete
      isHydrated: false, // ✅ NOVA FLAG - starts false
      error: null,

      setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),
      
      setTokens: (accessToken, refreshToken) => {
        saveTokensToStorage(accessToken, refreshToken);
        set({ accessToken, isAuthenticated: !!accessToken, isLoading: false });
      },

      clearError: () => set({ error: null }),
      
      setHydrated: (value) => set({ isHydrated: value }), // ✅ NOVA ACTION

      handleCritical401: () => {
        console.error('[AuthContext] Critical 401 error detected, clearing all auth data');
        clearTokensFromStorage();
        localStorage.removeItem('auth-storage');
        localStorage.removeItem('kucoin_connected');
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          isLoading: false,
          error: 'Sessão expirada. Por favor, faça login novamente.',
        });
      },

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const url = `${API_BASE_URL}/api/auth/login`;
          console.log('[AuthContext] === LOGIN START ===');
          console.log('[AuthContext] Email:', email);
          console.log('[AuthContext] URL:', url);
          console.log('[AuthContext] API_BASE_URL:', API_BASE_URL);
          console.log('[AuthContext] API_BASE_URL fallback:', 'http://localhost:8000');
          
          const payload = JSON.stringify({ email, password });
          console.log('[AuthContext] Payload:', payload);
          
          const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: payload,
          });
          
          console.log('[AuthContext] Response status:', res.status);
          console.log('[AuthContext] Response headers:', {
            contentType: res.headers.get('content-type'),
            corsHeaders: res.headers.get('access-control-allow-credentials'),
          });

          const text = await res.text();
          console.log('[AuthContext] Response body (raw):', text);
          
          if (!res.ok) {
            let errorData = {};
            try {
              errorData = JSON.parse(text);
            } catch (e) {
              console.error('[AuthContext] Failed to parse error response');
            }
            throw new Error(errorData?.message || errorData?.detail || `Erro HTTP: ${res.status}`);
          }

          const data = JSON.parse(text);
          console.log('[AuthContext] Parsed data:', { success: data.success, hasToken: !!data.access_token, requires_2fa: data.requires_2fa });

          if (!data.success) {
            throw new Error(data.message || 'Erro ao fazer login');
          }

          // Handle 2FA requirement
          if (data.requires_2fa) {
            console.log('[AuthContext] 2FA required, redirecting...');
            set({ isLoading: false });
            const err = new Error('2FA_REQUIRED') as any;
            err.requires2FA = true;
            err.pendingToken = data.pending_token;
            err.email = email;
            throw err;
          }

          // Salvar tokens no localStorage para sincronização com useApi
          saveTokensToStorage(data.access_token, null);

          set({
            user: data.user,
            accessToken: data.access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
          
          console.log('[AuthContext] === LOGIN SUCCESS ===');
        } catch (error: any) {
          let errorMsg = 'Erro de conexão com o servidor';
          
          console.error('[AuthContext] === LOGIN ERROR ===');
          console.error('[AuthContext] Full error:', error);
          console.error('[AuthContext] Error name:', error.name);
          console.error('[AuthContext] Error message:', error.message);
          console.error('[AuthContext] Error toString:', error.toString());
          
          if (error.name === 'AbortError') {
            errorMsg = 'Tempo limite de conexão excedido. Tente novamente.';
          } else if (error.message?.includes('NetworkError') || error.message?.includes('Failed to fetch')) {
            errorMsg = `Erro de rede: ${error.message || 'Servidor não respondeu'}`;
          } else if (error.message) {
            errorMsg = error.message;
          }
          
          console.error('[AuthContext] Final error message:', errorMsg);
          set({ isLoading: false, error: errorMsg });
          throw new Error(errorMsg);
        }
      },

      signup: async (email: string, password: string, name: string) => {
        set({ isLoading: true, error: null });
        try {
          const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email, password, name }),
          });

          if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP Error: ${res.status}`);
          }

          const data = await res.json();

          if (!data.success) {
            throw new Error(data.message || 'Erro ao registrar');
          }

          // Salvar tokens no localStorage para sincronização com useApi
          saveTokensToStorage(data.access_token, null);

          set({
            user: data.user,
            accessToken: data.access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error: any) {
          const errorMsg = error.message || 'Erro de conexão com o servidor';
          set({ isLoading: false, error: errorMsg });
          throw error;
        }
      },

      googleLogin: async (idToken: string, email: string, name: string) => {
        set({ isLoading: true, error: null });
        try {
          console.log('[AuthContext] Iniciando Google login para:', email);
          const res = await fetch(`${API_BASE_URL}/api/auth/google`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ id_token: idToken, email, name }),
          });

          console.log('[AuthContext] Resposta recebida:', res.status, res.statusText);
          
          if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            const errorMsg = errorData.detail || errorData.message || `HTTP Error: ${res.status}`;
            console.error('[AuthContext] Erro HTTP:', errorMsg);
            throw new Error(errorMsg);
          }

          const data = await res.json();
          console.log('[AuthContext] Resposta JSON:', { success: data.success, user: data.user?.email });

          if (!data.success) {
            throw new Error(data.message || 'Erro ao autenticar com Google');
          }

          // Salvar tokens no localStorage para sincronização com useApi
          saveTokensToStorage(data.access_token, null);

          console.log('[AuthContext] ✅ Login Google bem-sucedido para:', email);
          set({
            user: data.user,
            accessToken: data.access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error: any) {
          const errorMsg = error.message || 'Erro de conexão com o servidor';
          console.error('[AuthContext] ❌ Erro final:', errorMsg);
          set({ isLoading: false, error: errorMsg });
          throw error;
        }
      },

      logout: () => {
        // Tell the backend to blacklist the access token and clear the httpOnly cookie
        const currentToken = get().accessToken || authService.getAccessToken();
        fetch(`${API_BASE_URL}/api/auth/logout`, {
          method: 'POST',
          headers: currentToken ? { 'Authorization': `Bearer ${currentToken}` } : {},
          credentials: 'include',
        }).catch(() => { /* best-effort */ });

        clearTokensFromStorage();
        localStorage.removeItem('kucoin_connected');

        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      },

      checkAuth: async () => {
        const state = get();
        
        // 💡 Get token from authService (single source of truth)
        let token = state.accessToken || authService.getAccessToken();
        
        if (!token) {
          console.log('[AuthContext] Sem token encontrado');
          set({ isLoading: false, isAuthenticated: false });
          return;
        }

        set({ isLoading: true });

        const _tryRefresh = async (): Promise<string | null> => {
          console.log('[AuthContext] Tentando renovar token...');
          const newToken = await authService.refreshAccessToken();
          if (newToken) {
            set({
              accessToken: newToken,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
            console.log('[AuthContext] ✅ Token renovado com sucesso');
          } else {
            console.warn('[AuthContext] ❌ Refresh falhou — desautenticando');
            clearTokensFromStorage();
            localStorage.removeItem('auth-storage');
            set({
              user: null,
              accessToken: null,
              isAuthenticated: false,
              isLoading: false,
              error: 'Sessão expirada. Faça login novamente.',
            });
          }
          return newToken;
        };

        try {
          console.log('[AuthContext] ✅ Validando token com backend...');
          
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 10000);
          
          const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` },
            signal: controller.signal,
          });
          
          clearTimeout(timeoutId);

          // Token expirado — tentar refresh antes de desautenticar
          if (res.status === 401) {
            console.warn('[AuthContext] Token expirado (401), tentando refresh...');
            const newToken = await _tryRefresh();
            if (!newToken) return; // já desautenticou dentro de _tryRefresh
            // Re-validar com novo token
            const res2 = await fetch(`${API_BASE_URL}/api/auth/me`, {
              headers: { 'Authorization': `Bearer ${newToken}` },
            });
            if (!res2.ok) {
              console.warn('[AuthContext] Re-validação falhou após refresh — desautenticando');
              clearTokensFromStorage();
              localStorage.removeItem('auth-storage');
              set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false });
              return;
            }
            const data2 = await res2.json();
            if (data2.success) {
              set({ user: data2.user, isAuthenticated: true, error: null, isLoading: false });
            } else {
              set({ isLoading: false });
            }
            return;
          }

          if (!res.ok) {
            console.warn('[AuthContext] ❌ Falha na validação do token com status:', res.status);
            set({ isLoading: false });
            return;
          }

          const data = await res.json();

          if (data.success) {
            console.log('[AuthContext] ✅ Token é válido, usuário autenticado');
            set({ user: data.user, isAuthenticated: true, error: null, isLoading: false });
          } else {
            console.warn('[AuthContext] Token validation returned success=false');
            set({ isLoading: false });
          }
        } catch (error: any) {
          console.error('[AuthContext] ❌ Erro na validação do token:', error.message);
          // AbortError = timeout de rede: tentar refresh antes de desistir
          if (error.name === 'AbortError') {
            await _tryRefresh();
          } else {
            // Qualquer outro erro de rede: manter estado atual mas parar loading
            set({ isLoading: false });
          }
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        // accessToken is intentionally excluded from localStorage persistence
        // (stored in sessionStorage via authService for page-reload resilience)
        // refreshToken lives in httpOnly cookie — never persisted in JS storage
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          const accessToken = authService.getAccessToken();
          if (accessToken) {
            state.accessToken = accessToken;
            state.isAuthenticated = true;
            state.isLoading = false;
            state.isHydrated = true;
          } else {
            state.isLoading = false;
            state.isHydrated = true;
            state.isAuthenticated = false;
          }
        }
      },
    }
  )
);
