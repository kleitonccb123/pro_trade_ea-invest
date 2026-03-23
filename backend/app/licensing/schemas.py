from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class LicenseResponse(BaseModel):
    """
    Resposta padrão de verificação de licença — DOC-07.

    Compatível com o formato legado (features: Dict[str, bool]) e estendido
    com campos de grace period e expiração.
    """

    valid: bool
    plan: str                               # free | basic | pro | enterprise
    features: Dict[str, bool] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None
    # DOC-07 — grade period e grace expiration
    in_grace_period: bool = False
    grace_until: Optional[datetime] = None
    # DOC-07 — user context (útil para logging/audit)
    user_id: Optional[str] = None

    def is_paid(self) -> bool:
        """True se o plano tem algum recurso pago (não free/starter)."""
        return self.plan.lower() not in ("free", "starter", "unknown")

    def feature_value(self, key: str) -> Any:
        """Retorna o valor booleano de uma feature, False se ausente."""
        return self.features.get(key, False)


class LicenseDocument(BaseModel):
    """
    Documento salvo na coleção MongoDB `licenses`.

    Criado/atualizado pelo router de billing (Perfect Pay postback).
    Lido pelo LicensingService para verificações em tempo real.
    """

    user_id: str
    plan: str                               # free | basic | pro | enterprise
    subscription_id: Optional[str] = None  # perfect_pay_subscription_id
    sale_id: Optional[str] = None          # perfect_pay_sale_id (última venda)
    product_name: Optional[str] = None
    payment_method: Optional[str] = None
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # = next_charge_date
    # Grace period: ativo quando pagamento falha
    in_grace_period: bool = False
    grace_until: Optional[datetime] = None
    # Histórico
    downgraded_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None

