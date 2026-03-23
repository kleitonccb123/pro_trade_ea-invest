/**
 * useCredits Hook
 * Manages credit state, API calls, and credit validation logic
 * Used across components for consistent credit management
 */

import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface CreditData {
  plan: 'starter' | 'pro' | 'premium';
  activationCredits: number;
  activationCreditsUsed: number;
  activationCreditsRemaining: number;
  activeBotsCount: number;
  lastUpdated: string;
}

interface ValidationResponse {
  isValid: boolean;
  reason?: string;
  data?: any;
}

interface SwapValidationResponse {
  isFree: boolean;
  cost: number;
  swapCount: number;
}

// API configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

export const useCredits = () => {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  // Fetch credits profile
  const {
    data: credits,
    isLoading: isLoadingCredits,
    refetch: refetchCredits,
  } = useQuery<CreditData>(['credits'], async () => {
    const response = await fetch(
      `${API_BASE_URL}/auth/profile/activation-credits`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('authToken')}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch credits');
    }

    const data = await response.json();
    return {
      ...data,
      lastUpdated: new Date().toISOString(),
    };
  });

  // Validate if bot can be started
  const validateBotActivation = useCallback(
    async (botId: string): Promise<ValidationResponse> => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/bots/${botId}/validate-activation`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${localStorage.getItem('authToken')}`,
              'Content-Type': 'application/json',
            },
          }
        );

        const data = await response.json();

        if (!response.ok) {
          return {
            isValid: false,
            reason: data.detail || 'Validation failed',
            data,
          };
        }

        return {
          isValid: true,
          data,
        };
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Validation error';
        setError(message);
        return {
          isValid: false,
          reason: message,
        };
      }
    },
    []
  );

  // Validate swap cost
  const validateSwap = useCallback(
    async (botId: string): Promise<SwapValidationResponse> => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/bots/${botId}/validate-swap`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${localStorage.getItem('authToken')}`,
              'Content-Type': 'application/json',
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to validate swap');
        }

        return await response.json();
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Swap validation error';
        setError(message);
        throw err;
      }
    },
    []
  );

  // Start bot mutation
  const startBotMutation = useMutation(
    async (botId: string) => {
      const response = await fetch(`${API_BASE_URL}/bots/${botId}/start`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to start bot');
      }

      return response.json();
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['credits']);
      },
      onError: (err) => {
        const message = err instanceof Error ? err.message : 'Start bot error';
        setError(message);
      },
    }
  );

  // Stop bot mutation
  const stopBotMutation = useMutation(
    async (botId: string) => {
      const response = await fetch(`${API_BASE_URL}/bots/${botId}/stop`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to stop bot');
      }

      return response.json();
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['credits']);
      },
      onError: (err) => {
        const message = err instanceof Error ? err.message : 'Stop bot error';
        setError(message);
      },
    }
  );

  // Update bot config (with swap cost)
  const updateConfigMutation = useMutation(
    async ({
      botId,
      config,
    }: {
      botId: string;
      config: Record<string, any>;
    }) => {
      const response = await fetch(
        `${API_BASE_URL}/bots/${botId}/config`,
        {
          method: 'PUT',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('authToken')}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(config),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to update config');
      }

      return response.json();
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['credits']);
      },
      onError: (err) => {
        const message =
          err instanceof Error ? err.message : 'Config update error';
        setError(message);
      },
    }
  );

  // Upgrade plan
  const upgradePlanMutation = useMutation(
    async (newPlan: 'pro' | 'premium') => {
      const response = await fetch(
        `${API_BASE_URL}/users/upgrade-plan`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${localStorage.getItem('authToken')}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ plan: newPlan }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to upgrade plan');
      }

      return response.json();
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['credits']);
      },
      onError: (err) => {
        const message =
          err instanceof Error ? err.message : 'Plan upgrade error';
        setError(message);
      },
    }
  );

  // Check if user can perform action
  const canStartBot = useCallback(
    (botId?: string) => {
      return (
        credits &&
        credits.activationCreditsRemaining > 0 &&
        !startBotMutation.isLoading
      );
    },
    [credits, startBotMutation.isLoading]
  );

  const canSwapBot = useCallback(
    (swapCount: number) => {
      return credits && credits.activationCreditsRemaining > 0;
    },
    [credits]
  );

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    // Data
    credits,
    error,

    // Loading states
    isLoadingCredits,
    isStartingBot: startBotMutation.isLoading,
    isStoppingBot: stopBotMutation.isLoading,
    isUpdatingConfig: updateConfigMutation.isLoading,
    isUpgradingPlan: upgradePlanMutation.isLoading,

    // Methods
    refetchCredits,
    validateBotActivation,
    validateSwap,
    startBot: startBotMutation.mutateAsync,
    stopBot: stopBotMutation.mutateAsync,
    updateConfig: updateConfigMutation.mutateAsync,
    upgradePlan: upgradePlanMutation.mutateAsync,
    canStartBot,
    canSwapBot,
    clearError,
  };
};

export default useCredits;
