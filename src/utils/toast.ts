/**
 * notify — wrapper centralizado para toasts (sonner)
 *
 * SEMPRE use notify ao invés de import { toast } from 'sonner' diretamente.
 * Garante estilos consistentes com o design system em toda a aplicação.
 *
 * Uso:
 *   notify.success('Robô ativado', { description: 'BTC/USDT iniciou monitoramento' })
 *   notify.error('Falha ao conectar', { description: err.message, action: { label: 'Retry', onClick: fn } })
 *   notify.loading('Sincronizando...')
 *   notify.dismiss(toastId)
 *
 *   await notify.promise(fetchData(), {
 *     loading: 'Buscando dados...',
 *     success: 'Dados carregados!',
 *     error:   'Erro ao buscar dados',
 *   })
 */
import { toast } from 'sonner';

// ── Estilos base (design system tokens como inline styles — sonner não lê CSS vars) ──
const BASE = {
  background: '#0A1120', // surface.raised
  color:       '#F1F5F9', // content.primary
  borderRadius: '10px',  // --radius
  fontSize:    '14px',
} as const;

const BORDER = {
  success: 'rgba(16,185,129,0.30)',   // semantic.profit/30
  error:   'rgba(239,68,68,0.30)',    // semantic.loss/30
  warning: 'rgba(245,158,11,0.30)',   // semantic.warning/30
  loading: 'rgba(0,197,227,0.20)',    // brand.primary/20
  info:    'rgba(59,130,246,0.30)',   // semantic.info/30
} as const;

type ToastAction = {
  label: string;
  onClick: () => void;
};

interface NotifyOptions {
  description?: string;
  action?: ToastAction;
  /** Toast duration in ms. Default: 4000 */
  duration?: number;
}

// ─────────────────────────────────────────────────────────────────────────────

export const notify = {
  /**
   * Operação concluída com sucesso.
   * Ex: robô ativado, trade executado, configuração salva.
   */
  success(message: string, options?: NotifyOptions) {
    return toast.success(message, {
      description:  options?.description,
      action:       options?.action,
      duration:     options?.duration ?? 4000,
      style:        { ...BASE, border: `1px solid ${BORDER.success}` },
    });
  },

  /**
   * Erro em operação — sempre fornecer mensagem clara + ação de retry se possível.
   * Ex: falha de API, credencial inválida, timeout.
   */
  error(message: string, options?: NotifyOptions) {
    return toast.error(message, {
      description:  options?.description,
      action:       options?.action,
      duration:     options?.duration ?? 6000,
      style:        { ...BASE, border: `1px solid ${BORDER.error}` },
    });
  },

  /**
   * Alerta — situação que requer atenção mas não é erro crítico.
   * Ex: margem baixa, saldo insuficiente, mercado volátil.
   */
  warning(message: string, options?: NotifyOptions) {
    return toast.warning(message, {
      description: options?.description,
      action:      options?.action,
      duration:    options?.duration ?? 5000,
      style:       { ...BASE, border: `1px solid ${BORDER.warning}` },
    });
  },

  /**
   * Informação neutra.
   * Ex: nova versão disponível, lembrete de configuração.
   */
  info(message: string, options?: NotifyOptions) {
    return toast.info(message, {
      description: options?.description,
      action:      options?.action,
      duration:    options?.duration ?? 4000,
      style:       { ...BASE, border: `1px solid ${BORDER.info}` },
    });
  },

  /**
   * Estado de loading — retorna o ID para dismiss posterior.
   * Sempre chame notify.dismiss(id) ao resolver.
   */
  loading(message: string, options?: Pick<NotifyOptions, 'description' | 'duration'>) {
    return toast.loading(message, {
      description: options?.description,
      duration:    options?.duration ?? Infinity,
      style:       { ...BASE, border: `1px solid ${BORDER.loading}`, color: '#94A3B8' },
    });
  },

  /**
   * Wrapper para Promises — exibe loading → success ou error automaticamente.
   * Preferir este ao padrão manual de loading + dismiss.
   */
  promise<T>(
    promise: Promise<T>,
    messages: {
      loading: string;
      success: string | ((data: T) => string);
      error:   string | ((err: unknown) => string);
      description?: string;
    },
  ) {
    return toast.promise(promise, {
      loading:     messages.loading,
      success:     messages.success,
      error:       messages.error,
      description: messages.description,
    });
  },

  /** Remove um toast pelo ID retornado por notify.loading() */
  dismiss(id?: string | number) {
    toast.dismiss(id);
  },

  /** Remove todos os toasts ativos */
  dismissAll() {
    toast.dismiss();
  },
};
