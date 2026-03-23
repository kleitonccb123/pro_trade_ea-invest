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
    const value = getNestedValue(translations[language], key);
    // If key not found in current language (returned as-is), fall back to Portuguese
    if (value === key && language !== 'pt') {
      const ptValue = getNestedValue(translations['pt'], key);
      if (ptValue !== key) return ptValue;
    }
    return value;
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
