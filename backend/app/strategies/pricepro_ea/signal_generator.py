"""
SignalGenerator — Gera sinais de entrada combinando todos os filtros

Equivale ao bloco do OnTick() + CheckTrend() + CheckRSI() +
CheckCandleStrength() + CheckVolume() + CheckRangeAdaptive() do MT5.

Fluxo:
    1. Verificar tendência (EMA)
    2. Verificar RSI (retração ou impulso)
    3. Verificar força do candle (body %)
    4. Verificar volume
    5. Verificar range adaptativo
    → Se TODOS aprovados: retorna sinal BUY ou SELL
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import EAConfig
from .indicators import Candle, IndicatorSnapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums de direção e sinal
# ---------------------------------------------------------------------------

class Direction(str, Enum):
    NONE = "none"
    BUY  = "buy"
    SELL = "sell"


class EntrySignal(str, Enum):
    NO_ENTRY  = "no_entry"
    ENTER_BUY  = "enter_buy"
    ENTER_SELL = "enter_sell"


# ---------------------------------------------------------------------------
# Resultado da análise de filtros
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    """Resultado detalhado de cada filtro para logging/debug."""
    trend_direction: Direction
    trend_ok: bool

    rsi_value: Optional[float]
    rsi_ok: bool
    rsi_logic: str   # "retraction" | "impulse" | "disabled"

    body_pct: float
    body_ok: bool

    vol_ratio: float
    vol_ok: bool

    range_ratio: float
    range_ok: bool

    all_passed: bool
    signal: EntrySignal

    def log_debug(self, symbol: str) -> None:
        direction = self.trend_direction.value.upper()
        logger.debug(
            "[%s] Filtros — Dir=%s Trend=%s | RSI=%.1f(%s)=%s | "
            "Body=%.1f%%=%s | Vol=%.2f=%s | Range=%.2f=%s → %s",
            symbol, direction,
            "OK" if self.trend_ok else "BLOCK",
            self.rsi_value or 0, self.rsi_logic,
            "OK" if self.rsi_ok else "BLOCK",
            self.body_pct, "OK" if self.body_ok else "BLOCK",
            self.vol_ratio, "OK" if self.vol_ok else "BLOCK",
            self.range_ratio, "OK" if self.range_ok else "BLOCK",
            self.signal.value,
        )


# ---------------------------------------------------------------------------
# SignalGenerator
# ---------------------------------------------------------------------------

class SignalGenerator:
    """
    Avalia os cinco filtros do EA e retorna um sinal de entrada.

    Thread-safe: sem estado mutável entre chamadas.
    """

    def __init__(self, config: EAConfig):
        self.cfg = config

    # ── Tendência via EMA ────────────────────────────────────────────────────

    def _check_trend(self, snap: IndicatorSnapshot, current_price: float) -> Direction:
        """
        Compara preço de fechamento do último candle com a EMA.
        Se EMA desativada, permite qualquer direção (retorna BUY como padrão).
        """
        if not self.cfg.use_ema:
            return Direction.BUY  # permite entrada em qualquer direção

        if snap.ema_value is None:
            return Direction.NONE

        if snap.last_candle is None:
            return Direction.NONE

        close = snap.last_candle.close
        if close > snap.ema_value:
            return Direction.BUY
        if close < snap.ema_value:
            return Direction.SELL
        return Direction.NONE

    # ── RSI ─────────────────────────────────────────────────────────────────

    def _check_rsi(self, snap: IndicatorSnapshot, direction: Direction) -> tuple[bool, str]:
        """
        Verifica RSI conforme configuração:
        - rsi_with_trend=False (retração): BUY quando RSI sobrevendido, SELL sobrecomprado
        - rsi_with_trend=True  (impulso):  BUY quando RSI >= 50, SELL quando RSI <= 50
        """
        if not self.cfg.use_rsi:
            return True, "disabled"

        rsi_val = snap.rsi_value
        if rsi_val is None:
            return False, "no_data"

        logic = "impulse" if self.cfg.rsi_with_trend else "retraction"

        if self.cfg.rsi_with_trend:
            if direction == Direction.BUY:
                return rsi_val >= 50.0, logic
            if direction == Direction.SELL:
                return rsi_val <= 50.0, logic
        else:
            if direction == Direction.BUY:
                return rsi_val <= self.cfg.rsi_oversold, logic
            if direction == Direction.SELL:
                return rsi_val >= self.cfg.rsi_overbought, logic

        return False, logic

    # ── Força do candle ──────────────────────────────────────────────────────

    def _check_candle(self, snap: IndicatorSnapshot) -> bool:
        if not self.cfg.use_candle_strength:
            return True
        return snap.body_pct >= self.cfg.candle_body_min_pct

    # ── Volume ───────────────────────────────────────────────────────────────

    def _check_volume(self, snap: IndicatorSnapshot) -> bool:
        if not self.cfg.use_volume:
            return True
        return snap.vol_ratio >= self.cfg.volume_min_ratio

    # ── Range adaptativo ─────────────────────────────────────────────────────

    def _check_range(self, snap: IndicatorSnapshot) -> bool:
        if not self.cfg.use_range_adaptive:
            return True
        return snap.rng_ratio >= self.cfg.range_multiplier

    # ── Candle de força na direção (para scalper) ────────────────────────────

    def was_force_candle_in_direction(
        self, snap: IndicatorSnapshot, direction: Direction
    ) -> bool:
        """
        Verifica se o candle anterior foi um candle de força na direção informada.
        Equivale a WasPreviousCandleForceInDir() do MT5.
        """
        c = snap.last_candle
        if c is None:
            return False
        if snap.body_pct < self.cfg.candle_body_min_pct:
            return False
        if direction == Direction.BUY and c.close > c.open:
            return True
        if direction == Direction.SELL and c.close < c.open:
            return True
        return False

    # ── Análise principal ────────────────────────────────────────────────────

    def analyze(self, snap: IndicatorSnapshot, current_price: float) -> FilterResult:
        """
        Executa todos os filtros e retorna FilterResult com sinal de entrada.

        Equivale ao bloco de nova barra do OnTick() no MT5 que testa
        okRSI && okCandle && okVol && okRange.
        """
        direction = self._check_trend(snap, current_price)
        trend_ok = direction != Direction.NONE

        rsi_ok, rsi_logic = self._check_rsi(snap, direction)
        body_ok = self._check_candle(snap)
        vol_ok = self._check_volume(snap)
        range_ok = self._check_range(snap)

        all_passed = trend_ok and rsi_ok and body_ok and vol_ok and range_ok

        if all_passed:
            signal = EntrySignal.ENTER_BUY if direction == Direction.BUY else EntrySignal.ENTER_SELL
        else:
            signal = EntrySignal.NO_ENTRY

        result = FilterResult(
            trend_direction=direction,
            trend_ok=trend_ok,
            rsi_value=snap.rsi_value,
            rsi_ok=rsi_ok,
            rsi_logic=rsi_logic,
            body_pct=snap.body_pct,
            body_ok=body_ok,
            vol_ratio=snap.vol_ratio,
            vol_ok=vol_ok,
            range_ratio=snap.rng_ratio,
            range_ok=range_ok,
            all_passed=all_passed,
            signal=signal,
        )

        if self.cfg.debug:
            result.log_debug(self.cfg.symbol)

        return result
