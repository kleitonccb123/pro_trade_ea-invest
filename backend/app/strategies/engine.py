"""
StrategyEngine - Camada 4

Executa estratégias de forma ISOLADA.

Responsabilidades:
- Rodar estratégia por bot
- Cada bot em sua própria coroutine
- Não trava outras estratégias
- Comunicação via fila (não compartilha estado)
"""

from __future__ import annotations

import logging
import asyncio
from typing import Dict, Optional, List, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Sinal de entrada gerado pela estratégia."""
    symbol: str
    side: str  # "buy" or "sell"
    size: Decimal
    confidence: float  # 0.0 - 1.0
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    reason: Optional[str] = None


class StrategyBase(ABC):
    """Base class para todas as estratégias."""
    
    @abstractmethod
    async def analyze(self, market_data: List[Any]) -> Optional[TradeSignal]:
        """
        Analisa dados de mercado e retorna sinal.
        
        Args:
            market_data: Últimas N candles
        
        Returns:
            TradeSignal ou None se sem sinal
        """
        pass


class SMACrossoverStrategy(StrategyBase):
    """Exemplo: SMA 20 x SMA 50 crossover."""
    
    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    async def analyze(self, candles: List[Any]) -> Optional[TradeSignal]:
        """Implementa lógica SMA crossover."""
        if len(candles) < self.slow_period + 1:
            return None  # Dados insuficientes
        
        closes = [float(c.close) for c in candles]
        
        # Calcula SMAs
        sma_fast = sum(closes[-self.fast_period:]) / self.fast_period
        sma_slow = sum(closes[-self.slow_period:]) / self.slow_period
        
        prev_sma_fast = sum(closes[-self.fast_period-1:-1]) / self.fast_period
        prev_sma_slow = sum(closes[-self.slow_period-1:-1]) / self.slow_period
        
        # Detecta crossover
        if prev_sma_fast <= prev_sma_slow and sma_fast > sma_slow:
            # Golden cross: BUY
            confidence = min(1.0, (sma_fast - sma_slow) / sma_slow * 100)
            
            return TradeSignal(
                symbol=candles[-1].symbol if hasattr(candles[-1], 'symbol') else "BTC-USDT",
                side="buy",
                size=Decimal("0.1"),
                confidence=confidence,
                take_profit=Decimal(closes[-1]) * Decimal("1.04"),  # +4%
                stop_loss=Decimal(closes[-1]) * Decimal("0.98"),    # -2%
                reason=f"SMA Golden Cross: Fast={sma_fast:.2f}, Slow={sma_slow:.2f}"
            )
        
        elif prev_sma_fast >= prev_sma_slow and sma_fast < sma_slow:
            # Death cross: SELL
            confidence = min(1.0, (sma_slow - sma_fast) / sma_slow * 100)
            
            return TradeSignal(
                symbol="BTC-USDT",
                side="sell",
                size=Decimal("0.1"),
                confidence=confidence,
                reason=f"SMA Death Cross: Fast={sma_fast:.2f}, Slow={sma_slow:.2f}"
            )
        
        return None


class StrategyEngine:
    """
    Executa estratégias de forma isolada.
    
    Cada bot roda em sua própria coroutine.
    """
    
    def __init__(self):
        self.active_bots: Dict[str, asyncio.Task] = {}
        self.signal_callbacks: Dict[str, List[Callable]] = {}
    
    async def run_bot_strategy(
        self,
        bot_id: str,
        strategy: StrategyBase,
        market_data_provider: Callable,
        interval_seconds: float = 60,
    ):
        """
        Executa estratégia para um bot repetidamente.
        
        Args:
            bot_id: Identificador único do bot
            strategy: Instância da estratégia
            market_data_provider: Função async que retorna candles
            interval_seconds: Intervalo entre análises
        """
        logger.info(f"🤖 Iniciando bot {bot_id}")
        
        try:
            while True:
                try:
                    # Obtém dados de mercado
                    market_data = await market_data_provider(bot_id)
                    
                    # Analisa
                    signal = await strategy.analyze(market_data)
                    
                    # Se sinal, notifica
                    if signal:
                        logger.info(f"🎯 Bot {bot_id}: Sinal {signal.side} com {signal.confidence*100:.1f}% confiança")
                        await self._notify_signal(bot_id, signal)
                    
                    # Aguarda próximo intervalo
                    await asyncio.sleep(interval_seconds)
                    
                except asyncio.CancelledError:
                    logger.info(f"🛑 Bot {bot_id} cancelado")
                    raise
                except Exception as e:
                    logger.error(f"❌ Erro no bot {bot_id}: {e}")
                    await asyncio.sleep(5)  # Retry após curta espera
                    
        except asyncio.CancelledError:
            logger.info(f"✅ Bot {bot_id} finalizado gracefully")
        finally:
            if bot_id in self.active_bots:
                del self.active_bots[bot_id]
    
    async def start_bot(
        self,
        bot_id: str,
        strategy: StrategyBase,
        market_data_provider: Callable,
    ):
        """Inicia um bot."""
        if bot_id in self.active_bots:
            logger.warning(f"⚠️ Bot {bot_id} já está rodando")
            return
        
        task = asyncio.create_task(
            self.run_bot_strategy(bot_id, strategy, market_data_provider)
        )
        self.active_bots[bot_id] = task
        logger.info(f"✅ Bot {bot_id} iniciado")
    
    async def stop_bot(self, bot_id: str):
        """Para um bot."""
        if bot_id not in self.active_bots:
            logger.warning(f"⚠️ Bot {bot_id} não está rodando")
            return
        
        task = self.active_bots[bot_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        logger.info(f"✅ Bot {bot_id} parado")
    
    def subscribe_signal(self, bot_id: str, callback: Callable):
        """Subscreve a sinais de um bot."""
        if bot_id not in self.signal_callbacks:
            self.signal_callbacks[bot_id] = []
        self.signal_callbacks[bot_id].append(callback)
    
    async def _notify_signal(self, bot_id: str, signal: TradeSignal):
        """Notifica todos os subscribers de um sinal."""
        if bot_id not in self.signal_callbacks:
            return
        
        for callback in self.signal_callbacks[bot_id]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"❌ Erro ao chamar callback: {e}")


# Instância global
strategy_engine = StrategyEngine()
