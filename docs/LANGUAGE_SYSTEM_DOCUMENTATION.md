# 🌐 Sistema de Idiomas - Documentação Completa

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Componentes Principais](#componentes-principais)
4. [Como Funciona](#como-funciona)
5. [Como Usar](#como-usar)
6. [Adicionando Novos Idiomas](#adicionando-novos-idiomas)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O sistema de idiomas (i18n) permite que toda a interface da plataforma **mude instantaneamente** entre múltiplos idiomas. Atualmente suportamos:

- 🇧🇷 **Português** (PT)
- 🇺🇸 **English** (EN)
- 🇪🇸 **Español** (ES)
- 🇫🇷 **Français** (FR)

### Características Principais

✅ **Mudança instantânea** - Interface atualiza sem recarregar a página  
✅ **Persistência** - Preferência salva no `localStorage`  
✅ **Auto-detecção** - Detecta idioma do sistema operacional  
✅ **Reativo** - Usa React Context para atualizações em tempo real  
✅ **Type-safe** - TypeScript garante tipos corretos  

---

## 🏗️ Arquitetura

### Estrutura de Arquivos

```
src/
├── hooks/
│   └── use-language.tsx           # Hook principal do contexto
├── lib/
│   └── i18n/
│       ├── en.json               # Traduções em English
│       ├── pt.json               # Traduções em Português
│       ├── es.json               # Traduções em Español
│       └── fr.json               # Traduções em Français
└── components/
    └── LanguageSelector.tsx      # Componente de seleção
```

### Fluxo de Dados

```
App.tsx (LanguageProvider)
    ↓
useLanguage() Hook
    ├── language (estado atual)
    ├── setLanguage() (muda idioma)
    ├── t() (função de tradução)
    └── availableLanguages[] (lista de idiomas)
    ↓
Componentes (Settings, Dashboard, etc.)
    ↓
localStorage & localStorage event
```

---

## 🔧 Componentes Principais

### 1. Hook `use-language.tsx`

**Localização:** `src/hooks/use-language.tsx`

```tsx
export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage deve ser usado dentro de LanguageProvider');
  }
  return context;
}
```

**Interface:**

```tsx
interface LanguageContextType {
  language: Language;              // idioma atual ('pt', 'en', 'es', 'fr')
  setLanguage: (lang: Language) => void;  // muda o idioma
  t: (key: string) => string;     // função de tradução
  availableLanguages: Array<{      // lista de idiomas disponíveis
    code: Language;
    name: string;
    flag: string;
  }>;
}
```

### 2. LanguageProvider

Envolve toda a aplicação no `App.tsx`:

```tsx
const App = () => (
  <ErrorBoundary>
    <LanguageProvider>
      {/* resto da aplicação */}
    </LanguageProvider>
  </ErrorBoundary>
);
```

### 3. Componente LanguageSelector

**Localização:** `src/components/LanguageSelector.tsx`

Renderiza os 4 botões de seleção de idioma. Usado na aba "Idioma" das Settings.

```tsx
<LanguageSelector />
```

### 4. Arquivos de Tradução JSON

**Localização:** `src/lib/i18n/`

Exemplo estrutura (`pt.json`):

```json
{
  "common": {
    "save": "Salvar",
    "cancel": "Cancelar",
    "loading": "Carregando..."
  },
  "dashboard": {
    "title": "Dashboard",
    "welcome": "Bem-vindo"
  },
  "settings": {
    "language": {
      "title": "Idioma e Localização",
      "auto_detect": "Auto-detectar Idioma"
    }
  }
}
```

---

## ⚙️ Como Funciona

### Step 1: Inicialização

1. Aplicação carrega em `App.tsx`
2. `LanguageProvider` verifica `localStorage`:
   - Se existe `language` salvo → usa esse idioma
   - Se existe `use-system-language` → detecta idioma do sistema
   - Caso contrário → usa português como padrão

```tsx
const language = (() => {
  const saved = localStorage.getItem('language');
  if (saved && ['pt', 'en', 'es', 'fr'].includes(saved)) {
    return saved;
  }
  
  if (localStorage.getItem('use-system-language') === 'true') {
    return getSystemLanguage();
  }
  
  return 'pt'; // fallback
})();
```

### Step 2: Uso em Componentes

```tsx
export default function MyComponent() {
  const { language, t } = useLanguage();
  
  return (
    <div>
      <h1>{t('dashboard.title')}</h1>
      {/* Busca a chave "dashboard.title" no arquivo de tradução */}
    </div>
  );
}
```

### Step 3: Mudança de Idioma

Quando usuário clica em um idioma:

```tsx
const handleLanguageChange = (newLang: Language) => {
  setLanguage(newLang);              // muda estado
  localStorage.setItem('language', newLang);  // persiste
  // Toast de confirmação
  toast.success(`Idioma alterado para ${langName}`);
};
```

### Step 4: Atualização em Tempo Real

O hook dispara um evento customizado:

```tsx
window.dispatchEvent(new CustomEvent('languageChanged', { 
  detail: { language: lang } 
}));
```

Toda a interface se subscreve a mudanças do contexto React automaticamente.

---

## 📖 Como Usar

### Para Alterar Idioma na Interface

1. Acesse **Configurações** (`/settings`)
2. Clique na aba **Idioma** 🌐
3. Selecione o idioma desejado
4. A interface **muda instantaneamente**

### Para Usar Traduções em um Componente

```tsx
import { useLanguage } from '@/hooks/use-language';

export function MyComponent() {
  const { t, language } = useLanguage();
  
  return (
    <div>
      {/* Usar função t() para acessar traduções */}
      <button>{t('common.save')}</button>
      <p>{t('settings.language.title')}</p>
      
      {/* Acessar idioma atual se precisar fazer lógica específica */}
      {language === 'pt' && <p>Você está usando português</p>}
    </div>
  );
}
```

### Para Acessar Lista de Idiomas Disponíveis

```tsx
const { availableLanguages } = useLanguage();

availableLanguages.forEach(lang => {
  console.log(lang.code);  // 'pt', 'en', 'es', 'fr'
  console.log(lang.name);  // 'Português', 'English', etc
  console.log(lang.flag);  // '🇧🇷', '🇺🇸', etc
});
```

### Para Ativar Auto-Detecção

Na aba Idioma > Settings, toggle "Auto-detectar Idioma":

- ✅ ON: Usa idioma do OS (recarrega a página)
- ❌ OFF: Usa idioma selecionado manualmente

---

## ➕ Adicionando Novos Idiomas

### Passo 1: Criar Arquivo de Tradução

Criar `src/lib/i18n/de.json` (para Alemão):

```json
{
  "common": {
    "save": "Speichern",
    "cancel": "Abbrechen",
    "loading": "Lädt..."
  },
  "dashboard": {
    "title": "Dashboard",
    "welcome": "Willkommen"
  }
}
```

### Passo 2: Atualizar use-language.tsx

```tsx
import de from '@/lib/i18n/de.json';

type Language = 'pt' | 'en' | 'es' | 'fr' | 'de';

const translations: Record<Language, typeof pt> = {
  pt,
  en,
  es,
  fr,
  de,  // ← ADD HERE
};

const availableLanguages = [
  { code: 'pt' as Language, name: 'Português', flag: '🇧🇷' },
  { code: 'en' as Language, name: 'English', flag: '🇺🇸' },
  { code: 'es' as Language, name: 'Español', flag: '🇪🇸' },
  { code: 'fr' as Language, name: 'Français', flag: '🇫🇷' },
  { code: 'de' as Language, name: 'Deutsch', flag: '🇩🇪' },  // ← ADD HERE
];
```

### Passo 3: Copiar Todas as Chaves

Copie a estrutura completa de chaves de `pt.json` e traduza para o novo idioma.

**Importante:** Manter exatamente as mesmas chaves em todos os arquivos, apenas traduzir os valores.

---

## 🔍 Troubleshooting

### Problema: Idioma não muda

**Solução 1:** Verificar se localStorage está limpo
```typescript
// No console do navegador
localStorage.clear();
location.reload();
```

**Solução 2:** Verificar se LanguageProvider está envolvendo a app
```tsx
// App.tsx deve ter:
<LanguageProvider>
  <AppContent />
</LanguageProvider>
```

### Problema: Chave de tradução não encontrada

**Causa:** Chave digitada incorretamente ou não existe no arquivo JSON

**Solução:**
```tsx
const { t, language } = useLanguage();

// ❌ Errado
t('dashboard.titl');  // retorna a chave literal

// ✅ Correto
t('dashboard.title');

// Debug: logar o idioma atual
console.log('Idioma atual:', language);
```

### Problema: Tradução não atualiza imediatamente

**Causa:** Componente não se inscreve ao contexto corretamente

**Solução:** Garantir que o hook está sendo usado:
```tsx
// ✅ Correto - usa o hook
export function Component() {
  const { t } = useLanguage();
  return <p>{t('key')}</p>;
}

// ❌ Errado - tenta usar fora do contexto
export function Component() {
  // useLanguage retorna erro aqui
  return <p>{t('key')}</p>;
}
```

### Problema: Auto-detecção de idioma não funciona

**Solução:**
```tsx
// No console do navegador, verificar:
navigator.language;  // ex: "pt-BR"

// Se retornar idioma não suportado, fallback para 'pt'
const supportedLangs = ['pt', 'en', 'es', 'fr'];
const detected = navigator.language.split('-')[0];
const lang = supportedLangs.includes(detected) ? detected : 'pt';
```

---

## 📊 Estrutura de Tradução Recomendada

Para manter consistência, use a seguinte estrutura nos arquivos JSON:

```json
{
  "common": {
    "save": "",
    "cancel": "",
    "loading": "",
    "error": "",
    "success": ""
  },
  "navigation": {
    "dashboard": "",
    "settings": "",
    "profile": ""
  },
  "settings": {
    "title": "",
    "profile": {
      "title": "",
      "name": ""
    },
    "language": {
      "title": "",
      "auto_detect": ""
    }
  },
  "messages": {
    "welcome": "",
    "goodbye": ""
  }
}
```

---

## 🧪 Testando o Sistema

### Teste 1: Mudança de Idioma

1. Abir Settings `/settings?tab=language`
2. Clicar em "English"
3. ✅ Verificar se toda interface mudou para English
4. Recarregar a página (F5)
5. ✅ Verificar se mantém English (localStorage)

### Teste 2: Auto-detecção

1. Limpar localStorage: `localStorage.clear()`
2. Ativar toggle "Auto-detectar Idioma"
3. ✅ Página deve recarregar com idioma do sistema

### Teste 3: Componente Novo

1. Criar novo componente
2. Importar `useLanguage`
3. Usar `t('chave.subchave')`
4. ✅ Verificar se muda com os outros idiomas

---

## 📝 Checklist de Implementação

- [x] Hook `use-language.tsx` criado
- [x] LanguageProvider envolvendo App.tsx
- [x] Arquivos JSON de tradução (pt, en, es, fr)
- [x] Componente `LanguageSelector.tsx`
- [x] Integração em Settings (`/settings?tab=language`)
- [x] localStorage funcionando
- [x] Auto-detecção de idioma do sistema
- [x] Toast de confirmação
- [x] Type-safety com TypeScript
- [x] Documentação ✅

---

## 🚀 Próximas Melhorias

- [ ] Adicionar mais idiomas (Alemão, Chinês, Árabe, etc)
- [ ] Sincronizar idioma com backend (salvar preferência do usuário)
- [ ] RTL (Right-to-Left) para idiomas como Árabe
- [ ] Cache de tradução para melhor performance
- [ ] Editor visual de tradução
- [ ] Pluralização automática

---

## 📞 Suporte

Se encontrar problemas com o sistema de idiomas:

1. Verificar console do navegador para erros
2. Limpar localStorage: `localStorage.clear()`
3. Verificar se chave de tradução existe em todos os idiomas
4. Garantir que hook é usado dentro de LanguageProvider

---

**Última atualização:** 19 de Fevereiro de 2026  
**Version:** 1.0 - Sistema Completo e Funcional ✅
