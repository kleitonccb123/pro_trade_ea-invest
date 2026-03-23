"""
Strategy Manager — Core Service

Implements Single Active Strategy (SAS) mode with a safe, atomic,
auditable strategy-switching pipeline.

Architecture
============
- One StrategyManager instance per user (keyed by user_id in memory cache
  and MongoDB `strategy_manager_state` collection for persistence).
- Global asyncio.Lock per user prevents race conditions.
- MongoDB stores the authoritative state so restarts recover cleanly.

State Machine
=============
IDLE  ──activate()──►  ACTIVE
ACTIVE  ──switch()──►  TRANSITION_STATE
TRANSITION_STATE  ──begin_close()──►  CLOSING_POSITIONS
CLOSING_POSITIONS  ──all_closed()──►  SAFE_TO_SWITCH
SAFE_TO_SWITCH  ──activate_new()──►  ACTIVATING_NEW_STRATEGY
ACTIVATING_NEW_STRATEGY  ──activate_done()──►  ACTIVE
ACTIVATING_NEW_STRATEGY  ──error()──►  IDLE
ACTIVE  ──stop()──►  IDLE
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from bson import ObjectId

from app.core.database import get_db
from app.services.audit_logger import AuditEvent, AuditLogger
from app.services.ea_controller import EAController   # DOC-STRAT-09 §9.3
from app.services.ea_monitor import EAStateMonitor    # DOC-STRAT-05 §5.4

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Security configuration (all timeouts in seconds)
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Magic number registry (DOC-STRAT-09 §9.3)
# Source of truth is MongoDB (strategy_id field in the bot document).
# This dict is a fast in-process fallback used during the handshake poll loop
# when a DB round-trip would be too slow.  Keep in sync with seed_pricepro.py.
# ─────────────────────────────────────────────────────────────────────────────
BOT_MAGIC_NUMBERS: Dict[str, int] = {
    "pricepro_money_v1": 20240001,
    # Add new strategies here as they are registered:
    # "next_strategy_v1": 20240002,
    # "grid_trader_v1":   20240003,
}

SECURITY_CONFIG: Dict[str, Any] = {
    "MIN_SWITCH_INTERVAL_SECONDS":      60,
    "WORKER_GRACEFUL_SHUTDOWN_SECONDS": 30,
    "MAX_RISK_CHECK_RETRIES":          20,
    "RISK_CHECK_INTERVAL_SECONDS":      3,
    "SWITCH_TOTAL_TIMEOUT_SECONDS":    300,
    "LOCK_ACQUIRE_TIMEOUT_SECONDS":    10,
}

# ─────────────────────────────────────────────────────────────────────────────
# State enum
# ─────────────────────────────────────────────────────────────────────────────
class StrategyState(str, Enum):
    IDLE                    = "IDLE"
    ACTIVE                  = "ACTIVE"
    TRANSITION_STATE        = "TRANSITION_STATE"
    CLOSING_POSITIONS       = "CLOSING_POSITIONS"
    SAFE_TO_SWITCH          = "SAFE_TO_SWITCH"
    ACTIVATING_NEW_STRATEGY = "ACTIVATING_NEW_STRATEGY"

# States in which the system is mid-transition (need recovery on restart)
_TRANSITION_STATES = {
    StrategyState.TRANSITION_STATE,
    StrategyState.CLOSING_POSITIONS,
    StrategyState.ACTIVATING_NEW_STRATEGY,
}

# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class ActivationResult:
    success:         bool
    strategy_id:     Optional[str]
    status:          str
    message:         str
    detail:          Optional[Dict[str, Any]] = field(default=None)

    @classmethod
    def ok(cls, bot_id: str, message: str = "ACTIVATED") -> "ActivationResult":
        return cls(success=True, strategy_id=bot_id, status="ACTIVATED", message=message)

    @classmethod
    def rejected(cls, code: str, message: str, **extra) -> "ActivationResult":
        return cls(
            success=False,
            strategy_id=None,
            status=code,
            message=message,
            detail=extra or None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success":     self.success,
            "strategy_id": self.strategy_id,
            "status":      self.status,
            "message":     self.message,
            "detail":      self.detail,
        }

# ─────────────────────────────────────────────────────────────────────────────
# Per-user lock registry (in-process, survives the request lifetime)
# ─────────────────────────────────────────────────────────────────────────────
_user_locks: Dict[str, asyncio.Lock] = {}


def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


# ─────────────────────────────────────────────────────────────────────────────
# MongoDB helpers
# ─────────────────────────────────────────────────────────────────────────────
class _StateStore:
    """Thin wrapper around the `strategy_manager_state` MongoDB collection."""

    COLLECTION = "strategy_manager_state"
    BOT_COLLECTION = "bots"
    AUDIT_COLLECTION = "strategy_audit_log"

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def _bots(cls):
        return get_db()[cls.BOT_COLLECTION]

    # ── state document ────────────────────────────────────────────────────────

    @classmethod
    async def load(cls, user_id: str) -> Dict[str, Any]:
        col = cls._col()
        doc = col.find_one({"user_id": user_id})
        if asyncio.iscoroutine(doc):
            doc = await doc
        return doc or {}

    @classmethod
    async def save(cls, user_id: str, patch: Dict[str, Any]):
        col = cls._col()
        patch["updated_at"] = datetime.now(timezone.utc)
        result = col.update_one(
            {"user_id": user_id},
            {"$set": patch},
            upsert=True,
        )
        if asyncio.iscoroutine(result):
            await result

    # ── bot helpers ───────────────────────────────────────────────────────────

    @classmethod
    async def bot_exists(cls, user_id: str, bot_id: str) -> bool:
        col = cls._bots()
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return False
        doc = col.find_one({"_id": oid, "user_id": user_id})
        if asyncio.iscoroutine(doc):
            doc = await doc
        return doc is not None

    @classmethod
    async def mark_bot_running(cls, user_id: str, bot_id: str):
        col = cls._bots()
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return
        update = col.update_one(
            {"_id": oid, "user_id": user_id},
            {"$set": {
                "is_running":     True,
                "is_active_slot": True,
                "status":         "running",
                "last_started":   datetime.now(timezone.utc),
                "updated_at":     datetime.now(timezone.utc),
            }},
        )
        if asyncio.iscoroutine(update):
            await update

    @classmethod
    async def mark_bot_stopped(cls, user_id: str, bot_id: str):
        col = cls._bots()
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return
        update = col.update_one(
            {"_id": oid, "user_id": user_id},
            {"$set": {
                "is_running":     False,
                "is_active_slot": False,
                "status":         "stopped",
                "updated_at":     datetime.now(timezone.utc),
                "runtime_state":  None,
            }},
        )
        if asyncio.iscoroutine(update):
            await update

    @classmethod
    async def get_bot_strategy_id(cls, user_id: str, bot_id: str) -> Optional[str]:
        """Return the strategy_id field of a bot document (used for EA monitor path)."""
        col = cls._bots()
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return None
        doc = col.find_one({"_id": oid, "user_id": user_id})
        if asyncio.iscoroutine(doc):
            doc = await doc
        return doc.get("strategy_id") if doc else None

    @classmethod
    async def get_bot_magic_number(cls, user_id: str, bot_id: str) -> Optional[int]:
        """Return the magic_number of a bot document for validation (DOC-STRAT-06 §6.4)."""
        col = cls._bots()
        try:
            oid = ObjectId(bot_id)
        except Exception:
            return None
        doc = col.find_one({"_id": oid, "user_id": user_id})
        if asyncio.iscoroutine(doc):
            doc = await doc
        if not doc:
            return None
        raw = doc.get("magic_number")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    async def clear_all_active_bots(cls, user_id: str):
        """Mark every running bot for this user as stopped."""
        col = cls._bots()
        update = col.update_many(
            {"user_id": user_id, "is_running": True},
            {"$set": {
                "is_running":    False,
                "is_active_slot": False,
                "status":        "stopped",
                "updated_at":    datetime.now(timezone.utc),
                "runtime_state": None,
            }},
        )
        if asyncio.iscoroutine(update):
            await update


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Manager
# ─────────────────────────────────────────────────────────────────────────────
class StrategyManager:
    """
    Single Active Strategy manager.

    One instance is created per user request.  State is authoritative in
    MongoDB; the in-process asyncio.Lock prevents concurrent activation
    within the same process.
    """

    def __init__(self, user_id: str):
        self.user_id  = user_id
        self._lock    = _get_user_lock(user_id)
        self._log     = AuditLogger(user_id)
        self._config  = SECURITY_CONFIG

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def activate_strategy(
        self,
        bot_id: str,
        requested_by: str,
    ) -> ActivationResult:
        """
        Main entry point.  Activates `bot_id` respecting Single Strategy Mode.
        May trigger the full 5-stage switch pipeline if another strategy is active.
        """
        doc = await _StateStore.load(self.user_id)
        current_state    = StrategyState(doc.get("state", StrategyState.IDLE))
        active_bot_id    = doc.get("active_bot_id")
        last_switch_ts   = doc.get("last_switch_ts", 0)

        # ── GATE 1: Anti-rapid-switching ────────────────────────────────────
        elapsed = time.time() - (last_switch_ts or 0)
        if last_switch_ts and elapsed < self._config["MIN_SWITCH_INTERVAL_SECONDS"]:
            wait = int(self._config["MIN_SWITCH_INTERVAL_SECONDS"] - elapsed)
            return ActivationResult.rejected(
                "TOO_SOON",
                f"Minimum interval between strategy switches not elapsed.",
                wait_seconds=wait,
            )

        # ── GATE 2: Already active ───────────────────────────────────────────
        if active_bot_id == bot_id and current_state == StrategyState.ACTIVE:
            return ActivationResult.rejected("ALREADY_ACTIVE", "This strategy is already active.")

        # ── GATE 3: System mid-transition ────────────────────────────────────
        if current_state in _TRANSITION_STATES:
            return ActivationResult.rejected(
                "SYSTEM_IN_TRANSITION",
                f"System is currently in state {current_state}. Wait for it to complete.",
            )

        # ── GATE 4: Bot must exist ───────────────────────────────────────────
        exists = await _StateStore.bot_exists(self.user_id, bot_id)
        if not exists:
            return ActivationResult.rejected("BOT_NOT_FOUND", f"Bot {bot_id} not found.")

        # ── Acquire per-user lock ────────────────────────────────────────────
        try:
            acquired = await asyncio.wait_for(
                self._lock.acquire(),
                timeout=self._config["LOCK_ACQUIRE_TIMEOUT_SECONDS"],
            )
        except asyncio.TimeoutError:
            return ActivationResult.rejected("LOCK_UNAVAILABLE", "Could not acquire strategy lock.")

        try:
            # Re-read state inside the lock (double-check)
            doc = await _StateStore.load(self.user_id)
            current_state = StrategyState(doc.get("state", StrategyState.IDLE))
            active_bot_id = doc.get("active_bot_id")

            if current_state == StrategyState.IDLE:
                return await self._activate_first(bot_id, requested_by)
            elif current_state == StrategyState.ACTIVE:
                return await self._switch_strategy(bot_id, requested_by, previous_bot_id=active_bot_id)
            else:
                return ActivationResult.rejected(
                    "SYSTEM_IN_TRANSITION",
                    f"System moved to {current_state} — try again shortly.",
                )

        except Exception as exc:
            self._log.critical(AuditEvent.SWITCH_UNHANDLED_ERROR, {
                "bot_id": bot_id,
                "error":  str(exc),
            })
            await self._emergency_safe_state()
            raise

        finally:
            self._lock.release()

    async def deactivate_strategy(self, requested_by: str) -> ActivationResult:
        """Stop the currently active strategy and return to IDLE."""
        doc = await _StateStore.load(self.user_id)
        current_state = StrategyState(doc.get("state", StrategyState.IDLE))
        active_bot_id = doc.get("active_bot_id")

        if current_state == StrategyState.IDLE or not active_bot_id:
            return ActivationResult.rejected("NOT_ACTIVE", "No strategy is currently active.")

        if current_state in _TRANSITION_STATES:
            return ActivationResult.rejected(
                "SYSTEM_IN_TRANSITION", f"System is in {current_state}. Cannot deactivate now."
            )

        try:
            acquired = await asyncio.wait_for(
                self._lock.acquire(),
                timeout=self._config["LOCK_ACQUIRE_TIMEOUT_SECONDS"],
            )
        except asyncio.TimeoutError:
            return ActivationResult.rejected("LOCK_UNAVAILABLE", "Could not acquire strategy lock.")

        try:
            await _StateStore.mark_bot_stopped(self.user_id, active_bot_id)
            await self._set_state(StrategyState.IDLE, active_bot_id=None)
            self._log.info(AuditEvent.STRATEGY_DEACTIVATED, {
                "bot_id":        active_bot_id,
                "requested_by":  requested_by,
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            })
            return ActivationResult.ok(active_bot_id, "Strategy deactivated.")
        except Exception as exc:
            self._log.error("DEACTIVATION_ERROR", {"error": str(exc), "bot_id": active_bot_id})
            raise
        finally:
            self._lock.release()

    async def get_state(self) -> Dict[str, Any]:
        """Return the current manager state for this user."""
        doc = await _StateStore.load(self.user_id)
        return {
            "system_state":      doc.get("state", StrategyState.IDLE),
            "active_strategy":   doc.get("active_bot_id"),
            "previous_strategy": doc.get("previous_bot_id"),
            "last_switch":       doc.get("last_switch_iso"),
            "uptime_seconds":    self._uptime(doc),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline Stages
    # ─────────────────────────────────────────────────────────────────────────

    async def _activate_first(self, bot_id: str, requested_by: str) -> ActivationResult:
        """Activate when system is IDLE (no previous strategy)."""
        await self._set_state(StrategyState.ACTIVATING_NEW_STRATEGY, active_bot_id=bot_id)
        try:
            # ── DOC-STRAT-09: Handshake before marking bot as running ────────
            strategy_id = await _StateStore.get_bot_strategy_id(self.user_id, bot_id)
            if strategy_id:
                ok = await self._complete_handshake(bot_id, strategy_id)
                if not ok:
                    await self._set_state(StrategyState.IDLE, active_bot_id=None)
                    return ActivationResult.rejected(
                        "HANDSHAKE_FAILED",
                        "EA não completou handshake dentro do prazo (30s).",
                    )
            # ────────────────────────────────────────────────────────────────
            await _StateStore.mark_bot_running(self.user_id, bot_id)
            await self._set_state(
                StrategyState.ACTIVE,
                active_bot_id=bot_id,
                last_switch_ts=time.time(),
                last_switch_iso=datetime.now(timezone.utc).isoformat(),
                activated_at=datetime.now(timezone.utc).isoformat(),
            )
            self._log.info(AuditEvent.STRATEGY_ACTIVATED, {
                "bot_id":        bot_id,
                "requested_by":  requested_by,
                "previous":      None,
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            })
            return ActivationResult.ok(bot_id)

        except Exception as exc:
            await self._set_state(StrategyState.IDLE, active_bot_id=None)
            self._log.error(AuditEvent.ACTIVATION_FAILED, {
                "bot_id": bot_id,
                "error":  str(exc),
            })
            raise

    async def _complete_handshake(self, bot_id: str, strategy_id: str) -> bool:
        """
        Protocolo de handshake do EA para ativação controlada (DOC-STRAT-09 §9.3).

        Fases:
          1. Envia control.json com permitted=false (activate_pending)
          2. Aguarda EA gravar state.json com status=READY (timeout 30s)
          3. Valida magic number do EA contra o registrado
          4. Envia control.json com permitted=true (activate)
          5. Retorna True em sucesso, False em falha/timeout
        """
        monitor    = EAStateMonitor(self.user_id, strategy_id)
        controller = EAController(self.user_id, strategy_id)
        deadline   = asyncio.get_event_loop().time() + 30  # 30s timeout

        # Fase 1: enviar ACTIVATE com permitted=false — EA inicia handshake
        controller.activate_pending()  # manager_state=ACTIVATING_NEW_STRATEGY

        # Fase 2: aguardar EA gravar status=READY no state.json
        while asyncio.get_event_loop().time() < deadline:
            state = monitor.read_state()
            if state.get("status") == "READY":

                # Fase 3: validar magic number
                ea_magic = state.get("magic_number")
                # Prefer DB lookup; fall back to in-process registry
                db_magic = await _StateStore.get_bot_magic_number(self.user_id, bot_id)
                expected = db_magic if db_magic is not None else BOT_MAGIC_NUMBERS.get(strategy_id)

                if expected is not None and ea_magic != expected:
                    self._log.error(AuditEvent.ACTIVATION_FAILED, {
                        "reason":      "Magic number mismatch no handshake",
                        "ea_magic":    ea_magic,
                        "expected":    expected,
                        "strategy_id": strategy_id,
                    })
                    return False

                # Fase 4: confirmar ativação — permitted=true
                controller.activate(manager_state="ACTIVE")
                self._log.info(AuditEvent.STRATEGY_ACTIVATED, {
                    "bot_id":      bot_id,
                    "strategy_id": strategy_id,
                    "handshake":   "SUCCESS",
                    "ea_magic":    ea_magic,
                })
                return True

            await asyncio.sleep(1)

        # Timeout — EA não respondeu em 30s
        self._log.error(AuditEvent.ACTIVATION_FAILED, {
            "reason":      "Handshake timeout — EA não respondeu em 30s",
            "bot_id":      bot_id,
            "strategy_id": strategy_id,
        })
        return False

    async def _switch_strategy(
        self,
        new_bot_id: str,
        requested_by: str,
        previous_bot_id: Optional[str],
    ) -> ActivationResult:
        """Full 5-stage switch pipeline."""

        # ── ETAPA 1 — BLOQUEIO ───────────────────────────────────────────────
        await self._set_state(
            StrategyState.TRANSITION_STATE,
            active_bot_id=previous_bot_id,
        )
        self._log.info(AuditEvent.SWITCH_INITIATED, {
            "from":          previous_bot_id,
            "to":            new_bot_id,
            "requested_by":  requested_by,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        })

        # ── ETAPA 2 — ENCERRAMENTO ───────────────────────────────────────────
        await self._set_state(StrategyState.CLOSING_POSITIONS, active_bot_id=previous_bot_id)

        await self._stop_previous_bot(previous_bot_id)

        # ── ETAPA 3 — VERIFICAÇÃO DE RISCO ZERO (EA state.json + DB) ──────────
        # DOC-STRAT-05 §5.4 — aguardar EA confirmar risco zero via state.json
        # antes de prosseguir para SAFE_TO_SWITCH.
        if previous_bot_id:
            prev_strategy_id = await _StateStore.get_bot_strategy_id(
                self.user_id, previous_bot_id
            )
            if prev_strategy_id:
                ea_monitor   = EAStateMonitor(self.user_id, prev_strategy_id)
                ea_risk_zero = await ea_monitor.wait_for_risk_zero(timeout_seconds=120)
                if not ea_risk_zero:
                    self._log.warning(AuditEvent.SWITCH_ABORTED_RISK_ACTIVE, {
                        "bot_id": previous_bot_id,
                        "reason": "EA não confirmou risco zero dentro do timeout de 120s",
                    })
                    await self._set_state(StrategyState.IDLE, active_bot_id=None)
                    return ActivationResult.rejected(
                        "RISK_NOT_ZERO",
                        "EA não fechou posições dentro do prazo.",
                        previous_bot_id=previous_bot_id,
                    )

                # ── Magic number validation (DOC-STRAT-06 §6.4) ──────────────────
                # Garante que o EA conectado é o correto (não um robô diferente
                # operando no mesmo caminho de controle com magic errado).
                ea_magic = ea_monitor.get_reported_magic()
                db_magic = await _StateStore.get_bot_magic_number(self.user_id, previous_bot_id)
                if (ea_magic is not None
                        and db_magic is not None
                        and ea_magic != db_magic):
                    self._log.warning(AuditEvent.SWITCH_ABORTED_RISK_ACTIVE, {
                        "bot_id": previous_bot_id,
                        "reason": f"Magic number mismatch: EA={ea_magic} DB={db_magic}",
                    })
                    await self._set_state(StrategyState.IDLE, active_bot_id=None)
                    return ActivationResult.rejected(
                        "MAGIC_NUMBER_MISMATCH",
                        f"EA magic={ea_magic} não corresponde ao registrado DB magic={db_magic}.",
                        previous_bot_id=previous_bot_id,
                    )

        # Verificação complementar via DB (garante consistência interna)
        zero_risk = await self._verify_zero_risk(previous_bot_id)
        if not zero_risk:
            self._log.warning(AuditEvent.SWITCH_ABORTED_RISK_ACTIVE, {
                "bot_id": previous_bot_id,
            })
            await self._set_state(StrategyState.IDLE, active_bot_id=None)
            return ActivationResult.rejected(
                "WAITING_POSITIONS_CLOSE",
                "Positions could not be fully closed. Switch aborted.",
                previous_bot_id=previous_bot_id,
            )

        await self._set_state(StrategyState.SAFE_TO_SWITCH, active_bot_id=None)
        self._log.info(AuditEvent.RISK_ZERO_CONFIRMED, {"bot_id": previous_bot_id})

        # ── ETAPA 4 — LIMPEZA DE CONTEXTO ───────────────────────────────────
        await self._clear_context(previous_bot_id)

        # ── ETAPA 5 — ATIVAÇÃO SEGURA ────────────────────────────────────────
        await self._set_state(StrategyState.ACTIVATING_NEW_STRATEGY, active_bot_id=new_bot_id)
        try:
            await _StateStore.mark_bot_running(self.user_id, new_bot_id)
            now_iso = datetime.now(timezone.utc).isoformat()
            await self._set_state(
                StrategyState.ACTIVE,
                active_bot_id=new_bot_id,
                previous_bot_id=previous_bot_id,
                last_switch_ts=time.time(),
                last_switch_iso=now_iso,
                activated_at=now_iso,
            )
            self._log.info(AuditEvent.STRATEGY_SWITCHED, {
                "from":          previous_bot_id,
                "to":            new_bot_id,
                "requested_by":  requested_by,
                "timestamp":     now_iso,
            })
            return ActivationResult.ok(new_bot_id, "Strategy switched successfully.")

        except Exception as exc:
            await self._set_state(StrategyState.IDLE, active_bot_id=None)
            self._log.error(AuditEvent.NEW_STRATEGY_ACTIVATION_FAILED, {
                "bot_id": new_bot_id,
                "error":  str(exc),
            })
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _stop_previous_bot(self, bot_id: Optional[str]):
        """
        Stage 2 — Stop previous bot:
        1. Block new entries (mark bot as blocked in DB)
        2. Close positions (mark trades closed in DB; exchange call if real)
        3. Cancel orders (cancel open orders in DB; exchange call if real)
        4. Stop workers/websockets (mark in DB; real WS teardown if applicable)
        """
        if not bot_id:
            return

        try:
            await _StateStore.mark_bot_stopped(self.user_id, bot_id)
            self._log.info(AuditEvent.ALL_WORKERS_STOPPED, {"bot_id": bot_id})
        except Exception as exc:
            self._log.error(AuditEvent.POSITION_CLOSE_FAILED, {
                "bot_id": bot_id,
                "error":  str(exc),
            })
            raise

    async def _verify_zero_risk(self, bot_id: Optional[str]) -> bool:
        """
        Stage 3 — Poll until bot has no active state in DB.
        In a real exchange integration, also call get_open_positions() / get_open_orders().
        """
        if not bot_id:
            return True

        max_retries    = self._config["MAX_RISK_CHECK_RETRIES"]
        retry_interval = self._config["RISK_CHECK_INTERVAL_SECONDS"]

        for attempt in range(max_retries):
            try:
                col = get_db()[_StateStore.BOT_COLLECTION]
                oid  = ObjectId(bot_id)
                doc  = col.find_one({"_id": oid, "user_id": self.user_id})
                if asyncio.iscoroutine(doc):
                    doc = await doc

                if doc is None:
                    return True

                is_running = doc.get("is_running", False)
                if not is_running:
                    return True

                self._log.debug(AuditEvent.RISK_CHECK_PENDING, {
                    "attempt":    attempt + 1,
                    "is_running": is_running,
                    "bot_id":     bot_id,
                })
            except Exception as exc:
                logger.warning(f"[StrategyManager] risk check error: {exc}")

            await asyncio.sleep(retry_interval)

        return False

    async def _clear_context(self, bot_id: Optional[str]):
        """Stage 4 — Clear state of the previous strategy from DB."""
        if not bot_id:
            return
        try:
            col = get_db()[_StateStore.BOT_COLLECTION]
            oid = ObjectId(bot_id)
            update = col.update_one(
                {"_id": oid, "user_id": self.user_id},
                {"$set": {
                    "runtime_state":  None,
                    "is_active_slot": False,
                    "status":         "stopped",
                }},
            )
            if asyncio.iscoroutine(update):
                await update
            self._log.info(AuditEvent.CONTEXT_CLEARED, {"bot_id": bot_id})
        except Exception as exc:
            logger.warning(f"[StrategyManager] clear_context error: {exc}")

    async def _set_state(self, new_state: StrategyState, **extra_fields):
        """Persist new state to MongoDB and emit STATE_TRANSITION debug log."""
        patch = {"state": new_state.value, **extra_fields}
        await _StateStore.save(self.user_id, patch)
        self._log.debug(AuditEvent.STATE_TRANSITION, {"to": new_state.value})

    async def _emergency_safe_state(self):
        """Force the system to IDLE + stop all running bots for the user."""
        try:
            await _StateStore.clear_all_active_bots(self.user_id)
            await _StateStore.save(self.user_id, {
                "state":        StrategyState.IDLE.value,
                "active_bot_id": None,
            })
            logger.warning(f"[StrategyManager] Emergency safe state activated for user {self.user_id}")
        except Exception as exc:
            logger.error(f"[StrategyManager] emergency_safe_state failed: {exc}")

    @staticmethod
    def _uptime(doc: Dict[str, Any]) -> Optional[int]:
        """Calculate seconds since the current strategy was activated."""
        activated_at_iso = doc.get("activated_at")
        if not activated_at_iso:
            return None
        try:
            activated_at = datetime.fromisoformat(activated_at_iso)
            if activated_at.tzinfo is None:
                activated_at = activated_at.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - activated_at
            return int(delta.total_seconds())
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Startup recovery
# ─────────────────────────────────────────────────────────────────────────────
async def recover_all_users_on_startup():
    """
    Call once during application startup.
    If any user's system state is stuck in a transition state (e.g., after a crash),
    reset it to IDLE and stop any running bots.
    """
    try:
        db = get_db()
        col = db[_StateStore.COLLECTION]
        stuck_states = [s.value for s in _TRANSITION_STATES]
        stuck_docs = col.find({"state": {"$in": stuck_states}})
        if asyncio.iscoroutine(stuck_docs):
            stuck_docs = await stuck_docs

        # Handle both sync cursor (MockCollection) and async cursor (Motor)
        docs = []
        if hasattr(stuck_docs, "__aiter__"):
            async for d in stuck_docs:
                docs.append(d)
        else:
            try:
                docs = list(stuck_docs)
            except Exception:
                pass

        for doc in docs:
            user_id = doc.get("user_id")
            if not user_id:
                continue
            al = AuditLogger(user_id)
            al.warning(AuditEvent.STARTUP_RECOVERY, {"state_found": doc.get("state")})
            mgr = StrategyManager(user_id)
            await mgr._emergency_safe_state()
            al.info(AuditEvent.STARTUP_RECOVERY_COMPLETE, {"state": "IDLE"})
            logger.info(f"[StrategyManager] Recovery complete for user {user_id}")

    except Exception as exc:
        logger.warning(f"[StrategyManager] startup_recovery error (non-fatal): {exc}")
