import { useEffect, useState } from 'react';
import { useApi } from './useApi';

export interface RankedStrategy {
  id: string;
  name: string;
  pair: string;
  profit: number;
  profit_adjusted?: number;
  winRate: number;
  status: string;
  rank: number;
  is_top3: boolean;
  is_top10: boolean;
  medal?: string;
}

export interface RankedStrategiesResponse {
  current_seed: number;
  rotation_epoch: number;
  strategies: RankedStrategy[];
}

/**
 * Hook para carregar estratégias com ranking dinâmico (rotação a cada 15 dias)
 * 
 * Endpoint: GET /api/strategies/ranked
 * Retorna: 20 estratégias com lógica de rotação determinística
 */
export const useRankedStrategies = () => {
  const [strategies, setStrategies] = useState<RankedStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const api = useApi();

  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        setLoading(true);
        const response = await api.get<RankedStrategiesResponse>('/api/strategies/ranked');
        setStrategies(response.strategies);
        setError(null);
        console.log('[useRankedStrategies] Carregadas', response.strategies.length, 'estratégias');
      } catch (err: any) {
        console.error('[useRankedStrategies] Erro:', err);
        setError(err.message || 'Erro ao carregar estratégias');
        // Usar dados mock se falhar
        setStrategies(generateMockStrategies());
      } finally {
        setLoading(false);
      }
    };

    fetchStrategies();
  }, []);

  return { strategies, loading, error };
};

/**
 * Gera estratégias mock para fallback quando API falha
 */
function generateMockStrategies(): RankedStrategy[] {
  const strategies: RankedStrategy[] = [];
  
  // Top 10 BTC
  for (let i = 0; i < 10; i++) {
    strategies.push({
      id: `btc_${i}`,
      name: `Bitcoin Scalper ${i + 1}`,
      pair: 'BTC/USDT',
      profit: 2000 - i * 100,
      winRate: 72 - i,
      status: 'ACTIVE',
      rank: i + 1,
      is_top3: i < 3,
      is_top10: true,
      medal: ['🥇', '🥈', '🥉'][i] || undefined,
    });
  }
  
  // Top 10 ETH
  for (let i = 0; i < 10; i++) {
    strategies.push({
      id: `eth_${i}`,
      name: `Ethereum DCA ${i + 1}`,
      pair: 'ETH/USDT',
      profit: 1500 - i * 80,
      winRate: 68 - i,
      status: 'ACTIVE',
      rank: i + 11,
      is_top3: false,
      is_top10: false,
      medal: undefined,
    });
  }
  
  return strategies;
}
