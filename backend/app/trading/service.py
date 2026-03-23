"""
Real trading service layer
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.trading.binance_client import get_binance_client, get_binance_ws_client
from app.trading.models import (
    RealTrade, TradingSession, 
    RealTimeMarketData, TradingAlert, OrderStatusEnum, IdempotencyKey
)
from app.trading.schemas import (
    TradingCredentials, PlaceOrderRequest, OrderResponse,
    AccountBalance, RealTradeCreate, TradingSessionCreate,
    KlineData, TickerData
)
from app.services.redis_manager import redis_manager
from app.core.database import get_db
from fastapi import HTTPException

# DOC-K01: cipher import (lazy to avoid startup failure when key not set yet)
try:
    from app.security.cipher_singleton import get_cipher as _get_cipher
    _CIPHER_AVAILABLE = True
except Exception:
    _CIPHER_AVAILABLE = False
    _get_cipher = None  # type: ignore

logger = logging.getLogger(__name__)

class TradingService:
    def __init__(self):
        self.active_sessions: Dict[int, Dict] = {}  # session_id -> session_data
        self.websocket_tasks: Dict[int, List[asyncio.Task]] = {}
    
    async def create_trading_credentials(self, user_id: int, credentials: TradingCredentials) -> Dict[str, Any]:
        """Create new trading credentials for a user"""
        db = get_db()
        credentials_col = db['trading_credentials']
        
        # In production, encrypt the API secret
        # DOC-K01: Always encrypt credentials before storing
        if _CIPHER_AVAILABLE:
            cipher = _get_cipher()
            encrypted = cipher.encrypt_credentials(
                credentials.api_key,
                credentials.api_secret,
                getattr(credentials, 'api_passphrase', ''),
            )
            doc = {
                'user_id': user_id,
                'api_key_enc': encrypted['api_key_enc'],
                'api_secret_enc': encrypted['api_secret_enc'],
                'passphrase_enc': encrypted['passphrase_enc'],
                'algorithm': 'fernet',
                'testnet': credentials.testnet,
                'is_active': True,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            }
        else:
            # NEVER store credentials in plaintext
            raise HTTPException(
                status_code=500,
                detail="Encryption not configured (CREDENTIAL_ENCRYPTION_KEY). Cannot store credentials safely.",
            )
        
        result = await credentials_col.insert_one(doc)
        doc['_id'] = result.inserted_id
        return doc
    
    async def get_user_credentials(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get active trading credentials for a user"""
        db = get_db()
        credentials_col = db['trading_credentials']
        
        cred = await credentials_col.find_one({
            'user_id': user_id,
            'is_active': True
        })
        
        return cred
    
    async def test_credentials(self, credentials: TradingCredentials) -> Dict[str, Any]:
        """Test Binance credentials"""
        client = get_binance_client("test", credentials.api_key, credentials.api_secret, credentials.testnet)
        
        try:
            account_info = await client.get_account_info()
            return {
                "valid": True,
                "account_type": account_info.get("accountType", "UNKNOWN"),
                "can_trade": account_info.get("canTrade", False),
                "can_withdraw": account_info.get("canWithdraw", False)
            }
        except Exception as e:
            logger.error(f"Credentials test failed: {e}")
            return {
                "valid": False,
                "error": str(e)
            }
    
    async def get_account_balances(self, user_id: int) -> List[Dict[str, Any]]:
        """Get account balances"""
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            raise ValueError("No trading credentials found")
        
        client = get_binance_client(
            str(user_id), 
            credentials.get('api_key'), 
            credentials.get('api_secret'), 
            credentials.get('testnet', False)
        )
        
        balances_data = await client.get_balances()
        return [dict(balance) for balance in balances_data]
    
    async def place_order(self, user_id: int, order: PlaceOrderRequest) -> Dict[str, Any]:
        """Place a trading order with idempotency protection"""
        db = get_db()
        
        # Check idempotency key if provided
        if order.idempotency_key:
            # Check if this key was already used
            existing_key = await db.idempotency_keys.find_one({
                "user_id": str(user_id),
                "idempotency_key": order.idempotency_key
            })
            
            if existing_key:
                # Return the existing order result
                if existing_key.get("order_id"):
                    # Fetch the existing order details
                    existing_order = await db.real_orders.find_one({
                        "user_id": str(user_id),
                        "order_id": existing_key["order_id"]
                    })
                    if existing_order:
                        return {
                            "order_id": existing_order["order_id"],
                            "status": existing_order["status"],
                            "symbol": existing_order["symbol"],
                            "side": existing_order["side"],
                            "quantity": existing_order["quantity"],
                            "price": existing_order.get("price"),
                            "idempotency_key": order.idempotency_key,
                            "cached": True  # Indicate this is a cached result
                        }
                # If no order found but key exists, this is an error state
                raise ValueError(f"Idempotency key already used but order not found: {order.idempotency_key}")
        
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            raise ValueError("No trading credentials found")
        
        client = get_binance_client(
            str(user_id),
            credentials.get('api_key'),
            credentials.get('api_secret'),
            credentials.get('testnet', False)
        )
        
        # Store idempotency key before placing order
        if order.idempotency_key:
            idempotency_doc = {
                "user_id": str(user_id),
                "idempotency_key": order.idempotency_key,
                "order_data": order.model_dump(),
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=24)  # Expire after 24 hours
            }
            await db.idempotency_keys.insert_one(idempotency_doc)
        
        try:
            order_data = await client.place_order(
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.type.value,
                quantity=order.quantity,
                price=order.price
            )
            
            # Update idempotency key with order ID
            if order.idempotency_key:
                await db.idempotency_keys.update_one(
                    {"user_id": str(user_id), "idempotency_key": order.idempotency_key},
                    {"$set": {"order_id": order_data.get("orderId")}}
                )
            
            # Post-execution order status verification
            await self._verify_order_status(user_id, order_data, order.symbol)
            
            # Broadcast trade notification to user's sessions
            await self._broadcast_trade_notification(user_id, order_data)
            
            # Add idempotency key to response
            order_data["idempotency_key"] = order.idempotency_key
            return dict(order_data)
            
        except Exception as e:
            # Remove idempotency key on failure
            if order.idempotency_key:
                await db.idempotency_keys.delete_one({
                    "user_id": str(user_id),
                    "idempotency_key": order.idempotency_key
                })
            raise
    
    async def _verify_order_status(self, user_id: int, order_data: Dict[str, Any], symbol: str) -> None:
        """
        Verify order status after execution to ensure it was placed correctly.
        
        Args:
            user_id: User's ID
            order_data: Order data returned from exchange
            symbol: Trading symbol
        """
        try:
            # Wait a short time for order to be processed
            await asyncio.sleep(1)
            
            # Get order status from exchange
            client = get_binance_client(
                str(user_id),
                (await self.get_user_credentials(user_id))['api_key'],
                (await self.get_user_credentials(user_id))['api_secret'],
                (await self.get_user_credentials(user_id)).get('testnet', False)
            )
            
            order_id = order_data.get("orderId")
            if not order_id:
                logger.warning(f"No order ID found in order data for verification: {order_data}")
                return
            
            # Query order status
            status_response = await client.get_order(symbol, order_id)
            
            if status_response.get("status") not in ["FILLED", "PARTIALLY_FILLED", "NEW"]:
                logger.warning(f"Order {order_id} has unexpected status: {status_response.get('status')}")
                # Could raise an exception here or send notification
            else:
                logger.info(f"Order {order_id} verified with status: {status_response.get('status')}")
                
        except Exception as e:
            logger.error(f"Failed to verify order status for order {order_data.get('orderId', 'unknown')}: {e}")
            # Don't raise exception - verification failure shouldn't break the order placement
    
    async def _broadcast_trade_notification(self, user_id: int, order_data: Dict[str, Any]):
        """
        Broadcast trade notification to all active sessions of the user.
        
        Args:
            user_id: User's ID
            order_data: Order data from the exchange
        """
        try:
            db = get_db()
            trading_sessions_col = db['trading_sessions']
            
            # Find all active trading sessions for the user
            active_sessions = await trading_sessions_col.find({
                'user_id': str(user_id),
                'is_active': True
            }).to_list(length=None)
            
            if not active_sessions:
                logger.debug(f"No active sessions found for user {user_id}")
                return
            
            # Prepare notification message
            notification = {
                "type": "trade_notification",
                "data": {
                    "order_id": order_data.get("orderId"),
                    "symbol": order_data.get("symbol"),
                    "side": order_data.get("side"),
                    "quantity": order_data.get("origQty"),
                    "price": order_data.get("price"),
                    "status": order_data.get("status"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Broadcast to each active session
            for session in active_sessions:
                session_id = session.get('_id')
                if session_id:
                    await redis_manager.broadcast_to_session(
                        json.dumps(notification), 
                        session_id
                    )
                    logger.debug(f"Broadcasted trade notification to session {session_id}")
                    
        except Exception as e:
            logger.error(f"Failed to broadcast trade notification for user {user_id}: {e}")
    
    async def create_trading_session(self, user_id: int, session_data: TradingSessionCreate) -> Dict[str, Any]:
        """Create a new trading session"""
        db = get_db()
        credentials_col = db['trading_credentials']
        bot_instances_col = db['bot_instances']
        trading_sessions_col = db['trading_sessions']
        
        credentials = await self.get_user_credentials(user_id)
        if not credentials:
            raise ValueError("No trading credentials found")
        
        # Verify bot instance exists
        bot_instance = await bot_instances_col.find_one({'_id': session_data.bot_instance_id})
        if not bot_instance:
            raise ValueError("Bot instance not found")
        
        # Test credentials before creating session
        test_result = await self.test_credentials(TradingCredentials(
            api_key=session_data.api_key,
            api_secret=session_data.api_secret,
            testnet=session_data.testnet
        ))
        
        if not test_result.get("valid"):
            raise ValueError(f"Invalid credentials: {test_result.get('error')}")
        
        # Create trading session
        new_session = {
            'user_id': str(user_id),
            'bot_instance_id': session_data.bot_instance_id,
            'credentials_id': credentials.get('_id'),
            'symbol': session_data.symbol,
            'initial_balance': session_data.initial_balance,
            'current_balance': session_data.initial_balance,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = await trading_sessions_col.insert_one(new_session)
        new_session['_id'] = result.inserted_id
        
        # Start real-time data collection
        await self.start_realtime_data_collection(result.inserted_id, user_id)
        
        return new_session
    
    async def start_realtime_data_collection(self, session_id: int, user_id: int):
        """Start real-time data collection for a trading session"""
        db = get_db()
        trading_sessions_col = db['trading_sessions']
        
        session = await trading_sessions_col.find_one({'_id': session_id})
        if not session:
            return
        
        credentials_col = db['trading_credentials']
        credentials = await credentials_col.find_one({'_id': session.get('credentials_id')})
        
        ws_client = get_binance_ws_client(
            str(user_id),
            credentials.get('api_key'),
            credentials.get('api_secret'),
            credentials.get('testnet', False)
        )
        
        # Create WebSocket tasks
        tasks = []
        
        # Kline data (1m candlesticks)
        kline_task = asyncio.create_task(
            ws_client.subscribe_klines(
                session.get('symbol'),
                "1m",
                lambda data: self.handle_kline_data(session_id, data)
            )
        )
        tasks.append(kline_task)
        
        # Ticker data
        ticker_task = asyncio.create_task(
            ws_client.subscribe_ticker(
                session.get('symbol'),
                lambda data: self.handle_ticker_data(session_id, data)
            )
        )
        tasks.append(ticker_task)
        
        # User stream (account updates)
        user_stream_task = asyncio.create_task(
            ws_client.start_user_stream(
                lambda data: self.handle_user_stream_data(session_id, data)
            )
        )
        tasks.append(user_stream_task)
        
        # Store tasks for cleanup
        self.websocket_tasks[session_id] = tasks
        self.active_sessions[session_id] = {
            "session": session,
            "user_id": user_id,
            "tasks": tasks
        }
        
        logger.info(f"Started real-time data collection for session {session_id}")
    
    async def handle_kline_data(self, session_id: int, data: Dict[str, Any]):
        """Handle kline/candlestick data"""
        try:
            db = get_db()
            market_data_col = db['market_data']
            
            kline = data.get("k", {})
            if not kline:
                return
            
            market_data = {
                'trading_session_id': session_id,
                'symbol': kline.get("s"),
                'data_type': 'kline',
                'timestamp': datetime.fromtimestamp(kline.get("t") / 1000, tz=timezone.utc),
                'open_price': float(kline.get("o")),
                'high_price': float(kline.get("h")),
                'low_price': float(kline.get("l")),
                'close_price': float(kline.get("c")),
                'volume': float(kline.get("v")),
                'quote_volume': float(kline.get("q")),
                'raw_data': data
            }
            
            await market_data_col.insert_one(market_data)
            
            # Process trading signals here
            await self.process_trading_signals(session_id, market_data)
            
        except Exception as e:
            logger.error(f"Error handling kline data for session {session_id}: {e}")
    
    async def handle_ticker_data(self, session_id: int, data: Dict[str, Any]):
        """Handle 24hr ticker data"""
        try:
            db = get_db()
            market_data_col = db['market_data']
            
            market_data = {
                'trading_session_id': session_id,
                'symbol': data.get("s"),
                'data_type': 'ticker',
                'timestamp': datetime.fromtimestamp(data.get("E") / 1000, tz=timezone.utc),
                'close_price': float(data.get("c")),
                'open_price': float(data.get("o")),
                'high_price': float(data.get("h")),
                'low_price': float(data.get("l")),
                'volume': float(data.get("v")),
                'quote_volume': float(data.get("q")),
                'price_change': float(data.get("p")),
                'price_change_percent': float(data.get("P")),
                'bid_price': float(data.get("b")),
                'ask_price': float(data.get("a")),
                'raw_data': data
            }
            
            await market_data_col.insert_one(market_data)
            
        except Exception as e:
            logger.error(f"Error handling ticker data for session {session_id}: {e}")
    
    async def handle_user_stream_data(self, session_id: int, data: Dict[str, Any]):
        """Handle user account updates"""
        try:
            event_type = data.get("e")
            
            if event_type == "executionReport":
                # Order execution update
                await self.handle_execution_report(session_id, data)
            elif event_type == "outboundAccountPosition":
                # Account balance update
                await self.handle_account_update(session_id, data)
                
        except Exception as e:
            logger.error(f"Error handling user stream data for session {session_id}: {e}")
    
    async def handle_execution_report(self, session_id: int, data: Dict[str, Any]):
        """Handle order execution report"""
        try:
            db = get_db()
            real_trades_col = db['real_trades']
            
            order_id = data.get("i")  # Binance order ID
            client_order_id = data.get("c")
            symbol = data.get("s")
            side = data.get("S")
            order_type = data.get("o")
            status = data.get("X")
            executed_qty = float(data.get("z", 0))
            executed_price = float(data.get("L", 0)) if data.get("L") else None
            commission = float(data.get("n", 0))
            commission_asset = data.get("N")
            
            # Find existing trade or create new one
            trade = await real_trades_col.find_one({'binance_order_id': str(order_id)})
            
            if trade:
                # Update existing trade
                trade.status = OrderStatusEnum(status)
                trade.executed_quantity = executed_qty
                trade.executed_price = executed_price
                trade.commission = commission
                trade.commission_asset = commission_asset
                
                if status == "FILLED":
                    trade.filled_at = datetime.now(timezone.utc)
                    
                    # Calculate P&L if it's a closing trade
                    await self.calculate_trade_pnl(trade)
                
                self.db.commit()
                
                # Update session statistics
                await self.update_session_stats(session_id)
            
        except Exception as e:
            logger.error(f"Error handling execution report for session {session_id}: {e}")
    
    async def handle_account_update(self, session_id: int, data: Dict[str, Any]):
        """Handle account balance update"""
        try:
            # Update session balance based on account changes
            session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
            if session:
                # This would need more sophisticated balance tracking
                # For now, we'll update it during trade execution
                pass
                
        except Exception as e:
            logger.error(f"Error handling account update for session {session_id}: {e}")
    
    async def process_trading_signals(self, session_id: int, market_data: RealTimeMarketData):
        """Process trading signals from market data"""
        try:
            session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
            if not session or not session.is_active:
                return
            
            bot_instance = session.bot_instance
            if not bot_instance or bot_instance.state != "running":
                return
            
            # Here you would implement your trading strategy
            # For example, simple moving average crossover
            
            # Get recent market data for analysis
            recent_data = self.db.query(RealTimeMarketData).filter(
                RealTimeMarketData.trading_session_id == session_id,
                RealTimeMarketData.data_type == "kline"
            ).order_by(desc(RealTimeMarketData.timestamp)).limit(20).all()
            
            if len(recent_data) >= 20:
                # Calculate simple moving averages
                prices = [data.close_price for data in reversed(recent_data)]
                sma_10 = sum(prices[-10:]) / 10
                sma_20 = sum(prices) / 20
                
                current_price = market_data.close_price
                
                # Simple strategy: buy when SMA10 > SMA20 and price is above SMA10
                if sma_10 > sma_20 and current_price > sma_10:
                    # Check if we don't already have an open position
                    open_trades = self.db.query(RealTrade).filter(
                        RealTrade.trading_session_id == session_id,
                        RealTrade.status.in_([OrderStatusEnum.NEW, OrderStatusEnum.PARTIALLY_FILLED])
                    ).count()
                    
                    if open_trades == 0:
                        await self.create_signal_trade(session_id, "BUY", current_price, "SMA Crossover")
                
                # Sell signal: SMA10 < SMA20
                elif sma_10 < sma_20 and current_price < sma_10:
                    # Close any open long positions
                    open_long_trades = self.db.query(RealTrade).filter(
                        RealTrade.trading_session_id == session_id,
                        RealTrade.side == "BUY",
                        RealTrade.status == OrderStatusEnum.FILLED
                    ).all()
                    
                    for trade in open_long_trades:
                        await self.create_signal_trade(session_id, "SELL", current_price, "SMA Crossover Exit")
            
        except Exception as e:
            logger.error(f"Error processing trading signals for session {session_id}: {e}")
    
    async def create_signal_trade(self, session_id: int, side: str, price: float, reason: str):
        """Create a trade based on trading signal"""
        try:
            session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
            if not session:
                return
            
            # Calculate position size based on risk management
            position_size = min(session.max_position_size, session.current_balance * 0.02)  # 2% risk
            
            # Create trade record
            trade = RealTrade(
                bot_instance_id=session.bot_instance_id,
                trading_session_id=session_id,
                symbol=session.symbol,
                side=side,
                order_type="MARKET",
                quantity=position_size,
                price=price,
                status=OrderStatusEnum.NEW,
                entry_reason=reason
            )
            
            self.db.add(trade)
            self.db.commit()
            self.db.refresh(trade)
            
            # Execute order through Binance (implement based on your needs)
            # await self.execute_trade_order(trade)
            
            logger.info(f"Created signal trade for session {session_id}: {side} {position_size} at {price}")
            
        except Exception as e:
            logger.error(f"Error creating signal trade for session {session_id}: {e}")
    
    async def calculate_trade_pnl(self, trade: RealTrade):
        """Calculate P&L for a completed trade"""
        try:
            if not trade:
                return
            entry_price = getattr(trade, 'price', None) or 0
            exit_price = getattr(trade, 'executed_price', None) or 0
            qty = getattr(trade, 'executed_quantity', None) or getattr(trade, 'quantity', 0) or 0
            commission = getattr(trade, 'commission', None) or 0
            side = getattr(trade, 'side', 'buy')
            if hasattr(side, 'value'):
                side = side.value

            if entry_price and exit_price and qty:
                if side == 'buy':
                    pnl = (exit_price - entry_price) * qty - commission
                else:
                    pnl = (entry_price - exit_price) * qty - commission
                trade.pnl = round(pnl, 8)
            else:
                trade.pnl = 0.0
        except Exception as e:
            logger.error(f"Error calculating PnL: {e}")
            trade.pnl = 0.0
    
    async def update_session_stats(self, session_id: int):
        """Update trading session statistics"""
        session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
        if not session:
            return
        
        # Get all trades for this session
        trades = self.db.query(RealTrade).filter(
            RealTrade.trading_session_id == session_id,
            RealTrade.status == OrderStatusEnum.FILLED
        ).all()
        
        session.total_trades = len(trades)
        session.profitable_trades = len([t for t in trades if t.pnl > 0])
        session.losing_trades = len([t for t in trades if t.pnl < 0])
        session.total_pnl = sum(t.pnl for t in trades)
        
        if session.total_trades > 0:
            session.win_rate = session.profitable_trades / session.total_trades
        
        self.db.commit()
    
    async def stop_trading_session(self, session_id: int):
        """Stop a trading session and cleanup resources"""
        if session_id in self.websocket_tasks:
            # Cancel all WebSocket tasks
            tasks = self.websocket_tasks[session_id]
            for task in tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Cleanup
            del self.websocket_tasks[session_id]
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
        
        # Update session in database
        session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
        if session:
            session.is_active = False
            session.ended_at = datetime.now(timezone.utc)
            self.db.commit()
        
        # Also update MongoDB trading_sessions
        db = get_db()
        trading_sessions_col = db['trading_sessions']
        await trading_sessions_col.update_one(
            {'_id': session_id},
            {'$set': {'is_active': False, 'updated_at': datetime.utcnow()}}
        )
        
        logger.info(f"Stopped trading session {session_id}")
    
    async def get_session_performance(self, session_id: int) -> Dict[str, Any]:
        """Get trading session performance metrics"""
        session = self.db.query(TradingSession).filter(TradingSession.id == session_id).first()
        if not session:
            raise ValueError("Trading session not found")
        
        # Get recent market data for charts
        recent_data = self.db.query(RealTimeMarketData).filter(
            RealTimeMarketData.trading_session_id == session_id,
            RealTimeMarketData.data_type == "kline"
        ).order_by(desc(RealTimeMarketData.timestamp)).limit(100).all()
        
        # Get all trades
        trades = self.db.query(RealTrade).filter(
            RealTrade.trading_session_id == session_id
        ).order_by(RealTrade.created_at).all()
        
        return {
            "session": session,
            "market_data": [
                {
                    "timestamp": data.timestamp.isoformat(),
                    "open": data.open_price,
                    "high": data.high_price,
                    "low": data.low_price,
                    "close": data.close_price,
                    "volume": data.volume
                }
                for data in reversed(recent_data)
            ],
            "trades": [
                {
                    "id": trade.id,
                    "side": trade.side.value,
                    "quantity": trade.quantity,
                    "price": trade.executed_price or trade.price,
                    "pnl": trade.pnl,
                    "timestamp": trade.created_at.isoformat(),
                    "status": trade.status.value
                }
                for trade in trades
            ],
            "stats": {
                "total_trades": session.total_trades,
                "profitable_trades": session.profitable_trades,
                "losing_trades": session.losing_trades,
                "win_rate": session.win_rate,
                "total_pnl": session.total_pnl,
                "current_balance": session.current_balance,
                "initial_balance": session.initial_balance,
                "roi": ((session.current_balance - session.initial_balance) / session.initial_balance) * 100
            }
        }

def get_trading_service() -> TradingService:
    """Get trading service instance"""
    return TradingService()