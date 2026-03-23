#!/usr/bin/env python3
"""
🤖 Robot Data Updater - Atualiza dados dos robôs com simulações realistas
Atualiza: lucro, usuários, taxa de acerto, ordem dos vencedores
Executa continuamente para manter dados frescos e realistas
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncClient
from app.core.database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sample Bot Names and Creators
SAMPLE_BOTS = [
    {
        'name': 'Bitcoin Scalper Pro',
        'symbol': 'BTC/USDT',
        'strategy': 'Scalping',
        'creator': 'Li Wei',
        'creator_country': '🇨🇳 China',
        'base_profitability': 0.85,
        'volatility': 0.15
    },
    {
        'name': 'Legend Slayer',
        'symbol': 'ETH/USDT',
        'strategy': 'Combined',
        'creator': 'Dmitri Volkoff',
        'creator_country': '🇷🇺 Russia',
        'base_profitability': 0.82,
        'volatility': 0.18
    },
    {
        'name': 'Grid Precision',
        'symbol': 'BNB/USDT',
        'strategy': 'Grid Trading',
        'creator': 'Kenji Tanaka',
        'creator_country': '🇯🇵 Japan',
        'base_profitability': 0.78,
        'volatility': 0.12
    },
    {
        'name': 'Momentum Rider',
        'symbol': 'SOL/USDT',
        'strategy': 'Momentum',
        'creator': 'Sarah Johnson',
        'creator_country': '🇺🇸 USA',
        'base_profitability': 0.75,
        'volatility': 0.22
    },
    {
        'name': 'DCA Master',
        'symbol': 'ADA/USDT',
        'strategy': 'DCA',
        'creator': 'Miguel Garcia',
        'creator_country': '🇪🇸 Spain',
        'base_profitability': 0.72,
        'volatility': 0.10
    },
    {
        'name': 'Trend Analyzer',
        'symbol': 'XRP/USDT',
        'strategy': 'Trend',
        'creator': 'Yuki Kimura',
        'creator_country': '🇯🇵 Japan',
        'base_profitability': 0.70,
        'volatility': 0.14
    },
    {
        'name': 'AI Supremacy',
        'symbol': 'AVAX/USDT',
        'strategy': 'Machine Learning',
        'creator': 'Alex Chen',
        'creator_country': '🇹🇨 Taiwan',
        'base_profitability': 0.68,
        'volatility': 0.20
    },
    {
        'name': 'Arbitrage Pro',
        'symbol': 'LINK/USDT',
        'strategy': 'Arbitrage',
        'creator': 'Emma Watson',
        'creator_country': '🇬🇧 UK',
        'base_profitability': 0.65,
        'volatility': 0.08
    },
    {
        'name': 'Volatility Hunter',
        'symbol': 'DOGE/USDT',
        'strategy': 'Volatility',
        'creator': 'Carlos Rodriguez',
        'creator_country': '🇲🇽 Mexico',
        'base_profitability': 0.62,
        'volatility': 0.25
    },
    {
        'name': 'Smart Allocator',
        'symbol': 'MATIC/USDT',
        'strategy': 'Portfolio',
        'creator': 'Fatima Al-Mansouri',
        'creator_country': '🇦🇪 UAE',
        'base_profitability': 0.60,
        'volatility': 0.11
    },
]

class RobotDataUpdater:
    def __init__(self):
        self.db = None
        self.bots_col = None
        self.trades_col = None
        self.instances_col = None
        self.running = True

    async def connect(self):
        """Connect to database"""
        try:
            self.db = get_db()
            self.bots_col = self.db['bots']
            self.trades_col = self.db['simulated_trades']
            self.instances_col = self.db['bot_instances']
            logger.info('✅ Conectado ao banco de dados')
        except Exception as e:
            logger.error(f'❌ Erro ao conectar: {e}')
            raise

    async def initialize_sample_bots(self):
        """Create sample bots if they don't exist"""
        try:
            for bot_data in SAMPLE_BOTS:
                existing = await self.bots_col.find_one({'name': bot_data['name']})
                if not existing:
                    bot = {
                        'name': bot_data['name'],
                        'symbol': bot_data['symbol'],
                        'strategy': bot_data['strategy'],
                        'creator': bot_data['creator'],
                        'creator_country': bot_data['creator_country'],
                        'base_profitability': bot_data['base_profitability'],
                        'volatility': bot_data['volatility'],
                        'status': 'active',
                        'avg_pnl_percent': random.uniform(0.5, 5.0),
                        'win_rate': random.uniform(55, 75),
                        'total_trades': 0,
                        'total_profit': 0,
                        'users_count': random.randint(5, 100),
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                    await self.bots_col.insert_one(bot)
                    logger.info(f'✨ Robô criado: {bot_data["name"]}')
        except Exception as e:
            logger.error(f'❌ Erro ao inicializar robôs: {e}')

    async def generate_realistic_trade(self, bot_data, bot_id):
        """Generate a realistic trade for a bot"""
        try:
            # Base profitability with random variance
            profitability = bot_data['base_profitability']
            volatility = bot_data['volatility']
            
            # Random market conditions
            market_factor = random.gauss(1.0, volatility)
            win_probability = profitability * market_factor
            
            # Determine if trade wins or loses
            is_winning = random.random() < max(0.4, min(0.9, win_probability))
            
            # Trade size and profit/loss
            trade_size = random.uniform(100, 500)
            
            if is_winning:
                # Winning trade: 0.5% to 3% profit
                pnl = trade_size * random.uniform(0.005, 0.03)
                pnl_percent = random.uniform(0.5, 3.0)
            else:
                # Losing trade: -0.1% to -2% loss
                pnl = -trade_size * random.uniform(0.001, 0.02)
                pnl_percent = -random.uniform(0.1, 2.0)
            
            # Create trade record
            trade = {
                'bot_id': bot_id,
                'instance_id': bot_id,  # Using bot_id as instance_id for simplicity
                'symbol': bot_data['symbol'],
                'entry_price': random.uniform(100, 50000),
                'exit_price': 0,  # Will be calculated
                'quantity': random.uniform(0.1, 10),
                'pnl': round(pnl, 2),
                'pnl_percent': round(pnl_percent, 2),
                'status': 'closed',
                'type': 'long' if random.random() > 0.3 else 'short',
                'timestamp': datetime.utcnow(),
                'created_at': datetime.utcnow()
            }
            
            # Insert trade
            await self.trades_col.insert_one(trade)
            
            return {
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'is_winning': is_winning
            }
            
        except Exception as e:
            logger.error(f'❌ Erro ao gerar trade: {e}')
            return None

    async def update_bot_performance(self, bot_info):
        """Update bot performance metrics"""
        try:
            bot_data = next(b for b in SAMPLE_BOTS if b['name'] == bot_info['name'])
            
            # Generate 2-5 trades per update
            num_trades = random.randint(2, 5)
            total_pnl = 0
            winning_trades = 0
            
            for _ in range(num_trades):
                trade_result = await self.generate_realistic_trade(bot_data, bot_info['_id'])
                if trade_result:
                    total_pnl += trade_result['pnl']
                    if trade_result['is_winning']:
                        winning_trades += 1
            
            # Update bot metrics
            current_metrics = await self.bots_col.find_one({'_id': bot_info['_id']})
            
            new_win_rate = (current_metrics.get('win_rate', 50) * 0.95 + 
                           (winning_trades / max(num_trades, 1)) * 100 * 0.05)
            
            new_pnl_percent = (current_metrics.get('avg_pnl_percent', 1.0) * 0.95 +
                              random.uniform(0.1, 2.0) * 0.05)
            
            # Update users count (grow by 0-3 new users)
            new_users = current_metrics.get('users_count', 0) + random.randint(0, 3)
            
            # Update bot record
            await self.bots_col.update_one(
                {'_id': bot_info['_id']},
                {
                    '$set': {
                        'total_profit': current_metrics.get('total_profit', 0) + total_pnl,
                        'total_trades': current_metrics.get('total_trades', 0) + num_trades,
                        'win_rate': round(new_win_rate, 2),
                        'avg_pnl_percent': round(new_pnl_percent, 2),
                        'users_count': new_users,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            logger.info(
                f'📊 {bot_info["name"]} atualizado: '
                f'${total_pnl:.2f} PnL, {winning_trades}/{num_trades} vitórias, '
                f'{new_users} usuários'
            )
            
        except Exception as e:
            logger.error(f'❌ Erro ao atualizar performance: {e}')

    async def update_all_bots(self):
        """Update performance for all bots"""
        try:
            bots = await self.bots_col.find({'status': 'active'}).to_list(None)
            
            for bot in bots:
                await self.update_bot_performance(bot)
            
            logger.info(f'✅ {len(bots)} robôs atualizados com sucesso')
            
        except Exception as e:
            logger.error(f'❌ Erro ao atualizar todos os robôs: {e}')

    async def cleanup_old_trades(self):
        """Delete trades older than 90 days to keep DB clean"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            result = await self.trades_col.delete_many({'timestamp': {'$lt': cutoff_date}})
            
            if result.deleted_count > 0:
                logger.info(f'🧹 Limpeza: {result.deleted_count} trades antigos removidos')
                
        except Exception as e:
            logger.error(f'❌ Erro ao limpar trades: {e}')

    async def run_continuous_update(self, update_interval=300):
        """Run continuous updates every N seconds (default: 5 minutes)"""
        logger.info(f'🚀 Iniciando atualização contínua (intervalo: {update_interval}s)')
        
        while self.running:
            try:
                await self.update_all_bots()
                
                # Cleanup old trades every 6 updates (30 minutes)
                if random.random() < 0.16:
                    await self.cleanup_old_trades()
                
                # Wait before next update
                await asyncio.sleep(update_interval)
                
            except Exception as e:
                logger.error(f'❌ Erro no loop de atualização: {e}')
                await asyncio.sleep(60)  # Wait before retry

    async def stop(self):
        """Stop the updater"""
        self.running = False
        logger.info('⛔ Updater parado')

async def main():
    """Main entry point"""
    updater = RobotDataUpdater()
    
    try:
        await updater.connect()
        await updater.initialize_sample_bots()
        
        # Run continuous updates
        await updater.run_continuous_update(update_interval=300)  # 5 minutes
        
    except KeyboardInterrupt:
        logger.info('⛔ Interrupção do usuário')
        await updater.stop()
    except Exception as e:
        logger.error(f'❌ Erro fatal: {e}')
        raise

if __name__ == '__main__':
    asyncio.run(main())
