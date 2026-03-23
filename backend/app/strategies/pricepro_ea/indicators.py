"""
Indicators — Cálculo de indicadores técnicos

Equivalências MQL5 → Python:
    iMA(EMA 55)        → ema()
    iRSI               → rsi()
    iOpen/iClose/...   → recebidos como lista de candles
    GetCandleBodyPct   → candle_body_pct()
    GetVolumeRatio     → volume_ratio()
    GetRangeRatio      → range_ratio()

Todos os cálculos são sobre listas de candles OHLCV em ordem
cronológica (índice 0 = mais antigo, índice -1 = mais recente ainda
incompleto; índice -2 = candle anterior fechado — equivale ao
shift=1 do MT5).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estrutura de candle normalizado
# ---------------------------------------------------------------------------

class Candle(NamedTuple):
    timestamp: int      # Unix ms
    open: float
    high: float
    low: float
    close: float
    volume: float


# ---------------------------------------------------------------------------
# EMA (Exponential Moving Average)
# ---------------------------------------------------------------------------

def ema(closes: List[float], period: int) -> Optional[float]:
    """
    Calcula EMA usando o método progressivo (sem biblioteca externa).
    Compatível com a lógica iMA(MODE_EMA) do MT5.

    Retorna o valor da EMA para o último candle fechado (shift=1),
    ou None se dados insuficientes.
    """
    if len(closes) < period + 1:
        return None

    k = 2.0 / (period + 1)
    # Seed com SMA dos primeiros `period` valores
    result = sum(closes[:period]) / period
    for price in closes[period:]:
        result = price * k + result * (1 - k)
    return result


def sma(closes: List[float], period: int) -> Optional[float]:
    """Simple Moving Average."""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def wma(closes: List[float], period: int) -> Optional[float]:
    """Weighted Moving Average."""
    if len(closes) < period:
        return None
    weights = list(range(1, period + 1))
    segment = closes[-period:]
    return sum(w * c for w, c in zip(weights, segment)) / sum(weights)


def moving_average(closes: List[float], period: int, ma_type: str = "ema") -> Optional[float]:
    """Dispatcher de média móvel."""
    t = ma_type.lower()
    if t == "ema":
        return ema(closes, period)
    if t == "sma":
        return sma(closes, period)
    if t == "wma":
        return wma(closes, period)
    return ema(closes, period)


# ---------------------------------------------------------------------------
# RSI (Relative Strength Index)
# ---------------------------------------------------------------------------

def rsi(closes: List[float], period: int = 9) -> Optional[float]:
    """
    Calcula RSI usando o algoritmo de Wilder (como o MT5 usa por padrão).

    Retorna RSI [0-100] calculado sobre os dados disponíveis,
    ou None se insuficiente.
    """
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    # Seed
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


# ---------------------------------------------------------------------------
# Força do candle (body %)
# ---------------------------------------------------------------------------

def candle_body_pct(candle: Candle) -> float:
    """
    Retorna percentual do corpo em relação ao range total do candle.
    Equivale a GetCandleBodyPercent() do MT5.

    Retorna 0 se o range for zero (doji ou dados inválidos).
    """
    total_range = candle.high - candle.low
    if total_range <= 0:
        return 0.0
    body = abs(candle.close - candle.open)
    return (body / total_range) * 100.0


def is_bullish_candle(candle: Candle) -> bool:
    return candle.close > candle.open


def is_bearish_candle(candle: Candle) -> bool:
    return candle.close < candle.open


def is_strong_candle(candle: Candle, min_body_pct: float) -> bool:
    """Candle de força: corpo >= min_body_pct."""
    return candle_body_pct(candle) >= min_body_pct


# ---------------------------------------------------------------------------
# Volume ratio
# ---------------------------------------------------------------------------

def volume_ratio(candles: List[Candle], lookback: int = 3) -> float:
    """
    Razão entre o volume do candle anterior e a média dos últimos
    `lookback` candles (incluindo ele mesmo).

    Equivale a GetVolumeRatio() do MT5 (v1 + v2 + v3 / 3).

    Índices:
        candles[-2] = shift=1 (candle anterior fechado)
        candles[-3] = shift=2
        candles[-4] = shift=3
    """
    if len(candles) < lookback + 1:
        return 0.0

    closed = candles[:-1]  # excluir candle atual incompleto
    if len(closed) < lookback:
        return 0.0

    recent = closed[-lookback:]
    avg_vol = sum(c.volume for c in recent) / lookback
    if avg_vol <= 0:
        return 0.0

    return closed[-1].volume / avg_vol  # shift=1 é o último fechado


# ---------------------------------------------------------------------------
# Range adaptativo
# ---------------------------------------------------------------------------

def range_ratio(candles: List[Candle], period: int = 9) -> float:
    """
    Razão entre o range do candle anterior e a média dos últimos `period` candles.
    Equivale a GetRangeRatio() do MT5.
    """
    if len(candles) < period + 1:
        return 0.0

    closed = candles[:-1]
    if len(closed) < period:
        return 0.0

    recent = closed[-period:]
    avg_range = sum(c.high - c.low for c in recent) / period
    if avg_range <= 0:
        return 0.0

    current_range = closed[-1].high - closed[-1].low
    return current_range / avg_range


# ---------------------------------------------------------------------------
# Indicadores completos (snapshot para debug)
# ---------------------------------------------------------------------------

class IndicatorSnapshot:
    """Dados de indicadores calculados para um tick/barra."""

    def __init__(
        self,
        ema_value: Optional[float],
        rsi_value: Optional[float],
        body_pct: float,
        vol_ratio: float,
        rng_ratio: float,
        last_candle: Optional[Candle],
    ):
        self.ema_value = ema_value
        self.rsi_value = rsi_value
        self.body_pct = body_pct
        self.vol_ratio = vol_ratio
        self.rng_ratio = rng_ratio
        self.last_candle = last_candle

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ema": round(self.ema_value, 8) if self.ema_value is not None else None,
            "rsi": round(self.rsi_value, 2) if self.rsi_value is not None else None,
            "body_pct": round(self.body_pct, 2),
            "vol_ratio": round(self.vol_ratio, 3),
            "range_ratio": round(self.rng_ratio, 3),
        }


def compute_all(
    candles: List[Candle],
    ema_period: int = 55,
    ema_type: str = "ema",
    rsi_period: int = 9,
    range_period: int = 9,
    vol_lookback: int = 3,
) -> IndicatorSnapshot:
    """
    Calcula todos os indicadores de uma vez sobre a lista de candles.

    `candles` deve incluir o candle atual incompleto (índice -1),
    pois os cálculos usam índice -2 como shift=1.
    """
    closes = [c.close for c in candles]

    ema_val = moving_average(closes[:-1], ema_period, ema_type)   # sem candle atual
    rsi_val = rsi(closes[:-1], rsi_period)

    last_closed = candles[-2] if len(candles) >= 2 else None
    body = candle_body_pct(last_closed) if last_closed else 0.0
    vol = volume_ratio(candles, vol_lookback)
    rng = range_ratio(candles, range_period)

    return IndicatorSnapshot(
        ema_value=ema_val,
        rsi_value=rsi_val,
        body_pct=body,
        vol_ratio=vol,
        rng_ratio=rng,
        last_candle=last_closed,
    )
