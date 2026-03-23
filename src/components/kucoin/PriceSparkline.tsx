import React, { useMemo } from 'react';

type PriceSparklineProps = {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  positive?: boolean;
};

function getPathD(points: { x: number; y: number }[]) {
  if (!points.length) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;

  // Smooth path using quadratic bezier through midpoints
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const cur = points[i];
    const cx = (prev.x + cur.x) / 2;
    const cy = (prev.y + cur.y) / 2;
    d += ` Q ${prev.x} ${prev.y} ${cx} ${cy}`;
  }
  // final segment to last point
  const last = points[points.length - 1];
  d += ` T ${last.x} ${last.y}`;
  return d;
}

export default function PriceSparkline({ data, width = 100, height = 28, stroke = '#23C882', positive }: PriceSparklineProps) {
  const padding = 2;

  const { pathD, fillD, strokeColor } = useMemo(() => {
    if (!data || data.length === 0) return { pathD: '', fillD: '', strokeColor: stroke };

    const vals = data.slice(-30);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;

    const points = vals.map((v, i) => {
      const x = padding + (i / Math.max(1, vals.length - 1)) * (width - padding * 2);
      const y = padding + (1 - (v - min) / range) * (height - padding * 2);
      return { x, y };
    });

    const d = getPathD(points);

    // create fill path (closing to bottom)
    const first = points[0];
    const last = points[points.length - 1];
    const fillD = `${d} L ${last.x} ${height - padding} L ${first.x} ${height - padding} Z`;

    const strokeColor = stroke || (positive ? '#10B981' : '#EF4444');

    return { pathD: d, fillD, strokeColor };
  }, [data, width, height, stroke, positive]);

  const gradId = useMemo(() => `g${Math.random().toString(36).slice(2, 9)}`, []);

  return (
    <svg width={width} height={height} className="sparkline" aria-hidden>
      <defs>
        <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity={0.35} />
          <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
        </linearGradient>
      </defs>

      {pathD && (
        <>
          <path d={fillD} fill={`url(#${gradId})`} />
          <path d={pathD} fill="none" stroke={strokeColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}
    </svg>
  );
}
