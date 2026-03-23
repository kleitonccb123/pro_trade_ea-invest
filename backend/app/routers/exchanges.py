"""
Exchange Router - Setup and manage exchange credentials for users.

Endpoints:
- POST /api/exchanges/setup - Store encrypted API credentials
- GET /api/exchanges - List connected exchanges
- DELETE /api/exchanges/{exchange} - Remove exchange credentials
- POST /api/exchanges/verify - Verify credentials work with exchange
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import logging

from app.security import get_credential_store, LogSanitizer
from app.exchanges.kucoin.client import KuCoinRawClient, KuCoinAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ExchangeCredentialRequest(BaseModel):
    """Request to store exchange credentials."""
    exchange: str = Field(..., description="Exchange name: 'kucoin', 'binance'", pattern="^(kucoin|binance|kraken)$")
    api_key: str = Field(..., description="Exchange API key", min_length=1)
    api_secret: str = Field(..., description="Exchange API secret", min_length=1)
    passphrase: str = Field(..., description="Exchange API passphrase (for KuCoin)", min_length=1)
    
    class Config:
        schema_extra = {
            "example": {
                "exchange": "kucoin",
                "api_key": "63dcf...",
                "api_secret": "secret123...",
                "passphrase": "pass123..."
            }
        }


class ExchangeCredentialResponse(BaseModel):
    """Response after storing credentials."""
    exchange: str
    status: str
    message: str
    created_at: str


class ExchangeListResponse(BaseModel):
    """Response with list of connected exchanges."""
    exchanges: list[str]
    count: int


class CredentialVerifyRequest(BaseModel):
    """Request to verify credentials."""
    exchange: str


class CredentialVerifyResponse(BaseModel):
    """Response from credential verification."""
    exchange: str
    valid: bool
    status: str
    message: str
    account_info: dict = None


# ============================================================================
# Helper Functions
# ============================================================================

async def get_current_user_id(authorization: str = None) -> str:
    """
    Extract user ID from authorization header.
    
    TODO: Integrate with actual JWT auth
    For now, returns mock user_id from header.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    # TODO: Validate JWT token and extract user_id
    # For development: expect "Bearer <user_id>"
    try:
        scheme, credentials = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError("Invalid auth scheme")
        return credentials  # In prod, extract from JWT claims
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/setup", response_model=ExchangeCredentialResponse)
async def setup_exchange(
    request: ExchangeCredentialRequest,
    authorization: str = None
):
    """
    Store encrypted exchange credentials for user.
    
    The credentials are encrypted with Fernet before storage.
    API secret and passphrase are never stored in plaintext.
    """
    # Get current user
    try:
        user_id = await get_current_user_id(authorization)
    except HTTPException as e:
        raise e
    
    credential_store = get_credential_store()
    
    try:
        # Store encrypted credentials
        stored = await credential_store.store_credentials(
            user_id=user_id,
            exchange=request.exchange,
            api_key=request.api_key,
            api_secret=request.api_secret,
            passphrase=request.passphrase,
        )
        
        logger.info(f"✅ Credentials stored for {user_id} on {request.exchange}")
        
        return ExchangeCredentialResponse(
            exchange=request.exchange,
            status="success",
            message=f"Credentials stored for {request.exchange}",
            created_at=stored.created_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to store credentials: {LogSanitizer.sanitize(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store credentials"
        )


@router.get("/", response_model=ExchangeListResponse)
async def list_exchanges(authorization: str = None):
    """
    List all exchanges for which user has stored credentials.
    """
    try:
        user_id = await get_current_user_id(authorization)
    except HTTPException as e:
        raise e
    
    credential_store = get_credential_store()
    
    try:
        exchanges = await credential_store.list_user_exchanges(user_id)
        
        return ExchangeListResponse(
            exchanges=exchanges,
            count=len(exchanges)
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to list exchanges: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list exchanges"
        )


@router.delete("/{exchange}")
async def remove_exchange(exchange: str, authorization: str = None):
    """
    Remove exchange credentials for user.
    
    Once removed, user will need to re-authenticate with the exchange.
    """
    try:
        user_id = await get_current_user_id(authorization)
    except HTTPException as e:
        raise e
    
    credential_store = get_credential_store()
    
    try:
        deleted = await credential_store.delete_credentials(user_id, exchange)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Credentials not found for {exchange}"
            )
        
        logger.info(f"✅ Credentials removed for {user_id} on {exchange}")
        
        return {
            "status": "success",
            "message": f"Credentials for {exchange} removed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to remove credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove credentials"
        )


@router.post("/verify", response_model=CredentialVerifyResponse)
async def verify_credentials(
    request: CredentialVerifyRequest,
    authorization: str = None
):
    """
    Verify that stored credentials work with exchange.
    
    Makes a test API call to fetch account info.
    """
    try:
        user_id = await get_current_user_id(authorization)
    except HTTPException as e:
        raise e
    
    credential_store = get_credential_store()
    
    try:
        # Get stored credentials
        creds = await credential_store.get_credentials(user_id, request.exchange)
        
        if not creds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No credentials found for {request.exchange}"
            )
        
        # Test credentials based on exchange
        if request.exchange == "kucoin":
            # Create KuCoin client and fetch account info
            client = KuCoinRawClient(
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                passphrase=creds["passphrase"]
            )
            
            # Try to fetch accounts - basic validation
            accounts = await client.get_accounts()
            
            if not accounts:
                return CredentialVerifyResponse(
                    exchange=request.exchange,
                    valid=False,
                    status="error",
                    message="No accounts found - credentials may be invalid",
                    account_info=None
                )
            
            # Return first account as proof
            account_info = {
                "account_id": accounts[0].get("id"),
                "type": accounts[0].get("type"),
                "balance_count": len(accounts[0].get("balances", []))
            }
            
            logger.info(f"✅ Credentials verified for {user_id} on {request.exchange}")
            
            return CredentialVerifyResponse(
                exchange=request.exchange,
                valid=True,
                status="success",
                message="Credentials verified successfully",
                account_info=account_info
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exchange {request.exchange} verification not implemented"
            )
    
    except KuCoinAPIError as e:
        logger.error(f"❌ KuCoin API error during verification: {e}")
        return CredentialVerifyResponse(
            exchange=request.exchange,
            valid=False,
            status="error",
            message=f"API error: {str(e)[:100]}",
            account_info=None
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"❌ Failed to verify credentials: {LogSanitizer.sanitize(str(e))}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify credentials"
        )
