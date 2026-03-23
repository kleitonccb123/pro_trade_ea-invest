#!/usr/bin/env python
"""Script to create a test user in MongoDB for testing"""

import asyncio
import sys
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import get_password_hash
from app.core.config import settings

async def create_test_user():
    """Create a test user in MongoDB"""
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.database_url)
        db = client[settings.database_name]
        users_col = db['users']
        
        email = 'kleitonbrito@gmail.com'
        password = 'Teste123!'
        
        # Check if user already exists
        existing = await users_col.find_one({'email': email})
        if existing:
            print(f'✓ User already exists: {email}')
            client.close()
            return
        
        # Create test user
        test_user = {
            'email': email,
            'hashed_password': get_password_hash(password),
            'name': 'Demo User',
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        
        result = await users_col.insert_one(test_user)
        print(f'✓ User created successfully!')
        print(f'  ID: {result.inserted_id}')
        print(f'  Email: {email}')
        print(f'  Password: {password}')
        
        client.close()
        
    except Exception as e:
        print(f'✗ Error creating user: {e}')
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(create_test_user())
