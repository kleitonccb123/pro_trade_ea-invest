"""
EAConfig — Configuração completa do PricePro Money-EA

Espelha exatamente cada `input` do EA em MQL5, convertido para Python.
Cada campo possui valor padrão idêntico ao MT5 para facilitar migração.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List


# ---------------------------------------------------------------------------
# Nível individual do grid de proteções
# ---------------------------------------------------------------------------

@dataclass
class GridLevel:
    """Representa um nível do grid (distância em pontos + volume)."""
    distance_points: float   # distância do preço médio, em pontos (equivalente a pips)
    volume: Decimal          # tamanho de lote a abrir neste nível


# ---------------------------------------------------------------------------
# Configuração principal do EA
# ---------------------------------------------------------------------------

@dataclass
class EAConfig:
    """
    Todos os parâmetros do PricePro Money-EA.

    Equivalência com MQL5 inputs:
    ─────────────────────────────────────────────────────────────────────────
    AtivarEA                → active
    ModoDebug               → debug
    UsarRSI                 → use_rsi
    UsarRSI_A_favor_Tendencia → rsi_with_trend
    UsarForcaCandle         → use_candle_strength
    UsarVolume              → use_volume
    UsarRangeAdaptativo     → use_range_adaptive
    UsarLoteFixo            → use_fixed_lot
    LoteFixo                → fixed_lot
    UsarLotePorRisco        → use_risk_lot
    PercentualRisco         → risk_percent
    AtivarMediaMovel        → use_ema
    PeriodoMediaMovel       → ema_period
    TipoMedia               → ema_type  ("ema" | "sma" | "wma" | "dema" | "tema")
    PeriodoRSI              → rsi_period
    RSI_Sobrecomprado       → rsi_overbought
    RSI_Sobrevendido        → rsi_oversold
    CorpoCandleMinimo       → candle_body_min_pct
    VolumeMinimo            → volume_min_ratio
    PeriodoRange            → range_period
    MultiplicadorRange      → range_multiplier
    TP_USD                  → tp_usd
    SL_USD                  → sl_usd
    AtivarProtecoes         → use_grid
    MaxProtecoes            → max_grid_levels
    TempoEntreProtecoes     → grid_delay_s
    DistanciasProtecao      → grid_distances (pontos)
    VolumesProtecao         → grid_volumes
    MetaDiaria              → daily_target_usd
    LimitePercaDiaria       → daily_loss_limit_usd
    DrawdownEmergencia      → emergency_drawdown_pct
    NumeroMagico            → magic_number (identificador único da estratégia)
    BreakevenActivatePoints → breakeven_activate_points
    AtivarTrailingPorCandle → use_trailing_candle
    MinMovePoints           → min_move_points
    HabilitarScalper        → use_scalper
    IntervaloScalper        → scalper_interval_s
    ─────────────────────────────────────────────────────────────────────────
    """

    # ── Identificação do usuário (multi-tenant) ──────────────────────────────
    user_id: str = "default"

    # ── Símbolo principal (ex: "BTC-USDT") ──────────────────────────────────
    symbol: str = "BTC-USDT"
    market_type: str = "spot"       # "spot" | "futures"

    # ── Ativação ──────────────────────────────────────────────────────────────
    active: bool = True
    debug: bool = True

    # ── Filtros ───────────────────────────────────────────────────────────────
    use_rsi: bool = True
    rsi_with_trend: bool = False    # False = retração; True = impulso
    use_candle_strength: bool = True
    use_volume: bool = True
    use_range_adaptive: bool = True

    # ── Volume/Lote ───────────────────────────────────────────────────────────
    use_fixed_lot: bool = True
    fixed_lot: Decimal = Decimal("0.05")
    use_risk_lot: bool = False
    risk_percent: float = 10.0
    dynamic_lot_pct: float = 1.0        # % do saldo para lot dinâmico

    # ── EMA ───────────────────────────────────────────────────────────────────
    use_ema: bool = True
    ema_period: int = 55
    ema_type: str = "ema"           # "ema" | "sma" | "wma"
    ma_type: str = "ema"            # alias de ema_type usado internamente

    # ── RSI ───────────────────────────────────────────────────────────────────
    rsi_period: int = 9
    rsi_overbought: float = 66.0
    rsi_oversold: float = 33.0

    # ── Força do candle ───────────────────────────────────────────────────────
    candle_body_min_pct: float = 40.0   # corpo mínimo em % do range total

    # ── Volume ────────────────────────────────────────────────────────────────
    volume_min_ratio: float = 0.55      # razão volume atual / média 3 candles

    # ── Range adaptativo ──────────────────────────────────────────────────────
    range_period: int = 9
    range_multiplier: float = 1.15     # range atual deve ser ≥ multiplicador × média

    # ── TP / SL em USD ────────────────────────────────────────────────────────
    tp_usd: float = 10.0               # $ 0 = desativar
    sl_usd: float = 10.0               # $ 0 = desativar

    # ── Grid de proteções ────────────────────────────────────────────────────
    use_grid: bool = True
    max_grid_levels: int = 25
    grid_delay_s: int = 3
    # Distâncias das proteções em pontos (equivale a pips×10 para 5 dígitos)
    grid_distances: List[float] = field(default_factory=lambda: [
        900, 2100, 3800, 4100, 4900, 5200, 6400, 6800,
        8000, 9300, 10700, 12200, 13800, 15500, 17300, 19200, 21200,
    ])
    # Volumes das proteções (mesmo índice de grid_distances)
    grid_volumes: List[Decimal] = field(default_factory=lambda: [
        Decimal("0.05"), Decimal("0.05"), Decimal("0.05"), Decimal("0.05"),
        Decimal("0.07"), Decimal("0.07"), Decimal("0.09"), Decimal("0.09"),
        Decimal("0.16"), Decimal("0.16"), Decimal("0.16"), Decimal("0.32"),
        Decimal("0.32"), Decimal("0.32"), Decimal("0.64"), Decimal("0.64"),
        Decimal("0.64"),
    ])

    # ── Gestão financeira ─────────────────────────────────────────────────────
    daily_target_usd: float = 0.0      # 0 = desabilitado
    daily_loss_limit_usd: float = 0.0  # 0 = desabilitado
    emergency_drawdown_pct: float = 50.0

    # ── Identificação ─────────────────────────────────────────────────────────
    magic_number: int = 20260112       # identifica ordens desta estratégia

    # ── Breakeven + Trailing ──────────────────────────────────────────────────
    breakeven_activate_points: int = 500
    use_trailing_candle: bool = True
    min_move_points: int = 1

    # ── Scalper ───────────────────────────────────────────────────────────────
    use_scalper: bool = True
    scalper_interval_s: int = 5

    # ── Timeframe principal ───────────────────────────────────────────────────
    timeframe: str = "15min"           # KuCoin: "1min","5min","15min","1hour","1day"

    # ── Tolerância de preço (em decimais, ex: 5 dígitos → 0.00001) ───────────
    price_tick: Decimal = Decimal("0.00001")

    # ── Aquecimento de indicadores (barras históricas) ────────────────────────
    indicator_warmup_bars: int = 100

    # ── Grid levels pré-construídos (sobrepõe grid_distances+grid_volumes) ────
    grid_levels: List[GridLevel] = field(default_factory=list)

    # ---------------------------------------------------------------------------
    #  Helpers
    # ---------------------------------------------------------------------------

    def get_grid_levels(self) -> List[GridLevel]:
        """Retorna lista de GridLevel. Usa grid_levels se preenchido, senão combina distâncias+volumes."""
        if self.grid_levels:
            return self.grid_levels[:self.max_grid_levels]
        count = min(len(self.grid_distances), len(self.grid_volumes), self.max_grid_levels)
        return [
            GridLevel(distance_points=self.grid_distances[i], volume=self.grid_volumes[i])
            for i in range(count)
        ]

    def lot_size(self, balance_usdt: Decimal) -> Decimal:
        """Calcula tamanho de lote baseado na configuração."""
        if self.use_fixed_lot:
            return self.fixed_lot
        if self.use_risk_lot:
            risk_amount = balance_usdt * Decimal(str(self.risk_percent / 100.0))
            # Estimativa conservadora: 1000 USDT de risco ≈ 1 lote
            lot = risk_amount / Decimal("1000")
            return max(Decimal("0.01"), round(lot, 2))
        return self.fixed_lot

    def distance_to_price(self, distance_points: float, price_tick: Decimal) -> Decimal:
        """
        Converte distância em pontos para diferença de preço.
        No MT5 com 5 dígitos: 1 pip = 10 pontos = 10 × _Point.
        Na KuCoin usamos price_tick como equivalente ao _Point.
        """
        return Decimal(str(distance_points)) * price_tick

    def usd_to_price_distance(self, usd: float, volume: Decimal, tick_value_per_lot: Decimal) -> Decimal:
        """
        Converte valor em USD em distância de preço.

        Fórmula: price_diff = usd / (tick_value_per_lot × volume)
        tick_value_per_lot: valor em USD de 1 lote para 1 pip de movimento.
        Para BTC-USDT Spot: tick_value ≈ 1 USDT por 1 tick por lot.
        """
        if usd <= 0 or volume <= 0 or tick_value_per_lot <= 0:
            return Decimal("0")
        return Decimal(str(usd)) / (tick_value_per_lot * volume)
