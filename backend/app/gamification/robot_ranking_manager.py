"""
Robot Ranking Manager - Gerencia a ordenação dinâmica de robôs por período
Permite ordenar por: Top 10 mensal, semanal, 24h com dados verossímeis

Funcionalidades:
- Gera dados dinâmicos de robôs para diferentes períodos
- Calcula lucro, taxa de vitória e traders ativos baseado no período
- Mantém dados consistentes entre requisições
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from random import Random
import hashlib

logger = logging.getLogger(__name__)

class RobotRankingManager:
    """Gerencia ranking de robôs com suporte a múltiplos períodos"""
    
    # Seed determinística para cada robô (garante dados consistentes)
    ROBOT_SEEDS = {
        'bot_001': 12345,
        'bot_002': 12346,
        'bot_003': 12347,
        'bot_004': 12348,
        'bot_005': 12349,
        'bot_006': 12350,
        'bot_007': 12351,
        'bot_008': 12352,
        'bot_009': 12353,
        'bot_010': 12354,
        'bot_011': 12355,
        'bot_012': 12356,
        'bot_013': 12357,
        'bot_014': 12358,
        'bot_015': 12359,
        'bot_016': 12360,
        'bot_017': 12361,
        'bot_018': 12362,
        'bot_019': 12363,
        'bot_020': 12364,
    }
    
    # Base data dos robôs (template)
    ROBOT_BASE_DATA = {
        'bot_001': {
            'name': 'Volatility Dragon',
            'creator': 'Li Wei',
            'country': '🇨🇳',
            'strategy': 'grid',
            'is_on_fire': True,
            'base_profit_14d': 3450.67,
            'base_win_rate': 68.5,
            'base_traders': 245,
        },
        'bot_002': {
            'name': 'Legend Slayer',
            'creator': 'Dmitri Volkoff',
            'country': '🇷🇺',
            'strategy': 'combined',
            'is_on_fire': True,
            'base_profit_14d': 3200.50,
            'base_win_rate': 65.0,
            'base_traders': 200,
        },
        'bot_003': {
            'name': 'Grid Precision',
            'creator': 'Kenji Tanaka',
            'country': '🇯🇵',
            'strategy': 'grid',
            'is_on_fire': False,
            'base_profit_14d': 2950.25,
            'base_win_rate': 72.0,
            'base_traders': 180,
        },
        'bot_004': {
            'name': 'Hybrid Flame',
            'creator': 'Aviv Cohen',
            'country': '🇮🇱',
            'strategy': 'combined',
            'is_on_fire': False,
            'base_profit_14d': 2800.00,
            'base_win_rate': 70.0,
            'base_traders': 190,
        },
        'bot_005': {
            'name': 'RSI Hunter Elite',
            'creator': 'Marco Stein',
            'country': '🇨🇭',
            'strategy': 'rsi',
            'is_on_fire': False,
            'base_profit_14d': 2600.50,
            'base_win_rate': 65.5,
            'base_traders': 165,
        },
        'bot_006': {
            'name': 'Grid Master Alpha',
            'creator': 'Pedro Silva',
            'country': '🇧🇷',
            'strategy': 'grid',
            'is_on_fire': False,
            'base_profit_14d': 2450.80,
            'base_win_rate': 68.0,
            'base_traders': 155,
        },
        'bot_007': {
            'name': 'MACD Trendsetter',
            'creator': 'Wei Zhang',
            'country': '🇨🇳',
            'strategy': 'macd',
            'is_on_fire': False,
            'base_profit_14d': 2320.40,
            'base_win_rate': 66.5,
            'base_traders': 145,
        },
        'bot_008': {
            'name': 'DCA Accumulator',
            'creator': 'Yuki Yamamoto',
            'country': '🇯🇵',
            'strategy': 'dca',
            'is_on_fire': False,
            'base_profit_14d': 2150.00,
            'base_win_rate': 75.0,
            'base_traders': 120,
        },
        'bot_009': {
            'name': 'Scalper Ghost',
            'creator': 'Natasha Petrov',
            'country': '🇷🇺',
            'strategy': 'rsi',
            'is_on_fire': False,
            'base_profit_14d': 2050.25,
            'base_win_rate': 71.0,
            'base_traders': 155,
        },
        'bot_010': {
            'name': 'Grid Harvester Pro',
            'creator': 'David Goldstein',
            'country': '🇮🇱',
            'strategy': 'grid',
            'is_on_fire': False,
            'base_profit_14d': 1920.50,
            'base_win_rate': 69.0,
            'base_traders': 140,
        },
        'bot_011': {
            'name': 'Momentum Master',
            'creator': 'Carlos Ferreira',
            'country': '🇧🇷',
            'strategy': 'grid',
            'is_on_fire': False,
            'base_profit_14d': 1850.75,
            'base_win_rate': 67.5,
            'base_traders': 135,
        },
        'bot_012': {
            'name': 'Volatility Surfer',
            'creator': 'Sofia Zurich',
            'country': '🇨🇭',
            'strategy': 'combined',
            'is_on_fire': False,
            'base_profit_14d': 1750.50,
            'base_win_rate': 64.0,
            'base_traders': 130,
        },
        'bot_013': {
            'name': 'Bollinger Breaker',
            'creator': 'Igor Sokolov',
            'country': '🇷🇺',
            'strategy': 'macd',
            'is_on_fire': False,
            'base_profit_14d': 1680.20,
            'base_win_rate': 69.2,
            'base_traders': 128,
        },
        'bot_014': {
            'name': 'Fisher Predictor',
            'creator': 'Hiroshi Sato',
            'country': '🇯🇵',
            'strategy': 'rsi',
            'is_on_fire': False,
            'base_profit_14d': 1620.40,
            'base_win_rate': 72.5,
            'base_traders': 125,
        },
        'bot_015': {
            'name': 'Arbitrage Prophet',
            'creator': 'Abraham Levi',
            'country': '🇮🇱',
            'strategy': 'dca',
            'is_on_fire': False,
            'base_profit_14d': 1540.60,
            'base_win_rate': 70.8,
            'base_traders': 122,
        },
        'bot_016': {
            'name': 'Quantum Analyzer',
            'creator': 'Rafael Santos',
            'country': '🇧🇷',
            'strategy': 'combined',
            'is_on_fire': False,
            'base_profit_14d': 1480.50,
            'base_win_rate': 66.3,
            'base_traders': 120,
        },
        'bot_017': {
            'name': 'Neural Network Trader',
            'creator': 'Ming Li',
            'country': '🇨🇳',
            'strategy': 'grid',
            'is_on_fire': False,
            'base_profit_14d': 1420.80,
            'base_win_rate': 68.9,
            'base_traders': 118,
        },
        'bot_018': {
            'name': 'Fib Retracement Bot',
            'creator': 'Klaus Mueller',
            'country': '🇨🇭',
            'strategy': 'grid',
            'is_on_fire': False,
            'base_profit_14d': 1360.25,
            'base_win_rate': 65.5,
            'base_traders': 115,
        },
        'bot_019': {
            'name': 'EMA Crossover Pro',
            'creator': 'Anastasia Ivanova',
            'country': '🇷🇺',
            'strategy': 'macd',
            'is_on_fire': False,
            'base_profit_14d': 1290.50,
            'base_win_rate': 63.2,
            'base_traders': 112,
        },
        'bot_020': {
            'name': 'Stochastic Master',
            'creator': 'Akira Nakamura',
            'country': '🇯🇵',
            'strategy': 'rsi',
            'is_on_fire': False,
            'base_profit_14d': 1220.75,
            'base_win_rate': 61.8,
            'base_traders': 110,
        },
    }
    
    @staticmethod
    def _get_robot_rng(robot_id: str, period: str) -> Random:
        """
        Retorna um RNG determinístico para um robô em um período específico.
        Garante que o mesmo robô sempre gera os mesmos dados para o mesmo período.
        
        Args:
            robot_id: ID do robô
            period: 'daily' | 'weekly' | 'monthly'
        
        Returns:
            Random com seed determinística
        """
        seed = RobotRankingManager.ROBOT_SEEDS.get(robot_id, 10000)
        
        # Modifica seed baseado no período para variar dados entre períodos
        period_offset = {'daily': 0, 'weekly': 1000000, 'monthly': 2000000}
        seed += period_offset.get(period, 0)
        
        # Adiciona offset baseado na data para variar diariamente/semanalmente/mensalmente
        now = datetime.utcnow()
        if period == 'daily':
            time_key = now.date().day  # Muda a cada dia
        elif period == 'weekly':
            time_key = now.isocalendar()[1]  # Muda a cada semana
        else:  # monthly
            time_key = now.month  # Muda a cada mês
        
        seed += time_key * 10
        
        return Random(seed)
    
    @staticmethod
    def generate_robot_data(
        robot_id: str,
        period: str = 'monthly'  # 'daily' | 'weekly' | 'monthly'
    ) -> Dict[str, Any]:
        """
        Gera dados verossímeis para um robô em um período específico.
        
        Args:
            robot_id: ID do robô (bot_001 a bot_020)
            period: 'daily' | 'weekly' | 'monthly'
        
        Returns:
            Dict com dados do robô incluindo:
            - profit_24h, profit_7d, profit_15d
            - win_rate
            - active_traders
            - rank (será atribuído após ordenação)
        """
        if robot_id not in RobotRankingManager.ROBOT_BASE_DATA:
            logger.warning(f"Robot {robot_id} não encontrado")
            return {}
        
        base = RobotRankingManager.ROBOT_BASE_DATA[robot_id]
        rng = RobotRankingManager._get_robot_rng(robot_id, period)
        
        # Lucro base (14 dias)
        base_profit = base['base_profit_14d']
        
        # Gera lucro para cada período com variação verossímil
        # Período: monthly (15d) usa 90% do base_profit
        profit_monthly = base_profit * rng.uniform(0.85, 1.15)
        
        # Período: weekly gera ~40% do valor mensal (com variação)
        profit_weekly = (base_profit * 0.4) * rng.uniform(0.70, 1.30)
        
        # Período: daily gera ~10% do valor mensal (mais volátil)
        profit_daily = (base_profit * 0.1) * rng.uniform(0.40, 1.80)
        
        # Taxa de vitória com pequena variação (±5%)
        win_rate = base['base_win_rate'] + rng.uniform(-5, 5)
        win_rate = max(40, min(85, win_rate))  # Limita entre 40% e 85%
        
        # Traders ativos com variação (-30% a +50%)
        active_traders = int(base['base_traders'] * rng.uniform(0.70, 1.50))
        
        # Variação maior para dados de 24h
        if period == 'daily':
            active_traders = int(active_traders * rng.uniform(0.30, 0.80))
        
        return {
            'id': robot_id,
            'name': base['name'],
            'creator': base['creator'],
            'country': base['country'],
            'strategy': base['strategy'],
            'is_on_fire': base['is_on_fire'] or win_rate > 72,
            'profit_24h': round(profit_daily, 2),
            'profit_7d': round(profit_weekly, 2),
            'profit_15d': round(profit_monthly, 2),
            'win_rate': round(win_rate, 1),
            'active_traders': active_traders,
            'timestamp': datetime.utcnow().isoformat(),
        }
    
    @staticmethod
    def get_top_robots(
        period: str = 'monthly',
        limit: int = 10,
        sort_by: str = 'profit'
    ) -> List[Dict[str, Any]]:
        """
        Retorna top N robôs ordenados por um período específico.
        
        Args:
            period: 'daily' | 'weekly' | 'monthly'
            limit: Número de robôs a retornar (padrão 10)
            sort_by: 'profit' | 'win_rate' | 'active_traders'
        
        Returns:
            Lista ordenada de robôs com rank atribuído
        """
        # Gera dados para cada robô
        all_robots = []
        for robot_id in RobotRankingManager.ROBOT_SEEDS.keys():
            robot_data = RobotRankingManager.generate_robot_data(robot_id, period)
            all_robots.append(robot_data)
        
        # Determina chave de ordenação
        sort_key_map = {
            'profit': f'profit_{period.replace("monthly", "15d").replace("weekly", "7d").replace("daily", "24h")}',
            'win_rate': 'win_rate',
            'active_traders': 'active_traders',
        }
        
        sort_key = sort_key_map.get(sort_by, f'profit_{period.replace("monthly", "15d").replace("weekly", "7d").replace("daily", "24h")}')
        
        # Ordena
        all_robots.sort(
            key=lambda x: float(x.get(sort_key, 0)),
            reverse=True
        )
        
        # Atribui rank e limita
        for rank, robot in enumerate(all_robots[:limit], 1):
            robot['rank'] = rank
            robot['medal'] = RobotRankingManager._get_medal(rank)
        
        logger.info(
            f"✅ Top {limit} robôs gerados para período={period}, sort_by={sort_by}"
        )
        
        return all_robots[:limit]
    
    @staticmethod
    def _get_medal(rank: int) -> Optional[str]:
        """Retorna medal emoji pelo rank"""
        medals = {1: '🥇', 2: '🥈', 3: '🥉'}
        return medals.get(rank)
    
    @staticmethod
    def get_period_label(period: str) -> str:
        """Retorna label legível do período"""
        labels = {
            'daily': 'Top 10 - Últimas 24 Horas',
            'weekly': 'Top 10 - Última Semana',
            'monthly': 'Top 10 - Último Mês',
        }
        return labels.get(period, period)


if __name__ == "__main__":
    # Teste local
    print("=== Teste Robot Ranking Manager ===\n")
    
    for period in ['daily', 'weekly', 'monthly']:
        print(f"\n{RobotRankingManager.get_period_label(period)}")
        print("-" * 60)
        
        robots = RobotRankingManager.get_top_robots(period=period, limit=5)
        
        for robot in robots:
            profit_key = f"profit_{period.split('y')[0] if 'ly' in period else period}"
            if period == 'daily':
                profit_key = 'profit_24h'
            elif period == 'weekly':
                profit_key = 'profit_7d'
            else:
                profit_key = 'profit_15d'
            
            print(
                f"{robot['rank']:2d}. {robot['medal']} {robot['name']:30s} | "
                f"${robot.get(profit_key, 0):10.2f} | "
                f"{robot['win_rate']:5.1f}% | "
                f"👥 {robot['active_traders']:3d}"
            )
