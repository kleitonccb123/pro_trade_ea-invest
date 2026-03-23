"""
WebSocketOrderMonitor — Task 3.1

Monitora ordens em TEMPO REAL via WebSocket privada da KuCoin.
Atualiza banco automaticamente quando ordem é preenchida/cancelada.

Funcionalidades:
✓ Real-time order updates via private WebSocket
✓ Automatic database sync on order changes
✓ Reconnection with exponential backoff
✓ Heartbeat/ping to keep connection alive
✓ Graceful lifecycle management (start/stop)
✓ Per-user credential handling
✓ Comprehensive error handling and logging
✓ Audit trail for reconciliation events

Comparação: Reconciliation vs WebSocket
┌──────────────────────┬────────────────────┬─────────────────┐
│ Metric               │ Reconciliation     │ WebSocket       │
├──────────────────────┼────────────────────┼─────────────────┤
│ Latency              │ 60s (polling)      │ <100ms (real)   │
│ Resource Usage       │ Low (periodic)     │ Medium (live)   │
│ Completeness         │ 100% (all orders)  │ 100% (all orders)│
│ Best For             │ Backup sync        │ Real-time UX    │
└──────────────────────┴────────────────────┴─────────────────┘

Author: Crypto Trade Hub — Task 3.1
Date: March 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.trading.credentials_repository import CredentialsRepository, ExchangeType
from app.exchanges.kucoin.websocket_manager import (
    KuCoinWebSocketManager,
    OrderExecutionEvent,
)

logger = logging.getLogger(__name__)


@dataclass
class WebSocketOrderUpdate:
    """
    Represents a real-time order update from KuCoin WebSocket.
    
    Used for tracking and auditing what orders changed and when.
    """
    timestamp: datetime
    user_id: str
    order_id: str
    client_oid: str
    symbol: str
    status: str  # "open", "match", "done", "canceled"
    filled_price: Optional[Decimal] = None
    filled_quantity: Optional[Decimal] = None
    remaining_quantity: Optional[Decimal] = None
    reason: Optional[str] = None  # reason for status change


class WebSocketOrderMonitor:
    """
    Real-time order monitoring via KuCoin private WebSocket.
    
    Subscribes to /spotMarket/tradeOrders channel for a specific user.
    Updates MongoDB order records in real-time as events arrive.
    
    Architecture:
        User credentails (encrypted in MongoDB)
              ↓
        Get WebSocket auth token via REST API
              ↓
        Connect to wss://ws-auth.kucoin.com (private channel)
              ↓
        Subscribe to /spotMarket/tradeOrders
              ↓
        Receive real-time events (order_match, order_done, etc.)
              ↓
        Update trading_orders collection
              ↓
        Log to audit trail
    """
    
    def __init__(
        self,
        user_id: str,
        heartbeat_interval: float = 20.0,
        max_reconnect_attempts: int = 5,
        backoff_base: float = 2.0,
    ):
        """
        Initialize WebSocket order monitor.
        
        Args:
            user_id: User to monitor
            heartbeat_interval: Seconds between heartbeats (KuCoin requires < 30s)
            max_reconnect_attempts: Max reconnect retries before giving up
            backoff_base: Base for exponential backoff (2 = 1s, 2s, 4s, 8s, ...)
        """
        self.user_id = user_id
        self.heartbeat_interval = heartbeat_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.backoff_base = backoff_base
        
        self.is_running = False
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._ws_manager: Optional[KuCoinWebSocketManager] = None
        self._reconnect_count = 0
        self._last_heartbeat: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self._update_queue: asyncio.Queue = asyncio.Queue()

    async def start(self) -> None:
        """
        Start monitoring orders for this user.
        
        Connects to KuCoin WebSocket and subscribes to private order channel.
        Runs background tasks for:
        - Receiving order updates
        - Sending heartbeats
        - Processing updates
        - Maintaining connection
        """
        if self.is_running:
            logger.warning(f"WebSocket monitor for {self.user_id} already running")
            return
        
        self.is_running = True
        self._db = get_db()
        self._reconnect_count = 0
        
        logger.info(f"🔌 Starting WebSocket order monitor for {self.user_id}")
        
        try:
            # Create background task for main loop
            self._task = asyncio.create_task(self._run_monitor_loop())
            logger.info(f"✅ WebSocket monitor started for {self.user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket monitor: {e}")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """
        Stop monitoring and close WebSocket connection.
        
        Gracefully shuts down all background tasks.
        """
        if not self.is_running:
            return
        
        logger.info(f"🔌 Stopping WebSocket order monitor for {self.user_id}")
        
        self.is_running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        if self._ws_manager:
            try:
                await self._ws_manager.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket manager: {e}")
        
        logger.info(f"✅ WebSocket monitor stopped for {self.user_id}")

    # ─────────────────────── Main Event Loop ──────────────────────────

    async def _run_monitor_loop(self) -> None:
        """
        Main event loop.
        
        Handles:
        1. WebSocket connection/reconnection
        2. Heartbeat sending
        3. Order update processing
        4. Error recovery
        """
        while self.is_running:
            try:
                # Connect to WebSocket
                await self._connect()
                
                # Reset reconnect counter on successful connection
                self._reconnect_count = 0
                
                # Run until error or stop requested
                await self._monitor_loop()
                
            except asyncio.CancelledError:
                logger.info(f"Monitor task cancelled for {self.user_id}")
                break
                
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}", exc_info=True)
                
                if not self.is_running:
                    break
                
                # Attempt reconnection with exponential backoff
                await self._handle_reconnection()

    async def _connect(self) -> None:
        """
        Connect to KuCoin WebSocket.
        
        Steps:
        1. Get credentials from MongoDB
        2. Get WebSocket token from REST API
        3. Establish WebSocket connection
        4. Subscribe to private order channel
        """
        # Get encrypted credentials
        creds = await CredentialsRepository.get_credentials(
            self.user_id,
            ExchangeType.KUCOIN
        )
        
        if not creds:
            raise ValueError(f"No KuCoin credentials for user {self.user_id}")
        
        # Initialize WebSocket manager
        self._ws_manager = KuCoinWebSocketManager(creds)
        
        # Get WebSocket token (required for private channels)
        await self._ws_manager.get_ws_token()
        
        # Subscribe to private order channel
        await self._subscribe_to_orders()
        
        logger.info(f"✅ WebSocket connected for {self.user_id}")

    async def _subscribe_to_orders(self) -> None:
        """
        Subscribe to private order updates channel.
        
        Channel: /spotMarket/tradeOrders
        Events: order_open, order_match, order_done, order_canceled
        """
        if not self._ws_manager:
            raise RuntimeError("WebSocket manager not initialized")
        
        # Register callback for order events
        await self._ws_manager.subscribe(
            topic="/spotMarket/tradeOrders",
            callback=self._handle_order_event
        )
        
        logger.info(f"📡 Subscribed to order updates for {self.user_id}")

    async def _monitor_loop(self) -> None:
        """
        Main monitoring loop.
        
        Sends heartbeats and processes order updates.
        """
        heartbeat_task = asyncio.create_task(self._send_heartbeats())
        process_task = asyncio.create_task(self._process_updates())
        
        try:
            # Wait for either heartbeat or processing to fail
            done, pending = await asyncio.wait(
                [heartbeat_task, process_task],
                return_when=asyncio.FIRST_EXCEPTION
            )
            
            # Check for exceptions
            for task in done:
                if task.exception():
                    raise task.exception()
                    
        finally:
            heartbeat_task.cancel()
            process_task.cancel()

    # ─────────────────────── Event Handling ──────────────────────────

    async def _handle_order_event(self, event: Dict[str, Any]) -> None:
        """
        Handle incoming order event from WebSocket.
        
        Queues for processing to avoid blocking the WS receiver.
        """
        try:
            # Parse event into structured format
            update = self._parse_order_event(event)
            
            # Queue for async processing
            await self._update_queue.put(update)
            
            logger.debug(f"📨 Order event queued: {update.client_oid} -> {update.status}")
            
        except Exception as e:
            logger.error(f"❌ Error handling order event: {e}", exc_info=True)

    def _parse_order_event(self, event: Dict[str, Any]) -> WebSocketOrderUpdate:
        """
        Parse raw WebSocket event into WebSocketOrderUpdate.
        
        Event format from KuCoin:
        {
            "type": "message",
            "data": {
                "symbol": "BTC-USDT",
                "clientOid": "...",
                "orderId": "...",
                "type": "trade",
                "side": "buy",
                "price": "50000",
                "size": "0.001",
                "filledSize": "0.001",
                "cancelledSize": "0",
                "remainSize": "0",
                "status": "done",
                "matchTime": 1234567890000
            }
        }
        """
        data = event.get("data", {})
        
        status_map = {
            "open": "open",
            "match": "match",
            "done": "filled",
            "canceled": "canceled",
        }
        
        status = status_map.get(data.get("status"), data.get("status", "unknown"))
        
        return WebSocketOrderUpdate(
            timestamp=datetime.utcnow(),
            user_id=self.user_id,
            order_id=data.get("orderId"),
            client_oid=data.get("clientOid"),
            symbol=data.get("symbol"),
            status=status,
            filled_price=Decimal(data.get("price", 0)),
            filled_quantity=Decimal(data.get("filledSize", 0)),
            remaining_quantity=Decimal(data.get("remainSize", 0)),
            reason=data.get("reason"),
        )

    async def _process_updates(self) -> None:
        """
        Process queued order updates.
        
        Updates MongoDB trading_orders collection and audit trail.
        """
        while self.is_running:
            try:
                # Get next update (timeout to check is_running)
                update = await asyncio.wait_for(
                    self._update_queue.get(),
                    timeout=1.0
                )
                
                # Sync to database
                await self._sync_order_to_db(update)
                
                # Mark as done
                self._update_queue.task_done()
                
            except asyncio.TimeoutError:
                # Normal timeout, continue
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error processing update: {e}", exc_info=True)

    async def _sync_order_to_db(self, update: WebSocketOrderUpdate) -> None:
        """
        Sync order update to MongoDB.
        
        Updates trading_orders collection with latest status and fill info.
        Logs to audit trail for compliance.
        """
        if not self._db:
            logger.error("Database not initialized")
            return
        
        try:
            # Find order by client_oid
            order = await self._db.trading_orders.find_one({
                "user_id": self.user_id,
                "client_oid": update.client_oid,
            })
            
            if not order:
                logger.warning(
                    f"⚠️ Order not found: {update.client_oid} "
                    f"(may be external fill)"
                )
                # Still log to audit trail
                await self._log_order_event(update, "order_not_found")
                return
            
            # Prepare update based on status
            status_update = {
                "status": update.status,
                "synced_via_ws_at": update.timestamp,
            }
            
            if update.status == "filled":
                status_update.update({
                    "filled_price": update.filled_price,
                    "filled_quantity": update.filled_quantity,
                    "filled_at": update.timestamp,
                })
            
            # Update order in database
            result = await self._db.trading_orders.update_one(
                {"_id": order["_id"]},
                {"$set": status_update}
            )
            
            if result.modified_count > 0:
                logger.info(
                    f"✅ Order synced: {update.client_oid} → {update.status} "
                    f"(qty={update.filled_quantity})"
                )
                
                # Log successful sync
                await self._log_order_event(update, "synced")
                
            else:
                logger.debug(f"ℹ️ Order unchanged: {update.client_oid}")
            
        except Exception as e:
            logger.error(
                f"❌ Failed to sync order {update.client_oid}: {e}",
                exc_info=True
            )
            await self._log_order_event(update, "sync_error", str(e))

    # ─────────────────────── Heartbeat Management ──────────────────────────

    async def _send_heartbeats(self) -> None:
        """
        Send periodic heartbeats to keep WebSocket alive.
        
        KuCoin requires heartbeat every < 30 seconds.
        Default: 20 seconds (with 10s buffer).
        """
        while self.is_running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self._ws_manager and self.is_running:
                    await self._ws_manager.send_heartbeat()
                    self._last_heartbeat = datetime.utcnow()
                    logger.debug(f"💓 Heartbeat sent for {self.user_id}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Heartbeat error: {e}")
                raise

    # ─────────────────────── Reconnection Logic ──────────────────────────

    async def _handle_reconnection(self) -> None:
        """
        Handle reconnection with exponential backoff.
        
        Delay = base^attempt (1s, 2s, 4s, 8s, 16s...)
        Max attempts: 5
        """
        if self._reconnect_count >= self.max_reconnect_attempts:
            logger.error(
                f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) "
                f"reached for {self.user_id}"
            )
            self.is_running = False
            return
        
        # Calculate backoff delay
        delay_s = self.backoff_base ** self._reconnect_count
        self._reconnect_count += 1
        
        logger.warning(
            f"🔄 Reconnecting in {delay_s}s "
            f"(attempt {self._reconnect_count}/{self.max_reconnect_attempts})..."
        )
        
        await asyncio.sleep(delay_s)

    # ─────────────────────── Audit Logging ──────────────────────────

    async def _log_order_event(
        self,
        update: WebSocketOrderUpdate,
        event_type: str,
        error: Optional[str] = None,
    ) -> None:
        """
        Log order event to audit trail.
        
        Collection: ws_order_events
        Used for: Compliance, debugging, reconciliation
        """
        try:
            if not self._db:
                return
            
            log_entry = {
                "timestamp": datetime.utcnow(),
                "user_id": self.user_id,
                "order_id": update.order_id,
                "client_oid": update.client_oid,
                "symbol": update.symbol,
                "status": update.status,
                "event_type": event_type,
                "filled_price": update.filled_price,
                "filled_quantity": update.filled_quantity,
            }
            
            if error:
                log_entry["error"] = error
            
            await self._db.ws_order_events.insert_one(log_entry)
            
        except Exception as e:
            logger.error(f"⚠️ Failed to log order event: {e}")


# ─────────────────────────── Module Functions ──────────────────────────────

# Global registry of monitors per user
_monitors: Dict[str, WebSocketOrderMonitor] = {}
_monitors_lock = asyncio.Lock()


async def start_order_monitor(user_id: str) -> WebSocketOrderMonitor:
    """
    Start WebSocket order monitor for a user.
    
    If already running, returns existing monitor.
    
    Usage:
        monitor = await start_order_monitor(user_id="user123")
        # Monitor now running in background
    
    Args:
        user_id: User to monitor
        
    Returns:
        WebSocketOrderMonitor instance
    """
    async with _monitors_lock:
        if user_id in _monitors:
            monitor = _monitors[user_id]
            if monitor.is_running:
                return monitor
        
        # Create new monitor
        monitor = WebSocketOrderMonitor(user_id)
        await monitor.start()
        _monitors[user_id] = monitor
        
        logger.info(f"✅ Order monitor started for {user_id}")
        return monitor


async def stop_order_monitor(user_id: str) -> None:
    """
    Stop WebSocket order monitor for a user.
    
    Usage:
        await stop_order_monitor(user_id="user123")
    
    Args:
        user_id: User to stop monitoring
    """
    async with _monitors_lock:
        if user_id not in _monitors:
            return
        
        monitor = _monitors[user_id]
        await monitor.stop()
        del _monitors[user_id]
        
        logger.info(f"✅ Order monitor stopped for {user_id}")


async def stop_all_monitors() -> None:
    """
    Stop all active order monitors.
    
    Useful for graceful shutdown.
    """
    async with _monitors_lock:
        for user_id, monitor in list(_monitors.items()):
            if monitor.is_running:
                await monitor.stop()
        _monitors.clear()
        logger.info("✅ All order monitors stopped")


def get_order_monitor(user_id: str) -> Optional[WebSocketOrderMonitor]:
    """
    Get existing monitor for a user (non-async).
    
    Returns None if not running.
    """
    return _monitors.get(user_id)


# ─────────────────────────── FastAPI Integration ──────────────────────────

async def startup_order_monitors() -> None:
    """
    Called from FastAPI startup event.
    
    Placeholder for potentially starting monitors for all active users.
    (Currently monitors are started on-demand when user logs in)
    """
    logger.info("🔌 WebSocket order monitoring subsystem initialized")


async def shutdown_order_monitors() -> None:
    """
    Called from FastAPI shutdown event.
    
    Gracefully closes all monitors.
    """
    logger.info("🔌 Shutting down WebSocket order monitors...")
    await stop_all_monitors()
    logger.info("✅ All WebSocket order monitors shut down")
