import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { MobileSidebar } from './MobileSidebar';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/context/AuthContext';
import { usePlanStore } from '@/stores/plan-store';

export function AppLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isHydrated = useAuthStore((s) => s.isHydrated);
  const fetchPlan = usePlanStore((s) => s.fetch);
  const clearPlan = usePlanStore((s) => s.clear);

  // Sincroniza o plano com o estado de autenticação
  useEffect(() => {
    if (!isHydrated) return;
    if (isAuthenticated) {
      fetchPlan();
    } else {
      clearPlan();
    }
  }, [isAuthenticated, isHydrated, fetchPlan, clearPlan]);

  return (
    <div className="min-h-screen bg-surface-base flex" style={{ backgroundColor: '#0B0E11' }}>
      {/* Desktop Sidebar */}
      <div className="hidden lg:block fixed left-0 top-0 bottom-0 z-40">
        <Sidebar
          compact
          collapsed={sidebarCollapsed}
          onCollapsedChange={setSidebarCollapsed}
        />
      </div>

      {/* Mobile Sidebar */}
      <MobileSidebar open={mobileMenuOpen} onOpenChange={setMobileMenuOpen} />

      {/* Main content — margin tracks sidebar width */}
      <div
        className={cn(
          'flex-1 min-h-screen flex flex-col transition-all duration-300 relative z-10',
          sidebarCollapsed ? 'lg:ml-[68px]' : 'lg:ml-60'
        )}
      >
        <Header onMenuClick={() => setMobileMenuOpen(true)} />
        <main className="flex-1 bg-surface-base p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
