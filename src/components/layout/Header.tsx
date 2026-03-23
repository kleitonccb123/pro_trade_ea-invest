import { Search, User, LogOut, Menu, Settings, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { NotificationCenter } from '@/components/NotificationCenter';
import { LanguageSwitcher } from './LanguageSwitcher';
import { PlanBadge } from './PlanBadge';
import { useAuthStore } from '@/context/AuthContext';
import { usePlanStore } from '@/stores/plan-store';
import { useLanguage } from '@/hooks/use-language';

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const navigate = useNavigate();
  const { logout, user } = useAuthStore();
  const { t } = useLanguage();
  const [searchFocused, setSearchFocused] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const { planDisplay, isActive, daysRemaining, plan } = usePlanStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isPaidPlan = plan !== 'free' && plan !== 'starter';

  return (
    <header className="h-14 bg-surface-base border-b border-edge-subtle flex items-center justify-between px-4 sm:px-6 lg:px-8 sticky top-0 z-40" style={{ borderBottomColor: '#252932' }}>

      {/* LEFT — Mobile menu + Search */}
      <div className="flex items-center gap-3 flex-1">
        {/* Mobile hamburger */}
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden h-9 w-9 rounded-lg bg-surface-hover hover:bg-surface-active text-content-secondary hover:text-content-primary transition-colors border border-edge-subtle flex-shrink-0"
          onClick={onMenuClick}
        >
          <Menu className="w-5 h-5" />
        </Button>

        {/* Mobile logo */}
        <div className="lg:hidden font-display font-bold text-lg tracking-tight flex-shrink-0">
          <span className="text-brand-primary">CT</span>
          <span className="text-content-primary">HUB</span>
        </div>

        {/* Search Bar */}
        <div className="hidden sm:flex flex-1 max-w-sm relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-content-muted pointer-events-none" />
          <input
            type="text"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder={t('common.searchPlaceholder')}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            className={cn(
              'w-full h-9 pl-10 pr-4 rounded-lg text-sm text-content-primary placeholder:text-content-muted focus:outline-none transition-all duration-150',
              'bg-surface-hover border border-edge-default',
              searchFocused
                ? 'border-brand-primary ring-2 ring-brand-primary/15 bg-surface-overlay'
                : 'hover:border-edge-strong'
            )}
          />
        </div>
      </div>

      {/* RIGHT — Language + Notifications + User */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Language Switcher with flags */}
        <div className="hidden sm:flex items-center">
          <LanguageSwitcher />
        </div>

        {/* Divider */}
        <div className="hidden sm:block w-px h-6 bg-edge-subtle" />

        {/* Notifications */}
        <NotificationCenter />

        {/* Plan Badge */}
        <div className="hidden sm:flex items-center">
          <PlanBadge />
        </div>

        {/* Divider */}
        <div className="hidden sm:block w-px h-6 bg-edge-subtle" />

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="flex items-center gap-2 px-3 h-9 rounded-lg border border-edge-default bg-surface-hover hover:bg-surface-active text-content-primary transition-all duration-150"
            >
              <div className="w-7 h-7 rounded-full bg-brand-primary/15 border border-brand-primary/30 flex items-center justify-center flex-shrink-0">
                <User className="w-3.5 h-3.5 text-brand-primary" />
              </div>
              <span className="hidden sm:block text-sm font-medium max-w-[120px] truncate">
                {user?.name ?? user?.email ?? t('header.account')}
              </span>
              <ChevronDown className="w-3.5 h-3.5 hidden sm:block text-content-muted" />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent
            align="end"
            className="w-56 bg-surface-overlay border-edge-default rounded-xl shadow-xl mt-2"
          >
            <DropdownMenuLabel className="text-xs text-content-muted font-medium uppercase tracking-widest px-3 py-2.5">
              {t('header.myAccount')}
            </DropdownMenuLabel>

            {/* Plan info row */}
            {isPaidPlan && (
              <>
                <div
                  className="mx-2 mb-1.5 px-3 py-2 rounded-lg bg-surface-hover border border-edge-subtle flex items-center justify-between cursor-pointer hover:brightness-110 transition-all"
                  onClick={() => navigate('/billing')}
                >
                  <span className="text-xs text-content-muted">Plano</span>
                  <div className="flex items-center gap-1.5">
                    <span className="relative flex h-1.5 w-1.5">
                      {isActive && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />}
                      <span className={cn('relative inline-flex rounded-full h-1.5 w-1.5', isActive ? 'bg-emerald-400' : 'bg-red-400')} />
                    </span>
                    <span className="text-xs font-bold text-content-primary">{planDisplay}</span>
                    {daysRemaining !== null && (
                      <span className="text-xs text-content-muted">· {daysRemaining}d</span>
                    )}
                  </div>
                </div>
                <DropdownMenuSeparator className="bg-edge-subtle" />
              </>
            )}

            {!isPaidPlan && <DropdownMenuSeparator className="bg-edge-subtle" />}

            <DropdownMenuItem
              onClick={() => navigate('/settings')}
              className="text-sm text-content-body hover:text-content-primary hover:bg-surface-hover rounded-md mx-1 cursor-pointer transition-colors duration-150 px-3 py-2"
            >
              <User className="w-4 h-4 mr-2.5 text-content-muted" />
              {t('header.profile')}
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={() => navigate('/settings')}
              className="text-sm text-content-body hover:text-content-primary hover:bg-surface-hover rounded-md mx-1 cursor-pointer transition-colors duration-150 px-3 py-2"
            >
              <Settings className="w-4 h-4 mr-2.5 text-content-muted" />
              {t('header.settings')}
            </DropdownMenuItem>

            <DropdownMenuSeparator className="bg-edge-subtle my-1" />

            <DropdownMenuItem
              onClick={handleLogout}
              className="text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-md mx-1 mb-1 cursor-pointer transition-colors duration-150 px-3 py-2"
            >
              <LogOut className="w-4 h-4 mr-2.5" />
              {t('header.logout')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
