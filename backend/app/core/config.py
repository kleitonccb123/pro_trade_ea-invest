from __future__ import annotations

import os
import sys
import secrets
import logging
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

_config_logger = logging.getLogger(__name__)

# Load .env from project root (parent of backend dir)
backend_dir = Path(__file__).parent.parent.parent  # backend/
project_root = backend_dir.parent  # project root
env_file = project_root / ".env"

# Load .env file
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()  # Fallback: load from current directory

try:
    from pydantic_settings import BaseSettings
    from pydantic import field_validator
except ImportError:
    from pydantic import BaseSettings, validator as field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses pydantic-settings for validation and type safety.
    """

    # ============================================
    # ? CORE SETTINGS
    # ============================================

    # Application mode: dev/staging/prod (affects logging/default behavior)
    app_mode: str = os.getenv("APP_MODE", "dev")

    # ============================================
    # ?? DATABASE SETTINGS
    # ============================================

    # MongoDB Atlas connection URL
    # Format: mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mongodb://localhost:27017"  # Local MongoDB fallback
    )
    database_name: str = os.getenv("DATABASE_NAME", "trading_app_db")
    mongodb_driver: str = "motor"  # Using motor for async MongoDB

    # Redis settings for Pub/Sub and caching
    # SET TO EMPTY STRING TO DISABLE REDIS (useful for local development without Docker)
    redis_url: str = os.getenv("REDIS_URL", "")  # Default to empty (disabled)
    redis_pubsub_channel: str = os.getenv("REDIS_PUBSUB_CHANNEL", "trading_notifications")

    # ============================================
    # ? SECURITY SETTINGS
    # ============================================

    # JWT Secret Key (critical - must be set in production)
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    refresh_token_expire_minutes: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))

    # Encryption key for sensitive data (Fernet)
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        if not v:
            if os.getenv("APP_MODE", "dev") == "prod":
                raise ValueError(
                    "JWT_SECRET_KEY must be set via environment variable in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            _config_logger.warning(
                "JWT_SECRET_KEY not set — using an ephemeral random key. "
                "All tokens will be invalidated on every restart. "
                "Set JWT_SECRET_KEY in your .env file to fix this."
            )
            return secrets.token_hex(32)
        return v

    @field_validator("encryption_key", mode="before")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if not v:
            if os.getenv("APP_MODE", "dev") == "prod":
                raise ValueError(
                    "ENCRYPTION_KEY must be set via environment variable in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            _config_logger.warning(
                "ENCRYPTION_KEY not set — using an ephemeral random key. "
                "All encrypted API credentials will be lost on every restart. "
                "Set ENCRYPTION_KEY in your .env file to fix this."
            )
            return secrets.token_hex(32)
        return v

    # ============================================
    # ? TRADING SETTINGS
    # ============================================

    # Offline Mode (use in-memory mock data if true)
    offline_mode: bool = os.getenv("OFFLINE_MODE", "false").lower() in ("1", "true", "yes", "on")

    # Simulation
    initial_balance: float = float(os.getenv("INITIAL_BALANCE", "10000"))

    # ============================================
    # ? BOT & ANALYTICS SETTINGS
    # ============================================

    # Scheduler / automation flags
    enable_bots: bool = os.getenv("ENABLE_BOTS", "true").lower() in ("1", "true", "yes", "on")
    enable_analytics: bool = os.getenv("ENABLE_ANALYTICS", "true").lower() in ("1", "true", "yes", "on")

    # Intervals (in seconds) for scheduled tasks
    scheduler_bots_interval: float = float(os.getenv("SCHEDULER_BOTS_INTERVAL", "5"))
    scheduler_analytics_interval: float = float(os.getenv("SCHEDULER_ANALYTICS_INTERVAL", "60"))

    # ============================================
    # ? API & EXTERNAL SERVICES
    # ============================================

    # AI API Keys
    google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
    groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")

    # KuCoin API Keys (for live trading)
    kucoin_api_key: Optional[str] = os.getenv("KUCOIN_API_KEY")
    kucoin_api_secret: Optional[str] = os.getenv("KUCOIN_API_SECRET")
    kucoin_api_passphrase: Optional[str] = os.getenv("KUCOIN_API_PASSPHRASE")

    # Asaas Payment Gateway (PIX payouts for affiliates)
    asaas_api_key: Optional[str] = os.getenv("ASAAS_API_KEY")
    asaas_sandbox: bool = os.getenv("ASAAS_SANDBOX", "true").lower() == "true"

    # ============================================
    # ? CORS SETTINGS
    # ============================================

    # CORS allowed origins (reads CORS_ORIGINS first, falls back to ALLOWED_ORIGINS)
    allowed_origins_str: str = os.getenv("CORS_ORIGINS") or os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8080,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:5173"
    )

    # ============================================
    # ? MONITORING & LOGGING
    # ============================================

    # Sentry DSN for error tracking
    sentry_dsn: Optional[str] = os.getenv("SENTRY_DSN")

    # ============================================
    # ? TRANSLATION & LOCALIZATION
    # ============================================

    # Translation settings
    translation_enabled: bool = os.getenv("TRANSLATION_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    translation_target: str = os.getenv("TRANSLATION_TARGET", "pt")

    # ============================================
    # 🔔 WEB PUSH NOTIFICATIONS (VAPID)
    # ============================================

    # VAPID keys for Web Push API.
    # Generate with: python -c "from py_vapid import Vapid; ..."
    vapid_private_key: str = os.getenv("VAPID_PRIVATE_KEY", "")
    vapid_public_key: str = os.getenv("VAPID_PUBLIC_KEY", "")
    vapid_claims_email: str = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@cryptotradehub.com")

    # ============================================
    # 📝 LICENSING (FUTURE FEATURE)
    # ============================================

    # Licensing (future feature)
    licensing_url: str = os.getenv("LICENSING_URL", "")
    licensing_timeout: float = float(os.getenv("LICENSING_TIMEOUT", "5"))
    licensing_cache_ttl: int = int(os.getenv("LICENSING_CACHE_TTL", "300"))

    # ============================================
    # 💳 PERFECT PAY (PAGAMENTOS)
    # ============================================

    # Token pessoal gerado em: Ferramentas > API no painel Perfect Pay
    perfect_pay_api_key: Optional[str] = os.getenv("PERFECT_PAY_API_KEY")
    # Segredo compartilhado para validar autenticidade dos Postbacks
    perfect_pay_postback_secret: Optional[str] = os.getenv("PERFECT_PAY_POSTBACK_SECRET")
    # Mapeamento product_token→plano (JSON): ex: '{"tok_basic":"basic","tok_pro":"pro"}'
    perfect_pay_plan_map_json: str = os.getenv("PERFECT_PAY_PLAN_MAP", "{}")

    # ============================================
    # 🔐 CREDENTIAL ENCRYPTION
    # ============================================

    # Fernet key used to encrypt user API keys at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    credential_encryption_key: Optional[str] = os.getenv("CREDENTIAL_ENCRYPTION_KEY")

    # Fernet key used to encrypt strategy source code at rest (DOC-08).
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    strategy_encryption_key: Optional[str] = os.getenv("STRATEGY_ENCRYPTION_KEY")

    # Revenue share: percentual que fica com a plataforma (0.0-1.0)
    marketplace_platform_take_rate: float = float(os.getenv("MARKETPLACE_PLATFORM_TAKE_RATE", "0.30"))

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        env_prefix = ""  # No prefix for env vars
        extra = "ignore"  # Ignore extra environment variables

    @property
    def allowed_origins(self) -> List[str]:
        """Parse allowed origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins_str.split(",") if origin.strip()]


def get_settings() -> Settings:
    """Get the current application settings."""
    return settings


# Create global settings instance
settings = Settings()
