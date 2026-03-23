"""
FASE 1 + FASE 2 + FASE 3 Architecture - Complete System
========================================================

This document shows the complete 9-layer architecture with all components integrated.


LAYER 0: Client & Network
====================
    Frontend (React)
         ↓
    HTTP Requests
         ↓
    network/TLS
         ↓
    FastAPI Router


LAYER 1: HTTP & Security (FASE 2)
==================================
    ┌──────────────────────────────────────────────┐
    │           FastAPI Application                 │
    │  ┌──────────────────────────────────────────┐ │
    │  │       HTTP Routers (FASE 2)               │ │
    │  ├──────────────────────────────────────────┤ │
    │  │ /api/exchanges/* (setup, verify, list)   │ │
    │  │ /api/bots/* (create, list, start, stop)  │ │
    │  │ /api/orders/* (place, cancel, list)      │ │
    │  │ /api/positions (view, update, close)     │ │
    │  └──────────────────────────────────────────┘ │
    │                       ↓                        │
    │  ┌──────────────────────────────────────────┐ │
    │  │      Middleware Stack (FASE 2)            │ │
    │  ├──────────────────────────────────────────┤ │
    │  │ 1. CORSMiddleware                        │ │
    │  │ 2. GoogleOAuthCSPMiddleware              │ │
    │  │ 3. SecurityHeadersMiddleware             │ │
    │  │ 4. MaxUploadSizeMiddleware               │ │
    │  │ 5. AuthorizationMiddleware ← Bearer       │ │
    │  │ 6. RequestLoggingMiddleware ← Sanitizer   │ │
    │  │ 7. ErrorHandlingMiddleware               │ │
    │  └──────────────────────────────────────────┘ │
    │                       ↓                        │
    │    Authenticated Request (user_id known)      │
    └──────────────────────────────────────────────┘


LAYER 2: Security & Secrets Management (FASE 2)
================================================
    ┌──────────────────────────────────────────────┐
    │      Security Module (FASE 2)                 │
    ├──────────────────────────────────────────────┤
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ LogSanitizer                            │ │
    │  │ • Removes API keys from logs            │ │
    │  │ • Removes secrets from logs             │ │
    │  │ • Remove Bearer tokens from logs        │ │
    │  │ • Remove passwords from logs            │ │
    │  │ Patterns: 8 regex rules                 │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ CredentialEncryption                    │ │
    │  │ • Fernet symmetric encryption           │ │
    │  │ • Key derivation from .env              │ │
    │  │ • Encrypt credentials for storage       │ │
    │  │ • Decrypt on-demand for API calls       │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ CredentialStore                         │ │
    │  │ • Per-user credential storage           │ │
    │  │ • MongoDB: user_exchange_credentials    │ │
    │  │ • Unique index: (user_id, exchange)     │ │
    │  │ • Methods: store, get, delete, list     │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    └──────────────────────────────────────────────┘


LAYER 3: Service Layer (FASE 3)
================================
    ┌──────────────────────────────────────────────┐
    │   Service Layer (FASE 3)                      │
    ├──────────────────────────────────────────────┤
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ BotService                              │ │
    │  │ • create_bot()                          │ │
    │  │ • get_bot() with ownership check        │ │
    │  │ • list_bots() for user                  │ │
    │  │ • update_bot_status()                   │ │
    │  │ • update_bot_statistics()               │ │
    │  │ • update_bot_config()                   │ │
    │  │ • delete_bot()                          │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ OrderService ⭐ CRITICAL                │ │
    │  │ • create_order() → MongoDB              │ │
    │  │ • validate_and_execute_order() ↓        │ │
    │  │   - Gets RiskManager                    │ │
    │  │   - Calls validate_order()              │ │
    │  │   - Gets OrderManager                   │ │
    │  │   - Calls execute_order()               │ │
    │  │   - Updates MongoDB with result         │ │
    │  │ • get_order() with ownership            │ │
    │  │ • list_orders() by bot_id               │ │
    │  │ • cancel_order()                        │ │
    │  │ • record_execution()                    │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ PositionService                         │ │
    │  │ • open_position()                       │ │
    │  │ • get_position() with ownership         │ │
    │  │ • list_open_positions()                 │ │
    │  │ • update_position_price() → PnL calc    │ │
    │  │ • close_position() → realized_pnl       │ │
    │  │ • get_portfolio_summary()                │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    └──────────────────────────────────────────────┘


LAYER 4: Core Operations (FASE 1)
==================================
    ┌──────────────────────────────────────────────┐
    │      FASE 1 - Core Operations                 │
    ├──────────────────────────────────────────────┤
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ RiskManager                             │ │
    │  │ • Pre-execution order validation        │ │
    │  │ • Check account balance                 │ │
    │  │ • Validate order size                   │ │
    │  │ • Check leverage limits                 │ │
    │  │ • Verify account_id for user            │ │
    │  │ • Return: (is_valid, error_message)     │ │
    │  │                                         │ │
    │  │ Called by: OrderService                 │ │
    │  │ Input: OrderRequest + account_balance   │ │
    │  │ Output: (bool, str)                     │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ OrderManager                            │ │
    │  │ • Execute validated orders              │ │
    │  │ • KuCoin API communication              │ │
    │  │ • Retry logic with exponential backoff  │ │
    │  │ • Rate limit handling (429s)            │ │
    │  │ • Track exchange_order_id               │ │
    │  │ • Return: OrderResult                   │ │
    │  │                                         │ │
    │  │ Called by: OrderService                 │ │
    │  │ Input: OrderRequest                     │ │
    │  │ Output: OrderResult                     │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ TradingEngine                           │ │
    │  │ • Orchestrate bot trades                │ │
    │  │ • Manage strategy execution             │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ StrategyEngine                          │ │
    │  │ • Bot isolation via asyncio.Task        │ │
    │  │ • Per-bot independent execution         │ │
    │  │ • Strategy logic encapsulation          │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    │  ┌─────────────────────────────────────────┐ │
    │  │ StreamManager                           │ │
    │  │ • WebSocket connection pooling          │ │
    │  │ • Real-time price/order updates         │ │
    │  │ • Automatic reconnection + heartbeat    │ │
    │  └─────────────────────────────────────────┘ │
    │                                               │
    └──────────────────────────────────────────────┘


LAYER 5: Exchange API (FASE 1)
==============================
    ┌──────────────────────────────────────────────┐
    │   KuCoinRawClient (FASE 1)                    │
    ├──────────────────────────────────────────────┤
    │ • REST API communication with KuCoin         │
    │ • Rate limit handling (429)                  │
    │ • Automatic retry attempts                   │
    │ • Payload normalization                      │
    │ • Error handling & status tracking           │
    │                                               │
    │ Methods:                                      │
    │ • place_order(symbol, side, type, size, price)
    │ • cancel_order(order_id, symbol)            │
    │ • get_order(order_id, symbol)               │
    │ • get_fills(symbol, order_id)               │
    │ • get_accounts()                             │
    │ • get_balances(account_id)                  │
    │ • get_24h_stats(symbol)                     │
    │                                               │
    │ Per-order flow:                              │
    │ 1. Place order → get exchange_order_id       │
    │ 2. Track status via polling/WebSocket        │
    │ 3. Get fills if order partially executed     │
    │ 4. Cancel if needed                          │
    │                                               │
    └──────────────────────────────────────────────┘


LAYER 6: Data Models & Normalization (FASE 1+3)
================================================
    ┌──────────────────────────────────────────────┐
    │  Pydantic v2 Models                           │
    ├──────────────────────────────────────────────┤
    │                                               │
    │  FASE 1 Models:                              │
    │  • OrderRequest                              │
    │  • OrderResult                               │
    │  • Enums: OrderStatus, OrderSide, OrderType  │
    │                                               │
    │  FASE 3 Models (MongoDB):                    │
    │  • Bot (with BotStatus enum)                 │
    │  • Order (with OrderStatus enum)             │
    │  • Position (with PositionStatus enum)       │
    │  • Trade (individual fill records)           │
    │  • Response models for API serialization     │
    │                                               │
    │  Type Safety:                                 │
    │  • PyObjectId custom type for MongoDB        │
    │  • Validation on all inputs                  │
    │  • Automatic serialization/deserialization   │
    │                                               │
    └──────────────────────────────────────────────┘


LAYER 7: Persistence (FASE 3)
==============================
    ┌──────────────────────────────────────────────┐
    │    MongoDB Collections                        │
    ├──────────────────────────────────────────────┤
    │                                               │
    │  bots Collection:                             │
    │  ├─ user_id (string, indexed)                │
    │  ├─ name, exchange, account_id               │
    │  ├─ symbol, strategy_type, config            │
    │  ├─ risk_config (leverage, max_position)     │
    │  ├─ status: stopped|running|error|paused     │
    │  ├─ trades_count, total_pnl                  │
    │  └─ created_at, updated_at, started_at       │
    │                                               │
    │  orders Collection:                           │
    │  ├─ user_id, bot_id (indexed)                │
    │  ├─ symbol, side, type, size, price          │
    │  ├─ take_profit, stop_loss                   │
    │  ├─ status: pending|open|filled|cancelled    │
    │  ├─ filled_size, average_fill_price, fee     │
    │  ├─ exchange_order_id (null until executed)  │
    │  ├─ client_oid (for idempotency)             │
    │  ├─ executions: array of fills               │
    │  ├─ retry_count, error_message               │
    │  └─ created_at, updated_at                   │
    │                                               │
    │  positions Collection:                        │
    │  ├─ user_id, bot_id (indexed)                │
    │  ├─ symbol, side, size                       │
    │  ├─ entry_price, entry_cost, entry_order_id  │
    │  ├─ exit_order_id (null until closed)        │
    │  ├─ status: opening|open|closing|closed      │
    │  ├─ current_price, unrealized_pnl            │
    │  ├─ realized_pnl (on close)                  │
    │  ├─ take_profit_price, stop_loss_price       │
    │  └─ opened_at, closed_at                     │
    │                                               │
    │  trades Collection:                           │
    │  ├─ user_id, order_id (indexed)              │
    │  ├─ symbol, side                             │
    │  ├─ filled_size, filled_price, fee           │
    │  ├─ exchange_trade_id                        │
    │  └─ executed_at                              │
    │                                               │
    │  user_exchange_credentials Collection:        │
    │  ├─ user_id, exchange (unique index)         │
    │  ├─ api_key_encrypted (Fernet)               │
    │  ├─ api_secret_encrypted (Fernet)            │
    │  ├─ passphrase_encrypted (Fernet)            │
    │  └─ created_at, updated_at                   │
    │                                               │
    │  Indexes:                                     │
    │  • bots: (user_id, 1), (user_id, status, 1) │
    │  • orders: (user_id, 1), (client_oid, 1)    │
    │  • positions: (user_id, status, 1)           │
    │  • trades: (order_id, 1), (executed_at, -1)  │
    │                                               │
    └──────────────────────────────────────────────┘


Data Flow Example: Place Order
===============================

1. HTTP Request arrives:
   POST /api/orders/place
   {user_id, bot_id, symbol, side, type, size, price}

2. AuthorizationMiddleware validates Bearer token
   ↓ Extracts user_id from token

3. RequestLoggingMiddleware logs request
   ↓ LogSanitizer removes sensitive data

4. /api/orders/place router handler called
   ↓ Calls OrderService.create_order()

5. OrderService.create_order():
   • Create Order document (status=PENDING)
   • Insert into MongoDB orders collection
   ↓ Returns order_id

6. OrderService.validate_and_execute_order():
   ├─ Get RiskManager
   ├─ Get current account_balance from KuCoin API
   ├─ RiskManager.validate_order(): Check size, balance, leverage
   ├─ If VALID:
   │  ├─ Get OrderManager
   │  ├─ OrderManager.execute_order(): Place order with KuCoin
   │  ├─ Receive exchange_order_id from KuCoin
   │  ├─ Update MongoDB: status=OPEN, exchange_order_id=...
   │  └─ Create Position document (entry_order_id=order_id)
   └─ If INVALID:
      └─ Update MongoDB: status=REJECTED, error_message=...

7. Return HTTP response:
   {id, status, exchange_order_id, ...}

8. Client can now:
   • GET /api/orders/{order_id} → Check status
   • GET /api/positions → See unrealized PnL
   • POST /api/orders/{order_id}/cancel → Cancel if not filled
   • WebSocket → Real-time updates


Per-User Isolation
===================

All queries include user_id filter:

    # Find user's bots
    db.bots.find({"user_id": "user123"})
    
    # Find user's orders
    db.orders.find({"user_id": "user123"})
    
    # Find user's positions
    db.positions.find({"user_id": "user123"})
    
    # Get user's credentials (encrypted)
    db.user_exchange_credentials.find_one({"user_id": "user123", "exchange": "kucoin"})

This ensures:
• Each user only sees their own data
• No cross-user data leakage
• Credentials encrypted at rest
• Credential access only by authorized user


Atomic Operations
=================

OrderService.validate_and_execute_order() updates are atomic:

    // Update status and exchange_order_id atomically
    db.orders.update_one(
        {"_id": order_id, "user_id": user_id},
        {"$set": {
            "status": "open",
            "exchange_order_id": kucoin_order_id,
            "updated_at": now()
        }}
    )

PositionService.record_execution() is atomic:

    db.positions.update_one(
        {"_id": position_id, "user_id": user_id},
        {"$inc": {"filled_size": fill_size}}  // Increment atomically
    )
    db.positions.update_one(
        {"_id": position_id, "user_id": user_id},
        {"$set": {"average_fill_price": new_avg}}
    )
    db.trades.insert_one(trade_document)


Error Handling
==============

Errors propagate with context:

    try:
        result = await order_manager.execute_order(order_request)
    except Exception as e:
        # Update order status in database
        await orders_collection.update_one(
            {"_id": order_id},
            {
                "$set": {
                    "status": OrderStatus.FAILED,
                    "error_message": str(e),
                    "retry_count": retry_count + 1
                }
            }
        )
        # LogSanitizer removes API keys from error message
        logger.error(f"Order failed: {sanitizer.sanitize(str(e))}")
        # Return error to client
        raise


Performance Optimizations
=========================

1. Index Usage:
   • Quick lookups: user_id + status
   • Sorting: created_at descending
   • Uniqueness: client_oid for idempotency

2. Lazy Loading:
   • Don't load all user's orders at once
   • Paginate results: limit(20), skip(page*20)
   • Filter by status before loading

3. Caching (future):
   • Cache current prices for 5 seconds
   • Cache user's account balance for 30 seconds
   • Cache position statistics

4. Batch Operations:
   • Multiple position updates in single transaction
   • Trade execution in batch before DB write


Testing Coverage
================

test_integration_fase123.py includes:

1. FASE 2 Security Pipeline
   • LogSanitizer removes secrets
   • CredentialEncryption works correctly
   • CredentialStore model structure

2. FASE 1 Order Validation
   • RiskManager validates order safety
   • OrderManager executes orders
   • Mock KuCoin API responses

3. FASE 3 Database Models
   • Bot model creation
   • Order model creation
   • Position model with PnL
   • Response models serialization

4. Complete Integration Flow
   • HTTP Request → Auth → RiskManager → OrderManager → DB
   • All 6 layers working together

5. Service Layer Structure
   • BotService methods available
   • OrderService integration points
   • PositionService PnL calculation


Deployment Checklist
====================

✓ FASE 1 - Foundations (already complete)
✓ FASE 2 - Security & API (complete)
✓ FASE 3 - Database & Services (complete)

Ready for:
⏳ Integration testing in staging
⏳ Performance load testing
⏳ Security audit (encryption, auth)
⏳ Database backup strategy
⏳ Monitoring & alerting setup
⏳ Production deployment

Production Requirements:
• MongoDB Atlas with backup
• API key encryption in .env
• HTTPS/TLS for all traffic
• Rate limiting on HTTP endpoints
• WebSocket heartbeat monitoring
• Order execution logging
• Trade audit trail
• PnL calculations verified
"""
