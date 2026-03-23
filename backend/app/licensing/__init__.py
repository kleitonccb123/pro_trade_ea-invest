"""
Licensing package — DOC-07

Sistema de licenciamento real integrado com Perfect Pay.

Exportações principais::

    from app.licensing import get_licensing_service, LicensingService
    from app.licensing.exceptions import LicenseCheckError
    from app.licensing.features import PLAN_FEATURES, require_feature, require_plan
    from app.licensing.schemas import LicenseResponse
"""

from app.licensing.exceptions import LicenseCheckError, LicenseExpiredError, FeatureNotAvailableError
from app.licensing.schemas import LicenseResponse, LicenseDocument
from app.licensing.features import PLAN_FEATURES, features_for_plan, require_feature, require_plan
from app.licensing.service import LicensingService, get_licensing_service

__all__ = [
    # Serviço
    "LicensingService",
    "get_licensing_service",
    # Schemas
    "LicenseResponse",
    "LicenseDocument",
    # Exceções
    "LicenseCheckError",
    "LicenseExpiredError",
    "FeatureNotAvailableError",
    # Features
    "PLAN_FEATURES",
    "features_for_plan",
    "require_feature",
    "require_plan",
]
