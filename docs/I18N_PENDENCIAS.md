# Sistema de Idiomas — O que falta para funcionar 100%

> Análise feita em 02/03/2026. A infraestrutura existe e está corretamente conectada. O problema é que quase nenhuma página consome o sistema.

---

## ✅ O que já está pronto (não mexer)

| Componente | Arquivo | Status |
|---|---|---|
| Hook `useLanguage` + `LanguageProvider` | `src/hooks/use-language.tsx` | ✅ completo |
| Função `t(chave)` com dot-notation | idem | ✅ funciona |
| Persistência em `localStorage` | idem | ✅ funciona |
| Detecção automática do browser | idem | ✅ funciona |
| `LanguageProvider` envolve o app | `src/App.tsx` linha ~119 | ✅ correto |
| Arquivos JSON existem | `src/lib/i18n/pt|en|es|fr.json` | ✅ existem |
| `LanguageSwitcher` no header | `src/components/layout/LanguageSwitcher.tsx` | ✅ criado |

---

## 🔴 PROBLEMA 1 — Chave duplicada nos JSONs (bug silencioso)

**Afeta:** todos os 4 arquivos de tradução (`pt.json`, `en.json`, `es.json`, `fr.json`)

Dentro do bloco `"robots"` existe a chave `"performance"` **duas vezes**:

```json
"robots": {
  "performance": "Performance em Tempo Real",   ← sobrescrita
  ...
  "performance": "Alta Performance",             ← esta vence (comportamento inválido)
}
```

JSON não aceita chaves duplicadas. Em navegadores, a **segunda sobrescreve a primeira**, fazendo `t('robots.performance')` sempre retornar "Alta Performance" em vez de "Performance em Tempo Real".

### Correção

Renomear a primeira ocorrência em **todos os 4 arquivos**:

| Arquivo | Antes | Depois |
|---|---|---|
| `pt.json` | `"performance": "Performance em Tempo Real"` | `"performanceRealtime": "Performance em Tempo Real"` |
| `en.json` | `"performance": "Real-Time Performance"` | `"performanceRealtime": "Real-Time Performance"` |
| `es.json` | `"performance": "Rendimiento en Tiempo Real"` | `"performanceRealtime": "Rendimiento en Tiempo Real"` |
| `fr.json` | `"performance": "Performance en Temps Réel"` | `"performanceRealtime": "Performance en Temps Réel"` |

---

## 🔴 PROBLEMA 2 — Páginas com textos hardcoded (principal lacuna)

A troca de idioma já funciona tecnicamente, mas **nenhuma página usa `t()`**. Os textos estão escritos diretamente no JSX em português fixo.

### Páginas que precisam ser migradas

| Página / Componente | Arquivo | Textos hardcoded |
|---|---|---|
| Sidebar (navegação) | `src/components/layout/Sidebar.tsx` | Labels dos itens: "Dashboard", "Estratégias", "Projeções", etc. |
| Header | `src/components/layout/Header.tsx` | "Buscar robôs, pares...", "Minha Conta", "Perfil", etc. |
| Dashboard | `src/pages/Dashboard.tsx` | Títulos, cards, labels de métricas |
| Robôs / Marketplace | `src/pages/RobotsGameMarketplace.tsx` | Todos os textos da página |
| Afiliados | `src/pages/Affiliate.tsx` | Todos os textos |
| Projeções | `src/pages/Projections.tsx` | Todos os textos |
| Login | `src/pages/Login.tsx` | Formulário, botões, links |
| Signup | `src/pages/Signup.tsx` | Formulário |
| Esqueci a senha | `src/pages/ForgotPassword.tsx` | Formulário |
| Vídeo Aulas | `src/pages/VideoAulas.tsx` | Todos os textos |
| EA Monitor | `src/pages/EAMonitor.tsx` | Todos os textos |
| Licenças | `src/pages/Licenses.tsx` | Todos os textos |

### Como corrigir (padrão)

**Passo 1 — Importar o hook na página:**
```tsx
import { useLanguage } from '@/hooks/use-language';
```

**Passo 2 — Extrair `t` dentro do componente:**
```tsx
const { t } = useLanguage();
```

**Passo 3 — Substituir strings hardcoded por chamadas `t()`:**
```tsx
// ANTES
<span>Dashboard</span>

// DEPOIS
<span>{t('navigation.dashboard')}</span>
```

**Passo 4 — Garantir que a chave existe nos 4 JSONs** (`pt`, `en`, `es`, `fr`)

---

## 🟡 PROBLEMA 3 — Chaves faltando nos JSONs

Os arquivos JSON cobrem apenas 8 seções. Faltam traduções para várias partes do sistema.

### Seções faltando

| Seção | Chaves necessárias |
|---|---|
| `login` | email, password, forgotPassword, loginButton, noAccount, signupLink |
| `signup` | name, email, password, createAccount, alreadyHave, loginLink |
| `projections` | title, description, period, scenario, conservative, moderate, aggressive |
| `videoAulas` | title, description, watch, duration, level, beginner, advanced |
| `eaMonitor` | title, status, connected, disconnected, lastSync |
| `licenses` | title, active, expired, renew, plan, expiresAt |
| `strategies` | title, myStrategies, submit, public, private, backtest |
| `common` | search (placeholder), noResults, loadMore, viewAll |

### Exemplo de como adicionar ao `pt.json`:
```json
{
  "login": {
    "email": "E-mail",
    "password": "Senha",
    "forgotPassword": "Esqueci minha senha",
    "loginButton": "Entrar",
    "noAccount": "Não tem conta?",
    "signupLink": "Cadastre-se"
  }
}
```
Adicionar a mesma estrutura com os equivalentes em `en.json`, `es.json`, `fr.json`.

---

## 🟡 PROBLEMA 4 — Francês não aparece no switcher do header

O hook `useLanguage` suporta 4 idiomas: `pt`, `en`, `es`, `fr`.

O componente `LanguageSwitcher` (`src/components/layout/LanguageSwitcher.tsx`) exibe apenas 3 bandeiras:

```tsx
const LANGUAGES = [
  { code: 'pt', flag: '🇧🇷', name: 'Português' },
  { code: 'en', flag: '🇺🇸', name: 'English' },
  { code: 'es', flag: '🇪🇸', name: 'Español' },
  // 🇫🇷 Français — ausente
];
```

Decisão necessária: **incluir francês ou remover do hook**. Se não usar FR, remover o import de `fr.json` em `use-language.tsx` para não carregar JSON desnecessário.

---

## 📋 Checklist de prioridade

```
CRÍTICO (quebra silenciosa)
[ ] Corrigir chave duplicada "performance" nos 4 JSONs

ALTO (nenhuma página traduz de fato)
[ ] Migrar Sidebar.tsx para usar t('navigation.*')
[ ] Migrar Header.tsx para usar t('common.search') etc.
[ ] Migrar Dashboard.tsx
[ ] Migrar Affiliate.tsx
[ ] Migrar Login.tsx e Signup.tsx

MÉDIO (conteúdo faltando)
[ ] Adicionar seção "login" nos 4 JSONs
[ ] Adicionar seção "signup" nos 4 JSONs
[ ] Adicionar seção "projections" nos 4 JSONs
[ ] Adicionar seção "videoAulas" nos 4 JSONs

BAIXO
[ ] Decidir sobre FR: incluir no switcher ou remover do hook
[ ] Migrar páginas secundárias (Licenses, EAMonitor, VideoAulas)
```

---

## 🔧 Ordem de execução recomendada

1. **Fix JSONs** (corrigir chave duplicada + adicionar seções faltando)
2. **Migrar Sidebar** — maior impacto visual imediato (navega-se por ele em todas as páginas)
3. **Migrar Header** — segundo maior impacto
4. **Migrar Dashboard** — página inicial
5. **Migrar Login/Signup** — primeiras telas que o usuário vê
6. **Migrar páginas internas** — uma por vez, conforme prioridade de negócio
