"""
Gamification Module - Sistema de pontos, XP, níveis e Arena de Lucros

Organiza toda a lógica de gamificação incluindo:
- Perfis de jogador
- Sistema de pontos e XP
- Ranking de robôs por quinzena
- Recompensas diárias
"""

from app.gamification import router
from app.gamification.model import GameProfile, DailyChest, RobotRanking
from app.gamification.service import GameProfileService, RobotRankingService

__all__ = [
    "router",
    "GameProfile",
    "DailyChest",
    "RobotRanking",
    "GameProfileService",
    "RobotRankingService",
]
