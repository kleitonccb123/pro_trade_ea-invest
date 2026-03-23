#!/usr/bin/env python
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.local_db_manager import get_local_db
from app.core.security import verify_password

async def check_admin():
    db = get_local_db()
    admin = await db.find_user_by_email('admin@cryptotrade.com')
    if admin:
        print('✅ Admin encontrado:')
        print(f'   Email: {admin.get("email")}')
        print(f'   Is Superuser: {admin.get("is_superuser")}')
        print(f'   Activation Credits: {admin.get("activation_credits")}')
        
        # Testar as senhas possíveis
        pwd_to_test = 'AdminPassword123!'
        hashed = admin.get('hashed_password')
        if verify_password(pwd_to_test, hashed):
            print(f'   ✓ Senha "AdminPassword123!" está CORRETA')
        else:
            print(f'   ✗ Senha "AdminPassword123!" está INCORRETA')
            
        # Try common passwords
        common_passwords = ['admin123', 'password', 'demo123', 'Admin@123', '123456']
        print('\n   Testando senhas comuns...')
        for pwd in common_passwords:
            if verify_password(pwd, hashed):
                print(f'   ✓ ENCONTRADO: "{pwd}" funciona!')
                break
    else:
        print('❌ Admin não encontrado no banco')

asyncio.run(check_admin())
