/**
 * useStrategyMetrics Hook
 * Advanced hook for managing strategy data with real backend integration
 */

import { useCallback, useEffect, useState } from 'react';
import { strategyService, StrategyMetrics } from '@/services/strategyService';

interface UseStrategyMetricsState {
  strategies: StrategyMetrics[];
  publicStrategies: StrategyMetrics[];
  topStrategies: StrategyMetrics[];
  selectedStrategy: StrategyMetrics | null;
  loading: boolean;
  error: string | null;
  success: boolean;
}

interface UseStrategyMetricsActions {
  fetchStrategies: () => Promise<void>;
  fetchPublicStrategies: () => Promise<void>;
  fetchTopStrategies: (limit?: number) => Promise<void>;
  getStrategyDetails: (id: string) => Promise<void>;
  createStrategy: (data: Partial<StrategyMetrics>) => Promise<StrategyMetrics | null>;
  updateStrategy: (id: string, data: Partial<StrategyMetrics>) => Promise<StrategyMetrics | null>;
  cloneStrategy: (id: string) => Promise<StrategyMetrics | null>;
  deleteStrategy: (id: string) => Promise<boolean>;
  toggleVisibility: (id: string) => Promise<StrategyMetrics | null>;
  activateStrategy: (id: string) => Promise<StrategyMetrics | null>;
  deactivateStrategy: (id: string) => Promise<StrategyMetrics | null>;
  getPerformance: (id: string, days?: number) => Promise<any>;
  shareStrategy: (id: string) => Promise<string | null>;
  clearError: () => void;
  clearSuccess: () => void;
}

export function useStrategyMetrics(): UseStrategyMetricsState & UseStrategyMetricsActions {
  const [state, setState] = useState<UseStrategyMetricsState>({
    strategies: [],
    publicStrategies: [],
    topStrategies: [],
    selectedStrategy: null,
    loading: false,
    error: null,
    success: false,
  });

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  const clearSuccess = useCallback(() => {
    setState((prev) => ({ ...prev, success: false }));
  }, []);

  const handleError = useCallback((error: any) => {
    const message = error?.message || 'An error occurred';
    setState((prev) => ({ ...prev, error: message, loading: false }));
  }, []);

  const fetchStrategies = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await strategyService.getStrategies();
      setState((prev) => ({ ...prev, strategies: data, loading: false, error: null }));
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const fetchPublicStrategies = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await strategyService.getPublicStrategies();
      setState((prev) => ({ ...prev, publicStrategies: data, loading: false, error: null }));
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const fetchTopStrategies = useCallback(async (limit: number = 10) => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await strategyService.getTopStrategies(limit);
      setState((prev) => ({ ...prev, topStrategies: data, loading: false, error: null }));
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const getStrategyDetails = useCallback(async (id: string) => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await strategyService.getStrategyDetails(id);
      setState((prev) => ({
        ...prev,
        selectedStrategy: data,
        loading: false,
        error: null,
      }));
    } catch (error) {
      handleError(error);
    }
  }, [handleError]);

  const createStrategy = useCallback(
    async (data: Partial<StrategyMetrics>): Promise<StrategyMetrics | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const result = await strategyService.createStrategy(data);
        setState((prev) => ({
          ...prev,
          strategies: [...prev.strategies, result],
          loading: false,
          success: true,
        }));
        setTimeout(() => clearSuccess(), 3000);
        return result;
      } catch (error) {
        handleError(error);
        return null;
      }
    },
    [handleError, clearSuccess]
  );

  const updateStrategy = useCallback(
    async (id: string, data: Partial<StrategyMetrics>): Promise<StrategyMetrics | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const result = await strategyService.updateStrategy(id, data);
        setState((prev) => ({
          ...prev,
          strategies: prev.strategies.map((s) => (s.id === id ? result : s)),
          loading: false,
          success: true,
        }));
        setTimeout(() => clearSuccess(), 3000);
        return result;
      } catch (error) {
        handleError(error);
        return null;
      }
    },
    [handleError, clearSuccess]
  );

  const cloneStrategy = useCallback(
    async (id: string): Promise<StrategyMetrics | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const result = await strategyService.cloneStrategy(id);
        setState((prev) => ({
          ...prev,
          strategies: [...prev.strategies, result],
          loading: false,
          success: true,
        }));
        setTimeout(() => clearSuccess(), 3000);
        return result;
      } catch (error) {
        handleError(error);
        return null;
      }
    },
    [handleError, clearSuccess]
  );

  const deleteStrategy = useCallback(async (id: string): Promise<boolean> => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      await strategyService.deleteStrategy(id);
      setState((prev) => ({
        ...prev,
        strategies: prev.strategies.filter((s) => s.id !== id),
        loading: false,
        success: true,
      }));
      setTimeout(() => clearSuccess(), 3000);
      return true;
    } catch (error) {
      handleError(error);
      return false;
    }
  }, [handleError, clearSuccess]);

  const toggleVisibility = useCallback(
    async (id: string): Promise<StrategyMetrics | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const result = await strategyService.toggleStrategyVisibility(id);
        setState((prev) => ({
          ...prev,
          strategies: prev.strategies.map((s) => (s.id === id ? result : s)),
          loading: false,
          success: true,
        }));
        setTimeout(() => clearSuccess(), 3000);
        return result;
      } catch (error) {
        handleError(error);
        return null;
      }
    },
    [handleError, clearSuccess]
  );

  const activateStrategy = useCallback(
    async (id: string): Promise<StrategyMetrics | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const result = await strategyService.activateStrategy(id);
        setState((prev) => ({
          ...prev,
          strategies: prev.strategies.map((s) => (s.id === id ? result : s)),
          loading: false,
          success: true,
        }));
        setTimeout(() => clearSuccess(), 3000);
        return result;
      } catch (error) {
        handleError(error);
        return null;
      }
    },
    [handleError, clearSuccess]
  );

  const deactivateStrategy = useCallback(
    async (id: string): Promise<StrategyMetrics | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const result = await strategyService.deactivateStrategy(id);
        setState((prev) => ({
          ...prev,
          strategies: prev.strategies.map((s) => (s.id === id ? result : s)),
          loading: false,
          success: true,
        }));
        setTimeout(() => clearSuccess(), 3000);
        return result;
      } catch (error) {
        handleError(error);
        return null;
      }
    },
    [handleError, clearSuccess]
  );

  const getPerformance = useCallback(async (id: string, days: number = 30): Promise<any> => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await strategyService.getStrategyPerformance(id, days);
      setState((prev) => ({ ...prev, loading: false, error: null }));
      return data;
    } catch (error) {
      handleError(error);
      return null;
    }
  }, [handleError]);

  const shareStrategy = useCallback(async (id: string): Promise<string | null> => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const result = await strategyService.shareStrategy(id);
      setState((prev) => ({ ...prev, loading: false, success: true }));
      setTimeout(() => clearSuccess(), 3000);
      return result.shareUrl;
    } catch (error) {
      handleError(error);
      return null;
    }
  }, [handleError, clearSuccess]);

  return {
    ...state,
    fetchStrategies,
    fetchPublicStrategies,
    fetchTopStrategies,
    getStrategyDetails,
    createStrategy,
    updateStrategy,
    cloneStrategy,
    deleteStrategy,
    toggleVisibility,
    activateStrategy,
    deactivateStrategy,
    getPerformance,
    shareStrategy,
    clearError,
    clearSuccess,
  };
}

export default useStrategyMetrics;
