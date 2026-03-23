"""
PriceProEARunner — Orquestrador principal do EA adaptado do MQL5

Integra todos os módulos:
    SignalGenerator  → gera sinais de entrada na nova barra
    GridManager      → proteções/grid contra o mercado
    PositionTracker  → breakeven + trailing por candle
    ScalperModule    → entradas scalper adicionais
    DailyController  → metas e limites financeiros

Arquitetura:
    KuCoin WebSocket (candle events)
          │
    _on_candle_event()       ← evento de candle recebido
          │
    compute_all()            ← indicadores técnicos
          │
    DailyController.check()  ← meta/perda diária
          │
    SignalGenerator.analyze() ← filtros de entrada
          │
    TradingEngine.place_market_order() ← ordem de mercado
          │
    GridManager.tick()       ← proteções abertas se necessário
    PositionTracker.update() ← breakeven + trailing
    ScalperModule.tick()     ← scalper paralelo

Um runner por user_id (isolamento multi-tenant).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from app.exchanges.kucoin.websocket_manager import (
    CandleEvent,
    KuCoinWebSocketManager,
)
from app.trading.engine import TradingEngine

from .config import EAConfig
from .daily_controller import DailyController
from .grid_manager import GridManager, PositionSummary
from .indicators import Candle, compute_all
from .position_tracker import PositionTracker
from .scalper import ScalperModule
from .signal_generator import Direction, EntrySignal, SignalGenerator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estado de runtime exposto via /status
# ---------------------------------------------------------------------------

@dataclass
class EAStatus:
    user_id: str
    symbol: str
    running: bool
    can_trade: bool
    daily_summary: Dict[str, Any]
    signal_summary: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    open_positions: int = 0


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------

class PriceProEARunner:
    """
    Executa a lógica do PricePro EA para um único usuário/símbolo.

    Ciclo de vida:
        runner = PriceProEARunner(config, engine, ws_manager)
        await runner.start()   # inicia task assíncrona
        ...
        await runner.stop()    # para graciosamente
    """

    def __init__(
        self,
        config: EAConfig,
        engine: TradingEngine,
        ws_manager: KuCoinWebSocketManager,
    ):
        self.cfg = config
        self.engine = engine
        self.ws_manager = ws_manager

        # Submódulos
        self._signals = SignalGenerator(config)
        self._grid = GridManager(config)
        self._tracker = PositionTracker(config)
        self._scalper = ScalperModule(config)
        self._daily = DailyController(config)

        # Estado interno
        self._candle_history: List[Candle] = []
        self._open_order_ids: Set[str] = set()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Barra de controle (evita processar a mesma barra duas vezes)
        self._last_bar_ts: int = 0
        self._current_in_progress_candle: Optional[Candle] = None
        self._last_snap = None  # IndicatorSnapshot cacheado entre barras

        # Último candle FECHADO (para uso no scalper e trailing)
        self._last_closed_candle: Optional[Candle] = None

        self._errors: List[str] = []

    # ── Ciclo de vida ────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            logger.warning("[EARunner %s] Já em execução", self.cfg.symbol)
            return
        self._running = True

        # Inicializar equity
        try:
            balances = await self.engine.get_balance("USDT")
            equity = float(sum(
                Decimal(b.available)
                for b in balances
                if hasattr(b, "available")
            )) if balances else 0.0
        except Exception:
            equity = 0.0
        self._daily.initialize(equity)

        # Carregar histórico de candles via REST
        await self._load_initial_candles()

        # Subscrever canal de candles no WebSocket
        topic = f"/market/candles:{self.cfg.symbol}_{self.cfg.timeframe}"
        await self.ws_manager.subscribe(topic, self._on_candle_event)

        logger.info(
            "[EARunner] Iniciado — user=%s symbol=%s tf=%s",
            self.cfg.user_id, self.cfg.symbol, self.cfg.timeframe
        )

    async def stop(self) -> None:
        self._running = False
        topic = f"/market/candles:{self.cfg.symbol}_{self.cfg.timeframe}"
        try:
            await self.ws_manager.unsubscribe(topic, self._on_candle_event)
        except Exception:
            pass
        logger.info("[EARunner] Parado — %s", self.cfg.symbol)

    async def emergency_stop(self) -> None:
        """Fecha todas as posições imediatamente e para o EA."""
        await self._close_all_positions("emergência manual")
        await self.stop()

    # ── Carregamento inicial de candles ──────────────────────────────────────

    async def _load_initial_candles(self) -> None:
        """Carrega últimos N candles via REST para aquecer os indicadores."""
        try:
            normalized = await self.engine.get_klines(
                self.cfg.symbol,
                interval=self.cfg.timeframe,
                limit=self.cfg.indicator_warmup_bars,
            )
            self._candle_history = [
                Candle(
                    timestamp=int(c.timestamp.timestamp()),
                    open=float(c.open),
                    high=float(c.high),
                    low=float(c.low),
                    close=float(c.close),
                    volume=float(c.volume),
                )
                for c in normalized
            ]
            logger.info(
                "[EARunner] %d candles históricos carregados para %s",
                len(self._candle_history), self.cfg.symbol
            )
        except Exception as exc:
            logger.warning("[EARunner] Não foi possível carregar histórico: %s", exc)

    # ── Callback do WebSocket ─────────────────────────────────────────────────

    async def _on_candle_event(self, payload: Dict[str, Any]) -> None:
        """
        Callback recebido do KuCoinWebSocketManager para cada atualização de candle.
        Estrutura esperada: CandleEvent ou dict com campos de candle.
        """
        if not self._running:
            return

        try:
            data = payload.get("data", payload)
            candles_raw = data.get("candles", [])
            if not candles_raw or len(candles_raw) < 7:
                return

            # KuCoin candle format: [timestamp, open, close, high, low, txVol, baseVol]
            c = Candle(
                timestamp=int(candles_raw[0]),
                open=float(candles_raw[1]),
                close=float(candles_raw[2]),
                high=float(candles_raw[3]),
                low=float(candles_raw[4]),
                volume=float(candles_raw[6]),
            )

            # Nova barra
            if c.timestamp != self._last_bar_ts:
                # O candle anterior (last_bar) está fechado
                if self._current_in_progress_candle:
                    self._last_closed_candle = self._current_in_progress_candle
                    self._candle_history.append(self._last_closed_candle)
                    # Manter no máximo 500 barras em memória
                    if len(self._candle_history) > 500:
                        self._candle_history = self._candle_history[-500:]

                self._current_in_progress_candle = c
                self._last_bar_ts = c.timestamp
                await self._on_new_bar(c)
            else:
                # Atualização do candle em andamento (preço muda)
                self._current_in_progress_candle = c
                await self._on_tick(c)

        except Exception as exc:
            msg = f"Erro no callback de candle: {exc}"
            logger.error("[EARunner] %s", msg)
            self._errors.append(msg)
            if len(self._errors) > 50:
                self._errors = self._errors[-50:]

    # ── Nova barra ────────────────────────────────────────────────────────────

    async def _on_new_bar(self, current: Candle) -> None:
        """
        Executa toda a lógica de entrada/gestão na abertura de nova barra.
        Equivale ao bloco isNewBar do OnTick() no MT5.
        """
        if len(self._candle_history) < max(
            self.cfg.ema_period, self.cfg.rsi_period, 10
        ):
            return  # histórico insuficiente para indicadores

        closes = [c.close for c in self._candle_history]

        # Calcular todos os indicadores
        snap = compute_all(
            candles=self._candle_history,
            ema_period=self.cfg.ema_period,
            ema_type=self.cfg.ma_type,
            rsi_period=self.cfg.rsi_period,
            vol_lookback=3,
            range_period=9,
        )
        self._last_snap = snap  # cache for tick()

        bid = ask = current.close
        try:
            ticker = await self.engine.get_ticker(self.cfg.symbol)
            bid = float(ticker.get("bid", current.close))
            ask = float(ticker.get("ask", current.close))
        except Exception:
            pass

        # Atualizar P&L diário
        await self._refresh_daily_pnl()

        # Verificar P&L e metas
        self._daily.check_daily_stops(
            on_limit_fn=lambda: asyncio.create_task(
                self._close_all_positions("stop diário atingido")
            )
        )

        if not self._daily.can_trade:
            logger.info("[EARunner] EA bloqueado — %s", self._daily.status_text())
            return

        # Verificar equity para emergência
        try:
            balances = await self.engine.get_balance("USDT")
            equity = float(balances[0].available) if balances else 0.0
            self._daily.check_emergency_stop(
                equity,
                on_emergency_fn=lambda: asyncio.create_task(
                    self._close_all_positions("drawdown de emergência")
                ),
            )
        except Exception:
            pass

        # Analisar sinal de entrada
        result = self._signals.analyze(snap, bid)
        has_positions = bool(self._open_order_ids)

        # Escalper: ativar na nova barra
        was_force = self._signals.was_force_candle_in_direction(
            snap, result.trend_direction
        )
        self._scalper.on_new_bar(result.trend_direction, was_force, current.timestamp)
        self._scalper.check_bar_expiry(current.timestamp)

        # Abrir posição principal (se sinal e sem posições)
        if result.signal != EntrySignal.NO_ENTRY and not has_positions:
            await self._open_main_position(result.signal, bid, ask)

        # Grid: verificar proteção
        if has_positions and self.cfg.use_grid:
            await self._tick_grid(bid, ask)

        # Trailing/Breakeven
        await self._tracker.update(
            bid=bid,
            ask=ask,
            last_closed_candle=self._last_closed_candle,
            current_bar_time=current.timestamp,
            modify_fn=self._modify_sl_tp,
        )

    # ── Tick (entre barras) ───────────────────────────────────────────────────

    async def _on_tick(self, current: Candle) -> None:
        """
        Lógica executada em cada atualização de preço dentro da barra.
        Mantido leve — não recalcula indicadores.
        """
        if not self._running or not self._daily.can_trade:
            return

        bid = ask = current.close

        # Scalper
        try:
            ticker = await self.engine.get_ticker(self.cfg.symbol)
            bid = float(ticker.get("bid", current.close))
            ask = float(ticker.get("ask", current.close))
        except Exception:
            pass

        if not self._candle_history:
            return

        snap_ema: Optional[float] = None
        if hasattr(self, "_last_snap") and self._last_snap:
            snap_ema = self._last_snap.ema_value

        await self._scalper.tick(
            ema_value=snap_ema,
            bid=bid,
            ask=ask,
            has_open_positions=bool(self._open_order_ids),
            can_trade=self._daily.can_trade,
            open_order_fn=self._open_scalper_position,
            volume=self._lot_size(),
        )

    # ── Gestão de ordens ──────────────────────────────────────────────────────

    async def _open_main_position(self, signal: EntrySignal, bid: float, ask: float) -> None:
        side = "buy" if signal == EntrySignal.ENTER_BUY else "sell"
        volume = self._lot_size()
        price = ask if side == "buy" else bid
        open_price = price

        try:
            client_oid = f"ppea_{self.cfg.user_id}_{uuid.uuid4().hex[:12]}"
            order = await self.engine.place_market_order(
                symbol=self.cfg.symbol,
                side=side,
                size=volume,
                client_oid=client_oid,
                user_id=self.cfg.user_id,
            )
            self._open_order_ids.add(order.order_id)
            self._tracker.register(
                order_id=order.order_id,
                side=side,
                open_price=open_price,
            )
            logger.info(
                "[EARunner] Posição aberta — %s %s vol=%s @ %.5f id=%s",
                side, self.cfg.symbol, volume, price, order.order_id
            )
        except Exception as exc:
            logger.error("[EARunner] Erro ao abrir posição: %s", exc)

    async def _open_scalper_position(
        self, direction: str, symbol: str, volume: Any
    ) -> Optional[str]:
        try:
            client_oid = f"ppsc_{self.cfg.user_id}_{uuid.uuid4().hex[:12]}"
            order = await self.engine.place_market_order(
                symbol=symbol,
                side=direction,
                size=volume,
                client_oid=client_oid,
                user_id=self.cfg.user_id,
            )
            self._open_order_ids.add(order.order_id)
            logger.info("[EARunner] Scalper aberto — %s id=%s", direction, order.order_id)
            return order.order_id
        except Exception as exc:
            logger.error("[EARunner] Erro ao abrir scalper: %s", exc)
            return None

    async def _tick_grid(self, bid: float, ask: float) -> None:
        """Verifica e abre proteções de grid."""
        # Montar summary simplificado
        summary = await self._build_position_summary(bid, ask)
        if summary is None:
            return

        if self._grid.should_open_protection(summary, True, self._daily.can_trade):
            vol = self._grid.next_level_volume()
            if vol is None:
                return
            side = summary.direction.value
            try:
                client_oid = f"ppgd_{self.cfg.user_id}_{uuid.uuid4().hex[:12]}"
                order = await self.engine.place_market_order(
                    symbol=self.cfg.symbol,
                    side=side,
                    size=vol,
                    client_oid=client_oid,
                    user_id=self.cfg.user_id,
                )
                self._open_order_ids.add(order.order_id)
                self._grid.mark_protection_opened()
                logger.info("[Grid] Proteção aberta — nível %d", self._grid.protections_opened)
            except Exception as exc:
                logger.error("[Grid] Erro ao abrir proteção: %s", exc)
            return

        # Verificar se deve fechar tudo
        if self._grid.should_close_all(summary):
            await self._close_all_positions("grid target atingido")

    async def _close_all_positions(self, reason: str) -> None:
        """Fecha todas posições conhecidas."""
        logger.info("[EARunner] Fechando todas posições — motivo: %s", reason)
        for order_id in list(self._open_order_ids):
            try:
                await self.engine.cancel_order(order_id)
                self._open_order_ids.discard(order_id)
                self._tracker.remove(order_id)
            except Exception as exc:
                logger.warning("[EARunner] Erro ao fechar %s: %s", order_id, exc)
        self._grid.reset()

    async def _modify_sl_tp(
        self, order_id: str, sl: Optional[float], tp: Optional[float]
    ) -> bool:
        """Callback do PositionTracker para modificar SL/TP."""
        # KuCoin Spot não suporta amend de SL/TP diretamente em ordens abertas.
        # Registramos localmente e atualizamos na reabertura ou via OCO.
        self._tracker.update_sl(order_id, sl or 0.0)
        self._tracker.update_tp(order_id, tp or 0.0)
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _lot_size(self) -> Decimal:
        """Calcula volume baseado nas regras de lote da config."""
        if self.cfg.fixed_lot > Decimal("0"):
            return self.cfg.fixed_lot
        # Dynamic lot = % do saldo (simplificado)
        return Decimal("0.01")

    async def _refresh_daily_pnl(self) -> None:
        """Atualiza P&L realizado do dia consultando histórico da exchange."""
        try:
            orders = await self.engine.get_orders(self.cfg.symbol)
            # Apenas contabiliza ordens já fechadas (simplificado)
            # Em produção: usar endpoint de histórico de trades /api/v1/fills
            pass
        except Exception:
            pass

    async def _build_position_summary(
        self, bid: float, ask: float
    ) -> Optional[PositionSummary]:
        """Constrói PositionSummary a partir das ordens abertas conhecidas."""
        if not self._open_order_ids:
            return None
        # Resumo simplificado — em produção usar get_orders() para dados reais
        return PositionSummary(
            total_profit_usd=0.0,
            direction=Direction.BUY,
            avg_price=(bid + ask) / 2.0,
            net_volume=self._lot_size(),
            volume_long=self._lot_size(),
            volume_short=Decimal("0"),
            current_bid=bid,
            current_ask=ask,
        )

    # ── Status público ────────────────────────────────────────────────────────

    def get_status(self) -> EAStatus:
        return EAStatus(
            user_id=self.cfg.user_id,
            symbol=self.cfg.symbol,
            running=self._running,
            can_trade=self._daily.can_trade,
            daily_summary=self._daily.get_summary(),
            signal_summary={},
            errors=list(self._errors),
            open_positions=len(self._open_order_ids),
        )

    def update_config(self, new_config: EAConfig) -> None:
        """Aplica nova configuração sem reiniciar (runtime update)."""
        self.cfg = new_config
        self._signals = SignalGenerator(new_config)
        self._grid = GridManager(new_config)
        self._scalper = ScalperModule(new_config)
        logger.info("[EARunner] Config atualizada em runtime")


# ---------------------------------------------------------------------------
# Registry global de runners (um por user_id + symbol)
# ---------------------------------------------------------------------------

class EARegistry:
    """Mantém um runner por (user_id, symbol). Thread-safe via asyncio.Lock."""

    def __init__(self):
        self._runners: Dict[str, PriceProEARunner] = {}
        self._lock = asyncio.Lock()

    def _key(self, user_id: str, symbol: str) -> str:
        return f"{user_id}:{symbol}"

    async def start(
        self,
        config: EAConfig,
        engine: TradingEngine,
        ws_manager: KuCoinWebSocketManager,
    ) -> PriceProEARunner:
        async with self._lock:
            key = self._key(config.user_id, config.symbol)
            if key in self._runners:
                return self._runners[key]
            runner = PriceProEARunner(config, engine, ws_manager)
            await runner.start()
            self._runners[key] = runner
            return runner

    async def stop(self, user_id: str, symbol: str) -> bool:
        async with self._lock:
            key = self._key(user_id, symbol)
            runner = self._runners.pop(key, None)
            if runner:
                await runner.stop()
                return True
            return False

    async def emergency_stop(self, user_id: str, symbol: str) -> bool:
        async with self._lock:
            key = self._key(user_id, symbol)
            runner = self._runners.pop(key, None)
            if runner:
                await runner.emergency_stop()
                return True
            return False

    def get(self, user_id: str, symbol: str) -> Optional[PriceProEARunner]:
        return self._runners.get(self._key(user_id, symbol))

    def list_user(self, user_id: str) -> List[PriceProEARunner]:
        return [
            r for k, r in self._runners.items()
            if k.startswith(f"{user_id}:")
        ]


# Instância singleton
ea_registry = EARegistry()
