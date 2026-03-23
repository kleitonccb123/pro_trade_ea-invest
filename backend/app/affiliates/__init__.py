"""
Affiliate Module - Sistema de Indica??o/Afiliados
"""

from app.affiliates.service import AffiliateService, affiliate_service
from app.affiliates.router import router as affiliates_router

__all__ = ["AffiliateService", "affiliate_service", "affiliates_router"]
