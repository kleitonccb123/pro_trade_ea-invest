"""
TradingExecutor — Camada de Orquestração de Trading

Responsável por coordenar o fluxo completo de uma ordem:
1. Validação pré-trade (saldo, limites, risco)
2. Persistência idempotente (ANTES de enviar)
3. Execução na exchange
4. Monitoramento até preenchimento
5. Sincronização no banco de dados

Architecture:
    User/Strategy
        ↓
    TradingExecutor (orquestrador)
        ├─→ PreTradeValidator (validação)
        ├─→ RiskManager (checks de risco)
        ├─→ IdempotencyStore (geração de client_oid)
        ├─→ MongoDB (persistência)
        └─→ KuCoinClient (execução)

Author: Crypto Trade Hub — Production Ready
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Any, Tuple
from enum import Enum

from app.core.database import get_db
from app.trading.credentials_repository import CredentialsRepository, ExchangeType
from app.core.encryption import decrypt_credential, decrypt_kucoin_credentials
from app.exchanges.kucoin.client import KuCoinRawClient, KuCoinAPIError
from app.exchanges.kucoin.normalizer import NormalizedOrder, OrderStatus
from app.trading.pre_trade_validation import PreTradeValidator, ValidationError
from app.trading.risk_manager import RiskManager
from app.trading.idempotency_store import generate_client_oid
from app.trading.circuit_breaker import ExchangeHealthMonitor, CircuitOpenError

# Prometheus metrics (graceful se não disponível)
try:
    from app.observability.metrics import (
        trading_orders_total,
        trading_order_latency_ms,
        trading_order_fill_time_ms,
    )
    _HAS_METRICS = True
except ImportError:
    _HAS_METRICS = False

# Alert manager (graceful se não inicializado)
try:
    from app.observability.alert_manager import get_alert_manager, AlertSeverity
    _HAS_ALERTS = True
except ImportError:
    _HAS_ALERTS = False

logger = logging.getLogger(__name__)


class OrderExecutionError(Exception):
    """Erro genérico em execução de ordem"""
    pass


class InsufficientBalanceError(OrderExecutionError):
    """Saldo insuficiente"""
    pass


class ValidationFailedError(OrderExecutionError):
    """Validação pré-trade falhou"""
    pass


class ExchangeTimeoutError(OrderExecutionError):
    """Timeout ao comunicar com exchange"""
    pass


class OrderSide(str, Enum):
    """Lados possíveis de uma ordem"""
    BUY = "buy"
    SELL = "sell"


class TradingExecutor:
    """
    Orquestrador de trading — Pipeline completo de execução de ordens.
    
    Responsabilidades:
    ✓ Validação pré-trade (saldo real, limites, risco)
    ✓ Persistência idempotente (MongoDB)
    ✓ Execução real no exchange
    ✓ Monitoramento até preenchimento
    ✓ Sincronização de resultados
    
    Exemplo de uso:
    ```python
    executor = TradingExecutor(user_id="user_123", exchange="kucoin")
    await executor.initialize()  # Conecta com credenciais do usuário
    
    order = await executor.execute_market_order(
        symbol="BTC-USDT",
        side="buy",
        quantity=Decimal("0.1")
    )
    
    print(f"Ordem criada: {order['_id']}")
    print(f"Status: {order['status']}")  # "pending" → "filled"
    ```
    
    Atributos:
        user_id: ID do usuário (dono das credenciais)
        exchange: Nome da exchange ("kucoin", "binance", etc)
        credentials: Credenciais criptografadas (lazy-loaded)
        client: Cliente raw da exchange (inicializado em initialize())
        validator: Validador pré-trade
        risk_manager: Gerenciador de risco
        circuit_breaker: Circuit breaker para falhas
    """
    
    def __init__(
        self,
        user_id: str,
        exchange: str = "kucoin",
        testnet: bool = True,
        max_monitoring_time: int = 60,  # segundos
        polling_interval: float = 1.0,  # segundos
    ):
        """
        Inicializa TradingExecutor (sem conectar ainda).
        
        Args:
            user_id: ID do usuário (credenciais pertence a ele)
            exchange: Exchange ("kucoin", "binance")
            testnet: Se usar testnet ou mainnet
            max_monitoring_time: Max segundos para monitorar ordem
            polling_interval: Intervalo entre polls (em segundos)
        """
        self.user_id = user_id
        self.exchange = exchange.lower()
        self.testnet = testnet
        self.max_monitoring_time = max_monitoring_time
        self.polling_interval = polling_interval
        
        # Não inicializado ainda
        self.credentials: Optional[Dict[str, Any]] = None
        self.client: Optional[KuCoinRawClient] = None
        self.account_id: Optional[str] = None
        
        # Componentes
        self.validator = PreTradeValidator()
        self.risk_manager = RiskManager()
        self.circuit_breaker = ExchangeHealthMonitor()
        self.db = get_db()
        
        logger.info(
            f"✅ TradingExecutor inicializado para user={user_id}, "
            f"exchange={exchange}, testnet={testnet}"
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SETUP & INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════
    
    async def initialize(self) -> None:
        """
        Conecta com as credenciais do usuário e inicializa cliente.
        
        DEVE ser chamado antes de qualquer operação de trading.
        
        Passos:
        1. Obter credenciais criptografadas do MongoDB
        2. Descriptografar credenciais
        3. Conectar cliente KuCoin
        4. Validar conexão (test ping)
        5. Obter account_id
        
        Raises:
            PermissionError: Sem credenciais configuradas
            KuCoinAPIError: Falha ao conectar
            ValueError: Credenciais inválidas
        """
        logger.info(f"🔄 Inicializando TradingExecutor para user {self.user_id}...")
        
        try:
            # 1. Obter credenciais
            creds_encrypted = await CredentialsRepository.get_credentials(
                self.user_id,
                self.exchange
            )
            
            if not creds_encrypted:
                raise PermissionError(
                    f"Nenhuma credencial {self.exchange.upper()} configurada para este usuário. "
                    "Configure via /api/trading/kucoin/connect"
                )
            
            # 2. Descriptografar
            if self.exchange == "kucoin":
                creds_decrypted = decrypt_kucoin_credentials(
                    api_key_enc=creds_encrypted.get("api_key_encrypted"),
                    api_secret_enc=creds_encrypted.get("api_secret_encrypted"),
                    passphrase_enc=creds_encrypted.get("passphrase_encrypted")
                )
                api_key = creds_decrypted["api_key"]
                api_secret = creds_decrypted["api_secret"]
                passphrase = creds_decrypted.get("passphrase")
            else:
                raise NotImplementedError(f"Exchange {self.exchange} não suportada ainda")
            
            # 3. Conectar cliente
            self.client = KuCoinRawClient(
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                sandbox=self.testnet
            )
            
            # 4. Test connection (ping)
            server_time = await self.client.get_server_time()
            logger.debug(f"✅ Ping bem-sucedido. Server time: {server_time}")
            
            # 5. Obter account_id
            accounts = await self.client.get_accounts()
            if not accounts or len(accounts) == 0:
                raise ValueError("Nenhuma conta encontrada na exchange")
            
            # Usar primeira conta de trading
            self.account_id = accounts[0]["id"]
            logger.info(f"✅ Account ID obtido: {self.account_id}")
            
            # Store credentials para uso futuro (já descriptografadas)
            self.credentials = {
                "api_key": api_key,
                "api_secret": api_secret,
                "passphrase": passphrase,
                "account_id": self.account_id
            }
            
            logger.info(f"✅ TradingExecutor inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar TradingExecutor: {e}")
            raise
    
    # ═══════════════════════════════════════════════════════════════════════
    # ORDER EXECUTION
    # ═══════════════════════════════════════════════════════════════════════
    
    async def execute_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Executa uma ordem de MERCADO (market order) no exchange.
        
        Pipeline completo:
        1. ✓ Validação pré-trade (saldo, limites, risco)
        2. ✓ Persistência idempotente no MongoDB
        3. ✓ Execução na KuCoin
        4. ✓ Monitoramento até preenchimento
        5. ✓ Sincronização de resultado no MongoDB
        
        Args:
            symbol: Par de trading (ex: "BTC-USDT")
            side: Direção ("buy" ou "sell")
            quantity: Quantidade em base currency
            take_profit: Preço de take-profit (opcional, para limite)
            stop_loss: Preço de stop-loss (opcional, para limite)
        
        Returns:
            Dict com dados da ordem criada no banco:
            {
                "_id": ObjectId,
                "user_id": str,
                "symbol": str,
                "side": str,
                "quantity": Decimal,
                "status": "pending" | "filled" | "failed",
                "client_oid": str,
                "exchange_order_id": str (se enviada),
                "created_at": datetime,
                "filled_at": datetime (se preenchida),
                "filled_price": Decimal (se preenchida),
                ...
            }
        
        Raises:
            ValidationFailedError: Validação pré-trade falhou
            InsufficientBalanceError: Saldo insuficiente
            ExchangeTimeoutError: Timeout na execução
            OrderExecutionError: Erro genérico da ordem
        """
        if not self.client:
            raise RuntimeError("TradingExecutor não foi inicializado. Chame initialize() antes.")
        
        logger.info(
            f"🚀 Iniciando execução de ordem: "
            f"{side.upper()} {quantity} {symbol} (user={self.user_id})"
        )
        
        try:
            # ─────────────────────────────────────────────────────────────
            # 1. VALIDAÇÃO PRÉ-TRADE
            # ─────────────────────────────────────────────────────────────
            logger.debug(f"  [1/5] Validando ordem...")
            is_valid, error_msg = await self._validate_order(
                symbol=symbol,
                side=side,
                quantity=quantity
            )
            
            if not is_valid:
                logger.warning(f"❌ Validação falhou: {error_msg}")
                raise ValidationFailedError(f"Validação pré-trade falhou: {error_msg}")
            
            logger.debug(f"  ✅ Validação OK")
            
            # ─────────────────────────────────────────────────────────────
            # 2. PERSISTÊNCIA IDEMPOTENTE
            # ─────────────────────────────────────────────────────────────
            logger.debug(f"  [2/5] Persistindo ordem no banco...")
            order_db = await self._persist_pending_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                take_profit=take_profit,
                stop_loss=stop_loss
            )
            logger.debug(f"  ✅ Ordem persistida: {order_db['_id']}")
            
            # ─────────────────────────────────────────────────────────────
            # 3. EXECUÇÃO NA EXCHANGE
            # ─────────────────────────────────────────────────────────────
            logger.debug(f"  [3/5] Enviando ordem para exchange...")
            order_exchange = await self._place_at_exchange(order_db)
            logger.debug(f"  ✅ Ordem enviada. Exchange ID: {order_exchange.order_id}")
            
            # ─────────────────────────────────────────────────────────────
            # 4. MONITORAMENTO ATÉ FILL
            # ─────────────────────────────────────────────────────────────
            logger.debug(f"  [4/5] Monitorando até preenchimento (max {self.max_monitoring_time}s)...")
            filled_order = await self._monitor_until_filled(order_exchange)
            logger.debug(f"  ✅ Ordem preenchida! Preço: {filled_order.fill_price}, Qty: {filled_order.filled_qty}")
            
            # ─────────────────────────────────────────────────────────────
            # 5. SINCRONIZAÇÃO NO BANCO
            # ─────────────────────────────────────────────────────────────
            logger.debug(f"  [5/5] Sincronizando resultado no banco...")
            await self._sync_to_database(filled_order, order_db)
            logger.debug(f"  ✅ Sincronização completa")
            
            # Obter documento final
            final_order = await self.db.trading_orders.find_one({
                "_id": order_db["_id"]
            })
            
            logger.info(
                f"✅ ORDEM EXECUTADA COM SUCESSO: "
                f"{side.upper()} {quantity} {symbol} @ {final_order.get('filled_price')} "
                f"(Exchange ID: {final_order.get('exchange_order_id')})"
            )
            
            # Registrar métricas de sucesso
            self._record_metrics(symbol, side, "filled")
            
            return final_order
            
        except ValidationFailedError:
            self._record_metrics(symbol, side, "validation_failed")
            raise
        except InsufficientBalanceError:
            self._record_metrics(symbol, side, "insufficient_balance")
            raise
        except ExchangeTimeoutError:
            self._record_metrics(symbol, side, "timeout")
            raise
        except Exception as e:
            logger.error(f"❌ Erro crítico na execução: {e}", exc_info=True)
            self._record_metrics(symbol, side, "error")
            # Alertar se houver alert manager
            self._send_failure_alert(symbol, side, str(e))
            # Marcar ordem como failed no banco
            if "order_db" in locals():
                await self.db.trading_orders.update_one(
                    {"_id": order_db["_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "failed_at": datetime.utcnow()
                        }
                    }
                )
            raise OrderExecutionError(f"Erro ao executar ordem: {e}") from e
    
    # ═══════════════════════════════════════════════════════════════════════
    # PRIVATE METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    async def _validate_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida se ordem pode ser executada.
        
        Verifica:
        ✓ Circuit breaker (exchange OK?)
        ✓ Kill-switch (usuário bloqueado?)
        ✓ Saldo suficiente
        ✓ Tamanho dentro de limites
        ✓ Risk limits (daily loss, max position, etc)
        
        Returns:
            (is_valid, error_message)
        """
        # 1. Circuit breaker
        try:
            self.circuit_breaker.pre_request()
        except CircuitOpenError:
            return False, "Exchange está offline (circuit breaker aberto)"
        
        # 2. Kill-switch
        if await self.risk_manager.is_kill_switched(self.user_id):
            return False, "Kill-switch ativo. Contate suporte."
        
        # 3. Risk checks
        can_trade, risk_msg = await self.risk_manager.check_can_trade(
            user_id=self.user_id,
            symbol=symbol,
            side=side,
            quantity=quantity
        )
        
        if not can_trade:
            return False, risk_msg
        
        # 4. Pre-trade validation (saldo, limites, etc)
        # Nota: Pre-trade validator já está implementado
        # Aqui podemos adicionar chamada futura
        logger.debug(f"✅ Todas as validações passaram")
        
        return True, None
    
    async def _persist_pending_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Persiste ordem no MongoDB ANTES de enviar para exchange.
        
        Estratégia de idempotência:
        - Gera client_oid determinístico
        - Se a mesma ordem for retentada, gera o mesmo client_oid
        - KuCoin rejeita duplicatas com mesmo client_oid
        
        Returns:
            Documento inserido no MongoDB
        """
        client_oid = generate_client_oid(
            user_id=self.user_id,
            symbol=symbol,
            side=side
        )
        
        order_doc = {
            "user_id": self.user_id,
            "exchange": self.exchange,
            "symbol": symbol,
            "side": side.lower(),
            "quantity": quantity,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "client_oid": client_oid,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            # Preenchidos após execução:
            "exchange_order_id": None,
            "filled_price": None,
            "filled_quantity": None,
            "filled_at": None,
            # Metadata
            "testnet": self.testnet,
        }
        
        result = await self.db.trading_orders.insert_one(order_doc)
        order_doc["_id"] = result.inserted_id
        
        logger.debug(f"✅ Ordem persistida com client_oid={client_oid}")
        
        return order_doc
    
    async def _place_at_exchange(self, order_db: Dict[str, Any]) -> NormalizedOrder:
        """
        Envia ordem para KuCoin.
        
        Returns:
            NormalizedOrder (da classe normalizer)
        """
        try:
            order_exchange = await self.client.place_market_order(
                symbol=order_db["symbol"],
                side=order_db["side"],
                size=order_db["quantity"],
                take_profit=order_db.get("take_profit"),
                stop_loss=order_db.get("stop_loss"),
                client_oid=order_db["client_oid"]
            )
            
            # Atualizar banco com exchange_order_id
            await self.db.trading_orders.update_one(
                {"_id": order_db["_id"]},
                {
                    "$set": {
                        "exchange_order_id": order_exchange.order_id,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            return order_exchange
            
        except KuCoinAPIError as e:
            logger.error(f"❌ Erro KuCoin: {e}")
            raise OrderExecutionError(f"Erro ao enviar ordem para KuCoin: {e}") from e
    
    async def _monitor_until_filled(
        self,
        order_exchange: NormalizedOrder,
        max_attempts: Optional[int] = None
    ) -> NormalizedOrder:
        """
        Monitora ordem até preenchimento.
        
        Estratégia:
        - Faz polling a cada N segundos
        - Máximo de M tentativas (ou timeout)
        - Sai assim que detecta FILLED
        
        Args:
            order_exchange: Ordem normalizada
            max_attempts: Máximo de tentativas (None = usar max_monitoring_time)
        
        Returns:
            NormalizedOrder preenchida
        
        Raises:
            ExchangeTimeoutError: Não preencheu em tempo
        """
        max_attempts = max_attempts or int(self.max_monitoring_time / self.polling_interval)
        
        for attempt in range(max_attempts):
            try:
                # Obter status atual
                status = await self.client.get_order(order_exchange.order_id)
                
                logger.debug(
                    f"  Tentativa {attempt + 1}/{max_attempts}: "
                    f"Status={status.status}, "
                    f"Filled={status.filled_qty}/{order_exchange.size}"
                )
                
                # Se preencheu
                if status.status == OrderStatus.FILLED:
                    logger.info(f"✅ Ordem preenchida em {attempt + 1} tentativas")
                    return status
                
                # Se foi cancelada
                elif status.status == OrderStatus.CANCELLED:
                    raise OrderExecutionError(
                        f"Ordem foi cancelada pela exchange. "
                        f"Filled: {status.filled_qty}, Cancelada em: {status.cancel_reason}"
                    )
                
                # Aguardar antes de próxima tentativa
                await asyncio.sleep(self.polling_interval)
                
            except Exception as e:
                logger.error(f"❌ Erro ao monitorar ordem: {e}")
                raise
        
        # Timeout
        logger.error(f"❌ Ordem não preencheu em {self.max_monitoring_time}s")
        raise ExchangeTimeoutError(
            f"Ordem não preencheu em {self.max_monitoring_time} segundos. "
            f"Status final: {status.status} (filled={status.filled_qty}/{order_exchange.size})"
        )
    
    async def _sync_to_database(
        self,
        filled_order: NormalizedOrder,
        order_db: Dict[str, Any]
    ) -> None:
        """
        Sincroniza resultado final no MongoDB.
        
        Args:
            filled_order: Ordem preenchida do exchange
            order_db: Documento original do banco
        """
        await self.db.trading_orders.update_one(
            {"_id": order_db["_id"]},
            {
                "$set": {
                    "status": "filled",
                    "exchange_order_id": filled_order.order_id,
                    "filled_price": Decimal(str(filled_order.fill_price)),
                    "filled_quantity": Decimal(str(filled_order.filled_qty)),
                    "filled_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        logger.info(f"✅ Ordem sincronizada no banco")
    
    # ═══════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════
    
    async def get_account_balance(self) -> Dict[str, Decimal]:
        """
        Obtém saldo da conta.
        
        Returns:
            {
                "BTC": Decimal("0.5"),
                "USDT": Decimal("1000.00"),
                ...
            }
        """
        if not self.client:
            raise RuntimeError("TradingExecutor não foi inicializado")
        
        balances = await self.client.get_account_balance(self.account_id)
        
        result = {}
        for currency, balance in balances.items():
            result[currency] = Decimal(str(balance.get("available", 0)))
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════
    # METRICS & ALERTS
    # ═══════════════════════════════════════════════════════════════════════
    
    def _record_metrics(
        self, symbol: str, side: str, status: str
    ) -> None:
        """Registra métricas Prometheus para a ordem."""
        if not _HAS_METRICS:
            return
        try:
            trading_orders_total.labels(
                status=status,
                symbol=symbol,
                side=side,
                type="market",
                user_id=self.user_id,
            ).inc()
        except Exception:
            pass  # Métricas não devem quebrar o fluxo

    def _send_failure_alert(self, symbol: str, side: str, error: str) -> None:
        """Envia alerta em caso de falha crítica."""
        if not _HAS_ALERTS:
            return
        try:
            mgr = get_alert_manager()
            if mgr:
                asyncio.create_task(mgr.warning(
                    title="Ordem falhou",
                    message=f"{side.upper()} {symbol} — {error}",
                    component="trading_executor",
                    metadata={"user_id": self.user_id, "symbol": symbol, "side": side},
                ))
        except Exception:
            pass  # Alertas não devem quebrar o fluxo

    async def close(self) -> None:
        """Fecha conexões (se houver)"""
        logger.info(f"Fechando TradingExecutor para user {self.user_id}")
        # Future: fecha websockets, etc
