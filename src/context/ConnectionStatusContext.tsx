import React, { createContext, useState, useEffect, ReactNode, useMemo, useContext } from 'react';

interface ConnectionStatus {
  isOnline: boolean;
  websocketState: 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'failed';
  isReconnecting: boolean;
  reconnectAttempts: number;
  lastConnectedAt: Date | null;
  lastDisconnectedAt: Date | null;
}

interface ConnectionStatusContextType {
  connectionStatus: ConnectionStatus;
  setConnectionStatus: React.Dispatch<React.SetStateAction<ConnectionStatus>>;
}

export const ConnectionStatusContext = createContext<ConnectionStatusContextType | undefined>(undefined);

// Re-export useConnectionStatus hook for compatibility
export function useConnectionStatus() {
  const context = useContext(ConnectionStatusContext);
  if (context === undefined) {
    throw new Error('useConnectionStatus must be used within a ConnectionStatusProvider');
  }
  return context;
}

interface ConnectionStatusProviderProps {
  children: ReactNode;
}

export function ConnectionStatusProvider({ children }: ConnectionStatusProviderProps) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    isOnline: navigator.onLine,
    websocketState: 'disconnected',
    isReconnecting: false,
    reconnectAttempts: 0,
    lastConnectedAt: null,
    lastDisconnectedAt: null,
  });

  // Monitor browser online/offline status
  useEffect(() => {
    const handleOnline = () => {
      setConnectionStatus(prev => ({
        ...prev,
        isOnline: true,
      }));
    };

    const handleOffline = () => {
      setConnectionStatus(prev => ({
        ...prev,
        isOnline: false,
        websocketState: 'disconnected',
        lastDisconnectedAt: new Date(),
      }));
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const value = useMemo(() => ({ connectionStatus, setConnectionStatus }), [connectionStatus, setConnectionStatus]);

  return (
    <ConnectionStatusContext.Provider value={value}>
      {children}
    </ConnectionStatusContext.Provider>
  );
}
