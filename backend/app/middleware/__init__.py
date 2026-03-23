"""
Middleware package for Crypto Trade Hub API

Includes:
- GoogleOAuthCSPMiddleware: Content-Security-Policy for Google OAuth 3.0
"""

from .csp import GoogleOAuthCSPMiddleware

__all__ = ["GoogleOAuthCSPMiddleware"]
