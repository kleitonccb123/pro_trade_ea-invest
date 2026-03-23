import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  Activity,
  Square,
  TrendingUp,
  Target,
  Zap,
  BarChart3,
} from 'lucide-react';
import { Robot } from '@/types/robot';

interface ActiveRobotModalProps {
  isOpen: boolean;
  onClose: () => void;
  robot: Robot | null;
  onUpdateRobot: (robot: Robot) => void;
  onStop: () => void;
}

export function ActiveRobotModal({ isOpen, onClose, robot, onUpdateRobot, onStop }: ActiveRobotModalProps) {
  const [config, setConfig] = useState({
    amount: robot?.amount || 1000,
    stopLoss: robot?.stopLoss || 10,
    takeProfit: robot?.takeProfit || 10,
    maxTrades: 5,
    riskLevel: robot?.riskLevel || 'medium'
  });

  // Dados simulados para o gráfico
  const chartData = [
    { time: '00h', value: 1000 },
    { time: '04h', value: 1250 },
    { time: '08h', value: 1100 },
    { time: '12h', value: 1450 },
    { time: '16h', value: 1320 },
    { time: '20h', value: 1580 },
  ];

  useEffect(() => {
    if (!robot) return;
    
    setConfig(prev => ({
      ...prev,
      amount: robot.amount || 1000,
      stopLoss: robot.stopLoss || 10,
      takeProfit: robot.takeProfit || 10,
      riskLevel: robot.riskLevel || 'medium'
    }));
  }, [robot, isOpen]);

  if (!robot) return null;

  const handleConfigSave = () => {
    if (onUpdateRobot) {
      onUpdateRobot({
        ...robot,
        amount: config.amount,
        stopLoss: config.stopLoss,
        takeProfit: config.takeProfit,
        riskLevel: config.riskLevel as 'low' | 'medium' | 'high'
      });
    }
  };

  const handleStop = () => {
    onStop();
    onClose();
  };

  // Calcular lucro
  const profit = robot.profit || 2547;
  const maxValue = Math.max(...chartData.map(d => d.value));
  const minValue = Math.min(...chartData.map(d => d.value));

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-sm max-h-[75vh] overflow-hidden p-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 border border-slate-700/50 shadow-2xl rounded-lg">
        
        {/* ========== HEADER COM PROFUNDIDADE ========== */}
        <div className="relative overflow-hidden bg-gradient-to-r from-slate-800 to-slate-900">
          {/* Efeito de fundo */}
          <div className="absolute inset-0 opacity-30">
            <div className="absolute top-0 right-0 w-40 h-40 bg-primary/20 blur-3xl rounded-full" />
          </div>
          
          <DialogHeader className="relative border-b border-slate-700/50 px-4 py-3 flex-row items-center justify-between space-y-0">
            <div className="flex items-center gap-2.5 flex-1 min-w-0">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-primary to-accent rounded opacity-75 blur" />
                <div className="relative w-8 h-8 rounded bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                  <Activity className="w-4 h-4 text-white" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <DialogTitle className="text-sm font-bold text-white">{robot.name}</DialogTitle>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="success" className="h-5 px-2 text-xs bg-emerald-500/30 text-emerald-300 border-emerald-500/50 animate-pulse">
                    <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full mr-1" />
                    Ativo
                  </Badge>
                  <span className="text-xs text-slate-400">{robot.pair}</span>
                </div>
              </div>
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleStop} 
              className="h-8 px-2.5 text-xs hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded transition-all"
            >
              <Square className="w-3.5 h-3.5" />
            </Button>
          </DialogHeader>
        </div>

        {/* ========== CONTENT COM SCROLL ========== */}
        <div className="overflow-y-auto px-4 py-3" style={{ maxHeight: 'calc(75vh - 70px)' }}>
          
          {/* ========== SEÇÃO 1: KPIs COM PROFUNDIDADE ========== */}
          <div className="mb-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-primary" />
              Performance
            </h3>
            
            <div className="grid grid-cols-2 gap-2">
              {/* Card Lucro */}
              <div className="group relative overflow-hidden rounded-lg bg-gradient-to-br from-slate-800/60 to-slate-900/60 border border-emerald-500/20 p-3 hover:border-emerald-500/40 transition-all">
                <div className="absolute inset-0 opacity-0 group-hover:opacity-10 bg-gradient-to-br from-emerald-500 to-transparent transition-opacity" />
                <div className="relative">
                  <div className="text-xs text-slate-400 mb-1">Lucro Hoje</div>
                  <div className="text-lg font-bold text-emerald-400">+${profit.toFixed(0)}</div>
                  <div className="text-xs text-emerald-500/70 mt-1">+{robot.profit}%</div>
                </div>
              </div>

              {/* Card Taxa */}
              <div className="group relative overflow-hidden rounded-lg bg-gradient-to-br from-slate-800/60 to-slate-900/60 border border-cyan-500/20 p-3 hover:border-cyan-500/40 transition-all">
                <div className="absolute inset-0 opacity-0 group-hover:opacity-10 bg-gradient-to-br from-cyan-500 to-transparent transition-opacity" />
                <div className="relative">
                  <div className="text-xs text-slate-400 mb-1">Win Rate</div>
                  <div className="text-lg font-bold text-cyan-400">{robot.winRate}%</div>
                  <div className="text-xs text-cyan-500/70 mt-1">de acerto</div>
                </div>
              </div>

              {/* Card Ops */}
              <div className="group relative overflow-hidden rounded-lg bg-gradient-to-br from-slate-800/60 to-slate-900/60 border border-blue-500/20 p-3 hover:border-blue-500/40 transition-all">
                <div className="absolute inset-0 opacity-0 group-hover:opacity-10 bg-gradient-to-br from-blue-500 to-transparent transition-opacity" />
                <div className="relative">
                  <div className="text-xs text-slate-400 mb-1">Operações</div>
                  <div className="text-lg font-bold text-blue-400">{robot.trades}</div>
                  <div className="text-xs text-blue-500/70 mt-1">hoje</div>
                </div>
              </div>

              {/* Card Drawdown */}
              <div className="group relative overflow-hidden rounded-lg bg-gradient-to-br from-slate-800/60 to-slate-900/60 border border-amber-500/20 p-3 hover:border-amber-500/40 transition-all">
                <div className="absolute inset-0 opacity-0 group-hover:opacity-10 bg-gradient-to-br from-amber-500 to-transparent transition-opacity" />
                <div className="relative">
                  <div className="text-xs text-slate-400 mb-1">Drawdown</div>
                  <div className="text-lg font-bold text-amber-400">{robot.maxDrawdown?.toFixed(1) || '0'}%</div>
                  <div className="text-xs text-amber-500/70 mt-1">máximo</div>
                </div>
              </div>
            </div>
          </div>

          {/* ========== SEÇÃO 2: MINI GRÁFICO ========== */}
          <div className="mb-4 p-3 rounded-lg bg-gradient-to-br from-slate-800/40 to-slate-900/40 border border-slate-700/50">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 mb-2">
              <BarChart3 className="w-3.5 h-3.5 text-primary" />
              Evolução
            </h3>
            
            {/* Mini Gráfico em ASCII Art */}
            <div className="flex items-end justify-between h-16 gap-1 bg-slate-900/50 rounded p-2 border border-slate-700/30">
              {chartData.map((point, idx) => {
                const height = ((point.value - minValue) / (maxValue - minValue)) * 100;
                return (
                  <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                    <div 
                      className="w-full bg-gradient-to-t from-primary/80 to-primary rounded-sm transition-all hover:from-primary to-primary/60"
                      style={{ height: `${height}%`, minHeight: '4px' }}
                      title={`${point.time}: $${point.value}`}
                    />
                    <span className="text-xs text-slate-500">{point.time}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ========== SEÇÃO 3: CONFIGURAÇÕES ========== */}
          <div className="mb-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-primary" />
              Configuração
            </h3>
            
            <div className="grid grid-cols-2 gap-2">
              <div className="group">
                <Label className="text-xs text-slate-400 block mb-1 font-medium">Capital</Label>
                <Input
                  type="number"
                  value={config.amount}
                  onChange={(e) => setConfig(prev => ({ ...prev, amount: Number(e.target.value) }))}
                  className="h-7 text-xs bg-gradient-to-b from-slate-700/30 to-slate-800/30 border border-slate-600/40 text-white placeholder-slate-500 focus:border-primary/50 focus:ring-0 transition-colors rounded"
                />
              </div>

              <div className="group">
                <Label className="text-xs text-slate-400 block mb-1 font-medium">Stop Loss %</Label>
                <Input
                  type="number"
                  value={config.stopLoss}
                  onChange={(e) => setConfig(prev => ({ ...prev, stopLoss: Number(e.target.value) }))}
                  className="h-7 text-xs bg-gradient-to-b from-slate-700/30 to-slate-800/30 border border-slate-600/40 text-white placeholder-slate-500 focus:border-primary/50 focus:ring-0 transition-colors rounded"
                />
              </div>

              <div className="group">
                <Label className="text-xs text-slate-400 block mb-1 font-medium">Take Profit %</Label>
                <Input
                  type="number"
                  value={config.takeProfit}
                  onChange={(e) => setConfig(prev => ({ ...prev, takeProfit: Number(e.target.value) }))}
                  className="h-7 text-xs bg-gradient-to-b from-slate-700/30 to-slate-800/30 border border-slate-600/40 text-white placeholder-slate-500 focus:border-primary/50 focus:ring-0 transition-colors rounded"
                />
              </div>

              <div className="group">
                <Label className="text-xs text-slate-400 block mb-1 font-medium">Max Operações</Label>
                <Input
                  type="number"
                  value={config.maxTrades}
                  onChange={(e) => setConfig(prev => ({ ...prev, maxTrades: Number(e.target.value) }))}
                  min="1"
                  max="10"
                  className="h-7 text-xs bg-gradient-to-b from-slate-700/30 to-slate-800/30 border border-slate-600/40 text-white placeholder-slate-500 focus:border-primary/50 focus:ring-0 transition-colors rounded"
                />
              </div>
            </div>
          </div>

          {/* ========== SEÇÃO 4: STATUS ========== */}
          <div className="relative overflow-hidden rounded-lg bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border border-cyan-500/30 p-2.5">
            <div className="absolute inset-0 opacity-20">
              <div className="absolute -left-8 -top-8 w-16 h-16 bg-cyan-500 blur-2xl rounded-full" />
            </div>
            <div className="relative flex items-center justify-center gap-2">
              <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
              <span className="text-xs font-medium text-cyan-300">Sistema em Operação</span>
              <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
            </div>
          </div>
        </div>

        {/* ========== FOOTER ========== */}
        <div className="border-t border-slate-700/30 px-4 py-2.5 bg-gradient-to-r from-slate-900/50 to-slate-900/30 flex justify-end gap-2">
          <Button 
            variant="outline" 
            onClick={onClose} 
            className="h-7 text-xs px-3 border-slate-600/50 hover:bg-slate-700/50 hover:border-slate-500/50 transition-all rounded"
          >
            Fechar
          </Button>
          <Button 
            onClick={handleConfigSave} 
            className="h-7 text-xs px-3 bg-gradient-to-r from-primary to-accent hover:shadow-lg hover:shadow-primary/50 transition-all rounded text-white font-medium"
          >
            <Target className="w-3 h-3 mr-1" />
            Salvar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}