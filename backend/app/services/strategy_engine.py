# backend/app/services/strategy_engine.py
import asyncio
import pandas as pd
from datetime import datetime
from decimal import Decimal
from app.services.exchange_service import exchange_service
from app.websockets.notification_hub import notification_hub, Notification, NotificationType, NotificationPriority
from app.core.database import get_db
from app.trading.risk_manager import risk_manager
from bson import ObjectId

class StrategyEngine:
    def __init__(self):
        self.active_tasks = {}

    async def start_bot_logic(self, bot_id: str):
        """Inicia o loop de monitoramento do rob?"""
        if bot_id in self.active_tasks:
            return

        task = asyncio.create_task(self._run_strategy_loop(bot_id))
        self.active_tasks[bot_id] = task

    async def stop_bot_logic(self, bot_id: str):
        """Para o loop de monitoramento"""
        if bot_id in self.active_tasks:
            task = self.active_tasks[bot_id]
            task.cancel()
            del self.active_tasks[bot_id]

    async def _save_trade(self, bot, side, price, amount):
        """Salva um trade no hist?rico do MongoDB"""
        db = get_db()
        
        if side == "buy":
            # Para compras, criar nova posi??o aberta
            trade_data = {
                "user_id": bot["user_id"],
                "bot_id": str(bot["_id"]),
                "symbol": bot["pair"],  # Usando 'pair' diretamente do bot
                "side": side,
                "price": price,
                "amount": amount,
                "pnl": 0.0,  # Ser? calculado quando a posi??o fechar
                "status": "open",  # Posi??o aberta
                "timestamp": datetime.utcnow(),
                "strategy": "SMA_20_Crossover"
            }
            
            # Insere no MongoDB
            result = await db.trades.insert_one(trade_data)
            print(f"? Trade de COMPRA salvo: {result.inserted_id}")
            
        elif side == "sell":
            # Para vendas, fechar posi??o aberta existente
            open_trade = await db.trades.find_one({
                "bot_id": str(bot["_id"]),
                "status": "open"
            })
            
            if open_trade:
                # Calcular PnL da posi??o fechada
                entry_price = open_trade["price"]
                pnl = (price - entry_price) * amount
                
                # Atualizar trade existente para fechado
                await db.trades.update_one(
                    {"_id": open_trade["_id"]},
                    {"$set": {
                        "status": "closed",
                        "exit_price": price,
                        "pnl": round(pnl, 2),
                        "exit_reason": "SIGNAL_EXIT",
                        "timestamp_exit": datetime.utcnow()
                    }}
                )
                print(f"? Trade de VENDA fechado: PnL ${round(pnl, 2)}")
            else:
                print("?? Tentativa de venda sem posi??o aberta!")

        # Opcional: Atualizar estat?sticas do bot
        try:
            await db.bots.update_one(
                {"_id": bot["_id"]},
                {"$inc": {"trades_count": 1, "daily_trades": 1}}
            )
        except Exception as e:
            print(f"?? Erro ao atualizar estat?sticas do bot: {e}")

    async def _check_risk_management(self, bot, current_price):
        """Verifica se ? hora de sair da opera??o por lucro ou perda"""
        db = get_db()
        bot_id = str(bot["_id"])
        
        # 1. Buscar o ?ltimo trade aberto deste rob?
        open_trade = await db.trades.find_one({
            "bot_id": bot_id,
            "status": "open"
        })
        
        if not open_trade:
            return  # N?o h? posi??o aberta para gerenciar

        entry_price = open_trade["price"]
        sl_percent = bot.get("config", {}).get("stop_loss", 0.02)  # 2% padr?o
        tp_percent = bot.get("config", {}).get("take_profit", 0.04)  # 4% padr?o

        # 2. Calcular limites
        stop_loss_price = entry_price * (1 - sl_percent)
        take_profit_price = entry_price * (1 + tp_percent)

        # 3. Verificar Condi??es
        exit_reason = None
        if current_price <= stop_loss_price:
            exit_reason = "STOP_LOSS"
        elif current_price >= take_profit_price:
            exit_reason = "TAKE_PROFIT"

        if exit_reason:
            print(f"? SA?DA DE EMERG?NCIA: {exit_reason} em {current_price}")
            
            # Executar venda na Exchange
            symbol = bot['pair'].replace("/", "-")
            await exchange_service.create_order(symbol, 'sell', open_trade['amount'])
            
            # Calcular PnL Real
            pnl = (current_price - entry_price) * open_trade['amount']
            
            # Atualizar trade no banco para 'closed'
            await db.trades.update_one(
                {"_id": open_trade["_id"]},
                {"$set": {
                    "status": "closed",
                    "exit_price": current_price,
                    "pnl": round(pnl, 2),
                    "exit_reason": exit_reason,
                    "timestamp_exit": datetime.utcnow()
                }}
            )
            
            # Criar notifica??o de sa?da de emerg?ncia
            notification = Notification(
                type=NotificationType.TRADE_EXECUTED,
                title=f"? Sa?da de Emerg?ncia: {exit_reason}",
                message=f"Posi??o fechada automaticamente em {symbol} por {exit_reason}",
                priority=NotificationPriority.URGENT,
                data={
                    "side": "sell",
                    "symbol": symbol,
                    "price": current_price,
                    "entry_price": entry_price,
                    "pnl": round(pnl, 2),
                    "exit_reason": exit_reason,
                    "bot_id": bot_id,
                    "strategy": "RISK_MANAGEMENT"
                }
            )
            # Envia via WebSocket para o dono do bot
            await notification_hub.send_to_user(bot['user_id'], notification)

    async def _run_strategy_loop(self, bot_id: str):
        print(f"? Estrat?gia iniciada para o Bot: {bot_id}")

        while True:
            try:
                # 1. Buscar dados atualizados do Bot no Banco
                db = get_db()
                bot = await db.bots.find_one({"_id": ObjectId(bot_id)})
                if not bot or not bot.get('is_running', False):
                    break

                symbol = bot['pair'].replace("/", "-") # Formato KuCoin: BTC-USDT

                # 2. Buscar Hist?rico de Candles (OHLCV)
                ohlcv = await exchange_service.exchange.fetch_ohlcv(symbol, timeframe='1m', limit=50)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

                # 3. Calcular Indicador (SMA 20)
                df['sma_20'] = df['close'].rolling(window=20).mean()

                current_price = df['close'].iloc[-1]
                sma_20 = df['sma_20'].iloc[-1]

                print(f"? {symbol} | Pre?o: {current_price} | SMA20: {sma_20:.2f}")

                # 5. GEST?O DE RISCO: Verificar Stop Loss e Take Profit ANTES dos sinais
                await self._check_risk_management(bot, current_price)

                # 6. L?gica de Cruzamento (apenas se n?o h? posi??o aberta)
                # Primeiro, verificar se j? temos uma posi??o aberta
                db = get_db()
                open_trade = await db.trades.find_one({
                    "bot_id": bot_id,
                    "status": "open"
                })
                
                has_open_position = open_trade is not None

                if current_price > sma_20 and not has_open_position:
                    print(f"? SINAL DE COMPRA em {symbol}")

                    # Cria notifica??o usando o sistema existente
                    notification = Notification(
                        type=NotificationType.TRADE_EXECUTED,
                        title="? Sinal de Compra Detectado",
                        message=f"Rob? detectou oportunidade de compra em {symbol}",
                        priority=NotificationPriority.HIGH,
                        data={
                            "side": "buy",
                            "symbol": symbol,
                            "price": current_price,
                            "sma_20": sma_20,
                            "bot_id": bot_id,
                            "strategy": "SMA_20_Crossover"
                        }
                    )
                    # Envia via WebSocket para o dono do bot
                    await notification_hub.send_to_user(bot['user_id'], notification)

                    # Salvar trade no hist?rico
                    trade_amount = bot.get('config', {}).get('amount', 100)  # Valor padr?o se n?o definido

                    # ??? Validação de risco antes de executar ordem
                    is_valid, risk_error = await risk_manager.validate_order(
                        user_id=str(bot.get('user_id', '')),
                        symbol=symbol,
                        side='buy',
                        size=Decimal(str(trade_amount)),
                        price=Decimal(str(current_price)),
                    )
                    if not is_valid:
                        print(f"⛔ Ordem de COMPRA BLOQUEADA pelo RiskManager: {risk_error}")
                    else:
                        await self._save_trade(bot, 'buy', current_price, trade_amount)
                        # await exchange_service.create_order(symbol, 'buy', trade_amount)

                elif current_price < sma_20 and has_open_position:
                    print(f"? SINAL DE VENDA em {symbol}")

                    # Cria notifica??o usando o sistema existente
                    notification = Notification(
                        type=NotificationType.TRADE_EXECUTED,
                        title="? Sinal de Venda Detectado",
                        message=f"Rob? detectou oportunidade de venda em {symbol}",
                        priority=NotificationPriority.HIGH,
                        data={
                            "side": "sell",
                            "symbol": symbol,
                            "price": current_price,
                            "sma_20": sma_20,
                            "bot_id": bot_id,
                            "strategy": "SMA_20_Crossover"
                        }
                    )
                    # Envia via WebSocket para o dono do bot
                    await notification_hub.send_to_user(bot['user_id'], notification)

                    # Salvar trade no hist?rico
                    trade_amount = bot.get('config', {}).get('amount', 100)  # Valor padr?o se n?o definido

                    # ??? Validação de risco antes de executar ordem
                    is_valid, risk_error = await risk_manager.validate_order(
                        user_id=str(bot.get('user_id', '')),
                        symbol=symbol,
                        side='sell',
                        size=Decimal(str(trade_amount)),
                        price=Decimal(str(current_price)),
                    )
                    if not is_valid:
                        print(f"⛔ Ordem de VENDA BLOQUEADA pelo RiskManager: {risk_error}")
                    else:
                        await self._save_trade(bot, 'sell', current_price, trade_amount)
                        # await exchange_service.create_order(symbol, 'sell', trade_amount)

                # Esperar o pr?ximo fechamento de candle (1 minuto)
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                print(f"? Bot {bot_id} interrompido.")
                break
            except Exception as e:
                print(f"?? Erro no loop do bot {bot_id}: {e}")
                await asyncio.sleep(10)

strategy_engine = StrategyEngine()