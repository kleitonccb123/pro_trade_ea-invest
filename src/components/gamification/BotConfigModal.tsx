/**
 * BotConfigModal - Popup de configuração do robô antes de ativar
 *
 * Campos:
 * - Par de criptomoeda (BTC-USDT, ETH-USDT, etc.)
 * - Valor de investimento (USDT)
 * - Take Profit (%)
 * - Stop Loss (%)
 * - Timeframe (1m, 5m, 15m, 1h, 4h)
 * - Máx. trades por dia
 *
 * Ao clicar em "Ativar", salva config no localStorage e navega para /dashboard.
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  X,
  Zap,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Clock,
  BarChart2,
  Settings2,
  ChevronDown,
  Loader2,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogClose,
} from '@/components/ui/dialog';
import { apiCall } from '@/services/apiClient';

// ─── Tipos ───────────────────────────────────────────────────────────────────

export interface BotConfig {
  robotId: string;
  robotName: string;
  robotStrategy: string;
  pair: string;
  investmentUsdt: number;
  takeProfitPct: number;
  stopLossPct: number;
  timeframe: string;
  maxTradesPerDay: number;
  activatedAt: string; // ISO string
}

interface BotConfigModalProps {
  robot: {
    id: string;
    name: string;
    strategy: string;
    creator?: string;
    country?: string;
    win_rate?: number;
    profit_15d?: number;
  } | null;
  isOpen: boolean;
  onClose: () => void;
}

// ─── Constantes ──────────────────────────────────────────────────────────────

const PAIRS = [
  { label: 'BTC/USDT', value: 'BTC-USDT', icon: '₿' },
  { label: 'ETH/USDT', value: 'ETH-USDT', icon: 'Ξ' },
  { label: 'SOL/USDT', value: 'SOL-USDT', icon: '◎' },
  { label: 'BNB/USDT', value: 'BNB-USDT', icon: '⬡' },
  { label: 'XRP/USDT', value: 'XRP-USDT', icon: '✕' },
  { label: 'DOGE/USDT', value: 'DOGE-USDT', icon: 'Ð' },
  { label: 'ADA/USDT', value: 'ADA-USDT', icon: '◈' },
  { label: 'AVAX/USDT', value: 'AVAX-USDT', icon: '▲' },
  { label: 'MATIC/USDT', value: 'MATIC-USDT', icon: '◇' },
  { label: 'DOT/USDT', value: 'DOT-USDT', icon: '●' },
];

const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];

const STRATEGY_LABELS: Record<string, string> = {
  grid: '📊 GRID',
  rsi: '📈 RSI',
  macd: '🔄 MACD',
  dca: '💧 DCA',
  combined: '⚡ COMBINED',
};

// ─── Componente ──────────────────────────────────────────────────────────────

export const BotConfigModal: React.FC<BotConfigModalProps> = ({
  robot,
  isOpen,
  onClose,
}) => {
  const navigate = useNavigate();

  // Form state
  const [pair, setPair] = useState('BTC-USDT');
  const [investment, setInvestment] = useState<string>('100');
  const [takeProfit, setTakeProfit] = useState<string>('3');
  const [stopLoss, setStopLoss] = useState<string>('2');
  const [timeframe, setTimeframe] = useState('1h');
  const [maxTrades, setMaxTrades] = useState<string>('10');

  const [activating, setActivating] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  if (!robot) return null;

  // ── Validação ──────────────────────────────────────────────────────────────
  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    const inv = parseFloat(investment);
    const tp = parseFloat(takeProfit);
    const sl = parseFloat(stopLoss);
    const mt = parseInt(maxTrades, 10);

    if (!investment || isNaN(inv) || inv < 10) errs.investment = 'Mínimo de 10 USDT';
    if (inv > 100000) errs.investment = 'Máximo de 100.000 USDT';
    if (!takeProfit || isNaN(tp) || tp < 0.1) errs.takeProfit = 'Mínimo 0.1%';
    if (tp > 100) errs.takeProfit = 'Máximo 100%';
    if (!stopLoss || isNaN(sl) || sl < 0.1) errs.stopLoss = 'Mínimo 0.1%';
    if (sl > 100) errs.stopLoss = 'Máximo 100%';
    if (tp <= sl) errs.takeProfit = 'Take Profit deve ser maior que Stop Loss';
    if (!maxTrades || isNaN(mt) || mt < 1) errs.maxTrades = 'Mínimo 1 trade/dia';
    if (mt > 100) errs.maxTrades = 'Máximo 100 trades/dia';

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // ── Ativar ─────────────────────────────────────────────────────────────────
  const handleActivate = async () => {
    if (!validate()) return;

    setActivating(true);
    try {
      // ── 0. Verificar se credenciais KuCoin estão configuradas ────────
      const kuCoinConnected = localStorage.getItem('kucoin_connected') === 'true';
      if (!kuCoinConnected) {
        try {
          const credRes = await apiCall('/user/settings/exchanges');
          if (credRes.ok) {
            const creds = await credRes.json();
            const kucoin = creds.find((c: any) => c.exchange === 'kucoin' && c.connected);
            if (!kucoin) {
              setErrors({
                general: '⚠️ Configure suas credenciais KuCoin em Configurações antes de ativar um robô.',
              });
              setActivating(false);
              return;
            }
            localStorage.setItem('kucoin_connected', 'true');
          }
        } catch {
          // Falha de rede: avisa mas continua
          setErrors({ general: 'Não foi possível verificar credenciais. Continuando...' });
        }
      }

      const config: BotConfig = {
        robotId: robot.id,
        robotName: robot.name,
        robotStrategy: robot.strategy,
        pair,
        investmentUsdt: parseFloat(investment),
        takeProfitPct: parseFloat(takeProfit),
        stopLossPct: parseFloat(stopLoss),
        timeframe,
        maxTradesPerDay: parseInt(maxTrades, 10),
        activatedAt: new Date().toISOString(),
      };

      // ── 1. Criar bot no backend ──────────────────────────────────────
      let botId: string | null = null;
      try {
        const res = await apiCall('/bots', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: config.robotName,
            symbol: config.pair,       // ex: "BTC-USDT"
            config: {
              investment_usdt: config.investmentUsdt,
              take_profit_pct: config.takeProfitPct,
              stop_loss_pct: config.stopLossPct,
              timeframe: config.timeframe,
              max_trades_per_day: config.maxTradesPerDay,
              strategy: config.robotStrategy,
            },
          }),
        });

        if (res.ok) {
          const data = await res.json();
          botId = data.id;
          localStorage.setItem('active_bot_id', botId!);
          console.log('[BotConfig] Bot criado no backend:', botId);
        } else {
          // 402 = sem créditos, 403 = plano insuficiente
          const err = await res.json().catch(() => ({}));
          const msg = err?.detail?.message || err?.detail || 'Erro ao criar bot no servidor';
          setErrors({ general: `Backend: ${msg}` });
          return;
        }
      } catch (networkErr) {
        // Falha de rede: salva só no localStorage e avisa
        console.warn('[BotConfig] Backend indisponível, modo offline:', networkErr);
        setErrors({ general: 'Servidor offline. O robô será registrado localmente.' });
        // Não retorna — continua com modo offline
      }

      // ── 3. Iniciar execução do bot ───────────────────────────────────
      if (botId) {
        try {
          const startRes = await apiCall(`/bots/${botId}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // Sem body = modo simulação (sem credenciais KuCoin reais)
            // Para modo live, passar as credenciais KuCoin aqui
          });

          if (!startRes.ok) {
            const startErr = await startRes.json().catch(() => ({}));
            // 402 = sem créditos de ativação
            if (startRes.status === 402) {
              setErrors({
                general: `Sem créditos de ativação. Restantes: ${startErr?.detail?.credits_remaining ?? 0}`,
              });
              return;
            }
            console.warn('[BotConfig] Start falhou:', startErr);
          } else {
            const startData = await startRes.json();
            localStorage.setItem('active_instance_id', startData.instance_id || '');
            console.log('[BotConfig] Bot iniciado:', startData);
          }
        } catch (e) {
          console.warn('[BotConfig] Erro ao iniciar bot (modo offline):', e);
        }
      }

      // ── 2. Persistir config localmente ──────────────────────────────
      localStorage.setItem('active_bot_config', JSON.stringify(config));

      await new Promise((r) => setTimeout(r, 600));

      onClose();
      navigate('/dashboard');
    } finally {
      setActivating(false);
    }
  };

  // ── Input helper ───────────────────────────────────────────────────────────
  const Field = ({
    label,
    icon: Icon,
    id,
    value,
    onChange,
    type = 'number',
    min,
    max,
    step,
    suffix,
    error,
    placeholder,
  }: {
    label: string;
    icon: React.ElementType;
    id: string;
    value: string;
    onChange: (v: string) => void;
    type?: string;
    min?: string;
    max?: string;
    step?: string;
    suffix?: string;
    error?: string;
    placeholder?: string;
  }) => (
    <div className="space-y-1.5">
      <label htmlFor={id} className="flex items-center gap-1.5 text-sm font-semibold text-slate-300">
        <Icon className="w-4 h-4 text-slate-400" />
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          min={min}
          max={max}
          step={step}
          placeholder={placeholder}
          className={`w-full rounded-lg border bg-slate-800/60 px-4 py-2.5 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 transition-all ${
            error
              ? 'border-rose-500/60 focus:ring-rose-500/30'
              : 'border-slate-700/60 focus:ring-emerald-500/30 focus:border-emerald-500/60'
          } ${suffix ? 'pr-14' : ''}`}
        />
        {suffix && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold text-slate-400">
            {suffix}
          </span>
        )}
      </div>
      {error && (
        <p className="flex items-center gap-1 text-xs text-rose-400">
          <AlertTriangle className="w-3 h-3" />
          {error}
        </p>
      )}
    </div>
  );

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 border border-emerald-500/20 shadow-[0_0_60px_-12px_rgba(52,211,153,0.25)] p-0">
        <DialogClose className="absolute right-4 top-4 z-10 text-slate-400 hover:text-white transition-colors">
          <X className="w-5 h-5" />
        </DialogClose>

        <div className="p-6 space-y-5">
          {/* ── Header ─────────────────────────────────────────────────────── */}
          <div className="flex items-start gap-4 pb-4 border-b border-slate-700/50">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 flex items-center justify-center shadow-lg shadow-emerald-500/30 flex-shrink-0">
              <Settings2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white leading-tight">{robot.name}</h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                  {STRATEGY_LABELS[robot.strategy] ?? robot.strategy.toUpperCase()}
                </span>
                {robot.creator && (
                  <span className="text-xs text-slate-400">
                    {robot.country} {robot.creator}
                  </span>
                )}
              </div>
              {robot.win_rate != null && (
                <p className="text-xs text-slate-500 mt-1">
                  Win Rate: <span className="text-emerald-400 font-semibold">{robot.win_rate}%</span>
                  {robot.profit_15d != null && (
                    <> &nbsp;·&nbsp; Lucro 15D: <span className="text-emerald-400 font-semibold">${robot.profit_15d.toFixed(0)}</span></>
                  )}
                </p>
              )}
            </div>
          </div>

          {/* ── Aviso ──────────────────────────────────────────────────────── */}
          <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-200/80">
              Configure corretamente o <strong>Take Profit</strong> e o <strong>Stop Loss</strong> antes de ativar.
              O robô abrirá operações automaticamente via KuCoin.
            </p>
          </div>

          {/* ── Par de criptomoeda ─────────────────────────────────────────── */}
          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-sm font-semibold text-slate-300">
              <BarChart2 className="w-4 h-4 text-slate-400" />
              Par de Criptomoeda
            </label>
            <div className="relative">
              <select
                value={pair}
                onChange={(e) => setPair(e.target.value)}
                className="w-full appearance-none rounded-lg border border-slate-700/60 bg-slate-800/60 px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500/60 transition-all pr-10"
              >
                {PAIRS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.icon}  {p.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* ── Valor de Investimento ─────────────────────────────────────── */}
          <Field
            id="investment"
            label="Valor de Investimento"
            icon={DollarSign}
            value={investment}
            onChange={(v) => { setInvestment(v); setErrors((e) => ({ ...e, investment: '' })); }}
            min="10"
            max="100000"
            step="10"
            suffix="USDT"
            error={errors.investment}
            placeholder="Ex: 100"
          />

          {/* ── TP / SL lado a lado ───────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-4">
            <Field
              id="takeProfit"
              label="Take Profit"
              icon={TrendingUp}
              value={takeProfit}
              onChange={(v) => { setTakeProfit(v); setErrors((e) => ({ ...e, takeProfit: '' })); }}
              min="0.1"
              max="100"
              step="0.1"
              suffix="%"
              error={errors.takeProfit}
              placeholder="Ex: 3"
            />
            <Field
              id="stopLoss"
              label="Stop Loss"
              icon={TrendingDown}
              value={stopLoss}
              onChange={(v) => { setStopLoss(v); setErrors((e) => ({ ...e, stopLoss: '' })); }}
              min="0.1"
              max="100"
              step="0.1"
              suffix="%"
              error={errors.stopLoss}
              placeholder="Ex: 2"
            />
          </div>

          {/* ── Timeframe ─────────────────────────────────────────────────── */}
          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-sm font-semibold text-slate-300">
              <Clock className="w-4 h-4 text-slate-400" />
              Timeframe
            </label>
            <div className="flex flex-wrap gap-2">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${
                    timeframe === tf
                      ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300 shadow-sm shadow-emerald-500/20'
                      : 'bg-slate-800/50 border-slate-700/50 text-slate-400 hover:border-slate-600 hover:text-slate-300'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* ── Máx. Trades / Dia ─────────────────────────────────────────── */}
          <Field
            id="maxTrades"
            label="Máx. Trades por Dia"
            icon={BarChart2}
            value={maxTrades}
            onChange={(v) => { setMaxTrades(v); setErrors((e) => ({ ...e, maxTrades: '' })); }}
            min="1"
            max="100"
            step="1"
            error={errors.maxTrades}
            placeholder="Ex: 10"
          />

          {/* ── Resumo ────────────────────────────────────────────────────── */}
          <div className="rounded-lg bg-slate-800/40 border border-slate-700/40 p-4 space-y-2 text-xs">
            <p className="font-semibold text-slate-300 mb-2">Resumo da Configuração</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-slate-400">
              <span>Par:</span><span className="text-white font-mono">{pair}</span>
              <span>Investimento:</span><span className="text-emerald-400 font-mono">{investment || '—'} USDT</span>
              <span>Take Profit:</span><span className="text-emerald-400 font-mono">{takeProfit || '—'}%</span>
              <span>Stop Loss:</span><span className="text-rose-400 font-mono">{stopLoss || '—'}%</span>
              <span>Timeframe:</span><span className="text-white font-mono">{timeframe}</span>
              <span>Máx. Trades/dia:</span><span className="text-white font-mono">{maxTrades || '—'}</span>
            </div>
          </div>

          {/* ── Erro geral ───────────────────────────────────────────────── */}
          {errors.general && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-950/40 border border-yellow-500/30 text-sm text-yellow-300">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              {errors.general}
            </div>
          )}

          {/* ── Botões de ação ────────────────────────────────────────────── */}
          <div className="flex gap-3 pt-1">
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-xl border border-slate-700 bg-slate-800/50 text-slate-300 font-semibold hover:bg-slate-700/50 transition-all text-sm"
            >
              Cancelar
            </button>
            <motion.button
              whileHover={{ scale: activating ? 1 : 1.02 }}
              whileTap={{ scale: activating ? 1 : 0.98 }}
              onClick={handleActivate}
              disabled={activating}
              className="flex-[2] py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-400 hover:to-green-500 text-slate-950 font-black shadow-lg shadow-emerald-500/30 disabled:opacity-70 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 text-sm"
            >
              {activating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Ativando…
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Ativar e ir para o Dashboard
                </>
              )}
            </motion.button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default BotConfigModal;
