import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Bot, 
  TrendingUp, 
  Settings,
  Wallet,
  X,
  PlayCircle,
  Code,
  Crown
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from '@/components/ui/sheet';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard' },
  { icon: Bot, label: 'Robôs', path: '/robots' },
  { icon: Code, label: 'Estratégia', path: '/strategy' },
  { icon: TrendingUp, label: 'Projeções', path: '/projections' },
  { icon: Crown, label: 'Licenças', path: '/licenses' },
  { icon: PlayCircle, label: 'Vídeo Aulas', path: '/video-aulas' },
  { icon: Settings, label: 'Configurações', path: '/settings' },
];

interface MobileSidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileSidebar({ open, onOpenChange }: MobileSidebarProps) {
  const location = useLocation();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-72 bg-sidebar border-r border-sidebar-border p-0">
        <SheetHeader className="h-14 flex flex-row items-center justify-between px-4 border-b border-sidebar-border">
          <Link to="/dashboard" className="flex items-center gap-3" onClick={() => onOpenChange(false)}>
            <div className="w-8 h-8 rounded-md bg-brand-primary flex items-center justify-center">
              <Wallet className="w-4 h-4 text-surface-base" />
            </div>
            <SheetTitle className="font-bold text-base text-content-primary">TradeHub</SheetTitle>
          </Link>
        </SheetHeader>

        <nav className="flex-1 py-6 px-3 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => onOpenChange(false)}
                className={cn(
                  "sidebar-link",
                  isActive && "active"
                )}
              >
                <item.icon className={cn("w-5 h-5 flex-shrink-0", isActive && "text-primary")} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="flex items-center gap-2 px-1">
            <div className="w-1.5 h-1.5 rounded-full bg-brand-primary" />
            <span className="text-xs text-content-muted">Sistema ativo</span>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
