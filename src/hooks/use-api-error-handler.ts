/**
 * Hook para tratamento global de erros da API
 * Integra com sistema de toasts do Shadcn/UI
 */

import { useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiErrorEvents, ApiErrorEvent, ApiErrorType } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

interface UseApiErrorHandlerOptions {
  // Redirect to upgrade page on license error
  redirectOnLicense?: boolean;
  // Redirect to 2FA setup on 2FA required
  redirectOn2FA?: boolean;
  // Custom handlers for specific error types
  customHandlers?: Partial<Record<ApiErrorType, (error: ApiErrorEvent) => void>>;
}

export function useApiErrorHandler(options: UseApiErrorHandlerOptions = {}) {
  const { toast } = useToast();
  const navigate = useNavigate();
  
  const {
    redirectOnLicense = false,
    redirectOn2FA = false,
    customHandlers = {},
  } = options;

  const handleError = useCallback((error: ApiErrorEvent) => {
    // Check for custom handler first
    if (customHandlers[error.type]) {
      customHandlers[error.type]!(error);
      return;
    }

    switch (error.type) {
      case 'license_required':
        toast({
          variant: 'destructive',
          title: '⚠️ Plano Insuficiente',
          description: error.message,
          duration: 8000,
        });
        if (redirectOnLicense) {
          setTimeout(() => navigate('/pricing'), 2000);
        }
        break;

      case '2fa_required':
        toast({
          variant: 'destructive',
          title: '🔐 Verificação Necessária',
          description: error.message,
          duration: 6000,
        });
        if (redirectOn2FA && error.details?.redirect) {
          setTimeout(() => navigate(error.details!.redirect), 1500);
        }
        break;

      case 'circuit_breaker':
        const retrySeconds = error.details?.retryAfter || 30;
        toast({
          variant: 'destructive',
          title: '⚡ Sistema Sobrecarregado',
          description: `${error.message} Tente novamente em ${retrySeconds}s.`,
          duration: retrySeconds * 1000,
        });
        break;

      case 'rate_limited':
        const waitSeconds = error.details?.retryAfter || 60;
        toast({
          variant: 'destructive',
          title: '🚫 Limite de Requisições',
          description: `${error.message} Aguarde ${waitSeconds}s.`,
          duration: 5000,
        });
        break;

      case 'unauthorized':
        toast({
          variant: 'destructive',
          title: '🔒 Sessão Expirada',
          description: error.message,
          duration: 4000,
        });
        break;

      case 'server_error':
        toast({
          variant: 'destructive',
          title: '❌ Erro do Servidor',
          description: error.message,
          duration: 5000,
        });
        break;

      default:
        toast({
          variant: 'destructive',
          title: 'Erro',
          description: error.message,
          duration: 5000,
        });
    }
  }, [toast, navigate, redirectOnLicense, redirectOn2FA, customHandlers]);

  useEffect(() => {
    const unsubscribe = apiErrorEvents.subscribe(handleError);
    return () => {
      unsubscribe();
    };
  }, [handleError]);
}

// Simplified hook just for toasts without navigation
export function useApiErrorToast() {
  const { toast } = useToast();

  useEffect(() => {
    const unsubscribe = apiErrorEvents.subscribe((error) => {
      const variants: Record<ApiErrorType, { icon: string; title: string }> = {
        license_required: { icon: '⚠️', title: 'Plano Insuficiente' },
        '2fa_required': { icon: '🔐', title: 'Verificação Necessária' },
        circuit_breaker: { icon: '⚡', title: 'Sistema Sobrecarregado' },
        rate_limited: { icon: '🚫', title: 'Limite de Requisições' },
        unauthorized: { icon: '🔒', title: 'Não Autorizado' },
        server_error: { icon: '❌', title: 'Erro do Servidor' },
      };

      const variant = variants[error.type] || { icon: '⚠️', title: 'Erro' };

      toast({
        variant: 'destructive',
        title: `${variant.icon} ${variant.title}`,
        description: error.message,
        duration: error.type === 'circuit_breaker' ? 10000 : 5000,
      });
    });

    return () => {
      unsubscribe();
    };
  }, [toast]);
}
