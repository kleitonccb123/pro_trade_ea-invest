"""
Router FastAPI — PricePro EA

Endpoints:
    POST   /api/trading/pricepro-ea/start       Inicia EA para o usuário autenticado
    POST   /api/trading/pricepro-ea/stop        Para EA
    GET    /api/trading/pricepro-ea/status      Status + métricas em tempo real
    PATCH  /api/trading/pricepro-ea/config      Atualiza config sem reiniciar
    POST   /api/trading/pricepro-ea/emergency   Para EA e fecha todas as posições

Cada endpoint resolve os deps via FastAPI Depends:
    - current_user: usuário autenticado (JWT)
    - engine:       TradingEngine do usuário
    - ws_manager:   KuCoinWebSocketManager compartilhado
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .config import EAConfig
from .ea_runner import EAStatus, PriceProEARunner, ea_registry

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/trading/pricepro-ea",
    tags=["PricePro EA"],
)


# ---------------------------------------------------------------------------
# Modelos Pydantic de Request/Response
# ---------------------------------------------------------------------------

class StartEARequest(BaseModel):
    symbol: str = Field(..., example="BTC-USDT", description="Par de negociação ex: BTC-USDT")
    timeframe: str = Field("1min", description="Timeframe do candle: 1min, 5min, 15min, 1hour...")

    # Gestão de dinheiro
    fixed_lot: Optional[Decimal] = Field(None, ge=0, description="Lote fixo (0 = dinâmico)")
    dynamic_lot_pct: float = Field(1.0, ge=0, le=100)
    daily_target_usd: float = Field(10.0, ge=0)
    daily_loss_limit_usd: float = Field(20.0, ge=0)
    emergency_drawdown_pct: float = Field(20.0, ge=0, le=100)

    # Indicadores
    ema_period: int = Field(21, ge=2)
    ma_type: str = Field("ema", description="ema | sma | wma")
    rsi_period: int = Field(14, ge=2)
    rsi_oversold: float = Field(30.0)
    rsi_overbought: float = Field(70.0)
    rsi_with_trend: bool = False

    # Filtros
    use_ema: bool = True
    use_rsi: bool = True
    use_candle_strength: bool = True
    candle_body_min_pct: float = Field(50.0, ge=0, le=100)
    use_volume: bool = True
    volume_min_ratio: float = Field(1.2, ge=0)
    use_range_adaptive: bool = True
    range_multiplier: float = Field(1.0, ge=0)

    # TP/SL
    tp_usd: float = Field(5.0, ge=0)
    sl_usd: float = Field(3.0, ge=0)
    breakeven_activate_points: float = Field(30.0, ge=0)
    use_trailing_candle: bool = True
    min_move_points: float = Field(5.0, ge=0)

    # Grid
    use_grid: bool = True
    grid_delay_s: float = Field(1.0, ge=0)
    grid_distances: List[float] = Field(default_factory=lambda: [50.0, 100.0, 200.0])
    grid_volumes: List[float] = Field(default_factory=lambda: [0.01, 0.02, 0.04])

    # Scalper
    use_scalper: bool = True
    scalper_interval_s: int = Field(60, ge=0)

    # Misc
    price_tick: Decimal = Field(Decimal("0.01"), gt=0)
    indicator_warmup_bars: int = Field(100, ge=20)
    debug: bool = False

    def to_ea_config(self, user_id: str) -> EAConfig:
        from .config import GridLevel

        grid_levels = []
        for dist, vol in zip(self.grid_distances, self.grid_volumes):
            grid_levels.append(GridLevel(distance_points=dist, volume=Decimal(str(vol))))

        return EAConfig(
            user_id=user_id,
            symbol=self.symbol,
            timeframe=self.timeframe,
            active=True,
            fixed_lot=self.fixed_lot or Decimal("0"),
            dynamic_lot_pct=self.dynamic_lot_pct,
            daily_target_usd=self.daily_target_usd,
            daily_loss_limit_usd=self.daily_loss_limit_usd,
            emergency_drawdown_pct=self.emergency_drawdown_pct,
            ema_period=self.ema_period,
            ma_type=self.ma_type,
            rsi_period=self.rsi_period,
            rsi_oversold=self.rsi_oversold,
            rsi_overbought=self.rsi_overbought,
            rsi_with_trend=self.rsi_with_trend,
            use_ema=self.use_ema,
            use_rsi=self.use_rsi,
            use_candle_strength=self.use_candle_strength,
            candle_body_min_pct=self.candle_body_min_pct,
            use_volume=self.use_volume,
            volume_min_ratio=self.volume_min_ratio,
            use_range_adaptive=self.use_range_adaptive,
            range_multiplier=self.range_multiplier,
            tp_usd=self.tp_usd,
            sl_usd=self.sl_usd,
            breakeven_activate_points=self.breakeven_activate_points,
            use_trailing_candle=self.use_trailing_candle,
            min_move_points=self.min_move_points,
            use_grid=self.use_grid,
            grid_delay_s=self.grid_delay_s,
            grid_levels=grid_levels,
            use_scalper=self.use_scalper,
            scalper_interval_s=self.scalper_interval_s,
            price_tick=self.price_tick,
            indicator_warmup_bars=self.indicator_warmup_bars,
            debug=self.debug,
        )


class UpdateConfigRequest(BaseModel):
    symbol: str = Field(..., description="Símbolo para identificar o runner ativo")
    daily_target_usd: Optional[float] = None
    daily_loss_limit_usd: Optional[float] = None
    tp_usd: Optional[float] = None
    sl_usd: Optional[float] = None
    debug: Optional[bool] = None
    active: Optional[bool] = None


class EAStatusResponse(BaseModel):
    user_id: str
    symbol: str
    running: bool
    can_trade: bool
    daily_summary: Dict[str, Any]
    signal_summary: Dict[str, Any]
    errors: List[str]
    open_positions: int


# ---------------------------------------------------------------------------
# Helpers de dependência
# ---------------------------------------------------------------------------

def _get_engine_and_ws():
    """
    Dependência que resolve TradingEngine + KuCoinWebSocketManager
    a partir do app state ou de um service locator.

    Implementação real deve usar o padrão do projeto (ex: app.state.engine).
    """
    from fastapi import Request
    # Retorna uma factory — será sobrescrita no teste ou via app state
    raise NotImplementedError(
        "Registre _get_engine_and_ws no app state antes de usar o router"
    )


async def _require_user_id(x_user_id: str = "anonymous") -> str:
    """
    Placeholder de autenticação. Em produção substituir por Depends(get_current_user).
    Lê header X-User-Id para compatibilidade com o sistema de auth existente.
    """
    return x_user_id


# ---------------------------------------------------------------------------
# Injeção de dependências (configurável externamente)
# ---------------------------------------------------------------------------

_engine_factory = None
_ws_factory = None


def configure_dependencies(engine_factory, ws_factory) -> None:
    """
    Chamado no startup da aplicação para registrar as factories.

    Exemplo em main.py:
        from app.strategies.pricepro_ea.router import configure_dependencies
        configure_dependencies(
            lambda uid: engine_registry.get(uid),
            lambda: shared_ws_manager,
        )
    """
    global _engine_factory, _ws_factory
    _engine_factory = engine_factory
    _ws_factory = ws_factory


def _engine(user_id: str):
    if _engine_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TradingEngine não configurado",
        )
    eng = _engine_factory(user_id)
    if eng is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma conta KuCoin configurada para este usuário",
        )
    return eng


def _ws():
    if _ws_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocketManager não configurado",
        )
    return _ws_factory()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_ea(
    req: StartEARequest,
    user_id: str = Depends(_require_user_id),
):
    """
    Inicia o PricePro EA para o usuário autenticado.

    O EA começa a consumir candles via WebSocket e operar automaticamente.
    Retorna erro 409 se já estiver em execução para o mesmo símbolo.
    """
    existing = ea_registry.get(user_id, req.symbol)
    if existing and existing._running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"EA já em execução para {req.symbol}",
        )

    config = req.to_ea_config(user_id)
    engine = _engine(user_id)
    ws = _ws()

    try:
        runner = await ea_registry.start(config, engine, ws)
        logger.info("[Router] EA iniciado — user=%s symbol=%s", user_id, req.symbol)
        return {
            "status": "started",
            "user_id": user_id,
            "symbol": req.symbol,
            "timeframe": req.timeframe,
        }
    except Exception as exc:
        logger.error("[Router] Erro ao iniciar EA: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.post("/stop")
async def stop_ea(
    symbol: str,
    user_id: str = Depends(_require_user_id),
):
    """
    Para o EA sem fechar posições abertas.
    As posições existentes permanecem até serem fechadas manualmente.
    """
    stopped = await ea_registry.stop(user_id, symbol)
    if not stopped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum EA em execução para {symbol}",
        )
    return {"status": "stopped", "symbol": symbol}


@router.get("/status", response_model=EAStatusResponse)
async def get_status(
    symbol: str,
    user_id: str = Depends(_require_user_id),
):
    """
    Retorna status completo do EA: indicadores, P&L diário, posições, erros.
    """
    runner = ea_registry.get(user_id, symbol)
    if runner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum EA em execução para {symbol}",
        )
    s = runner.get_status()
    return EAStatusResponse(
        user_id=s.user_id,
        symbol=s.symbol,
        running=s.running,
        can_trade=s.can_trade,
        daily_summary=s.daily_summary,
        signal_summary=s.signal_summary,
        errors=s.errors,
        open_positions=s.open_positions,
    )


@router.get("/list")
async def list_active(user_id: str = Depends(_require_user_id)):
    """Lista todos os EAs ativos do usuário."""
    runners = ea_registry.list_user(user_id)
    return {
        "active": [
            {"symbol": r.cfg.symbol, "timeframe": r.cfg.timeframe, "running": r._running}
            for r in runners
        ]
    }


@router.patch("/config")
async def update_config(
    req: UpdateConfigRequest,
    user_id: str = Depends(_require_user_id),
):
    """
    Atualiza parâmetros do EA em tempo real sem reiniciar.
    Campos omitidos não são alterados.
    """
    runner = ea_registry.get(user_id, req.symbol)
    if runner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum EA em execução para {req.symbol}",
        )

    cfg = runner.cfg
    updated: Dict[str, Any] = {}

    if req.daily_target_usd is not None:
        delta = req.daily_target_usd - runner._daily._state.runtime_daily_target
        runner._daily.adjust_target(delta)
        updated["daily_target_usd"] = req.daily_target_usd

    if req.daily_loss_limit_usd is not None:
        delta = req.daily_loss_limit_usd - runner._daily._state.runtime_loss_limit
        runner._daily.adjust_limit(delta)
        updated["daily_loss_limit_usd"] = req.daily_loss_limit_usd

    if req.tp_usd is not None:
        cfg.tp_usd = req.tp_usd
        updated["tp_usd"] = req.tp_usd

    if req.sl_usd is not None:
        cfg.sl_usd = req.sl_usd
        updated["sl_usd"] = req.sl_usd

    if req.debug is not None:
        cfg.debug = req.debug
        updated["debug"] = req.debug

    if req.active is not None and not req.active:
        cfg.active = False
        updated["active"] = False

    return {"updated": updated, "symbol": req.symbol}


@router.post("/reactivate")
async def reactivate_ea(
    symbol: str,
    new_target: float,
    new_limit: float,
    user_id: str = Depends(_require_user_id),
):
    """
    Reativa o EA após bloqueio por meta/limite diário.
    Exige que os valores sejam diferentes dos que causaram o bloqueio.
    Equivale ao BTN_REACTIVATE do painel MT5.
    """
    runner = ea_registry.get(user_id, symbol)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"EA não encontrado para {symbol}")

    ok = runner._daily.try_reactivate(new_target, new_limit)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Reativação negada — altere a MetaDiaria ou LimitePerda antes de reativar. "
                "Os novos valores devem ser diferentes dos que causaram o bloqueio."
            ),
        )
    cfg = runner.cfg
    cfg.active = True
    return {"status": "reactivated", "symbol": symbol, "new_target": new_target, "new_limit": new_limit}


@router.post("/emergency")
async def emergency_stop(
    symbol: str,
    user_id: str = Depends(_require_user_id),
):
    """
    Fecha todas as posições abertas imediatamente e para o EA.
    Uso: situação de risco extremo ou teste de kill-switch.
    """
    stopped = await ea_registry.emergency_stop(user_id, symbol)
    if not stopped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum EA em execução para {symbol}",
        )
    logger.warning("[Router] EMERGÊNCIA executada — user=%s symbol=%s", user_id, symbol)
    return {"status": "emergency_stop_executed", "symbol": symbol}
