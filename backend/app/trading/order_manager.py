"""
OrderManager - Camada 5

Gerencia ciclo de vida das ordens:
- Fila interna (evita duplicatas)
- Lock por símbolo (evita race conditions)
- Retry com exponential backoff
- Idempotência via client_oid (persiste ANTES de enviar)
- TP/SL tracking
- Atualização de status via WebSocket execution report
- Sem polling GET /orders após POST (performance)

Fluxo correto:
    Strategy
        ↓
    Queue Interna
        ↓
    [lock por símbolo]
        ↓
    Persiste PENDING no banco (idempotência)
        ↓
    OrderManager → TradingEngine → KuCoin
        ↓
    Atualização via WS execution report (sem 2º request REST)
"""

from __future__ import annotations

import logging
import asyncio
import time
import uuid
from typing import Dict, Optional, List, Set
from decimal import Decimal
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from app.services.redis_manager import redis_manager  # distributed lock
from app.trading.idempotency_store import get_idempotency_store, generate_client_oid

# DOC-04 — importados com try/except para evitar erros se módulos ausentes
try:
    from app.trading.distributed_lock import DistributedLock
    from app.trading.balance_reservation import BalanceReservationSystem
except ImportError:
    DistributedLock = None  # type: ignore[assignment,misc]
    BalanceReservationSystem = None  # type: ignore[assignment,misc]

# DOC-06 — métricas de ordens
try:
    from app.observability.metrics import (
        trading_orders_total,
        trading_order_latency_ms,
    )
    _ORDER_METRICS_OK = True
except Exception:
    _ORDER_METRICS_OK = False

logger = logging.getLogger(__name__)

# ─── Exceção compartilhada com OrderQueueConsumer (DOC-04) ───────────────────
class TerminalOrderError(Exception):
    """Rejeição permanente — OrderQueueConsumer faz XACK sem retentar."""


# ─── Erros KuCoin que NÃO devem ser retentados (definitivos) ──────────────────
# Ref: https://docs.kucoin.com/#errors
TERMINAL_ERROR_CODES: Set[str] = {
    "400100",  # Order size too small
    "400200",  # Insufficient balance
    "400300",  # Order price precision error
    "400500",  # Order price too high
    "400600",  # Order price too low
    "400700",  # Order amount below minimum
    "900014",  # Invalid symbol
    "200004",  # Insufficient funds
    "300000",  # Order already exists (same clientOid)
}


class OrderExecutionStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class OrderRequest:
    """Requisição de ordem interna."""
    order_id: str
    symbol: str
    side: str
    size: Decimal
    order_type: str
    price: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderExecutionResult:
    """Resultado da execução."""
    order_request_id: str
    kucoin_order_id: str
    status: OrderExecutionStatus
    filled: Decimal = Decimal("0")
    error: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrderQueue:
    """Fila interna com atomicidade garantida."""
    
    def __init__(self):
        self.pending: Dict[str, OrderRequest] = {}
        self.executing: Dict[str, OrderRequest] = {}
        self.executed: Dict[str, OrderExecutionResult] = {}
        self.lock = asyncio.Lock()
    
    async def enqueue(self, request: OrderRequest) -> str:
        """Adiciona ordem à fila."""
        async with self.lock:
            request_id = request.order_id
            
            # Verifica duplicata
            if request_id in self.pending or request_id in self.executing:
                logger.warning(f"⚠️ Ordem duplicada: {request_id}")
                return request_id  # Retorna existente
            
            self.pending[request_id] = request
            logger.info(f"📝 Ordem enfileirada: {request_id}")
            return request_id
    
    async def mark_executing(self, request_id: str) -> bool:
        """Move para executando."""
        async with self.lock:
            if request_id not in self.pending:
                return False
            
            request = self.pending.pop(request_id)
            self.executing[request_id] = request
            logger.info(f"⚙️ Executando: {request_id}")
            return True
    
    async def mark_executed(
        self,
        request_id: str,
        result: OrderExecutionResult,
    ) -> None:
        """Move para executada."""
        async with self.lock:
            if request_id in self.executing:
                del self.executing[request_id]
            
            self.executed[request_id] = result
            logger.info(f"✅ Executada: {request_id} → KuCoin {result.kucoin_order_id}")
    
    async def get_pending(self) -> List[OrderRequest]:
        """Retorna cópia das pendentes."""
        async with self.lock:
            return list(self.pending.values())
    
    async def is_duplicate(self, request_id: str) -> bool:
        """Verifica se ordem já foi processada."""
        async with self.lock:
            return request_id in self.executed or request_id in self.executing


class OrderManager:
    """
    Gerencia ordens com retry, idempotência e lock por símbolo.

    Garante:
    - Uma ordem nunca é duplicada (idempotência via clientOid InMemory + DB)
    - Lock por símbolo: apenas 1 ordem por símbolo em paralelo
    - Retry automático com backoff
    - Atualização de status via WebSocket (sem 2º request REST)
    - TP/SL sincronizado
    - Estado consistente
    """

    def __init__(
        self,
        trading_engine,
        max_retries: int = 3,
        dist_lock=None,             # Optional[DistributedLock]   — DOC-04
        balance_reservation=None,   # Optional[BalanceReservationSystem] — DOC-04
    ):
        self.engine = trading_engine
        self.queue = OrderQueue()
        self.max_retries = max_retries
        self.base_backoff = 1.0

        # Lock por símbolo: evita race condition / overtrading
        self._symbol_locks: Dict[str, asyncio.Lock] = {}
        self._symbol_locks_mutex = asyncio.Lock()

        # Mapa clientOid → kucoin_order_id (atualizado por WS)
        self._ws_execution_updates: Dict[str, Dict] = {}

        # DOC-04: locks distribuídos multinível e reserva de saldo
        self._dist_lock = dist_lock
        self._balance_reservation = balance_reservation

        logger.info("✅ OrderManager inicializado")

    async def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        """Retorna (criando se necessário) o lock para um símbolo."""
        async with self._symbol_locks_mutex:
            if symbol not in self._symbol_locks:
                self._symbol_locks[symbol] = asyncio.Lock()
            return self._symbol_locks[symbol]

    async def on_ws_execution(self, event: Dict) -> None:
        """
        Callback chamado pelo WebSocketManager quando chega um execution report.

        Elimina a necessidade de fazer GET /orders após POST.
        Registra o update e notifica qualquer waiter.
        """
        client_oid = event.get("client_oid", "")
        if client_oid:
            self._ws_execution_updates[client_oid] = event
            logger.info(
                f"📩 Execution report via WS: {client_oid} "
                f"status={event.get('status')} filled={event.get('filled_size')}"
            )

    async def execute_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        order_type: str = "market",
        price: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        pre_persisted_client_oid: Optional[str] = None,
    ) -> OrderExecutionResult:
        """
        Executa ordem com lock por símbolo, retry e idempotência.

        Args:
            pre_persisted_client_oid: clientOid já salvo no banco como PENDING.
                Se fornecido, qualquer retry verifica via API se a ordem já chegou
                (evita duplicata). Caso None, um novo UUID é gerado.

        ⭐ BOAS PRÁTICAS:
            Sempre salve a ordem no banco com status=PENDING ANTES de chamar este
            método, passando o clientOid gerado:

            client_oid = str(uuid.uuid4())
            await order_service.create_pending(client_oid, ...)
            result = await order_manager.execute_order(
                ..., pre_persisted_client_oid=client_oid
            )
        """

        # Cria requisição
        request_id = pre_persisted_client_oid or str(uuid.uuid4())
        # DOC-06: timer de latência
        _t0 = time.perf_counter()
        _order_status = "failed"
        request = OrderRequest(
            order_id=request_id,
            symbol=symbol,
            side=side,
            size=size,
            order_type=order_type,
            price=price,
            take_profit=take_profit,
            stop_loss=stop_loss,
        )

        # ⭐ Verificação de idempotência via Redis (SET NX)
        idempotency = get_idempotency_store()
        idempotency_payload = {
            "symbol": symbol, "side": side,
            "size": str(size), "order_type": order_type,
        }
        idem_result = await idempotency.check_and_set(request_id, idempotency_payload)
        if idem_result.is_duplicate:
            existing = idem_result.existing_result or {}
            existing_order_id = existing.get("order_id", "")
            logger.info(
                "⭐ Ordem idempotente: clientOid=%s já processado (orderId=%s)",
                request_id, existing_order_id,
            )
            return OrderExecutionResult(
                order_request_id=request_id,
                kucoin_order_id=existing_order_id,
                status=OrderExecutionStatus.EXECUTED,
            )

        # Enfileira
        await self.queue.enqueue(request)

        # ⭐ Lock distribuído por símbolo: evita race condition entre workers
        # Usa Redis quando disponível (multi-worker); asyncio.Lock como fallback
        redis_lock_key = f"lock:order:symbol:{symbol}"
        redis_acquired = False

        if redis_manager.redis_client is not None:
            redis_acquired = await redis_manager.acquire_lock(
                redis_lock_key, timeout_seconds=30, max_retries=5, retry_delay=0.5
            )
            if not redis_acquired:
                raise Exception(
                    f"Não foi possível adquirir lock distribuído para {symbol}. "
                    "Outra ordem está em execução. Tente novamente em instantes."
                )

        try:
            # Fallback: lock em memória (loop single-worker ou Redis offline)
            sym_lock = await self._get_symbol_lock(symbol)
            async with sym_lock:
                result = None
                for attempt in range(1, self.max_retries + 1):
                    try:
                        if not await self.queue.mark_executing(request_id):
                            logger.warning(f"⚠️ Ordem {request_id} já foi executada")
                            if request_id in self.queue.executed:
                                return self.queue.executed[request_id]
                            raise Exception("Ordem perdida na fila")

                        # Executa chamada à API
                        if order_type == "market":
                            result = await self._execute_market_order(request, request_id)
                        elif order_type == "limit":
                            result = await self._execute_limit_order(request, request_id)
                        else:
                            raise ValueError(f"Tipo de ordem inválido: {order_type}")

                        await self.queue.mark_executed(request_id, result)
                        # Marca sucesso no IdempotencyStore
                        await idempotency.mark_completed(
                            request_id, result.kucoin_order_id, "SENT"
                        )
                        _order_status = "success"
                        return result

                    except Exception as e:
                        logger.error(f"❌ Tentativa {attempt}/{self.max_retries} falhou: {e}")

                        # ⭐ Erros terminais: não faz retry
                        error_code = _extract_kucoin_error_code(e)
                        if error_code and error_code in TERMINAL_ERROR_CODES:
                            logger.error(
                                "🚫 Erro terminal KuCoin %s — sem retry. Motivo: %s",
                                error_code, str(e),
                            )
                            await idempotency.mark_failed(request_id, str(e))
                            result = OrderExecutionResult(
                                order_request_id=request_id,
                                kucoin_order_id="",
                                status=OrderExecutionStatus.FAILED,
                                error=f"Terminal error {error_code}: {e}",
                            )
                            await self.queue.mark_executed(request_id, result)
                            raise

                        if attempt < self.max_retries:
                            wait_time = self.base_backoff * (2 ** (attempt - 1))
                            logger.info(f"⏳ Aguardando {wait_time}s antes de retry...")
                            await asyncio.sleep(wait_time)
                        else:
                            # Esgotou tentativas — falha definitiva
                            await idempotency.mark_failed(request_id, str(e))
                            result = OrderExecutionResult(
                                order_request_id=request_id,
                                kucoin_order_id="",
                                status=OrderExecutionStatus.FAILED,
                                error=str(e),
                            )
                            await self.queue.mark_executed(request_id, result)
                            raise

            raise Exception("Execution flow error")
        finally:
            # DOC-06: observa latência e incrementa contador
            if _ORDER_METRICS_OK:
                try:
                    _lat = (time.perf_counter() - _t0) * 1_000
                    trading_order_latency_ms.labels(
                        symbol=symbol, type=order_type
                    ).observe(_lat)
                    trading_orders_total.labels(
                        status=_order_status,
                        symbol=symbol,
                        side=side,
                        type=order_type,
                        user_id="",
                    ).inc()
                except Exception:
                    pass
            if redis_acquired:
                await redis_manager.release_lock(redis_lock_key)
    
    async def _execute_market_order(
        self,
        request: OrderRequest,
        request_id: str,
    ) -> OrderExecutionResult:
        """Executa ordem de mercado."""
        normalized_order = await self.engine.place_market_order(
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            take_profit=request.take_profit,
            stop_loss=request.stop_loss,
            client_oid=request_id,  # ⭐ Idempotência
        )

        return OrderExecutionResult(
            order_request_id=request_id,
            kucoin_order_id=normalized_order.order_id,
            status=OrderExecutionStatus.EXECUTED,
            filled=normalized_order.filled,
        )

    async def _execute_limit_order(
        self,
        request: OrderRequest,
        request_id: str,
    ) -> OrderExecutionResult:
        """Executa ordem limite."""
        if not request.price:
            raise ValueError("Preço obrigatório para ordem limite")

        normalized_order = await self.engine.place_limit_order(
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            price=request.price,
            client_oid=request_id,  # ⭐ Idempotência
        )

        return OrderExecutionResult(
            order_request_id=request_id,
            kucoin_order_id=normalized_order.order_id,
            status=OrderExecutionStatus.EXECUTED,
            filled=normalized_order.filled,
        )

    # ── DOC-04: safe_process_order (Níveis 1-3) ─────────────────────────────

    async def safe_process_order(
        self,
        signal_id: str,
        bot_id: str,
        user_id: str,
        strategy_id: str,
        symbol: str,
        side: str,
        order_type: str,
        size: Decimal,
        price: Optional[Decimal] = None,
        currency: str = "USDT",
        kucoin_client: Optional[object] = None,
    ) -> "OrderExecutionResult":
        """
        Executa ordem com proteção multinível contra race conditions (DOC-04):

          Nível 1 — Idempotency Store (Redis SET NX)         — em execute_order()
          Nível 2 — Bot Lock  lock:bot:{botId}  TTL 30s      max_wait 30s
          Nível 3 — Balance Lock lock:balance:{userId} TTL 15s max_wait 10s
                    + BalanceReservationSystem.reserve()
          Nível 4 — Redis Stream (XADD/XREADGROUP)           — OrderQueueConsumer

        Args:
            signal_id:     ID único do sinal (seed para clientOid determinístico)
            bot_id:        ID do bot trader
            user_id:       ID do usuário dono da conta
            strategy_id:   ID da estratégia
            symbol:        Par de trading (ex: "BTC-USDT")
            side:          "buy" | "sell"
            order_type:    "market" | "limit"
            size:          Quantidade base
            price:         Preço para limite; None para mercado
            currency:      Moeda de cotação da reserva (ex: "USDT")
            kucoin_client: KuCoinClient para buscar saldo real (Nível 3)

        Raises:
            TerminalOrderError: saldo insuficiente ou validação permanente
            RuntimeError:       lock não adquirido dentro do timeout
        """
        # clientOid determinístico: mesmo sinal+bot → mesmo oid → idempotente
        client_oid = generate_client_oid(signal_id, bot_id)

        lock = self._dist_lock
        if lock is None:
            logger.warning(
                "safe_process_order: sem DistributedLock — "
                "executando sem Níveis 2/3 (signal=%s)",
                signal_id,
            )
            return await self.execute_order(
                symbol=symbol, side=side, size=size,
                order_type=order_type, price=price,
                pre_persisted_client_oid=client_oid,
            )

        # ── Nível 2: Bot Lock ─────────────────────────────────────────────────
        async with lock.acquire_ctx(
            f"bot:{bot_id}", ttl_ms=30_000, max_wait_ms=30_000
        ):
            reservation_id: Optional[str] = None

            # ── Nível 3: Balance Lock + Reserva ──────────────────────────────
            if self._balance_reservation is not None:
                async with lock.acquire_ctx(
                    f"balance:{user_id}", ttl_ms=15_000, max_wait_ms=10_000
                ):
                    res = await self._balance_reservation.reserve(
                        user_id=user_id,
                        bot_id=bot_id,
                        currency=currency,
                        amount=size,
                        reservation_id=client_oid,
                        kucoin_client=kucoin_client,
                    )
                    if not res["success"]:
                        raise TerminalOrderError(res["reason"])
                    reservation_id = client_oid
                # ← balance lock liberado aqui
            else:
                logger.debug(
                    "safe_process_order: sem BalanceReservationSystem "
                    "— pulando Nível 3 (signal=%s)", signal_id,
                )

            # ── Envia ordem (dentro do Bot Lock, fora do Balance Lock) ────────
            try:
                result = await self.execute_order(
                    symbol=symbol,
                    side=side,
                    size=size,
                    order_type=order_type,
                    price=price,
                    pre_persisted_client_oid=client_oid,
                )
            finally:
                # Libera reserva virtual sempre — sucesso ou falha
                if reservation_id is not None and self._balance_reservation is not None:
                    await self._balance_reservation.release(
                        user_id, currency, reservation_id
                    )

            return result

    # ─────────────────────────────────────────────────────────────────────────

    async def get_order_status(self, request_id: str) -> Optional[OrderExecutionResult]:
        """Retorna status de uma ordem."""
        if request_id in self.queue.executed:
            return self.queue.executed[request_id]
        return None
    
    async def get_pending_orders(self) -> List[OrderRequest]:
        """Retorna ordens ainda pendentes."""
        return await self.queue.get_pending()
    
    async def cancel_order(self, request_id: str) -> bool:
        """Cancela uma ordem pendente."""
        async with self.queue.lock:
            if request_id in self.queue.pending:
                del self.queue.pending[request_id]
                logger.info(f"❌ Ordem cancelada: {request_id}")
                return True
            return False


# Instância global
order_manager: Optional[OrderManager] = None

def init_order_manager(
    trading_engine,
    dist_lock=None,
    balance_reservation=None,
):
    global order_manager
    order_manager = OrderManager(
        trading_engine,
        dist_lock=dist_lock,
        balance_reservation=balance_reservation,
    )
    return order_manager

def get_order_manager() -> OrderManager:
    """Get the global OrderManager instance."""
    global order_manager
    if order_manager is None:
        raise RuntimeError("OrderManager not initialized. Call init_order_manager() first.")
    return order_manager


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_kucoin_error_code(exc: Exception) -> Optional[str]:
    """
    Extrai o código de erro KuCoin de uma exceção HTTP.

    KuCoin retorna erros como:
      { "code": "400200", "msg": "Insufficient balance" }
    em respostas com status 4xx.
    """
    # httpx / requests style
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            data = response.json() if callable(getattr(response, "json", None)) else {}
            code = data.get("code") or data.get("error_code")
            return str(code) if code else None
        except Exception:
            pass
    # Mensagem direta (alguns wrappers colocam o código no str)
    msg = str(exc)
    for part in msg.split():
        if part.isdigit() and len(part) == 6:
            return part
    return None
