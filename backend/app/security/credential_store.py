"""
Credential Store - Manages encrypted user exchange credentials in database.

Per-user, per-exchange credential storage with encryption.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from bson import ObjectId
import logging

from app.security.credential_encryption import get_credential_encryption, CredentialEncryptionError
from app.security.log_sanitizer import LogSanitizer

logger = logging.getLogger(__name__)


@dataclass
class StoredCredential:
    """Represents encrypted credential in database."""
    user_id: str
    exchange: str  # 'kucoin', 'binance', etc
    api_key_enc: str
    api_secret_enc: str
    passphrase_enc: str
    created_at: datetime
    updated_at: datetime
    algorithm: str = "fernet"
    _id: Optional[ObjectId] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to MongoDB document format."""
        return {
            "user_id": self.user_id,
            "exchange": self.exchange,
            "api_key_enc": self.api_key_enc,
            "api_secret_enc": self.api_secret_enc,
            "passphrase_enc": self.passphrase_enc,
            "algorithm": self.algorithm,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @staticmethod
    def from_dict(doc: Dict[str, Any]) -> "StoredCredential":
        """Create from MongoDB document."""
        return StoredCredential(
            user_id=doc.get("user_id"),
            exchange=doc.get("exchange"),
            api_key_enc=doc.get("api_key_enc"),
            api_secret_enc=doc.get("api_secret_enc"),
            passphrase_enc=doc.get("passphrase_enc"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            algorithm=doc.get("algorithm", "fernet"),
            _id=doc.get("_id"),
        )


class CredentialStore:
    """Manages encrypted credential storage and retrieval."""
    
    def __init__(self, db_collection):
        """
        Initialize credential store.
        
        Args:
            db_collection: MongoDB collection for storing credentials
                          (typically: db.user_exchange_credentials)
        """
        self.db = db_collection
        self.cipher = get_credential_encryption()
    
    async def store_credentials(
        self,
        user_id: str,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str,
    ) -> StoredCredential:
        """
        Store encrypted credentials for user.
        
        Args:
            user_id: User ID
            exchange: Exchange name ('kucoin', 'binance', etc)
            api_key: Public API key (encrypted anyway for extra security)
            api_secret: Secret key (MUST be encrypted)
            passphrase: API passphrase (MUST be encrypted)
            
        Returns:
            StoredCredential object
            
        Raises:
            CredentialEncryptionError: If encryption fails
            
        Example:
            >>> cred = await store.store_credentials(
            ...     user_id="user123",
            ...     exchange="kucoin",
            ...     api_key="63dcf...",
            ...     api_secret="secret123",
            ...     passphrase="pass123"
            ... )
        """
        now = datetime.utcnow()
        
        # Encrypt all fields
        encrypted = self.cipher.encrypt_credentials(api_key, api_secret, passphrase)
        
        stored = StoredCredential(
            user_id=user_id,
            exchange=exchange,
            api_key_enc=encrypted["api_key_enc"],
            api_secret_enc=encrypted["api_secret_enc"],
            passphrase_enc=encrypted["passphrase_enc"],
            algorithm=encrypted["algorithm"],
            created_at=now,
            updated_at=now,
        )
        
        # Insert or replace credential
        result = await self.db.update_one(
            {"user_id": user_id, "exchange": exchange},
            {
                "$set": stored.to_dict()
            },
            upsert=True
        )
        
        logger.info(
            f"✅ Credentials stored for user {user_id} exchange {exchange} "
            f"(upserted={result.upserted_id or result.modified_count > 0})"
        )
        
        return stored
    
    async def get_credentials(
        self,
        user_id: str,
        exchange: str
    ) -> Optional[Dict[str, str]]:
        """
        Retrieve and decrypt credentials for user.
        
        Args:
            user_id: User ID
            exchange: Exchange name
            
        Returns:
            Decrypted credentials dict: {"api_key": "...", "api_secret": "...", "passphrase": "..."}
            None if credentials not found
            
        Raises:
            CredentialEncryptionError: If decryption fails or data corrupted
            
        Example:
            >>> creds = await store.get_credentials("user123", "kucoin")
            >>> if creds:
            ...     client = KuCoinRawClient(**creds)
        """
        doc = await self.db.find_one({"user_id": user_id, "exchange": exchange})
        
        if not doc:
            logger.warning(f"Credentials not found for user {user_id} exchange {exchange}")
            return None
        
        try:
            stored = StoredCredential.from_dict(doc)
            decrypted = self.cipher.decrypt_credentials(
                stored.api_key_enc,
                stored.api_secret_enc,
                stored.passphrase_enc
            )
            
            logger.debug(f"✅ Credentials decrypted for user {user_id} exchange {exchange}")
            return decrypted
            
        except CredentialEncryptionError as e:
            logger.error(f"❌ Failed to decrypt credentials for {user_id}: {e}")
            raise
    
    async def delete_credentials(self, user_id: str, exchange: str) -> bool:
        """
        Delete stored credentials.
        
        Args:
            user_id: User ID
            exchange: Exchange name
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.db.delete_one({"user_id": user_id, "exchange": exchange})
        
        if result.deleted_count > 0:
            logger.info(f"✅ Credentials deleted for user {user_id} exchange {exchange}")
            return True
        else:
            logger.warning(f"Credentials not found for deletion: {user_id} {exchange}")
            return False
    
    async def list_user_exchanges(self, user_id: str) -> list[str]:
        """
        List all exchanges for which user has stored credentials.
        
        Args:
            user_id: User ID
            
        Returns:
            List of exchange names (e.g., ['kucoin', 'binance'])
        """
        docs = await self.db.find({"user_id": user_id}).to_list(length=None)
        exchanges = [doc.get("exchange") for doc in docs]
        logger.debug(f"User {user_id} has credentials for: {exchanges}")
        return exchanges
    
    async def has_credentials(self, user_id: str, exchange: str) -> bool:
        """
        Check if user has credentials for exchange.
        
        Args:
            user_id: User ID
            exchange: Exchange name
            
        Returns:
            True if credentials exist, False otherwise
        """
        doc = await self.db.find_one({"user_id": user_id, "exchange": exchange})
        return doc is not None


# Global instance
_store: Optional[CredentialStore] = None


def init_credential_store(db_collection) -> CredentialStore:
    """
    Initialize global credential store.
    
    Args:
        db_collection: MongoDB collection for credentials
        
    Returns:
        CredentialStore instance
    """
    global _store
    _store = CredentialStore(db_collection)
    logger.info("✅ Credential store initialized")
    return _store


def get_credential_store() -> CredentialStore:
    """
    Get global credential store instance.
    
    Returns:
        CredentialStore instance
        
    Raises:
        RuntimeError: If not initialized
    """
    global _store
    if _store is None:
        raise RuntimeError("Credential store not initialized. Call init_credential_store() first")
    return _store
