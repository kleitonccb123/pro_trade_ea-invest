"""
Subscription Guard — Dependência FastAPI para verificar assinatura ativa.

Uso básico:
    from app.auth.subscription import verificar_assinatura_ativa, RequirePlan

    # Qualquer plano pago (não starter):
    @router.get("/rota-premium")
    async def rota(user=Depends(get_current_user), _=Depends(verificar_assinatura_ativa)):
        ...

    # Exige plano mínimo específico:
    @router.post("/bots/start")
    async def start(_=Depends(RequirePlan("pro"))):
        ...

Lógica de verificação (em camadas — a primeira falha bloqueia):
    1. Superusuário → sempre liberado
    2. plan == "starter" (free) → bloqueado (nunca pagou)
    3. perfect_pay_next_charge_date expirada → bloqueado (assinatura vencida)
    4. Aviso se faltam ≤ 3 dias → retorna campo "aviso" no header da resposta
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Response, status

from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

# Hierarquia de planos: índice maior = plano superior
_PLANO_NIVEL = {
    "starter":    0,
    "pro":        1,
    "premium":    2,
    "enterprise": 3,
}

_AVISO_EXPIRANDO_DIAS = 3  # Quantos dias antes de expirar exibir aviso


# ---------------------------------------------------------------------------
# Utilitário interno
# ---------------------------------------------------------------------------

def _parse_next_charge_date(valor: object) -> Optional[datetime]:
    """
    Converte next_charge_date (string "YYYY-MM-DD" ou datetime) para
    datetime com timezone UTC.

    Retorna None se o valor for nulo ou inválido.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    if isinstance(valor, str):
        valor = valor.strip()
        if not valor:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(valor, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    logger.warning(f"[SUBSCRIPTION] Formato de next_charge_date não reconhecido: {valor!r}")
    return None


# ---------------------------------------------------------------------------
# Dependência principal
# ---------------------------------------------------------------------------

async def verificar_assinatura_ativa(
    response: Response,
    user: dict = Depends(get_current_user),
) -> dict:
    """
    Verifica se o usuário possui assinatura ativa.

    Retorna o dict do usuário (para que a rota possa usá-lo sem um Depends extra).

    Headers de resposta adicionados:
        X-Subscription-Plan      — plano atual do usuário
        X-Subscription-Expires   — data da próxima cobrança (se disponível)
        X-Subscription-Warning   — presente quando faltam ≤ 3 dias

    Raises:
        HTTPException 403: Plano gratuito (nunca pagou).
        HTTPException 403: Assinatura expirada.
    """
    # 1. Superusuário: acesso irrestrito
    if user.get("is_superuser"):
        response.headers["X-Subscription-Plan"] = "superuser"
        return user

    plano = str(user.get("plan", "starter")).lower()
    response.headers["X-Subscription-Plan"] = plano

    # 2. Plano free (starter): nunca assinou
    if plano == "starter":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error":   "subscription_required",
                "message": "Esta funcionalidade requer um plano pago. "
                           "Acesse /billing para assinar.",
            },
        )

    # 3. Verificar validade pela next_charge_date (segunda camada de segurança)
    next_charge_raw = user.get("perfect_pay_next_charge_date")
    next_charge = _parse_next_charge_date(next_charge_raw)

    if next_charge:
        response.headers["X-Subscription-Expires"] = next_charge.strftime("%Y-%m-%d")
        agora = datetime.now(timezone.utc)

        if agora > next_charge:
            logger.warning(
                f"[SUBSCRIPTION] Assinatura expirada para user={user.get('email')} "
                f"next_charge={next_charge.date()}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error":   "subscription_expired",
                    "message": "Sua assinatura expirou. "
                               "Renove seu plano para continuar usando este recurso.",
                    "expired_at": next_charge.strftime("%Y-%m-%d"),
                },
            )

        # 4. Aviso: vence em ≤ 3 dias
        dias_restantes = (next_charge - agora).days
        if dias_restantes <= _AVISO_EXPIRANDO_DIAS:
            aviso = f"Sua assinatura vence em {dias_restantes} dia(s). Renove para não perder acesso."
            response.headers["X-Subscription-Warning"] = aviso
            logger.info(f"[SUBSCRIPTION] {aviso} user={user.get('email')}")

    return user


# ---------------------------------------------------------------------------
# Verificação de nível de plano
# ---------------------------------------------------------------------------

class RequirePlan:
    """
    Dependência parametrizada que exige um plano mínimo.

    Combina verificação de assinatura ativa + nível mínimo de plano.

    Exemplo:
        @router.post("/bots/criar")
        async def criar_bot(_=Depends(RequirePlan("pro"))):
            ...

        @router.post("/analytics/avancado")
        async def analytics(_=Depends(RequirePlan("premium"))):
            ...
    """

    def __init__(self, plano_minimo: str):
        """
        Args:
            plano_minimo: Um de "pro", "premium", "enterprise".
                          "starter" não é aceito (equivale a sem restrição de nível).
        """
        if plano_minimo not in _PLANO_NIVEL:
            raise ValueError(
                f"plano_minimo inválido: '{plano_minimo}'. "
                f"Use um de {list(_PLANO_NIVEL.keys())}"
            )
        self.nivel_minimo = _PLANO_NIVEL[plano_minimo]
        self.plano_minimo = plano_minimo

    async def __call__(
        self,
        response: Response,
        user: dict = Depends(get_current_user),
    ) -> dict:
        # Reutiliza toda a lógica de verificar_assinatura_ativa
        user = await verificar_assinatura_ativa(response=response, user=user)

        plano_atual = str(user.get("plan", "starter")).lower()
        nivel_atual = _PLANO_NIVEL.get(plano_atual, 0)

        if nivel_atual < self.nivel_minimo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error":          "plan_upgrade_required",
                    "message":        f"Esta funcionalidade requer o plano '{self.plano_minimo}' ou superior. "
                                      f"Seu plano atual é '{plano_atual}'.",
                    "current_plan":   plano_atual,
                    "required_plan":  self.plano_minimo,
                },
            )

        return user


# ---------------------------------------------------------------------------
# Instâncias prontas para uso comum
# ---------------------------------------------------------------------------

# Exige qualquer plano pago (pro, premium, enterprise):
requer_plano_pago = verificar_assinatura_ativa

# Exige plano Pro ou superior:
requer_plano_pro = RequirePlan("pro")

# Exige plano Premium ou superior:
requer_plano_premium = RequirePlan("premium")

# Exige plano Enterprise:
requer_plano_enterprise = RequirePlan("enterprise")
