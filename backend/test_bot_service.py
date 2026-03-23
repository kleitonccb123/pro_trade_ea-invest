"""
Unit Tests for BotService
==========================

Tests the complete BotService functionality including:
- Bot creation
- Bot retrieval and listing
- Bot status updates
- Bot statistics updates
- Bot deletion with validation
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.db.bot_service import BotService
from app.db.models import BotStatus, Bot


class TestBotServiceCreate:
    """Test bot creation functionality."""
    
    @pytest.mark.asyncio
    async def test_create_bot_basic(self, sample_bot_data, mock_bots_collection):
        """Test creating a basic bot."""
        # Setup
        mock_bots_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        service = BotService(mock_bots_collection)
        
        # Execute
        bot = await service.create_bot(**sample_bot_data)
        
        # Verify
        assert bot is not None
        assert bot.user_id == "test_user_123"
        assert bot.name == "Test Bot"
        assert bot.status == BotStatus.STOPPED
        assert bot.trades_count == 0
        assert bot.total_pnl == Decimal("0")
        mock_bots_collection.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_bot_with_config(self, sample_bot_data, mock_bots_collection):
        """Test creating a bot with custom configuration."""
        mock_bots_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )
        service = BotService(mock_bots_collection)
        
        sample_bot_data["config"]["custom_param"] = "custom_value"
        bot = await service.create_bot(**sample_bot_data)
        
        assert bot.config["custom_param"] == "custom_value"


class TestBotServiceRetrieve:
    """Test bot retrieval functionality."""
    
    @pytest.mark.asyncio
    async def test_get_bot_success(self, sample_bot, mock_bots_collection):
        """Test retrieving an existing bot."""
        bot_id = ObjectId()
        mock_bots_collection.find_one = AsyncMock(return_value=sample_bot.model_dump())
        service = BotService(mock_bots_collection)
        
        result = await service.get_bot(str(bot_id), "test_user_123")
        
        assert result is not None
        mock_bots_collection.find_one.assert_called_once()
        # Verify query includes ownership check
        call_args = mock_bots_collection.find_one.call_args
        assert "_id" in call_args[0][0]
        assert "user_id" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_get_bot_not_found(self, mock_bots_collection):
        """Test retrieving a non-existent bot."""
        mock_bots_collection.find_one = AsyncMock(return_value=None)
        service = BotService(mock_bots_collection)
        
        result = await service.get_bot("nonexistent_id", "test_user_123")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_bots_for_user(self, sample_bot_data, mock_bots_collection):
        """Test listing all bots for a user."""
        # Create multiple bot docs
        bot1_doc = sample_bot_data.copy()
        bot2_doc = sample_bot_data.copy()
        bot2_doc["name"] = "Bot 2"
        
        # Mock cursor behavior
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([bot1_doc, bot2_doc])
        mock_bots_collection.find = MagicMock(return_value=mock_cursor)
        
        service = BotService(mock_bots_collection)
        result = await service.list_bots("test_user_123")
        
        # Verify query filters by user_id
        mock_bots_collection.find.assert_called_once()
        call_args = mock_bots_collection.find.call_args[0][0]
        assert call_args["user_id"] == "test_user_123"
    
    @pytest.mark.asyncio
    async def test_list_bots_with_status_filter(self, sample_bot_data, mock_bots_collection):
        """Test listing bots filtered by status."""
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([])
        mock_bots_collection.find = MagicMock(return_value=mock_cursor)
        
        service = BotService(mock_bots_collection)
        await service.list_bots("test_user_123", status=BotStatus.RUNNING)
        
        # Verify query includes status filter
        call_args = mock_bots_collection.find.call_args[0][0]
        assert call_args["status"] == BotStatus.RUNNING.value


class TestBotServiceUpdate:
    """Test bot update functionality."""
    
    @pytest.mark.asyncio
    async def test_update_bot_status(self, mock_bots_collection):
        """Test updating bot status."""
        mock_bots_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        service = BotService(mock_bots_collection)
        
        bot_id = "test_bot_123"
        success = await service.update_bot_status(bot_id, "test_user_123", BotStatus.RUNNING)
        
        assert success is True
        mock_bots_collection.update_one.assert_called_once()
        # Verify update includes started_at timestamp
        call_args = mock_bots_collection.update_one.call_args[0]
        assert "started_at" in call_args[1]["$set"]
    
    @pytest.mark.asyncio
    async def test_update_bot_statistics(self, mock_bots_collection):
        """Test updating bot trading statistics."""
        mock_bots_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        service = BotService(mock_bots_collection)
        
        success = await service.update_bot_statistics(
            "test_bot_123",
            "test_user_123",
            trades_count=42,
            total_pnl=Decimal("1234.56")
        )
        
        assert success is True
        # Verify all statistics are updated
        call_args = mock_bots_collection.update_one.call_args[0]
        update_doc = call_args[1]["$set"]
        assert update_doc["trades_count"] == 42
        assert update_doc["total_pnl"] == Decimal("1234.56")
    
    @pytest.mark.asyncio
    async def test_update_bot_config_success(self, mock_bots_collection):
        """Test updating bot configuration (allowed when stopped)."""
        # Mock find_one to return a stopped bot
        mock_bots_collection.find_one = AsyncMock(
            return_value={"status": BotStatus.STOPPED.value}
        )
        mock_bots_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        service = BotService(mock_bots_collection)
        
        new_config = {"interval": "30m", "amount": 500}
        success = await service.update_bot_config(
            "test_bot_123",
            "test_user_123",
            new_config
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_update_bot_config_blocked_when_running(self, mock_bots_collection):
        """Test that bot config cannot be updated while running."""
        # Mock find_one to return a running bot
        mock_bots_collection.find_one = AsyncMock(
            return_value={"status": BotStatus.RUNNING.value}
        )
        service = BotService(mock_bots_collection)
        
        new_config = {"interval": "30m"}
        success = await service.update_bot_config(
            "test_bot_123",
            "test_user_123",
            new_config
        )
        
        assert success is False


class TestBotServiceDelete:
    """Test bot deletion functionality."""
    
    @pytest.mark.asyncio
    async def test_delete_bot_success(self, mock_bots_collection):
        """Test deleting a bot that is stopped."""
        # Mock find_one to return a stopped bot
        mock_bots_collection.find_one = AsyncMock(
            return_value={"status": BotStatus.STOPPED.value}
        )
        mock_bots_collection.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )
        service = BotService(mock_bots_collection)
        
        success = await service.delete_bot("test_bot_123", "test_user_123")
        
        assert success is True
        mock_bots_collection.delete_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_bot_fails_if_running(self, mock_bots_collection):
        """Test that running bots cannot be deleted."""
        # Mock find_one to return a running bot
        mock_bots_collection.find_one = AsyncMock(
            return_value={"status": BotStatus.RUNNING.value}
        )
        service = BotService(mock_bots_collection)
        
        success = await service.delete_bot("test_bot_123", "test_user_123")
        
        assert success is False
        # Verify delete was not called
        mock_bots_collection.delete_one.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_bot(self, mock_bots_collection):
        """Test deleting a bot that doesn't exist."""
        mock_bots_collection.find_one = AsyncMock(return_value=None)
        service = BotService(mock_bots_collection)
        
        success = await service.delete_bot("nonexistent_id", "test_user_123")
        
        assert success is False


class TestBotServiceOwnershipValidation:
    """Test ownership validation in all bot operations."""
    
    @pytest.mark.asyncio
    async def test_get_bot_ownership_check(self, mock_bots_collection):
        """Test that bot retrieval checks user ownership."""
        mock_bots_collection.find_one = AsyncMock(return_value=None)
        service = BotService(mock_bots_collection)
        
        # Try to get user1's bot as user2
        result = await service.get_bot("bot123", "other_user")
        
        # Should not find the bot (different user)
        assert result is None
        # Verify the query included both _id and user_id
        call_args = mock_bots_collection.find_one.call_args[0][0]
        assert "user_id" in call_args
        assert call_args["user_id"] == "other_user"
    
    @pytest.mark.asyncio
    async def test_list_bots_per_user_isolation(self, mock_bots_collection):
        """Test that listing bots only returns user's own bots."""
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter([])
        mock_bots_collection.find = MagicMock(return_value=mock_cursor)
        
        service = BotService(mock_bots_collection)
        await service.list_bots("user_123")
        
        # Verify query filters by exact user_id
        call_args = mock_bots_collection.find.call_args[0][0]
        assert call_args["user_id"] == "user_123"


class TestBotServiceIntegration:
    """Integration tests for BotService workflows."""
    
    @pytest.mark.asyncio
    async def test_full_bot_lifecycle(self, sample_bot_data, mock_bots_collection):
        """Test a complete bot lifecycle: create → start → update stats → stop → delete."""
        # Setup mock responses for each operation
        bot_id = ObjectId()
        
        # Create
        mock_bots_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=bot_id)
        )
        # Get
        mock_bots_collection.find_one = AsyncMock(
            return_value={
                **sample_bot_data,
                "_id": bot_id,
                "status": BotStatus.STOPPED.value
            }
        )
        # Update status
        mock_bots_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        # Delete
        mock_bots_collection.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )
        
        service = BotService(mock_bots_collection)
        
        # Lifecycle operations
        bot = await service.create_bot(**sample_bot_data)
        assert bot is not None
        
        await service.update_bot_status(str(bot_id), "test_user_123", BotStatus.RUNNING)
        await service.update_bot_statistics(str(bot_id), "test_user_123", 5, Decimal("100"))
        await service.update_bot_status(str(bot_id), "test_user_123", BotStatus.STOPPED)
        success = await service.delete_bot(str(bot_id), "test_user_123")
        
        assert success is True
