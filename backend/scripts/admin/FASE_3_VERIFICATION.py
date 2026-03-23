"""
FASE 3 Implementation - Integration Checklist & Verification
=============================================================

Use this checklist to verify all components are working correctly after startup.
"""


FASE 2 Security Layer Startup
==============================

✓ Check: LogSanitizer initialized
  Command: Check logs for "🔐 LogSanitizer initialized"
  Expected: No API keys visible in any log message
  Verification:
    - Place an order with sensitive credentials
    - Check application logs
    - Verify API keys are redacted as "***"
    
✓ Check: CredentialEncryption initialized  
  Command: Check .env for CREDENTIAL_ENCRYPTION_KEY
  Expected: Base64-encoded Fernet key present
  Verification:
    - Key should start with standard Fernet key format
    - Length should be 44+ characters
    
✓ Check: CredentialStore working
  Command: Test POST /api/exchanges/setup
  Expected: 
    - Endpoint returns 200 OK
    - MongoDB user_exchange_credentials collection created
    - Credentials stored encrypted
  Verification:
    curl -X POST http://localhost:8000/api/exchanges/setup \
      -H "Authorization: Bearer user123" \
      -H "Content-Type: application/json" \
      -d '{
        "exchange": "kucoin",
        "api_key": "test_key",
        "api_secret": "test_secret",
        "passphrase": "test_passphrase"
      }'

✓ Check: Middleware chain working
  Command: Test any endpoint with invalid token
  Expected: 401 Unauthorized response
  Verification:
    curl -X GET http://localhost:8000/api/bots \
      -H "Authorization: Bearer invalid_token"
    # Should return 401


FASE 1 Core Layer Startup  
==========================

✓ Check: RiskManager initialized
  Command: Check logs for "RiskManager initialized"
  Expected: RiskManager singleton available globally
  Verification:
    from app.core.engines import get_risk_manager
    risk_mgr = get_risk_manager()
    assert risk_mgr is not None

✓ Check: OrderManager initialized
  Command: Check logs for "OrderManager initialized"
  Expected: OrderManager singleton available globally
  Verification:
    from app.core.engines import get_order_manager
    order_mgr = get_order_manager()
    assert order_mgr is not None

✓ Check: KuCoinRawClient pool ready
  Command: Check logs for "KuCoinRawClient pool initialized"
  Expected: Client ready to make API calls
  Verification:
    Run validate_fase2.py script - should complete without errors


FASE 3 Database Layer Startup
==============================

✓ Check: MongoDB connection established
  Command: Check logs for "✅ FASE 3 initialization complete!"
  Expected: All collections created, indexes built
  Verification:
    # In MongoDB shell or MongoDB Compass:
    db.bots.getIndexes()
    db.orders.getIndexes()
    db.positions.getIndexes()
    db.trades.getIndexes()
    # Should show indexes on user_id, status, etc.

✓ Check: BotService initialized
  Command: Check startup logs for "BotService initialized"
  Expected: BotService singleton available
  Verification:
    from app.db.bot_service import get_bot_service
    bot_service = get_bot_service()
    assert bot_service is not None

✓ Check: OrderService initialized with RiskManager/OrderManager
  Command: Check startup logs for "OrderService initialized"
  Expected: OrderService has access to FASE 1 components
  Verification:
    from app.db.order_service import get_order_service
    order_service = get_order_service()
    # Check that order_service can call RiskManager
    assert hasattr(order_service, 'validate_and_execute_order')

✓ Check: PositionService initialized
  Command: Check startup logs for "PositionService initialized"
  Expected: PositionService singleton available
  Verification:
    from app.db.position_service import get_position_service
    pos_service = get_position_service()
    assert pos_service is not None


Integration Point Verification
===============================

Test: RiskManager → OrderManager → Database Flow
================================================

Setup:
1. Start the application: python -m uvicorn app.main:app --reload
2. Create a test bot and exchange credentials
3. Run the following verification:

    import asyncio
    from decimal import Decimal
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # Step 1: Setup credentials
    response = client.post("/api/exchanges/setup", 
        headers={"Authorization": "Bearer testuser"},
        json={
            "exchange": "kucoin",
            "api_key": os.getenv("KUCOIN_API_KEY"),
            "api_secret": os.getenv("KUCOIN_API_SECRET"),
            "passphrase": os.getenv("KUCOIN_API_PASSPHRASE")
        }
    )
    assert response.status_code == 200, "Credentials setup failed"
    print("✓ Credentials stored and encrypted")
    
    # Step 2: Create a bot
    response = client.post("/api/bots",
        headers={"Authorization": "Bearer testuser"},
        json={
            "name": "Test Bot",
            "exchange": "kucoin",
            "account_id": "account123",
            "symbol": "BTC-USDT",
            "strategy_type": "dca",
            "config": {"interval": "1h"},
            "risk_config": {
                "max_position_size": 1,
                "leverage": 1,
                "stop_loss_percent": 5
            }
        }
    )
    assert response.status_code == 200, "Bot creation failed"
    bot_id = response.json()["id"]
    print(f"✓ Bot created: {bot_id}")
    
    # Step 3: Place an order (tests RiskManager → OrderManager → DB)
    response = client.post("/api/orders/place",
        headers={"Authorization": "Bearer testuser"},
        json={
            "bot_id": bot_id,
            "symbol": "BTC-USDT",
            "side": "buy",
            "type": "limit",
            "size": 0.01,
            "price": 45000,
            "stop_loss": 40000,
            "take_profit": 50000
        }
    )
    assert response.status_code == 200, "Order placement failed"
    order_id = response.json()["id"]
    print(f"✓ Order placed: {order_id}")
    
    # Step 4: Verify order in database
    response = client.get(f"/api/orders/{order_id}",
        headers={"Authorization": "Bearer testuser"}
    )
    assert response.status_code == 200, "Order retrieval failed"
    order = response.json()
    assert order["status"] in ["pending", "open"]
    print(f"✓ Order status verified: {order['status']}")
    
    # Step 5: Verify position created
    response = client.get("/api/positions",
        headers={"Authorization": "Bearer testuser"}
    )
    assert response.status_code == 200, "Position retrieval failed"
    positions = response.json()
    assert len(positions) > 0, "Position not created"
    print(f"✓ Position created with unrealized PnL")


Database Collection Verification
=================================

Verify collections exist and have correct structure:

    # In MongoDB shell:
    
    # Check bots collection
    db.bots.findOne()
    # Expected output includes: user_id, name, exchange, status, trades_count, total_pnl
    
    # Check orders collection
    db.orders.findOne()
    # Expected output includes: user_id, bot_id, symbol, status, exchange_order_id, client_oid
    
    # Check positions collection
    db.positions.findOne()
    # Expected output includes: user_id, bot_id, symbol, entry_price, unrealized_pnl
    
    # Check trades collection
    db.trades.findOne()
    # Expected output includes: user_id, order_id, filled_price, fee, exchange_trade_id
    
    # Check user_exchange_credentials collection
    db.user_exchange_credentials.findOne()
    # Expected output includes: user_id, exchange, api_key_encrypted (binary), api_secret_encrypted
    
    # Verify encryption - credentials should be encrypted (not readable):
    db.user_exchange_credentials.findOne()
    # api_key_encrypted should be binary data, not plain text


Verify Indexes
==============

    # In MongoDB shell:
    
    # Check bots indexes
    db.bots.getIndexes()
    # Should include: user_id, (user_id, exchange), (user_id, status)
    
    # Check orders indexes  
    db.orders.getIndexes()
    # Should include: user_id, (user_id, bot_id), (user_id, status), client_oid, (created_at, -1)
    
    # Check positions indexes
    db.positions.getIndexes()
    # Should include: user_id, (user_id, bot_id), (user_id, status), symbol
    
    # Check trades indexes
    db.trades.getIndexes()
    # Should include: user_id, (user_id, order_id), exchange_trade_id, (executed_at, -1)


API Endpoints Testing
====================

Test FASE 2 Security Endpoints:

✓ POST /api/exchanges/setup
  curl -X POST http://localhost:8000/api/exchanges/setup \
    -H "Authorization: Bearer user123" \
    -H "Content-Type: application/json" \
    -d '{"exchange": "kucoin", "api_key": "...", "api_secret": "...", "passphrase": "..."}'
  Expected: 200 OK

✓ GET /api/exchanges
  curl -X GET http://localhost:8000/api/exchanges \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, list of connected exchanges

✓ POST /api/exchanges/verify
  curl -X POST http://localhost:8000/api/exchanges/verify \
    -H "Authorization: Bearer user123" \
    -H "Content-Type: application/json" \
    -d '{"exchange": "kucoin"}'
  Expected: 200 OK, verified account info from KuCoin

✓ DELETE /api/exchanges/kucoin
  curl -X DELETE http://localhost:8000/api/exchanges/kucoin \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, credentials removed

Test FASE 3 Bot Endpoints:

✓ POST /api/bots (create)
  curl -X POST http://localhost:8000/api/bots \
    -H "Authorization: Bearer user123" \
    -H "Content-Type: application/json" \
    -d '{"name": "Bot1", "exchange": "kucoin", ...}'
  Expected: 200 OK, returns bot_id

✓ GET /api/bots (list)
  curl -X GET http://localhost:8000/api/bots \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, list of user's bots

✓ POST /api/bots/{bot_id}/start
  curl -X POST http://localhost:8000/api/bots/bot123/start \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, bot status changes to running

✓ POST /api/bots/{bot_id}/stop
  curl -X POST http://localhost:8000/api/bots/bot123/stop \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, bot status changes to stopped

Test FASE 3 Order Endpoints:

✓ POST /api/orders/place
  curl -X POST http://localhost:8000/api/orders/place \
    -H "Authorization: Bearer user123" \
    -H "Content-Type: application/json" \
    -d '{"bot_id": "bot123", "symbol": "BTC-USDT", "side": "buy", ...}'
  Expected: 200 OK, order created and executed (RiskManager → OrderManager → DB)

✓ GET /api/orders
  curl -X GET http://localhost:8000/api/orders \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, list of user's orders

✓ POST /api/orders/{order_id}/cancel
  curl -X POST http://localhost:8000/api/orders/order123/cancel \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, order status changes to cancelled

✓ GET /api/positions
  curl -X GET http://localhost:8000/api/positions \
    -H "Authorization: Bearer user123"
  Expected: 200 OK, list of open positions with unrealized PnL


Security Verification
====================

✓ Check: API keys not in logs
  1. Tail application logs: tail -f app.log
  2. Place an order with credentials
  3. Grep for API keys: grep -i "apikey\\|secret\\|token" app.log
  Expected: No API keys found (redacted as ***)

✓ Check: Credentials encrypted in database
  1. Get stored credential: db.user_exchange_credentials.findOne()
  2. Check api_key_encrypted field
  Expected: Binary data (Fernet formatted), not plain text

✓ Check: Bearer token validation
  1. Try request without Authorization header: curl http://localhost:8000/api/bots
  Expected: 401 Unauthorized

✓ Check: Cross-user isolation
  1. Create order as user123
  2. Try to access as user456: GET /api/orders - with Bearer user456
  Expected: Order not visible (user456 doesn't see user123's data)


Performance Testing
==================

Load test the service layer:

    import asyncio
    import time
    from decimal import Decimal
    
    async def load_test():
        from app.db.order_service import get_order_service
        from app.core.engines import get_risk_manager, get_order_manager
        
        order_service = get_order_service()
        risk_manager = get_risk_manager()
        
        # Test 1: Create 100 orders rapidly
        start = time.time()
        for i in range(100):
            await order_service.create_order(
                user_id="user123",
                bot_id="bot123",
                symbol="BTC-USDT",
                side="buy",
                order_type="limit",
                size=Decimal("0.01"),
                price=Decimal("45000"),
                stop_loss=Decimal("40000"),
                take_profit=Decimal("50000")
            )
        elapsed = time.time() - start
        print(f"Created 100 orders in {elapsed:.2f}s ({100/elapsed:.0f} ops/sec)")
        
        # Test 2: Risk validation speed (should be < 100ms per order)
        start = time.time()
        is_valid, error = await risk_manager.validate_order(
            user_id="user123",
            symbol="BTC-USDT",
            side="buy",
            size=Decimal("0.01"),
            price=Decimal("45000"),
            stop_loss=Decimal("40000"),
            account_balance=Decimal("10000"),
            risk_config={"max_position_size": 1, "leverage": 1}
        )
        elapsed = (time.time() - start) * 1000
        print(f"Risk validation: {elapsed:.2f}ms")
        assert elapsed < 100, "Risk validation too slow"
        
        # Test 3: List orders with filters (should be < 50ms)
        start = time.time()
        orders = await order_service.list_orders(
            user_id="user123",
            bot_id="bot123",
            status=None,
            limit=50
        )
        elapsed = (time.time() - start) * 1000
        print(f"List orders: {elapsed:.2f}ms")
        assert elapsed < 50, "Order listing too slow (check indexes)"
    
    asyncio.run(load_test())


Troubleshooting
===============

Problem: "OrderService not initialized"
Solution: Verify init_fase_3() is called in main.py startup event

Problem: "RiskManager validation failing"
Solution: Check account_balance parameter is being passed correctly

Problem: "Orders not appearing in MongoDB"
Solution: Verify database_init.py was called and collections exist

Problem: "API keys visible in logs"
Solution: Check LogSanitizer is initialized and PATTERNS are correct

Problem: "Orders placed but trade not executed"
Solution: Check OrderManager.execute_order() for KuCoin API errors

Problem: "Position PnL calculation incorrect"
Solution: Verify formula: For LONG: (current_price - entry_price) * size

Problem: "Cross-user data leakage"
Solution: Check all queries include user_id filter


Monitoring & Alerts
===================

Key metrics to monitor:

1. Order Execution Time
   - RiskManager validation: target < 100ms
   - OrderManager execution: target < 500ms
   - Database write: target < 50ms
   
2. Error Rates
   - Failed orders: track why orders are rejected
   - MongoDB connection errors: auto-reconnect handled?
   - KuCoin API errors: rate limits, credentials?
   
3. Data Accuracy
   - Filled sizes match KuCoin reports
   - PnL calculations verified against manual calculation
   - No orders stuck in "pending" state

4. Security
   - No API keys in logs
   - Credentials encrypted at rest
   - Bearer token validation on all endpoints
   
5. Performance
   - Average response time for /api/orders/place
   - Average response time for /api/positions
   - MongoDB query performance (use explain())


Production Checklist
====================

Before deploying to production:

□ All FASE 1+2+3 tests passing
□ Security audit completed
□ Load testing completed (1000+ orders/sec)
□ MongoDB backup configured
□ API key rotation policy in place
□ Error logging and monitoring setup
□ Rate limiting configured
□ WebSocket reconnection tested
□ Database indexes verified
□ Cross-user isolation tested
□ Order idempotency (client_oid) tested
□ Graceful error handling verified
□ Encryption keys securely stored
□ HTTPS/TLS configured
□ CORS properly configured
□ Rate limits per IP configured
□ Audit trail logging enabled
□ PnL calculations verified
□ Disaster recovery plan documented
"""
