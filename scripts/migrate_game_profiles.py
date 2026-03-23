"""
Script de Seed - Migrar usuários existentes para game_profiles

Propósito:
- Buscar todos os usuários na collection `users`
- Para cada usuário SEM perfil em `game_profiles`, criar um perfil inicial
- Valores iniciais: trade_points: 500, level: 1, xp: 0, etc

Uso:
    cd backend
    python -m scripts.migrate_game_profiles
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from bson import ObjectId

# Adicionar backend ao path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Importar dependências
try:
    from app.core.database import get_db
except ImportError:
    logger.error("❌ Erro ao importar get_db. Certifique-se de que este script é executado do diretório backend")
    sys.exit(1)


async def migrate_game_profiles():
    """
    Migra todos os usuários existentes para a collection game_profiles.
    """
    logger.info("=" * 80)
    logger.info("🔄 INICIANDO MIGRAÇÃO DE USUÁRIOS PARA GAME_PROFILES")
    logger.info("=" * 80)
    
    try:
        db = get_db()
        users_col = db["users"]
        game_profiles_col = db["game_profiles"]
        
        # 1. Buscar todos os usuários
        total_users = await users_col.count_documents({})
        logger.info(f"\n📊 Total de usuários no banco: {total_users}")
        
        # 2. Buscar usuários que já têm perfil em game_profiles
        existing_profiles = await game_profiles_col.count_documents({})
        logger.info(f"📊 Perfis de gamificação existentes: {existing_profiles}")
        
        # 3. Buscar usuários SEM perfil em game_profiles
        users_without_profile = []
        async for user in users_col.find({}):
            user_id_str = str(user.get("_id"))
            profile = await game_profiles_col.find_one({"user_id": user_id_str})
            
            if not profile:
                users_without_profile.append(user)
        
        users_to_migrate = len(users_without_profile)
        logger.info(f"🎯 Usuários a migrar: {users_to_migrate}")
        
        if users_to_migrate == 0:
            logger.info("✅ Todos os usuários já possuem perfil de gamificação!")
            return
        
        # 4. Criar perfis para usuários sem perfil
        created_count = 0
        errors = []
        
        for idx, user in enumerate(users_without_profile, 1):
            user_id = str(user.get("_id"))
            user_email = user.get("email", "unknown")
            
            try:
                profile_doc = {
                    "user_id": user_id,
                    "trade_points": 500,  # Valor inicial conforme especificação
                    "level": 1,
                    "xp": 0,
                    "unlocked_robots": [],
                    "lifetime_profit": 0.0,
                    "last_daily_chest_opened": None,
                    "streak_count": 0,
                    "created_at": user.get("created_at", datetime.utcnow()),
                    "updated_at": datetime.utcnow(),
                }
                
                result = await game_profiles_col.insert_one(profile_doc)
                created_count += 1
                
                # Mostrar progresso
                if idx % 10 == 0 or idx == users_to_migrate:
                    logger.info(f"✅ {idx}/{users_to_migrate} perfis criados... ({user_email})")
                
            except Exception as e:
                error_msg = f"❌ Erro ao criar perfil para {user_email}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # 5. Relatório final
        logger.info("\n" + "=" * 80)
        logger.info("📋 RELATÓRIO FINAL DA MIGRAÇÃO")
        logger.info("=" * 80)
        logger.info(f"✅ Perfis criados: {created_count}")
        logger.info(f"❌ Erros: {len(errors)}")
        
        if errors:
            logger.info("\n⚠️ Erros ocorridos:")
            for error in errors[:10]:  # Mostrar apenas os primeiros 10
                logger.info(f"   {error}")
            if len(errors) > 10:
                logger.info(f"   ... e mais {len(errors) - 10} erros")
        
        # 6. Validação final
        final_count = await game_profiles_col.count_documents({})
        logger.info(f"\n📊 Total de perfis após migração: {final_count}")
        logger.info(f"📊 Total de usuários: {total_users}")
        
        if final_count >= total_users:
            logger.info("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO! Todos os usuários têm perfis.")
        else:
            logger.warning(f"⚠️ {total_users - final_count} usuários ainda sem perfil")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO NA MIGRAÇÃO: {str(e)}")
        raise


async def main():
    """Função principal"""
    try:
        await migrate_game_profiles()
        logger.info("\n✅ Script finalizado com sucesso")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Script finalizado com erro: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
