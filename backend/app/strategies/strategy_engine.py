"""
Strategy Engine - Motor de Estrat?gias de Trading

Implementa templates de estrat?gias profissionais:
1. Grid Trading - Compra/vende em intervalos de pre?o
2. DCA (Dollar Cost Averaging) - Compras regulares independente do pre?o
3. RSI Strategy - Baseado no ?ndice de For?a Relativa
4. MACD Strategy - Baseado em Moving Average Convergence Divergence

Cada estrat?gia implementa a interface StrategyBase com:
- analyze(): Analisa mercado e retorna sinal
- calculate_position(): Calcula tamanho da posi??o
- get_entry_conditions(): Condi??es de entrada
- get_exit_conditions(): Condi??es de sa?da

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional, List
import numpy as np

logger = logging.getLogger(__name__)


# ==================== ENUMS & DATA CLASSES ====================

class Signal(str, Enum):
    """Sinais de trading."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class StrategyType(str, Enum):
    """Tipos de estrat?gia dispon?veis."""
    GRID = "grid"
    DCA = "dca"
    RSI = "rsi"
    MACD = "macd"
    COMBINED = "combined"


@dataclass
class MarketData:
    """Dados de mercado para an?lise."""
    symbol: str
    current_price: Decimal
    high_24h: Decimal
    low_24h: Decimal
    volume_24h: Decimal
    price_change_24h: float
    
    # Hist?rico de pre?os (OHLCV)
    closes: List[float] = field(default_factory=list)
    highs: List[float] = field(default_factory=list)
    lows: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)


@dataclass
class StrategySignal:
    """Resultado da an?lise de estrat?gia."""
    signal: Signal
    confidence: float  # 0-100
    strategy_type: StrategyType
    
    # Recomenda??es
    recommended_action: str
    entry_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    position_size_percent: float = 0.0
    
    # Indicadores calculados
    indicators: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""


@dataclass
class GridConfig:
    """Configura??o para Grid Trading."""
    upper_price: Decimal
    lower_price: Decimal
    grid_levels: int = 10
    total_investment: Decimal = Decimal("1000")
    arithmetic: bool = True  # True = grids iguais, False = geom?trico


@dataclass
class DCAConfig:
    """Configura??o para DCA."""
    investment_amount: Decimal = Decimal("100")
    frequency_hours: int = 24  # Intervalo entre compras
    max_purchases: int = 30   # M?ximo de compras
    price_drop_multiplier: float = 1.5  # Comprar mais se cair X%


@dataclass
class RSIConfig:
    """Configura??o para RSI Strategy."""
    period: int = 14
    overbought: float = 70.0
    oversold: float = 30.0
    confirmation_candles: int = 2


@dataclass
class MACDConfig:
    """Configura??o para MACD Strategy."""
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9


# ==================== TECHNICAL INDICATORS ====================

class TechnicalIndicators:
    """C?lculo de indicadores t?cnicos."""
    
    @staticmethod
    def sma(prices: List[float], period: int) -> List[float]:
        """Simple Moving Average."""
        if len(prices) < period:
            return []
        
        result = []
        for i in range(period - 1, len(prices)):
            avg = sum(prices[i - period + 1:i + 1]) / period
            result.append(avg)
        return result
    
    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """Exponential Moving Average."""
        if len(prices) < period:
            return []
        
        multiplier = 2 / (period + 1)
        ema_values = [sum(prices[:period]) / period]  # SMA inicial
        
        for price in prices[period:]:
            ema_values.append(
                (price - ema_values[-1]) * multiplier + ema_values[-1]
            )
        
        return ema_values
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[float]:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return []
        
        # Calcular mudan?as de pre?o
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        # M?dia inicial
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rsi_values = []
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi_values.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))
        
        return rsi_values
    
    @staticmethod
    def macd(
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, List[float]]:
        """MACD (Moving Average Convergence Divergence)."""
        if len(prices) < slow + signal:
            return {"macd": [], "signal": [], "histogram": []}
        
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)
        
        # Alinhar tamanhos
        offset = len(ema_fast) - len(ema_slow)
        ema_fast = ema_fast[offset:]
        
        # MACD line
        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        
        # Signal line
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        
        # Alinhar
        offset = len(macd_line) - len(signal_line)
        macd_line = macd_line[offset:]
        
        # Histogram
        histogram = [m - s for m, s in zip(macd_line, signal_line)]
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    @staticmethod
    def bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, List[float]]:
        """Bollinger Bands."""
        if len(prices) < period:
            return {"upper": [], "middle": [], "lower": []}
        
        middle = TechnicalIndicators.sma(prices, period)
        
        upper = []
        lower = []
        
        for i in range(len(middle)):
            idx = i + period - 1
            window = prices[idx - period + 1:idx + 1]
            std = np.std(window)
            
            upper.append(middle[i] + std_dev * std)
            lower.append(middle[i] - std_dev * std)
        
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower
        }


# ==================== STRATEGY BASE ====================

class StrategyBase(ABC):
    """Classe base para todas as estrat?gias."""
    
    def __init__(self, name: str, strategy_type: StrategyType):
        self.name = name
        self.strategy_type = strategy_type
        self.indicators = TechnicalIndicators()
    
    @abstractmethod
    async def analyze(self, market_data: MarketData) -> StrategySignal:
        """Analisa o mercado e retorna um sinal."""
        pass
    
    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """Retorna schema de configura??o da estrat?gia."""
        pass
    
    def calculate_position_size(
        self,
        balance: Decimal,
        risk_percent: float = 2.0,
        stop_loss_percent: float = 5.0
    ) -> Decimal:
        """Calcula tamanho da posi??o baseado em risco."""
        # Position sizing baseado em risco fixo
        # Risk = Balance * Risk% = Position * StopLoss%
        # Position = (Balance * Risk%) / StopLoss%
        
        risk_amount = balance * Decimal(str(risk_percent / 100))
        position = risk_amount / Decimal(str(stop_loss_percent / 100))
        
        # Limitar a 50% do balan?o
        max_position = balance * Decimal("0.5")
        return min(position, max_position)


# ==================== GRID TRADING STRATEGY ====================

class GridTradingStrategy(StrategyBase):
    """
    Grid Trading Strategy.
    
    Cria uma grade de ordens de compra e venda em intervalos de pre?o.
    Lucra com a volatilidade do mercado.
    
    Ideal para: Mercados laterais (ranging)
    """
    
    def __init__(self, config: GridConfig = None):
        super().__init__("Grid Trading", StrategyType.GRID)
        self.config = config or GridConfig(
            upper_price=Decimal("50000"),
            lower_price=Decimal("40000"),
            grid_levels=10,
        )
    
    async def analyze(self, market_data: MarketData) -> StrategySignal:
        """Analisa se o pre?o est? dentro da grade."""
        current = float(market_data.current_price)
        upper = float(self.config.upper_price)
        lower = float(self.config.lower_price)
        
        # Verificar se pre?o est? dentro do range
        in_range = lower <= current <= upper
        
        # Calcular posi??o na grade
        if in_range:
            position_in_grid = (current - lower) / (upper - lower)
            
            # Sinal baseado na posi??o
            if position_in_grid < 0.3:
                signal = Signal.BUY
                confidence = 70 + (0.3 - position_in_grid) * 100
            elif position_in_grid > 0.7:
                signal = Signal.SELL
                confidence = 70 + (position_in_grid - 0.7) * 100
            else:
                signal = Signal.HOLD
                confidence = 50
        else:
            signal = Signal.HOLD
            confidence = 30
            position_in_grid = 0
        
        # Calcular n?veis da grade
        grid_size = (upper - lower) / self.config.grid_levels
        grid_levels = [lower + i * grid_size for i in range(self.config.grid_levels + 1)]
        
        return StrategySignal(
            signal=signal,
            confidence=min(confidence, 100),
            strategy_type=self.strategy_type,
            recommended_action=f"{'Comprar' if signal == Signal.BUY else 'Vender' if signal == Signal.SELL else 'Aguardar'}",
            entry_price=market_data.current_price,
            indicators={
                "position_in_grid": position_in_grid,
                "grid_levels": len(grid_levels),
                "in_range": 1 if in_range else 0,
            },
            reason=f"Pre?o {'dentro' if in_range else 'fora'} do range da grade ({position_in_grid*100:.1f}%)"
        )
    
    def get_grid_orders(self, current_price: Decimal) -> List[Dict[str, Any]]:
        """Gera lista de ordens para a grade."""
        upper = float(self.config.upper_price)
        lower = float(self.config.lower_price)
        levels = self.config.grid_levels
        
        if self.config.arithmetic:
            # Grade aritm?tica (intervalos iguais)
            step = (upper - lower) / levels
            prices = [lower + i * step for i in range(levels + 1)]
        else:
            # Grade geom?trica (percentuais iguais)
            ratio = (upper / lower) ** (1 / levels)
            prices = [lower * (ratio ** i) for i in range(levels + 1)]
        
        current = float(current_price)
        investment_per_grid = float(self.config.total_investment) / levels
        
        orders = []
        for price in prices:
            if price < current:
                # Ordem de compra abaixo do pre?o atual
                orders.append({
                    "side": "buy",
                    "price": price,
                    "amount": investment_per_grid / price,
                })
            elif price > current:
                # Ordem de venda acima do pre?o atual
                orders.append({
                    "side": "sell",
                    "price": price,
                    "amount": investment_per_grid / price,
                })
        
        return orders
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "upper_price": {"type": "number", "description": "Limite superior da grade"},
            "lower_price": {"type": "number", "description": "Limite inferior da grade"},
            "grid_levels": {"type": "integer", "default": 10, "min": 3, "max": 100},
            "total_investment": {"type": "number", "description": "Investimento total"},
            "arithmetic": {"type": "boolean", "default": True},
        }


# ==================== DCA STRATEGY ====================

class DCAStrategy(StrategyBase):
    """
    DCA (Dollar Cost Averaging) Strategy.
    
    Compra regularmente independente do pre?o, com multiplicador
    em quedas para melhorar pre?o m?dio.
    
    Ideal para: Acumula??o de longo prazo
    """
    
    def __init__(self, config: DCAConfig = None):
        super().__init__("DCA - Dollar Cost Averaging", StrategyType.DCA)
        self.config = config or DCAConfig()
        self.purchases_made = 0
        self.total_invested = Decimal("0")
        self.total_coins = Decimal("0")
    
    async def analyze(self, market_data: MarketData) -> StrategySignal:
        """Analisa condi??es para pr?xima compra DCA."""
        current_price = float(market_data.current_price)
        
        # Calcular pre?o m?dio atual
        avg_price = float(self.total_invested / self.total_coins) if self.total_coins > 0 else current_price
        
        # Verificar se ? momento de comprar mais (queda significativa)
        price_change = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        
        # Calcular quantidade a comprar
        base_amount = float(self.config.investment_amount)
        
        if price_change < -10:
            # Pre?o caiu mais de 10% - comprar mais
            multiplier = min(self.config.price_drop_multiplier, 3.0)
            buy_amount = base_amount * multiplier
            signal = Signal.STRONG_BUY
            confidence = 90
            reason = f"Pre?o {abs(price_change):.1f}% abaixo da m?dia - oportunidade de DCA agressivo"
        elif price_change < -5:
            buy_amount = base_amount * 1.5
            signal = Signal.BUY
            confidence = 75
            reason = f"Pre?o {abs(price_change):.1f}% abaixo da m?dia - DCA com bonus"
        else:
            buy_amount = base_amount
            signal = Signal.BUY
            confidence = 60
            reason = "DCA regular programado"
        
        # Verificar se atingiu m?ximo de compras
        if self.purchases_made >= self.config.max_purchases:
            signal = Signal.HOLD
            confidence = 50
            reason = f"M?ximo de {self.config.max_purchases} compras atingido"
        
        return StrategySignal(
            signal=signal,
            confidence=confidence,
            strategy_type=self.strategy_type,
            recommended_action=f"Comprar ${buy_amount:.2f}",
            entry_price=market_data.current_price,
            position_size_percent=buy_amount / float(self.config.investment_amount * self.config.max_purchases) * 100,
            indicators={
                "purchases_made": self.purchases_made,
                "total_invested": float(self.total_invested),
                "avg_price": avg_price,
                "price_vs_avg": price_change,
            },
            reason=reason
        )
    
    def record_purchase(self, price: Decimal, amount: Decimal):
        """Registra uma compra realizada."""
        self.purchases_made += 1
        self.total_invested += price * amount
        self.total_coins += amount
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "investment_amount": {"type": "number", "default": 100},
            "frequency_hours": {"type": "integer", "default": 24, "min": 1},
            "max_purchases": {"type": "integer", "default": 30, "min": 1},
            "price_drop_multiplier": {"type": "number", "default": 1.5, "min": 1.0, "max": 5.0},
        }


# ==================== RSI STRATEGY ====================

class RSIStrategy(StrategyBase):
    """
    RSI (Relative Strength Index) Strategy.
    
    Compra quando RSI est? oversold (<30) e vende quando overbought (>70).
    
    Ideal para: Identificar revers?es de tend?ncia
    """
    
    def __init__(self, config: RSIConfig = None):
        super().__init__("RSI Strategy", StrategyType.RSI)
        self.config = config or RSIConfig()
    
    async def analyze(self, market_data: MarketData) -> StrategySignal:
        """Analisa RSI e retorna sinal."""
        if len(market_data.closes) < self.config.period + 10:
            return StrategySignal(
                signal=Signal.HOLD,
                confidence=0,
                strategy_type=self.strategy_type,
                recommended_action="Dados insuficientes",
                reason=f"Necess?rio {self.config.period + 10} candles, tem {len(market_data.closes)}"
            )
        
        # Calcular RSI
        rsi_values = self.indicators.rsi(market_data.closes, self.config.period)
        
        if not rsi_values:
            return StrategySignal(
                signal=Signal.HOLD,
                confidence=0,
                strategy_type=self.strategy_type,
                recommended_action="Erro no c?lculo",
                reason="N?o foi poss?vel calcular RSI"
            )
        
        current_rsi = rsi_values[-1]
        prev_rsi = rsi_values[-2] if len(rsi_values) > 1 else current_rsi
        
        # Analisar sinal
        if current_rsi < self.config.oversold:
            # RSI oversold - poss?vel compra
            if prev_rsi < current_rsi:  # RSI subindo
                signal = Signal.STRONG_BUY
                confidence = 85
                reason = f"RSI {current_rsi:.1f} oversold e subindo"
            else:
                signal = Signal.BUY
                confidence = 70
                reason = f"RSI {current_rsi:.1f} oversold"
        
        elif current_rsi > self.config.overbought:
            # RSI overbought - poss?vel venda
            if prev_rsi > current_rsi:  # RSI caindo
                signal = Signal.STRONG_SELL
                confidence = 85
                reason = f"RSI {current_rsi:.1f} overbought e caindo"
            else:
                signal = Signal.SELL
                confidence = 70
                reason = f"RSI {current_rsi:.1f} overbought"
        
        else:
            # RSI neutro
            signal = Signal.HOLD
            confidence = 50
            reason = f"RSI {current_rsi:.1f} em zona neutra"
        
        # Definir stop loss e take profit
        current_price = market_data.current_price
        if signal in [Signal.BUY, Signal.STRONG_BUY]:
            stop_loss = current_price * Decimal("0.95")  # 5% abaixo
            take_profit = current_price * Decimal("1.10")  # 10% acima
        elif signal in [Signal.SELL, Signal.STRONG_SELL]:
            stop_loss = current_price * Decimal("1.05")
            take_profit = current_price * Decimal("0.90")
        else:
            stop_loss = None
            take_profit = None
        
        return StrategySignal(
            signal=signal,
            confidence=confidence,
            strategy_type=self.strategy_type,
            recommended_action=self._get_action_text(signal),
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators={
                "rsi": current_rsi,
                "rsi_prev": prev_rsi,
                "oversold": self.config.oversold,
                "overbought": self.config.overbought,
            },
            reason=reason
        )
    
    def _get_action_text(self, signal: Signal) -> str:
        actions = {
            Signal.STRONG_BUY: "Compra forte recomendada",
            Signal.BUY: "Compra recomendada",
            Signal.HOLD: "Manter posi??o",
            Signal.SELL: "Venda recomendada",
            Signal.STRONG_SELL: "Venda forte recomendada",
        }
        return actions.get(signal, "Aguardar")
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "period": {"type": "integer", "default": 14, "min": 2, "max": 50},
            "overbought": {"type": "number", "default": 70, "min": 60, "max": 90},
            "oversold": {"type": "number", "default": 30, "min": 10, "max": 40},
        }


# ==================== MACD STRATEGY ====================

class MACDStrategy(StrategyBase):
    """
    MACD (Moving Average Convergence Divergence) Strategy.
    
    Compra quando MACD cruza acima da linha de sinal.
    Vende quando cruza abaixo.
    
    Ideal para: Identificar momentum e tend?ncia
    """
    
    def __init__(self, config: MACDConfig = None):
        super().__init__("MACD Strategy", StrategyType.MACD)
        self.config = config or MACDConfig()
    
    async def analyze(self, market_data: MarketData) -> StrategySignal:
        """Analisa MACD e retorna sinal."""
        min_candles = self.config.slow_period + self.config.signal_period + 5
        
        if len(market_data.closes) < min_candles:
            return StrategySignal(
                signal=Signal.HOLD,
                confidence=0,
                strategy_type=self.strategy_type,
                recommended_action="Dados insuficientes",
                reason=f"Necess?rio {min_candles} candles"
            )
        
        # Calcular MACD
        macd_data = self.indicators.macd(
            market_data.closes,
            self.config.fast_period,
            self.config.slow_period,
            self.config.signal_period
        )
        
        if not macd_data["macd"] or len(macd_data["macd"]) < 2:
            return StrategySignal(
                signal=Signal.HOLD,
                confidence=0,
                strategy_type=self.strategy_type,
                recommended_action="Erro no c?lculo",
                reason="N?o foi poss?vel calcular MACD"
            )
        
        macd_line = macd_data["macd"][-1]
        signal_line = macd_data["signal"][-1]
        histogram = macd_data["histogram"][-1]
        
        prev_macd = macd_data["macd"][-2]
        prev_signal = macd_data["signal"][-2]
        prev_histogram = macd_data["histogram"][-2]
        
        # Detectar cruzamentos
        bullish_cross = prev_macd < prev_signal and macd_line > signal_line
        bearish_cross = prev_macd > prev_signal and macd_line < signal_line
        
        # Analisar sinal
        if bullish_cross:
            signal = Signal.STRONG_BUY
            confidence = 85
            reason = "MACD cruzou acima da linha de sinal (bullish)"
        elif bearish_cross:
            signal = Signal.STRONG_SELL
            confidence = 85
            reason = "MACD cruzou abaixo da linha de sinal (bearish)"
        elif macd_line > signal_line and histogram > prev_histogram:
            signal = Signal.BUY
            confidence = 65
            reason = "MACD acima do sinal com momentum crescente"
        elif macd_line < signal_line and histogram < prev_histogram:
            signal = Signal.SELL
            confidence = 65
            reason = "MACD abaixo do sinal com momentum decrescente"
        else:
            signal = Signal.HOLD
            confidence = 50
            reason = "MACD sem sinal claro"
        
        current_price = market_data.current_price
        
        return StrategySignal(
            signal=signal,
            confidence=confidence,
            strategy_type=self.strategy_type,
            recommended_action=self._get_action_text(signal),
            entry_price=current_price,
            stop_loss=current_price * (Decimal("0.95") if signal in [Signal.BUY, Signal.STRONG_BUY] else Decimal("1.05")),
            take_profit=current_price * (Decimal("1.10") if signal in [Signal.BUY, Signal.STRONG_BUY] else Decimal("0.90")),
            indicators={
                "macd": macd_line,
                "signal": signal_line,
                "histogram": histogram,
                "bullish_cross": bullish_cross,
                "bearish_cross": bearish_cross,
            },
            reason=reason
        )
    
    def _get_action_text(self, signal: Signal) -> str:
        actions = {
            Signal.STRONG_BUY: "Compra forte - cruzamento bullish",
            Signal.BUY: "Compra - momentum positivo",
            Signal.HOLD: "Manter posi??o",
            Signal.SELL: "Venda - momentum negativo",
            Signal.STRONG_SELL: "Venda forte - cruzamento bearish",
        }
        return actions.get(signal, "Aguardar")
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "fast_period": {"type": "integer", "default": 12, "min": 5, "max": 50},
            "slow_period": {"type": "integer", "default": 26, "min": 10, "max": 100},
            "signal_period": {"type": "integer", "default": 9, "min": 3, "max": 30},
        }


# ==================== STRATEGY FACTORY ====================

class StrategyFactory:
    """Factory para criar inst?ncias de estrat?gias."""
    
    _strategies = {
        StrategyType.GRID: GridTradingStrategy,
        StrategyType.DCA: DCAStrategy,
        StrategyType.RSI: RSIStrategy,
        StrategyType.MACD: MACDStrategy,
    }
    
    @classmethod
    def create(cls, strategy_type: StrategyType, config: Dict[str, Any] = None) -> StrategyBase:
        """Cria uma inst?ncia de estrat?gia."""
        if strategy_type not in cls._strategies:
            raise ValueError(f"Estrat?gia desconhecida: {strategy_type}")
        
        strategy_class = cls._strategies[strategy_type]
        
        if config:
            # Criar config espec?fica
            if strategy_type == StrategyType.GRID:
                cfg = GridConfig(**config)
            elif strategy_type == StrategyType.DCA:
                cfg = DCAConfig(**config)
            elif strategy_type == StrategyType.RSI:
                cfg = RSIConfig(**config)
            elif strategy_type == StrategyType.MACD:
                cfg = MACDConfig(**config)
            else:
                cfg = None
            
            return strategy_class(cfg)
        
        return strategy_class()
    
    @classmethod
    def get_available_strategies(cls) -> List[Dict[str, Any]]:
        """Retorna lista de estrat?gias dispon?veis."""
        return [
            {
                "type": strategy_type.value,
                "name": cls._strategies[strategy_type]().name,
                "config_schema": cls._strategies[strategy_type]().get_config_schema(),
            }
            for strategy_type in cls._strategies
        ]
