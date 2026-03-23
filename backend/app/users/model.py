from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class PlanType(str, Enum):
    """Tipos de planos de licen?a com cr?ditos de ativa??o."""
    starter = "starter"      # 1 cr?dito
    pro = "pro"              # 5 cr?ditos
    premium = "premium"      # 15 cr?ditos
    enterprise = "enterprise"  # Cr?ditos customizados


class User(BaseModel):
    """Modelo de Usu?rio com suporte a Sistema de Cr?ditos de Ativa??o."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[str] = None
    email: str
    hashed_password: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    
    # OAuth
    auth_provider: str = "local"
    google_id: Optional[str] = None
    
    # Ativa??o e Plano
    is_active: bool = True
    is_superuser: bool = False
    plan: PlanType = PlanType.starter
    
    # ?? SISTEMA DE CR?DITOS DE ATIVA??O
    activation_credits: int = Field(
        default=1,
        description="N?mero de cr?ditos de ativa??o dispon?veis (Starter=1, Pro=5, Premium=15)"
    )
    activation_credits_used: int = Field(
        default=0,
        description="N?mero de cr?ditos j? utilizados para ativar bots"
    )
    
    # Rastreamento
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    login_count: int = 0
    
    # Configura??es
    exchange_api_keys: Dict[str, Any] = Field(
        default_factory=dict,
        description="API Keys armazenadas (encrypted em produ??o)"
    )
    
    @property
    def activation_credits_remaining(self) -> int:
        """Cr?ditos dispon?veis para ativar novos bots."""
        return max(0, self.activation_credits - self.activation_credits_used)
