"""
Gamification Models - Sistema de Pontos, XP e Níveis (TradePoints Arena)

Define:
- GameProfile: Perfil de gamificação do usuário
- DailyChest: Baú de recompensas diárias
- RobotRanking: Ranking de robôs por performance
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class GameProfile(BaseModel):
    """Perfil de Gamificação do Usuário (TradePoints Arena)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[str] = None
    user_id: str = Field(..., description="ID do usuário proprietário (indexado)")
    
    # 🎯 SISTEMA DE PONTOS
    trade_points: int = Field(
        default=1000,
        ge=0,
        description="Saldo de TradePoints (moeda de gamificação). Default: 1000 (bônus de boas-vindas)"
    )
    
    # 🏆 SISTEMA DE NÍVEL & XP
    level: int = Field(default=1, ge=1, description="Nível atual do usuário (1-100)")
    xp: int = Field(default=0, ge=0, description="XP acumulado (total desde início)")
    
    # 🤖 ROBÔS DESBLOQUEADOS
    unlocked_robots: List[str] = Field(
        default_factory=list,
        description="Lista de IDs dos robôs desbloqueados (ex: ['bot_001', 'bot_002'])"
    )
    
    # 📊 RIQUEZA VISÍVEL (Para UI/Estatísticas)
    lifetime_profit: float = Field(default=0.0, description="Lucro total acumulado em USD")
    
    # 🎁 RECOMPENSAS DIÁRIAS
    last_daily_chest_opened: Optional[datetime] = Field(
        default=None,
        description="Último timestamp quando o baú diário foi aberto"
    )
    last_daily_xp_claimed: Optional[datetime] = Field(
        default=None,
        description="Último timestamp quando XP diário foi reclamado (separado do baú)"
    )
    streak_count: int = Field(
        default=0,
        description="Número de dias consecutivos abrindo baú"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def xp_for_next_level(self) -> int:
        """Calcula XP necessário para próximo nível usando fórmula: XP = 100 × (total_level)²"""
        return 100 * (self.level + 1) ** 2
    
    def xp_progress_percent(self) -> float:
        """Retorna percentual de progresso para próximo nível (0-100) baseado em XP total"""
        total_xp_for_current_level = sum(100 * (i + 1) ** 2 for i in range(self.level))
        total_xp_for_next_level = sum(100 * (i + 1) ** 2 for i in range(self.level + 1))
        
        progress = total_xp_for_next_level - total_xp_for_current_level
        if progress == 0:
            return 0.0
        
        current_level_xp = self.xp - total_xp_for_current_level
        return min(100.0, max(0.0, (current_level_xp / progress) * 100))
    
    def add_xp(self, amount: int) -> bool:
        """
        Adiciona XP e verifica se houve level up.
        
        Returns:
            True se houve level up
        """
        self.xp += amount
        
        # Recalcula nível baseado em XP total
        total_xp_needed = 0
        new_level = 1
        
        while True:
            xp_for_next = 100 * (new_level + 1) ** 2
            if total_xp_needed + xp_for_next > self.xp:
                break
            total_xp_needed += xp_for_next
            new_level += 1
        
        level_up = new_level > self.level
        self.level = new_level
        
        return level_up
    
    def add_trade_points(self, amount: int) -> None:
        """Adiciona TradePoints"""
        self.trade_points += amount
        self.updated_at = datetime.utcnow()


class DailyChest(BaseModel):
    """Recompensa Diária (Daily Chest)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[str] = None
    user_id: str = Field(..., description="ID do usuário")
    
    # Recompensa
    xp_reward: int = Field(default=0, ge=0, description="XP ganho")
    points_reward: int = Field(default=0, ge=0, description="Pontos ganhos")
    
    # Metadata
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RobotRanking(BaseModel):
    """Ranking de Robôs por Performance"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[str] = None
    robot_id: str = Field(..., description="ID do robô")
    user_id: str = Field(..., description="ID do usuário proprietário")
    
    # Performance (atualizado períodicamente)
    profit_24h: float = Field(default=0.0, description="Lucro em 24h")
    profit_7d: float = Field(default=0.0, description="Lucro em 7 dias")
    profit_15d: float = Field(default=0.0, description="Lucro em 15 dias")
    
    win_rate: float = Field(default=0.0, ge=0, le=100, description="Taxa de vitória (%)")
    total_trades: int = Field(default=0, ge=0, description="Total de trades")
    
    # Ranking (atualizado por quinzena = 15 dias)
    biweekly_rank: int = Field(default=500, description="Posição no ranking da quinzena atual")
    biweekly_period: int = Field(default=0, description="Período (quinzena) da última atualização")
    
    # Burnout/Performance Status
    is_on_fire: bool = Field(default=False, description="Flag para status 'ON FIRE' (alta performance)")
    
    # Timestamps
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PlanRewardInfo(BaseModel):
    """Mapeamento de Recompensas por Plano"""
    model_config = ConfigDict(from_attributes=True)
    
    plan_name: str
    monthly_price: float
    initial_points: int
    monthly_bonus_points: int
    
    
# ============================================
# MAPA DE RECOMPENSAS POR PLANO (USD)
# ============================================
PLAN_REWARD_MAP = {
    "starter": {
        "plan_name": "START",
        "currency": "USD",
        "monthly_price": 9.99,
        "robot_slots": 3,
        "initial_points": 500,
        "monthly_bonus_points": 500,
        "initial_xp": 50,
        "xp_boost_multiplier": 1.0,
    },
    "pro": {
        "plan_name": "PRO+",
        "currency": "USD",
        "monthly_price": 11.99,
        "robot_slots": 5,
        "initial_points": 1500,
        "monthly_bonus_points": 1500,
        "initial_xp": 150,
        "xp_boost_multiplier": 1.2,
        "is_most_popular": True,
    },
    "premium": {
        "plan_name": "QUANT",
        "currency": "USD",
        "monthly_price": 17.99,
        "robot_slots": 10,
        "initial_points": 3000,
        "monthly_bonus_points": 3000,
        "initial_xp": 300,
        "xp_boost_multiplier": 1.5,
    },
    "enterprise": {
        "plan_name": "BLACK",
        "currency": "USD",
        "monthly_price": 39.99,
        "robot_slots": 15,
        "initial_points": 10000,
        "monthly_bonus_points": 10000,
        "initial_xp": 1000,
        "xp_boost_multiplier": 2.0,
    },
}

# ============================================
# LOJA DE PONTOS (POINT BUNDLES)
# ============================================
POINT_BUNDLES = {
    "pouch": {
        "name": "Pouch of Points",
        "price": 2.99,
        "currency": "USD",
        "points": 1000,
        "display_order": 1,
    },
    "bag": {
        "name": "Bag of Points",
        "price": 4.99,
        "currency": "USD",
        "points": 2500,
        "display_order": 2,
    },
    "chest": {
        "name": "Chest of Points",
        "price": 9.99,
        "currency": "USD",
        "points": 6000,
        "is_best_value": True,
        "display_order": 3,
    },
}


# ============================================
# MICRO-TRANSAÇÕES (Pacotes Emergenciais)
# Exibidos quando o usuário tenta desbloquear um robô
# e não tem saldo suficiente.
# ============================================
MICRO_BUNDLES = {
    "micro_100": {
        "name": "Boost Rápido",
        "emoji": "⚡",
        "price": 0.49,
        "currency": "USD",
        "points": 100,
        "display_order": 1,
        "description": "Para quem precisa de pouquinho",
    },
    "micro_250": {
        "name": "Impulso",
        "emoji": "🚀",
        "price": 0.99,
        "currency": "USD",
        "points": 250,
        "display_order": 2,
        "description": "O suficiente para desbloquear",
    },
    "micro_500": {
        "name": "Turbo Pack",
        "emoji": "💎",
        "price": 1.49,
        "currency": "USD",
        "points": 500,
        "display_order": 3,
        "description": "Melhor custo-benefício micro",
        "is_best_value": True,
    },
    "micro_1500": {
        "name": "Mega Boost",
        "emoji": "🔥",
        "price": 2.99,
        "currency": "USD",
        "points": 1500,
        "display_order": 4,
        "description": "Desbloqueie qualquer robô Elite",
    },
}
