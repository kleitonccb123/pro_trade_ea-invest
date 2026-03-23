"""
Log Sanitizer - Remove secrets from logs to prevent credential leaks.

Removes:
- API keys
- Secret tokens
- Bearer tokens
- Passwords
"""

import re
from typing import Any


class LogSanitizer:
    """Sanitizes log messages to remove sensitive data."""
    
    # Patterns to match and hide secrets
    PATTERNS = [
        # API keys
        (r"'apiKey'\s*:\s*'([^']+)'", "apiKey"),
        (r'"apiKey"\s*:\s*"([^"]+)"', "apiKey"),
        (r"api_key[=:]\s*['\"]([^'\"]+)['\"]", "api_key"),
        
        # Secrets
        (r"'secret'\s*:\s*'([^']+)'", "secret"),
        (r'"secret"\s*:\s*"([^"]+)"', "secret"),
        (r"api_secret[=:]\s*['\"]([^'\"]+)['\"]", "api_secret"),
        
        # Passphrases
        (r"'passphrase'\s*:\s*'([^']+)'", "passphrase"),
        (r'"passphrase"\s*:\s*"([^"]+)"', "passphrase"),
        (r"password[=:]\s*['\"]([^'\"]+)['\"]", "password"),
        
        # Bearer tokens
        (r"Bearer\s+([a-zA-Z0-9_\-\.]+)", "Bearer token"),
        (r"Authorization:\s*Bearer\s+([a-zA-Z0-9_\-\.]+)", "Bearer token"),
        
        # JWT tokens
        (r"jwt[=:]\s*['\"]([^'\"]+)['\"]", "jwt"),
        
        # AWS credentials
        (r"aws_secret_access_key[=:]\s*['\"]([^'\"]+)['\"]", "aws_secret"),
        (r"AKIA[0-9A-Z]{16}", "AWS_KEY"),
    ]
    
    @staticmethod
    def sanitize(text: str, mask_length: int = 20) -> str:
        """
        Remove secrets from log message.
        
        Args:
            text: Raw log message
            mask_length: Show first N characters before '***'
            
        Returns:
            Sanitized message with secrets masked
            
        Example:
            >>> original = "apiKey: 'abc123def456ghi789jkl012'"
            >>> LogSanitizer.sanitize(original)
            "apiKey: 'abc123def456ghi7***'"
        """
        if not isinstance(text, str):
            return str(text)
        
        result = text
        
        for pattern, label in LogSanitizer.PATTERNS:
            def mask_secret(match):
                full_match = match.group(0)
                
                # If match has groups, use the captured group (the secret)
                if match.groups():
                    secret = match.group(1)
                    # Show first N chars + ***
                    if len(secret) > mask_length:
                        masked = secret[:mask_length] + "***"
                    else:
                        masked = "***"
                    
                    # Replace the secret part in the full match
                    return full_match.replace(secret, masked)
                else:
                    # No groups, just mask the whole thing
                    return full_match[:mask_length] + "***"
            
            result = re.sub(pattern, mask_secret, result, flags=re.IGNORECASE)
        
        return result
    
    @staticmethod
    def sanitize_dict(data: dict) -> dict:
        """
        Recursively sanitize dictionary values.
        
        Args:
            data: Dictionary potentially containing secrets
            
        Returns:
            Dictionary with sanitized string values
        """
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            # Check if key itself is sensitive
            if any(secret_key in key.lower() for secret_key in 
                   ['api', 'secret', 'key', 'token', 'password', 'credential']):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = LogSanitizer.sanitize_dict(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    LogSanitizer.sanitize_dict(v) if isinstance(v, dict) else v 
                    for v in value
                ]
            elif isinstance(value, str):
                sanitized[key] = LogSanitizer.sanitize(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    @staticmethod
    def sanitize_exception(exc: Exception) -> str:
        """
        Sanitize exception message to prevent secret leaks in stack traces.
        
        Args:
            exc: Exception to sanitize
            
        Returns:
            Sanitized exception string
        """
        return LogSanitizer.sanitize(str(exc))


# Global instance for convenience
_sanitizer = LogSanitizer()


def sanitize(text: str) -> str:
    """Convenience function for sanitizing text."""
    return _sanitizer.sanitize(text)


def sanitize_dict(data: dict) -> dict:
    """Convenience function for sanitizing dictionaries."""
    return _sanitizer.sanitize_dict(data)
