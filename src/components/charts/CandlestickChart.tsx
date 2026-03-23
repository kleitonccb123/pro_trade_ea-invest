import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, CandlestickData } from 'lightweight-charts';

export function CandlestickChart({ symbol = 'BTC/USDT' }: { symbol?: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 360,
      layout: { backgroundColor: '#0F1419', textColor: '#d1d5db' },
      rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { timeVisible: true },
    });

    const series = chart.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    });

    // seed placeholder data
    const now = Date.now();
    const seed: CandlestickData[] = [];
    for (let i = 60; i >= 0; i--) {
      const t = Math.floor((now - i * 60 * 1000) / 1000);
      const base = 40000 + i * 10;
      seed.push({ time: t, open: base, high: base + 50, low: base - 50, close: base + 5 });
    }
    series.setData(seed);

    chartRef.current = chart;

    const handleResize = () => chart.applyOptions({ width: containerRef.current?.clientWidth || 600 });
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  return (
    <div className="glass-card p-4 lg:p-6 h-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">{symbol} — Candles</h3>
      </div>
      <div ref={containerRef} style={{ width: '100%', height: 360 }} />
    </div>
  );
}

export default CandlestickChart;
