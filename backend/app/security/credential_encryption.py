"""
Credential Encryption - Encrypt/decrypt user API credentials using Fernet.

Uses cryptography.fernet for symmetric encryption:
- Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
- Store in .env: CREDENTIAL_ENCRYPTION_KEY=<key>
"""

import os
from typing import Dict, Optional
from cryptography.fernet import Fernet, InvalidToken
import logging

logger = logging.getLogger(__name__)


class CredentialEncryptionError(Exception):
    """Raised when encryption/decryption fails."""
    pass


class CredentialEncryption:
    """Encrypts and decrypts user exchange credentials."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize cipher.
        
        Args:
            encryption_key: Fernet encryption key. If None, loads from CREDENTIAL_ENCRYPTION_KEY env var.
            
        Raises:
            CredentialEncryptionError: If key is invalid or missing.
        """
        if encryption_key is None:
            encryption_key = os.getenv('CREDENTIAL_ENCRYPTION_KEY')
        
        if not encryption_key:
            raise CredentialEncryptionError(
                "Encryption key not provided. Set CREDENTIAL_ENCRYPTION_KEY env var or pass key to __init__"
            )
        
        try:
            # Validate key format (should be valid Fernet key)
            self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except Exception as e:
            raise CredentialEncryptionError(f"Invalid Fernet key: {e}")
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate new Fernet encryption key.
        
        Returns:
            Base64-encoded key string
            
        Usage:
            >>> key = CredentialEncryption.generate_key()
            >>> print(f"CREDENTIAL_ENCRYPTION_KEY={key}")
        """
        return Fernet.generate_key().decode()
    
    def encrypt_secret(self, secret: str) -> str:
        """
        Encrypt a secret value.
        
        Args:
            secret: Plaintext secret to encrypt
            
        Returns:
            Base64-encoded encrypted secret
            
        Raises:
            CredentialEncryptionError: If encryption fails
        """
        try:
            encrypted = self.cipher.encrypt(secret.encode() if isinstance(secret, str) else secret)
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise CredentialEncryptionError(f"Failed to encrypt secret: {e}")
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt a secret value.
        
        Args:
            encrypted_secret: Base64-encoded encrypted secret
            
        Returns:
            Plaintext secret
            
        Raises:
            CredentialEncryptionError: If decryption fails
        """
        try:
            decrypted = self.cipher.decrypt(
                encrypted_secret.encode() if isinstance(encrypted_secret, str) else encrypted_secret
            )
            return decrypted.decode()
        except InvalidToken:
            logger.error("Failed to decrypt: invalid token or corrupted data")
            raise CredentialEncryptionError("Failed to decrypt: invalid token or corrupted data")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise CredentialEncryptionError(f"Failed to decrypt secret: {e}")
    
    def encrypt_credentials(self, api_key: str, api_secret: str, passphrase: str) -> Dict[str, str]:
        """
        Encrypt all credential fields.
        
        Args:
            api_key: KuCoin API key (public, but encrypt anyway)
            api_secret: KuCoin API secret (MUST be encrypted)
            passphrase: KuCoin API passphrase (MUST be encrypted)
            
        Returns:
            Dict with encrypted values:
            {
                "api_key_enc": "...",
                "api_secret_enc": "...",
                "passphrase_enc": "...",
                "algorithm": "fernet"
            }
        """
        return {
            "api_key_enc": self.encrypt_secret(api_key),
            "api_secret_enc": self.encrypt_secret(api_secret),
            "passphrase_enc": self.encrypt_secret(passphrase),
            "algorithm": "fernet"
        }
    
    def decrypt_credentials(self, api_key_enc: str, api_secret_enc: str, passphrase_enc: str) -> Dict[str, str]:
        """
        Decrypt all credential fields.
        
        Args:
            api_key_enc: Encrypted API key
            api_secret_enc: Encrypted API secret
            passphrase_enc: Encrypted passphrase
            
        Returns:
            Dict with decrypted values:
            {
                "api_key": "...",
                "api_secret": "...",
                "passphrase": "..."
            }
            
        Raises:
            CredentialEncryptionError: If any decryption fails
        """
        return {
            "api_key": self.decrypt_secret(api_key_enc),
            "api_secret": self.decrypt_secret(api_secret_enc),
            "passphrase": self.decrypt_secret(passphrase_enc),
        }


# Global instance
_cipher: Optional[CredentialEncryption] = None


def init_credential_encryption(encryption_key: Optional[str] = None) -> CredentialEncryption:
    """
    Initialize global credential encryption instance.
    
    Args:
        encryption_key: Optional encryption key (loads from env if not provided)
        
    Returns:
        CredentialEncryption instance
    """
    global _cipher
    _cipher = CredentialEncryption(encryption_key)
    logger.info("✅ Credential encryption initialized")
    return _cipher


def get_credential_encryption() -> CredentialEncryption:
    """
    Get global credential encryption instance.
    
    Returns:
        CredentialEncryption instance
        
    Raises:
        CredentialEncryptionError: If not initialized
    """
    global _cipher
    if _cipher is None:
        raise CredentialEncryptionError("Credential encryption not initialized. Call init_credential_encryption() first")
    return _cipher


def validate_encryption_key_at_startup() -> None:
    """
    Validate CREDENTIAL_ENCRYPTION_KEY at application startup.

    Raises:
        RuntimeError: If the key is missing or not a valid Fernet key.
                      This is intentional — the app must NOT start without a
                      stable encryption key, otherwise stored credentials
                      cannot be decrypted after a restart.
    """
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "\n" + "=" * 70 + "\n"
            "CRÍTICO: CREDENTIAL_ENCRYPTION_KEY não está definida.\n"
            "As chaves de API dos usuários não podem ser criptografadas/\n"
            "descriptografadas sem esta chave.\n\n"
            "Gere uma chave segura com:\n"
            "  python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"\n\n"
            "Adicione ao .env:\n"
            "  CREDENTIAL_ENCRYPTION_KEY=<chave gerada>\n"
            + "=" * 70
        )
    try:
        Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise RuntimeError(
            f"CREDENTIAL_ENCRYPTION_KEY inválida: {exc}\n"
            "A chave deve ser uma Fernet key em Base64 de 32 bytes.\n"
            "Gere uma nova com: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        ) from exc
    logger.info("✅ CREDENTIAL_ENCRYPTION_KEY validada com sucesso.")
