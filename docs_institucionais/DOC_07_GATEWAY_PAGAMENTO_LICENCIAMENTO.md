# DOC 07 — Gateway de Pagamento + Licenciamento Real
## Manual Técnico de Nível Institucional

> **Versão:** 1.0.0 | **Audiência:** Equipe de Engenharia

---

## 1. Objetivo

Substituir o sistema de licenciamento mock (com dev bypass de `Premium` para todos) por um sistema real de pagamento integrado com Stripe, que:

- Controle granular de features por plano (Basic/Pro/Enterprise)
- Bloqueio automático por inadimplência com período de grace
- Downgrade automático após cancelamento
- Webhooks seguros com validação de assinatura HMAC-SHA256
- Zero perda de serviço por falha temporária do Stripe
- Auditoria completa de todos os eventos de cobrança

---

## 2. Problema Atual

### 2.1 Dev Bypass Crítico (DEVE SER REMOVIDO)

```python
# backend/app/licensing/service.py — VULNERABILIDADE EXISTENTE
async def get_license(user_id: str) -> LicenseResponse:
    try:
        license = await db.licenses.find_one({"user_id": user_id})
        if not license:
            raise NotFound()
        return LicenseResponse(**license)
    except Exception:
        # ← CRÍTICO: Qualquer erro retorna Premium gratuitamente
        return LicenseResponse(valid=True, plan="Premium", features=ALL_FEATURES)
```

**Impacto:** Qualquer usuário sem registro, ou com MongoDB offline, recebe acesso Premium **gratuitamente**. Em produção, isso significa perda total de receita.

---

## 3. Arquitetura do Sistema de Pagamento

```
┌────────────────────────────────────────────────────────────────────┐
│                    FLUXO DE PAGAMENTO                              │
│                                                                    │
│  USUARIO                                                           │
│     │                                                              │
│     │  1. Seleciona plano                                         │
│     ▼                                                              │
│  FRONTEND (React)                                                  │
│     │  POST /api/billing/checkout                                  │
│     ▼                                                              │
│  BACKEND (FastAPI) ──── Cria Checkout Session ──── STRIPE         │
│     │                                               │              │
│     │  Retorna checkout_url                         │              │
│     ▼                                               │              │
│  FRONTEND redireciona para Stripe Hosted UI         │              │
│                                                      │              │
│  STRIPE processa pagamento                          │              │
│     │                                               │              │
│     │  Webhook → POST /api/billing/webhook           │              │
│     ▼                                               │              │
│  BACKEND valida assinatura HMAC-SHA256              │              │
│     │                                               │              │
│     ├── checkout.session.completed ──→ Ativa licença│              │
│     ├── invoice.payment_failed     ──→ Inicia grace period         │
│     ├── invoice.payment_succeeded  ──→ Renova licença              │
│     └── customer.subscription.deleted ──→ Downgrade               │
│                                                                    │
│  LICENSE CACHE (Redis TTL=30min)                                   │
│     │                                                              │
│     └── Todos os requests verificam cache antes do MongoDB         │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementação

### 4.1 Remover Dev Bypass e Implementar Serviço Real

```python
# backend/app/licensing/service.py — VERSÃO CORRIGIDA

from app.core.redis import get_redis
from app.core.database import get_db
from app.billing.stripe_client import StripeClient
from app.core.logger import get_logger
from datetime import datetime, UTC
import json

logger = get_logger(__name__)

PLAN_FEATURES: dict[str, list[str]] = {
    "basic": [
        "bots:1",
        "symbols:3",
        "backtesting:false",
        "marketplace:read",
        "support:community"
    ],
    "pro": [
        "bots:5",
        "symbols:20",
        "backtesting:true",
        "marketplace:read+write",
        "support:email",
        "analytics:advanced",
        "tp_sl:true"
    ],
    "enterprise": [
        "bots:unlimited",
        "symbols:unlimited",
        "backtesting:true",
        "marketplace:read+write+sell",
        "support:dedicated",
        "analytics:advanced",
        "tp_sl:true",
        "multi_exchange:true",
        "api_access:true"
    ]
}

class LicensingService:
    def __init__(self, db, redis):
        self.db = db
        self.redis = redis

    async def get_license(self, user_id: str) -> "LicenseResponse":
        """
        Verificação de licença com cache Redis.
        JAMAIS retorna plano Premium em caso de erro — falha com acesso negado.
        """
        cache_key = f"license:{user_id}"

        # 1. Checar cache Redis (30min TTL)
        cached = await self.redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return LicenseResponse(**data)

        # 2. Buscar no MongoDB
        try:
            license_doc = await self.db.licenses.find_one(
                {"user_id": user_id},
                {"_id": 0}
            )
        except Exception as e:
            logger.error({
                "event": "license_db_error",
                "user_id": user_id,
                "error": str(e)
            })
            # NUNCA retornar premium em fallback — negar acesso
            raise LicenseCheckError("Serviço de licenciamento temporariamente indisponível")

        if not license_doc:
            # Usuário sem licença → Free tier
            response = LicenseResponse(
                valid=True,
                plan="free",
                features=["bots:0", "symbols:0"],
                expires_at=None,
                in_grace_period=False
            )
            await self.redis.setex(cache_key, 300, response.model_dump_json())
            return response

        # 3. Validar expiração e grace period
        now = datetime.now(UTC)
        expires_at: datetime | None = license_doc.get("expires_at")
        grace_until: datetime | None = license_doc.get("grace_until")

        if expires_at and now > expires_at:
            if grace_until and now <= grace_until:
                # Dentro do grace period (3 dias após falha de pagamento)
                logger.warn({"event": "license_in_grace", "user_id": user_id})
                response = LicenseResponse(
                    valid=True,
                    plan=license_doc["plan"],
                    features=PLAN_FEATURES.get(license_doc["plan"], []),
                    expires_at=expires_at,
                    in_grace_period=True,
                    grace_until=grace_until
                )
            else:
                # Expirado e fora do grace → downgrade para free
                await self._downgrade_to_free(user_id)
                response = LicenseResponse(
                    valid=True,
                    plan="free",
                    features=[],
                    expires_at=None,
                    in_grace_period=False
                )
        else:
            response = LicenseResponse(
                valid=True,
                plan=license_doc["plan"],
                features=PLAN_FEATURES.get(license_doc["plan"], []),
                expires_at=expires_at,
                in_grace_period=False
            )

        # Cache por 30 minutos
        await self.redis.setex(cache_key, 1800, response.model_dump_json())
        return response

    async def _downgrade_to_free(self, user_id: str) -> None:
        """Downgrade automático com log de auditoria."""
        await self.db.licenses.update_one(
            {"user_id": user_id},
            {"$set": {"plan": "free", "downgraded_at": datetime.now(UTC)}}
        )
        await self.db.license_audit.insert_one({
            "user_id": user_id,
            "event": "auto_downgrade_to_free",
            "reason": "payment_failed_grace_period_expired",
            "timestamp": datetime.now(UTC)
        })
        # Invalidar cache
        await self.redis.delete(f"license:{user_id}")
        logger.info({"event": "license_downgraded", "user_id": user_id})
```

### 4.2 Webhook Stripe Seguro

```python
# backend/app/billing/webhook.py

from fastapi import APIRouter, Request, HTTPException, Header
import stripe
from app.core.config import settings
from app.licensing.service import LicensingService
from app.core.logger import get_logger
from datetime import datetime, UTC, timedelta

logger = get_logger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
    licensing: LicensingService = Depends(get_licensing_service)
):
    payload = await request.body()

    # ── VALIDAÇÃO OBRIGATÓRIA de assinatura HMAC-SHA256 ──────────────
    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warn({"event": "webhook_signature_invalid", "error": str(e)})
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error({"event": "webhook_parse_error", "error": str(e)})
        raise HTTPException(status_code=400, detail="Invalid payload")

    # ── IDEMPOTÊNCIA: Evitar processar mesmo evento duas vezes ────────
    event_id = event["id"]
    if await licensing.isEventProcessed(event_id):
        logger.info({"event": "webhook_duplicate", "stripe_event_id": event_id})
        return {"status": "already_processed"}

    # ── PROCESSAR EVENTO ──────────────────────────────────────────────
    match event["type"]:
        case "checkout.session.completed":
            await handle_checkout_completed(event["data"]["object"], licensing)

        case "invoice.payment_succeeded":
            await handle_payment_succeeded(event["data"]["object"], licensing)

        case "invoice.payment_failed":
            await handle_payment_failed(event["data"]["object"], licensing)

        case "customer.subscription.deleted":
            await handle_subscription_deleted(event["data"]["object"], licensing)

        case _:
            logger.debug({"event": "webhook_unhandled", "type": event["type"]})

    # Marcar como processado
    await licensing.markEventProcessed(event_id)
    return {"status": "ok"}


async def handle_checkout_completed(session: dict, licensing: LicensingService):
    user_id = session["metadata"].get("user_id")
    plan = session["metadata"].get("plan", "basic")

    if not user_id:
        logger.error({"event": "webhook_no_user_id", "session": session["id"]})
        return

    subscription_id = session.get("subscription")

    # Calcular expiração (1 mês ou 1 ano dependendo do plano)
    interval = session["metadata"].get("interval", "month")
    delta = timedelta(days=365 if interval == "year" else 31)
    expires_at = datetime.now(UTC) + delta

    await licensing.activateLicense({
        "user_id": user_id,
        "plan": plan,
        "stripe_subscription_id": subscription_id,
        "stripe_customer_id": session.get("customer"),
        "expires_at": expires_at,
        "activated_at": datetime.now(UTC)
    })

    logger.info({"event": "license_activated", "user_id": user_id, "plan": plan})


async def handle_payment_failed(invoice: dict, licensing: LicensingService):
    subscription_id = invoice.get("subscription")
    license = await licensing.findBySubscriptionId(subscription_id)
    if not license:
        return

    # Grace period: 3 dias para regularizar
    grace_until = datetime.now(UTC) + timedelta(days=3)

    await licensing.setGracePeriod(license["user_id"], grace_until)

    # Invalida cache para forçar re-verificação
    await licensing.invalidateCache(license["user_id"])

    logger.warn({
        "event": "license_payment_failed",
        "user_id": license["user_id"],
        "grace_until": grace_until.isoformat()
    })
    # TODO: Enviar email de warning ao usuário
```

### 4.3 Middleware de Feature Gate

```typescript
// src/middleware/feature-gate.middleware.ts

import { Request, Response, NextFunction } from 'express';
import { LicensingClient } from '../licensing/licensing-client';

const FEATURE_LIMITS: Record<string, Record<string, number | boolean | string>> = {
  basic:      { maxBots: 1, maxSymbols: 3, backtesting: false, marketplace: 'read' },
  pro:        { maxBots: 5, maxSymbols: 20, backtesting: true, marketplace: 'read+write' },
  enterprise: { maxBots: -1, maxSymbols: -1, backtesting: true, marketplace: 'read+write+sell' },
  free:       { maxBots: 0, maxSymbols: 0, backtesting: false, marketplace: 'none' }
};

export function requireFeature(feature: string) {
  return async (req: Request, res: Response, next: NextFunction) => {
    const userId = req.user!.id;
    const license = await LicensingClient.getLicense(userId);

    if (!license.valid) {
      return res.status(402).json({ error: 'Licença inválida ou expirada' });
    }

    if (license.in_grace_period) {
      res.setHeader('X-License-Warning', 'Grace period ativo — regularize seu pagamento');
    }

    const limits = FEATURE_LIMITS[license.plan] ?? FEATURE_LIMITS.free;
    const hasFeature = limits[feature];

    if (!hasFeature || hasFeature === 'none' || hasFeature === false || hasFeature === 0) {
      return res.status(403).json({
        error: 'Recurso não disponível no seu plano',
        feature,
        currentPlan: license.plan,
        upgrade: '/planos'
      });
    }

    req.licenseContext = { plan: license.plan, limits };
    next();
  };
}

// Uso:
// router.post('/bots', requireFeature('maxBots'), createBotHandler);
// router.get('/backtesting', requireFeature('backtesting'), backtestHandler);
```

---

## 5. Fluxo de Checkout com Stripe Checkout Sessions

```typescript
// src/billing/checkout.service.ts

import Stripe from 'stripe';

const PRICE_IDS: Record<string, Record<string, string>> = {
  basic:      { month: 'price_basic_monthly', year: 'price_basic_yearly' },
  pro:        { month: 'price_pro_monthly', year: 'price_pro_yearly' },
  enterprise: { month: 'price_enterprise_monthly', year: 'price_enterprise_yearly' }
};

export class CheckoutService {
  constructor(private stripe: Stripe) {}

  async createCheckoutSession(params: {
    userId: string;
    plan: 'basic' | 'pro' | 'enterprise';
    interval: 'month' | 'year';
    successUrl: string;
    cancelUrl: string;
  }): Promise<string> {
    const priceId = PRICE_IDS[params.plan]?.[params.interval];
    if (!priceId) throw new Error(`Plano inválido: ${params.plan}/${params.interval}`);

    const session = await this.stripe.checkout.sessions.create({
      mode: 'subscription',
      payment_method_types: ['card'],
      line_items: [{ price: priceId, quantity: 1 }],
      metadata: {
        user_id: params.userId,
        plan: params.plan,
        interval: params.interval
      },
      success_url: params.successUrl + '?session_id={CHECKOUT_SESSION_ID}',
      cancel_url: params.cancelUrl,
      allow_promotion_codes: true,
      subscription_data: {
        trial_period_days: params.plan === 'pro' ? 7 : undefined  // 7 dias trial Pro
      }
    });

    return session.url!;
  }
}
```

---

## 6. Testes Obrigatórios

```python
# tests/test_licensing.py

async def test_no_premium_bypass_on_db_error():
    """CRÍTICO: Nunca retornar Premium em caso de erro."""
    db_mock.licenses.find_one.side_effect = Exception("MongoDB timeout")
    with pytest.raises(LicenseCheckError):
        await licensing_service.get_license("user-001")

async def test_grace_period_allows_access():
    future = datetime.now(UTC) + timedelta(days=2)
    past = datetime.now(UTC) - timedelta(hours=1)
    db_mock.licenses.find_one.return_value = {
        "plan": "pro", "expires_at": past, "grace_until": future
    }
    result = await licensing_service.get_license("user-001")
    assert result.valid is True
    assert result.in_grace_period is True

async def test_expired_grace_period_downgrades():
    db_mock.licenses.find_one.return_value = {
        "plan": "pro",
        "expires_at": datetime.now(UTC) - timedelta(days=5),
        "grace_until": datetime.now(UTC) - timedelta(days=1)  # Grace expirado
    }
    result = await licensing_service.get_license("user-001")
    assert result.plan == "free"

async def test_webhook_rejects_invalid_signature():
    response = client.post("/api/billing/webhook",
        content=b'{"type": "checkout.session.completed"}',
        headers={"stripe-signature": "invalid"}
    )
    assert response.status_code == 400
```

---

## 7. Checklist de Implementação

- [ ] **REMOVER** dev bypass em `licensing/service.py` imediatamente
- [ ] Variável `STRIPE_WEBHOOK_SECRET` em `.env` e validada no startup
- [ ] Variável `STRIPE_SECRET_KEY` em `.env` (nunca exposta no frontend)
- [ ] Price IDs do Stripe configurados por ambiente (test/prod)
- [ ] Middleware `requireFeature()` aplicado em todas as rotas protegidas
- [ ] Grace period de 3 dias configurado e testado
- [ ] Downgrade automático por expiração de grace
- [ ] Idempotência de webhooks (tabela `webhook_events` com `stripe_event_id`)
- [ ] Cache Redis de licença com TTL=30min + invalidação em eventos de billing
- [ ] Testes com `stripe-signature` inválida (deve retornar 400)
- [ ] Teste de `no_premium_bypass` obrigatório em CI
- [ ] Portal do cliente Stripe para autoatendimento de fatura

---

## 8. Critérios de Validação Final

| Critério | Aprovação |
|---|---|
| Dev bypass removido | 0 retornos de Premium sem licença válida |
| Webhook com assinatura inválida | Sempre 400, nunca processado |
| Grace period | Acesso mantido por exatamente 3 dias após falha |
| Downgrade automático | Ocorre em < 1h após expiração do grace |
| Cache consistency | Licença invalidada em < 30min após evento Stripe |
| Zero perda de receita | Usuários free não acessam features pagas |
