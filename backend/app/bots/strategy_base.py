from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Strategy(ABC):
    """Base strategy interface. Implementations receive a list of candles and must return a Signal.

    Candle structure: Dict[str, Any] with keys: open, high, low, close, volume, timestamp
    """

    @abstractmethod
    def on_candles(self, candles: List[Dict[str, Any]]) -> Signal:
        raise NotImplementedError()


# ─────────────────────────────────────────────────────────────────────────────
# SaaS Strategy Module — contrato obrigatório para toda estratégia controlada
# remotamente pelo Strategy Manager (Single Active Strategy mode).
#
# Cada robô registrado no SaaS deve implementar esta interface.
# Os 6 contratos abaixo são verificados pelo StrategyManager antes de:
#   - marcar o bot como running  (activate)
#   - iniciar o pipeline de troca (safe_shutdown)
#   - confirmar zero-risco        (is_risk_zero)
#   - detecção de EA morto        (is_alive)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategyStatus:
    """
    Snapshot do estado operacional de um módulo de estratégia.
    Gerado por get_status() e consumido pelo StrategyManager e pelo frontend.
    """
    strategy_id:          str
    magic_number:         int
    # READY | RUNNING | PAUSED | SAFE_TO_SWITCH | SHUTDOWN_COMPLETE | OFFLINE | UNREACHABLE
    status:               str
    open_positions:       int          # posições com este magic number
    open_orders:          int          # ordens pendentes com este magic number
    unrealized_pnl:       float        # PnL flutuante das posições abertas
    account_balance:      float
    account_equity:       float
    heartbeat:            Optional[datetime]   # último heartbeat do EA
    uptime_seconds:       int
    manager_state_local:  str          # estado que o EA lê do control.json


class SaaSStrategyModule(ABC):
    """
    Interface base para todo Strategy Module registrado no Crypto Trade Hub SaaS.

    Compliance
    ----------
    Toda classe concreta que herdar SaaSStrategyModule deve implementar os
    6 contratos abaixo. O StrategyManager chama estes métodos diretamente
    durante o pipeline de ativação/troca/encerramento.

    Convenção de strategy_id
    ------------------------
    "<nome_curto>_v<major>" — ex: "pricepro_money_v1", "grid_scalper_v1".
    Deve bater exatamente com o campo `strategy_id` do documento MongoDB.

    Convenção de magic_number
    -------------------------
    YYYYNNNN onde YYYY = ano de criação e NNNN = sequencial único.
    Nunca reutilizar um magic number, mesmo após desativar uma estratégia.
    """

    # ── Identificação ─────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """Identificador único registrado no MongoDB e no STRATEGY_REGISTRY."""
        ...

    @property
    @abstractmethod
    def magic_number(self) -> int:
        """
        Magic number exclusivo para controle de posições no MT5/exchange.
        Todas as operações de abertura/fechamento usam este número como filtro.
        """
        ...

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    @abstractmethod
    async def activate(self) -> bool:
        """
        Inicia o módulo e aguarda handshake do EA dentro de 30 s.

        Sequência interna esperada:
        1. Escreve control.json com command=ACTIVATE, permitted=false
        2. Aguarda EA gravar state.json com status=READY
        3. Valida magic_number do state.json
        4. Escreve control.json com permitted=true, manager_state=ACTIVE
        5. Retorna True se handshake OK, False se timeout

        Chamado pelo StrategyManager em ACTIVATING_NEW_STRATEGY.
        """
        ...

    @abstractmethod
    async def deactivate(self) -> bool:
        """
        Desativa o módulo sem fechar posições (troca config, pausa temporária).
        Escreve command=DEACTIVATE, permitted=false no control.json.
        Retorna True imediatamente — não aguarda confirmação do EA.
        """
        ...

    @abstractmethod
    async def safe_shutdown(self, timeout_seconds: int = 120) -> bool:
        """
        Inicia o SafeShutdown no EA e aguarda confirmação de risco zero.

        Sequência interna esperada:
        1. Escreve control.json com command=SAFE_SHUTDOWN
        2. Aguarda state.json reportar open_positions=0 e open_orders=0
        3. Ou aguarda status=SAFE_TO_SWITCH | SHUTDOWN_COMPLETE
        4. Retorna True se risco zero dentro de timeout_seconds, False se timeout

        Chamado pelo StrategyManager em CLOSING_POSITIONS.
        Nunca retornar True enquanto houver posições abertas.
        """
        ...

    # ── Observabilidade ───────────────────────────────────────────────────────

    @abstractmethod
    def get_status(self) -> StrategyStatus:
        """
        Retorna snapshot atual lido do state.json (escrito pelo EA).
        Não faz chamada à exchange — apenas lê o arquivo local.
        Usado pelo StrategyManager, pelo dashboard e pelos alertas de risco.
        """
        ...

    @abstractmethod
    async def is_alive(self) -> bool:
        """
        Retorna True se o EA está respondendo (heartbeat nos últimos 30 s).
        False indica EA morto, travado ou desconectado do MT5.
        Usado pelo watchdog do StrategyManager.
        """
        ...

    @abstractmethod
    async def is_risk_zero(self) -> bool:
        """
        Retorna True se não há posições ou ordens abertas com este magic number.
        Consulta state.json — não requer chamada à exchange.
        O StrategyManager usa este método para confirmar SAFE_TO_SWITCH.
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Registro central de estratégias
# Adicionar cada nova estratégia aqui antes de registrá-la no MongoDB.
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "pricepro_money_v1": {
        "magic_number":            20240001,
        "display_name":            "PRICEPRO MONEY",
        "version":                 "1.0",
        "min_switch_interval_s":   60,
        "safe_shutdown_timeout_s": 120,
        "handshake_timeout_s":     30,
    },
    # Reservados — não reutilizar magic numbers:
    # "grid_scalper_v1":  { "magic_number": 20240002, ... }
    # "dca_builder_v1":   { "magic_number": 20240003, ... }
}
