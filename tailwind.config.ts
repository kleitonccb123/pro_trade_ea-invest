import type { Config } from "tailwindcss";
import { tokens } from "./src/design-system/tokens";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    // ── Breakpoints — inclui 3xl para setups de trading (1920px) ──────
    screens: {
      sm:   "640px",
      md:   "768px",
      lg:   "1024px",
      xl:   "1280px",
      "2xl": "1536px",
      "3xl": "1920px",
    },
    container: {
      center: true,
      padding: "1.5rem",
      screens: {
        "2xl": "1600px",
      },
    },
    extend: {
      // ── Tipografia ───────────────────────────────────────────────────
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
        mono:    ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "1rem" }],
        xs:    ["0.75rem",  { lineHeight: "1rem" }],
        sm:    ["0.875rem", { lineHeight: "1.25rem" }],
        base:  ["1rem",     { lineHeight: "1.5rem" }],
        lg:    ["1.125rem", { lineHeight: "1.75rem" }],
        xl:    ["1.25rem",  { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem",   { lineHeight: "2rem",    letterSpacing: "-0.02em" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.025em" }],
        "4xl": ["2.25rem",  { lineHeight: "2.5rem",  letterSpacing: "-0.03em" }],
        "5xl": ["3rem",     { lineHeight: "1.15",    letterSpacing: "-0.04em" }],
        "6xl": ["3.75rem",  { lineHeight: "1.1",     letterSpacing: "-0.04em" }],
      },

      // ── Cores ────────────────────────────────────────────────────────
      colors: {
        // ── Tokens semânticos do Design System (fonte de verdade) ──
        brand: {
          primary:   tokens.color.brand.primary,
          alt:       tokens.color.brand.alt,
          secondary: tokens.color.brand.secondary,
        },
        surface: {
          base:    tokens.color.surface.base,
          raised:  tokens.color.surface.raised,
          overlay: tokens.color.surface.overlay,
          hover:   tokens.color.surface.hover,
          active:  tokens.color.surface.active,
        },
        semantic: {
          profit:     tokens.color.semantic.profit,
          profitDeep: tokens.color.semantic.profitDeep,
          loss:       tokens.color.semantic.loss,
          lossDeep:   tokens.color.semantic.lossDeep,
          warning:    tokens.color.semantic.warning,
          info:       tokens.color.semantic.info,
          neutral:    tokens.color.semantic.neutral,
        },
        content: {
          primary:   tokens.color.text.primary,
          body:      tokens.color.text.body,
          secondary: tokens.color.text.secondary,
          muted:     tokens.color.text.muted,
          inverse:   tokens.color.text.inverse,
        },
        edge: {
          subtle:  tokens.color.border.subtle,
          default: tokens.color.border.default,
          strong:  tokens.color.border.strong,
        },

        // ── Compatibilidade shadcn/ui (manter intacto) ──────────────
        border:     "hsl(var(--border))",
        input:      "hsl(var(--input))",
        ring:       "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT:    "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT:    "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT:    "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        success: {
          DEFAULT:    "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT:    "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        muted: {
          DEFAULT:    "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT:    "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT:    "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT:    "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        chart: {
          bullish: "hsl(var(--chart-bullish))",
          bearish: "hsl(var(--chart-bearish))",
          neutral: "hsl(var(--chart-neutral))",
          line:    "hsl(var(--chart-line))",
        },
        sidebar: {
          DEFAULT:              "hsl(var(--sidebar-background))",
          foreground:           "hsl(var(--sidebar-foreground))",
          primary:              "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent:               "hsl(var(--sidebar-accent))",
          "accent-foreground":  "hsl(var(--sidebar-accent-foreground))",
          border:               "hsl(var(--sidebar-border))",
          ring:                 "hsl(var(--sidebar-ring))",
        },
      },

      // ── Border radius ────────────────────────────────────────────────
      borderRadius: {
        lg:   "var(--radius)",               // 10px
        md:   "calc(var(--radius) - 2px)",   // 8px
        sm:   "calc(var(--radius) - 4px)",   // 6px
        xl:   "calc(var(--radius) + 4px)",   // 14px
        "2xl":"calc(var(--radius) + 10px)",  // 20px
      },

      // ── Sombras ──────────────────────────────────────────────────────
      boxShadow: {
        card:   tokens.shadow.card,
        raised: tokens.shadow.raised,
        glow:   tokens.shadow.glow,
        profit: tokens.shadow.profit,
        loss:   tokens.shadow.loss,
      },

      // ── Keyframes — apenas funcionais ────────────────────────────────
      keyframes: {
        // shadcn/ui
        "accordion-down": {
          from: { height: "0" },
          to:   { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to:   { height: "0" },
        },
        // Entrada padrão — cards, listas (substituiu fade-up)
        "fade-up-in": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        // Fade simples — modais, tooltips
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        // Entrada lateral — drawer, painel
        "slide-in": {
          from: { opacity: "0", transform: "translateX(-8px)" },
          to:   { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translateX(8px)" },
          to:   { opacity: "1", transform: "translateX(0)" },
        },
        // Scale — modal principal
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.97)" },
          to:   { opacity: "1", transform: "scale(1)" },
        },
        // Ping — status de robô ativo (funcional)
        "ping": {
          "75%, 100%": { transform: "scale(2)", opacity: "0" },
        },
        // Shimmer — skeleton loading
        "shimmer": {
          "0%":   { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        // Pulse sutil — substitui animate-pulse genérico no skeleton
        "subtle-pulse": {
          "0%, 100%": { opacity: "0.6" },
          "50%":      { opacity: "0.9" },
        },
        // MANTIDOS para backward compat (não usar em componentes novos)
        "fade-up": {
          from: { opacity: "0", transform: "translateY(20px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        // RetroGrid
        "grid": {
          "0%":   { transform: "translateY(-50%)" },
          "100%": { transform: "translateY(0)" },
        },
        "grid-fade": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.6" },
        },
      },

      // ── Animations ───────────────────────────────────────────────────
      animation: {
        "accordion-down":  "accordion-down 0.2s ease-out",
        "accordion-up":    "accordion-up 0.2s ease-out",
        "fade-up-in":      "fade-up-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "fade-in":         "fade-in 0.2s ease-out forwards",
        "slide-in":        "slide-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "slide-in-right":  "slide-in-right 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "scale-in":        "scale-in 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "ping":            "ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite",
        "shimmer":         "shimmer 2s linear infinite",
        "subtle-pulse":    "subtle-pulse 2s ease-in-out infinite",
        // Backward compat
        "fade-up":         "fade-up 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        // RetroGrid
        "grid":            "grid 15s linear infinite",
        "grid-fade":       "grid-fade 8s ease-in-out infinite",
      },

      // ── Background images ────────────────────────────────────────────
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        // Gradiente de botão primário — KuCoin green
        "gradient-primary":
          "linear-gradient(135deg, #23C882 0%, #1BAF72 100%)",
        // Gradiente sutil para hero/page-header — não usar em cards
        "gradient-page-hero":
          "radial-gradient(circle at 15% 50%, rgba(35,200,130,0.06) 0%, transparent 45%), " +
          "radial-gradient(circle at 85% 30%, rgba(27,175,114,0.04) 0%, transparent 45%)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
