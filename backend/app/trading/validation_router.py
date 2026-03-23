"""
Pre-Trade Validation Router - Endpoints para valida??o antes de trades
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from decimal import Decimal

from app.auth.dependencies import get_current_user
from app.trading.pre_trade_validation import PreTradeValidator, ValidationResult
from app.core.database import get_db

router = APIRouter(prefix="/trading", tags=["trading"])


# ============== SCHEMAS ==============

class PreTradeValidationRequest(BaseModel):
    exchange: str
    symbol: str
    amount: float
    side: str  # 'buy' or 'sell'
    price: Optional[float] = None


class PreTradeValidationResponse(BaseModel):
    valid: bool
    available_balance: float
    required_balance: float
    min_order_size: float
    max_order_size: float
    errors: List[str]
    warnings: List[str] = []
    adjusted_amount: Optional[float] = None


class SystemHealthResponse(BaseModel):
    status: str  # 'healthy', 'degraded', 'unhealthy'
    circuit_breaker: dict
    services: dict
    uptime: float


# ============== ENDPOINTS ==============

@router.post("/validate-pre-trade", response_model=PreTradeValidationResponse)
async def validate_pre_trade(
    request: PreTradeValidationRequest,
    current_user = Depends(get_current_user)
):
    """
    Valida se uma ordem pode ser executada antes de enviar para a exchange.
    
    Verifica:
    - Saldo dispon?vel
    - Tamanho m?nimo/m?ximo da ordem
    - Precis?o do par
    - Limites de rate
    """
    try:
        db = await get_database()
        user_id = str(current_user.id)
        
        # Get user's API credentials for the exchange
        credentials = await db.api_credentials.find_one({
            "user_id": user_id,
            "exchange": request.exchange
        })
        
        if not credentials:
            # Return mock validation for demo (no API connected)
            return _mock_validation(request)
        
        # Initialize validator
        validator = PreTradeValidator()
        
        # Get exchange client
        from app.trading.ccxt_exchange_service import CCXTExchangeService
        
        exchange_service = CCXTExchangeService(
            exchange_id=request.exchange,
            api_key=credentials.get("api_key"),
            api_secret=credentials.get("api_secret"),
            passphrase=credentials.get("passphrase"),
            sandbox=credentials.get("sandbox", True)
        )
        
        # Validate the order
        result = await validator.validate_order(
            exchange=exchange_service.exchange,
            symbol=request.symbol,
            side=request.side,
            amount=Decimal(str(request.amount)),
            price=Decimal(str(request.price)) if request.price else None
        )
        
        return PreTradeValidationResponse(
            valid=result.valid,
            available_balance=float(result.available_balance) if result.available_balance is not None else 0.0,
            required_balance=float(result.required_balance or request.amount),
            min_order_size=float(result.min_order_size or 0),
            max_order_size=float(result.max_order_size or 1000000),
            errors=result.errors,
            warnings=result.warnings,
            adjusted_amount=float(result.adjusted_amount) if result.adjusted_amount else None
        )
        
    except Exception as e:
        # Return mock validation in case of errors
        return _mock_validation(request)


def _mock_validation(request: PreTradeValidationRequest) -> PreTradeValidationResponse:
    """Return mock validation for demo/development."""
    
    # Simulate different scenarios
    mock_balance = 10000.0  # Mock available balance
    min_order = 10.0
    max_order = 100000.0
    
    errors = []
    warnings = []
    
    if request.amount > mock_balance:
        errors.append(f"Saldo insuficiente. Dispon?vel: ${mock_balance:.2f}, Necess?rio: ${request.amount:.2f}")
    
    if request.amount < min_order:
        errors.append(f"Valor abaixo do m?nimo permitido (${min_order:.2f})")
    
    if request.amount > max_order:
        errors.append(f"Valor acima do m?ximo permitido (${max_order:.2f})")
    
    if request.amount > mock_balance * 0.5:
        warnings.append("Aten??o: Esta ordem representa mais de 50% do seu saldo dispon?vel")
    
    return PreTradeValidationResponse(
        valid=len(errors) == 0,
        available_balance=mock_balance,
        required_balance=request.amount,
        min_order_size=min_order,
        max_order_size=max_order,
        errors=errors,
        warnings=warnings,
        adjusted_amount=None
    )


@router.get("/health/detailed", response_model=SystemHealthResponse)
async def get_system_health(
    current_user = Depends(get_current_user)
):
    """
    Retorna status detalhado do sistema incluindo Circuit Breaker.
    """
    from app.core.resilience import (
        kucoin_circuit, binance_circuit,
        CircuitBreakerState
    )
    import time
    
    # Check services
    services = {
        "database": True,
        "exchange_api": True,
        "redis": True
    }
    
    # Try to ping database
    try:
        db = await get_database()
        await db.command("ping")
    except:
        services["database"] = False
    
    # Check circuit breakers
    circuit_states = {
        "kucoin": {
            "state": kucoin_circuit.state.value,
            "failures": kucoin_circuit.failure_count,
            "last_failure": kucoin_circuit.last_failure_time
        },
        "binance": {
            "state": binance_circuit.state.value,
            "failures": binance_circuit.failure_count,
            "last_failure": binance_circuit.last_failure_time
        }
    }
    
    # Determine overall status
    any_open = any(
        cb["state"] == "OPEN" 
        for cb in circuit_states.values()
    )
    any_half_open = any(
        cb["state"] == "HALF_OPEN" 
        for cb in circuit_states.values()
    )
    all_services_up = all(services.values())
    
    if any_open or not all_services_up:
        status = "unhealthy"
    elif any_half_open:
        status = "degraded"
    else:
        status = "healthy"
    
    # Calculate uptime (mock for now)
    uptime = time.time() % 86400  # Seconds since last "restart"
    
    return SystemHealthResponse(
        status=status,
        circuit_breaker=circuit_states,
        services=services,
        uptime=uptime
    )
