"""
Exceções do sistema de licenciamento — DOC-07

Regra de ouro: NUNCA capturar LicenseCheckError com um fallback de Premium.
Em caso de falha do banco, o acesso deve ser NEGADO, não concedido.
"""

from __future__ import annotations


class LicenseCheckError(Exception):
    """
    Levantada quando o serviço de licenciamento não consegue verificar
    o estado da licença de um usuário (ex: MongoDB offline, timeout).

    CRÍTICO: Jamais retornar Premium como fallback quando esta exceção
    for capturada. A resposta correta é HTTP 503 (serviço indisponível).
    """

    def __init__(self, message: str = "Serviço de licenciamento temporariamente indisponível") -> None:
        super().__init__(message)
        self.message = message


class LicenseExpiredError(Exception):
    """Levantada quando a licença do usuário está expirada e fora do grace period."""

    def __init__(self, user_id: str, plan: str) -> None:
        super().__init__(f"Licença expirada: user={user_id} plan={plan}")
        self.user_id = user_id
        self.plan = plan


class FeatureNotAvailableError(Exception):
    """Levantada quando o plano atual não inclui a feature solicitada."""

    def __init__(self, feature: str, current_plan: str) -> None:
        super().__init__(f"Feature '{feature}' não disponível no plano '{current_plan}'")
        self.feature = feature
        self.current_plan = current_plan
