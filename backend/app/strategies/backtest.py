"""
DOC-08 — Marketplace de Estratégias
Motor de Backtesting: critérios obrigatórios de publicação, cálculo de métricas.

- Dados históricos: KuCoin public REST API (klines)
- Critérios de aprovação: Sharpe >= 0.5, MaxDD <= 30%, WinRate >= 40%, Trades >= 50, Dias >= 90
- Código de estratégia NUNCA exposto ao comprador
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Critérios mínimos de publicação (DOC-08 §5) ───────────────────────────────
PUBLICATION_CRITERIA: Dict[str, Any] = {
    "min_sharpe_ratio": 0.5,
    "max_drawdown_pct": 30.0,
    "min_win_rate": 40.0,
    "min_total_trades": 50,
    "min_backtest_days": 90,
}

# KuCoin public klines endpoint (não requer autenticação)
KUCOIN_KLINES_URL = "https://api.kucoin.com/api/v1/market/candles"


# ──────────────────────────────────────────────────────────────────────────────
# Modelos de dados
# ──────────────────────────────────────────────────────────────────────────────

class OHLCV(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class BacktestConfig(BaseModel):
    strategy_id: str
    version_id: str
    symbol: str                       # ex: "BTC-USDT"
    exchange: str = "kucoin"
    start_ts: int                     # Unix timestamp segundos
    end_ts: int
    initial_capital_usd: float = 1000.0
    parameters: Dict[str, Any] = Field(default_factory=dict)
    maker_fee_pct: float = 0.1
    taker_fee_pct: float = 0.1

    @property
    def period_days(self) -> int:
        return max(1, (self.end_ts - self.start_ts) // 86400)


class BacktestTrade(BaseModel):
    entry_index: int
    exit_index: int
    side: str = "long"
    entry_price: float
    exit_price: float
    size: float
    pnl_usd: float
    pnl_pct: float
    fees_usd: float
    exit_reason: str   # 'tp' | 'sl' | 'signal' | 'end_of_data'


class BacktestMetrics(BaseModel):
    total_return_usd: float = 0.0
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: int = 0
    win_rate: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0
    total_trades: int = 0
    avg_holding_period_hours: float = 0.0
    best_trade_usd: float = 0.0
    worst_trade_usd: float = 0.0


class BacktestResult(BaseModel):
    backtest_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str
    version_id: str
    config: BacktestConfig
    metrics: BacktestMetrics = Field(default_factory=BacktestMetrics)
    trades: List[BacktestTrade] = Field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    buy_hold_curve: List[Dict[str, Any]] = Field(default_factory=list)
    buy_hold_return_pct: float = 0.0
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    passed: bool = False
    failure_reasons: List[str] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Engine de Backtesting
# ──────────────────────────────────────────────────────────────────────────────

class BacktestEngine:
    """
    Motor de backtesting com dados reais da KuCoin.

    Arquitetura:
      1. Busca klines históricos via API pública KuCoin
      2. Aplica lógica da estratégia candle a candle (via parâmetros)
      3. Simula trades com taxas de maker/taker
      4. Calcula métricas (Sharpe, MaxDD, WinRate, etc.)
      5. Valida critérios obrigatórios de publicação

    IMPORTANTE: O código da estratégia nunca é transmitido ao engine em plaintext
                via HTTP. Apenas os parâmetros configuráveis são usados aqui para
                simular uma estratégia de moving-average paramétrica como proxy de
                backtesting. A lógica proprietária é executada internamente com o
                hash de código verificado.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._results_col = db["backtest_results"]

    # ── API pública ────────────────────────────────────────────────────────────

    async def run(self, config: BacktestConfig) -> BacktestResult:
        """
        Executa backtesting completo e persiste o resultado no MongoDB.
        Levanta ValueError se os dados históricos forem insuficientes.
        """
        logger.info(
            "Iniciando backtest strategy=%s version=%s symbol=%s",
            config.strategy_id, config.version_id, config.symbol,
        )

        if config.period_days < PUBLICATION_CRITERIA["min_backtest_days"]:
            result = BacktestResult(
                strategy_id=config.strategy_id,
                version_id=config.version_id,
                config=config,
                passed=False,
                failure_reasons=[
                    f"Período de backtest {config.period_days}d < mínimo "
                    f"{PUBLICATION_CRITERIA['min_backtest_days']}d"
                ],
            )
            await self._persist(result)
            return result

        klines = await self._fetch_klines(config)
        if len(klines) < 60:
            result = BacktestResult(
                strategy_id=config.strategy_id,
                version_id=config.version_id,
                config=config,
                passed=False,
                failure_reasons=["Dados históricos insuficientes (< 60 candles)"],
            )
            await self._persist(result)
            return result

        trades, equity_curve = self._simulate(klines, config)
        metrics = self._calculate_metrics(trades, config)
        passed, reasons = self._validate_criteria(metrics)

        buy_hold_curve, buy_hold_return = self._buy_and_hold(klines, config)

        result = BacktestResult(
            strategy_id=config.strategy_id,
            version_id=config.version_id,
            config=config,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            buy_hold_curve=buy_hold_curve,
            buy_hold_return_pct=buy_hold_return,
            passed=passed,
            failure_reasons=reasons,
        )
        await self._persist(result)
        logger.info(
            "Backtest concluído strategy=%s passed=%s sharpe=%.2f dd=%.1f%%",
            config.strategy_id, passed, metrics.sharpe_ratio, metrics.max_drawdown_pct,
        )
        return result

    async def get_result(self, backtest_id: str) -> Optional[BacktestResult]:
        doc = await self._results_col.find_one({"backtest_id": backtest_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return BacktestResult(**doc)

    async def list_results(
        self, strategy_id: str, limit: int = 10
    ) -> List[BacktestResult]:
        """Lista últimos backtests de uma estratégia."""
        cursor = self._results_col.find(
            {"strategy_id": strategy_id}
        ).sort("completed_at", -1).limit(limit)
        results: List[BacktestResult] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(BacktestResult(**doc))
        return results

    # ── Dados históricos ───────────────────────────────────────────────────────

    async def _fetch_klines(self, config: BacktestConfig) -> List[OHLCV]:
        """
        Busca klines diários da KuCoin (máx 1500 candles por chamada).
        Usa timeframe "1day" para cobrir período >= 90 dias.
        """
        params = {
            "symbol": config.symbol,
            "type": "1day",
            "startAt": str(config.start_ts),
            "endAt": str(config.end_ts),
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(KUCOIN_KLINES_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != "200000":
                    logger.warning("KuCoin API erro: %s", data.get("msg"))
                    return []

                candles = data.get("data", [])
                # Formato KuCoin: [timestamp, open, close, high, low, volume, turnover]
                result: List[OHLCV] = []
                for c in reversed(candles):  # API retorna do mais recente ao mais antigo
                    try:
                        result.append(OHLCV(
                            timestamp=datetime.fromtimestamp(int(c[0]), tz=timezone.utc),
                            open=float(c[1]),
                            close=float(c[2]),
                            high=float(c[3]),
                            low=float(c[4]),
                            volume=float(c[5]),
                        ))
                    except (IndexError, ValueError):
                        continue
                return result
        except httpx.HTTPError as exc:
            logger.error("Erro ao buscar klines KuCoin: %s", exc)
            return []

    # ── Simulação ──────────────────────────────────────────────────────────────

    def _simulate(
        self, klines: List[OHLCV], config: BacktestConfig
    ) -> Tuple[List[BacktestTrade], List[Dict[str, Any]]]:
        """
        Simula estratégia de cruzamento de médias móveis (SMA) como motor proxy.
        Parâmetros usados dos config.parameters:
          - 'short_period' (int, default=9)
          - 'long_period'  (int, default=21)
          - 'stop_loss_pct' (float, default=5.0)
          - 'take_profit_pct' (float, default=10.0)
        """
        short_p = int(config.parameters.get("short_period", 9))
        long_p = int(config.parameters.get("long_period", 21))
        sl_pct = float(config.parameters.get("stop_loss_pct", 5.0)) / 100.0
        tp_pct = float(config.parameters.get("take_profit_pct", 10.0)) / 100.0

        closes = [k.close for k in klines]
        trades: List[BacktestTrade] = []
        equity = config.initial_capital_usd
        equity_curve: List[Dict[str, Any]] = []

        in_trade = False
        entry_price = 0.0
        entry_idx = 0
        size = 0.0

        warm_up = max(long_p, 50)

        for i in range(warm_up, len(klines)):
            short_sma = sum(closes[i - short_p: i]) / short_p
            long_sma = sum(closes[i - long_p: i]) / long_p
            prev_short = sum(closes[i - short_p - 1: i - 1]) / short_p
            prev_long = sum(closes[i - long_p - 1: i - 1]) / long_p

            price = closes[i]
            ts = klines[i].timestamp.isoformat()

            if not in_trade:
                # Sinal de entrada: cruzamento SMA para cima
                if prev_short <= prev_long and short_sma > long_sma:
                    fee = equity * (config.taker_fee_pct / 100.0)
                    size = (equity - fee) / price
                    entry_price = price
                    entry_idx = i
                    in_trade = True
                    equity -= fee

            else:
                # Verificar TP / SL
                change_pct = (price - entry_price) / entry_price
                exit_reason = None

                if change_pct >= tp_pct:
                    exit_reason = "tp"
                elif change_pct <= -sl_pct:
                    exit_reason = "sl"
                elif prev_short >= prev_long and short_sma < long_sma:
                    exit_reason = "signal"
                elif i == len(klines) - 1:
                    exit_reason = "end_of_data"

                if exit_reason:
                    exit_price = price
                    gross_pnl = (exit_price - entry_price) * size
                    fee_exit = size * exit_price * (config.taker_fee_pct / 100.0)
                    net_pnl = gross_pnl - fee_exit
                    pnl_pct = (exit_price - entry_price) / entry_price * 100.0
                    equity += size * exit_price - fee_exit

                    trades.append(BacktestTrade(
                        entry_index=entry_idx,
                        exit_index=i,
                        side="long",
                        entry_price=entry_price,
                        exit_price=exit_price,
                        size=size,
                        pnl_usd=round(net_pnl, 6),
                        pnl_pct=round(pnl_pct, 4),
                        fees_usd=round(fee_exit, 6),
                        exit_reason=exit_reason,
                    ))
                    in_trade = False

            equity_curve.append({"timestamp": ts, "equity_usd": round(equity, 4)})

        return trades, equity_curve

    # ── Métricas ───────────────────────────────────────────────────────────────

    def _calculate_metrics(
        self, trades: List[BacktestTrade], config: BacktestConfig
    ) -> BacktestMetrics:
        if not trades:
            return BacktestMetrics()

        wins = [t for t in trades if t.pnl_usd > 0]
        losses = [t for t in trades if t.pnl_usd < 0]
        days = max(1, config.period_days)

        total_pnl = sum(t.pnl_usd for t in trades)
        total_ret_pct = (total_pnl / config.initial_capital_usd) * 100.0
        ann_ret_pct = ((1 + total_ret_pct / 100.0) ** (365.0 / days) - 1) * 100.0

        # Drawdown
        equity = config.initial_capital_usd
        peak = equity
        max_dd = 0.0
        for t in trades:
            equity += t.pnl_usd
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak) * 100.0 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        win_rate = (len(wins) / len(trades)) * 100.0 if trades else 0.0
        avg_win = sum(t.pnl_usd for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(t.pnl_usd for t in losses) / len(losses) if losses else 0.0

        gross_wins = sum(t.pnl_usd for t in wins)
        gross_losses = abs(sum(t.pnl_usd for t in losses))
        profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else 0.0

        calmar = (ann_ret_pct / max_dd) if max_dd > 0 else 0.0

        sharpe = self._calc_sharpe(trades)
        sortino = self._calc_sortino(trades)

        # Avg holding period (dias entre entry e exit)
        holding_hours = 0.0
        if trades:
            total_bars = sum(abs(t.exit_index - t.entry_index) for t in trades)
            holding_hours = (total_bars / len(trades)) * 24.0  # 1 bar ≈ 1 dia

        return BacktestMetrics(
            total_return_usd=round(total_pnl, 4),
            total_return_pct=round(total_ret_pct, 4),
            annualized_return_pct=round(ann_ret_pct, 4),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            max_drawdown_pct=round(max_dd, 4),
            win_rate=round(win_rate, 4),
            avg_win_usd=round(avg_win, 4),
            avg_loss_usd=round(avg_loss, 4),
            profit_factor=round(profit_factor, 4),
            calmar_ratio=round(calmar, 4),
            total_trades=len(trades),
            avg_holding_period_hours=round(holding_hours, 2),
            best_trade_usd=round(max((t.pnl_usd for t in trades), default=0.0), 4),
            worst_trade_usd=round(min((t.pnl_usd for t in trades), default=0.0), 4),
        )

    @staticmethod
    def _calc_sharpe(trades: List[BacktestTrade]) -> float:
        if len(trades) < 2:
            return 0.0
        returns = [t.pnl_pct / 100.0 for t in trades]
        avg = sum(returns) / len(returns)
        variance = sum((r - avg) ** 2 for r in returns) / len(returns)
        std = math.sqrt(variance)
        return (avg / std) * math.sqrt(252) if std > 0 else 0.0

    @staticmethod
    def _calc_sortino(trades: List[BacktestTrade]) -> float:
        if not trades:
            return 0.0
        returns = [t.pnl_pct / 100.0 for t in trades]
        avg = sum(returns) / len(returns)
        neg = [r for r in returns if r < 0]
        down_std = math.sqrt(sum(r ** 2 for r in neg) / len(neg)) if neg else 0.0
        return (avg / down_std) * math.sqrt(252) if down_std > 0 else 0.0

    # ── Critérios de publicação ────────────────────────────────────────────────

    @staticmethod
    def _validate_criteria(metrics: BacktestMetrics) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        c = PUBLICATION_CRITERIA

        if metrics.sharpe_ratio < c["min_sharpe_ratio"]:
            reasons.append(
                f"Sharpe {metrics.sharpe_ratio:.2f} < mínimo {c['min_sharpe_ratio']}"
            )
        if metrics.max_drawdown_pct > c["max_drawdown_pct"]:
            reasons.append(
                f"Max drawdown {metrics.max_drawdown_pct:.1f}% > máximo {c['max_drawdown_pct']}%"
            )
        if metrics.win_rate < c["min_win_rate"]:
            reasons.append(
                f"Win rate {metrics.win_rate:.1f}% < mínimo {c['min_win_rate']}%"
            )
        if metrics.total_trades < c["min_total_trades"]:
            reasons.append(
                f"Apenas {metrics.total_trades} trades (mínimo {c['min_total_trades']})"
            )
        return (len(reasons) == 0, reasons)

    # ── Buy-and-Hold benchmark ───────────────────────────────────────────────

    @staticmethod
    def _buy_and_hold(
        klines: List[OHLCV], config: BacktestConfig
    ) -> Tuple[List[Dict[str, Any]], float]:
        """Calcula equity curve de buy-and-hold para comparação."""
        if not klines:
            return [], 0.0
        first_close = klines[0].close
        if first_close <= 0:
            return [], 0.0
        units = config.initial_capital_usd / first_close
        curve: List[Dict[str, Any]] = []
        for k in klines:
            curve.append({
                "timestamp": k.timestamp.isoformat(),
                "equity_usd": round(units * k.close, 4),
            })
        last_equity = units * klines[-1].close
        ret_pct = ((last_equity - config.initial_capital_usd) / config.initial_capital_usd) * 100.0
        return curve, round(ret_pct, 4)

    # ── Persistência ───────────────────────────────────────────────────────────

    async def _persist(self, result: BacktestResult) -> None:
        try:
            doc = result.model_dump()
            await self._results_col.update_one(
                {"backtest_id": result.backtest_id},
                {"$set": doc},
                upsert=True,
            )
        except Exception as exc:
            logger.error("Falha ao persistir backtest %s: %s", result.backtest_id, exc)
