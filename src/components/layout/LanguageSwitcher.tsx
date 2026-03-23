import { useLanguage } from '@/hooks/use-language';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const LANGUAGES = [
  { code: 'pt' as const, flag: '🇧🇷', name: 'Português' },
  { code: 'en' as const, flag: '🇺🇸', name: 'English' },
  { code: 'es' as const, flag: '🇪🇸', name: 'Español' },
  { code: 'fr' as const, flag: '🇫🇷', name: 'Français' },
];

export function LanguageSwitcher() {
  const { language, setLanguage } = useLanguage();

  return (
    <div className="flex items-center gap-1">
      {LANGUAGES.map((lang) => (
        <Tooltip key={lang.code}>
          <TooltipTrigger asChild>
            <button
              onClick={() => setLanguage(lang.code)}
              className={cn(
                'text-lg leading-none w-8 h-8 flex items-center justify-center rounded-md transition-all duration-150',
                language === lang.code
                  ? 'bg-brand-primary/15 scale-110'
                  : 'opacity-50 hover:opacity-100 hover:scale-110 hover:bg-surface-hover'
              )}
              aria-label={lang.name}
            >
              {lang.flag}
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="text-xs">
            {lang.name}
          </TooltipContent>
        </Tooltip>
      ))}
    </div>
  );
}
