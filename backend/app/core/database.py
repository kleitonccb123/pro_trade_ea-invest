"""
MongoDB Database Configuration with Motor (Async Driver)

Supports:
1. MongoDB Atlas (mongodb+srv://) - Cloud hosted
2. Local MongoDB (mongodb://) - Development
3. Offline/Mock Mode - When no database is available

Para usar MongoDB Atlas em nuvem:
1. Crie uma conta em https://cloud.mongodb.com/
2. Crie um cluster
3. Copie a connection string (mongodb+srv://...)
4. Configure a vari?vel de ambiente DATABASE_URL
5. Adicione seu IP na whitelist do Atlas

Para usar localmente:
DATABASE_URL=mongodb://localhost:27017
"""

from __future__ import annotations

import os
import ssl
import certifi
import logging
from typing import Optional, Any, Dict, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Configurar logging para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flag para modo offline
_offline_mode: bool = False
_mock_data: Dict[str, List[Dict[str, Any]]] = {}

# Global MongoDB client (will be None in offline mode)
_mongodb_client: Optional[Any] = None
_mongodb_db: Optional[Any] = None


class MockCollection:
    """Mock collection for offline mode."""
    def __init__(self, name: str):
        self.name = name
        if name not in _mock_data:
            _mock_data[name] = []
    
    async def find_one(self, query: dict = None, sort=None) -> Optional[dict]:
        logger.info(f"? MOCK SEARCH in {self.name}: query={query}")
        data = list(_mock_data.get(self.name, []))
        if query:
            data = [item for item in data if self._match_query(item, query)]
        if sort:
            for field, direction in reversed(sort):
                data = sorted(data, key=lambda x: x.get(field, 0), reverse=(direction == -1))
        result = data[0] if data else None
        if result:
            logger.info(f"? MOCK FOUND match in {self.name}")
        else:
            logger.warning(f"? MOCK NOT FOUND in {self.name}")
        return result
    
    def find(self, query: dict = None):
        """Return a cursor (NOT a coroutine)."""
        return MockCursor(self.name, query)
    
    async def insert_one(self, document: dict):
        from bson import ObjectId
        doc = document.copy()
        if '_id' not in doc:
            doc['_id'] = ObjectId()
        if self.name not in _mock_data:
            _mock_data[self.name] = []
        _mock_data[self.name].append(doc)
        return type('InsertResult', (), {'inserted_id': doc['_id']})()

    async def find_one_and_update(
        self,
        query: dict,
        update: dict,
        upsert: bool = False,
        return_document: bool = False,
    ) -> Optional[dict]:
        """Find a document, update it, and return the updated document."""
        data = _mock_data.get(self.name, [])
        for item in data:
            if self._match_query(item, query):
                if '$set' in update:
                    item.update(update['$set'])
                if '$inc' in update:
                    for k, v in update['$inc'].items():
                        item[k] = item.get(k, 0) + v
                return item
        if upsert:
            new_doc = {**query}
            if '$set' in update:
                new_doc.update(update['$set'])
            if '$setOnInsert' in update:
                new_doc.update(update['$setOnInsert'])
            if self.name not in _mock_data:
                _mock_data[self.name] = []
            await self.insert_one(new_doc)
            return new_doc
        return None
    
    async def insert_many(self, documents: list):
        from bson import ObjectId
        if self.name not in _mock_data:
            _mock_data[self.name] = []
        ids = []
        for doc in documents:
            d = doc.copy()
            if '_id' not in d:
                d['_id'] = ObjectId()
            _mock_data[self.name].append(d)
            ids.append(d['_id'])
        return type('InsertResult', (), {'inserted_ids': ids})()
    
    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        data = _mock_data.get(self.name, [])
        for i, item in enumerate(data):
            if self._match_query(item, query):
                if '$set' in update:
                    item.update(update['$set'])
                if '$inc' in update:
                    for k, v in update['$inc'].items():
                        item[k] = item.get(k, 0) + v
                return type('UpdateResult', (), {'modified_count': 1, 'matched_count': 1})()
        if upsert:
            await self.insert_one({**query, **update.get('$set', {})})
            return type('UpdateResult', (), {'modified_count': 0, 'matched_count': 0, 'upserted_id': True})()
        return type('UpdateResult', (), {'modified_count': 0, 'matched_count': 0})()
    
    async def update_many(self, query: dict, update: dict):
        data = _mock_data.get(self.name, [])
        count = 0
        for item in data:
            if self._match_query(item, query):
                if '$set' in update:
                    item.update(update['$set'])
                if '$inc' in update:
                    for k, v in update['$inc'].items():
                        item[k] = item.get(k, 0) + v
                count += 1
        return type('UpdateResult', (), {'modified_count': count, 'matched_count': count})()
    
    async def delete_one(self, query: dict):
        data = _mock_data.get(self.name, [])
        for i, item in enumerate(data):
            if self._match_query(item, query):
                data.pop(i)
                return type('DeleteResult', (), {'deleted_count': 1})()
        return type('DeleteResult', (), {'deleted_count': 0})()
    
    async def delete_many(self, query: dict):
        data = _mock_data.get(self.name, [])
        original_len = len(data)
        _mock_data[self.name] = [item for item in data if not self._match_query(item, query)]
        deleted = original_len - len(_mock_data[self.name])
        return type('DeleteResult', (), {'deleted_count': deleted})()
    
    async def count_documents(self, query: dict = None) -> int:
        if not query:
            return len(_mock_data.get(self.name, []))
        return sum(1 for item in _mock_data.get(self.name, []) 
                   if self._match_query(item, query))
    
    async def create_index(self, *args, **kwargs):
        pass  # No-op in mock mode
    
    async def aggregate(self, pipeline: list):
        """Simple aggregation support."""
        return MockCursor(self.name, {})
    
    def _match_query(self, item: dict, query: dict) -> bool:
        """Match an item against a MongoDB-style query."""
        if not query:
            return True
        
        for key, value in query.items():
            # Handle special operators
            if key == '$or':
                if not any(self._match_query(item, cond) for cond in value):
                    return False
            elif key == '$and':
                if not all(self._match_query(item, cond) for cond in value):
                    return False
            elif isinstance(value, dict):
                # Handle operators like $lt, $gt, $in, etc.
                item_value = item.get(key)
                for op, op_value in value.items():
                    if op == '$lt':
                        if not (item_value is not None and item_value < op_value):
                            return False
                    elif op == '$lte':
                        if not (item_value is not None and item_value <= op_value):
                            return False
                    elif op == '$gt':
                        if not (item_value is not None and item_value > op_value):
                            return False
                    elif op == '$gte':
                        if not (item_value is not None and item_value >= op_value):
                            return False
                    elif op == '$in':
                        if item_value not in op_value:
                            return False
                    elif op == '$ne':
                        if item_value == op_value:
                            return False
                    elif op == '$exists':
                        if op_value and key not in item:
                            return False
                        if not op_value and key in item:
                            return False
            else:
                # Simple equality
                if item.get(key) != value:
                    return False
        
        return True


class MockCursor:
    """Mock cursor for offline mode."""
    def __init__(self, collection_name: str, query: dict = None):
        self.collection_name = collection_name
        self.query = query or {}
        self._data = None
        self._skip = 0
        self._limit = None
        self._sort = None
    
    def skip(self, n: int):
        self._skip = n
        return self
    
    def limit(self, n: int):
        self._limit = n
        return self
    
    def sort(self, key_or_list, direction=None):
        self._sort = (key_or_list, direction)
        return self
    
    def _match_query(self, item: dict, query: dict) -> bool:
        """Match an item against a MongoDB-style query."""
        if not query:
            return True
        
        for key, value in query.items():
            if key == '$or':
                if not any(self._match_query(item, cond) for cond in value):
                    return False
            elif key == '$and':
                if not all(self._match_query(item, cond) for cond in value):
                    return False
            elif isinstance(value, dict):
                item_value = item.get(key)
                for op, op_value in value.items():
                    if op == '$lt' and not (item_value is not None and item_value < op_value):
                        return False
                    elif op == '$lte' and not (item_value is not None and item_value <= op_value):
                        return False
                    elif op == '$gt' and not (item_value is not None and item_value > op_value):
                        return False
                    elif op == '$gte' and not (item_value is not None and item_value >= op_value):
                        return False
                    elif op == '$in' and item_value not in op_value:
                        return False
                    elif op == '$ne' and item_value == op_value:
                        return False
            else:
                if item.get(key) != value:
                    return False
        return True
    
    async def to_list(self, length: int = None) -> list:
        data = _mock_data.get(self.collection_name, [])
        
        # Apply query filter
        if self.query:
            data = [item for item in data if self._match_query(item, self.query)]
        
        # Apply skip
        data = data[self._skip:]
        
        # Apply limit
        if self._limit:
            data = data[:self._limit]
        if length:
            data = data[:length]
        
        return data
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self._data is None:
            self._data = await self.to_list()
            self._index = 0
        
        if self._index >= len(self._data):
            raise StopAsyncIteration
        
        item = self._data[self._index]
        self._index += 1
        return item


class MockDatabase:
    """Mock database for offline mode."""
    def __init__(self, name: str):
        self.name = name
        self._collections = {}
    
    def __getitem__(self, name: str) -> MockCollection:
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]
    
    def __getattr__(self, name: str) -> MockCollection:
        return self[name]


class SQLiteUserCollection:
    """Wrapper para usar SQLite como collection de usu?rios."""
    
    def __init__(self, local_db):
        self.local_db = local_db
        self.name = "users"
    
    async def find_one(self, query: dict = None) -> Optional[dict]:
        """Busca um usu?rio."""
        if not query:
            users = await self.local_db.list_users(limit=1)
            return users[0] if users else None
        
        # Busca por email
        if "email" in query:
            return await self.local_db.find_user_by_email(query["email"])
        
        # Busca por google_id
        if "google_id" in query:
            return await self.local_db.find_user_by_google_id(query["google_id"])
        
        # Busca por _id
        if "_id" in query:
            return await self.local_db.find_user_by_id(str(query["_id"]))
        
        return None
    
    def find(self, query: dict = None):
        """Retorna cursor para listagem."""
        return SQLiteUserCursor(self.local_db, query)
    
    async def insert_one(self, document: dict):
        """Insere um novo usu?rio."""
        user = await self.local_db.create_user(document)
        return type('InsertResult', (), {'inserted_id': user["_id"]})()
    
    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        """Atualiza um usu?rio."""
        user = await self.find_one(query)
        if user:
            updates = update.get('$set', {})
            await self.local_db.update_user(user["_id"], updates)
            return type('UpdateResult', (), {'modified_count': 1, 'matched_count': 1})()
        return type('UpdateResult', (), {'modified_count': 0, 'matched_count': 0})()
    
    async def count_documents(self, query: dict = None) -> int:
        """Conta usu?rios."""
        users = await self.local_db.list_users()
        return len(users)
    
    async def create_index(self, *args, **kwargs):
        """No-op - SQLite j? tem ?ndices."""
        pass


class SQLiteUserCursor:
    """Cursor para listagem de usu?rios do SQLite."""
    
    def __init__(self, local_db, query: dict = None):
        self.local_db = local_db
        self.query = query or {}
        self._data = None
        self._index = 0
    
    def skip(self, n: int):
        return self
    
    def limit(self, n: int):
        return self
    
    def sort(self, key_or_list, direction=None):
        return self
    
    async def to_list(self, length: int = None) -> list:
        users = await self.local_db.list_users(limit=length or 100)
        return users
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self._data is None:
            self._data = await self.to_list()
        
        if self._index >= len(self._data):
            raise StopAsyncIteration
        
        item = self._data[self._index]
        self._index += 1
        return item


class SQLiteGameProfileCollection:
    """SQLite wrapper para a collection game_profiles."""

    def __init__(self, local_db):
        self.local_db = local_db
        self.name = "game_profiles"

    async def find_one(self, query: dict = None) -> Optional[dict]:
        if not query:
            return None
        if "user_id" in query:
            return await self.local_db.get_game_profile(str(query["user_id"]))
        return None

    def find(self, query: dict = None):
        return MockCursor("game_profiles", query)

    async def insert_one(self, document: dict):
        user_id = document.get("user_id")
        await self.local_db.save_game_profile(user_id, document)
        logger.info(f"✅ [SQLite] game_profile criado para user_id={user_id}")
        return type('InsertResult', (), {'inserted_id': user_id})()

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        user_id = str(query.get("user_id", ""))
        existing = await self.local_db.get_game_profile(user_id)

        if not existing:
            if not upsert:
                return type('UpdateResult', (), {'modified_count': 0, 'matched_count': 0})()
            existing = {
                "user_id": user_id, "trade_points": 1000, "level": 1, "xp": 0,
                "unlocked_robots": [], "bots_unlocked": 0, "lifetime_profit": 0.0,
                "streak_count": 0,
            }

        # Apply $set
        if "$set" in update:
            for k, v in update["$set"].items():
                existing[k] = v

        # Apply $inc
        if "$inc" in update:
            for k, v in update["$inc"].items():
                existing[k] = existing.get(k, 0) + v

        # Apply $addToSet
        if "$addToSet" in update:
            for k, v in update["$addToSet"].items():
                lst = existing.get(k, [])
                if isinstance(lst, list) and v not in lst:
                    lst.append(v)
                existing[k] = lst

        await self.local_db.save_game_profile(user_id, existing)
        return type('UpdateResult', (), {'modified_count': 1, 'matched_count': 1})()

    async def count_documents(self, query: dict = None) -> int:
        return 0

    async def create_index(self, *args, **kwargs):
        pass

    def aggregate(self, pipeline: list):
        """Suporte básico a aggregate para leaderboard: $sort, $limit, $project."""
        local_db = self.local_db

        class AggCursor:
            def __init__(self, ldb, pipe):
                self._ldb = ldb
                self._pipe = pipe

            async def to_list(self, length=None):
                docs = await self._ldb.get_all_game_profiles()
                for stage in self._pipe:
                    if "$sort" in stage:
                        for field, direction in reversed(list(stage["$sort"].items())):
                            docs.sort(key=lambda d: d.get(field, 0), reverse=(direction == -1))
                    elif "$limit" in stage:
                        docs = docs[:stage["$limit"]]
                    elif "$project" in stage:
                        keep = {k for k, v in stage["$project"].items() if v and k != "_id"}
                        docs = [{k: d[k] for k in keep if k in d} for d in docs]
                if length is not None:
                    docs = docs[:length]
                return docs

        return AggCursor(local_db, pipeline)


class SQLiteStrategyManagerStateCollection:
    """SQLite wrapper para a collection strategy_manager_state."""

    def __init__(self, local_db):
        self.local_db = local_db
        self.name = "strategy_manager_state"

    async def find_one(self, query: dict = None) -> Optional[dict]:
        if not query:
            return None
        if "user_id" in query:
            return await self.local_db.get_strategy_state(str(query["user_id"]))
        return None

    def find(self, query: dict = None):
        return MockCursor("strategy_manager_state", query)

    async def insert_one(self, document: dict):
        user_id = document.get("user_id", "")
        await self.local_db.save_strategy_state(user_id, document)
        return type('InsertResult', (), {'inserted_id': user_id})()

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        user_id = str(query.get("user_id", ""))
        if "$set" in update:
            await self.local_db.save_strategy_state(user_id, update["$set"])
        return type('UpdateResult', (), {'modified_count': 1, 'matched_count': 1})()

    async def count_documents(self, query: dict = None) -> int:
        return 0

    async def create_index(self, *args, **kwargs):
        pass


class MockDatabaseWithSQLite:
    """Mock database que usa SQLite para users, game_profiles, strategy_manager_state e mock para outros."""

    def __init__(self, name: str, local_db):
        self.name = name
        self.local_db = local_db
        self._collections = {}
        # Collections com persistência SQLite
        self._collections["users"] = SQLiteUserCollection(local_db)
        self._collections["game_profiles"] = SQLiteGameProfileCollection(local_db)
        self._collections["strategy_manager_state"] = SQLiteStrategyManagerStateCollection(local_db)

    def __getitem__(self, name: str):
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]

    def __getattr__(self, name: str):
        return self[name]


def _clean_mongodb_uri(uri: str) -> str:
    """
    Remove conflicting TLS options from MongoDB URI.
    Returns a clean URI suitable for programmatic TLS configuration.
    """
    # Parse the URI
    parsed = urlparse(uri)
    
    # Parse query parameters
    query_params = parse_qs(parsed.query)
    
    # Remove TLS-related parameters (we'll set them programmatically)
    tls_params_to_remove = [
        'tls', 'ssl', 'tlsAllowInvalidCertificates', 'tlsInsecure',
        'tlsCAFile', 'tlsCertificateKeyFile', 'sslAllowInvalidCertificates'
    ]
    
    for param in tls_params_to_remove:
        query_params.pop(param, None)
    
    # Rebuild query string (parse_qs returns lists, so flatten)
    clean_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
    new_query = urlencode(clean_params, doseq=True)
    
    # Rebuild URI
    clean_uri = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    return clean_uri


async def connect_db() -> None:
    """Connect to MongoDB on startup. Falls back to offline mode if connection fails."""
    global _mongodb_client, _mongodb_db, _offline_mode
    
    # Import settings here to avoid circular imports
    from app.core.config import settings
    
    # Check for OFFLINE_MODE environment variable (priority: env variable > settings)
    offline_mode_env = os.environ.get('OFFLINE_MODE', '').lower()
    if offline_mode_env in ('true', '1', 'yes'):
        logger.warning("??  MODO OFFLINE ativado via vari?vel de ambiente OFFLINE_MODE=true")
        _enable_offline_mode()
        return
    
    # Get database configuration
    db_url = os.environ.get('DATABASE_URL') or settings.database_url
    db_name = os.environ.get('DATABASE_NAME') or settings.database_name
    
    logger.info(f"[*] DATABASE_URL configurada: {db_url[:50]}..." if db_url else "[*] DATABASE_URL n?o configurada")
    logger.info(f"[*] DATABASE_NAME: {db_name}")
    
    # If no valid URL, use offline mode
    if not db_url:
        logger.warning("[!] Nenhuma DATABASE_URL configurada - usando modo OFFLINE")
        _enable_offline_mode()
        return
    
    # Clean URI from conflicting TLS params
    clean_url = _clean_mongodb_uri(db_url)
    
    # Determine if using Atlas (mongodb+srv) or local
    is_atlas = clean_url.startswith("mongodb+srv://")
    
    try:
        # Import motor here (may fail if not installed properly)
        from motor.motor_asyncio import AsyncIOMotorClient
        
        # Build connection options
        connection_options = {
            "serverSelectionTimeoutMS": 3000,  # Reduzido drasticamente para fallback r?pido
            "connectTimeoutMS": 3000,
            "socketTimeoutMS": 3000,
            "retryWrites": True,
            "retryReads": True,
            "maxPoolSize": 10,
            "minPoolSize": 1,
        }
        
        if is_atlas:
            # For MongoDB Atlas: Use TLS with certifi certificates
            _is_dev = os.getenv("APP_MODE", "dev") != "prod"
            connection_options["tls"] = True
            connection_options["tlsCAFile"] = certifi.where()
            # Only bypass certificate checks in development — NEVER in production
            connection_options["tlsAllowInvalidCertificates"] = _is_dev
            connection_options["tlsAllowInvalidHostnames"] = _is_dev
            
            logger.info("[*] Tentando conex?o com MongoDB Atlas...")
        else:
            logger.info("[*] Usando conex?o local MongoDB (sem TLS)")
        
        _mongodb_client = AsyncIOMotorClient(clean_url, **connection_options)
        _mongodb_db = _mongodb_client[db_name]
        
        # Test connection with timeout
        logger.info("[*] Testando conexão...")
        await _mongodb_client.admin.command('ping')
        
        logger.info(f"[OK] Connected to MongoDB successfully!")
        logger.info(f"[OK] Database: {db_name}")
        _offline_mode = False
        
        # Initialize indexes
        await init_db()
        
    except Exception as e:
        logger.error(f"[-] Erro ao conectar ao MongoDB: {e}")
        logger.critical("=" * 80)
        logger.critical("🚨 MONGODB CONNECTION FAILED")
        logger.critical("=" * 80)
        logger.critical(f"DATABASE_URL: {db_url[:60]}...")
        logger.critical(f"Error: {str(e)[:200]}")
        logger.critical("Possible causes:")
        logger.critical("  1. SSL/TLS certificate validation failed (certifi issue)")
        logger.critical("  2. Network timeout (MongoDB Atlas unreachable)")
        logger.critical("  3. Invalid credentials in connection string")
        logger.critical("  4. IP not whitelisted in MongoDB Atlas")
        logger.critical("=" * 80)
        logger.warning("[!] Ativando modo OFFLINE com SQLite local")
        await _enable_offline_mode_with_sqlite()


async def _enable_offline_mode_with_sqlite():
    """Enable offline mode with SQLite for data persistence."""
    global _mongodb_client, _mongodb_db, _offline_mode
    
    _offline_mode = True
    _mongodb_client = None
    
    # Usar SQLite para persistência local
    try:
        from app.core.local_db import get_local_user_db
        local_db = await get_local_user_db()
        
        # Criar wrapper que usa SQLite para users e mock para outros
        _mongodb_db = MockDatabaseWithSQLite("crypto_trade_hub", local_db)
        
        # ⚠️ CRITICAL LOGGING - Database fallback detected
        logger.critical("=" * 80)
        logger.critical("🚨 MONGODB CONNECTION FAILED - FALLBACK TO SQLITE ACTIVE")
        logger.critical("=" * 80)
        logger.critical("ISSUE: MongoDB Atlas did not respond. Certificate/SSL validation failed.")
        logger.critical("STATUS: Using SQLite local database for persistence")
        logger.critical("PATH: backend/data/local_users.db")
        logger.critical("IMPACT: Application is running in degraded mode")
        logger.critical("ACTION: Check MongoDB Atlas configuration:")
        logger.critical("  1. Verify DATABASE_URL environment variable")
        logger.critical("  2. Check IP whitelist in MongoDB Atlas console") 
        logger.critical("  3. Verify certificates with: python -m certifi")
        logger.critical("  4. Test connection: python -c 'import certifi; print(certifi.where())'")
        logger.critical("=" * 80)
        
        # 🚨 SEND ALERT TO DISCORD/SLACK
        try:
            from app.services.error_notifier import ErrorNotifier, ErrorAlert, AlertSeverity
            notifier = ErrorNotifier()
            
            alert = ErrorAlert(
                severity=AlertSeverity.CRITICAL,
                title="🚨 MongoDB Fallback Triggered",
                message="MongoDB Atlas connection failed. Application switched to SQLite local database.",
                tags={
                    "database": "mongodb_fallback",
                    "mode": "degraded",
                    "status": "requires_investigation"
                }
            )
            
            # Send async (don't block initialization)
            import asyncio
            try:
                asyncio.create_task(notifier.send_to_all(alert))
            except:
                # Fallback if asyncio not available during init
                pass
        except Exception as alert_error:
            logger.error(f"[✗] Failed to send MongoDB fallback alert: {alert_error}")
        
        logger.info("? MODO LOCAL ATIVO - Usando SQLite para persistência")
        logger.info("? Os dados de usuários são salvos em: backend/data/local_users.db")
        logger.info("? Credenciais: demo@tradehub.com / demo123")
        
    except Exception as e:
        logger.error(f"Erro ao inicializar SQLite: {e}")
        # Fallback para modo em memória
        _mongodb_db = MockDatabase("crypto_trade_hub")
        _init_mock_data()
        
        # ⚠️ CRITICAL LOGGING - MongoDB AND SQLite failed
        logger.critical("=" * 80)
        logger.critical("🚨 CRITICAL ERROR - BOTH MONGODB AND SQLITE FAILED")
        logger.critical("=" * 80)
        logger.critical(f"SQLite initialization error: {e}")
        logger.critical("STATUS: Using in-memory mock database (data will be lost on restart)")
        logger.critical("=" * 80)
        
        logger.info("=" * 70)
        logger.info("⚠️  MODO OFFLINE ATIVO - Usando dados em memória")
        logger.info("⚠️  Os dados serão perdidos ao reiniciar o servidor")
        logger.info("=" * 70)


def _enable_offline_mode():
    """Enable offline/mock mode when MongoDB is not available (sync version)."""
    global _mongodb_client, _mongodb_db, _offline_mode
    
    _offline_mode = True
    _mongodb_client = None
    _mongodb_db = MockDatabase("crypto_trade_hub")
    
    # Initialize with demo data
    _init_mock_data()
    
    logger.info("=" * 70)
    logger.info("??  MODO OFFLINE ATIVO - Usando dados em mem?ria")
    logger.info("??  Os dados ser?o perdidos ao reiniciar o servidor")
    logger.info("??  Para usar MongoDB Atlas, configure:")
    logger.info("    ? OFFLINE_MODE=false")
    logger.info("    ? DATABASE_URL=mongodb+srv://user:pass@cluster...") 
    logger.info("    ? DATABASE_NAME=seu_banco")
    logger.info("=" * 70)


def _init_mock_data():
    """Initialize mock data for offline mode."""
    from datetime import datetime
    from bson import ObjectId
    from app.core.security import get_password_hash
    
    # Generate correct hash using SHA256+bcrypt (same as security.py)
    # This ensures passwords work with verify_password()
    demo_password_hash = get_password_hash("demo123")
    logger.info(f"[*] Generated demo password hash: {demo_password_hash[:30]}...")
    
    # Demo users - password is "demo123" for all
    _mock_data['users'] = [
        {
            '_id': ObjectId(),
            'email': 'demo@cryptotrade.com',
            'username': 'demo',
            'name': 'Demo User',
            'hashed_password': demo_password_hash,
            'full_name': 'Demo User',
            'created_at': datetime.utcnow(),
            'is_active': True,
            'is_superuser': False,
            'auth_provider': 'local',
        },
        {
            '_id': ObjectId(),
            'email': 'demo@tradehub.com',
            'username': 'demo2',
            'name': 'Demo TradeHub',
            'hashed_password': demo_password_hash,
            'full_name': 'Demo TradeHub',
            'created_at': datetime.utcnow(),
            'is_active': True,
            'is_superuser': False,
            'auth_provider': 'local',
        },
        {
            '_id': ObjectId(),
            'email': 'admin@cryptotrade.com',
            'username': 'admin',
            'name': 'Admin',
            'hashed_password': demo_password_hash,
            'full_name': 'Administrator',
            'created_at': datetime.utcnow(),
            'is_active': True,
            'is_superuser': True,
            'auth_provider': 'local',
        }
    ]
    
    # Demo bots
    _mock_data['bots'] = [
        {
            '_id': ObjectId(),
            'name': 'CryptoBot Pro',
            'status': 'active',
            'pair': 'BTC/USDT',
            'profit': 12.5,
            'trades': 150,
            'created_at': datetime.utcnow(),
        },
        {
            '_id': ObjectId(),
            'name': 'ETH Trader',
            'status': 'paused',
            'pair': 'ETH/USDT',
            'profit': 8.3,
            'trades': 89,
            'created_at': datetime.utcnow(),
        }
    ]
    
    # Demo strategies
    _mock_data['strategies'] = [
        {
            '_id': ObjectId(),
            'name': 'Momentum Strategy',
            'description': 'Follows market momentum with RSI indicators',
            'type': 'momentum',
            'risk_level': 'medium',
            'created_at': datetime.utcnow(),
        },
        {
            '_id': ObjectId(),
            'name': 'Grid Trading',
            'description': 'Places buy/sell orders at intervals',
            'type': 'grid',
            'risk_level': 'low',
            'created_at': datetime.utcnow(),
        }
    ]
    
    logger.info("[+] Dados de demonstra??o inicializados")


async def disconnect_db() -> None:
    """Disconnect from MongoDB on shutdown."""
    global _mongodb_client
    
    if _mongodb_client:
        _mongodb_client.close()
        logger.info("[-] Desconectado do MongoDB")


def get_db():
    """Get MongoDB database instance (works in both online and offline mode)."""
    global _mongodb_db
    if _mongodb_db is None:
        # Auto-enable offline mode if not connected
        logger.warning("[!] Database not connected, enabling offline mode")
        _enable_offline_mode()
    return _mongodb_db


async def get_database():
    """
    Async alias for get_db() - for compatibility with async routes.
    Returns the MongoDB database instance.
    """
    return get_db()


async def get_db_async():
    """
    Async version of get_db for repository pattern.
    Returns the MongoDB database instance.
    """
    return get_db()


def is_offline_mode() -> bool:
    """Check if running in offline mode."""
    return _offline_mode


async def init_db() -> None:
    """Initialize database collections and indexes."""
    if _offline_mode:
        logger.info("[*] Modo offline - pulando cria??o de ?ndices MongoDB")
        return
    
    # Only import these for real MongoDB
    from pymongo import ASCENDING, DESCENDING
    
    db = get_db()
    
    try:
        # Create indexes for users collection
        users_col = db['users']
        await users_col.create_index('email', unique=True)
        
        # Create indexes for bots collection
        bots_col = db['bots']
        await bots_col.create_index('name')
        await bots_col.create_index('user_id')
        
        # Create indexes for bot_instances collection
        instances_col = db['bot_instances']
        await instances_col.create_index('bot_id')
        await instances_col.create_index('state')
        await instances_col.create_index('user_id')
        
        # Create indexes for simulated_trades collection
        trades_col = db['simulated_trades']
        await trades_col.create_index('instance_id')
        # TTL: Auto-delete trades ap?s 30 dias (2592000 segundos) - economiza espa?o no M0
        try:
            await trades_col.drop_index('timestamp_1')  # Remove ?ndice antigo se existir
        except Exception:
            pass  # ?ndice n?o existe, ok
        await trades_col.create_index('timestamp', expireAfterSeconds=2592000, name='ttl_30_days')
        
        # Create indexes for user_strategies collection
        strategies_col = db['user_strategies']
        await strategies_col.create_index([('user_id', ASCENDING), ('status', ASCENDING)])
        await strategies_col.create_index([('user_id', ASCENDING), ('created_at', DESCENDING)])
        await strategies_col.create_index('expires_at', expireAfterSeconds=0)  # TTL index
        
        # Create indexes for strategy_bot_instances collection
        strategy_instances_col = db['strategy_bot_instances']
        await strategy_instances_col.create_index('strategy_id')
        
        # Create indexes for strategy_trades collection
        strategy_trades_col = db['strategy_trades']
        await strategy_trades_col.create_index([('strategy_id', ASCENDING), ('entry_time', DESCENDING)])
        
        # Create indexes for notifications collection
        notifications_col = db['notifications']
        await notifications_col.create_index('user_id')
        await notifications_col.create_index('is_read')
        await notifications_col.create_index('read_at', expireAfterSeconds=604800, name='ttl_read_7_days', sparse=True)
        await notifications_col.create_index('created_at', expireAfterSeconds=2592000, name='ttl_all_30_days')
        
        # Create indexes for price_alerts collection
        alerts_col = db['price_alerts']
        await alerts_col.create_index('user_id')
        await alerts_col.create_index('symbol')
        await alerts_col.create_index('is_active')
        
        # Analytics Cache
        analytics_cache_col = db['analytics_cache']
        await analytics_cache_col.create_index('user_id', unique=True)
        await analytics_cache_col.create_index('updated_at', expireAfterSeconds=600, name='ttl_cache_10_min')
        
        # Error Logs
        error_logs_col = db['error_logs']
        await error_logs_col.create_index('level')
        await error_logs_col.create_index('created_at', expireAfterSeconds=172800, name='ttl_errors_48h')
        
        # Strategy Trades TTL
        strategy_trades_col_ttl = db['strategy_trades']
        await strategy_trades_col_ttl.create_index('exit_time', expireAfterSeconds=5184000, name='ttl_60_days', sparse=True)
        
        logger.info("[OK] MongoDB indexes created successfully!")
    except Exception as e:
        logger.warning(f"[!] Erro ao criar ?ndices: {e}")


async def get_session():
    """Get database session (for compatibility with old code)."""
    return get_db()


async def get_collection(collection_name: str):
    """Get a collection from the database."""
    db = get_db()
    return db[collection_name]
