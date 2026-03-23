"""
TpSlRecord — Modelo de dados para Take Profit / Stop Loss

Persiste no MongoDB (coleção: tpsl_records) ANTES de enviar qualquer
ordem à exchange, garantindo recuperação após restart.

Ciclo de vida:
  ACTIVE
    ├── TP atingido → TP_HIT   (SL cancelado automaticamente)
    ├── SL atingido → SL_HIT   (TP cancelado automaticamente)
    ├── Fechado manualmente → MANUALLY_CLOSED
    ├── Posição zerada externamente → ORPHANED (Guardian cancela)
    └── Cancelado explicitamente → CANCELED

Invariante de integridade:
  - tpClientOid e slClientOid são gerados e persistidos ANTES de enviar
    qualquer ordem à exchange.
  - Se o envio do SL falhar, o TP já enviado é cancelado imediatamente
    para manter consistência.
  - Redis Lock garante que TP e SL não sejam ambos marcados como HIT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class TpSlStatus(str, Enum):
    ACTIVE          = "ACTIVE"           # Ambas as ordens ativas na exchange
    TP_HIT          = "TP_HIT"           # Take Profit executado, SL cancelado
    SL_HIT          = "SL_HIT"           # Stop Loss executado, TP cancelado
    MANUALLY_CLOSED = "MANUALLY_CLOSED"  # Fechado via intervenção manual
    CANCELED        = "CANCELED"         # Cancelado sem execução
    ORPHANED        = "ORPHANED"         # Posição fechada mas TP/SL ainda ativos


class MarketType(str, Enum):
    SPOT    = "SPOT"
    FUTURES = "FUTURES"


@dataclass
class TpSlRecord:
    """
    Registro persistido de um par Take Profit / Stop Loss.

    Cada registro protege exatamente uma posição.
    Os campos *ClientOid são os clientOids enviados à KuCoin.
    Os campos *OrderId são os IDs reais retornados pela KuCoin.
    """

    # ── Identificação ─────────────────────────────────────────────────────────
    id: str
    bot_id: str
    user_id: str
    strategy_id: str
    position_id: str           # FK para PositionManager / positions collection

    # ── Mercado ───────────────────────────────────────────────────────────────
    market_type: MarketType    # SPOT | FUTURES
    symbol: str                # Ex: BTC-USDT
    side: str                  # Lado da POSIÇÃO: "buy" (long) | "sell" (short)

    # ── Tamanho ───────────────────────────────────────────────────────────────
    total_size: str            # Tamanho total da posição (str para precisão)
    remaining_size: str        # Tamanho ainda não executado pelo TP/SL

    # ── Preços ────────────────────────────────────────────────────────────────
    entry_price: str
    tp_price: str
    sl_price: str
    sl_stop_price: str = ""    # Stop-limit: gatilho (≠ limit price)

    # ── Ordem de Take Profit ──────────────────────────────────────────────────
    tp_client_oid: str = ""
    tp_order_id: Optional[str] = None
    tp_filled_size: Optional[str] = None
    tp_filled_at: Optional[datetime] = None

    # ── Ordem de Stop Loss ────────────────────────────────────────────────────
    sl_client_oid: str = ""
    sl_order_id: Optional[str] = None
    sl_filled_size: Optional[str] = None
    sl_filled_at: Optional[datetime] = None

    # ── Status ────────────────────────────────────────────────────────────────
    status: TpSlStatus = TpSlStatus.ACTIVE
    cancelation_source: Optional[str] = None   # TP_HIT | SL_HIT | MANUAL | POSITION_CLOSED
    error: Optional[str] = None

    # ── P&L (preenchido ao fechar) ────────────────────────────────────────────
    realized_pnl: Optional[str] = None
    pnl_percent: Optional[str] = None

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Serialização ──────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":                 self.id,
            "bot_id":             self.bot_id,
            "user_id":            self.user_id,
            "strategy_id":        self.strategy_id,
            "position_id":        self.position_id,
            "market_type":        self.market_type.value,
            "symbol":             self.symbol,
            "side":               self.side,
            "total_size":         self.total_size,
            "remaining_size":     self.remaining_size,
            "entry_price":        self.entry_price,
            "tp_price":           self.tp_price,
            "sl_price":           self.sl_price,
            "sl_stop_price":      self.sl_stop_price,
            "tp_client_oid":      self.tp_client_oid,
            "tp_order_id":        self.tp_order_id,
            "tp_filled_size":     self.tp_filled_size,
            "tp_filled_at":       _iso(self.tp_filled_at),
            "sl_client_oid":      self.sl_client_oid,
            "sl_order_id":        self.sl_order_id,
            "sl_filled_size":     self.sl_filled_size,
            "sl_filled_at":       _iso(self.sl_filled_at),
            "status":             self.status.value,
            "cancelation_source": self.cancelation_source,
            "error":              self.error,
            "realized_pnl":       self.realized_pnl,
            "pnl_percent":        self.pnl_percent,
            "created_at":         _iso(self.created_at),
            "updated_at":         _iso(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TpSlRecord":
        return cls(
            id=str(data.get("id", data.get("_id", ""))),
            bot_id=data.get("bot_id", ""),
            user_id=data.get("user_id", ""),
            strategy_id=data.get("strategy_id", ""),
            position_id=data.get("position_id", ""),
            market_type=MarketType(data.get("market_type", MarketType.SPOT.value)),
            symbol=data.get("symbol", ""),
            side=data.get("side", "buy"),
            total_size=data.get("total_size", "0"),
            remaining_size=data.get("remaining_size", "0"),
            entry_price=data.get("entry_price", "0"),
            tp_price=data.get("tp_price", "0"),
            sl_price=data.get("sl_price", "0"),
            sl_stop_price=data.get("sl_stop_price", ""),
            tp_client_oid=data.get("tp_client_oid", ""),
            tp_order_id=data.get("tp_order_id"),
            tp_filled_size=data.get("tp_filled_size"),
            sl_client_oid=data.get("sl_client_oid", ""),
            sl_order_id=data.get("sl_order_id"),
            sl_filled_size=data.get("sl_filled_size"),
            status=TpSlStatus(data.get("status", TpSlStatus.ACTIVE.value)),
            cancelation_source=data.get("cancelation_source"),
            error=data.get("error"),
            realized_pnl=data.get("realized_pnl"),
            pnl_percent=data.get("pnl_percent"),
        )


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None
