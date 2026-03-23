/**
 * useApi Hook - Centralização de Chamadas ao Backend
 * 
 * Features:
 * - Axios com JWT automático no header Authorization
 * - Interceptor 401: Token expirado → redirect /login
 * - Interceptor 503: Circuit Breaker OPEN → Toast de Cool Down
 * - Estados: loading, error, data
 * - Funções: get, post, put, delete
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import axios, { AxiosInstance, AxiosRequestConfig, AxiosError, AxiosResponse } from 'axios';
import { useNavigate } from 'react-router-dom';
import { useToast } from '@/hooks/use-toast';

// ============== TYPES ==============

export interface CircuitBreakerStatus {
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  failures: number;
  last_failure?: string;
  cooldown_remaining?: number;
}

export interface ApiError {
  message: string;
  status: number;
  code?: string;
  circuit_breaker?: CircuitBreakerStatus;
}

export interface ApiResponse<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
}

export interface UseApiReturn {
  // States
  loading: boolean;
  error: ApiError | null;
  circuitBreakerStatus: CircuitBreakerStatus | null;
  
  // Methods
  get: <T>(url: string, config?: AxiosRequestConfig) => Promise<T>;
  post: <T>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<T>;
  put: <T>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<T>;
  del: <T>(url: string, config?: AxiosRequestConfig) => Promise<T>;
  patch: <T>(url: string, data?: any, config?: AxiosRequestConfig) => Promise<T>;
  
  // Utilities
  clearError: () => void;
  setToken: (token: string) => void;
  clearToken: () => void;
  isAuthenticated: () => boolean;
}

// ============== CONSTANTS ==============

const API_BASE_URL = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// Circuit Breaker error messages
const CIRCUIT_BREAKER_MESSAGES = {
  OPEN: '⚠️ Sistema em Cool Down. O serviço de trading está temporariamente indisponível para proteger suas operações. Tente novamente em alguns minutos.',
  HALF_OPEN: '🔄 Sistema em recuperação. Algumas funcionalidades podem estar limitadas.',
};

// ============== HOOK ==============

export function useApi(): UseApiReturn {
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [circuitBreakerStatus, setCircuitBreakerStatus] = useState<CircuitBreakerStatus | null>(null);
  
  // Ref to track if component is mounted
  const isMounted = useRef(true);
  
  // Axios instance ref
  const axiosInstance = useRef<AxiosInstance | null>(null);

  // Initialize axios instance with interceptors
  useEffect(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // ============== REQUEST INTERCEPTOR ==============
    instance.interceptors.request.use(
      (config) => {
        // Add JWT token to all requests
        const token = localStorage.getItem(TOKEN_KEY);
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        
        // Add request timestamp for debugging
        (config as any).metadata = { startTime: new Date() };
        
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // ============== RESPONSE INTERCEPTOR ==============
    instance.interceptors.response.use(
      (response: AxiosResponse) => {
        // Check for Circuit Breaker status in headers
        const cbStatus = response.headers['x-circuit-breaker-status'];
        if (cbStatus) {
          try {
            const status = JSON.parse(cbStatus) as CircuitBreakerStatus;
            if (isMounted.current) {
              setCircuitBreakerStatus(status);
            }
            
            // Warn if HALF_OPEN
            if (status.state === 'HALF_OPEN') {
              toast({
                title: 'Sistema em Recuperação',
                description: CIRCUIT_BREAKER_MESSAGES.HALF_OPEN,
                variant: 'default',
              });
            }
          } catch (e) {
            // Ignore parsing errors
          }
        }
        
        return response;
      },
      async (error: AxiosError) => {
        const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
        
        // ============== HANDLE 401 - TOKEN EXPIRED ==============
        if (error.response?.status === 401) {
          // Check if we already tried to refresh
          if (!originalRequest._retry) {
            originalRequest._retry = true;
            
            const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
            if (refreshToken) {
              try {
                // Try to refresh the token
                const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
                  refresh_token: refreshToken,
                });
                
                const { access_token, refresh_token: newRefreshToken } = response.data;
                localStorage.setItem(TOKEN_KEY, access_token);
                if (newRefreshToken) {
                  localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
                }
                
                // Retry original request with new token
                if (originalRequest.headers) {
                  originalRequest.headers.Authorization = `Bearer ${access_token}`;
                }
                return instance(originalRequest);
              } catch (refreshError) {
                // Refresh failed — just propagate the error.
                // Do NOT clear tokens or navigate here: AuthContext.checkAuth()
                // already handles session expiry and ProtectedRoute handles redirect.
              }
            }
          }
          
          // Propagate the 401 error to the caller — do not force redirect.
          // Session management is handled by AuthContext + ProtectedRoute.
          return Promise.reject(error);
        }
        
        // ============== HANDLE 503 - CIRCUIT BREAKER OPEN ==============
        if (error.response?.status === 503) {
          const responseData = error.response.data as any;
          
          // Extract Circuit Breaker status from response
          const cbStatus: CircuitBreakerStatus = responseData?.circuit_breaker || {
            state: 'OPEN',
            failures: responseData?.failures || 0,
            cooldown_remaining: responseData?.retry_after || 60,
          };
          
          if (isMounted.current) {
            setCircuitBreakerStatus(cbStatus);
          }
          
          // Show Circuit Breaker toast
          toast({
            title: '🛡️ Sistema em Cool Down',
            description: CIRCUIT_BREAKER_MESSAGES.OPEN,
            variant: 'destructive',
            duration: 10000, // Show for 10 seconds
          });
          
          // Create custom error
          const cbError: ApiError = {
            message: CIRCUIT_BREAKER_MESSAGES.OPEN,
            status: 503,
            code: 'CIRCUIT_BREAKER_OPEN',
            circuit_breaker: cbStatus,
          };
          
          return Promise.reject(cbError);
        }
        
        // ============== HANDLE 429 - RATE LIMITED ==============
        if (error.response?.status === 429) {
          toast({
            title: '⏱️ Limite de Requisições',
            description: 'Muitas requisições em pouco tempo. Aguarde alguns segundos.',
            variant: 'default',
          });
        }
        
        // ============== HANDLE OTHER ERRORS ==============
        const rawDetail = (error.response?.data as any)?.detail;
        const detailMessage = typeof rawDetail === 'string'
          ? rawDetail
          : rawDetail?.message || (rawDetail ? JSON.stringify(rawDetail) : undefined);
        const apiError: ApiError = {
          message: detailMessage ||
                   (error.response?.data as any)?.message ||
                   error.message || 
                   'Erro desconhecido',
          status: error.response?.status || 0,
          code: (error.response?.data as any)?.code,
        };
        
        return Promise.reject(apiError);
      }
    );

    axiosInstance.current = instance;

    return () => {
      isMounted.current = false;
    };
  }, [navigate, toast]);

  // ============== REQUEST WRAPPER ==============
  const request = useCallback(async <T>(
    method: 'get' | 'post' | 'put' | 'delete' | 'patch',
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> => {
    if (!axiosInstance.current) {
      throw new Error('API not initialized');
    }

    setLoading(true);
    setError(null);

    try {
      let response: AxiosResponse<T>;
      
      switch (method) {
        case 'get':
          response = await axiosInstance.current.get<T>(url, config);
          break;
        case 'post':
          response = await axiosInstance.current.post<T>(url, data, config);
          break;
        case 'put':
          response = await axiosInstance.current.put<T>(url, data, config);
          break;
        case 'delete':
          response = await axiosInstance.current.delete<T>(url, config);
          break;
        case 'patch':
          response = await axiosInstance.current.patch<T>(url, data, config);
          break;
        default:
          throw new Error(`Unsupported method: ${method}`);
      }

      return response.data;
    } catch (err) {
      const apiError = err as ApiError;
      if (isMounted.current) {
        setError(apiError);
      }
      throw apiError;
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, []);

  // ============== PUBLIC METHODS ==============
  const get = useCallback(<T>(url: string, config?: AxiosRequestConfig) => 
    request<T>('get', url, undefined, config), [request]);

  const post = useCallback(<T>(url: string, data?: any, config?: AxiosRequestConfig) => 
    request<T>('post', url, data, config), [request]);

  const put = useCallback(<T>(url: string, data?: any, config?: AxiosRequestConfig) => 
    request<T>('put', url, data, config), [request]);

  const del = useCallback(<T>(url: string, config?: AxiosRequestConfig) => 
    request<T>('delete', url, undefined, config), [request]);

  const patch = useCallback(<T>(url: string, data?: any, config?: AxiosRequestConfig) => 
    request<T>('patch', url, data, config), [request]);

  // ============== UTILITIES ==============
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const setToken = useCallback((token: string) => {
    localStorage.setItem(TOKEN_KEY, token);
  }, []);

  const clearToken = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }, []);

  const isAuthenticated = useCallback(() => {
    return !!localStorage.getItem(TOKEN_KEY);
  }, []);

  return {
    loading,
    error,
    circuitBreakerStatus,
    get,
    post,
    put,
    del,
    patch,
    clearError,
    setToken,
    clearToken,
    isAuthenticated,
  };
}

// ============== STANDALONE API INSTANCE ==============
// For use outside of React components

export const createApiClient = () => {
  const instance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  instance.interceptors.request.use((config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  return instance;
};

export default useApi;
