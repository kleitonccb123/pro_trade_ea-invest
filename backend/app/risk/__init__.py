"""
risk — Módulo de Risk Management Institucional (DOC-05) + DOC-07

Exportações principais:
  RiskManager        — Gate institucional; evaluate() + record_trade_closed()
  RiskRepository     — CRUD de perfis e estados de risco no MongoDB
  RiskAuditLog       — Log imutável com hash encadeado
  MarketVolatilityIndexer — Índice de volatilidade intraday (proxy VIX)
  DailyResetJob      — Job cron de reset diário (00:00 UTC)
  UserRiskProfile, BotRiskProfile, RiskState, RiskDecision — modelos de dados

  --- DOC-07 ---
  PositionRiskManager — Gerenciador de risco por posição (BotWorker)
  RiskConfig          — Configuração de risco por bot
  StopReason          — Enum de motivos de parada
  KillSwitchService   — Serviço de kill switch Redis (global / usuário / bot)
"""

from app.risk.models import (
    UserRiskProfile,
    BotRiskProfile,
    RiskState,
    RiskDecision,
    RiskRejectionReason,
    RiskSeverity,
)
from app.risk.repository import RiskRepository
from app.risk.audit_log import RiskAuditLog
from app.risk.volatility_indexer import MarketVolatilityIndexer
from app.risk.risk_manager import RiskManager, get_risk_manager, init_risk_manager
from app.risk.daily_reset_job import DailyResetJob

# DOC-07: per-position risk management
from app.risk.manager import PositionRiskManager, RiskConfig, StopReason
from app.risk.kill_switch import KillSwitchService

__all__ = [
    # Institutional (pre-order gate)
    "UserRiskProfile",
    "BotRiskProfile",
    "RiskState",
    "RiskDecision",
    "RiskRejectionReason",
    "RiskSeverity",
    "RiskRepository",
    "RiskAuditLog",
    "MarketVolatilityIndexer",
    "RiskManager",
    "get_risk_manager",
    "init_risk_manager",
    "DailyResetJob",
    # Per-position / session (DOC-07)
    "PositionRiskManager",
    "RiskConfig",
    "StopReason",
    "KillSwitchService",
]
