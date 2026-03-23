"""
CSRF Protection Middleware — double-submit cookie pattern.

Only state-changing endpoints that rely on the HttpOnly refresh-token cookie
need CSRF protection (refresh, logout).  All other endpoints use the
Authorization: Bearer header which is CSRF-safe by nature.

Protection method:
  1. At login / Google-auth, server sets a non-HttpOnly cookie named `csrf_token`
     containing a random hex value.
  2. JS reads the cookie and sends it as the `X-CSRF-Token` request header.
  3. This middleware verifies that the header value matches the cookie value
     for protected cookie-reliant endpoints.
"""
import secrets
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Endpoints that accept the HttpOnly refresh-cookie and must therefore be CSRF-protected
_CSRF_PROTECTED_PATHS = {
    "/api/auth/refresh",
    "/api/auth/logout",
}

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


class CSRFMiddleware(BaseHTTPMiddleware):
    """Enforce CSRF token validation for cookie-reliant state-changing endpoints."""

    async def dispatch(self, request: Request, call_next):
        if (
            request.method in ("POST", "PUT", "DELETE", "PATCH")
            and request.url.path in _CSRF_PROTECTED_PATHS
        ):
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            csrf_header = request.headers.get(CSRF_HEADER_NAME)

            if not csrf_cookie or not csrf_header:
                logger.warning(
                    "[CSRF] Missing token for %s (cookie=%s, header=%s)",
                    request.url.path,
                    bool(csrf_cookie),
                    bool(csrf_header),
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token ausente"},
                )

            if not secrets.compare_digest(csrf_cookie, csrf_header):
                logger.warning("[CSRF] Token mismatch for %s", request.url.path)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token inválido"},
                )

        return await call_next(request)


def set_csrf_cookie(response: JSONResponse, is_prod: bool = False) -> None:
    """Attach a new CSRF token as a readable (non-HttpOnly) cookie.

    Call this from login / Google-auth endpoints after issuing the refresh cookie.
    The JS side must read this cookie and include its value as X-CSRF-Token on
    requests to /api/auth/refresh and /api/auth/logout.
    """
    token = secrets.token_hex(32)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # Must be readable by JS
        secure=is_prod,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/",
    )
