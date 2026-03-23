"""
MarketVolatilityIndexer — Proxy de Crypto VIX

DOC-05 §6

Calcula índice de volatilidade intraday (score 0-100) composto por:
  - ATR% como % do preço (peso 0.5)
  - Volume spike vs média histórica (peso 0.3)
  - Spread bid/ask como % do mid-price (peso 0.2)

Score > 85 → bloquear novas ordens (Camada 1 do RiskManager).
Cache Redis de 30 segundos por símbolo.

Fórmulas (DOC-05 §7):

  TR_t = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)
  ATR   = média(TR) / preço × 100
  ATR_score = min(100, ATR_pct × 100)

  VolumeSpike = (currentVol / avgVol - 1) × 33.3
  SpreadScore = spread_pct × 100

  V_score = min(100, ATR_score × 0.5 + VolumeSpike × 0.3 + SpreadScore × 0.2)

KuCoin kline format: [timestamp, open, close, high, low, volume, turnover]
  index 2 = close, 3 = high, 4 = low, 5 = volume
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SEC = 30
VOLATILITY_BLOCK_THRESHOLD = 85.0


class MarketVolatilityIndexer:
    """
    Calcula o score de volatilidade de mercado com cache Redis.
    
    Uso:
    ```python
    indexer = MarketVolatilityIndexer(kucoin_client, redis_client)
    score = await indexer.get_volatility_score("BTC-USDT")
    if score > 85:
        # bloquear ordem
    ```
    """

    def __init__(
        self,
        kucoin_client: Any,
        redis_client: Optional[Any] = None,
    ) -> None:
        self._kucoin = kucoin_client
        self._redis  = redis_client
        # Fallback em memória se Redis não disponível
        self._mem_cache: Dict[str, tuple[float, float]] = {}  # {symbol: (score, expires_at)}

    async def get_volatility_score(self, symbol: str) -> float:
        """
        Retorna o score de volatilidade (0-100) para o símbolo.
        Cache Redis 30s; fallback memória.

        Raises:
            Não levanta exceções — retorna 0.0 em caso de falha de dados,
            preservando o fluxo normal de ordens quando os dados não estão disponíveis.
        """
        # ── Cache ─────────────────────────────────────────────────────────────
        cache_key = f"volatility:{symbol}"

        if self._redis is not None:
            try:
                cached = await self._redis.get(cache_key)
                if cached:
                    logger.debug("VolatilityIndexer: cache hit %s=%s", symbol, cached)
                    return float(cached)
            except Exception as exc:
                logger.debug("VolatilityIndexer: redis cache read error: %s", exc)
        else:
            # Fallback memória
            if symbol in self._mem_cache:
                score, expires = self._mem_cache[symbol]
                if time.monotonic() < expires:
                    return score

        # ── Cálculo ───────────────────────────────────────────────────────────
        try:
            score = await self._compute_score(symbol)
        except Exception as exc:
            logger.warning(
                "VolatilityIndexer: erro ao calcular score para %s: %s "
                "— retornando 0 (permitir ordem). Verifique conectividade.",
                symbol, exc,
            )
            return 0.0

        # ── Store cache ───────────────────────────────────────────────────────
        try:
            if self._redis is not None:
                await self._redis.setex(cache_key, CACHE_TTL_SEC, f"{score:.4f}")
            else:
                self._mem_cache[symbol] = (score, time.monotonic() + CACHE_TTL_SEC)
        except Exception as exc:
            logger.debug("VolatilityIndexer: falha ao armazenar cache: %s", exc)

        logger.debug("VolatilityIndexer: %s score=%.2f", symbol, score)
        return score

    async def _compute_score(self, symbol: str) -> float:
        """Busca dados e calcula o score composto."""
        klines, ticker = await self._fetch_data(symbol)

        atr_score    = self._calculate_atr_pct(klines)
        volume_spike = self._calculate_volume_spike(klines)
        spread_score = self._calculate_spread_pct(ticker)

        score = min(100.0, atr_score * 0.5 + volume_spike * 0.3 + spread_score * 0.2)
        return score

    async def _fetch_data(self, symbol: str):
        """Busca klines (20 velas de 1min) e ticker em paralelo."""
        import asyncio
        klines_coro = self._kucoin.get_klines(symbol, interval="1min")
        ticker_coro = self._kucoin.get_ticker(symbol)
        klines, ticker = await asyncio.gather(klines_coro, ticker_coro)

        # KuCoin retorna klines em ordem decrescente → reverter para ordem cronológica
        if isinstance(klines, list):
            klines = list(reversed(klines))
            klines = klines[-20:]   # Últimas 20 velas

        return klines, ticker

    # ── Cálculos de componentes ───────────────────────────────────────────────

    @staticmethod
    def _calculate_atr_pct(klines: List[Any]) -> float:
        """
        ATR: True Range médio como % do preço de fechamento.
        Normalizado: 0.1% ATR → score 10, 1% ATR → score 100.

        KuCoin kline: [timestamp, open, close, high, low, volume, turnover]
          index: 0=time, 1=open, 2=close, 3=high, 4=low, 5=volume
        """
        if len(klines) < 2:
            return 0.0

        true_ranges = []
        for i in range(1, len(klines)):
            prev  = klines[i - 1]
            kline = klines[i]
            try:
                high       = float(kline[3])
                low        = float(kline[4])
                close      = float(kline[2])
                prev_close = float(prev[2])

                if close <= 0:
                    continue

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low  - prev_close),
                )
                true_ranges.append((tr / close) * 100.0)
            except (IndexError, ValueError, ZeroDivisionError):
                continue

        if not true_ranges:
            return 0.0

        atr_pct = sum(true_ranges) / len(true_ranges)
        # Normalizar: 1% ATR = score 100
        return min(100.0, atr_pct * 100.0)

    @staticmethod
    def _calculate_volume_spike(klines: List[Any]) -> float:
        """
        Volume spike: vela atual vs média das anteriores.
        2× volume → score 33.3, 4× → score 100.
        """
        if len(klines) < 2:
            return 0.0

        try:
            volumes = [float(k[5]) for k in klines]
        except (IndexError, ValueError):
            return 0.0

        avg_vol     = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 0.0
        current_vol = volumes[-1]

        if avg_vol <= 0:
            return 0.0

        ratio = current_vol / avg_vol
        return min(100.0, (ratio - 1.0) * 33.3)

    @staticmethod
    def _calculate_spread_pct(ticker: Any) -> float:
        """
        Spread bid/ask como % do mid-price.
        0.1% spread → score 10, 1% spread → score 100.

        KuCoin level1 ticker: {"bestBid": "...", "bestAsk": "...", ...}
        """
        try:
            bid = float(ticker.get("bestBid", 0))
            ask = float(ticker.get("bestAsk", 0))
            if bid <= 0:
                return 0.0
            spread_pct = ((ask - bid) / bid) * 100.0
            return min(100.0, spread_pct * 100.0)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0
