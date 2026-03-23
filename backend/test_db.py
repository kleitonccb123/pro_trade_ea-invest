import asyncio
from app.core.local_db_manager import init_local_db, get_local_db

async def test():
    await init_local_db()
    db = get_local_db()
    user = await db.find_user_by_email('demo@tradehub.com')
    print(f'✅ Usuário demo encontrado: {user is not None}')
    if user:
        print(f'   Email: {user["email"]}')
        print(f'   Name: {user.get("name", "N/A")}')
        print(f'   ID: {user["_id"]}')

if __name__ == "__main__":
    asyncio.run(test())