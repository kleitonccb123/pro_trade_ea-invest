"""
cipher_singleton.py — DOC-K01

Singleton thread-safe do CredentialEncryption.
Inicializado uma vez no startup da aplicação. Falha imediatamente
(RuntimeError) se CREDENTIAL_ENCRYPTION_KEY não estiver configurada.

Uso:
    from app.security.cipher_singleton import get_cipher
    cipher = get_cipher()
    enc = cipher.encrypt_credentials(api_key, api_secret, passphrase)
    dec = cipher.decrypt_credentials(**enc)
"""
from __future__ import annotations

import os
from functools import lru_cache

from app.security.credential_encryption import CredentialEncryption, CredentialEncryptionError  # noqa: F401


@lru_cache(maxsize=1)
def get_cipher() -> CredentialEncryption:
    """
    Retorna instância única do cipher.
    Falha em startup se CREDENTIAL_ENCRYPTION_KEY não estiver configurada.

    Raises:
        RuntimeError: se a env var não estiver setada.
        CredentialEncryptionError: se a chave for inválida (Fernet).
    """
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "[STARTUP FATAL] CREDENTIAL_ENCRYPTION_KEY não configurada. "
            "Gere com: python -c "
            "\"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return CredentialEncryption(encryption_key=key)
