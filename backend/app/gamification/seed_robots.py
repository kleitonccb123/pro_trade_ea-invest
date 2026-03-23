"""
Seed Script - Criação de 20 Robôs Estratégicos com dados de Performance

Cria 20 robôs únicos com:
- Nomes temáticos (Grid Master, RSI Hunter, etc)
- Estratégias variadas
- Performance realista baseada na quinzena atual
- Dados para ranking e gamificação
"""

import random
from datetime import datetime, timedelta

ROBOT_TEMPLATES = [
    # Robôs Grid Trading
    {
        "name": "Grid Master Alpha",
        "strategy": "grid",
        "description": "Especialista em Grid Trading para volatilidade média",
        "pair": "BTC/USDT",
        "base_profit_multiplier": 1.8,
        "consistency": 0.85,
    },
    {
        "name": "Grid Harvester Pro",
        "strategy": "grid",
        "description": "Grid Trading adaptativo para detectar padrões de preço",
        "pair": "ETH/USDT",
        "base_profit_multiplier": 1.9,
        "consistency": 0.82,
    },
    {
        "name": "Grid Precision",
        "strategy": "grid",
        "description": "Grid Trading de alta precisão com stops inteligentes",
        "pair": "XRP/USDT",
        "base_profit_multiplier": 2.1,
        "consistency": 0.88,
    },
    
    # Robôs RSI
    {
        "name": "RSI Hunter Elite",
        "strategy": "rsi",
        "description": "Detecção de sobrecompra/sobrevenda com RSI avançado",
        "pair": "ADA/USDT",
        "base_profit_multiplier": 1.5,
        "consistency": 0.75,
    },
    {
        "name": "RSI Momentum",
        "strategy": "rsi",
        "description": "Segue momentum com RSI e volume",
        "pair": "SOL/USDT",
        "base_profit_multiplier": 2.3,
        "consistency": 0.70,
    },
    {
        "name": "RSI Divergence",
        "strategy": "rsi",
        "description": "Detecta divergências RSI para reversões",
        "pair": "LINK/USDT",
        "base_profit_multiplier": 2.0,
        "consistency": 0.78,
    },
    
    # Robôs MACD
    {
        "name": "MACD Trendsetter",
        "strategy": "macd",
        "description": "Segue tendências usando cruzamentos MACD",
        "pair": "DOT/USDT",
        "base_profit_multiplier": 1.7,
        "consistency": 0.80,
    },
    {
        "name": "MACD Signal Lock",
        "strategy": "macd",
        "description": "MACD com sinais confirmados por volume",
        "pair": "AVAX/USDT",
        "base_profit_multiplier": 2.2,
        "consistency": 0.81,
    },
    {
        "name": "MACD Wave Rider",
        "strategy": "macd",
        "description": "Captura ondas de preço com MACD",
        "pair": "MATIC/USDT",
        "base_profit_multiplier": 1.9,
        "consistency": 0.79,
    },
    
    # Robôs DCA
    {
        "name": "DCA Accumulator",
        "strategy": "dca",
        "description": "Acumula posição com Dollar Cost Averaging",
        "pair": "BTC/USDT",
        "base_profit_multiplier": 1.2,
        "consistency": 0.95,  # DCA é mais consistente
    },
    {
        "name": "DCA Steady Gains",
        "strategy": "dca",
        "description": "Compras consistentes independente do preço",
        "pair": "ETH/USDT",
        "base_profit_multiplier": 1.3,
        "consistency": 0.93,
    },
    {
        "name": "DCA Long Term",
        "strategy": "dca",
        "description": "DCA focado em acumulação de longo prazo",
        "pair": "BNB/USDT",
        "base_profit_multiplier": 1.4,
        "consistency": 0.92,
    },
    
    # Robôs Híbridos (Combos)
    {
        "name": "Hybrid Warrior",
        "strategy": "combined",
        "description": "Combina RSI + MACD para sinais mais fortes",
        "pair": "LTC/USDT",
        "base_profit_multiplier": 2.4,
        "consistency": 0.77,
    },
    {
        "name": "Hybrid Master Pro",
        "strategy": "combined",
        "description": "Sinergia perfeita entre Grid + RSI",
        "pair": "XLM/USDT",
        "base_profit_multiplier": 2.5,
        "consistency": 0.76,
    },
    {
        "name": "Hybrid Flame",
        "strategy": "combined",
        "description": "Performance ardente com estratégia combinada",
        "pair": "DOGE/USDT",
        "base_profit_multiplier": 2.8,
        "consistency": 0.72,
    },
    {
        "name": "Hybrid Thunder",
        "strategy": "combined",
        "description": "Ataca o mercado com força - Híbrido turbo",
        "pair": "SHIB/USDT",
        "base_profit_multiplier": 2.6,
        "consistency": 0.74,
    },
    
    # Robôs Especiais (Nicho)
    {
        "name": "Volatility Dragon",
        "strategy": "grid",
        "description": "Domina mercados altamente voláteis",
        "pair": "PEPE/USDT",
        "base_profit_multiplier": 3.0,
        "consistency": 0.65,  # Mais risco, mais recompensa
    },
    {
        "name": "Scalper Ghost",
        "strategy": "rsi",
        "description": "Scalping invisível com micro-movimentos",
        "pair": "1INCH/USDT",
        "base_profit_multiplier": 1.6,
        "consistency": 0.87,
    },
    {
        "name": "Phantom Profit",
        "strategy": "combined",
        "description": "Lucros fantasmagóricos com timing perfeito",
        "pair": "ENS/USDT",
        "base_profit_multiplier": 2.7,
        "consistency": 0.73,
    },
    {
        "name": "Legend Slayer",
        "strategy": "combined",
        "description": "Lendário - o melhor robô da plataforma",
        "pair": "TAO/USDT",
        "base_profit_multiplier": 3.2,
        "consistency": 0.68,
    },
]


def generate_robot_performance_data(base_multiplier: float, consistency: float, biweekly_period: int):
    """
    Gera dados de performance realistas baseado em multiplicador e consistência.
    
    Args:
        base_multiplier: Multiplicador base de lucro
        consistency: Fator de consistência (0-1)
        biweekly_period: Período da quinzena para variar scores
    
    Returns:
        dict com dados de performance
    """
    # Variação por período para fazer ranking natural
    period_variation = (biweekly_period * 17) % 1000 / 1000.0  # Determinístico
    
    # Lucro em 15 dias (valor em USD)
    base_profit = base_multiplier * 100 * (1 + period_variation * 0.5)
    profit_15d = base_profit * consistency + random.gauss(0, base_profit * 0.1)
    
    # Lucro em 7 dias (aproximadamente 50% de 15 dias)
    profit_7d = profit_15d * 0.52 + random.gauss(0, profit_15d * 0.05)
    
    # Lucro em 24h (aproximadamente 7-8% de 15 dias)
    profit_24h = profit_15d * 0.075 + random.gauss(0, profit_15d * 0.02)
    
    # Taxa de vitória baseada em consistência
    win_rate = (70 + consistency * 25) + random.gauss(0, 3)
    win_rate = max(40, min(98, win_rate))  # Clamp entre 40-98%
    
    # Total de trades (quanto mais tempo, mais trades)
    total_trades = int(20 + base_multiplier * 30 + random.gauss(0, 10))
    
    # Status "ON FIRE" (top 5 com score alto)
    is_on_fire = profit_15d > (base_multiplier * 100 * consistency * 1.3)
    
    return {
        "profit_24h": round(max(0, profit_24h), 2),
        "profit_7d": round(max(0, profit_7d), 2),
        "profit_15d": round(max(0, profit_15d), 2),
        "win_rate": round(max(0, win_rate), 1),
        "total_trades": total_trades,
        "is_on_fire": is_on_fire,
    }


def create_robot_seed_data(user_id: str, current_date: datetime = None):
    """
    Cria dados seed para 20 robôs.
    
    Args:
        user_id: ID do usuário
        current_date: Data atual (para calcular biweekly_period)
    
    Returns:
        List[dict] com dados dos 20 robôs
    """
    if current_date is None:
        current_date = datetime.utcnow()
    
    # Calcula período da quinzena (a cada 15 dias muda)
    biweekly_period = int(current_date.timestamp() / (15 * 24 * 60 * 60))
    
    robots_data = []
    
    for idx, template in enumerate(ROBOT_TEMPLATES):
        performance = generate_robot_performance_data(
            template["base_profit_multiplier"],
            template["consistency"],
            biweekly_period
        )
        
        robot = {
            "name": template["name"],
            "strategy": template["strategy"],
            "description": template["description"],
            "pair": template["pair"],
            "user_id": user_id,
            "is_locked": True,  # Todos começam bloqueados
            "unlock_cost": 500 + (idx * 50),  # Custo variável
            "is_active_slot": False,
            "status": "locked",
            "created_at": current_date - timedelta(days=random.randint(1, 60)),
            **performance,
            "biweekly_rank": None,  # Será calculado pelo backend
            "biweekly_period": biweekly_period,
        }
        
        robots_data.append(robot)
    
    # Classifica por profit_15d para ranking
    robots_data.sort(key=lambda x: x["profit_15d"], reverse=True)
    
    # Atribui ranking
    for rank, robot in enumerate(robots_data, 1):
        robot["biweekly_rank"] = rank
    
    return robots_data


if __name__ == "__main__":
    # Teste
    seed_data = create_robot_seed_data("test_user_123")
    
    print(f"✅ Criados {len(seed_data)} robôs seed\n")
    print("TOP 3:")
    for robot in seed_data[:3]:
        print(f"  🥇 #{robot['biweekly_rank']} - {robot['name']}: +${robot['profit_15d']}")
    
    print("\n" + "="*50)
    print(f"Total de robôs: {len(ROBOT_TEMPLATES)}")
    print(f"Período da quinzena: {int(datetime.utcnow().timestamp() / (15 * 24 * 60 * 60))}")
