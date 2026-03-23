"""
Marketplace Robots Router — Gamified Robot Marketplace (PEND-14)

Endpoints:
    POST /marketplace/robots/{id}/purchase    — debitar pontos, vincular robô
    GET  /marketplace/robots/{id}/performance — histórico de performance
    POST /marketplace/robots/{id}/review      — avaliar robô comprado
    GET  /marketplace/robots/{id}/reviews     — listar avaliações do robô
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user as _get_current_user
from app.core.database import get_db
from app.gamification.service import (
    ELITE_ROBOTS,
    ROBOT_UNLOCK_COST,
    VALID_ROBOT_IDS,
    GameProfileService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace/robots", tags=["🛒 Robot Marketplace"])


# ─── Auth helper ─────────────────────────────────────────────────────────────

async def _get_user(user: dict = Depends(_get_current_user)):
    from types import SimpleNamespace
    return SimpleNamespace(**user) if isinstance(user, dict) else user


# ─── Pydantic models ─────────────────────────────────────────────────────────

class PurchaseResponse(BaseModel):
    success: bool
    message: str
    robot_id: str
    points_spent: Optional[int] = None
    points_remaining: Optional[int] = None
    performance_preview: Optional[Dict[str, Any]] = None


class PerformanceDataPoint(BaseModel):
    date: str
    profit: float
    win_rate: float
    trades: int


class PerformanceResponse(BaseModel):
    robot_id: str
    robot_name: str
    strategy: str
    total_profit_30d: float
    avg_daily_profit: float
    win_rate: float
    total_trades: int
    max_drawdown: float
    sharpe_ratio: float
    data_points: List[PerformanceDataPoint]
    last_updated: str


class ReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Avaliação de 1 a 5 estrelas")
    comment: str = Field(
        "",
        max_length=500,
        description="Comentário opcional (máx 500 caracteres)",
    )


class ReviewItem(BaseModel):
    id: str
    user_masked: str
    rating: int
    comment: str
    created_at: str


class ReviewResponse(BaseModel):
    success: bool
    message: str
    robot_id: str
    rating: int
    comment: str
    created_at: str


class ReviewsListResponse(BaseModel):
    robot_id: str
    total: int
    avg_rating: float
    reviews: List[ReviewItem]


# ─── Static metadata for 20 robots (mirrors frontend mock) ───────────────────

_ROBOT_META: Dict[str, Dict[str, Any]] = {
    "bot_001": {"name": "Volatility Dragon", "strategy": "grid", "creator": "Li Wei"},
    "bot_002": {"name": "Legend Slayer", "strategy": "combined", "creator": "Dmitri Volkoff"},
    "bot_003": {"name": "Grid Precision", "strategy": "grid", "creator": "Kenji Tanaka"},
    "bot_004": {"name": "Hybrid Flame", "strategy": "combined", "creator": "Aviv Cohen"},
    "bot_005": {"name": "RSI Hunter Elite", "strategy": "rsi", "creator": "Marco Stein"},
    "bot_006": {"name": "Grid Master Alpha", "strategy": "grid", "creator": "Pedro Silva"},
    "bot_007": {"name": "MACD Trendsetter", "strategy": "macd", "creator": "Wei Zhang"},
    "bot_008": {"name": "DCA Accumulator", "strategy": "dca", "creator": "Yuki Yamamoto"},
    "bot_009": {"name": "Scalper Ghost", "strategy": "rsi", "creator": "Natasha Petrov"},
    "bot_010": {"name": "Grid Harvester Pro", "strategy": "grid", "creator": "David Goldstein"},
    "bot_011": {"name": "Momentum Master", "strategy": "grid", "creator": "Carlos Ferreira"},
    "bot_012": {"name": "Volatility Surfer", "strategy": "combined", "creator": "Sofia Zurich"},
    "bot_013": {"name": "Bollinger Breaker", "strategy": "macd", "creator": "Igor Sokolov"},
    "bot_014": {"name": "Fisher Predictor", "strategy": "rsi", "creator": "Hiroshi Sato"},
    "bot_015": {"name": "Arbitrage Prophet", "strategy": "dca", "creator": "Abraham Levi"},
    "bot_016": {"name": "Quantum Analyzer", "strategy": "combined", "creator": "Rafael Santos"},
    "bot_017": {"name": "Neural Network Trader", "strategy": "grid", "creator": "Ming Li"},
    "bot_018": {"name": "Fib Retracement Bot", "strategy": "grid", "creator": "Klaus Mueller"},
    "bot_019": {"name": "EMA Crossover Pro", "strategy": "macd", "creator": "Anastasia Ivanova"},
    "bot_020": {"name": "Stochastic Master", "strategy": "rsi", "creator": "Akira Nakamura"},
}

# ─── Performance generation helper ───────────────────────────────────────────

def _generate_performance(robot_id: str) -> Dict[str, Any]:
    """
    Generate deterministic performance data based on robot_id seed.
    Production: replace with real trade data from MongoDB.
    """
    seed = int(hashlib.md5(robot_id.encode()).hexdigest()[:8], 16)

    # Base metrics seeded from robot_id
    base_profit = 200 + (seed % 3000)
    base_win_rate = 55 + (seed % 20)
    base_trades = 100 + (seed % 200)
    max_dd = 5 + (seed % 15)
    sharpe = round(0.8 + (seed % 20) / 10, 2)

    today = datetime.now(timezone.utc)
    data_points: List[Dict] = []
    cumulative = 0.0
    for i in range(30):
        day_seed = int(hashlib.md5(f"{robot_id}:{i}".encode()).hexdigest()[:8], 16)
        daily_profit = round(((day_seed % 200) - 50) * (base_profit / 2000), 2)
        cumulative += daily_profit
        date_str = (today.replace(day=1) if i == 0
                    else datetime.fromtimestamp(
                        today.timestamp() - (30 - i) * 86400, tz=timezone.utc
                    )).strftime("%Y-%m-%d")
        data_points.append({
            "date": date_str,
            "profit": round(daily_profit, 2),
            "win_rate": round(base_win_rate + (day_seed % 10) - 5, 1),
            "trades": 3 + (day_seed % 12),
        })

    return {
        "total_profit_30d": round(base_profit, 2),
        "avg_daily_profit": round(base_profit / 30, 2),
        "win_rate": float(base_win_rate),
        "total_trades": base_trades,
        "max_drawdown": float(max_dd),
        "sharpe_ratio": sharpe,
        "data_points": data_points,
    }


# ─── POST /marketplace/robots/{id}/purchase ──────────────────────────────────

@router.post(
    "/{robot_id}/purchase",
    response_model=PurchaseResponse,
    summary="Comprar/desbloquear robô com TradePoints",
)
async def purchase_robot(
    robot_id: str,
    current_user=Depends(_get_user),
):
    """
    Debita TradePoints e vincula o robô à conta do usuário.

    Equivalente a `POST /api/gamification/robots/{id}/unlock` mas:
    - Prefixo `/marketplace/` para consistência com a UI
    - Retorna `performance_preview` para exibir dados de compra
    - Registra a compra na coleção `robot_purchases` para auditoria

    **Erros possíveis:**
    - 400: Robô inválido ou já desbloqueado
    - 403: Saldo de pontos insuficiente / plano incompatível
    - 404: Perfil de gamificação não encontrado
    """
    if robot_id not in VALID_ROBOT_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Robô '{robot_id}' inválido.",
        )

    user_id = str(current_user.id)

    # Delegate to existing unlock logic (atomic, same business rules)
    result = await GameProfileService.unlock_robot_logic(user_id=user_id, robot_id=robot_id)

    if result["success"]:
        points_spent = ROBOT_UNLOCK_COST.get(
            "elite" if robot_id in ELITE_ROBOTS else "common", 500
        )

        # Record purchase for audit (best-effort; non-fatal)
        try:
            db = get_db()
            await db["robot_purchases"].insert_one({
                "user_id": user_id,
                "robot_id": robot_id,
                "points_spent": points_spent,
                "purchased_at": datetime.now(timezone.utc),
            })
        except Exception as exc:
            logger.warning("[Marketplace] Falha ao registrar compra: %s", exc)

        perf = _generate_performance(robot_id)
        meta = _ROBOT_META.get(robot_id, {})
        logger.info("[Marketplace] Compra: robot=%s user=%s pontos=%s", robot_id, user_id, points_spent)
        return PurchaseResponse(
            success=True,
            message=f"✅ Robô {meta.get('name', robot_id)} desbloqueado com sucesso!",
            robot_id=robot_id,
            points_spent=points_spent,
            points_remaining=result.get("new_balance", 0),
            performance_preview={
                "win_rate": perf["win_rate"],
                "total_profit_30d": perf["total_profit_30d"],
                "sharpe_ratio": perf["sharpe_ratio"],
            },
        )

    # Map unlock errors to HTTP codes
    error_code = result.get("error", "unknown")
    error_map = {
        "already_unlocked": (400, f"Robô '{robot_id}' já foi desbloqueado!"),
        "insufficient_balance": (403, result.get("message", "Pontos insuficientes.")),
        "license_required": (403, result.get("message", "Upgrade de plano necessário.")),
        "plan_limit_reached": (403, result.get("message", "Limite de robôs do plano atingido.")),
        "profile_not_found": (404, "Perfil de gamificação não encontrado."),
    }
    http_status, detail = error_map.get(error_code, (500, "Erro ao processar compra."))
    raise HTTPException(status_code=http_status, detail=detail)


# ─── GET /marketplace/robots/{id}/performance ────────────────────────────────

@router.get(
    "/{robot_id}/performance",
    response_model=PerformanceResponse,
    summary="Histórico de performance do robô",
)
async def get_performance(robot_id: str, current_user=Depends(_get_user)):
    """
    Retorna histórico de performance dos últimos 30 dias.

    Os dados são gerados deterministicamente a partir do `robot_id` (sem dados reais
    de trades ainda). Em produção, este endpoint deverá consultar a coleção
    `robot_rankings` e `bot_trades` para dados reais.
    """
    if robot_id not in VALID_ROBOT_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Robô '{robot_id}' inválido.",
        )

    meta = _ROBOT_META.get(robot_id, {})
    perf = _generate_performance(robot_id)

    # Try to get live data from robot_rankings collection
    try:
        db = get_db()
        doc = await db["robot_rankings"].find_one(
            {"robot_id": robot_id},
            sort=[("last_updated", -1)],
        )
        if doc:
            perf["total_profit_30d"] = doc.get("profit_15d", perf["total_profit_30d"]) * 2
            perf["win_rate"] = doc.get("win_rate", perf["win_rate"])
            perf["total_trades"] = doc.get("total_trades", perf["total_trades"])
    except Exception as exc:
        logger.debug("[Marketplace] performance: DB lookup failed: %s", exc)

    return PerformanceResponse(
        robot_id=robot_id,
        robot_name=meta.get("name", f"Robot {robot_id}"),
        strategy=meta.get("strategy", "unknown"),
        total_profit_30d=perf["total_profit_30d"],
        avg_daily_profit=perf["avg_daily_profit"],
        win_rate=perf["win_rate"],
        total_trades=perf["total_trades"],
        max_drawdown=perf["max_drawdown"],
        sharpe_ratio=perf["sharpe_ratio"],
        data_points=[PerformanceDataPoint(**dp) for dp in perf["data_points"]],
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


# ─── POST /marketplace/robots/{id}/review ────────────────────────────────────

@router.post(
    "/{robot_id}/review",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Avaliar robô (requer desbloqueio prévio)",
)
async def post_review(
    robot_id: str,
    req: ReviewRequest,
    current_user=Depends(_get_user),
):
    """
    Submete uma avaliação com nota (1-5 estrelas) e comentário opcional.

    **Requisito:** o usuário precisa ter desbloqueado o robô antes de avaliar.

    Cada usuário pode submeter **uma** avaliação por robô; submissões posteriores
    atualizam a avaliação existente (upsert).
    """
    if robot_id not in VALID_ROBOT_IDS:
        raise HTTPException(status_code=400, detail=f"Robô '{robot_id}' inválido.")

    user_id = str(current_user.id)

    # Verify the user has purchased the robot
    profile = await GameProfileService.get_or_create_profile(user_id)
    if robot_id not in (profile.unlocked_robots or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você precisa desbloquear o robô antes de avaliá-lo.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    review_doc = {
        "user_id": user_id,
        "robot_id": robot_id,
        "rating": req.rating,
        "comment": req.comment,
        "updated_at": datetime.now(timezone.utc),
    }

    try:
        db = get_db()
        await db["robot_reviews"].update_one(
            {"user_id": user_id, "robot_id": robot_id},
            {"$set": review_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    except Exception as exc:
        logger.error("[Marketplace] Falha ao salvar review: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao salvar avaliação.")

    logger.info("[Marketplace] Review: robot=%s user=%s rating=%d", robot_id, user_id, req.rating)
    return ReviewResponse(
        success=True,
        message=f"✅ Avaliação de {req.rating}★ registrada!",
        robot_id=robot_id,
        rating=req.rating,
        comment=req.comment,
        created_at=now_iso,
    )


# ─── GET /marketplace/robots/{id}/reviews ────────────────────────────────────

@router.get(
    "/{robot_id}/reviews",
    response_model=ReviewsListResponse,
    summary="Listar avaliações do robô",
)
async def list_reviews(robot_id: str, current_user=Depends(_get_user)):
    """
    Retorna as avaliações públicas do robô (e-mails mascarados para LGPD).
    """
    if robot_id not in VALID_ROBOT_IDS:
        raise HTTPException(status_code=400, detail=f"Robô '{robot_id}' inválido.")

    try:
        db = get_db()
        cursor = db["robot_reviews"].find({"robot_id": robot_id}).sort("updated_at", -1).limit(50)
        docs = await cursor.to_list(length=50)
    except Exception as exc:
        logger.error("[Marketplace] Falha ao listar reviews: %s", exc)
        docs = []

    reviews: List[ReviewItem] = []
    total_rating = 0
    for doc in docs:
        uid = doc.get("user_id", "")
        # Mask user identity for LGPD compliance
        masked = f"u{'*' * 4}{uid[-4:]}" if len(uid) >= 4 else "u****"
        reviews.append(
            ReviewItem(
                id=str(doc.get("_id", "")),
                user_masked=masked,
                rating=doc.get("rating", 0),
                comment=doc.get("comment", ""),
                created_at=(
                    doc["created_at"].isoformat()
                    if isinstance(doc.get("created_at"), datetime)
                    else str(doc.get("created_at", ""))
                ),
            )
        )
        total_rating += doc.get("rating", 0)

    avg = round(total_rating / len(docs), 1) if docs else 0.0
    return ReviewsListResponse(
        robot_id=robot_id,
        total=len(reviews),
        avg_rating=avg,
        reviews=reviews,
    )
