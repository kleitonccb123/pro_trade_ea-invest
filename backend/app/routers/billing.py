"""
Billing Router -- Perfect Pay Postback (Webhook) Handler

CONFIGURACAO NO PAINEL PERFECT PAY
  1. Ferramentas -> Webhook - Vendas -> Adicionar
  2. URL: https://<ngrok-ou-dominio>/api/billing/postback
  3. Selecione produtos e eventos: approved, refunded, chargeback, billet_printed, canceled
  4. Formato: JSON
  5. Token pessoal (Ferramentas -> API) = PERFECT_PAY_POSTBACK_SECRET (e PERFECT_PAY_API_KEY)

VALIDACAO DO POSTBACK
  A Perfect Pay envia o campo `token` = token pessoal do produtor.
  Comparamos com PERFECT_PAY_POSTBACK_SECRET via hmac.compare_digest (anti timing-attack).

CAMPO `status` -- strings usadas pela Perfect Pay
  "approved"       -> Pagamento confirmado (cartao/pix/boleto)
  "billet_printed" -> Boleto gerado, aguardando pagamento
  "pending"        -> Aguardando confirmacao
  "canceled"       -> Cancelado pelo cliente/produtor
  "refunded"       -> Reembolso solicitado
  "chargeback"     -> Chargeback (contestacao no cartao)
  "in_process"     -> Em analise/mediacao
  "authorized"     -> Pre-autorizado (nao liquidado ainda)
  "complete"       -> Ciclo completo (assinatura encerrada normalmente)

CAMPO `sale_status_enum` -- inteiros (fallback quando `status` nao vier)
  1=Aguardando | 2=Em Processo | 3=Aprovado  | 4=Em Mediacao
  5=Rejeitado  | 6=Cancelado   | 7=Devolvido | 8=Autorizado
  9=Enviado de Volta | 10=Completo | 11=Erro Checkout | 12=Pre Checkout

PAYLOAD TIPICO (JSON):
{
  "status":           "approved",           <- campo principal (string)
  "sale_id":          "PP-123456789",
  "sale_status":      "Aprovado",           <- legivel, nao usar para logica
  "sale_status_enum": 3,                    <- fallback numerico
  "sale_amount":      "97.00",
  "payment_method":   "credit_card",        <- credit_card | pix | boleto
  "installments":     1,
  "product_token":    "PROD-TOKEN-AQUI",
  "product_name":     "Plano Premium Mensal",
  "customer_name":    "Joao Silva",
  "customer_email":   "joao@email.com",
  "customer_document":"123.456.789-00",
  "customer_phone":   "11999999999",
  "subscription_id":  "SUB-987654",         <- OBRIGATORIO salvar em assinaturas
  "next_charge_date": "2026-03-24",
  "token":            "<TOKEN_DO_PRODUTOR>"
}

TESTE LOCAL COM NGROK
  1. Instale: https://ngrok.com/download  (ou: choco install ngrok)
  2. Inicie o backend: uvicorn app.main:app --port 8000
  3. Em outro terminal: ngrok http 8000
  4. Copie a URL https://<id>.ngrok-free.app/api/billing/postback
  5. Cole no painel Perfect Pay -> Webhook - Vendas
  6. Teste com: GET https://<id>.ngrok-free.app/api/billing/postback/ping
"""

import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from app.core.config import settings
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["Billing"])


# ---------------------------------------------------------------------------
# Status strings enviados pela Perfect Pay no campo `status`
# ---------------------------------------------------------------------------

# Liberam acesso ao plano pago
_STATUS_LIBERAR: Set[str] = {"approved", "authorized", "complete"}

# Revogam acesso IMEDIATAMENTE (fraude / estorno)
_STATUS_REVOGAR: Set[str] = {"refunded", "chargeback"}

# Iniciam grace period de 3 dias (cancelamento/rejeição — não fraude)
_STATUS_GRACE: Set[str] = {"canceled", "rejected"}

# Informativos -- nao alteram plano
_STATUS_AGUARDAR: Set[str] = {"billet_printed", "pending", "in_process"}

# Grace period padrão em dias
_GRACE_PERIOD_DAYS = 3

# Mapeamento sale_status_enum -> status string (fallback)
_ENUM_TO_STATUS: Dict[int, str] = {
    1:  "pending",
    2:  "in_process",
    3:  "approved",
    4:  "in_process",
    5:  "canceled",
    6:  "canceled",
    7:  "refunded",
    8:  "authorized",
    9:  "canceled",
    10: "complete",
    11: "canceled",
    12: "pending",
}


# ---------------------------------------------------------------------------
# Schema do Postback
# ---------------------------------------------------------------------------

class PerfectPayPostback(BaseModel):
    """
    Payload JSON enviado pela Perfect Pay no Postback.

    O campo `status` (string) e o primario para logica de negocios.
    O `sale_status_enum` (inteiro) e usado como fallback se `status` nao vier.
    """
    # Campo principal de status (string)
    status:            Optional[str]   = Field(None, description="Status em ingles: approved, refunded...")

    # Identificadores da venda
    sale_id:           str
    sale_status:       Optional[str]   = None  # ex: "Aprovado" (legivel, PT-BR)
    sale_status_enum:  Optional[int]   = None  # ex: 3

    # Valores
    sale_amount:       Optional[str]   = None
    sale_amount_float: Optional[float] = None
    payment_method:    Optional[str]   = None  # credit_card | pix | boleto
    installments:      Optional[int]   = None

    # Produto
    product_token:     Optional[str]   = None
    product_name:      Optional[str]   = None

    # Cliente
    customer_name:     Optional[str]   = None
    customer_email:    Optional[str]   = None
    customer_document: Optional[str]   = None
    customer_phone:    Optional[str]   = None

    # Assinatura recorrente -- SALVAR NO BANCO
    subscription_id:   Optional[str]   = None
    next_charge_date:  Optional[str]   = None

    # Token do produtor (validacao de autenticidade)
    token:             str = Field(..., description="Token do produtor")

    class Config:
        extra = "allow"  # aceitar campos que a Perfect Pay possa adicionar no futuro

    def resolved_status(self) -> str:
        """
        Retorna o status canonico para decisao de negocio.

        Prioridade:
          1. Campo `status` (string inglesa) -- mais confiavel
          2. `sale_status_enum` mapeado -- fallback numerico
          3. "unknown" -- caso nenhum dos dois esteja presente
        """
        if self.status:
            return self.status.lower().strip()
        if self.sale_status_enum is not None:
            return _ENUM_TO_STATUS.get(self.sale_status_enum, "unknown")
        return "unknown"


# ---------------------------------------------------------------------------
# Validacao de autenticidade
# ---------------------------------------------------------------------------

def _validate_postback_token(received_token: str, expected_secret: str) -> None:
    """
    Valida o campo `token` do Postback contra PERFECT_PAY_POSTBACK_SECRET.

    Usa hmac.compare_digest para evitar timing attacks.

    Raises:
        HTTPException 401: Token invalido.
    """
    is_valid = hmac.compare_digest(received_token.strip(), expected_secret.strip())
    if not is_valid:
        logger.warning(
            "Postback Perfect Pay recebido com token INVALIDO. "
            "Verifique se PERFECT_PAY_POSTBACK_SECRET bate com o token pessoal do painel."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de postback invalido.",
        )


# ---------------------------------------------------------------------------
# Utilitario: normalizar data de cobranca para datetime UTC nativo do Mongo
# ---------------------------------------------------------------------------

def _normalizar_data_cobranca(data_str: Optional[str]) -> Optional[datetime]:
    """
    Converte a string "YYYY-MM-DD" enviada pela Perfect Pay para um objeto
    datetime UTC (meia-noite) pronto para ser salvo como Date nativo no MongoDB.

    Salvar como datetime (nao como string) permite:
      - Queries de range nativas: db.users.find({perfect_pay_next_charge_date: {$lt: new Date()}})
      - Scripts de expiracao: encontrar todos os users que expiram amanhã em O(1)
      - Indices TTL do MongoDB (se quiser expirar documentos automaticamente)

    Retorna None se a string for nula ou invalida.
    """
    if not data_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(data_str.strip(), fmt)
            # Meia-noite UTC -- consistente independente do fuso do servidor
            return dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.warning(f"[BILLING] Formato de next_charge_date nao reconhecido: {data_str!r} -- salvo como None")
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Mapeamento de nome de produto → plano (ajuste conforme seus produtos no Perfect Pay)
_PRODUCT_PLAN_MAP: Dict[str, str] = {
    "basic":      "basic",
    "basico":     "basic",
    "pro":        "pro",
    "premium":    "pro",    # legado
    "enterprise": "enterprise",
    "empresarial": "enterprise",
}


def _resolve_plan_from_payload(payload: "PerfectPayPostback") -> str:
    """
    Determina o plano a partir do product_name ou product_token do postback.

    Ordem de prioridade:
      1. product_token exato no _PRODUCT_PLAN_MAP
      2. product_name (lowercase, busca por substring)
      3. Fallback: 'pro' (plano padrão pago)
    """
    token = (payload.product_token or "").lower().strip()
    if token in _PRODUCT_PLAN_MAP:
        return _PRODUCT_PLAN_MAP[token]

    name = (payload.product_name or "").lower()
    for keyword, plan in _PRODUCT_PLAN_MAP.items():
        if keyword in name:
            return plan

    # Fallback: se nenhum mapeamento encontrado, assume "pro"
    logger.warning(
        "[BILLING] Plano não identificado para product_token=%r product_name=%r — usando 'pro'",
        payload.product_token, payload.product_name,
    )
    return "pro"


# ---------------------------------------------------------------------------
# Acoes de negocio
# ---------------------------------------------------------------------------

async def _liberar_acesso(payload: PerfectPayPostback) -> None:
    """
    Ativa o plano pago do usuario.

    Acionado por: approved, authorized, complete.

    O que salvar no banco:
      - plan = "premium"
      - perfect_pay_sale_id       (para auditoria)
      - perfect_pay_subscription_id (CRITICO para recorrencia)
      - next_charge_date          (para exibir no perfil)
    """
    logger.info(
        f"[BILLING] LIBERANDO ACESSO | venda={payload.sale_id} "
        f"status={payload.resolved_status()} email={payload.customer_email} "
        f"subscription_id={payload.subscription_id}"
    )

    from app.core.database import get_db
    db = get_db()

    if not payload.customer_email:
        logger.error(f"[BILLING] customer_email ausente na venda {payload.sale_id} -- nao e possivel identificar o usuario.")
        return

    user = await db.users.find_one({"email": payload.customer_email})
    if not user:
        logger.warning(f"[BILLING] Usuario nao encontrado para email={payload.customer_email}. Crie o usuario ou sincronize via webhook de cadastro.")
        return

    user_id = str(user["_id"])
    plan    = _resolve_plan_from_payload(payload)
    next_charge_dt = _normalizar_data_cobranca(payload.next_charge_date)

    # 1. Atualiza coleção users (backward compat com subscription guard existente)
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "plan":                          plan,
            "perfect_pay_sale_id":           payload.sale_id,
            "perfect_pay_subscription_id":   payload.subscription_id,
            "perfect_pay_next_charge_date":  next_charge_dt,
            "perfect_pay_product":           payload.product_name,
        }}
    )

    # 2. DOC-07: Atualiza coleção licenses (fonte de verdade do LicensingService)
    from app.licensing.service import get_licensing_service
    svc = get_licensing_service()
    if svc is not None:
        await svc.activate_license(
            user_id=user_id,
            plan=plan,
            subscription_id=payload.subscription_id,
            sale_id=payload.sale_id,
            product_name=payload.product_name,
            payment_method=payload.payment_method,
            expires_at=next_charge_dt,
        )
    else:
        # Fallback: grava direto se o serviço ainda não foi inicializado
        now = datetime.now(timezone.utc)
        await db.licenses.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id":         user_id,
                "plan":            plan,
                "subscription_id": payload.subscription_id,
                "sale_id":         payload.sale_id,
                "product_name":    payload.product_name,
                "payment_method":  payload.payment_method,
                "expires_at":      next_charge_dt,
                "activated_at":    now,
                "in_grace_period": False,
                "grace_until":     None,
                "updated_at":      now,
            }},
            upsert=True,
        )

    # 3. Gerar fatura (invoice) automaticamente
    try:
        from app.billing.service import generate_invoice_from_event
        await generate_invoice_from_event(
            db,
            user_id=user_id,
            sale_id=payload.sale_id,
            payload={
                "sale_amount":      payload.sale_amount,
                "payment_method":   payload.payment_method,
                "product_name":     payload.product_name,
                "subscription_id":  payload.subscription_id,
                "customer_email":   payload.customer_email,
            },
        )
    except Exception as inv_exc:
        logger.warning("[BILLING] Falha ao gerar invoice: %s", inv_exc)

    logger.info(
        f"[BILLING] Plano {plan!r} ativado para user_id={user_id} "
        f"next_charge={next_charge_dt.date() if next_charge_dt else 'N/A'}"
    )


async def _revogar_acesso(payload: PerfectPayPostback, motivo: str) -> None:
    """
    Rebaixa o usuario para plano free.

    Acionado por: refunded, chargeback, canceled.

    A Perfect Pay envia o subscription_id no cancelamento -- usamos para
    encontrar o usuario mesmo que ele tenha mudado de email.
    """
    logger.warning(
        f"[BILLING] REVOGANDO ACESSO ({motivo}) | venda={payload.sale_id} "
        f"email={payload.customer_email} subscription_id={payload.subscription_id}"
    )

    from app.core.database import get_db
    db = get_db()

    # Tentativa 1: localizar pelo subscription_id
    user = None
    if payload.subscription_id:
        user = await db.users.find_one({"perfect_pay_subscription_id": payload.subscription_id})

    # Tentativa 2: localizar por email
    if not user and payload.customer_email:
        user = await db.users.find_one({"email": payload.customer_email})

    if not user:
        logger.error(
            f"[BILLING] Nao foi possivel encontrar usuario para revogar acesso. "
            f"subscription_id={payload.subscription_id} email={payload.customer_email}"
        )
        return

    user_id = str(user["_id"])

    # 1. Atualiza coleção users (backward compat)
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "plan":                          "free",
            "perfect_pay_subscription_id":   None,
            "perfect_pay_sale_id":           None,
            "perfect_pay_next_charge_date":  None,
        }}
    )

    # 2. DOC-07: downgrade imediato no LicensingService (fraude/estorno)
    from app.licensing.service import get_licensing_service
    svc = get_licensing_service()
    if svc is not None:
        await svc.downgrade_to_free(user_id, reason=motivo)
    else:
        now = datetime.now(timezone.utc)
        await db.licenses.update_one(
            {"user_id": user_id},
            {"$set": {"plan": "free", "in_grace_period": False, "grace_until": None, "downgraded_at": now}},
            upsert=True,
        )

    logger.warning(f"[BILLING] Plano rebaixado para FREE user_id={user_id} motivo={motivo}")


async def _iniciar_grace_period(payload: PerfectPayPostback, motivo: str) -> None:
    """
    Inicia grace period de ACCESS_GRACE_DAYS dias.

    Acionado por: canceled (assinatura encerrada normalmente), rejected.
    Diferente de _revogar_acesso (que é para fraude/estorno), aqui o
    usuário mantém acesso por alguns dias para regularizar.
    """
    logger.warning(
        f"[BILLING] INICIANDO GRACE PERIOD ({motivo}) | venda={payload.sale_id} "
        f"email={payload.customer_email} subscription_id={payload.subscription_id}"
    )

    from app.core.database import get_db
    db = get_db()

    user = None
    if payload.subscription_id:
        user = await db.users.find_one({"perfect_pay_subscription_id": payload.subscription_id})
    if not user and payload.customer_email:
        user = await db.users.find_one({"email": payload.customer_email})

    if not user:
        logger.error(
            f"[BILLING] Grace period: usuario nao encontrado "
            f"subscription_id={payload.subscription_id} email={payload.customer_email}"
        )
        return

    user_id    = str(user["_id"])
    grace_until = datetime.now(timezone.utc) + timedelta(days=_GRACE_PERIOD_DAYS)

    from app.licensing.service import get_licensing_service
    svc = get_licensing_service()
    if svc is not None:
        await svc.set_grace_period(user_id, grace_until)
    else:
        await db.licenses.update_one(
            {"user_id": user_id},
            {"$set": {"in_grace_period": True, "grace_until": grace_until}},
        )

    logger.warning(
        f"[BILLING] Grace period ativo: user_id={user_id} até={grace_until.date()} motivo={motivo}"
    )
    # TODO: Enviar email de aviso ao usuário


async def _aguardar_pagamento(payload: PerfectPayPostback, descricao: str) -> None:
    """Registra evento informativo (boleto gerado, pendente, etc.) sem alterar plano."""
    logger.info(
        f"[BILLING] Evento informativo: '{descricao}' | venda={payload.sale_id} "
        f"email={payload.customer_email} payment_method={payload.payment_method}"
    )
    # Opcional: salvar no banco que o boleto foi gerado para exibir aviso ao usuario
    # from app.core.database import get_db
    # db = get_db()
    # if payload.customer_email:
    #     await db.users.update_one(
    #         {"email": payload.customer_email},
    #         {"$set": {"payment_pending": True, "payment_method": payload.payment_method}}
    #     )


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------

@router.post(
    "/postback",
    status_code=status.HTTP_200_OK,
    summary="Perfect Pay Postback - recebe e processa eventos de pagamento",
)
async def perfect_pay_postback(payload: PerfectPayPostback) -> Dict[str, str]:
    """
    Fluxo:
      1. Validar campo `token` (hmac.compare_digest)
      2. Resolver status canonico (`status` string > `sale_status_enum`)
      3. Executar acao de negocio: liberar | revogar | aguardar
      4. Retornar 200 (a Perfect Pay retenta em case de falha HTTP)
    """
    postback_secret = settings.perfect_pay_postback_secret
    if not postback_secret:
        logger.error("[BILLING] PERFECT_PAY_POSTBACK_SECRET nao configurado no .env")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integracao Perfect Pay nao configurada.",
        )

    # 1 -- Validar token
    _validate_postback_token(payload.token, postback_secret)

    # 2 -- Resolver status
    resolved = payload.resolved_status()
    logger.info(f"[BILLING] Postback recebido | sale_id={payload.sale_id} resolved_status={resolved}")

    # 3 -- DOC-07: Idempotência — evitar processar o mesmo evento duas vezes
    from app.licensing.service import get_licensing_service
    _svc = get_licensing_service()
    if _svc is not None and await _svc.is_event_processed(payload.sale_id):
        logger.info(f"[BILLING] Evento já processado — ignorando (sale_id={payload.sale_id})")
        return {"status": "already_processed", "sale_id": payload.sale_id}

    # 4 -- Despachar acao
    try:
        if resolved in _STATUS_LIBERAR:
            await _liberar_acesso(payload)

        elif resolved in _STATUS_REVOGAR:
            motivo_map = {
                "refunded":   "Reembolso (refunded)",
                "chargeback": "Chargeback — fraude",
            }
            await _revogar_acesso(payload, motivo_map.get(resolved, resolved))

        elif resolved in _STATUS_GRACE:
            motivo_map = {
                "canceled":  "Assinatura cancelada — grace period",
                "rejected":  "Pagamento rejeitado — grace period",
            }
            await _iniciar_grace_period(payload, motivo_map.get(resolved, resolved))

        elif resolved in _STATUS_AGUARDAR:
            descricao_map = {
                "billet_printed": "Boleto Gerado (aguardando pagamento)",
                "pending":        "Pendente",
                "in_process":     "Em Processo/Mediacao",
            }
            await _aguardar_pagamento(payload, descricao_map.get(resolved, resolved))

        else:
            logger.info(f"[BILLING] Status '{resolved}' sem handler definido -- ignorado (venda={payload.sale_id})")

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            f"[BILLING] Erro ao processar postback venda={payload.sale_id} status={resolved}: {exc}"
        )
        return {"status": "received", "resolved_status": resolved, "processed": "error"}

    # 5 -- DOC-07: Marcar evento como processado (idempotência)
    if _svc is not None:
        await _svc.mark_event_processed(
            sale_id=payload.sale_id,
            event_type=resolved,
        )

    return {"status": "received", "resolved_status": resolved}


# ---------------------------------------------------------------------------
# Endpoint de ping -- use para testar se o ngrok esta recebendo requisicoes
# ---------------------------------------------------------------------------

@router.get(
    "/postback/ping",
    status_code=status.HTTP_200_OK,
    summary="Ping -- verifica se o endpoint de postback esta acessivel",
    description=(
        "Use este endpoint com o Ngrok para confirmar que o tunel esta funcionando "
        "antes de configurar a URL no painel da Perfect Pay. "
        "Acesse GET https://<id>.ngrok-free.app/api/billing/postback/ping"
    ),
)
async def postback_ping() -> Dict[str, str]:
    """Responde 200 com informacoes de configuracao para facilitar o debug com Ngrok."""
    postback_secret = settings.perfect_pay_postback_secret
    return {
        "status":     "ok",
        "endpoint":   "/api/billing/postback",
        "method":     "POST",
        "configured": "yes" if postback_secret else "NO -- defina PERFECT_PAY_POSTBACK_SECRET no .env",
    }


# ---------------------------------------------------------------------------
# Status da assinatura do usuario autenticado
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Status da assinatura do usuario atual",
    description=(
        "Retorna o plano atual, a data de expiracao e quantos dias restam. "
        "Use para exibir alertas no painel do usuario ('Sua assinatura vence em X dias')."
    ),
)
async def subscription_status(
    response: Response,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Nao exige assinatura ativa -- qualquer usuario autenticado pode consultar.
    Retorna status para o frontend poder exibir banners de aviso, plano ativo e dias restantes.
    """
    from app.auth.subscription import _parse_next_charge_date, _AVISO_EXPIRANDO_DIAS
    from app.core.plan_config import get_plan_display, resolve_plan_key
    from datetime import datetime, timezone

    is_superuser = bool(current_user.get("is_superuser"))

    # Superusuários têm acesso irrestrito — plano virtual
    if is_superuser:
        return {
            "plan":              "superuser",
            "plan_display":      "ADMIN",
            "subscription_id":   None,
            "next_charge_date":  None,
            "plan_activated_at": None,
            "days_remaining":    None,
            "is_active":         True,
            "is_expired":        False,
            "expiring_soon":     False,
            "is_superuser":      True,
        }

    plano_raw = str(current_user.get("plan", "starter")).lower()
    plano_key = resolve_plan_key(plano_raw)  # normaliza aliases (black→enterprise, quant→premium)
    plan_display = get_plan_display(plano_raw)

    # Compatibilidade: campo pode vir como string ISO ou datetime
    next_charge_raw = current_user.get("perfect_pay_next_charge_date")
    next_charge = _parse_next_charge_date(next_charge_raw)

    # Data de ativação do plano (para exibição informativa)
    plan_activated_at = current_user.get("plan_activated_at")
    if isinstance(plan_activated_at, datetime):
        plan_activated_at = plan_activated_at.strftime("%Y-%m-%d")

    agora = datetime.now(timezone.utc)
    dias_restantes: Optional[int] = None
    expirada = False
    aviso = False

    if next_charge:
        delta = next_charge - agora
        dias_restantes = max(delta.days, 0)
        expirada = agora > next_charge
        aviso = not expirada and dias_restantes <= _AVISO_EXPIRANDO_DIAS

    # Planos sem next_charge_date (ativados manualmente) são considerados ativos
    is_paid_plan = plano_raw not in ("starter", "free")
    is_active = is_paid_plan and not expirada

    result: Dict[str, Any] = {
        "plan":              plano_raw,
        "plan_display":      plan_display,
        "plan_key":          plano_key,
        "subscription_id":   current_user.get("perfect_pay_subscription_id"),
        "next_charge_date":  next_charge.strftime("%Y-%m-%d") if next_charge else None,
        "plan_activated_at": plan_activated_at,
        "days_remaining":    dias_restantes,
        "is_active":         is_active,
        "is_expired":        expirada,
        "expiring_soon":     aviso,
        "is_superuser":      False,
    }

    if aviso:
        msg = f"Sua assinatura vence em {dias_restantes} dia(s). Renove para nao perder acesso."
        result["warning_message"] = msg
        response.headers["X-Subscription-Warning"] = msg

    if expirada:
        result["warning_message"] = "Assinatura expirada. Renove seu plano para continuar."

    return result
