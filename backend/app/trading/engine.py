"""
TradingEngine - Camada 3

Orquestra:
- KuCoinRawClient (camada 1)
- PayloadNormalizer (camada 2)
- Lógica de trading

Responsabilidades:
- Converter business requests em API calls
- Normalizar respostas
- Manter estado mínimo
- Não trata concorrência (OrderManager faz isso)
"""

from __future__ import annotations

import logging
import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.exchanges.kucoin.client import KuCoinRawClient, KuCoinAPIError
from app.exchanges.kucoin.normalizer import (
    PayloadNormalizer,
    NormalizedOrder,
    NormalizedCandle,
    NormalizedBalance,
)
from app.trading.circuit_breaker import ExchangeHealthMonitor, CircuitOpenError
from app.trading.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Engine de trading que coordena cliente + normalizer.
    
    Exemplo:
    ```python
    engine = TradingEngine(kucoin_client, account_id)
    
    order = await engine.place_market_order(
        symbol="BTC-USDT",
        side="buy",
        size=Decimal("0.1"),
        take_profit=Decimal("35000"),
        stop_loss=Decimal("30000")
    )
    
    # Resultado já normalizado
    assert isinstance(order, NormalizedOrder)
    assert order.status == OrderStatus.OPEN
    
    # Monitora
    updated = await engine.get_order(order.order_id)
    ```
    """

    def __init__(
        self,
        kucoin_client: KuCoinRawClient,
        account_id: str,
        circuit_breaker: Optional[ExchangeHealthMonitor] = None,
        risk_manager: Optional[RiskManager] = None,
    ):
        self.client          = kucoin_client
        self.account_id      = account_id
        self.normalizer      = PayloadNormalizer()
        self._circuit        = circuit_breaker
        self._risk_manager   = risk_manager

        logger.info(f"TradingEngine inicializado para account {account_id}")

    # ==================== GUARD DE SEGURANCA ====================

    def _guard_trade(self, user_id: Optional[str] = None) -> None:
        """
        Verificacao de seguranca executada antes de qualquer operacao de ordem.
        Hierarquia (mais alta para mais baixa):
          1. Kill-switch do RiskManager (para todo e qualquer trade)
          2. Circuit Breaker da exchange (falhas externas)

        Lanca excecao descritiva se qualquer guard falhar.
        Obrigatorio chamar em place_market_order e place_limit_order.
        """
        # ── 1. Kill-switch (nivel mais alto) ──────────────────────────────────
        if self._risk_manager and user_id:
            if self._risk_manager.is_kill_switched(user_id):
                raise PermissionError(
                    f"Kill-switch ativo para user={user_id}. "
                    f"Todos os trades estao bloqueados. "
                    f"Contate o administrador para reativar."
                )

        # ── 2. Circuit Breaker da exchange ────────────────────────────────────
        if self._circuit:
            self._circuit.pre_request()  # lanca CircuitOpenError se OPEN
    
    # ==================== CONTAS ====================
    
    async def get_balance(
        self,
        currency: Optional[str] = None,
    ) -> List[NormalizedBalance]:
        """Obtém saldo formatado."""
        try:
            raw_balances = await self.client.get_account_balance(
                self.account_id,
                currency=currency
            )
            
            normalized = [
                self.normalizer.normalize_balance(bal, self.account_id)
                for bal in raw_balances
            ]
            
            logger.info(f"✅ Saldo obtido: {len(normalized)} assets")
            return normalized
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter saldo: {e}")
            raise
    
    # ==================== ORDERS ====================
    
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        client_oid: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> NormalizedOrder:
        """Coloca ordem de mercado normalizada."""
        # Guard de seguranca: kill-switch + circuit breaker
        self._guard_trade(user_id)

        try:
            raw_response = await self.client.place_market_order(
                symbol=symbol,
                side=side,
                size=size,
                take_profit=take_profit,
                stop_loss=stop_loss,
                client_oid=client_oid,
            )

            # Busca ordem completa para normalizacao
            order_id = raw_response.get("orderId")
            order_detail = await self.client.get_order(order_id)

            # Normaliza
            normalized = self.normalizer.normalize_order(order_detail)

            if self._circuit:
                self._circuit.record_success()

            logger.info(
                f"Market order colocada: "
                f"{side} {size} {symbol} @ {order_id}"
            )
            return normalized

        except (PermissionError, CircuitOpenError):
            raise  # nao registrar no circuit breaker — sao guards locais
        except KuCoinAPIError as e:
            if self._circuit:
                self._circuit.record_failure(e)
            logger.error(f"API Error: {e.code} - {e.message}")
            raise
        except Exception as e:
            if self._circuit:
                self._circuit.record_failure(e)
            logger.error(f"Erro ao colocar ordem: {e}")
            raise
    
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        price: Decimal,
        client_oid: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> NormalizedOrder:
        """Coloca ordem limite normalizada."""
        # Guard de seguranca: kill-switch + circuit breaker
        self._guard_trade(user_id)

        try:
            raw_response = await self.client.place_limit_order(
                symbol=symbol,
                side=side,
                size=size,
                price=price,
                client_oid=client_oid,
            )

            # Busca ordem completa
            order_id = raw_response.get("orderId")
            order_detail = await self.client.get_order(order_id)

            # Normaliza
            normalized = self.normalizer.normalize_order(order_detail)

            if self._circuit:
                self._circuit.record_success()

            logger.info(
                f"Limit order colocada: "
                f"{side} {size} {symbol} @ {price} ({order_id})"
            )
            return normalized

        except (PermissionError, CircuitOpenError):
            raise
        except Exception as e:
            if self._circuit:
                self._circuit.record_failure(e)
            logger.error(f"❌ Erro ao colocar ordem limite: {e}")
            raise
    
    async def get_order(self, order_id: str) -> NormalizedOrder:
        """Obtém ordem normalizada."""
        try:
            raw_order = await self.client.get_order(order_id)
            normalized = self.normalizer.normalize_order(raw_order)
            return normalized
        except Exception as e:
            logger.error(f"❌ Erro ao obter ordem: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancela ordem."""
        try:
            await self.client.cancel_order(order_id)
            logger.info(f"✅ Ordem cancelada: {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao cancelar ordem: {e}")
            return False
    
    async def get_orders(self, symbol: Optional[str] = None) -> List[NormalizedOrder]:
        """Lista ordens abertas."""
        try:
            raw_orders = await self.client.get_orders(symbol=symbol, status="active")
            normalized = [
                self.normalizer.normalize_order(order)
                for order in raw_orders
            ]
            return normalized
        except Exception as e:
            logger.error(f"❌ Erro ao listar ordens: {e}")
            raise
    
    # ==================== MARKET DATA ====================
    
    async def get_ticker(self, symbol: str) -> Dict[str, Decimal]:
        """Obtém ticker current."""
        try:
            raw_ticker = await self.client.get_ticker(symbol)
            
            return {
                "bid": Decimal(raw_ticker.get("bestBid", "0")),
                "ask": Decimal(raw_ticker.get("bestAsk", "0")),
                "last": Decimal(raw_ticker.get("price", "0")),
                "high": Decimal(raw_ticker.get("high", "0")),
                "low": Decimal(raw_ticker.get("low", "0")),
                "volume": Decimal(raw_ticker.get("volValue", "0")),
            }
        except Exception as e:
            logger.error(f"❌ Erro ao obter ticker: {e}")
            raise
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1min",
        limit: int = 100,
    ) -> List[NormalizedCandle]:
        """Obtém candles normalizados."""
        try:
            raw_candles = await self.client.get_klines(symbol, interval)
            
            # KuCoin retorna em ordem crescente, pegamos últimas N
            normalized = [
                self.normalizer.normalize_candle(candle)
                for candle in raw_candles[-limit:]
            ]
            
            return normalized
        except Exception as e:
            logger.error(f"❌ Erro ao obter candles: {e}")
            raise
    
    # ==================== CLEANUP ====================
    
    async def close(self):
        """Fecha recursos."""
        await self.client.close()
        logger.info("✅ TradingEngine fechado")
