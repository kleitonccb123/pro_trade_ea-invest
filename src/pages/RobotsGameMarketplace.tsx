/**
 * RobotsMarketplacePage - Página principal da Arena de Lucros Gamificada
 * 
 * Exibe:
 * - GameProfileWidget no topo (dados reais via useGamification)
 * - Botão para abrir painel de período (24h/7d/15d)
 * - Grid de 20 robôs com RobotMarketplaceCard
 * - LockedRobotModal ao clicar em robô
 * - UnlockRobotModal ao desbloquear com TradePoints
 * - LevelUpModal ao fazer level up
 * - Ranking com Top 3 destacado
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Star, X as XIcon } from 'lucide-react';
import { apiCall } from '@/services/apiClient';
import {
  Flame,
  Clock,
  Trophy,
  BarChart3,
  Zap,
  Filter,
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  DollarSign,
  Layers,
  Loader2,
  Monitor,
  Power,
  PowerOff,
  RefreshCw,
  Shield,
  TrendingDown,
  TrendingUp,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import {
  type ActivationResponse,
  type AuditLogEntry,
  type SystemStateResponse,
  type EATelemetry,
  STRATEGY_REGISTRY,
  activateStrategy,
  deactivateStrategy,
  getAuditLog,
  getSystemState,
  eaStatusColor,
  eaStatusLabel,
  formatUptime,
  stateColor,
  stateLabel,
  timeframeColor,
} from '@/services/strategyManagerService';
import { GameProfileWidget } from '@/components/gamification/GameProfileWidget';
import { RobotMarketplaceCard } from '@/components/gamification/RobotMarketplaceCard';
import { LockedRobotModal } from '@/components/gamification/LockedRobotModal';
import { LevelUpModal } from '@/components/gamification/LevelUpModal';
import { UnlockRobotModal } from '@/components/gamification/UnlockRobotModal';
import { RankingPeriodSelector } from '@/components/gamification/RankingPeriodSelector';
import { BotConfigModal } from '@/components/gamification/BotConfigModal';
import { useGamification } from '@/hooks/use-gamification';

// Mock Data para demonstração
const mockRobots = [
  {
    id: 'bot_001',
    name:'Volatility Dragon',
    creator: 'Li Wei',
    country: '🇨🇳',
    strategy: 'grid',
    rank: 1,
    medal: '🥇',
    is_locked: true,
    is_on_fire: true,
    unlock_cost: 1500, // ELITE — custo real do backend
    profit_15d: 3450.67,
    profit_7d: 1725.34,
    profit_24h: 245.67,
    win_rate: 68.5,
    total_trades: 245,
  },
  {
    id: 'bot_002',
    name: 'Legend Slayer',
    creator: 'Dmitri Volkoff',
    country: '🇷🇺',
    strategy: 'combined',
    rank: 2,
    medal: '🥈',
    is_locked: true,
    is_on_fire: true,
    unlock_cost: 1500, // ELITE — custo real do backend
    profit_15d: 3200.50,
    profit_7d: 1600.25,
    profit_24h: 228.50,
    win_rate: 65.0,
    total_trades: 200,
  },
  {
    id: 'bot_003',
    name: 'Grid Precision',
    creator: 'Kenji Tanaka',
    country: '🇯🇵',
    strategy: 'grid',
    rank: 3,
    medal: '🥉',
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 1500, // ELITE — custo real do backend
    profit_15d: 2950.25,
    profit_7d: 1475.13,
    profit_24h: 210.75,
    win_rate: 72.0,
    total_trades: 180,
  },
  {
    id: 'bot_004',
    name: 'Hybrid Flame',
    creator: 'Aviv Cohen',
    country: '🇮🇱',
    strategy: 'combined',
    rank: 4,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 500,
    profit_15d: 2800.00,
    profit_7d: 1400.00,
    profit_24h: 200.00,
    win_rate: 70.0,
    total_trades: 190,
  },
  {
    id: 'bot_005',
    name: 'RSI Hunter Elite',
    creator: 'Marco Stein',
    country: '🇨🇭',
    strategy: 'rsi',
    rank: 5,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 450,
    profit_15d: 2600.50,
    profit_7d: 1300.25,
    profit_24h: 185.75,
    win_rate: 65.5,
    total_trades: 165,
  },
  {
    id: 'bot_006',
    name: 'Grid Master Alpha',
    creator: 'Pedro Silva',
    country: '🇧🇷',
    strategy: 'grid',
    rank: 6,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 480,
    profit_15d: 2450.80,
    profit_7d: 1225.40,
    profit_24h: 175.05,
    win_rate: 68.0,
    total_trades: 155,
  },
  {
    id: 'bot_007',
    name: 'MACD Trendsetter',
    creator: 'Wei Zhang',
    country: '🇨🇳',
    strategy: 'macd',
    rank: 7,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 470,
    profit_15d: 2320.40,
    profit_7d: 1160.20,
    profit_24h: 165.85,
    win_rate: 66.5,
    total_trades: 145,
  },
  {
    id: 'bot_008',
    name: 'DCA Accumulator',
    creator: 'Yuki Yamamoto',
    country: '🇯🇵',
    strategy: 'dca',
    rank: 8,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 400,
    profit_15d: 2150.00,
    profit_7d: 1075.00,
    profit_24h: 153.57,
    win_rate: 75.0,
    total_trades: 120,
  },
  {
    id: 'bot_009',
    name: 'Scalper Ghost',
    creator: 'Natasha Petrov',
    country: '🇷🇺',
    strategy: 'rsi',
    rank: 9,
    medal: undefined,
    is_locked: false,
    is_on_fire: false,
    unlock_cost: 420,
    profit_15d: 2050.25,
    profit_7d: 1025.13,
    profit_24h: 146.47,
    win_rate: 71.0,
    total_trades: 155,
  },
  {
    id: 'bot_010',
    name: 'Grid Harvester Pro',
    creator: 'David Goldstein',
    country: '🇮🇱',
    strategy: 'grid',
    rank: 10,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 490,
    profit_15d: 1920.50,
    profit_7d: 960.25,
    profit_24h: 137.18,
    win_rate: 69.0,
    total_trades: 140,
  },
  {
    id: 'bot_011',
    name: 'Momentum Master',
    creator: 'Carlos Ferreira',
    country: '🇧🇷',
    strategy: 'grid',
    rank: 11,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 460,
    profit_15d: 1850.75,
    profit_7d: 925.38,
    profit_24h: 132.20,
    win_rate: 67.5,
    total_trades: 135,
  },
  {
    id: 'bot_012',
    name: 'Volatility Surfer',
    creator: 'Sofia Zurich',
    country: '🇨🇭',
    strategy: 'combined',
    rank: 12,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 430,
    profit_15d: 1750.50,
    profit_7d: 875.25,
    profit_24h: 125.04,
    win_rate: 64.0,
    total_trades: 130,
  },
  {
    id: 'bot_013',
    name: 'Bollinger Breaker',
    creator: 'Igor Sokolov',
    country: '🇷🇺',
    strategy: 'macd',
    rank: 13,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 450,
    profit_15d: 1680.20,
    profit_7d: 840.10,
    profit_24h: 120.15,
    win_rate: 69.2,
    total_trades: 128,
  },
  {
    id: 'bot_014',
    name: 'Fisher Predictor',
    creator: 'Hiroshi Sato',
    country: '🇯🇵',
    strategy: 'rsi',
    rank: 14,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 410,
    profit_15d: 1620.40,
    profit_7d: 810.20,
    profit_24h: 115.74,
    win_rate: 72.5,
    total_trades: 125,
  },
  {
    id: 'bot_015',
    name: 'Arbitrage Prophet',
    creator: 'Abraham Levi',
    country: '🇮🇱',
    strategy: 'dca',
    rank: 15,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 380,
    profit_15d: 1540.60,
    profit_7d: 770.30,
    profit_24h: 110.04,
    win_rate: 70.8,
    total_trades: 122,
  },
  {
    id: 'bot_016',
    name: 'Quantum Analyzer',
    creator: 'Rafael Santos',
    country: '🇧🇷',
    strategy: 'combined',
    rank: 16,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 440,
    profit_15d: 1480.50,
    profit_7d: 740.25,
    profit_24h: 105.75,
    win_rate: 66.3,
    total_trades: 120,
  },
  {
    id: 'bot_017',
    name: 'Neural Network Trader',
    creator: 'Ming Li',
    country: '🇨🇳',
    strategy: 'grid',
    rank: 17,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 420,
    profit_15d: 1420.80,
    profit_7d: 710.40,
    profit_24h: 101.49,
    win_rate: 68.9,
    total_trades: 118,
  },
  {
    id: 'bot_018',
    name: 'Fib Retracement Bot',
    creator: 'Klaus Mueller',
    country: '🇨🇭',
    strategy: 'grid',
    rank: 18,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 400,
    profit_15d: 1360.25,
    profit_7d: 680.13,
    profit_24h: 97.18,
    win_rate: 65.5,
    total_trades: 115,
  },
  {
    id: 'bot_019',
    name: 'EMA Crossover Pro',
    creator: 'Anastasia Ivanova',
    country: '🇷🇺',
    strategy: 'macd',
    rank: 19,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 380,
    profit_15d: 1290.50,
    profit_7d: 645.25,
    profit_24h: 92.18,
    win_rate: 63.2,
    total_trades: 112,
  },
  {
    id: 'bot_020',
    name: 'Stochastic Master',
    creator: 'Akira Nakamura',
    country: '🇯🇵',
    strategy: 'rsi',
    rank: 20,
    medal: undefined,
    is_locked: true,
    is_on_fire: false,
    unlock_cost: 360,
    profit_15d: 1220.75,
    profit_7d: 610.38,
    profit_24h: 87.19,
    win_rate: 61.8,
    total_trades: 110,
  },
];

// ─── EA helpers (inline, sem importar EAMonitor) ───────────────────────────
function EABadge({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${className}`}>
      {children}
    </span>
  );
}
function SystemStateBadge({ state }: { state: string }) {
  const map: Record<string, string> = {
    IDLE: 'bg-slate-700/50 text-slate-300 border-slate-600/50',
    ACTIVE: 'bg-green-600/20 text-green-300 border-green-500/40',
    TRANSITION_STATE: 'bg-yellow-600/20 text-yellow-300 border-yellow-500/40',
    CLOSING_POSITIONS: 'bg-orange-600/20 text-orange-300 border-orange-500/40',
    SAFE_TO_SWITCH: 'bg-blue-600/20 text-blue-300 border-blue-500/40',
    ACTIVATING_NEW_STRATEGY: 'bg-purple-600/20 text-purple-300 border-purple-500/40',
  };
  return <EABadge className={map[state] ?? 'bg-slate-700/50 text-slate-300 border-slate-600/50'}>{stateLabel(state)}</EABadge>;
}
function AuditLevelBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    INFO: 'bg-blue-600/20 text-blue-300 border-blue-500/30',
    WARNING: 'bg-yellow-600/20 text-yellow-300 border-yellow-500/30',
    ERROR: 'bg-red-600/20 text-red-300 border-red-500/30',
    CRITICAL: 'bg-red-700/30 text-red-200 border-red-500/50',
    SUCCESS: 'bg-green-600/20 text-green-300 border-green-500/30',
  };
  return <EABadge className={map[(level ?? '').toUpperCase()] ?? 'bg-slate-600/20 text-slate-300 border-slate-500/30'}>{level ?? '—'}</EABadge>;
}
function EAMetricCard({ label, value, sub, icon: Icon, valueClass = 'text-white' }: {
  label: string; value: React.ReactNode; sub?: React.ReactNode; icon?: React.ElementType; valueClass?: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">{Icon && <Icon size={12} />}{label}</div>
      <div className={`text-xl font-bold ${valueClass}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}
function fmtTs(ts: string | null | undefined): string {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleString('pt-BR', { day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit' }); } catch { return ts; }
}
function fmtPnl(v: number | undefined | null): string {
  if (v == null) return '—'; const s = v >= 0 ? '+' : ''; return `${s}$${v.toFixed(2)}`;
}
// ────────────────────────────────────────────────────────────────────────────

export default function RobotsMarketplacePage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { profile, leveledUp, newLevel, unlockRobot } = useGamification();
  const [selectedRobot, setSelectedRobot] = React.useState<any>(null);
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [isLevelUpModalOpen, setIsLevelUpModalOpen] = React.useState(leveledUp);
  const [isRankingModalOpen, setIsRankingModalOpen] = React.useState(false);
  const [currentPeriod, setCurrentPeriod] = React.useState<'daily' | 'weekly' | 'monthly'>('monthly');
  const [topRobots, setTopRobots] = React.useState<any[]>([]);
  const [isLoadingRobots, setIsLoadingRobots] = React.useState(false);
  
  // ✅ NEW: Estados para UnlockRobotModal
  const [isUnlockModalOpen, setIsUnlockModalOpen] = React.useState(false);
  const [selectedRobotForUnlock, setSelectedRobotForUnlock] = React.useState<any>(null);
  const [justUnlocked, setJustUnlocked] = React.useState(false);

  // ✅ NEW: Estados para BotConfigModal (ativar robô)
  const [isBotConfigModalOpen, setIsBotConfigModalOpen] = React.useState(false);
  const [selectedBotForConfig, setSelectedBotForConfig] = React.useState<any>(null);

  // ── PEND-14: Marketplace performance + review states ────────────────────
  const [purchasePreview, setPurchasePreview] = React.useState<any>(null);
  const [performanceData, setPerformanceData] = React.useState<any>(null);
  const [loadingPerformance, setLoadingPerformance] = React.useState(false);
  const [isPerfModalOpen, setIsPerfModalOpen] = React.useState(false);
  const [perfModalRobot, setPerfModalRobot] = React.useState<any>(null);
  const [reviewForm, setReviewForm] = React.useState({ rating: 5, comment: '' });
  const [submittingReview, setSubmittingReview] = React.useState(false);
  const [reviewSubmitted, setReviewSubmitted] = React.useState(false);
  const [reviewRobotId, setReviewRobotId] = React.useState<string | null>(null);

  // ── EA Monitor states ───────────────────────────────────────────────────
  const [eaSystemState, setEaSystemState] = React.useState<SystemStateResponse | null>(null);
  const [eaTelemetry, setEaTelemetry] = React.useState<EATelemetry | null>(null);
  const [eaAuditLog, setEaAuditLog] = React.useState<AuditLogEntry[]>([]);
  const [eaLoading, setEaLoading] = React.useState(true);
  const [eaRefreshing, setEaRefreshing] = React.useState(false);
  const [eaError, setEaError] = React.useState<string | null>(null);
  const [eaActivating, setEaActivating] = React.useState<string | null>(null);
  const [eaDeactivating, setEaDeactivating] = React.useState(false);
  const [eaLastRefresh, setEaLastRefresh] = React.useState<Date | null>(null);

  /**
   * Sincroniza estado do modal de level up
   */
  React.useEffect(() => {
    setIsLevelUpModalOpen(leveledUp);
  }, [leveledUp]);

  // ── EA Monitor fetch ────────────────────────────────────────────────────
  const fetchEaAll = useCallback(async (silent = false) => {
    if (!silent) setEaLoading(true); else setEaRefreshing(true);
    setEaError(null);
    try {
      const [state, log] = await Promise.all([getSystemState(), getAuditLog(50)]);
      setEaSystemState(state);
      setEaAuditLog(log.entries ?? []);
      setEaLastRefresh(new Date());
    } catch (err) {
      setEaError(err instanceof Error ? err.message : 'Erro ao carregar EA');
    } finally {
      setEaLoading(false); setEaRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    fetchEaAll(false);
    const id = setInterval(() => fetchEaAll(true), 5000);
    return () => clearInterval(id);
  }, [fetchEaAll]);

  const handleEaActivate = async (stratId: string, name: string) => {
    if (eaActivating) return;
    setEaActivating(stratId);
    try {
      const res: ActivationResponse = await activateStrategy(stratId);
      if (res.success) {
        toast({ title: `✅ Estratégia Ativada`, description: `${name} foi ativada com sucesso.` });
        await fetchEaAll(true);
      } else {
        toast({ title: 'Falha na Ativação', description: res.message ?? 'Verifique o backend.', variant: 'destructive' });
      }
    } catch (err) {
      toast({ title: 'Erro de Conexão', description: err instanceof Error ? err.message : 'Verifique o backend.', variant: 'destructive' });
    } finally { setEaActivating(null); }
  };

  const handleEaDeactivate = async () => {
    if (eaDeactivating) return;
    setEaDeactivating(true);
    try {
      const res: ActivationResponse = await deactivateStrategy();
      if (res.success) {
        toast({ title: '⏹️ Sistema Desativado', description: res.message });
        setEaTelemetry(null);
        await fetchEaAll(true);
      } else {
        toast({ title: 'Falha na Desativação', description: res.message, variant: 'destructive' });
      }
    } catch (err) {
      toast({ title: 'Erro de Conexão', description: err instanceof Error ? err.message : 'Verifique o backend.', variant: 'destructive' });
    } finally { setEaDeactivating(false); }
  };

  const eaIsIdle = !eaSystemState || eaSystemState.system_state === 'IDLE';
  const eaInTransition = ['TRANSITION_STATE','CLOSING_POSITIONS','SAFE_TO_SWITCH','ACTIVATING_NEW_STRATEGY'].includes(eaSystemState?.system_state ?? '');
  const eaActiveStratId = eaSystemState?.active_strategy ?? null;

  /**
   * Busca robôs ranking pela API quando período muda
   */
  React.useEffect(() => {
    fetchTopRobotsByPeriod(currentPeriod);
  }, [currentPeriod]);

  /**
   * Busca top robôs de um período específico
   */
  const fetchTopRobotsByPeriod = async (period: 'daily' | 'weekly' | 'monthly') => {
    try {
      setIsLoadingRobots(true);
      
      const response = await fetch(
        `/api/gamification/robots/ranking-by-period?period=${period}&limit=10&sort_by=profit`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Erro ao buscar robôs: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.success && data.data) {
        // Transforma dados da API para o formato esperado
        const transformedRobots = data.data.map((robot: any) => ({
          id: robot.id,
          name: robot.name,
          creator: robot.creator,
          country: robot.country,
          strategy: robot.strategy,
          rank: robot.rank,
          medal: robot.medal,
          is_locked: !profile?.unlocked_robots?.includes(robot.id) ?? true,
          is_on_fire: robot.is_on_fire,
          unlock_cost: 500, // Default value
          profit_15d: robot.profit_15d,
          profit_7d: robot.profit_7d,
          profit_24h: robot.profit_24h,
          win_rate: robot.win_rate,
          total_trades: robot.active_traders,
        }));
        
        setTopRobots(transformedRobots);
      }
    } catch (error) {
      console.error('[RobotsMarketplace] Erro ao buscar top robôs:', error);
      // Fallback para dados mockados se API falhar
      setTopRobots(mockRobots.slice(0, 10));
    } finally {
      setIsLoadingRobots(false);
    }
  };

  /**
   * ✅ NEW: Abre modal de desbloqueio
   * @param robotId ID do robô a desbloquear
   */
  const handleUnlockClick = (robotId: string) => {
    const robot = topRobots.find((r) => r.id === robotId) || mockRobots.find((r) => r.id === robotId);
    if (robot) {
      setSelectedRobotForUnlock(robot);
      setIsUnlockModalOpen(true);
    }
  };

  /**
   * ✅ PEND-14: Confirma compra chamando marketplace API + hook legacy
   * @param robotId ID do robô
   */
  const handleConfirmUnlock = async (robotId: string) => {
    try {
      console.log('[RobotsMarketplace] Comprando robô:', robotId);

      // 1. Call marketplace purchase endpoint (PEND-14)
      let perfPreview: any = null;
      try {
        const purchaseRes = await apiCall(`/marketplace/robots/${robotId}/purchase`, { method: 'POST' });
        if (purchaseRes.ok) {
          const purchaseData = await purchaseRes.json();
          perfPreview = purchaseData.performance_preview ?? null;
          setPurchasePreview(perfPreview);
        }
      } catch {
        // non-fatal — marketplace endpoint unavailable, continue with legacy unlock
      }

      // 2. Legacy unlock (deducts TradePoints via gamification hook)
      const result = await unlockRobot(robotId);

      if (result !== null) {
        setIsUnlockModalOpen(false);
        setSelectedRobotForUnlock(null);
        setReviewRobotId(robotId);
        setReviewSubmitted(false);
        setJustUnlocked(true);
        setTimeout(() => setJustUnlocked(false), 4350);

        const robot = topRobots.find((r) => r.id === robotId) || mockRobots.find((r) => r.id === robotId);
        setPerfModalRobot(robot ?? null);
        setPerformanceData(perfPreview);

        if (perfPreview) {
          // Show performance + review modal
          setIsPerfModalOpen(true);
        } else {
          // Fallback: scroll to EA section
          setTimeout(() => {
            const el = document.getElementById('ea-monitor');
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 350);
          toast({
            title: '⬇️ Role para ativar o robô',
            description: 'Agora clique em Ativar no painel de Expert Advisors abaixo.',
            duration: 5000,
          });
        }
      }
    } catch (error) {
      console.error('[RobotsMarketplace] ❌ Erro ao comprar:', error);
      // Erro tratado no hook (toast mostrado)
    }
  };

  /**
   * PEND-14: Envia avaliação de robô comprado
   */
  const handleSubmitReview = async () => {
    if (!reviewRobotId || submittingReview || reviewSubmitted) return;
    setSubmittingReview(true);
    try {
      const res = await apiCall(`/marketplace/robots/${reviewRobotId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating: reviewForm.rating, comment: reviewForm.comment }),
      });
      if (res.ok) {
        setReviewSubmitted(true);
        toast({ title: '⭐ Avaliação enviada!', description: 'Obrigado pelo seu feedback.', duration: 3000 });
      } else {
        const err = await res.json().catch(() => ({}));
        toast({ title: 'Erro ao enviar avaliação', description: err.detail ?? 'Tente novamente.', variant: 'destructive' });
      }
    } catch {
      toast({ title: 'Erro de conexão', description: 'Verifique o backend.', variant: 'destructive' });
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleRobotInfo = async (robotId: string) => {
    const robot = topRobots.find((r) => r.id === robotId) || mockRobots.find((r) => r.id === robotId);
    if (robot) {
      setSelectedRobot(robot);
      setIsModalOpen(true);
      setReviewRobotId(robotId);
      setReviewSubmitted(false);
      setPerformanceData(null);
      // Fetch performance data for unlocked robots (PEND-14)
      const isUnlocked = profile?.unlocked_robots?.includes(robotId) ?? false;
      if (isUnlocked) {
        setLoadingPerformance(true);
        try {
          const res = await apiCall(`/marketplace/robots/${robotId}/performance`);
          if (res.ok) setPerformanceData(await res.json());
        } catch { /* non-fatal */ }
        finally { setLoadingPerformance(false); }
      }
    }
  };

  /**
   * ✅ NEW: Abre modal de configuração do robô (quando usuário clica "Ativar")
   */
  const handleActivateRobot = (robotId: string) => {
    if (localStorage.getItem('kucoin_connected') !== 'true') {
      toast({
        title: '⚠️ Credenciais KuCoin não configuradas',
        description: 'Configure suas credenciais KuCoin em Configurações antes de ativar um robô.',
        variant: 'destructive',
      });
    }
    const robot = topRobots.find((r) => r.id === robotId) || mockRobots.find((r) => r.id === robotId);
    if (robot) {
      // Fecha qualquer modal aberto antes
      setIsModalOpen(false);
      setIsUnlockModalOpen(false);
      setSelectedBotForConfig(robot);
      setIsBotConfigModalOpen(true);
    }
  };

  /**
   * Alterna período de ranking
   */
  const handlePeriodChange = (newPeriod: 'daily' | 'weekly' | 'monthly') => {
    setCurrentPeriod(newPeriod);
    setIsRankingModalOpen(false);
  };

  // Animações
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const gridVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.05,
      },
    },
  };

  return (
    <div className="min-h-screen bg-[#0B0E11] overflow-hidden">

      {/* Main Content */}
      <div className="relative z-10 p-6 md:p-8 space-y-12">
        {/* Header Section */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4"
        >
          {/* KuCoin institutional badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border backdrop-blur-sm" style={{ background: 'rgba(35,200,130,0.08)', borderColor: 'rgba(35,200,130,0.30)' }}>
            <span style={{ color: '#23C882' }} className="text-xs font-bold uppercase tracking-widest">🏆 Marketplace de Robôs</span>
            <span className="w-px h-3 bg-white/20" />
            <span className="text-xs text-slate-400">Arena de Lucros Pro</span>
          </div>

          <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-[1.2]">
            <span className="text-white">Um Exército de Robôs</span>
            <br />
            <span style={{ color: '#23C882' }}>
              Trabalhando por Você
            </span>
          </h1>

          <p className="text-base text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Acesse estratégias exclusivas, desbloqueie robôs de elite com{' '}
            <span style={{ color: '#23C882' }} className="font-semibold">TradePoints</span> e
            deixe o mercado trabalhar enquanto você vive.
          </p>

          <div className="flex flex-wrap justify-center gap-6 pt-2 text-xs text-slate-500">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#23C882' }} />
              Novos robôs adicionados regularmente
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#23C882' }} />
              Ranking atualizado em tempo real
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: '#23C882' }} />
              Estratégias multi-mercado
            </div>
          </div>
        </motion.div>

        {/* Game Profile Widget */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <GameProfileWidget />
        </motion.div>

        {/* Ranking Info Banner */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.35 }}
          className="max-w-4xl mx-auto p-4 rounded-lg flex items-center gap-3 border"
          style={{ background: 'rgba(22,26,30,0.60)', borderColor: 'rgba(35,200,130,0.25)' }}
        >
          <Clock className="w-5 h-5 flex-shrink-0" style={{ color: '#23C882' }} />
          <div className="text-sm text-slate-300">
            <span className="font-semibold" style={{ color: '#23C882' }}>Ranking atualiza a cada 15 dias</span>
            {' — Robôs são reordenados por performance.'}
          </div>
        </motion.div>

        {/* Available Slots Panel */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.37 }}
          className="max-w-4xl mx-auto"
        >
          <div className="relative rounded-xl overflow-hidden p-6" style={{ background: 'rgba(22,26,30,0.90)', border: '1px solid rgba(35,200,130,0.25)' }}>

            {/* Content */}
            <div className="relative flex items-center justify-between">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(35,200,130,0.12)', border: '1px solid rgba(35,200,130,0.25)' }}>
                    <Trophy className="w-4 h-4" style={{ color: '#23C882' }} />
                  </div>
                  <h3 className="text-xl font-bold" style={{ color: '#23C882' }}>
                    Seu Arsenal
                  </h3>
                </div>
                <p className="text-sm text-slate-300">
                  Você já desbloqueou {profile?.unlocked_robots?.length || 0} robôs — continue evoluindo!
                </p>
              </div>

              {/* Slot Visualization */}
              <div className="flex items-center gap-2">
                <div className="space-y-1">
                  <div className="flex gap-1">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <div
                        key={i}
                        className={`w-4 h-4 rounded-sm transition-all ${
                          i < (profile?.unlocked_robots?.length || 0)
                            ? ''
                            : 'bg-slate-800'
                        }`}
                        style={i < (profile?.unlocked_robots?.length || 0) ? { backgroundColor: '#23C882' } : {}}
                      />
                    ))}
                  </div>
                  <div className="flex gap-1">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <div
                        key={i + 10}
                        className={`w-4 h-4 rounded-sm transition-all ${
                          i + 10 < (profile?.unlocked_robots?.length || 0)
                            ? ''
                            : 'bg-slate-800'
                        }`}
                        style={i + 10 < (profile?.unlocked_robots?.length || 0) ? { backgroundColor: '#23C882' } : {}}
                      />
                    ))}
                  </div>
                </div>
                <div className="text-right ml-4">
                  <p className="text-3xl font-bold" style={{ color: '#23C882' }}>
                    {profile?.unlocked_robots?.length || 0}
                    <span className="text-sm text-slate-400 font-normal"> desbloqueados</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Mais robôs chegando em breve
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Top 3 Highlight Section + Dynamic Ranking */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="space-y-3"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(35,200,130,0.12)', border: '1px solid rgba(35,200,130,0.25)' }}>
                <Trophy className="w-4 h-4" style={{ color: '#23C882' }} />
              </div>
              <h2 className="text-xl font-bold text-white">
                {currentPeriod === 'daily' && 'Top 10 — Últimas 24h'}
                {currentPeriod === 'weekly' && 'Top 10 — Última Semana'}
                {currentPeriod === 'monthly' && 'Top 10 — Último Mês'}
              </h2>
            </div>

            {/* Period Filter Button — KuCoin green */}
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              onClick={() => setIsRankingModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all"
              style={{ background: 'rgba(35,200,130,0.10)', border: '1px solid rgba(35,200,130,0.35)', color: '#23C882' }}
            >
              <Filter className="w-4 h-4" />
              <span>Alterar Período</span>
            </motion.button>
          </div>

          {/* Dynamic Top 10 Grid */}
          {isLoadingRobots ? (
            <div className="flex justify-center items-center py-12">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.4, repeat: Infinity, ease: 'linear' }}
                className="w-8 h-8 rounded-full"
                style={{ border: '3px solid rgba(35,200,130,0.2)', borderTopColor: '#23C882' }}
              />
            </div>
          ) : (
            <motion.div
              variants={gridVariants}
              initial="hidden"
              animate="visible"
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4"
            >
              {(topRobots.length > 0 ? topRobots : mockRobots.slice(0, 10)).map((robot, i) => {
                // ✅ Verificar se está desbloqueado
                const isUnlocked = profile?.unlocked_robots?.includes(robot.id) ?? false;
                return (
                  <div key={robot.id} style={{ perspective: '1000px' }}>
                    <RobotMarketplaceCard
                      robot={{ ...robot, is_locked: !isUnlocked }}
                      onUnlock={() => handleUnlockClick(robot.id)}
                      onInfo={handleRobotInfo}
                      onActivate={handleActivateRobot}
                    />
                  </div>
                );
              })}
            </motion.div>
          )}
        </motion.div>

        {/* All Robots Grid */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="space-y-3"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(35,200,130,0.12)', border: '1px solid rgba(35,200,130,0.25)' }}>
              <BarChart3 className="w-4 h-4" style={{ color: '#23C882' }} />
            </div>
            <h2 className="text-xl font-bold text-white">
              Todos os Robôs Disponíveis
            </h2>
          </div>

          <motion.div
            variants={gridVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-4"
          >
            {mockRobots.map((robot, i) => {
              // ✅ Verificar se está desbloqueado
              const isUnlocked = profile?.unlocked_robots?.includes(robot.id) ?? false;
              return (
                <div key={robot.id} style={{ perspective: '1000px' }}>
                  <RobotMarketplaceCard
                    robot={{ ...robot, is_locked: !isUnlocked }}
                    onUnlock={() => handleUnlockClick(robot.id)}
                    onInfo={handleRobotInfo}
                    onActivate={handleActivateRobot}
                  />
                </div>
              );
            })}
          </motion.div>
        </motion.div>

        {/* ── EA Expert Advisors — hidden from end users ── */}
        {false && <motion.div
          id="ea-monitor"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.55 }}
          className={`space-y-6 rounded-2xl transition-all duration-700 ${justUnlocked ? 'ring-2 ring-green-400/60 ring-offset-2 ring-offset-slate-950 p-4' : ''}`}
        >
          {/* Header EA */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="rounded-xl border border-green-500/30 bg-green-600/20 p-3">
                <Monitor className="text-green-400" size={22} />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">EA — Expert Advisors</h2>
                <p className="text-sm text-slate-400">PRICEPRO SaaS — Painel de Controle em Tempo Real</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {eaLastRefresh && (
                <span className="text-xs text-slate-500">Atualizado: {eaLastRefresh.toLocaleTimeString('pt-BR')}</span>
              )}
              <button
                onClick={() => fetchEaAll(true)}
                disabled={eaRefreshing}
                className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
              >
                <RefreshCw size={14} className={eaRefreshing ? 'animate-spin' : ''} />
                Atualizar
              </button>
              <button
                onClick={handleEaDeactivate}
                disabled={eaIsIdle || eaDeactivating || eaInTransition}
                className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-600/20 px-4 py-2 text-sm text-red-300 transition hover:bg-red-600/30 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {eaDeactivating ? <Loader2 size={14} className="animate-spin" /> : <PowerOff size={14} />}
                Desativar Sistema
              </button>
            </div>
          </div>

          {/* Error banner */}
          {eaError && (
            <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-600/10 px-4 py-3 text-sm text-red-300">
              <AlertTriangle size={16} />{eaError}
            </div>
          )}

          {/* Estado do Sistema */}
          {!eaLoading && (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
              <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-300">
                <Zap size={15} className="text-yellow-400" />Estado do Sistema
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <EAMetricCard label="Estado FSM" value={eaSystemState ? <SystemStateBadge state={eaSystemState.system_state} /> : '—'} icon={Activity} />
                <EAMetricCard label="Estratégia Ativa" value={eaSystemState?.active_strategy ?? 'Nenhuma'} valueClass={eaSystemState?.active_strategy ? 'text-green-300' : 'text-slate-400'} icon={Layers} />
                <EAMetricCard label="Última Troca" value={fmtTs(eaSystemState?.last_switch)} icon={Clock} valueClass="text-sm text-slate-300" />
                <EAMetricCard label="Uptime do Gerenciador" value={formatUptime(eaSystemState?.uptime_seconds)} sub={eaSystemState?.uptime_seconds != null ? `${eaSystemState.uptime_seconds}s` : undefined} icon={Power} />
              </div>
            </div>
          )}

          {/* Telemetria */}
          {eaTelemetry ? (
            <div className="rounded-2xl border border-green-500/20 bg-white/5 p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-300">
                  <Activity size={15} className="text-green-400" />Telemetria — {eaTelemetry.strategy_id}
                </div>
                <div className="flex items-center gap-2 text-xs">
                  {Date.now() - new Date(eaTelemetry.heartbeat).getTime() < 15000 ? (
                    <span className="flex items-center gap-1 text-green-400"><Wifi size={12} /> Heartbeat OK</span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-400"><WifiOff size={12} /> Heartbeat Atrasado</span>
                  )}
                  <span className="text-slate-500">{fmtTs(eaTelemetry.heartbeat)}</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                <EAMetricCard label="Posições Abertas" value={eaTelemetry.open_positions} icon={BarChart3} valueClass={eaTelemetry.open_positions > 0 ? 'text-blue-300' : 'text-slate-400'} />
                <EAMetricCard label="Ordens Abertas" value={eaTelemetry.open_orders} icon={Layers} />
                <EAMetricCard label="PnL Flutuante" value={fmtPnl(eaTelemetry.unrealized_pnl)} icon={(eaTelemetry.unrealized_pnl ?? 0) >= 0 ? TrendingUp : TrendingDown} valueClass={(eaTelemetry.unrealized_pnl ?? 0) >= 0 ? 'text-green-300' : 'text-red-300'} />
                <EAMetricCard label="PnL Realizado Hoje" value={fmtPnl(eaTelemetry.realized_pnl_today)} icon={DollarSign} valueClass={(eaTelemetry.realized_pnl_today ?? 0) >= 0 ? 'text-green-300' : 'text-red-300'} />
                <EAMetricCard label="Saldo" value={`$${eaTelemetry.account_balance?.toFixed(2) ?? '—'}`} icon={DollarSign} />
                <EAMetricCard label="Equidade" value={`$${eaTelemetry.account_equity?.toFixed(2) ?? '—'}`} icon={DollarSign} />
              </div>
            </div>
          ) : !eaIsIdle && !eaLoading ? (
            <div className="flex items-center gap-3 rounded-2xl border border-yellow-500/20 bg-yellow-600/10 p-5 text-sm text-yellow-300">
              <Loader2 size={16} className="animate-spin" />Aguardando telemetria do EA ativo…
            </div>
          ) : null}

          {/* Estratégias EA */}
          <div>
            <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
              <Layers size={18} className="text-blue-400" />Estratégias EA Disponíveis
            </h3>
            {eaLoading ? (
              <div className="flex justify-center py-8"><Loader2 className="animate-spin text-green-400" size={32} /></div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {STRATEGY_REGISTRY.map((strat) => {
                  const isActive = eaActiveStratId === strat.id;
                  const isLoading = eaActivating === strat.id;
                  return (
                    <div key={strat.id} className={`relative overflow-hidden rounded-2xl border p-5 transition-all ${isActive ? 'border-green-500/40 bg-green-600/10' : 'border-white/10 bg-white/5 hover:border-white/20'}`}>
                      {isActive && (
                        <div className="absolute right-3 top-3">
                          <EABadge className="border-green-500/40 bg-green-600/20 text-green-300"><CheckCircle2 size={10} /> Ativo</EABadge>
                        </div>
                      )}
                      <div className="mb-3 flex items-center gap-2">
                        <span className={`rounded-md border px-2 py-0.5 text-xs font-bold ${timeframeColor(strat.timeframe)}`}>{strat.timeframe}</span>
                      </div>
                      <h4 className="mb-1 font-semibold leading-tight text-white">{strat.display_name}</h4>
                      <p className="mb-4 text-xs text-slate-400 line-clamp-3">{strat.description}</p>
                      <div className="mb-4 space-y-1 text-xs text-slate-500">
                        <div className="flex justify-between"><span>Magic</span><span className="font-mono text-slate-300">{strat.magic_number}</span></div>
                        <div className="flex justify-between"><span>Versão</span><span className="text-slate-300">v{strat.version}</span></div>
                        <div className="flex justify-between"><span>Shutdown timeout</span><span className="text-slate-300">{strat.safe_shutdown_timeout_s}s</span></div>
                      </div>
                      <button
                        onClick={() => {
                          // Mapeia a estratégia EA para o formato de robô do BotConfigModal
                          const robotFromEa = {
                            id: strat.id,
                            name: strat.display_name,
                            strategy: strat.timeframe?.toLowerCase() ?? 'grid',
                            creator: 'PRICEPRO SaaS',
                            country: '🤖',
                            win_rate: null,
                            profit_15d: null,
                          };
                          setSelectedBotForConfig(robotFromEa);
                          setIsBotConfigModalOpen(true);
                        }}
                        disabled={isActive || isLoading || !!eaActivating || eaInTransition}
                        className={`flex w-full items-center justify-center gap-2 rounded-xl py-2 text-sm font-semibold transition-all ${isActive ? 'cursor-default border border-green-500/30 bg-green-600/20 text-green-300' : 'border border-blue-500/30 bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 disabled:cursor-not-allowed disabled:opacity-40'}`}
                      >
                        {isLoading ? <Loader2 size={14} className="animate-spin" /> : isActive ? <CheckCircle2 size={14} /> : <ChevronRight size={14} />}
                        {isActive ? 'Ativo' : 'Ativar'}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Audit Log */}
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
              <Shield size={18} className="text-purple-400" />Audit Log
              <span className="ml-2 text-xs font-normal text-slate-500">Últimas {eaAuditLog.length} entradas</span>
            </h3>
            {eaAuditLog.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">Nenhum evento registrado.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-xs text-slate-500">
                      <th className="pb-2 pr-4">Timestamp</th><th className="pb-2 pr-4">Nível</th><th className="pb-2 pr-4">Evento</th><th className="pb-2">Detalhes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {eaAuditLog.map((entry, i) => (
                      <tr key={i} className="border-b border-white/5 transition hover:bg-white/5">
                        <td className="py-2 pr-4 font-mono text-xs text-slate-400">{fmtTs(entry.timestamp)}</td>
                        <td className="py-2 pr-4"><AuditLevelBadge level={entry.level ?? '—'} /></td>
                        <td className="py-2 pr-4 text-slate-200">{entry.event ?? '—'}</td>
                        <td className="py-2 max-w-[260px] truncate text-xs text-slate-500">{entry.data ? JSON.stringify(entry.data).slice(0, 120) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </motion.div>}

        {/* Footer Info */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="max-w-4xl mx-auto p-6 rounded-lg bg-gradient-to-r from-slate-900/60 to-slate-800/60 border border-slate-700/50 backdrop-blur-sm space-y-3"
        >
          <h3 className="font-bold text-white flex items-center gap-2">
            <Zap className="w-5 h-5 text-yellow-400" />
            Como Desbloquear Robôs?
          </h3>
          <ul className="text-sm text-slate-300 space-y-2">
            <li>
              <strong>Option 1:</strong> Ganhe{' '}
              <span className="text-yellow-400 font-bold">TradePoints</span> através de:
              <ul className="ml-4 mt-1 space-y-1">
                <li>• Adquirir planos de licença (START, PRO+, QUANT, BLACK)</li>
                <li>• Abrir o Daily Chest todos os dias (10-50 pts)</li>
                <li>• Alcançar milestones de trading e achievements</li>
              </ul>
            </li>
            <li className="mt-3">
              <strong>Option 2:</strong> Faça upgrade do seu plano para desbloquear robôs
              automaticamente
            </li>
            <li className="mt-3">
              <strong>Ganhe Automaticamente:</strong> Quando um robô estiver desbloqueado, ele
              trabalha 24/7 gerando lucro passivo
            </li>
          </ul>
        </motion.div>
      </div>

      {/* ✅ NEW: Bot Config Modal (configurações antes de ativar) */}
      <BotConfigModal
        robot={selectedBotForConfig}
        isOpen={isBotConfigModalOpen}
        onClose={() => {
          setIsBotConfigModalOpen(false);
          setSelectedBotForConfig(null);
        }}
      />

      {/* ── PEND-14: Performance + Review modal (shown after purchase) ── */}
      {isPerfModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-slate-900 shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
              <div>
                <h2 className="text-lg font-bold text-white">🎉 Robô Desbloqueado!</h2>
                <p className="text-xs text-slate-400">{perfModalRobot?.name ?? reviewRobotId}</p>
              </div>
              <button
                onClick={() => setIsPerfModalOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
              >
                <XIcon size={18} />
              </button>
            </div>

            <div className="space-y-5 overflow-y-auto p-6" style={{ maxHeight: '70vh' }}>
              {/* Performance preview */}
              {performanceData ? (
                <div>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
                    <BarChart3 size={14} className="text-cyan-400" /> Performance (30 dias)
                  </h3>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: 'Retorno Total', value: `${performanceData.total_return_pct?.toFixed(1) ?? '—'}%`, positive: (performanceData.total_return_pct ?? 0) >= 0 },
                      { label: 'Win Rate', value: `${performanceData.win_rate?.toFixed(1) ?? '—'}%`, positive: true },
                      { label: 'Max Drawdown', value: `${performanceData.max_drawdown_pct?.toFixed(1) ?? '—'}%`, positive: false },
                    ].map((m) => (
                      <div key={m.label} className="rounded-xl border border-white/10 bg-white/5 p-3 text-center">
                        <div className={`text-xl font-bold ${m.positive ? 'text-green-300' : 'text-red-300'}`}>{m.value}</div>
                        <div className="mt-0.5 text-xs text-slate-500">{m.label}</div>
                      </div>
                    ))}
                  </div>
                  {/* 7-day sparkline preview */}
                  {Array.isArray(performanceData.data_points) && performanceData.data_points.length > 0 && (
                    <div className="mt-3 overflow-x-auto rounded-xl border border-white/10 bg-white/5 p-3">
                      <div className="flex h-16 items-end gap-0.5">
                        {performanceData.data_points.slice(-14).map((pt: any, i: number) => {
                          const maxPnl = Math.max(...performanceData.data_points.map((p: any) => Math.abs(p.daily_pnl ?? 0)), 1);
                          const h = Math.max(4, Math.round(((Math.abs(pt.daily_pnl ?? 0)) / maxPnl) * 56));
                          return (
                            <div
                              key={i}
                              style={{ height: `${h}px` }}
                              className={`flex-1 rounded-t-sm ${(pt.daily_pnl ?? 0) >= 0 ? 'bg-green-400/60' : 'bg-red-400/60'}`}
                              title={`${pt.date}: $${(pt.daily_pnl ?? 0).toFixed(2)}`}
                            />
                          );
                        })}
                      </div>
                      <p className="mt-1 text-center text-xs text-slate-500">Últimos 14 dias</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center text-sm text-slate-400">
                  Performance detalhada disponível em breve.
                </div>
              )}

              {/* Review form */}
              <div className="rounded-xl border border-yellow-500/20 bg-yellow-600/5 p-4">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
                  <Star size={14} className="text-yellow-400" /> Avaliar este robô
                </h3>
                {reviewSubmitted ? (
                  <p className="text-center text-sm text-green-400">✅ Avaliação enviada! Obrigado.</p>
                ) : (
                  <div className="space-y-3">
                    {/* Star rating */}
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <button
                          key={s}
                          onClick={() => setReviewForm((f) => ({ ...f, rating: s }))}
                          className={`text-2xl transition-transform hover:scale-110 ${s <= reviewForm.rating ? 'text-yellow-400' : 'text-slate-600'}`}
                        >
                          ★
                        </button>
                      ))}
                      <span className="ml-2 text-sm text-slate-400">{reviewForm.rating}/5</span>
                    </div>
                    <textarea
                      rows={3}
                      placeholder="Compartilhe sua experiência com este robô…"
                      value={reviewForm.comment}
                      onChange={(e) => setReviewForm((f) => ({ ...f, comment: e.target.value }))}
                      className="w-full resize-none rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-yellow-500/50 focus:outline-none"
                    />
                    <button
                      onClick={handleSubmitReview}
                      disabled={submittingReview}
                      className="flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-600/20 px-4 py-2 text-sm text-yellow-300 hover:bg-yellow-600/30 disabled:opacity-40"
                    >
                      {submittingReview ? <Loader2 size={13} className="animate-spin" /> : <Star size={13} />}
                      Enviar Avaliação
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="flex justify-end border-t border-white/10 px-6 py-3">
              <button
                onClick={() => {
                  setIsPerfModalOpen(false);
                  setTimeout(() => {
                    const el = document.getElementById('ea-monitor');
                    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }, 200);
                }}
                className="rounded-lg border border-green-500/30 bg-green-600/20 px-4 py-2 text-sm text-green-300 hover:bg-green-600/30"
              >
                Ativar Robô ↓
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Locked Robot Modal */}
      <LockedRobotModal
        robot={selectedRobot}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        userTradePoints={profile?.trade_points || 0}
        onUpgradePlan={() => {
          // TODO: Navegar para página de planos
          console.log('Ir para planos');
        }}
      />

      {/* ✅ NEW: Unlock Robot Modal */}
      {selectedRobotForUnlock && (
        <UnlockRobotModal
          isOpen={isUnlockModalOpen}
          robotId={selectedRobotForUnlock.id}
          robotName={selectedRobotForUnlock.name}
          robotType={['bot_001', 'bot_002', 'bot_003'].includes(selectedRobotForUnlock.id) ? 'elite' : 'common'}
          unlockCost={selectedRobotForUnlock.unlock_cost}
          currentBalance={profile?.trade_points || 0}
          onConfirm={handleConfirmUnlock}
          onClose={() => {
            setIsUnlockModalOpen(false);
            setSelectedRobotForUnlock(null);
          }}
        />
      )}

      {/* ✅ NEW: Ranking Period Selector Modal */}
      <RankingPeriodSelector
        isOpen={isRankingModalOpen}
        onClose={() => setIsRankingModalOpen(false)}
        onSelectPeriod={handlePeriodChange}
        currentPeriod={currentPeriod}
      />

      {/* Level Up Modal */}
      {newLevel !== null && (
        <LevelUpModal
          isOpen={isLevelUpModalOpen}
          newLevel={newLevel}
          onClose={() => setIsLevelUpModalOpen(false)}
          autoClose={true}
          autoCloseDelay={5000}
        />
      )}
    </div>
  );
}
