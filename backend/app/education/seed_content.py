"""
Seed education content — Creates initial courses and lessons.

Usage:
    cd backend
    python -m app.education.seed_content
"""
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


COURSES = [
    {
        "title": "Introdução ao Trading de Criptomoedas",
        "description": "Aprenda os conceitos fundamentais do trading de criptomoedas, desde o funcionamento dos mercados até suas primeiras operações.",
        "level": "beginner",
        "category": "Fundamentos",
        "tags": ["trading", "cripto", "iniciante", "mercado"],
        "estimated_duration": 120,
        "is_premium": False,
        "instructor_name": "Crypto Trade Hub",
        "status": "published",
        "lessons": [
            {
                "title": "O que é Trading de Criptomoedas?",
                "description": "Entenda o mercado cripto e como funcionam as exchanges.",
                "type": "video",
                "order": 1,
                "video_url": "https://www.youtube.com/watch?v=1YyAzVmP9xQ",
                "video_duration": 900,
                "video_provider": "youtube",
                "is_preview": True,
                "content_markdown": "## O que é Trading?\n\nTrading é a compra e venda de ativos financeiros com o objetivo de lucrar com as variações de preço.\n\n### Mercado de Criptomoedas\n\n- Funciona 24/7\n- Alta volatilidade\n- Descentralizado\n- Global\n\n### Exchanges\n\nPlataformas onde você compra e vende criptomoedas. Ex: KuCoin, Binance.",
            },
            {
                "title": "Tipos de Ordens: Market, Limit e Stop",
                "description": "Aprenda a diferença entre os principais tipos de ordens.",
                "type": "article",
                "order": 2,
                "is_preview": False,
                "content_markdown": "## Tipos de Ordens\n\n### Market Order (Ordem a Mercado)\nExecuta imediatamente ao melhor preço disponível.\n\n**Quando usar:** Quando quer entrar/sair rapidamente.\n\n### Limit Order (Ordem Limitada)\nExecuta apenas no preço que você definir ou melhor.\n\n**Quando usar:** Quando quer controlar o preço de entrada/saída.\n\n### Stop-Loss\nOrdem que é ativada quando o preço atinge um determinado nível.\n\n**Quando usar:** Para limitar perdas em posições abertas.\n\n### Stop-Limit\nCombinação de stop e limit order. Mais controle, mas pode não executar.",
            },
            {
                "title": "Leitura de Gráficos de Candlestick",
                "description": "Como ler e interpretar gráficos de velas japonesas.",
                "type": "video",
                "order": 3,
                "video_url": "https://www.youtube.com/watch?v=KV5QlSgq7lg",
                "video_duration": 1200,
                "video_provider": "youtube",
                "is_preview": False,
                "content_markdown": "## Candlesticks\n\nCada vela representa um período e mostra:\n- **Open** (abertura)\n- **High** (máxima)\n- **Low** (mínima)\n- **Close** (fechamento)\n\n### Velas de Alta (verde)\nClose > Open\n\n### Velas de Baixa (vermelha)\nClose < Open\n\n### Padrões Importantes\n- Doji: indecisão\n- Hammer: possível reversão de alta\n- Engulfing: forte sinal de reversão",
            },
            {
                "title": "Quiz: Fundamentos do Trading",
                "description": "Teste seus conhecimentos sobre os fundamentos abordados.",
                "type": "quiz",
                "order": 4,
                "is_preview": False,
                "content_markdown": "Responda as questões abaixo para testar seu conhecimento.",
                "resources": [
                    {"question": "O mercado de criptomoedas funciona:", "options": ["Apenas em dias úteis", "24 horas, 7 dias por semana", "Apenas durante horário comercial", "Apenas de segunda a sexta"], "correct_index": 1, "explanation": "O mercado cripto não fecha, funcionando 24/7."},
                    {"question": "Uma Market Order:", "options": ["Executa apenas no preço que você define", "Executa imediatamente ao melhor preço", "É cancelada se não executar em 1 hora", "É uma ordem programada"], "correct_index": 1, "explanation": "Market orders executam instantaneamente ao melhor preço disponível."},
                    {"question": "Um Stop-Loss serve para:", "options": ["Aumentar lucros", "Limitar perdas", "Comprar mais barato", "Cancelar ordens"], "correct_index": 1, "explanation": "Stop-Loss é uma proteção que limita o prejuízo em uma operação."},
                ],
            },
        ],
    },
    {
        "title": "Robôs de Trading Automatizado",
        "description": "Conheça as estratégias automatizadas e como configurar robôs de trading na plataforma.",
        "level": "intermediate",
        "category": "Automação",
        "tags": ["bots", "automação", "estratégias", "configuração"],
        "estimated_duration": 180,
        "is_premium": False,
        "instructor_name": "Crypto Trade Hub",
        "status": "published",
        "lessons": [
            {
                "title": "Como Funcionam os Robôs de Trading",
                "description": "Entenda a arquitetura e o ciclo de vida de um bot de trading.",
                "type": "video",
                "order": 1,
                "video_url": "https://www.youtube.com/watch?v=XbOKNq3cPRE",
                "video_duration": 1500,
                "video_provider": "youtube",
                "is_preview": True,
                "content_markdown": "## Robôs de Trading\n\nUm robô de trading é um programa que executa operações automaticamente baseado em regras predefinidas.\n\n### Ciclo de Operação\n\n1. **Receber dados** — WebSocket com preços em tempo real\n2. **Analisar** — Cálculo de indicadores técnicos\n3. **Decidir** — Sinal de compra, venda ou esperar\n4. **Executar** — Criação de ordem na exchange\n5. **Monitorar** — Acompanhar execução e P&L\n\n### Vantagens\n- Opera 24/7\n- Sem emoções\n- Rápido\n- Disciplinado",
            },
            {
                "title": "Estratégia RSI (Índice de Força Relativa)",
                "description": "Como a estratégia RSI identifica pontos de compra e venda.",
                "type": "article",
                "order": 2,
                "is_preview": False,
                "content_markdown": "## Estratégia RSI\n\nO RSI mede a velocidade e magnitude das mudanças de preço.\n\n### Parâmetros\n- **Período:** 14 (padrão)\n- **Sobrevendido:** RSI < 30 (sinal de compra)\n- **Sobrecomprado:** RSI > 70 (sinal de venda)\n\n### Como Configurar na Plataforma\n1. Acesse o painel de Robôs\n2. Clique em 'Criar Bot'\n3. Selecione a estratégia 'RSI'\n4. Configure os parâmetros\n5. Defina capital e par de trading\n6. Ative o bot\n\n### Dicas\n- Combine com filtro de volume\n- Use stop-loss sempre\n- Comece com capital pequeno",
            },
            {
                "title": "Estratégia Grid Trading",
                "description": "Saiba como o Grid Trading funciona em mercados laterais.",
                "type": "article",
                "order": 3,
                "is_preview": False,
                "content_markdown": "## Grid Trading\n\nGrid Trading divide uma faixa de preço em níveis (\"grid\") e coloca ordens de compra e venda em cada nível.\n\n### Como Funciona\n1. Defina um range de preço (ex: $40.000 a $45.000)\n2. Divida em N níveis\n3. Compre quando o preço cai para um nível\n4. Venda quando sobe para o próximo nível\n\n### Ideal Para\n- Mercados laterais (sem tendência clara)\n- Pares com boa liquidez\n\n### Riscos\n- Se o preço sair do range, ordens ficam presas\n- Precisa de capital suficiente para todas as ordens",
            },
            {
                "title": "Estratégia DCA (Dollar Cost Averaging)",
                "description": "Entradas programadas para suavizar o preço médio.",
                "type": "article",
                "order": 4,
                "is_preview": False,
                "content_markdown": "## DCA — Dollar Cost Averaging\n\nComprar uma quantidade fixa em intervalos regulares, independente do preço.\n\n### Configuração\n- **Intervalo:** Diário, semanal ou mensal\n- **Quantidade:** Valor fixo em USDT por compra\n- **Take Profit:** % de lucro para vender automaticamente\n- **Stop Loss:** % máxima de perda\n\n### Vantagens\n- Reduz impacto da volatilidade\n- Não precisa \"acertar o tempo\"\n- Estratégia comprovada a longo prazo\n\n### Na Plataforma\nSelecione DCA ao criar o bot, defina o intervalo e valor por entrada.",
            },
        ],
    },
    {
        "title": "Estratégias Avançadas de Trading",
        "description": "Aprofunde-se em técnicas avançadas como MACD, Scalping e estratégias combinadas.",
        "level": "advanced",
        "category": "Estratégias",
        "tags": ["avançado", "MACD", "scalping", "multi-estratégia"],
        "estimated_duration": 240,
        "is_premium": True,
        "instructor_name": "Crypto Trade Hub",
        "status": "published",
        "lessons": [
            {
                "title": "MACD: Convergência e Divergência",
                "description": "Aprenda a usar o indicador MACD para identificar tendências.",
                "type": "video",
                "order": 1,
                "video_url": "https://www.youtube.com/watch?v=VcUjp1AEyVg",
                "video_duration": 1800,
                "video_provider": "youtube",
                "is_preview": True,
                "content_markdown": "## MACD (Moving Average Convergence Divergence)\n\n### Componentes\n- **MACD Line:** EMA(12) - EMA(26)\n- **Signal Line:** EMA(9) da MACD Line\n- **Histograma:** MACD - Signal\n\n### Sinais\n- **Compra:** MACD cruza acima da Signal Line (crossover bullish)\n- **Venda:** MACD cruza abaixo da Signal Line (crossover bearish)\n- **Divergência:** Preço e MACD em direções opostas → possível reversão\n\n### Configuração na Plataforma\nSelecione 'MACD' ao criar bot. Parâmetros: fast_period=12, slow_period=26, signal_period=9.",
            },
            {
                "title": "Scalping: Operações Rápidas",
                "description": "Técnica de scalping usando Bollinger Bands e RSI rápido.",
                "type": "article",
                "order": 2,
                "is_preview": False,
                "content_markdown": "## Scalping\n\nScalping busca lucros pequenos em operações de curta duração (1-15 minutos).\n\n### Indicadores Usados\n- **Bollinger Bands** (período 20, desvio 2.0)\n- **RSI rápido** (período 7)\n\n### Sinais\n- **Compra:** Preço na banda inferior + RSI < 30\n- **Venda:** Preço na banda superior + RSI > 70\n\n### Parâmetros na Plataforma\n- Profit Target: 0.3%\n- Stop Loss: 0.15%\n- Timeframe: 1min ou 5min\n\n### Riscos\n- Alto número de operações = mais taxas\n- Necessita boa liquidez\n- Não funciona bem em mercados com spread alto",
            },
            {
                "title": "Estratégias Combinadas (Multi-Sinal)",
                "description": "Como combinar RSI + MACD para confirmação dupla.",
                "type": "article",
                "order": 3,
                "is_preview": False,
                "content_markdown": "## Estratégia Combinada (RSI + MACD)\n\nUsa dois indicadores para reduzir sinais falsos.\n\n### Lógica\n- **Compra:** RSI < 30 **E** MACD crossover bullish\n- **Venda:** RSI > 70 **E** MACD crossover bearish\n\n### Vantagens\n- Menos sinais falsos\n- Maior confiança nos trades\n\n### Desvantagens\n- Menos oportunidades (filtro mais rígido)\n- Pode perder movimentos rápidos\n\n### Na Plataforma\nSelecione 'Combined' ou 'Multi' ao criar o bot.",
            },
        ],
    },
    {
        "title": "Gestão de Risco e Capital",
        "description": "Proteja seu capital com técnicas profissionais de gestão de risco.",
        "level": "intermediate",
        "category": "Risco",
        "tags": ["risco", "capital", "stop-loss", "drawdown", "position-size"],
        "estimated_duration": 150,
        "is_premium": False,
        "instructor_name": "Crypto Trade Hub",
        "status": "published",
        "lessons": [
            {
                "title": "Por que Gestão de Risco é Essencial",
                "description": "Entenda por que a maioria perde dinheiro e como evitar.",
                "type": "video",
                "order": 1,
                "video_url": "https://www.youtube.com/watch?v=7PM4rNDTxKA",
                "video_duration": 900,
                "video_provider": "youtube",
                "is_preview": True,
                "content_markdown": "## Gestão de Risco\n\nA gestão de risco é o que separa traders lucrativos dos que perdem dinheiro.\n\n### Regras Fundamentais\n1. **Nunca arrisque mais de 2% do capital por trade**\n2. **Sempre use Stop-Loss**\n3. **Defina seu risco antes de entrar**\n4. **Diversifique pares e estratégias**\n\n### Métricas Importantes\n- **Win Rate:** % de trades lucrativos\n- **Risk/Reward:** Relação risco/retorno por trade\n- **Max Drawdown:** Maior queda do capital\n- **Sharpe Ratio:** Retorno ajustado ao risco",
            },
            {
                "title": "Position Sizing: Calculando o Tamanho da Posição",
                "description": "Como calcular o tamanho ideal de cada operação.",
                "type": "article",
                "order": 2,
                "is_preview": False,
                "content_markdown": "## Position Sizing\n\n### Fórmula Básica\n```\nTamanho = (Capital * % Risco) / (Preço Entrada - Stop Loss)\n```\n\n### Exemplo\n- Capital: $10.000\n- Risco por trade: 2% = $200\n- Preço de entrada BTC: $42.000\n- Stop Loss: $41.500 (diferença: $500)\n- Tamanho: $200 / $500 = 0.4 BTC\n\n### Na Plataforma\nO Risk Manager calcula automaticamente o position size baseado:\n- Capital disponível\n- % risco configurado\n- Distância do stop-loss",
            },
            {
                "title": "As 4 Camadas de Proteção da Plataforma",
                "description": "Como nosso sistema de risco protege seu capital.",
                "type": "article",
                "order": 3,
                "is_preview": False,
                "content_markdown": "## 4 Camadas de Risco\n\n### 1. Kill Switch Global\nPara todos os bots imediatamente em caso de emergência.\n\n### 2. Volatilidade de Mercado\nBloqueia novas operações quando a volatilidade está extrema.\n\n### 3. Limites por Usuário\n- Perda diária máxima\n- Drawdown máximo\n- Tamanho máximo por posição\n\n### 4. Limites por Bot\n- Máximo de perdas consecutivas\n- Pausa automática após N perdas",
            },
        ],
    },
]


async def seed_education_content():
    """Insert initial education courses and lessons into MongoDB."""
    from app.core.database import get_db

    db = get_db()
    courses_col = db["courses"]
    lessons_col = db["lessons"]

    existing = await courses_col.count_documents({})
    if existing > 0:
        logger.info(f"Education content already seeded ({existing} courses). Skipping.")
        return

    for course_data in COURSES:
        lessons = course_data.pop("lessons", [])
        course_data["created_at"] = datetime.utcnow()
        course_data["updated_at"] = datetime.utcnow()
        course_data["published_at"] = datetime.utcnow()
        course_data["lesson_count"] = len(lessons)
        course_data["enrolled_count"] = 0
        course_data["rating"] = 0.0
        course_data["review_count"] = 0

        result = await courses_col.insert_one(course_data)
        course_id = str(result.inserted_id)
        logger.info(f"Created course: {course_data['title']} (ID: {course_id})")

        for lesson in lessons:
            lesson["course_id"] = course_id
            lesson["created_at"] = datetime.utcnow()
            lesson["updated_at"] = datetime.utcnow()
            lesson["view_count"] = 0
            lesson["completion_count"] = 0
            lesson.setdefault("video_url", None)
            lesson.setdefault("video_duration", 0)
            lesson.setdefault("video_provider", None)
            lesson.setdefault("content_markdown", "")
            lesson.setdefault("is_preview", False)
            lesson.setdefault("is_downloadable", False)
            lesson.setdefault("resources", [])
            await lessons_col.insert_one(lesson)

        logger.info(f"  → {len(lessons)} lessons created")

    total = await courses_col.count_documents({})
    logger.info(f"✅ Education seed complete: {total} courses")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_education_content())
