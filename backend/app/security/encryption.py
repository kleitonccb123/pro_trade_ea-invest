"""
CredentialEncryption - Fernet-based encryption for credentials
Armazena secrets criptografados no MongoDB
"""

import os
from typing import Dict, Optional
from datetime import datetime
from cryptography.fernet import Fernet, InvalidToken
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class CredentialEncryption:
    """Gerencia criptografia de credenciais com Fernet."""
    
    def __init__(self, encryption_key: str):
        """
        Inicializa cipher com chave Fernet.
        
        Args:
            encryption_key: Chave Fernet (gerada com Fernet.generate_key())
        """
        try:
            # Tira espacos em branco
            encryption_key = encryption_key.strip()
            
            # Se for string, converte para bytes
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            
            self.cipher = Fernet(encryption_key)
            logger.info("✅ CredentialEncryption initialized")
        except Exception as e:
            logger.error(f"❌ Invalid encryption key: {e}")
            raise ValueError("Invalid Fernet encryption key") from e
    
    def encrypt(self, plaintext: str) -> str:
        """
        Criptografa texto.
        
        Args:
            plaintext: Texto a criptografar
            
        Returns:
            Token Fernet criptografado em format string
        """
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        
        try:
            encrypted = self.cipher.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"❌ Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Descriptografa texto.
        
        Args:
            encrypted_text: Token Fernet criptografado
            
        Returns:
            Texto original
        """
        try:
            if isinstance(encrypted_text, str):
                encrypted_text = encrypted_text.encode()
            
            decrypted = self.cipher.decrypt(encrypted_text)
            return decrypted.decode()
        except InvalidToken:
            logger.error("❌ Decryption failed: Invalid token")
            raise ValueError("Failed to decrypt - token invalid or corrupted")
        except Exception as e:
            logger.error(f"❌ Decryption error: {e}")
            raise


class CredentialStore:
    """Armazena e recupera credenciais criptografadas por usuário."""
    
    def __init__(self, encryption: CredentialEncryption, db):
        """
        Inicializa credential store.
        
        Args:
            encryption: Instância de CredentialEncryption
            db: MongoDB database object
        """
        self.encryption = encryption
        self.db = db
        self.collection = db.user_exchange_credentials
    
    async def store_credentials(
        self,
        user_id: str,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: str = None
    ) -> Dict:
        """
        Armazena credenciais criptografadas para usuário.
        
        Args:
            user_id: ID do usuário
            exchange: Nome da exchange (kucoin, binance, etc)
            api_key: API key (public, não criptografa)
            api_secret: API secret (criptografa)
            passphrase: Passphrase se necessário (criptografa)
            
        Returns:
            Documento inserido
        """
        try:
            # Criptografa campos sensíveis
            encrypted_secret = self.encryption.encrypt(api_secret)
            encrypted_pass = None
            if passphrase:
                encrypted_pass = self.encryption.encrypt(passphrase)
            
            # Remove credencial anterior se existir
            await self.collection.delete_many({
                "user_id": user_id,
                "exchange": exchange
            })
            
            # Armazena nova credencial
            credential_doc = {
                "user_id": user_id,
                "exchange": exchange,
                "api_key": api_key,  # PUBLIC key, não precisa criptografar
                "api_secret_enc": encrypted_secret,  # ENCRYPTED
                "passphrase_enc": encrypted_pass,  # ENCRYPTED
                "algorithm": "fernet",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_active": True
            }
            
            result = await self.collection.insert_one(credential_doc)
            logger.info(f"✅ Credentials stored for user {user_id} on {exchange}")
            return credential_doc
            
        except Exception as e:
            logger.error(f"❌ Failed to store credentials: {e}")
            raise
    
    async def get_credentials(self, user_id: str, exchange: str = "kucoin") -> Optional[Dict]:
        """
        Recupera credenciais descriptografadas para usuário.
        
        Args:
            user_id: ID do usuário
            exchange: Nome da exchange
            
        Returns:
            Dict com api_key, api_secret, passphrase descriptografados
        """
        try:
            doc = await self.collection.find_one({
                "user_id": user_id,
                "exchange": exchange,
                "is_active": True
            })
            
            if not doc:
                logger.warning(f"❌ No credentials found for user {user_id}")
                return None
            
            # Descriptografa campos
            return {
                "api_key": doc["api_key"],
                "api_secret": self.encryption.decrypt(doc["api_secret_enc"]),
                "passphrase": self.encryption.decrypt(doc["passphrase_enc"]) if doc.get("passphrase_enc") else None,
                "created_at": doc["created_at"],
                "updated_at": doc["updated_at"]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve credentials: {e}")
            raise
    
    async def delete_credentials(self, user_id: str, exchange: str = "kucoin") -> bool:
        """
        Deleta credenciais armazenadas.
        
        Args:
            user_id: ID do usuário
            exchange: Nome da exchange
            
        Returns:
            True se deletado com sucesso
        """
        try:
            result = await self.collection.delete_one({
                "user_id": user_id,
                "exchange": exchange
            })
            
            if result.deleted_count > 0:
                logger.info(f"✅ Credentials deleted for user {user_id}")
                return True
            else:
                logger.warning(f"❌ No credentials found to delete")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to delete credentials: {e}")
            raise
    
    async def list_user_exchanges(self, user_id: str) -> list:
        """
        Lista exchanges configuradas para usuário.
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Lista de exchanges
        """
        try:
            docs = await self.collection.find({
                "user_id": user_id,
                "is_active": True
            }).to_list(None)
            
            return [doc["exchange"] for doc in docs]
            
        except Exception as e:
            logger.error(f"❌ Failed to list exchanges: {e}")
            raise


# Singleton instance
_credential_store: Optional[CredentialStore] = None


def init_credential_store(encryption_key: str, db) -> CredentialStore:
    """
    Inicializa credential store global.
    
    Args:
        encryption_key: Chave Fernet
        db: MongoDB database
        
    Returns:
        CredentialStore instance
    """
    global _credential_store
    
    try:
        encryption = CredentialEncryption(encryption_key)
        _credential_store = CredentialStore(encryption, db)
        return _credential_store
    except Exception as e:
        logger.error(f"❌ Failed to initialize credential store: {e}")
        raise


def get_credential_store() -> CredentialStore:
    """Retorna credential store global."""
    if _credential_store is None:
        raise RuntimeError("Credential store not initialized. Call init_credential_store first.")
    return _credential_store


# Gera nova chave Fernet para .env
def generate_encryption_key() -> str:
    """
    Gera nova chave Fernet.
    Use isto em seu .env como: ENCRYPTION_KEY=<resultado>
    
    Returns:
        Chave Fernet em formato string
    """
    key = Fernet.generate_key()
    return key.decode()
