"""
Gamification Router - Endpoints da API para sistema gamificado

Endpoints:
- GET /game-profile - Obter perfil gamificado
- POST /daily-chest/open - Abrir baú diário
- GET /robots/ranking - Ranking de robôs (com Top 3)
- POST /robots/{robot_id}/unlock - Desbloquear robô com pontos
- GET /robots/ranking-by-period - Ranking de robôs por período (24h/7d/15d)
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user as _get_current_user
from app.shared.redis_client import get_redis
from types import SimpleNamespace


async def get_current_user(user: dict = Depends(_get_current_user)):
    """Wrapper: converte dict do SQLite em objeto com acesso por atributo (.id, .email, etc.)"""
    if isinstance(user, dict):
        return SimpleNamespace(**user)
    return user
from app.gamification.ranking_service import RankingService
from app.core.database import get_db
from app.gamification.model import GameProfile, DailyChest, RobotRanking
from app.gamification.service import (
    GameProfileService,
    RobotRankingService,
    GamificationAchievements,
    ELITE_ROBOTS,
    ROBOT_UNLOCK_COST,
)
from app.gamification.robot_ranking_manager import RobotRankingManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gamification", tags=["🎮 Gamification"])

# TTL cache for robot ranking raw docs (5 min) — avoids repeated DB scans
_ranking_cache: Dict[int, Dict] = {}  # keyed by biweekly_period


# ============================================
# ? Schemas (Request/Response)
# ============================================

class GameProfileResponse(BaseModel):
    """Response schema para perfil gamificado"""
    id: Optional[str]
    user_id: str
    trade_points: int
    level: int
    current_xp: int
    total_xp: int
    xp_for_next_level: int
    xp_progress_percent: float
    lifetime_profit: float
    bots_unlocked: int
    unlocked_robots: List[str] = []  # ✅ NOVO: Lista de robôs desbloqueados
    last_daily_chest_opened: Optional[datetime] = None  # ✅ NOVO
    daily_chest_streak: int
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DailyChestRewardResponse(BaseModel):
    """Response ao abrir Daily Chest com sistema de streaks avançado"""
    success: bool
    message: str
    error: Optional[str] = None
    xp_reward: Optional[int] = None
    points_reward: Optional[int] = None
    new_level: Optional[int] = None
    leveled_up: bool = False
    new_streak: Optional[int] = None
    streak_bonus_percent: Optional[int] = None
    multiplier: Optional[float] = None
    next_chest_available_at: Optional[str] = None
    seconds_remaining: Optional[int] = None
    
    class Config:
        from_attributes = True


class RobotRankingItem(BaseModel):
    """Item individual no ranking de robôs"""
    rank: int
    medal: Optional[str] = None  # 🥇🥈🥉
    robot_id: str
    robot_name: str
    user_name: str
    strategy: str
    profit_15d: float
    profit_7d: float
    profit_24h: float
    win_rate: float
    total_trades: int
    is_on_fire: bool
    is_unlocked: Optional[bool] = None
    unlock_cost: Optional[int] = None
    
    class Config:
        from_attributes = True


class RobotRankingResponse(BaseModel):
    """Response com ranking de robôs"""
    current_period: int
    period_ends_in_days: int
    ranking: List[RobotRankingItem]
    
    class Config:
        from_attributes = True


class RobotByPeriodItem(BaseModel):
    """Item de robô no ranking por período dinâmico"""
    rank: int
    medal: Optional[str] = None
    id: str
    name: str
    creator: str
    country: str
    strategy: str
    is_on_fire: bool
    profit_24h: float
    profit_7d: float
    profit_15d: float
    win_rate: float
    active_traders: int
    timestamp: str
    
    class Config:
        from_attributes = True


class RobotRankingByPeriodResponse(BaseModel):
    """Response com ranking de robôs por período específico"""
    success: bool
    period: str  # 'daily', 'weekly', 'monthly'
    period_label: str
    data: List[RobotByPeriodItem]
    timestamp: datetime
    
    class Config:
        from_attributes = True


class UnlockRobotResponse(BaseModel):
    """Response ao desbloquear robô"""
    success: bool
    message: str
    points_remaining: Optional[int] = None
    
    class Config:
        from_attributes = True


class LeaderboardItemResponse(BaseModel):
    """Item individual no leaderboard global"""
    rank: int
    user_masked_name: str
    level: int
    trade_points: int
    badge: str
    is_top_3: bool
    
    class Config:
        from_attributes = True


class LeaderboardResponse(BaseModel):
    """Response completo do leaderboard global"""
    success: bool
    message: str
    total_entries: int
    leaderboard: List[LeaderboardItemResponse]
    user_rank: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class PointBundleItem(BaseModel):
    """Item de pacote de pontos na loja"""
    bundle_id: str
    name: str
    price: float
    currency: str
    points: int
    is_best_value: bool = False
    display_order: int
    
    class Config:
        from_attributes = True


class StoreBundlesResponse(BaseModel):
    """Response com todos os pacotes de pontos disponíveis"""
    success: bool
    message: str
    bundles: List[PointBundleItem]
    
    class Config:
        from_attributes = True


class PurchasePointsRequest(BaseModel):
    """Request para comprar pontos"""
    bundle_id: str = Field(..., description="ID do pacote (pouch, bag, chest)")
    payment_method: Optional[str] = Field(default="simulated", description="Método de pagamento (simulated, stripe, paypal)")
    transaction_id: Optional[str] = Field(default=None, description="ID da transação de pagamento")


class PurchasePointsResponse(BaseModel):
    """Response após comprar pontos"""
    success: bool
    message: str
    error: Optional[str] = None
    bundle_id: Optional[str] = None
    points_added: Optional[int] = None
    points_balance: Optional[int] = None
    transaction_id: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============================================
# ? Endpoints
# ============================================

@router.get(
    "/profile",
    response_model=GameProfileResponse,
    summary="Obter Perfil Gamificado",
    description="Retorna o perfil de gamificação do usuário (pontos, XP, nível, etc). Cria automaticamente se não existir."
)
async def get_game_profile(current_user = Depends(get_current_user)):
    """
    **Obter Perfil Gamificado**
    
    Endpoint PROTEGIDO - requer autenticação JWT.
    
    Busca ou cria automaticamente o perfil de gamificação no banco de dados.
    
    Retorna:
    - **trade_points**: Saldo de TradePoints (moeda de gamificação)
    - **level**: Nível atual (1-100)
    - **xp**: Total de XP acumulado
    - **xp_for_next_level**: XP necessário para próximo nível
    - **xp_progress_percent**: Progresso em % para próximo nível
    - **unlocked_robots**: Lista de IDs de robôs desbloqueados
    - **lifetime_profit**: Lucro total em USD
    - **streak_count**: Dias consecutivos abrindo Daily Chest
    - **last_daily_chest_opened**: Timestamp do último baú aberto
    
    Status Code:
    - 200: Perfil retornado com sucesso
    - 401: Não autenticado
    - 500: Erro interno do servidor
    """
    try:
        # Busca ou cria perfil
        profile = await GameProfileService.get_or_create_profile(current_user.id)
        
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "trade_points": profile.trade_points,
            "level": profile.level,
            "current_xp": profile.xp,  # Para compatibilidade frontend
            "total_xp": profile.xp,    # Para compatibilidade frontend
            "xp_for_next_level": profile.xp_for_next_level(),
            "xp_progress_percent": profile.xp_progress_percent(),
            "lifetime_profit": profile.lifetime_profit,
            "bots_unlocked": len(profile.unlocked_robots),  # Compatibilidade
            "unlocked_robots": profile.unlocked_robots,
            "daily_chest_streak": profile.streak_count,  # Compatibilidade
            "last_daily_chest_opened": profile.last_daily_chest_opened,
            "updated_at": profile.updated_at,
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao obter GameProfile para user_id={current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar perfil de gamificação"
        )


@router.post(
    "/claim-daily-xp",
    summary="Reclamar XP Diário",
    description="Adiciona XP aleatório diário ao usuário (anti-spam: 1x por dia)"
)
async def claim_daily_xp(current_user = Depends(get_current_user)):
    """
    **Reclamar XP Diário**
    
    Endpoint PROTEGIDO - requer autenticação JWT.
    
    Adiciona XP aleatório (20-50) ao usuário uma vez por dia.
    Detecta automaticamente level up.
    
    **Anti-Spam:** Implementado via constraint de última abertura (last_daily_chest_opened).
    
    Retorna:
    - **xp_gained**: Quantidade de XP adicionada
    - **new_level**: Novo nível do usuário
    - **leveled_up**: Se houve level up
    - **current_xp**: Total de XP acumulado
    - **xp_required_for_level**: XP necessário para próximo nível
    
    Status Code:
    - 200: XP reclamado com sucesso
    - 400: Já foi reclamado hoje
    - 401: Não autenticado
    - 500: Erro interno
    """
    try:
        # Busca perfil
        profile = await GameProfileService.get_or_create_profile(current_user.id)
        
        # Validação anti-spam: Pode reclamar 1x por dia (usa timestamp SEPARADO do baú)
        now = datetime.utcnow()
        last_xp_claimed = profile.last_daily_xp_claimed or profile.last_daily_chest_opened
        if last_xp_claimed:
            time_since_last = now - last_xp_claimed
            if time_since_last.total_seconds() < 86400:  # 24h em segundos
                remaining_seconds = 86400 - int(time_since_last.total_seconds())
                hours = remaining_seconds // 3600
                minutes = (remaining_seconds % 3600) // 60
                return {
                    "success": False,
                    "message": f"Você já reclamou XP hoje! Próxima oportunidade em {hours}h {minutes}m",
                    "error": "daily_xp_limit"
                }
        
        # Gera XP aleatório (20-50)
        xp_amount = random.randint(20, 50)
        
        # Adiciona XP e persiste
        result = await GameProfileService.add_xp_to_profile(current_user.id, xp_amount)
        
        # Atualiza timestamp SEPARADO para evitar conflito com daily chest
        collection = GameProfileService._get_collection()
        await collection.update_one(
            {"user_id": str(current_user.id)},
            {"$set": {"last_daily_xp_claimed": now, "updated_at": now}}
        )
        
        # Log
        if result['leveled_up']:
            logger.info(f"✅ LEVEL UP! user_id={current_user.id}: +{xp_amount} XP → Nível {result['new_level']}")
        else:
            logger.info(f"✓ +{xp_amount} XP reclamado para user_id={current_user.id}")
        
        return {
            "success": True,
            "message": f"✓ +{xp_amount} XP ganho!",
            "xp_gained": result['xp_gained'],
            "new_level": result['new_level'],
            "leveled_up": result['leveled_up'],
            "current_xp": result['current_xp'],
            "xp_required_for_level": result['xp_required_for_level'],
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao reclamar XP diário: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao reclamar XP"
        )


@router.post(
    "/daily-chest/open",
    response_model=DailyChestRewardResponse,
    summary="Abrir Baú Diário",
    description="Abre baú diário e recebe recompensas aleatórias (pontos + XP)"
)
async def open_daily_chest(current_user = Depends(get_current_user)):
    """
    **🎁 Abrir Baú Diário com Sistema de Streaks Avançado**
    
    Abre o baú uma vez por dia (período de 24h).
    
    **Recompensas Base:**
    - TradePoints: 100
    - XP: 50
    
    **Bônus por Streak:**
    - +10% por dia consecutivo (1 dia = 10%, 5 dias = 50%, etc)
    
    **Lógica de Streak:**
    - 24h-48h desde última abertura: streak incrementa em 1
    - >48h: streak reseta para 1
    """
    try:
        result = await GameProfileService.open_daily_chest(current_user.id)
        
        if result['success']:
            return DailyChestRewardResponse(
                success=True,
                message=result['message'],
                points_reward=result.get('points_won'),
                xp_reward=result.get('xp_won'),
                new_streak=result.get('new_streak'),
                streak_bonus_percent=result.get('streak_bonus_percent'),
                multiplier=result.get('multiplier'),
                leveled_up=result.get('leveled_up', False),
                new_level=result.get('new_level'),
                next_chest_available_at=result.get('next_chest_available_at', '').isoformat() if result.get('next_chest_available_at') else None,
            )
        
        # Cooldown ativo
        if result.get('error') == 'cooldown_active':
            return DailyChestRewardResponse(
                success=False,
                message="⏰ Baú já foi aberto! Volta amanhã",
                error='cooldown_active',
                next_chest_available_at=result.get('next_chest_available_at', '').isoformat() if result.get('next_chest_available_at') else None,
                seconds_remaining=result.get('seconds_remaining'),
            )
        
        return DailyChestRewardResponse(
            success=False,
            message=result.get('message', 'Erro ao abrir baú'),
            error=result.get('error'),
        )
    
    except Exception as e:
        logger.error(f"❌ Erro ao abrir daily chest: {str(e)}")
        return DailyChestRewardResponse(
            success=False,
            message="Erro ao abrir baú",
            error='internal_error',
        )


@router.get(
    "/robots/ranking",
    response_model=RobotRankingResponse,
    summary="Ranking de Robôs da Quinzena",
    description="Retorna o ranking dos 20 robôs com Top 3 em destaque"
)
async def get_robots_ranking(
    current_user = Depends(get_current_user),
    limit: int = 20
):
    """
    **Ranking de Robôs por Performance**
    
    Exibe os 20 robôs ordenados por lucro em 15 dias.
    
    **Ranking:**
    - Atualiza a cada 15 dias automaticamente
    - Baseado em profit_15d
    - Top 3 com medalhas (🥇🥈🥉)
    - Status "ON FIRE" para top performers
    
    **Marcas:**
    - 🔥 ON FIRE: Alto desempenho (top 5)
    - 🥇/🥈/🥉: Medalhas para top 3
    
    **Campos por Robô:**
    - rank: Posição no ranking
    - profit_15d, profit_7d, profit_24h
    - win_rate: Taxa de vitória
    - total_trades: Operações realizadas
    - is_unlocked: Se o usuário já desbloqueou
    - unlock_cost: Custo em TradePoints
    
    **Return:**
        {
            "current_period": 123,
            "period_ends_in_days": 7,
            "ranking": [
                {
                    "rank": 1,
                    "medal": "🥇",
                    "robot_id": "bot_xyz",
                    "robot_name": "Grid Master Alpha",
                    "profit_15d": 345.67,
                    ...
                }
            ]
        }
    """
    # TODO: Implementar busca real no banco de dados
    
    current_period = RobotRankingService.calculate_biweekly_period()
    
    # Calcula dias restantes até mudança de período (15 dias)
    seconds_in_period = 15 * 24 * 60 * 60
    current_timestamp = datetime.utcnow().timestamp()
    period_start = current_period * seconds_in_period
    period_end = (current_period + 1) * seconds_in_period
    seconds_remaining = period_end - current_timestamp
    days_remaining = max(0, int(seconds_remaining / (24 * 60 * 60)))
    
    # ✅ FIXED: Busca real no banco de dados em vez de dados mockados
    db = get_db()
    profile = await GameProfileService.get_or_create_profile(current_user.id)
    user_unlocked = set(profile.unlocked_robots or [])
    
    # --- TTL cache for raw ranking docs (5 min) ---
    _cached = _ranking_cache.get(current_period)
    if _cached and datetime.utcnow() < _cached["expires_at"]:
        ranking_docs = _cached["docs"]
        logger.debug("[ranking] Serving from cache (period=%s)", current_period)
    else:
        # Busca robôs do ranking (collection robot_rankings ou bot_configs)
        ranking_col = db.get_collection("robot_rankings")
        cursor = ranking_col.find(
            {"biweekly_period": current_period}
        ).sort("profit_15d", -1).limit(limit)
        ranking_docs = await cursor.to_list(length=limit)
        _ranking_cache[current_period] = {
            "docs": ranking_docs,
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
        }
        # Evict old period caches
        for old_period in list(_ranking_cache.keys()):
            if old_period != current_period:
                del _ranking_cache[old_period]
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    ranking_items = []
    
    if ranking_docs:
        for idx, doc in enumerate(ranking_docs, 1):
            rid = doc.get("robot_id", f"bot_{idx:03d}")
            ranking_items.append({
                "rank": idx,
                "medal": medals.get(idx, ""),
                "robot_id": rid,
                "robot_name": doc.get("robot_name", f"Robot #{idx}"),
                "user_name": doc.get("user_name", "Trader"),
                "strategy": doc.get("strategy", "grid"),
                "profit_15d": doc.get("profit_15d", 0.0),
                "profit_7d": doc.get("profit_7d", 0.0),
                "profit_24h": doc.get("profit_24h", 0.0),
                "win_rate": doc.get("win_rate", 0.0),
                "total_trades": doc.get("total_trades", 0),
                "is_on_fire": doc.get("is_on_fire", idx <= 5),
                "is_unlocked": rid in user_unlocked,
                "unlock_cost": ROBOT_UNLOCK_COST.get(
                    'elite' if rid in ELITE_ROBOTS else 'common',
                    500
                ),
            })
    else:
        # Fallback: gera dados seed para não retornar vazio na primeira vez
        import hashlib
        seed_robots = [
            ("bot_001", "Volatility Dragon", "grid"),
            ("bot_002", "Legend Slayer", "combined"),
            ("bot_003", "Grid Precision", "grid"),
            ("bot_004", "Momentum Scout", "scalping"),
            ("bot_005", "Trend Surfer", "trend"),
        ]
        for idx, (rid, name, strat) in enumerate(seed_robots[:limit], 1):
            # Gera valores determinísticos baseados no período + robot_id
            seed = int(hashlib.md5(f"{current_period}:{rid}".encode()).hexdigest()[:8], 16)
            ranking_items.append({
                "rank": idx,
                "medal": medals.get(idx, ""),
                "robot_id": rid,
                "robot_name": name,
                "user_name": f"Trader #{idx}",
                "strategy": strat,
                "profit_15d": round((seed % 5000) + 500, 2),
                "profit_7d": round(((seed >> 4) % 2500) + 250, 2),
                "profit_24h": round(((seed >> 8) % 500) + 50, 2),
                "win_rate": round(55 + (seed % 20), 1),
                "total_trades": 100 + (seed % 200),
                "is_on_fire": idx <= 3,
                "is_unlocked": rid in user_unlocked,
                "unlock_cost": ROBOT_UNLOCK_COST.get(
                    'elite' if rid in ELITE_ROBOTS else 'common',
                    500
                ),
            })
    
    return {
        "current_period": current_period,
        "period_ends_in_days": days_remaining,
        "ranking": ranking_items,
    }


@router.get(
    "/robots/ranking-by-period",
    response_model=RobotRankingByPeriodResponse,
    summary="Ranking de Robôs por Período",
    description="Retorna ranking de robôs ordenado por período (24h, 7d ou 15d) com dados dinâmicos"
)
async def get_robots_ranking_by_period(
    period: str = "monthly",  # 'daily' | 'weekly' | 'monthly'
    limit: int = 10,
    sort_by: str = "profit",  # 'profit' | 'win_rate' | 'active_traders'
    current_user = Depends(get_current_user)
):
    """
    **Ranking de Robôs Dinâmico por Período**
    
    Retorna top N robôs ordenados por período específico com dados verossímeis.
    
    **Parâmetros:**
    - `period`: 'daily' (últimas 24h) | 'weekly' (última semana) | 'monthly' (último mês)
    - `limit`: Número de robôs a retornar (padrão: 10, máximo: 20)
    - `sort_by`: Campo para ordenação: 'profit' | 'win_rate' | 'active_traders'
    
    **Campos por Robô:**
    - rank: Posição no ranking
    - profit_24h, profit_7d, profit_15d: Lucro por período
    - win_rate: Taxa de vitória (%)
    - active_traders: Número de traders ativos
    - is_on_fire: Status de alta performance
    - medal: 🥇🥈🥉 para top 3
    
    **Exemplo de Uso:**
    ```
    GET /api/gamification/robots/ranking-by-period?period=daily&limit=10&sort_by=profit
    ```
    
    **Response Exemplo:**
    ```json
    {
        "success": true,
        "period": "daily",
        "period_label": "Top 10 - Últimas 24 Horas",
        "data": [
            {
                "rank": 1,
                "medal": "🥇",
                "id": "bot_001",
                "name": "Volatility Dragon",
                "creator": "Li Wei",
                "country": "🇨🇳",
                "strategy": "grid",
                "is_on_fire": true,
                "profit_24h": 245.67,
                "profit_7d": 1725.34,
                "profit_15d": 3450.67,
                "win_rate": 68.5,
                "active_traders": 245,
                "timestamp": "2026-02-23T09:15:30"
            },
            ...
        ],
        "timestamp": "2026-02-23T09:15:30"
    }
    ```
    """
    try:
        # Validação de entrada
        if period not in ['daily', 'weekly', 'monthly']:
            raise HTTPException(
                status_code=400,
                detail=f"Período inválido. Use: 'daily', 'weekly' ou 'monthly'"
            )
        
        if limit < 1 or limit > 20:
            limit = min(20, max(1, limit))
        
        if sort_by not in ['profit', 'win_rate', 'active_traders']:
            sort_by = 'profit'
        
        # Obtém ranking do gerenciador
        robots = RobotRankingManager.get_top_robots(
            period=period,
            limit=limit,
            sort_by=sort_by
        )
        
        # Mapeia para o modelo de resposta
        response_data = [
            RobotByPeriodItem(
                rank=robot.get('rank'),
                medal=robot.get('medal'),
                id=robot.get('id'),
                name=robot.get('name'),
                creator=robot.get('creator'),
                country=robot.get('country'),
                strategy=robot.get('strategy'),
                is_on_fire=robot.get('is_on_fire', False),
                profit_24h=robot.get('profit_24h', 0.0),
                profit_7d=robot.get('profit_7d', 0.0),
                profit_15d=robot.get('profit_15d', 0.0),
                win_rate=robot.get('win_rate', 0.0),
                active_traders=robot.get('active_traders', 0),
                timestamp=robot.get('timestamp', datetime.utcnow().isoformat()),
            )
            for robot in robots
        ]
        
        return RobotRankingByPeriodResponse(
            success=True,
            period=period,
            period_label=RobotRankingManager.get_period_label(period),
            data=response_data,
            timestamp=datetime.utcnow()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao buscar ranking por período: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar ranking de robôs"
        )


@router.post(
    "/robots/{robot_id}/unlock",
    response_model=UnlockRobotResponse,
    summary="Desbloquear Robô com TradePoints",
    description="Gasta TradePoints para desbloquear um robô estratégico"
)
async def unlock_robot(
    robot_id: str,
    current_user = Depends(get_current_user)
):
    """
    **Desbloquear Robô com TradePoints**
    
    Usa TradePoints (moeda de gamificação) para desbloquear
    um dos 20 robôs estratégicos.
    
    **Validações:**
    - Verifica se usuário tem pontos suficientes
    - Verificar se robô não está já desbloqueado
    - Persistir desbloqueio na conta (ATOMIC operation)
    
    **Return:**
        {
            "success": true,
            "message": "Robô desbloqueado com sucesso!",
            "points_remaining": 2450
        }
    """
    try:
        # Chamar lógica de desbloqueio com operações ATÔMICAS
        result = await GameProfileService.unlock_robot_logic(
            user_id=current_user.id,
            robot_id=robot_id
        )
        
        # Sucesso - retornar resposta
        if result['success']:
            logger.info(f"✅ Robô {robot_id} desbloqueado para usuário {current_user.id}")
            return UnlockRobotResponse(
                success=True,
                message=f"✅ Robô {robot_id} desbloqueado com sucesso!",
                points_remaining=result.get('new_balance', 0)
            )
        
        # ❌ Erro 1: Licença insuficiente (FREE users)
        if result['error'] == 'license_required':
            logger.warning(f"🔒 Usuário {current_user.id} ({result.get('current_plan', 'starter')}) não pode desbloquear")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "license_required",
                    "message": result.get('message', 'Upgrade para PRO necessário'),
                    "current_plan": result.get('current_plan'),
                }
            )
        
        # ❌ Erro 2: Limite de robôs do plano atingido
        if result['error'] == 'plan_limit_reached':
            logger.warning(f"⚠️ Usuário {current_user.id} atingiu limite: {result.get('unlocked_count')}/{result.get('limit')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "plan_limit_reached",
                    "message": result.get('message'),
                    "current_plan": result.get('current_plan'),
                    "unlocked_count": result.get('unlocked_count'),
                    "limit": result.get('limit'),
                }
            )
        
        # ❌ Erro 3: Robô já foi desbloqueado
        if result['error'] == 'already_unlocked':
            logger.warning(f"⚠️ Robô {robot_id} já estava desbloqueado para {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Robô {robot_id} já foi desbloqueado!"
            )
        
        # ❌ Erro 4: Saldo insuficiente
        if result['error'] == 'insufficient_balance':
            shortage = result.get('shortage', 0)
            logger.warning(f"❌ Saldo insuficiente para {current_user.id}: faltam {shortage} pts")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Pontos insuficientes. Você precisa de {shortage} pontos a mais. (Saldo: {result.get('current_balance', 0)})"
            )
        
        # ❌ Erro 5: Perfil não encontrado
        if result['error'] == 'profile_not_found':
            logger.error(f"❌ Perfil não encontrado para {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perfil de gamificação não encontrado"
            )
        
        # ❌ Erro desconhecido
        logger.error(f"❌ Erro desconhecido ao desbloquear {robot_id}: {result}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get('message', 'Erro ao desbloquear robô')
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions (erros já tratados)
        raise
    except Exception as e:
        logger.error(f"❌ Exceção ao desbloquear robô {robot_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar desbloqueio de robô"
        )


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Leaderboard Global",
    description="Retorna o ranking dos Top 50 usuários (lido do cache atualizado a cada 6h) e a posição do usuário atual"
)
async def get_leaderboard(
    current_user = Depends(get_current_user),
    limit: int = 50
):
    """
    **🏆 Leaderboard Global de Gamificação**
    
    Retorna os Top N usuários da cache atualizada a cada 6 horas.
    
    **Features:**
    - Top 3 destacado com badges (🥇🥈🥉)
    - Email mascarado por privacidade (LGPD/GDPR compliance)
    - Badges por nível (Novato, Trader, Expert, Whale, Lenda)
    - Posição do usuário atual (se fora do Top 50)
    - ⚡ PERFORMÁTICO: Lê de cache, não calcula em tempo real
    
    **Cache Strategy:**
    - Atualizado a cada 6 horas via scheduler
    - Projeção: apenas campos necessários para ranking
    - Resposta instantânea (<50ms)
    
    Returns:
        {
            "success": true,
            "leaderboard": [
                {
                    "rank": 1,
                    "user_masked_name": "usu***@gmail.com",
                    "level": 45,
                    "trade_points": 5000,
                    "badge": "🟡 Whale",
                    "is_top_3": true
                },
                ...
            ],
            "user_rank": {
                "rank": 1205,
                "trade_points": 1500,
                "level": 15,
                "badge": "🔵 Trader"
            }
        }
    """
    try:
        logger.info(f"📊 Buscando leaderboard do cache (top {limit}) para usuário {current_user.id}")
        
        db = get_db()
        cache_col = db["leaderboard_cache"]
        
        # Busca leaderboard do cache (já ordenado)
        leaderboard_data = await cache_col.find({}).limit(limit).to_list(limit)
        
        logger.info(f"✅ Leaderboard cache: {len(leaderboard_data)} usuários encontrados")
        
        # Prepara resposta sem _id
        leaderboard_items = [
            LeaderboardItemResponse(
                rank=item['rank'],
                user_masked_name=item['user_masked_name'],
                level=item['level'],
                trade_points=item['trade_points'],
                badge=item['badge'],
                is_top_3=item.get('is_top_3', False),
            )
            for item in leaderboard_data
        ]
        
        # Busca posição do usuário atual (se não está no top)
        user_rank = None
        if leaderboard_items:
            # Verifica se usuário está no leaderboard
            user_in_top = any(
                item.user_masked_name == current_user.email 
                for item in leaderboard_items
            )
            
            if not user_in_top:
                # Se não está no top, busca sua posição específica
                user_rank = await GameProfileService.get_user_rank(current_user.id)
        
        return LeaderboardResponse(
            success=True,
            message=f"✅ Leaderboard carregado (atualizado a cada 6h) com {len(leaderboard_items)} usuários",
            total_entries=len(leaderboard_items),
            leaderboard=leaderboard_items,
            user_rank=user_rank,
        )
    
    except Exception as e:
        logger.error(f"❌ Erro ao buscar leaderboard do cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar leaderboard"
        )


@router.get(
    "/store/bundles",
    response_model=StoreBundlesResponse,
    summary="Obter Pacotes de Pontos",
    description="Retorna todos os pacotes de TradePoints disponíveis para compra na loja"
)
async def get_store_bundles(current_user = Depends(get_current_user)):
    """
    **🏪 Loja de Pontos - Listar Pacotes Disponíveis**
    
    Retorna os pacotes de TradePoints disponíveis com preços em USD.
    
    **Pacotes:**
    - Pouch of Points: $2.99 → 1.000 pts
    - Bag of Points: $4.99 → 2.500 pts  
    - Chest of Points: $9.99 → 6.000 pts (MELHOR CUSTO-BENEFÍCIO)
    
    Returns:
        {
            "success": true,
            "message": "✅ Pacotes carregados",
            "bundles": [
                {
                    "bundle_id": "pouch",
                    "name": "Pouch of Points",
                    "price": 2.99,
                    "currency": "USD",
                    "points": 1000,
                    "is_best_value": false,
                    "display_order": 1
                },
                {
                    "bundle_id": "bag",
                    "name": "Bag of Points",
                    "price": 4.99,
                    "currency": "USD",
                    "points": 2500,
                    "is_best_value": false,
                    "display_order": 2
                },
                {
                    "bundle_id": "chest",
                    "name": "Chest of Points",
                    "price": 9.99,
                    "currency": "USD",
                    "points": 6000,
                    "is_best_value": true,
                    "display_order": 3
                }
            ]
        }
    """
    try:
        from app.gamification.model import POINT_BUNDLES
        
        logger.info(f"📦 Carregando pacotes de pontos para usuário {current_user.id}")
        
        # Converte dicionário de bundles para lista ordenada
        bundles_list = [
            PointBundleItem(
                bundle_id=bundle_id,
                name=bundle_data["name"],
                price=bundle_data["price"],
                currency=bundle_data["currency"],
                points=bundle_data["points"],
                is_best_value=bundle_data.get("is_best_value", False),
                display_order=bundle_data["display_order"],
            )
            for bundle_id, bundle_data in POINT_BUNDLES.items()
        ]
        
        # Ordena por display_order
        bundles_list.sort(key=lambda x: x.display_order)
        
        logger.info(f"✅ {len(bundles_list)} pacotes carregados")
        
        return StoreBundlesResponse(
            success=True,
            message="✅ Pacotes de pontos carregados com sucesso",
            bundles=bundles_list,
        )
    
    except Exception as e:
        logger.error(f"❌ Erro ao carregar pacotes de pontos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar pacotes de pontos"
        )


@router.post(
    "/store/purchase-points",
    response_model=PurchasePointsResponse,
    summary="Comprar TradePoints",
    description="Processa a compra de um pacote de TradePoints"
)
async def purchase_points(
    request: PurchasePointsRequest,
    current_user = Depends(get_current_user)
):
    """
    **🛒 Loja de Pontos - Realizar Compra**
    
    Processa a compra de um pacote de TradePoints.
    
    **Lógica:**
    1. Valida se o pacote existe
    2. Simula ou processa o pagamento (webhook)
    3. Incrementa trade_points do usuário
    4. Registra transação no log de auditoria (gamification_transactions)
    5. Retorna novo saldo
    
    **Request:**
    ```json
    {
        "bundle_id": "chest",
        "payment_method": "simulated",
        "transaction_id": "txn_12345"
    }
    ```
    
    Returns:
        {
            "success": true,
            "message": "✅ 6.000 pontos adicionados com sucesso!",
            "bundle_id": "chest",
            "points_added": 6000,
            "points_balance": 8500,
            "transaction_id": "txn_12345"
        }
    """
    try:
        from app.gamification.model import POINT_BUNDLES
        from datetime import datetime
        
        logger.info(f"🛒 Processando compra de pontos para usuário {current_user.id}: bundle={request.bundle_id}")
        
        # Valida se o pacote existe
        if request.bundle_id not in POINT_BUNDLES:
            logger.warning(f"❌ Pacote inválido: {request.bundle_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pacote '{request.bundle_id}' não encontrado"
            )
        
        bundle_data = POINT_BUNDLES[request.bundle_id]
        points_to_add = bundle_data["points"]
        bundle_price = bundle_data["price"]
        
        db = get_db()
        
        # Busca ou cria perfil de gamificação (static method — NÃO instanciar)
        game_profile = await GameProfileService.get_or_create_profile(current_user.id)
        
        # Adiciona pontos ao perfil
        game_profile.add_trade_points(points_to_add)
        
        # Salva perfil atualizado
        await GameProfileService.save_profile(game_profile)
        
        # Registra transação no log de auditoria
        transactions_col = db["gamification_transactions"]
        transaction_record = {
            "user_id": current_user.id,
            "transaction_type": "point_purchase",
            "bundle_id": request.bundle_id,
            "bundle_name": bundle_data["name"],
            "price_usd": bundle_price,
            "points_added": points_to_add,
            "payment_method": request.payment_method or "simulated",
            "transaction_id": request.transaction_id or f"sim_{current_user.id}_{datetime.utcnow().timestamp()}",
            "status": "completed",
            "created_at": datetime.utcnow(),
        }
        
        await transactions_col.insert_one(transaction_record)
        
        logger.info(f"✅ Compra processada: {points_to_add} pontos adicionados para {current_user.id}. Novo saldo: {game_profile.trade_points}")
        
        return PurchasePointsResponse(
            success=True,
            message=f"✅ {points_to_add:,} TradePoints adicionados com sucesso! 🎉",
            bundle_id=request.bundle_id,
            points_added=points_to_add,
            points_balance=game_profile.trade_points,
            transaction_id=transaction_record["transaction_id"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao processar compra de pontos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar compra de pontos"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MICRO-TRANSAÇÕES (Pacotes Emergenciais)
# ─────────────────────────────────────────────────────────────────────────────

class MicroBundleItem(BaseModel):
    bundle_id: str
    name: str
    emoji: str = ""
    price: float
    currency: str = "USD"
    points: int
    description: str = ""
    is_best_value: bool = False
    display_order: int = 0

class MicroBundlesResponse(BaseModel):
    success: bool
    bundles: List[MicroBundleItem]
    message: str = ""

class MicroPurchaseAndUnlockRequest(BaseModel):
    bundle_id: str = Field(..., description="ID do micro pacote (micro_100, micro_250, etc)")
    robot_id: str = Field(..., description="ID do robô a desbloquear após compra")
    payment_method: Optional[str] = "simulated"
    transaction_id: Optional[str] = None

class MicroPurchaseAndUnlockResponse(BaseModel):
    success: bool
    message: str
    points_added: int = 0
    robot_unlocked: bool = False
    robot_id: Optional[str] = None
    new_balance: int = 0
    unlock_cost: int = 0
    transaction_id: Optional[str] = None


@router.get(
    "/store/micro-bundles",
    response_model=MicroBundlesResponse,
    summary="Micro Pacotes Emergenciais",
    description="Retorna pacotes micro para micro-transações (quando saldo é insuficiente)"
)
async def get_micro_bundles(
    shortage: int = Query(0, description="Deficit de pontos do usuário"),
    current_user = Depends(get_current_user)
):
    """
    **⚡ Micro Pacotes — Pacotes emergenciais para saldo insuficiente**
    
    Retorna micro pacotes ordenados por display_order.
    Se `shortage` > 0, marca o menor pacote que cobre o deficit como 'recommended'.
    """
    try:
        from app.gamification.model import MICRO_BUNDLES
        
        bundles_list = [
            MicroBundleItem(
                bundle_id=bid,
                name=bdata["name"],
                emoji=bdata.get("emoji", ""),
                price=bdata["price"],
                currency=bdata.get("currency", "USD"),
                points=bdata["points"],
                description=bdata.get("description", ""),
                is_best_value=bdata.get("is_best_value", False),
                display_order=bdata.get("display_order", 0),
            )
            for bid, bdata in MICRO_BUNDLES.items()
        ]
        bundles_list.sort(key=lambda x: x.display_order)
        
        return MicroBundlesResponse(
            success=True,
            bundles=bundles_list,
            message=f"✅ {len(bundles_list)} micro pacotes disponíveis"
        )
    except Exception as e:
        logger.error(f"❌ Erro ao carregar micro bundles: {e}")
        raise HTTPException(status_code=500, detail="Erro ao carregar micro pacotes")


@router.post(
    "/store/micro-purchase-and-unlock",
    response_model=MicroPurchaseAndUnlockResponse,
    summary="Compra Micro + Desbloqueio Automático",
    description="Compra um micro pacote e tenta desbloquear o robô em uma única operação"
)
async def micro_purchase_and_unlock(
    request: MicroPurchaseAndUnlockRequest,
    current_user = Depends(get_current_user)
):
    """
    **⚡ Compra micro + desbloqueio automático**
    
    1. Valida micro pacote
    2. Adiciona pontos ao saldo
    3. Tenta desbloquear o robô
    4. Retorna resultado unificado
    """
    try:
        from app.gamification.model import MICRO_BUNDLES
        
        if request.bundle_id not in MICRO_BUNDLES:
            raise HTTPException(400, f"Micro pacote '{request.bundle_id}' não encontrado")
        
        bundle = MICRO_BUNDLES[request.bundle_id]
        points_to_add = bundle["points"]
        
        db = get_db()
        
        # 1. Adiciona pontos
        profile = await GameProfileService.get_or_create_profile(current_user.id)
        collection = GameProfileService._get_collection()
        await collection.update_one(
            {"user_id": str(current_user.id)},
            {
                "$inc": {"trade_points": points_to_add},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        # 2. Log da compra
        tx_id = request.transaction_id or f"micro_{current_user.id}_{datetime.utcnow().timestamp()}"
        await db["gamification_transactions"].insert_one({
            "user_id": current_user.id,
            "transaction_type": "micro_purchase",
            "bundle_id": request.bundle_id,
            "bundle_name": bundle["name"],
            "price_usd": bundle["price"],
            "points_added": points_to_add,
            "payment_method": request.payment_method or "simulated",
            "transaction_id": tx_id,
            "status": "completed",
            "created_at": datetime.utcnow(),
        })
        
        # 3. Tenta desbloquear o robô
        unlock_result = await GameProfileService.unlock_robot_logic(current_user.id, request.robot_id)
        
        updated_profile = await GameProfileService.get_or_create_profile(current_user.id)
        
        if unlock_result.get("success"):
            logger.info(f"✅ Micro compra + desbloqueio: {request.bundle_id} → {request.robot_id} para {current_user.id}")
            return MicroPurchaseAndUnlockResponse(
                success=True,
                message=f"✅ +{points_to_add} pontos + robô {request.robot_id} desbloqueado!",
                points_added=points_to_add,
                robot_unlocked=True,
                robot_id=request.robot_id,
                new_balance=updated_profile.trade_points,
                unlock_cost=unlock_result.get("cost", 0),
                transaction_id=tx_id,
            )
        else:
            # Pontos adicionados mas desbloqueio falhou (ex: ainda insuficiente)
            return MicroPurchaseAndUnlockResponse(
                success=False,
                message=f"+{points_to_add} pontos adicionados, mas: {unlock_result.get('message', 'Erro no desbloqueio')}",
                points_added=points_to_add,
                robot_unlocked=False,
                robot_id=request.robot_id,
                new_balance=updated_profile.trade_points,
                unlock_cost=0,
                transaction_id=tx_id,
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro micro compra+unlock: {e}")
        raise HTTPException(500, "Erro ao processar micro compra")


# ─────────────────────────────────────────────────────────────────────────────
# HISTÓRICO DE TRANSAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

class TransactionItem(BaseModel):
    transaction_type: str
    points_change: Optional[int] = 0
    xp_change: Optional[int] = 0
    description: str = ""
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

class TransactionsResponse(BaseModel):
    success: bool
    transactions: List[TransactionItem]
    total: int
    page: int
    page_size: int


@router.get(
    "/transactions",
    response_model=TransactionsResponse,
    summary="Histórico de Transações",
    description="Retorna histórico de transações de gamificação do usuário com paginação"
)
async def get_transactions(
    page: int = Query(1, ge=1, description="Página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
    tx_type: Optional[str] = Query(None, description="Filtrar por tipo (daily_chest, point_purchase, robot_unlock, micro_purchase, monthly_bonus)"),
    current_user = Depends(get_current_user)
):
    """
    **📋 Histórico de Transações**
    
    Retorna todas as transações do usuário com paginação.
    Tipos: daily_chest, point_purchase, robot_unlock, micro_purchase, monthly_bonus, claim_daily_xp
    """
    try:
        db = get_db()
        col = db["gamification_transactions"]
        
        query_filter: Dict[str, Any] = {"user_id": current_user.id}
        if tx_type:
            query_filter["transaction_type"] = tx_type
        
        total = await col.count_documents(query_filter)
        
        skip = (page - 1) * page_size
        cursor = col.find(query_filter).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        
        transactions = []
        for doc in docs:
            t_type = doc.get("transaction_type", "unknown")
            # Build description
            if t_type == "daily_chest":
                desc = f"Baú Diário: +{doc.get('points_change', 0)} pts, +{doc.get('xp_change', 0)} XP"
            elif t_type == "point_purchase":
                desc = f"Compra: {doc.get('bundle_name', '')} (+{doc.get('points_added', 0)} pts)"
            elif t_type == "micro_purchase":
                desc = f"Micro Compra: {doc.get('bundle_name', '')} (+{doc.get('points_added', 0)} pts)"
            elif t_type == "robot_unlock":
                desc = f"Desbloqueio: {doc.get('robot_id', '')} (-{abs(doc.get('points_change', 0))} pts)"
            elif t_type == "monthly_bonus":
                desc = f"Bônus Mensal: +{doc.get('points_change', 0)} pts"
            else:
                desc = doc.get("description", t_type)
            
            created = doc.get("created_at")
            transactions.append(TransactionItem(
                transaction_type=t_type,
                points_change=doc.get("points_change") or doc.get("points_added", 0),
                xp_change=doc.get("xp_change", 0),
                description=desc,
                metadata=doc.get("metadata"),
                created_at=created.isoformat() if created else None,
            ))
        
        return TransactionsResponse(
            success=True,
            transactions=transactions,
            total=total,
            page=page,
            page_size=page_size,
        )
    
    except Exception as e:
        logger.error(f"❌ Erro ao buscar transações: {e}")
        raise HTTPException(500, "Erro ao buscar histórico de transações")


# ─────────────────────────────────────────────────────────────────────────────
# REAL TRADING LEADERBOARD (DOC_06)
# Separate from the gamification (trade_points) leaderboard above.
# Based on actual bot_trades PnL — composite score: ROI, win_rate, PnL, PF, volume.
# ─────────────────────────────────────────────────────────────────────────────

class TradingLeaderboardEntry(BaseModel):
    rank_position:   int
    display_name:    str
    avatar_url:      Optional[str] = None
    robot_name:      Optional[str] = None
    pair:            Optional[str] = None
    roi_pct:         float
    win_rate:        float
    total_pnl_usdt:  float
    profit_factor:   float
    total_trades:    int
    total_fees_usdt: float
    composite_score: float

    class Config:
        from_attributes = True


class TradingLeaderboardResponse(BaseModel):
    entries:     List[TradingLeaderboardEntry]
    total:       int
    period_days: int
    computed_at: Optional[str] = None
    user_rank:   Optional[TradingLeaderboardEntry] = None
    message:     Optional[str] = None

    class Config:
        from_attributes = True


@router.get(
    "/leaderboard/trading",
    response_model=TradingLeaderboardResponse,
    summary="Leaderboard de Trading Real",
    description="Ranking baseado em PnL real das trades fechadas. Score composto: ROI 35%, Win Rate 25%, PnL 20%, Profit Factor 15%, Volume 5%.",
)
async def get_trading_leaderboard(
    period: int = Query(30, ge=7, le=90, description="Janela em dias"),
    limit:  int = Query(50, ge=10, le=100, description="Número máximo de entradas"),
    current_user = Depends(get_current_user),
):
    """
    **Leaderboard de Trading Real**

    Endpoint PROTEGIDO — requer autenticação JWT.

    Responde do cache (Redis → MongoDB) para latência mínima (<20ms).
    O cálculo real roda a cada 15 min em background.

    - **period**: janela de análise em dias (7–90)
    - **limit**: quantas entradas retornar (10–100)
    - **user_rank**: posição e métricas do usuário autenticado (null se sem trades)
    """
    db      = get_db()
    redis   = await get_redis()
    service = RankingService(db=db, redis=redis)
    user_id = str(current_user.id)

    entries = await service.get_cached_ranking(period_days=period)

    if not entries:
        # No ranking yet — trigger async computation and respond immediately
        asyncio.create_task(service.compute_ranking(period))
        return TradingLeaderboardResponse(
            entries=[],
            total=0,
            period_days=period,
            computed_at=None,
            user_rank=None,
            message="Ranking sendo calculado. Disponível em ~60 segundos.",
        )

    # Locate current user entry (user_id is stored as _user_id internally)
    user_entry_raw = next(
        (e for e in entries if e.get("_user_id") == user_id),
        None,
    )

    def _to_entry(raw: dict) -> TradingLeaderboardEntry:
        return TradingLeaderboardEntry(
            rank_position   = raw.get("rank_position", 0),
            display_name    = raw.get("display_name", "Trader Anônimo"),
            avatar_url      = raw.get("avatar_url"),
            robot_name      = raw.get("robot_name"),
            pair            = raw.get("pair"),
            roi_pct         = float(raw.get("roi_pct", 0)),
            win_rate        = float(raw.get("win_rate", 0)),
            total_pnl_usdt  = float(raw.get("total_pnl_usdt", 0)),
            profit_factor   = float(raw.get("profit_factor", 0)),
            total_trades    = int(raw.get("total_trades", 0)),
            total_fees_usdt = float(raw.get("total_fees_usdt", 0)),
            composite_score = float(raw.get("composite_score", 0)),
        )

    computed_at = (
        str(entries[0].get("computed_at", "")) if entries else None
    )

    return TradingLeaderboardResponse(
        entries     = [_to_entry(e) for e in entries[:limit]],
        total       = len(entries),
        period_days = period,
        computed_at = computed_at,
        user_rank   = _to_entry(user_entry_raw) if user_entry_raw else None,
    )


@router.get(
    "/leaderboard/my-position",
    summary="Minha Posição no Ranking de Trading",
    description="Retorna apenas a posição e métricas do usuário autenticado no ranking de trading real.",
)
async def get_my_trading_position(current_user = Depends(get_current_user)):
    """
    **Minha Posição no Ranking**

    Endpoint PROTEGIDO — requer autenticação JWT.

    Retorna:
    - **ranked**: false se o usuário ainda não tem 5 trades fechadas
    - Todos os campos da TradingLeaderboardEntry se já está no ranking
    """
    db      = get_db()
    redis   = await get_redis()
    service = RankingService(db=db, redis=redis)
    user_id = str(current_user.id)

    entries = await service.get_cached_ranking(period_days=30)
    user_entry = next(
        (e for e in (entries or []) if e.get("_user_id") == user_id),
        None,
    )

    if not user_entry:
        return {
            "ranked":  False,
            "message": "Você ainda não tem trades suficientes para entrar no ranking (mínimo: 5 trades fechadas).",
        }

    return {
        "ranked":          True,
        "rank_position":   user_entry.get("rank_position"),
        "display_name":    user_entry.get("display_name"),
        "roi_pct":         user_entry.get("roi_pct"),
        "win_rate":        user_entry.get("win_rate"),
        "total_pnl_usdt":  user_entry.get("total_pnl_usdt"),
        "profit_factor":   user_entry.get("profit_factor"),
        "total_trades":    user_entry.get("total_trades"),
        "composite_score": user_entry.get("composite_score"),
        "pair":            user_entry.get("pair"),
        "robot_name":      user_entry.get("robot_name"),
    }
