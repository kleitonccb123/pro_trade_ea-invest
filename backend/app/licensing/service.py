"""
LicensingService — DOC-07

Verificação de licença por usuário com:
  - Cache Redis (TTL 30 min) — evita queries MongoDB a cada request
  - MongoDB como fonte de verdade (coleção `licenses`)
  - Grace period respeitado (3 dias após falha de pagamento)
  - Downgrade automático quando grace period expira
  - NUNCA retorna plano pago em caso de falha no banco

REGRA DE OURO:
  Em caso de erro do MongoDB → lança LicenseCheckError → HTTP 503
  Em caso de Redis offline   → vai direto ao MongoDB (fallback gracioso)
  Em caso de licença ausente → retorna plano "free" (nunca Premium)

Uso::

    from app.licensing.service import get_licensing_service

    @router.get("/protected")
    async def endpoint(current_user=Depends(get_current_user)):
        svc = get_licensing_service()
        lic = await svc.get_license(str(current_user["_id"]))
        if not lic.valid or lic.plan == "free":
            raise HTTPException(402, "Assinatura necessária")
        ...
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Optional

from app.licensing.exceptions import LicenseCheckError
from app.licensing.features import to_bool_features
from app.licensing.schemas import LicenseResponse

logger = logging.getLogger(__name__)

_CACHE_TTL_NORMAL = 1_800   # 30 min
_CACHE_TTL_FREE   = 300     # 5 min (compra recente reflete mais rápido)
_GRACE_DAYS       = 3


def _cache_key(user_id: str) -> str:
    return f"license:{user_id}"


def _free_response(user_id: str) -> LicenseResponse:
    return LicenseResponse(
        valid=True,
        plan="free",
        features=to_bool_features("free"),
        user_id=user_id,
    )


class LicensingService:
    """
    Serviço de licenciamento per-user — DOC-07.

    Instância singleton criada pelo on_startup do main.py
    via init_licensing_service().
    """

    def __init__(self, db: Any, redis: Optional[Any]) -> None:
        self._db    = db
        self._redis = redis

    # ── API pública ───────────────────────────────────────────────────────────

    async def get_license(self, user_id: str) -> LicenseResponse:
        """
        Retorna o status de licença do usuário com cache Redis.

        NUNCA retorna plano pago em caso de erro — lança LicenseCheckError.
        """
        cached = await self._get_cached(user_id)
        if cached is not None:
            return cached

        doc = await self._fetch_from_db(user_id)

        if doc is None:
            resp = _free_response(user_id)
            await self._set_cache(user_id, resp, ttl=_CACHE_TTL_FREE)
            return resp

        resp = await self._resolve_license(user_id, doc)
        ttl = _CACHE_TTL_FREE if resp.plan == "free" else _CACHE_TTL_NORMAL
        await self._set_cache(user_id, resp, ttl=ttl)
        return resp

    async def is_feature_enabled(self, user_id: str, feature: str) -> bool:
        """Verifica se uma feature está habilitada para o usuário."""
        try:
            lic = await self.get_license(user_id)
            return lic.valid and lic.features.get(feature, False)
        except LicenseCheckError:
            return False

    async def is_valid(self, user_id: str) -> bool:
        """Compat. legado — verifica se a licença é válida (não free)."""
        try:
            lic = await self.get_license(user_id)
            return lic.valid and lic.plan.lower() not in ("free", "starter")
        except LicenseCheckError:
            return False

    async def invalidate_cache(self, user_id: str) -> None:
        """Invalida cache — chamado pelo billing router após eventos de pagamento."""
        if self._redis is not None:
            try:
                await self._redis.delete(_cache_key(user_id))
            except Exception as exc:
                logger.warning("LicensingService.invalidate_cache: redis error: %s", exc)

    async def is_event_processed(self, sale_id: str) -> bool:
        """Idempotência: o sale_id já foi processado?"""
        try:
            doc = await self._db.webhook_events.find_one({"sale_id": sale_id}, {"_id": 1})
            return doc is not None
        except Exception as exc:
            logger.warning("LicensingService.is_event_processed: db error: %s", exc)
            return False

    async def mark_event_processed(
        self,
        sale_id: str,
        event_type: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Registra evento como processado para idempotência futura."""
        try:
            await self._db.webhook_events.update_one(
                {"sale_id": sale_id},
                {"$set": {
                    "sale_id":      sale_id,
                    "event_type":   event_type,
                    "user_id":      user_id,
                    "processed_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
        except Exception as exc:
            logger.warning("LicensingService.mark_event_processed: db error: %s", exc)

    async def activate_license(
        self,
        user_id: str,
        plan: str,
        subscription_id: Optional[str] = None,
        sale_id: Optional[str] = None,
        product_name: Optional[str] = None,
        payment_method: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> None:
        """Ativa ou renova a licença. Chamado pelo billing router em approved/complete."""
        now = datetime.now(timezone.utc)
        await self._db.licenses.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id":          user_id,
                "plan":             plan,
                "subscription_id":  subscription_id,
                "sale_id":          sale_id,
                "product_name":     product_name,
                "payment_method":   payment_method,
                "expires_at":       expires_at,
                "activated_at":     now,
                "in_grace_period":  False,
                "grace_until":      None,
                "canceled_at":      None,
                "downgraded_at":    None,
                "updated_at":       now,
            }},
            upsert=True,
        )
        await self._audit(user_id, "license_activated", {"plan": plan, "sale_id": sale_id})
        await self.invalidate_cache(user_id)
        logger.info("LicensingService: licença ativada user=%s plan=%s", user_id, plan)

    async def set_grace_period(self, user_id: str, grace_until: datetime) -> None:
        """Inicia grace period após falha de pagamento (3 dias de acesso mantido)."""
        await self._db.licenses.update_one(
            {"user_id": user_id},
            {"$set": {
                "in_grace_period": True,
                "grace_until":     grace_until,
                "updated_at":      datetime.now(timezone.utc),
            }},
        )
        await self._audit(user_id, "grace_period_started", {"grace_until": grace_until.isoformat()})
        await self.invalidate_cache(user_id)
        logger.warning(
            "LicensingService: grace period iniciado user=%s até=%s",
            user_id, grace_until.isoformat(),
        )

    async def downgrade_to_free(self, user_id: str, reason: str) -> None:
        """Rebaixa usuário para free. Chamado por cancelamento ou expiração de grace."""
        now = datetime.now(timezone.utc)
        await self._db.licenses.update_one(
            {"user_id": user_id},
            {"$set": {
                "plan":             "free",
                "in_grace_period":  False,
                "grace_until":      None,
                "subscription_id":  None,
                "expires_at":       None,
                "downgraded_at":    now,
                "updated_at":       now,
            }},
            upsert=True,
        )
        await self._audit(user_id, "downgraded_to_free", {"reason": reason})
        await self.invalidate_cache(user_id)
        logger.warning(
            "LicensingService: downgrade para free user=%s motivo=%s", user_id, reason
        )

    async def find_by_subscription_id(self, subscription_id: str) -> Optional[dict]:
        """Localiza documento de licença pelo subscription_id da Perfect Pay."""
        try:
            return await self._db.licenses.find_one({"subscription_id": subscription_id})
        except Exception as exc:
            logger.warning("LicensingService.find_by_subscription_id: db error: %s", exc)
            return None

    # ── Internos ──────────────────────────────────────────────────────────────

    async def _get_cached(self, user_id: str) -> Optional[LicenseResponse]:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(_cache_key(user_id))
            if raw:
                data = json.loads(raw)
                return LicenseResponse(**data)
        except Exception as exc:
            logger.debug("LicensingService: cache miss: %s", exc)
        return None

    async def _set_cache(self, user_id: str, resp: LicenseResponse, ttl: int) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.setex(
                _cache_key(user_id), ttl,
                resp.model_dump_json(exclude_none=False),
            )
        except Exception as exc:
            logger.debug("LicensingService: falha ao escrever cache: %s", exc)

    async def _fetch_from_db(self, user_id: str) -> Optional[dict]:
        """
        CRÍTICO: qualquer exceção do banco → lança LicenseCheckError.
        NUNCA retorna plano pago como fallback.
        """
        try:
            return await self._db.licenses.find_one({"user_id": user_id}, {"_id": 0})
        except Exception as exc:
            logger.error(
                "LicensingService: erro ao consultar banco user=%s: %s", user_id, exc
            )
            raise LicenseCheckError(
                "Serviço de licenciamento temporariamente indisponível — tente novamente"
            ) from exc

    async def _resolve_license(self, user_id: str, doc: dict) -> LicenseResponse:
        """Aplica lógica de expiração e grace period ao documento do banco."""
        now         = datetime.now(timezone.utc)
        plan        = doc.get("plan", "free")
        expires_at  = _to_dt(doc.get("expires_at"))
        grace_until = _to_dt(doc.get("grace_until"))
        in_grace    = bool(doc.get("in_grace_period", False))

        if plan.lower() in ("free", "starter"):
            return _free_response(user_id)

        # Licença sem data de expiração (perpétua ou primeiro registro)
        if expires_at is None:
            return LicenseResponse(
                valid=True,
                plan=plan,
                features=to_bool_features(plan),
                user_id=user_id,
            )

        # Ainda dentro da vigência
        if now <= expires_at:
            return LicenseResponse(
                valid=True,
                plan=plan,
                features=to_bool_features(plan),
                expires_at=expires_at,
                in_grace_period=False,
                user_id=user_id,
            )

        # Expirada — verificar grace period
        if in_grace and grace_until and now <= grace_until:
            logger.warning(
                "LicensingService: grace period ativo user=%s até=%s",
                user_id, grace_until.isoformat(),
            )
            return LicenseResponse(
                valid=True,
                plan=plan,
                features=to_bool_features(plan),
                expires_at=expires_at,
                in_grace_period=True,
                grace_until=grace_until,
                user_id=user_id,
            )

        # Grace expirado → downgrade automático
        await self.downgrade_to_free(user_id, "grace_period_expired")
        return _free_response(user_id)

    async def _audit(self, user_id: str, event: str, context: dict) -> None:
        try:
            await self._db.license_audit.insert_one({
                "user_id":   user_id,
                "event":     event,
                "context":   context,
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception as exc:
            logger.warning("LicensingService._audit: db error: %s", exc)


def _to_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    return None


# ─── Singleton global ─────────────────────────────────────────────────────────

_licensing_service: Optional[LicensingService] = None


def init_licensing_service(db: Any, redis: Optional[Any]) -> LicensingService:
    """Inicializa o singleton. Chamado pelo on_startup do main.py (DOC-07)."""
    global _licensing_service
    _licensing_service = LicensingService(db=db, redis=redis)
    logger.info("LicensingService (DOC-07) inicializado")
    return _licensing_service


def get_licensing_service() -> Optional[LicensingService]:
    return _licensing_service


# Compat. legado — a antiga instância global usada pelos routers existentes
# (será depreciada — migrar para get_licensing_service() + user_id explícito)
class _LegacyLicensingService:
    """Wrapper de compatibilidade que preserva a API antiga sem argumentos."""

    async def get_license(self) -> LicenseResponse:  # type: ignore[override]
        return LicenseResponse(valid=True, plan="free", features={})

    async def is_feature_enabled(self, feature: str) -> bool:
        return False

    async def is_valid(self) -> bool:
        return False


licensing_service = _LegacyLicensingService()
