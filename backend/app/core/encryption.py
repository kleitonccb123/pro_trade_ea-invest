"""
Servi?o de Criptografia para Credenciais de Troca
================================================

Usa Fernet (simetria) para criptografar credenciais KuCoin:
- API Key
- API Secret  
- API Passphrase

Nunca salvamos em texto plano. Todas credenciais s?o encriptadas
antes de persistir em MongoDB.

Exemplo:
    from app.core.encryption import encrypt_credential, decrypt_credential
    
    encrypted = encrypt_credential("minha-api-key-123")
    original = decrypt_credential(encrypted)
    assert original == "minha-api-key-123"
"""

from cryptography.fernet import Fernet
import os
from typing import Optional

# ========================================
# Inicializa??o da Chave de Criptografia
# ========================================

def _get_encryption_key() -> bytes:
    """
    Obt?m chave de criptografia do .env.
    
    ?? CR?TICO PARA PRODU??O:
    - A ENCRYPTION_KEY DEVE estar no .env
    - FA?A BACKUP F?SICO da chave (papel, cofre)
    - Se perder a chave, TODAS as API Keys dos usu?rios ser?o perdidas
    - Nunca commite a chave no Git
    """
    env_key = os.getenv("ENCRYPTION_KEY")
    app_mode = os.getenv("APP_MODE", "development")
    
    if env_key:
        # Validar formato da chave Fernet (44 caracteres base64)
        try:
            decoded = env_key.encode() if isinstance(env_key, str) else env_key
            # Testar se ? uma chave Fernet v?lida
            Fernet(decoded)
            return decoded
        except Exception as e:
            raise ValueError(
                f"? ENCRYPTION_KEY inv?lida no .env: {e}\n"
                f"Gere uma nova com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
    
    # Em produ??o, NUNCA permitir sem chave
    if app_mode in ["production", "staging"]:
        raise RuntimeError(
            "? CRITICAL: ENCRYPTION_KEY n?o configurada!\n"
            "Em produ??o, voc? DEVE configurar ENCRYPTION_KEY no .env\n"
            "Gere com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    
    # Apenas em desenvolvimento: gerar chave tempor?ria
    new_key = Fernet.generate_key()
    print("\n" + "="*60)
    print("??  AVISO: ENCRYPTION_KEY n?o configurada!")
    print("="*60)
    print("Uma chave TEMPOR?RIA foi gerada para desenvolvimento.")
    print("\n? Adicione ao seu .env para persistir as credenciais:")
    print(f"\nENCRYPTION_KEY={new_key.decode()}")
    print("\n??  IMPORTANTE: Fa?a backup desta chave!")
    print("Sem ela, voc? n?o conseguir? descriptografar as API Keys.")
    print("="*60 + "\n")
    return new_key


# Inicializar cipher suite globalmente (lazy loading)
_ENCRYPTION_KEY = None
_cipher_suite = None

def _get_cipher_suite():
    """
    Obtem a cipher suite de forma lazy.
    Isso permite que load_dotenv() seja chamado antes
    da chave ser inicializada.
    """
    global _ENCRYPTION_KEY, _cipher_suite
    if _cipher_suite is None:
        _ENCRYPTION_KEY = _get_encryption_key()
        _cipher_suite = Fernet(_ENCRYPTION_KEY)
    return _cipher_suite


# ========================================
# Fun??es de Criptografia
# ========================================

def encrypt_credential(text: str) -> str:
    """
    Criptografa uma credencial (API Key, Secret, Passphrase).
    
    Args:
        text: String a criptografar
        
    Returns:
        String criptografada em base64
        
    Exemplo:
        encrypted = encrypt_credential("api_key_123")
        # "gAAAAABl_xyz..."
    """
    if not text:
        raise ValueError("Credencial n?o pode ser vazia")
    
    cipher_suite = _get_cipher_suite()
    encrypted_bytes = cipher_suite.encrypt(text.encode())
    return encrypted_bytes.decode()


def decrypt_credential(encrypted_text: str) -> str:
    """
    Descriptografa uma credencial previamente encriptada.
    
    Args:
        encrypted_text: String criptografada (output de encrypt_credential)
        
    Returns:
        String original descriptografada
        
    Raises:
        cryptography.fernet.InvalidToken: Se chave ou token forem inv?lidos
        
    Exemplo:
        original = decrypt_credential(encrypted)
        # "api_key_123"
    """
    if not encrypted_text:
        raise ValueError("Texto encriptado n?o pode ser vazio")
    
    try:
        cipher_suite = _get_cipher_suite()
        decrypted_bytes = cipher_suite.decrypt(encrypted_text.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        raise ValueError(f"Falha ao descriptografar: {str(e)}")


def encrypt_kucoin_credentials(api_key: str, api_secret: str, api_passphrase: str) -> dict:
    """
    Encripta todas as credenciais KuCoin de uma vez.
    
    Args:
        api_key: Chave de API da KuCoin
        api_secret: Secret da KuCoin
        api_passphrase: Passphrase da KuCoin
        
    Returns:
        Dict com campos encriptados:
        {
            "api_key_enc": "...",
            "api_secret_enc": "...",
            "api_passphrase_enc": "..."
        }
        
    Exemplo:
        encrypted = encrypt_kucoin_credentials(
            api_key="123abc",
            api_secret="secret456",
            api_passphrase="pass789"
        )
    """
    return {
        "api_key_enc": encrypt_credential(api_key),
        "api_secret_enc": encrypt_credential(api_secret),
        "api_passphrase_enc": encrypt_credential(api_passphrase),
    }


def decrypt_kucoin_credentials(encrypted_data: dict) -> dict:
    """
    Descriptografa todas as credenciais KuCoin de uma vez.
    
    Args:
        encrypted_data: Dict com campos encriptados (de encrypt_kucoin_credentials)
        
    Returns:
        Dict com credenciais descriptografadas:
        {
            "api_key": "123abc",
            "api_secret": "secret456",
            "api_passphrase": "pass789"
        }
    """
    return {
        "api_key": decrypt_credential(encrypted_data.get("api_key_enc", "")),
        "api_secret": decrypt_credential(encrypted_data.get("api_secret_enc", "")),
        "api_passphrase": decrypt_credential(encrypted_data.get("api_passphrase_enc", "")),
    }


# ========================================
# Testes Locais
# ========================================

if __name__ == "__main__":
    """Teste r?pido de criptografia"""
    print("? Testando criptografia Fernet...")
    
    # Teste 1: Credencial ?nica
    test_value = "my-secret-api-key-12345"
    encrypted = encrypt_credential(test_value)
    decrypted = decrypt_credential(encrypted)
    
    assert decrypted == test_value, "Falha na descriptografia!"
    print(f"? Teste 1 passou: {test_value[:10]}... ? encriptado ? ?")
    
    # Teste 2: Credenciais KuCoin
    kucoin_data = encrypt_kucoin_credentials(
        api_key="abc123",
        api_secret="secret456",
        api_passphrase="pass789"
    )
    
    decrypted_data = decrypt_kucoin_credentials(kucoin_data)
    assert decrypted_data["api_key"] == "abc123"
    assert decrypted_data["api_secret"] == "secret456"
    assert decrypted_data["api_passphrase"] == "pass789"
    
    print(f"? Teste 2 passou: KuCoin (3 campos) ? encriptados ? ?")
    
    # Teste 3: Valores vazios
    try:
        encrypt_credential("")
        assert False, "Deveria rejeitar vazio"
    except ValueError:
        print(f"? Teste 3 passou: Valida??o de entrada vazia ?")
    
    print("\n? Todos os testes de criptografia passaram!")


# ========================================
# Classe EncryptionService (Wrapper OOP)
# ========================================

class EncryptionService:
    """
    Servi?o de criptografia orientado a objetos.
    
    Wrapper para as fun??es de criptografia, ?til para inje??o
    de depend?ncia e mocking em testes.
    
    Exemplo:
        service = EncryptionService()
        encrypted = service.encrypt("meu-segredo")
        original = service.decrypt(encrypted)
    """
    
    def __init__(self):
        """Inicializa o servi?o usando a chave global."""
        self._cipher = _get_cipher_suite()
    
    def encrypt(self, text: str) -> str:
        """
        Criptografa um texto.
        
        Args:
            text: String a criptografar
            
        Returns:
            String criptografada em base64
        """
        return encrypt_credential(text)
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Descriptografa um texto.
        
        Args:
            encrypted_text: String criptografada
            
        Returns:
            String original
        """
        return decrypt_credential(encrypted_text)
    
    def encrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Criptografa campos espec?ficos de um dicion?rio.
        
        Args:
            data: Dicion?rio original
            fields: Lista de campos a criptografar
            
        Returns:
            Dicion?rio com campos especificados criptografados
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[f"{field}_enc"] = self.encrypt(result[field])
                del result[field]
        return result
    
    def decrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Descriptografa campos espec?ficos de um dicion?rio.
        
        Args:
            data: Dicion?rio com campos criptografados
            fields: Lista de nomes base dos campos (sem _enc)
            
        Returns:
            Dicion?rio com campos descriptografados
        """
        result = data.copy()
        for field in fields:
            enc_field = f"{field}_enc"
            if enc_field in result and result[enc_field]:
                result[field] = self.decrypt(result[enc_field])
                del result[enc_field]
        return result
