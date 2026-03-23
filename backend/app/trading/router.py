"""
Real trading API endpoints
"""
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Query

from app.services.redis_manager import redis_manager
from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.encryption import encrypt_kucoin_credentials
from app.users.model import User
from app.trading.service import get_trading_service, TradingService
from app.trading.schemas import (
    TradingCredentials, PlaceOrderRequest, OrderResponse,
    AccountBalance, RealTradeCreate, TradingSessionCreate,
    TradingSessionResponse, RealTimeData,
    # New multi-exchange schemas
    ExchangeCredentialsCreate, ExchangeCredentialsResponse,
    TestCredentialsRequest, TestCredentialsResponse,
    BalanceRequest, ExchangeType
)
from app.trading.models import TradingSession, RealTrade, RealTimeMarketData
from app.trading.credentials_repository import CredentialsRepository
from app.trading.ccxt_exchange_service import (
    CCXTExchangeService,
    test_exchange_credentials,
    get_user_balances
)
from app.core.metrics import trades_executed_total

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trading", tags=["trading"])

# WebSocket connection manager (Redis-based for scalability)
manager = redis_manager


# ==================== CREDENTIALS ENDPOINTS ====================

@router.get("/auth/verify")
async def verify_token(
    current_user: dict = Depends(get_current_user)
):
    """
    Verify if the current token is valid.
    """
    return {
        "status": "valid",
        "user_id": str(current_user.get("_id")),
        "email": current_user.get("email")
    }


@router.post("/kucoin/connect")
async def connect_kucoin_simple(
    request_body: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Simple endpoint to connect KuCoin credentials.
    """
    db = get_db()
    
    try:
        logger.info(f"🔵 KuCoin connect request from user: {current_user.get('_id')}")
        
        # Get credentials from body
        api_key = request_body.get("api_key", "").strip()
        api_secret = request_body.get("api_secret", "").strip()
        api_passphrase = request_body.get("api_passphrase", "").strip()
        
        # Validate
        if not api_key or not api_secret or not api_passphrase:
            logger.warning(f"⚠️ Missing credentials from user {current_user.get('_id')}")
            return {
                "status": "error",
                "message": "API Key, Secret e Passphrase são obrigatórios"
            }
        
        # Encrypt
        encrypted = encrypt_kucoin_credentials(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase
        )
        
        # Save
        user_id = str(current_user.get("_id"))
        result = await db["trading_credentials"].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "api_key_enc": encrypted["api_key_enc"],
                    "api_secret_enc": encrypted["api_secret_enc"],
                    "api_passphrase_enc": encrypted["api_passphrase_enc"],
                    "is_sandbox": True,
                    "is_active": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ KuCoin connected successfully for user {user_id}")
        
        return {
            "status": "success",
            "message": "Credenciais conectadas com sucesso!",
            "connected": True
        }
        
    except Exception as e:
        logger.error(f"❌ Error connecting KuCoin: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Erro ao conectar: {str(e)}"
        }


@router.post("/credentials", response_model=ExchangeCredentialsResponse, status_code=201)
async def create_credentials(
    credentials: ExchangeCredentialsCreate,
    current_user: User = Depends(get_current_user),
):
    """
    Create or update exchange credentials.
    
    The credentials are validated by testing the connection to the exchange
    before being encrypted and stored.
    
    Supports: Binance, KuCoin
    """
    try:
        # Test credentials first
        test_result = await test_exchange_credentials(
            exchange=credentials.exchange.value,
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            passphrase=credentials.passphrase,
            is_testnet=credentials.is_testnet
        )
        
        if not test_result.get("valid"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid credentials: {test_result.get('error', 'Unknown error')}"
            )
        
        # Save credentials (encrypted)
        saved = await CredentialsRepository.save_credentials(
            user_id=str(current_user.id),
            exchange=credentials.exchange.value,
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            passphrase=credentials.passphrase,
            is_testnet=credentials.is_testnet,
            label=credentials.label
        )
        
        return ExchangeCredentialsResponse(
            id=str(saved.get("_id", "")),
            exchange=saved.get("exchange", ""),
            api_key_partial=saved.get("api_key_partial", "****"),
            is_testnet=saved.get("is_testnet", True),
            is_active=saved.get("is_active", True),
            label=saved.get("label"),
            created_at=saved.get("created_at"),
            updated_at=saved.get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating credentials for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save credentials")


@router.post("/credentials/test", response_model=TestCredentialsResponse)
async def test_credentials(
    credentials: TestCredentialsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test exchange credentials without saving.
    
    Use this to verify API keys are valid before saving.
    """
    try:
        result = await test_exchange_credentials(
            exchange=credentials.exchange.value,
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            passphrase=credentials.passphrase,
            is_testnet=credentials.is_testnet
        )
        return TestCredentialsResponse(**result)
    except Exception as e:
        logger.error(f"Error testing credentials: {e}")
        return TestCredentialsResponse(
            valid=False,
            error=str(e)
        )


@router.get("/credentials", response_model=List[ExchangeCredentialsResponse])
async def get_user_credentials(
    current_user: User = Depends(get_current_user)
):
    """Get all saved credentials for the current user (no sensitive data)."""
    try:
        credentials = await CredentialsRepository.get_user_credentials(
            user_id=str(current_user.id),
            include_inactive=False
        )
        
        return [
            ExchangeCredentialsResponse(
                id=str(cred.get("_id", "")),
                exchange=cred.get("exchange", ""),
                api_key_partial=cred.get("api_key_partial", "****"),
                is_testnet=cred.get("is_testnet", True),
                is_active=cred.get("is_active", True),
                label=cred.get("label"),
                created_at=cred.get("created_at"),
                updated_at=cred.get("updated_at")
            )
            for cred in credentials
        ]
    except Exception as e:
        logger.error(f"Error getting credentials for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get credentials")


@router.delete("/credentials/{exchange}")
async def delete_credentials(
    exchange: ExchangeType,
    current_user: User = Depends(get_current_user)
):
    """Delete credentials for a specific exchange."""
    try:
        result = await CredentialsRepository.deactivate_credentials(
            user_id=str(current_user.id),
            exchange=exchange.value
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Credentials not found")
        
        return {"message": f"Credentials for {exchange.value} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting credentials for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete credentials")


# ==================== BALANCE ENDPOINTS ====================

@router.get("/account/balances", response_model=List[AccountBalance])
async def get_balances(
    exchange: ExchangeType = Query(..., description="Exchange to fetch balances from"),
    min_balance: float = Query(0.0, ge=0, description="Minimum balance to include"),
    current_user: User = Depends(get_current_user)
):
    """
    Get account balances from an exchange.
    
    Requires valid saved credentials for the specified exchange.
    """
    try:
        balances = await get_user_balances(
            user_id=str(current_user.id),
            exchange=exchange.value,
            min_balance=min_balance
        )
        
        return [
            AccountBalance(
                asset=b["asset"],
                free=b["free"],
                locked=b["locked"],
                total=b["total"]
            )
            for b in balances
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting balances for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get account balances")


# ==================== LEGACY ENDPOINTS (for backwards compatibility) ====================

@router.get("/credentials/test-legacy")
async def test_credentials_legacy(
    credentials: TradingCredentials,
    current_user: User = Depends(get_current_user)
):
    """Test trading credentials (legacy Binance-only endpoint)"""
    result = await test_exchange_credentials(
        exchange="binance",
        api_key=credentials.api_key,
        api_secret=credentials.api_secret,
        is_testnet=credentials.testnet
    )
    return result

@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order: PlaceOrderRequest,
    current_user: User = Depends(get_current_user)
):
    """Place a trading order"""
    trading_service = get_trading_service()
    try:
        result = await trading_service.place_order(current_user.id, order)
        # Increment trades counter on successful order placement
        trades_executed_total.inc()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error placing order for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to place order")

@router.post("/sessions", response_model=TradingSessionResponse)
async def create_trading_session(
    session_data: TradingSessionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Create a new trading session"""
    trading_service = get_trading_service()
    try:
        session = await trading_service.create_trading_session(current_user.id, session_data)
        
        # Return session response
        return TradingSessionResponse(
            id=session.id,
            bot_instance_id=session.bot_instance_id,
            symbol=session.symbol,
            initial_balance=session.initial_balance,
            current_balance=session.current_balance,
            total_trades=session.total_trades,
            profitable_trades=session.profitable_trades,
            total_pnl=session.total_pnl,
            max_drawdown=session.max_drawdown,
            is_active=session.is_active,
            started_at=session.started_at,
            ended_at=session.ended_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating trading session for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create trading session")

@router.get("/sessions", response_model=List[TradingSessionResponse])
async def get_trading_sessions(
    current_user: User = Depends(get_current_user)
):
    """Get user's trading sessions"""
    db = get_db()
    user_id = str(current_user.get("_id", getattr(current_user, "id", None)))
    cursor = db["trading_sessions"].find({"user_id": user_id, "is_active": True}).sort("started_at", -1)
    sessions = []
    async for s in cursor:
        try:
            sessions.append(TradingSessionResponse(
                id=str(s["_id"]),
                bot_instance_id=str(s.get("bot_instance_id", "")),
                symbol=s.get("symbol", ""),
                initial_balance=s.get("initial_balance", 0),
                current_balance=s.get("current_balance", 0),
                total_trades=s.get("total_trades", 0),
                profitable_trades=s.get("profitable_trades", 0),
                total_pnl=s.get("total_pnl", 0),
                max_drawdown=s.get("max_drawdown", 0),
                is_active=s.get("is_active", True),
                started_at=s.get("started_at"),
                ended_at=s.get("ended_at")
            ))
        except Exception:
            pass
    return sessions

@router.get("/sessions/{session_id}/performance")
async def get_session_performance(
    session_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get trading session performance data"""
    trading_service = get_trading_service()
    try:
        performance = await trading_service.get_session_performance(session_id)
        return performance
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting session performance {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session performance")

@router.post("/sessions/{session_id}/stop")
async def stop_trading_session(
    session_id: int,
    current_user: User = Depends(get_current_user)
):
    """Stop a trading session"""
    trading_service = get_trading_service()
    try:
        await trading_service.stop_trading_session(session_id)
        return {"message": "Trading session stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop trading session")

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: int
):
    """WebSocket endpoint for real-time trading data"""
    await manager.connect(websocket, session_id)
    try:
        # Send initial session data
        trading_service = get_trading_service()
        performance = await trading_service.get_session_performance(session_id)
        await websocket.send_json({
            "type": "initial_data",
            "data": performance
        })
        
        # Keep connection alive and send periodic updates
        while True:
            # Wait for new data or send periodic updates
            await asyncio.sleep(5)  # Update every 5 seconds
            
            # Get latest performance data
            try:
                performance = await trading_service.get_session_performance(session_id)
                await websocket.send_json({
                    "type": "performance_update",
                    "data": {
                        "stats": performance["stats"],
                        "latest_trades": performance["trades"][-10:],  # Last 10 trades
                        "latest_market_data": performance["market_data"][-50:]  # Last 50 candlesticks
                    }
                })
            except Exception as e:
                logger.error(f"Error sending performance update: {e}")
                break
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(websocket, session_id)

@router.get("/sessions/{session_id}/trades")
async def get_session_trades(
    session_id: int,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get trades for a trading session"""
    db = get_db()
    cursor = db["trades"].find(
        {"trading_session_id": str(session_id)}
    ).skip(offset).limit(limit).sort("created_at", -1)
    trades = []
    async for trade in cursor:
        trade["_id"] = str(trade["_id"])
        trades.append({
            "id": str(trade.get("_id")),
            "symbol": trade.get("symbol", ""),
            "side": trade.get("side", "buy"),
            "order_type": trade.get("order_type", "market"),
            "quantity": trade.get("quantity", 0),
            "price": trade.get("price", 0),
            "executed_price": trade.get("executed_price"),
            "executed_quantity": trade.get("executed_quantity"),
            "status": trade.get("status", "pending"),
            "pnl": trade.get("pnl"),
            "commission": trade.get("commission"),
            "created_at": trade.get("created_at", ""),
            "filled_at": trade.get("filled_at"),
            "entry_reason": trade.get("entry_reason"),
            "exit_reason": trade.get("exit_reason")
        })
    return trades

@router.get("/sessions/{session_id}/chart-data")
async def get_chart_data(
    session_id: int,
    interval: str = "1m",
    limit: int = 500,
    current_user: User = Depends(get_current_user)
):
    """Get chart data for a trading session"""
    db = get_db()
    cursor = db["market_data"].find(
        {"trading_session_id": str(session_id), "data_type": "kline"}
    ).sort("timestamp", -1).limit(limit)
    data_list = []
    async for data in cursor:
        data_list.append({
            "timestamp": str(data.get("timestamp", "")),
            "open": data.get("open_price", 0),
            "high": data.get("high_price", 0),
            "low": data.get("low_price", 0),
            "close": data.get("close_price", 0),
            "volume": data.get("volume", 0)
        })
    return list(reversed(data_list))

@router.get("/symbols")
async def get_trading_symbols():
    """Get available trading symbols from KuCoin (cached 5 min)."""
    import aiohttp
    from app.services.redis_manager import redis_manager

    cache_key = "kucoin:symbols:list"
    cached = None
    try:
        cached = await redis_manager.get(cache_key)
    except Exception:
        pass

    if cached:
        import json
        return json.loads(cached)

    # Fetch from KuCoin public API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.kucoin.com/api/v1/symbols",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    symbols_raw = data.get("data", [])
                    symbols = [
                        {
                            "symbol": s["symbol"],
                            "name": s.get("name", s["symbol"]),
                            "baseCurrency": s.get("baseCurrency", ""),
                            "quoteCurrency": s.get("quoteCurrency", ""),
                            "enableTrading": s.get("enableTrading", False),
                        }
                        for s in symbols_raw
                        if s.get("enableTrading")
                    ]
                    # Cache for 5 minutes
                    try:
                        import json
                        await redis_manager.set(cache_key, json.dumps(symbols), ex=300)
                    except Exception:
                        pass
                    return symbols
    except Exception as e:
        logger.warning(f"Failed to fetch symbols from KuCoin: {e}")

    # Fallback to popular symbols if KuCoin API is unreachable
    popular_symbols = [
        "BTC-USDT", "ETH-USDT", "BNB-USDT", "ADA-USDT", "DOT-USDT",
        "XRP-USDT", "LTC-USDT", "LINK-USDT", "SOL-USDT", "AVAX-USDT",
        "UNI-USDT", "MATIC-USDT", "FIL-USDT", "TRX-USDT", "ETC-USDT",
    ]
    return [
        {"symbol": s, "name": s, "baseCurrency": s.split("-")[0], "quoteCurrency": "USDT", "enableTrading": True}
        for s in popular_symbols
    ]

@router.get("/market-data/{symbol}")
async def get_market_data(
    symbol: str,
    interval: str = "1hour",
    limit: int = 100
):
    """Get real OHLCV market data from KuCoin (public endpoint, no auth needed)."""
    import aiohttp
    import time as _time

    # Map common interval aliases to KuCoin format
    interval_map = {
        "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
        "1h": "1hour", "2h": "2hour", "4h": "4hour", "6h": "6hour",
        "1d": "1day", "1w": "1week",
    }
    kucoin_interval = interval_map.get(interval, interval)

    tf_seconds = {
        "1min": 60, "3min": 180, "5min": 300, "15min": 900, "30min": 1800,
        "1hour": 3600, "2hour": 7200, "4hour": 14400, "6hour": 21600,
        "8hour": 28800, "12hour": 43200, "1day": 86400, "1week": 604800,
    }
    period = tf_seconds.get(kucoin_interval, 3600)
    end_at = int(_time.time())
    start_at = end_at - (period * limit)

    # Normalize symbol format: "BTCUSDT" → "BTC-USDT"
    kucoin_symbol = symbol.upper()
    if "-" not in kucoin_symbol and "USDT" in kucoin_symbol:
        kucoin_symbol = kucoin_symbol.replace("USDT", "-USDT")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.kucoin.com/api/v1/market/candles",
                params={
                    "symbol": kucoin_symbol,
                    "type": kucoin_interval,
                    "startAt": start_at,
                    "endAt": end_at,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    raw = await resp.json()
                    rows = raw.get("data", [])
                    # KuCoin returns: [time, open, close, high, low, volume, turnover] newest-first
                    candles = []
                    for row in reversed(rows):
                        candles.append({
                            "timestamp": int(row[0]),
                            "open": float(row[1]),
                            "close": float(row[2]),
                            "high": float(row[3]),
                            "low": float(row[4]),
                            "volume": float(row[5]),
                            "turnover": float(row[6]) if len(row) > 6 else 0,
                        })
                    return {"symbol": symbol, "interval": interval, "data": candles[-limit:]}
    except Exception as e:
        logger.warning(f"Failed to fetch klines for {symbol}: {e}")

    return {"symbol": symbol, "interval": interval, "data": []}


@router.get("/kucoin/ws-token")
async def get_kucoin_ws_token():
    """Get a public WebSocket token from KuCoin for real-time market data (no auth needed)."""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.kucoin.com/api/v1/bullet-public",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    raw = await resp.json()
                    data = raw.get("data", {})
                    return {
                        "token": data.get("token", ""),
                        "instanceServers": data.get("instanceServers", []),
                    }
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=f"KuCoin bullet-public returned {resp.status}",
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to get KuCoin WS token: {e}")
        raise HTTPException(status_code=502, detail="Failed to get KuCoin WS token")


# ========================================
# KuCoin Integration (Nova - 2024)
# ========================================

from app.core.encryption import encrypt_kucoin_credentials, decrypt_kucoin_credentials
from app.trading.models import (
    KuCoinCredentialCreate,
    KuCoinCredentialResponse,
    KuCoinCredentialUpdate,
    KuCoinConnectionStatus,
)
from datetime import datetime

# NOTE: /kucoin/connect is already defined above (connect_kucoin_simple).
# The typed version below is available as /kucoin/connect-typed for structured requests.


@router.post("/kucoin/connect-typed", response_model=KuCoinCredentialResponse)
async def connect_kucoin(
    creds: KuCoinCredentialCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    ? Conecta conta KuCoin com seguran?a m?xima.
    
    Processo:
    1. Valida credenciais (Pydantic)
    2. Encripta com Fernet (256-bit)
    3. Salva em MongoDB
    4. Retorna resposta SEM secrets
    
    Seguran?a:
    - API Secret e Passphrase NUNCA s?o retornados
    - Dados encriptados em repouso
    - user_id extra?do do JWT (n?o do request body)
    """
    
    db = get_db()
    
    try:
        # 1. Encriptar credenciais ANTES de salvar
        encrypted = encrypt_kucoin_credentials(
            api_key=creds.api_key,
            api_secret=creds.api_secret,
            api_passphrase=creds.api_passphrase
        )
        
        # 2. Preparar documento para MongoDB
        credential_doc = {
            "user_id": str(current_user.get("_id")),
            **encrypted,  # api_key_enc, api_secret_enc, api_passphrase_enc
            "is_active": True,
            "is_sandbox": creds.is_sandbox,
            "created_at": datetime.utcnow(),
            "last_used": None,
        }
        
        # 3. Upsert: Substituir credenciais antigas ou criar novas
        result = await db["trading_credentials"].update_one(
            {"user_id": str(current_user.get("_id"))},
            {"$set": credential_doc},
            upsert=True
        )
        
        # 4. Retornar resposta segura (SEM secrets)
        return KuCoinCredentialResponse(
            id=str(result.upserted_id or result.matched_id),
            user_id=credential_doc["user_id"],
            is_active=credential_doc["is_active"],
            is_sandbox=credential_doc["is_sandbox"],
            created_at=credential_doc["created_at"],
            last_used=credential_doc.get("last_used"),
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Erro ao encriptar: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar: {str(e)}")


@router.get("/kucoin/status", response_model=KuCoinConnectionStatus)
async def get_kucoin_status(
    current_user: dict = Depends(get_current_user)
):
    """
    ? Verifica se KuCoin est? conectada e funcional.
    """
    
    db = get_db()
    
    try:
        cred_doc = await db["trading_credentials"].find_one(
            {"user_id": str(current_user.get("_id"))}
        )
        
        if not cred_doc or not cred_doc.get("is_active"):
            return KuCoinConnectionStatus(
                connected=False,
                status="not_configured",
                error="Credenciais não configuradas"
            )
        
        # Actually test the connection by trying to fetch account info
        try:
            decrypted = decrypt_kucoin_credentials(
                cred_doc.get("api_key_enc", ""),
                cred_doc.get("api_secret_enc", ""),
                cred_doc.get("api_passphrase_enc", "")
            )
            service = CCXTExchangeService(
                exchange="kucoin",
                api_key=decrypted["api_key"],
                api_secret=decrypted["api_secret"],
                passphrase=decrypted["api_passphrase"],
                is_testnet=cred_doc.get("is_sandbox", True)
            )
            # Light test: fetch balances with high min to minimize data
            await service.get_balances(min_balance=999999)
            
            return KuCoinConnectionStatus(
                connected=True,
                status="success",
                exchange_info={
                    "exchange": "KuCoin",
                    "mode": "sandbox" if cred_doc.get("is_sandbox") else "production"
                }
            )
        except Exception as test_err:
            logger.warning(f"KuCoin connection test failed: {test_err}")
            return KuCoinConnectionStatus(
                connected=False,
                status="credentials_invalid",
                error=f"Credenciais salvas mas conexão falhou: {str(test_err)}"
            )
        
    except Exception as e:
        return KuCoinConnectionStatus(
            connected=False,
            status="error",
            error=str(e)
        )


@router.put("/kucoin/update", response_model=KuCoinCredentialResponse)
async def update_kucoin_credential(
    update_data: KuCoinCredentialUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    ?? Edita is_active e is_sandbox.
    
    Para trocar API Key/Secret/Passphrase: Desconecte e conecte novamente.
    """
    
    db = get_db()
    
    try:
        update_dict = {}
        if update_data.is_active is not None:
            update_dict["is_active"] = update_data.is_active
        if update_data.is_sandbox is not None:
            update_dict["is_sandbox"] = update_data.is_sandbox
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
        
        result = await db["trading_credentials"].find_one_and_update(
            {"user_id": str(current_user.get("_id"))},
            {"$set": update_dict},
            return_document=True
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Credenciais n?o encontradas")
        
        return KuCoinCredentialResponse(
            id=str(result["_id"]),
            user_id=result["user_id"],
            is_active=result["is_active"],
            is_sandbox=result["is_sandbox"],
            created_at=result["created_at"],
            last_used=result.get("last_used"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/kucoin/disconnect")
async def disconnect_kucoin(
    current_user: dict = Depends(get_current_user)
):
    """
    ? Desconecta (deleta) credenciais KuCoin.
    
    As credenciais encriptadas s?o permanentemente removidas.
    """
    
    db = get_db()
    
    try:
        result = await db["trading_credentials"].delete_one(
            {"user_id": str(current_user.get("_id"))}
        )
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Nenhuma credencial para desconectar")
        
        return {
            "status": "success",
            "message": "Credenciais KuCoin desconectadas com sucesso"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kucoin/account")
async def get_kucoin_account(
    current_user: dict = Depends(get_current_user)
):
    """
    Get KuCoin account information for the authenticated user.
    """
    db = get_db()
    
    try:
        # Verify credentials exist
        cred_doc = await db["trading_credentials"].find_one(
            {"user_id": str(current_user.get("_id"))}
        )
        
        if not cred_doc:
            return {
                "status": "error",
                "message": "Credenciais não encontradas"
            }
        
        # Return account info; for real balances use /kucoin/balances
        return {
            "subUserId": str(current_user.get("_id")),
            "subName": current_user.get("name", "Main Account"),
            "remarks": None,
            "accountType": "trading",
            "status": "connected"
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching KuCoin account: {str(e)}")
        return {
            "status": "error",
            "message": f"Erro ao buscar conta: {str(e)}"
        }


@router.get("/kucoin/balances")
async def get_kucoin_balances(
    current_user: dict = Depends(get_current_user)
):
    """
    Get KuCoin account balances for all currencies.
    """
    db = get_db()
    
    try:
        # Verify credentials exist
        cred_doc = await db["trading_credentials"].find_one(
            {"user_id": str(current_user.get("_id"))}
        )
        
        if not cred_doc:
            return {
                "status": "error",
                "message": "Credenciais não encontradas"
            }
        
        # Fetch real balances via ccxt if available
        try:
            decrypted = decrypt_kucoin_credentials(
                cred_doc.get("api_key_enc", ""),
                cred_doc.get("api_secret_enc", ""),
                cred_doc.get("api_passphrase_enc", "")
            )
            service = CCXTExchangeService(
                exchange="kucoin",
                api_key=decrypted["api_key"],
                api_secret=decrypted["api_secret"],
                passphrase=decrypted["api_passphrase"],
                is_testnet=cred_doc.get("is_sandbox", True)
            )
            balances = await service.get_balances(min_balance=0.0)
            return {
                "status": "success",
                "balances": balances
            }
        except Exception as bal_err:
            logger.warning(f"Could not fetch live balances: {bal_err}")
            return {
                "status": "partial",
                "message": "Credenciais encontradas, mas não foi possível buscar saldos ao vivo",
                "balances": []
            }
        
    except Exception as e:
        logger.error(f"❌ Error fetching KuCoin balances: {str(e)}")
        return {
            "status": "error",
            "message": f"Erro ao buscar saldos: {str(e)}"
        }


@router.get("/rate-limit/status", tags=["trading"])
async def get_rate_limit_status(
    current_user: dict = Depends(get_current_user),
):
    """
    DOC-K02: Retorna estado atual do rate limit com a KuCoin.

    Usado pelo dashboard para mostrar saúde do gateway em tempo real.
    """
    import time
    from app.integrations.kucoin.rest_client import _GATEWAY_STATE
    return {
        "gateway_limit": _GATEWAY_STATE.limit,
        "gateway_remaining": _GATEWAY_STATE.remaining,
        "usage_pct": round(_GATEWAY_STATE.usage_pct() * 100, 1),
        "seconds_until_reset": round(_GATEWAY_STATE.seconds_until_reset(), 1),
        "last_updated_ago_seconds": (
            round(time.monotonic() - _GATEWAY_STATE.last_updated, 1)
            if _GATEWAY_STATE.last_updated else None
        ),
        "health": "ok" if _GATEWAY_STATE.usage_pct() < 0.8 else "throttling",
    }


@router.get("/circuit-breakers", tags=["trading"])
async def get_circuit_breaker_status():
    """
    Get status of all circuit breakers for exchange resilience.

    Shows which exchanges have circuit breakers open due to repeated failures.
    """
    from app.services.network_resilience import get_all_circuit_breaker_statuses
    return get_all_circuit_breaker_statuses()
