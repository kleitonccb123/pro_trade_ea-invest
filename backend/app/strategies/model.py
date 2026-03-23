"""
DOC-08 — Marketplace de Estratégias
Modelos MongoDB (Pydantic v2) para UserStrategy, StrategyBotInstance e StrategyTrade.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class StrategyStatus(str, Enum):
    draft = "draft"
    testing = "testing"
    backtesting = "backtesting"
    approved = "approved"
    rejected = "rejected"
    published = "published"
    deprecated = "deprecated"
    archived = "archived"


class StrategyCategory(str, Enum):
    trend_following = "trend_following"
    mean_reversion = "mean_reversion"
    scalping = "scalping"
    arbitrage = "arbitrage"
    custom = "custom"


class PricingType(str, Enum):
    free = "free"
    monthly = "monthly"
    one_time = "one_time"


class TradeStatus(str, Enum):
    open = "open"
    closed = "closed"
    cancelled = "cancelled"


class ExitReason(str, Enum):
    tp_hit = "tp_hit"
    sl_hit = "sl_hit"
    manual = "manual"
    strategy_signal = "strategy_signal"


# ──────────────────────────────────────────────────────────────────────────────
# Sub-modelos
# ──────────────────────────────────────────────────────────────────────────────

class StrategyParameter(BaseModel):
    """Parâmetro configurável de uma estratégia."""
    key: str
    label: str
    type: Literal["number", "string", "boolean", "select"]
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    options: Optional[List[str]] = None  # Para tipo 'select'
    required: bool = True
    description: str = ""

    model_config = {"from_attributes": True}


class StrategyPricing(BaseModel):
    type: PricingType = PricingType.free
    amount_usd: float = 0.0
    required_plan: Literal["free", "basic", "pro", "enterprise"] = "free"

    model_config = {"from_attributes": True}


class StrategyPublicMetrics(BaseModel):
    """Métricas verificadas calculadas pelo backtesting aprovado."""
    backtest_period_days: int = 0
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_duration: str = ""
    verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StrategyVersion(BaseModel):
    """Versão imutável de uma estratégia após aprovação."""
    version_id: str
    semver: str                          # ex: "1.2.0"
    code_encrypted: str                  # código cifrado AES-256 (Fernet)
    code_hash: str                       # SHA-256 do código original
    parameters: List[StrategyParameter] = Field(default_factory=list)
    changelog: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    backtest_result_id: Optional[str] = None
    status: StrategyStatus = StrategyStatus.draft

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────────────────────────
# Documentos MongoDB principais
# ──────────────────────────────────────────────────────────────────────────────

class UserStrategy(BaseModel):
    """Documento MongoDB: coleção `strategies`."""
    strategy_id: str                               # UUID gerado na criação
    creator_id: str                                # user_id do criador
    name: str
    description: str = ""
    category: StrategyCategory = StrategyCategory.custom
    exchanges: List[str] = Field(default_factory=list)          # ['kucoin']
    asset_types: List[Literal["spot", "futures"]] = Field(default_factory=lambda: ["spot"])
    current_version: str = ""                      # semver publicada atual
    versions: List[StrategyVersion] = Field(default_factory=list)
    pricing: StrategyPricing = Field(default_factory=StrategyPricing)
    metrics: StrategyPublicMetrics = Field(default_factory=StrategyPublicMetrics)
    total_subscribers: int = 0
    total_revenue_usd: float = 0.0
    is_published: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    # status agregado da estratégia (para gestão interna)
    status: StrategyStatus = StrategyStatus.draft

    model_config = {"from_attributes": True}


class StrategySubscription(BaseModel):
    """Documento MongoDB: coleção `strategy_subscriptions`."""
    subscription_id: str
    user_id: str
    strategy_id: str
    strategy_version: str
    pricing_type: PricingType
    amount_usd: float = 0.0
    payment_ref: Optional[str] = None      # ID do pagamento Perfect Pay
    is_active: bool = True
    subscribed_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # None = sem expiração (one_time)
    canceled_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StrategyBotInstance(BaseModel):
    """Documento MongoDB: coleção `strategy_bot_instances`.
    Criado quando comprador configura a execução de uma estratégia num bot."""
    instance_id: str
    bot_id: Optional[str] = None          # ID do bot na plataforma
    user_id: str
    strategy_id: str
    strategy_version: str
    subscription_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    started_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    stopped_at: Optional[datetime] = None
    stop_reason: Optional[str] = None     # 'canceled', 'teardown', 'manual'

    model_config = {"from_attributes": True}


class StrategyTrade(BaseModel):
    """Documento MongoDB: coleção `strategy_trades`.
    Registro de cada trade executado por uma instância de estratégia."""
    trade_id: str
    instance_id: str
    strategy_id: str
    user_id: str
    symbol: str
    side: Literal["long", "short"]
    entry_price: float
    exit_price: Optional[float] = None
    size: float
    pnl_usd: Optional[float] = None
    pnl_pct: Optional[float] = None
    entry_order_id: str
    exit_order_id: Optional[str] = None
    entry_at: datetime = Field(default_factory=datetime.utcnow)
    exit_at: Optional[datetime] = None
    status: TradeStatus = TradeStatus.open
    exit_reason: Optional[ExitReason] = None
    fees_usd: float = 0.0

    model_config = {"from_attributes": True}


