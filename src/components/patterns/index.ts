/**
 * Patterns — re-export central
 * Molecules: combinam primitivos, sem fetch, sem estado global.
 */
export { MetricCard }                   from './MetricCard';
export type { MetricCardProps }         from './MetricCard';
export {
  MetricCardSkeleton,
  TableRowSkeleton,
  TableSkeleton,
  ChartSkeleton,
  DashboardKPISkeleton,
}                                       from './Skeleton';
export { EmptyState, ErrorState }       from './EmptyState';
