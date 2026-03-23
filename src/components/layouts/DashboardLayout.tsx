/**
 * DashboardLayout — page-level wrapper para páginas de dashboard
 *
 * Combina PageContainer + cabeçalho opcional de página.
 * Não substitui AppLayout — é usado DENTRO do <Outlet /> do AppLayout.
 *
 * Uso:
 *   export default function Dashboard() {
 *     return (
 *       <DashboardLayout title="Dashboard" description="Visão geral da conta">
 *         <DashboardGrid.Root>...</DashboardGrid.Root>
 *       </DashboardLayout>
 *     );
 *   }
 */
import React from 'react';
import { cn } from '@/lib/utils';
import { PageContainer } from './PageContainer';

interface DashboardLayoutProps extends React.PropsWithChildren {
  /** Título da página (H1) — se fornecido, renderiza PageHeader interno */
  title?: string;
  /** Subtítulo/descrição abaixo do título */
  description?: string;
  /** Elemento à direita do header (botão de ação, badge de status etc.) */
  headerAction?: React.ReactNode;
  /** Override de largura repassado para PageContainer */
  width?: 'default' | 'narrow' | 'full';
  className?: string;
}

export function DashboardLayout({
  children,
  title,
  description,
  headerAction,
  width = 'default',
  className,
}: DashboardLayoutProps) {
  return (
    <PageContainer width={width} className={className}>
      {/* Cabeçalho de página — opcional */}
      {title && (
        <div className="flex items-start justify-between mb-6">
          <div className="min-w-0">
            <h1 className="font-display font-bold text-3xl text-content-primary tracking-tight leading-tight">
              {title}
            </h1>
            {description && (
              <p className="mt-1 text-sm text-content-secondary font-sans">{description}</p>
            )}
          </div>
          {headerAction && (
            <div className="flex-shrink-0 ml-6 mt-1">{headerAction}</div>
          )}
        </div>
      )}

      {/* Conteúdo da página */}
      {children}
    </PageContainer>
  );
}
