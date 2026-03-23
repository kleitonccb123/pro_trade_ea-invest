/**
 * DashboardGrid — sistema de 12 colunas para composição de dashboard
 *
 * Fornece sub-layouts semânticos:
 *   DashboardGrid.Root    → grid de 12 cols com gap padrão
 *   DashboardGrid.KPIRow  → faixa de 4 KPIs col-span-12
 *   DashboardGrid.Main    → área principal (8 cols em xl)
 *   DashboardGrid.Aside   → painel lateral (4 cols em xl)
 *   DashboardGrid.Full    → linha full-width (12 cols)
 *
 * Uso:
 *   <DashboardGrid.Root>
 *     <DashboardGrid.KPIRow>
 *       <MetricCard ... /> × 4
 *     </DashboardGrid.KPIRow>
 *
 *     <DashboardGrid.Main>
 *       <EquityChart />
 *     </DashboardGrid.Main>
 *     <DashboardGrid.Aside>
 *       <ActiveRobotsPanel />
 *       <RecentTradesPanel />
 *     </DashboardGrid.Aside>
 *
 *     <DashboardGrid.Full>
 *       <TradeHistoryTable />
 *     </DashboardGrid.Full>
 *   </DashboardGrid.Root>
 */
import React from 'react';
import { cn } from '@/lib/utils';

type DivProps = React.HTMLAttributes<HTMLDivElement>;

// ─────────────────────────────────────────────────────────────────────────────
// Root — grid pai de 12 colunas
// ─────────────────────────────────────────────────────────────────────────────
function Root({ children, className, ...props }: DivProps) {
  return (
    <div
      className={cn('grid grid-cols-12 gap-4 3xl:gap-6', className)}
      {...props}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// KPIRow — linha de KPIs: 2 cols em sm, 4 cols em lg+
// Sempre ocupa as 12 colunas do pai
// ─────────────────────────────────────────────────────────────────────────────
function KPIRow({ children, className, ...props }: DivProps) {
  return (
    <div
      className={cn('col-span-12 grid grid-cols-2 lg:grid-cols-4 gap-4', className)}
      {...props}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main — área de gráfico principal (12 cols → 8 cols em xl+)
// ─────────────────────────────────────────────────────────────────────────────
function Main({ children, className, ...props }: DivProps) {
  return (
    <div
      className={cn('col-span-12 xl:col-span-8', className)}
      {...props}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Aside — painel lateral (12 cols → 4 cols em xl+)
// ─────────────────────────────────────────────────────────────────────────────
function Aside({ children, className, ...props }: DivProps) {
  return (
    <div
      className={cn('col-span-12 xl:col-span-4 flex flex-col gap-4', className)}
      {...props}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Full — linha full-width (12 colunas sempre)
// ─────────────────────────────────────────────────────────────────────────────
function Full({ children, className, ...props }: DivProps) {
  return (
    <div
      className={cn('col-span-12', className)}
      {...props}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Half — duas colunas de 6 (abre em md+)
// ─────────────────────────────────────────────────────────────────────────────
function Half({ children, className, ...props }: DivProps) {
  return (
    <div
      className={cn('col-span-12 md:col-span-6', className)}
      {...props}
    >
      {children}
    </div>
  );
}

export const DashboardGrid = { Root, KPIRow, Main, Aside, Full, Half };
