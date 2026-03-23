"""
PricePro Money-EA — Adaptação KuCoin

Modules:
    config            → EAConfig (todos os parâmetros do EA)
    indicators        → Cálculo de indicadores técnicos (EMA, RSI, candle, volume, range)
    signal_generator  → Combina filtros e retorna sinal de entrada
    grid_manager      → Sistema de proteções (grid)
    position_tracker  → Breakeven + trailing por candle
    scalper           → Entradas scalper dentro do candle seguinte
    daily_controller  → Stop diário (meta + limite) e emergência
    ea_runner         → Orquestrador principal (loop assíncrono)
    router            → FastAPI endpoints para gerenciar instâncias do EA
"""

from .config import EAConfig, GridLevel
from .ea_runner import PriceProEARunner, ea_registry
from .router import configure_dependencies, router

__all__ = [
    "EAConfig",
    "GridLevel",
    "PriceProEARunner",
    "ea_registry",
    "router",
    "configure_dependencies",
]

from .config import EAConfig, GridLevel
from .ea_runner import PriceProEARunner

__all__ = ["EAConfig", "GridLevel", "PriceProEARunner"]
