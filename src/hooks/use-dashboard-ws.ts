import { useCallback, useEffect, useMemo } from 'react';
import { API_BASE_URL } from '@/config/constants';
import { useWebSocket, type UseWebSocketReturn } from '@/hooks/use-websocket';
import { authService } from '@/services/authService';

const NOOP_WS: UseWebSocketReturn = {
  isConnected: false,
  isReconnecting: false,
  connectionState: 'disconnected' as const,
  reconnectAttempts: 0,
  lastMessage: null,
  sendMessage: () => {},
  disconnect: () => {},
  connect: () => {},
};

export function useDashboardWS(): UseWebSocketReturn {
  // Always use authService to get token (handles both sessionStorage and in-memory storage)
  const token = authService.getAccessToken();
  const hasToken = !!token;
  
  const wsBase = API_BASE_URL.replace(/^http/, 'ws').replace(/\/$/, '');
  const url = hasToken ? `${wsBase}/ws/notifications?token=${token}` : '';

  const onMessage = useCallback((message: any) => {
    try {
      const now = Date.now();
      const parsed = typeof message === 'string' ? JSON.parse(message) : message;
      console.debug('[WS][dashboard] received', { at: new Date(now).toISOString(), message: parsed });
    } catch (e) {
      console.debug('[WS][dashboard] received (raw)', message);
    }
  }, []);

  const ws = useWebSocket({ url: url || 'disabled', onMessage, autoReconnect: hasToken, reconnectInterval: 3000 });

  // If no token, return a safe no-op object that won't crash destructuring
  const result = hasToken ? ws : NOOP_WS;

  // Lightweight heartbeat: send a small ping every 15s while connected.
  // Kept minimal to avoid main-thread work. Do not cause state updates here.
  useEffect(() => {
    let id: number | null = null;
    if (result && result.isConnected && typeof window !== 'undefined') {
      id = window.setInterval(() => {
        try {
          if (result.isConnected) {
            result.sendMessage({ type: 'ping' });
          }
        } catch (e) {
          // ignore send errors
        }
      }, 15000);
    }

    return () => {
      if (id != null) window.clearInterval(id);
    };
  }, [result]);

  return result;
}
