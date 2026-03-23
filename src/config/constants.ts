/**
 * Application Configuration Constants
 * 
 * Centralized configuration for API URLs, timeouts, and other constants.
 * Ensures all parts of the application use the same configuration.
 * 
 * Environment Variables Required:
 * - VITE_API_BASE_URL: Base URL for backend API (default: http://localhost:8000)
 * - VITE_WS_BASE_URL: Base URL for WebSocket (default: derived from API_BASE_URL)
 * 
 * @example
 * import { API_BASE_URL, WS_BASE_URL, API_TIMEOUT } from '@/config/constants';
 */

/**
 * Base URL for API endpoints
 * 
 * Loaded from VITE_API_BASE_URL environment variable.
 * Fallback: http://localhost:8000
 * 
 * Examples:
 * - Production: https://api.pro-trader-ea.com
 * - Development: http://localhost:8000
 * - Docker: http://crypto-api:8000
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || 
  (() => {
    // Fallback logic for development
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
      
      if (isLocalhost) {
        return 'http://localhost:8000';
      }
      
      // If not localhost, assume API is on same host, different port
      return `${window.location.protocol}//${hostname}:8000`;
    }
    
    return 'http://localhost:8000';
  })();

/**
 * Convert HTTP/HTTPS URL to WebSocket URL
 * 
 * @param httpUrl HTTP(S) URL to convert
 * @returns WebSocket URL (ws:// or wss://)
 */
function httpToWsUrl(httpUrl: string): string {
  try {
    const url = new URL(httpUrl);
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${url.host}${url.pathname}`;
  } catch (error) {
    console.error('[CONFIG] Failed to convert HTTP URL to WebSocket URL:', httpUrl, error);
    // Fallback: simple string replacement
    return httpUrl.replace(/^https?:/, (match) => match === 'https:' ? 'wss:' : 'ws:');
  }
}

/**
 * Base URL for WebSocket connections
 * 
 * Automatically converted from API_BASE_URL or loaded from VITE_WS_BASE_URL.
 * 
 * Examples:
 * - wss://api.pro-trader-ea.com
 * - ws://localhost:8000
 */
export const WS_BASE_URL: string = (() => {
  const envWsUrl = import.meta.env.VITE_WS_BASE_URL;
  
  if (envWsUrl) {
    // Validate and log
    console.log('[CONFIG] Using explicit WebSocket URL from VITE_WS_BASE_URL:', envWsUrl);
    return envWsUrl;
  }
  
  // Convert API URL to WS URL
  const wsUrl = httpToWsUrl(API_BASE_URL);
  console.log('[CONFIG] Derived WebSocket URL from API_BASE_URL:', {
    from: API_BASE_URL,
    to: wsUrl
  });
  
  return wsUrl;
})();

/**
 * API request timeout in milliseconds
 * 
 * Used by Axios and fetch() calls for request timeout.
 * Default: 30 seconds
 */
export const API_TIMEOUT: number = 30_000; // 30 seconds

/**
 * WebSocket connection timeout in milliseconds
 * 
 * Time to wait for WebSocket connection to establish.
 * Default: 10 seconds
 */
export const WS_TIMEOUT: number = 10_000; // 10 seconds

/**
 * WebSocket auto-reconnect configuration
 */
export const WS_RECONNECT_CONFIG = {
  enabled: true,
  maxAttempts: 10,
  initialDelayMs: 3_000,
  maxDelayMs: 30_000,
} as const;

/**
 * Authentication configuration
 */
export const AUTH_CONFIG = {
  /** JWT token storage key in localStorage */
  accessTokenKey: 'access_token',
  
  /** Refresh token storage key in localStorage */
  refreshTokenKey: 'refresh_token',
  
  /** Token refresh endpoint */
  refreshTokenEndpoint: '/api/auth/refresh',
  
  /** Token validation endpoint */
  validateTokenEndpoint: '/api/auth/me',
  
  /** Login timeout in milliseconds */
  loginTimeoutMs: 15_000, // 15 seconds (increased from 10s)
} as const;

/**
 * Storage keys used throughout the application
 */
export const STORAGE_KEYS = {
  auth: {
    accessToken: AUTH_CONFIG.accessTokenKey,
    refreshToken: AUTH_CONFIG.refreshTokenKey,
    user: 'auth_user',
  },
  ui: {
    theme: 'ui_theme',
    language: 'ui_language',
  },
  app: {
    emailHistory: 'app_email_history',
    rememberEmail: 'app_remember_email',
  },
} as const;

/**
 * Email regex for validation (RFC 5322 simplified)
 */
export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Log debug mode
 */
export const DEBUG_MODE = import.meta.env.DEV || import.meta.env.VITE_DEBUG === 'true';

/**
 * Application version
 */
export const APP_VERSION = import.meta.env.VITE_APP_VERSION || '2.0.0';

/**
 * Initialize configuration logging
 */
if (DEBUG_MODE) {
  console.info('[CONFIG] Configuration initialized:', {
    API_BASE_URL,
    WS_BASE_URL,
    API_TIMEOUT,
    WS_TIMEOUT,
    DEBUG_MODE,
    APP_VERSION,
  });
}

export default {
  API_BASE_URL,
  WS_BASE_URL,
  API_TIMEOUT,
  WS_TIMEOUT,
  AUTH_CONFIG,
  STORAGE_KEYS,
  EMAIL_REGEX,
  DEBUG_MODE,
  APP_VERSION,
};
