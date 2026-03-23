"""
Two-Factor Authentication (2FA) Module

Implementa:
1. TOTP (Time-based One-Time Password) - Google Authenticator
2. Backup codes para recupera??o
3. Verifica??o obrigat?ria para opera??es cr?ticas
4. Rate limiting para prote??o contra brute force

Author: Crypto Trade Hub
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import secrets
import struct
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from app.core.database import get_db
from app.core.encryption import EncryptionService

logger = logging.getLogger(__name__)


# ==================== TOTP IMPLEMENTATION ====================

class TOTP:
    """
    TOTP (Time-based One-Time Password) implementation.
    Compatible with Google Authenticator, Authy, etc.
    """
    
    def __init__(
        self,
        secret: str,
        digits: int = 6,
        interval: int = 30,
        algorithm: str = "sha1"
    ):
        self.secret = secret
        self.digits = digits
        self.interval = interval
        self.algorithm = algorithm
    
    @classmethod
    def generate_secret(cls, length: int = 32) -> str:
        """Gera um secret aleat?rio em base32."""
        # 20 bytes = 160 bits de entropia
        random_bytes = secrets.token_bytes(length)
        return base64.b32encode(random_bytes).decode("utf-8").rstrip("=")
    
    def _get_counter(self, timestamp: float = None) -> int:
        """Calcula o counter baseado no timestamp."""
        if timestamp is None:
            timestamp = time.time()
        return int(timestamp // self.interval)
    
    def _generate_hotp(self, counter: int) -> str:
        """Gera HOTP para um counter espec?fico."""
        # Decodificar secret
        key = base64.b32decode(self.secret.upper() + "=" * ((8 - len(self.secret)) % 8))
        
        # Counter em bytes (big-endian, 8 bytes)
        counter_bytes = struct.pack(">Q", counter)
        
        # HMAC-SHA1
        if self.algorithm == "sha1":
            hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        elif self.algorithm == "sha256":
            hmac_hash = hmac.new(key, counter_bytes, hashlib.sha256).digest()
        else:
            raise ValueError(f"Algoritmo n?o suportado: {self.algorithm}")
        
        # Dynamic truncation
        offset = hmac_hash[-1] & 0x0F
        truncated = struct.unpack(">I", hmac_hash[offset:offset + 4])[0]
        truncated &= 0x7FFFFFFF
        
        # Gerar c?digo com n?mero de d?gitos
        code = truncated % (10 ** self.digits)
        return str(code).zfill(self.digits)
    
    def generate(self, timestamp: float = None) -> str:
        """Gera c?digo TOTP atual."""
        counter = self._get_counter(timestamp)
        return self._generate_hotp(counter)
    
    def verify(self, code: str, window: int = 1) -> bool:
        """
        Verifica um c?digo TOTP.
        
        Args:
            code: C?digo a verificar
            window: Janela de toler?ncia (default: ?1 intervalo = 30s)
        
        Returns:
            True se c?digo v?lido
        """
        current_counter = self._get_counter()
        
        # Verificar c?digos em janela de toler?ncia
        for i in range(-window, window + 1):
            expected = self._generate_hotp(current_counter + i)
            if hmac.compare_digest(code, expected):
                return True
        
        return False
    
    def get_provisioning_uri(
        self,
        account_name: str,
        issuer: str = "CryptoTradeHub"
    ) -> str:
        """
        Gera URI para QR code.
        
        Formato: otpauth://totp/ISSUER:ACCOUNT?secret=XXX&issuer=ISSUER&algorithm=SHA1&digits=6&period=30
        """
        import urllib.parse
        
        label = urllib.parse.quote(f"{issuer}:{account_name}")
        params = {
            "secret": self.secret,
            "issuer": issuer,
            "algorithm": self.algorithm.upper(),
            "digits": str(self.digits),
            "period": str(self.interval),
        }
        
        query = urllib.parse.urlencode(params)
        return f"otpauth://totp/{label}?{query}"


# ==================== 2FA SERVICE ====================

@dataclass
class TwoFactorSetup:
    """Dados para configura??o de 2FA."""
    secret: str
    provisioning_uri: str
    backup_codes: List[str]
    qr_code_data: Optional[str] = None


class TwoFactorAuthService:
    """
    Servi?o de autentica??o de dois fatores.
    
    Features:
    - Setup de TOTP com QR code
    - Gera??o de backup codes
    - Verifica??o de c?digos
    - Rate limiting contra brute force
    """
    
    COLLECTION = "user_2fa"
    BACKUP_CODES_COUNT = 10
    MAX_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15
    
    def __init__(self):
        self.encryption = EncryptionService()
    
    def _get_collection(self):
        db = get_db()
        return db[self.COLLECTION]
    
    async def setup_2fa(self, user_id: str, email: str) -> TwoFactorSetup:
        """
        Inicia configura??o de 2FA para um usu?rio.
        
        Returns:
            TwoFactorSetup com secret, URI e backup codes
        """
        # Gerar secret
        secret = TOTP.generate_secret()
        
        # Gerar backup codes
        backup_codes = self._generate_backup_codes()
        
        # Criar TOTP
        totp = TOTP(secret)
        provisioning_uri = totp.get_provisioning_uri(email)
        
        # Salvar (ainda n?o ativado)
        collection = self._get_collection()
        
        # Encriptar secret e backup codes
        encrypted_secret = self.encryption.encrypt(secret)
        encrypted_backup = [self.encryption.encrypt(code) for code in backup_codes]
        
        await collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "secret_encrypted": encrypted_secret,
                    "backup_codes_encrypted": encrypted_backup,
                    "backup_codes_used": [],
                    "is_enabled": False,
                    "setup_started_at": datetime.utcnow(),
                    "enabled_at": None,
                    "failed_attempts": 0,
                    "locked_until": None,
                }
            },
            upsert=True
        )
        
        logger.info(f"? 2FA setup iniciado para user {user_id}")
        
        return TwoFactorSetup(
            secret=secret,
            provisioning_uri=provisioning_uri,
            backup_codes=backup_codes,
        )
    
    def _generate_backup_codes(self) -> List[str]:
        """Gera c?digos de backup."""
        codes = []
        for _ in range(self.BACKUP_CODES_COUNT):
            # Formato: XXXX-XXXX (8 caracteres)
            code = secrets.token_hex(4).upper()
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes
    
    async def confirm_setup(self, user_id: str, code: str) -> bool:
        """
        Confirma configura??o de 2FA verificando um c?digo.
        
        Deve ser chamado ap?s o usu?rio escanear o QR code.
        """
        collection = self._get_collection()
        
        doc = await collection.find_one({"user_id": user_id})
        if not doc:
            return False
        
        if doc.get("is_enabled"):
            logger.warning(f"?? 2FA j? est? ativo para user {user_id}")
            return True
        
        # Decriptar secret
        secret = self.encryption.decrypt(doc["secret_encrypted"])
        
        # Verificar c?digo
        totp = TOTP(secret)
        if totp.verify(code):
            await collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_enabled": True,
                        "enabled_at": datetime.utcnow(),
                    }
                }
            )
            logger.info(f"? 2FA ativado para user {user_id}")
            return True
        
        logger.warning(f"?? C?digo 2FA inv?lido na confirma??o para user {user_id}")
        return False
    
    async def verify(self, user_id: str, code: str) -> Tuple[bool, str]:
        """
        Verifica c?digo 2FA.
        
        Returns:
            (success, message)
        """
        collection = self._get_collection()
        
        doc = await collection.find_one({"user_id": user_id})
        if not doc:
            return False, "2FA n?o configurado"
        
        if not doc.get("is_enabled"):
            return False, "2FA n?o est? ativo"
        
        # Verificar lockout
        if doc.get("locked_until"):
            if datetime.utcnow() < doc["locked_until"]:
                remaining = (doc["locked_until"] - datetime.utcnow()).seconds // 60
                return False, f"Conta bloqueada. Tente novamente em {remaining} minutos"
            else:
                # Desbloquear
                await collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"locked_until": None, "failed_attempts": 0}}
                )
        
        # Decriptar secret
        secret = self.encryption.decrypt(doc["secret_encrypted"])
        
        # Verificar TOTP
        totp = TOTP(secret)
        if totp.verify(code):
            # Reset failed attempts
            await collection.update_one(
                {"user_id": user_id},
                {"$set": {"failed_attempts": 0, "last_success": datetime.utcnow()}}
            )
            return True, "C?digo verificado"
        
        # Verificar backup codes
        if self._is_backup_code_format(code):
            result = await self._verify_backup_code(user_id, code, doc)
            if result:
                return True, "Backup code usado"
        
        # Falha - incrementar contador
        failed = doc.get("failed_attempts", 0) + 1
        update = {"$set": {"failed_attempts": failed}}
        
        if failed >= self.MAX_ATTEMPTS:
            lock_until = datetime.utcnow() + timedelta(minutes=self.LOCKOUT_MINUTES)
            update["$set"]["locked_until"] = lock_until
            logger.warning(f"? User {user_id} bloqueado por {self.LOCKOUT_MINUTES} min ap?s {failed} tentativas")
        
        await collection.update_one({"user_id": user_id}, update)
        
        remaining = self.MAX_ATTEMPTS - failed
        return False, f"C?digo inv?lido. {remaining} tentativas restantes"
    
    def _is_backup_code_format(self, code: str) -> bool:
        """Verifica se c?digo tem formato de backup code."""
        return len(code) == 9 and code[4] == "-"
    
    async def _verify_backup_code(self, user_id: str, code: str, doc: Dict) -> bool:
        """Verifica e consome um backup code."""
        collection = self._get_collection()
        
        # Verificar se j? foi usado
        if code in doc.get("backup_codes_used", []):
            return False
        
        # Verificar contra codes encriptados
        for encrypted_code in doc.get("backup_codes_encrypted", []):
            decrypted = self.encryption.decrypt(encrypted_code)
            if hmac.compare_digest(code.upper(), decrypted.upper()):
                # Marcar como usado
                await collection.update_one(
                    {"user_id": user_id},
                    {"$push": {"backup_codes_used": code.upper()}}
                )
                logger.info(f"? Backup code usado por user {user_id}")
                return True
        
        return False
    
    async def is_2fa_enabled(self, user_id: str) -> bool:
        """Verifica se 2FA est? ativo para um usu?rio."""
        collection = self._get_collection()
        doc = await collection.find_one({"user_id": user_id})
        return doc.get("is_enabled", False) if doc else False
    
    async def disable_2fa(self, user_id: str, code: str) -> Tuple[bool, str]:
        """
        Desativa 2FA (requer verifica??o).
        """
        # Verificar c?digo antes de desativar
        success, message = await self.verify(user_id, code)
        
        if not success:
            return False, message
        
        collection = self._get_collection()
        await collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "is_enabled": False,
                    "disabled_at": datetime.utcnow(),
                }
            }
        )
        
        logger.info(f"? 2FA desativado para user {user_id}")
        return True, "2FA desativado com sucesso"
    
    async def regenerate_backup_codes(self, user_id: str, code: str) -> Tuple[bool, List[str]]:
        """
        Regenera backup codes (requer verifica??o).
        """
        success, message = await self.verify(user_id, code)
        
        if not success:
            return False, []
        
        # Gerar novos codes
        new_codes = self._generate_backup_codes()
        encrypted_codes = [self.encryption.encrypt(c) for c in new_codes]
        
        collection = self._get_collection()
        await collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "backup_codes_encrypted": encrypted_codes,
                    "backup_codes_used": [],
                    "backup_codes_regenerated_at": datetime.utcnow(),
                }
            }
        )
        
        logger.info(f"? Backup codes regenerados para user {user_id}")
        return True, new_codes
    
    async def get_2fa_status(self, user_id: str) -> Dict[str, Any]:
        """Retorna status do 2FA para um usu?rio."""
        collection = self._get_collection()
        doc = await collection.find_one({"user_id": user_id})
        
        if not doc:
            return {
                "enabled": False,
                "setup_started": False,
            }
        
        backup_used = len(doc.get("backup_codes_used", []))
        backup_total = len(doc.get("backup_codes_encrypted", []))
        
        return {
            "enabled": doc.get("is_enabled", False),
            "setup_started": True,
            "enabled_at": doc.get("enabled_at"),
            "backup_codes_remaining": backup_total - backup_used,
            "last_verification": doc.get("last_success"),
            "failed_attempts": doc.get("failed_attempts", 0),
            "is_locked": doc.get("locked_until") and datetime.utcnow() < doc.get("locked_until"),
        }


# ==================== SESSION MANAGEMENT ====================

class SessionManager:
    """
    Gerenciador de sess?es para JWT refresh tokens.
    
    Features:
    - M?ltiplas sess?es por usu?rio
    - Revoga??o individual ou em massa
    - Detec??o de dispositivo/IP
    """
    
    COLLECTION = "user_sessions"
    MAX_SESSIONS = 5
    
    def _get_collection(self):
        db = get_db()
        return db[self.COLLECTION]
    
    async def create_session(
        self,
        user_id: str,
        refresh_token: str,
        device_info: Dict[str, str] = None,
        ip_address: str = None
    ) -> str:
        """Cria uma nova sess?o."""
        collection = self._get_collection()
        
        # Limpar sess?es antigas se exceder m?ximo
        existing = await collection.count_documents({"user_id": user_id})
        if existing >= self.MAX_SESSIONS:
            # Remover sess?o mais antiga
            oldest = await collection.find_one(
                {"user_id": user_id},
                sort=[("created_at", 1)]
            )
            if oldest:
                await collection.delete_one({"_id": oldest["_id"]})
        
        # Gerar session ID
        session_id = secrets.token_urlsafe(32)
        
        # Hash do refresh token (n?o armazenar plain text)
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        session_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "device_info": device_info or {},
            "ip_address": ip_address,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "is_active": True,
        }
        
        await collection.insert_one(session_doc)
        logger.info(f"? Sess?o criada para user {user_id}: {session_id[:8]}...")
        
        return session_id
    
    async def validate_session(self, user_id: str, refresh_token: str) -> bool:
        """Valida se uma sess?o ? v?lida."""
        collection = self._get_collection()
        
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        session = await collection.find_one({
            "user_id": user_id,
            "token_hash": token_hash,
            "is_active": True,
        })
        
        if session:
            # Atualizar ?ltima atividade
            await collection.update_one(
                {"_id": session["_id"]},
                {"$set": {"last_activity": datetime.utcnow()}}
            )
            return True
        
        return False
    
    async def revoke_session(self, user_id: str, session_id: str) -> bool:
        """Revoga uma sess?o espec?fica."""
        collection = self._get_collection()
        
        result = await collection.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"is_active": False, "revoked_at": datetime.utcnow()}}
        )
        
        if result.modified_count > 0:
            logger.info(f"? Sess?o revogada: {session_id[:8]}...")
            return True
        
        return False
    
    async def revoke_all_sessions(self, user_id: str, except_session: str = None) -> int:
        """Revoga todas as sess?es de um usu?rio."""
        collection = self._get_collection()
        
        query = {"user_id": user_id, "is_active": True}
        if except_session:
            query["session_id"] = {"$ne": except_session}
        
        result = await collection.update_many(
            query,
            {"$set": {"is_active": False, "revoked_at": datetime.utcnow()}}
        )
        
        logger.info(f"? {result.modified_count} sess?es revogadas para user {user_id}")
        return result.modified_count
    
    async def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Lista sess?es ativas de um usu?rio."""
        collection = self._get_collection()
        
        cursor = collection.find(
            {"user_id": user_id, "is_active": True},
            {"token_hash": 0}  # N?o retornar hash
        ).sort("last_activity", -1)
        
        sessions = await cursor.to_list(length=self.MAX_SESSIONS)
        
        for s in sessions:
            s["_id"] = str(s["_id"])
        
        return sessions


# Inst?ncias globais
two_factor_service = TwoFactorAuthService()
session_manager = SessionManager()
