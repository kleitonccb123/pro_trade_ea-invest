/**
 * useNotifications - Hook para gerenciar notificações em tempo real
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { notificationsApi, Notification, NotificationListResponse } from '@/lib/api';
import { API_BASE_URL } from '@/config/constants';
import { useToast } from './use-toast';

interface UseNotificationsOptions {
  enableWebSocket?: boolean;
  autoConnect?: boolean;
}

interface UseNotificationsReturn {
  notifications: Notification[];
  unreadCount: number;
  total: number;
  loading: boolean;
  error: string | null;
  connected: boolean;
  
  // Actions
  fetchNotifications: (params?: { limit?: number; offset?: number; unread_only?: boolean }) => Promise<void>;
  markAsRead: (ids: number[]) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  deleteNotification: (id: number) => Promise<void>;
  sendTestNotification: () => Promise<void>;
  connect: () => void;
  disconnect: () => void;
}

export function useNotifications(options: UseNotificationsOptions = {}): UseNotificationsReturn {
  const { enableWebSocket = true, autoConnect = true } = options;
  
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const { toast } = useToast();
  
  // Fetch notifications from API
  const fetchNotifications = useCallback(async (params?: { limit?: number; offset?: number; unread_only?: boolean }) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await notificationsApi.getNotifications(params);
      setNotifications(response.notifications);
      setTotal(response.total);
      setUnreadCount(response.unread_count);
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar notificações');
      console.error('Error fetching notifications:', err);
    } finally {
      setLoading(false);
    }
  }, []);
  
  // Mark notifications as read
  const markAsRead = useCallback(async (ids: number[]) => {
    try {
      await notificationsApi.markAsRead(ids);
      
      // Update local state
      setNotifications(prev => 
        prev.map(n => 
          ids.includes(n.id) ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
        )
      );
      setUnreadCount(prev => Math.max(0, prev - ids.length));
    } catch (err: any) {
      console.error('Error marking as read:', err);
      throw err;
    }
  }, []);
  
  // Mark all as read
  const markAllAsRead = useCallback(async () => {
    try {
      await notificationsApi.markAllAsRead();
      
      setNotifications(prev => 
        prev.map(n => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      );
      setUnreadCount(0);
    } catch (err: any) {
      console.error('Error marking all as read:', err);
      throw err;
    }
  }, []);
  
  // Delete notification
  const deleteNotification = useCallback(async (id: number) => {
    try {
      await notificationsApi.deleteNotification(id);
      
      setNotifications(prev => prev.filter(n => n.id !== id));
      setTotal(prev => prev - 1);
      
      // Update unread count if was unread
      const notification = notifications.find(n => n.id === id);
      if (notification && !notification.is_read) {
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (err: any) {
      console.error('Error deleting notification:', err);
      throw err;
    }
  }, [notifications]);
  
  // Send test notification
  const sendTestNotification = useCallback(async () => {
    try {
      const result = await notificationsApi.sendTestNotification();
      if (result.success) {
        toast({
          title: 'Notificação de teste enviada!',
          description: 'Verifique suas notificações.',
        });
      }
    } catch (err: any) {
      toast({
        title: 'Erro ao enviar teste',
        description: err.message,
        variant: 'destructive',
      });
    }
  }, [toast]);
  
  // WebSocket connection
  const connect = useCallback(() => {
    if (!enableWebSocket) return;
    
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.log('No token, skipping WebSocket connection');
      return;
    }
    
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }
    
    const wsBase = API_BASE_URL.replace('http', 'ws');
    const wsUrl = `${wsBase}/notifications/ws?token=${token}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('Notification WebSocket connected');
        setConnected(true);
        setError(null);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'notification') {
            // Nova notificação recebida
            const newNotification: Notification = {
              id: data.notification.id,
              type: data.notification.type,
              priority: 'medium',
              title: data.notification.title,
              message: data.notification.message,
              data: data.notification.data,
              is_read: false,
              sent_push: true,
              sent_email: false,
              created_at: data.notification.timestamp,
            };
            
            setNotifications(prev => [newNotification, ...prev]);
            setUnreadCount(prev => prev + 1);
            setTotal(prev => prev + 1);
            
            // Show toast for new notification
            toast({
              title: newNotification.title,
              description: newNotification.message,
            });
          } else if (data.type === 'unread_count') {
            setUnreadCount(data.count);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };
      
      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('Erro na conexão de notificações');
      };
      
      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setConnected(false);
        
        // Reconnect after 5 seconds if not intentionally closed
        if (event.code !== 1000 && event.code !== 4001) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('Attempting WebSocket reconnection...');
            connect();
          }, 5000);
        }
      };
    } catch (err) {
      console.error('Error creating WebSocket:', err);
      setError('Erro ao conectar notificações');
    }
  }, [enableWebSocket, toast]);
  
  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnect');
      wsRef.current = null;
    }
    setConnected(false);
  }, []);
  
  // Auto-connect and fetch on mount
  useEffect(() => {
    fetchNotifications({ limit: 20 });
    
    if (autoConnect && enableWebSocket) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, []);
  
  // Ping to keep connection alive
  useEffect(() => {
    if (!connected || !wsRef.current) return;
    
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
    
    return () => clearInterval(pingInterval);
  }, [connected]);
  
  return {
    notifications,
    unreadCount,
    total,
    loading,
    error,
    connected,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    sendTestNotification,
    connect,
    disconnect,
  };
}

export default useNotifications;
