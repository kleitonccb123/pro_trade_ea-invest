# DOC 05 — Sistema de Cálculo de PnL Real

> **Nível:** Produção | **Escopo:** PnL Realizado, Não-Realizado, Fees, Slippage  
> **Prioridade:** Alta — dados incorretos destroem a confiança do usuário

---

## 1. OBJETIVO

Implementar o cálculo de PnL (Profit and Loss) com:
- Separação clara entre **PnL realizado** (trades fechados) e **não-realizado** (posição aberta)
- Deducão correta de **fees de trading** (maker/taker da KuCoin)
- Cálculo de **slippage** (diferença entre preço esperado e executado)
- Snapshots periódicos para construção de curva de capital
- Exibição correta no frontend (sem confundir o usuário)

---

## 2. CONCEITOS FUNDAMENTAIS

### 2.1 PnL Realizado vs Não-Realizado

```
PnL Realizado   = somatório de todos os trades fechados (entrada + saída executada)
PnL Não-Real.   = P&L da posição aberta atual (preço atual - preço de entrada)
PnL Total       = PnL Realizado + PnL Não-Realizado

Exemplo:
  Comprou BTC a $60,000 com $1,000 USDT
  Vendeu $400 a $66,000  → PnL realizado = +$40 (≈ 40%)
  Ainda tem $600 abertos
  BTC atual = $64,000     → PnL não-real. = +$40 (6.67% × $600)
  PnL Total = +$80
```

### 2.2 Fee Structure KuCoin (Spot)

```python
# Taxas padrão KuCoin (podem mudar com volume/VIP tier)
MAKER_FEE = 0.001   # 0.10% — ordem limit que entra no book
TAKER_FEE = 0.001   # 0.10% — ordem market ou que consuma do book
```

### 2.3 Slippage

```
Slippage = preço executado - preço esperado (bid/ask no momento do sinal)

Slippage positivo = execução melhor que o esperado (raro)
Slippage negativo = execução pior   (comum em ordens market grandes)
```

---

## 3. MODELO DE DADOS

```python
# backend/app/engine/trade_models.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeRecord(BaseModel):
    """
    Representa um ciclo completo de entrada + saída.
    Uma trade contém a ordem de entrada e a ordem de saída.
    """
    bot_instance_id: str
    user_id: str

    # Ordem de entrada
    entry_order_id: str                  # ID da ordem na KuCoin
    entry_price: float                   # Preço médio preenchido
    entry_funds: float                   # USDT investido (antes do fee)
    entry_quantity: float                # Quantidade de base asset comprada
    entry_fee_usdt: float                # Fee pago na entrada
    entry_timestamp: datetime

    # Ordem de saída (opcional — None = posição aberta)
    exit_order_id: Optional[str] = None
    exit_price: Optional[float] = None
    exit_quantity: Optional[float] = None
    exit_fee_usdt: Optional[float] = 0.0
    exit_timestamp: Optional[datetime] = None
    exit_reason: Optional[str] = None   # "take_profit", "stop_loss", "manual", "trailing"

    # Slippage
    expected_entry_price: Optional[float] = None   # preço ao gerar sinal
    expected_exit_price: Optional[float] = None
    entry_slippage_pct: Optional[float] = None
    exit_slippage_pct: Optional[float] = None

    # PnL calculado (atualizado no fechamento)
    pnl_gross_usdt: Optional[float] = None   # sem fees
    pnl_net_usdt: Optional[float] = None     # descontando ambos fees
    pnl_net_pct: Optional[float] = None      # % sobre capital investido
    roi_pct: Optional[float] = None          # ROI real = net_pnl / entry_funds
    holding_minutes: Optional[int] = None

    status: TradeStatus = TradeStatus.OPEN
    pair: str
    timeframe: str

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
```

---

## 4. CALCULADOR DE PNL

```python
# backend/app/pnl/calculator.py

import logging
from typing import Optional
from datetime import datetime
from app.engine.trade_models import TradeRecord, TradeStatus

logger = logging.getLogger("pnl.calculator")

MAKER_FEE = 0.001
TAKER_FEE = 0.001


class PnLCalculator:

    @staticmethod
    def calculate_entry_fee(funds_usdt: float, order_type: str = "market") -> float:
        """
        Calcula fee da entrada.
        - market order = taker fee
        - limit order = maker fee (assumindo que realmente entra no book)
        """
        fee_rate = TAKER_FEE if order_type == "market" else MAKER_FEE
        return round(funds_usdt * fee_rate, 8)

    @staticmethod
    def calculate_entry_quantity(funds_usdt: float, entry_price: float, fee_usdt: float) -> float:
        """
        Quantidade efetiva comprada = (funds - fee) / preço
        """
        net_funds = funds_usdt - fee_usdt
        return round(net_funds / entry_price, 8)

    @staticmethod
    def calculate_exit_fee(exit_value_usdt: float, order_type: str = "market") -> float:
        fee_rate = TAKER_FEE if order_type == "market" else MAKER_FEE
        return round(exit_value_usdt * fee_rate, 8)

    @staticmethod
    def calculate_slippage(expected_price: float, executed_price: float, side: str) -> float:
        """
        Slippage em % — negativo = pior execução.
        """
        pct = ((executed_price - expected_price) / expected_price) * 100
        # Para compra: preço maior = slippage negativo
        # Para venda: preço menor = slippage negativo
        return -pct if side == "buy" else pct

    @classmethod
    def close_trade(
        cls,
        trade: TradeRecord,
        exit_price: float,
        exit_quantity: float,
        exit_order_id: str,
        exit_reason: str,
        exit_order_type: str = "market",
        expected_exit_price: Optional[float] = None,
    ) -> TradeRecord:
        """
        Fecha uma trade e calcula todos os valores de PnL.
        """
        # Valor bruto de saída
        exit_gross_usdt = exit_price * exit_quantity
        
        # Fee de saída
        exit_fee_usdt = cls.calculate_exit_fee(exit_gross_usdt, exit_order_type)
        
        # PnL bruto = receita bruta - custo bruto
        pnl_gross = exit_gross_usdt - trade.entry_funds
        
        # PnL líquido = PnL bruto - total de fees
        total_fees = trade.entry_fee_usdt + exit_fee_usdt
        pnl_net = pnl_gross - total_fees
        
        # Porcentagem de retorno sobre o capital investido
        pnl_net_pct = (pnl_net / trade.entry_funds) * 100
        roi_pct = ((exit_gross_usdt - total_fees - trade.entry_funds) / trade.entry_funds) * 100

        # Slippage de saída
        exit_slippage = None
        if expected_exit_price:
            exit_slippage = cls.calculate_slippage(expected_exit_price, exit_price, "sell")

        # Duração da trade
        now = datetime.utcnow()
        holding_minutes = int((now - trade.entry_timestamp).total_seconds() / 60)

        trade.exit_order_id = exit_order_id
        trade.exit_price = exit_price
        trade.exit_quantity = exit_quantity
        trade.exit_fee_usdt = exit_fee_usdt
        trade.exit_timestamp = now
        trade.exit_reason = exit_reason
        trade.expected_exit_price = expected_exit_price
        trade.exit_slippage_pct = exit_slippage
        trade.pnl_gross_usdt = round(pnl_gross, 6)
        trade.pnl_net_usdt = round(pnl_net, 6)
        trade.pnl_net_pct = round(pnl_net_pct, 4)
        trade.roi_pct = round(roi_pct, 4)
        trade.holding_minutes = holding_minutes
        trade.status = TradeStatus.CLOSED

        logger.info(
            f"Trade fechada: {trade.bot_instance_id} | "
            f"PnL líquido: {pnl_net:+.4f} USDT ({pnl_net_pct:+.2f}%) | "
            f"Fees: {total_fees:.4f} USDT | "
            f"Razão: {exit_reason} | "
            f"Duração: {holding_minutes}min"
        )
        return trade

    @staticmethod
    def calc_unrealized_pnl(
        entry_price: float,
        current_price: float,
        entry_quantity: float,
        entry_fee_usdt: float
    ) -> dict:
        """
        Calcula PnL não-realizado da posição aberta.
        """
        current_value = current_price * entry_quantity
        initial_cost = entry_price * entry_quantity + entry_fee_usdt
        unrealized_usdt = current_value - initial_cost
        unrealized_pct = (unrealized_usdt / initial_cost) * 100
        return {
            "unrealized_pnl_usdt": round(unrealized_usdt, 4),
            "unrealized_pnl_pct": round(unrealized_pct, 4),
            "current_value_usdt": round(current_value, 4),
        }
```

---

## 5. ACUMULADOR DE MÉTRICAS DO BOT

```python
# backend/app/pnl/metrics_aggregator.py

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BotMetricsAccumulator:
    """
    Atualizado em memória a cada trade fechada, persistido no MongoDB periodicamente.
    """
    initial_capital_usdt: float
    current_capital_usdt: float
    total_pnl_usdt: float = 0.0
    total_fees_usdt: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    largest_win_usdt: float = 0.0
    largest_loss_usdt: float = 0.0
    total_volume_usdt: float = 0.0
    avg_holding_minutes: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    max_drawdown_pct: float = 0.0
    peak_capital: float = 0.0

    def record_trade(self, pnl_net_usdt: float, fee_usdt: float, volume_usdt: float, holding_minutes: int):
        """Registra o resultado de uma trade fechada."""
        self.total_trades += 1
        self.total_pnl_usdt = round(self.total_pnl_usdt + pnl_net_usdt, 6)
        self.total_fees_usdt = round(self.total_fees_usdt + fee_usdt, 6)
        self.total_volume_usdt = round(self.total_volume_usdt + volume_usdt, 2)
        self.current_capital_usdt = round(self.current_capital_usdt + pnl_net_usdt, 6)

        if pnl_net_usdt >= 0:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.consecutive_wins)
            if pnl_net_usdt > self.largest_win_usdt:
                self.largest_win_usdt = pnl_net_usdt
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
            if pnl_net_usdt < self.largest_loss_usdt:
                self.largest_loss_usdt = pnl_net_usdt

        # Atualizar drawdown máximo
        if self.current_capital_usdt > self.peak_capital:
            self.peak_capital = self.current_capital_usdt
        elif self.peak_capital > 0:
            dd = ((self.peak_capital - self.current_capital_usdt) / self.peak_capital) * 100
            self.max_drawdown_pct = max(self.max_drawdown_pct, dd)

        # Média de duração
        self.avg_holding_minutes = (
            (self.avg_holding_minutes * (self.total_trades - 1) + holding_minutes)
            / self.total_trades
        )

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return round((self.winning_trades / self.total_trades) * 100, 2)

    @property
    def profit_factor(self) -> float:
        """Lucro total / Perda total (ideal > 1.5)"""
        total_wins = sum(...)  # somar só os positivos — manter lista separada ou consultar DB
        total_losses = abs(sum(...))
        if total_losses == 0:
            return float("inf")
        return round(total_wins / total_losses, 2)

    @property
    def roi_pct(self) -> float:
        return round((self.total_pnl_usdt / self.initial_capital_usdt) * 100, 4)
```

---

## 6. SNAPSHOT DIÁRIO (CURVA DE CAPITAL)

```python
# backend/app/pnl/snapshot_service.py
# Executado via APScheduler a cada 1h

async def take_bot_performance_snapshot(bot_instance_id: str, db, current_price: dict):
    """
    Salva snapshot de PnL para plotar curva de capital ao longo do tempo.
    """
    instance = await db["user_bot_instances"].find_one({"_id": ObjectId(bot_instance_id)})
    if not instance or instance["status"] != "running":
        return

    metrics = instance["metrics"]
    open_position = instance.get("current_position")

    unrealized = {}
    if open_position:
        price = current_price.get(instance["configuration"]["pair"], 0)
        unrealized = PnLCalculator.calc_unrealized_pnl(
            entry_price=open_position["entry_price"],
            current_price=price,
            entry_quantity=open_position["quantity"],
            entry_fee_usdt=open_position["entry_fee_usdt"]
        )

    snapshot = {
        "bot_instance_id": bot_instance_id,
        "user_id": instance["user_id"],
        "timestamp": datetime.utcnow(),
        "realized_pnl_usdt": metrics["total_pnl_usdt"],
        "unrealized_pnl_usdt": unrealized.get("unrealized_pnl_usdt", 0),
        "total_pnl_usdt": metrics["total_pnl_usdt"] + unrealized.get("unrealized_pnl_usdt", 0),
        "capital_usdt": metrics["current_capital_usdt"],
        "total_trades": metrics["total_trades"],
        "win_rate": metrics["win_rate"],
        "roi_pct": metrics["roi_pct"],
        "total_fees_usdt": metrics["total_fees_usdt"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
    }

    await db["bot_performance_snapshots"].insert_one(snapshot)
```

---

## 7. FRONTEND — EXIBIÇÃO DO PNL

```tsx
// src/components/BotMetricsCard.tsx

interface BotMetrics {
  realized_pnl_usdt: number;
  unrealized_pnl_usdt: number;
  total_pnl_usdt: number;
  roi_pct: number;
  win_rate: number;
  total_trades: number;
  total_fees_usdt: number;
}

const PnLDisplay: React.FC<{ metrics: BotMetrics }> = ({ metrics }) => {
  const isProfit = metrics.total_pnl_usdt >= 0;

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <p className="text-sm text-muted-foreground">PnL Realizado</p>
        <p className={`text-lg font-bold ${metrics.realized_pnl_usdt >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {metrics.realized_pnl_usdt >= 0 ? '+' : ''}{metrics.realized_pnl_usdt.toFixed(4)} USDT
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">PnL Não-Realizado</p>
        <p className={`text-lg font-bold ${metrics.unrealized_pnl_usdt >= 0 ? 'text-yellow-400' : 'text-orange-400'}`}>
          {metrics.unrealized_pnl_usdt >= 0 ? '+' : ''}{metrics.unrealized_pnl_usdt.toFixed(4)} USDT
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">ROI Total</p>
        <p className={`text-xl font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
          {metrics.roi_pct >= 0 ? '+' : ''}{metrics.roi_pct.toFixed(2)}%
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">Taxa Pagas (fees)</p>
        <p className="text-sm text-muted-foreground">
          -{metrics.total_fees_usdt.toFixed(4)} USDT
        </p>
      </div>
      <div>
        <p className="text-sm text-muted-foreground">Win Rate</p>
        <p className="text-lg font-semibold">
          {metrics.win_rate.toFixed(1)}% ({metrics.total_trades} trades)
        </p>
      </div>
    </div>
  );
};
```

---

## 8. VALIDAÇÕES CRÍTICAS

| Regra | Implementação |
|---|---|
| Fee nunca pode ser negativo | Assert `fee >= 0` antes de salvar |
| PnL net = gross - fees | Sempre recalcular, nunca confiar no valor cacheado |
| Entry_quantity deve ser positivo | Validar antes de abrir posição |
| Unrealized só existe com posição aberta | Checar `current_position is not None` |
| Exit_price × exit_quantity ≈ saída real | Conferir contra os fills da KuCoin |

---

## 9. CHECKLIST

- [ ] `TradeRecord` salvo com entry_fee, exit_fee, slippage separados
- [ ] PnL net sempre = (saída bruta) - (entrada) - (fees totais)
- [ ] Snapshot de capital salvo a cada hora
- [ ] Frontend separa realizado vs não-realizado
- [ ] Fees exibidas separadamente (clareza para o usuário)
- [ ] Drawdown máximo calculado e exibido
- [ ] Win rate calculado: wins / total (não só wins / losses)
- [ ] Slippage registrado para análise de qualidade de execução
- [ ] API endpoint `GET /bots/{id}/trades` com paginação retorna histórico completo
