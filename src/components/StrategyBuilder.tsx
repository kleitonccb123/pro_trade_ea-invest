import React, { useState } from 'react';
import { StrategySubmitRequest } from '../types/strategy';
import { Plus, Trash2, Code2, Save } from 'lucide-react';

interface StrategyBuilderProps {
  onSave: (strategy: StrategySubmitRequest) => Promise<void>;
}

const PRESET_STRATEGIES = [
  {
    label: 'SMA Crossover',
    value: 'sma_crossover',
    description: 'Cruzamento de médias móveis simples (rápida e lenta)',
    defaultParams: { fast_period: 9, slow_period: 21, symbol: 'BTC-USDT' },
  },
  {
    label: 'RSI',
    value: 'rsi',
    description: 'Overbought / oversold usando Índice de Força Relativa',
    defaultParams: { period: 14, overbought: 70, oversold: 30, symbol: 'BTC-USDT' },
  },
  {
    label: 'Grid Trading',
    value: 'grid',
    description: 'Compra e venda automática em faixas de preço',
    defaultParams: { upper_price: 50000, lower_price: 40000, grid_lines: 10, symbol: 'BTC-USDT' },
  },
  {
    label: 'Personalizada',
    value: 'custom',
    description: 'Defina seus próprios parâmetros manualmente',
    defaultParams: {},
  },
];

export function StrategyBuilder({ onSave }: StrategyBuilderProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState(PRESET_STRATEGIES[0]);
  const [params, setParams] = useState<Record<string, any>>(PRESET_STRATEGIES[0].defaultParams);
  const [customKey, setCustomKey] = useState('');
  const [customValue, setCustomValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePresetChange = (preset: typeof PRESET_STRATEGIES[0]) => {
    setSelectedPreset(preset);
    setParams(preset.defaultParams);
  };

  const handleParamChange = (key: string, value: string) => {
    const parsed = isNaN(Number(value)) || value === '' ? value : Number(value);
    setParams((prev) => ({ ...prev, [key]: parsed }));
  };

  const handleAddCustomParam = () => {
    if (!customKey.trim()) return;
    const parsed = isNaN(Number(customValue)) || customValue === '' ? customValue : Number(customValue);
    setParams((prev) => ({ ...prev, [customKey.trim()]: parsed }));
    setCustomKey('');
    setCustomValue('');
  };

  const handleRemoveParam = (key: string) => {
    setParams((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSave = async () => {
    setError(null);
    if (!name.trim()) {
      setError('Nome da estratégia é obrigatório.');
      return;
    }
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        description: description.trim() || `Estratégia ${selectedPreset.label}`,
        parameters: { strategy_type: selectedPreset.value, ...params },
        is_public: isPublic,
      });
    } catch (err: any) {
      setError(err?.message ?? 'Erro ao salvar estratégia.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-slate-800 rounded-2xl border border-slate-700 p-6 w-full max-w-2xl mx-auto text-white space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Code2 className="w-6 h-6 text-blue-400" />
        <h2 className="text-xl font-bold">Construtor de Estratégia</h2>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-600 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Preset selector */}
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-2">Tipo de Estratégia</label>
        <div className="grid grid-cols-2 gap-2">
          {PRESET_STRATEGIES.map((p) => (
            <button
              key={p.value}
              onClick={() => handlePresetChange(p)}
              className={`text-left p-3 rounded-lg border transition-all text-sm ${
                selectedPreset.value === p.value
                  ? 'border-blue-500 bg-blue-900/30 text-blue-300'
                  : 'border-slate-600 bg-slate-700/40 text-slate-300 hover:border-slate-500'
              }`}
            >
              <div className="font-semibold">{p.label}</div>
              <div className="text-xs text-slate-400 mt-0.5 line-clamp-2">{p.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Name */}
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-1">Nome *</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Minha SMA 9/21"
          className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-1">Descrição</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          placeholder="Descreva sua estratégia..."
          className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none"
        />
      </div>

      {/* Parameters */}
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-2">Parâmetros</label>
        <div className="space-y-2">
          {Object.entries(params).map(([key, val]) => (
            <div key={key} className="flex gap-2 items-center">
              <span className="w-32 text-xs text-slate-400 font-mono truncate">{key}</span>
              <input
                type="text"
                value={String(val)}
                onChange={(e) => handleParamChange(key, e.target.value)}
                className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={() => handleRemoveParam(key)}
                className="p-1 text-red-400 hover:text-red-300"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        {/* Add custom param */}
        <div className="flex gap-2 mt-3">
          <input
            type="text"
            value={customKey}
            onChange={(e) => setCustomKey(e.target.value)}
            placeholder="campo"
            className="w-28 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-500"
          />
          <input
            type="text"
            value={customValue}
            onChange={(e) => setCustomValue(e.target.value)}
            placeholder="valor"
            className="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleAddCustomParam}
            className="flex items-center gap-1 px-3 py-1 bg-slate-600 hover:bg-slate-500 rounded text-sm"
          >
            <Plus className="w-4 h-4" /> Adicionar
          </button>
        </div>
      </div>

      {/* Public toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setIsPublic((v) => !v)}
          className={`relative w-10 h-6 rounded-full transition-colors ${isPublic ? 'bg-blue-500' : 'bg-slate-600'}`}
        >
          <span className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${isPublic ? 'translate-x-4' : ''}`} />
        </button>
        <span className="text-sm text-slate-300">Tornar estratégia pública</span>
      </div>

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full flex items-center justify-center gap-2 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg font-semibold text-sm transition-colors"
      >
        <Save className="w-4 h-4" />
        {saving ? 'Salvando...' : 'Salvar Estratégia'}
      </button>
    </div>
  );
}
