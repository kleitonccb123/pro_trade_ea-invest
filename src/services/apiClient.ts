/**
 * API Client with Automatic Token Refresh
 *
 * Intercepts all API requests and handles token refresh automatically
 * when a 401 Unauthorized response is received.
 *
 * Features:
 * - Automatic retry after token refresh
 * - Prevents multiple simultaneous refresh attempts
 * - Graceful fallback to login on refresh failure
 * - Works with all HTTP methods
 */

import { API_BASE_URL } from '@/config/constants';
import { authService } from '@/services/authService';

// Flag to prevent multiple simultaneous token refresh attempts
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

/**
 * Make API request with automatic token refresh on 401
 *
 * @param url - Endpoint URL (relative or absolute)
 * @param options - Fetch options
 * @returns - Fetch response
 */
export async function apiCall(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  // Normalize URL
  const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;

  // Add auth header if token exists
  const token = authService.getAccessToken();
  const headers = {
    ...options.headers,
  } as Record<string, string>;

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Make initial request
  let response = await fetch(fullUrl, {
    ...options,
    headers,
  });

  // If 401, try to refresh token and retry
  if (response.status === 401) {
    console.warn('[⚠️] Token expired (401). Attempting refresh...');

    // Use single refresh promise to prevent multiple refresh attempts
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = authService.refreshAccessToken();
    }

    // Wait for refresh to complete
    const newToken = await refreshPromise;

    // Reset flags
    isRefreshing = false;
    refreshPromise = null;

    if (newToken) {
      console.log('[✓] Token refreshed successfully. Retrying request...');

      // Retry with new token
      const newHeaders = {
        ...options.headers,
        'Authorization': `Bearer ${newToken}`,
      } as Record<string, string>;

      response = await fetch(fullUrl, {
        ...options,
        headers: newHeaders,
      });
    } else {
      // Refresh failed - user needs to login again
      console.error('[✗] Token refresh failed. User must login again.');
      authService.clearTokens();

      // Dispatch event so other parts of the app know to redirect to login
      window.dispatchEvent(new CustomEvent('authExpired', {
        detail: { reason: 'token_refresh_failed' }
      }));
    }
  }

  return response;
}

/**
 * Convenience function for GET requests
 */
export async function apiGet<T = any>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await apiCall(url, {
    ...options,
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`GET ${url} failed with status ${response.status}`);
  }

  return response.json();
}

/**
 * Convenience function for POST requests
 */
export async function apiPost<T = any>(
  url: string,
  data?: Record<string, any>,
  options: RequestInit = {}
): Promise<T> {
  const response = await apiCall(url, {
    ...options,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: data ? JSON.stringify(data) : undefined,
  });

  if (!response.ok) {
    throw new Error(`POST ${url} failed with status ${response.status}`);
  }

  return response.json();
}

/**
 * Convenience function for PUT requests
 */
export async function apiPut<T = any>(
  url: string,
  data?: Record<string, any>,
  options: RequestInit = {}
): Promise<T> {
  const response = await apiCall(url, {
    ...options,
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: data ? JSON.stringify(data) : undefined,
  });

  if (!response.ok) {
    throw new Error(`PUT ${url} failed with status ${response.status}`);
  }

  return response.json();
}

/**
 * Convenience function for PATCH requests
 */
export async function apiPatch<T = any>(
  url: string,
  data?: Record<string, any>,
  options: RequestInit = {}
): Promise<T> {
  const response = await apiCall(url, {
    ...options,
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: data ? JSON.stringify(data) : undefined,
  });

  if (!response.ok) {
    throw new Error(`PATCH ${url} failed with status ${response.status}`);
  }

  return response.json();
}

/**
 * Convenience function for DELETE requests
 */
export async function apiDelete<T = any>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await apiCall(url, {
    ...options,
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`DELETE ${url} failed with status ${response.status}`);
  }

  return response.json();
}
