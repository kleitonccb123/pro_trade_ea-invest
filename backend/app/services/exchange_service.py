# backend/app/services/exchange_service.py
import ccxt.async_support as ccxt
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class ExchangeService:
    def __init__(self, use_sandbox=True):
        # Configura??es da KuCoin
        # Nota: KuCoin n?o tem sandbox mode no CCXT, use testnet ou conta real com pouco dinheiro
        self.exchange = ccxt.kucoin({
            'apiKey': os.getenv('KUCOIN_API_KEY'),
            'secret': os.getenv('KUCOIN_API_SECRET'),
            'password': os.getenv('KUCOIN_API_PASSPHRASE'),
            'enableRateLimit': True,
        })

        # KuCoin n?o suporta sandbox mode no CCXT
        # Para testes, use uma conta real com pouco dinheiro ou aguarde implementa??o de testnet
        if use_sandbox:
            logger.warning("??  KuCoin n?o suporta sandbox mode no CCXT. Usando conta real (configure chaves de teste).")
            logger.info("? Para testes seguros, use uma conta KuCoin com pouco saldo.")

    async def get_balance(self):
        try:
            balance = await self.exchange.fetch_balance()
            return balance['total']
        except Exception as e:
            logger.error(f"Erro ao buscar saldo: {e}")
            return None

    async def create_order(self, symbol, side, amount, price=None, type='market'):
        """
        Cria uma ordem na Exchange.
        side: 'buy' ou 'sell'
        type: 'market' (execu??o imediata) ou 'limit' (pre?o fixo)
        """
        try:
            if type == 'market':
                order = await self.exchange.create_market_order(symbol, side, amount)
            else:
                order = await self.exchange.create_limit_order(symbol, side, amount, price)

            logger.info(f"? Ordem de {side} executada: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"? Falha ao executar ordem: {e}")
            return None

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancela uma ordem espec?fica na Exchange.
        
        Args:
            order_id: ID da ordem a cancelar
            symbol: Par de moedas (ex: BTC/USDT)
            
        Returns:
            True se cancelada com sucesso, False caso contr?rio
        """
        try:
            result = await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"? Ordem cancelada: {order_id}")
            return result is not None
        except ccxt.OrderNotFound:
            logger.warning(f"??  Ordem n?o encontrada (possivelmente j? executada): {order_id}")
            return True  # Retorna True pois ordem n?o existe = objetivo alcan?ado
        except Exception as e:
            logger.error(f"? Erro ao cancelar ordem {order_id}: {e}")
            return False

    async def cancel_all_orders(self, symbol: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Cancela TODAS as ordens abertas para um s?mbolo espec?fico.
        Implementa retry com polling para garantir que as ordens foram realmente canceladas.
        
        Args:
            symbol: Par de moedas (ex: BTC/USDT)
            max_retries: N?mero m?ximo de tentativas
            
        Returns:
            Dict com resultado:
            {
                "success": bool,
                "cancelled_count": int,
                "remaining_orders": int,
                "message": str,
                "error": Optional[str]
            }
        """
        logger.info(f"? Cancelando TODAS as ordens abertas para {symbol}...")
        
        try:
            cancelled_orders = []
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Busca todas as ordens abertas (open orders)
                    open_orders = await self.exchange.fetch_open_orders(symbol)
                    
                    if not open_orders:
                        logger.info(f"? Nenhuma ordem aberta encontrada para {symbol}")
                        return {
                            "success": True,
                            "cancelled_count": len(cancelled_orders),
                            "remaining_orders": 0,
                            "message": "Todas as ordens foram canceladas com sucesso"
                        }
                    
                    # Cancela cada ordem aberta
                    for order in open_orders:
                        try:
                            await self.cancel_order(order['id'], symbol)
                            cancelled_orders.append(order['id'])
                            # Pequeno delay para n?o sobrecarregar a exchange
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            logger.warning(f"??  Erro ao cancelar ordem {order['id']}: {e}")
                    
                    # Verifica se ainda h? ordens abertas (polling)
                    await asyncio.sleep(0.5)  # Aguarda um pouco para exchange processar
                    remaining_orders = await self.exchange.fetch_open_orders(symbol)
                    
                    if not remaining_orders:
                        logger.info(f"? Todas as {len(cancelled_orders)} ordens foram canceladas para {symbol}")
                        return {
                            "success": True,
                            "cancelled_count": len(cancelled_orders),
                            "remaining_orders": 0,
                            "message": f"Canceladas {len(cancelled_orders)} ordens com sucesso"
                        }
                    
                    # Se ainda h? ordens, tenta novamente
                    retry_count += 1
                    logger.warning(
                        f"? Ainda h? {len(remaining_orders)} ordens abertas, "
                        f"tentativa {retry_count}/{max_retries}"
                    )
                    await asyncio.sleep(1)  # Aguarda antes de tentar novamente
                    
                except Exception as e:
                    logger.error(f"? Erro ao buscar/cancelar ordens: {e}")
                    retry_count += 1
                    await asyncio.sleep(1)
            
            # Se chegou aqui, ainda h? ordens ap?s max_retries
            remaining = await self.exchange.fetch_open_orders(symbol)
            return {
                "success": False,
                "cancelled_count": len(cancelled_orders),
                "remaining_orders": len(remaining),
                "message": f"Falha ao cancelar todas as ordens ap?s {max_retries} tentativas",
                "error": f"Ainda h? {len(remaining)} ordens abertas"
            }
            
        except Exception as e:
            logger.error(f"? Erro cr?tico ao cancelar ordens para {symbol}: {e}")
            return {
                "success": False,
                "cancelled_count": 0,
                "remaining_orders": -1,
                "message": "Erro ao cancelar ordens",
                "error": str(e)
            }

    async def close(self):
        await self.exchange.close()


# Inst?ncia ?nica para o sistema
exchange_service = ExchangeService(use_sandbox=True)