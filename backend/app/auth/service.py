from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Union

from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import verify_password, get_password_hash
from app.users import repository as user_repo


def _now() -> datetime:
    return datetime.utcnow()


def create_access_token(
    subject: Union[int, str],
    scope: Optional[str] = None,
    expire_minutes: Optional[int] = None,
) -> str:
    minutes = expire_minutes if expire_minutes is not None else settings.access_token_expire_minutes
    expire = _now() + timedelta(minutes=minutes)
    to_encode: dict = {"sub": str(subject), "exp": expire}
    if scope:
        to_encode["scope"] = scope
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def create_refresh_token(subject: Union[int, str]) -> str:
    expire = _now() + timedelta(minutes=settings.refresh_token_expire_minutes)
    to_encode = {"sub": str(subject), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        raise


async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await user_repo.get_user_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def register_user(db: AsyncSession, email: str, password: str):
    existing = await user_repo.get_user_by_email(db, email=email)
    if existing:
        return None
    hashed = get_password_hash(password)
    user = await user_repo.create_user(db, email=email, hashed_password=hashed)
    return user


# ---------------------------------------------------------------------------
# Token blacklist (prevents use of revoked / logged-out tokens)
# Uses Redis when available, falls back to an in-memory set.
# ---------------------------------------------------------------------------

_token_blacklist_memory: set[str] = set()


async def add_to_blacklist(token: str, expire_seconds: int) -> None:
    """Add a JWT to the blacklist. Called on logout."""
    try:
        from app.core.config import settings as _cfg
        if _cfg.redis_url:
            import redis.asyncio as _aioredis
            _r = _aioredis.from_url(_cfg.redis_url, decode_responses=True)
            await _r.setex(f"blacklist:{token}", expire_seconds, "1")
            await _r.aclose()
            return
    except Exception:
        pass
    _token_blacklist_memory.add(token)


async def is_blacklisted(token: str) -> bool:
    """Return True if the token has been revoked."""
    try:
        from app.core.config import settings as _cfg
        if _cfg.redis_url:
            import redis.asyncio as _aioredis
            _r = _aioredis.from_url(_cfg.redis_url, decode_responses=True)
            result = await _r.exists(f"blacklist:{token}")
            await _r.aclose()
            return bool(result)
    except Exception:
        pass
    return token in _token_blacklist_memory
