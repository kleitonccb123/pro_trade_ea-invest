/**
 * MicroTransactionNotification — Componente de micro-transação
 * 
 * Exibido automaticamente quando o SaaS detecta que o usuário tentou
 * desbloquear um robô mas não tem saldo suficiente.
 * 
 * Features:
 * - 4 pacotes micro (100, 250, 500, 1500 pontos)
 * - Destaque do pacote ideal (cobre o deficit)
 * - Compra + desbloqueio em 1 clique
 * - Animação de entrada/saída
 * - Feedback visual de sucesso/erro
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, X, Sparkles, ArrowRight, Check, AlertTriangle } from 'lucide-react';

interface MicroBundle {
  bundle_id: string;
  name: string;
  emoji: string;
  price: number;
  currency: string;
  points: number;
  description: string;
  is_best_value: boolean;
  display_order: number;
}

interface MicroTransactionNotificationProps {
  /** Visível */
  visible: boolean;
  /** Pontos que faltam para desbloquear */
  shortage: number;
  /** Saldo atual do usuário */
  currentBalance: number;
  /** Custo do robô */
  unlockCost: number;
  /** ID do robô a desbloquear */
  robotId: string;
  /** Nome do robô */
  robotName?: string;
  /** Callback ao fechar */
  onClose: () => void;
  /** Callback ao completar compra+desbloqueio */
  onPurchaseAndUnlock?: (result: {
    success: boolean;
    pointsAdded: number;
    newBalance: number;
    robotUnlocked: boolean;
  }) => void;
}

const FALLBACK_BUNDLES: MicroBundle[] = [
  { bundle_id: 'micro_100', name: 'Boost Rápido', emoji: '⚡', price: 0.49, currency: 'USD', points: 100, description: 'Para quem precisa de pouquinho', is_best_value: false, display_order: 1 },
  { bundle_id: 'micro_250', name: 'Impulso', emoji: '🚀', price: 0.99, currency: 'USD', points: 250, description: 'O suficiente para desbloquear', is_best_value: false, display_order: 2 },
  { bundle_id: 'micro_500', name: 'Turbo Pack', emoji: '💎', price: 1.49, currency: 'USD', points: 500, description: 'Melhor custo-benefício micro', is_best_value: true, display_order: 3 },
  { bundle_id: 'micro_1500', name: 'Mega Boost', emoji: '🔥', price: 2.99, currency: 'USD', points: 1500, description: 'Desbloqueie qualquer robô Elite', is_best_value: false, display_order: 4 },
];

export const MicroTransactionNotification: React.FC<MicroTransactionNotificationProps> = ({
  visible,
  shortage,
  currentBalance,
  unlockCost,
  robotId,
  robotName,
  onClose,
  onPurchaseAndUnlock,
}) => {
  const [bundles, setBundles] = useState<MicroBundle[]>(FALLBACK_BUNDLES);
  const [selectedBundle, setSelectedBundle] = useState<string | null>(null);
  const [purchasing, setPurchasing] = useState(false);
  const [purchaseResult, setPurchaseResult] = useState<'success' | 'error' | null>(null);

  // Fetch micro bundles from API
  useEffect(() => {
    if (!visible) return;
    
    const fetchBundles = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/gamification/store/micro-bundles?shortage=${shortage}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          if (data.success && data.bundles?.length > 0) {
            setBundles(data.bundles);
          }
        }
      } catch (err) {
        console.warn('[MicroTransaction] Failed to fetch bundles, using fallback:', err);
      }
    };

    fetchBundles();
  }, [visible, shortage]);

  // Auto-select the cheapest bundle that covers the shortage
  useEffect(() => {
    if (!visible || bundles.length === 0) return;
    
    const sufficient = bundles
      .filter((b) => b.points >= shortage)
      .sort((a, b) => a.price - b.price);
    
    if (sufficient.length > 0) {
      setSelectedBundle(sufficient[0].bundle_id);
    } else {
      // If none covers the shortage, select the biggest
      const sorted = [...bundles].sort((a, b) => b.points - a.points);
      setSelectedBundle(sorted[0]?.bundle_id ?? null);
    }
  }, [visible, bundles, shortage]);

  const handlePurchase = useCallback(async () => {
    if (!selectedBundle || purchasing) return;
    
    setPurchasing(true);
    setPurchaseResult(null);
    
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/gamification/store/micro-purchase-and-unlock', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          bundle_id: selectedBundle,
          robot_id: robotId,
        }),
      });
      
      const data = await res.json();
      
      if (data.success || data.robot_unlocked) {
        setPurchaseResult('success');
        onPurchaseAndUnlock?.({
          success: true,
          pointsAdded: data.points_added || 0,
          newBalance: data.new_balance || 0,
          robotUnlocked: data.robot_unlocked || false,
        });
        // Auto-close after success
        setTimeout(() => onClose(), 2000);
      } else {
        setPurchaseResult('error');
        onPurchaseAndUnlock?.({
          success: false,
          pointsAdded: data.points_added || 0,
          newBalance: data.new_balance || 0,
          robotUnlocked: false,
        });
      }
    } catch (err) {
      console.error('[MicroTransaction] Purchase error:', err);
      setPurchaseResult('error');
    } finally {
      setPurchasing(false);
    }
  }, [selectedBundle, robotId, purchasing, onClose, onPurchaseAndUnlock]);

  const selectedBundleData = bundles.find((b) => b.bundle_id === selectedBundle);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 30, scale: 0.95 }}
          transition={{ type: 'spring', damping: 20, stiffness: 300 }}
          className="fixed bottom-6 right-6 z-[9999] w-[380px] max-w-[calc(100vw-2rem)]"
        >
          <div className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-yellow-500/40 rounded-2xl shadow-2xl shadow-yellow-500/10 overflow-hidden">
            {/* Header Glow Effect */}
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-yellow-400 via-amber-400 to-yellow-400" />

            {/* Close Button */}
            <button
              onClick={onClose}
              className="absolute top-3 right-3 p-1 rounded-full hover:bg-white/10 transition-colors z-10"
            >
              <X className="w-4 h-4 text-slate-400" />
            </button>

            {/* Header */}
            <div className="px-5 pt-5 pb-3">
              <div className="flex items-center gap-2 mb-2">
                <div className="p-2 rounded-lg bg-yellow-500/20">
                  <Zap className="w-5 h-5 text-yellow-400" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-yellow-200">
                    ⚡ Pontos Insuficientes
                  </h3>
                  <p className="text-xs text-slate-400">
                    Faltam <span className="text-yellow-300 font-semibold">{shortage.toLocaleString()}</span> pontos
                    {robotName ? ` para ${robotName}` : ''}
                  </p>
                </div>
              </div>

              {/* Balance Bar */}
              <div className="flex items-center justify-between text-xs text-slate-500 mt-2">
                <span>Saldo: <span className="text-yellow-300">{currentBalance.toLocaleString()}</span></span>
                <span>Custo: <span className="text-rose-300">{unlockCost.toLocaleString()}</span></span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-slate-700 mt-1 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-yellow-500 to-amber-400 rounded-full transition-all"
                  style={{ width: `${Math.min(100, (currentBalance / unlockCost) * 100)}%` }}
                />
              </div>
            </div>

            {/* Bundle Grid */}
            <div className="px-5 pb-2 grid grid-cols-2 gap-2">
              {bundles.map((bundle) => {
                const isSelected = selectedBundle === bundle.bundle_id;
                const coversShortage = bundle.points >= shortage;
                
                return (
                  <button
                    key={bundle.bundle_id}
                    onClick={() => setSelectedBundle(bundle.bundle_id)}
                    className={`
                      relative p-3 rounded-xl border transition-all text-left
                      ${isSelected
                        ? 'border-yellow-400 bg-yellow-500/10 ring-1 ring-yellow-400/50'
                        : 'border-slate-600/50 bg-slate-800/50 hover:border-slate-500'
                      }
                    `}
                  >
                    {coversShortage && (
                      <div className="absolute -top-1.5 -right-1.5">
                        <div className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center">
                          <Check className="w-2.5 h-2.5 text-white" />
                        </div>
                      </div>
                    )}

                    <div className="text-lg mb-0.5">{bundle.emoji}</div>
                    <div className="text-xs font-semibold text-slate-200">{bundle.name}</div>
                    <div className="text-sm font-bold text-yellow-300">
                      {bundle.points.toLocaleString()} pts
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      ${bundle.price.toFixed(2)}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Purchase Button */}
            <div className="px-5 pb-5 pt-2">
              {purchaseResult === 'success' ? (
                <div className="flex items-center justify-center gap-2 py-3 rounded-xl bg-emerald-500/20 border border-emerald-500/40">
                  <Sparkles className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm font-semibold text-emerald-300">
                    Desbloqueado com Sucesso! 🎉
                  </span>
                </div>
              ) : purchaseResult === 'error' ? (
                <div className="flex items-center justify-center gap-2 py-3 rounded-xl bg-rose-500/20 border border-rose-500/40">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span className="text-sm font-semibold text-rose-300">
                    Erro ao processar. Tente novamente.
                  </span>
                </div>
              ) : (
                <button
                  onClick={handlePurchase}
                  disabled={!selectedBundle || purchasing}
                  className={`
                    w-full flex items-center justify-center gap-2 py-3 rounded-xl
                    font-semibold text-sm transition-all
                    ${purchasing
                      ? 'bg-slate-600 text-slate-400 cursor-wait'
                      : 'bg-gradient-to-r from-yellow-500 to-amber-500 text-black hover:from-yellow-400 hover:to-amber-400 shadow-lg shadow-yellow-500/25'
                    }
                  `}
                >
                  {purchasing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                      Processando...
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      Comprar {selectedBundleData ? `+ ${selectedBundleData.points} pts` : ''} e Desbloquear
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              )}

              <p className="text-[10px] text-slate-500 text-center mt-2">
                Pagamento seguro • Pontos creditados instantaneamente
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default MicroTransactionNotification;
