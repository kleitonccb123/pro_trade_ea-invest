"""
Exemplo de Endpoint FastAPI — Usando TradingExecutor

Este arquivo demonstra como integrar o TradingExecutor em um endpoint real.

Adicione este router em seu main.py:
    from app.trading.executor_example import router as executor_router
    app.include_router(executor_router)

Endpoints:
    POST /api/trading/execute/market-order
    GET /api/trading/orders/{order_id}
    GET /api/trading/orders
    GET /api/trading/balance
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime

from app.auth.dependencies import get_current_user
from app.trading.executor import (
    TradingExecutor,
    OrderExecutionError,
    ValidationFailedError,
    InsufficientBalanceError
)
from app.core.database import get_db

router = APIRouter(prefix="/api/trading", tags=["trading-executor"])


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMAS (Pydantic Models)
# ═══════════════════════════════════════════════════════════════════════════

class ExecuteMarketOrderRequest(BaseModel):
    """Request para executar ordem de mercado"""
    symbol: str = Field(..., example="BTC-USDT", description="Par de trading")
    side: str = Field(..., example="buy", description="Direção (buy/sell)")
    quantity: Decimal = Field(..., example=Decimal("0.1"), description="Quantidade")
    take_profit: Optional[Decimal] = Field(None, example=Decimal("45000"), description="Preço TP")
    stop_loss: Optional[Decimal] = Field(None, example=Decimal("40000"), description="Preço SL")


class OrderResponse(BaseModel):
    """Response com dados da ordem"""
    id: str = Field(..., alias="_id")
    user_id: str
    symbol: str
    side: str
    quantity: Decimal
    status: str  # "pending" | "filled" | "failed"
    client_oid: str
    exchange_order_id: Optional[str] = None
    created_at: datetime
    filled_at: Optional[datetime] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: Optional[Decimal] = None
    testnet: bool
    
    class Config:
        populate_by_name = True


class BalanceResponse(BaseModel):
    """Response com saldo da conta"""
    balances: Dict[str, Decimal]
    total_usd: Optional[Decimal] = None
    last_updated: datetime


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/execute/market-order", response_model=OrderResponse)
async def execute_market_order(
    request: ExecuteMarketOrderRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Executa uma ordem de MERCADO em tempo real.
    
    Pipeline:
    1. ✓ Validação pré-trade
    2. ✓ Persistência no MongoDB
    3. ✓ Execução na KuCoin
    4. ✓ Monitoramento até fill
    5. ✓ Sincronização de resultado
    
    Exemplo curl:
    ```bash
    curl -X POST http://localhost:8000/api/trading/execute/market-order \\
      -H "Authorization: Bearer <token>" \\
      -H "Content-Type: application/json" \\
      -d '{
        "symbol": "BTC-USDT",
        "side": "buy",
        "quantity": 0.1
      }'
    ```
    
    Response (200):
    ```json
    {
      "id": "507f1f77bcf86cd799439011",
      "user_id": "user_123",
      "symbol": "BTC-USDT",
      "side": "buy",
      "quantity": 0.1,
      "status": "filled",
      "filled_price": 42000.50,
      "filled_at": "2026-03-23T10:30:45Z",
      ...
    }
    ```
    """
    
    user_id = str(current_user.get("_id"))
    
    try:
        # ─────────────────────────────────────────────────────────────
        # 1. Criar executor
        # ─────────────────────────────────────────────────────────────
        executor = TradingExecutor(
            user_id=user_id,
            exchange="kucoin",
            testnet=True,  # TODO: decidir baseado no user's config
            max_monitoring_time=60
        )
        
        # ─────────────────────────────────────────────────────────────
        # 2. Inicializar (conectar com credenciais do usuário)
        # ─────────────────────────────────────────────────────────────
        await executor.initialize()
        
        # ─────────────────────────────────────────────────────────────
        # 3. Executar ordem (pipeline completo)
        # ─────────────────────────────────────────────────────────────
        order_result = await executor.execute_market_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            take_profit=request.take_profit,
            stop_loss=request.stop_loss
        )
        
        # ─────────────────────────────────────────────────────────────
        # 4. Cleanup
        # ─────────────────────────────────────────────────────────────
        await executor.close()
        
        # ─────────────────────────────────────────────────────────────
        # 5. Notificar usuário (background)
        # ─────────────────────────────────────────────────────────────
        background_tasks.add_task(
            notify_user_order_filled,
            user_id=user_id,
            order=order_result
        )
        
        return OrderResponse(**order_result)
        
    except ValidationFailedError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Validação falhou: {str(e)}"
        )
    except InsufficientBalanceError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Saldo insuficiente: {str(e)}"
        )
    except OrderExecutionError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao executar ordem: {str(e)}"
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"Sem permissão: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Obtém detalhes de uma ordem específica.
    
    Exemplo:
    ```bash
    curl -X GET http://localhost:8000/api/trading/orders/507f1f77bcf86cd799439011 \\
      -H "Authorization: Bearer <token>"
    ```
    """
    
    from bson import ObjectId
    
    user_id = str(current_user.get("_id"))
    db = get_db()
    
    try:
        order = await db.trading_orders.find_one({
            "_id": ObjectId(order_id),
            "user_id": user_id  # Segurança: apenas seu próprio usuário
        })
        
        if not order:
            raise HTTPException(status_code=404, detail="Ordem não encontrada")
        
        return OrderResponse(**order)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    limit: int = 50,
    skip: int = 0,
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Lista todas as ordens do usuário.
    
    Query params:
        - limit: Quantas ordens retornar (default 50)
        - skip: Pular primeiras N ordens (for pagination)
        - status: Filtrar por status ("pending", "filled", "failed")
    
    Exemplo:
    ```bash
    curl -X GET \
      "http://localhost:8000/api/trading/orders?limit=10&status=filled" \\
      -H "Authorization: Bearer <token>"
    ```
    """
    
    user_id = str(current_user.get("_id"))
    db = get_db()
    
    # Build filter
    filter_doc = {"user_id": user_id}
    if status:
        filter_doc["status"] = status
    
    # Query
    cursor = db.trading_orders.find(filter_doc).sort("created_at", -1).skip(skip).limit(limit)
    orders = await cursor.to_list(length=limit)
    
    return [OrderResponse(**order) for order in orders]


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Obtém saldo da conta no exchange (em tempo real).
    
    Chama TradingExecutor.get_account_balance()
    
    Exemplo:
    ```bash
    curl -X GET http://localhost:8000/api/trading/balance \\
      -H "Authorization: Bearer <token>"
    ```
    
    Response:
    ```json
    {
      "balances": {
        "BTC": 0.5,
        "USDT": 1000.00,
        "ETH": 2.5
      },
      "total_usd": 35000.00,
      "last_updated": "2026-03-23T10:30:45Z"
    }
    ```
    """
    
    user_id = str(current_user.get("_id"))
    
    try:
        # Criar executor
        executor = TradingExecutor(user_id=user_id, exchange="kucoin", testnet=True)
        await executor.initialize()
        
        # Obter saldo
        balance_dict = await executor.get_account_balance()
        
        # Cleanup
        await executor.close()
        
        # TODO: Calcular total em USD (chamar price API)
        
        return BalanceResponse(
            balances=balance_dict,
            last_updated=datetime.utcnow()
        )
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════

async def notify_user_order_filled(user_id: str, order: Dict[str, Any]):
    """
    Notifica usuário que sua ordem foi preenchida.
    
    Pode enviar:
    - Email
    - SMS
    - Notificação push
    - WebSocket
    """
    
    from app.services.notifications import send_email, send_notification
    
    # TODO: Implementar notificação real
    print(f"📩 Notificando user {user_id} sobre ordem {order['_id']}")
    
    message = f"""
    Sua ordem foi preenchida!
    
    Par: {order['symbol']}
    Lado: {order['side']}
    Quantidade: {order['filled_quantity']}
    Preço: {order['filled_price']}
    PnL: {order.get('pnl', 'N/A')}
    """
    
    # await send_email(user_id, "Ordem Preenchida", message)
    # await send_notification(user_id, message)


# ═══════════════════════════════════════════════════════════════════════════
# EXEMPLO DE USO (DEV ONLY)
# ═══════════════════════════════════════════════════════════════════════════

"""
Exemplo de como usar este endpoint em um cliente:

```python
import httpx
from decimal import Decimal

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Login
        response = await client.post(
            "http://localhost:8000/api/auth/login",
            json={"email": "test@example.com", "password": "password123"}
        )
        token = response.json()["access_token"]
        
        # 2. Executar ordem
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.post(
            "http://localhost:8000/api/trading/execute/market-order",
            headers=headers,
            json={
                "symbol": "BTC-USDT",
                "side": "buy",
                "quantity": 0.1
            }
        )
        
        order = response.json()
        print(f"✅ Ordem criada: {order['id']}")
        print(f"   Status: {order['status']}")
        print(f"   Preço: {order.get('filled_price')}")
        
        # 3. Obter saldo
        response = await client.get(
            "http://localhost:8000/api/trading/balance",
            headers=headers
        )
        
        balance = response.json()
        print(f"💰 Saldo: {balance['balances']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
"""
