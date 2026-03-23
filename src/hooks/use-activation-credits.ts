/**
 * Hook: useActivationCredits
 * 
 * Syncs user's real activation credits from backend.
 * Fetches from GET /me/activations and updates on:
 * - Component mount
 * - Every 30 seconds (polling)
 * - Manually via refresh()
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '@/config/constants';
import { authService } from '@/services/authService';

export interface ActivationData {
  plan: string;
  activationCredits: number;
  activationCreditsUsed: number;
  activationCreditsRemaining: number;
  activeBotsCount: number;
  maxActiveBots: number;
}

interface UseActivationCreditsReturn {
  data: ActivationData | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  lastUpdated: Date | null;
}

const DEFAULT_DATA: ActivationData = {
  plan: 'starter',
  activationCredits: 0,
  activationCreditsUsed: 0,
  activationCreditsRemaining: 0,
  activeBotsCount: 0,
  maxActiveBots: 5,
};

export function useActivationCredits(): UseActivationCreditsReturn {
  const [data, setData] = useState<ActivationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchActivationData = useCallback(async () => {
    try {
      const token = authService.getAccessToken();
      if (!token) {
        console.warn('[useActivationCredits] No token available, using default data');
        setData(DEFAULT_DATA);
        setLoading(false);
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/me/activations`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          console.warn('[useActivationCredits] Token invalid/expired, using default data');
          // Token might be expired - use default data instead of throwing
          setData(DEFAULT_DATA);
          setError(null);
          setLoading(false);
          return;
        }
        if (response.status === 404) {
          console.warn('[useActivationCredits] Endpoint not found, using default data');
          setData(DEFAULT_DATA);
          setError(null);
          setLoading(false);
          return;
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result: ActivationData = await response.json();
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      console.error('[useActivationCredits] Error:', errorMsg);
      // Don't fail the entire dashboard - use default data and continue
      setData(DEFAULT_DATA);
      setError(null); // Don't persist error state
    } finally {
      setLoading(false);
    }
  }, []);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      console.error('[useActivationCredits] Error:', errorMsg);
      setError(errorMsg);
      // Use default data on error instead of null
      setData(DEFAULT_DATA);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchActivationData();
  }, [fetchActivationData]);

  // Polling every 30 seconds
  useEffect(() => {
    pollingIntervalRef.current = setInterval(() => {
      fetchActivationData();
    }, 30_000);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [fetchActivationData]);

  // Listen for activation events
  useEffect(() => {
    const handleActivationEvent = () => {
      console.log('[useActivationCredits] Activation event detected, refreshing...');
      fetchActivationData();
    };

    window.addEventListener('botActivated', handleActivationEvent);
    window.addEventListener('botStoppedGracefully', handleActivationEvent);

    return () => {
      window.removeEventListener('botActivated', handleActivationEvent);
      window.removeEventListener('botStoppedGracefully', handleActivationEvent);
    };
  }, [fetchActivationData]);

  return {
    data: data || DEFAULT_DATA,
    loading,
    error,
    refresh: fetchActivationData,
    lastUpdated,
  };
}
