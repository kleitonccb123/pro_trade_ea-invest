/**
 * P3-07: Backend Status Banner
 * Polls /api/health every 30 seconds and shows a banner when the backend is offline.
 */
import { useEffect, useState, useRef, useCallback } from 'react';
import { AlertTriangle, WifiOff, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '@/config/constants';

type Status = 'unknown' | 'online' | 'offline' | 'degraded';

export function BackendStatusBanner() {
  const [status, setStatus] = useState<Status>('unknown');
  const [checking, setChecking] = useState(false);
  const statusRef = useRef<Status>('unknown');
  // Use a ref for the guard so it works correctly across stale closures and
  // React StrictMode double-invocations (no stale closure bug with state).
  const checkingRef = useRef(false);

  const checkHealth = useCallback(async () => {
    if (checkingRef.current) return;
    checkingRef.current = true;
    setChecking(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/health`, {
        signal: AbortSignal.timeout(8000),
        cache: 'no-store',
        headers: { Connection: 'close' },
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        const statusField: string = data?.status ?? 'ok';
        const newStatus: Status = statusField === 'degraded' ? 'degraded' : 'online';
        statusRef.current = newStatus;
        setStatus(newStatus);
      } else {
        statusRef.current = 'offline';
        setStatus('offline');
      }
    } catch {
      statusRef.current = 'offline';
      setStatus('offline');
    } finally {
      checkingRef.current = false;
      setChecking(false);
    }
  }, []); // stable reference — no stale closure on 'checking'

  useEffect(() => {
    checkHealth();

    let timer: ReturnType<typeof setTimeout>;

    const scheduleNext = async () => {
      await checkHealth();
      const delay = statusRef.current === 'offline' || statusRef.current === 'unknown'
        ? 5_000
        : 30_000;
      timer = setTimeout(scheduleNext, delay);
    };

    // Kick off the first scheduled cycle after an initial delay
    const delay = statusRef.current === 'offline' || statusRef.current === 'unknown'
      ? 5_000
      : 30_000;
    timer = setTimeout(scheduleNext, delay);

    // Recheck immediately when tab becomes visible again
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') checkHealth();
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [checkHealth]);

  if (status === 'online' || status === 'unknown') return null;

  const isDegraded = status === 'degraded';

  return (
    <div
      role="alert"
      className={`fixed top-0 left-0 right-0 z-50 flex items-center justify-between gap-3 px-4 py-2 text-sm font-medium ${
        isDegraded
          ? 'bg-yellow-500/90 text-yellow-950'
          : 'bg-destructive/90 text-destructive-foreground'
      } backdrop-blur-sm`}
    >
      <div className="flex items-center gap-2">
        {isDegraded ? (
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        ) : (
          <WifiOff className="w-4 h-4 flex-shrink-0" />
        )}
        <span>
          {isDegraded
            ? 'Servidor em modo degradado — algumas funcionalidades podem estar indisponíveis.'
            : 'Servidor offline — verifique sua conexão ou tente novamente em instantes.'}
        </span>
      </div>
      <button
        onClick={checkHealth}
        disabled={checking}
        className="flex items-center gap-1 rounded px-2 py-0.5 hover:bg-black/10 disabled:opacity-50 transition-colors"
        aria-label="Verificar conexão novamente"
      >
        <RefreshCw className={`w-3 h-3 ${checking ? 'animate-spin' : ''}`} />
        <span className="hidden sm:inline">Tentar novamente</span>
      </button>
    </div>
  );
}
