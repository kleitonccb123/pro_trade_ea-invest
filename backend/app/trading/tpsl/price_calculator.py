"""
TpSlPriceCalculator — Cálculo de preços de Take Profit e Stop Loss

Para LONG (side='buy'):
  TP = entry * (1 + tp_pct/100)  → acima da entrada
  SL = entry * (1 - sl_pct/100)  → abaixo da entrada

Para SHORT (side='sell'):
  TP = entry * (1 - tp_pct/100)  → abaixo da entrada
  SL = entry * (1 + sl_pct/100)  → acima da entrada

Stop-Limit (spotTPSL):
  O stopPrice (gatilho) é posicionado ligeiramente mais próximo da entrada
  do que o limitPrice, para garantir que a ordem seja executada mesmo com
  pequeno slippage no momento do trigger.

  Para LONG SL:
    limitPrice = entry * (1 - sl_pct/100)
    stopPrice  = limitPrice * (1 + sl_buffer/100)   ← gatilho acima do limite

  Para SHORT SL:
    limitPrice = entry * (1 + sl_pct/100)
    stopPrice  = limitPrice * (1 - sl_buffer/100)   ← gatilho abaixo do limite
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass
class TpSlPrices:
    tp_price:      Decimal   # Preço de Take Profit (limit)
    sl_price:      Decimal   # Preço limite do Stop Loss
    sl_stop_price: Decimal   # Gatilho do Stop Loss (stop-limit trigger)


class TpSlPriceCalculator:
    """
    Calcula preços de TP e SL arredondados ao tick_size do mercado.

    Uso:
    ```python
    calc = TpSlPriceCalculator()
    prices = calc.calculate(
        entry_price=Decimal("50000"),
        side="buy",          # posição LONG
        tp_percent=Decimal("2.5"),
        sl_percent=Decimal("1.5"),
        tick_size=Decimal("0.1"),
        sl_buffer=Decimal("0.1"),
    )
    # prices.tp_price      → 51250.0
    # prices.sl_price      → 49250.0
    # prices.sl_stop_price → 49299.2  (ligeiramente acima do limite)
    ```
    """

    def calculate(
        self,
        entry_price: Decimal,
        side: str,              # "buy" (long) ou "sell" (short)
        tp_percent: Decimal,    # Ex: Decimal("2.5") para 2.5%
        sl_percent: Decimal,    # Ex: Decimal("1.5") para 1.5%
        tick_size: Decimal,     # Incremento mínimo de preço do par
        sl_buffer: Decimal = Decimal("0.1"),  # Buffer stopPrice vs limitPrice (%)
    ) -> TpSlPrices:
        hundred = Decimal("100")

        if side == "buy":
            # LONG: TP acima, SL abaixo
            tp_raw  = entry_price * (hundred + tp_percent) / hundred
            sl_raw  = entry_price * (hundred - sl_percent) / hundred
            # Gatilho do SL fica ligeiramente ACIMA do limitPrice
            stop_raw = sl_raw * (hundred + sl_buffer) / hundred
        else:
            # SHORT: TP abaixo, SL acima
            tp_raw  = entry_price * (hundred - tp_percent) / hundred
            sl_raw  = entry_price * (hundred + sl_percent) / hundred
            # Gatilho do SL fica ligeiramente ABAIXO do limitPrice
            stop_raw = sl_raw * (hundred - sl_buffer) / hundred

        tp_price      = self._round_to_tick(tp_raw,   tick_size)
        sl_price      = self._round_to_tick(sl_raw,   tick_size)
        sl_stop_price = self._round_to_tick(stop_raw, tick_size)

        return TpSlPrices(
            tp_price=tp_price,
            sl_price=sl_price,
            sl_stop_price=sl_stop_price,
        )

    @staticmethod
    def _round_to_tick(price: Decimal, tick_size: Decimal) -> Decimal:
        """Arredonda para baixo ao múltiplo de tick_size mais próximo."""
        if tick_size <= 0:
            return price
        return (price / tick_size).to_integral_value(rounding=ROUND_DOWN) * tick_size

    def pnl_percent(
        self,
        entry_price: Decimal,
        exit_price: Decimal,
        side: str,
    ) -> Decimal:
        """Calcula PnL percentual de uma posição."""
        if entry_price == 0:
            return Decimal("0")
        if side == "buy":
            return (exit_price - entry_price) / entry_price * Decimal("100")
        else:
            return (entry_price - exit_price) / entry_price * Decimal("100")
