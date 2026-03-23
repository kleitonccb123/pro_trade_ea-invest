"""
Exchange Credentials Repository - MongoDB Implementation

This module provides secure storage for exchange API credentials.
All credentials are encrypted using Fernet before storage.

Collections:
- exchange_credentials: Encrypted API credentials per user/exchange

Security:
- API keys, secrets, and passphrases are ALWAYS encrypted
- Never store or log plain-text credentials
- Use encryption_service from app.core.encryption

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from enum import Enum

from app.core.database import get_db
from app.core.encryption import (
    encrypt_credential,
    decrypt_credential,
    encrypt_kucoin_credentials,
    decrypt_kucoin_credentials,
)

logger = logging.getLogger(__name__)


class ExchangeType(str, Enum):
    """Supported exchange types."""
    BINANCE = "binance"
    KUCOIN = "kucoin"
    BYBIT = "bybit"


class CredentialsRepository:
    """
    Repository for Exchange Credentials in MongoDB.
    
    All credentials are encrypted before storage using Fernet encryption.
    This ensures that even if the database is compromised, API keys remain safe.
    """
    
    COLLECTION_NAME = "exchange_credentials"
    
    @classmethod
    def _get_collection(cls):
        """Get the credentials collection."""
        db = get_db()
        return db[cls.COLLECTION_NAME]
    
    # ==================== CREATE/UPDATE ====================
    
    @classmethod
    async def save_credentials(
        cls,
        user_id: str | ObjectId,
        exchange: str | ExchangeType,
        api_key: str,
        api_secret: str,
        passphrase: str = None,
        is_testnet: bool = True,
        label: str = None,
        **extra_fields
    ) -> Dict[str, Any]:
        """
        Save exchange credentials for a user.
        
        If credentials already exist for this user/exchange combo,
        they will be updated. Otherwise, new credentials are created.
        
        IMPORTANT: Credentials are encrypted before storage!
        
        Args:
            user_id: User's ObjectId
            exchange: Exchange name (binance, kucoin, etc.)
            api_key: Plain text API key (will be encrypted)
            api_secret: Plain text API secret (will be encrypted)
            passphrase: Plain text passphrase for KuCoin (will be encrypted)
            is_testnet: Whether using testnet/sandbox mode
            label: Optional label for this credential set
            extra_fields: Additional fields to store
            
        Returns:
            Created/updated credentials document (without decrypted values)
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        exchange = exchange.lower()
        
        # Encrypt all sensitive fields
        encrypted_key = encrypt_credential(api_key)
        encrypted_secret = encrypt_credential(api_secret)
        encrypted_passphrase = encrypt_credential(passphrase) if passphrase else None
        
        now = datetime.utcnow()
        
        # Check if credentials already exist
        existing = await collection.find_one({
            "user_id": user_id,
            "exchange": exchange
        })
        
        cred_doc = {
            "user_id": user_id,
            "exchange": exchange,
            "api_key_encrypted": encrypted_key,
            "api_secret_encrypted": encrypted_secret,
            "passphrase_encrypted": encrypted_passphrase,
            "is_testnet": is_testnet,
            "label": label or f"{exchange.capitalize()} API",
            "is_active": True,
            "updated_at": now,
            # Store partial key for display (first 4 and last 4 chars)
            "api_key_partial": f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****",
            **extra_fields
        }
        
        if existing:
            # Update existing
            result = await collection.find_one_and_update(
                {"_id": existing["_id"]},
                {"$set": cred_doc},
                return_document=True
            )
            logger.info(f"? Updated {exchange} credentials for user {user_id}")
            return result
        else:
            # Create new
            cred_doc["created_at"] = now
            result = await collection.insert_one(cred_doc)
            cred_doc["_id"] = result.inserted_id
            logger.info(f"? Created {exchange} credentials for user {user_id}")
            return cred_doc
    
    @classmethod
    async def save_kucoin_credentials(
        cls,
        user_id: str | ObjectId,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        is_sandbox: bool = True,
        label: str = None
    ) -> Dict[str, Any]:
        """
        Convenience method for saving KuCoin credentials.
        
        KuCoin requires a passphrase in addition to API key/secret.
        """
        return await cls.save_credentials(
            user_id=user_id,
            exchange=ExchangeType.KUCOIN,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=api_passphrase,
            is_testnet=is_sandbox,
            label=label
        )
    
    @classmethod
    async def save_binance_credentials(
        cls,
        user_id: str | ObjectId,
        api_key: str,
        api_secret: str,
        is_testnet: bool = True,
        label: str = None
    ) -> Dict[str, Any]:
        """
        Convenience method for saving Binance credentials.
        """
        return await cls.save_credentials(
            user_id=user_id,
            exchange=ExchangeType.BINANCE,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=None,
            is_testnet=is_testnet,
            label=label
        )
    
    # ==================== READ ====================
    
    @classmethod
    async def get_credentials(
        cls,
        user_id: str | ObjectId,
        exchange: str | ExchangeType,
        decrypt: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get credentials for a user and exchange.
        
        Args:
            user_id: User's ObjectId
            exchange: Exchange name
            decrypt: If True, decrypt the credentials before returning
            
        Returns:
            Credentials document with decrypted values (if decrypt=True)
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        cred = await collection.find_one({
            "user_id": user_id,
            "exchange": exchange.lower(),
            "is_active": True
        })
        
        if not cred:
            return None
        
        if decrypt:
            # Decrypt sensitive fields
            try:
                cred["api_key"] = decrypt_credential(cred.get("api_key_encrypted", ""))
                cred["api_secret"] = decrypt_credential(cred.get("api_secret_encrypted", ""))
                if cred.get("passphrase_encrypted"):
                    cred["passphrase"] = decrypt_credential(cred["passphrase_encrypted"])
            except Exception as e:
                logger.error(f"? Failed to decrypt credentials: {e}")
                return None
        
        return cred
    
    @classmethod
    async def get_kucoin_credentials(
        cls,
        user_id: str | ObjectId,
        decrypt: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get KuCoin credentials for a user."""
        return await cls.get_credentials(user_id, ExchangeType.KUCOIN, decrypt)
    
    @classmethod
    async def get_binance_credentials(
        cls,
        user_id: str | ObjectId,
        decrypt: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get Binance credentials for a user."""
        return await cls.get_credentials(user_id, ExchangeType.BINANCE, decrypt)
    
    @classmethod
    async def get_user_credentials(
        cls,
        user_id: str | ObjectId,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all credentials for a user (without decrypting).
        
        Returns summary info only - no decrypted keys!
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        query = {"user_id": user_id}
        if not include_inactive:
            query["is_active"] = True
        
        cursor = collection.find(query)
        credentials = await cursor.to_list(length=100)
        
        # Remove encrypted fields for safety - only return metadata
        result = []
        for cred in credentials:
            result.append({
                "_id": cred["_id"],
                "exchange": cred["exchange"],
                "label": cred.get("label"),
                "api_key_partial": cred.get("api_key_partial", "****"),
                "is_testnet": cred.get("is_testnet", True),
                "is_active": cred.get("is_active", True),
                "created_at": cred.get("created_at"),
                "updated_at": cred.get("updated_at"),
            })
        
        return result
    
    @classmethod
    async def has_credentials(
        cls,
        user_id: str | ObjectId,
        exchange: str | ExchangeType
    ) -> bool:
        """Check if user has credentials for an exchange."""
        cred = await cls.get_credentials(user_id, exchange, decrypt=False)
        return cred is not None
    
    # ==================== DELETE ====================
    
    @classmethod
    async def delete_credentials(
        cls,
        user_id: str | ObjectId,
        exchange: str | ExchangeType
    ) -> bool:
        """
        Delete credentials for a user and exchange.
        
        Actually performs a soft delete (sets is_active=False).
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        result = await collection.update_one(
            {"user_id": user_id, "exchange": exchange.lower()},
            {"$set": {"is_active": False, "deleted_at": datetime.utcnow()}}
        )
        
        if result.modified_count > 0:
            logger.info(f"? Deleted {exchange} credentials for user {user_id}")
            return True
        return False
    
    @classmethod
    async def hard_delete_credentials(
        cls,
        user_id: str | ObjectId,
        exchange: str | ExchangeType
    ) -> bool:
        """
        Permanently delete credentials (use with caution!).
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        if isinstance(exchange, ExchangeType):
            exchange = exchange.value
        
        result = await collection.delete_one({
            "user_id": user_id,
            "exchange": exchange.lower()
        })
        
        return result.deleted_count > 0
    
    # ==================== VALIDATION ====================
    
    @classmethod
    async def test_credentials(
        cls,
        user_id: str | ObjectId,
        exchange: str | ExchangeType
    ) -> Dict[str, Any]:
        """
        Test if stored credentials are valid by making a test API call.
        
        Returns:
            Dict with 'success' boolean and 'message' string
        """
        cred = await cls.get_credentials(user_id, exchange, decrypt=True)
        
        if not cred:
            return {"success": False, "message": "No credentials found"}
        
        exchange_name = exchange.value if isinstance(exchange, ExchangeType) else exchange
        
        try:
            if exchange_name == "kucoin":
                from kucoin.client import Client as KuCoinClient
                
                client = KuCoinClient(
                    cred["api_key"],
                    cred["api_secret"],
                    cred.get("passphrase", ""),
                    sandbox=cred.get("is_testnet", True)
                )
                # Test call
                accounts = client.get_accounts()
                return {"success": True, "message": "KuCoin credentials valid", "accounts": len(accounts)}
                
            elif exchange_name == "binance":
                from binance.client import Client as BinanceClient
                
                client = BinanceClient(
                    cred["api_key"],
                    cred["api_secret"],
                    testnet=cred.get("is_testnet", True)
                )
                # Test call
                account = client.get_account()
                return {"success": True, "message": "Binance credentials valid"}
            
            else:
                return {"success": False, "message": f"Unknown exchange: {exchange_name}"}
                
        except Exception as e:
            logger.error(f"? Credential test failed: {e}")
            return {"success": False, "message": str(e)}
    
    # ==================== INDEXES ====================
    
    @classmethod
    async def ensure_indexes(cls) -> None:
        """Create necessary indexes."""
        collection = cls._get_collection()
        
        try:
            # Compound unique index on user_id + exchange
            await collection.create_index(
                [("user_id", 1), ("exchange", 1)],
                unique=True
            )
            
            # Index on user_id for queries
            await collection.create_index("user_id")
            
            # Index on is_active for filtering
            await collection.create_index("is_active")
            
            logger.info(f"? Created indexes for {cls.COLLECTION_NAME}")
        except Exception as e:
            logger.warning(f"??  Could not create indexes: {e}")
    
    # ==================== ALIASES ====================
    
    @classmethod
    async def deactivate_credentials(
        cls,
        user_id: str | ObjectId,
        exchange: str | ExchangeType
    ) -> bool:
        """Alias for delete_credentials (soft delete)."""
        return await cls.delete_credentials(user_id, exchange)


# Convenience instance
credentials_repository = CredentialsRepository()
