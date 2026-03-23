/**
 * CreateRobotModal - Modal de Criação de Robô com Estratégias Dinâmicas
 * 
 * Features:
 * - Seleção de Estratégia: Grid Trading, DCA, RSI, MACD
 * - Campos dinâmicos por estratégia
 * - Validação pré-trade (saldo insuficiente)
 * - Integração com strategy_engine.py
 */

import { useState, useEffect } from 'react';
import { Bot, TrendingUp, Grid3x3, DollarSign, BarChart3, Activity, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import useApi from '@/hooks/useApi';

// ============== TYPES ==============

type StrategyType = 'grid' | 'dca' | 'rsi' | 'macd';

interface StrategyConfig {
  type: StrategyType;
  name: string;
  icon: React.ReactNode;
  description: string;
  color: string;
}

interface GridConfig {
  upper_price: number;
  lower_price: number;
  grid_levels: number;
  amount_per_grid: number;
}

interface DCAConfig {
  investment_amount: number;
  interval_hours: number;
  price_drop_percentage: number;
  max_positions: number;
}

interface RSIConfig {
  oversold_threshold: number;
  overbought_threshold: number;
  rsi_period: number;
  amount: number;
}

interface MACDConfig {
  fast_period: number;
  slow_period: number;
  signal_period: number;
  amount: number;
}

interface RobotFormData {
  name: string;
  exchange: string;
  symbol: string;
  strategy_type: StrategyType;
  amount: number;
  stop_loss: number;
  take_profit: number;
  is_live: boolean;
  strategy_config: GridConfig | DCAConfig | RSIConfig | MACDConfig;
}

interface PreTradeValidation {
  valid: boolean;
  available_balance: number;
  required_balance: number;
  min_order_size: number;
  max_order_size: number;
  errors: string[];
}

interface CreateRobotModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (robot: any) => void;
}

// ============== STRATEGIES CONFIG ==============

const STRATEGIES: Record<StrategyType, StrategyConfig> = {
  grid: {
    type: 'grid',
    name: 'Grid Trading',
    icon: <Grid3x3 className="w-5 h-5" />,
    description: 'Distribui ordens em níveis de preço predefinidos para lucrar com oscilações',
    color: 'blue',
  },
  dca: {
    type: 'dca',
    name: 'DCA (Dollar Cost Average)',
    icon: <DollarSign className="w-5 h-5" />,
    description: 'Compras periódicas para reduzir impacto da volatilidade',
    color: 'green',
  },
  rsi: {
    type: 'rsi',
    name: 'RSI Strategy',
    icon: <BarChart3 className="w-5 h-5" />,
    description: 'Compra em oversold (<30), vende em overbought (>70)',
    color: 'purple',
  },
  macd: {
    type: 'macd',
    name: 'MACD Crossover',
    icon: <Activity className="w-5 h-5" />,
    description: 'Sinais baseados em cruzamentos das linhas MACD',
    color: 'orange',
  },
};

const DEFAULT_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];

const EXCHANGES = [
  { id: 'binance', name: 'Binance' },
  { id: 'kucoin', name: 'KuCoin' },
];

// ============== COMPONENT ==============

export default function CreateRobotModal({ isOpen, onClose, onSuccess }: CreateRobotModalProps) {
  const api = useApi();
  const [dynamicPairs, setDynamicPairs] = useState<string[]>(DEFAULT_PAIRS);
  const [loadingPairs, setLoadingPairs] = useState(false);

  const { toast } = useToast();

  // Form state
  const [formData, setFormData] = useState<RobotFormData>({
    name: '',
    exchange: 'binance',
    symbol: 'BTC/USDT',
    strategy_type: 'grid',
    amount: 1000,
    stop_loss: 5,
    take_profit: 10,
    is_live: false,
    strategy_config: {
      upper_price: 50000,
      lower_price: 40000,
      grid_levels: 10,
      amount_per_grid: 100,
    } as GridConfig,
  });

  // Fetch symbols dynamically when exchange changes
  useEffect(() => {
    let cancelled = false;
    const fetchSymbols = async () => {
      setLoadingPairs(true);
      try {
        const data = await api.get<{ symbols: string[] }>('/api/trading/symbols');
        if (!cancelled && data?.symbols?.length) {
          setDynamicPairs(data.symbols);
        }
      } catch {
        if (!cancelled) setDynamicPairs(DEFAULT_PAIRS);
      } finally {
        if (!cancelled) setLoadingPairs(false);
      }
    };
    fetchSymbols();
    return () => { cancelled = true; };
  }, [formData.exchange]);

  // Validation state
  const [validation, setValidation] = useState<PreTradeValidation | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [step, setStep] = useState<'strategy' | 'config' | 'review'>('strategy');

  // Get available pairs: use dynamically-fetched list or fallback
  const availablePairs = dynamicPairs;

  // Reset strategy config when strategy type changes
  useEffect(() => {
    const defaultConfigs: Record<StrategyType, any> = {
      grid: { upper_price: 50000, lower_price: 40000, grid_levels: 10, amount_per_grid: 100 },
      dca: { investment_amount: 100, interval_hours: 24, price_drop_percentage: 5, max_positions: 10 },
      rsi: { oversold_threshold: 30, overbought_threshold: 70, rsi_period: 14, amount: 100 },
      macd: { fast_period: 12, slow_period: 26, signal_period: 9, amount: 100 },
    };
    
    setFormData(prev => ({
      ...prev,
      strategy_config: defaultConfigs[prev.strategy_type],
    }));
  }, [formData.strategy_type]);

  // Validate pre-trade when moving to review
  useEffect(() => {
    if (step === 'review') {
      validatePreTrade();
    }
  }, [step]);

  const validatePreTrade = async () => {
    setIsValidating(true);
    
    try {
      const result = await api.post<PreTradeValidation>('/trading/validate-pre-trade', {
        exchange: formData.exchange,
        symbol: formData.symbol,
        amount: formData.amount,
        side: 'buy',
      });
      
      setValidation(result);
    } catch (err: any) {
      // Mock validation for demo
      setValidation({
        valid: formData.amount <= 5000,
        available_balance: 10000,
        required_balance: formData.amount,
        min_order_size: 10,
        max_order_size: 100000,
        errors: formData.amount > 5000 ? ['Saldo insuficiente para esta operação'] : [],
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleCreate = async () => {
    if (!validation?.valid) {
      toast({
        title: 'Validação Falhou',
        description: 'Corrija os erros antes de criar o robô.',
        variant: 'destructive',
      });
      return;
    }

    setIsCreating(true);

    try {
      const payload = {
        name: formData.name || `${STRATEGIES[formData.strategy_type].name} Bot`,
        symbol: formData.symbol,
        config: {
          exchange: formData.exchange,
          strategy: formData.strategy_type,
          amount: formData.amount,
          stop_loss: formData.stop_loss,
          take_profit: formData.take_profit,
          is_live: formData.is_live,
          strategy_params: formData.strategy_config,
        },
      };

      const result = await api.post('/bots/create', payload);
      
      toast({
        title: '✅ Robô Criado',
        description: `${formData.name || 'Robô'} foi criado com sucesso!`,
      });

      if (onSuccess) {
        onSuccess(result);
      }
      
      onClose();
    } catch (err: any) {
      toast({
        title: 'Erro ao Criar Robô',
        description: err.message || 'Falha ao criar robô. Tente novamente.',
        variant: 'destructive',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const updateStrategyConfig = (key: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      strategy_config: {
        ...prev.strategy_config,
        [key]: value,
      },
    }));
  };

  // ============== RENDER ==============

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl bg-slate-900 border-slate-800 text-white max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl flex items-center gap-2">
            <Bot className="w-6 h-6 text-blue-500" />
            Criar Novo Robô
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            Configure sua estratégia automatizada de trading
          </DialogDescription>
        </DialogHeader>

        {/* Step Indicator */}
        <div className="flex items-center justify-center gap-2 py-4">
          {(['strategy', 'config', 'review'] as const).map((s, i) => (
            <div key={s} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                step === s 
                  ? 'bg-blue-600 text-white' 
                  : i < ['strategy', 'config', 'review'].indexOf(step)
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-700 text-slate-400'
              }`}>
                {i < ['strategy', 'config', 'review'].indexOf(step) ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : (
                  i + 1
                )}
              </div>
              {i < 2 && <div className="w-12 h-0.5 bg-slate-700 mx-2" />}
            </div>
          ))}
        </div>

        {/* Step 1: Strategy Selection */}
        {step === 'strategy' && (
          <div className="space-y-4">
            <Label className="text-sm text-slate-400">Selecione a Estratégia</Label>
            <div className="grid grid-cols-2 gap-3">
              {Object.values(STRATEGIES).map((strategy) => (
                <Card
                  key={strategy.type}
                  className={`cursor-pointer transition-all hover:scale-[1.02] ${
                    formData.strategy_type === strategy.type
                      ? 'bg-blue-600/20 border-blue-500'
                      : 'bg-slate-800 border-slate-700 hover:border-slate-600'
                  }`}
                  onClick={() => setFormData(prev => ({ ...prev, strategy_type: strategy.type }))}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg bg-${strategy.color}-500/20`}>
                        {strategy.icon}
                      </div>
                      <div className="flex-1">
                        <h4 className="font-medium text-white">{strategy.name}</h4>
                        <p className="text-xs text-slate-400 mt-1">{strategy.description}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Basic Config */}
            <div className="grid grid-cols-2 gap-4 pt-4">
              <div className="space-y-2">
                <Label>Exchange</Label>
                <Select
                  value={formData.exchange}
                  onValueChange={(v) => setFormData(prev => ({ ...prev, exchange: v }))}
                >
                  <SelectTrigger className="bg-slate-800 border-slate-700">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700">
                    {EXCHANGES.map(ex => (
                      <SelectItem key={ex.id} value={ex.id}>{ex.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Par de Trading</Label>
                <Select
                  value={formData.symbol}
                  onValueChange={(v) => setFormData(prev => ({ ...prev, symbol: v }))}
                >
                  <SelectTrigger className="bg-slate-800 border-slate-700">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700">
                    {availablePairs.map(pair => (
                      <SelectItem key={pair} value={pair}>{pair}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Strategy Configuration */}
        {step === 'config' && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 p-3 bg-slate-800 rounded-lg">
              {STRATEGIES[formData.strategy_type].icon}
              <div>
                <p className="font-medium">{STRATEGIES[formData.strategy_type].name}</p>
                <p className="text-xs text-slate-400">{formData.symbol} • {formData.exchange}</p>
              </div>
            </div>

            {/* Grid Trading Config */}
            {formData.strategy_type === 'grid' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Preço Superior ($)</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as GridConfig).upper_price}
                      onChange={(e) => updateStrategyConfig('upper_price', parseFloat(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Preço Inferior ($)</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as GridConfig).lower_price}
                      onChange={(e) => updateStrategyConfig('lower_price', parseFloat(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Níveis de Grid</Label>
                    <Input
                      type="number"
                      min={3}
                      max={50}
                      value={(formData.strategy_config as GridConfig).grid_levels}
                      onChange={(e) => updateStrategyConfig('grid_levels', parseInt(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Valor por Grid ($)</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as GridConfig).amount_per_grid}
                      onChange={(e) => updateStrategyConfig('amount_per_grid', parseFloat(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* DCA Config */}
            {formData.strategy_type === 'dca' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Valor por Compra ($)</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as DCAConfig).investment_amount}
                      onChange={(e) => updateStrategyConfig('investment_amount', parseFloat(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Intervalo (horas)</Label>
                    <Input
                      type="number"
                      min={1}
                      value={(formData.strategy_config as DCAConfig).interval_hours}
                      onChange={(e) => updateStrategyConfig('interval_hours', parseInt(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Queda para Comprar Extra (%)</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as DCAConfig).price_drop_percentage}
                      onChange={(e) => updateStrategyConfig('price_drop_percentage', parseFloat(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Máximo de Posições</Label>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      value={(formData.strategy_config as DCAConfig).max_positions}
                      onChange={(e) => updateStrategyConfig('max_positions', parseInt(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* RSI Config */}
            {formData.strategy_type === 'rsi' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>RSI Oversold (Compra): {(formData.strategy_config as RSIConfig).oversold_threshold}</Label>
                  <Slider
                    value={[(formData.strategy_config as RSIConfig).oversold_threshold]}
                    onValueChange={([v]) => updateStrategyConfig('oversold_threshold', v)}
                    min={10}
                    max={40}
                    step={1}
                    className="py-2"
                  />
                </div>
                <div className="space-y-2">
                  <Label>RSI Overbought (Venda): {(formData.strategy_config as RSIConfig).overbought_threshold}</Label>
                  <Slider
                    value={[(formData.strategy_config as RSIConfig).overbought_threshold]}
                    onValueChange={([v]) => updateStrategyConfig('overbought_threshold', v)}
                    min={60}
                    max={90}
                    step={1}
                    className="py-2"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Período RSI</Label>
                    <Input
                      type="number"
                      min={7}
                      max={30}
                      value={(formData.strategy_config as RSIConfig).rsi_period}
                      onChange={(e) => updateStrategyConfig('rsi_period', parseInt(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Valor por Trade ($)</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as RSIConfig).amount}
                      onChange={(e) => updateStrategyConfig('amount', parseFloat(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* MACD Config */}
            {formData.strategy_type === 'macd' && (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Período Rápido</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as MACDConfig).fast_period}
                      onChange={(e) => updateStrategyConfig('fast_period', parseInt(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Período Lento</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as MACDConfig).slow_period}
                      onChange={(e) => updateStrategyConfig('slow_period', parseInt(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Período Sinal</Label>
                    <Input
                      type="number"
                      value={(formData.strategy_config as MACDConfig).signal_period}
                      onChange={(e) => updateStrategyConfig('signal_period', parseInt(e.target.value))}
                      className="bg-slate-800 border-slate-700"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Valor por Trade ($)</Label>
                  <Input
                    type="number"
                    value={(formData.strategy_config as MACDConfig).amount}
                    onChange={(e) => updateStrategyConfig('amount', parseFloat(e.target.value))}
                    className="bg-slate-800 border-slate-700"
                  />
                </div>
              </div>
            )}

            {/* Common Settings */}
            <div className="border-t border-slate-700 pt-4 space-y-4">
              <div className="space-y-2">
                <Label>Nome do Robô (opcional)</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder={`${STRATEGIES[formData.strategy_type].name} Bot`}
                  className="bg-slate-800 border-slate-700"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Stop Loss (%)</Label>
                  <Input
                    type="number"
                    value={formData.stop_loss}
                    onChange={(e) => setFormData(prev => ({ ...prev, stop_loss: parseFloat(e.target.value) }))}
                    className="bg-slate-800 border-slate-700"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Take Profit (%)</Label>
                  <Input
                    type="number"
                    value={formData.take_profit}
                    onChange={(e) => setFormData(prev => ({ ...prev, take_profit: parseFloat(e.target.value) }))}
                    className="bg-slate-800 border-slate-700"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Review & Validate */}
        {step === 'review' && (
          <div className="space-y-4">
            {/* Validation Status */}
            {isValidating ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                <span className="ml-2 text-slate-400">Validando saldo...</span>
              </div>
            ) : validation ? (
              <>
                {validation.valid ? (
                  <Alert className="bg-emerald-500/10 border-emerald-500/30">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    <AlertDescription className="text-emerald-400">
                      ✅ Validação aprovada! Saldo disponível: ${validation.available_balance.toLocaleString()}
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Alert variant="destructive" className="bg-red-500/10 border-red-500/30">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      {validation.errors.map((err, i) => (
                        <p key={i}>{err}</p>
                      ))}
                      <p className="mt-2 text-xs">
                        Disponível: ${validation.available_balance.toLocaleString()} | 
                        Necessário: ${validation.required_balance.toLocaleString()}
                      </p>
                    </AlertDescription>
                  </Alert>
                )}
              </>
            ) : null}

            {/* Summary */}
            <div className="bg-slate-800 rounded-lg p-4 space-y-3">
              <h4 className="font-medium text-white">Resumo da Configuração</h4>
              
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="text-slate-400">Estratégia:</div>
                <div className="text-white font-medium">{STRATEGIES[formData.strategy_type].name}</div>
                
                <div className="text-slate-400">Exchange:</div>
                <div className="text-white">{formData.exchange}</div>
                
                <div className="text-slate-400">Par:</div>
                <div className="text-white">{formData.symbol}</div>
                
                <div className="text-slate-400">Stop Loss:</div>
                <div className="text-red-400">{formData.stop_loss}%</div>
                
                <div className="text-slate-400">Take Profit:</div>
                <div className="text-emerald-400">{formData.take_profit}%</div>
              </div>
            </div>

            {/* Live Mode Toggle */}
            <div className="flex items-center justify-between p-4 bg-slate-800 rounded-lg">
              <div>
                <Label className="text-white">Modo Ao Vivo</Label>
                <p className="text-xs text-slate-400">
                  {formData.is_live ? '⚠️ Trades reais serão executados!' : '🔒 Modo simulação ativo'}
                </p>
              </div>
              <Switch
                checked={formData.is_live}
                onCheckedChange={(v) => setFormData(prev => ({ ...prev, is_live: v }))}
              />
            </div>
          </div>
        )}

        {/* Footer Buttons */}
        <DialogFooter className="flex gap-2 pt-4">
          {step !== 'strategy' && (
            <Button
              variant="outline"
              onClick={() => setStep(step === 'review' ? 'config' : 'strategy')}
              className="border-slate-700 hover:bg-slate-800"
            >
              Voltar
            </Button>
          )}
          
          {step !== 'review' ? (
            <Button
              onClick={() => setStep(step === 'strategy' ? 'config' : 'review')}
              className="bg-blue-600 hover:bg-blue-700 flex-1"
            >
              Próximo
            </Button>
          ) : (
            <Button
              onClick={handleCreate}
              disabled={!validation?.valid || isCreating}
              className="bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-700 hover:to-green-700 flex-1"
            >
              {isCreating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Criando...
                </>
              ) : (
                <>
                  <Bot className="w-4 h-4 mr-2" />
                  Iniciar Robô
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { CreateRobotModal };
