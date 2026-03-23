import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '@/context/AuthContext';
import { authService } from '@/services/authService';
import { WS_BASE_URL, WS_TIMEOUT, WS_RECONNECT_CONFIG, DEBUG_MODE } from '@/config/constants';

interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
}

interface UseWebSocketOptions {
  url: string;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
  requireAuth?: boolean;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  isReconnecting: boolean;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'failed';
  reconnectAttempts: number;
  lastMessage: WebSocketMessage | null;
  sendMessage: (message: any) => void;
  disconnect: () => void;
  connect: () => void;
}

/**
 * Sanitize URL to remove duplicate slashes (except in protocol)
 * Example: ws://localhost:8000//emergency/ws -> ws://localhost:8000/emergency/ws
 * 
 * @param url URL to sanitize
 * @returns Sanitized URL
 */
const sanitizeUrl = (url: string): string => {
  return url.replace(/([^:])\/{2,}/g, '$1/');
};

/**
 * Convert HTTP(S) URL to WebSocket URL safely using URL API
 * 
 * @param httpUrl HTTP(S) URL
 * @returns WebSocket URL (ws:// or wss://)
 */
const httpToWsUrl = (httpUrl: string): string => {
  try {
    const url = new URL(httpUrl);
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return sanitizeUrl(`${protocol}//${url.host}${url.pathname}`);
  } catch (error) {
    console.error('[WebSocket] Failed to convert HTTP URL to WS:', httpUrl, error);
    // Fallback: simple replacement (less reliable)
    return sanitizeUrl(httpUrl.replace(/^https?:/, (match) => match === 'https:' ? 'wss:' : 'ws:'));
  }
};

/**
 * Build WebSocket URL with query parameters
 * 
 * @param baseUrl Base WebSocket URL
 * @param token Optional authentication token
 * @returns Complete WebSocket URL with parameters
 */
const buildWsUrl = (baseUrl: string, token?: string | null): string => {
  try {
    const url = new URL(baseUrl);
    
    if (token) {
      url.searchParams.set('token', token);
    }
    
    return url.toString();
  } catch (error) {
    console.error('[WebSocket] Failed to build URL:', baseUrl, error);
    // Fallback: manual parameter addition
    const separator = baseUrl.includes('?') ? '&' : '?';
    return token ? `${baseUrl}${separator}token=${encodeURIComponent(token)}` : baseUrl;
  }
};

export function useWebSocket({
  url,
  onMessage,
  onConnect,
  onDisconnect,
  onError,
  autoReconnect = WS_RECONNECT_CONFIG.enabled,
  reconnectInterval = WS_RECONNECT_CONFIG.initialDelayMs,
  requireAuth = true
}: UseWebSocketOptions): UseWebSocketReturn {
  // Get auth state from context
  const { isAuthenticated } = useAuthStore();
  
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'failed'>('disconnected');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  
  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = WS_RECONNECT_CONFIG.maxAttempts;

  // Refs to read latest connection state inside effects without adding them as deps
  const isConnectedRef = useRef(false);
  const connectionStateRef = useRef<'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'failed'>('disconnected');

  /**
   * Lazy Connection: Only connect if user is authenticated
   * This prevents connection with invalid/missing tokens
   */
  const shouldConnect = (): boolean => {
    if (!requireAuth) {
      return true; // Connect even without auth
    }
    
    const authToken = authService.getAccessToken();
    if (!authToken) {
      if (DEBUG_MODE) {
        console.log('[WebSocket] Skipping connection - no auth token available');
      }
      return false;
    }
    
    return isAuthenticated;
  };

  const connect = useCallback(() => {
    // ⚠️ LAZY CONNECTION: Don't connect if auth is required but not available
    if (!shouldConnect()) {
      if (DEBUG_MODE) {
        console.log('[WebSocket] Lazy connection: User not authenticated, delaying connection');
      }
      setConnectionState('disconnected');
      return;
    }

    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setConnectionState('connecting');
    setIsReconnecting(false);

    try {
      // Build WebSocket URL with proper timeout
      let wsUrl = url;
      
      // Convert HTTP to WS if needed
      if (url.startsWith('http://') || url.startsWith('https://')) {
        wsUrl = httpToWsUrl(url);
      }
      
      // Use WS_BASE_URL if url is relative
      if (url.startsWith('/')) {
        wsUrl = sanitizeUrl(`${WS_BASE_URL}${url}`);
      }
      
      // Add auth token if required
      if (requireAuth) {
        const token = authService.getAccessToken();
        wsUrl = buildWsUrl(wsUrl, token);
      }
      
      if (DEBUG_MODE) {
        console.log('[WebSocket] Connecting to:', wsUrl.split('?')[0]); // Hide token in logs
      }

      const ws = new WebSocket(wsUrl);
      
      // Set connection timeout
      const connectionTimeoutId = setTimeout(() => {
        if (ws.readyState === WebSocket.CONNECTING) {
          console.warn('[WebSocket] Connection timeout, closing...');
          ws.close();
        }
      }, WS_TIMEOUT);
      
      websocketRef.current = ws;

      ws.onopen = () => {
        clearTimeout(connectionTimeoutId);
        console.log('[WebSocket] ✅ Connected');
        setIsConnected(true);
        setConnectionState('connected');
        setIsReconnecting(false);
        setReconnectAttempts(0);
        reconnectAttemptsRef.current = 0;
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessage?.(message);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      ws.onclose = () => {
        clearTimeout(connectionTimeoutId);
        console.log('[WebSocket] ❌ Disconnected');
        setIsConnected(false);
        setConnectionState('disconnected');
        websocketRef.current = null;
        onDisconnect?.();

        // Auto-reconnect logic
        if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts && shouldConnect()) {
          reconnectAttemptsRef.current += 1;
          setReconnectAttempts(reconnectAttemptsRef.current);
          setIsReconnecting(true);
          setConnectionState('reconnecting');
          
          // Exponential backoff with max delay cap
          const delay = Math.min(
            reconnectInterval * Math.pow(1.5, reconnectAttemptsRef.current - 1),
            WS_RECONNECT_CONFIG.maxDelayMs
          );
          
          console.log(`[WebSocket] 🔄 Reconnect attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts} in ${Math.round(delay / 1000)}s...`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          setConnectionState('failed');
          setIsReconnecting(false);
          console.error('[WebSocket] ⚠️ Max reconnection attempts reached');
        }
      };

      ws.onerror = (error) => {
        clearTimeout(connectionTimeoutId);
        console.error('[WebSocket] Error:', error);
        setConnectionState('disconnected');
        onError?.(error);
      };
    } catch (error) {
      console.error('[WebSocket] Failed to create WebSocket connection:', error);
      setConnectionState('failed');
    }
  }, [url, onConnect, onMessage, onDisconnect, onError, autoReconnect, reconnectInterval, requireAuth, isAuthenticated]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }
    
    setIsConnected(false);
    setIsReconnecting(false);
    setConnectionState('disconnected');
    setReconnectAttempts(0);
    reconnectAttemptsRef.current = maxReconnectAttempts; // Prevent auto-reconnect
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Message not sent:', message);
    }
  }, []);

  // Keep refs in sync with state (reading refs in effects avoids adding state as deps)
  isConnectedRef.current = isConnected;
  connectionStateRef.current = connectionState;

  useEffect(() => {
    /**
     * Monitor authentication status and connect/disconnect accordingly.
     * We intentionally omit isConnected / connectionState from deps and read
     * them via refs instead — adding them caused an infinite loop because every
     * failed connection attempt cycled the state and re-triggered this effect,
     * whose cleanup called disconnect() and whose body called connect().
     */
    if (requireAuth) {
      if (isAuthenticated && !isConnectedRef.current && connectionStateRef.current !== 'connecting') {
        if (DEBUG_MODE) {
          console.log('[WebSocket] Auth detected, initiating connection...');
        }
        connect();
      } else if (!isAuthenticated && isConnectedRef.current) {
        if (DEBUG_MODE) {
          console.log('[WebSocket] Auth lost, disconnecting...');
        }
        disconnect();
      }
    } else {
      // If auth not required, connect on mount
      if (!isConnectedRef.current) {
        connect();
      }
    }

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connect, disconnect, isAuthenticated, requireAuth]); // isConnected/connectionState intentionally omitted — use refs above

  // Listen for token refresh events and reconnect WebSocket
  useEffect(() => {
    const handleTokenRefreshed = () => {
      console.log('[WebSocket] Token refreshed event received - reconnecting...');
      // Disconnect and reconnect to use new token
      if (websocketRef.current) {
        websocketRef.current.close();
      }
      // Reset reconnect attempts to allow new connection
      reconnectAttemptsRef.current = 0;
      setReconnectAttempts(0);
      // Trigger reconnection with new token
      setTimeout(() => {
        connect();
      }, 100);
    };

    const handleWebsocketReconnectNeeded = () => {
      console.log('[WebSocket] Reconnect needed event received...');
      reconnectAttemptsRef.current = 0;
      setReconnectAttempts(0);
      connect();
    };

    window.addEventListener('tokenRefreshed', handleTokenRefreshed);
    window.addEventListener('websocketReconnectNeeded', handleWebsocketReconnectNeeded);

    return () => {
      window.removeEventListener('tokenRefreshed', handleTokenRefreshed);
      window.removeEventListener('websocketReconnectNeeded', handleWebsocketReconnectNeeded);
    };
  }, [connect]);

  return {
    isConnected,
    isReconnecting,
    connectionState,
    reconnectAttempts,
    lastMessage,
    sendMessage,
    disconnect,
    connect
  };
}

// Specialized hook for trading WebSocket
export function useTradingWebSocket(clientType: 'dashboard' | 'robots' | 'trades' = 'dashboard') {
  const [trades, setTrades] = useState<any[]>([]);
  const [klineData, setKlineData] = useState<any[]>([]);
  const [robotStatus, setRobotStatus] = useState<Record<number, any>>({});

  const { isConnected, sendMessage } = useWebSocket({
    url: `/api/bots/ws/${clientType}`,
    onMessage: (message) => {
      switch (message.type) {
        case 'trade_update':
          setTrades(prev => [message.data, ...prev.slice(0, 99)]); // Keep last 100 trades
          break;
        case 'kline_update':
          setKlineData(prev => {
            const newData = [...prev];
            const existingIndex = newData.findIndex(
              k => k.symbol === message.data.symbol && k.open_time === message.data.open_time
            );
            
            if (existingIndex >= 0) {
              newData[existingIndex] = message.data;
            } else {
              newData.push(message.data);
            }
            
            return newData.slice(-500); // Keep last 500 klines
          });
          break;
        case 'robot_status':
          setRobotStatus(prev => ({
            ...prev,
            [message.data.instance_id]: message.data
          }));
          break;
      }
    },
    onConnect: () => {
      console.log('Trading WebSocket connected');
    },
    onDisconnect: () => {
      console.log('Trading WebSocket disconnected');
    }
  });

  return {
    isConnected,
    trades,
    klineData,
    robotStatus,
    sendMessage
  };
}

// ============== SYSTEM HEALTH WEBSOCKET ==============
interface SystemHealthState {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  database: boolean;
  botsRunning: number;
  circuitBreakerOpen: boolean;
  lastUpdate: string | null;
}

export function useSystemHealthWebSocket() {
  const [health, setHealth] = useState<SystemHealthState>({
    status: 'unknown',
    database: false,
    botsRunning: 0,
    circuitBreakerOpen: false,
    lastUpdate: null,
  });

  const { isConnected, sendMessage } = useWebSocket({
    url: `/api/system/health/ws`,
    onMessage: (message) => {
      if (message.type === 'health_update') {
        setHealth({
          status: message.data.status || 'unknown',
          database: message.data.database?.status === 'ok',
          botsRunning: message.data.bots_running || 0,
          circuitBreakerOpen: message.data.circuit_breaker_open || false,
          lastUpdate: message.timestamp,
        });
      }
    },
    autoReconnect: true,
    reconnectInterval: 5000,
  });

  // Request health update
  const requestUpdate = useCallback(() => {
    sendMessage({ type: 'request_health' });
  }, [sendMessage]);

  return {
    isConnected,
    health,
    requestUpdate,
  };
}

// ============== KILL SWITCH WEBSOCKET ==============
interface KillSwitchState {
  isActive: boolean;
  activatedAt: string | null;
  activatedBy: string | null;
  reason: string | null;
  affectedBots: number;
  cancelledOrders: number;
}

export function useKillSwitchWebSocket() {
  const [killSwitch, setKillSwitch] = useState<KillSwitchState>({
    isActive: false,
    activatedAt: null,
    activatedBy: null,
    reason: null,
    affectedBots: 0,
    cancelledOrders: 0,
  });

  const { isConnected, sendMessage } = useWebSocket({
    url: `/api/emergency/ws`,
    onMessage: (message) => {
      if (message.type === 'kill_switch_update' || message.type === 'kill_switch_activated') {
        setKillSwitch({
          isActive: message.data.is_active,
          activatedAt: message.data.activated_at || null,
          activatedBy: message.data.activated_by || null,
          reason: message.data.reason || null,
          affectedBots: message.data.affected_bots || 0,
          cancelledOrders: message.data.cancelled_orders || 0,
        });
      }
    },
    autoReconnect: true,
    reconnectInterval: 3000,
  });

  return {
    isConnected,
    killSwitch,
    sendMessage,
  };
}

// ============== PNL REAL-TIME WEBSOCKET ==============
interface PnLUpdate {
  timestamp: string;
  totalPnL: number;
  dailyPnL: number;
  unrealizedPnL: number;
  tradeCount: number;
}

export function usePnLWebSocket() {
  const [pnlData, setPnlData] = useState<PnLUpdate[]>([]);
  const [currentPnL, setCurrentPnL] = useState<PnLUpdate | null>(null);

  const { isConnected, sendMessage } = useWebSocket({
    url: `/api/analytics/pnl/ws`,
    onMessage: (message) => {
      if (message.type === 'pnl_update') {
        const update: PnLUpdate = {
          timestamp: message.timestamp,
          totalPnL: message.data.total_pnl || 0,
          dailyPnL: message.data.daily_pnl || 0,
          unrealizedPnL: message.data.unrealized_pnl || 0,
          tradeCount: message.data.trade_count || 0,
        };
        setCurrentPnL(update);
        setPnlData(prev => [...prev.slice(-100), update]); // Keep last 100 points
      }
    },
    autoReconnect: true,
    reconnectInterval: 3000,
  });

  return {
    isConnected,
    currentPnL,
    pnlData,
    sendMessage,
  };
}

// ============== NOTIFICATIONS WEBSOCKET ==============
interface NotificationUpdate {
  id: number;
  type: string;
  title: string;
  message: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
}

export function useNotificationsWebSocket() {
  const [notifications, setNotifications] = useState<NotificationUpdate[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const { isConnected, sendMessage } = useWebSocket({
    url: `/api/notifications/ws`,
    onMessage: (message) => {
      switch (message.type) {
        case 'notification':
          const notification: NotificationUpdate = {
            id: message.data.id,
            type: message.data.type,
            title: message.data.title,
            message: message.data.message,
            priority: message.data.priority || 'medium',
            timestamp: message.timestamp,
          };
          setNotifications(prev => [notification, ...prev.slice(0, 49)]);
          setUnreadCount(prev => prev + 1);
          break;
        case 'unread_count':
          setUnreadCount(message.data.count || 0);
          break;
      }
    },
    autoReconnect: true,
    reconnectInterval: 5000,
  });

  const markAsRead = useCallback((notificationId: number) => {
    sendMessage({ type: 'mark_read', notification_id: notificationId });
    setUnreadCount(prev => Math.max(0, prev - 1));
  }, [sendMessage]);

  const markAllAsRead = useCallback(() => {
    sendMessage({ type: 'mark_all_read' });
    setUnreadCount(0);
  }, [sendMessage]);

  return {
    isConnected,
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
  };
}