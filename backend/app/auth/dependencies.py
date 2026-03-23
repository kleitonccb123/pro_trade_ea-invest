"""
Authentication dependencies for FastAPI.
Centralized to avoid circular imports.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from typing import Optional
import logging

from app.auth import service as auth_service

logger = logging.getLogger(__name__)


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency to extract and validate JWT token from Authorization header.
    
    Args:
        authorization: Authorization header value (should be "Bearer <token>")
        
    Returns:
        dict: User document from database
        
    Raises:
        HTTPException 401: If token is missing or invalid
        HTTPException 404: If user not found in database
    """
    # Check if Authorization header exists and has correct format
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Missing or invalid token format in Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token format",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract token from "Bearer <token>"
    token = authorization.replace("Bearer ", "").strip()

    # Reject blacklisted tokens (logged-out / revoked)
    if await auth_service.is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revogado",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # Decode token using auth service
        payload = auth_service.decode_token(token)
    except Exception as e:
        logger.error(f"Token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract user_id from token payload
    user_id = payload.get("sub")
    if not user_id:
        logger.error("Token payload does not contain 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload invalid",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Query database for user (uses local SQLite, same as login)
    try:
        from app.core.local_db_manager import get_local_db
        local_db = get_local_db()
        user = await local_db.find_user_by_id(user_id)
        
        if not user:
            logger.warning(f"User not found for id: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.debug(f"User authenticated: {user.get('email')}")
        # Garante que o dict sempre tenha "id" com o valor do JWT sub (user_id)
        # pois find_user_by_id pode retornar dicts com "_id" ou "id" nulo
        user["id"] = user_id
        return user
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


async def get_current_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    FastAPI dependency that ensures the current user has admin privileges.

    Checks the ``is_admin`` / ``is_superuser`` / ``role`` fields on the
    user document.  Raises 403 if the user is not an admin.
    """
    is_admin = (
        current_user.get("is_admin")
        or current_user.get("is_superuser")
        or current_user.get("role") == "admin"
    )
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
