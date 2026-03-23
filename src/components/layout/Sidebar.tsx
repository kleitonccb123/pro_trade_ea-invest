import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Bot, 
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  PlayCircle,
  Share2,
  Code,
  Wallet,
  Crown,
  BarChart3,
  Circle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { useLanguage } from '@/hooks/use-language';

const navSections = [
  {
    labelKey: 'nav.main',
    label: 'PRINCIPAL',
    items: [
      { icon: LayoutDashboard, labelKey: 'sidebar.dashboard', path: '/dashboard' },
      { icon: BarChart3,       labelKey: 'sidebar.performance', path: '/performance' },
    ],
  },
  {
    labelKey: 'nav.trading',
    label: 'TRADING',
    items: [
      { icon: Bot,      labelKey: 'sidebar.strategies',   path: '/robots' },
      { icon: Code,     labelKey: 'sidebar.myStrategies', path: '/strategies' },
      { icon: Wallet,   labelKey: 'sidebar.wallet',       path: '/ea-monitor' },
    ],
  },
  {
    labelKey: 'nav.account',
    label: 'CONTA',
    items: [
      { icon: Crown,      labelKey: 'sidebar.licenses',    path: '/licenses' },
      { icon: Share2,     labelKey: 'sidebar.affiliates',  path: '/affiliate' },
      { icon: PlayCircle, labelKey: 'sidebar.videoLessons',path: '/video-aulas' },
      { icon: Settings,   labelKey: 'sidebar.settings',    path: '/settings' },
    ],
  },
];

interface SidebarProps {
  compact?: boolean;
  collapsed?: boolean;
  onCollapsedChange?: (v: boolean) => void;
}

export function Sidebar({ compact, collapsed: controlledCollapsed, onCollapsedChange }: SidebarProps) {
  const location = useLocation();
  const { t } = useLanguage();
  const [internalCollapsed, setInternalCollapsed] = useState(compact || false);

  const collapsed = controlledCollapsed !== undefined ? controlledCollapsed : internalCollapsed;
  const setCollapsed = (v: boolean) => {
    setInternalCollapsed(v);
    onCollapsedChange?.(v);
  };

  return (
    <aside
      className={cn(
        "h-screen flex flex-col transition-all duration-300 z-40 relative",
        collapsed ? "w-[68px]" : "w-60"
      )}
      style={{
        background: 'linear-gradient(180deg, #0D1117 0%, #0B0E13 60%, #090C10 100%)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '4px 0 32px rgba(0,0,0,0.5), inset -1px 0 0 rgba(255,255,255,0.03)',
      }}
    >
      {/* Top edge accent */}
      <div className="absolute top-0 left-0 right-0 h-px" style={{ background: 'linear-gradient(90deg, transparent 0%, rgba(35,200,130,0.4) 50%, transparent 100%)' }} />

      {/* Header */}
      <div
        className="h-16 flex items-center justify-between flex-shrink-0"
        style={{
          padding: collapsed ? '0 14px' : '0 16px',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
          background: 'linear-gradient(180deg, rgba(35,200,130,0.04) 0%, transparent 100%)',
        }}
      >
        <Link to="/dashboard" className="flex items-center gap-3 group min-w-0">
          <div
            className="flex items-center justify-center flex-shrink-0 rounded-lg"
            style={{
              width: 34, height: 34,
              background: 'linear-gradient(135deg, #23C882 0%, #1aaa6e 100%)',
              boxShadow: '0 0 12px rgba(35,200,130,0.35), 0 2px 8px rgba(0,0,0,0.4)',
            }}
          >
            <Zap className="w-4 h-4 text-[#0B0E11]" strokeWidth={2.5} />
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-sm text-white tracking-wide leading-tight">TradeHub</span>
              <span className="text-[10px] text-[#23C882] font-medium tracking-widest leading-tight opacity-70">PRO</span>
            </div>
          )}
        </Link>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex-shrink-0 rounded-md transition-all duration-150 p-1"
          style={{ color: 'rgba(255,255,255,0.25)' }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.6)'; (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.25)'; (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3" style={{ scrollbarWidth: 'none' }}>
        {navSections.map((section, si) => (
          <div key={section.label} className={si > 0 ? 'mt-1' : ''}>
            {/* Section label */}
            {!collapsed && (
              <div
                className="flex items-center gap-2 mb-1"
                style={{ padding: '6px 14px 4px' }}
              >
                <span
                  className="text-[10px] font-semibold tracking-widest"
                  style={{ color: 'rgba(255,255,255,0.2)' }}
                >
                  {section.label}
                </span>
                <div className="flex-1 h-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
              </div>
            )}
            {collapsed && si > 0 && (
              <div className="my-2 mx-3 h-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
            )}

            {/* Items */}
            <div className="space-y-0.5 px-2">
              {section.items.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    title={collapsed ? t(item.labelKey) : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-lg transition-all duration-150 relative group",
                      collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
                    )}
                    style={isActive ? {
                      background: 'linear-gradient(90deg, rgba(35,200,130,0.14) 0%, rgba(35,200,130,0.04) 100%)',
                      boxShadow: 'inset 0 0 0 1px rgba(35,200,130,0.12)',
                    } : {}}
                    onMouseEnter={e => {
                      if (!isActive) (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
                    }}
                    onMouseLeave={e => {
                      if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent';
                    }}
                  >
                    {/* Active left bar */}
                    {isActive && (
                      <span
                        className="absolute left-0 top-1/2 -translate-y-1/2 rounded-r-full"
                        style={{
                          width: 3, height: 20,
                          background: 'linear-gradient(180deg, #23C882 0%, #1aaa6e 100%)',
                          boxShadow: '0 0 8px rgba(35,200,130,0.6)',
                        }}
                      />
                    )}

                    {/* Icon */}
                    <div
                      className="flex items-center justify-center flex-shrink-0 rounded-md transition-all duration-150"
                      style={{
                        width: 28, height: 28,
                        background: isActive ? 'rgba(35,200,130,0.15)' : 'transparent',
                        color: isActive ? '#23C882' : 'rgba(255,255,255,0.38)',
                      }}
                    >
                      <item.icon className="w-4 h-4" strokeWidth={isActive ? 2.2 : 1.8} />
                    </div>

                    {/* Label */}
                    {!collapsed && (
                      <span
                        className="text-sm font-medium truncate transition-colors duration-150"
                        style={{
                          color: isActive ? '#e8f9f3' : 'rgba(255,255,255,0.5)',
                          letterSpacing: '0.01em',
                        }}
                      >
                        {t(item.labelKey)}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div
        className="flex-shrink-0 p-3"
        style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
      >
        {!collapsed ? (
          <div
            className="flex items-center gap-2.5 rounded-lg px-3 py-2.5"
            style={{ background: 'rgba(35,200,130,0.05)', border: '1px solid rgba(35,200,130,0.1)' }}
          >
            <div className="relative flex-shrink-0">
              <Circle className="w-2 h-2 fill-[#23C882] text-[#23C882]" />
              <span
                className="absolute inset-0 rounded-full animate-ping"
                style={{ background: 'rgba(35,200,130,0.5)', animationDuration: '2.5s' }}
              />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium" style={{ color: '#23C882' }}>{t('sidebar.systemActive')}</p>
              <p className="text-[10px] truncate" style={{ color: 'rgba(255,255,255,0.3)' }}>{t('sidebar.allWorking')}</p>
            </div>
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="relative">
              <Circle className="w-2 h-2 fill-[#23C882] text-[#23C882]" />
              <span
                className="absolute inset-0 rounded-full animate-ping"
                style={{ background: 'rgba(35,200,130,0.5)', animationDuration: '2.5s' }}
              />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

