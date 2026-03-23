"""
PriceProMoneyModule — Implementação SaaS do PRICEPRO_MONEY-EA

Este módulo é o adaptador entre o StrategyManager (Python/SaaS) e o
Expert Advisor PRICEPRO_MONEY-EA rodando no MetaTrader 5.

Hierarquia de herança
---------------------
    SaaSStrategyModule (ABC)
        └── PriceProMoneyModule  ← este arquivo

Responsabilidades
-----------------
- Escrever control.json via EAController (comandos → EA)
- Ler state.json via EAStateMonitor (telemetria ← EA)
- Implementar todos os 6 contratos definidos em strategy_base.SaaSStrategyModule
- Validar magic_number durante handshake
- Nunca retornar is_risk_zero()=True enquanto houver posições reais abertas

Registro
--------
Este módulo é instanciado pelo STRATEGY_REGISTRY em strategy_base.py.
O document MongoDB correspondente é criado por seed_pricepro.py.

Constantes de identificação
----------------------------
    STRATEGY_ID  = "pricepro_money_v1"
    MAGIC_NUMBER = 20240001
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.bots.strategy_base import SaaSStrategyModule, StrategyStatus
from app.services.ea_controller import EAController
from app.services.ea_monitor import EAStateMonitor

logger = logging.getLogger(__name__)

_STRATEGY_ID  = "pricepro_money_v1"
_MAGIC_NUMBER = 20240001


class PriceProMoneyModule(SaaSStrategyModule):
    """
    Implementação concreta do PRICEPRO_MONEY-EA como SaaS Strategy Module.

    Protocolo de ativação (DOC-STRAT-09):
    1. activate_pending() → EA recebe ACTIVATE com permitted=false
    2. EA grava state.json com status=READY
    3. Backend valida magic_number=20240001
    4. activate() → EA recebe permitted=true, manager_state=ACTIVE
    5. EA inicia ExecuteStrategy()

    Protocolo de encerramento (DOC-STRAT-03):
    1. safe_shutdown() → EA recebe SAFE_SHUTDOWN
    2. EA executa SafeShutdown() a cada tick (cancela ordens → fecha posições)
    3. EA grava state.json com status=SAFE_TO_SWITCH e open_positions=0
    4. wait_for_risk_zero() retorna True → StrategyManager avança para SAFE_TO_SWITCH
    """

    def __init__(self, user_id: str):
        self._user_id    = user_id
        self._controller = EAController(user_id, _STRATEGY_ID)
        self._monitor    = EAStateMonitor(user_id, _STRATEGY_ID)
        logger.debug(
            "[PriceProMoneyModule] Instância criada para user=%s", user_id
        )

    # ── Identificação ─────────────────────────────────────────────────────────

    @property
    def strategy_id(self) -> str:
        return _STRATEGY_ID

    @property
    def magic_number(self) -> int:
        return _MAGIC_NUMBER

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    async def activate(self) -> bool:
        """
        Envia sinal de ativação ao EA e aguarda handshake (até 30 s).

        Fluxo:
          1. Escreve control.json com permitted=false (EA prepara handshake)
          2. Aguarda EA reportar status=READY em state.json
          3. Valida magic_number reportado pelo EA
          4. Escreve control.json com permitted=true
          5. Retorna True se OK, False em caso de timeout ou mismatch
        """
        logger.info(
            "[PriceProMoneyModule] Iniciando ativação — user=%s", self._user_id
        )

        # Passo 1 — Enviar ACTIVATE pendente (sem permissão ainda)
        self._controller.activate_pending()

        # Passo 2 — Aguardar EA confirmar READY
        ready = await self._monitor.wait_for_ready(timeout_seconds=30)
        if not ready:
            logger.error(
                "[PriceProMoneyModule] Handshake timeout (EA não respondeu READY): user=%s",
                self._user_id,
            )
            return False

        # Passo 3 — Validar magic number
        ea_magic = self._monitor.get_reported_magic()
        if ea_magic != _MAGIC_NUMBER:
            logger.error(
                "[PriceProMoneyModule] Magic number mismatch: ea=%s esperado=%s user=%s",
                ea_magic, _MAGIC_NUMBER, self._user_id,
            )
            return False

        # Passo 4 — Confirmar ativação plena
        self._controller.activate(manager_state="ACTIVE")
        logger.info(
            "[PriceProMoneyModule] Handshake concluído. Trading habilitado — user=%s",
            self._user_id,
        )
        return True

    async def deactivate(self) -> bool:
        """
        Desativa o módulo sem fechar posições.
        Retorna imediatamente — não aguarda confirmação do EA.
        """
        logger.info(
            "[PriceProMoneyModule] Desativando (sem fechar posições) — user=%s",
            self._user_id,
        )
        self._controller.deactivate()
        return True

    async def safe_shutdown(self, timeout_seconds: int = 120) -> bool:
        """
        Envia SAFE_SHUTDOWN e aguarda confirmação de risco zero pelo EA.

        O EA executa SafeShutdown() a cada tick enquanto manager_state
        for CLOSING_POSITIONS. Quando open_positions=0 e open_orders=0,
        o EA grava status=SAFE_TO_SWITCH e este método retorna True.

        Retorna False se o EA não zeriar dentro de timeout_seconds.
        NUNCA retornar True com posições ainda abertas.
        """
        logger.info(
            "[PriceProMoneyModule] Iniciando SafeShutdown — user=%s timeout=%ds",
            self._user_id, timeout_seconds,
        )
        self._controller.safe_shutdown()
        result = await self._monitor.wait_for_risk_zero(timeout_seconds)
        if not result:
            logger.error(
                "[PriceProMoneyModule] SafeShutdown timeout — posições podem estar abertas! user=%s",
                self._user_id,
            )
        return result

    def emergency_stop(self) -> None:
        """
        Kill switch imediato — não aguarda confirmação.
        Chamado pelo RiskManager quando daily loss ou drawdown é atingido.
        """
        logger.critical(
            "[PriceProMoneyModule] EMERGENCY STOP acionado — user=%s",
            self._user_id,
        )
        self._controller.emergency_stop()

    # ── Observabilidade ───────────────────────────────────────────────────────

    def get_status(self) -> StrategyStatus:
        """
        Lê state.json e retorna StrategyStatus normalizado.
        Nunca lança exceção — retorna status UNREACHABLE em caso de falha.
        """
        raw = self._monitor.read_state()

        heartbeat: Optional[datetime] = None
        raw_hb = raw.get("heartbeat")
        if raw_hb:
            try:
                raw_hb_iso = str(raw_hb).replace(".", "-", 2).replace(" ", "T")
                if not raw_hb_iso.endswith("Z") and "+" not in raw_hb_iso:
                    raw_hb_iso += "Z"
                heartbeat = datetime.fromisoformat(raw_hb_iso.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return StrategyStatus(
            strategy_id=raw.get("strategy_id", _STRATEGY_ID),
            magic_number=int(raw.get("magic_number", _MAGIC_NUMBER)),
            status=raw.get("status", "UNREACHABLE"),
            open_positions=int(raw.get("open_positions", -1)),
            open_orders=int(raw.get("open_orders", -1)),
            unrealized_pnl=float(raw.get("unrealized_pnl", 0.0)),
            account_balance=float(raw.get("account_balance", 0.0)),
            account_equity=float(raw.get("account_equity", 0.0)),
            heartbeat=heartbeat,
            uptime_seconds=int(raw.get("uptime_seconds", 0)),
            manager_state_local=raw.get("manager_state_local", "UNKNOWN"),
        )

    async def is_alive(self) -> bool:
        """
        True se heartbeat foi recebido nos últimos 30 s.
        Execução síncrona internamente — wrapper async para compatibilidade
        com a interface SaaSStrategyModule.
        """
        return self._monitor.is_alive()

    async def is_risk_zero(self) -> bool:
        """
        True se EA confirmou zero posições e zero ordens abertas.
        Consulta state.json — sem chamada à exchange.
        """
        return self._monitor.is_risk_zero()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def update_risk_limits(
        self,
        daily_loss_limit:   float = 0.0,
        daily_loss_current: float = 0.0,
        max_drawdown_pct:   float = 20.0,
        cooldown_until:     Optional[str] = None,
    ) -> None:
        """
        Atualiza limites de risco no control.json sem alterar permitted/kill_switch.
        Chamado pelo RiskManager após cada trade fechado ou marcação de daily loss.
        """
        self._controller.update_risk_limits(
            daily_loss_limit=daily_loss_limit,
            daily_loss_current=daily_loss_current,
            max_drawdown_pct=max_drawdown_pct,
            cooldown_until=cooldown_until,
        )

    def __repr__(self) -> str:
        status = self.get_status().status
        return (
            f"PriceProMoneyModule("
            f"user={self._user_id!r}, "
            f"magic={_MAGIC_NUMBER}, "
            f"status={status!r})"
        )
