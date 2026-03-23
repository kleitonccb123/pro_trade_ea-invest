"""
Middleware - Request/response processing and validation.

Includes:
- Authorization validation
- Request/response logging with sanitization
- Error handling
- CORS support
"""

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import logging
import time

from app.security import LogSanitizer

logger = logging.getLogger(__name__)


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Validate authorization header on protected routes.
    
    Allows:
    - /api/exchanges/verify without auth
    - /health without auth
    - All other routes require Authorization header
    """
    
    # Routes that don't require authentication
    UNPROTECTED_ROUTES = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/auth/login",  # TODO: implement
        "/api/auth/signup",  # TODO: implement
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request and validate authorization."""
        
        # Skip auth check for unprotected routes
        if any(request.url.path.startswith(route) for route in self.UNPROTECTED_ROUTES):
            return await call_next(request)
        
        # Require Authorization header for protected routes
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning(f"Missing auth header: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Authorization header required",
                    "code": "MISSING_AUTH"
                }
            )
        
        # Validate Bearer token format
        if not auth_header.startswith("Bearer "):
            logger.warning(f"Invalid auth format: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid authorization format",
                    "code": "INVALID_AUTH_FORMAT"
                }
            )
        
        # Validate JWT token structure
        token = auth_header.replace("Bearer ", "").strip()
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Empty token",
                    "code": "EMPTY_TOKEN",
                },
            )

        try:
            import jwt as pyjwt
            import os

            secret = os.getenv("JWT_SECRET_KEY", "")
            if not secret and os.getenv("APP_MODE", "dev") == "prod":
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Server misconfiguration: JWT_SECRET_KEY not set"},
                )
            if secret:
                pyjwt.decode(token, secret, algorithms=["HS256"])
            else:
                # Dev only: verify token is decodable without signature
                pyjwt.decode(token, options={"verify_signature": False})
        except pyjwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token expired", "code": "TOKEN_EXPIRED"},
            )
        except pyjwt.InvalidTokenError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token", "code": "INVALID_TOKEN"},
            )
        
        # Inject auth header for router endpoints to use
        request.state.authorization = auth_header
        
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests/responses with sanitization.
    
    Removes API keys, secrets, tokens from logs.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Log request and response."""
        
        start_time = time.time()
        
        # Get request body for logging (if applicable)
        body = ""
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                # Re-attach body so endpoint can read it
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except:
                pass
        
        # Log request
        sanitized_body = LogSanitizer.sanitize(body.decode() if body else "")
        logger.debug(
            f"→ {request.method} {request.url.path} "
            f"(client: {request.client.host if request.client else 'unknown'}) "
            f"body: {sanitized_body[:100]}"
        )
        
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"❌ Request failed: {LogSanitizer.sanitize(str(e))}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )
        
        # Log response
        elapsed = time.time() - start_time
        logger.debug(
            f"← {response.status_code} {request.method} {request.url.path} "
            f"({elapsed:.2f}s)"
        )
        
        # Add processing time header
        response.headers["X-Process-Time"] = str(elapsed)
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Centralized error handling and formatting.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Handle errors from endpoints."""
        
        try:
            response = await call_next(request)
            return response
        
        except HTTPException as e:
            # Re-raise HTTP exceptions - FastAPI handles these
            raise
        
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": str(e),
                    "code": "VALIDATION_ERROR"
                }
            )
        
        except Exception as e:
            logger.error(f"Unhandled error: {LogSanitizer.sanitize(str(e))}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "code": "INTERNAL_ERROR"
                }
            )


def setup_middleware(app):
    """
    Setup all middleware for FastAPI app.
    
    Order matters - middleware are applied in reverse order of addition.
    
    Args:
        app: FastAPI application instance
    """
    
    # CORS - must be added first
    # Reads CORS_ORIGINS first, falls back to ALLOWED_ORIGINS for compat
    import os
    origins_str = os.getenv("CORS_ORIGINS") or os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:8081,http://localhost:5173"
    )
    allowed_origins = [o.strip() for o in origins_str.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Error handling
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Request logging
    app.add_middleware(RequestLoggingMiddleware)
    
    # Authorization validation
    app.add_middleware(AuthorizationMiddleware)
    
    logger.info("✅ Middleware configured")
