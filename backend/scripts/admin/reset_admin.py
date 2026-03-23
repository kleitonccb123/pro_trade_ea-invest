#!/usr/bin/env python
"""Script para resetar a senha do admin"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Setup FastAPI app para inicializar o banco
from app.main import app, startup_event

async def reset_admin_password():
    # Executar startup para inicializar o banco
    await startup_event()
    
    from app.core.local_db_manager import get_local_db
    from app.core.security import get_password_hash
    
    db = get_local_db()
    
    # Email e nova senha
    admin_email = 'admin@cryptotrade.com'
    new_password = 'admin123'  # Senha simples para teste
    
    # Procurar admin existente
    admin = await db.find_user_by_email(admin_email)
    
    if admin:
        print(f'✅ Admin encontrado')
        # Atualizar senha
        hashed_pwd = get_password_hash(new_password)
        await db.connection.users.update_one(
            {'email': admin_email},
            {'$set': {'hashed_password': hashed_pwd}}
        )
        print(f'✅ Senha atualizada com sucesso!')
        print(f'   Email: {admin_email}')
        print(f'   Nova Senha: {new_password}')
    else:
        print('❌ Admin não encontrado')

# Executar
try:
    asyncio.run(reset_admin_password())
except Exception as e:
    print(f'❌ Erro: {e}')
    import traceback
    traceback.print_exc()
