/**
 * useGamification Hook
 * 
 * Hook customizado para gerenciar estado da gamificação.
 * Busca dados do endpoint /api/gamification/profile e mantém sincronizado com o backend.
 * 
 * Features:
 * - GET /api/gamification/profile (lazy loading)
 * - Refetch manual
 * - Error handling com retry
 * - Automatic updates baseado em ações do usuário
 */

import { useState, useEffect, useCallback } from 'react';
import useApi from './useApi';
import { useToast } from './use-toast';
import { useAuthStore } from '@/context/AuthContext';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export interface GameProfile {
  id?: string;
  user_id: string;
  trade_points: number;
  level: number;
  current_xp: number;
  total_xp: number;
  xp_for_next_level: number;
  xp_progress_percent: number;
  lifetime_profit: number;
  bots_unlocked: number;
  unlocked_robots: string[];
  daily_chest_streak: number;
  streak_count: number;  // ✅ NEW: Alias para daily_chest_streak
  xp: number;  // ✅ NEW: Alias para total_xp
  last_daily_chest_opened?: string | null;
  updated_at: string;
}

export interface LeaderboardItem {
  rank: number;
  user_masked_name: string;
  level: number;
  trade_points: number;
  badge: string;
  is_top_3: boolean;
}

export interface UserRankInfo {
  rank: number;
  trade_points: number;
  level: number;
  badge: string;
}

export interface LeaderboardData {
  success: boolean;
  message: string;
  total_entries: number;
  leaderboard: LeaderboardItem[];
  user_rank?: UserRankInfo;
}

export interface UseGamificationReturn {
  profile: GameProfile | null;
  loading: boolean;
  error: string | null;
  leveledUp: boolean;
  newLevel: number | null;
  refetch: () => Promise<void>;
  updateProfile: (updates: Partial<GameProfile>) => void;
  addTradePoints: (amount: number) => void;
  addXp: (amount: number) => void;
  unlockRobot: (robotId: string) => Promise<any>;
  claimDailyXp: () => Promise<any>;
  openDailyChest: () => Promise<any>;
  canOpenDailyChest: boolean;
  dailyChestTimeRemaining: {
    hours: number;
    minutes: number;
    seconds: number;
  } | null;
  // 🏆 Leaderboard functions ✅ NEW
  fetchLeaderboard: (limit?: number) => Promise<LeaderboardData | null>;
  leaderboard: LeaderboardItem[] | null;
  leaderboardLoading: boolean;
  leaderboardError: string | null;

}

/**
 * Hook principal para gamificação
 * 
 * @returns {UseGamificationReturn} State e funções de gamificação
 */
export function useGamification(): UseGamificationReturn {
  const { get, post } = useApi();
  const { toast } = useToast();
  
  const [profile, setProfile] = useState<GameProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [leveledUp, setLeveledUp] = useState(false);
  const [newLevel, setNewLevel] = useState<number | null>(null);

  // 🏆 Leaderboard state ✅ NEW
  const [leaderboard, setLeaderboard] = useState<LeaderboardItem[] | null>(null);
  const [leaderboardLoading, setLeaderboardLoading] = useState(false);
  const [leaderboardError, setLeaderboardError] = useState<string | null>(null);

  const [retrying, setRetrying] = useState(false);

  /**
   * Busca perfil diretamente via fetch() nativo para evitar dependência
   * do useApi (cujo axiosInstance é inicializado em useEffect e pode
   * não estar pronto na primeira chamada).
   */
  const fetchProfile = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.warn('[useGamification] Sem token — abortando fetch de perfil.');
      return;
    }

    setLoading(true);
    setError(null);
    setUnavailable(false);

    try {
      console.log('[useGamification] Buscando perfil (fetch nativo)...');

      const res = await fetch(`${API_BASE}/api/gamification/profile`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const data: GameProfile = await res.json();
        console.log('[useGamification] ✓ Perfil carregado:', data);
        setProfile(data);
        setUnavailable(false);
      } else if (res.status === 401) {
        // Token expirado — tenta refresh depois de 1s
        console.warn('[useGamification] 401 — agendando retry...');
        setRetrying(true);
        setTimeout(async () => {
          const newToken = localStorage.getItem('access_token');
          if (!newToken) { setUnavailable(true); setRetrying(false); return; }
          try {
            const r2 = await fetch(`${API_BASE}/api/gamification/profile`, {
              headers: { Authorization: `Bearer ${newToken}` },
            });
            if (r2.ok) { const d2: GameProfile = await r2.json(); setProfile(d2); setUnavailable(false); }
            else { setUnavailable(true); }
          } catch { setUnavailable(true); }
          finally { setRetrying(false); }
        }, 1000);
        return;
      } else {
        console.error('[useGamification] ✗ HTTP', res.status);
        setError(`Erro HTTP ${res.status}`);
        setUnavailable(true);
      }
    } catch (err: any) {
      console.error('[useGamification] ✗ Falha de rede:', err?.message);
      setError(err?.message || 'Erro de rede');
      setUnavailable(true);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Busca autenticação do Zustand store
   */
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isHydrated = useAuthStore((s) => s.isHydrated);

  /**
   * Só carrega o perfil quando o auth estiver hidratado e o usuário logado.
   * Limpa o perfil ao fazer logout.
   * Fallback: se isHydrated nunca virar true mas há token no localStorage, busca mesmo assim.
   */
  useEffect(() => {
    const hasToken = !!localStorage.getItem('access_token');

    // Auth ainda rehidratando — aguarda, mas só até ter token local
    if (!isHydrated && !hasToken) {
      console.log('[useGamification] Aguardando hidratação do auth...');
      return;
    }

    const shouldFetch = isAuthenticated || hasToken;

    if (!shouldFetch) {
      console.log('[useGamification] Usuário não autenticado — limpando perfil.');
      setProfile(null);
      setUnavailable(false);
      setError(null);
      return;
    }
    console.log('[useGamification] Auth pronto (isAuthenticated=%s, hasToken=%s), buscando perfil...', isAuthenticated, hasToken);
    fetchProfile();

    // Sincroniza todas as instâncias do hook quando outro componente dispara unlock
    const handler = () => { fetchProfile(); };
    window.addEventListener('gamification:profile-reload', handler);
    return () => window.removeEventListener('gamification:profile-reload', handler);
  }, [isAuthenticated, isHydrated, fetchProfile]);

  /**
   * Atualiza perfil localmente (para otimismo)
   */
  const updateProfile = useCallback((updates: Partial<GameProfile>) => {
    if (profile) {
      const updated = { ...profile, ...updates };
      setProfile(updated);
      console.log('[useGamification] Profile atualizado localmente:', updated);
    }
  }, [profile]);

  /**
   * Adiciona Trade Points localmente
   */
  const addTradePoints = useCallback((amount: number) => {
    if (profile) {
      const newPoints = profile.trade_points + amount;
      updateProfile({ trade_points: newPoints });
      console.log(`[useGamification] +${amount} trade_points (total: ${newPoints})`);
    }
  }, [profile, updateProfile]);

  /**
   * Adiciona XP localmente e verifica level-up
   */
  const addXp = useCallback((amount: number) => {
    if (profile) {
      const newXp = profile.current_xp + amount;
      const totalXp = profile.total_xp + amount;
      
      // Calcula se teve level up
      const xpForNextLevel = profile.xp_for_next_level;
      let newLevel = profile.level;
      
      if (newXp >= xpForNextLevel) {
        newLevel += 1;
        console.log(`[useGamification] 🎉 LEVEL UP! ${profile.level} → ${newLevel}`);
      }
      
      updateProfile({
        total_xp: totalXp,
        current_xp: newXp,
        level: newLevel,
      });
      
      console.log(`[useGamification] +${amount} XP (total: ${totalXp}, level: ${newLevel})`);
    }
  }, [profile, updateProfile]);

  /**
   * Desbloqueia robô via API com operações ATÔMICAS
   * 
   * @param robotId ID do robô a desbloquear
   * @returns Promise com resultado ou null se erro
   */
  const unlockRobot = useCallback(async (robotId: string): Promise<any> => {
    if (!profile) {
      console.error('[useGamification] ❌ Perfil não carregado');
      toast({
        title: '❌ Erro',
        description: 'Perfil não foi carregado',
        variant: 'destructive',
      });
      return null;
    }

    // Validação local: robô já desbloqueado
    if (profile.unlocked_robots.includes(robotId)) {
      console.warn(`[useGamification] ⚠️ Robô ${robotId} já estava desbloqueado`);
      toast({
        title: '⚠️ Aviso',
        description: 'Este robô já foi desbloqueado!',
        variant: 'destructive',
      });
      return null;
    }

    const token = localStorage.getItem('access_token');
    if (!token) {
      toast({ title: '❌ Sessão expirada', description: 'Faça login novamente.', variant: 'destructive' });
      return null;
    }

    try {
      console.log(`[useGamification] 🔓 Desbloqueando robô: ${robotId}...`);

      // Usa fetch nativo (igual ao fetchProfile) para evitar problemas de init do axios
      const res = await fetch(`${API_BASE}/api/gamification/robots/${robotId}/unlock`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });

      const data = await res.json();

      if (res.ok && data?.success) {
        const points_remaining = data.points_remaining ?? data.new_balance ?? profile.trade_points;

        // Atualiza profile localmente
        const updated = {
          ...profile,
          unlocked_robots: [...profile.unlocked_robots, robotId],
          bots_unlocked: (profile.bots_unlocked || 0) + 1,
          trade_points: points_remaining,
        };
        setProfile(updated);

        // Notifica todas as outras instâncias do hook (ex: GameProfileWidget)
        window.dispatchEvent(new CustomEvent('gamification:profile-reload'));

        toast({
          title: '✅ Robô desbloqueado!',
          description: `Pontos restantes: ${points_remaining.toLocaleString()}`,
          duration: 3000,
        });

        console.log(`[useGamification] ✅ Sucesso: ${robotId} | pontos: ${points_remaining}`);
        return data;
      }

      // Erro retornado pelo backend
      const detail = data?.detail;
      const msg = typeof detail === 'string'
        ? detail
        : (detail?.message || JSON.stringify(detail) || 'Erro ao desbloquear robô');

      console.error(`[useGamification] ❌ HTTP ${res.status}: ${msg}`);

      if (res.status === 400) {
        toast({ title: '⚠️ Já desbloqueado', description: msg, variant: 'destructive', duration: 3000 });
      } else if (res.status === 403) {
        toast({ title: '❌ Saldo insuficiente', description: msg, variant: 'destructive', duration: 4000 });
      } else {
        toast({ title: '❌ Erro', description: msg, variant: 'destructive', duration: 4000 });
      }
      return null;

    } catch (error: any) {
      console.error('[useGamification] ❌ Exceção ao desbloquear:', error);
      toast({
        title: '❌ Erro de conexão',
        description: 'Não foi possível conectar ao servidor.',
        variant: 'destructive',
        duration: 4000,
      });
      return null;
    }
  }, [profile, toast]);

  /**
   * Reclamar XP Diário via API
   */
  const claimDailyXp = useCallback(async () => {
    try {
      console.log('[useGamification] Reclamando XP diário...');
      const response = await post('/api/gamification/claim-daily-xp', {}) as any;

      // post() já retorna response.data, então response É o body
      if (response?.success) {
        const { xp_gained, new_level, leveled_up, current_xp, xp_required_for_level } = response;
        
        // Atualiza profile localmente
        if (profile) {
          const updated = {
            ...profile,
            current_xp: current_xp,
            level: new_level,
            xp_for_next_level: xp_required_for_level,
          };
          setProfile(updated);
        }
        
        // Detecta level up
        if (leveled_up) {
          setLeveledUp(true);
          setNewLevel(new_level);
          console.log(`[useGamification] 🎉 LEVEL UP! → Nível ${new_level}`);
          
          // Auto-limpar flag após 5s
          setTimeout(() => {
            setLeveledUp(false);
            setNewLevel(null);
          }, 5000);
        }
        
        // Toast de sucesso
        toast({
          title: `✓ +${xp_gained} XP ganho!`,
          description: leveled_up ? `Parabéns! Você atingiu o nível ${new_level}!` : undefined,
          duration: 3000,
        });
        
        return response;
      } else {
        // XP já foi reclamado hoje
        const errorMsg = response?.message || 'Não foi possível reclamar XP';
        toast({
          title: '⏰ Limite atingido',
          description: errorMsg,
          variant: 'destructive',
          duration: 3000,
        });
        console.warn('[useGamification] XP daily limit:', errorMsg);
        return null;
      }
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Erro ao reclamar XP';
      console.error('[useGamification] ❌ Erro ao reclamar XP:', error);
      
      toast({
        title: '❌ Erro',
        description: errorMsg,
        variant: 'destructive',
        duration: 3000,
      });
      
      return null;
    }
  }, [profile, post, toast]);

  /**
   * ✅ NEW: Estados para Daily Chest com Timer
   */
  const [canOpenDailyChest, setCanOpenDailyChest] = useState(true);
  const [dailyChestTimeRemaining, setDailyChestTimeRemaining] = useState<{
    hours: number;
    minutes: number;
    seconds: number;
  } | null>(null);

  /**
   * ✅ NEW: Verificar status do Daily Chest e iniciar timer
   */
  useEffect(() => {
    if (!profile?.last_daily_chest_opened) {
      setCanOpenDailyChest(true);
      setDailyChestTimeRemaining(null);
      return;
    }

    const checkChestStatus = () => {
      const lastOpened = new Date(profile.last_daily_chest_opened!);
      const now = new Date();
      const diff = now.getTime() - lastOpened.getTime();
      const secondsRemaining = Math.max(0, 86400000 - diff);

      if (secondsRemaining <= 0) {
        setCanOpenDailyChest(true);
        setDailyChestTimeRemaining(null);
      } else {
        setCanOpenDailyChest(false);
        
        const hours = Math.floor(secondsRemaining / (1000 * 60 * 60));
        const minutes = Math.floor((secondsRemaining % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((secondsRemaining % (1000 * 60)) / 1000);

        setDailyChestTimeRemaining({ hours, minutes, seconds });
      }
    };

    checkChestStatus();
    const interval = setInterval(checkChestStatus, 1000);

    return () => clearInterval(interval);
  }, [profile?.last_daily_chest_opened]);

  /**
   * ✅ NEW: Abre o baú diário via API
   */
  const openDailyChest = useCallback(async (): Promise<any> => {
    try {
      console.log('[useGamification] 🎁 Abrindo baú diário...');

      const response = await post('/api/gamification/daily-chest/open', {}) as any;

      // post() já retorna response.data, então response É o body
      if (response?.success) {
        const {
          points_won,
          xp_won,
          new_streak,
          streak_bonus_percent,
          leveled_up,
          new_level,
        } = response;

        // Atualizar profile localmente
        if (profile) {
          const updated = {
            ...profile,
            trade_points: (profile.trade_points || 0) + points_won,
            total_xp: (profile.total_xp || 0) + xp_won,
            current_xp: (profile.current_xp || 0) + xp_won,
            xp: (profile.xp || profile.total_xp || 0) + xp_won,
            streak_count: new_streak,
            daily_chest_streak: new_streak,
            last_daily_chest_opened: new Date().toISOString(),
            level: new_level || profile.level,
          };
          setProfile(updated);
        }

        // Detecta level up
        if (leveled_up) {
          setLeveledUp(true);
          setNewLevel(new_level);
          console.log(`[useGamification] 🎉 LEVEL UP! → Nível ${new_level}`);
          
          setTimeout(() => {
            setLeveledUp(false);
            setNewLevel(null);
          }, 5000);
        }

        // Toast de sucesso
        toast({
          title: `🎁 +${points_won}pts +${xp_won}XP!`,
          description: `Ofensiva: ${new_streak} dias (+${streak_bonus_percent}% bônus)`,
          duration: 3000,
        });

        console.log(`[useGamification] ✅ Baú aberto! +${points_won}pts +${xp_won}XP (streak: ${new_streak})`);
        return response;
      } else {
        // Cooldown ativo
        const errorMsg = response?.message || 'Baú ainda em cooldown';
        console.warn(`[useGamification] ⏰ Cooldown: ${errorMsg}`);
        
        toast({
          title: '⏰ Baú em cooldown',
          description: errorMsg,
          variant: 'destructive',
          duration: 3000,
        });
        
        return null;
      }
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Erro ao abrir baú';
      console.error('[useGamification] ❌ Erro ao abrir baú:', error);

      toast({
        title: '❌ Erro',
        description: errorMsg,
        variant: 'destructive',
      });

      return null;
    }
  }, [profile, post, toast]);

  /**
   * 🏆 NEW: Busca leaderboard do servidor
   */
  const fetchLeaderboard = useCallback(async (limit: number = 50): Promise<LeaderboardData | null> => {
    setLeaderboardLoading(true);
    setLeaderboardError(null);

    try {
      console.log(`[useGamification] 🏆 Buscando leaderboard (limit: ${limit})...`);

      const response = await get(`/api/gamification/leaderboard?limit=${limit}`);
      
      // get() já retorna response.data, então response É o body
      if (response) {
        const data = response as LeaderboardData;
        console.log(`[useGamification] ✓ Leaderboard carregado: ${data.total_entries} usuários`);
        setLeaderboard(data.leaderboard);
        return data;
      } else {
        throw new Error('Resposta vazia do servidor');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Erro ao carregar leaderboard';
      console.error('[useGamification] ✗ Erro no leaderboard:', errorMsg);
      setLeaderboardError(errorMsg);
      
      toast({
        title: '⚠️ Erro',
        description: 'Não foi possível carregar o leaderboard',
        variant: 'destructive',
      });
      
      return null;
    } finally {
      setLeaderboardLoading(false);
    }
  }, [get, toast]);

  /**
   * 🏆 NEW: Limpa leaderboard ao trocar de aba
   */
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        console.log('[useGamification] Página oculta, limpando cache de leaderboard');
        setLeaderboard(null);
        setLeaderboardError(null);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  return {
    profile,
    loading: loading || retrying,
    error,
    leveledUp,
    newLevel,
    refetch: fetchProfile,
    updateProfile,
    addTradePoints,
    addXp,
    unlockRobot,
    claimDailyXp,
    openDailyChest,
    canOpenDailyChest,
    dailyChestTimeRemaining,
    fetchLeaderboard,
    leaderboard,
    leaderboardLoading,
    leaderboardError,
  };
}

/**
 * Hook para Status de Daily Chest
 * 
 * Verifica se o usuário pode abrir o Daily Chest hoje
 */
export function useDailyChestStatus(profile: GameProfile | null) {
  const [canOpen, setCanOpen] = useState(true);
  const [timeRemaining, setTimeRemaining] = useState<{
    hours: number;
    minutes: number;
    seconds: number;
  } | null>(null);

  useEffect(() => {
    if (!profile?.last_daily_chest_opened) {
      setCanOpen(true);
      return;
    }

    const checkChestStatus = () => {
      const lastOpened = new Date(profile.last_daily_chest_opened!);
      const now = new Date();
      const diff = now.getTime() - lastOpened.getTime();
      const secondsRemaining = Math.max(0, 86400000 - diff);

      if (secondsRemaining <= 0) {
        setCanOpen(true);
        setTimeRemaining(null);
      } else {
        setCanOpen(false);
        
        const hours = Math.floor(secondsRemaining / (1000 * 60 * 60));
        const minutes = Math.floor((secondsRemaining % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((secondsRemaining % (1000 * 60)) / 1000);

        setTimeRemaining({ hours, minutes, seconds });
      }
    };

    checkChestStatus();
    const interval = setInterval(checkChestStatus, 1000);

    return () => clearInterval(interval);
  }, [profile?.last_daily_chest_opened]);

  return { canOpen, timeRemaining };
}

/**
 * Hook para cálculos de progresso
 */
export function useGamificationProgress(profile: GameProfile | null) {
  return {
    level: profile?.level ?? 1,
    xpPercent: profile?.xp_progress_percent ?? 0,
    nextLevelXp: profile?.xp_for_next_level ?? 100,
    totalXp: profile?.total_xp ?? 0,
    streakDays: profile?.daily_chest_streak ?? 0,
    pointsBalance: profile?.trade_points ?? 0,
    botsUnlocked: profile?.bots_unlocked ?? 0,
  };
}
