/**
 * Pro Trader-EA — Design Tokens
 * Única fonte de verdade para todos os valores visuais.
 * Nenhum componente deve usar valores literais de cor, espaçamento ou sombra.
 * Importe daqui ou use as classes Tailwind geradas a partir deste arquivo.
 */

export const tokens = {
  color: {
    // ── Identidade da marca — KuCoin Institutional ──────────────────
    brand: {
      primary:   '#23C882', // KuCoin green — CTAs, links ativos, highlight
      alt:       '#1BAF72', // Verde escuro — hover, pressed states
      secondary: '#00B896', // Teal complementar — uso moderado
    },

    // ── Superfícies (backgrounds) ────────────────────────────────────
    surface: {
      base:    '#0B0E11', // Fundo da página — preto institucional
      raised:  '#161A1E', // Cards, painéis — levemente elevado
      overlay: '#1C2127', // Modais, dropdowns, tooltips
      hover:   '#222830', // Hover interativo
      active:  '#2A303A', // Selecionado, ativo
    },

    // ── Semânticos (dados financeiros) ───────────────────────────────
    semantic: {
      profit:      '#23C882', // Lucro, variação positiva — KuCoin green
      profitDeep:  '#1BAF72', // Lucro confirmado, settled
      loss:        '#EF4444', // Perda, variação negativa — Red 500
      lossDeep:    '#DC2626', // Crítico, erro grave — Red 600
      warning:     '#F59E0B', // Alerta, pendente — Amber 500
      info:        '#3B82F6', // Informativo — Blue 500
      neutral:     '#848E9C', // Neutro, sem variação
    },

    // ── Texto ────────────────────────────────────────────────────────
    text: {
      primary:   '#E6E8EC', // Branco-gelo — títulos, valores principais
      body:      '#C5C9D2', // Cinza claro — corpo de texto
      secondary: '#848E9C', // Cinza médio — labels, legendas
      muted:     '#545B68', // Cinza escuro — disabled, placeholder
      inverse:   '#0B0E11', // Texto sobre fundo claro (raro)
    },

    // ── Bordas ───────────────────────────────────────────────────────
    border: {
      subtle:  '#252932', // Separadores internos de cards
      default: '#2E333F', // Bordas de inputs e cards
      strong:  '#3A404D', // Bordas enfatizadas, focus rings
    },
  },

  // ── Espaçamento (escala 4pt) ────────────────────────────────────────
  // Não usar valores fora desta escala. Toda margem/padding/gap
  // deve ser múltiplo de 4px.
  spacing: {
    1:  '4px',
    2:  '8px',
    3:  '12px',
    4:  '16px',
    5:  '20px',
    6:  '24px',
    8:  '32px',
    10: '40px',
    12: '48px',
    16: '64px',
    20: '80px',
    24: '96px',
  },

  // ── Border radius ────────────────────────────────────────────────────
  radius: {
    sm:   '6px',
    md:   '10px',  // padrão global
    lg:   '14px',
    xl:   '20px',
    full: '9999px',
  },

  // ── Sombras ──────────────────────────────────────────────────────────
  shadow: {
    card:   '0 1px 3px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)',
    raised: '0 4px 24px rgba(0,0,0,0.6)',
    glow:   '0 0 20px rgba(35,200,130,0.15)',
    profit: '0 0 12px rgba(35,200,130,0.2)',
    loss:   '0 0 12px rgba(239,68,68,0.2)',
  },

  // ── Opacidades de badge ───────────────────────────────────────────────
  // Padrão para fundos de badge semântico: cor + esta opacidade
  badgeOpacity: {
    bg:     0.12,
    border: 0.25,
  },
} as const;

export type Tokens      = typeof tokens;
export type ColorToken  = typeof tokens.color;
export type BrandColor  = typeof tokens.color.brand;
export type SurfaceColor = typeof tokens.color.surface;
export type SemanticColor = typeof tokens.color.semantic;
export type TextColor   = typeof tokens.color.text;
export type BorderColor = typeof tokens.color.border;
