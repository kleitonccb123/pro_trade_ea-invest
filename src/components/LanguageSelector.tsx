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
                ? 'border-emerald-500 bg-gradient-to-br from-emerald-900/40 to-emerald-700/20 shadow-2xl shadow-emerald-500/40 scale-105'
                : 'border-slate-600 bg-gradient-to-br from-slate-800/30 to-slate-700/20 hover:border-emerald-500/60 hover:shadow-lg hover:shadow-emerald-500/20'
            }`}
          >
            {/* Background gradient effect */}
            <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${isSelected ? 'opacity-30' : ''}`}>
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 to-transparent" />
            </div>

            <div className="relative z-10 flex items-center justify-between">
              <div className="text-left">
                <p className="text-3xl mb-2">{lang.flag}</p>
                <p
                  className={`text-lg font-bold transition-colors ${
                    isSelected ? 'text-emerald-200' : 'text-white group-hover:text-emerald-300'
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
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg animate-pulse">
                    <span className="text-white text-lg font-bold">✓</span>
                  </div>
                  <span className="text-xs text-emerald-300 font-bold mt-2">Ativo</span>
                </div>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
