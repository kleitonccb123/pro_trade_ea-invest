/**
 * PageContainer — wrapper padrão de página
 *
 * Substitui `container mx-auto px-4` ad-hoc.
 * Max-width 1600px respeitando o sidebar, padding 4pt consistente.
 *
 * Uso:
 *   <PageContainer>
 *     <DashboardGrid />
 *   </PageContainer>
 */
import React from 'react';
import { cn } from '@/lib/utils';

interface PageContainerProps extends React.PropsWithChildren {
  /** Classe extra (ex: override de padding) */
  className?: string;
  /**
   * 'default' → max-w-[1600px] px-6 py-6  (padrão dashboard)
   * 'narrow'  → max-w-[960px]  px-6 py-8  (formulários, settings)
   * 'full'    → w-full px-4               (tabelas wide)
   */
  width?: 'default' | 'narrow' | 'full';
}

const widthMap: Record<NonNullable<PageContainerProps['width']>, string> = {
  default: 'max-w-[1600px] mx-auto px-6 py-6',
  narrow:  'max-w-[960px]  mx-auto px-6 py-8',
  full:    'w-full px-4 py-6',
};

export function PageContainer({ children, className, width = 'default' }: PageContainerProps) {
  return (
    <div className={cn(widthMap[width], className)}>
      {children}
    </div>
  );
}
