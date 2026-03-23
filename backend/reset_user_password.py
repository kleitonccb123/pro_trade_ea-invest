#!/usr/bin/env python
"""
Script para resetar a senha de um usu?rio no banco de dados
Uso: python reset_user_password.py <email> <nova_senha>
"""

import asyncio
import sys
import os
from bson import ObjectId

# Adicionar o caminho do app ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import connect_db, disconnect_db, get_db
from app.core.security import get_password_hash


async def reset_password(email: str, new_password: str):
    """Reseta a senha de um usu?rio"""
    try:
        await connect_db()
        db = get_db()
        users_col = db.users
        
        # Buscar usu?rio
        user = await users_col.find_one({"email": email.lower()})
        if not user:
            print(f"? Usu?rio com email '{email}' n?o encontrado!")
            await disconnect_db()
            return False
        
        # Hash da nova senha
        hashed_password = get_password_hash(new_password)
        
        # Atualizar senha
        result = await users_col.update_one(
            {"email": email.lower()},
            {"$set": {"hashed_password": hashed_password}}
        )
        
        if result.modified_count > 0:
            print(f"? Senha resetada com sucesso para {email}")
            print(f"   Nova senha: {new_password}")
            await disconnect_db()
            return True
        else:
            print(f"? Falha ao atualizar senha para {email}")
            await disconnect_db()
            return False
            
    except Exception as e:
        print(f"? Erro: {e}")
        await disconnect_db()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python reset_user_password.py <email> <nova_senha>")
        print("Exemplo: python reset_user_password.py kleitonbritocosta@gmail.com senha123")
        sys.exit(1)
    
    email = sys.argv[1]
    new_password = sys.argv[2]
    
    success = asyncio.run(reset_password(email, new_password))
    sys.exit(0 if success else 1)
