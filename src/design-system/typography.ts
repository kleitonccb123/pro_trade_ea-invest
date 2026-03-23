/**
 * Pro Trader-EA — Escala Tipográfica
 *
 * Papéis definidos:
 *  • Dados financeiros (preços, percentuais, volumes) → font-mono
 *  • Títulos de página/seção                         → font-display (Space Grotesk)
 *  • Body e labels                                   → font-sans (Inter)
 *  • Timestamps e metadados                          → font-mono
 */

export const typography = {
  // ── Famílias ────────────────────────────────────────────────────────
  family: {
    sans:    "'Inter', system-ui, sans-serif",
    display: "'Space Grotesk', 'Inter', system-ui, sans-serif",
    mono:    "'JetBrains Mono', 'Fira Code', monospace",
  },

  // ── Escala de tamanhos ───────────────────────────────────────────────
  // [tamanho, line-height]
  scale: {
    '2xs': ['0.625rem', '1rem'],    // 10px — micro labels
    xs:    ['0.75rem',  '1rem'],    // 12px — caption, timestamp
    sm:    ['0.875rem', '1.25rem'], // 14px — body small, labels
    base:  ['1rem',     '1.5rem'],  // 16px — body principal
    lg:    ['1.125rem', '1.75rem'], // 18px — body large, subtítulos
    xl:    ['1.25rem',  '1.75rem'], // 20px — H4, card title
    '2xl': ['1.5rem',   '2rem'],    // 24px — H3, section header
    '3xl': ['1.875rem', '2.25rem'], // 30px — H2, page title
    '4xl': ['2.25rem',  '2.5rem'],  // 36px — H1, hero
    '5xl': ['3rem',     '1.15'],    // 48px — metric principal
    '6xl': ['3.75rem',  '1.1'],     // 60px — metric destaque máximo
  },

  // ── Pesos ────────────────────────────────────────────────────────────
  weight: {
    light:     300,
    regular:   400,
    medium:    500,
    semibold:  600,
    bold:      700,
    extrabold: 800,
  },

  // ── Line heights ─────────────────────────────────────────────────────
  leading: {
    none:    1,
    tight:   1.2,   // Títulos grandes (≥ 30px)
    snug:    1.35,  // Subtítulos
    normal:  1.5,   // Body text
    relaxed: 1.65,  // Texto longo
  },

  // ── Letter spacing ───────────────────────────────────────────────────
  tracking: {
    tighter: '-0.04em',  // Títulos ≥ 30px
    tight:   '-0.025em', // Títulos médios
    normal:   '0',
    wide:     '0.05em',  // All-caps labels
    wider:    '0.1em',   // Micro-labels uppercase
  },

  // ── Papéis (use como referência para criar componentes) ──────────────
  roles: {
    /**
     * PREÇO / SALDO / VOLUME
     * font-mono font-semibold tabular-nums tracking-tight
     * Cor: baseada em profit/loss/neutral
     */
    financialValue: {
      fontFamily: 'mono',
      fontWeight: 600,
      letterSpacing: '-0.025em',
      fontVariantNumeric: 'tabular-nums slashed-zero',
    },

    /**
     * TÍTULO DE PÁGINA (H1)
     * font-display font-bold text-3xl tracking-tight
     * Cor: text.primary
     */
    pageTitle: {
      fontFamily: 'display',
      fontWeight: 700,
      fontSize: '1.875rem',
      lineHeight: '2.25rem',
      letterSpacing: '-0.03em',
    },

    /**
     * CARD HEADER / SUBTÍTULO (H3)
     * font-display font-semibold text-xl tracking-tight
     */
    cardTitle: {
      fontFamily: 'display',
      fontWeight: 600,
      fontSize: '1.25rem',
      lineHeight: '1.75rem',
      letterSpacing: '-0.02em',
    },

    /**
     * LABEL DE SEÇÃO
     * font-sans font-medium text-xs uppercase tracking-wider
     * Cor: text.secondary
     */
    sectionLabel: {
      fontFamily: 'sans',
      fontWeight: 500,
      fontSize: '0.75rem',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
    },

    /**
     * BODY
     * font-sans font-regular text-sm leading-normal
     * Cor: text.body
     */
    body: {
      fontFamily: 'sans',
      fontWeight: 400,
      fontSize: '0.875rem',
      lineHeight: '1.5rem',
    },

    /**
     * TIMESTAMP / METADATA
     * font-mono font-regular text-xs
     * Cor: text.muted
     */
    timestamp: {
      fontFamily: 'mono',
      fontWeight: 400,
      fontSize: '0.75rem',
    },
  },
} as const;
