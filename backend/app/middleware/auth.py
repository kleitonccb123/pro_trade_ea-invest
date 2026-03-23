"""
Authentication Middleware - JWT + Permission Validation
Valida autenticação e autorização em endpoints
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not SECRET_KEY:
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY not set — authentication will fail in production.",
        stacklevel=2,
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()


class TokenBlacklist:
    """Gerencia tokens inválidos (logout)."""
    
    def __init__(self):
        self.blacklist: set = set()
    
    async def add_to_blacklist(self, token: str):
        """Adiciona token ao blacklist (loggedout)."""
        self.blacklist.add(token)
        logger.info(f"✅ Token added to blacklist")
    
    def is_blacklisted(self, token: str) -> bool:
        """Verifica se token está no blacklist."""
        return token in self.blacklist


# Singleton instance
_token_blacklist: Optional[TokenBlacklist] = None


def get_token_blacklist() -> TokenBlacklist:
    """Retorna token blacklist global."""
    global _token_blacklist
    if _token_blacklist is None:
        _token_blacklist = TokenBlacklist()
    return _token_blacklist


class TokenManager:
    """Gerencia criação e validação de JWT tokens."""
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Cria JWT token.
        
        Args:
            data: Dict com user_id, email, etc
            expires_delta: Tempo de expiração customizado
            
        Returns:
            Token JWT
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        
        try:
            encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
            logger.info(f"✅ Token created for user {data.get('user_id')}")
            return encoded_jwt
        except Exception as e:
            logger.error(f"❌ Failed to create token: {e}")
            raise
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Valida JWT token.
        
        Args:
            token: Token JWT
            
        Returns:
            Dict com payload do token
            
        Raises:
            HTTPException se token inválido/expirado
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("❌ Token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError:
            logger.warning("❌ Invalid token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"❌ Token validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate token"
            )


async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security),
    db=None
) -> Dict[str, Any]:
    """
    Valida token e retorna usuário atual.
    Uso: @app.get("/me", dependencies=[Depends(get_current_user)])
    
    Args:
        credentials: Bearer token
        db: MongoDB database
        
    Returns:
        Dict com user info
        
    Raises:
        HTTPException se não autenticado
    """
    token = credentials.credentials
    
    # Verifica blacklist (logout)
    blacklist = get_token_blacklist()
    if blacklist.is_blacklisted(token):
        logger.warning("❌ Token is blacklisted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )
    
    # Valida token
    payload = TokenManager.verify_token(token)
    user_id = payload.get("user_id")
    email = payload.get("email")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return {
        "user_id": user_id,
        "email": email,
        "raw_token": token
    }


async def check_user_permission(
    bot_id: str,
    current_user: Dict = Depends(get_current_user),
    db=None
) -> bool:
    """
    Valida se usuário é dono do bot.
    Uso: @app.post("/bots/{bot_id}/start", dependencies=[Depends(check_user_permission)])
    
    Args:
        bot_id: ID do bot
        current_user: Usuário autenticado
        db: MongoDB database
        
    Returns:
        True se autorizado
        
    Raises:
        HTTPException se não autorizado
    """
    try:
        from bson import ObjectId
        
        if not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database not available"
            )
        
        # Busca bot
        bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        # Valida ownership
        if bot.get("user_id") != current_user["user_id"]:
            logger.warning(
                f"❌ User {current_user['user_id']} tried to access bot {bot_id} "
                f"belonging to {bot.get('user_id')}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource"
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Permission check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Permission check failed"
        )


async def check_order_permission(
    order_id: str,
    current_user: Dict = Depends(get_current_user),
    db=None
) -> bool:
    """
    Valida se usuário é dono da ordem.
    
    Args:
        order_id: ID da ordem
        current_user: Usuário autenticado
        db: MongoDB database
        
    Returns:
        True se autorizado
    """
    try:
        from bson import ObjectId
        
        if not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database not available"
            )
        
        order = await db.orders.find_one({"_id": ObjectId(order_id)})
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        if order.get("user_id") != current_user["user_id"]:
            logger.warning(
                f"❌ User {current_user['user_id']} tried to access order {order_id} "
                f"belonging to {order.get('user_id')}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this order"
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Order permission check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Permission check failed"
        )
