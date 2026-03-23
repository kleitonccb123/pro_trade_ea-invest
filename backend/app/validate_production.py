"""
Production Preflight Validator — Crypto Trade Hub
Run before deploying: python -m app.validate_production
Checks all critical configuration, connectivity, and security requirements.
"""
import os
import sys

CHECKS_PASSED = 0
CHECKS_FAILED = 0
WARNINGS = 0


def ok(msg: str):
    global CHECKS_PASSED
    CHECKS_PASSED += 1
    print(f"  [OK] {msg}")


def fail(msg: str):
    global CHECKS_FAILED
    CHECKS_FAILED += 1
    print(f"  [FAIL] {msg}")


def warn(msg: str):
    global WARNINGS
    WARNINGS += 1
    print(f"  [WARN] {msg}")


def check_env_vars():
    print("\n[SECURITY] CHECKING ENVIRONMENT VARIABLES...")

    critical = [
        ("APP_MODE", "prod"),
        ("JWT_SECRET_KEY", None),
        ("ENCRYPTION_KEY", None),
        ("DATABASE_URL", None),
    ]
    for var, expected in critical:
        val = os.getenv(var, "")
        if not val:
            fail(f"{var} is NOT SET")
        elif expected and val != expected:
            fail(f"{var} = '{val}' (expected '{expected}')")
        else:
            ok(f"{var} is set")

    # JWT secret must not be default
    jwt = os.getenv("JWT_SECRET_KEY", "")
    if jwt and len(jwt) < 32:
        fail(f"JWT_SECRET_KEY too short ({len(jwt)} chars, need >= 32)")
    if jwt in ("your-secret-key-change-in-production", "changeme", "secret"):
        fail("JWT_SECRET_KEY is still the default placeholder!")

    # Credential encryption
    cek = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    if not cek:
        fail("CREDENTIAL_ENCRYPTION_KEY not set — user API keys will NOT be encrypted")
    else:
        ok("CREDENTIAL_ENCRYPTION_KEY is set")

    # Redis
    redis = os.getenv("REDIS_URL", "")
    if not redis:
        fail("REDIS_URL not set — distributed locks, Kill Switch, pub/sub will FAIL")
    else:
        ok(f"REDIS_URL is set")

    # CORS
    cors = os.getenv("CORS_ORIGINS") or os.getenv("ALLOWED_ORIGINS", "")
    if "*" in cors:
        fail("CORS allows ALL origins (*) — must be restrictive in production")
    elif "localhost" in cors and os.getenv("APP_MODE") == "prod":
        warn("CORS includes localhost — remove for production")
    else:
        ok(f"CORS origins: {cors[:80]}...")

    # Optional but recommended
    optional = [
        ("GOOGLE_CLIENT_ID", "Google OAuth will be disabled"),
        ("SENTRY_DSN", "Error monitoring disabled"),
        ("PERFECT_PAY_API_KEY", "Payment integration disabled"),
        ("SMTP_USER", "Email sending disabled"),
    ]
    for var, impact in optional:
        if os.getenv(var):
            ok(f"{var} is set")
        else:
            warn(f"{var} not set — {impact}")


def check_database():
    print("\n[DB] CHECKING DATABASE CONNECTIVITY...")
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio

        url = os.getenv("DATABASE_URL", "")
        if not url:
            fail("DATABASE_URL not set")
            return

        async def test_db():
            client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
            await client.admin.command("ping")
            db_name = os.getenv("DATABASE_NAME", "crypto_trade_hub")
            db = client[db_name]
            collections = await db.list_collection_names()
            return len(collections)

        count = asyncio.run(test_db())
        ok(f"MongoDB connected ({count} collections)")
    except Exception as e:
        fail(f"MongoDB connection failed: {e}")


def check_redis():
    print("\n[REDIS] CHECKING REDIS CONNECTIVITY...")
    try:
        import redis as redis_lib

        url = os.getenv("REDIS_URL", "")
        if not url:
            fail("REDIS_URL not set")
            return

        r = redis_lib.from_url(url, socket_connect_timeout=5)
        r.ping()
        ok("Redis connected and responding")
    except Exception as e:
        fail(f"Redis connection failed: {e}")


def check_encryption():
    print("\n[CRYPTO] CHECKING ENCRYPTION KEYS...")
    try:
        from cryptography.fernet import Fernet

        for var in ("ENCRYPTION_KEY", "CREDENTIAL_ENCRYPTION_KEY", "STRATEGY_ENCRYPTION_KEY"):
            key = os.getenv(var, "")
            if not key:
                if var == "STRATEGY_ENCRYPTION_KEY":
                    warn(f"{var} not set (optional)")
                else:
                    fail(f"{var} not set")
                continue
            try:
                Fernet(key.encode())
                ok(f"{var} is a valid Fernet key")
            except Exception:
                fail(f"{var} is NOT a valid Fernet key")
    except ImportError:
        fail("cryptography package not installed")


def check_security():
    print("\n[SHIELD] CHECKING SECURITY CONFIGURATION...")

    # Check APP_MODE
    mode = os.getenv("APP_MODE", "dev")
    if mode == "prod":
        ok("APP_MODE = prod")
    else:
        fail(f"APP_MODE = '{mode}' (must be 'prod' for production)")

    # Check DEBUG
    debug = os.getenv("DEBUG", "false").lower()
    if debug in ("true", "1", "yes"):
        fail("DEBUG is enabled — must be false in production")
    else:
        ok("DEBUG is disabled")


def main():
    print("=" * 60)
    print("  CRYPTO TRADE HUB — Production Preflight Check")
    print("=" * 60)

    # Load .env if present
    try:
        from dotenv import load_dotenv
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_file):
            load_dotenv(env_file)
    except ImportError:
        pass

    check_env_vars()
    check_security()
    check_encryption()
    check_database()
    check_redis()

    print("\n" + "=" * 60)
    print(f"  RESULTS: {CHECKS_PASSED} passed, {CHECKS_FAILED} failed, {WARNINGS} warnings")
    print("=" * 60)

    if CHECKS_FAILED > 0:
        print("\n  [BLOCKED] PRODUCTION DEPLOY BLOCKED -- fix the failures above.")
        sys.exit(1)
    elif WARNINGS > 0:
        print("\n  [CAUTION] Warnings present -- review before deploying.")
        sys.exit(0)
    else:
        print("\n  [READY] ALL CHECKS PASSED -- ready to deploy!")
        sys.exit(0)


if __name__ == "__main__":
    main()
