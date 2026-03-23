#!/usr/bin/env python
"""Script to create an admin user with infinite credits"""

import asyncio
import sys
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import get_password_hash
from app.core.config import settings

async def create_admin_user():
    """Create an admin user with infinite credits in MongoDB"""
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.database_url)
        db = client[settings.database_name]
        users_col = db['users']
        
        email = 'admin@cryptotrade.com'
        password = 'AdminPassword123!'
        
        # Check if user already exists
        existing = await users_col.find_one({'email': email})
        if existing:
            print(f'✓ Admin user already exists: {email}')
            print(f'  ID: {existing["_id"]}')
            client.close()
            return
        
        # Create admin user with infinite credits
        admin_user = {
            'email': email,
            'hashed_password': get_password_hash(password),
            'name': 'Admin',
            'username': 'admin',
            'full_name': 'System Administrator',
            'auth_provider': 'local',
            'is_active': True,
            'is_superuser': True,  # Admin flag
            'plan': 'enterprise',
            'activation_credits': 999999,  # Infinite credits
            'activation_credits_used': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'login_count': 0,
            'exchange_api_keys': {},
        }
        
        result = await users_col.insert_one(admin_user)
        print(f'✓ ADMIN USER CREATED SUCCESSFULLY!')
        print(f'')
        print(f'  📧 Email: {email}')
        print(f'  🔑 Password: {password}')
        print(f'  🆔 ID: {result.inserted_id}')
        print(f'  👑 Superuser: True')
        print(f'  💰 Activation Credits: 999,999 (INFINITE)')
        print(f'  📋 Plan: Enterprise')
        print(f'')
        
        client.close()
        
    except Exception as e:
        print(f'✗ Error creating admin user: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(create_admin_user())
