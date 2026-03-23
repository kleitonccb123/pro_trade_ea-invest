/**
 * Pro Trader-EA — Sistema de Animações
 *
 * Regra fundamental: animate data changes, not decorations.
 *
 * PERMITIDAS  — funcionais, acionadas por mudança de estado:
 *   fade-up-in, fade-in, slide-in, ping (status ativo)
 *
 * PROIBIDAS   — decorativas, perpétuas:
 *   float, glow-pulse, pulse-glow, border-glow, spin-slow em ícones estáticos
 *
 * Durações:
 *   hover / click       → 100–200ms
 *   entrada de elemento → 200–300ms
 *   transição de página → 250–350ms
 *   tick de dado        → 300–500ms
 *   modal / drawer      → 200–250ms ease-out
 */

export const animations = {
  // Duração padrão por categoria
  duration: {
    micro:    '150ms',
    fast:     '200ms',
    normal:   '250ms',
    moderate: '350ms',
    slow:     '500ms',
  },

  // Easing padrão — SEMPRE ease-out para entradas (termina suave)
  easing: {
    default:  'cubic-bezier(0.16, 1, 0.3, 1)',
    decelerate: 'cubic-bezier(0, 0, 0.2, 1)',
    linear:   'linear',
  },

  // Stagger máximo por item em listas (ms)
  staggerItem: 40,

  // Keyframes canônicos do projeto
  keyframes: {
    // Entrada padrão de cards e elementos de página
    'fade-up-in': {
      from: { opacity: '0', transform: 'translateY(10px)' },
      to:   { opacity: '1', transform: 'translateY(0)' },
    },
    'fade-in': {
      from: { opacity: '0' },
      to:   { opacity: '1' },
    },
    // Entrada lateral (drawer, painel)
    'slide-in': {
      from: { opacity: '0', transform: 'translateX(-8px)' },
      to:   { opacity: '1', transform: 'translateX(0)' },
    },
    'slide-in-right': {
      from: { opacity: '0', transform: 'translateX(8px)' },
      to:   { opacity: '1', transform: 'translateX(0)' },
    },
    // Scale para modais
    'scale-in': {
      from: { opacity: '0', transform: 'scale(0.97)' },
      to:   { opacity: '1', transform: 'scale(1)' },
    },
    // Ping para status de robô ativo (funcional — não decorativo)
    'ping': {
      '75%, 100%': { transform: 'scale(2)', opacity: '0' },
    },
    // Shimmer para skeleton loading
    'shimmer': {
      '0%':   { backgroundPosition: '200% 0' },
      '100%': { backgroundPosition: '-200% 0' },
    },
    // Pulse sutil para skeleton (substituir animate-pulse padrão do Tailwind)
    'subtle-pulse': {
      '0%, 100%': { opacity: '0.6' },
      '50%':      { opacity: '0.9' },
    },
    // Accordion (shadcn/ui)
    'accordion-down': {
      from: { height: '0' },
      to:   { height: 'var(--radix-accordion-content-height)' },
    },
    'accordion-up': {
      from: { height: 'var(--radix-accordion-content-height)' },
      to:   { height: '0' },
    },
  },

  // Classes de animation para Tailwind
  animation: {
    'fade-up-in':      'fade-up-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
    'fade-in':         'fade-in 0.2s ease-out forwards',
    'slide-in':        'slide-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
    'slide-in-right':  'slide-in-right 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
    'scale-in':        'scale-in 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
    'ping':            'ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite',
    'shimmer':         'shimmer 2s linear infinite',
    'subtle-pulse':    'subtle-pulse 2s ease-in-out infinite',
    'accordion-down':  'accordion-down 0.2s ease-out',
    'accordion-up':    'accordion-up 0.2s ease-out',
  },
} as const;
