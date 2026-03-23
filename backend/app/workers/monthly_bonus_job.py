"""
Monthly Bonus Worker — Credita bônus mensal de pontos por plano.

Deve ser registrado no scheduler (APScheduler ou cron) para rodar
no primeiro dia de cada mês à 00:05 UTC.

Uso com APScheduler:
    from app.workers.monthly_bonus_job import credit_monthly_bonuses
    scheduler.add_job(credit_monthly_bonuses, 'cron', day=1, hour=0, minute=5)

Ou com cron:
    0 5 1 * * cd /app && python -m app.workers.monthly_bonus_job
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from app.core.database import get_db
from app.core.plan_config import PLAN_CONFIG, resolve_plan_key

logger = logging.getLogger(__name__)


async def credit_monthly_bonuses() -> Dict[str, Any]:
    """
    Credita bônus mensal de TradePoints para todos os usuários com plano ativo.
    
    Regras:
    - Cada plano tem um valor monthly_bonus_points em PLAN_CONFIG
    - free/starter: 0 (ou conforme config)
    - Usa operação atômica $inc no MongoDB
    - Registra transação para auditoria
    - Idempotência: verifica se já creditou neste mês (via gamification_transactions)
    
    Returns:
        {
            'users_credited': int,
            'total_points_distributed': int,
            'month': str,
            'errors': int,
        }
    """
    db = get_db()
    users_col = db["users"]
    profiles_col = db["game_profiles"]
    transactions_col = db["gamification_transactions"]
    
    now = datetime.utcnow()
    month_key = now.strftime("%Y-%m")  # e.g. "2025-01"
    
    logger.info(f"🎁 Iniciando creditação de bônus mensal para {month_key}")
    
    stats = {
        "users_credited": 0,
        "total_points_distributed": 0,
        "month": month_key,
        "errors": 0,
        "skipped_free": 0,
        "skipped_already_credited": 0,
    }
    
    try:
        # Busca todos os usuários com plano ativo
        cursor = users_col.find(
            {"plan": {"$exists": True}},
            {"_id": 1, "plan": 1, "email": 1}
        )
        
        async for user_doc in cursor:
            user_id = str(user_doc["_id"])
            raw_plan = user_doc.get("plan", "free")
            
            try:
                canonical_plan = resolve_plan_key(raw_plan)
                plan_cfg = PLAN_CONFIG.get(canonical_plan, PLAN_CONFIG["free"])
                bonus_points = plan_cfg.get("monthly_bonus_points", 0)
                
                # Skip free/zero bonus plans
                if bonus_points <= 0:
                    stats["skipped_free"] += 1
                    continue
                
                # Idempotência: verifica se já creditou este mês
                already_credited = await transactions_col.find_one({
                    "user_id": user_id,
                    "transaction_type": "monthly_bonus",
                    "metadata.month_key": month_key,
                })
                
                if already_credited:
                    stats["skipped_already_credited"] += 1
                    continue
                
                # Credita pontos atomicamente
                result = await profiles_col.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"trade_points": bonus_points},
                        "$set": {"updated_at": now},
                    }
                )
                
                if result.matched_count == 0:
                    # Perfil não existe ainda — cria um básico
                    await profiles_col.insert_one({
                        "user_id": user_id,
                        "trade_points": 1000 + bonus_points,  # Bônus boas-vindas + mensal
                        "level": 1,
                        "xp": 0,
                        "unlocked_robots": [],
                        "lifetime_profit": 0.0,
                        "streak_count": 0,
                        "created_at": now,
                        "updated_at": now,
                    })
                
                # Registra transação
                await transactions_col.insert_one({
                    "user_id": user_id,
                    "transaction_type": "monthly_bonus",
                    "points_change": bonus_points,
                    "xp_change": 0,
                    "description": f"Bônus mensal do plano {plan_cfg['display']} ({month_key})",
                    "metadata": {
                        "month_key": month_key,
                        "plan": canonical_plan,
                        "plan_display": plan_cfg["display"],
                        "bonus_points": bonus_points,
                    },
                    "status": "completed",
                    "created_at": now,
                })
                
                stats["users_credited"] += 1
                stats["total_points_distributed"] += bonus_points
                
                logger.debug(f"  ✓ {user_id} ({plan_cfg['display']}): +{bonus_points} pts")
                
            except Exception as e:
                logger.error(f"  ❌ Erro ao creditar {user_id}: {e}")
                stats["errors"] += 1
        
        logger.info(
            f"✅ Bônus mensal {month_key} concluído: "
            f"{stats['users_credited']} creditados, "
            f"{stats['total_points_distributed']} pts distribuídos, "
            f"{stats['skipped_free']} free, "
            f"{stats['skipped_already_credited']} já creditados, "
            f"{stats['errors']} erros"
        )
        
        return stats
    
    except Exception as e:
        logger.error(f"❌ Erro fatal no job de bônus mensal: {e}")
        raise


# Permite rodar diretamente: python -m app.workers.monthly_bonus_job
if __name__ == "__main__":
    asyncio.run(credit_monthly_bonuses())
