"""
LogSanitizer - Remove secrets from logs
Previne vazamento de API keys, tokens e credenciais
"""

import re
from typing import Any
import logging

logger = logging.getLogger(__name__)


class LogSanitizer:
    """Sanitiza strings para remover informações sensíveis em logs."""
    
    # Padrões regex para secrets
    SENSITIVE_PATTERNS = [
        # API Keys
        (r"(['\"])apiKey\1\s*:\s*['\"]([^'\"]+)['\"]", r"apiKey: '***REDACTED***'"),
        (r"(['\"])api_key\1\s*:\s*['\"]([^'\"]+)['\"]", r"api_key: '***REDACTED***'"),
        
        # Secrets
        (r"(['\"])secret\1\s*:\s*['\"]([^'\"]+)['\"]", r"secret: '***REDACTED***'"),
        (r"(['\"])api_secret\1\s*:\s*['\"]([^'\"]+)['\"]", r"api_secret: '***REDACTED***'"),
        (r"(['\"])password\1\s*:\s*['\"]([^'\"]+)['\"]", r"password: '***REDACTED***'"),
        (r"(['\"])passphrase\1\s*:\s*['\"]([^'\"]+)['\"]", r"passphrase: '***REDACTED***'"),
        
        # Tokens
        (r"Bearer\s+([a-zA-Z0-9_\-\.]+)", r"Bearer ***REDACTED***"),
        (r"Token\s+([a-zA-Z0-9_\-\.]+)", r"Token ***REDACTED***"),
        
        # MongoDB connection strings
        (r"mongodb(\+srv)?://([^:]+):([^@]+)@", r"mongodb://***:***@"),
        
        # Database passwords
        (r"db_password['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]", r"db_password: '***REDACTED***'"),
        
        # Encryption keys
        (r"encryption_key['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]", r"encryption_key: '***REDACTED***'"),
        
        # Private keys
        (r"-----BEGIN\s+PRIVATE\s+KEY-----(.+?)-----END\s+PRIVATE\s+KEY-----", 
         r"-----BEGIN PRIVATE KEY-----***REDACTED***-----END PRIVATE KEY-----"),
    ]
    
    @staticmethod
    def sanitize(text: str) -> str:
        """Remove informações sensíveis do texto."""
        if not isinstance(text, str):
            return str(text)
        
        result = text
        for pattern, replacement in LogSanitizer.SENSITIVE_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE | re.DOTALL)
        
        return result
    
    @staticmethod
    def sanitize_dict(data: dict) -> dict:
        """Remove informações sensíveis de um dicionário."""
        if not isinstance(data, dict):
            return data
        
        sensitive_keys = {
            'api_key', 'apiKey', 'api_secret', 'secret', 'password', 
            'passphrase', 'token', 'access_token', 'refresh_token',
            'db_password', 'encryption_key', 'private_key'
        }
        
        result = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                result[key] = '***REDACTED***'
            elif isinstance(value, dict):
                result[key] = LogSanitizer.sanitize_dict(value)
            elif isinstance(value, str):
                result[key] = LogSanitizer.sanitize(value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def create_safe_logger(logger_instance: logging.Logger) -> logging.Logger:
        """Cria um logger que sanitiza automaticamente mensagens."""
        
        class SanitizingFormatter(logging.Formatter):
            def format(self, record):
                record.msg = LogSanitizer.sanitize(str(record.msg))
                if record.args:
                    if isinstance(record.args, dict):
                        record.args = LogSanitizer.sanitize_dict(record.args)
                    else:
                        record.args = tuple(
                            LogSanitizer.sanitize(str(arg)) if isinstance(arg, str) else arg 
                            for arg in record.args
                        )
                return super().format(record)
        
        for handler in logger_instance.handlers:
            handler.setFormatter(SanitizingFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        return logger_instance
