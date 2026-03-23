/**
 * Strategy Service
 * Handles all strategy-related API calls with proper error handling
 */

import { apiGet, apiPost, apiPut, apiDelete } from './apiClient';
import { API_BASE_URL } from '@/config/constants';

export interface StrategyMetrics {
  id: string;
  name: string;
  description: string;
  isPublic: boolean;
  isActive: boolean;
  winRate?: number;
  monthlyReturn?: number;
  riskLevel?: 'low' | 'medium' | 'high';
  swapsUsed?: number;
  maxSwaps?: number;
  activationsUsed?: number;
  maxActivations?: number;
  createdAt?: string;
  totalTrades?: number;
  totalProfit?: number;
  drawdown?: number;
  sharpeRatio?: number;
  successRate?: number;
  avgWin?: number;
  avgLoss?: number;
}

// Fetch all strategies
export async function getStrategies(): Promise<StrategyMetrics[]> {
  try {
    const response = await apiGet<StrategyMetrics[]>('/api/strategies/my');
    return response;
  } catch (error) {
    console.error('Error fetching strategies:', error);
    throw error;
  }
}

// Fetch public strategies
export async function getPublicStrategies(): Promise<StrategyMetrics[]> {
  try {
    const response = await apiGet<StrategyMetrics[]>('/api/strategies/public/list');
    return response;
  } catch (error) {
    console.error('Error fetching public strategies:', error);
    throw error;
  }
}

// Get single strategy details with full metrics
export async function getStrategyDetails(strategyId: string): Promise<StrategyMetrics> {
  try {
    const response = await apiGet<StrategyMetrics>(`/api/strategies/${strategyId}`);
    return response;
  } catch (error) {
    console.error('Error fetching strategy details:', error);
    throw error;
  }
}

// Create a new strategy
export async function createStrategy(data: Partial<StrategyMetrics>): Promise<StrategyMetrics> {
  try {
    const response = await apiPost<StrategyMetrics>('/api/strategies', data);
    return response;
  } catch (error) {
    console.error('Error creating strategy:', error);
    throw error;
  }
}

// Update strategy
export async function updateStrategy(
  strategyId: string,
  data: Partial<StrategyMetrics>
): Promise<StrategyMetrics> {
  try {
    const response = await apiPut<StrategyMetrics>(`/api/strategies/${strategyId}`, data);
    return response;
  } catch (error) {
    console.error('Error updating strategy:', error);
    throw error;
  }
}

// Clone a strategy
export async function cloneStrategy(strategyId: string): Promise<StrategyMetrics> {
  try {
    const response = await apiPost<StrategyMetrics>(
      `/api/strategies/${strategyId}/clone`,
      {}
    );
    return response;
  } catch (error) {
    console.error('Error cloning strategy:', error);
    throw error;
  }
}

// Delete a strategy
export async function deleteStrategy(strategyId: string): Promise<void> {
  try {
    await apiDelete(`/api/strategies/${strategyId}`);
  } catch (error) {
    console.error('Error deleting strategy:', error);
    throw error;
  }
}

// Toggle strategy visibility
export async function toggleStrategyVisibility(strategyId: string): Promise<StrategyMetrics> {
  try {
    const response = await apiPut<StrategyMetrics>(
      `/api/strategies/${strategyId}/toggle-visibility`,
      {}
    );
    return response;
  } catch (error) {
    console.error('Error toggling strategy visibility:', error);
    throw error;
  }
}

// Activate a strategy
export async function activateStrategy(strategyId: string): Promise<StrategyMetrics> {
  try {
    const response = await apiPost<StrategyMetrics>(
      `/api/strategies/${strategyId}/activate`,
      {}
    );
    return response;
  } catch (error) {
    console.error('Error activating strategy:', error);
    throw error;
  }
}

// Deactivate a strategy
export async function deactivateStrategy(strategyId: string): Promise<StrategyMetrics> {
  try {
    const response = await apiPost<StrategyMetrics>(
      `/api/strategies/${strategyId}/deactivate`,
      {}
    );
    return response;
  } catch (error) {
    console.error('Error deactivating strategy:', error);
    throw error;
  }
}

// Get strategy performance metrics
export async function getStrategyPerformance(
  strategyId: string,
  days: number = 30
): Promise<any> {
  try {
    const response = await apiGet(`/api/strategies/${strategyId}/performance?days=${days}`);
    return response;
  } catch (error) {
    console.error('Error fetching strategy performance:', error);
    throw error;
  }
}

// Get top performing strategies
export async function getTopStrategies(limit: number = 10): Promise<StrategyMetrics[]> {
  try {
    const response = await apiGet<StrategyMetrics[]>(
      `/api/strategies/public/top?limit=${limit}`
    );
    return response;
  } catch (error) {
    console.error('Error fetching top strategies:', error);
    throw error;
  }
}

// Share a strategy
export async function shareStrategy(strategyId: string): Promise<{ shareUrl: string }> {
  try {
    const response = await apiPost<{ shareUrl: string }>(
      `/api/strategies/${strategyId}/share`,
      {}
    );
    return response;
  } catch (error) {
    console.error('Error sharing strategy:', error);
    throw error;
  }
}

// Get real-time strategy status (websocket alternative for polling)
export async function getStrategyStatus(strategyId: string): Promise<any> {
  try {
    const response = await apiGet(`/api/strategies/${strategyId}/status`);
    return response;
  } catch (error) {
    console.error('Error fetching strategy status:', error);
    throw error;
  }
}

// Subscribe to WebSocket updates for a strategy
export function subscribeToStrategyUpdates(
  strategyId: string,
  onUpdate: (data: any) => void,
  onError: (error: any) => void
): WebSocket | null {
  try {
    const wsUrl = `${API_BASE_URL.replace(/^http/, 'ws')}/ws/strategies/${strategyId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`Connected to strategy ${strategyId} updates`);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onUpdate(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError(error);
    };

    ws.onclose = () => {
      console.log(`Disconnected from strategy ${strategyId} updates`);
    };

    return ws;
  } catch (error) {
    console.error('Error subscribing to strategy updates:', error);
    onError(error);
    return null;
  }
}

export const strategyService = {
  getStrategies,
  getPublicStrategies,
  getStrategyDetails,
  createStrategy,
  updateStrategy,
  cloneStrategy,
  deleteStrategy,
  toggleStrategyVisibility,
  activateStrategy,
  deactivateStrategy,
  getStrategyPerformance,
  getTopStrategies,
  shareStrategy,
  getStrategyStatus,
  subscribeToStrategyUpdates,
};

export default strategyService;
