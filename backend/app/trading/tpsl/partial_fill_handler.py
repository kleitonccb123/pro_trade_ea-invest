"""
PartialFillHandler — Trata recriação de TP/SL após fills parciais

Problema:
  A ordem de entrada pode ser preenchida em múltiplas partes (match events).
  O par TP/SL deve refletir o tamanho REALMENTE preenchido.

Estratégia:
  1. Primeiro fill (nenhum TpSlRecord ACTIVE existe):
     → Cria novo TpSlRecord e envia TP + SL pelo filledSize atual.

  2. Fill adicional (TpSlRecord ACTIVE já existe):
     → Cancela TP e SL atuais na exchange.
     → Cancela o TpSlRecord existente (status=CANCELED).
     → Recria novo TpSlRecord com o tamanho total (old + new fill),
       usando o preço médio ponderado como entryPrice.

Lock de 30s durante o resize para evitar execução concorrente.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Optional

from app.trading.tpsl.models import TpSlStatus
from app.trading.tpsl.repository import TpSlRepository
from app.trading.tpsl.price_calculator import TpSlPriceCalculator

logger = logging.getLogger(__name__)


class PartialFillHandler:
    """
    Coordena a recriação de TP/SL quando a posição é preenchida parcialmente.

    Uso:
    ```python
    handler = PartialFillHandler(tpsl_repo, spot_manager, calculator)

    # Chamado pelo ExecutionProcessor em cada evento WS 'match':
    await handler.handle(
        position_id=..., bot_id=..., user_id=..., strategy_id=...,
        symbol="BTC-USDT", side="buy",
        additional_filled_size=Decimal("0.05"),
        fill_price=Decimal("50000"),
        signal_id="sig123",
        tp_percent=Decimal("2.5"),
        sl_percent=Decimal("1.5"),
        tick_size=Decimal("0.1"),
    )
    ```
    """

    LOCK_TTL = 30  # segundos

    def __init__(
        self,
        tpsl_repo: TpSlRepository,
        spot_manager: Any,            # SpotTpSlManager
        calculator: Optional[TpSlPriceCalculator] = None,
        redis_client: Optional[Any] = None,
    ) -> None:
        self._repo       = tpsl_repo
        self._manager    = spot_manager
        self._calc       = calculator or TpSlPriceCalculator()
        self._redis      = redis_client
        self._mem_locks: dict = {}
        self._locks_mx   = asyncio.Lock()

    async def handle(
        self,
        position_id: str,
        bot_id: str,
        user_id: str,
        strategy_id: str,
        symbol: str,
        side: str,
        additional_filled_size: Decimal,
        fill_price: Decimal,
        signal_id: str,
        tp_percent: Decimal,
        sl_percent: Decimal,
        tick_size: Decimal = Decimal("0.01"),
        sl_buffer: Decimal = Decimal("0.1"),
    ) -> None:
        """Processa um fill (parcial ou total) e mantém TP/SL consistente."""

        lock_key = f"tpsl:resize:{position_id}"
        lock_acquired = await self._acquire_lock(lock_key)
        if not lock_acquired:
            logger.warning(
                "PartialFillHandler: lock não adquirido para %s — retry em breve",
                position_id,
            )
            return

        try:
            existing = await self._repo.find_active_by_position(position_id)

            if existing is None:
                # ── Primeiro fill: criar TP/SL pela primeira vez ──────────────
                logger.info(
                    "PartialFillHandler: primeiro fill position=%s size=%s price=%s",
                    position_id, additional_filled_size, fill_price,
                )
                prices = self._calc.calculate(
                    entry_price=fill_price,
                    side=side,
                    tp_percent=tp_percent,
                    sl_percent=sl_percent,
                    tick_size=tick_size,
                    sl_buffer=sl_buffer,
                )
                await self._manager.create(
                    bot_id=bot_id,
                    user_id=user_id,
                    strategy_id=strategy_id,
                    position_id=position_id,
                    signal_id=signal_id,
                    symbol=symbol,
                    side=side,
                    filled_size=additional_filled_size,
                    entry_price=fill_price,
                    tp_price=prices.tp_price,
                    sl_price=prices.sl_price,
                    sl_stop_price=prices.sl_stop_price,
                )

            else:
                # ── Fill adicional: cancelar e recriar com novo tamanho ───────
                old_size  = Decimal(existing.total_size)
                old_price = Decimal(existing.entry_price)
                new_total = old_size + additional_filled_size
                # Preço médio ponderado
                avg_price = (old_size * old_price + additional_filled_size * fill_price) / new_total

                logger.info(
                    "PartialFillHandler: resize position=%s %s→%s avg_price=%s",
                    position_id, old_size, new_total, avg_price,
                )

                # Cancela ordens existentes na exchange
                if existing.tp_order_id:
                    await self._cancel_order(existing.tp_order_id, stop=False)
                if existing.sl_order_id:
                    await self._cancel_order(existing.sl_order_id, stop=True)

                # Fecha o TpSlRecord antigo
                await self._repo.cancel(existing.id, "RESIZED_FOR_PARTIAL_FILL")

                # Recria com tamanho total e preço médio
                prices = self._calc.calculate(
                    entry_price=avg_price,
                    side=side,
                    tp_percent=tp_percent,
                    sl_percent=sl_percent,
                    tick_size=tick_size,
                    sl_buffer=sl_buffer,
                )
                await self._manager.create(
                    bot_id=bot_id,
                    user_id=user_id,
                    strategy_id=strategy_id,
                    position_id=position_id,
                    signal_id=f"{signal_id}:resize",
                    symbol=symbol,
                    side=side,
                    filled_size=new_total,
                    entry_price=avg_price,
                    tp_price=prices.tp_price,
                    sl_price=prices.sl_price,
                    sl_stop_price=prices.sl_stop_price,
                )

        except Exception as exc:
            logger.error("PartialFillHandler: erro ao processar fill: %s", exc)
        finally:
            await self._release_lock(lock_key)

    async def _cancel_order(self, order_id: str, stop: bool) -> None:
        """Cancela ordem na exchange de forma silenciosa."""
        try:
            if stop:
                await self._manager._kucoin.cancel_stop_order(order_id)
            else:
                await self._manager._kucoin.cancel_order(order_id)
        except Exception as exc:
            logger.warning("PartialFillHandler: falha ao cancelar %s: %s", order_id, exc)

    # ── Locking ───────────────────────────────────────────────────────────────

    async def _acquire_lock(self, key: str) -> bool:
        if self._redis is not None:
            result = await self._redis.set(key, "1", ex=self.LOCK_TTL, nx=True)
            return result is not None
        async with self._locks_mx:
            if key not in self._mem_locks:
                self._mem_locks[key] = asyncio.Lock()
        lock = self._mem_locks[key]
        return not lock.locked()

    async def _release_lock(self, key: str) -> None:
        if self._redis is not None:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
