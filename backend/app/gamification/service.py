"""
Gamification Service - Lógica de negócio para o sistema gamificado

Implementa:
- Cálculos de XP e níveis
- Recompensas diárias
- Ranking de robôs 
- Desbloqueio de robôs com pontos
- Persistência MongoDB
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from bson import ObjectId

from app.core.database import get_db
from app.core.plan_config import resolve_plan_key, get_plan_config, get_max_robots_arena
from app.gamification.model import (
    GameProfile, 
    DailyChest, 
    RobotRanking,
    PLAN_REWARD_MAP,
)

logger = logging.getLogger(__name__)

# ============================================
# ═ Configuração de Robôs
# ============================================

ELITE_ROBOTS = ['bot_001', 'bot_002', 'bot_003']  # Top 3 do Ranking
ROBOT_UNLOCK_COST = {
    'elite': 1500,      # Robôs Elite (Top 3)
    'common': 500,      # Robôs Comuns
}

# IDs válidos do marketplace — necessário para validar chamadas da API
VALID_ROBOT_IDS = {
    'bot_001', 'bot_002', 'bot_003', 'bot_004', 'bot_005',
    'bot_006', 'bot_007', 'bot_008', 'bot_009', 'bot_010',
    'bot_011', 'bot_012', 'bot_013', 'bot_014', 'bot_015',
    'bot_016', 'bot_017', 'bot_018', 'bot_019', 'bot_020',
}

# Limite máximo para bônus de streak (evita exploits)
MAX_STREAK_BONUS = 10  # Cap: +100% max


class GameProfileService:
    """Service para gerenciar perfis de gamificação (com MongoDB)"""
    
    @staticmethod
    def _get_collection():
        """Retorna collection de game_profiles do MongoDB"""
        db = get_db()
        return db["game_profiles"]
    
    @staticmethod
    async def get_or_create_profile(user_id: str) -> GameProfile:
        """
        Busca ou cria um perfil de gamificação para o usuário.
        
        Args:
            user_id: ID do usuário (string)
        
        Returns:
            GameProfile com dados do banco ou novo
        
        Raises:
            Logs de erro se houver problema com DB
        """
        collection = GameProfileService._get_collection()
        
        try:
            # Converte user_id para ObjectId se necessário
            if isinstance(user_id, str):
                try:
                    user_id_obj = ObjectId(user_id)
                except:
                    user_id_obj = user_id
            else:
                user_id_obj = user_id
            
            # Tenta buscar perfil existente
            existing_profile = await collection.find_one({"user_id": str(user_id)})
            
            if existing_profile:
                logger.info(f"✓ GameProfile encontrado para user_id={user_id}")
                
                # Converte documentoMongoDB para modelo Pydantic
                profile_data = {
                    "id": str(existing_profile.get("_id")),
                    "user_id": existing_profile["user_id"],
                    "trade_points": existing_profile.get("trade_points", 1000),
                    "level": existing_profile.get("level", 1),
                    "xp": existing_profile.get("xp", 0),
                    "unlocked_robots": existing_profile.get("unlocked_robots", []),
                    "lifetime_profit": existing_profile.get("lifetime_profit", 0.0),
                    "last_daily_chest_opened": existing_profile.get("last_daily_chest_opened"),
                    "streak_count": existing_profile.get("streak_count", 0),
                    "created_at": existing_profile.get("created_at", datetime.utcnow()),
                    "updated_at": existing_profile.get("updated_at", datetime.utcnow()),
                }
                return GameProfile(**profile_data)
            
            # Cria novo perfil
            logger.info(f"⚙️ Criando novo GameProfile para user_id={user_id}")
            
            # Busca plano do usuário para definir pontos iniciais corretos
            from app.gamification.model import PLAN_REWARD_MAP
            initial_pts = 1000  # Default fallback
            try:
                license_info = await GameProfileService._get_user_license(str(user_id))
                canonical_plan = license_info.get('plan', 'starter')
                plan_rewards = PLAN_REWARD_MAP.get(canonical_plan, PLAN_REWARD_MAP.get('starter'))
                initial_pts = plan_rewards.get('initial_points', 1000)
                logger.info(f"✓ Pontos iniciais para plano '{canonical_plan}': {initial_pts}")
            except Exception as e:
                logger.warning(f"⚠️ Não foi possível obter plano, usando 1000 pts: {e}")
            
            new_profile = GameProfile(
                user_id=str(user_id),
                trade_points=initial_pts,  # Baseado no plano do usuário
                level=1,
                xp=0,
                unlocked_robots=[],
                lifetime_profit=0.0,
                last_daily_chest_opened=None,
                streak_count=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            # Salva no MongoDB
            insert_result = await collection.insert_one({
                "user_id": str(user_id),
                "trade_points": new_profile.trade_points,
                "level": new_profile.level,
                "xp": new_profile.xp,
                "unlocked_robots": new_profile.unlocked_robots,
                "lifetime_profit": new_profile.lifetime_profit,
                "last_daily_chest_opened": new_profile.last_daily_chest_opened,
                "streak_count": new_profile.streak_count,
                "created_at": new_profile.created_at,
                "updated_at": new_profile.updated_at,
            })
            
            new_profile.id = str(insert_result.inserted_id)
            logger.info(f"✅ GameProfile criado com ID={new_profile.id}")
            
            return new_profile
        
        except Exception as e:
            logger.error(f"❌ Erro ao buscar/criar GameProfile: {str(e)}")
            # Retorna perfil default em caso de erro
            logger.warning(f"⚠️ Retornando perfil default para user_id={user_id}")
            return GameProfile(user_id=str(user_id))
    
    @staticmethod
    async def save_profile(profile: GameProfile) -> bool:
        """
        Salva/atualiza um perfil no MongoDB.
        
        Args:
            profile: GameProfile a salvar
        
        Returns:
            True se bem-sucedido
        """
        collection = GameProfileService._get_collection()
        
        try:
            # Prepara documento
            doc = {
                "user_id": profile.user_id,
                "trade_points": profile.trade_points,
                "level": profile.level,
                "xp": profile.xp,
                "unlocked_robots": profile.unlocked_robots,
                "lifetime_profit": profile.lifetime_profit,
                "last_daily_chest_opened": profile.last_daily_chest_opened,
                "streak_count": profile.streak_count,
                "updated_at": datetime.utcnow(),
            }
            
            # Upsert (insere se não existe, atualiza se existe)
            result = await collection.update_one(
                {"user_id": profile.user_id},
                {"$set": doc},
                upsert=True
            )
            
            logger.info(f"✓ GameProfile atualizado para user_id={profile.user_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Erro ao salvar GameProfile: {str(e)}")
            return False
    
    @staticmethod
    def create_default_profile(user_id: str) -> GameProfile:
        """Cria um perfil padrão em-memória (não persiste)"""
        return GameProfile(
            user_id=str(user_id),
            trade_points=1000,
            level=1,
            xp=0,
        )
    
    @staticmethod
    def grant_plan_rewards(profile: GameProfile, plan: str) -> None:
        """
        Concede recompensas ao mudar de plano.
        
        Args:
            profile: Perfil a atualizar
            plan: Nome do plano (starter, pro, premium, enterprise)
        """
        if plan not in PLAN_REWARD_MAP:
            return
        
        reward_info = PLAN_REWARD_MAP[plan]
        profile.trade_points += reward_info["initial_points"]
        
        # Adiciona XP também
        xp_gained = reward_info.get("initial_xp", 100)
        profile.add_xp(xp_gained)
        
        profile.updated_at = datetime.utcnow()
        logger.info(f"✓ Recompensas do plano '{plan}' concedidas: +{reward_info['initial_points']} pontos, +{xp_gained} XP")
    
    @staticmethod
    def add_trade_profit(profile: GameProfile, profit: float) -> Tuple[bool, int]:
        """
        Adiciona XP baseado em lucro obtido de trades.
        
        Args:
            profile: Perfil a atualizar
            profit: Lucro em USD
        
        Returns:
            (houve_level_up, xp_ganho)
        """
        # Fórmula: 1 XP a cada $10 de lucro (mínimo 1)
        xp_gained = max(1, int(profit / 10))
        
        should_level_up = profile.add_xp(xp_gained)
        profile.lifetime_profit += profit
        profile.updated_at = datetime.utcnow()
        
        logger.info(f"✓ Lucro de ${profit:.2f} adicionado a user_id={profile.user_id}: +{xp_gained} XP (level_up={should_level_up})")
        
        return should_level_up, xp_gained
    
    @staticmethod
    async def add_xp_to_profile(user_id: str, xp_amount: int) -> Dict[str, Any]:
        """
        Adiciona XP ao perfil do usuário de forma ATÔMICA.
        Detecta level up e persiste no MongoDB.
        
        Args:
            user_id: ID do usuário
            xp_amount: Quantidade de XP a adicionar
        
        Returns:
            {
                'xp_gained': int,
                'new_level': int, 
                'leveled_up': bool,
                'current_xp': int,
                'xp_required_for_level': int,
            }
        
        Raises:
            Exception se erro no bank de dados
        """
        try:
            # 1. Busca perfil atual
            profile = await GameProfileService.get_or_create_profile(user_id)
            old_level = profile.level
            
            # 2. Adiciona XP (usa método do model que recalcula level)
            leveled_up = profile.add_xp(xp_amount)
            new_level = profile.level
            
            # 3. Persiste no banco de dados
            await GameProfileService.save_profile(profile)
            
            # 4. Log
            if leveled_up:
                logger.info(f"✅ LEVEL UP! user_id={user_id}: level {old_level} → {new_level} (+{xp_amount} XP)")
            else:
                logger.info(f"✓ +{xp_amount} XP adicionado ao user_id={user_id} (nível {profile.level})")
            
            # 5. Retorna resposta estruturada
            return {
                'xp_gained': xp_amount,
                'new_level': new_level,
                'leveled_up': leveled_up,
                'current_xp': profile.xp,
                'xp_required_for_level': profile.xp_for_next_level(),
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar XP: {str(e)}")
            raise
    
    @staticmethod
    async def open_daily_chest(user_id: str) -> Dict[str, Any]:
        """
        🎁 Abre baú diário com sistema de STREAKS avançado.
        
        **Validações:**
        - Verifica cooldown de 24h
        - Calcula streak com recompensas escaláveis
        
        **Lógica de Streak:**
        - 24h-48h desde última abertura: streak += 1
        - >48h: streak = 1 (reset)
        - Bônus: +10% por dia de ofensiva (streak * 0.1)
        
        **Recompensas Base:**
        - Pontos: 100 + 20 (aleatório)
        - XP: 50 + 10 (aleatório)
        - Multiplicador: 1 + (streak * 0.1)
        
        **Return:**
        {
            'success': bool,
            'points_won': int,
            'xp_won': int,
            'new_streak': int,
            'streak_bonus_percent': float,
            'next_chest_available_at': datetime,
            'message': str
        }
        """
        try:
            # Busca perfil do usuário
            profile = await GameProfileService.get_or_create_profile(user_id)
            
            now = datetime.utcnow()
            
            # ✅ VALIDAÇÃO: Cooldown de 24h
            if profile.last_daily_chest_opened:
                time_since_last = now - profile.last_daily_chest_opened
                seconds_since = time_since_last.total_seconds()
                
                # Ainda não passaram 24h
                if seconds_since < 86400:  # 86400 = 24h em segundos
                    next_available = profile.last_daily_chest_opened + timedelta(hours=24)
                    seconds_remaining = (next_available - now).total_seconds()
                    
                    logger.warning(f"⏰ Baú ainda em cooldown para {user_id}: {int(seconds_remaining)}s restantes")
                    return {
                        'success': False,
                        'error': 'cooldown_active',
                        'message': 'Baú voltará em 24h',
                        'next_chest_available_at': next_available,
                        'seconds_remaining': int(seconds_remaining),
                    }
            
            # ✅ LÓGICA DE STREAK
            new_streak = 1
            if profile.last_daily_chest_opened:
                time_since_last = now - profile.last_daily_chest_opened
                seconds_since = time_since_last.total_seconds()
                
                # Entre 24h e 48h: mantém e incrementa streak
                if 86400 <= seconds_since < 172800:  # 172800 = 48h
                    new_streak = profile.streak_count + 1
                    logger.info(f"🔥 Streak incrementado: {profile.streak_count} → {new_streak}")
                
                # Mais de 48h: reseta streak
                elif seconds_since >= 172800:
                    new_streak = 1
                    logger.warning(f"⚠️ Streak resetado para {user_id} (inatividade >48h)")
            
            # ✅ RECOMPENSAS ESCALÁVEIS
            # Base: 100 pts + 50 XP
            base_points = 100
            base_xp = 50
            
            # Bônus: 10% por dia de streak, com cap em MAX_STREAK_BONUS
            effective_streak = min(new_streak, MAX_STREAK_BONUS)
            streak_bonus_percent = effective_streak * 10
            multiplier = 1.0 + (effective_streak * 0.1)
            
            # Aplic recompensas com bônus
            points_won = int(base_points * multiplier)
            xp_won = int(base_xp * multiplier)
            
            # ✅ PERSISTÊNCIA NO MONGODB
            collection = GameProfileService._get_collection()
            result = await collection.update_one(
                {"user_id": str(user_id)},
                {
                    "$inc": {
                        "trade_points": points_won,      # Atomic increment
                        "xp": xp_won,
                    },
                    "$set": {
                        "streak_count": new_streak,
                        "last_daily_chest_opened": now,
                        "updated_at": now,
                    }
                }
            )
            
            if result.matched_count == 0:
                logger.error(f"❌ Perfil não encontrado: {user_id}")
                return {
                    'success': False,
                    'error': 'profile_not_found',
                    'message': 'Perfil não encontrado',
                }
            
            # Busca perfil atualizado para verificar level up
            updated_profile = await GameProfileService.get_or_create_profile(user_id)
            new_level = updated_profile.level
            leveled_up = new_level > profile.level
            
            next_available = now + timedelta(hours=24)
            
            logger.info(
                f"✅ Baú aberto: {user_id} | "
                f"+{points_won}pts (streak: {new_streak}x) | "
                f"+{xp_won}XP | "
                f"Bônus: {streak_bonus_percent}% | "
                f"Level: {profile.level}→{new_level}"
            )
            
            # 📝 LOG AUDITORIA: Registrar transação
            await GameProfileService.log_transaction(
                user_id=user_id,
                transaction_type="daily_chest",
                points_change=points_won,
                xp_change=xp_won,
                metadata={
                    "streak_at_time": new_streak,
                    "streak_bonus_percent": streak_bonus_percent,
                    "multiplier": multiplier,
                    "level_before": profile.level,
                    "level_after": new_level,
                    "leveled_up": leveled_up,
                }
            )
            
            return {
                'success': True,
                'points_won': points_won,
                'xp_won': xp_won,
                'new_streak': new_streak,
                'streak_bonus_percent': streak_bonus_percent,
                'multiplier': multiplier,
                'next_chest_available_at': next_available,
                'leveled_up': leveled_up,
                'new_level': new_level,
                'message': f'🎁 Baú aberto! +{points_won}pts +{xp_won}XP (Ofensiva: {new_streak} dias)',
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao abrir baú diário: {str(e)}")
            return {
                'success': False,
                'error': 'internal_error',
                'message': str(e),
            }
    
    @staticmethod
    def unlock_robot_with_points(
        profile: GameProfile, 
        robot_id: str,
        unlock_cost: int
    ) -> Tuple[bool, str]:
        """
        Tenta desbloquear um robô usando TradePoints.
        
        Args:
            profile: Perfil do usuário
            robot_id: ID do robô a desbloquear
            unlock_cost: Custo em pontos
        
        Returns:
            (sucesso, mensagem)
        """
        # Valida se já foi desbloqueado
        if robot_id in profile.unlocked_robots:
            return False, "Este robô já foi desbloqueado!"
        
        # Valida pontos
        if profile.trade_points < unlock_cost:
            shortfall = unlock_cost -profile.trade_points
            return False, f"Você precisa de {shortfall} pontos a mais"
        
        # Executa desbloqueio
        profile.trade_points -= unlock_cost
        profile.unlocked_robots.append(robot_id)
        profile.updated_at = datetime.utcnow()
        
        logger.info(f"✓ Robô {robot_id} desbloqueado para user_id={profile.user_id} (-{unlock_cost} pontos)")
        
        return True, "Robô desbloqueado com sucesso!"
    
    @staticmethod
    async def _get_user_license(user_id: str) -> Dict[str, Any]:
        """
        💳 Busca licença/plano do usuário da collection 'users'.
        Usa plan_config.py como fonte única de verdade.
        
        Returns:
            {
                'plan': str (chave canônica),
                'license_display': str (START|PRO+|QUANT|BLACK),
                'max_robots': int,
            }
        
        Default: free (0 robôs)
        """
        try:
            db = get_db()

            # Tenta ObjectId (MongoDB) com fallback para string (SQLite/UUID)
            try:
                query_id = ObjectId(user_id)
            except Exception:
                query_id = user_id

            user_doc = await db["users"].find_one({"_id": query_id})
            
            if not user_doc:
                logger.warning(f"⚠️ Usuário {user_id} não encontrado, usando default: free")
                return {
                    'plan': 'free',
                    'license_display': 'FREE',
                    'max_robots': 0,
                }
            
            raw_plan = user_doc.get("plan", "free")
            
            # Resolve aliases (start→starter, quant→premium, black→enterprise)
            canonical = resolve_plan_key(raw_plan)
            cfg = get_plan_config(raw_plan)
            
            logger.info(f"✓ Licença do user_id={user_id}: plan={canonical} (raw={raw_plan}), max_robots={cfg['max_robots_arena']}")
            
            return {
                'plan': canonical,
                'license_display': cfg['display'],
                'max_robots': cfg['max_robots_arena'],
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao buscar licença do user_id={user_id}: {str(e)}")
            return {
                'plan': 'free',
                'license_display': 'FREE',
                'max_robots': 0,
            }
    
    @staticmethod
    async def unlock_robot_logic(user_id: str, robot_id: str) -> Dict[str, Any]:
        """
        💳 Desbloqueia um robô com VALIDAÇÃO DE LICENÇA + operações ATÔMICAS.
        
        **Algoritmo:**
        1. Verifica licença/plano do usuário
        2. Valida limite de robôs desbloqueados
        3. Determina custo do robô
        4. Valida se já foi desbloqueado
        5. Executa desbloqueio atômico
        
        **Regras de Licença:**
        - starter (FREE): 0 robôs (bloqueado)
        - pro: 5 robôs
        - premium: 15 robôs
        - enterprise: Ilimitado
        
        Args:
            user_id: ID do usuário
            robot_id: ID do robô a desbloquear
        
        Returns:
            {
                'success': bool,
                'robot_id': str,
                'cost': int,
                'new_balance': int,
                'unlocked_robots': List[str],
            }
        
        Raises:
            HTTPException(403): Licença insuficiente ou limite atingido
            HTTPException(400): Robô já desbloqueado
            HTTPException(403): Saldo insuficiente
        """
        try:
            collection = GameProfileService._get_collection()
            
            # 0️⃣ VALIDAÇÃO DE ID: rejeita robot_ids inexistentes no marketplace
            if robot_id not in VALID_ROBOT_IDS:
                logger.warning(f"❌ Robot ID inválido: '{robot_id}' não existe no marketplace")
                return {
                    'success': False,
                    'error': 'invalid_robot',
                    'message': f'Robô "{robot_id}" não existe no marketplace.',
                    'robot_id': robot_id,
                }

            # 1️⃣ VALVE DE LICENÇA: Verifica se pode desbloquear
            license_info = await GameProfileService._get_user_license(user_id)
            
            # FREE Users (starter) cannot unlock any robot
            if license_info['max_robots'] == 0:
                logger.warning(f"❌ Usuário {user_id} (plano {license_info['plan']}) não pode desbloquear robôs")
                return {
                    'success': False,
                    'error': 'license_required',
                    'http_status': 403,
                    'message': f"Upgrade necessário! Seu plano {license_info['license_display']} não permite desbloqueio de robôs.",
                    'current_plan': license_info['license_display'],
                    'robot_id': robot_id,
                }
            
            # 2. Busca perfil para validar limite
            profile = await GameProfileService.get_or_create_profile(user_id)
            current_unlocked_count = len(profile.unlocked_robots)
            
            # Verifica se atingiu o limite do plano
            if current_unlocked_count >= license_info['max_robots'] and license_info['max_robots'] < 999:
                logger.warning(f"❌ Usuário {user_id} atingiu limite de robôs: {current_unlocked_count}/{license_info['max_robots']}")
                return {
                    'success': False,
                    'error': 'plan_limit_reached',
                    'http_status': 403,
                    'message': f"Limite do plano atingido. Seu plano {license_info['license_display']} permite apenas {license_info['max_robots']} robôs.",
                    'current_plan': license_info['license_display'],
                    'unlocked_count': current_unlocked_count,
                    'limit': license_info['max_robots'],
                    'robot_id': robot_id,
                }
            
            # 3. Determina custo (Elite vs Common)
            unlock_cost = ROBOT_UNLOCK_COST['elite'] if robot_id in ELITE_ROBOTS else ROBOT_UNLOCK_COST['common']
            logger.info(f"🔓 Tentando desbloquear {robot_id} para user_id={user_id} (plano: {license_info['plan']}, custo: {unlock_cost} pts)")
            
            # 4. Valida se já está desbloqueado
            if robot_id in profile.unlocked_robots:
                logger.warning(f"⚠️ Robot {robot_id} já estava desbloqueado para user_id={user_id}")
                return {
                    'success': False,
                    'error': 'already_unlocked',
                    'message': f'O robô {robot_id} já foi desbloqueado!',
                    'robot_id': robot_id,
                }
            
            # 5. Valida saldo
            if profile.trade_points < unlock_cost:
                shortage = unlock_cost - profile.trade_points
                logger.warning(f"❌ Saldo insuficiente para user_id={user_id}: tem {profile.trade_points}, precisa de {unlock_cost}")
                return {
                    'success': False,
                    'error': 'insufficient_balance',
                    'message': f'Saldo insuficiente. Você precisa de {shortage} pontos a mais',
                    'current_balance': profile.trade_points,
                    'required': unlock_cost,
                    'shortage': shortage,
                    'robot_id': robot_id,
                }
            
            # 6️⃣ Operação ATÔMICA: Desbloqueia e subtrai pontos simultaneamente
            result = await collection.update_one(
                {"user_id": str(user_id)},
                {
                    "$inc": {"trade_points": -unlock_cost},
                    "$addToSet": {"unlocked_robots": robot_id},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.matched_count == 0:
                logger.error(f"❌ Perfil não encontrado para user_id={user_id}")
                return {
                    'success': False,
                    'error': 'profile_not_found',
                    'message': 'Perfil não encontrado',
                }
            
            if result.modified_count == 0:
                logger.warning(f"⚠️ Nenhuma modificação realizada para user_id={user_id}")
                return {
                    'success': False,
                    'error': 'no_update',
                    'message': 'Nenhuma modificação realizada',
                }
            
            # 7. Busca perfil atualizado
            updated_profile = await GameProfileService.get_or_create_profile(user_id)
            
            logger.info(f"✅ Robô {robot_id} desbloqueado com sucesso para user_id={user_id}! (plano: {license_info['plan']}, -{unlock_cost} pts, novo saldo: {updated_profile.trade_points})")
            
            return {
                'success': True,
                'robot_id': robot_id,
                'cost': unlock_cost,
                'robot_tier': 'elite' if robot_id in ELITE_ROBOTS else 'common',
                'previous_balance': profile.trade_points,
                'new_balance': updated_profile.trade_points,
                'unlocked_robots': updated_profile.unlocked_robots,
                'total_unlocked': len(updated_profile.unlocked_robots),
                'plan': license_info['plan'],
                'plan_display': license_info['license_display'],
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao desbloquear robô {robot_id}: {str(e)}")
            raise
    
    @staticmethod
    async def calculate_robot_performance(robot_id: str, user_id: str, days: int = 15) -> Dict[str, Any]:
        """
        📊 Calcula performance REAL de um robô baseado em trades dos últimos N dias.
        
        **Lógica:**
        - Varre collection 'trades' dos últimos 15 dias
        - Ignora paper_trading=true
        - Calcula win_rate (operações lucrativas / total)
        - Calcula profit_percentage ((lucro_total / capital_investido) * 100)
        - Determina is_on_fire se win_rate > 60%
        
        Args:
            robot_id: ID do robô
            user_id: ID do usuário prop
            days: Número de dias para análise (default 15)
        
        Returns:
            {
                'robot_id': str,
                'user_id': str,
                'profit_24h': float,
                'profit_7d': float,
                'profit_15d': float,
                'win_rate': float (0-100),
                'total_trades': int,
                'is_on_fire': bool,
                'last_updated': datetime,
            }
        """
        try:
            db = get_db()
            trades_collection = db.get_collection("trades")
            
            # 🔍 Data range: últimos N dias
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # 📋 Query trades reais (não paper trading)
            query = {
                "robot_id": robot_id,
                "user_id": user_id,
                "created_at": {"$gte": cutoff_date},
                "paper_trading": {"$ne": True}  # Exclui simulações
            }
            
            trades = await trades_collection.find(query).to_list(None)
            
            if not trades or len(trades) == 0:
                logger.warning(f"⚠️ Nenhum trade encontrado para {robot_id} nos últimos {days} dias")
                return {
                    'robot_id': robot_id,
                    'user_id': user_id,
                    'profit_24h': 0.0,
                    'profit_7d': 0.0,
                    'profit_15d': 0.0,
                    'win_rate': 0.0,
                    'total_trades': 0,
                    'is_on_fire': False,
                    'last_updated': datetime.utcnow(),
                }
            
            # 📈 Calcula métricas
            total_profit = 0.0
            winning_trades = 0
            total_capital = 0.0
            
            profit_24h = 0.0
            profit_7d = 0.0
            profit_15d = 0.0
            
            now = datetime.utcnow()
            cutoff_24h = now - timedelta(hours=24)
            cutoff_7d = now - timedelta(days=7)
            
            for trade in trades:
                profit = float(trade.get("profit", 0) or 0)
                capital = float(trade.get("entry_amount", trade.get("amount", 0)) or 0)
                created_at = trade.get("created_at", datetime.utcnow())
                
                total_profit += profit
                total_capital += capital
                
                # Win/Loss rate
                if profit > 0:
                    winning_trades += 1
                
                # Time-based profit aggregation
                if created_at >= cutoff_24h:
                    profit_24h += profit
                if created_at >= cutoff_7d:
                    profit_7d += profit
                profit_15d += profit
            
            # 🎯 Calcula percentuais
            total_trades = len(trades)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            
            # Status "ON FIRE": win_rate > 60% E profit positivo
            is_on_fire = win_rate > 60.0 and total_profit > 0
            
            logger.info(
                f"✅ Performance calculada para {robot_id}: "
                f"trades={total_trades}, win_rate={win_rate:.1f}%, "
                f"profit_15d=${profit_15d:.2f}, on_fire={is_on_fire}"
            )
            
            return {
                'robot_id': robot_id,
                'user_id': user_id,
                'profit_24h': round(profit_24h, 2),
                'profit_7d': round(profit_7d, 2),
                'profit_15d': round(profit_15d, 2),
                'win_rate': round(win_rate, 2),
                'total_trades': total_trades,
                'is_on_fire': is_on_fire,
                'last_updated': datetime.utcnow(),
            }
        
        except Exception as e:
            logger.error(f"❌1 Erro ao calcular performance do {robot_id}: {str(e)}")
            # Retorna dados default em caso de erro
            return {
                'robot_id': robot_id,
                'user_id': user_id,
                'profit_24h': 0.0,
                'profit_7d': 0.0,
                'profit_15d': 0.0,
                'win_rate': 0.0,
                'total_trades': 0,
                'is_on_fire': False,
                'last_updated': datetime.utcnow(),
            }
    
    @staticmethod
    def add_trade_profit(profile: GameProfile, profit: float) -> Tuple[bool, int]:
        """
        Adiciona XP baseado em lucro obtido de trades.
        
        Args:
            profile: Perfil a atualizar
            profit: Lucro em USD
        
        Returns:
            (houve_level_up, xp_ganho)
        """
        # Fórmula: 1 XP a cada $10 de lucro (mínimo 1)
        xp_gained = max(1, int(profit / 10))
        
        should_level_up = profile.add_xp(xp_gained)
        profile.lifetime_profit += profit
        profile.updated_at = datetime.utcnow()
        
        return should_level_up, xp_gained
    
    @staticmethod
    def open_daily_chest(profile: GameProfile) -> Optional[DailyChest]:
        """
        Abre baú diário e retorna recompensa.
        Pode ser aberto uma vez por dia (por período de 24h).
        
        Returns:
            DailyChest com recompensa, ou None se já foi aberto hoje
        """
        now = datetime.utcnow()
        
        # Verifica se já foi aberto nas últimas 24h
        if profile.last_daily_chest_opened:
            time_since_last = now - profile.last_daily_chest_opened
            if time_since_last.total_seconds() < 86400:  # 24h em segundos
                return None
        
        # Calcula streak (se abriu ontem, incrementa; caso contrário, reseta)
        if profile.last_daily_chest_opened:
            time_since_last = now - profile.last_daily_chest_opened
            if time_since_last.total_seconds() > 86400 * 2:  # Mais de 2 dias = reseta
                profile.daily_chest_streak = 0
        
        # Random rewards (10-50 pontos, 25-75 XP)
        points_reward = random.randint(10, 50)
        xp_reward = random.randint(25, 75)
        
        # Bônus por streak (a cada 7 dias, +25% de recompensa)
        streak_multiplier = 1.0 + (profile.daily_chest_streak // 7) * 0.25
        points_reward = int(points_reward * streak_multiplier)
        xp_reward = int(xp_reward * streak_multiplier)
        
        # Aplica recompensas
        profile.trade_points += points_reward
        should_level_up = profile.add_xp(xp_reward)
        profile.daily_chest_streak += 1
        profile.last_daily_chest_opened = now
        profile.updated_at = now
        
        # Cria registro da recompensa
        chest = DailyChest(
            user_id=profile.user_id,
            xp_reward=xp_reward,
            points_reward=points_reward,
            opened_at=now,
        )
        
        return chest
    
    @staticmethod
    def unlock_robot_with_points(
        profile: GameProfile, 
        unlock_cost: int
    ) -> Tuple[bool, str]:
        """
        Tenta desbloquear um robô usando TradePoints.
        
        Returns:
            (sucesso, mensagem)
        """
        if profile.trade_points < unlock_cost:
            shortfall = unlock_cost - profile.trade_points
            return False, f"Você precisa de {shortfall} pontos a mais"
        
        profile.trade_points -= unlock_cost
        profile.bots_unlocked += 1
        profile.updated_at = datetime.utcnow()
        
        return True, "Robô desbloqueado com sucesso!"
    
    @staticmethod
    async def initialize_indexes():
        """
        ⚡ Inicializa índices MongoDB para performance.
        Deve ser chamado ao iniciar a aplicação.
        """
        collection = GameProfileService._get_collection()
        
        try:
            # Índice descendente em trade_points para queries rápidas de leaderboard
            await collection.create_index(
                [("trade_points", -1)],
                name="idx_trade_points_desc",
                background=True
            )
            logger.info("✅ Índice MongoDB criado: idx_trade_points_desc")
            
            # Índice em user_id para buscas rápidas
            await collection.create_index(
                [("user_id", 1)],
                name="idx_user_id",
                background=True,
                unique=True
            )
            logger.info("✅ Índice MongoDB criado: idx_user_id")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao criar índices (pode ser apenas aviso): {str(e)}")
    
    @staticmethod
    def _get_badge_by_level(level: int) -> str:
        """
        Retorna badge visual baseado no nível.
        
        Args:
            level: Nível do usuário (1+)
        
        Returns:
            String com badge + descrição
        """
        if level <= 10:
            return "🟢 Novato"
        elif level <= 30:
            return "🔵 Trader"
        elif level <= 60:
            return "🟣 Expert"
        elif level <= 100:
            return "🟡 Whale"
        else:
            return "👑 Lenda"
    
    @staticmethod
    def _mask_email(email: str) -> str:
        """
        Mascara email por privacidade.
        
        Exemplo: "usuario@gmail.com" → "usu***@gmail.com"
        Se não houver @, retorna primeiros 3 chars + ***.
        
        Args:
            email: Email ou identificador do usuário
        
        Returns:
            Email mascarado
        """
        if not email or '@' not in email:
            if not email:
                return "User***"
            # Se não tem @, assume que é um username
            return email[:3] + "***" if len(email) > 3 else "***"
        
        local, domain = email.split('@', 1)
        
        # Mostra primeiros 3 caracteres
        if len(local) <= 3:
            masked_local = "***"
        else:
            masked_local = local[:3] + "***"
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    async def get_leaderboard(limit: int = 50) -> List[Dict[str, Any]]:
        """
        ⭐ Busca o leaderboard global dos Top N usuários.
        
        **Otimização:**
        - Query usa índice descendente em trade_points
        - Projection retorna apenas campos necessários
        
        **Privacidade:**
        - Email mascarado automaticamente
        
        Args:
            limit: Número de usuários a retornar (padrão: 50)
        
        Returns:
            Lista de dicts com:
            {
                "rank": int (1-based),
                "user_masked_name": str,
                "level": int,
                "trade_points": int,
                "badge": str,
                "is_top_3": bool,
            }
        """
        try:
            collection = GameProfileService._get_collection()
            
            # Query otimizada com projection (apenas campos necessários)
            pipeline = [
                # Stage 1: Ordenar por trade_points descendente (usa índice)
                {"$sort": {"trade_points": -1}},
                
                # Stage 2: Limitar a N resultados
                {"$limit": limit},
                
                # Stage 3: Projetar apenas campos necessários
                {"$project": {
                    "_id": 0,
                    "user_id": 1,
                    "trade_points": 1,
                    "level": 1,
                    "email": {"$ifNull": ["$email", "anonymous"]},  # Caso não tenha email registrado
                }}
            ]
            
            cursor = await collection.aggregate(pipeline).to_list(length=limit)
            
            leaderboard = []
            for idx, doc in enumerate(cursor, start=1):
                masked_email = GameProfileService._mask_email(doc.get("email", ""))
                badge = GameProfileService._get_badge_by_level(doc.get("level", 1))
                
                leaderboard.append({
                    "rank": idx,
                    "user_masked_name": masked_email,
                    "level": doc.get("level", 1),
                    "trade_points": doc.get("trade_points", 0),
                    "badge": badge,
                    "is_top_3": idx <= 3,
                })
            
            logger.info(f"✅ Leaderboard retornado: {len(leaderboard)} usuários")
            return leaderboard
        
        except Exception as e:
            logger.error(f"❌ Erro ao buscar leaderboard: {str(e)}")
            return []
    
    @staticmethod
    async def get_user_rank(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca a posição de um usuário específico no leaderboard global.
        
        Útil para mostrar: "Você está na posição #1205!"
        
        Args:
            user_id: ID do usuário
        
        Returns:
            {
                "rank": int,
                "trade_points": int,
                "level": int,
                "badge": str,
            }
            ou None se usuário não encontrado
        """
        try:
            collection = GameProfileService._get_collection()
            
            # Busca o perfil do usuário
            user_profile = await collection.find_one(
                {"user_id": str(user_id)},
                {"trade_points": 1, "level": 1}
            )
            
            if not user_profile:
                logger.warning(f"⚠️ Perfil não encontrado para ranking: {user_id}")
                return None
            
            user_points = user_profile.get("trade_points", 0)
            user_level = user_profile.get("level", 1)
            
            # Conta quantos usuários têm mais pontos
            users_ahead = await collection.count_documents(
                {"trade_points": {"$gt": user_points}}
            )
            
            # Rank = pessoas antes + 1
            rank = users_ahead + 1
            
            badge = GameProfileService._get_badge_by_level(user_level)
            
            logger.info(f"✅ Rank do usuário {user_id}: #{rank}")
            
            return {
                "rank": rank,
                "trade_points": user_points,
                "level": user_level,
                "badge": badge,
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao buscar rank do usuário: {str(e)}")
            return None
    
    @staticmethod
    async def log_transaction(
        user_id: str,
        transaction_type: str,
        points_change: int,
        xp_change: int,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Log auditoria de transação na collection gamification_transactions.
        
        Rastreia:
        - user_id
        - type: "daily_chest", "unlock_robot", "achievement", etc
        - points_change (pode ser negativo)
        - xp_change (pode ser negativo)
        - metadata: info extra (streak, robot_id, etc)
        - created_at: timestamp
        
        Args:
            user_id: ID do usuário
            transaction_type: Tipo de transação
            points_change: Mudança em pontos (positivo ou negativo)
            xp_change: Mudança em XP
            metadata: Dados adicionais
        
        Returns:
            True se bem-sucedido
        """
        try:
            db = get_db()
            transactions_col = db["gamification_transactions"]
            
            transaction_doc = {
                "user_id": str(user_id),
                "type": transaction_type,
                "points_change": points_change,
                "xp_change": xp_change,
                "metadata": metadata or {},
                "created_at": datetime.utcnow(),
            }
            
            result = await transactions_col.insert_one(transaction_doc)
            
            logger.info(
                f"✅ Transação auditada: {transaction_type} para {user_id} | "
                f"Pts: {points_change:+d}, XP: {xp_change:+d}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Erro ao log transação: {str(e)}")
            # Não bloqueia operação principal se auditoria falhar
            return False
    
    @staticmethod
    async def update_leaderboard_cache() -> Dict[str, Any]:
        """
        Recalcula e atualiza cache do leaderboard.
        Deve ser chamado periodicamente por scheduler.
        
        Fluxo:
        1. Busca todos perfis ordenados por trade_points DESC
        2. Calcula rank e badge para cada
        3. Atualiza collection leaderboard_cache
        4. Retorna estatísticas
        
        Returns:
            Dict com status e estatísticas
        """
        try:
            db = get_db()
            profiles_col = db["game_profiles"]
            cache_col = db["leaderboard_cache"]
            
            logger.info("📊 Iniciando atualização de cache do leaderboard...")
            
            # Busca todos perfis ordem por trade_points DESC
            # Projeção: apenas campos necessários
            profiles = await profiles_col.aggregate([
                {
                    "$sort": {"trade_points": -1}
                },
                {
                    "$project": {
                        "_id": 1,
                        "user_id": 1,
                        "trade_points": 1,
                        "level": 1,
                        "xp": 1,
                        "created_at": 1,
                    }
                }
            ]).to_list(None)
            
            # Limpa cache anterior
            await cache_col.delete_many({})
            
            # Insere ranking atualizado
            updated_at = datetime.utcnow()
            cache_entries = []
            
            for rank, profile in enumerate(profiles, 1):
                badge = GameProfileService._get_badge_by_level(profile.get("level", 1))
                
                # Mascara email/nome (usar user_id como fallback)
                user_id = profile.get("user_id", "anonymous")
                masked_name = GameProfileService._mask_email(user_id)
                
                cache_entries.append({
                    "rank": rank,
                    "user_id": user_id,
                    "user_masked_name": masked_name,
                    "level": profile.get("level", 1),
                    "trade_points": profile.get("trade_points", 0),
                    "badge": badge,
                    "is_top_3": rank <= 3,
                    "updated_at": updated_at,
                })
            
            if cache_entries:
                await cache_col.insert_many(cache_entries)
            
            logger.info(
                f"✅ Leaderboard cache atualizado: {len(cache_entries)} usuários | "
                f"Top 1: {cache_entries[0]['user_masked_name'] if cache_entries else 'N/A'}"
            )
            
            return {
                "success": True,
                "total_entries": len(cache_entries),
                "updated_at": updated_at,
                "message": f"Cache atualizado com {len(cache_entries)} usuários",
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar leaderboard cache: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Erro ao atualizar leaderboard",
            }


class RobotRankingService:

    """Service para calcular e manter ranking de robôs"""
    
    @staticmethod
    def calculate_biweekly_period(date: Optional[datetime] = None) -> int:
        """
        Calcula id da quinzena atual.
        Muda a cada 15 dias automaticamente.
        
        Args:
            date: Data para calcular (padrão: agora)
        
        Returns:
            Número inteiro representando a quinzena
        """
        if date is None:
            date = datetime.utcnow()
        
        # Epoch time é 1970-01-01
        # Calcula quantas quinzenas se passaram
        period = int(date.timestamp() / (15 * 24 * 60 * 60))
        return period
    
    @staticmethod
    def recalculate_rankings(rankings: List[RobotRanking]) -> List[RobotRanking]:
        """
        Recalcula ranking baseado em profit_15d.
        Se período mudou, reseta os ranks.
        
        Args:
            rankings: Lista de RobotRanking
        
        Returns:
            Lista atualizada com novos ranks
        """
        current_period = RobotRankingService.calculate_biweekly_period()
        
        # Filtra robôs do período atual
        current_period_rankings = [
            r for r in rankings 
            if r.biweekly_period == current_period
        ]
        
        # Ordena por profit_15d (maior primeiro)
        current_period_rankings.sort(
            key=lambda x: x.profit_15d, 
            reverse=True
        )
        
        # Atribui novos ranks
        for rank, ranking in enumerate(current_period_rankings, 1):
            ranking.biweekly_rank = rank
            
            # Status "ON FIRE": Top 5 com performance acima da média
            top_5_threshold = current_period_rankings[min(4, len(current_period_rankings)-1)].profit_15d * 0.95
            ranking.is_on_fire = ranking.profit_15d >= top_5_threshold and rank <= 5
        
        return rankings
    
    @staticmethod
    def get_medal_by_rank(rank: int) -> Optional[str]:
        """
        Retorna emoji de medalha baseado no rank.
        
        Returns:
            🥇 para 1º, 🥈 para 2º, 🥉 para 3º, None para outros
        """
        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }
        return medals.get(rank)
    
    @staticmethod
    def format_robot_display(ranking: RobotRanking) -> Dict[str, Any]:
        """
        Formata dados de ranking para exibição no frontend.
        
        Returns:
            Dict com dados formatados
        """
        medal = RobotRankingService.get_medal_by_rank(ranking.biweekly_rank)
        
        return {
            "rank": ranking.biweekly_rank,
            "medal": medal,
            "is_on_fire": ranking.is_on_fire,
            "profit_15d": ranking.profit_15d,
            "profit_7d": ranking.profit_7d,
            "profit_24h": ranking.profit_24h,
            "win_rate": ranking.win_rate,
            "total_trades": ranking.total_trades,
        }


class GamificationAchievements:
    """Achievements e marcos (Extensível)"""
    
    ACHIEVEMENTS = {
        "first_bot_unlock": {
            "name": "Primeiro Passo",
            "description": "Desbloqueie seu primeiro robô",
            "icon": "🤖",
            "points": 50,
        },
        "level_10": {
            "name": "Nível 10",
            "description": "Alcance o nível 10",
            "icon": "📈",
            "points": 200,
        },
        "7_day_streak": {
            "name": "7 Dias Consecutivos",
            "description": "Abra o Daily Chest por 7 dias",
            "icon": "🔥",
            "points": 150,
        },
        "top_trader": {
            "name": "Top Trader",
            "description": "Ganhe R$10,000 em lucro",
            "icon": "👑",
            "points": 500,
        },
    }
    
    @staticmethod
    def check_achievements(profile: GameProfile) -> List[str]:
        """
        Verifica quais achievements foram desbloqueados.
        
        Returns:
            Lista de achievement IDs desbloqueados
        """
        unlocked = []
        
        if profile.bots_unlocked >= 1:
            unlocked.append("first_bot_unlock")
        if profile.level >= 10:
            unlocked.append("level_10")
        if profile.daily_chest_streak >= 7:
            unlocked.append("7_day_streak")
        if profile.lifetime_profit >= 10000:
            unlocked.append("top_trader")
        
        return unlocked
