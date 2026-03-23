import React, { useState } from 'react';
import { AlertCircle, Check, Play, Save, Code2, Zap, TrendingUp, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface AnalysisResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
  winrate_estimate?: number;
}

interface TestResult {
  status: 'pending' | 'running' | 'completed' | 'error';
  accuracy: number;
  trades: number;
  profit: number;
  message?: string;
}

interface StrategyBuilderProps {
  onSave?: (code: string, name: string, accuracy: number) => void;
  initialCode?: string;
}

export function StrategyBuilder({ onSave, initialCode }: StrategyBuilderProps) {
  const [code, setCode] = useState(initialCode || `# Sua estratégia de trading
# Exemplo: Cruzamento de Médias Móveis

import pandas as pd
import numpy as np

class TradingStrategy:
    """
    Sua estratégia deve implementar:
    - __init__(self, **params): Inicializar parâmetros
    - analyze(self, df: pd.DataFrame) -> pd.DataFrame: Retornar sinais (1=compra, 0=venda, -1=sem ação)
    """
    
    def __init__(self, short_ma=9, long_ma=21, **kwargs):
        self.short_ma = short_ma
        self.long_ma = long_ma
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recebe: DataFrame com close, volume, etc
        Retorna: DataFrame com coluna 'signal' (1, 0, ou -1)
        """
        df['short_ma'] = df['close'].rolling(self.short_ma).mean()
        df['long_ma'] = df['close'].rolling(self.long_ma).mean()
        
        # Gerar sinais
        df['signal'] = 0
        df.loc[df['short_ma'] > df['long_ma'], 'signal'] = 1
        df.loc[df['short_ma'] < df['long_ma'], 'signal'] = -1
        
        return df
`);

  const [strategyName, setStrategyName] = useState('Minha Estratégia');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [activeTab, setActiveTab] = useState<'code' | 'analysis' | 'test'>('code');

  // Analisar código Python
  const analyzeCode = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/strategies/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({ code }),
      });

      const data = await response.json();
      setAnalysis(data);
      
      if (!data.valid && data.errors.length > 0) {
        setActiveTab('analysis');
      }
    } catch (err) {
      setAnalysis({
        valid: false,
        errors: [err instanceof Error ? err.message : 'Erro ao analisar código'],
        warnings: [],
        suggestions: [],
      });
    } finally {
      setLoading(false);
    }
  };

  // Testar estratégia
  const testStrategy = async () => {
    setLoading(true);
    setTestResult({ status: 'running', accuracy: 0, trades: 0, profit: 0 });

    try {
      const response = await fetch('http://localhost:8000/api/strategies/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({ code, name: strategyName }),
      });

      const data = await response.json();

      if (data.status === 'error') {
        setTestResult({
          status: 'error',
          accuracy: 0,
          trades: 0,
          profit: 0,
          message: data.message,
        });
      } else {
        setTestResult({
          status: 'completed',
          accuracy: data.accuracy,
          trades: data.trades,
          profit: data.profit,
          message: data.message,
        });
        setActiveTab('test');
      }
    } catch (err) {
      setTestResult({
        status: 'error',
        accuracy: 0,
        trades: 0,
        profit: 0,
        message: err instanceof Error ? err.message : 'Erro ao testar estratégia',
      });
    } finally {
      setLoading(false);
    }
  };

  // Salvar estratégia
  const saveStrategy = async () => {
    // Verifica se acurácia é > 40%
    if (!testResult || testResult.accuracy < 40) {
      alert('Sua estratégia precisa de acurácia > 40% para ser publicada na loja de robôs');
      return;
    }

    if (onSave) {
      onSave(code, strategyName, testResult.accuracy);
    } else {
      // Salvar via API
      setLoading(true);
      try {
        const response = await fetch('http://localhost:8000/api/strategies/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          },
          body: JSON.stringify({
            name: strategyName,
            code,
            accuracy: testResult.accuracy,
            trades: testResult.trades,
            profit: testResult.profit,
          }),
        });

        const data = await response.json();
        if (data.status === 'success') {
          alert('✅ Estratégia salva com sucesso! Publicada na loja de robôs.');
        } else {
          alert('❌ ' + data.message);
        }
      } catch (err) {
        alert('Erro ao salvar: ' + (err instanceof Error ? err.message : 'Erro desconhecido'));
      } finally {
        setLoading(false);
      }
    }
  };

  // Corrigir erros automaticamente
  const fixCode = async () => {
    if (!analysis || analysis.errors.length === 0) return;

    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/strategies/fix', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({ code, errors: analysis.errors }),
      });

      const data = await response.json();
      if (data.fixed_code) {
        setCode(data.fixed_code);
        alert('✅ Código corrigido! Verifique as alterações.');
      }
    } catch (err) {
      alert('Erro ao corrigir: ' + (err instanceof Error ? err.message : 'Erro desconhecido'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2 flex items-center gap-3">
            <Code2 className="w-10 h-10 text-blue-400" />
            Construtor de Estratégias
          </h1>
          <p className="text-slate-400">Crie, teste e publique suas estratégias de trading automático</p>
        </div>

        {/* Main Grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left: Code Editor */}
          <div className="lg:col-span-2">
            <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
              {/* Header */}
              <div className="bg-slate-900 border-b border-slate-700 p-4 flex items-center justify-between">
                <input
                  type="text"
                  value={strategyName}
                  onChange={(e) => setStrategyName(e.target.value)}
                  placeholder="Nome da estratégia"
                  className="flex-1 bg-slate-700 text-white px-3 py-2 rounded mr-3 text-sm focus:outline-none focus:border-blue-500"
                />
                <span className="text-xs text-slate-400 px-2 py-1 bg-slate-700 rounded">Python</span>
              </div>

              {/* Code Editor */}
              <div className="relative h-96 overflow-hidden">
                <textarea
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="absolute inset-0 w-full h-full p-4 font-mono text-sm bg-slate-900 text-slate-50 resize-none focus:outline-none border-none"
                  spellCheck="false"
                />
              </div>

              {/* Action Buttons */}
              <div className="bg-slate-900 border-t border-slate-700 p-4 flex gap-2">
                <button
                  onClick={analyzeCode}
                  disabled={loading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 disabled:bg-yellow-900 text-white rounded font-semibold transition"
                >
                  <AlertTriangle className="w-4 h-4" />
                  Analisar Código
                </button>
                <button
                  onClick={testStrategy}
                  disabled={loading || !analysis?.valid}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-900 text-white rounded font-semibold transition"
                >
                  <Play className="w-4 h-4" />
                  Testar
                </button>
              </div>
            </div>
          </div>

          {/* Right: Results & Info */}
          <div className="space-y-6">
            {/* Analysis Results */}
            {analysis && (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                <h3 className="font-bold text-white mb-3 flex items-center gap-2">
                  {analysis.valid ? (
                    <>
                      <CheckCircle2 className="w-5 h-5 text-green-500" />
                      Código Válido ✅
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-5 h-5 text-red-500" />
                      Há Erros ❌
                    </>
                  )}
                </h3>

                {analysis.errors.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs text-red-400 font-semibold mb-2">Erros:</p>
                    <ul className="space-y-1 text-xs text-red-300">
                      {analysis.errors.map((err, i) => (
                        <li key={i}>• {err}</li>
                      ))}
                    </ul>
                    {analysis.errors.length > 0 && (
                      <button
                        onClick={fixCode}
                        disabled={loading}
                        className="mt-2 w-full py-2 px-3 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-semibold transition"
                      >
                        🔧 Corrigir Automaticamente
                      </button>
                    )}
                  </div>
                )}

                {analysis.warnings.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs text-yellow-400 font-semibold mb-2">Avisos:</p>
                    <ul className="space-y-1 text-xs text-yellow-300">
                      {analysis.warnings.map((warn, i) => (
                        <li key={i}>⚠️ {warn}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {analysis.suggestions.length > 0 && (
                  <div>
                    <p className="text-xs text-blue-400 font-semibold mb-2">Sugestões:</p>
                    <ul className="space-y-1 text-xs text-blue-300">
                      {analysis.suggestions.map((sug, i) => (
                        <li key={i}>💡 {sug}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Test Results */}
            {testResult && testResult.status === 'completed' && (
              <div className={`bg-slate-800 border rounded-lg p-4 ${
                testResult.accuracy >= 40 ? 'border-green-600' : 'border-red-600'
              }`}>
                <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-blue-400" />
                  Resultado do Teste
                </h3>

                <div className="space-y-3">
                  <div className="bg-slate-900 rounded p-3">
                    <p className="text-xs text-slate-400">Acurácia</p>
                    <p className={`text-2xl font-bold ${
                      testResult.accuracy >= 40 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {testResult.accuracy.toFixed(2)}%
                    </p>
                    {testResult.accuracy >= 40 && (
                      <p className="text-xs text-green-400 mt-1">✅ Qualificada para loja de robôs!</p>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-slate-900 rounded p-3">
                      <p className="text-xs text-slate-400">Trades</p>
                      <p className="text-xl font-bold text-blue-300">{testResult.trades}</p>
                    </div>
                    <div className="bg-slate-900 rounded p-3">
                      <p className="text-xs text-slate-400">Lucro</p>
                      <p className={`text-xl font-bold ${
                        testResult.profit >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {testResult.profit > 0 ? '+' : ''}{testResult.profit.toFixed(2)}%
                      </p>
                    </div>
                  </div>

                  {testResult.accuracy >= 40 && (
                    <button
                      onClick={saveStrategy}
                      disabled={loading}
                      className="w-full py-3 px-4 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 disabled:from-green-900 disabled:to-green-900 text-white rounded font-bold transition flex items-center justify-center gap-2"
                    >
                      <Save className="w-4 h-4" />
                      Publicar na Loja
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Info Box */}
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <h4 className="font-bold text-white mb-3 flex items-center gap-2">
                <Zap className="w-4 h-4 text-yellow-400" />
                Requisitos
              </h4>
              <ul className="space-y-2 text-sm text-slate-300">
                <li className="flex items-start gap-2">
                  <span className="text-green-400 mt-1">✓</span>
                  <span>Classe TradingStrategy com método analyze()</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-400 mt-1">✓</span>
                  <span>Retornar DataFrame com coluna 'signal'</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-400 mt-1">✓</span>
                  <span>Acurácia mínima: 40%</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-400 mt-1">✓</span>
                  <span>Usar pandas/numpy para análise</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
