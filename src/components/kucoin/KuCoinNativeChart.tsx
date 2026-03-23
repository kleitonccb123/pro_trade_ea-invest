import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ISeriesApi, IChartApi, UTCTimestamp } from 'lightweight-charts';
import { useDashboardWS } from '@/hooks/use-dashboard-ws';
import { apiGet } from '@/services/apiClient';

const TIMEFRAMES = [
  { label: '1m', value: '1min', seconds: 60 },
  { label: '5m', value: '5min', seconds: 300 },
  { label: '15m', value: '15min', seconds: 900 },
  { label: '1h', value: '1hour', seconds: 3600 },
  { label: '4h', value: '4hour', seconds: 14400 },
  { label: '1D', value: '1day', seconds: 86400 },
];

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface KuCoinMessage {
  type: string;
  topic?: string;
  data?: any;
}

export default function KuCoinNativeChart({ symbol = 'BTC/USDT' }: { symbol?: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const maSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const markersRef = useRef<any[]>([]);
  const [connectionStatus, setConnectionStatus] = useState('🔴 Desconectado');
  const [timeframe, setTimeframe] = useState('1min');
  const wsRef = useRef<WebSocket | null>(null);
  const lastCandleRef = useRef<Candle | null>(null);
  const messageIdRef = useRef<number>(0);
  const priceHistoryRef = useRef<number[]>([]);
  const reconnectAttemptsRef = useRef<number>(0);
  const [showRSI, setShowRSI] = useState(false);
  const [showBB, setShowBB] = useState(false);
  const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiContainerRef = useRef<HTMLDivElement | null>(null);
  const candlesDataRef = useRef<Candle[]>([]);

  const { lastMessage } = useDashboardWS();

  // Convert symbol format: "BTC/USDT" → "BTC-USDT"
  const kucoinSymbol = symbol.replace('/', '-');

  // Compute and set MA20 from a candle array
  const computeMA20 = useCallback((candles: Candle[]) => {
    if (!maSeriesRef.current || candles.length < 20) return;
    const maData: { time: UTCTimestamp; value: number }[] = [];
    for (let i = 19; i < candles.length; i++) {
      const slice = candles.slice(i - 19, i + 1);
      const avg = slice.reduce((s, c) => s + c.close, 0) / 20;
      maData.push({ time: candles[i].time as UTCTimestamp, value: avg });
    }
    maSeriesRef.current.setData(maData);
  }, []);

  // Compute Bollinger Bands (period=20, multiplier=2)
  const computeBB = useCallback((candles: Candle[]) => {
    if (!bbUpperRef.current || !bbLowerRef.current || candles.length < 20) return;
    const upper: { time: UTCTimestamp; value: number }[] = [];
    const lower: { time: UTCTimestamp; value: number }[] = [];
    for (let i = 19; i < candles.length; i++) {
      const slice = candles.slice(i - 19, i + 1).map((c) => c.close);
      const sma = slice.reduce((a, b) => a + b, 0) / 20;
      const variance = slice.reduce((a, b) => a + (b - sma) ** 2, 0) / 20;
      const std = Math.sqrt(variance);
      upper.push({ time: candles[i].time as UTCTimestamp, value: sma + 2 * std });
      lower.push({ time: candles[i].time as UTCTimestamp, value: sma - 2 * std });
    }
    bbUpperRef.current.setData(upper);
    bbLowerRef.current.setData(lower);
  }, []);

  // Compute RSI (period=14)
  const computeRSI = useCallback((candles: Candle[]) => {
    if (!rsiSeriesRef.current || candles.length < 16) return;
    const period = 14;
    const rsiData: { time: UTCTimestamp; value: number }[] = [];
    let avgGain = 0;
    let avgLoss = 0;
    for (let i = 1; i <= period; i++) {
      const change = candles[i].close - candles[i - 1].close;
      if (change > 0) avgGain += change;
      else avgLoss += Math.abs(change);
    }
    avgGain /= period;
    avgLoss /= period;
    const rs0 = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsiData.push({ time: candles[period].time as UTCTimestamp, value: 100 - 100 / (1 + rs0) });
    for (let i = period + 1; i < candles.length; i++) {
      const change = candles[i].close - candles[i - 1].close;
      avgGain = (avgGain * (period - 1) + (change > 0 ? change : 0)) / period;
      avgLoss = (avgLoss * (period - 1) + (change < 0 ? Math.abs(change) : 0)) / period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      rsiData.push({ time: candles[i].time as UTCTimestamp, value: 100 - 100 / (1 + rs) });
    }
    rsiSeriesRef.current.setData(rsiData);
  }, []);

  // ─── Create chart (once) ──────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 600,
      layout: { background: { type: 'solid', color: '#0B0E11' }, textColor: '#E0E6ED' },
      grid: {
        vertLines: { color: '#1a2332', style: 1, visible: true },
        horzLines: { color: '#1a2332', style: 1, visible: true },
      },
      rightPriceScale: {
        scaleMargins: { top: 0.2, bottom: 0.2 },
        borderColor: '#2a3f5f',
        textColor: '#8FFF00',
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#2a3f5f',
        textColor: '#8FFF00',
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00FF41',
      downColor: '#FF1493',
      wickUpColor: '#00FF41',
      wickDownColor: '#FF1493',
      borderVisible: false,
    });

    const maSeries = chart.addLineSeries({
      color: '#FFD700',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      title: 'MA20',
    });

    const bbUpper = chart.addLineSeries({
      color: 'rgba(33, 150, 243, 0.5)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      title: 'BB+',
      visible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const bbLower = chart.addLineSeries({
      color: 'rgba(33, 150, 243, 0.5)',
      lineWidth: 1,
      crosshairMarkerVisible: false,
      title: 'BB\u2212',
      visible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    maSeriesRef.current = maSeries;
    bbUpperRef.current = bbUpper;
    bbLowerRef.current = bbLower;

    const handleResize = () => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // ─── RSI chart (separate pane below main chart) ───────────
  useEffect(() => {
    if (!showRSI || !rsiContainerRef.current) {
      if (rsiChartRef.current) {
        rsiChartRef.current.remove();
        rsiChartRef.current = null;
        rsiSeriesRef.current = null;
      }
      return;
    }

    const rsiChart = createChart(rsiContainerRef.current, {
      width: rsiContainerRef.current.clientWidth,
      height: 150,
      layout: { background: { type: 'solid' as const, color: '#0B0E11' }, textColor: '#E0E6ED' },
      grid: {
        vertLines: { color: '#1a2332', style: 1, visible: true },
        horzLines: { color: '#1a2332', style: 1, visible: true },
      },
      rightPriceScale: {
        scaleMargins: { top: 0.1, bottom: 0.1 },
        borderColor: '#2a3f5f',
        textColor: '#E040FB',
      },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#2a3f5f' },
    });

    const rsiLine = rsiChart.addLineSeries({
      color: '#E040FB',
      lineWidth: 2,
      title: 'RSI(14)',
      priceLineVisible: false,
    });

    rsiLine.createPriceLine({ price: 70, color: 'rgba(255,82,82,0.5)', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });
    rsiLine.createPriceLine({ price: 30, color: 'rgba(76,175,80,0.5)', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '' });

    rsiChartRef.current = rsiChart;
    rsiSeriesRef.current = rsiLine;

    // Sync visible range with main chart
    if (chartRef.current) {
      let syncing = false;
      const mainTS = chartRef.current.timeScale();
      const rsiTS = rsiChart.timeScale();
      mainTS.subscribeVisibleLogicalRangeChange((range) => {
        if (syncing || !range) return;
        syncing = true;
        rsiTS.setVisibleLogicalRange(range);
        syncing = false;
      });
      rsiTS.subscribeVisibleLogicalRangeChange((range) => {
        if (syncing || !range) return;
        syncing = true;
        mainTS.setVisibleLogicalRange(range);
        syncing = false;
      });
    }

    computeRSI(candlesDataRef.current);

    const handleResize = () => {
      if (rsiContainerRef.current && rsiChartRef.current) {
        rsiChartRef.current.applyOptions({ width: rsiContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      rsiChart.remove();
      rsiChartRef.current = null;
      rsiSeriesRef.current = null;
    };
  }, [showRSI, computeRSI]);

  // ─── BB visibility toggle ─────────────────────────────────
  useEffect(() => {
    bbUpperRef.current?.applyOptions({ visible: showBB });
    bbLowerRef.current?.applyOptions({ visible: showBB });
    if (showBB) computeBB(candlesDataRef.current);
  }, [showBB, computeBB]);

  // ─── Load historical klines from backend on mount / timeframe change ───
  useEffect(() => {
    let cancelled = false;

    const loadHistory = async () => {
      try {
        const resp = await apiGet<{ data: any[] }>(
          `/api/trading/market-data/${kucoinSymbol}?interval=${timeframe}&limit=200`
        );
        if (cancelled) return;

        const candles: Candle[] = (resp.data || []).map((k: any) => ({
          time: k.timestamp as UTCTimestamp,
          open: k.open,
          high: k.high,
          low: k.low,
          close: k.close,
        }));

        if (candles.length > 0 && candleSeriesRef.current) {
          candleSeriesRef.current.setData(candles);
          lastCandleRef.current = candles[candles.length - 1];
          priceHistoryRef.current = candles.map((c) => c.close);
          computeMA20(candles);
          candlesDataRef.current = candles;
          computeBB(candles);
          computeRSI(candles);
        }

        // Clear markers on timeframe change
        markersRef.current = [];
        candleSeriesRef.current?.setMarkers([]);
      } catch (e) {
        console.warn('Failed to load historical klines:', e);
      }
    };

    loadHistory();
    return () => { cancelled = true; };
  }, [kucoinSymbol, timeframe, computeMA20, computeBB, computeRSI]);

  // ─── WebSocket: KuCoin native candle channel ──────────────
  useEffect(() => {
    let cancelled = false;

    const connectKuCoinWS = async () => {
      try {
        // Get WS token from backend (proxied from KuCoin bullet-public)
        const tokenData = await apiGet<{
          token: string;
          instanceServers: { endpoint: string; pingInterval: number }[];
        }>('/api/trading/kucoin/ws-token');

        if (cancelled) return;

        const server = tokenData.instanceServers?.[0];
        if (!server || !tokenData.token) {
          console.warn('No WS token / server from KuCoin');
          setConnectionStatus('🔴 Sem Token');
          return;
        }

        const connectId = `chart_${Date.now()}`;
        const wsUrl = `${server.endpoint}?token=${tokenData.token}&connectId=${connectId}`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (cancelled) { ws.close(); return; }
          console.log('✅ Conectado ao WebSocket KuCoin');
          setConnectionStatus('🟢 KuCoin Conectado');
          reconnectAttemptsRef.current = 0;

          // Subscribe to native candle channel for current pair + timeframe
          const candleMsg = {
            id: ++messageIdRef.current,
            type: 'subscribe',
            topic: `/market/candles:${kucoinSymbol}_${timeframe}`,
            privateChannel: false,
            response: true,
          };
          ws.send(JSON.stringify(candleMsg));

          // Ping to keep connection alive
          const pingMs = server.pingInterval || 30000;
          const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ id: ++messageIdRef.current, type: 'ping' }));
            }
          }, pingMs);

          ws.addEventListener('close', () => clearInterval(pingInterval));
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data) as KuCoinMessage;

            // Handle native candle updates
            if (msg.topic?.startsWith('/market/candles:')) {
              const candles = msg.data?.candles;
              if (!candles || !Array.isArray(candles)) return;

              // KuCoin candle array: [time, open, close, high, low, volume, turnover]
              const candleData: Candle = {
                time: parseInt(candles[0]),
                open: parseFloat(candles[1]),
                close: parseFloat(candles[2]),
                high: parseFloat(candles[3]),
                low: parseFloat(candles[4]),
              };

              if (candleSeriesRef.current) {
                candleSeriesRef.current.update(candleData);
                lastCandleRef.current = candleData;

                // Update MA20 incrementally
                priceHistoryRef.current.push(candleData.close);
                if (priceHistoryRef.current.length > 220) {
                  priceHistoryRef.current = priceHistoryRef.current.slice(-200);
                }

                if (priceHistoryRef.current.length >= 20 && maSeriesRef.current) {
                  const last20 = priceHistoryRef.current.slice(-20);
                  const avg = last20.reduce((a, b) => a + b, 0) / 20;
                  maSeriesRef.current.update({
                    time: candleData.time as UTCTimestamp,
                    value: avg,
                  });
                }

                // Update stored candle data for BB / RSI
                const cdRef = candlesDataRef.current;
                const lastIdx = cdRef.length > 0 ? cdRef.length - 1 : -1;
                if (lastIdx >= 0 && cdRef[lastIdx].time === candleData.time) {
                  cdRef[lastIdx] = candleData;
                } else {
                  cdRef.push(candleData);
                  if (cdRef.length > 220) candlesDataRef.current = cdRef.slice(-200);
                }
                computeBB(candlesDataRef.current);
                computeRSI(candlesDataRef.current);
              }
            }
          } catch (e) {
            console.error('Erro ao processar mensagem KuCoin:', e);
          }
        };

        ws.onerror = () => {
          setConnectionStatus('🔴 Erro KuCoin');
        };

        ws.onclose = () => {
          if (cancelled) return;
          setConnectionStatus('🟡 Reconectando...');
          // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
          const attempts = reconnectAttemptsRef.current++;
          const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
          setTimeout(() => { if (!cancelled) connectKuCoinWS(); }, delay);
        };

        wsRef.current = ws;
      } catch (error) {
        console.error('Erro ao conectar WebSocket:', error);
        setConnectionStatus('🔴 Falha');
        // Retry with backoff
        const attempts = reconnectAttemptsRef.current++;
        const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
        setTimeout(() => { if (!cancelled) connectKuCoinWS(); }, delay);
      }
    };

    connectKuCoinWS();

    return () => {
      cancelled = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [kucoinSymbol, timeframe]);

  // ─── Bot trade markers from dashboard WS ──────────────────
  useEffect(() => {
    if (!lastMessage || !candleSeriesRef.current) return;

    try {
      const msg = lastMessage as any;
      if (msg.type === 'trade_executed' || msg.type === 'TRADE_EXECUTED') {
        const d = msg.data || msg;
        const price = Number(d.price);
        const amount = Number(d.amount || d.qty || 0);
        const side = d.side || d.direction || 'buy';

        // Align trade time to current timeframe period
        const tfConfig = TIMEFRAMES.find((t) => t.value === timeframe);
        const periodSec = tfConfig?.seconds || 60;
        const time = Math.floor(Date.now() / 1000 / periodSec) * periodSec;

        const marker = {
          time,
          position: side === 'buy' ? 'belowBar' : 'aboveBar',
          color: side === 'buy' ? '#00FF41' : '#FF006E',
          shape: side === 'buy' ? 'arrowUp' : 'arrowDown',
          text: `🤖 ${side.toUpperCase()} ${amount.toFixed(4)} @ $${price}`,
        };

        markersRef.current = [...markersRef.current, marker].slice(-100);
        candleSeriesRef.current?.setMarkers(
          markersRef.current.sort((a: any, b: any) => a.time - b.time)
        );
      }
    } catch (e) {
      console.error('Erro ao processar trade do robô:', e);
    }
  }, [lastMessage, timeframe]);

  return (
    <div className="glass-card p-4 lg:p-6 h-full">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-foreground">{symbol} — Tempo Real</h3>
          <span className="text-xs font-medium bg-emerald-500/20 px-2.5 py-1 rounded-full border border-emerald-500/30 text-emerald-300">
            {connectionStatus}
          </span>
        </div>
        <div className="flex gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.value}
              onClick={() => setTimeframe(tf.value)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                timeframe === tf.value
                  ? 'bg-green-500 text-black font-bold'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {tf.label}
            </button>
          ))}
          <span className="mx-1 border-l border-gray-700" />
          <button
            onClick={() => setShowBB((v) => !v)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              showBB ? 'bg-blue-500 text-white font-bold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            BB
          </button>
          <button
            onClick={() => setShowRSI((v) => !v)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              showRSI ? 'bg-purple-500 text-white font-bold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            RSI
          </button>
        </div>
      </div>
      <div ref={containerRef} className="w-full" style={{ height: 600 }} />
      <div ref={rsiContainerRef} className="w-full mt-1" style={{ height: 150, display: showRSI ? 'block' : 'none' }} />
    </div>
  );
}
