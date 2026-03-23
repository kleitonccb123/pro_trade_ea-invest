"""
Auth Router - Login, Logout, Token Management
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import timedelta
import logging

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class LogoutRequest(BaseModel):
    pass


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db=None):
    """
    Login com email e password.
    Retorna JWT token.
    """
    try:
        # Busca usuário
        user = await db.users.find_one({"email": request.email})
        
        if not user:
            logger.warning(f"❌ Login failed: user {request.email} not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Valida password
        if not pwd_context.verify(request.password, user["password_hash"]):
            logger.warning(f"❌ Login failed: wrong password for {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        if not user.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive"
            )
        
        # Cria token
        from app.middleware.auth import TokenManager
        
        token_data = {
            "user_id": str(user["_id"]),
            "email": user["email"],
            "username": user["username"]
        }
        
        token = TokenManager.create_access_token(
            data=token_data,
            expires_delta=timedelta(hours=24)
        )
        
        logger.info(f"✅ User {request.email} logged in successfully")
        
        return LoginResponse(
            access_token=token,
            user_id=str(user["_id"]),
            email=user["email"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/logout")
async def logout(current_user = Depends(lambda: None), db=None):
    """
    Logout - adiciona token ao blacklist.
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        # Adiciona token ao blacklist
        from app.middleware.auth import get_token_blacklist
        
        blacklist = get_token_blacklist()
        await blacklist.add_to_blacklist(current_user.get("raw_token"))
        
        logger.info(f"✅ User {current_user['email']} logged out")
        
        return {"message": "Logged out successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me")
async def get_current_user_info(current_user = Depends(lambda: None), db=None):
    """
    Retorna informações do usuário autenticado.
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        from bson import ObjectId
        
        user = await db.users.find_one({"_id": ObjectId(current_user["user_id"])})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "user_id": str(user["_id"]),
            "email": user["email"],
            "username": user["username"],
            "is_active": user["is_active"],
            "created_at": user["created_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get user info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user info"
        )
