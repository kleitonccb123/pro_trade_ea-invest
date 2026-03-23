"""
Shared Test Fixtures — conftest.py
===================================

Provides:
- MockDatabase / MockCollection for MongoDB isolation
- Fake user data and JWT tokens
- FastAPI TestClient with dependency overrides
- Async event loop configuration
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend source is on the path
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

# Pre-set env vars BEFORE any app imports
os.environ.setdefault("APP_MODE", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("ENCRYPTION_KEY", "k1cTQzwPY4AYGTW4K5DQT_d8RGdX8oYFI2Hn1ND5UAU=")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "k1cTQzwPY4AYGTW4K5DQT_d8RGdX8oYFI2Hn1ND5UAU=")
os.environ.setdefault("STRATEGY_ENCRYPTION_KEY", "k1cTQzwPY4AYGTW4K5DQT_d8RGdX8oYFI2Hn1ND5UAU=")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "fake-google-client-id.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-google-secret")


# ---------------------------------------------------------------------------
# In-memory MockDatabase (reuses app.core.database.MockDatabase)
# ---------------------------------------------------------------------------
from app.core.database import MockDatabase, _mock_data


@pytest.fixture(autouse=True)
def _clear_mock_data():
    """Reset the global mock data store between tests."""
    _mock_data.clear()
    yield
    _mock_data.clear()


@pytest.fixture()
def mock_db():
    """Return a fresh MockDatabase instance."""
    return MockDatabase("test_db")


# ---------------------------------------------------------------------------
# Fake user helpers
# ---------------------------------------------------------------------------
TEST_USER_ID = "665f0c0a1234567890abcdef"
TEST_USER_EMAIL = "test@cryptotradehub.com"
TEST_USER_NAME = "Test User"
TEST_USER_PASSWORD = "StrongP@ss1"


@pytest.fixture()
def fake_user():
    """Minimal user dict as it would come from the database."""
    from app.core.security import get_password_hash

    return {
        "_id": TEST_USER_ID,
        "id": TEST_USER_ID,
        "email": TEST_USER_EMAIL,
        "name": TEST_USER_NAME,
        "hashed_password": get_password_hash(TEST_USER_PASSWORD),
        "is_active": True,
        "created_at": datetime.utcnow(),
        "plan": "free",
    }


# ---------------------------------------------------------------------------
# JWT token helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def access_token():
    """Create a valid JWT access token for the test user."""
    from app.auth.service import create_access_token

    return create_access_token(subject=TEST_USER_ID)


@pytest.fixture()
def auth_header(access_token):
    """Authorization header dict ready for TestClient requests."""
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture()
def expired_token():
    """Create an expired JWT token."""
    from jose import jwt
    from app.core.config import settings

    payload = {
        "sub": TEST_USER_ID,
        "exp": datetime.utcnow() - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.algorithm)


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------
@pytest.fixture()
def app():
    """Create a fresh FastAPI app with dependency overrides."""
    # Patch local_db so get_current_user resolves without real SQLite
    with patch("app.core.local_db_manager.get_local_db") as mock_get_local_db:
        mock_local_db = AsyncMock()
        mock_local_db.find_user_by_id = AsyncMock(
            return_value={
                "_id": TEST_USER_ID,
                "id": TEST_USER_ID,
                "email": TEST_USER_EMAIL,
                "name": TEST_USER_NAME,
                "hashed_password": "unused-in-fixture",
                "is_active": True,
                "plan": "free",
            }
        )
        mock_get_local_db.return_value = mock_local_db

        # Patch get_db to return an in-memory mock
        with patch("app.core.database.get_db") as mock_get_db:
            _test_db = MockDatabase("test_db")
            mock_get_db.return_value = _test_db

            # Import app *inside* patches so startup doesn't hit real DBs
            from app.main import app as _app

            yield _app


@pytest.fixture()
def client(app):
    """Synchronous TestClient for integration tests."""
    from httpx import ASGITransport, AsyncClient

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Utility: seed mock database with user
# ---------------------------------------------------------------------------
@pytest.fixture()
async def seeded_db(mock_db, fake_user):
    """Insert the fake user into the mock DB and return the DB."""
    await mock_db.users.insert_one(fake_user)
    return mock_db
