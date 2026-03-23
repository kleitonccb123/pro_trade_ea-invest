import { useEffect, useState, useCallback, ReactNode } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Activity,
  Target,
  Shield,
  Clock,
  RefreshCw,
  Trophy,
  ChevronDown,
  Bot,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/context/AuthContext";
import { apiCall } from "@/services/apiClient";

/* â”€â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

interface BotInfo {
  id: string;
  name: string;
  pair?: string;
  symbol?: string;
  status?: string;
  strategy?: string;
}

interface AdvancedMetrics {
  total_pnl: number;
  total_return_pct: number;
  num_trades: number;
  win_rate: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number;
  worst_trade: number;
  avg_trade_duration_hours: number;
  win_rate_7d: number;
  win_rate_30d: number;
  win_rate_90d: number;
  equity_curve: number[];
  trading_days: number;
  // Legacy optional fields used in old dead code:
  calmar_ratio?: number;
  max_drawdown_duration_days?: number;
  annualized_return_pct?: number;
  max_drawdown_abs?: number;
}

/* â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

// ── Design constants ─────────────────────────────────────────────────────────
const G = "#23C882";
const CARD_BG = { background: "#161A1E", border: "1px solid #222831" };
const INPUT_STYLE = {
  background: "#0D1117",
  border: "1px solid #2D3748",
  color: "#E2E8F0",
  padding: "6px 10px",
  borderRadius: 6,
  fontSize: 13,
};

const fmt = (v: number, d = 2) =>
  v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });

/** Blue-white-red for correlation (âˆ’1 to 1). */


/* â”€â”€â”€ Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

const PerformanceDashboard = () => {
  const { accessToken: token } = useAuthStore();

  const [bots, setBots] = useState<BotInfo[]>([]);
  const [selectedBot, setSelectedBot] = useState<BotInfo | null>(null);
  const [metrics, setMetrics] = useState<AdvancedMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [botsLoading, setBotsLoading] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const fetchBots = useCallback(async () => {
    if (!token) return;
    setBotsLoading(true);
    try {
      const res = await apiCall("/bots");
      if (res.ok) {
        const data: BotInfo[] = await res.json();
        setBots(data);
        if (data.length > 0) setSelectedBot((prev) => prev ?? data[0]);
      }
    } catch {
      // silent
    } finally {
      setBotsLoading(false);
    }
  }, [token]);

  const fetchMetrics = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedBot?.id) params.set("bot_id", selectedBot.id);
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      const qs = params.toString();
      const res = await apiCall(`/analytics/advanced-metrics${qs ? `?${qs}` : ""}`);
      if (res.ok) setMetrics(await res.json());
      else setMetrics(null);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [token, selectedBot, startDate, endDate]);

  useEffect(() => { fetchBots(); }, [fetchBots]);
  useEffect(() => { if (token) fetchMetrics(); }, [fetchMetrics]);

  const equityData = (metrics?.equity_curve ?? []).map((v, i) => ({ idx: i + 1, equity: v }));
  const winPeriods = metrics
    ? [
        { period: "7d", rate: metrics.win_rate_7d },
        { period: "30d", rate: metrics.win_rate_30d },
        { period: "90d", rate: metrics.win_rate_90d },
        { period: "Total", rate: metrics.win_rate },
      ]
    : [];

  return (
    <div style={{ minHeight: "100vh", background: "#0B0E11", padding: "24px 28px" }} className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <BarChart3 className="h-7 w-7" style={{ color: G }} />
            Análise de Performance
          </h1>
          <p className="text-gray-400 text-sm mt-0.5">
            Métricas de risco, P&amp;L e resultados dos robôs
          </p>
        </div>
        <Button
          onClick={() => { fetchBots(); fetchMetrics(); }}
          disabled={loading}
          style={{ background: G, color: "#0B0E11", fontWeight: 600 }}
          className="h-9 px-4"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Atualizar
        </Button>
      </div>

      {/* Bot Selector + Filters */}
      <Card style={CARD_BG}>
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1.5 block uppercase tracking-wider">
                Analisar Robô
              </label>
              <div className="relative">
                <Button
                  variant="outline"
                  onClick={() => setDropdownOpen((o) => !o)}
                  disabled={botsLoading}
                  style={{
                    background: "#0D1117",
                    border: "1px solid #2D3748",
                    minWidth: 210,
                    justifyContent: "space-between",
                    color: "#E2E8F0",
                  }}
                >
                  <span className="flex items-center gap-2">
                    <Bot className="h-4 w-4" style={{ color: G }} />
                    {botsLoading
                      ? "Carregando…"
                      : selectedBot
                        ? selectedBot.name
                        : "Selecionar Robô"}
                  </span>
                  <ChevronDown className="h-4 w-4 text-gray-500 ml-2" />
                </Button>
                {dropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0"
                      style={{ zIndex: 40 }}
                      onClick={() => setDropdownOpen(false)}
                    />
                    <div
                      style={{
                        position: "absolute",
                        top: "calc(100% + 4px)",
                        left: 0,
                        background: "#0D1117",
                        border: "1px solid #2D3748",
                        borderRadius: 8,
                        zIndex: 50,
                        minWidth: 240,
                        boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
                      }}
                    >
                      {bots.length === 0 ? (
                        <div className="px-4 py-3 text-gray-400 text-sm">
                          Nenhum robô encontrado
                        </div>
                      ) : (
                        bots.map((bot, i) => (
                          <div
                            key={bot.id}
                            onClick={() => { setSelectedBot(bot); setDropdownOpen(false); }}
                            className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-gray-800"
                            style={{
                              borderBottom: i < bots.length - 1 ? "1px solid #1A2030" : "none",
                              borderRadius: i === 0 ? "8px 8px 0 0" : i === bots.length - 1 ? "0 0 8px 8px" : 0,
                            }}
                          >
                            <div
                              style={{
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                background: bot.status === "running" ? G : "#4B5563",
                                boxShadow: bot.status === "running" ? `0 0 6px ${G}80` : "none",
                                flexShrink: 0,
                              }}
                            />
                            <div>
                              <div className="text-white text-sm font-medium">{bot.name}</div>
                              <div className="text-gray-500 text-xs">{bot.pair ?? bot.symbol ?? "—"}</div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-500 mb-1.5 block uppercase tracking-wider">Início</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={INPUT_STYLE} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1.5 block uppercase tracking-wider">Fim</label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={INPUT_STYLE} />
            </div>

            <Button
              onClick={fetchMetrics}
              disabled={loading}
              style={{ background: G, color: "#0B0E11", fontWeight: 600 }}
              className="h-9 px-4"
            >
              Aplicar
            </Button>
            {(startDate || endDate) && (
              <Button
                variant="ghost"
                onClick={() => { setStartDate(""); setEndDate(""); }}
                className="h-9 text-gray-400 hover:text-white"
              >
                Limpar filtros
              </Button>
            )}
          </div>

          {selectedBot && (
            <div className="mt-3 flex items-center gap-3">
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: selectedBot.status === "running" ? G : "#4B5563",
                  boxShadow: selectedBot.status === "running" ? `0 0 8px ${G}80` : "none",
                }}
              />
              <span className="text-gray-300 text-sm">
                <span className="text-white font-medium">{selectedBot.name}</span>
                {selectedBot.strategy && (
                  <span className="text-gray-500 ml-2">{selectedBot.strategy}</span>
                )}
                {(selectedBot.pair ?? selectedBot.symbol) && (
                  <span className="text-gray-500 ml-2">
                    · {selectedBot.pair ?? selectedBot.symbol}
                  </span>
                )}
              </span>
              <span
                style={{
                  background:
                    selectedBot.status === "running"
                      ? "rgba(35,200,130,0.12)"
                      : "rgba(75,85,99,0.2)",
                  color: selectedBot.status === "running" ? G : "#9CA3AF",
                  padding: "1px 8px",
                  borderRadius: 20,
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.05em",
                }}
              >
                {selectedBot.status === "running" ? "ATIVO" : "PARADO"}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KPICard
          label="P&L Total"
          value={metrics ? `$${fmt(metrics.total_pnl)}` : "—"}
          sub={metrics ? `${fmt(metrics.total_return_pct)}%` : undefined}
          icon={<TrendingUp className="h-5 w-5" style={{ color: G }} />}
          accent={metrics ? (metrics.total_pnl >= 0 ? G : "#EF4444") : undefined}
        />
        <KPICard
          label="Win Rate"
          value={metrics ? `${fmt(metrics.win_rate)}%` : "—"}
          icon={<Trophy className="h-5 w-5" style={{ color: G }} />}
          accent={metrics ? (metrics.win_rate >= 50 ? G : "#F59E0B") : undefined}
        />
        <KPICard
          label="Operações"
          value={metrics ? String(metrics.num_trades) : "—"}
          icon={<BarChart3 className="h-5 w-5 text-gray-500" />}
        />
        <KPICard
          label="Max Drawdown"
          value={metrics ? `${fmt(metrics.max_drawdown_pct)}%` : "—"}
          icon={<TrendingDown className="h-5 w-5 text-red-400" />}
          accent="#EF4444"
        />
        <KPICard
          label="Profit Factor"
          value={metrics ? fmt(metrics.profit_factor, 2) : "—"}
          icon={<Target className="h-5 w-5 text-yellow-400" />}
          accent={metrics ? (metrics.profit_factor >= 1.5 ? G : "#F59E0B") : undefined}
        />
        <KPICard
          label="Sharpe Ratio"
          value={metrics ? fmt(metrics.sharpe_ratio, 2) : "—"}
          icon={<Shield className="h-5 w-5 text-blue-400" />}
          accent={metrics ? (metrics.sharpe_ratio >= 1 ? G : "#F59E0B") : undefined}
        />
      </div>

      {/* P&L Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <PnLCard label="Melhor Operação" value={metrics ? `$${fmt(metrics.best_trade)}` : "—"} positive />
        <PnLCard label="Pior Operação" value={metrics ? `$${fmt(metrics.worst_trade)}` : "—"} positive={false} />
        <PnLCard label="Média de Ganho" value={metrics ? `$${fmt(metrics.avg_win)}` : "—"} positive />
        <PnLCard label="Média de Perda" value={metrics ? `$${fmt(metrics.avg_loss)}` : "—"} positive={false} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card style={CARD_BG}>
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-sm font-semibold flex items-center gap-2">
              <Activity className="h-4 w-4" style={{ color: G }} />
              Curva de Capital
            </CardTitle>
          </CardHeader>
          <CardContent>
            {equityData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={equityData}>
                  <defs>
                    <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={G} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={G} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1A2030" />
                  <XAxis dataKey="idx" tick={{ fill: "#4B5563", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#4B5563", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#0D1117", border: "1px solid #2D3748", color: "#E2E8F0", borderRadius: 6 }}
                    formatter={(v: number) => [`$${fmt(v)}`, "Capital"]}
                  />
                  <Area type="monotone" dataKey="equity" stroke={G} fill="url(#eqGrad)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState icon={<Activity className="h-10 w-10 text-gray-700" />} label="Sem dados de capital" />
            )}
          </CardContent>
        </Card>

        <Card style={CARD_BG}>
          <CardHeader className="pb-2">
            <CardTitle className="text-white text-sm font-semibold flex items-center gap-2">
              <Trophy className="h-4 w-4" style={{ color: G }} />
              Win Rate por Período
            </CardTitle>
          </CardHeader>
          <CardContent>
            {winPeriods.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={winPeriods}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1A2030" />
                  <XAxis dataKey="period" tick={{ fill: "#4B5563", fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: "#4B5563", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#0D1117", border: "1px solid #2D3748", color: "#E2E8F0", borderRadius: 6 }}
                    formatter={(v: number) => [`${fmt(v)}%`, "Win Rate"]}
                  />
                  <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                    {winPeriods.map((e, i) => (
                      <Cell key={i} fill={e.rate >= 50 ? G : "#F59E0B"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState icon={<BarChart3 className="h-10 w-10 text-gray-700" />} label="Sem dados de win rate" />
            )}
          </CardContent>
        </Card>
      </div>

      {metrics && (
        <Card style={CARD_BG}>
          <CardContent className="pt-4 pb-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <InfoItem
                icon={<Clock className="h-4 w-4 text-gray-500" />}
                label="Duração Média"
                value={`${fmt(metrics.avg_trade_duration_hours)}h`}
              />
              <InfoItem
                icon={<Activity className="h-4 w-4 text-gray-500" />}
                label="Sortino Ratio"
                value={fmt(metrics.sortino_ratio, 2)}
              />
              <InfoItem
                icon={<Shield className="h-4 w-4 text-gray-500" />}
                label="Drawdown Abs."
                value={`${fmt(metrics.max_drawdown_pct)}%`}
              />
              <InfoItem
                icon={<TrendingUp className="h-4 w-4" style={{ color: G }} />}
                label="Dias de Trading"
                value={String(metrics.trading_days)}
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
// Legacy type declarations for dead code below (to be removed with dead code cleanup):
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare function useLanguage(): { t: (key: string) => string };
declare const API: string;
type BotComparison = any;
type StrategyMetrics = any;
type HeatmapData = any;
type CorrelationData = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const Filter: any, Layers: any, Grid3x3: any, GitBranch: any, Download: any, Input: any, Tabs: any, TabsList: any, TabsTrigger: any, TabsContent: any;
declare function heatColor(val: number, min: number, max: number): string;
declare function corrColor(val: number): string;
const pctColor = (v: number) => (v >= 0 ? "text-emerald-400" : "text-red-400");

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const PerformanceDashboard_DEL = () => {
  const { accessToken: token } = useAuthStore();
  const { t } = useLanguage();

  const [metrics, setMetrics] = useState<AdvancedMetrics | null>(null);
  const [bots, setBots] = useState<BotComparison[]>([]);
  const [strategies, setStrategies] = useState<StrategyMetrics[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null);
  const [correlation, setCorrelation] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(false);

  // Filters
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [symbol, setSymbol] = useState("");
  const [botId, setBotId] = useState("");
  const [strategy, setStrategy] = useState("");

  const headers = useCallback(
    () => ({
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    }),
    [token],
  );

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      if (symbol) params.set("symbol", symbol);
      if (botId) params.set("bot_id", botId);
      if (strategy) params.set("strategy", strategy);
      const qs = params.toString();
      const pfx = qs ? `?${qs}` : "";

      const dateParams = new URLSearchParams();
      if (startDate) dateParams.set("start_date", startDate);
      if (endDate) dateParams.set("end_date", endDate);
      const dateQs = dateParams.toString();
      const datePfx = dateQs ? `?${dateQs}` : "";

      const [mRes, bRes, sRes, hRes, cRes] = await Promise.all([
        fetch(`${API}/analytics/advanced-metrics${pfx}`, { headers: headers() }),
        fetch(`${API}/analytics/bot-comparison${datePfx}`, { headers: headers() }),
        fetch(`${API}/analytics/by-strategy${pfx}`, { headers: headers() }),
        fetch(`${API}/analytics/heatmap${pfx}`, { headers: headers() }),
        fetch(`${API}/analytics/correlation${datePfx}`, { headers: headers() }),
      ]);

      if (mRes.ok) setMetrics(await mRes.json());
      if (bRes.ok) setBots(await bRes.json());
      if (sRes.ok) setStrategies(await sRes.json());
      if (hRes.ok) setHeatmap(await hRes.json());
      if (cRes.ok) setCorrelation(await cRes.json());
    } catch (err) {
      console.error("Failed to load performance data", err);
    } finally {
      setLoading(false);
    }
  }, [token, headers, startDate, endDate, symbol, botId, strategy]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  /* â”€â”€ Derived chart data â”€â”€ */
  const equityData = (metrics?.equity_curve || []).map((v, i) => ({ idx: i + 1, equity: v }));

  const winRatePeriod = metrics
    ? [
        { period: "7d", rate: metrics.win_rate_7d },
        { period: "30d", rate: metrics.win_rate_30d },
        { period: "90d", rate: metrics.win_rate_90d },
        { period: t("performance.allTime") || "All", rate: metrics.win_rate },
      ]
    : [];

  /* â”€â”€ Render â”€â”€ */
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="h-7 w-7 text-cyan-400" />
            {t("performance.title") || "Performance Dashboard"}
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            {t("performance.subtitle") || "Advanced risk-adjusted metrics & bot comparison"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            disabled={loading}
            className="border-cyan-700 text-cyan-400 hover:bg-cyan-900/30"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            {t("performance.refresh") || "Refresh"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="border-cyan-700 text-cyan-400 hover:bg-cyan-900/30"
            onClick={async () => {
              try {
                const params = new URLSearchParams();
                if (startDate) params.set("start_date", startDate);
                if (endDate) params.set("end_date", endDate);
                if (symbol) params.set("symbol", symbol);
                if (botId) params.set("bot_id", botId);
                const qs = params.toString();
                const response = await apiCall(`/analytics/export/pdf${qs ? `?${qs}` : ""}`);
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `performance-${new Date().toISOString().slice(0, 10)}.pdf`;
                a.click();
                URL.revokeObjectURL(url);
              } catch { /* toast handled by apiCall */ }
            }}
          >
            <Download className="h-4 w-4 mr-2" />
            {t("performance.exportPdf") || "PDF"}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="bg-gray-900/60 border-gray-800">
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex items-center gap-2 text-gray-400">
              <Filter className="h-4 w-4" />
              <span className="text-sm font-medium">{t("performance.filters") || "Filters"}</span>
            </div>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-36 bg-gray-800 border-gray-700 text-gray-200 text-sm"
            />
            <Input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-36 bg-gray-800 border-gray-700 text-gray-200 text-sm"
            />
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder={t("performance.symbolPlaceholder") || "Symbol (BTC-USDT)"}
              className="w-40 bg-gray-800 border-gray-700 text-gray-200 text-sm"
            />
            <Input
              value={botId}
              onChange={(e) => setBotId(e.target.value)}
              placeholder={t("performance.botIdPlaceholder") || "Bot ID"}
              className="w-32 bg-gray-800 border-gray-700 text-gray-200 text-sm"
            />
            <Input
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              placeholder={t("performance.strategyPlaceholder") || "Strategy"}
              className="w-36 bg-gray-800 border-gray-700 text-gray-200 text-sm"
            />
            <Button
              size="sm"
              onClick={fetchData}
              disabled={loading}
              className="bg-cyan-600 hover:bg-cyan-700 text-white"
            >
              {t("performance.apply") || "Apply"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="bg-gray-900/80 border border-gray-800">
          <TabsTrigger value="overview" className="data-[state=active]:bg-cyan-700 data-[state=active]:text-white">
            <Activity className="h-4 w-4 mr-1.5" />
            {t("performance.tabOverview") || "Overview"}
          </TabsTrigger>
          <TabsTrigger value="strategy" className="data-[state=active]:bg-cyan-700 data-[state=active]:text-white">
            <Layers className="h-4 w-4 mr-1.5" />
            {t("performance.tabStrategy") || "Por EstratÃ©gia"}
          </TabsTrigger>
          <TabsTrigger value="heatmap" className="data-[state=active]:bg-cyan-700 data-[state=active]:text-white">
            <Grid3x3 className="h-4 w-4 mr-1.5" />
            {t("performance.tabHeatmap") || "Heatmap"}
          </TabsTrigger>
          <TabsTrigger value="correlation" className="data-[state=active]:bg-cyan-700 data-[state=active]:text-white">
            <GitBranch className="h-4 w-4 mr-1.5" />
            {t("performance.tabCorrelation") || "CorrelaÃ§Ã£o"}
          </TabsTrigger>
        </TabsList>

        {/* â”€â”€ Tab: Overview â”€â”€ */}
        <TabsContent value="overview" className="space-y-6">
          {/* KPI Cards â€” Row 1 */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <KPICard
              label={t("performance.totalPnl") || "Total P&L"}
              value={metrics ? `$${fmt(metrics.total_pnl)}` : "â€”"}
              sub={metrics ? `${fmt(metrics.total_return_pct)}%` : ""}
              icon={<TrendingUp className="h-5 w-5 text-cyan-400" />}
              colorClass={metrics ? pctColor(metrics.total_pnl) : ""}
            />
            <KPICard
              label={t("performance.sharpeRatio") || "Sharpe Ratio"}
              value={metrics ? fmt(metrics.sharpe_ratio, 3) : "â€”"}
              icon={<Shield className="h-5 w-5 text-blue-400" />}
              colorClass={metrics && metrics.sharpe_ratio >= 1 ? "text-emerald-400" : "text-yellow-400"}
            />
            <KPICard
              label={t("performance.sortinoRatio") || "Sortino Ratio"}
              value={metrics ? fmt(metrics.sortino_ratio, 3) : "â€”"}
              icon={<Shield className="h-5 w-5 text-indigo-400" />}
              colorClass={metrics && metrics.sortino_ratio >= 1 ? "text-emerald-400" : "text-yellow-400"}
            />
            <KPICard
              label={t("performance.maxDrawdown") || "Max Drawdown"}
              value={metrics ? `${fmt(metrics.max_drawdown_pct)}%` : "â€”"}
              sub={metrics ? `${metrics.max_drawdown_duration_days}d` : ""}
              icon={<TrendingDown className="h-5 w-5 text-red-400" />}
              colorClass="text-red-400"
            />
            <KPICard
              label={t("performance.profitFactor") || "Profit Factor"}
              value={metrics ? fmt(metrics.profit_factor, 3) : "â€”"}
              icon={<Target className="h-5 w-5 text-amber-400" />}
              colorClass={metrics && metrics.profit_factor >= 1.5 ? "text-emerald-400" : "text-yellow-400"}
            />
            <KPICard
              label={t("performance.calmarRatio") || "Calmar Ratio"}
              value={metrics ? fmt(metrics.calmar_ratio, 3) : "â€”"}
              icon={<Activity className="h-5 w-5 text-purple-400" />}
              colorClass={metrics && metrics.calmar_ratio >= 1 ? "text-emerald-400" : "text-yellow-400"}
            />
          </div>

          {/* KPI Cards â€” Row 2 */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <KPICard
              label={t("performance.winRate") || "Win Rate"}
              value={metrics ? `${fmt(metrics.win_rate)}%` : "â€”"}
              icon={<Trophy className="h-5 w-5 text-emerald-400" />}
              colorClass={metrics && metrics.win_rate >= 50 ? "text-emerald-400" : "text-yellow-400"}
            />
            <KPICard
              label={t("performance.numTrades") || "Trades"}
              value={metrics ? String(metrics.num_trades) : "â€”"}
              icon={<BarChart3 className="h-5 w-5 text-gray-400" />}
              colorClass="text-white"
            />
            <KPICard
              label={t("performance.avgWin") || "Avg Win"}
              value={metrics ? `$${fmt(metrics.avg_win)}` : "â€”"}
              icon={<TrendingUp className="h-5 w-5 text-emerald-400" />}
              colorClass="text-emerald-400"
            />
            <KPICard
              label={t("performance.avgLoss") || "Avg Loss"}
              value={metrics ? `$${fmt(metrics.avg_loss)}` : "â€”"}
              icon={<TrendingDown className="h-5 w-5 text-red-400" />}
              colorClass="text-red-400"
            />
            <KPICard
              label={t("performance.bestTrade") || "Best Trade"}
              value={metrics ? `$${fmt(metrics.best_trade)}` : "â€”"}
              colorClass="text-emerald-400"
            />
            <KPICard
              label={t("performance.avgDuration") || "Avg Duration"}
              value={metrics ? `${fmt(metrics.avg_trade_duration_hours)}h` : "â€”"}
              icon={<Clock className="h-5 w-5 text-gray-400" />}
              colorClass="text-white"
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="bg-gray-900/60 border-gray-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-white text-base">
                  {t("performance.equityCurve") || "Equity Curve"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {equityData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={equityData}>
                      <defs>
                        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="idx" tick={{ fill: "#9ca3af", fontSize: 11 }} />
                      <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }}
                        labelStyle={{ color: "#9ca3af" }}
                      />
                      <Area type="monotone" dataKey="equity" stroke="#06b6d4" fill="url(#eqGrad)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-gray-500 text-sm py-16 text-center">
                    {t("performance.noData") || "No trades yet"}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card className="bg-gray-900/60 border-gray-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-white text-base">
                  {t("performance.winRateByPeriod") || "Win Rate by Period"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {winRatePeriod.length > 0 && metrics ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={winRatePeriod}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="period" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                      <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} domain={[0, 100]} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }}
                        formatter={(v: number) => [`${fmt(v)}%`, "Win Rate"]}
                      />
                      <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
                        {winRatePeriod.map((entry, idx) => (
                          <Cell key={idx} fill={entry.rate >= 50 ? "#10b981" : "#f59e0b"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-gray-500 text-sm py-16 text-center">
                    {t("performance.noData") || "No trades yet"}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Bot Comparison Table */}
          {bots.length > 0 && (
            <Card className="bg-gray-900/60 border-gray-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-amber-400" />
                  {t("performance.botComparison") || "Bot Comparison"}
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase">
                      <th className="py-2 px-3">Bot</th>
                      <th className="py-2 px-3">{t("performance.symbolCol") || "Symbol"}</th>
                      <th className="py-2 px-3 text-right">P&L</th>
                      <th className="py-2 px-3 text-right">{t("performance.returnCol") || "Return"}</th>
                      <th className="py-2 px-3 text-right">{t("performance.tradesCol") || "Trades"}</th>
                      <th className="py-2 px-3 text-right">{t("performance.winRateCol") || "Win %"}</th>
                      <th className="py-2 px-3 text-right">Sharpe</th>
                      <th className="py-2 px-3 text-right">Sortino</th>
                      <th className="py-2 px-3 text-right">MDD %</th>
                      <th className="py-2 px-3 text-right">PF</th>
                      <th className="py-2 px-3 text-right">Calmar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bots.map((b) => (
                      <tr key={b.bot_id} className="border-b border-gray-800 hover:bg-gray-800/40">
                        <td className="py-2 px-3 text-cyan-400 font-mono text-xs">{b.bot_id}</td>
                        <td className="py-2 px-3 text-gray-300">{b.symbol || "—"}</td>
                        <td className={`py-2 px-3 text-right font-medium ${pctColor(b.total_pnl)}`}>${fmt(b.total_pnl)}</td>
                        <td className={`py-2 px-3 text-right ${pctColor(b.total_return_pct)}`}>{fmt(b.total_return_pct)}%</td>
                        <td className="py-2 px-3 text-right text-gray-300">{b.num_trades}</td>
                        <td className={`py-2 px-3 text-right ${b.win_rate >= 50 ? "text-emerald-400" : "text-yellow-400"}`}>{fmt(b.win_rate)}%</td>
                        <td className="py-2 px-3 text-right text-gray-300">{fmt(b.sharpe_ratio, 3)}</td>
                        <td className="py-2 px-3 text-right text-gray-300">{fmt(b.sortino_ratio, 3)}</td>
                        <td className="py-2 px-3 text-right text-red-400">{fmt(b.max_drawdown_pct)}%</td>
                        <td className="py-2 px-3 text-right text-gray-300">{fmt(b.profit_factor, 3)}</td>
                        <td className="py-2 px-3 text-right text-gray-300">{fmt(b.calmar_ratio, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* â”€â”€ Tab: Por EstratÃ©gia â”€â”€ */}
        <TabsContent value="strategy">
          <Card className="bg-gray-900/60 border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-white text-base flex items-center gap-2">
                <Layers className="h-5 w-5 text-cyan-400" />
                {t("performance.strategyMetrics") || "MÃ©tricas por EstratÃ©gia"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {strategies.length === 0 ? (
                <p className="text-gray-500 text-sm py-10 text-center">
                  {t("performance.noStrategyData") || "Nenhuma estratÃ©gia encontrada nos trades filtrados"}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead>
                      <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase">
                        <th className="py-2 px-3">{t("performance.strategyCol") || "EstratÃ©gia"}</th>
                        <th className="py-2 px-3">{t("performance.botsCol") || "Bots"}</th>
                        <th className="py-2 px-3 text-right">P&L</th>
                        <th className="py-2 px-3 text-right">Retorno</th>
                        <th className="py-2 px-3 text-right">Trades</th>
                        <th className="py-2 px-3 text-right">Win %</th>
                        <th className="py-2 px-3 text-right">Sharpe</th>
                        <th className="py-2 px-3 text-right">MDD %</th>
                        <th className="py-2 px-3 text-right">PF</th>
                        <th className="py-2 px-3 text-right">Avg Win</th>
                        <th className="py-2 px-3 text-right">Avg Loss</th>
                        <th className="py-2 px-3 text-right">Best</th>
                        <th className="py-2 px-3 text-right">Worst</th>
                        <th className="py-2 px-3 text-right">DuraÃ§Ã£o</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategies.map((s) => (
                        <tr key={s.strategy_name} className="border-b border-gray-800 hover:bg-gray-800/40">
                          <td className="py-2 px-3 text-cyan-400 font-medium">{s.strategy_name}</td>
                          <td className="py-2 px-3 text-gray-500 text-xs font-mono">
                            {s.bot_ids.length > 0 ? s.bot_ids.join(", ") : "â€”"}
                          </td>
                          <td className={`py-2 px-3 text-right font-medium ${pctColor(s.total_pnl)}`}>${fmt(s.total_pnl)}</td>
                          <td className={`py-2 px-3 text-right ${pctColor(s.total_return_pct)}`}>{fmt(s.total_return_pct)}%</td>
                          <td className="py-2 px-3 text-right text-gray-300">{s.num_trades}</td>
                          <td className={`py-2 px-3 text-right ${s.win_rate >= 50 ? "text-emerald-400" : "text-yellow-400"}`}>{fmt(s.win_rate)}%</td>
                          <td className="py-2 px-3 text-right text-gray-300">{fmt(s.sharpe_ratio, 3)}</td>
                          <td className="py-2 px-3 text-right text-red-400">{fmt(s.max_drawdown_pct)}%</td>
                          <td className="py-2 px-3 text-right text-gray-300">{fmt(s.profit_factor, 3)}</td>
                          <td className="py-2 px-3 text-right text-emerald-400">${fmt(s.avg_win)}</td>
                          <td className="py-2 px-3 text-right text-red-400">${fmt(s.avg_loss)}</td>
                          <td className="py-2 px-3 text-right text-emerald-400">${fmt(s.best_trade)}</td>
                          <td className="py-2 px-3 text-right text-red-400">${fmt(s.worst_trade)}</td>
                          <td className="py-2 px-3 text-right text-gray-300">{fmt(s.avg_trade_duration_hours)}h</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* â”€â”€ Tab: Heatmap â”€â”€ */}
        <TabsContent value="heatmap">
          <Card className="bg-gray-900/60 border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-white text-base flex items-center gap-2">
                <Grid3x3 className="h-5 w-5 text-cyan-400" />
                {t("performance.heatmapTitle") || "Performance por Hora/Dia (Avg PnL)"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!heatmap || heatmap.cells.every((c) => c.count === 0) ? (
                <p className="text-gray-500 text-sm py-10 text-center">
                  {t("performance.noHeatmapData") || "Nenhum trade com timestamp para gerar o heatmap"}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <div className="min-w-[700px]">
                    {/* Hour header */}
                    <div className="flex">
                      <div className="w-12 shrink-0" />
                      {heatmap.hours.map((h) => (
                        <div
                          key={h}
                          className="flex-1 text-center text-gray-500 text-[10px] font-mono pb-1"
                          style={{ minWidth: 28 }}
                        >
                          {h}
                        </div>
                      ))}
                    </div>
                    {/* Rows */}
                    {heatmap.days.map((day, di) => (
                      <div key={day} className="flex items-center mb-0.5">
                        <div className="w-12 shrink-0 text-gray-400 text-xs font-medium pr-2 text-right">
                          {day}
                        </div>
                        {heatmap.hours.map((hour) => {
                          const cell = heatmap.cells.find((c) => c.day === di && c.hour === hour);
                          const avg = cell?.avg_pnl ?? 0;
                          const count = cell?.count ?? 0;
                          const bg = count > 0
                            ? heatColor(avg, heatmap.min_pnl, heatmap.max_pnl)
                            : "#1f2937";
                          return (
                            <div
                              key={hour}
                              className="flex-1 rounded-sm mx-px cursor-default"
                              style={{ minWidth: 28, height: 28, backgroundColor: bg }}
                              title={count > 0 ? `${day} ${hour}h â€” avg $${avg.toFixed(2)} (${count} trades)` : "no trades"}
                            />
                          );
                        })}
                      </div>
                    ))}
                    {/* Legend */}
                    <div className="flex items-center gap-3 mt-4 text-xs text-gray-400">
                      <div
                        className="w-20 h-3 rounded"
                        style={{ background: "linear-gradient(to right, rgb(110,0,0), #1f2937, rgb(0,255,70))" }}
                      />
                      <span>${fmt(heatmap.min_pnl)}</span>
                      <span className="mx-1 text-gray-600">Â·</span>
                      <span>$0</span>
                      <span className="mx-1 text-gray-600">Â·</span>
                      <span>${fmt(heatmap.max_pnl)}</span>
                      <span className="ml-3 text-gray-500">
                        (hover cell for details)
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* â”€â”€ Tab: CorrelaÃ§Ã£o â”€â”€ */}
        <TabsContent value="correlation">
          <Card className="bg-gray-900/60 border-gray-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-white text-base flex items-center gap-2">
                <GitBranch className="h-5 w-5 text-cyan-400" />
                {t("performance.correlationTitle") || "CorrelaÃ§Ã£o de Retornos entre Bots (Pearson)"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!correlation || correlation.bots.length < 2 ? (
                <p className="text-gray-500 text-sm py-10 text-center">
                  {t("performance.noCorrelationData") ||
                    "SÃ£o necessÃ¡rios pelo menos 2 bots com trades para calcular correlaÃ§Ã£o"}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="text-xs border-separate border-spacing-0.5">
                    <thead>
                      <tr>
                        <th className="text-gray-400 font-normal pr-3 text-right" />
                        {correlation.bots.map((b) => (
                          <th key={b} className="text-gray-400 font-mono font-normal px-2 pb-1 text-center max-w-[80px] truncate" title={b}>
                            {b.length > 8 ? b.slice(0, 8) + "â€¦" : b}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {correlation.bots.map((rowBot, i) => (
                        <tr key={rowBot}>
                          <td className="text-gray-400 font-mono pr-3 text-right max-w-[80px] truncate" title={rowBot}>
                            {rowBot.length > 8 ? rowBot.slice(0, 8) + "â€¦" : rowBot}
                          </td>
                          {correlation.matrix[i].map((val, j) => (
                            <td
                              key={j}
                              className="rounded text-center font-mono font-medium cursor-default"
                              style={{
                                width: 52,
                                height: 36,
                                backgroundColor: corrColor(val),
                                color: Math.abs(val) > 0.6 ? "#fff" : "#374151",
                              }}
                              title={`${correlation.bots[i]} Ã— ${correlation.bots[j]}: ${val.toFixed(4)}`}
                            >
                              {fmt(val, 2)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {/* Legend */}
                  <div className="flex items-center gap-3 mt-4 text-xs text-gray-400">
                    <div
                      className="w-32 h-3 rounded"
                      style={{ background: "linear-gradient(to right, rgb(255,0,0), #fff, rgb(0,0,255))" }}
                    />
                    <span>âˆ’1.0 (negativo)</span>
                    <span className="mx-1 text-gray-600">Â·</span>
                    <span>0</span>
                    <span className="mx-1 text-gray-600">Â·</span>
                    <span>+1.0 (positivo)</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

/* â”€â”€ KPI Card sub-component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

// ── Sub-components ───────────────────────────────────────────────────────────────────────────
interface KPICardProps {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  accent?: string;
  // Legacy optional prop from old code:
  colorClass?: string;
}

const KPICard = ({ label, value, sub, icon, accent }: KPICardProps) => (
  <Card style={CARD_BG}>
    <CardContent className="pt-4 pb-3 px-4">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-gray-500 text-xs uppercase tracking-wide">{label}</span>
        {icon}
      </div>
      <p className="text-xl font-bold" style={{ color: accent ?? "#FFFFFF" }}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </CardContent>
  </Card>
);

const PnLCard = ({ label, value, positive }: { label: string; value: string; positive: boolean }) => (
  <div
    style={{
      background: positive ? "rgba(35,200,130,0.06)" : "rgba(239,68,68,0.06)",
      border: `1px solid ${positive ? "rgba(35,200,130,0.18)" : "rgba(239,68,68,0.18)"}`,
      borderRadius: 8,
      padding: "14px 16px",
    }}
  >
    <div className="text-gray-500 text-xs uppercase tracking-wide mb-1.5">{label}</div>
    <div className="text-xl font-bold" style={{ color: positive ? G : "#EF4444" }}>
      {value}
    </div>
  </div>
);

const EmptyState = ({ icon, label }: { icon: ReactNode; label: string }) => (
  <div className="flex flex-col items-center justify-center py-16 gap-3">
    {icon}
    <p className="text-gray-600 text-sm">{label}</p>
  </div>
);

const InfoItem = ({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) => (
  <div className="flex items-center gap-2">
    {icon}
    <div>
      <div className="text-gray-500 text-xs">{label}</div>
      <div className="text-white text-sm font-semibold mt-0.5">{value}</div>
    </div>
  </div>
);

export default PerformanceDashboard;
