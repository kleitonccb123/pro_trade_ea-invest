"""
EAStateMonitor — Leitura do arquivo de estado dos EAs MT5

Responsabilidade única: monitorar o state.json que o EA grava a cada 5 s
via FileWriteString() no MT5. É o canal de telemetria EA → backend.

Uso
---
    mon = EAStateMonitor(user_id="abc123", strategy_id="pricepro_money_v1")
    mon.is_alive()                          # heartbeat recente?
    mon.is_risk_zero()                      # posições e ordens zeradas?
    await mon.wait_for_risk_zero(120)       # aguarda com timeout
    mon.read_state()                        # dict completo do state.json

Arquivo monitorado
------------------
    C:\\MT5_Control\\<user_id>\\<strategy_id>\\state.json

Campos esperados no state.json
-------------------------------
    strategy_id           str
    magic_number          int
    status                READY | RUNNING | PAUSED | SAFE_TO_SWITCH |
                          SHUTDOWN_COMPLETE | SHUTDOWN_PENDING | OFFLINE |
                          HANDSHAKE_TIMEOUT
    manager_state_local   str — replica do manager_state lido pelo EA
    permitted             bool
    kill_switch_active    bool
    open_positions        int
    open_orders           int
    unrealized_pnl        float
    realized_pnl_today    float
    floating_drawdown     float
    account_balance       float
    account_equity        float
    heartbeat             "YYYY.MM.DD HH:MM:SS" (formato MT5)
    uptime_seconds        int
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_BASE_PATH             = Path("C:/MT5_Control")
_HEARTBEAT_TIMEOUT_S   = 30    # EA considerado morto após este intervalo
_RISK_ZERO_POLL_S      = 2     # intervalo de polling em wait_for_risk_zero

# Statuses que confirmam risco zero inequivocamente
_RISK_ZERO_STATUSES = {"SAFE_TO_SWITCH", "SHUTDOWN_COMPLETE", "OFFLINE"}


class EAStateMonitor:
    """
    Monitora o state.json escrito pelo EA MT5 com debounce mínimo de I/O.

    Instâncias são stateless (leitura pura do sistema de arquivos) — podem
    ser criadas por demanda sem custo relevante.
    """

    def __init__(self, user_id: str, strategy_id: str):
        self.user_id     = user_id
        self.strategy_id = strategy_id
        self._path       = _BASE_PATH / user_id / strategy_id / "state.json"

    # ── Leitura bruta ─────────────────────────────────────────────────────────

    def read_state(self) -> Dict[str, Any]:
        """
        Retorna o conteúdo atual do state.json como dict.
        Nunca lança exceção — retorna sentinel safe em caso de erro.
        """
        if not self._path.exists():
            return {"status": "UNREACHABLE", "open_positions": -1, "open_orders": -1}
        try:
            raw = self._path.read_text(encoding="utf-8")
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[EAStateMonitor] JSON inválido em state.json: %s", self._path)
            return {"status": "PARSE_ERROR", "open_positions": -1, "open_orders": -1}
        except OSError as exc:
            logger.warning("[EAStateMonitor] Erro ao ler state.json: %s", exc)
            return {"status": "READ_ERROR", "open_positions": -1, "open_orders": -1}

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def is_alive(self) -> bool:
        """
        Retorna True se o EA produziu um heartbeat nos últimos
        HEARTBEAT_TIMEOUT_S segundos (padrão: 30 s).

        O campo `heartbeat` no state.json usa o formato MT5:
        "YYYY.MM.DD HH:MM:SS" (sem fuso — assumido UTC).
        """
        state = self.read_state()
        raw_hb = state.get("heartbeat")
        if not raw_hb:
            return False
        try:
            # Suporta tanto formato MT5 ("2026.02.27 14:00:05")
            # quanto ISO8601 ("2026-02-27T14:00:05Z")
            raw_hb = str(raw_hb).replace(".", "-", 2).replace(" ", "T")
            if not raw_hb.endswith("Z") and "+" not in raw_hb:
                raw_hb += "Z"
            hb = datetime.fromisoformat(raw_hb.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - hb).total_seconds()
            return age < _HEARTBEAT_TIMEOUT_S
        except (ValueError, TypeError) as exc:
            logger.debug("[EAStateMonitor] Heartbeat parse error: %s — %s", raw_hb, exc)
            return False

    # ── Risco zero ────────────────────────────────────────────────────────────

    def is_risk_zero(self) -> bool:
        """
        Retorna True quando o EA confirmou que não há exposição ao mercado:
          - status em {SAFE_TO_SWITCH, SHUTDOWN_COMPLETE, OFFLINE}
          OU
          - open_positions == 0 E open_orders == 0

        Esta lógica OR garante backward-compatibility com EAs que não
        escrevem o campo status corretamente.
        """
        state   = self.read_state()
        status  = state.get("status", "")
        pos     = state.get("open_positions", -1)
        orders  = state.get("open_orders", -1)

        by_status   = status in _RISK_ZERO_STATUSES
        by_counters = (isinstance(pos, int) and pos == 0
                       and isinstance(orders, int) and orders == 0)

        return by_status or by_counters

    async def wait_for_risk_zero(self, timeout_seconds: int = 120) -> bool:
        """
        Aguarda até que is_risk_zero() retorne True ou o timeout expire.
        Faz polling a cada _RISK_ZERO_POLL_S segundos (padrão: 2 s).

        Retorna True se risco zero confirmado, False se timeout.
        Deve ser chamado com await dentro de um contexto async.
        """
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        logger.info(
            "[EAStateMonitor] Aguardando risco zero: user=%s strategy=%s timeout=%ds",
            self.user_id, self.strategy_id, timeout_seconds,
        )
        while asyncio.get_event_loop().time() < deadline:
            if self.is_risk_zero():
                logger.info(
                    "[EAStateMonitor] Risco zero confirmado: user=%s strategy=%s",
                    self.user_id, self.strategy_id,
                )
                return True
            await asyncio.sleep(_RISK_ZERO_POLL_S)

        logger.warning(
            "[EAStateMonitor] Timeout aguardando risco zero: user=%s strategy=%s",
            self.user_id, self.strategy_id,
        )
        return False

    async def wait_for_ready(self, timeout_seconds: int = 30) -> bool:
        """
        Aguarda o EA publicar status=READY no state.json.
        Usado pelo pipeline de handshake em ACTIVATING_NEW_STRATEGY.
        """
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while asyncio.get_event_loop().time() < deadline:
            state = self.read_state()
            if state.get("status") == "READY":
                return True
            await asyncio.sleep(1)
        return False

    # ── Validação de magic number ─────────────────────────────────────────────

    def get_reported_magic(self) -> Optional[int]:
        """
        Retorna o magic_number reportado pelo EA no state.json.
        Usado para validar que o EA correto está conectado.
        """
        state = self.read_state()
        raw = state.get("magic_number")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
