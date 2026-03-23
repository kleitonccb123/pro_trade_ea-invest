"""
Integration Tests — Robot Marketplace Endpoints  (PEND-14)
===========================================================

Tests:
  POST  /marketplace/robots/{id}/purchase
  GET   /marketplace/robots/{id}/performance
  POST  /marketplace/robots/{id}/review
  GET   /marketplace/robots/{id}/reviews
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

os.environ.setdefault("APP_MODE", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-marketplace")
os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_app():
    from app.main import app
    return app


def _make_token(user_id: str = "user_mkt_001") -> str:
    from jose import jwt as jose_jwt
    return jose_jwt.encode(
        {"sub": user_id, "type": "access"},
        "test-secret-for-marketplace",
        algorithm="HS256",
    )


def _auth_headers(user_id: str = "user_mkt_001") -> dict:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _mock_user(user_id: str = "user_mkt_001"):
    return {
        "id": user_id,
        "email": f"{user_id}@test.com",
        "name": "MKT Tester",
        "is_active": True,
        "hashed_password": "x",
        "plan": "PRO+",
    }


def _mock_profile(user_id: str, include_robot: str | None = None):
    unlocked = [include_robot] if include_robot else []
    return {
        "user_id": user_id,
        "trade_points": 5000,
        "level": 3,
        "xp": 300,
        "unlocked_robots": unlocked,
        "achievements": [],
    }


# ── POST /marketplace/robots/{id}/purchase ───────────────────────────────────

class TestRobotPurchase:
    """POST /api/marketplace/robots/{id}/purchase"""

    async def test_purchase_success(self):
        app = _make_app()
        user_id = "user_mkt_buy_001"
        robot_id = "bot_005"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_purchases = AsyncMock()
        mock_purchases.insert_one = AsyncMock(return_value=MagicMock(inserted_id="purchase_id_1"))
        mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
            "users": mock_users,
            "robot_purchases": mock_purchases,
        }.get(k, AsyncMock()))
        mock_db.users = mock_users
        mock_db.robot_purchases = mock_purchases

        # Mock the unlock logic to succeed
        unlock_result = MagicMock()
        unlock_result.success = True
        unlock_result.message = "Robot unlocked!"
        unlock_result.new_trade_points = 3500
        unlock_result.unlock_cost = 500

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db), \
             patch(
                 "app.marketplace.robots_router.GameProfileService.unlock_robot_logic",
                 new_callable=AsyncMock,
                 return_value=unlock_result,
             ):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    f"/api/marketplace/robots/{robot_id}/purchase",
                    headers=_auth_headers(user_id),
                )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["robot_id"] == robot_id
        assert "performance_preview" in data

    async def test_purchase_invalid_robot(self):
        app = _make_app()
        user_id = "user_mkt_buy_002"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/marketplace/robots/bot_999_invalid/purchase",
                    headers=_auth_headers(user_id),
                )

        assert resp.status_code == 404

    async def test_purchase_insufficient_points(self):
        app = _make_app()
        user_id = "user_mkt_buy_003"
        robot_id = "bot_001"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        from fastapi import HTTPException

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db), \
             patch(
                 "app.marketplace.robots_router.GameProfileService.unlock_robot_logic",
                 new_callable=AsyncMock,
                 side_effect=HTTPException(status_code=402, detail="Pontos insuficientes"),
             ):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    f"/api/marketplace/robots/{robot_id}/purchase",
                    headers=_auth_headers(user_id),
                )

        assert resp.status_code == 402

    async def test_purchase_unauthenticated(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/api/marketplace/robots/bot_001/purchase")

        assert resp.status_code in (401, 403)


# ── GET /marketplace/robots/{id}/performance ─────────────────────────────────

class TestRobotPerformance:
    """GET /api/marketplace/robots/{id}/performance"""

    async def test_performance_returns_data(self):
        app = _make_app()
        user_id = "user_mkt_perf_001"
        robot_id = "bot_003"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_rankings = AsyncMock()
        mock_rankings.find_one = AsyncMock(return_value=None)  # no DB data → deterministic
        mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
            "users": mock_users,
            "robot_rankings": mock_rankings,
        }.get(k, AsyncMock()))
        mock_db.users = mock_users
        mock_db.robot_rankings = mock_rankings

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(
                    f"/api/marketplace/robots/{robot_id}/performance",
                    headers=_auth_headers(user_id),
                )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["robot_id"] == robot_id
        assert "data_points" in data
        assert len(data["data_points"]) == 30
        assert "total_return_pct" in data
        assert "win_rate" in data
        assert "max_drawdown_pct" in data

    async def test_performance_invalid_robot(self):
        app = _make_app()
        user_id = "user_mkt_perf_002"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(
                    "/api/marketplace/robots/bot_not_real/performance",
                    headers=_auth_headers(user_id),
                )

        assert resp.status_code == 404

    async def test_performance_unauthenticated(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/marketplace/robots/bot_001/performance")

        assert resp.status_code in (401, 403)


# ── POST /marketplace/robots/{id}/review ─────────────────────────────────────

class TestRobotReview:
    """POST /api/marketplace/robots/{id}/review"""

    async def test_review_success(self):
        app = _make_app()
        user_id = "user_mkt_rev_001"
        robot_id = "bot_002"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_profiles = AsyncMock()
        # Profile has the robot unlocked
        mock_profiles.find_one = AsyncMock(return_value=_mock_profile(user_id, robot_id))
        mock_reviews = AsyncMock()
        mock_reviews.find_one = AsyncMock(return_value=None)  # no existing review
        mock_reviews.replace_one = AsyncMock()
        mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
            "users": mock_users,
            "game_profiles": mock_profiles,
            "robot_reviews": mock_reviews,
        }.get(k, AsyncMock()))
        mock_db.users = mock_users
        mock_db.game_profiles = mock_profiles
        mock_db.robot_reviews = mock_reviews

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    f"/api/marketplace/robots/{robot_id}/review",
                    headers=_auth_headers(user_id),
                    json={"rating": 5, "comment": "Excelente robô!"},
                )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["robot_id"] == robot_id
        assert data["rating"] == 5

    async def test_review_invalid_rating(self):
        app = _make_app()
        user_id = "user_mkt_rev_002"
        robot_id = "bot_002"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_profiles = AsyncMock()
        mock_profiles.find_one = AsyncMock(return_value=_mock_profile(user_id, robot_id))
        mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
            "users": mock_users,
            "game_profiles": mock_profiles,
        }.get(k, AsyncMock()))
        mock_db.users = mock_users
        mock_db.game_profiles = mock_profiles

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    f"/api/marketplace/robots/{robot_id}/review",
                    headers=_auth_headers(user_id),
                    json={"rating": 10, "comment": "Too high rating"},  # invalid: >5
                )

        assert resp.status_code == 422

    async def test_review_robot_not_owned(self):
        app = _make_app()
        user_id = "user_mkt_rev_003"
        robot_id = "bot_001"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_profiles = AsyncMock()
        # Profile does NOT have the robot unlocked
        mock_profiles.find_one = AsyncMock(return_value=_mock_profile(user_id, include_robot=None))
        mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
            "users": mock_users,
            "game_profiles": mock_profiles,
        }.get(k, AsyncMock()))
        mock_db.users = mock_users
        mock_db.game_profiles = mock_profiles

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    f"/api/marketplace/robots/{robot_id}/review",
                    headers=_auth_headers(user_id),
                    json={"rating": 4, "comment": "Good"},
                )

        assert resp.status_code == 403

    async def test_review_unauthenticated(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/marketplace/robots/bot_001/review",
                json={"rating": 3, "comment": "test"},
            )

        assert resp.status_code in (401, 403)


# ── GET /marketplace/robots/{id}/reviews ─────────────────────────────────────

class TestRobotReviews:
    """GET /api/marketplace/robots/{id}/reviews"""

    async def test_reviews_listed(self):
        app = _make_app()
        user_id = "user_mkt_list_001"
        robot_id = "bot_004"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_reviews = AsyncMock()
        # Return a cursor-like with to_list
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[
            {"user_id": "u1", "robot_id": robot_id, "rating": 5, "comment": "Great!", "created_at": "2026-03-01T00:00:00Z"},
            {"user_id": "u2", "robot_id": robot_id, "rating": 4, "comment": "Good",   "created_at": "2026-03-02T00:00:00Z"},
        ])
        mock_reviews.find = MagicMock(return_value=mock_cursor)
        mock_db.__getitem__ = MagicMock(side_effect=lambda k: {
            "users": mock_users,
            "robot_reviews": mock_reviews,
        }.get(k, AsyncMock()))
        mock_db.users = mock_users
        mock_db.robot_reviews = mock_reviews

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(
                    f"/api/marketplace/robots/{robot_id}/reviews",
                    headers=_auth_headers(user_id),
                )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["robot_id"] == robot_id
        assert len(data["reviews"]) == 2
        assert data["avg_rating"] == pytest.approx(4.5, 0.01)

    async def test_reviews_invalid_robot(self):
        app = _make_app()
        user_id = "user_mkt_list_002"

        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
        mock_db.__getitem__ = MagicMock(return_value=mock_users)
        mock_db.users = mock_users

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.marketplace.robots_router.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get(
                    "/api/marketplace/robots/bot_not_real/reviews",
                    headers=_auth_headers(user_id),
                )

        assert resp.status_code == 404
