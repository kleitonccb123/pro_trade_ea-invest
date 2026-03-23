/**
 * Hook para consumir o stream de P&L de um bot via WebSocket.
 * Reconecta automaticamente em caso de queda.
 */
import { useEffect, useState, useRef } from 'react';
import { authService } from '@/services/authService';

export interface BotPnL {
  state: string;
  total_pnl: number;
  total_pnl_percent: number;
  total_trades: number;
  winning_trades: number;
  win_rate: number;
  current_position: any | null;
  last_trade: any | null;
  started_at: string | null;
}

const WS_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace('http://', 'ws://')
  .replace('https://', 'wss://');

export function useBotPnL(botId: string | null) {
  const [pnl, setPnL] = useState<BotPnL | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!botId) return;

    const connect = () => {
      const token = authService.getAccessToken();
      const url = `${WS_BASE}/bots/${botId}/pnl/stream?token=${token}`;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'pnl_update' && msg.data) {
            setPnL(msg.data);
          }
        } catch {}
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconectar após 5 segundos
        retryRef.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      wsRef.current?.close();
      if (retryRef.current) clearTimeout(retryRef.current);
    };
  }, [botId]);

  return { pnl, connected };
}
