"""
SQLite Local Database for User Authentication

Persist?ncia local para quando MongoDB Atlas n?o est? dispon?vel.
Os dados s?o salvos em arquivo e persistem entre reinicializa??es.
"""

import os
import json
import aiosqlite
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Caminho do banco de dados local
DB_PATH = Path(__file__).parent.parent.parent / "data" / "local_users.db"


class LocalUserDatabase:
    """Banco de dados SQLite local para usu?rios."""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Conecta ao banco de dados SQLite."""
        # Criar diret?rio se n?o existir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row
        
        # Criar tabelas
        await self._create_tables()
        
        # Migração: adiciona colunas novas em dbs já existentes (safe/idempotente)
        await self._migrate_columns()
        
        # Criar usuários demo se não existirem
        await self._ensure_demo_users()
        
        logger.info(f"? SQLite conectado: {self.db_path}")
    
    async def _migrate_columns(self):
        """Adiciona colunas novas em bancos de dados já existentes (migração safe)."""
        new_columns = [
            ("plan", "TEXT DEFAULT 'starter'"),
            ("plan_activated_at", "TEXT"),
            ("perfect_pay_next_charge_date", "TEXT"),
            ("perfect_pay_subscription_id", "TEXT"),
        ]
        async with self._connection.execute("PRAGMA table_info(users)") as cur:
            existing = {row[1] async for row in cur}
        for col_name, col_def in new_columns:
            if col_name not in existing:
                await self._connection.execute(
                    f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"
                )
                logger.info(f"✅ Migração: coluna '{col_name}' adicionada à tabela users")
        await self._connection.commit()
    
    async def _create_tables(self):
        """Cria as tabelas necess?rias."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                username TEXT,
                name TEXT,
                hashed_password TEXT NOT NULL,
                full_name TEXT,
                auth_provider TEXT DEFAULT 'local',
                google_id TEXT,
                is_active INTEGER DEFAULT 1,
                is_superuser INTEGER DEFAULT 0,
                activation_credits INTEGER DEFAULT 0,
                activation_credits_used INTEGER DEFAULT 0,
                plan TEXT DEFAULT 'starter',
                plan_activated_at TEXT,
                perfect_pay_next_charge_date TEXT,
                perfect_pay_subscription_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                last_login TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);

            CREATE TABLE IF NOT EXISTS game_profiles (
                user_id TEXT PRIMARY KEY,
                trade_points INTEGER DEFAULT 1000,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                unlocked_robots TEXT DEFAULT '[]',
                bots_unlocked INTEGER DEFAULT 0,
                lifetime_profit REAL DEFAULT 0.0,
                last_daily_chest_opened TEXT,
                streak_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS strategy_manager_state (
                user_id TEXT PRIMARY KEY,
                state_json TEXT DEFAULT '{}',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._connection.commit()
    
    async def _ensure_demo_users(self):
        """Garante que os usu?rios demo existam (apenas em modo desenvolvimento)."""
        import os as _os
        if _os.getenv("APP_MODE", "dev") != "dev":
            return
        from app.core.security import get_password_hash
        
        demo_users = [
            {
                "email": "demo@cryptotrade.com",
                "username": "demo",
                "name": "Demo User",
                "is_superuser": False,
            },
            {
                "email": "demo@tradehub.com", 
                "username": "demo2",
                "name": "Demo TradeHub",
                "is_superuser": False,
            },
            {
                "email": "admin@cryptotrade.com",
                "username": "admin",
                "name": "Administrator",
                "is_superuser": True,
            },
        ]
        
        for user_data in demo_users:
            existing = await self.find_user_by_email(user_data["email"])
            if not existing:
                import uuid
                user_id = str(uuid.uuid4())
                password_hash = get_password_hash("demo123")
                now = datetime.utcnow().isoformat()
                
                await self._connection.execute("""
                    INSERT INTO users (id, email, username, name, hashed_password, full_name, 
                                       auth_provider, is_active, is_superuser, created_at, updated_at, last_login)
                    VALUES (?, ?, ?, ?, ?, ?, 'local', 1, ?, ?, ?, NULL)
                """, (user_id, user_data["email"], user_data["username"], user_data["name"],
                      password_hash, user_data["name"], user_data["is_superuser"], now, now))
                
                await self._connection.commit()
                logger.info(f"? Usu?rio demo criado: {user_data['email']}")
    
    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Busca usu?rio por email."""
        async with self._connection.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None
    
    async def find_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Busca usu?rio por ID."""
        async with self._connection.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None
    
    async def find_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """Busca usu?rio por Google ID."""
        async with self._connection.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None
    
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo usu?rio."""
        import uuid
        
        user_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        await self._connection.execute("""
            INSERT INTO users (id, email, username, name, hashed_password, full_name,
                              auth_provider, google_id, is_active, is_superuser, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            user_data.get("email", "").lower(),
            user_data.get("username", ""),
            user_data.get("name", ""),
            user_data.get("hashed_password", ""),
            user_data.get("full_name", user_data.get("name", "")),
            user_data.get("auth_provider", "local"),
            user_data.get("google_id"),
            1 if user_data.get("is_active", True) else 0,
            1 if user_data.get("is_superuser", False) else 0,
            now,
            now
        ))
        
        await self._connection.commit()
        
        return await self.find_user_by_id(user_id)
    
    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Atualiza um usu?rio."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]
        
        await self._connection.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            values
        )
        await self._connection.commit()
        
        return await self.find_user_by_id(user_id)
    
    async def list_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Lista todos os usu?rios."""
        async with self._connection.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
    
    # ── game_profiles ─────────────────────────────────────────────────────────

    async def get_game_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Busca perfil de gamificação por user_id."""
        async with self._connection.execute(
            "SELECT * FROM game_profiles WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                try:
                    data["unlocked_robots"] = json.loads(data.get("unlocked_robots") or "[]")
                except Exception:
                    data["unlocked_robots"] = []
                data["_id"] = data["user_id"]
                return data
        return None

    async def get_all_game_profiles(self) -> list:
        """Retorna todos os perfis de gamificação."""
        async with self._connection.execute("SELECT * FROM game_profiles") as cursor:
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    d["unlocked_robots"] = json.loads(d.get("unlocked_robots") or "[]")
                except Exception:
                    d["unlocked_robots"] = []
                d["_id"] = d["user_id"]
                result.append(d)
            return result

    async def save_game_profile(self, user_id: str, data: Dict[str, Any]):
        """Salva (upsert) perfil de gamificação."""
        now = datetime.utcnow().isoformat()
        unlocked = json.dumps(data.get("unlocked_robots", []))
        await self._connection.execute("""
            INSERT INTO game_profiles
                (user_id, trade_points, level, xp, unlocked_robots, bots_unlocked,
                 lifetime_profit, last_daily_chest_opened, streak_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                trade_points            = excluded.trade_points,
                level                   = excluded.level,
                xp                      = excluded.xp,
                unlocked_robots         = excluded.unlocked_robots,
                bots_unlocked           = excluded.bots_unlocked,
                lifetime_profit         = excluded.lifetime_profit,
                last_daily_chest_opened = excluded.last_daily_chest_opened,
                streak_count            = excluded.streak_count,
                updated_at              = excluded.updated_at
        """, (
            user_id,
            data.get("trade_points", 1000),
            data.get("level", 1),
            data.get("xp", 0),
            unlocked,
            data.get("bots_unlocked", len(data.get("unlocked_robots", []))),
            data.get("lifetime_profit", 0.0),
            data.get("last_daily_chest_opened"),
            data.get("streak_count", 0),
            data.get("created_at", now),
            now,
        ))
        await self._connection.commit()

    # ── strategy_manager_state ────────────────────────────────────────────────

    async def get_strategy_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Busca estado do strategy manager por user_id."""
        async with self._connection.execute(
            "SELECT state_json FROM strategy_manager_state WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                try:
                    state = json.loads(row[0] or "{}")
                    state["user_id"] = user_id
                    return state
                except Exception:
                    return {"user_id": user_id}
        return None

    async def save_strategy_state(self, user_id: str, patch: Dict[str, Any]):
        """Salva (upsert/merge) estado do strategy manager."""
        existing = await self.get_strategy_state(user_id) or {}
        existing.pop("user_id", None)
        existing.update({k: v for k, v in patch.items() if k != "user_id"})
        state_json = json.dumps(existing, default=str)
        now = datetime.utcnow().isoformat()
        await self._connection.execute("""
            INSERT INTO strategy_manager_state (user_id, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
        """, (user_id, state_json, now))
        await self._connection.commit()

    async def close(self):
        """Fecha a conex?o."""
        if self._connection:
            await self._connection.close()
            logger.info("SQLite desconectado")
    
    def _row_to_dict(self, row: aiosqlite.Row) -> Dict[str, Any]:
        """Converte uma row do SQLite para dicion?rio compat?vel com MongoDB."""
        data = dict(row)
        # Converter ID para formato MongoDB-like
        data["_id"] = data.pop("id")
        # Converter booleanos
        data["is_active"] = bool(data.get("is_active", 1))
        data["is_superuser"] = bool(data.get("is_superuser", 0))
        return data


# Inst?ncia global
_local_db: Optional[LocalUserDatabase] = None


async def get_local_user_db() -> LocalUserDatabase:
    """Obt?m a inst?ncia do banco de dados local."""
    global _local_db
    if _local_db is None:
        _local_db = LocalUserDatabase()
        await _local_db.connect()
    return _local_db


async def close_local_db():
    """Fecha o banco de dados local."""
    global _local_db
    if _local_db:
        await _local_db.close()
        _local_db = None
