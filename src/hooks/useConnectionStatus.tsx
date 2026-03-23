import { useContext } from 'react';
import { ConnectionStatusContext } from '@/context/ConnectionStatusContext';

export function useConnectionStatus() {
  const context = useContext(ConnectionStatusContext);
  if (context === undefined) {
    throw new Error('useConnectionStatus must be used within a ConnectionStatusProvider');
  }
  return context;
}

export default useConnectionStatus;
