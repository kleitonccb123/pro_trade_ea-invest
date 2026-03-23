/**
 * Authentication Service
 * 
 * Centralized token management for the entire application.
 * Provides methods for:
 * - Getting/setting access and refresh tokens
 * - Validating token existence
 * - Clearing tokens
 * - Refreshing expired tokens
 * 
 * This service acts as the single source of truth for token management.
 * All components and hooks should use this service instead of directly
 * accessing localStorage or context state.
 */

import { STORAGE_KEYS, AUTH_CONFIG, API_BASE_URL, DEBUG_MODE } from '@/config/constants';

/**
 * Token data stored in localStorage
 */
interface StoredTokens {
  accessToken: string | null;
  refreshToken: string | null;
}

/**
 * Validation result for token status
 */
interface TokenValidationResult {
  isValid: boolean;
  hasAccessToken: boolean;
  hasRefreshToken: boolean;
  isExpired: (token: string) => boolean;
}

class AuthService {
  private static instance: AuthService;

  /**
   * Primary in-memory store for the access token.
   * Falls back to sessionStorage for page-reload resilience.
   * The refresh token is NEVER stored in JS — it lives in an httpOnly cookie.
   */
  private _accessToken: string | null = null;

  /**
   * Get singleton instance of AuthService
   */
  static getInstance(): AuthService {
    if (!AuthService.instance) {
      AuthService.instance = new AuthService();
    }
    return AuthService.instance;
  }

  /**
   * Get both access and refresh tokens from localStorage
   * 
   * @returns Object containing both tokens or null values if not found
   * 
   * @example
   * const { accessToken, refreshToken } = authService.getTokens();
   */
  getTokens(): StoredTokens {
    return {
      accessToken: this.getAccessToken(),
      refreshToken: null, // refresh token lives in httpOnly cookie only
    };
  }

  /**
   * Get only the access token
   * 
   * @returns Access token string or null if not found
   * 
   * @example
   * const token = authService.getAccessToken();
   * console.log('Token:', token);
   */
  getAccessToken(): string | null {
    // Prefer in-memory; fall back to sessionStorage for page-reload resilience
    if (this._accessToken) return this._accessToken;
    try {
      const stored = sessionStorage.getItem(STORAGE_KEYS.auth.accessToken);
      if (stored) {
        this._accessToken = stored; // restore to memory
        return stored;
      }
    } catch { /* ignore */ }
    return null;
  }

  /**
   * Refresh token is stored in httpOnly cookie by the backend.
   * This method is kept for API compatibility but always returns null.
   */
  getRefreshToken(): string | null {
    return null;
  }

  /**
   * Set both access and refresh tokens in localStorage
   * 
   * Stores tokens securely in localStorage and triggers storage events
   * for other tabs/windows to stay in sync.
   * 
   * @param accessToken - JWT access token
   * @param refreshToken - JWT refresh token
   * 
   * @throws Error if localStorage fails
   * 
   * @example
   * authService.setTokens(accessToken, refreshToken);
   */
  setTokens(accessToken: string | null, _refreshToken: string | null): void {
    // _refreshToken is intentionally ignored: it is delivered as an httpOnly
    // cookie by the backend and must NOT be stored in JS-accessible storage.
    this._accessToken = accessToken;
    try {
      if (accessToken) {
        sessionStorage.setItem(STORAGE_KEYS.auth.accessToken, accessToken);
      } else {
        sessionStorage.removeItem(STORAGE_KEYS.auth.accessToken);
      }
      // Clean up any legacy localStorage entries
      localStorage.removeItem(STORAGE_KEYS.auth.accessToken);
      localStorage.removeItem(STORAGE_KEYS.auth.refreshToken);
    } catch { /* ignore storage errors */ }

    if (DEBUG_MODE) {
      console.log('[AuthService] setTokens() - access token stored in memory + sessionStorage');
    }

    window.dispatchEvent(new CustomEvent('tokensUpdated', {
      detail: { accessToken: !!accessToken, refreshToken: false }
    }));
  }

  /**
   * Set access token only
   * 
   * @param accessToken - JWT access token or null to clear
   */
  setAccessToken(accessToken: string | null): void {
    this._accessToken = accessToken;
    try {
      if (accessToken) {
        sessionStorage.setItem(STORAGE_KEYS.auth.accessToken, accessToken);
      } else {
        sessionStorage.removeItem(STORAGE_KEYS.auth.accessToken);
      }
    } catch { /* ignore */ }
    window.dispatchEvent(new CustomEvent('tokenUpdated', {
      detail: { type: 'accessToken' }
    }));
  }

  /**
   * Clear all tokens from localStorage
   * 
   * @example
   * authService.clearTokens(); // logout
   */
  clearTokens(): void {
    this._accessToken = null;
    try {
      sessionStorage.removeItem(STORAGE_KEYS.auth.accessToken);
      localStorage.removeItem(STORAGE_KEYS.auth.accessToken);
      localStorage.removeItem(STORAGE_KEYS.auth.refreshToken);
      localStorage.removeItem(STORAGE_KEYS.auth.user);
    } catch { /* ignore */ }

    if (DEBUG_MODE) {
      console.log('[AuthService] clearTokens() - all tokens removed');
    }

    window.dispatchEvent(new CustomEvent('tokensCleared'));
  }

  /**
   * Check if tokens exist and are valid
   * 
   * @returns Validation result with detailed status
   * 
   * @example
   * const { isValid, hasAccessToken } = authService.validateTokens();
   * if (isValid) {
   *   // User is authenticated
   * }
   */
  validateTokens(): TokenValidationResult {
    const accessToken = this.getAccessToken();
    return {
      isValid: !!accessToken && this.isTokenValid(accessToken),
      hasAccessToken: !!accessToken,
      hasRefreshToken: false, // refresh token in httpOnly cookie, not inspectable by JS
      isExpired: (token: string) => {
        try {
          const payload = this.parseJwt(token);
          const expiresAt = payload.exp * 1000;
          return Date.now() > expiresAt;
        } catch {
          return true;
        }
      },
    };
  }

  /**
   * Check if user is authenticated (has valid access token)
   * 
   * @returns True if access token exists and is not expired
   * 
   * @example
   * if (authService.isAuthenticated()) {
   *   // Show authenticated UI
   * }
   */
  isAuthenticated(): boolean {
    const { isValid } = this.validateTokens();
    return isValid;
  }

  /**
   * Parse JWT token and extract payload
   * 
   * @param token - JWT token string
   * @returns Decoded payload object
   * @throws Error if token is invalid
   * 
   * @internal
   */
  private parseJwt(token: string): Record<string, any> {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('[AuthService] Failed to parse JWT:', error);
      throw new Error('Invalid JWT token');
    }
  }

  /**
   * Check if JWT token is valid and not expired
   * 
   * @param token - JWT token string
   * @returns True if token is valid and not expired
   * 
   * @internal
   */
  private isTokenValid(token: string): boolean {
    try {
      const payload = this.parseJwt(token);
      const expiresAt = payload.exp * 1000; // Convert to milliseconds
      
      // Return true if not expired, false otherwise
      // Add 60 second buffer to avoid edge cases
      return Date.now() < (expiresAt - 60_000);
    } catch {
      return false;
    }
  }

  /**
   * Manually refresh the access token using refresh token
   * 
   * Makes an API call to refresh endpoint with refresh token.
   * 
   * @returns New access token if successful, null otherwise
   * 
   * @example
   * const newToken = await authService.refreshAccessToken();
   * if (newToken) {
   *   // Token refreshed successfully
   * } else {
   *   // Refresh failed, user needs to login again
   * }
   */
  async refreshAccessToken(): Promise<string | null> {
    try {
      // No body needed — the httpOnly refresh cookie is sent automatically
      const response = await fetch(`${API_BASE_URL}${AUTH_CONFIG.refreshTokenEndpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });

      if (!response.ok) {
        console.error('[AuthService] Token refresh failed with status:', response.status);
        this.clearTokens();
        return null;
      }

      const data = await response.json();
      const newAccessToken = data.access_token;

      if (newAccessToken) {
        this.setAccessToken(newAccessToken);
        if (DEBUG_MODE) {
          console.log('[AuthService] Access token refreshed successfully');
        }
        return newAccessToken;
      }

      return null;
    } catch (error) {
      console.error('[AuthService] Error refreshing token:', error);
      return null;
    }
  }

  /**
   * Get authorization header value for API requests
   * 
   * @returns Authorization header value or null if no token
   * 
   * @example
   * const authHeader = authService.getAuthHeader();
   * // Returns: "Bearer eyJhbG..." or null
   */
  getAuthHeader(): string | null {
    const token = this.getAccessToken();
    return token ? `Bearer ${token}` : null;
  }

  /**
   * Start monitoring token expiration and auto-refresh
   * 
   * This method sets up an interval that checks if the token is expiring soon
   * and automatically refreshes it before it expires. Useful for keeping
   * WebSocket and long-running operations authenticated.
   * 
   * @param expirationBufferMs - Time before actual expiration to refresh (default: 5 minutes)
   * @returns Cleanup function to stop monitoring
   * 
   * @example
   * // Start monitoring (will auto-refresh 5 minutes before expiration)
   * const stopMonitoring = authService.startTokenExpirationMonitor();
   * 
   * // Later, stop monitoring
   * stopMonitoring();
   */
  startTokenExpirationMonitor(expirationBufferMs: number = 5 * 60 * 1000): () => void {
    let monitoringInterval: NodeJS.Timeout | null = null;
    
    const monitor = async () => {
      try {
        const accessToken = this.getAccessToken();
        if (!accessToken) {
          if (DEBUG_MODE) console.log('[AuthService] No access token to monitor');
          return;
        }
        
        try {
          const payload = this.parseJwt(accessToken);
          const expiresAt = payload.exp * 1000; // Convert to milliseconds
          const timeUntilExpiry = expiresAt - Date.now();
          
          if (DEBUG_MODE) {
            console.log('[AuthService] Token expiration check:', {
              expiresIn: Math.round(timeUntilExpiry / 1000) + 's',
              willRefreshIn: Math.round((timeUntilExpiry - expirationBufferMs) / 1000) + 's',
            });
          }
          
          // If token expires within buffer period, refresh now
          if (timeUntilExpiry < expirationBufferMs) {
            console.log('[AuthService] Token expiring soon, refreshing now...');
            const newToken = await this.refreshAccessToken();
            
            if (newToken) {
              console.log('[✓] Token auto-refresh successful');
              // Dispatch event so WebSocket and other services know to reconnect
              window.dispatchEvent(new CustomEvent('tokenAutoRefreshed', {
                detail: { newToken }
              }));
            } else {
              console.warn('[⚠] Token auto-refresh failed, user needs to re-authenticate');
            }
          }
        } catch (parseError) {
          console.error('[AuthService] Error parsing JWT during expiration check:', parseError);
        }
      } catch (error) {
        console.error('[AuthService] Error in token expiration monitor:', error);
      }
    };
    
    // Check every 1 minute
    monitoringInterval = setInterval(monitor, 60_000);
    
    // Run once immediately
    monitor();
    
    // Return cleanup function
    return () => {
      if (monitoringInterval) {
        clearInterval(monitoringInterval);
        if (DEBUG_MODE) console.log('[AuthService] Token expiration monitor stopped');
      }
    };
  }

  /**
   * Listen for token updates (useful for syncing across tabs)
   * 
   * @param callback - Function to call when tokens change
   * @returns Unsubscribe function
   * 
   * @example
   * const unsubscribe = authService.onTokensChange(() => {
   *   // Refresh UI with new token status
   * });
   */
  onTokensChange(callback: () => void): () => void {
    const handleStorageChange = (e: StorageEvent) => {
      if (
        e.key === STORAGE_KEYS.auth.accessToken ||
        e.key === STORAGE_KEYS.auth.refreshToken
      ) {
        callback();
      }
    };
    
    const handleCustomEvent = () => {
      callback();
    };
    
    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('tokensUpdated', handleCustomEvent);
    window.addEventListener('tokensCleared', handleCustomEvent);
    
    // Return unsubscribe function
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('tokensUpdated', handleCustomEvent);
      window.removeEventListener('tokensCleared', handleCustomEvent);
    };
  }
}

/**
 * Export singleton instance
 * 
 * Usage:
 * ```typescript
 * import { authService } from '@/services/authService';
 * 
 * const token = authService.getAccessToken();
 * ```
 */
export const authService = AuthService.getInstance();

export default authService;
