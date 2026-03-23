import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/context/AuthContext';
import { API_BASE_URL } from '@/config/constants';
import { KuCoinOnboarding } from '@/components/KuCoinOnboarding';
import { KuCoinDashboard } from '@/components/kucoin/KuCoinDashboard';
import type { BotConfig } from '@/components/gamification/BotConfigModal';
import { DashboardKPISkeleton, ChartSkeleton } from '@/components/patterns';
import { DashboardLayout, DashboardGrid } from '@/components/layouts';

const KUCOIN_STORAGE_KEY = 'kucoin_connected';
const ACTIVE_BOT_KEY = 'active_bot_config';

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, accessToken, isHydrated } = useAuthStore();
  const [loading, setLoading] = useState(true);

  // Lê do localStorage imediatamente para evitar flash do onboarding
  const [hasKuCoinCredentials, setHasKuCoinCredentials] = useState<boolean>(
    () => localStorage.getItem(KUCOIN_STORAGE_KEY) === 'true'
  );

  const [activeBotConfig, setActiveBotConfig] = useState<BotConfig | null>(() => {
    try {
      const saved = localStorage.getItem(ACTIVE_BOT_KEY);
      return saved ? (JSON.parse(saved) as BotConfig) : null;
    } catch {
      return null;
    }
  });
  // Se já temos cache, não precisa mostrar skeleton aguardando o check
  const [checkingCredentials, setCheckingCredentials] = useState(
    () => localStorage.getItem(KUCOIN_STORAGE_KEY) !== 'true'
  );

  useEffect(() => {
    // Wait for hydration
    if (!isHydrated) {
      console.log('[Dashboard] Aguardando rehydratação...');
      return;
    }

    if (!user || !accessToken) {
      console.warn('[Dashboard] Não autenticado, redirecionando para login');
      navigate('/login', { replace: true });
    } else {
      setLoading(false);
      checkKuCoinStatus();
    }
  }, [isHydrated, user, accessToken, navigate]);

  const saveKuCoinStatus = (connected: boolean) => {
    if (connected) {
      localStorage.setItem(KUCOIN_STORAGE_KEY, 'true');
    } else {
      localStorage.removeItem(KUCOIN_STORAGE_KEY);
    }
    setHasKuCoinCredentials(connected);
  };

  const checkKuCoinStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trading/kucoin/status`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.connected === true) {
          // Backend confirmou: está conectado
          saveKuCoinStatus(true);
        } else if (data.status === 'not_configured') {
          // Backend confirmou explicitamente: sem credenciais
          saveKuCoinStatus(false);
        }
        // Se status === 'error' (erro interno do backend), manter cache atual
      }
      // Erros HTTP (401, 500 etc.) → manter cache atual silenciosamente
    } catch (err) {
      console.error('Erro ao verificar status KuCoin:', err);
      // Erro de rede → manter cache atual
    } finally {
      setCheckingCredentials(false);
    }
  };

  if (loading || checkingCredentials) {
    // ── Skeleton de loading — nunca spinner central ──────────────────────
    return (
      <DashboardLayout>
        <DashboardGrid.Root>
          {/* Nível 1: KPIs */}
          <DashboardGrid.Full>
            <DashboardKPISkeleton />
          </DashboardGrid.Full>
          {/* Nível 2: gráfico + painel lateral */}
          <DashboardGrid.Main>
            <ChartSkeleton height={480} />
          </DashboardGrid.Main>
          <DashboardGrid.Aside>
            <ChartSkeleton height={220} />
            <ChartSkeleton height={220} />
          </DashboardGrid.Aside>
        </DashboardGrid.Root>
      </DashboardLayout>
    );
  }

  // Se não tiver credenciais configuradas, mostrar onboarding
  if (!hasKuCoinCredentials) {
    return <KuCoinOnboarding onCredentialsAdded={() => saveKuCoinStatus(true)} />;
  }

  // Se estiver conectado, mostrar dashboard da KuCoin
  const handleBotStopped = () => setActiveBotConfig(null);

  return <KuCoinDashboard accessToken={accessToken} activeBotConfig={activeBotConfig} onBotStop={handleBotStopped} />;
}
