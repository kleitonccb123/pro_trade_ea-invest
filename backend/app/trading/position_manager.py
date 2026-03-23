"""
PositionManager — Gestao persistente de posicoes abertas

Problema sem isso:
  - RiskManager tem posicoes em memory-dict -> perda no restart
  - Nao ha preco medio real (apenas signals de entrada)
  - PnL nao e calculado com fees reais
  - Reconciliacao nao tem base de posicoes para comparar

Solucao:
  - Toda posicao aberta e salva no banco (MongoDB collection: positions)
  - Preco medio ponderado e recalculado a cada execution report (match)
  - Fees acumuladas por position_id
  - PnL realizado calculado ao fechar
  - PnL nao realizado calculado com preco de mercado atual

Schema MongoDB (colecao: positions):
  {
    "_id":              ObjectId,
    "user_id":          str,
    "bot_id":           str,           # ou null se manual
    "symbol":           str,           # "BTC-USDT"
    "side":             str,           # "long" | "short"
    "status":           str,           # "open" | "closed" | "partial"
    "size":             Decimal,       # tamanho total
    "filled_size":      Decimal,       # preenchido ate agora
    "avg_entry_price":  Decimal,       # preco medio ponderado
    "accumulated_fees": Decimal,       # fees totais (moeda de cotacao)
    "fee_currency":     str,
    "realized_pnl":     Decimal,       # PnL ao fechar (ou parciais)
    "entry_order_ids":  [str],         # todos os orderId de entrada
    "exit_order_ids":   [str],         # todos os orderId de saida
    "opened_at":        datetime,
    "closed_at":        datetime | null,
    "take_profit":      Decimal | null,
    "stop_loss":        Decimal | null,
  }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Gestao persistente de posicoes abertas com calculo de PnL real.

    Uso:
    ```python
    pm = PositionManager(db)

    # Ao abrir ordem:
    pos = await pm.open_position(
        user_id="u1", bot_id="b1", symbol="BTC-USDT",
        side="long", size=Decimal("0.1"),
        entry_order_id="abc123"
    )

    # Ao receber execution report (WS match event):
    await pm.apply_execution(pos["_id"], execution_event)

    # Para calcular PnL nao realizado:
    unrealized = await pm.unrealized_pnl(pos["_id"], current_price=Decimal("65000"))

    # Ao fechar:
    await pm.close_position(pos["_id"], exit_order_id="xyz", exit_price=Decimal("66000"))
    ```
    """

    COLLECTION = "positions"

    def __init__(self, db: Any) -> None:
        self._db = db
        self._col = db[self.COLLECTION]

    # ──────────────────────────── Abertura ───────────────────────────────────

    async def open_position(
        self,
        user_id: str,
        bot_id: Optional[str],
        symbol: str,
        side: str,               # "long" | "short"
        size: Decimal,
        entry_order_id: str,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Cria registro de posicao com status 'open'.
        avg_entry_price sera atualizado assim que o execution report chegar.
        """
        doc = {
            "user_id":          user_id,
            "bot_id":           bot_id,
            "symbol":           symbol,
            "side":             side.lower(),
            "status":           "open",
            "size":             str(size),
            "filled_size":      "0",
            "avg_entry_price":  "0",
            "accumulated_fees": "0",
            "fee_currency":     "USDT",
            "realized_pnl":     "0",
            "entry_order_ids":  [entry_order_id],
            "exit_order_ids":   [],
            "opened_at":        datetime.now(timezone.utc),
            "closed_at":        None,
            "take_profit":      str(take_profit) if take_profit else None,
            "stop_loss":        str(stop_loss) if stop_loss else None,
        }
        result = await self._col.insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(
            f"Posicao aberta: {side.upper()} {size} {symbol} "
            f"[{result.inserted_id}]"
        )
        return doc

    # ──────────────────────────── Execution report ───────────────────────────

    async def apply_execution(
        self,
        position_id: Any,
        event: Dict[str, Any],
    ) -> None:
        """
        Atualiza posicao com base em um execution report do WebSocket.

        Recalcula:
        - avg_entry_price (media ponderada acumulada)
        - filled_size
        - accumulated_fees

        event esperado (formato _parse_order_execution do websocket_manager):
          {
            "status":      "match",
            "match_size":  Decimal,
            "price":       Decimal,
            "fee":         Decimal,
            "fee_currency": str,
          }
        """
        if event.get("status") not in ("match", "done"):
            return

        match_size = Decimal(str(event.get("match_size", "0")))
        price      = Decimal(str(event.get("price", "0")))
        fee        = Decimal(str(event.get("fee", "0")))
        fee_cur    = event.get("fee_currency", "USDT")

        if match_size == 0:
            # Evento 'done' sem match_size usa filled_size total
            match_size = Decimal(str(event.get("filled_size", "0")))

        # Busca estado atual da posicao
        pos = await self._col.find_one({"_id": position_id})
        if not pos:
            logger.warning(f"apply_execution: posicao {position_id} nao encontrada")
            return

        old_filled = Decimal(pos.get("filled_size", "0"))
        old_avg    = Decimal(pos.get("avg_entry_price", "0"))
        old_fees   = Decimal(pos.get("accumulated_fees", "0"))

        # Preco medio ponderado: (Qold * Pavg + Qnew * Pnew) / (Qold + Qnew)
        new_filled = old_filled + match_size
        if new_filled > 0 and price > 0:
            new_avg = (old_filled * old_avg + match_size * price) / new_filled
        else:
            new_avg = old_avg

        new_fees = old_fees + fee

        status = pos.get("status", "open")
        total_size = Decimal(pos.get("size", "0"))
        if new_filled >= total_size:
            status = "filled"

        await self._col.update_one(
            {"_id": position_id},
            {"$set": {
                "filled_size":      str(new_filled),
                "avg_entry_price":  str(new_avg),
                "accumulated_fees": str(new_fees),
                "fee_currency":     fee_cur,
                "status":           status,
                "updated_at":       datetime.now(timezone.utc),
            }},
        )
        logger.debug(
            f"Posicao {position_id} atualizada: "
            f"filled={new_filled}, avg={new_avg:.6f}, fees={new_fees}"
        )

    # ──────────────────────────── Fechamento ─────────────────────────────────

    async def close_position(
        self,
        position_id: Any,
        exit_order_id: str,
        exit_price: Decimal,
        exit_size: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Fecha uma posicao (total ou parcial).

        Calcula PnL realizado:
          LONG:  (exit_price - avg_entry_price) * exit_size - fees
          SHORT: (avg_entry_price - exit_price) * exit_size - fees

        Retorna: PnL realizado
        """
        pos = await self._col.find_one({"_id": position_id})
        if not pos:
            logger.warning(f"close_position: posicao {position_id} nao encontrada")
            return Decimal("0")

        avg_entry  = Decimal(pos.get("avg_entry_price", "0"))
        filled     = Decimal(pos.get("filled_size", "0"))
        total_fees = Decimal(pos.get("accumulated_fees", "0"))
        side       = pos.get("side", "long")
        old_pnl    = Decimal(pos.get("realized_pnl", "0"))

        close_size = exit_size if exit_size else filled

        if side == "long":
            raw_pnl = (exit_price - avg_entry) * close_size
        else:
            raw_pnl = (avg_entry - exit_price) * close_size

        # Subtrai fees proporcionais
        prop_fees = total_fees * (close_size / filled) if filled > 0 else Decimal("0")
        realized  = raw_pnl - prop_fees
        new_total_pnl = old_pnl + realized

        is_full_close = (close_size >= filled)
        new_status = "closed" if is_full_close else "partial"

        update: Dict[str, Any] = {
            "realized_pnl": str(new_total_pnl),
            "status":       new_status,
            "updated_at":   datetime.now(timezone.utc),
        }
        if is_full_close:
            update["closed_at"] = datetime.now(timezone.utc)

        await self._col.update_one(
            {"_id": position_id},
            {
                "$set":  update,
                "$push": {"exit_order_ids": exit_order_id},
            },
        )

        logger.info(
            f"Posicao {position_id} {'fechada' if is_full_close else 'parcial'}: "
            f"PnL realizado = {realized:.6f} (acumulado = {new_total_pnl:.6f})"
        )
        return realized

    # ──────────────────────── PnL nao realizado ──────────────────────────────

    async def unrealized_pnl(
        self,
        position_id: Any,
        current_price: Decimal,
    ) -> Decimal:
        """
        Calcula PnL nao realizado com preco atual de mercado.

        LONG:  (current - avg_entry) * filled
        SHORT: (avg_entry - current) * filled
        """
        pos = await self._col.find_one({"_id": position_id})
        if not pos:
            return Decimal("0")

        avg_entry = Decimal(pos.get("avg_entry_price", "0"))
        filled    = Decimal(pos.get("filled_size", "0"))
        side      = pos.get("side", "long")

        if side == "long":
            return (current_price - avg_entry) * filled
        else:
            return (avg_entry - current_price) * filled

    # ──────────────────────────── Consultas ──────────────────────────────────

    async def get_open_positions(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista posicoes abertas (status=open ou filled)."""
        query: Dict[str, Any] = {"status": {"$in": ["open", "filled"]}}
        if user_id:
            query["user_id"] = user_id
        if symbol:
            query["symbol"] = symbol
        return await self._col.find(query).to_list(length=500)

    async def get_position(self, position_id: Any) -> Optional[Dict[str, Any]]:
        """Busca posicao por _id."""
        return await self._col.find_one({"_id": position_id})

    async def count_open_by_symbol(self, user_id: str, symbol: str) -> int:
        """Conta posicoes abertas de um usuario em um simbolo especifico."""
        return await self._col.count_documents(
            {"user_id": user_id, "symbol": symbol, "status": {"$in": ["open", "filled"]}}
        )
