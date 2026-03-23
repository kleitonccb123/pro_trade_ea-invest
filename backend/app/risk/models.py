"""
Modelos de dados do Risk Manager — DOC-05

Tradução fiel das interfaces TypeScript para dataclasses Python.
Todos os campos monetários usam float (como no spec TS).
Decisões de risco retornam RiskDecision (dict typed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union


# ─── Enums ────────────────────────────────────────────────────────────────────

class RiskSeverity(str, Enum):
    WARN  = "warn"
    BLOCK = "block"
    KILL  = "kill"


class RiskRejectionReason(str, Enum):
    MAX_DAILY_LOSS_REACHED    = "MAX_DAILY_LOSS_REACHED"
    MAX_DRAWDOWN_REACHED      = "MAX_DRAWDOWN_REACHED"
    MAX_CAPITAL_AT_RISK       = "MAX_CAPITAL_AT_RISK"
    MAX_POSITION_SIZE         = "MAX_POSITION_SIZE"
    COOLDOWN_ACTIVE           = "COOLDOWN_ACTIVE"
    BOT_KILLED                = "BOT_KILLED"
    MARKET_VOLATILITY_HIGH    = "MARKET_VOLATILITY_HIGH"
    GLOBAL_KILL_SWITCH        = "GLOBAL_KILL_SWITCH"
    INSUFFICIENT_LIQUIDITY    = "INSUFFICIENT_LIQUIDITY"
    CONSECUTIVE_LOSSES_LIMIT  = "CONSECUTIVE_LOSSES_LIMIT"


# ─── Perfis (persistidos no MongoDB) ─────────────────────────────────────────

@dataclass
class UserRiskProfile:
    """
    Configuração de risco de um usuário.
    Persistida na coleção `risk_user_profiles`.
    """
    user_id: str

    # Versão para controle de migração
    version: int = 1

    # Limites USD
    max_daily_loss_usd: float          = 500.0
    max_drawdown_pct: float            = 20.0    # %
    max_capital_at_risk_pct: float     = 40.0    # % do saldo total
    max_position_size_usd: float       = 2000.0  # por símbolo
    max_aggregated_position_usd: float = 5000.0  # todos os bots somados

    # Cooldowns
    cooldown_after_loss_minutes: int         = 30
    cooldown_after_consecutive_losses: int   = 3   # Nº de perdas que aciona cooldown
    cooldown_duration_minutes: int           = 60

    # Kill automático
    auto_kill_after_loss_breaches: int  = 2   # 2 dias ruins → matar bot

    plan: str = "basic"   # "basic" | "pro" | "enterprise"

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_doc(self) -> Dict[str, Any]:
        return {
            "user_id":                        self.user_id,
            "version":                        self.version,
            "max_daily_loss_usd":             self.max_daily_loss_usd,
            "max_drawdown_pct":               self.max_drawdown_pct,
            "max_capital_at_risk_pct":        self.max_capital_at_risk_pct,
            "max_position_size_usd":          self.max_position_size_usd,
            "max_aggregated_position_usd":    self.max_aggregated_position_usd,
            "cooldown_after_loss_minutes":    self.cooldown_after_loss_minutes,
            "cooldown_after_consecutive_losses": self.cooldown_after_consecutive_losses,
            "cooldown_duration_minutes":      self.cooldown_duration_minutes,
            "auto_kill_after_loss_breaches":  self.auto_kill_after_loss_breaches,
            "plan":                           self.plan,
            "created_at":                     self.created_at,
            "updated_at":                     self.updated_at,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "UserRiskProfile":
        doc = {k: v for k, v in doc.items() if k != "_id"}
        return cls(**{k: doc[k] for k in cls.__dataclass_fields__ if k in doc})


@dataclass
class BotRiskProfile:
    """
    Configuração de risco de um bot específico.
    Persistida na coleção `risk_bot_profiles`.
    """
    bot_id: str
    user_id: str

    max_daily_loss_usd: float    = 200.0
    max_open_positions: int      = 3
    max_single_order_usd: float  = 500.0
    consecutive_loss_limit: int  = 5    # Matar bot após N perdas consecutivas

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_doc(self) -> Dict[str, Any]:
        return {
            "bot_id":                self.bot_id,
            "user_id":               self.user_id,
            "max_daily_loss_usd":    self.max_daily_loss_usd,
            "max_open_positions":    self.max_open_positions,
            "max_single_order_usd":  self.max_single_order_usd,
            "consecutive_loss_limit": self.consecutive_loss_limit,
            "created_at":            self.created_at,
            "updated_at":            self.updated_at,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "BotRiskProfile":
        doc = {k: v for k, v in doc.items() if k != "_id"}
        return cls(**{k: doc[k] for k in cls.__dataclass_fields__ if k in doc})


# ─── Estado diário de risco ───────────────────────────────────────────────────

@dataclass
class RiskState:
    """
    Estado de risco de um usuário em uma data específica.
    Chave composta: user_id + date.
    Reset automático a cada 00:00 UTC (ver DailyResetJob).
    Persistido na coleção `risk_states`.
    """
    user_id: str
    date: str                       # "2025-01-21"  (ISO date, UTC)

    daily_pnl_usd: float            = 0.0
    peak_daily_balance_usd: float   = 0.0   # para cálculo do drawdown
    current_drawdown_pct: float     = 0.0   # (peak - current) / peak * 100
    capital_at_risk_usd: float      = 0.0   # soma de posições abertas

    is_in_cooldown: bool            = False
    cooldown_until: Optional[datetime] = None
    consecutive_losses: int         = 0
    breach_count: int               = 0     # reset semanal

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_doc(self) -> Dict[str, Any]:
        return {
            "user_id":                self.user_id,
            "date":                   self.date,
            "daily_pnl_usd":         self.daily_pnl_usd,
            "peak_daily_balance_usd": self.peak_daily_balance_usd,
            "current_drawdown_pct":   self.current_drawdown_pct,
            "capital_at_risk_usd":    self.capital_at_risk_usd,
            "is_in_cooldown":         self.is_in_cooldown,
            "cooldown_until":         self.cooldown_until,
            "consecutive_losses":     self.consecutive_losses,
            "breach_count":           self.breach_count,
            "created_at":             self.created_at,
            "updated_at":             self.updated_at,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "RiskState":
        doc = {k: v for k, v in doc.items() if k != "_id"}
        return cls(**{k: doc[k] for k in cls.__dataclass_fields__ if k in doc})


# ─── Resultado de avaliação de risco ─────────────────────────────────────────

@dataclass
class RiskDecision:
    """
    Resultado do RiskManager.evaluate().
    """
    approved: bool
    reason: Optional[RiskRejectionReason] = None
    severity: Optional[RiskSeverity]      = None
    details: Optional[str]                = None

    def __bool__(self) -> bool:
        return self.approved

    @classmethod
    def allow(cls) -> "RiskDecision":
        return cls(approved=True)

    @classmethod
    def deny(
        cls,
        reason: RiskRejectionReason,
        severity: RiskSeverity,
        details: str,
    ) -> "RiskDecision":
        return cls(
            approved=False,
            reason=reason,
            severity=severity,
            details=details,
        )


# ─── Input da avaliação ───────────────────────────────────────────────────────

@dataclass
class RiskEvaluationInput:
    """
    Parâmetros de entrada para RiskManager.evaluate().
    """
    user_id: str
    bot_id: str
    symbol: str
    side: str                       # "buy" | "sell"
    estimated_value_usd: float      # Valor total em USD da ordem
    current_position_usd: float     # Posição já aberta em USD neste símbolo
    # closing_side: se True, é uma ordem de fechamento → imune a cooldown
    is_closing_order: bool = False
