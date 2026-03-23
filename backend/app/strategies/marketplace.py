"""
DOC-08 — Marketplace de Estratégias
MarketplaceService: publicação, assinatura, teardown, revenue share.

Regras de segurança:
  - Código da estratégia SEMPRE armazenado cifrado (AES-256 via Fernet).
  - Compradores NUNCA recebem o código-fonte — apenas executam instâncias.
  - Publicação bloqueada se backtesting não aprovado.
  - Teardown de instâncias em < 5 minutos após cancelamento.
  - Revenue share: 70% criador / 30% plataforma (configurável via env).
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.strategies.model import (
    PricingType,
    StrategyBotInstance,
    StrategyCategory,
    StrategyPricing,
    StrategyPublicMetrics,
    StrategyStatus,
    StrategySubscription,
    StrategyVersion,
    UserStrategy,
)

logger = logging.getLogger(__name__)

# Constantes de revenue share (sobrescritas pelo config se disponível)
_DEFAULT_PLATFORM_TAKE_RATE = 0.30
_DEFAULT_CREATOR_SHARE = 0.70


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic request/response helpers
# ──────────────────────────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    backtest_result_id: str   # ID do BacktestResult aprovado
    semver: str               # ex: "1.0.0"
    changelog: str = ""
    pricing_type: PricingType = PricingType.free
    amount_usd: float = 0.0
    required_plan: str = "free"


class SubscribeRequest(BaseModel):
    payment_ref: Optional[str] = None   # Referência Perfect Pay (se pago)


class MarketplaceListing(BaseModel):
    strategy_id: str
    name: str
    description: str
    category: str
    creator_id: str
    pricing: StrategyPricing
    metrics: StrategyPublicMetrics
    total_subscribers: int
    is_published: bool
    published_at: Optional[datetime] = None
    current_version: str


# ──────────────────────────────────────────────────────────────────────────────
# Serviço principal
# ──────────────────────────────────────────────────────────────────────────────

class MarketplaceService:
    """
    Serviço assíncrono (Motor) para gestão do marketplace de estratégias.

    Coleções MongoDB utilizadas:
      - strategies              (documentos UserStrategy)
      - strategy_subscriptions  (assinaturas ativas)
      - strategy_bot_instances  (instâncias de bots)
      - strategy_trades         (trades executados)
      - backtest_results        (resultados de backtesting)
      - revenue_events          (log de revenue share)
      - strategy_creator_wallets (saldos dos criadores)
    """

    PLATFORM_TAKE_RATE: float = _DEFAULT_PLATFORM_TAKE_RATE
    CREATOR_SHARE: float = _DEFAULT_CREATOR_SHARE

    def __init__(self, db: AsyncIOMotorDatabase, encryption_key: Optional[str] = None):
        self.db = db
        self._strategies = db["strategies"]
        self._subscriptions = db["strategy_subscriptions"]
        self._instances = db["strategy_bot_instances"]
        self._trades = db["strategy_trades"]
        self._backtest_results = db["backtest_results"]
        self._revenue_events = db["revenue_events"]
        self._creator_wallets = db["strategy_creator_wallets"]

        # Fernet key para AES-256 do código; gera ephemeral key se não configurada
        key = encryption_key
        if not key:
            key = os.getenv("STRATEGY_ENCRYPTION_KEY")
        if not key:
            warnings.warn(
                "STRATEGY_ENCRYPTION_KEY não configurada. "
                "Gerando chave efêmera — codes serão ilegíveis após restart!",
                RuntimeWarning,
                stacklevel=2,
            )
            key = Fernet.generate_key().decode()
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    # ── Cifragem ───────────────────────────────────────────────────────────────

    def encrypt_code(self, source_code: str) -> str:
        """Cifra código-fonte da estratégia. Retorna bytes base64 como str."""
        return self._fernet.encrypt(source_code.encode()).decode()

    def decrypt_code(self, encrypted: str) -> str:
        """Decifra código. Apenas para execução interna — nunca expor via API."""
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Código cifrado inválido ou chave incorreta") from exc

    @staticmethod
    def hash_code(source_code: str) -> str:
        return hashlib.sha256(source_code.encode()).hexdigest()

    # ── Criação de estratégia ──────────────────────────────────────────────────

    async def create_strategy(
        self,
        creator_id: str,
        name: str,
        description: str,
        category: str,
        source_code: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        exchanges: Optional[List[str]] = None,
        asset_types: Optional[List[str]] = None,
    ) -> UserStrategy:
        """
        Cria rascunho de estratégia, cifrando o código imediatamente.
        Retorna UserStrategy salvo no MongoDB.
        """
        strategy_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        encrypted = self.encrypt_code(source_code)
        code_hash = self.hash_code(source_code)

        version = StrategyVersion(
            version_id=version_id,
            semver="0.1.0",
            code_encrypted=encrypted,
            code_hash=code_hash,
            parameters=parameters or [],
            changelog="Versão inicial",
            status=StrategyStatus.draft,
        )

        strategy = UserStrategy(
            strategy_id=strategy_id,
            creator_id=creator_id,
            name=name,
            description=description,
            category=StrategyCategory(category) if category in StrategyCategory.__members__ else StrategyCategory.custom,
            exchanges=exchanges or ["kucoin"],
            asset_types=asset_types or ["spot"],
            current_version="0.1.0",
            versions=[version],
            status=StrategyStatus.draft,
        )

        await self._strategies.update_one(
            {"strategy_id": strategy_id},
            {"$set": strategy.model_dump()},
            upsert=True,
        )
        logger.info("Estratégia criada strategy_id=%s creator=%s", strategy_id, creator_id)
        return strategy

    # ── Publicação ─────────────────────────────────────────────────────────────

    async def publish_strategy(
        self,
        strategy_id: str,
        creator_id: str,
        req: PublishRequest,
    ) -> UserStrategy:
        """
        Publica estratégia após validar backtesting aprovado.
        Levanta ValueError se backtest não aprovado ou estratégia não pertence ao criador.
        """
        # Verifica autoria
        doc = await self._strategies.find_one({"strategy_id": strategy_id, "creator_id": creator_id})
        if not doc:
            raise ValueError("Estratégia não encontrada ou sem permissão")

        # Valida backtest aprovado
        bt_doc = await self._backtest_results.find_one({"backtest_id": req.backtest_result_id})
        if not bt_doc:
            raise ValueError("Resultado de backtesting não encontrado")
        if not bt_doc.get("passed", False):
            reasons = "; ".join(bt_doc.get("failure_reasons", []))
            raise ValueError(f"Backtesting não aprovado: {reasons}")
        if bt_doc.get("strategy_id") != strategy_id:
            raise ValueError("backtest_result_id não pertence a esta estratégia")

        # Extrai métricas do backtest para o perfil público
        bt_metrics = bt_doc.get("metrics", {})
        config = bt_doc.get("config", {})
        period_days = max(1, (config.get("end_ts", 0) - config.get("start_ts", 0)) // 86400)
        verified_at = datetime.now(timezone.utc)

        public_metrics = StrategyPublicMetrics(
            backtest_period_days=period_days,
            total_return_pct=bt_metrics.get("total_return_pct", 0.0),
            annualized_return_pct=bt_metrics.get("annualized_return_pct", 0.0),
            sharpe_ratio=bt_metrics.get("sharpe_ratio", 0.0),
            max_drawdown_pct=bt_metrics.get("max_drawdown_pct", 0.0),
            win_rate=bt_metrics.get("win_rate", 0.0),
            profit_factor=bt_metrics.get("profit_factor", 0.0),
            total_trades=bt_metrics.get("total_trades", 0),
            avg_trade_duration=f"{bt_metrics.get('avg_holding_period_hours', 0.0):.1f}h",
            verified_at=verified_at,
        )

        # Cria nova versão publicada vinculada ao backtest
        # Reaproveita o código cifrado da versão atual (não exige reenvio)
        existing_versions: List[Dict] = doc.get("versions", [])
        latest_code_enc = existing_versions[-1]["code_encrypted"] if existing_versions else ""
        latest_code_hash = existing_versions[-1]["code_hash"] if existing_versions else ""

        new_version = StrategyVersion(
            version_id=str(uuid.uuid4()),
            semver=req.semver,
            code_encrypted=latest_code_enc,
            code_hash=latest_code_hash,
            changelog=req.changelog,
            backtest_result_id=req.backtest_result_id,
            status=StrategyStatus.published,
        )

        pricing = StrategyPricing(
            type=req.pricing_type,
            amount_usd=req.amount_usd,
            required_plan=req.required_plan,
        )

        now = datetime.now(timezone.utc)
        await self._strategies.update_one(
            {"strategy_id": strategy_id},
            {
                "$set": {
                    "is_published": True,
                    "status": StrategyStatus.published.value,
                    "current_version": req.semver,
                    "metrics": public_metrics.model_dump(),
                    "pricing": pricing.model_dump(),
                    "published_at": now,
                },
                "$push": {"versions": new_version.model_dump()},
            },
        )

        # Vincula backtest à estratégia
        await self._backtest_results.update_one(
            {"backtest_id": req.backtest_result_id},
            {"$set": {"published_at": now}},
        )

        logger.info(
            "Estratégia publicada strategy_id=%s semver=%s", strategy_id, req.semver
        )
        updated = await self._strategies.find_one({"strategy_id": strategy_id})
        updated.pop("_id", None)
        return UserStrategy(**updated)

    # ── Listagem marketplace ───────────────────────────────────────────────────

    async def list_marketplace(
        self,
        category: Optional[str] = None,
        sort_by: str = "metrics.sharpe_ratio",
        limit: int = 50,
        offset: int = 0,
    ) -> List[MarketplaceListing]:
        """Retorna estratégias publicadas (sem código-fonte)."""
        query: Dict[str, Any] = {"is_published": True}
        if category:
            query["category"] = category

        cursor = (
            self._strategies.find(query, {"versions": 0})  # Exclui versions (contém código)
            .sort(sort_by, -1)
            .skip(offset)
            .limit(limit)
        )

        results: List[MarketplaceListing] = []
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                results.append(MarketplaceListing(
                    strategy_id=doc["strategy_id"],
                    name=doc["name"],
                    description=doc.get("description", ""),
                    category=doc.get("category", "custom"),
                    creator_id=doc["creator_id"],
                    pricing=StrategyPricing(**doc.get("pricing", {})),
                    metrics=StrategyPublicMetrics(**doc.get("metrics", {})),
                    total_subscribers=doc.get("total_subscribers", 0),
                    is_published=doc.get("is_published", False),
                    published_at=doc.get("published_at"),
                    current_version=doc.get("current_version", ""),
                ))
            except Exception as exc:
                logger.debug("Ignorando estratégia malformatada: %s", exc)
        return results

    # ── Assinatura ─────────────────────────────────────────────────────────────

    async def subscribe(
        self,
        user_id: str,
        strategy_id: str,
        req: SubscribeRequest,
    ) -> StrategySubscription:
        """
        Registra assinatura de estratégia.
        Para estratégias pagas, req.payment_ref deve conter o ID de pagamento.
        """
        strategy_doc = await self._strategies.find_one({"strategy_id": strategy_id})
        if not strategy_doc or not strategy_doc.get("is_published"):
            raise ValueError("Estratégia não disponível no marketplace")

        # Verifica assinatura ativa existente (idempotência)
        existing = await self._subscriptions.find_one(
            {"user_id": user_id, "strategy_id": strategy_id, "is_active": True}
        )
        if existing:
            existing.pop("_id", None)
            return StrategySubscription(**existing)

        pricing = StrategyPricing(**strategy_doc.get("pricing", {}))

        # Estratégias pagas exigem referência de pagamento
        if pricing.type != PricingType.free and not req.payment_ref:
            raise ValueError(
                f"Estratégia requer pagamento ({pricing.type.value}). "
                "Forneça payment_ref válido."
            )

        sub = StrategySubscription(
            subscription_id=str(uuid.uuid4()),
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_version=strategy_doc.get("current_version", ""),
            pricing_type=pricing.type,
            amount_usd=pricing.amount_usd,
            payment_ref=req.payment_ref,
            expires_at=(
                datetime.now(timezone.utc) + timedelta(days=31)
                if pricing.type == PricingType.monthly
                else None
            ),
        )

        await self._subscriptions.insert_one(sub.model_dump())
        # Incrementa contador de assinantes
        await self._strategies.update_one(
            {"strategy_id": strategy_id},
            {"$inc": {"total_subscribers": 1}},
        )

        logger.info(
            "Assinatura criada user=%s strategy=%s sub=%s",
            user_id, strategy_id, sub.subscription_id,
        )
        return sub

    # ── Cancelamento / Teardown ────────────────────────────────────────────────

    async def unsubscribe(
        self,
        user_id: str,
        strategy_id: str,
    ) -> Dict[str, Any]:
        """
        Cancela assinatura e derruba todas as instâncias de bot em < 5 min.
        Retorna sumário de instâncias encerradas.
        """
        now = datetime.now(timezone.utc)

        # Cancela assinatura
        result = await self._subscriptions.update_one(
            {"user_id": user_id, "strategy_id": strategy_id, "is_active": True},
            {"$set": {"is_active": False, "canceled_at": now}},
        )
        if result.matched_count == 0:
            raise ValueError("Assinatura ativa não encontrada")

        # Derruba instâncias (teardown)
        instances_result = await self._instances.update_many(
            {"user_id": user_id, "strategy_id": strategy_id, "is_active": True},
            {
                "$set": {
                    "is_active": False,
                    "stopped_at": now,
                    "stop_reason": "canceled",
                }
            },
        )

        # Decrementa contador
        await self._strategies.update_one(
            {"strategy_id": strategy_id},
            {"$inc": {"total_subscribers": -1}},
        )

        logger.info(
            "Teardown user=%s strategy=%s instances_stopped=%d",
            user_id, strategy_id, instances_result.modified_count,
        )
        return {
            "unsubscribed": True,
            "instances_stopped": instances_result.modified_count,
            "stopped_at": now.isoformat(),
        }

    # ── Revenue share ──────────────────────────────────────────────────────────

    async def process_revenue_share(
        self,
        subscription_id: str,
        strategy_id: str,
        amount_usd: float,
    ) -> Dict[str, Any]:
        """
        Distribui receita de assinatura: 70% criador / 30% plataforma.
        Idempotente — ignora se já processado para este subscription_id.
        Deve ser chamado pelo webhook de confirmação de pagamento.
        """
        # Idempotência
        existing = await self._revenue_events.find_one(
            {"subscription_id": subscription_id, "status": "processed"}
        )
        if existing:
            logger.info("Revenue share já processado para %s", subscription_id)
            return {"skipped": True, "reason": "already_processed"}

        strategy_doc = await self._strategies.find_one({"strategy_id": strategy_id})
        if not strategy_doc:
            raise ValueError(f"Estratégia {strategy_id} não encontrada")

        creator_id = strategy_doc["creator_id"]
        creator_amount = round(amount_usd * self.CREATOR_SHARE, 6)
        platform_amount = round(amount_usd * self.PLATFORM_TAKE_RATE, 6)
        now = datetime.now(timezone.utc)

        # Credita saldo do criador na wallet de estratégias
        await self._creator_wallets.update_one(
            {"user_id": creator_id},
            {
                "$inc": {"balance_usd": creator_amount, "total_earned_usd": creator_amount},
                "$set": {"updated_at": now},
                "$setOnInsert": {"user_id": creator_id, "created_at": now},
            },
            upsert=True,
        )

        # Registra evento de revenue
        event = {
            "event_id": str(uuid.uuid4()),
            "subscription_id": subscription_id,
            "strategy_id": strategy_id,
            "creator_id": creator_id,
            "total_amount_usd": amount_usd,
            "creator_amount_usd": creator_amount,
            "platform_amount_usd": platform_amount,
            "processed_at": now,
            "status": "processed",
        }
        await self._revenue_events.insert_one(event)

        # Atualiza total de receita da estratégia
        await self._strategies.update_one(
            {"strategy_id": strategy_id},
            {"$inc": {"total_revenue_usd": creator_amount}},
        )

        logger.info(
            "Revenue share processado strategy=%s creator=%s amount_usd=%.2f creator_usd=%.2f",
            strategy_id, creator_id, amount_usd, creator_amount,
        )
        return {
            "processed": True,
            "creator_id": creator_id,
            "creator_amount_usd": creator_amount,
            "platform_amount_usd": platform_amount,
        }

    # ── Dashboard do criador ───────────────────────────────────────────────────

    async def creator_dashboard(self, creator_id: str) -> Dict[str, Any]:
        """Estatísticas agregadas para o criador."""
        strategies = []
        async for doc in self._strategies.find({"creator_id": creator_id}, {"versions": 0}):
            doc.pop("_id", None)
            strategies.append(doc)

        wallet_doc = await self._creator_wallets.find_one({"user_id": creator_id})
        wallet = {"balance_usd": 0.0, "total_earned_usd": 0.0}
        if wallet_doc:
            wallet_doc.pop("_id", None)
            wallet = wallet_doc

        total_subscribers = sum(s.get("total_subscribers", 0) for s in strategies)
        published_count = sum(1 for s in strategies if s.get("is_published"))

        return {
            "creator_id": creator_id,
            "published_strategies": published_count,
            "total_strategies": len(strategies),
            "total_subscribers": total_subscribers,
            "wallet": wallet,
            "strategies": strategies,
        }

    # ── Instâncias de bot ──────────────────────────────────────────────────────

    async def create_bot_instance(
        self,
        user_id: str,
        strategy_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        bot_id: Optional[str] = None,
    ) -> StrategyBotInstance:
        """Cria instância de bot vinculada a uma estratégia assinada."""
        # Verifica assinatura ativa
        sub_doc = await self._subscriptions.find_one(
            {"user_id": user_id, "strategy_id": strategy_id, "is_active": True}
        )
        if not sub_doc:
            raise ValueError("Assinatura ativa necessária para criar instância de bot")

        strategy_doc = await self._strategies.find_one({"strategy_id": strategy_id})
        if not strategy_doc:
            raise ValueError("Estratégia não encontrada")

        instance = StrategyBotInstance(
            instance_id=str(uuid.uuid4()),
            bot_id=bot_id,
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_version=strategy_doc.get("current_version", ""),
            subscription_id=sub_doc.get("subscription_id"),
            parameters=parameters or {},
            is_active=True,
            started_at=datetime.now(timezone.utc),
        )
        await self._instances.insert_one(instance.model_dump())
        logger.info(
            "BotInstance criado instance=%s user=%s strategy=%s",
            instance.instance_id, user_id, strategy_id,
        )
        return instance


# ──────────────────────────────────────────────────────────────────────────────
# Singleton global
# ──────────────────────────────────────────────────────────────────────────────

_marketplace_service: Optional[MarketplaceService] = None


def init_marketplace_service(
    db: AsyncIOMotorDatabase,
    encryption_key: Optional[str] = None,
    platform_take_rate: float = _DEFAULT_PLATFORM_TAKE_RATE,
) -> MarketplaceService:
    global _marketplace_service
    svc = MarketplaceService(db=db, encryption_key=encryption_key)
    svc.PLATFORM_TAKE_RATE = platform_take_rate
    svc.CREATOR_SHARE = 1.0 - platform_take_rate
    _marketplace_service = svc
    return svc


def get_marketplace_service() -> MarketplaceService:
    if _marketplace_service is None:
        raise RuntimeError(
            "MarketplaceService não inicializado. "
            "Chame init_marketplace_service() no startup."
        )
    return _marketplace_service
