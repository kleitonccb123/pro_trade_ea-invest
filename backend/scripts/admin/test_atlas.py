import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    uri = os.getenv("DATABASE_URL")
    print(f"🔌 Testando conexão com: {uri[:50]}...")
    
    client = AsyncIOMotorClient(uri)
    try:
        # O comando ping verifica se a conexão está ativa
        await client.admin.command('ping')
        print("✅ SUCESSO: Conectado ao MongoDB Atlas!")
    except Exception as e:
        print(f"❌ ERRO de conexão: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())
