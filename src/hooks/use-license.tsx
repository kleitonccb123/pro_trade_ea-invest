/**
 * License Hook
 * 
 * Provides license/plan information and feature gates.
 */

import { useState, useEffect, useCallback, createContext, useContext, ReactNode } from 'react';
import { licenseApi, MyPlan } from '@/lib/api';
import { useAuthStore } from '@/context/AuthContext';
import { authService } from '@/services/authService';

interface LicenseContextType {
  plan: MyPlan | null;
  loading: boolean;
  error: string | null;
  isActive: boolean;
  canStartBot: boolean;
  canUseCopyTrading: boolean;
  canUseAdvancedAnalytics: boolean;
  canUseTelegramAlerts: boolean;
  maxBots: number;
  maxApiKeys: number;
  daysRemaining: number | null;
  refresh: () => Promise<void>;
}

const LicenseContext = createContext<LicenseContextType | null>(null);

export function LicenseProvider({ children }: { children: ReactNode }) {
  const [plan, setPlan] = useState<MyPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Get auth state
  const { isAuthenticated, isHydrated } = useAuthStore();

  const fetchPlan = useCallback(async () => {
    try {
      // Check if token exists
      const token = authService.getAccessToken();
      
      if (!token) {
        console.warn('[useLicense] Sem token, aguardando autenticação');
        setError(null);
        setLoading(false);
        return; // Não faz requisição
      }
      
      setError(null);
      const data = await licenseApi.getMyPlan();
      setPlan(data);
    } catch (err) {
      console.error('Failed to fetch license:', err);
      setError('Não foi possível verificar sua licença');
      // Default to free plan if can't fetch
      setPlan({
        user_id: 0,
        plan_type: 'free',
        license_active: true,
        features: {
          max_bots: 1,
          max_api_keys: 1,
          has_advanced_analytics: false,
          has_copy_trading: false,
          has_telegram_alerts: false,
        },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Wait for Zustand hydration before fetching
    if (!isHydrated) {
      console.log('[useLicense] Esperando rehydratação do Zustand...');
      return;
    }
    
    // Only fetch if authenticated
    if (isAuthenticated) {
      console.log('[useLicense] Autenticado, buscando plano...');
      fetchPlan();
    } else {
      console.log('[useLicense] Não autenticado, resetando...');
      setLoading(false);
      setPlan(null);
    }
  }, [isHydrated, isAuthenticated, fetchPlan]);

  const value: LicenseContextType = {
    plan,
    loading,
    error,
    isActive: plan?.license_active ?? false,
    canStartBot: plan?.license_active ?? false,
    canUseCopyTrading: plan?.features?.has_copy_trading ?? false,
    canUseAdvancedAnalytics: plan?.features?.has_advanced_analytics ?? false,
    canUseTelegramAlerts: plan?.features?.has_telegram_alerts ?? false,
    maxBots: plan?.features?.max_bots ?? 1,
    maxApiKeys: plan?.features?.max_api_keys ?? 1,
    daysRemaining: plan?.days_remaining ?? null,
    refresh: fetchPlan,
  };

  return (
    <LicenseContext.Provider value={value}>
      {children}
    </LicenseContext.Provider>
  );
}

export function useLicense() {
  const context = useContext(LicenseContext);
  if (!context) {
    throw new Error('useLicense must be used within LicenseProvider');
  }
  return context;
}

/**
 * Hook to check if a feature is available based on license
 */
export function useFeatureGate(feature: 'start_bot' | 'copy_trading' | 'advanced_analytics' | 'telegram_alerts') {
  const license = useLicense();
  
  switch (feature) {
    case 'start_bot':
      return {
        allowed: license.canStartBot,
        reason: license.isActive ? undefined : 'Licença inativa. Faça upgrade para continuar.',
      };
    case 'copy_trading':
      return {
        allowed: license.canUseCopyTrading,
        reason: license.canUseCopyTrading ? undefined : 'Recurso disponível apenas no plano Pro ou superior.',
      };
    case 'advanced_analytics':
      return {
        allowed: license.canUseAdvancedAnalytics,
        reason: license.canUseAdvancedAnalytics ? undefined : 'Recurso disponível apenas no plano Pro ou superior.',
      };
    case 'telegram_alerts':
      return {
        allowed: license.canUseTelegramAlerts,
        reason: license.canUseTelegramAlerts ? undefined : 'Recurso disponível apenas no plano Business.',
      };
    default:
      return { allowed: false, reason: 'Recurso desconhecido' };
  }
}
