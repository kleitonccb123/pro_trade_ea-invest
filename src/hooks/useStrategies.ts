/**
 * Custom Hook: useStrategies
 * 
 * Gerencia tudo relacionado a estratégias:
 * - Carregar listagem
 * - Criar nova estratégia
 * - Editar estratégia
 * - Deletar estratégia
 * - Toggle visibilidade
 */

import { useState, useCallback, useEffect } from 'react';
import api from '../lib/api';
import { 
  StrategyResponse, 
  StrategySubmitRequest, 
  StrategyListItem,
  ApiError 
} from '../types/strategy';

export interface UseStrategiesState {
  strategies: StrategyResponse[];
  loading: boolean;
  error: ApiError | null;
  success: boolean;
}

export interface UseStrategiesActions {
  fetchStrategies: () => Promise<void>;
  fetchPublicStrategies: () => Promise<StrategyResponse[]>;
  createStrategy: (strategy: StrategySubmitRequest) => Promise<StrategyResponse | null>;
  updateStrategy: (id: string, strategy: StrategySubmitRequest) => Promise<StrategyResponse | null>;
  deleteStrategy: (id: string) => Promise<boolean>;
  toggleVisibility: (id: string) => Promise<StrategyResponse | null>;
  clearError: () => void;
  clearSuccess: () => void;
}

export const useStrategies = (): UseStrategiesState & UseStrategiesActions => {
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [success, setSuccess] = useState(false);

  // Carregar estratégias do usuário autenticado
  const fetchStrategies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<StrategyResponse[]>('/api/strategies/my');
      setStrategies(data);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000); // Limpar após 3s
    } catch (err: any) {
      const apiError: ApiError = {
        detail: err.response?.data?.detail || 'Erro ao carregar estratégias',
        message: err.message,
        status: err.response?.status,
      };
      setError(apiError);
      console.error('Erro ao carregar estratégias:', apiError);
    } finally {
      setLoading(false);
    }
  }, []);

  // Carregar estratégias públicas (sem autenticação necessária)
  const fetchPublicStrategies = useCallback(async (): Promise<StrategyResponse[]> => {
    try {
      const { data } = await api.get<StrategyResponse[]>('/api/strategies/public/list');
      return data;
    } catch (err: any) {
      console.error('Erro ao carregar estratégias públicas:', err);
      return [];
    }
  }, []);

  // Criar nova estratégia
  const createStrategy = useCallback(
    async (strategy: StrategySubmitRequest): Promise<StrategyResponse | null> => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await api.post<StrategyResponse>(
          '/api/strategies/submit',
          strategy
        );
        setStrategies([data, ...strategies]);
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        return data;
      } catch (err: any) {
        const apiError: ApiError = {
          detail: err.response?.data?.detail || 'Erro ao criar estratégia',
          message: err.message,
          status: err.response?.status,
        };
        setError(apiError);
        console.error('Erro ao criar estratégia:', apiError);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [strategies]
  );

  // Atualizar estratégia
  const updateStrategy = useCallback(
    async (id: string, strategy: StrategySubmitRequest): Promise<StrategyResponse | null> => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await api.put<StrategyResponse>(
          `/api/strategies/${id}`,
          strategy
        );
        setStrategies(
          strategies.map((s) => (s.id === id ? data : s))
        );
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        return data;
      } catch (err: any) {
        const apiError: ApiError = {
          detail: err.response?.data?.detail || 'Erro ao atualizar estratégia',
          message: err.message,
          status: err.response?.status,
        };
        setError(apiError);
        console.error('Erro ao atualizar estratégia:', apiError);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [strategies]
  );

  // Deletar estratégia
  const deleteStrategy = useCallback(
    async (id: string): Promise<boolean> => {
      setLoading(true);
      setError(null);
      try {
        await api.delete(`/api/strategies/${id}`);
        setStrategies(strategies.filter((s) => s.id !== id));
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        return true;
      } catch (err: any) {
        const apiError: ApiError = {
          detail: err.response?.data?.detail || 'Erro ao deletar estratégia',
          message: err.message,
          status: err.response?.status,
        };
        setError(apiError);
        console.error('Erro ao deletar estratégia:', apiError);
        return false;
      } finally {
        setLoading(false);
      }
    },
    [strategies]
  );

  // Alternar visibilidade (público/privado)
  const toggleVisibility = useCallback(
    async (id: string): Promise<StrategyResponse | null> => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await api.post<StrategyResponse>(
          `/api/strategies/${id}/toggle-public`
        );
        setStrategies(
          strategies.map((s) => (s.id === id ? data : s))
        );
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        return data;
      } catch (err: any) {
        const apiError: ApiError = {
          detail: err.response?.data?.detail || 'Erro ao alterar visibilidade',
          message: err.message,
          status: err.response?.status,
        };
        setError(apiError);
        console.error('Erro ao alterar visibilidade:', apiError);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [strategies]
  );

  // Limpar erro
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Limpar sucesso
  const clearSuccess = useCallback(() => {
    setSuccess(false);
  }, []);

  return {
    strategies,
    loading,
    error,
    success,
    fetchStrategies,
    fetchPublicStrategies,
    createStrategy,
    updateStrategy,
    deleteStrategy,
    toggleVisibility,
    clearError,
    clearSuccess,
  };
};
