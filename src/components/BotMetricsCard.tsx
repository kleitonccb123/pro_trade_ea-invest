/**
 * BotMetricsCard.tsx — PnL display card for a running bot (DOC_05 §7).
 *
 * Shows realized PnL, unrealized PnL, ROI, fees, win rate, drawdown and
 * profit factor.  Separates realized vs unrealized clearly so the user is
 * never confused about locked-in gains vs open-position mark-to-market.
 */

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface BotMetrics {
  realized_pnl_usdt:   number;
  unrealized_pnl_usdt: number;
  total_pnl_usdt:      number;
  roi_pct:             number;
  win_rate:            number;
  total_trades:        number;
  winning_trades:      number;
  losing_trades:       number;
  total_fees_usdt:     number;
  max_drawdown_pct:    number;
  profit_factor:       number;
  avg_holding_minutes: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (v: number, decimals = 4): string =>
  `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}`;

const pctClass = (v: number) =>
  v >= 0 ? "text-green-400" : "text-red-400";

const unrealizedClass = (v: number) =>
  v >= 0 ? "text-yellow-400" : "text-orange-400";

interface MetricRowProps {
  label:     string;
  value:     React.ReactNode;
  subValue?: React.ReactNode;
}

const MetricRow: React.FC<MetricRowProps> = ({ label, value, subValue }) => (
  <div className="flex flex-col gap-0.5">
    <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
    <div className="text-sm font-semibold leading-tight">{value}</div>
    {subValue && (
      <div className="text-xs text-muted-foreground">{subValue}</div>
    )}
  </div>
);

// ── Component ─────────────────────────────────────────────────────────────────

interface BotMetricsCardProps {
  metrics:         BotMetrics;
  botName?:        string;
  pair?:           string;
  isRunning?:      boolean;
  /** Pass true when a position is currently open (shows unrealized section) */
  hasOpenPosition?: boolean;
}

export const BotMetricsCard: React.FC<BotMetricsCardProps> = ({
  metrics,
  botName  = "Bot",
  pair,
  isRunning      = false,
  hasOpenPosition = false,
}) => {
  const isProfit = metrics.total_pnl_usdt >= 0;

  return (
    <Card className="bg-card border-border">
      {/* Header */}
      <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base font-semibold">
          {botName}
          {pair && (
            <span className="ml-2 text-sm text-muted-foreground font-normal">
              {pair}
            </span>
          )}
        </CardTitle>
        <div className="flex gap-2">
          {isRunning && (
            <Badge variant="outline" className="text-green-400 border-green-400 text-xs">
              Ativo
            </Badge>
          )}
          {hasOpenPosition && (
            <Badge variant="outline" className="text-yellow-400 border-yellow-400 text-xs">
              Posição aberta
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">

        {/* ROI — hero metric */}
        <div className="text-center py-2 border-b border-border">
          <p className="text-xs text-muted-foreground mb-1">ROI Total</p>
          <p className={`text-3xl font-bold ${pctClass(metrics.roi_pct)}`}>
            {fmt(metrics.roi_pct, 2)}%
          </p>
          <p className={`text-sm ${pctClass(metrics.total_pnl_usdt)}`}>
            {fmt(metrics.total_pnl_usdt)} USDT
          </p>
        </div>

        {/* Realized / Unrealized split */}
        <div className="grid grid-cols-2 gap-4">
          <MetricRow
            label="PnL Realizado"
            value={
              <span className={pctClass(metrics.realized_pnl_usdt)}>
                {fmt(metrics.realized_pnl_usdt)} USDT
              </span>
            }
          />
          <MetricRow
            label="PnL Não-Realizado"
            value={
              hasOpenPosition ? (
                <span className={unrealizedClass(metrics.unrealized_pnl_usdt)}>
                  {fmt(metrics.unrealized_pnl_usdt)} USDT
                </span>
              ) : (
                <span className="text-muted-foreground">—</span>
              )
            }
            subValue={hasOpenPosition ? "posição em aberto" : undefined}
          />
        </div>

        {/* Win rate & trades */}
        <div className="grid grid-cols-2 gap-4">
          <MetricRow
            label="Win Rate"
            value={`${metrics.win_rate.toFixed(1)}%`}
            subValue={`${metrics.winning_trades}W / ${metrics.losing_trades}L`}
          />
          <MetricRow
            label="Trades totais"
            value={metrics.total_trades}
            subValue={
              metrics.avg_holding_minutes > 0
                ? `${Math.round(metrics.avg_holding_minutes)}min/trade`
                : undefined
            }
          />
        </div>

        {/* Profit factor & drawdown */}
        <div className="grid grid-cols-2 gap-4">
          <MetricRow
            label="Profit Factor"
            value={
              metrics.profit_factor >= 999 ? "∞" : metrics.profit_factor.toFixed(2)
            }
            subValue={metrics.profit_factor >= 1.5 ? "✓ saudável" : "⚠ baixo"}
          />
          <MetricRow
            label="Drawdown Máx."
            value={
              <span className={metrics.max_drawdown_pct > 15 ? "text-red-400" : "text-foreground"}>
                -{metrics.max_drawdown_pct.toFixed(2)}%
              </span>
            }
          />
        </div>

        {/* Fees — shown last, smaller */}
        <div className="flex items-center justify-between text-xs text-muted-foreground border-t border-border pt-2">
          <span>Fees totais pagos</span>
          <span>-{metrics.total_fees_usdt.toFixed(4)} USDT</span>
        </div>

      </CardContent>
    </Card>
  );
};

// ── PnLDisplay (inline widget, re-exported for existing pages) ────────────────

export const PnLDisplay: React.FC<{ metrics: BotMetrics }> = ({ metrics }) => {
  const isProfit = metrics.total_pnl_usdt >= 0;

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-sm text-muted-foreground">PnL Realizado</p>
        <p className={`text-lg font-bold ${pctClass(metrics.realized_pnl_usdt)}`}>
          {fmt(metrics.realized_pnl_usdt)} USDT
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">PnL Não-Realizado</p>
        <p className={`text-lg font-bold ${unrealizedClass(metrics.unrealized_pnl_usdt)}`}>
          {fmt(metrics.unrealized_pnl_usdt)} USDT
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">ROI Total</p>
        <p className={`text-xl font-bold ${pctClass(metrics.roi_pct)}`}>
          {fmt(metrics.roi_pct, 2)}%
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">Taxas Pagas (fees)</p>
        <p className="text-sm text-muted-foreground">
          -{metrics.total_fees_usdt.toFixed(4)} USDT
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">Win Rate</p>
        <p className="text-lg font-semibold">
          {metrics.win_rate.toFixed(1)}% ({metrics.total_trades} trades)
        </p>
      </div>
    </div>
  );
};

export default BotMetricsCard;
