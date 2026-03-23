"""
BotWorker — executes ONE robot instance in a continuous async loop.

Responsibilities:
- Instantiate the correct strategy for the robot type
- Main loop: subscribe to price feed → calculate signal → risk check → place order
- Cancel all open orders and persist state on graceful stop
- Log every significant event with structured metadata
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger("engine.worker")


class BotWorker:
    """
    One BotWorker per active bot instance.
    Runs as an asyncio.Task managed by BotOrchestrator.
    """

    def __init__(self, instance: dict):
        self.instance = instance
        self.bot_id = str(instance["_id"])
        self.user_id = instance["user_id"]
        self.robot_id = instance["robot_id"]
        self.config: dict = instance.get("configuration", {})

        self._running = False
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused by default

        # Open position tracked in memory (persisted in DB too)
        self._open_position: Optional[dict] = None

        # DOC-K05/K06: Track native stop order IDs for TP/SL
        # {
        #   "sl_order_id": str | None,   # Stop Loss native order ID
        #   "tp_order_id": str | None,   # Take Profit native order ID
        # }
        self._stop_orders: dict = {"sl_order_id": None, "tp_order_id": None}

        # DOC-K10: Intra-worker cycle lock — prevents two concurrent ticks from
        # both seeing _open_position = None and placing duplicate orders.
        self._cycle_lock: asyncio.Lock = asyncio.Lock()
        # Flag set BEFORE the first await inside _open_position_handler;
        # cleared after the order is confirmed (filled or failed).
        self._order_in_progress: bool = False

        # Lazy-initialised components (avoid import cycles at module level)
        self._exchange = None
        self._strategy = None
        self._risk = None

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_components(self):
        """Initialise exchange client, strategy and risk manager."""
        from app.engine.exchange.kucoin_client import KuCoinClient
        from app.engine.strategies import get_strategy
        from app.engine.risk_adapter import RiskAdapter

        self._exchange = KuCoinClient(
            api_key=self.instance.get("decrypted_api_key", ""),
            api_secret=self.instance.get("decrypted_api_secret", ""),
            api_passphrase=self.instance.get("decrypted_api_passphrase", ""),
            sandbox=self._is_sandbox(),
        )

        # DOC-K01: Wipe plaintext credentials from instance dict immediately
        # after they've been handed off to KuCoinClient.  They are no longer
        # needed here and must not persist in memory longer than necessary.
        for _cred_key in ("decrypted_api_key", "decrypted_api_secret", "decrypted_api_passphrase"):
            self.instance.pop(_cred_key, None)

        robot_type = self.instance.get("robot_type", "rsi")
        self._strategy = get_strategy(robot_type, self.config)

        self._risk = RiskAdapter(self.bot_id, self.config)
        logger.info(
            f"🤖 BotWorker {self.bot_id[:8]} — "
            f"strategy={robot_type}, pair={self.config.get('pair')}"
        )

    def _is_sandbox(self) -> bool:
        import os
        return os.getenv("KUCOIN_SANDBOX", "false").lower() in ("1", "true", "yes")

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def run(self):
        """Entry point called by BotOrchestrator._run_worker_with_supervision."""
        self._running = True
        self._init_components()
        logger.info(f"▶️  BotWorker {self.bot_id[:8]} iniciando execução")

        await self._update_status("running")

        # DOC-K03: Subscribe to private WS execution reports
        ws_task: Optional[asyncio.Task] = None
        try:
            from app.integrations.kucoin.ws_client import KuCoinWebSocketClient, TOPIC_ORDERS
            self._ws_client = KuCoinWebSocketClient(
                rest_client=self._exchange._client
                if hasattr(self._exchange, "_client") else self._exchange,
                on_message=self._handle_ws_execution_report,
                on_disconnect=self._on_ws_disconnect,
                private=True,
            )
            await self._ws_client.subscribe(TOPIC_ORDERS, private=True)
            ws_task = asyncio.create_task(
                self._ws_client.connect(),
                name=f"ws-exec-{self.bot_id[:8]}",
            )
            logger.info(f"[DOC-K03] WebSocket execution reports subscrito [{self.bot_id[:8]}]")
        except Exception as ws_init_err:
            logger.warning(
                f"[DOC-K03] Falha ao iniciar WS execution reports: {ws_init_err} "
                f"— continuando sem WS (polling mode)"
            )
            self._ws_client = None

        try:
            pair = self.config.get("pair", "BTC-USDT")
            async for tick in self._exchange.price_feed(pair, stop_event=self._stop_event):
                if self._stop_event.is_set():
                    break

                # Block here if paused
                await self._pause_event.wait()

                try:
                    await self._execute_cycle(tick)
                except Exception as exc:
                    logger.error(
                        f"❌ Erro no ciclo bot {self.bot_id[:8]}: {exc}",
                        exc_info=True,
                    )
                    await self._log_event("ERROR", str(exc))
                    # ── Error burst circuit-breaker ──────────────────────
                    burst_reason = self._risk.record_error()
                    if burst_reason:
                        logger.error(
                            f"🚨 Error burst detectado [{self.bot_id[:8]}] — parando bot"
                        )
                        await self._update_status("stopped", stop_reason=burst_reason)
                        self._stop_event.set()
                        break

        finally:
            self._running = False
            # DOC-K03: Shutdown WS execution report client
            if ws_task and not ws_task.done():
                ws_task.cancel()
            if hasattr(self, "_ws_client") and self._ws_client:
                try:
                    await self._ws_client.disconnect()
                except Exception:
                    pass
            await self._update_status("stopped")
            logger.info(f"⏹️  BotWorker {self.bot_id[:8]} encerrado")

    # ── Trading Cycle ─────────────────────────────────────────────────────────

    async def _execute_cycle(self, tick: dict):
        """One decision cycle: price data → signal → risk → order → persist."""
        from app.engine.repository import BotInstanceRepository

        pair = self.config.get("pair", "BTC-USDT")
        lock_acquired = await BotInstanceRepository.acquire_lock(
            self.bot_id, pair, ttl_seconds=30
        )
        if not lock_acquired:
            logger.debug(f"Ciclo pulado — lock ocupado [{self.bot_id[:8]}]")
            return

        try:
            await self._do_execute_cycle(tick)
        finally:
            await BotInstanceRepository.release_lock(self.bot_id, pair)

    async def _do_execute_cycle(self, tick: dict):
        """Actual cycle logic, called only when the distributed lock is held."""
        # DOC-K10: Intra-worker asyncio.Lock — only one cycle at a time.
        if self._cycle_lock.locked():
            logger.debug(f"Ciclo local pulado — ciclo anterior ainda em andamento [{self.bot_id[:8]}]")
            return

        async with self._cycle_lock:
            await self._do_execute_cycle_locked(tick)

    async def _do_execute_cycle_locked(self, tick: dict):
        """Actual cycle logic, called only when both distributed + local locks are held."""
        current_price: float = tick["price"]

        # ── 1. Check risk on open position ─────────────────────────────────
        if self._open_position:
            exit_reason = self._risk.check_position_exit(
                entry_price=self._open_position["entry_price"],
                current_price=current_price,
                entry_timestamp=self._open_position["entry_timestamp"],
            )
            if exit_reason:
                await self._close_position(current_price, reason=exit_reason)
                return

        # ── 2. Guard: skip cycle if an order is already being placed ────────
        if self._order_in_progress:
            logger.debug(
                "[DOC-K10] Ciclo pulado — ordem em andamento. [bot=%s]",
                self.bot_id[:8],
            )
            return

        # ── 3. Fetch recent candles ─────────────────────────────────────────
        candles = await self._exchange.get_candles(
            pair=self.config.get("pair", "BTC-USDT"),
            timeframe=self.config.get("timeframe", "1h"),
            limit=200,
        )
        if not candles:
            return

        # ── 4. Strategy signal ──────────────────────────────────────────────
        signal = await self._strategy.calculate(candles, current_price)
        if signal.action == "hold":
            return

        # ── 5. Session-level risk check ─────────────────────────────────────
        stop_reason = await self._check_session_risk(signal.action)
        if stop_reason:
            logger.warning(f"🛑 Sessão encerrada por risco: {stop_reason}")
            await self._update_status("stopped", stop_reason=stop_reason)
            self._stop_event.set()
            return

        # ── 6. Place order — protected by cycle_lock + _order_in_progress ───
        # DOC-K10: GUARD 2 — set flag BEFORE any await to block concurrent ticks
        if signal.action == "buy" and not self._open_position and not self._order_in_progress:
            self._order_in_progress = True
            try:
                await self._open_position_handler(current_price, signal)
            finally:
                self._order_in_progress = False

        elif signal.action == "sell" and self._open_position and not self._order_in_progress:
            self._order_in_progress = True
            try:
                await self._close_position(current_price, reason="strategy_signal")
            finally:
                self._order_in_progress = False

    async def _open_position_handler(self, price: float, signal):
        """Execute buy order and record open position.

        DOC-K10: _order_in_progress flag is set by the caller (_do_execute_cycle_locked)
        BEFORE this coroutine is awaited, so it is already True when we enter here.
        We do NOT touch the flag — the caller's finally block resets it.
        """
        # Dupla verificação — bail out if position already exists
        if self._open_position:
            logger.warning(
                "[DOC-K10] _open_position_handler chamado mas _open_position já existe. "
                "Race condition evitado. [bot=%s]",
                self.bot_id[:8],
            )
            return
        await self._open_position_handler_inner(price, signal)

    async def _open_position_handler_inner(self, price: float, signal):
        """Inner buy logic — called only when _order_in_progress lock is held."""
        from app.core.database import get_db
        from app.engine.order_intent_store import OrderIntentStore, DuplicateOrderIntentError

        # DOC-K10: Inner guard — bail out if position already open (double-check)
        if self._open_position:
            logger.warning(
                "[DOC-K10] _open_position_handler_inner chamado mas _open_position já existe. "
                "Race condition evitado. [bot=%s]",
                self.bot_id[:8],
            )
            return

        pair = self.config.get("pair", "BTC-USDT")
        capital = float(self.config.get("capital_usdt", 100))

        # DOC-K10: Exchange double-check — abort if open orders already exist
        try:
            open_orders = await self._exchange.get_open_orders(pair)
            if open_orders:
                logger.warning(
                    "[DOC-K10] ⚠️  %d ordem(ns) abertas na exchange antes de abrir posição. "
                    "Abortando para evitar duplicata. [bot=%s]",
                    len(open_orders), self.bot_id[:8],
                )
                return
        except Exception as exc:
            logger.warning(
                "[DOC-K10] Não foi possível verificar ordens abertas: %s. "
                "Prosseguindo com cautela. [bot=%s]",
                exc, self.bot_id[:8],
            )

        db = get_db()
        store = OrderIntentStore(db)

        # DOC-K04: Gerar clientOid UMA VEZ antes de qualquer await de rede
        client_oid = OrderIntentStore.generate_client_oid()

        # Persistir intent ANTES de enviar à exchange (Write-Ahead Log)
        try:
            await store.create_intent(
                bot_instance_id=self.bot_id,
                user_id=self.user_id,
                pair=pair,
                side="buy",
                order_type="market",
                funds=capital,
                client_oid=client_oid,
            )
        except DuplicateOrderIntentError:
            logger.warning(f"[DOC-K04] Intent buy duplicado — não enviando nova ordem [{self.bot_id[:8]}]")
            return

        try:
            order = await self._exchange.place_market_order(
                pair=pair, side="buy", funds=capital, client_oid=client_oid
            )
            if not order:
                await store.mark_error(client_oid, "place_market_order retornou None")
                return

            exchange_order_id = order.get("orderId", "")
            await store.mark_sent(client_oid, exchange_order_id)

            filled_price = float(order.get("dealPrice") or price)
            filled_funds = float(order.get("dealFunds") or capital)
            fee = float(order.get("fee") or filled_funds * 0.001)
            fee_currency = order.get("feeCurrency") or "USDT"
            quantity = (filled_funds - fee) / filled_price if filled_price else 0

            await store.mark_filled(client_oid, exchange_order_id, filled_price, filled_funds, fee)

            self._open_position = {
                "entry_order_id": exchange_order_id,
                "entry_client_oid": client_oid,
                "entry_price": filled_price,
                "entry_funds": filled_funds,
                "entry_quantity": quantity,
                "entry_fee": fee,
                "entry_fee_currency": fee_currency,
                "entry_timestamp": datetime.now(timezone.utc),
                "reason": signal.reason,
            }

            await self._persist_trade_event("buy", order, signal)
            await self._log_event(
                "TRADE",
                f"📈 BUY @ {filled_price:.4f} | qty={quantity:.6f} | reason={signal.reason}",
            )

            # DOC-K05: Place native Stop-Loss on KuCoin exchange server
            import uuid as _uuid
            sl_cfg  = self.config.get("stop_loss") or {}
            tp_cfg  = self.config.get("take_profit") or {}

            if sl_cfg and sl_cfg.get("use_native_order") and quantity > 0:
                sl_mode  = sl_cfg.get("mode", "percentage")
                sl_value = float(sl_cfg.get("value", 2.0))
                if sl_mode == "percentage":
                    stop_price  = filled_price * (1 - sl_value / 100)
                    limit_price = stop_price * 0.995   # 0.5% slippage buffer
                elif sl_mode == "fixed_price":
                    stop_price  = float(sl_value)
                    limit_price = stop_price * 0.995
                else:
                    stop_price = limit_price = None

                if stop_price:
                    try:
                        sl_client_oid = str(_uuid.uuid4())
                        sl_order = await self._exchange.place_stop_order(
                            pair=pair,
                            side="sell",
                            stop_price=round(stop_price, 8),
                            size=round(quantity, 8),
                            stop_type="loss",
                            order_type="limit",
                            limit_price=round(limit_price, 8),
                            client_oid=sl_client_oid,
                        )
                        self._stop_orders["sl_order_id"] = sl_order.get("orderId", "")
                        logger.info(
                            "🛡️  SL nativo @ %.4f (%.1f%%) — orderId=%s [bot=%s]",
                            stop_price, sl_value,
                            self._stop_orders["sl_order_id"], self.bot_id[:8],
                        )
                        await self._log_event(
                            "INFO",
                            f"SL nativo colocado @ {stop_price:.4f} ({sl_value:.1f}%)",
                        )
                    except Exception as sl_exc:
                        logger.error("Falha ao criar Stop-Loss nativo: %s [bot=%s]", sl_exc, self.bot_id[:8])
                        await self._log_event("ERROR", f"Falha ao criar SL nativo: {sl_exc}")

            # DOC-K05: Place native Take-Profit (limit sell) on KuCoin exchange server
            if tp_cfg and tp_cfg.get("use_native_order") and quantity > 0:
                tp_mode  = tp_cfg.get("mode", "percentage")
                tp_value = float(tp_cfg.get("value", 5.0))
                if tp_mode == "percentage":
                    tp_price = filled_price * (1 + tp_value / 100)
                elif tp_mode == "fixed_price":
                    tp_price = float(tp_value)
                else:
                    tp_price = None

                if tp_price:
                    try:
                        tp_client_oid = str(_uuid.uuid4())
                        tp_order = await self._exchange.place_limit_order(
                            pair=pair,
                            side="sell",
                            price=round(tp_price, 8),
                            size=round(quantity, 8),
                            client_oid=tp_client_oid,
                        )
                        self._stop_orders["tp_order_id"] = tp_order.get("orderId", "")
                        logger.info(
                            "🎯 TP nativo @ %.4f (%.1f%%) — orderId=%s [bot=%s]",
                            tp_price, tp_value,
                            self._stop_orders["tp_order_id"], self.bot_id[:8],
                        )
                        await self._log_event(
                            "INFO",
                            f"TP nativo colocado @ {tp_price:.4f} ({tp_value:.1f}%)",
                        )
                    except Exception as tp_exc:
                        logger.error("Falha ao criar Take-Profit nativo: %s [bot=%s]", tp_exc, self.bot_id[:8])
                        await self._log_event("ERROR", f"Falha ao criar TP nativo: {tp_exc}")

        except Exception as exc:
            await store.mark_error(client_oid, str(exc))
            logger.error(f"Falha ao abrir posição: {exc}", exc_info=True)
            await self._log_event("ERROR", f"Falha ao abrir posição: {exc}")

    async def _close_position(self, current_price: float, reason: str):
        """Execute sell order, calculate PnL, record trade close."""
        if not self._open_position:
            return

        # DOC-K05: Cancel native SL/TP stop orders before placing manual sell
        # to prevent duplicate sells (engine close + native order firing simultaneously).
        for label, order_id in (
            ("SL", self._stop_orders.get("sl_order_id")),
            ("TP", self._stop_orders.get("tp_order_id")),
        ):
            if order_id:
                try:
                    await self._exchange.cancel_stop_order(order_id)
                    logger.debug(
                        "Stop order nativa %s (%s) cancelada antes do fechamento manual. [bot=%s]",
                        label, order_id, self.bot_id[:8],
                    )
                except Exception as cancel_exc:
                    logger.warning(
                        "Falha ao cancelar stop order nativa %s (%s): %s [bot=%s]",
                        label, order_id, cancel_exc, self.bot_id[:8],
                    )
        self._stop_orders = {"sl_order_id": None, "tp_order_id": None}

        pair = self.config.get("pair", "BTC-USDT")
        qty = self._open_position["entry_quantity"]

        try:
            order = await self._exchange.place_market_order(
                pair=pair, side="sell", size=qty
            )
            if not order:
                return

            exit_price = float(order.get("dealPrice") or current_price)
            exit_gross = exit_price * qty
            exit_fee = float(order.get("fee") or exit_gross * 0.001)
            exit_fee_currency = order.get("feeCurrency") or "USDT"
            pnl_net = exit_gross - exit_fee - self._open_position["entry_funds"]

            await self._persist_trade_close(order, exit_price, pnl_net, reason)
            await self._update_instance_metrics(pnl_net)
            await self._log_event(
                "TRADE",
                f"📉 SELL @ {exit_price:.4f} | PnL={pnl_net:+.4f} USDT | reason={reason}",
            )

            # Update session risk tracker — check for session circuit-breakers
            session_stop = self._risk.record_trade_result(pnl_net)
            self._open_position = None
            if session_stop:
                logger.warning(
                    f"🛑 Sessão encerrada por risco [{self.bot_id[:8]}]: {session_stop}"
                )
                await self._update_status("stopped", stop_reason=session_stop)
                self._stop_event.set()

        except Exception as exc:
            logger.error(f"Falha ao fechar posição: {exc}", exc_info=True)
            await self._log_event("ERROR", f"Falha ao fechar posição: {exc}")

    # ── Risk Session Check ────────────────────────────────────────────────────

    async def _check_session_risk(self, action: str) -> Optional[str]:
        """Returns a stop reason string if the session should end, otherwise None."""
        kill_reason = await self._risk.check_kill_switch(self.user_id)
        if kill_reason:
            return kill_reason
        return None

    # ── DOC-K03: WebSocket Execution Reports ──────────────────────────────────

    async def _handle_ws_execution_report(self, msg: dict) -> None:
        """
        DOC-K03: Process private order execution reports from KuCoin WS.
        Topic: /spotMarket/tradeOrders

        Handles: partial fills, full fills, cancellations.
        Updates _open_position state and persists corrections to DB.
        """
        try:
            topic = msg.get("topic", "")
            if "tradeOrders" not in topic:
                return

            # DOC-K03: Filter by subject — only orderChange/match events
            subject = msg.get("subject", "")
            if subject and subject not in ("orderChange", "match"):
                return

            data         = msg.get("data", {})
            order_id     = data.get("orderId", "")
            client_oid   = data.get("clientOid", "")
            status       = data.get("status", "")
            side         = data.get("side", "")
            symbol       = data.get("symbol", "")
            # Prefer filledSize/filledFunds; fall back to matchSize/matchFunds
            filled_size  = float(data.get("filledSize") or data.get("matchSize") or 0)
            filled_funds = float(data.get("filledFunds") or data.get("matchFunds") or 0)
            fee          = float(data.get("fee") or 0)

            logger.debug(
                "WS execution report: orderId=%s status=%s symbol=%s side=%s "
                "filledSize=%s filledFunds=%s",
                order_id, status, symbol, side, filled_size, filled_funds,
            )

            if not self._open_position:
                # Check sell-side (OCO) even without open position guard below
                pass
            else:
                tracked_order_id = self._open_position.get("entry_order_id", "")
                tracked_client_oid = self._open_position.get("entry_client_oid", "")

                # ── CASO 1: Ordem de ENTRADA preenchida (parcial ou total) ──────
                if side == "buy" and (order_id == tracked_order_id or client_oid == tracked_client_oid):
                    if status in ("match", "done"):
                        if filled_size > 0:
                            old_qty = self._open_position.get("entry_quantity", 0)
                            divergence = abs(filled_size - old_qty) / max(old_qty, 1e-10)
                            if divergence > 0.01:  # >1% divergence — update
                                actual_price = (
                                    filled_funds / filled_size if filled_size > 0 else 0
                                )
                                logger.warning(
                                    "⚠️  Partial fill detectado: qty esperada=%.6f real=%.6f "
                                    "[bot=%s]",
                                    old_qty, filled_size, self.bot_id[:8],
                                )
                                self._open_position["entry_quantity"] = filled_size
                                self._open_position["entry_funds"]    = filled_funds
                                self._open_position["entry_fee"]      = fee
                                self._open_position["entry_price"]    = actual_price

                                # Persist correction to DB
                                trade_doc_id = self._open_position.get("_trade_doc_id")
                                if trade_doc_id:
                                    from app.core.database import get_db
                                    db = get_db()
                                    await db["bot_trades"].update_one(
                                        {"_id": ObjectId(trade_doc_id)},
                                        {"$set": {
                                            "entry_price":    actual_price,
                                            "entry_funds":    filled_funds,
                                            "entry_fee_usdt": fee,
                                        }},
                                    )
                            else:
                                # Small divergence: just update qty silently
                                self._open_position["entry_quantity"] = filled_size
                                logger.info(
                                    "[DOC-K03] Fill confirmado via WS: qty=%.6f [%s]",
                                    filled_size, self.bot_id[:8],
                                )

                    elif status == "cancelled":
                        logger.warning(
                            "⚠️  Ordem de compra %s CANCELADA pela exchange. "
                            "Limpando posição local. [bot=%s]",
                            order_id, self.bot_id[:8],
                        )
                        trade_doc_id = self._open_position.get("_trade_doc_id")
                        if trade_doc_id:
                            from app.core.database import get_db
                            db = get_db()
                            await db["bot_trades"].update_one(
                                {"_id": ObjectId(trade_doc_id)},
                                {"$set": {
                                    "status":      "cancelled",
                                    "exit_reason": "order_cancelled_by_exchange",
                                }},
                            )
                        await self._log_event(
                            "WARNING",
                            f"Ordem de compra {order_id} cancelada pela exchange — posição limpa",
                            {"order_id": order_id, "symbol": symbol},
                        )
                        self._open_position = None

            # ── CASO 2: Ordem de SAÍDA / OCO (DOC-K06) ──────────────────────
            if self._open_position and side == "sell" and status == "done":
                sl_id = self._stop_orders.get("sl_order_id")
                tp_id = self._stop_orders.get("tp_order_id")
                exit_order_id = self._open_position.get("exit_order_id", "")

                if order_id in (sl_id, tp_id):
                    triggered_leg = "SL" if order_id == sl_id else "TP"
                    opposing_id   = tp_id if order_id == sl_id else sl_id
                    logger.info(
                        "[DOC-K06] %s disparado via WS — cancelando leg oposta "
                        "(orderId=%s) [%s]",
                        triggered_leg, opposing_id, self.bot_id[:8],
                    )
                    if opposing_id:
                        try:
                            # DOC-K06: SL is a stop order → cancel_stop_order
                            #          TP is a plain limit order → cancel_order
                            if triggered_leg == "SL":
                                # SL fired → cancel opposing TP (plain limit order)
                                await self._exchange.cancel_order(opposing_id)
                            else:
                                # TP fired → cancel opposing SL (stop-limit order)
                                await self._exchange.cancel_stop_order(opposing_id)
                            logger.info(
                                "[DOC-K06] Leg oposta %s cancelada com sucesso.",
                                opposing_id,
                            )
                        except Exception as cancel_exc:
                            logger.warning(
                                "[DOC-K06] Falha ao cancelar leg oposta %s: %s",
                                opposing_id, cancel_exc,
                            )
                    fill_price = float(data.get("dealPrice") or data.get("matchPrice") or 0)
                    fill_funds_exit = float(data.get("dealFunds") or filled_funds or 0)
                    fee_exit = float(data.get("fee") or fee or 0)
                    await self._oco_close_position(
                        fill_price=fill_price,
                        fill_funds=fill_funds_exit,
                        fee=fee_exit,
                        order_id=order_id,
                        reason=f"ws_{triggered_leg.lower()}_triggered",
                    )
                elif order_id == exit_order_id:
                    logger.info(
                        "✅ Ordem de saída %s confirmada via WS. filledSize=%.6f [bot=%s]",
                        order_id, filled_size, self.bot_id[:8],
                    )

        except Exception as exc:
            logger.error(f"[DOC-K03] Erro ao processar execution report: {exc}", exc_info=True)

    async def _oco_close_position(
        self,
        fill_price: float,
        fill_funds: float,
        fee: float,
        order_id: str,
        reason: str,
    ) -> None:
        """
        DOC-K06: Record a position close triggered by a native OCO leg on the exchange.

        Does NOT send a new sell order — the exchange order already executed.
        Calculates PnL, persists trade close, updates metrics, and checks
        session-level risk circuit-breakers (daily loss, drawdown).
        """
        if not self._open_position:
            return

        entry_funds = self._open_position.get("entry_funds", 0)
        quantity    = self._open_position.get("entry_quantity", 0)

        # Use funds from WS event when available; fall back to price × qty
        exit_funds = fill_funds if fill_funds > 0 else (fill_price * quantity)
        pnl_net    = exit_funds - fee - entry_funds

        label = reason.replace("ws_", "").replace("_triggered", "").upper()
        await self._persist_trade_close(
            order={"orderId": order_id, "fee": fee},
            exit_price=fill_price,
            pnl_net=pnl_net,
            reason=reason,
        )
        await self._update_instance_metrics(pnl_net)
        await self._log_event(
            "TRADE",
            f"📉 OCO {label} @ {fill_price:.4f} | PnL={pnl_net:+.4f} USDT",
        )

        self._open_position = None
        self._stop_orders   = {"sl_order_id": None, "tp_order_id": None}

        # DOC-K06: Check session-level circuit-breakers AFTER clearing position
        session_stop = self._risk.record_trade_result(pnl_net)
        if session_stop:
            logger.warning(
                "🛑 Sessão encerrada por risco após OCO [bot=%s]: %s",
                self.bot_id[:8], session_stop,
            )
            await self._update_status("stopped", stop_reason=session_stop)
            self._stop_event.set()

    async def _on_ws_disconnect(self, reconnect_count: int) -> None:
        """
        DOC-K03 + DOC-K08: Called before each WS reconnect attempt.
        Reconcile position state via REST in case orders filled during disconnect.
        Also checks native stop orders that may have fired while offline.
        """
        logger.warning(
            "📡 WS offline — reconciliando estado (reconexão %d). [bot=%s]",
            reconnect_count, self.bot_id[:8],
        )

        if reconnect_count == 0:
            return  # primeira desconexão — aguardar reconexão antes de reconciliar

        if not self._open_position:
            return

        # Reconciliar posição via REST (órfãs, partial fills)
        try:
            await self._reconcile_position_via_rest()
        except Exception as exc:
            logger.error("Falha na reconciliação REST: %s [bot=%s]", exc, self.bot_id[:8])

        # === DOC-K08 Catch-up: verificar stop orders nativas executadas durante offline ===
        if self._open_position:
            pair = self.config.get("pair", "BTC-USDT")
            try:
                open_stop_orders = await self._exchange.get_open_stop_orders(pair)
                open_stop_ids = {o.get("id") for o in open_stop_orders}

                native_sl_id = self._open_position.get("native_sl_order_id")
                native_tp_id = self._open_position.get("native_tp_order_id")

                # Se SL sumiu das stop orders abertas → foi executado durante offline
                if native_sl_id and native_sl_id not in open_stop_ids:
                    logger.warning(
                        "🔄 Catch-up: SL nativo %s executado durante offline. "
                        "Fechando posição local. [bot=%s]",
                        native_sl_id, self.bot_id[:8],
                    )
                    # Cancelar TP antes de registrar fechamento
                    if native_tp_id:
                        try:
                            await self._exchange.cancel_order(native_tp_id)
                        except Exception:
                            pass
                    await self._oco_close_position(
                        fill_price=self._open_position.get("native_sl_stop_price", 0),
                        fill_funds=0,
                        fee=0,
                        order_id=native_sl_id,
                        reason="stop_loss_native_offline",
                    )
                    return

                # Se TP sumiu das ordens regulares → foi executado durante offline
                # (TP é uma limit order normal, não stop — verificar via get_order)
                if native_tp_id and self._open_position:
                    try:
                        tp_order = await self._exchange.get_order(native_tp_id)
                        tp_active = tp_order.get("isActive", True)
                        tp_status = tp_order.get("status", "")
                        if not tp_active and tp_status == "done":
                            logger.warning(
                                "🔄 Catch-up: TP nativo %s executado durante offline. "
                                "Fechando posição local. [bot=%s]",
                                native_tp_id, self.bot_id[:8],
                            )
                            # Cancelar SL antes de registrar fechamento
                            if native_sl_id:
                                try:
                                    await self._exchange.cancel_stop_order(native_sl_id)
                                except Exception:
                                    pass
                            exit_price = float(tp_order.get("dealPrice") or
                                               self._open_position.get("native_tp_price", 0))
                            await self._oco_close_position(
                                fill_price=exit_price,
                                fill_funds=float(tp_order.get("dealFunds") or 0),
                                fee=float(tp_order.get("fee") or 0),
                                order_id=native_tp_id,
                                reason="take_profit_native_offline",
                            )
                    except Exception as tp_exc:
                        logger.error(
                            "Erro ao verificar TP nativo no catch-up: %s [bot=%s]",
                            tp_exc, self.bot_id[:8],
                        )

            except Exception as exc:
                logger.error("Erro no catch-up pós-reconexão: %s [bot=%s]", exc, self.bot_id[:8])

    async def _reconcile_position_via_rest(self) -> None:
        """
        DOC-K03: Verify open position state against KuCoin REST API.
        Called after WS reconnect to catch fills that happened while offline.
        """
        if not self._open_position:
            return

        entry_order_id = self._open_position.get("entry_order_id", "")
        if not entry_order_id:
            return

        try:
            order = await self._exchange.get_order(entry_order_id)
            is_active   = order.get("isActive", True)  # False means done/cancelled
            filled_size = float(order.get("dealSize") or 0)

            if not is_active and filled_size == 0:
                # Order cancelled with no fill — no real position
                logger.warning(
                    "🔄 Reconciliação: ordem %s não encontrada/cancelada. "
                    "Limpando posição local. [bot=%s]",
                    entry_order_id, self.bot_id[:8],
                )
                self._open_position = None

            elif abs(filled_size - self._open_position.get("entry_quantity", 0)) > 0.000001:
                # Quantity divergence detected (partial fill missed during disconnect)
                logger.warning(
                    "🔄 Reconciliação: quantidade real=%.6f difere do local=%.6f. "
                    "Corrigindo. [bot=%s]",
                    filled_size, self._open_position.get("entry_quantity", 0),
                    self.bot_id[:8],
                )
                self._open_position["entry_quantity"] = filled_size

        except Exception as exc:
            logger.error("Erro na reconciliação via REST: %s [bot=%s]", exc, self.bot_id[:8])

    # ── Control Methods ────────────────────────────────────────────────────────

    async def stop(self, reason: str = "unknown"):
        """Request a graceful stop — cancels open orders before exiting."""
        logger.info(f"🛑 Parando worker {self.bot_id[:8]} — motivo: {reason}")

        pair = self.config.get("pair")
        if pair:
            try:
                await self._exchange.cancel_all_orders(pair)
            except Exception as exc:
                logger.warning(f"Erro ao cancelar ordens abertas: {exc}")

        self._stop_event.set()
        await self._update_status("stopped", stop_reason=reason)

    async def pause(self):
        """Pause signal processing (open orders remain active on exchange)."""
        self._pause_event.clear()
        await self._update_status("paused")
        logger.info(f"⏸️  Worker {self.bot_id[:8]} pausado")

    async def resume(self):
        """Resume signal processing."""
        self._pause_event.set()
        await self._update_status("running")
        logger.info(f"▶️  Worker {self.bot_id[:8]} retomado")

    # ── Persistence Helpers ───────────────────────────────────────────────────

    async def _update_status(self, status: str, **kwargs):
        from app.core.database import get_db
        db = get_db()
        update_fields = {
            "status": status,
            "last_heartbeat": datetime.now(timezone.utc),
            **kwargs,
        }
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(self.bot_id)},
            {"$set": update_fields},
        )

    async def _persist_trade_event(self, side: str, order: dict, signal):
        from app.core.database import get_db
        db = get_db()
        doc = {
            "bot_instance_id": self.bot_id,
            "user_id": self.user_id,
            "robot_id": self.robot_id,
            "exchange_order_id": order.get("orderId", ""),
            "pair": self.config.get("pair"),
            "side": side,
            "status": "open",
            "entry_price": float(order.get("dealPrice") or 0),
            "entry_funds": float(order.get("dealFunds") or 0),
            "entry_fee_usdt": float(order.get("fee") or 0),
            "strategy_reason": signal.reason,
            "entry_timestamp": datetime.now(timezone.utc),
        }
        result = await db["bot_trades"].insert_one(doc)
        self._open_position["_trade_doc_id"] = str(result.inserted_id)

    async def _persist_trade_close(
        self, order: dict, exit_price: float, pnl_net: float, reason: str
    ):
        from app.core.database import get_db
        db = get_db()
        trade_id = self._open_position.get("_trade_doc_id")
        if not trade_id:
            return
        entry_ts = self._open_position["entry_timestamp"]
        now = datetime.now(timezone.utc)
        holding_minutes = int((now - entry_ts).total_seconds() / 60)
        await db["bot_trades"].update_one(
            {"_id": ObjectId(trade_id)},
            {
                "$set": {
                    "status": "closed",
                    "exit_order_id": order.get("orderId", ""),
                    "exit_price": exit_price,
                    "exit_fee_usdt": float(order.get("fee") or 0),
                    "exit_timestamp": now,
                    "exit_reason": reason,
                    "pnl_net_usdt": round(pnl_net, 6),
                    "holding_minutes": holding_minutes,
                }
            },
        )

    async def _update_instance_metrics(self, pnl_net: float):
        from app.core.database import get_db
        db = get_db()
        inc_op = {"metrics.total_pnl_usdt": round(pnl_net, 6), "metrics.total_trades": 1}
        if pnl_net >= 0:
            inc_op["metrics.winning_trades"] = 1
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(self.bot_id)},
            {"$inc": inc_op},
        )

    async def _log_event(self, level: str, message: str, metadata: dict = None):
        from app.core.database import get_db
        db = get_db()
        await db["bot_execution_logs"].insert_one(
            {
                "bot_instance_id": self.bot_id,
                "user_id": self.user_id,
                "level": level,
                "message": message[:1000],
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc),
            }
        )
