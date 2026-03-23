/**
 * MetricCardSkeleton — estado de loading do MetricCard
 * Usa subtle-pulse definido em index.css (overrides Tailwind default)
 */
import React from 'react';

export function MetricCardSkeleton() {
  return (
    <div className="bg-surface-raised border border-edge-subtle rounded-lg p-6 animate-pulse">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <div className="h-3 bg-surface-active rounded w-24" />
        <div className="h-4 w-4 bg-surface-active rounded" />
      </div>
      {/* Value */}
      <div className="h-9 bg-surface-active rounded w-36 mb-2" />
      {/* Delta */}
      <div className="h-3 bg-surface-active rounded w-20" />
    </div>
  );
}

/**
 * TableRowSkeleton — linha de tabela em loading
 */
export function TableRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-4 py-3 animate-pulse border-b border-edge-subtle last:border-0">
      <div className="h-3 bg-surface-active rounded w-24 flex-shrink-0" />
      <div className="h-3 bg-surface-active rounded w-16 flex-shrink-0" />
      <div className="h-3 bg-surface-active rounded flex-1" />
      <div className="h-3 bg-surface-active rounded w-20 flex-shrink-0" />
      <div className="h-3 bg-surface-active rounded w-16 flex-shrink-0" />
    </div>
  );
}

/**
 * TableSkeleton — tabela completa em loading
 */
export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="rounded-lg border border-edge-subtle overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-4 px-4 py-3 bg-surface-hover border-b border-edge-subtle animate-pulse">
        <div className="h-3 bg-surface-active rounded w-20 flex-shrink-0" />
        <div className="h-3 bg-surface-active rounded w-16 flex-shrink-0" />
        <div className="h-3 bg-surface-active rounded flex-1" />
        <div className="h-3 bg-surface-active rounded w-24 flex-shrink-0" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <TableRowSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * ChartSkeleton — área de gráfico em loading com shimmer
 */
export function ChartSkeleton({ height = 400 }: { height?: number }) {
  return (
    <div
      className="bg-surface-raised border border-edge-subtle rounded-lg overflow-hidden animate-shimmer"
      style={{ height }}
    />
  );
}

/**
 * DashboardKPISkeleton — linha de 4 KPIs em loading
 */
export function DashboardKPISkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <MetricCardSkeleton key={i} />
      ))}
    </div>
  );
}
