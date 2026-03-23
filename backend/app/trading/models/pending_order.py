"""
PendingOrder — Modelo de ordem persistida antes do envio à exchange

Ciclo de vida de status:
  PENDING_QUEUE
      ↓ (pre-flight aprovado)
  PREFLIGHT_OK
      ↓ (início do envio HTTP)
  SENDING
      ↓ (aceito pela KuCoin 201)
  SENT
      ↓ (WS: open)
  OPEN
      ↓ (WS: match)
  PARTIAL_FILL
      ↓ (WS: filled)
  FILLED / RECONCILED

Desvios:
  PREFLIGHT_FAIL   — saldo insuficiente / risco excedido
  IDEMPOTENT       — clientOid já processado anteriormente
  REJECTED         — erro terminal da exchange (ex: preço inválido)
  FAILED           — erro técnico não recuperável
  CANCELED         — cancelada pelo usuário ou pela exchange
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class OrderStatus(str, Enum):
    PENDING_QUEUE  = "PENDING_QUEUE"   # Na fila, ainda não processado
    PREFLIGHT_OK   = "PREFLIGHT_OK"    # Pre-flight aprovado
    PREFLIGHT_FAIL = "PREFLIGHT_FAIL"  # Pre-flight rejeitado
    IDEMPOTENT     = "IDEMPOTENT"      # Já processado anteriormente
    SENDING        = "SENDING"         # Sendo enviado à exchange
    SENT           = "SENT"            # Aceito pela exchange (201)
    OPEN           = "OPEN"            # Ordem aberta na exchange
    PARTIAL_FILL   = "PARTIAL_FILL"    # Execução parcial
    FILLED         = "FILLED"          # Execução completa
    CANCELED       = "CANCELED"        # Cancelada
    REJECTED       = "REJECTED"        # Rejeitada pela exchange (erro terminal)
    FAILED         = "FAILED"          # Falha técnica no envio
    RECONCILED     = "RECONCILED"      # Confirmada via reconciliação


@dataclass
class PendingOrder:
    """
    Representa uma ordem persistida no banco antes de ser enviada à exchange.

    O campo `client_oid` é gerado deterministicamente a partir de
    `signal_id + bot_id + attempt` e deve ser persistido ANTES do envio HTTP.
    """

    # ── Identificação ─────────────────────────────────────────────────────────
    id: str                          # ID interno (MongoDB ObjectId ou UUID)
    client_oid: str                  # Enviado à KuCoin como clientOid (max 32 chars)
    signal_id: str                   # Signal que originou esta ordem
    bot_id: str
    user_id: str
    strategy_id: str
    order_id: Optional[str] = None   # ID real retornado pela KuCoin

    # ── Parâmetros da ordem ───────────────────────────────────────────────────
    symbol: str = ""                 # Ex: BTC-USDT
    side: str = "buy"                # "buy" | "sell"
    order_type: str = "market"       # "limit" | "market"
    size: str = "0"                  # String para preservar precisão decimal
    price: Optional[str] = None      # None se market
    time_in_force: str = "GTC"       # GTC | GTT | IOC | FOK

    # ── Controle de status ────────────────────────────────────────────────────
    status: OrderStatus = OrderStatus.PENDING_QUEUE
    attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    last_error: Optional[str] = None

    # ── Execução ──────────────────────────────────────────────────────────────
    filled_size: Optional[str] = None
    filled_funds: Optional[str] = None
    avg_fill_price: Optional[str] = None
    fee: Optional[str] = None
    fee_currency: Optional[str] = None

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None

    # ── Auditoria ─────────────────────────────────────────────────────────────
    preflight_result: Optional[Dict[str, Any]] = None
    exchange_response: Optional[Dict[str, Any]] = None
    reconciled: bool = False
    reconciled_at: Optional[datetime] = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para persistência no banco."""
        return {
            "id":               self.id,
            "client_oid":       self.client_oid,
            "order_id":         self.order_id,
            "signal_id":        self.signal_id,
            "bot_id":           self.bot_id,
            "user_id":          self.user_id,
            "strategy_id":      self.strategy_id,
            "symbol":           self.symbol,
            "side":             self.side,
            "order_type":       self.order_type,
            "size":             self.size,
            "price":            self.price,
            "time_in_force":    self.time_in_force,
            "status":           self.status.value,
            "attempts":         self.attempts,
            "last_attempt_at":  _iso(self.last_attempt_at),
            "last_error":       self.last_error,
            "filled_size":      self.filled_size,
            "filled_funds":     self.filled_funds,
            "avg_fill_price":   self.avg_fill_price,
            "fee":              self.fee,
            "fee_currency":     self.fee_currency,
            "created_at":       _iso(self.created_at),
            "updated_at":       _iso(self.updated_at),
            "sent_at":          _iso(self.sent_at),
            "filled_at":        _iso(self.filled_at),
            "canceled_at":      _iso(self.canceled_at),
            "preflight_result": self.preflight_result,
            "exchange_response": self.exchange_response,
            "reconciled":       self.reconciled,
            "reconciled_at":    _iso(self.reconciled_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingOrder":
        """Reconstrói a partir de um dict vindo do banco."""
        return cls(
            id=data["id"],
            client_oid=data["client_oid"],
            signal_id=data.get("signal_id", ""),
            bot_id=data.get("bot_id", ""),
            user_id=data.get("user_id", ""),
            strategy_id=data.get("strategy_id", ""),
            order_id=data.get("order_id"),
            symbol=data.get("symbol", ""),
            side=data.get("side", "buy"),
            order_type=data.get("order_type", "market"),
            size=data.get("size", "0"),
            price=data.get("price"),
            time_in_force=data.get("time_in_force", "GTC"),
            status=OrderStatus(data.get("status", OrderStatus.PENDING_QUEUE.value)),
            attempts=data.get("attempts", 0),
            last_error=data.get("last_error"),
            filled_size=data.get("filled_size"),
            filled_funds=data.get("filled_funds"),
            avg_fill_price=data.get("avg_fill_price"),
            fee=data.get("fee"),
            fee_currency=data.get("fee_currency"),
            reconciled=data.get("reconciled", False),
            preflight_result=data.get("preflight_result"),
            exchange_response=data.get("exchange_response"),
        )


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None
