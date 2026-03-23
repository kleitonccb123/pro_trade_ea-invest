"""
Balance Guard Service

Valida se o usu?rio tem saldo suficiente na exchange para executar um bot.

Regra: Antes de ativar um rob?, verificar se o saldo USDT (ou coin de refer?ncia)
na exchange ? suficiente para a 'Order Size' configurada.

Isso evita erros de "Minimum Order Amount" na KuCoin/Binance.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from bson import ObjectId

from app.services.exchange_service import exchange_service
from app.bots import repository as bots_repo

logger = logging.getLogger(__name__)


class BalanceGuard:
    """Valida saldo dispon?vel antes de executar um bot."""

    @classmethod
    async def check_balance(
        cls,
        user_id: str | ObjectId,
        bot_id: str | ObjectId,
        api_key: str,
        api_secret: str,
        exchange: str = "kucoin",
    ) -> Dict[str, Any]:
        """
        Verifica se h? saldo suficiente para executar o bot.

        Args:
            user_id: ID do usu?rio
            bot_id: ID do bot
            api_key: Chave API da exchange
            api_secret: Chave secreta da exchange
            exchange: Nome da exchange (kucoin, binance, etc)

        Returns:
            {
                "has_sufficient_balance": bool,
                "required_amount": float,
                "available_balance": float,
                "currency": str,
                "message": str,
                "warnings": List[str]
            }

        Raises:
            ValueError: Se bot ou configura??o n?o encontrados
            Exception: Erros de conex?o com exchange
        """
        if isinstance(bot_id, str):
            bot_id = ObjectId(bot_id)

        # Buscar configura??o do bot
        bot = await bots_repo.find_bot_by_id(bot_id)
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")

        # Extrair amount da configura??o
        config = bot.get("config", {})
        required_amount = config.get("amount", 1000.0)
        
        # Determinar moeda base (padr?o USDT)
        pair = bot.get("pair", "BTC/USDT")
        quote_currency = pair.split("/")[1] if "/" in pair else "USDT"

        try:
            # Conectar ? exchange e obter saldo
            balance_info = await exchange_service.get_balance(
                api_key=api_key,
                api_secret=api_secret,
                exchange=exchange,
                currency=quote_currency,
            )

            available_balance = balance_info.get("available", 0.0)
            has_sufficient = available_balance >= required_amount

            warnings = []
            if available_balance <= required_amount * 1.1:
                warnings.append(
                    f"?? Low balance: only {available_balance:.2f} {quote_currency}, "
                    f"need {required_amount:.2f}"
                )

            # Check for minimum exchange requirements
            min_order = 10.0  # M?nimo t?pico na KuCoin
            if required_amount < min_order:
                warnings.append(
                    f"?? Order size below exchange minimum ({min_order} {quote_currency})"
                )

            message = (
                f"? Sufficient balance: {available_balance:.2f} {quote_currency}"
                if has_sufficient
                else f"? Insufficient balance: {available_balance:.2f} {quote_currency}, "
                f"need {required_amount:.2f}"
            )

            return {
                "has_sufficient_balance": has_sufficient,
                "required_amount": required_amount,
                "available_balance": available_balance,
                "currency": quote_currency,
                "message": message,
                "warnings": warnings,
            }

        except Exception as e:
            logger.error(f"? Balance check failed for user {user_id}: {str(e)}")
            raise Exception(
                f"Failed to check balance on {exchange}: {str(e)}"
            ) from e

    @classmethod
    async def validate_before_start(
        cls,
        user_id: str | ObjectId,
        bot_id: str | ObjectId,
        api_key: str,
        api_secret: str,
        exchange: str = "kucoin",
    ) -> bool:
        """
        Wrapper simplificado: retorna True/False para saldo suficiente.

        Raises exception se falhar a verifica??o.
        """
        result = await cls.check_balance(
            user_id=user_id,
            bot_id=bot_id,
            api_key=api_key,
            api_secret=api_secret,
            exchange=exchange,
        )

        if not result["has_sufficient_balance"]:
            raise ValueError(result["message"])

        return True
