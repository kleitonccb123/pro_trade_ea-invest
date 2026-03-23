import { useState, useEffect } from 'react';
import { Plus, Trash2, Play, Save, Check, AlertCircle, Copy, Settings, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';
import { authService } from '@/services/authService';

interface Strategy {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  strategy_code: string;
  status: string;
  trade_count: number;
  total_pnl: number;
  win_rate: number | null;
  symbol: string | null;
  timeframe: string | null;
  is_active: boolean;
  is_publishable: boolean;
  is_expired: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  expires_at: string;
}

interface ValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export default function Strategy() {
  const { toast } = useToast();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  const [loading, setLoading] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  // Form states
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    strategy_code: '',
    symbol: 'BTCUSDT',
    timeframe: '1h',
  });

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/strategies', {
        headers: {
          'Authorization': `Bearer ${authService.getAccessToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch strategies');
      }

      const data = await response.json();
      setStrategies(data.strategies || []);
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Falha ao carregar estratégias',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const validateCode = async (code: string) => {
    try {
      const response = await fetch('/api/strategies/validate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authService.getAccessToken()}`,
        },
        body: JSON.stringify({ strategy_code: code }),
      });

      if (!response.ok) {
        throw new Error('Validation failed');
      }

      const result = await response.json();
      setValidationResult(result);
      return result.is_valid;
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Erro ao validar código',
        variant: 'destructive',
      });
      return false;
    }
  };

  const handleCreateStrategy = async () => {
    if (!formData.name || !formData.strategy_code) {
      toast({
        title: 'Erro',
        description: 'Preencha os campos obrigatórios',
        variant: 'destructive',
      });
      return;
    }

    const isValid = await validateCode(formData.strategy_code);
    if (!isValid && validationResult?.errors.length) {
      toast({
        title: 'Código inválido',
        description: validationResult.errors[0],
        variant: 'destructive',
      });
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('/api/strategies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authService.getAccessToken()}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error('Failed to create strategy');
      }

      toast({
        title: 'Sucesso',
        description: 'Estratégia criada com sucesso',
      });

      setFormData({
        name: '',
        description: '',
        strategy_code: '',
        symbol: 'BTCUSDT',
        timeframe: '1h',
      });
      setValidationResult(null);
      setShowNewModal(false);
      fetchStrategies();
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Falha ao criar estratégia',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePublishStrategy = async (strategyId: number) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/strategies/${strategyId}/publish`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authService.getAccessToken()}`,
        },
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to publish strategy');
      }

      toast({
        title: 'Sucesso',
        description: 'Estratégia publicada na vitrine',
      });

      fetchStrategies();
    } catch (error) {
      toast({
        title: 'Erro',
        description: error instanceof Error ? error.message : 'Falha ao publicar estratégia',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteStrategy = async (strategyId: number) => {
    if (!confirm('Tem certeza que deseja deletar esta estratégia?')) return;

    try {
      setLoading(true);
      const response = await fetch(`/api/strategies/${strategyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authService.getAccessToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete strategy');
      }

      toast({
        title: 'Sucesso',
        description: 'Estratégia deletada',
      });

      fetchStrategies();
    } catch (error) {
      toast({
        title: 'Erro',
        description: 'Falha ao deletar estratégia',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-background to-primary/5 overflow-hidden">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-10 w-72 h-72 bg-gradient-to-br from-primary/20 to-primary/0 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-gradient-to-tl from-accent/15 to-secondary/5 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
        <div className="absolute inset-0 bg-[linear-gradient(rgba(190,95,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(190,95,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px] opacity-50"></div>
      </div>

      {/* Strategy Details Modal */}
      {selectedStrategy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-gradient-to-br from-gray-900 to-black border border-primary/20 rounded-2xl shadow-2xl shadow-primary/20 w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="bg-gradient-to-r from-primary/20 to-accent/20 border-b border-primary/20 p-6">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div className="flex-1">
                  <h2 className="text-2xl md:text-3xl font-bold text-white mb-2">{selectedStrategy.name}</h2>
                  <div className="flex flex-wrap gap-3 items-center">
                    <span className={cn(
                      'text-xs px-3 py-1 rounded-full font-medium',
                      selectedStrategy.status === 'published'
                        ? 'bg-green-500/30 text-green-300 border border-green-500/50'
                        : selectedStrategy.status === 'testing'
                          ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50'
                          : 'bg-gray-500/30 text-gray-300 border border-gray-500/50'
                    )}>
                      {selectedStrategy.status === 'published' ? '✓ Publicada' : selectedStrategy.status === 'testing' ? '◐ Testando' : '○ Rascunho'}
                    </span>
                    {selectedStrategy.is_expired && (
                      <span className="text-xs px-3 py-1 rounded-full font-medium bg-red-500/30 text-red-300 border border-red-500/50">
                        ⚠ Expirada
                      </span>
                    )}
                    <span className="text-xs text-gray-400">v{selectedStrategy.version}</span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedStrategy(null)}
                  className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/10 rounded-lg"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="overflow-y-auto flex-1 p-6 space-y-6">
              {/* Description */}
              {selectedStrategy.description && (
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-gray-300 mb-2">Descrição</h3>
                  <p className="text-gray-300 text-sm leading-relaxed">{selectedStrategy.description}</p>
                </div>
              )}

              {/* Configuration */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gradient-to-br from-primary/10 to-transparent border border-primary/20 rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Par de Trading</h3>
                  <p className="text-xl font-bold text-primary">{selectedStrategy.symbol || '-'}</p>
                </div>
                <div className="bg-gradient-to-br from-accent/10 to-transparent border border-accent/20 rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Timeframe</h3>
                  <p className="text-xl font-bold text-accent">{selectedStrategy.timeframe || '-'}</p>
                </div>
              </div>

              {/* Statistics */}
              {selectedStrategy.trade_count > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Operações</h3>
                    <p className="text-2xl font-bold text-white">{selectedStrategy.trade_count}/20</p>
                  </div>
                  <div className={cn(
                    "border rounded-xl p-4",
                    selectedStrategy.total_pnl > 0
                      ? "bg-green-500/10 border-green-500/30"
                      : "bg-red-500/10 border-red-500/30"
                  )}>
                    <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">P&L Total</h3>
                    <p className={cn(
                      "text-2xl font-bold",
                      selectedStrategy.total_pnl > 0 ? "text-green-400" : "text-red-400"
                    )}>
                      ${selectedStrategy.total_pnl.toFixed(2)}
                    </p>
                  </div>
                  {selectedStrategy.win_rate !== null && (
                    <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
                      <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2">Taxa de Acerto</h3>
                      <p className="text-2xl font-bold text-blue-400">{selectedStrategy.win_rate.toFixed(1)}%</p>
                    </div>
                  )}
                </div>
              )}

              {/* Code Section */}
              <div className="bg-gray-950 border border-gray-700 rounded-xl p-4">
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Código Python</h3>
                <div className="bg-black/50 rounded-lg p-4 overflow-x-auto border border-gray-700">
                  <code className="text-gray-300 font-mono text-xs whitespace-pre-wrap break-words max-h-64 overflow-y-auto block">
                    {selectedStrategy.strategy_code}
                  </code>
                </div>
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4 text-sm pt-2 border-t border-gray-700">
                <div className="text-gray-400">
                  Criada em: <span className="text-white">{new Date(selectedStrategy.created_at).toLocaleDateString('pt-BR')}</span>
                </div>
                <div className="text-gray-400">
                  Atualizada em: <span className="text-white">{new Date(selectedStrategy.updated_at).toLocaleDateString('pt-BR')}</span>
                </div>
              </div>
            </div>

            {/* Actions Footer */}
            <div className="bg-gray-950 border-t border-gray-700 p-6 flex gap-3">
              {selectedStrategy.is_publishable && !selectedStrategy.is_expired && (
                <Button
                  onClick={() => {
                    handlePublishStrategy(selectedStrategy.id);
                    setSelectedStrategy(null);
                  }}
                  className="flex-1 gap-2 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                  disabled={loading}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  {loading ? 'Publicando...' : 'Publicar na Vitrine'}
                </Button>
              )}
              <Button
                onClick={() => {
                  handleDeleteStrategy(selectedStrategy.id);
                  setSelectedStrategy(null);
                }}
                variant="outline"
                className="flex-1 gap-2 text-red-400 border-red-500/50 hover:bg-red-900/20"
                disabled={loading}
              >
                <Trash2 size={16} />
                {loading ? 'Deletando...' : 'Deletar'}
              </Button>
              <Button
                onClick={() => setSelectedStrategy(null)}
                variant="outline"
                className="flex-1 gap-2"
              >
                Fechar
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="relative z-10 p-6 md:p-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
              Criador de Estratégias
            </h1>
            <p className="text-gray-400">
              Crie e configure suas estratégias de trading automatizado
            </p>
          </div>

          <Dialog open={showNewModal} onOpenChange={setShowNewModal}>
            <DialogTrigger asChild>
              <Button
                className="gap-2 bg-gradient-to-r from-primary to-accent hover:shadow-lg hover:shadow-primary/20"
                size="lg"
              >
                <Plus size={20} />
                Nova Estratégia
              </Button>
            </DialogTrigger>

            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Nova Estratégia de Trading</DialogTitle>
              </DialogHeader>

              <div className="space-y-6">
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Nome da Estratégia *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-primary"
                    placeholder="Ex: Momentum Strategy"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Descrição
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-primary h-24 resize-none"
                    placeholder="Descreva sua estratégia..."
                  />
                </div>

                {/* Symbol and Timeframe */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Par de Trading *
                    </label>
                    <select
                      value={formData.symbol}
                      onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}
                      className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-primary"
                    >
                      <option value="BTCUSDT">BTC/USDT</option>
                      <option value="ETHUSDT">ETH/USDT</option>
                      <option value="BNBUSDT">BNB/USDT</option>
                      <option value="SOLUSDT">SOL/USDT</option>
                      <option value="ADAUSDT">ADA/USDT</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Timeframe *
                    </label>
                    <select
                      value={formData.timeframe}
                      onChange={(e) => setFormData({ ...formData, timeframe: e.target.value })}
                      className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-primary"
                    >
                      <option value="1m">1 Minuto</option>
                      <option value="5m">5 Minutos</option>
                      <option value="15m">15 Minutos</option>
                      <option value="1h">1 Hora</option>
                      <option value="4h">4 Horas</option>
                      <option value="1d">1 Dia</option>
                    </select>
                  </div>
                </div>

                {/* Strategy Code */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Código Python da Estratégia *
                  </label>
                  <textarea
                    value={formData.strategy_code}
                    onChange={(e) => {
                      setFormData({ ...formData, strategy_code: e.target.value });
                      setValidationResult(null);
                    }}
                    className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-primary font-mono text-sm h-64 resize-none"
                    placeholder={`def on_buy_signal(data):
    # Suas condições de compra
    return condition

def on_sell_signal(data):
    # Suas condições de venda
    return condition`}
                  />
                  <p className="text-xs text-gray-400 mt-2">
                    Sua estratégia deve conter as funções: on_buy_signal() e on_sell_signal()
                  </p>
                </div>

                {/* Validation Result */}
                {validationResult && (
                  <div className={cn(
                    "p-4 rounded-lg",
                    validationResult.is_valid
                      ? "bg-green-900/20 border border-green-800"
                      : "bg-red-900/20 border border-red-800"
                  )}>
                    <div className="flex items-start gap-3">
                      {validationResult.is_valid ? (
                        <Check className="text-green-500 mt-1 flex-shrink-0" size={20} />
                      ) : (
                        <AlertCircle className="text-red-500 mt-1 flex-shrink-0" size={20} />
                      )}
                      <div className="flex-1">
                        {validationResult.is_valid && (
                          <p className="text-green-400 font-medium">Código validado com sucesso</p>
                        )}
                        {validationResult.errors.length > 0 && (
                          <div>
                            <p className="text-red-400 font-medium mb-2">Erros:</p>
                            <ul className="text-red-300 text-sm space-y-1">
                              {validationResult.errors.map((error, i) => (
                                <li key={i}>• {error}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {validationResult.warnings.length > 0 && (
                          <div className={validationResult.errors.length > 0 ? 'mt-3' : ''}>
                            <p className="text-yellow-400 font-medium mb-2">Avisos:</p>
                            <ul className="text-yellow-300 text-sm space-y-1">
                              {validationResult.warnings.map((warning, i) => (
                                <li key={i}>• {warning}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-4">
                  <Button
                    onClick={() => validateCode(formData.strategy_code)}
                    variant="outline"
                    className="flex-1 gap-2"
                    disabled={!formData.strategy_code}
                  >
                    <Check size={18} />
                    Validar Código
                  </Button>
                  <Button
                    onClick={handleCreateStrategy}
                    className="flex-1 gap-2 bg-gradient-to-r from-primary to-accent"
                    disabled={loading || !formData.name || !formData.strategy_code}
                  >
                    <Save size={18} />
                    {loading ? 'Criando...' : 'Criar Estratégia'}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Strategies List */}
        <div className="space-y-4">
          {strategies.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-400 mb-4">Você ainda não criou nenhuma estratégia</p>
              <Button
                onClick={() => setShowNewModal(true)}
                className="gap-2 bg-gradient-to-r from-primary to-accent"
              >
                <Plus size={18} />
                Criar Sua Primeira Estratégia
              </Button>
            </div>
          ) : (
            strategies.map((strategy) => (
              <div
                key={strategy.id}
                className="bg-gray-900/40 backdrop-blur-md border border-gray-800 rounded-lg p-6 hover:border-primary/50 transition-all cursor-pointer"
                onClick={() => setSelectedStrategy(strategy)}
              >
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-bold text-white">{strategy.name}</h3>
                      <span className={cn(
                        'text-xs px-3 py-1 rounded-full font-medium',
                        strategy.status === 'published'
                          ? 'bg-green-900/30 text-green-400'
                          : strategy.status === 'testing'
                            ? 'bg-blue-900/30 text-blue-400'
                            : 'bg-gray-700/30 text-gray-400'
                      )}>
                        {strategy.status === 'published' ? 'Publicada' : strategy.status === 'testing' ? 'Testando' : 'Rascunho'}
                      </span>
                      {strategy.is_expired && (
                        <span className="text-xs px-3 py-1 rounded-full font-medium bg-red-900/30 text-red-400">
                          Expirada
                        </span>
                      )}
                    </div>

                    {strategy.description && (
                      <p className="text-gray-400 text-sm mb-3">{strategy.description}</p>
                    )}

                    <div className="flex flex-wrap gap-4 text-sm">
                      <div>
                        <span className="text-gray-400">Par: </span>
                        <span className="text-white font-medium">{strategy.symbol || '-'}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Timeframe: </span>
                        <span className="text-white font-medium">{strategy.timeframe || '-'}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Operações: </span>
                        <span className="text-white font-medium">{strategy.trade_count}/20</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Versão: </span>
                        <span className="text-white font-medium">v{strategy.version}</span>
                      </div>
                    </div>

                    {strategy.trade_count > 0 && (
                      <div className="flex gap-4 mt-3 text-sm">
                        <div className="flex items-center gap-1">
                          <TrendingUp size={16} className="text-green-400" />
                          <span className={strategy.total_pnl > 0 ? 'text-green-400' : 'text-red-400'}>
                            ${strategy.total_pnl.toFixed(2)}
                          </span>
                        </div>
                        {strategy.win_rate !== null && (
                          <div className="text-gray-400">
                            Taxa de acerto: <span className="text-white font-medium">{strategy.win_rate.toFixed(1)}%</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    {strategy.is_publishable && !strategy.is_expired && (
                      <Button
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePublishStrategy(strategy.id);
                        }}
                        size="sm"
                        className="gap-2 bg-green-600 hover:bg-green-700"
                        disabled={loading}
                      >
                        <Copy size={16} />
                        Publicar
                      </Button>
                    )}
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteStrategy(strategy.id);
                      }}
                      size="sm"
                      variant="outline"
                      className="gap-2 text-red-400 border-red-700/50 hover:bg-red-900/20"
                      disabled={loading}
                    >
                      <Trash2 size={16} />
                      Deletar
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
