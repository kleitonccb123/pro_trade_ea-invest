/**
 * Hook: useTokenRefreshMonitoring
 *
 * Monitors authentication status and handles:
 * - Token expiration detection (checks every 30 seconds, not 60)
 * - Automatic token refresh before expiration (proactive)
 * - WebSocket reconnection after refresh
 * - User logout on refresh failure
 */

import { useEffect, useRef } from 'react';
import { authService } from '@/services/authService';
import { useAuthStore } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';

export function useTokenRefreshMonitoring(): void {
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const wasAuthenticatedRef = useRef(false);
  const { handleCritical401 } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    const checkAndRefreshToken = async () => {
      const { isValid, hasAccessToken, hasRefreshToken } = authService.validateTokens();

      if (!hasAccessToken || !hasRefreshToken) {
        // No tokens - user is logged out
        if (wasAuthenticatedRef.current) {
          console.warn('[⚠️] User logged out - no valid tokens');
          wasAuthenticatedRef.current = false;
        }
        return;
      }

      wasAuthenticatedRef.current = true;

      // Check if token is about to expire (within 5 minutes)
      const tokens = authService.getTokens();
      if (tokens.accessToken) {
        try {
          const payload = JSON.parse(
            atob(tokens.accessToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
          );
          const expiresAt = payload.exp * 1000; // Convert to milliseconds
          const timeUntilExpiry = expiresAt - Date.now();
          const FIVE_MINUTES = 5 * 60 * 1000;

          // If token expires within 5 minutes, refresh it proactively
          if (timeUntilExpiry < FIVE_MINUTES && timeUntilExpiry > 0) {
            console.log('[ℹ️] Token expiring soon, refreshing proactively...');

            const newToken = await authService.refreshAccessToken();

            if (newToken) {
              console.log('[✓] Token refreshed successfully');

              // Dispatch event so WebSocket and other services know to reconnect
              window.dispatchEvent(new CustomEvent('tokenRefreshed', {
                detail: { newToken }
              }));
            } else {
              // Refresh failed - user needs to login again
              console.error('[✗] Token refresh failed');
              authService.clearTokens();

              window.dispatchEvent(new CustomEvent('authExpired', {
                detail: { reason: 'token_refresh_failed' }
              }));
            }
          } else if (timeUntilExpiry <= 0) {
            // Token already expired
            console.warn('[⚠️] Token has expired');
            const newToken = await authService.refreshAccessToken();

            if (!newToken) {
              authService.clearTokens();
              window.dispatchEvent(new CustomEvent('authExpired', {
                detail: { reason: 'token_expired' }
              }));
            }
          }
        } catch (err) {
          console.error('[✗] Error parsing token:', err);
        }
      }
    };

    // Check token status every 30 seconds (not 60) for faster detection
    refreshIntervalRef.current = setInterval(checkAndRefreshToken, 30_000);

    // Run once immediately
    checkAndRefreshToken();

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, []);

  // Listen for authExpired event and redirect to login
  useEffect(() => {
    const handleAuthExpired = (event: any) => {
      const reason = event.detail?.reason;
      console.error('[🚨] Authentication expired:', reason);
      
      // Clear auth state
      handleCritical401();
      
      // Redirect to login
      navigate('/login', { replace: true });
    };

    window.addEventListener('authExpired', handleAuthExpired);
    return () => {
      window.removeEventListener('authExpired', handleAuthExpired);
    };
  }, [handleCritical401, navigate]);

  // Listen for auth-related events
  useEffect(() => {
    const handleTokenRefreshed = () => {
      console.log('[ℹ️] Token refresh event received - reconnecting WebSocket...');
      window.dispatchEvent(new CustomEvent('websocketReconnectNeeded'));
    };

    const handleAuthExpired = () => {
      console.log('[ℹ️] Auth expired event received - redirecting to login...');
      // Redirect to login page
      window.location.href = '/login';
    };

    window.addEventListener('tokenRefreshed', handleTokenRefreshed);
    window.addEventListener('authExpired', handleAuthExpired);

    return () => {
      window.removeEventListener('tokenRefreshed', handleTokenRefreshed);
      window.removeEventListener('authExpired', handleAuthExpired);
    };
  }, []);
}
