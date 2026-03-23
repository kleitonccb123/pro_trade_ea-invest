"""
Unit Tests — Gamification Service
===================================

Tests GameProfile creation, point calculations, and robot unlock costs.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from app.gamification.service import (
    GameProfileService,
    ELITE_ROBOTS,
    ROBOT_UNLOCK_COST,
    VALID_ROBOT_IDS,
    MAX_STREAK_BONUS,
)


class TestConstants:
    def test_elite_robots_defined(self):
        assert len(ELITE_ROBOTS) == 3

    def test_unlock_costs_defined(self):
        assert ROBOT_UNLOCK_COST["elite"] > ROBOT_UNLOCK_COST["common"]
        assert ROBOT_UNLOCK_COST["elite"] == 1500
        assert ROBOT_UNLOCK_COST["common"] == 500

    def test_valid_robot_ids_not_empty(self):
        assert len(VALID_ROBOT_IDS) == 20

    def test_max_streak_bonus(self):
        assert MAX_STREAK_BONUS == 10


class TestGetOrCreateProfile:
    async def test_creates_new_profile_when_none_exists(self):
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="gp_id_123")
        )

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("app.gamification.service.get_db", return_value=mock_db):
            profile = await GameProfileService.get_or_create_profile("user_abc")

        assert profile.user_id == "user_abc"
        assert profile.level == 1
        assert profile.xp == 0
        assert profile.trade_points > 0  # plan-based (varies by license)

    async def test_returns_existing_profile(self):
        existing = {
            "_id": "existing_gp_id",
            "user_id": "user_abc",
            "trade_points": 2500,
            "level": 5,
            "xp": 450,
            "unlocked_robots": ["bot_001"],
            "lifetime_profit": 1234.56,
            "last_daily_chest_opened": None,
            "streak_count": 3,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=existing)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("app.gamification.service.get_db", return_value=mock_db):
            profile = await GameProfileService.get_or_create_profile("user_abc")

        assert profile.user_id == "user_abc"
        assert profile.trade_points == 2500
        assert profile.level == 5
        assert "bot_001" in profile.unlocked_robots

    async def test_handles_db_error_gracefully(self):
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(side_effect=Exception("DB down"))

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("app.gamification.service.get_db", return_value=mock_db):
            profile = await GameProfileService.get_or_create_profile("user_err")

        # Should return default profile, not crash
        assert profile.user_id == "user_err"
        assert profile.level == 1
