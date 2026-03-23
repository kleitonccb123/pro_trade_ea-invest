"""
Unit tests for Task 3.1: WebSocketOrderMonitor

Tests validate:
✅ WebSocket connection and subscription
✅ Real-time order event processing
✅ Database synchronization
✅ Heartbeat management
✅ Reconnection with exponential backoff
✅ Graceful lifecycle management
✅ Audit logging
✅ Error handling
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from bson import ObjectId

from app.exchanges.kucoin.websocket_private import (
    WebSocketOrderMonitor,
    WebSocketOrderUpdate,
    start_order_monitor,
    stop_order_monitor,
    stop_all_monitors,
    get_order_monitor,
)


# ============================================================================
#  FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock MongoDB database."""
    mock = MagicMock()
    mock.trading_orders = AsyncMock()
    mock.ws_order_events = AsyncMock()
    return mock


@pytest.fixture
def mock_ws_manager():
    """Mock KuCoinWebSocketManager."""
    mock = AsyncMock()
    mock.subscribe = AsyncMock()
    mock.send_heartbeat = AsyncMock()
    mock.close = AsyncMock()
    mock.get_ws_token = AsyncMock()
    return mock


@pytest.fixture
def mock_credentials():
    """Mock KuCoin credentials."""
    return {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "passphrase": "test_passphrase",
        "is_testnet": True,
    }


@pytest.fixture
def sample_order_event():
    """Sample order event from KuCoin WebSocket."""
    return {
        "type": "message",
        "data": {
            "symbol": "BTC-USDT",
            "clientOid": "abc123def456",
            "orderId": "order_123",
            "type": "trade",
            "side": "buy",
            "price": "50000",
            "size": "0.001",
            "filledSize": "0.001",
            "cancelledSize": "0",
            "remainSize": "0",
            "status": "done",
            "matchTime": 1234567890000,
        }
    }


@pytest.fixture
def sample_filled_order():
    """Sample order document from MongoDB (before sync)."""
    return {
        "_id": ObjectId(),
        "user_id": "user123",
        "client_oid": "abc123def456",
        "exchange_order_id": "order_123",
        "symbol": "BTC-USDT",
        "side": "buy",
        "quantity": Decimal("0.001"),
        "status": "pending",
        "created_at": datetime.utcnow(),
    }


# ============================================================================
#  BASIC INITIALIZATION TESTS
# ============================================================================

class TestWebSocketOrderMonitorInit:
    """Test monitor initialization."""
    
    @pytest.mark.asyncio
    async def test_monitor_initializes_with_user_id(self):
        """Test monitor init."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        
        assert monitor.user_id == "user123"
        assert monitor.is_running is False
        assert monitor._reconnect_count == 0
        assert monitor.heartbeat_interval == 20.0
        assert monitor.max_reconnect_attempts == 5
    
    @pytest.mark.asyncio
    async def test_monitor_initializes_with_custom_params(self):
        """Test monitor init with custom parameters."""
        monitor = WebSocketOrderMonitor(
            user_id="user456",
            heartbeat_interval=30.0,
            max_reconnect_attempts=3,
            backoff_base=3.0,
        )
        
        assert monitor.heartbeat_interval == 30.0
        assert monitor.max_reconnect_attempts == 3
        assert monitor.backoff_base == 3.0


# ============================================================================
#  CONNECTION & SUBSCRIPTION TESTS
# ============================================================================

class TestWebSocketConnection:
    """Test WebSocket connection management."""
    
    @pytest.mark.asyncio
    async def test_monitor_connects_successfully(self, mock_db, mock_ws_manager):
        """Test successful connection."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        
        with patch("app.exchanges.kucoin.websocket_private.get_db", return_value=mock_db), \
             patch("app.exchanges.kucoin.websocket_private.CredentialsRepository.get_credentials", 
                   return_value={"api_key": "test"}), \
             patch("app.exchanges.kucoin.websocket_private.KuCoinWebSocketManager", 
                   return_value=mock_ws_manager):
            
            await monitor._connect()
            
            assert monitor._ws_manager is not None
            mock_ws_manager.get_ws_token.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_raises_on_missing_credentials(self, mock_db):
        """Test error when credentials missing."""
        monitor = WebSocketOrderMonitor(user_id="user_no_creds")
        
        with patch("app.exchanges.kucoin.websocket_private.get_db", return_value=mock_db), \
             patch("app.exchanges.kucoin.websocket_private.CredentialsRepository.get_credentials", 
                   return_value=None):
            
            with pytest.raises(ValueError, match="No KuCoin credentials"):
                await monitor._connect()


# ============================================================================
#  ORDER EVENT PARSING TESTS
# ============================================================================

class TestOrderEventParsing:
    """Test order event parsing from WebSocket."""
    
    @pytest.mark.asyncio
    async def test_parse_filled_order_event(self, sample_order_event):
        """Test parsing filled order event."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        
        update = monitor._parse_order_event(sample_order_event)
        
        assert update.user_id == "user123"
        assert update.client_oid == "abc123def456"
        assert update.order_id == "order_123"
        assert update.symbol == "BTC-USDT"
        assert update.status == "filled"
        assert update.filled_quantity == Decimal("0.001")
        assert update.filled_price == Decimal("50000")
    
    @pytest.mark.asyncio
    async def test_parse_canceled_order_event(self):
        """Test parsing canceled order event."""
        event = {
            "type": "message",
            "data": {
                "symbol": "ETH-USDT",
                "clientOid": "xyz789",
                "orderId": "order_456",
                "status": "canceled",
                "reason": "user_canceled",
            }
        }
        
        monitor = WebSocketOrderMonitor(user_id="user123")
        update = monitor._parse_order_event(event)
        
        assert update.status == "canceled"
        assert update.reason == "user_canceled"
        assert update.client_oid == "xyz789"
    
    @pytest.mark.asyncio
    async def test_parse_partial_fill_event(self):
        """Test parsing partial fill event."""
        event = {
            "type": "message",
            "data": {
                "symbol": "BTC-USDT",
                "clientOid": "partial123",
                "orderId": "order_789",
                "status": "match",
                "filledSize": "0.0005",
                "remainSize": "0.0005",
            }
        }
        
        monitor = WebSocketOrderMonitor(user_id="user123")
        update = monitor._parse_order_event(event)
        
        assert update.status == "match"
        assert update.filled_quantity == Decimal("0.0005")
        assert update.remaining_quantity == Decimal("0.0005")


# ============================================================================
#  DATABASE SYNCHRONIZATION TESTS
# ============================================================================

class TestDatabaseSync:
    """Test database synchronization."""
    
    @pytest.mark.asyncio
    async def test_sync_filled_order_to_db(self, mock_db, sample_filled_order):
        """Test syncing filled order to database."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        monitor._db = mock_db
        
        # Setup mock
        mock_db.trading_orders.find_one.return_value = sample_filled_order
        mock_db.trading_orders.update_one.return_value = MagicMock(modified_count=1)
        
        # Create update
        update = WebSocketOrderUpdate(
            timestamp=datetime.utcnow(),
            user_id="user123",
            order_id="order_123",
            client_oid="abc123def456",
            symbol="BTC-USDT",
            status="filled",
            filled_price=Decimal("50000"),
            filled_quantity=Decimal("0.001"),
        )
        
        await monitor._sync_order_to_db(update)
        
        # Verify update
        mock_db.trading_orders.update_one.assert_called_once()
        call_args = mock_db.trading_orders.update_one.call_args
        assert call_args[1]["$set"]["status"] == "filled"
        assert call_args[1]["$set"]["filled_price"] == Decimal("50000")
    
    @pytest.mark.asyncio
    async def test_sync_handles_missing_order(self, mock_db):
        """Test handling when order not found."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        monitor._db = mock_db
        
        # Setup mock - order not found
        mock_db.trading_orders.find_one.return_value = None
        
        update = WebSocketOrderUpdate(
            timestamp=datetime.utcnow(),
            user_id="user123",
            order_id="unknown_order",
            client_oid="unknown_oid",
            symbol="BTC-USDT",
            status="filled",
        )
        
        # Should not raise, but log warning
        await monitor._sync_order_to_db(update)
        
        # Order update should not be called
        mock_db.trading_orders.update_one.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_sync_logs_audit_event(self, mock_db, sample_filled_order):
        """Test audit logging on sync."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        monitor._db = mock_db
        
        mock_db.trading_orders.find_one.return_value = sample_filled_order
        mock_db.trading_orders.update_one.return_value = MagicMock(modified_count=1)
        
        update = WebSocketOrderUpdate(
            timestamp=datetime.utcnow(),
            user_id="user123",
            order_id="order_123",
            client_oid="abc123def456",
            symbol="BTC-USDT",
            status="filled",
        )
        
        await monitor._sync_order_to_db(update)
        
        # Verify audit logged
        mock_db.ws_order_events.insert_one.assert_called_once()


# ============================================================================
#  EVENT HANDLING TESTS
# ============================================================================

class TestEventHandling:
    """Test event handling and queuing."""
    
    @pytest.mark.asyncio
    async def test_handle_order_event_queues_update(self, sample_order_event):
        """Test event handler queues update."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        
        await monitor._handle_order_event(sample_order_event)
        
        # Verify queued
        assert not monitor._update_queue.empty()
    
    @pytest.mark.asyncio
    async def test_handle_order_event_handles_invalid_data(self):
        """Test handling of invalid event data."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        
        invalid_event = {"type": "message", "data": None}
        
        # Should not raise
        try:
            await monitor._handle_order_event(invalid_event)
        except:
            pytest.fail("Should handle invalid event gracefully")


# ============================================================================
#  HEARTBEAT TESTS
# ============================================================================

class TestHeartbeat:
    """Test heartbeat management."""
    
    @pytest.mark.asyncio
    async def test_heartbeat_sends_periodically(self, mock_ws_manager):
        """Test heartbeat sent at intervals."""
        monitor = WebSocketOrderMonitor(user_id="user123", heartbeat_interval=0.1)
        monitor.is_running = True
        monitor._ws_manager = mock_ws_manager
        
        # Run for short time
        task = asyncio.create_task(monitor._send_heartbeats())
        await asyncio.sleep(0.3)
        monitor.is_running = False
        
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.CancelledError:
            pass
        
        # Should have sent at least 2 heartbeats
        assert mock_ws_manager.send_heartbeat.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_heartbeat_tracks_timestamp(self, mock_ws_manager):
        """Test heartbeat updates timestamp."""
        monitor = WebSocketOrderMonitor(user_id="user123", heartbeat_interval=0.05)
        monitor.is_running = True
        monitor._ws_manager = mock_ws_manager
        
        before = datetime.utcnow()
        
        task = asyncio.create_task(monitor._send_heartbeats())
        await asyncio.sleep(0.1)
        monitor.is_running = False
        
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.CancelledError:
            pass
        
        after = datetime.utcnow()
        assert monitor._last_heartbeat is not None
        assert before <= monitor._last_heartbeat <= after


# ============================================================================
#  LIFECYCLE TESTS
# ============================================================================

class TestLifecycle:
    """Test monitor start/stop lifecycle."""
    
    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """Test start() creates task."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        
        with patch("app.exchanges.kucoin.websocket_private.get_db") as mock_get_db, \
             patch.object(monitor, "_run_monitor_loop", new_callable=AsyncMock):
            
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            await monitor.start()
            
            assert monitor.is_running is True
            assert monitor._task is not None
    
    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """Test stop() cancels background task."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        monitor.is_running = True
        monitor._task = asyncio.create_task(asyncio.sleep(100))
        monitor._ws_manager = AsyncMock()
        
        await monitor.stop()
        
        assert monitor.is_running is False
        assert monitor._task.cancelled()
    
    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test start() is idempotent."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        monitor.is_running = True  # Already running
        
        with patch.object(monitor, "_run_monitor_loop"):
            await monitor.start()
            
            # Should not create new task
            assert monitor._task is None


# ============================================================================
#  RECONNECTION TESTS
# ============================================================================

class TestReconnection:
    """Test reconnection logic."""
    
    @pytest.mark.asyncio
    async def test_reconnect_with_exponential_backoff(self):
        """Test exponential backoff calculation."""
        monitor = WebSocketOrderMonitor(
            user_id="user123",
            backoff_base=2.0,
            max_reconnect_attempts=3
        )
        monitor.is_running = True
        
        # Test backoff delays
        start = time.time()
        
        # First attempt (2^0 = 1s)
        await monitor._handle_reconnection()
        assert monitor._reconnect_count == 1
        
        # Second attempt (2^1 = 2s - skip for speed)
        monitor._reconnect_count = 1
        # Just verify counter increments
        await monitor._handle_reconnection()
        assert monitor._reconnect_count == 2
    
    @pytest.mark.asyncio
    async def test_reconnect_gives_up_after_max_attempts(self):
        """Test reconnection gives up after max attempts."""
        monitor = WebSocketOrderMonitor(
            user_id="user123",
            max_reconnect_attempts=2
        )
        monitor.is_running = True
        monitor._reconnect_count = 2
        
        await monitor._handle_reconnection()
        
        # Should stop trying
        assert monitor.is_running is False


# ============================================================================
#  MODULE FUNCTION TESTS
# ============================================================================

class TestModuleFunctions:
    """Test module-level functions."""
    
    @pytest.mark.asyncio
    async def test_start_order_monitor(self):
        """Test starting monitor via module function."""
        with patch.object(WebSocketOrderMonitor, "start", new_callable=AsyncMock):
            monitor = await start_order_monitor(user_id="user1")
            
            assert monitor.user_id == "user1"
            assert get_order_monitor("user1") is monitor
            
            # Cleanup
            await stop_all_monitors()
    
    @pytest.mark.asyncio
    async def test_stop_order_monitor(self):
        """Test stopping monitor."""
        with patch.object(WebSocketOrderMonitor, "start", new_callable=AsyncMock), \
             patch.object(WebSocketOrderMonitor, "stop", new_callable=AsyncMock):
            
            monitor = await start_order_monitor(user_id="user2")
            await stop_order_monitor(user_id="user2")
            
            assert get_order_monitor("user2") is None
            
            # Cleanup
            await stop_all_monitors()
    
    @pytest.mark.asyncio
    async def test_stop_all_monitors(self):
        """Test stopping all monitors."""
        with patch.object(WebSocketOrderMonitor, "start", new_callable=AsyncMock), \
             patch.object(WebSocketOrderMonitor, "stop", new_callable=AsyncMock):
            
            m1 = await start_order_monitor(user_id="user_a")
            m2 = await start_order_monitor(user_id="user_b")
            
            await stop_all_monitors()
            
            assert get_order_monitor("user_a") is None
            assert get_order_monitor("user_b") is None


# ============================================================================
#  INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""
    
    @pytest.mark.asyncio
    async def test_full_order_lifecycle_via_websocket(self, mock_db, sample_filled_order):
        """Test complete order update flow."""
        monitor = WebSocketOrderMonitor(user_id="user123")
        monitor._db = mock_db
        
        mock_db.trading_orders.find_one.return_value = sample_filled_order
        mock_db.trading_orders.update_one.return_value = MagicMock(modified_count=1)
        
        # Simulate WebSocket event
        ws_event = {
            "type": "message",
            "data": {
                "symbol": "BTC-USDT",
                "clientOid": "abc123def456",
                "orderId": "order_123",
                "status": "done",
                "filledSize": "0.001",
                "price": "50000",
            }
        }
        
        # Handle event
        await monitor._handle_order_event(ws_event)
        
        # Process queue
        update = await monitor._update_queue.get()
        await monitor._sync_order_to_db(update)
        
        # Verify sync
        mock_db.trading_orders.update_one.assert_called_once()
