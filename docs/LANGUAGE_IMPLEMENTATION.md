# 🔧 Implementação Atual - Sistema de Idiomas

## 📝 Código Atual em Produção

### 1. Hook - use-language.tsx

**Localização:** `src/hooks/use-language.tsx`

**Código completo:**

```typescript
import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import en from '@/lib/i18n/en.json';
import pt from '@/lib/i18n/pt.json';
import es from '@/lib/i18n/es.json';
import fr from '@/lib/i18n/fr.json';

type Language = 'pt' | 'en' | 'es' | 'fr';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
  availableLanguages: Array<{ code: Language; name: string; flag: string }>;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const translations: Record<Language, typeof pt> = {
  pt,
  en,
  es,
  fr,
};

const getSystemLanguage = (): Language => {
  const browserLang = navigator.language.split('-')[0].toLowerCase();
  
  const supportedLangs: Language[] = ['pt', 'en', 'es', 'fr'];
  if (supportedLangs.includes(browserLang as Language)) {
    return browserLang as Language;
  }
  
  return 'pt'; // fallback
};

const getNestedValue = (obj: any, path: string): string => {
  const keys = path.split('.');
  let value = obj;
  
  for (const key of keys) {
    if (value && typeof value === 'object' && key in value) {
      value = value[key];
    } else {
      return path; // retorna a chave se não encontrar
    }
  }
  
  return typeof value === 'string' ? value : path;
};

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    const saved = localStorage.getItem('language');
    if (saved && ['pt', 'en', 'es', 'fr'].includes(saved)) {
      return saved as Language;
    }
    
    const systemLang = localStorage.getItem('use-system-language');
    if (systemLang === 'true') {
      return getSystemLanguage();
    }
    
    return 'pt';
  });

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.setAttribute('data-language', language);
  }, [language]);

  const setLanguage = (lang: Language) => {
    console.log('[useLanguage] Alterando idioma para:', lang);
    setLanguageState(lang);
    localStorage.setItem('language', lang);
    localStorage.removeItem('use-system-language');
    // Force update by dispatching an event
    window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
  };

  const t = (key: string): string => {
    return getNestedValue(translations[language], key);
  };

  const availableLanguages = [
    { code: 'pt' as Language, name: 'Português', flag: '🇧🇷' },
    { code: 'en' as Language, name: 'English', flag: '🇺🇸' },
    { code: 'es' as Language, name: 'Español', flag: '🇪🇸' },
    { code: 'fr' as Language, name: 'Français', flag: '🇫🇷' },
  ];

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, availableLanguages }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage deve ser usado dentro de LanguageProvider');
  }
  return context;
}
```

---

### 2. Componente - LanguageSelector.tsx

**Localização:** `src/components/LanguageSelector.tsx`

```typescript
import { useLanguage } from '@/hooks/use-language';
import { CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

type Language = 'pt' | 'en' | 'es' | 'fr';

export function LanguageSelector() {
  const { language, setLanguage, availableLanguages } = useLanguage();

  const handleLanguageChange = (newLang: Language) => {
    console.log('[LanguageSelector] Mudando idioma para:', newLang);
    setLanguage(newLang);
    
    toast.success(`Idioma alterado para ${availableLanguages.find(l => l.code === newLang)?.name}`, {
      description: 'A interface foi atualizada!',
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
    });
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {availableLanguages.map((lang) => {
        const isSelected = language === lang.code;
        return (
          <button
            key={lang.code}
            onClick={() => handleLanguageChange(lang.code as Language)}
            className={`relative p-6 rounded-xl border-2 transition-all duration-300 group overflow-hidden ${
              isSelected
                ? 'border-cyan-500 bg-gradient-to-br from-cyan-900/40 to-cyan-700/20 shadow-2xl shadow-cyan-500/40 scale-105'
                : 'border-slate-600 bg-gradient-to-br from-slate-800/30 to-slate-700/20 hover:border-cyan-500/60 hover:shadow-lg hover:shadow-cyan-500/20'
            }`}
          >
            {/* Background gradient effect */}
            <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${isSelected ? 'opacity-30' : ''}`}>
              <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 to-transparent" />
            </div>

            <div className="relative z-10 flex items-center justify-between">
              <div className="text-left">
                <p className="text-3xl mb-2">{lang.flag}</p>
                <p
                  className={`text-lg font-bold transition-colors ${
                    isSelected ? 'text-cyan-200' : 'text-white group-hover:text-cyan-300'
                  }`}
                >
                  {lang.name}
                </p>
                <p className="text-xs text-slate-400 mt-2 font-semibold uppercase tracking-widest">
                  {lang.code}
                </p>
              </div>
              {isSelected && (
                <div className="flex flex-col items-center">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 to-cyan-600 flex items-center justify-center shadow-lg animate-pulse">
                    <span className="text-white text-lg font-bold">✓</span>
                  </div>
                  <span className="text-xs text-cyan-300 font-bold mt-2">Ativo</span>
                </div>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
```

---

### 3. Integração em App.tsx

**Localização:** `src/App.tsx`

```typescript
import { LanguageProvider } from "@/hooks/use-language";

const App = () => (
  <ErrorBoundary>
    <LanguageProvider>  {/* ← Provider envolvendo toda a app */}
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <LicenseProvider>
            <ConnectionStatusProvider>
              <Toaster />
              <Sonner />
              <BrowserRouter>
                <AppContent />
              </BrowserRouter>
            </ConnectionStatusProvider>
          </LicenseProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </LanguageProvider>
  </ErrorBoundary>
);

export default App;
```

---

### 4. Integração em Settings.tsx

**Localização:** `src/pages/Settings.tsx` (Aba de Idioma)

```typescript
import { LanguageSelector } from '@/components/LanguageSelector';
import { useLanguage } from '@/hooks/use-language';

export default function Settings() {
  const { language, availableLanguages } = useLanguage();
  
  // ... resto do componente
  
  return (
    <>
      {/* Language Tab */}
      <TabsContent value="language" className="space-y-6">
        <div className="glass-card p-6 lg:p-8 rounded-xl border border-slate-700 ...">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8 pb-6 border-b border-slate-700">
            <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-cyan-600 to-cyan-700 ...">
              <Globe className="w-7 h-7 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white">Idioma e Localização</h2>
              <p className="text-sm text-slate-400">
                Escolha o idioma da plataforma e toda a interface será atualizada
              </p>
            </div>
          </div>

          <div className="space-y-8">
            {/* Auto-detect Toggle */}
            <div className="p-4 md:p-6 bg-gradient-to-br from-cyan-900/20 to-cyan-700/10 ...">
              {/* ... toggle código ... */}
            </div>

            {/* Language Selection */}
            <div>
              <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                <span className="text-2xl">🌐</span>
                Selecione seu Idioma
              </h3>
              <LanguageSelector />  {/* ← Componente de seleção */}
            </div>

            {/* Current Language Preview */}
            <div className="p-6 bg-gradient-to-br from-indigo-900/30 to-purple-900/20 ...">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-indigo-600 to-purple-600 ...">
                  <span className="text-2xl">
                    {availableLanguages.find(l => l.code === language)?.flag}
                  </span>
                </div>
                <div className="flex-1">
                  <p className="text-xs text-indigo-300 uppercase ...">Idioma Atual</p>
                  <p className="text-2xl font-bold text-white mb-2">
                    {availableLanguages.find(l => l.code === language)?.name}
                  </p>
                  <p className="text-sm text-slate-300">
                    Código: <code className="...">{language.toUpperCase()}</code>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </TabsContent>
    </>
  );
}
```

---

## 📋 Fluxo de Execução - Passo a Passo

### Quando app carrega:

1. `App.tsx` renderiza com `<LanguageProvider>`
2. Provider inicializa em `use-language.tsx`:
   - Verifica `localStorage.getItem('language')`
   - Se não existe, verifica `use-system-language`
   - Se nada, usa 'pt' como padrão
3. `document.documentElement.lang` é definido
4. Provider passa contexto para toda a árvore de componentes

### Quando usuário clica em um idioma:

1. `LanguageSelector` dispara `handleLanguageChange(newLang)`
2. Chama `setLanguage(newLang)` do contexto
3. Em `use-language.tsx`:
   - `setLanguageState(newLang)` atualiza estado
   - `localStorage.setItem('language', newLang)` persiste
   - `dispatchEvent('languageChanged')` notifica listeners
4. Todos os componentes que usam `useLanguage()` recebem novo `language`
5. Função `t()` retorna tradução do novo idioma
6. Componentes re-renderizam com novo `t(key)` values
7. Toast mostra confirmação

---

## 🧪 Exemplos de Uso Real

### Exemplo 1: Dashboard.tsx

```typescript
import { useLanguage } from '@/hooks/use-language';

export default function Dashboard() {
  const { t, language } = useLanguage();
  
  return (
    <div>
      <h1>{t('dashboard.title')}</h1>
      <p>{t('dashboard.welcome')}</p>
      
      {language === 'pt' && (
        <p>Bem-vindo ao dashboard em português!</p>
      )}
    </div>
  );
}
```

### Exemplo 2: Button Component

```typescript
import { useLanguage } from '@/hooks/use-language';

export function SubmitButton() {
  const { t } = useLanguage();
  
  return (
    <button type="submit">
      {t('common.save')}  {/* Muda: Salvar → Save → Guardar → Enregistrer */}
    </button>
  );
}
```

### Exemplo 3: Toast Messages

```typescript
import { useLanguage } from '@/hooks/use-language';
import { toast } from 'sonner';

export function handleDelete() {
  const { t } = useLanguage();
  
  try {
    // delete logic
    toast.success(t('messages.deleted_success'));
  } catch (error) {
    toast.error(t('messages.deleted_error'));
  }
}
```

---

## 📦 Arquivos JSON de Tradução

**Localização:** `src/lib/i18n/`

### Estrutura (all 4 files similar):

```json
{
  "common": {
    "save": "Salvar",
    "cancel": "Cancelar",
    "loading": "Carregando...",
    "error": "Erro",
    "success": "Sucesso"
  },
  "navigation": {
    "dashboard": "Dashboard",
    "settings": "Configurações",
    "profile": "Perfil"
  },
  "settings": {
    "language": {
      "title": "Idioma e Localização",
      "auto_detect": "Auto-detectar Idioma",
      "selected": "Idioma Selecionado"
    },
    "profile": {
      "title": "Informações Pessoais",
      "name": "Nome Completo"
    }
  }
}
```

---

## ✅ Verificação Final

Para confirmar que tudo está funcionando:

```bash
# 1. Verificar imports
grep -r "useLanguage" src/

# 2. Verificar Provider em App
grep "LanguageProvider" src/App.tsx

# 3. Verificar JSON files
ls -la src/lib/i18n/*.json

# 4. Verificar uso em componentes
grep -r "t(" src/ | head -20
```

---

## 🎯 Status Atual

✅ **Sistema Completo e Funcional**

- ✅ Hook criado e testado
- ✅ Provider envolvendo App
- ✅ 4 idiomas implementados (PT, EN, ES, FR)
- ✅ Selector UI criado
- ✅ Integrado em Settings
- ✅ localStorage funcionando
- ✅ Auto-detecção funcionando
- ✅ Toast de confirmação
- ✅ Type-safe
- ✅ Documentação completa

---

**Última atualização:** 19/02/2026  
**Versão:** 1.0  
**Status:** ✅ Pronto para Produção
