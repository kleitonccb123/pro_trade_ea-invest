"""
EAController — Escrita do arquivo de controle para EAs MT5

Responsabilidade única: gravar o control.json que o EA lê via FileOpen()
a cada tick. É o canal de comando do backend → EA.

Uso
---
    ctrl = EAController(user_id="abc123", strategy_id="pricepro_money_v1")
    ctrl.activate()           # inicia trading
    ctrl.safe_shutdown()      # inicia encerramento seguro
    ctrl.emergency_stop()     # kill switch imediato

Arquivo gerado
--------------
    C:\\MT5_Control\\<user_id>\\<strategy_id>\\control.json

Campos do arquivo
-----------------
    command         ACTIVATE | DEACTIVATE | SAFE_SHUTDOWN | EMERGENCY_STOP
    permitted       bool — EA pode abrir novas entradas quando True
    kill_switch     bool — fecha tudo imediatamente, sem exceção
    emergency_stop  bool — aciona SafeShutdown imediato no EA
    manager_state   string — estado atual do StrategyManager
    daily_loss_limit      float — limite de perda diária (0 = sem limite)
    daily_loss_current    float — perda acumulada hoje
    max_drawdown_pct      float — drawdown máximo em % do balanço
    cooldown_until        ISO8601 | null
    sequence        int — incrementado a cada escrita; EA descarta se <= anterior
    issued_at       ISO8601 UTC
    issued_by       "strategy_manager"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Raiz dos arquivos de controle (mesmo host que o MT5)
_BASE_PATH = Path("C:/MT5_Control")


class EAController:
    """
    Grava o control.json consumido pelo EA PRICEPRO_MONEY (e futuros EAs)
    via FileOpen() + FileReadString() no MT5.

    Thread-safe para uso síncrono.  O Strategy Manager (async) deve chamar
    via run_in_executor se necessário, mas em prática a escrita é tão
    rápida que não bloqueia o event loop de forma relevante.
    """

    def __init__(self, user_id: str, strategy_id: str):
        self.user_id     = user_id
        self.strategy_id = strategy_id
        self._seq        = 0          # monotônico por instância
        self._path       = _BASE_PATH / user_id / strategy_id / "control.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ── Comandos públicos ──────────────────────────────────────────────────────

    def activate(self, manager_state: str = "ACTIVE") -> None:
        """
        Habilita trading.  Usado após handshake concluído.
        permitted=True, kill_switch=False.
        """
        self._write({
            "command":            "ACTIVATE",
            "permitted":          True,
            "kill_switch":        False,
            "emergency_stop":     False,
            "manager_state":      manager_state,
        })

    def activate_pending(self, manager_state: str = "ACTIVATING_NEW_STRATEGY") -> None:
        """
        Sinaliza ao EA que deve iniciar o handshake mas ainda não operar.
        permitted=False até que o backend confirme status=READY no state.json.
        """
        self._write({
            "command":            "ACTIVATE",
            "permitted":          False,
            "kill_switch":        False,
            "emergency_stop":     False,
            "manager_state":      manager_state,
        })

    def deactivate(self, manager_state: str = "IDLE") -> None:
        """
        Desabilita novas entradas sem fechar posições existentes.
        Usado para pausas, manutenção ou reconfiguração.
        """
        self._write({
            "command":            "DEACTIVATE",
            "permitted":          False,
            "kill_switch":        False,
            "emergency_stop":     False,
            "manager_state":      manager_state,
        })

    def safe_shutdown(self) -> None:
        """
        Inicia encerramento seguro: bloqueia entradas + fecha posições.
        EA executa SafeShutdown() a cada tick até risco zero.
        Usado pelo StrategyManager em CLOSING_POSITIONS.
        """
        self._write({
            "command":            "SAFE_SHUTDOWN",
            "permitted":          False,
            "kill_switch":        False,
            "emergency_stop":     False,
            "manager_state":      "CLOSING_POSITIONS",
        })

    def emergency_stop(self) -> None:
        """
        Kill switch imediato: kill_switch=True força fechamento em qualquer estado.
        Prioridade máxima — o EA fecha tudo sem aguardar confirmação do manager.
        Usado pelo RiskManager quando daily loss ou drawdown é atingido.
        """
        self._write({
            "command":            "EMERGENCY_STOP",
            "permitted":          False,
            "kill_switch":        True,
            "emergency_stop":     True,
            "manager_state":      "CLOSING_POSITIONS",
        })

    def update_risk_limits(
        self,
        daily_loss_limit:   float = 0.0,
        daily_loss_current: float = 0.0,
        max_drawdown_pct:   float = 20.0,
        cooldown_until:     Optional[str] = None,
    ) -> None:
        """
        Atualiza limites de risco sem mudar o estado de permitted/kill_switch.
        Lido pela função IsRiskAcceptable() do EA a cada tick.
        """
        # Lê o arquivo atual para preservar os demais campos
        existing = self._read_current()
        existing.update({
            "daily_loss_limit":   daily_loss_limit,
            "daily_loss_current": daily_loss_current,
            "max_drawdown_pct":   max_drawdown_pct,
            "cooldown_until":     cooldown_until,
        })
        self._write_raw(existing)

    # ── Internos ───────────────────────────────────────────────────────────────

    def _write(self, payload: dict) -> None:
        """Adiciona campos de controle e persiste o arquivo."""
        payload.setdefault("daily_loss_limit",   0.0)
        payload.setdefault("daily_loss_current", 0.0)
        payload.setdefault("max_drawdown_pct",   20.0)
        payload.setdefault("cooldown_until",     None)
        self._write_raw(payload)

    def _write_raw(self, payload: dict) -> None:
        self._seq += 1
        payload["sequence"]  = self._seq
        payload["issued_at"] = datetime.now(timezone.utc).isoformat()
        payload["issued_by"] = "strategy_manager"

        try:
            self._path.write_text(
                json.dumps(payload, indent=2, default=str),
                encoding="utf-8",
            )
            logger.debug(
                "[EAController] control.json atualizado "
                "user=%s strategy=%s cmd=%s seq=%d",
                self.user_id, self.strategy_id,
                payload.get("command", "—"), self._seq,
            )
        except OSError as exc:
            logger.error(
                "[EAController] Falha ao escrever control.json: %s", exc
            )

    def _read_current(self) -> dict:
        """Lê o arquivo atual para operações de patch parcial."""
        try:
            if self._path.exists():
                return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}
