"""
DOC-08 — Marketplace de Estratégias
Router FastAPI: endpoints do marketplace, backtesting e dashboard de criador.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.strategies.backtest import BacktestConfig, BacktestEngine, BacktestResult
from app.strategies.marketplace import (
    MarketplaceListing,
    MarketplaceService,
    PublishRequest,
    SubscribeRequest,
    get_marketplace_service,
)
from app.strategies.model import StrategyBotInstance, UserStrategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _svc() -> MarketplaceService:
    """FastAPI dependency — retorna singleton do MarketplaceService."""
    return get_marketplace_service()


def _backtest_engine(svc: MarketplaceService = Depends(_svc)) -> BacktestEngine:
    return BacktestEngine(db=svc.db)


# ──────────────────────────────────────────────────────────────────────────────
# Request bodies
# ──────────────────────────────────────────────────────────────────────────────

class CreateStrategyRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "custom"
    source_code: str
    exchanges: List[str] = ["kucoin"]
    asset_types: List[str] = ["spot"]
    parameters: Optional[List[Dict[str, Any]]] = None


class SubmitBacktestRequest(BaseModel):
    version_id: Optional[str] = None   # Opcional — usa versão mais recente se omitido
    symbol: str = "BTC-USDT"
    start_ts: int    # Unix timestamp segundos
    end_ts: int
    initial_capital_usd: float = 1000.0
    parameters: Dict[str, Any] = {}
    maker_fee_pct: float = 0.1
    taker_fee_pct: float = 0.1


class CreateBotInstanceRequest(BaseModel):
    parameters: Dict[str, Any] = {}
    bot_id: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Marketplace público
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[MarketplaceListing])
async def list_marketplace(
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    sort_by: str = Query("metrics.sharpe_ratio", description="Campo de ordenação"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: MarketplaceService = Depends(_svc),
):
    """
    Lista estratégias publicadas no marketplace.
    Acesso público — não requer autenticação.
    O código-fonte NUNCA é incluído na resposta.
    """
    try:
        return await svc.list_marketplace(
            category=category,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        logger.error("Erro ao listar marketplace: %s", exc)
        raise HTTPException(status_code=500, detail="Erro interno ao listar marketplace")


# ──────────────────────────────────────────────────────────────────────────────
# Criação de estratégia (criador)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/strategies", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: CreateStrategyRequest,
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
):
    """
    Cria nova estratégia como rascunho.
    O código-fonte é cifrado com AES-256 imediatamente ao receber.
    Requer autenticação.
    """
    try:
        strategy = await svc.create_strategy(
            creator_id=str(current_user["_id"]),
            name=body.name,
            description=body.description,
            category=body.category,
            source_code=body.source_code,
            parameters=body.parameters,
            exchanges=body.exchanges,
            asset_types=body.asset_types,
        )
        return {
            "strategy_id": strategy.strategy_id,
            "name": strategy.name,
            "status": strategy.status.value,
            "created_at": strategy.created_at.isoformat(),
        }
    except Exception as exc:
        logger.error("Erro ao criar estratégia: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Backtesting
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/strategies/{strategy_id}/backtest", response_model=Dict[str, Any])
async def submit_backtest(
    strategy_id: str,
    body: SubmitBacktestRequest,
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
    engine: BacktestEngine = Depends(_backtest_engine),
):
    """
    Submete estratégia para backtesting.
    - Período mínimo: 90 dias
    - Se aprovado, o backtest_result_id pode ser usado para publicar
    Criador é associado ao resultado; outros usuários não podem submeter backtests de estratégias alheias.
    """
    # Verifica autoria (apenas criador pode submeter backtest)
    doc = await svc._strategies.find_one(
        {"strategy_id": strategy_id, "creator_id": str(current_user["_id"])}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Estratégia não encontrada ou sem permissão")

    config = BacktestConfig(
        strategy_id=strategy_id,
        version_id=body.version_id or "",
        symbol=body.symbol,
        start_ts=body.start_ts,
        end_ts=body.end_ts,
        initial_capital_usd=body.initial_capital_usd,
        parameters=body.parameters,
        maker_fee_pct=body.maker_fee_pct,
        taker_fee_pct=body.taker_fee_pct,
    )

    try:
        t0 = time.monotonic()
        result = await engine.run(config)
        elapsed = round(time.monotonic() - t0, 2)
        return {
            "backtest_id": result.backtest_id,
            "strategy_id": result.strategy_id,
            "passed": result.passed,
            "failure_reasons": result.failure_reasons,
            "metrics": result.metrics.model_dump(),
            "total_trades": result.metrics.total_trades,
            "elapsed_seconds": elapsed,
            "completed_at": result.completed_at.isoformat(),
        }
    except Exception as exc:
        logger.error("Erro no backtest strategy=%s: %s", strategy_id, exc)
        raise HTTPException(status_code=500, detail=f"Erro no backtesting: {exc}")


@router.get("/backtest/{backtest_id}", response_model=Dict[str, Any])
async def get_backtest_result(
    backtest_id: str,
    current_user: dict = Depends(get_current_user),
    engine: BacktestEngine = Depends(_backtest_engine),
):
    """Retorna resultado completo de backtesting pelo ID."""
    result = await engine.get_result(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest não encontrado")
    return result.model_dump()


# ──────────────────────────────────────────────────────────────────────────────
# Publicação
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/strategies/{strategy_id}/publish", response_model=Dict[str, Any])
async def publish_strategy(
    strategy_id: str,
    body: PublishRequest,
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
):
    """
    Publica estratégia no marketplace.
    OBRIGATÓRIO: backtest_result_id aprovado (passed=true).
    Estratégias sem backtesting aprovado são REJEITADAS (100% enforcement).
    """
    try:
        strategy = await svc.publish_strategy(
            strategy_id=strategy_id,
            creator_id=str(current_user["_id"]),
            req=body,
        )
        return {
            "strategy_id": strategy.strategy_id,
            "name": strategy.name,
            "is_published": strategy.is_published,
            "current_version": strategy.current_version,
            "published_at": strategy.published_at.isoformat() if strategy.published_at else None,
            "metrics": strategy.metrics.model_dump(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao publicar estratégia %s: %s", strategy_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao publicar estratégia")


# ──────────────────────────────────────────────────────────────────────────────
# Assinatura
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/strategies/{strategy_id}/subscribe", response_model=Dict[str, Any])
async def subscribe_to_strategy(
    strategy_id: str,
    body: SubscribeRequest,
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
):
    """
    Assina estratégia do marketplace.
    Para estratégias pagas, forneça payment_ref do Perfect Pay.
    """
    try:
        sub = await svc.subscribe(
            user_id=str(current_user["_id"]),
            strategy_id=strategy_id,
            req=body,
        )
        return {
            "subscription_id": sub.subscription_id,
            "strategy_id": sub.strategy_id,
            "strategy_version": sub.strategy_version,
            "pricing_type": sub.pricing_type.value,
            "is_active": sub.is_active,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "subscribed_at": sub.subscribed_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao assinar estratégia %s: %s", strategy_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao processar assinatura")


@router.delete("/strategies/{strategy_id}/subscribe", response_model=Dict[str, Any])
async def unsubscribe_from_strategy(
    strategy_id: str,
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
):
    """
    Cancela assinatura e derruba todas as instâncias de bot em < 5 min.
    """
    try:
        return await svc.unsubscribe(
            user_id=str(current_user["_id"]),
            strategy_id=strategy_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao cancelar assinatura %s: %s", strategy_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao cancelar assinatura")


# ──────────────────────────────────────────────────────────────────────────────
# Instâncias de bot
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/strategies/{strategy_id}/instances", response_model=Dict[str, Any])
async def create_bot_instance(
    strategy_id: str,
    body: CreateBotInstanceRequest,
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
):
    """
    Cria instância de bot para executar estratégia assinada.
    Requer assinatura ativa.
    """
    try:
        instance = await svc.create_bot_instance(
            user_id=str(current_user["_id"]),
            strategy_id=strategy_id,
            parameters=body.parameters,
            bot_id=body.bot_id,
        )
        return {
            "instance_id": instance.instance_id,
            "strategy_id": instance.strategy_id,
            "strategy_version": instance.strategy_version,
            "is_active": instance.is_active,
            "created_at": instance.created_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao criar instância de bot: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao criar instância de bot")


@router.get("/strategies/{strategy_id}/instances", response_model=List[Dict[str, Any]])
async def list_bot_instances(
    strategy_id: str,
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
):
    """Lista instâncias de bot ativas do usuário para a estratégia."""
    cursor = svc._instances.find(
        {"user_id": str(current_user["_id"]), "strategy_id": strategy_id}
    )
    results = []
    async for doc in cursor:
        doc.pop("_id", None)
        results.append(doc)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard do criador
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/creator/dashboard", response_model=Dict[str, Any])
async def creator_dashboard(
    current_user: dict = Depends(get_current_user),
    svc: MarketplaceService = Depends(_svc),
):
    """
    Dashboard do criador: lista de estratégias, subscribers, receita acumulada e saldo de wallet.
    """
    try:
        return await svc.creator_dashboard(creator_id=str(current_user["_id"]))
    except Exception as exc:
        logger.error("Erro no dashboard do criador: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao obter dashboard")


# ──────────────────────────────────────────────────────────────────────────────
# Revenue share (webhook interno — não expor publicamente)
# ──────────────────────────────────────────────────────────────────────────────

class RevenueShareRequest(BaseModel):
    subscription_id: str
    strategy_id: str
    amount_usd: float


@router.post("/internal/revenue-share", include_in_schema=False)
async def process_revenue_share(
    body: RevenueShareRequest,
    svc: MarketplaceService = Depends(_svc),
):
    """
    Endpoint interno: processa revenue share após confirmação de pagamento.
    Chamado pelo billing.py no postback do Perfect Pay.
    NÃO exposto na documentação pública.
    """
    try:
        return await svc.process_revenue_share(
            subscription_id=body.subscription_id,
            strategy_id=body.strategy_id,
            amount_usd=body.amount_usd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro no revenue share: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao processar revenue share")
