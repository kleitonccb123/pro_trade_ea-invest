"""
Financial Audit Module - Logs de Transa??es e Auditoria Financeira

Implementa:
1. Log detalhado de todas as transa??es (ordens, execu??es, taxas)
2. C?lculo de PnL real (descontando taxas)
3. Webhooks para alertas (Telegram, Discord)

Collections MongoDB:
- trade_logs: Registro detalhado de cada trade
- pnl_history: Hist?rico de PnL di?rio/por bot
- audit_events: Eventos de auditoria

Author: Crypto Trade Hub
"""

from __future__ import annotations

import asyncio
import logging
import hashlib
import httpx
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
from bson import ObjectId

from app.core.database import get_db

logger = logging.getLogger(__name__)


# ==================== ENUMS ====================

class TradeType(str, Enum):
    """Tipo de transa??o."""
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    FEE = "fee"
    FUNDING = "funding"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class AuditEventType(str, Enum):
    """Tipos de eventos de auditoria."""
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BOT_ERROR = "bot_error"
    CONFIG_CHANGED = "config_changed"
    CREDENTIALS_ADDED = "credentials_added"
    CREDENTIALS_REMOVED = "credentials_removed"
    LARGE_ORDER = "large_order"
    UNUSUAL_ACTIVITY = "unusual_activity"
    API_ERROR = "api_error"
    BALANCE_LOW = "balance_low"


# ==================== DATA MODELS ====================

@dataclass
class TradeLog:
    """Registro detalhado de uma transa??o."""
    user_id: str
    bot_id: Optional[str]
    exchange: str
    symbol: str
    trade_type: TradeType
    side: OrderSide
    
    # IDs
    order_id: str
    client_order_id: Optional[str] = None
    trade_id: Optional[str] = None
    
    # Valores
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    cost: Decimal = Decimal("0")           # quantity * price
    fee: Decimal = Decimal("0")
    fee_currency: str = "USDT"
    
    # Timestamps
    timestamp: datetime = None
    created_at: datetime = None
    
    # Status
    status: str = "filled"
    error_message: Optional[str] = None
    
    # Metadados
    raw_response: Optional[Dict] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.cost == 0 and self.quantity and self.price:
            self.cost = self.quantity * self.price
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["trade_type"] = self.trade_type.value
        result["side"] = self.side.value
        result["quantity"] = float(self.quantity)
        result["price"] = float(self.price)
        result["cost"] = float(self.cost)
        result["fee"] = float(self.fee)
        return result


@dataclass
class PnLRecord:
    """Registro de PnL."""
    user_id: str
    bot_id: Optional[str]
    exchange: str
    symbol: str
    
    # PnL
    realized_pnl: Decimal = Decimal("0")    # Lucro/Preju?zo realizado
    unrealized_pnl: Decimal = Decimal("0")  # Lucro/Preju?zo n?o realizado
    total_fees: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")         # PnL l?quido (- fees)
    
    # Estat?sticas
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Volume
    total_volume: Decimal = Decimal("0")
    buy_volume: Decimal = Decimal("0")
    sell_volume: Decimal = Decimal("0")
    
    # Per?odo
    period_start: datetime = None
    period_end: datetime = None
    
    def __post_init__(self):
        if self.period_start is None:
            self.period_start = datetime.utcnow()
        if self.period_end is None:
            self.period_end = datetime.utcnow()
        
        # Calcular PnL l?quido
        self.net_pnl = self.realized_pnl - self.total_fees
        
        # Calcular win rate
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100


# ==================== TRADE LOG REPOSITORY ====================

class TradeLogRepository:
    """Reposit?rio para logs de transa??es."""
    
    COLLECTION = "trade_logs"
    PNL_COLLECTION = "pnl_history"
    AUDIT_COLLECTION = "audit_events"
    
    @classmethod
    def _get_collection(cls, name: str = None):
        db = get_db()
        return db[name or cls.COLLECTION]
    
    @classmethod
    async def log_trade(cls, trade: TradeLog) -> str:
        """Registra uma transa??o."""
        collection = cls._get_collection()
        
        doc = trade.to_dict()
        doc["_hash"] = cls._generate_trade_hash(trade)
        
        result = await collection.insert_one(doc)
        
        logger.info(
            f"? Trade logged: {trade.exchange} {trade.symbol} "
            f"{trade.side.value} {trade.quantity} @ {trade.price} "
            f"(fee: {trade.fee} {trade.fee_currency})"
        )
        
        return str(result.inserted_id)
    
    @classmethod
    def _generate_trade_hash(cls, trade: TradeLog) -> str:
        """Gera hash ?nico para evitar duplica??o."""
        hash_input = f"{trade.exchange}:{trade.order_id}:{trade.trade_id or ''}:{trade.timestamp}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    @classmethod
    async def get_user_trades(
        cls,
        user_id: str,
        symbol: Optional[str] = None,
        bot_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Obt?m trades de um usu?rio."""
        collection = cls._get_collection()
        
        query = {"user_id": user_id}
        
        if symbol:
            query["symbol"] = symbol
        if bot_id:
            query["bot_id"] = bot_id
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        trades = await cursor.to_list(length=limit)
        
        # Serializar ObjectId
        for t in trades:
            t["_id"] = str(t["_id"])
        
        return trades
    
    @classmethod
    async def calculate_pnl(
        cls,
        user_id: str,
        symbol: Optional[str] = None,
        bot_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> PnLRecord:
        """
        Calcula PnL real para um usu?rio/bot.
        
        F?rmula: PnL = ?(Vendas) - ?(Compras) - Taxas
        """
        collection = cls._get_collection()
        
        query = {"user_id": user_id, "trade_type": TradeType.ORDER_FILLED.value}
        if symbol:
            query["symbol"] = symbol
        if bot_id:
            query["bot_id"] = bot_id
        
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        query["timestamp"] = {"$gte": start_date, "$lte": end_date}
        
        # Agregar por lado (buy/sell)
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$side",
                "total_cost": {"$sum": "$cost"},
                "total_fee": {"$sum": "$fee"},
                "total_volume": {"$sum": "$quantity"},
                "count": {"$sum": 1}
            }}
        ]
        
        results = {}
        async for doc in collection.aggregate(pipeline):
            results[doc["_id"]] = doc
        
        # Calcular PnL
        buy_data = results.get("buy", {"total_cost": 0, "total_fee": 0, "total_volume": 0, "count": 0})
        sell_data = results.get("sell", {"total_cost": 0, "total_fee": 0, "total_volume": 0, "count": 0})
        
        total_buys = Decimal(str(buy_data["total_cost"]))
        total_sells = Decimal(str(sell_data["total_cost"]))
        total_fees = Decimal(str(buy_data["total_fee"])) + Decimal(str(sell_data["total_fee"]))
        
        # PnL = Vendas - Compras - Fees
        realized_pnl = total_sells - total_buys
        net_pnl = realized_pnl - total_fees
        
        total_trades = buy_data["count"] + sell_data["count"]
        
        return PnLRecord(
            user_id=user_id,
            bot_id=bot_id,
            exchange="all",
            symbol=symbol or "all",
            realized_pnl=realized_pnl,
            total_fees=total_fees,
            net_pnl=net_pnl,
            total_trades=total_trades,
            buy_volume=Decimal(str(buy_data["total_volume"])),
            sell_volume=Decimal(str(sell_data["total_volume"])),
            total_volume=Decimal(str(buy_data["total_volume"])) + Decimal(str(sell_data["total_volume"])),
            period_start=start_date,
            period_end=end_date,
        )
    
    @classmethod
    async def save_pnl_snapshot(cls, pnl: PnLRecord):
        """Salva snapshot de PnL para hist?rico."""
        collection = cls._get_collection(cls.PNL_COLLECTION)
        
        doc = {
            "user_id": pnl.user_id,
            "bot_id": pnl.bot_id,
            "exchange": pnl.exchange,
            "symbol": pnl.symbol,
            "realized_pnl": float(pnl.realized_pnl),
            "unrealized_pnl": float(pnl.unrealized_pnl),
            "total_fees": float(pnl.total_fees),
            "net_pnl": float(pnl.net_pnl),
            "total_trades": pnl.total_trades,
            "win_rate": pnl.win_rate,
            "total_volume": float(pnl.total_volume),
            "period_start": pnl.period_start,
            "period_end": pnl.period_end,
            "created_at": datetime.utcnow(),
        }
        
        await collection.insert_one(doc)
    
    @classmethod
    async def log_audit_event(
        cls,
        user_id: str,
        event_type: AuditEventType,
        description: str,
        metadata: Dict[str, Any] = None
    ):
        """Registra evento de auditoria."""
        collection = cls._get_collection(cls.AUDIT_COLLECTION)
        
        doc = {
            "user_id": user_id,
            "event_type": event_type.value,
            "description": description,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow(),
        }
        
        await collection.insert_one(doc)
        logger.info(f"? Audit event: [{event_type.value}] {description}")


# ==================== WEBHOOK ALERTS ====================

class WebhookAlertService:
    """Servi?o para envio de alertas via webhooks."""
    
    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client
    
    async def send_telegram(
        self,
        bot_token: str,
        chat_id: str,
        message: str,
        parse_mode: str = "HTML"
    ) -> bool:
        """
        Envia mensagem para Telegram.
        
        Args:
            bot_token: Token do bot Telegram (obtido do @BotFather)
            chat_id: ID do chat/grupo
            message: Mensagem a enviar
            
        Returns:
            True se enviado com sucesso
        """
        try:
            client = await self._get_client()
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }
            
            response = await client.post(url, json=data)
            
            if response.status_code == 200:
                logger.info(f"? Telegram alert enviado para {chat_id}")
                return True
            else:
                logger.error(f"? Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"? Erro ao enviar Telegram: {e}")
            return False
    
    async def send_discord(
        self,
        webhook_url: str,
        message: str,
        username: str = "Crypto Trade Hub",
        embed: Dict[str, Any] = None
    ) -> bool:
        """
        Envia mensagem para Discord via webhook.
        
        Args:
            webhook_url: URL do webhook do Discord
            message: Mensagem a enviar
            embed: Embed opcional (t?tulo, descri??o, cor, etc)
            
        Returns:
            True se enviado com sucesso
        """
        try:
            client = await self._get_client()
            
            data = {
                "username": username,
                "content": message,
            }
            
            if embed:
                data["embeds"] = [embed]
            
            response = await client.post(webhook_url, json=data)
            
            if response.status_code in (200, 204):
                logger.info("? Discord alert enviado")
                return True
            else:
                logger.error(f"? Discord error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"? Erro ao enviar Discord: {e}")
            return False
    
    async def send_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        severity: str = "info",
        telegram_config: Dict[str, str] = None,
        discord_config: Dict[str, str] = None
    ):
        """
        Envia alerta para todos os canais configurados.
        
        Args:
            alert_type: Tipo do alerta (trade, error, warning)
            title: T?tulo do alerta
            message: Mensagem detalhada
            severity: info, warning, error, critical
            telegram_config: {"bot_token": "...", "chat_id": "..."}
            discord_config: {"webhook_url": "..."}
        """
        # Formatar mensagem
        severity_emoji = {
            "info": "??",
            "warning": "??",
            "error": "?",
            "critical": "?",
        }
        emoji = severity_emoji.get(severity, "?")
        
        formatted_msg = f"{emoji} <b>{title}</b>\n\n{message}\n\n<i>Crypto Trade Hub</i>"
        
        tasks = []
        
        if telegram_config:
            tasks.append(
                self.send_telegram(
                    telegram_config["bot_token"],
                    telegram_config["chat_id"],
                    formatted_msg
                )
            )
        
        if discord_config:
            discord_embed = {
                "title": f"{emoji} {title}",
                "description": message,
                "color": {
                    "info": 0x3498db,
                    "warning": 0xf39c12,
                    "error": 0xe74c3c,
                    "critical": 0x8e44ad,
                }.get(severity, 0x95a5a6),
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "Crypto Trade Hub"}
            }
            
            tasks.append(
                self.send_discord(
                    discord_config["webhook_url"],
                    "",
                    embed=discord_embed
                )
            )
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# ==================== CONVENIENCE FUNCTIONS ====================

webhook_service = WebhookAlertService()


async def log_order_execution(
    user_id: str,
    exchange: str,
    order_response: Dict[str, Any],
    bot_id: str = None
) -> str:
    """
    Loga uma execu??o de ordem a partir da resposta da exchange.
    
    Args:
        user_id: ID do usu?rio
        exchange: Nome da exchange
        order_response: Resposta da API da exchange (CCXT format)
        bot_id: ID do bot (se autom?tico)
        
    Returns:
        ID do log criado
    """
    trade = TradeLog(
        user_id=user_id,
        bot_id=bot_id,
        exchange=exchange,
        symbol=order_response.get("symbol", ""),
        trade_type=TradeType.ORDER_FILLED if order_response.get("status") == "closed" else TradeType.ORDER_PLACED,
        side=OrderSide(order_response.get("side", "buy")),
        order_id=order_response.get("id", ""),
        client_order_id=order_response.get("clientOrderId"),
        quantity=Decimal(str(order_response.get("filled", 0) or order_response.get("amount", 0))),
        price=Decimal(str(order_response.get("average", 0) or order_response.get("price", 0))),
        cost=Decimal(str(order_response.get("cost", 0))),
        fee=Decimal(str((order_response.get("fee") or {}).get("cost", 0))),
        fee_currency=(order_response.get("fee") or {}).get("currency", "USDT"),
        status=order_response.get("status", "unknown"),
        timestamp=datetime.fromisoformat(order_response["datetime"].replace("Z", "+00:00")) if order_response.get("datetime") else datetime.utcnow(),
        raw_response=order_response,
    )
    
    return await TradeLogRepository.log_trade(trade)


async def send_trade_alert(
    user_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    pnl: float = None,
    telegram_config: Dict = None,
    discord_config: Dict = None
):
    """Envia alerta de trade executado."""
    emoji = "?" if side.lower() == "buy" else "?"
    pnl_text = f"\nPnL: {'?' if pnl >= 0 else '?'} ${pnl:.2f}" if pnl is not None else ""
    
    message = (
        f"{emoji} <b>{side.upper()}</b> {quantity} {symbol}\n"
        f"? Pre?o: ${price:.4f}\n"
        f"? Total: ${quantity * price:.2f}"
        f"{pnl_text}"
    )
    
    await webhook_service.send_alert(
        alert_type="trade",
        title=f"Trade Executado: {symbol}",
        message=message,
        severity="info",
        telegram_config=telegram_config,
        discord_config=discord_config
    )


async def send_error_alert(
    error_type: str,
    error_message: str,
    context: Dict[str, Any] = None,
    telegram_config: Dict = None,
    discord_config: Dict = None
):
    """Envia alerta de erro cr?tico."""
    context_text = "\n".join([f"{k}: {v}" for k, v in (context or {}).items()])
    
    message = (
        f"? <b>Erro:</b> {error_type}\n\n"
        f"? Detalhes: {error_message}\n\n"
        f"{context_text}"
    )
    
    await webhook_service.send_alert(
        alert_type="error",
        title=f"?? Erro: {error_type}",
        message=message,
        severity="error",
        telegram_config=telegram_config,
        discord_config=discord_config
    )
