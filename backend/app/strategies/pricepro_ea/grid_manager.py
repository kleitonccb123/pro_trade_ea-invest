"""
GridManager — Sistema de Proteções (Grid)

Equivale ao grid de proteções do MT5:
    ShouldOpenProtection()
    OpenProtection()
    UpdateProtectionTargets()
    GetCurrentDrawdownPips()

Conceito:
    Quando o preço vai contra a posição principal em X pontos,
    o EA abre uma nova posição na mesma direção (proteção/martingale
    controlado). O sistema fecha tudo quando o lucro total ≥ +$0.50.

Estado mantido por instância (um GridManager por usuário/símbolo).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .config import EAConfig, GridLevel
from .signal_generator import Direction

logger = logging.getLogger(__name__)

# Tipo de callback para envio de ordem
OrderCallback = Callable[..., Coroutine[Any, Any, str]]  # retorna order_id

# Lucro mínimo em USD para fechar tudo (equivale a minProfitToClose do MT5)
MIN_PROFIT_TO_CLOSE_USD: float = 0.50


@dataclass
class PositionSummary:
    """Resumo de posições abertas (calculado externamente e passado aqui)."""
    total_profit_usd: float                   # P&L não realizado total
    direction: Direction                       # direção líquida
    avg_price: float                           # preço médio ponderado
    net_volume: Decimal                        # volume líquido
    volume_long: Decimal                       # volume total de compras
    volume_short: Decimal                      # volume total de vendas
    current_bid: float
    current_ask: float
    positions: List[Dict[str, Any]] = field(default_factory=list)


class GridManager:
    """
    Gerencia a lógica do grid de proteções.

    Uso pelo EA runner:
        summary = await get_position_summary()
        if grid.should_open_protection(summary, current_time):
            level = grid.next_level()
            await grid.open_protection(level, direction, open_order_fn)
        await grid.update_targets(summary, modify_tp_fn, close_all_fn)
    """

    def __init__(self, config: EAConfig):
        self.cfg = config
        self._levels: List[GridLevel] = config.get_grid_levels()
        self._opened: int = 0                  # proteções abertas (índice no grid)
        self._last_open_time: float = 0.0      # monotonic timestamp da última abertura
        self._last_update_time: float = 0.0    # controle de throttle para UpdateTargets

    # ── Estado ───────────────────────────────────────────────────────────────

    @property
    def protections_opened(self) -> int:
        return self._opened

    @property
    def total_levels(self) -> int:
        return len(self._levels)

    def reset(self) -> None:
        """Chamado quando não há posições abertas."""
        self._opened = 0
        if self.cfg.debug:
            logger.debug("[Grid] Reset — sem posições abertas")

    # ── Drawdown em pontos ───────────────────────────────────────────────────

    def _drawdown_points(self, summary: PositionSummary) -> float:
        """
        Retorna o drawdown atual em pontos (equivale a GetCurrentDrawdownPips() * 10).
        Para KuCoin usamos points = (diferença de preço / price_tick).
        """
        if summary.direction == Direction.NONE:
            return 0.0

        tick = float(self.cfg.price_tick)
        if tick <= 0:
            return 0.0

        if summary.direction == Direction.BUY:
            diff = summary.avg_price - summary.current_bid
        else:
            diff = summary.current_ask - summary.avg_price

        if diff <= 0:
            return 0.0

        return diff / tick

    # ── Verificar se deve abrir proteção ────────────────────────────────────

    def should_open_protection(
        self,
        summary: PositionSummary,
        has_open_positions: bool,
        can_trade: bool,
    ) -> bool:
        """
        Equivale a ShouldOpenProtection() do MT5.
        Retorna True se for hora de abrir o próximo nível do grid.
        """
        if not self.cfg.use_grid:
            return False
        if not has_open_positions:
            return False
        if not can_trade:
            return False
        if self._opened >= len(self._levels):
            return False
        if summary.direction == Direction.NONE:
            return False

        # Throttle por tempo
        now = time.monotonic()
        if now - self._last_open_time < self.cfg.grid_delay_s:
            return False

        # Drawdown mínimo para o próximo nível
        ddp = self._drawdown_points(summary)
        if ddp <= 0:
            return False

        next_level = self._levels[self._opened]
        if ddp >= next_level.distance_points:
            return True

        return False

    def next_level_volume(self) -> Optional[Decimal]:
        """Volume do próximo nível do grid a ser aberto."""
        if self._opened >= len(self._levels):
            return None
        return self._levels[self._opened].volume

    def mark_protection_opened(self) -> None:
        """Registra que uma proteção foi aberta."""
        self._opened += 1
        self._last_open_time = time.monotonic()
        if self.cfg.debug:
            logger.debug(
                "[Grid] Proteção aberta — nível %d/%d",
                self._opened, len(self._levels)
            )

    # ── Atualizar TP das proteções ───────────────────────────────────────────

    def should_update_targets(self) -> bool:
        """Throttle: executar UpdateTargets a cada 300 ms no máximo."""
        now = time.monotonic()
        if now - self._last_update_time < 0.3:
            return False
        self._last_update_time = now
        return True

    def calculate_recovery_price(
        self, summary: PositionSummary
    ) -> Optional[float]:
        """
        Calcula o preço alvo (TP) necessário para cobrir o prejuízo acumulado
        e ainda gerar lucro líquido mínimo de $0.01.

        Equivale a UpdateProtectionTargets() do MT5.

        Retorna None se não for necessário ajuste (já lucrativo ou sem dados).
        """
        profit = summary.total_profit_usd

        # Fechar tudo se lucro >= mínimo
        if profit >= MIN_PROFIT_TO_CLOSE_USD:
            return None  # sinaliza para fechar tudo

        # Se positivo mas abaixo do mínimo, aguardar
        if profit >= 0:
            return None

        # Calcular distância necessária para cobrir o prejuízo
        buffer_usd = 0.01
        required_usd = abs(profit) + buffer_usd

        # Side com maior volume (que vai lucrar quando o preço mover a favor)
        side_volume = (
            summary.volume_long if summary.direction == Direction.BUY
            else summary.volume_short
        )

        if side_volume <= 0:
            return None

        # price_diff = required_usd / side_volume (simplificado para USDT pairs)
        # Para pares USDT spot: P&L = volume × price_diff (em USDT por unidade base)
        price_dist = float(required_usd) / float(side_volume)

        if summary.direction == Direction.BUY:
            return summary.current_ask + price_dist
        else:
            return summary.current_bid - price_dist

    def should_close_all(self, summary: PositionSummary) -> bool:
        """Retorna True se o resultado total justifica fechar tudo."""
        return summary.total_profit_usd >= MIN_PROFIT_TO_CLOSE_USD
