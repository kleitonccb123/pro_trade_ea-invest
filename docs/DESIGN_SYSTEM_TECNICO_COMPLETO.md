# DOCUMENTAÇÃO TÉCNICA — MODERNIZAÇÃO FRONTEND FINTECH
## CryptoTradeHub — Sistema de Design Profissional v2.0
> Nível: Senior Product Designer + Frontend Architect  
> Linguagem: Português  
> Stack: React + TypeScript + Tailwind CSS + shadcn/ui  
> Data: Fevereiro 2026

---

# SUMÁRIO EXECUTIVO

Este documento cobre os 10 pilares para transformar o frontend do CryptoTradeHub de um produto com aparência genérica para um SaaS financeiro de nível institucional. Cada ponto é executável, com código real, estrutura de componentes e critérios de validação.

---

## PONTO 1 — SISTEMA DE DESIGN UNIFICADO (Design System Próprio)

### 1.1 Problema Atual
O projeto usa variáveis CSS no `index.css` e tokens no `tailwind.config.ts`, mas os componentes consomem esses tokens de forma inconsistente. Vários arquivos definem estilos inline, classes Tailwind arbitrárias e classes CSS puras misturadas sem critério. Um componente em `src/pages/Dashboard.tsx` pode usar `text-cyan-400` enquanto outro usa `text-primary` — semanticamente diferentes, visualmente semelhantes por coincidência.

### 1.2 Impacto Negativo
- Impossível escalar: mudar uma cor quebra partes inesperadas
- Times não sabem qual token usar
- Resultado visual é inconsistente entre páginas
- O produto parece "montado por partes" — porque é

### 1.3 Solução Proposta
Criar um **Design System interno** com uma única fonte de verdade. Todos os valores de cor, espaçamento, tipografia e sombra vêm de tokens semânticos. Nenhum componente usa valores literais de cor.

### 1.4 Mudanças Técnicas

**Criar `src/design-system/tokens.ts`:**

```typescript
export const tokens = {
  color: {
    brand: {
      primary:   '#00C5E3',  // Cyan institucional
      secondary: '#7B5EA7',  // Roxo profundo
      accent:    '#00E5B4',  // Verde menta (lucro)
    },
    surface: {
      base:      '#060B14',  // Fundo base
      raised:    '#0A1120',  // Cards
      overlay:   '#0F1929',  // Modais, popovers
      hover:     '#141F31',  // Hover state
    },
    semantic: {
      profit:    '#10B981',  // Verde — lucro, positivo
      loss:      '#EF4444',  // Vermelho — perda, erro
      warning:   '#F59E0B',  // Âmbar — alerta
      neutral:   '#6B7280',  // Cinza — neutro
      info:      '#3B82F6',  // Azul — info
    },
    text: {
      primary:   '#F1F5F9',  // Título principal
      secondary: '#94A3B8',  // Subtítulo, label
      tertiary:  '#475569',  // Placeholder, disabled
      inverse:   '#060B14',  // Texto sobre fundo claro
    },
    border: {
      subtle:    '#1E2D45',  // Borda suave
      default:   '#243348',  // Borda padrão
      strong:    '#334D6E',  // Borda enfatizada
    },
  },
  spacing: {
    // Escala 4pt — base de toda indústria fintech profissional
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
  radius: {
    sm:   '6px',
    md:   '10px',
    lg:   '14px',
    xl:   '20px',
    full: '9999px',
  },
  shadow: {
    card:   '0 1px 3px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.2)',
    raised: '0 4px 24px rgba(0,0,0,0.5)',
    glow:   '0 0 20px rgba(0,197,227,0.15)',
    profit: '0 0 12px rgba(16,185,129,0.2)',
    loss:   '0 0 12px rgba(239,68,68,0.2)',
  },
} as const;

export type ColorToken = typeof tokens.color;
```

**Integrar no `tailwind.config.ts` (substituir valores hardcoded):**

```typescript
import { tokens } from './src/design-system/tokens';

// No theme.extend.colors:
colors: {
  brand: tokens.color.brand,
  surface: tokens.color.surface,
  semantic: tokens.color.semantic,
  content: tokens.color.text,
  edge: tokens.color.border,
  // Manter compatibilidade shadcn:
  background: tokens.color.surface.base,
  foreground: tokens.color.text.primary,
  primary: { DEFAULT: tokens.color.brand.primary, foreground: tokens.color.text.inverse },
  // ...
}
```

### 1.5 Estrutura de Componentes

```
src/
  design-system/
    tokens.ts           ← Fonte única de verdade
    typography.ts       ← Escala tipográfica
    animations.ts       ← Keyframes e transições
    index.ts            ← Re-export central
  components/
    ui/                 ← shadcn/ui base (não modificar diretamente)
    primitives/         ← Atoms: Button, Badge, Tag, Divider
    patterns/           ← Molecules: MetricCard, PriceDisplay, TradePair
    layouts/            ← Organisms: DashboardGrid, SidebarLayout, PageHeader
    features/           ← Feature-specific: RobotCard, StrategyBuilder
```

### 1.6 Sistema de Design

| Token             | Valor         | Uso                          |
|-------------------|---------------|------------------------------|
| `surface.base`    | `#060B14`     | Background da página         |
| `surface.raised`  | `#0A1120`     | Cards, painéis               |
| `brand.primary`   | `#00C5E3`     | CTAs, links ativos           |
| `semantic.profit` | `#10B981`     | Variação positiva, lucro     |
| `semantic.loss`   | `#EF4444`     | Variação negativa, perda     |
| `text.secondary`  | `#94A3B8`     | Labels, subtítulos           |

### 1.7 Microinterações
- Transição de tema: nenhuma — sempre dark (fintech profissional não tem toggle de tema)
- Token de radius dinâmico: `--radius` global de `10px`, sem exagero arredondado

### 1.8 Erros Comuns a Corrigir
- ❌ `text-cyan-400` direto em componente → ✅ `text-brand-primary`
- ❌ `bg-gray-900` → ✅ `bg-surface-raised`
- ❌ `border-gray-700/30` → ✅ `border-edge-subtle`
- ❌ Inline `style={{ color: '#00ff00' }}` → ✅ nunca

### 1.9 Exemplo de Migração de Card
```tsx
// ❌ ANTES — genérico, sem semântica
<div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">

// ✅ DEPOIS — semântico, consistente
<div className="bg-surface-raised border border-edge-subtle rounded-lg p-6">
```

### 1.10 Checklist de Validação
- [ ] `tokens.ts` criado e importado pelo `tailwind.config.ts`
- [ ] Nenhum componente usa cores Tailwind literais (gray-X, cyan-X, etc.)
- [ ] `grep -r "bg-gray" src/` retorna zero resultados
- [ ] `grep -r "text-cyan" src/` retorna zero resultados
- [ ] Design System documentado no `src/design-system/index.ts`

---

## PONTO 2 — PALETA DE CORES PROFISSIONAL ESTILO FINTECH

### 2.1 Problema Atual
O CSS atual define `--primary: 190 95% 50%` (cyan intenso) e `--accent: 270 80% 60%` (roxo vibrante). Essa combinação gera um visual que lembra dashboards de jogos ou crypto exchanges genéricas. O **cyan + roxo neon** virou clichê no segmento. Falta profundidade, calma e autoridade institucional.

### 2.2 Impacto Negativo
Usuários com capital para investir associam cores saturadas e brilhantes a risco e amadorismo. Plataformas como Bloomberg, Coinbase Pro e Kraken usam paletas controladas exatamente por esse motivo. Saturação excessiva = produto não confiável.

### 2.3 Solução Proposta
Substituir a paleta "neon maximalista" por uma paleta **azul-profunda + ciano controlado + verde institucional**. Mantém o tema dark mas transmite seriedade.

### 2.4 Nova Paleta Completa com HEX

#### Paleta Base (Fundos e Superfícies)
```
#060B14  → surface.base      | Fundo principal — azul-noite profundo
#0A1120  → surface.raised    | Cards — ligeiramente elevado
#0F1929  → surface.overlay   | Modais, dropdowns
#141F31  → surface.hover     | Estado hover interativo
#1A2B42  → surface.active    | Estado ativo, selecionado
```

#### Paleta Brand (Identidade)
```
#00C5E3  → brand.primary     | Cyan institucional — links, CTAs, accent
#0EA5E9  → brand.alt         | Azul sky — alternativa harmônica
#7C3AED  → brand.secondary   | Roxo escuro — usado com moderação
```

#### Paleta Semântica (Dados Financeiros)
```
#10B981  → profit            | Verde Emerald — lucro, variação positiva
#059669  → profit.deep       | Verde mais escuro — confirmado, settled
#EF4444  → loss              | Vermelho — perda, variação negativa
#DC2626  → loss.deep         | Vermelho escuro — crítico
#F59E0B  → warning           | Âmbar — alertas, pending
#3B82F6  → info              | Azul médio — informativo
```

#### Paleta Tipográfica (Texto)
```
#F1F5F9  → text.primary      | Branco-gelo — títulos, valores principais
#CBD5E1  → text.body         | Cinza claro — corpo de texto
#94A3B8  → text.secondary    | Cinza médio — labels, legendas
#475569  → text.muted        | Cinza escuro — disabled, placeholder
#1E293B  → text.inverse      | Texto sobre fundo claro (raro)
```

#### Paleta de Bordas
```
#1E2D45  → border.subtle     | Separadores internos de cards
#243348  → border.default    | Bordas de inputs e cards
#334D6E  → border.strong     | Bordas enfatizadas, focus rings
```

### 2.5 Atualização do `index.css`

```css
@layer base {
  :root {
    /* ── Superfícies ── */
    --background:      223 56% 6%;    /* #060B14 */
    --card:            221 51% 9%;    /* #0A1120 */
    --popover:         220 46% 12%;   /* #0F1929 */

    /* ── Brand ── */
    --primary:         191 100% 45%; /* #00C5E3 */
    --primary-foreground: 223 56% 6%;

    /* ── Texto ── */
    --foreground:      214 32% 95%;  /* #F1F5F9 */
    --muted-foreground: 215 16% 57%; /* #94A3B8 */
    
    /* ── Semânticos ── */
    --success:         160 84% 39%;  /* #10B981 */
    --destructive:     0 84% 60%;    /* #EF4444 */
    --warning:         38 92% 50%;   /* #F59E0B */

    /* ── Bordas ── */
    --border:          214 34% 20%;  /* #1E2D45 */
    --input:           213 34% 19%;  /* #243348 */
    --ring:            191 100% 45%; /* #00C5E3 */

    /* ── Radius único ── */
    --radius: 0.625rem; /* 10px — profissional, não infantil */
  }
}
```

### 2.6 Regras de Uso da Paleta

| Contexto                  | Cor                | Regra                              |
|---------------------------|--------------------|------------------------------------|
| Valor positivo (lucro)    | `#10B981`          | Sempre verde — nunca azul          |
| Valor negativo (perda)    | `#EF4444`          | Sempre vermelho — nunca laranja    |
| CTA principal             | `#00C5E3`          | Único ponto de cyan saturado       |
| Links e nav ativos        | `#00C5E3`          | Consistência com CTA               |
| Fundo de gráficos         | `#060B14`          | Nunca transparente em chart        |
| Backgrounds de badge      | Cor + 15% opacidade| Ex: `rgba(16,185,129,0.15)`        |
| Glow/shadow               | Cor + 20% opacidade| Máximo — não exagerar              |

### 2.7 Microinterações de Cor
```css
/* Hover em valores financeiros — transição suave */
.price-value {
  transition: color 150ms ease;
}
.price-value.tick-up   { color: #10B981; }
.price-value.tick-down { color: #EF4444; }
.price-value.tick-neutral { color: #94A3B8; }
```

### 2.8 Erros Comuns a Corrigir
- ❌ Usar verde `#00ff00` ou `lime-400` para lucro — parece terminal dos anos 90
- ❌ Gradiente roxo+cyan em backgrounds — clichê de crypto 2021
- ❌ Bordas com `border-white/5` — invisíveis e inúteis
- ❌ Backgrounds semi-transparentes sem backdrop-blur — sujos
- ❌ `opacity-50` em texto já secundário — triplo-muted, ilegível

### 2.9 Gradientes Permitidos (Uso Restrito)
```css
/* Apenas em hero e header de página — não em cards */
.page-hero-gradient {
  background: linear-gradient(
    135deg,
    rgba(0,197,227,0.08) 0%,
    rgba(6,11,20,0) 50%
  );
}

/* Badge de status — sutil */
.badge-profit {
  background: rgba(16,185,129,0.12);
  border: 1px solid rgba(16,185,129,0.25);
  color: #10B981;
}
```

### 2.10 Checklist de Validação
- [ ] Paleta implementada no `index.css` com variáveis HSL
- [ ] Nenhum gradiente neon em áreas de conteúdo
- [ ] Valores positivos sempre `profit (#10B981)`
- [ ] Valores negativos sempre `loss (#EF4444)`
- [ ] Contraste mínimo AA (4.5:1) validado no WebAIM Contrast Checker
- [ ] Screenshot do dashboard aprovado sem "efeito neon excessivo"

---

## PONTO 3 — TIPOGRAFIA MODERNA E HIERARQUIA VISUAL CORRETA

### 3.1 Problema Atual
O projeto já importa Inter + Space Grotesk + JetBrains Mono — excelente escolha. O problema é como essas fontes são **aplicadas**. Títulos têm tamanhos inconsistentes, peso (font-weight) é usado sem critério, e dados financeiros (preços, percentuais) misturam fontes sans-serif com mono sem padrão definido.

### 3.2 Impacto Negativo
Hierarquia tipográfica fraca faz o usuário não saber onde olhar. Em dashboards financeiros, o olho precisa de uma rota clara: título → valor principal → contexto → ação. Sem isso, tudo parece igual e o produto perde autoridade.

### 3.3 Solução Proposta
Definir uma **escala tipográfica rigorosa** com papéis claros para cada nível. Dados numéricos financeiros sempre em `JetBrains Mono` — isso é convenção universal em fintechs profissionais.

### 3.4 Escala Tipográfica Completa

**Criar `src/design-system/typography.ts`:**

```typescript
export const typography = {
  // Escala de tamanhos (rem)
  scale: {
    '2xs': '0.625rem',  // 10px — micro labels
    'xs':  '0.75rem',   // 12px — caption, timestamp
    'sm':  '0.875rem',  // 14px — body small, labels
    'base':'1rem',      // 16px — body principal
    'lg':  '1.125rem',  // 18px — body large, subtítulos
    'xl':  '1.25rem',   // 20px — H4, card title
    '2xl': '1.5rem',    // 24px — H3, section header
    '3xl': '1.875rem',  // 30px — H2, page title
    '4xl': '2.25rem',   // 36px — H1, hero
    '5xl': '3rem',      // 48px — metric principal
    '6xl': '3.75rem',   // 60px — metric destaque máximo
  },
  // Pesos
  weight: {
    light:    300,
    regular:  400,
    medium:   500,
    semibold: 600,
    bold:     700,
    extrabold:800,
  },
  // Line heights
  leading: {
    none:    1,
    tight:   1.2,   // Títulos grandes
    snug:    1.35,  // Subtítulos
    normal:  1.5,   // Body text
    relaxed: 1.65,  // Texto longo, artigo
  },
  // Letter spacing
  tracking: {
    tighter: '-0.04em',  // Títulos grandes (> 30px)
    tight:   '-0.025em', // Títulos médios
    normal:   '0',
    wide:     '0.05em',  // All-caps labels, badges
    wider:    '0.1em',   // Micro-labels
  },
} as const;
```

### 3.5 Papéis Tipográficos por Contexto

```
DADOS FINANCEIROS (preços, percentuais, volumes):
  Font: JetBrains Mono
  Size: text-xl a text-5xl
  Weight: font-semibold (600)
  Tracking: tracking-tight
  Color: baseado em profit/loss

TÍTULOS DE PÁGINA E SEÇÃO:
  Font: Space Grotesk
  Size: text-2xl a text-4xl
  Weight: font-bold (700)
  Tracking: -0.03em
  Color: text.primary (#F1F5F9)

SUBTÍTULOS E CARD HEADERS:
  Font: Space Grotesk
  Size: text-lg a text-xl
  Weight: font-semibold (600)
  Tracking: -0.02em
  Color: text.primary

LABELS E LEGENDAS:
  Font: Inter
  Size: text-xs a text-sm
  Weight: font-medium (500)
  Tracking: 0.04em (uppercase) ou 0 (normal)
  Color: text.secondary (#94A3B8)
  Transform: uppercase (para legendas de gráfico/tabela)

BODY DE TEXTO:
  Font: Inter
  Size: text-sm a text-base
  Weight: font-regular (400)
  Leading: 1.5
  Color: text.body (#CBD5E1)

TIMESTAMPS E METADADOS:
  Font: JetBrains Mono
  Size: text-xs
  Weight: font-regular
  Color: text.muted (#475569)
```

### 3.6 Implementação no Tailwind (`tailwind.config.ts`)

```typescript
theme: {
  extend: {
    fontFamily: {
      sans:    ['Inter', 'system-ui', 'sans-serif'],
      display: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
      mono:    ['JetBrains Mono', 'Fira Code', 'monospace'],
    },
    fontSize: {
      '2xs': ['0.625rem', { lineHeight: '1rem' }],
      'xs':  ['0.75rem',  { lineHeight: '1rem' }],
      'sm':  ['0.875rem', { lineHeight: '1.25rem' }],
      'base':['1rem',     { lineHeight: '1.5rem' }],
      'lg':  ['1.125rem', { lineHeight: '1.75rem' }],
      'xl':  ['1.25rem',  { lineHeight: '1.75rem' }],
      '2xl': ['1.5rem',   { lineHeight: '2rem', letterSpacing: '-0.02em' }],
      '3xl': ['1.875rem', { lineHeight: '2.25rem', letterSpacing: '-0.025em' }],
      '4xl': ['2.25rem',  { lineHeight: '2.5rem', letterSpacing: '-0.03em' }],
      '5xl': ['3rem',     { lineHeight: '1.15', letterSpacing: '-0.04em' }],
    },
  }
}
```

### 3.7 Componentes Tipográficos

**`src/primitives/Typography.tsx`:**

```tsx
import { cn } from '@/lib/utils';

// Valor financeiro principal (preço, saldo)
export function MetricValue({ value, positive, negative, className }: {
  value: string;
  positive?: boolean;
  negative?: boolean;
  className?: string;
}) {
  return (
    <span className={cn(
      'font-mono font-semibold tracking-tight tabular-nums',
      positive && 'text-emerald-400',
      negative && 'text-red-400',
      !positive && !negative && 'text-content-primary',
      className
    )}>
      {value}
    </span>
  );
}

// Título de página
export function PageTitle({ children, className }: React.PropsWithChildren<{ className?: string }>) {
  return (
    <h1 className={cn(
      'font-display font-bold text-3xl text-content-primary tracking-tight',
      className
    )}>
      {children}
    </h1>
  );
}

// Label de seção (uppercase, rastreado)
export function SectionLabel({ children, className }: React.PropsWithChildren<{ className?: string }>) {
  return (
    <span className={cn(
      'font-sans font-medium text-xs text-content-secondary uppercase tracking-widest',
      className
    )}>
      {children}
    </span>
  );
}
```

### 3.8 Erros Comuns a Corrigir
- ❌ `text-white` em labels secundários — use `text-content-secondary`
- ❌ Percentuais em fonte sans-serif — sempre `font-mono`
- ❌ `font-bold` em tudo — destrui hierarquia
- ❌ `text-sm font-bold` em títulos de seção — pequeno demais
- ❌ Não usar `tabular-nums` em tabelas com números — desalinha colunas

### 3.9 Regra de Ouro: `tabular-nums`
Todo dado numérico que esteja em lista ou tabela DEVE ter `font-variant-numeric: tabular-nums` para que os dígitos se alinhem verticalmente:

```tsx
// Sempre que números mudam dinamicamente
<span className="font-mono tabular-nums slashed-zero">
  {price.toFixed(8)}
</span>
```

### 3.10 Checklist de Validação
- [ ] Preços e percentuais em `font-mono` em 100% dos componentes
- [ ] `tabular-nums` em todas as tabelas de trading
- [ ] Hierarquia: H1 > H2 > H3 > body sem duplicação de tamanho entre níveis
- [ ] Nenhum título com `text-sm font-bold` (anti-pattern)
- [ ] Label de seção padronizado com uppercase + tracking

---

## PONTO 4 — LAYOUT GRID CONSISTENTE E RESPONSIVO

### 4.1 Problema Atual
As páginas em `src/pages/` usam estruturas de grid ad-hoc: alguns cards em `grid-cols-3`, outros em `flex flex-wrap`, outros em `grid-cols-1 md:grid-cols-2`. Não existe um sistema de grade definido. O resultado em telas de 1280px é excelente em alguns lugares e quebrado em outros.

### 4.2 Impacto Negativo
Usuários de dashboards de trading geralmente têm monitores wide (1440px, 1920px, 2560px ou ultrawide). Um layout sem grid system desperdiça espaço ou estica componentes de forma grotesca.

### 4.3 Solução Proposta
Implementar um **layout de 12 colunas** com breakpoints específicos para trading (onde telas grandes são comuns) e um sistema de `DashboardLayout` reutilizável.

### 4.4 Sistema de Grid Padrão

```
Breakpoints:
  sm:  640px   → Mobile
  md:  768px   → Tablet portrait
  lg:  1024px  → Tablet landscape / laptop pequeno
  xl:  1280px  → Desktop padrão ← FOCO PRINCIPAL
  2xl: 1536px  → Monitor wide
  3xl: 1920px  → Monitor full HD / trading setup

Colunas por breakpoint:
  sm:  1 coluna
  md:  2 colunas
  lg:  3 colunas
  xl:  12 colunas (sistema completo)
  2xl: 12 colunas (mais espaçamento)
```

**Adicionar no `tailwind.config.ts`:**

```typescript
screens: {
  sm:  '640px',
  md:  '768px',
  lg:  '1024px',
  xl:  '1280px',
  '2xl': '1536px',
  '3xl': '1920px',
},
```

### 4.5 Layout Ideal para Dashboard de Trading

```tsx
// src/layouts/DashboardLayout.tsx
export function DashboardLayout({ children }: React.PropsWithChildren) {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-base">
      {/* Sidebar fixa — 64px colapsada / 240px expandida */}
      <Sidebar />
      
      {/* Main content com scroll independente */}
      <main className="flex-1 overflow-y-auto min-w-0">
        {/* Header sticky */}
        <TopBar />
        
        {/* Container de conteúdo */}
        <div className="px-6 py-6 max-w-[1600px] mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
```

```tsx
// src/layouts/DashboardGrid.tsx
// Template de grid para página de dashboard
export function DashboardGrid() {
  return (
    <div className="grid grid-cols-12 gap-4">
      {/* KPIs — linha superior — 3 colunas cada */}
      <div className="col-span-12 grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Saldo Total" value="$42,308.50" delta="+2.4%" positive />
        <MetricCard title="P&L Hoje"    value="$1,024.80"  delta="+3.1%" positive />
        <MetricCard title="Robôs Ativos" value="7"         delta="" />
        <MetricCard title="Win Rate"    value="68.4%"      delta="+0.8%" positive />
      </div>

      {/* Gráfico principal — 8 colunas */}
      <div className="col-span-12 xl:col-span-8">
        <EquityChart />
      </div>

      {/* Painel lateral direito — 4 colunas */}
      <div className="col-span-12 xl:col-span-4 flex flex-col gap-4">
        <ActiveRobotsPanel />
        <RecentTradesPanel />
      </div>

      {/* Tabela full-width */}
      <div className="col-span-12">
        <TradeHistoryTable />
      </div>
    </div>
  );
}
```

### 4.6 Regras de Espaçamento (Escala 4pt)

```
gap-1  → 4px  → Dentro de elementos (ícone + texto)
gap-2  → 8px  → Entre elementos relacionados
gap-4  → 16px → Entre cards no grid
gap-6  → 24px → Seções dentro de um card
gap-8  → 32px → Entre seções da página
gap-12 → 48px → Entre blocos maiores

Padding interno de card:
  Padrão: p-6 (24px)
  Compacto: p-4 (16px)
  Roomy: p-8 (32px)

Margem entre seções:
  mb-6 (24px) para seções próximas
  mb-10 (40px) para seções que mudam de contexto
```

### 4.7 Sidebar: Largura e Comportamento

```
Desktop (xl+): 240px expandida, 64px colapsada
Laptop (lg):   64px colapsada por padrão, hover para expandir
Tablet (md):   Overlay modal quando aberta, fechada por padrão
Mobile:        Bottom navigation bar (substituir sidebar)
```

### 4.8 Erros Comuns a Corrigir
- ❌ `max-w-7xl mx-auto` dentro de sidebar+content — container errado
- ❌ Cards que crescem indefinidamente em ultrawide
- ❌ Grid que não considera o sidebar width no cálculo
- ❌ `overflow-hidden` no body — impede scroll natural
- ❌ Padding inconsistente: `p-4` em uns, `px-6 py-4` em outros

### 4.9 Anti-pattern: Largura Máxima Correta

```tsx
// ❌ ANTES
<div className="container mx-auto px-4">

// ✅ DEPOIS — levando em conta sidebar+conteúdo
<div className="max-w-[1600px] mx-auto px-6">
```

### 4.10 Checklist de Validação
- [ ] Grid de 12 colunas operacional em todas as páginas principais
- [ ] Nenhum layout quebra em 1280px, 1440px, 1920px
- [ ] Sidebar tem largura fixa e não afeta o cálculo do grid
- [ ] KPIs sempre em linha superior horizontal
- [ ] Escala de espaçamento `4pt` usada consistentemente

---

## PONTO 5 — DASHBOARD PRINCIPAL LIMPO E ESTRATÉGICO

### 5.1 Problema Atual
O `src/pages/Dashboard.tsx` provavelmente contém muita informação simultaneamente, com cards de diferentes tamanhos, densidades e importâncias visuais competindo pela atenção. Em dashboards financeiros, o excesso de informação é tão prejudicial quanto a falta.

### 5.2 Impacto Negativo
O usuário abre o dashboard e não sabe onde olhar. Isso causa ansiedade, não confiança. Plataformas institucionais são deliberadamente simples no primeiro carregamento — mostram o essencial e oferecem drill-down.

### 5.3 Hierarquia de Informação no Dashboard

```
NÍVEL 1 — VISÃO IMEDIATA (0-2 segundos)
  • Saldo total da conta
  • P&L do dia (valor + percentual)
  • Status dos robôs (quantos ativos/parados)
  • Alerta crítico se houver

NÍVEL 2 — CONTEXTO (2-5 segundos)
  • Gráfico de equity/performance
  • Resumo das últimas operações
  • Distribuição de portfólio

NÍVEL 3 — DETALHE (sob demanda)
  • Histórico completo de trades
  • Logs de robôs
  • Configurações
```

### 5.4 Componente `MetricCard` Profissional

```tsx
// src/components/patterns/MetricCard.tsx
interface MetricCardProps {
  title: string;
  value: string;
  delta?: string;
  deltaPositive?: boolean;
  icon?: React.ReactNode;
  suffix?: string;
  loading?: boolean;
}

export function MetricCard({
  title, value, delta, deltaPositive, icon, suffix, loading
}: MetricCardProps) {
  if (loading) return <MetricCardSkeleton />;

  return (
    <div className="
      bg-surface-raised
      border border-edge-subtle
      rounded-lg p-6
      relative overflow-hidden
      group
      transition-all duration-200
      hover:border-edge-default
      hover:shadow-card
    ">
      {/* Label superior */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium text-content-secondary uppercase tracking-widest">
          {title}
        </span>
        {icon && (
          <div className="text-content-muted text-brand-primary/60 group-hover:text-brand-primary transition-colors">
            {icon}
          </div>
        )}
      </div>

      {/* Valor principal */}
      <div className="flex items-end gap-2">
        <span className="font-mono font-semibold text-3xl text-content-primary tabular-nums tracking-tight">
          {value}
        </span>
        {suffix && (
          <span className="font-mono text-sm text-content-secondary mb-1">{suffix}</span>
        )}
      </div>

      {/* Delta */}
      {delta && (
        <div className={cn(
          'flex items-center gap-1 mt-2 text-sm font-medium font-mono tabular-nums',
          deltaPositive ? 'text-emerald-400' : 'text-red-400'
        )}>
          {deltaPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          <span>{delta}</span>
          <span className="text-xs text-content-muted font-sans ml-1">vs ontem</span>
        </div>
      )}

      {/* Linha de accent no hover */}
      <div className="
        absolute bottom-0 left-0 right-0 h-[2px]
        bg-brand-primary/0 group-hover:bg-brand-primary/40
        transition-all duration-300
      " />
    </div>
  );
}
```

### 5.5 Regras de Densidade Visual

```
Cards KPI:         sempre na mesma linha, nunca empilhados verticalmente em desktop
Gráfico principal: mínimo 400px de altura, preferência 480px
Tabelas:           máximo 8-10 linhas visíveis sem scroll
Sidebar de robôs:  lista compacta, não cards grandes
Textos em cards:   máximo 2 linhas descritivas
```

### 5.6 O Que REMOVER do Dashboard
- ❌ Animações de entrada em cada card individualmente (confuso, lento)
- ❌ Cards decorativos sem dado real ("Bem-vindo ao CryptoTradeHub")
- ❌ Múltiplos gradientes neon em backgrounds de card
- ❌ Ícones grandes sem função (decorativos)
- ❌ Tooltips que aparecem sem hover real

### 5.7 O Que ADICIONAR
- ✅ Empty state elegante quando não há dados
- ✅ Indicador de "última atualização: Xm atrás"
- ✅ Botão de refresh manual com loading
- ✅ Status de conexão com KuCoin visível mas discreta

### 5.8 Empty State Profissional
```tsx
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-lg bg-surface-hover flex items-center justify-center mb-4">
        <BarChart2 className="text-content-muted" size={20} />
      </div>
      <h3 className="font-display font-semibold text-lg text-content-primary mb-2">{title}</h3>
      <p className="text-sm text-content-secondary max-w-xs mb-6">{description}</p>
      {action}
    </div>
  );
}
```

### 5.9 Sidebar de Robôs Compacta
```tsx
// Ao invés de cards grandes por robô, use lista compacta
<div className="space-y-1">
  {robots.map(robot => (
    <div key={robot.id} className="
      flex items-center gap-3 px-3 py-2.5 rounded-md
      hover:bg-surface-hover transition-colors cursor-pointer
    ">
      <div className={cn(
        'w-2 h-2 rounded-full flex-shrink-0',
        robot.active ? 'bg-emerald-400' : 'bg-content-muted'
      )} />
      <span className="text-sm font-medium text-content-primary truncate flex-1">
        {robot.name}
      </span>
      <span className={cn(
        'text-xs font-mono tabular-nums',
        robot.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
      )}>
        {robot.pnl >= 0 ? '+' : ''}{robot.pnl.toFixed(2)}%
      </span>
    </div>
  ))}
</div>
```

### 5.10 Checklist de Validação
- [ ] Dashboard carrega com no máximo 4 KPIs no topo
- [ ] Gráfico de equity ocupa posição de destaque
- [ ] Nenhum texto decorativo sem informação real
- [ ] Empty states implementados para todos os painéis
- [ ] "Última atualização" sempre visível

---

## PONTO 6 — COMPONENTIZAÇÃO CORRETA

### 6.1 Problema Atual
Com 20+ páginas e dezenas de componentes em `src/components/`, a probabilidade de duplicação é alta. Um `RobotCard` em `src/components/robots/` pode ter estrutura diferente do `RobotCard` em `src/components/dashboard/`. Cada feature provavelmente reimplementa seus próprios estados de loading, badges de status e formatação de preço.

### 6.2 Impacto Negativo
Duplicação = inconsistência visual. Quando o designer quer mudar o visual de "robô ativo", precisa alterar 5 arquivos. Quebra sempre.

### 6.3 Estrutura de Componentização Correta

```
src/components/
  ├── primitives/           ← Atoms (sem lógica)
  │   ├── Badge.tsx         ← Status, tag, label
  │   ├── Divider.tsx       ← Separador com label opcional
  │   ├── PriceDisplay.tsx  ← Preço formatado com cor automática
  │   ├── PercentBadge.tsx  ← Percentual +/- com cor
  │   ├── StatusDot.tsx     ← Ponto de status (active/inactive)
  │   └── Skeleton.tsx      ← Skeleton universal
  │
  ├── patterns/             ← Molecules (combinam primitivos)
  │   ├── MetricCard.tsx    ← KPI card reutilizável
  │   ├── TradePair.tsx     ← Par de trading (BTC/USDT)
  │   ├── RobotListItem.tsx ← Item de robô em lista
  │   ├── TradeRow.tsx      ← Linha de trade em tabela
  │   └── AlertItem.tsx     ← Item de alerta/notificação
  │
  ├── layouts/              ← Organisms (estrutura)
  │   ├── PageContainer.tsx ← Wrapper padrão de página
  │   ├── SectionHeader.tsx ← Título + ação de seção
  │   ├── DataTable.tsx     ← Tabela genérica com sort/filter
  │   └── SplitPanel.tsx    ← Layout de dois painéis
  │
  └── features/             ← Feature-specific (não reusar)
      ├── robots/
      ├── strategies/
      └── kucoin/
```

### 6.4 Componente `PriceDisplay` Universal

```tsx
// src/components/primitives/PriceDisplay.tsx
// Usado em TODOS os lugares onde há preço — sem exceção

interface PriceDisplayProps {
  value: number;
  currency?: string;
  decimals?: number;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showSign?: boolean;
  className?: string;
}

const sizes = {
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-xl',
  xl: 'text-3xl',
};

export function PriceDisplay({
  value, currency = 'USDT', decimals = 2, size = 'md', showSign = false, className
}: PriceDisplayProps) {
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(value));

  const isPositive = value > 0;
  const isNegative = value < 0;

  return (
    <span className={cn(
      'font-mono tabular-nums font-semibold',
      sizes[size],
      showSign && isPositive && 'text-emerald-400',
      showSign && isNegative && 'text-red-400',
      !showSign && 'text-content-primary',
      className
    )}>
      {showSign && isPositive && '+'}
      {showSign && isNegative && '-'}
      {formatted}
      {currency && (
        <span className="text-content-secondary font-medium ml-1 text-[0.75em]">
          {currency}
        </span>
      )}
    </span>
  );
}
```

### 6.5 Componente `PercentBadge` Universal

```tsx
// src/components/primitives/PercentBadge.tsx
export function PercentBadge({ value, className }: { value: number; className?: string }) {
  const positive = value > 0;
  const negative = value < 0;
  
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium tabular-nums',
      positive && 'bg-emerald-400/12 text-emerald-400 border border-emerald-400/20',
      negative && 'bg-red-400/12 text-red-400 border border-red-400/20',
      !positive && !negative && 'bg-surface-hover text-content-secondary border border-edge-subtle',
      className
    )}>
      {positive && <TrendingUp size={10} />}
      {negative && <TrendingDown size={10} />}
      {positive ? '+' : ''}{value.toFixed(2)}%
    </span>
  );
}
```

### 6.6 Erros Comuns a Corrigir
- ❌ Reinventar `Badge` em cada feature — padronize um e use
- ❌ Formatar preço com `toFixed(2)` inline — use `PriceDisplay`
- ❌ Lógica de status (active/inactive) duplicada em múltiplos componentes
- ❌ Props drilling excessivo — use Context ou composição

### 6.7 Regra: Nenhum Componente Formata Preço Sozinho
Qualquer número financeiro exibe via `<PriceDisplay>` ou `<PercentBadge>`. Nunca `{value.toFixed(2)}` direto no JSX.

### 6.8 Checklist de Validação
- [ ] `PriceDisplay.tsx` criado e usado em 100% dos lugares com preço
- [ ] `PercentBadge.tsx` criado e usado em 100% dos percentuais
- [ ] Nenhum `toFixed()` direto no JSX de componentes de UI
- [ ] Duplicação de RobotCard eliminada
- [ ] `StatusDot` padronizado para todos os indicadores de status

---

## PONTO 7 — FEEDBACK VISUAL PROFISSIONAL

### 7.1 Problema Atual
Loading states provavelmente usam spinners genéricos do shadcn. Erros exibem em toast genérico ou alert vermelho. Sucesso pode não ter feedback visual claro. Em uma plataforma de trading onde operações envolvem dinheiro real, o feedback inadequado gera ansiedade e desconfiança.

### 7.2 Solução: Sistema de 4 Estados Obrigatórios

Para cada operação assíncrona, implementar todos os 4 estados:

```
1. LOADING   → Skeleton ou spinner contextual
2. SUCCESS   → Feedback positivo breve (toast + animação)
3. ERROR     → Feedback claro com ação de recuperação
4. EMPTY     → Estado vazio elegante com orientação
```

### 7.3 Skeleton de Card Profissional

```tsx
// src/components/primitives/Skeleton.tsx
export function MetricCardSkeleton() {
  return (
    <div className="bg-surface-raised border border-edge-subtle rounded-lg p-6 animate-pulse">
      <div className="flex justify-between mb-4">
        <div className="h-3 bg-surface-active rounded w-24" />
        <div className="h-4 w-4 bg-surface-active rounded" />
      </div>
      <div className="h-8 bg-surface-active rounded w-32 mb-2" />
      <div className="h-3 bg-surface-active rounded w-20" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-0 divide-y divide-edge-subtle">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3 animate-pulse">
          <div className="h-3 bg-surface-active rounded w-24 flex-shrink-0" />
          <div className="h-3 bg-surface-active rounded w-16 flex-shrink-0" />
          <div className="h-3 bg-surface-active rounded flex-1" />
          <div className="h-3 bg-surface-active rounded w-20 flex-shrink-0" />
        </div>
      ))}
    </div>
  );
}
```

**CSS para pulse suave (não exagerado):**

```css
/* Em index.css — substituir o pulse padrão */
@keyframes subtle-pulse {
  0%, 100% { opacity: 0.6; }
  50%       { opacity: 0.9; }
}

.animate-pulse {
  animation: subtle-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
```

### 7.4 Sistema de Toast Profissional

```tsx
// src/utils/toast.ts — wrapper com estilos consistentes
import { toast } from 'sonner';

export const notify = {
  success: (message: string, options?: { description?: string }) =>
    toast.success(message, {
      description: options?.description,
      style: {
        background: '#0A1120',
        border: '1px solid rgba(16,185,129,0.3)',
        color: '#F1F5F9',
      },
      icon: <CheckCircle size={16} className="text-emerald-400" />,
    }),

  error: (message: string, options?: { description?: string; action?: ToastAction }) =>
    toast.error(message, {
      description: options?.description,
      action: options?.action,
      style: {
        background: '#0A1120',
        border: '1px solid rgba(239,68,68,0.3)',
        color: '#F1F5F9',
      },
    }),

  loading: (message: string) =>
    toast.loading(message, {
      style: {
        background: '#0A1120',
        border: '1px solid rgba(0,197,227,0.2)',
        color: '#94A3B8',
      },
    }),

  promise: <T,>(promise: Promise<T>, messages: { loading: string; success: string; error: string }) =>
    toast.promise(promise, messages),
};
```

**Uso:**
```tsx
// ❌ ANTES
toast({ title: "Operação realizada" });

// ✅ DEPOIS
notify.success('Robô ativado com sucesso', {
  description: 'BTC/USDT bot iniciou monitoramento'
});
```

### 7.5 Error State com Ação
```tsx
export function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-10 h-10 rounded-lg bg-red-400/10 flex items-center justify-center mb-4">
        <AlertCircle className="text-red-400" size={18} />
      </div>
      <h3 className="font-display font-semibold text-content-primary mb-1">{title}</h3>
      <p className="text-sm text-content-secondary mb-4 max-w-xs">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium text-brand-primary hover:text-brand-primary/80 transition-colors"
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}
```

### 7.6 Loading de Página vs Loading de Componente

```
Loading de PÁGINA inteira → Skeleton da estrutura completa (nunca spinner central)
Loading de CARD individual → Skeleton do card específico
Loading de BOTÃO → Spinner inline no botão (disable + spinner)
Loading de TABELA → Skeleton das linhas (não spinner no centro)
Loading de GRÁFICO → Área cinza com shimmer
```

### 7.7 Erros Comuns a Corrigir
- ❌ Spinner no centro da página durante loading
- ❌ "Loading..." como texto sem skeleton
- ❌ Toast de sucesso por mais de 4 segundos
- ❌ Error sem mensagem clara ou sem ação
- ❌ Botão que some durante loading (travamento visual)

### 7.8 Checklist de Validação
- [ ] Todo componente async tem skeleton definido
- [ ] `notify.ts` centralizado e usado em 100% dos toasts
- [ ] Botões têm estado de loading com spinner inline
- [ ] Error states têm botão "Tentar novamente"
- [ ] Nenhum toast dura mais de 5 segundos

---

## PONTO 8 — MICROINTERAÇÕES E ANIMAÇÕES SUAVES

### 8.1 Problema Atual
O `tailwind.config.ts` define `pulse-glow`, `float`, `glow-pulse` e outros — ou seja, animações excessivas. O problema é que animações perpétuas em dados financeiros cansam o usuário e distraem de informação real. Animações em dashboards de trading devem ser **funcionais**, não decorativas.

### 8.2 Regra Fundamental
> "Animate data changes, not decorations."

Animate quando: dados mudam, usuário age, estado transita.  
Não anime: cards carregando, backgrounds, ícones decorativos.

### 8.3 Animações Funcionais Recomendadas

**1. Tick de preço (dado muda):**
```tsx
// Hook para flash quando preço muda
function usePriceTick(value: number) {
  const [tick, setTick] = useState<'up' | 'down' | null>(null);
  const prevValue = useRef(value);

  useEffect(() => {
    if (value > prevValue.current) setTick('up');
    else if (value < prevValue.current) setTick('down');
    prevValue.current = value;
    const t = setTimeout(() => setTick(null), 500);
    return () => clearTimeout(t);
  }, [value]);

  return tick;
}

// No componente:
function LivePrice({ price }: { price: number }) {
  const tick = usePriceTick(price);
  return (
    <span className={cn(
      'font-mono font-semibold text-xl tabular-nums transition-colors duration-300',
      tick === 'up'   && 'text-emerald-400',
      tick === 'down' && 'text-red-400',
      !tick           && 'text-content-primary',
    )}>
      {price.toFixed(2)}
    </span>
  );
}
```

**2. Entrada de página:**
```css
/* index.css — entrada padrão de cards */
@keyframes fade-up-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

.animate-page-enter {
  animation: fade-up-in 0.25s ease-out forwards;
}
```

```tsx
// Stagger em listas
{items.map((item, i) => (
  <div
    key={item.id}
    className="animate-page-enter"
    style={{ animationDelay: `${i * 40}ms` }}
  >
    <RobotListItem item={item} />
  </div>
))}
```

**3. Hover em botão de ação:**
```css
/* Botão primário — escala sutil */
.btn-primary {
  transition: transform 150ms ease, box-shadow 150ms ease, background-color 150ms ease;
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(0, 197, 227, 0.25);
}
.btn-primary:active {
  transform: translateY(0);
  box-shadow: none;
}
```

**4. Status de robô (pulsação funcional):**
```css
/* Apenas no dot de robô ativo — não em cards */
.status-active {
  position: relative;
}
.status-active::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: rgba(16, 185, 129, 0.4);
  animation: ping 2s cubic-bezier(0, 0, 0.2, 1) infinite;
}
@keyframes ping {
  75%, 100% { transform: scale(2); opacity: 0; }
}
```

### 8.4 Animações Proibidas

| Animação                 | Motivo para remover                    |
|--------------------------|----------------------------------------|
| Float em cards           | Distrai da leitura de dados            |
| Glow pulsante em cards   | Parece notificação, confunde usuário   |
| Rotate em ícone estático | Sem função, cansa                      |
| Entrance em cada render  | Incomoda em atualizações frequentes    |
| Gradient animado de fundo| Nauseante em sessões longas            |

### 8.5 Configuração Correta no Tailwind

```typescript
// tailwind.config.ts — remoção de animações excessivas
keyframes: {
  // MANTER — funcionais
  'fade-up':    { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
  'fade-in':    { from: { opacity: '0' }, to: { opacity: '1' } },
  'slide-in':   { from: { opacity: '0', transform: 'translateX(-8px)' }, to: { opacity: '1', transform: 'translateX(0)' } },
  'ping':       { '75%,100%': { transform: 'scale(2)', opacity: '0' } },
  
  // REMOVER — decorativas
  // 'float'    → remove
  // 'glow-pulse' → remove
  // 'pulse-glow' → remove (usar só em status crítico)
},
animation: {
  'fade-up':  'fade-up 0.2s ease-out',
  'fade-in':  'fade-in 0.15s ease-out',
  'slide-in': 'slide-in 0.2s ease-out',
  'ping':     'ping 1.5s cubic-bezier(0,0,0.2,1) infinite',
},
```

### 8.6 Regra de Duração
```
Micro (hover, click):       100-200ms
Entrada de elemento:        200-300ms
Transição de página:        250-350ms
Animação de dado (tick):    300-500ms
Modal/drawer:               200-250ms (ease-out)
```

### 8.7 Erros Comuns a Corrigir
- ❌ `transition-all` em componentes com muitas propriedades — performático ruim
- ❌ `duration-500` em hover — lento demais
- ❌ Animações com `ease-in` — terminam bruscas, use `ease-out`
- ❌ Cards pulsando sem motivo quando não há alerta

### 8.8 Checklist de Validação
- [ ] Animações perpétuas removidas (float, glow-pulse, pulse-glow)
- [ ] Tick de preço implementado para dados em tempo real
- [ ] Hover em botões com `translateY(-1px)` e 150ms
- [ ] Entrada de página com `fade-up` de 250ms max
- [ ] Nenhuma animação com `ease-in`

---

## PONTO 9 — ORGANIZAÇÃO E ARQUITETURA DE PASTAS FRONTEND

### 9.1 Problema Atual
A estrutura atual em `src/` tem `components/`, `pages/`, `services/`, `hooks/`, `context/` mas dentro de `components/` há mistura de atomic design e feature-based sem critério. Componentes como `BinanceTrading.tsx`, `KuCoinDashboard.tsx` e `Fireworks.tsx` estão na raiz de `components/` junto com `ErrorBoundary.tsx` e `NavLink.tsx` — níveis completamente diferentes.

### 9.2 Solução: Arquitetura Feature-First com Atoms Compartilhados

```
src/
├── design-system/              ← Design tokens e utilitários visuais
│   ├── tokens.ts
│   ├── typography.ts
│   ├── animations.ts
│   └── index.ts
│
├── components/                 ← Componentes reutilizáveis
│   ├── ui/                     ← shadcn/ui (NÃO MODIFICAR)
│   ├── primitives/             ← Atoms - sem estado, sem fetch
│   │   ├── Badge.tsx
│   │   ├── PriceDisplay.tsx
│   │   ├── PercentBadge.tsx
│   │   ├── StatusDot.tsx
│   │   ├── Skeleton.tsx
│   │   └── index.ts
│   ├── patterns/               ← Molecules - combinam primitivos
│   │   ├── MetricCard.tsx
│   │   ├── MetricCardSkeleton.tsx
│   │   ├── TradePair.tsx
│   │   ├── EmptyState.tsx
│   │   ├── ErrorState.tsx
│   │   └── index.ts
│   └── layouts/                ← Organisms de estrutura
│       ├── PageContainer.tsx
│       ├── PageHeader.tsx
│       ├── SectionHeader.tsx
│       ├── DashboardGrid.tsx
│       └── index.ts
│
├── features/                   ← Módulos por domínio
│   ├── dashboard/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── index.ts
│   ├── robots/
│   │   ├── components/
│   │   │   ├── RobotCard.tsx
│   │   │   ├── RobotListItem.tsx
│   │   │   └── RobotStatusBadge.tsx
│   │   ├── hooks/
│   │   │   └── useRobots.ts
│   │   └── index.ts
│   ├── strategies/
│   ├── kucoin/
│   ├── affiliate/
│   └── auth/
│
├── pages/                      ← Rotas — apenas composição, sem lógica
│   ├── Dashboard.tsx
│   ├── Robots.tsx
│   └── Settings.tsx
│
├── hooks/                      ← Hooks globais reutilizáveis
│   ├── useWebSocket.ts
│   ├── useDebounce.ts
│   └── useLocalStorage.ts
│
├── services/                   ← Camada de API
│   ├── api.ts                  ← Cliente base (axios/fetch)
│   ├── robots.service.ts
│   ├── kucoin.service.ts
│   └── auth.service.ts
│
├── stores/                     ← Estado global (Zustand ou Context)
│   ├── auth.store.ts
│   ├── ui.store.ts
│   └── trading.store.ts
│
├── utils/                      ← Utilitários puros
│   ├── format.ts               ← formatPrice, formatPercent, formatDate
│   ├── toast.ts                ← Sistema de notificações
│   └── cn.ts                  ← Utilitário de classnames
│
└── types/                      ← TypeScript types globais
    ├── trading.types.ts
    ├── api.types.ts
    └── ui.types.ts
```

### 9.3 Regra de Hierarquia de Import

```
pages/ → pode importar de: features/, components/, hooks/, utils/, services/
features/ → pode importar de: components/, hooks/, utils/, services/, types/
components/ → pode importar de: design-system/, utils/, types/
hooks/ → pode importar de: services/, utils/, types/
services/ → pode importar de: utils/, types/
utils/ → sem imports internos
```

**Nenhuma camada importa de uma camada "acima" dela.**

### 9.4 Centralizar Formatação em `utils/format.ts`

```typescript
// src/utils/format.ts
export function formatPrice(
  value: number,
  options: { currency?: string; decimals?: number } = {}
): string {
  const { currency = 'USDT', decimals = 2 } = options;
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
  return currency ? `${formatted} ${currency}` : formatted;
}

export function formatPercent(value: number, options: { sign?: boolean } = {}): string {
  const { sign = true } = options;
  const prefix = sign && value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

export function formatDate(date: string | Date, format: 'short' | 'long' | 'time' = 'short'): string {
  const d = new Date(date);
  if (format === 'time') return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  if (format === 'long')  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' });
  return d.toLocaleDateString('pt-BR');
}

export function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000)     return `${(value / 1_000).toFixed(2)}K`;
  return value.toFixed(2);
}
```

### 9.5 Erros de Organização a Corrigir
- ❌ `BinanceTrading.tsx` na raiz de `components/` — mover para `features/`
- ❌ `Fireworks.tsx` em `components/` — mover para `features/gamification/`
- ❌ Lógica de negócio em `pages/` — extrair para feature hooks
- ❌ Múltiplos `useEffect` de fetch em pages — centralizar em services
- ❌ Constantes mágicas inline — centralizar em `types/` ou `utils/`

### 9.6 Checklist de Validação
- [ ] Pastas `primitives/`, `patterns/`, `layouts/` criadas
- [ ] Features movidas para `features/`
- [ ] `utils/format.ts` centralizado e importado por todos
- [ ] Nenhuma `page/` tem chamada de API direta
- [ ] Hierarquia de imports respeitada (validar com ESLint plugin `import/order`)

---

## PONTO 10 — CHECKLIST FINAL PARA REMOVER "CARA DE IA"

### 10.1 O Que Faz um Produto Parecer "Feito por IA"

Existem padrões visuais que delateurs imediatos:

| Symptom                           | Diagnóstico                              |
|-----------------------------------|------------------------------------------|
| Cards com gradiente roxo+cyan     | ChatGPT sugeriu, dev copiou             |
| "Bem-vindo de volta, [nome]!"     | Placeholder deixado como feature real   |
| Ícones em cada item de lista      | Maximizar visual sem motivo             |
| Efeitos glow em tudo              | Confunde destaque com decoração         |
| Bordas glassmorphism pesadas      | Tendência 2022, já clichê               |
| Animações de entrada em hover     | Dev nunca testou com dados reais        |
| Placeholder "Lorem ipsum" vivo    | Produto não testado                     |
| Breakpoints que não testou        | CSS gerado, não validado                |
| Tipografia sem linha de base      | Não usa sistema, usa valores ad-hoc     |
| Espaçamento "no olho"             | Não tem grid, não tem sistema           |

### 10.2 Auditoria Visual — 20 Perguntas

Execute esse checklist no produto:

**Identidade:**
- [ ] O logo é profissional e tem versão escura?
- [ ] Existe um favicon customizado (não o padrão do vite)?
- [ ] O nome do produto aparece na `<title>` correta?
- [ ] As fontes carregam com `font-display: swap`?

**Paleta:**
- [ ] Há mais de 3 cores diferentes sendo usadas como destaque?
- [ ] Existe algum elemento verde `#00ff00` ou equivalente?
- [ ] Gradientes estão restritos a máximo 2 pontos na página?
- [ ] Bordas são visíveis, não `rgba(255,255,255,0.03)`?

**Tipografia:**
- [ ] H1 > H2 > H3 têm diferença visual clara de escala?
- [ ] Todos os preços e percentuais usam `font-mono`?
- [ ] Há texto em `opacity-50` sobre texto já secundário?
- [ ] Labels usam uppercase + tracking correto?

**Espaçamento:**
- [ ] O padding dos cards é consistente (todos `p-6` ou todos `p-4`)?
- [ ] O gap do grid é o mesmo em toda a aplicação?
- [ ] Existe airespace entre groups de conteúdo?

**Interação:**
- [ ] Todo botão tem hover visível?
- [ ] Inputs têm focus ring claramente visível?
- [ ] Erros de formulário têm mensagem abaixo do campo?
- [ ] Loading states estão implementados em 100% dos fetches?

**Dados:**
- [ ] Não há `undefined`, `NaN` ou `null` renderizados na tela?

### 10.3 Os 10 Indicadores de Premium vs. Genérico

| Genérico (remover)                    | Premium (implementar)                    |
|---------------------------------------|------------------------------------------|
| Spinner centralizado                  | Skeleton específico por componente       |
| Toast vermelho genérico               | Toast contextual com ação de recovery    |
| `text-white` em tudo                  | Hierarquia com 3 tons de texto           |
| `bg-gray-800` como card               | `bg-surface-raised` com token            |
| `border-white/10`                     | `border-edge-subtle` definido            |
| Gradient roxo+cyan em card            | Ausência de gradiente em áreas de dado   |
| Ícones com `text-4xl`                 | Ícones `size={16}` ou `size={20}`        |
| "Nenhum dado" sem estilo              | EmptyState com orientação ao usuário     |
| Font-size aleatório                   | Escala tipográfica rigorosa              |
| Animações em todo render              | Animação apenas em mudança de dado       |

### 10.4 Critério de "Pronto"

Um dashboard fintech profissional:

1. **Silencioso quando estável** — sem animações, sem piscadas, sem glow quando dados não mudam
2. **Expressivo quando algo muda** — price tick, notificação, status change
3. **Denso mas não poluído** — informação compacta, mas com breathing room
4. **Escuro mas legível** — contraste mínimo 4.5:1 em todo texto
5. **Consistente do primeiro ao último pixel** — mesmo token, mesmo espaçamento
6. **Responsivo de verdade** — testado em 768px, 1280px, 1440px, 1920px
7. **Rápido na percepção** — skeleton em < 100ms, dados em < 800ms
8. **Confiável visualmente** — sem undefined, sem erros silenciosos
9. **Sem decoração vazia** — cada elemento tem função
10. **Com identidade própria** — não parece nenhum template conhecido

### 10.5 Script de Auditoria Rápida

Execute no terminal do projeto para detectar problemas comuns:

```bash
# Detectar cores hardcoded que deveriam ser tokens
grep -rn "bg-gray-\|text-gray-\|border-gray-" src/components/ src/pages/
grep -rn "text-cyan-\|bg-cyan-\|border-cyan-" src/components/ src/pages/
grep -rn "text-white\b" src/components/ src/pages/

# Detectar toFixed() direto no JSX (deve usar PriceDisplay)
grep -rn "\.toFixed(" src/components/ src/pages/

# Detectar animações proibidas
grep -rn "animate-float\|pulse-glow\|glow-pulse" src/

# Detectar Lorem ipsum ou texto de placeholder
grep -rn "Lorem ipsum\|placeholder text\|TODO:" src/pages/
```

### 10.6 Prioridade de Execução

Execute as mudanças nesta ordem:

```
SPRINT 1 — Fundação (2-3 dias)
  ✦ Implementar tokens.ts e refatorar tailwind.config.ts
  ✦ Atualizar paleta de cores no index.css
  ✦ Criar PriceDisplay e PercentBadge universais
  ✦ Centralizar format.ts

SPRINT 2 — Componentes Core (3-4 dias)
  ✦ MetricCard com skeleton
  ✦ Sistema de toast unificado
  ✦ EmptyState e ErrorState
  ✦ Tipografia padronizada

SPRINT 3 — Layout e Grid (2-3 dias)
  ✦ DashboardGrid de 12 colunas
  ✦ DashboardLayout com sidebar correta
  ✦ Responsividade validada
  ✦ Espaçamento padronizado

SPRINT 4 — Refinamento (2 dias)
  ✦ Remover animações proibidas
  ✦ Implementar tick de preço
  ✦ Auditoria de acessibilidade (contraste)
  ✦ Auditoria com os 20 critérios do Checklist Final

TOTAL ESTIMADO: 9-12 dias de desenvolvimento focado
```

### 10.7 Checklist Final Definitivo

- [ ] Design tokens implementados e em produção
- [ ] Nova paleta sem cores neon excessivas
- [ ] Escala tipográfica com 5 níveis claros
- [ ] Grid de 12 colunas em todas as páginas
- [ ] Dashboard com hierarquia de informação L1/L2/L3
- [ ] PriceDisplay e PercentBadge em 100% dos dados financeiros
- [ ] Skeleton em 100% dos componentes assíncronos
- [ ] Sistema de toast unificado e estilizado
- [ ] EmptyState elegante em todas as listagens
- [ ] Animações perpétuas removidas
- [ ] Tick de preço implementado para dados em tempo real
- [ ] Arquitetura de pastas refatorada (feature-first)
- [ ] `utils/format.ts` centralizado
- [ ] 20 perguntas da auditoria visual aprovadas
- [ ] Testado em 768px, 1280px, 1440px e 1920px
- [ ] Contraste mínimo AA verificado
- [ ] Nenhuma cor hardcoded nos componentes
- [ ] Nenhum `undefined` ou `NaN` renderizado
- [ ] Script de auditoria rápida retorna zero ocorrências
- [ ] Review visual: produto não se parece com nenhum template

---

## REFERÊNCIAS VISUAIS DE PRODUTOS PREMIUM NO SEGMENTO

| Produto            | O que aprender                                     |
|--------------------|----------------------------------------------------|
| **Coinbase Pro**   | Densidade de informação, paleta azul sóbria        |
| **Kraken**         | Hierarquia tipográfica, dados compactos            |
| **Bloomberg Terminal** | Densidade máxima sem poluição               |
| **Linear**         | Espaçamento, transições, empty states              |
| **Vercel Dashboard** | Cards minimalistas, feedback de estado           |
| **Stripe Dashboard** | Tipografia, paleta, MetricCards                 |
| **Robinhood**      | Preço como herói, minimalismo funcional            |

---

*Documentação gerada com base na análise do codebase real do CryptoTradeHub.*  
*Stack analisada: React + TypeScript + Tailwind CSS + shadcn/ui + Vite.*  
*Fontes identificadas: Inter, Space Grotesk, JetBrains Mono.*
