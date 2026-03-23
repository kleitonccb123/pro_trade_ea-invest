from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class BotState(str, Enum):
    idle = "idle"
    running = "running"
    paused = "paused"
    stopped = "stopped"
    switching = "switching"  # ? Estado de transi??o: limpando rob? antigo


class SwapHistory(BaseModel):
    """Hist?rico de uma troca de configura??o do rob?."""
    model_config = ConfigDict(from_attributes=True)
    
    timestamp: datetime
    old_config: Dict[str, Any]
    new_config: Dict[str, Any]
    credit_charged: bool = False  # Se gastou cr?dito nesta troca
    change_type: str = Field(
        default="config_update",
        description="Tipo de mudan?a: config_update, strategy_change, etc"
    )


class BotConfig(BaseModel):
    """Bot configuration schema."""
    model_config = ConfigDict(from_attributes=True)
    
    amount: float = 1000.0
    stop_loss: float = 5.0
    take_profit: float = 10.0
    risk_level: str = "medium"
    timeframe: str = "5m"
    indicators: List[str] = ["RSI", "MACD"]
    strategy: str = "Custom Strategy"


class Bot(BaseModel):
    """Bot model with execution state."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[str] = None
    user_id: str = Field(..., description="ID do usu?rio dono do bot")  # NOVO CAMPO OBRIGAT?RIO
    name: str
    description: Optional[str] = None
    strategy: str = "Custom Strategy"
    exchange: str = "binance"
    pair: str = "BTC/USDT"
    status: str = "stopped"
    is_running: bool = False
    last_started: Optional[datetime] = None
    config: BotConfig = BotConfig()
    created_at: datetime = datetime.utcnow()
    last_updated: datetime = datetime.utcnow()
    
    # Performance metrics
    profit: float = 0.0
    trades: int = 0
    win_rate: float = 0.0
    runtime: str = "0h 0m"
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    
    # ?? SISTEMA DE CR?DITOS E LIMITES DE TROCA
    is_active_slot: bool = Field(
        default=False,
        description="Indica se este bot est? em um slot ativo (consome cr?dito de ativa??o)"
    )
    activation_credits_used: int = Field(
        default=0,
        description="Quantos cr?ditos de ativa??o foram consumidos para ativar este bot"
    )
    swap_count: int = Field(
        default=0,
        description="N?mero de trocas/reconfigurations j? realizadas neste bot (at? 2 gratuitas)"
    )
    swap_history: List[SwapHistory] = Field(
        default_factory=list,
        description="Hist?rico completo de trocas realizadas"
    )
    last_run_timestamp: Optional[datetime] = Field(
        default=None,
        description="?ltimo timestamp quando o bot foi executado com sucesso"
    )


class BotInstance(BaseModel):
    """Bot instance model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    bot_id: str
    state: BotState = BotState.idle
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()
    last_heartbeat: Optional[datetime] = None
    error_message: Optional[str] = None


class SimulatedTrade(BaseModel):
    """Simulated trade model."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    instance_id: Optional[int] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    timestamp: datetime
    side: str
