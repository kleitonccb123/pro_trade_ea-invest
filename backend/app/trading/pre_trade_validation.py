"""
Pre-Trade Validation - Valida??o de Saldo e Condi??es Pr?-Trade

Verifica antes de enviar ordens:
1. Saldo dispon?vel suficiente
2. Limites de ordem (min/max)
3. Precis?o de pre?o e quantidade
4. Margem de seguran?a

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class ValidationError(Exception):
    """Erro de valida??o pr?-trade."""
    def __init__(self, code: str, message: str, details: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass
class MarketInfo:
    """Informa??es de mercado para um s?mbolo."""
    symbol: str
    base_currency: str          # Ex: BTC
    quote_currency: str         # Ex: USDT
    min_order_size: Decimal     # Tamanho m?nimo da ordem (em base)
    max_order_size: Decimal     # Tamanho m?ximo
    min_notional: Decimal       # Valor m?nimo em quote (ex: 10 USDT)
    price_precision: int        # Casas decimais do pre?o
    quantity_precision: int     # Casas decimais da quantidade
    tick_size: Decimal          # Incremento m?nimo de pre?o
    step_size: Decimal          # Incremento m?nimo de quantidade


@dataclass
class Balance:
    """Saldo de uma moeda."""
    currency: str
    available: Decimal
    locked: Decimal
    total: Decimal


@dataclass
class PreTradeValidation:
    """Resultado da valida??o pr?-trade."""
    valid: bool
    adjusted_quantity: Optional[Decimal] = None
    adjusted_price: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    estimated_fee: Optional[Decimal] = None
    warnings: list = None
    errors: list = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


# Alias para compatibilidade
ValidationResult = PreTradeValidation


class PreTradeValidator:
    """
    Validador de ordens pr?-trade.
    
    Verifica todas as condi??es antes de enviar uma ordem para a exchange.
    """
    
    # Taxa padr?o das exchanges (pode ser sobrescrita)
    DEFAULT_FEE_RATE = Decimal("0.001")  # 0.1%
    
    # Margem de seguran?a para saldo (evita erros de arredondamento)
    BALANCE_SAFETY_MARGIN = Decimal("0.999")  # 99.9% do saldo
    
    def __init__(self, fee_rate: Decimal = None):
        self.fee_rate = fee_rate or self.DEFAULT_FEE_RATE
    
    def validate_order(
        self,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
        market: MarketInfo,
        balance: Balance,
        is_market_order: bool = False
    ) -> PreTradeValidation:
        """
        Valida uma ordem antes de enviar para a exchange.
        
        Args:
            side: BUY ou SELL
            quantity: Quantidade desejada
            price: Pre?o (0 para market order)
            market: Informa??es do mercado
            balance: Saldo dispon?vel
            is_market_order: Se ? ordem a mercado
            
        Returns:
            PreTradeValidation com resultado e ajustes
        """
        result = PreTradeValidation(valid=True)
        
        try:
            # 1. Ajustar precis?o da quantidade
            adjusted_qty = self._adjust_quantity(quantity, market)
            result.adjusted_quantity = adjusted_qty
            
            # 2. Ajustar precis?o do pre?o (se n?o for market order)
            if not is_market_order:
                adjusted_price = self._adjust_price(price, market)
                result.adjusted_price = adjusted_price
            else:
                adjusted_price = price
            
            # 3. Validar tamanho m?nimo/m?ximo
            self._validate_order_size(adjusted_qty, market, result)
            
            # 4. Validar valor notional m?nimo
            self._validate_notional(adjusted_qty, adjusted_price, market, result)
            
            # 5. Calcular custo estimado e taxas
            cost, fee = self._calculate_cost_and_fee(
                side, adjusted_qty, adjusted_price, is_market_order
            )
            result.estimated_cost = cost
            result.estimated_fee = fee
            
            # 6. Validar saldo dispon?vel
            self._validate_balance(side, cost, fee, market, balance, result)
            
            # 7. Verificar se h? erros cr?ticos
            if result.errors:
                result.valid = False
            
            return result
            
        except Exception as e:
            logger.error(f"? Erro na valida??o pr?-trade: {e}")
            result.valid = False
            result.errors.append(f"Erro interno: {str(e)}")
            return result
    
    def _adjust_quantity(self, quantity: Decimal, market: MarketInfo) -> Decimal:
        """Ajusta quantidade para a precis?o do mercado."""
        if market.step_size > 0:
            # Arredondar para baixo no step_size
            adjusted = (quantity // market.step_size) * market.step_size
        else:
            # Usar precis?o decimal
            adjusted = quantity.quantize(
                Decimal(10) ** -market.quantity_precision,
                rounding=ROUND_DOWN
            )
        return adjusted
    
    def _adjust_price(self, price: Decimal, market: MarketInfo) -> Decimal:
        """Ajusta pre?o para a precis?o do mercado."""
        if market.tick_size > 0:
            # Arredondar para o tick_size mais pr?ximo
            adjusted = (price // market.tick_size) * market.tick_size
        else:
            # Usar precis?o decimal
            adjusted = price.quantize(
                Decimal(10) ** -market.price_precision,
                rounding=ROUND_DOWN
            )
        return adjusted
    
    def _validate_order_size(
        self,
        quantity: Decimal,
        market: MarketInfo,
        result: PreTradeValidation
    ):
        """Valida tamanho da ordem."""
        if quantity < market.min_order_size:
            result.errors.append(
                f"Quantidade {quantity} abaixo do m?nimo {market.min_order_size} {market.base_currency}"
            )
        
        if market.max_order_size > 0 and quantity > market.max_order_size:
            result.errors.append(
                f"Quantidade {quantity} acima do m?ximo {market.max_order_size} {market.base_currency}"
            )
    
    def _validate_notional(
        self,
        quantity: Decimal,
        price: Decimal,
        market: MarketInfo,
        result: PreTradeValidation
    ):
        """Valida valor notional m?nimo."""
        notional = quantity * price
        
        if notional < market.min_notional:
            result.errors.append(
                f"Valor da ordem {notional:.2f} {market.quote_currency} "
                f"abaixo do m?nimo {market.min_notional} {market.quote_currency}"
            )
    
    def _calculate_cost_and_fee(
        self,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
        is_market_order: bool
    ) -> Tuple[Decimal, Decimal]:
        """Calcula custo e taxa estimados."""
        notional = quantity * price
        
        # Taxa um pouco maior para market orders (slippage)
        fee_multiplier = Decimal("1.5") if is_market_order else Decimal("1.0")
        fee = notional * self.fee_rate * fee_multiplier
        
        if side == OrderSide.BUY:
            # Para compra: custo = notional + fee
            cost = notional + fee
        else:
            # Para venda: custo = quantidade (em base), recebe notional - fee
            cost = quantity
        
        return cost, fee
    
    def _validate_balance(
        self,
        side: OrderSide,
        cost: Decimal,
        fee: Decimal,
        market: MarketInfo,
        balance: Balance,
        result: PreTradeValidation
    ):
        """Valida saldo dispon?vel."""
        # Aplicar margem de seguran?a
        safe_balance = balance.available * self.BALANCE_SAFETY_MARGIN
        
        if side == OrderSide.BUY:
            # Para compra, precisa de quote currency (ex: USDT)
            required_currency = market.quote_currency
            required_amount = cost
        else:
            # Para venda, precisa de base currency (ex: BTC)
            required_currency = market.base_currency
            required_amount = cost
        
        # Verificar se a moeda do saldo bate
        if balance.currency.upper() != required_currency.upper():
            result.errors.append(
                f"Moeda do saldo ({balance.currency}) n?o corresponde "
                f"? moeda necess?ria ({required_currency})"
            )
            return
        
        if safe_balance < required_amount:
            result.errors.append(
                f"Saldo insuficiente: dispon?vel {balance.available:.8f} {balance.currency}, "
                f"necess?rio {required_amount:.8f} {required_currency} "
                f"(incluindo taxa estimada de {fee:.8f})"
            )
            
            # Calcular quanto pode comprar/vender
            max_possible = safe_balance
            if side == OrderSide.BUY:
                max_possible = safe_balance / (Decimal("1") + self.fee_rate)
            
            result.warnings.append(
                f"M?ximo poss?vel: {max_possible:.8f} {required_currency}"
            )
    
    def calculate_max_order(
        self,
        side: OrderSide,
        price: Decimal,
        market: MarketInfo,
        balance: Balance
    ) -> Decimal:
        """
        Calcula a quantidade m?xima poss?vel de uma ordem.
        
        Args:
            side: BUY ou SELL
            price: Pre?o estimado
            market: Informa??es do mercado
            balance: Saldo dispon?vel
            
        Returns:
            Quantidade m?xima poss?vel
        """
        safe_balance = balance.available * self.BALANCE_SAFETY_MARGIN
        
        if side == OrderSide.BUY:
            # Quanto de base pode comprar com o saldo em quote
            # balance = quantity * price * (1 + fee)
            # quantity = balance / (price * (1 + fee))
            max_qty = safe_balance / (price * (Decimal("1") + self.fee_rate))
        else:
            # Para venda, ? o pr?prio saldo em base
            max_qty = safe_balance
        
        # Ajustar para precis?o do mercado
        max_qty = self._adjust_quantity(max_qty, market)
        
        # Garantir que n?o excede o m?ximo do mercado
        if market.max_order_size > 0:
            max_qty = min(max_qty, market.max_order_size)
        
        return max_qty


# ==================== EXCHANGE-SPECIFIC MARKET INFO ====================

async def get_market_info_from_ccxt(symbol: str, exchange) -> MarketInfo:
    """
    Obt?m informa??es de mercado de QUALQUER exchange via CCXT.
    
    Usa market['precision'] para obter:
    - precision.amount: casas decimais para quantidade
    - precision.price: casas decimais para pre?o
    
    ?? IMPORTANTE: Diferentes exchanges t?m diferentes precis?es!
    - KuCoin: alguns pares com 6 casas decimais
    - Binance: at? 8 casas decimais
    - Bybit: varia por par
    
    O CCXT normaliza tudo isso para voc?.
    """
    try:
        markets = await exchange.load_markets()
        market = markets.get(symbol)
        
        if not market:
            raise ValueError(f"Mercado {symbol} n?o encontrado na exchange")
        
        limits = market.get("limits", {})
        precision = market.get("precision", {})
        
        # CCXT precision pode ser int (casas decimais) ou float (tick size)
        # Normalizar para ambos os formatos
        price_precision = precision.get("price", 8)
        amount_precision = precision.get("amount", 8)
        
        # Calcular tick_size e step_size a partir da precis?o se n?o dispon?vel
        # Algumas exchanges retornam como float direto, outras como int
        if isinstance(price_precision, float) and price_precision < 1:
            tick_size = Decimal(str(price_precision))
            price_precision_int = abs(Decimal(str(price_precision)).as_tuple().exponent)
        else:
            price_precision_int = int(price_precision)
            tick_size = Decimal(10) ** -price_precision_int
            
        if isinstance(amount_precision, float) and amount_precision < 1:
            step_size = Decimal(str(amount_precision))
            amount_precision_int = abs(Decimal(str(amount_precision)).as_tuple().exponent)
        else:
            amount_precision_int = int(amount_precision)
            step_size = Decimal(10) ** -amount_precision_int
        
        # Tentar obter valores espec?ficos da exchange (info raw)
        info = market.get("info", {})
        if info.get("priceIncrement"):
            tick_size = Decimal(str(info["priceIncrement"]))
        if info.get("baseIncrement"):
            step_size = Decimal(str(info["baseIncrement"]))
        if info.get("tickSize"):
            tick_size = Decimal(str(info["tickSize"]))
        if info.get("stepSize") or info.get("lotSize"):
            step_size = Decimal(str(info.get("stepSize") or info.get("lotSize")))
        
        logger.debug(
            f"? Precis?o {symbol}: price={price_precision_int} decimais, "
            f"amount={amount_precision_int} decimais, "
            f"tick={tick_size}, step={step_size}"
        )
        
        return MarketInfo(
            symbol=symbol,
            base_currency=market.get("base", ""),
            quote_currency=market.get("quote", ""),
            min_order_size=Decimal(str(limits.get("amount", {}).get("min", 0) or 0)),
            max_order_size=Decimal(str(limits.get("amount", {}).get("max", 0) or 0)),
            min_notional=Decimal(str(limits.get("cost", {}).get("min", 10) or 10)),
            price_precision=price_precision_int,
            quantity_precision=amount_precision_int,
            tick_size=tick_size,
            step_size=step_size,
        )
    except Exception as e:
        logger.error(f"? Erro ao obter info do mercado {symbol}: {e}")
        # Retornar valores padr?o seguros (conservadores)
        return MarketInfo(
            symbol=symbol,
            base_currency=symbol.split("/")[0] if "/" in symbol else symbol[:3],
            quote_currency=symbol.split("/")[1] if "/" in symbol else "USDT",
            min_order_size=Decimal("0.0001"),
            max_order_size=Decimal("0"),
            min_notional=Decimal("10"),
            price_precision=8,
            quantity_precision=8,
            tick_size=Decimal("0.00000001"),
            step_size=Decimal("0.00000001"),
        )


# Alias para compatibilidade
async def get_kucoin_market_info(symbol: str, exchange) -> MarketInfo:
    """Alias para get_market_info_from_ccxt - funciona com qualquer exchange."""
    return await get_market_info_from_ccxt(symbol, exchange)


async def get_balance_for_currency(currency: str, exchange) -> Balance:
    """Obt?m saldo de uma moeda na exchange."""
    try:
        balances = await exchange.fetch_balance()
        currency_balance = balances.get(currency, {})
        
        return Balance(
            currency=currency,
            available=Decimal(str(currency_balance.get("free", 0) or 0)),
            locked=Decimal(str(currency_balance.get("used", 0) or 0)),
            total=Decimal(str(currency_balance.get("total", 0) or 0)),
        )
    except Exception as e:
        logger.error(f"? Erro ao obter saldo de {currency}: {e}")
        return Balance(
            currency=currency,
            available=Decimal("0"),
            locked=Decimal("0"),
            total=Decimal("0"),
        )


# ==================== HIGH-LEVEL VALIDATION ====================

async def validate_trade(
    exchange,
    symbol: str,
    side: str,
    quantity: float,
    price: float = None,
    order_type: str = "limit"
) -> PreTradeValidation:
    """
    Fun??o de alto n?vel para validar uma trade.
    
    Args:
        exchange: Inst?ncia CCXT da exchange
        symbol: Par de trading (ex: BTC/USDT)
        side: "buy" ou "sell"
        quantity: Quantidade desejada
        price: Pre?o (None para market order)
        order_type: "limit" ou "market"
        
    Returns:
        PreTradeValidation com resultado
    """
    # Obter informa??es do mercado
    market_info = await get_kucoin_market_info(symbol, exchange)
    
    # Determinar moeda necess?ria
    if side.lower() == "buy":
        required_currency = market_info.quote_currency
    else:
        required_currency = market_info.base_currency
    
    # Obter saldo
    balance = await get_balance_for_currency(required_currency, exchange)
    
    # Para market order, usar pre?o atual estimado
    is_market = order_type.lower() == "market"
    if is_market and not price:
        ticker = await exchange.fetch_ticker(symbol)
        price = ticker.get("last", 0)
    
    # Validar
    validator = PreTradeValidator()
    result = validator.validate_order(
        side=OrderSide(side.lower()),
        quantity=Decimal(str(quantity)),
        price=Decimal(str(price or 0)),
        market=market_info,
        balance=balance,
        is_market_order=is_market
    )
    
    logger.info(
        f"? Valida??o pr?-trade: {symbol} {side} {quantity} @ {price} - "
        f"{'? OK' if result.valid else '? FALHOU'}"
    )
    
    if not result.valid:
        for error in result.errors:
            logger.warning(f"   ? {error}")
    
    return result


# ==================== HELPER FUNCTIONS ====================

def get_quote_currency(symbol: str) -> str:
    """
    Extrai a moeda de cotação de um símbolo de negociação.
    
    Exemplos:
    - "BTC/USDT" → "USDT"
    - "ETH-USD" → "USD"
    - "BTC_USDT" → "USDT"
    
    Args:
        symbol: Símbolo de negociação
        
    Returns:
        Moeda de cotação
    """
    # Tentar diferentes separadores
    for sep in ["/", "-", "_"]:
        if sep in symbol:
            parts = symbol.split(sep)
            if len(parts) >= 2:
                return parts[1].strip().upper()
    
    # Fallback: assumir último 4 caracteres
    if len(symbol) > 4:
        return symbol[-4:].upper()
    
    return symbol.upper()


def get_base_currency(symbol: str) -> str:
    """
    Extrai a moeda base de um símbolo de negociação.
    
    Exemplos:
    - "BTC/USDT" → "BTC"
    - "ETH-USD" → "ETH"
    - "BTC_USDT" → "BTC"
    
    Args:
        symbol: Símbolo de negociação
        
    Returns:
        Moeda base
    """
    # Tentar diferentes separadores
    for sep in ["/", "-", "_"]:
        if sep in symbol:
            parts = symbol.split(sep)
            return parts[0].strip().upper()
    
    # Fallback: assumir primeiros 3-4 caracteres
    for length in [4, 3]:
        if len(symbol) >= length:
            return symbol[:length].upper()
    
    return symbol.upper()


async def get_last_price(symbol: str, exchange=None) -> Decimal:
    """
    Obtém o último preço de um símbolo.
    
    Args:
        symbol: Símbolo de negociação
        exchange: Instância CCXT da exchange (optional)
        
    Returns:
        Último preço como Decimal
    """
    try:
        if exchange:
            ticker = await exchange.fetch_ticker(symbol)
            return Decimal(str(ticker.get("last", 0)))
    except Exception as e:
        logger.warning(f"? Erro ao obter último preço de {symbol}: {e}")
    
    return Decimal("0")


# ==================== TASK 1.2: VALIDATE_ORDER_EXECUTABLE ====================

async def validate_order_executable(
    user_id: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    current_price: Decimal = None
) -> Tuple[bool, Optional[str]]:
    """
    Valida se uma ordem pode ser executada verificando:
    ✓ Credenciais disponíveis
    ✓ Saldo suficiente (balance real vs. requerido)
    ✓ Tamanho dentro de limites (min/max ordem)
    ✓ Acima do mínimo notional (min valor da ordem)
    ✓ Sem violação de limites de risco
    ✓ Máximo de posições abertas não atingido
    
    Esta função é O GATEWAY principal antes de executar qualquer ordem real.
    
    Args:
        user_id: ID do usuário
        symbol: Símbolo (ex: "BTC-USDT")
        side: "BUY" ou "SELL"
        quantity: Quantidade desejada
        current_price: Preço atual (None = obter automaticamente)
        
    Returns:
        Tuple[bool, Optional[str]]:
            - (True, None) se validação passou
            - (False, "error message") se validação falhou
            
    Examples:
        # Validar compra de 0.1 BTC
        is_valid, error = await validate_order_executable(
            user_id="user_123",
            symbol="BTC-USDT",
            side="BUY",
            quantity=Decimal("0.1"),
            current_price=Decimal("42000")
        )
        
        if not is_valid:
            logger.error(f"Validação falhou: {error}")
            return
        
        # Proceder com a execução da ordem...
    """
    logger.info(f"? Validando ordem: user={user_id}, {symbol} {side} {quantity}")
    
    try:
        # ✓ 1. VALIDAR CREDENCIAIS
        from app.trading.credentials_repository import CredentialsRepository
        
        creds = await CredentialsRepository.get_credentials(user_id, "kucoin")
        if not creds:
            error_msg = f"Sem credenciais KuCoin configuradas para user={user_id}"
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # ✓ 2. CONECTAR À EXCHANGE
        from app.trading.kucoin_client import KuCoinClient
        
        client = KuCoinClient(creds, is_testnet=True)
        
        # ✓ 3. OBTER SALDO REAL
        try:
            balance_data = await client.get_account_balance()
        except Exception as e:
            error_msg = f"Erro ao obter saldo: {str(e)}"
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # ✓ 4. OBTER INFORMAÇÕES DO MERCADO
        try:
            market_info = await get_market_info_from_ccxt(symbol, client.exchange)
        except Exception as e:
            error_msg = f"Erro ao obter info do mercado {symbol}: {str(e)}"
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # ✓ 5. VALIDAR QUANTIDADE (min/max)
        if quantity < market_info.min_order_size:
            error_msg = (
                f"Quantidade {quantity} abaixo do mínimo "
                f"{market_info.min_order_size} {market_info.base_currency}"
            )
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        if market_info.max_order_size > 0 and quantity > market_info.max_order_size:
            error_msg = (
                f"Quantidade {quantity} acima do máximo "
                f"{market_info.max_order_size} {market_info.base_currency}"
            )
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # ✓ 6. VALIDAR SALDO DISPONÍVEL
        if side.upper() == "BUY":
            # Para BUY: precisamos de quote currency (ex: USDT)
            quote_currency = market_info.quote_currency
            
            # Obter preço
            if current_price is None:
                current_price = await get_last_price(symbol, client.exchange)
            
            # Calcular custo estimado
            estimated_cost = quantity * current_price
            
            # Aplicar margem de taxa (assumir 0.1%)
            fee_rate = Decimal("0.001")
            estimated_cost_with_fee = estimated_cost * (Decimal("1") + fee_rate)
            
            # Obter saldo disponível
            quote_balance = balance_data.get(quote_currency, {}).get("available", Decimal("0"))
            
            logger.debug(
                f"  BUY validation: precisa={estimated_cost_with_fee:.2f} {quote_currency}, "
                f"tem={quote_balance:.2f}"
            )
            
            if quote_balance < estimated_cost_with_fee:
                error_msg = (
                    f"Saldo insuficiente em {quote_currency}. "
                    f"Precisa: {estimated_cost_with_fee:.8f}, "
                    f"Tem: {quote_balance:.8f}"
                )
                logger.warning(f"! {error_msg}")
                return False, error_msg
        
        elif side.upper() == "SELL":
            # Para SELL: precisamos de base currency (ex: BTC)
            base_currency = market_info.base_currency
            
            # Obter saldo disponível
            base_balance = balance_data.get(base_currency, {}).get("available", Decimal("0"))
            
            logger.debug(
                f"  SELL validation: precisa={quantity:.8f} {base_currency}, "
                f"tem={base_balance:.8f}"
            )
            
            if base_balance < quantity:
                error_msg = (
                    f"Saldo insuficiente em {base_currency}. "
                    f"Precisa: {quantity:.8f}, "
                    f"Tem: {base_balance:.8f}"
                )
                logger.warning(f"! {error_msg}")
                return False, error_msg
        
        else:
            error_msg = f"Side inválido: {side}. Deve ser BUY ou SELL"
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # ✓ 7. VALIDAR NOTIONAL MÍNIMO
        if current_price is None:
            current_price = await get_last_price(symbol, client.exchange)
        
        notional = quantity * current_price
        if notional < market_info.min_notional:
            error_msg = (
                f"Valor da ordem {notional:.2f} {market_info.quote_currency} "
                f"abaixo do mínimo {market_info.min_notional} {market_info.quote_currency}"
            )
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # ✓ 8. VALIDAR LIMITES DE RISCO
        from app.trading.risk_manager import RiskManager
        
        risk_manager = RiskManager()
        
        # Verificar kill-switch
        if risk_manager._kill_switched and user_id in risk_manager._kill_switched:
            error_msg = "Kill-switch ativo. Contate admin."
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # Verificar cooldown
        if risk_manager.is_in_cooldown(user_id):
            error_msg = "Cooldown ativo após loss anterior. Aguarde."
            logger.warning(f"! {error_msg}")
            return False, error_msg
        
        # ✓ 9. VALIDAR MAX POSIÇÕES ABERTAS
        # Tentar obter PositionManager
        try:
            from app.bots.position_manager import PositionManager
            
            position_manager = PositionManager()
            open_positions = await position_manager.get_open_positions(user_id)
            max_open = risk_manager.config.max_open_positions
            
            if len(open_positions) >= max_open:
                error_msg = (
                    f"Máximo de posições abertas ({max_open}) atingido. "
                    f"Feche uma posição antes de abrir nova."
                )
                logger.warning(f"! {error_msg}")
                return False, error_msg
        except ImportError:
            logger.debug("PositionManager não disponível, pulando validação")
        except Exception as e:
            logger.warning(f"Erro ao validar max posições: {e}")
            # Não falhar validação por causa disto
        
        # ✓ VALIDAÇÃO BEM-SUCEDIDA!
        logger.info(
            f"✓ Ordem validada com sucesso: {symbol} {side} {quantity} @ {current_price}"
        )
        return True, None
    
    except Exception as e:
        error_msg = f"Erro durante validação: {str(e)}"
        logger.error(f"? {error_msg}")
        return False, error_msg
