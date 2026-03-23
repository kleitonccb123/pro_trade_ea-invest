"""
Documentação de Estratégias de Trading para o Crypto Trade Hub

Cada estratégia deve ser um código Python que contenha duas funções obrigatórias:
- on_buy_signal(data)
- on_sell_signal(data)

ESTRUTURA BÁSICA:

```python
def on_buy_signal(data):
    '''
    Função chamada para determinar se um sinal de compra deve ser gerado.
    
    Args:
        data: Dicionário com dados da vela atual e histórico
            - data['close']: Preço de fechamento atual
            - data['open']: Preço de abertura
            - data['high']: Preço máximo
            - data['low']: Preço mínimo
            - data['volume']: Volume de negociação
            - data['closes']: Lista dos últimos N fechamentos
            - data['highs']: Lista dos últimos N máximos
            - data['lows']: Lista dos últimos N mínimos
    
    Returns:
        bool: True se o sinal de compra deve ser gerado, False caso contrário
    '''
    # Sua lógica aqui
    return condition

def on_sell_signal(data):
    '''
    Função chamada para determinar se um sinal de venda deve ser gerado.
    '''
    # Sua lógica aqui
    return condition
```

REGRAS:
1. Use apenas Python padrão e bibliotecas permitidas (numpy, pandas, ta, talib)
2. Não use eval(), exec() ou compile()
3. Não importe modules do SO (os, sys, subprocess, etc)
4. Máximo 500 linhas de código
5. Funções obrigatórias: on_buy_signal() e on_sell_signal()

EXEMPLO 1 - Estratégia SMA:

```python
def on_buy_signal(data):
    '''Comprar quando SMA rápida cruza SMA lenta para cima'''
    if len(data['closes']) < 21:
        return False
    
    sma_fast = sum(data['closes'][-10:]) / 10
    sma_slow = sum(data['closes'][-20:]) / 20
    
    sma_fast_prev = sum(data['closes'][-11:-1]) / 10
    sma_slow_prev = sum(data['closes'][-21:-1]) / 20
    
    return sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow

def on_sell_signal(data):
    '''Vender quando SMA rápida cruza SMA lenta para baixo'''
    if len(data['closes']) < 21:
        return False
    
    sma_fast = sum(data['closes'][-10:]) / 10
    sma_slow = sum(data['closes'][-20:]) / 20
    
    sma_fast_prev = sum(data['closes'][-11:-1]) / 10
    sma_slow_prev = sum(data['closes'][-21:-1]) / 20
    
    return sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow
```

EXEMPLO 2 - Estratégia RSI:

```python
def calculate_rsi(closes, period=14):
    '''Calcula o RSI (Relative Strength Index)'''
    if len(closes) < period + 1:
        return None
    
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100 if avg_gain > 0 else 0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def on_buy_signal(data):
    '''Comprar quando RSI sai da zona de sobrevenda'''
    rsi = calculate_rsi(data['closes'], 14)
    if rsi is None:
        return False
    
    rsi_prev = calculate_rsi(data['closes'][:-1], 14)
    if rsi_prev is None:
        return False
    
    return rsi_prev <= 30 and rsi > 30

def on_sell_signal(data):
    '''Vender quando RSI sai da zona de sobrecompra'''
    rsi = calculate_rsi(data['closes'], 14)
    if rsi is None:
        return False
    
    rsi_prev = calculate_rsi(data['closes'][:-1], 14)
    if rsi_prev is None:
        return False
    
    return rsi_prev >= 70 and rsi < 70
```

DICAS IMPORTANTES:
- Comece com estratégias simples
- Teste com dados históricos antes de publicar
- O robô precisa de 20+ operações para aparecer na vitrine
- Sua estratégia fica salva por 6 meses no banco de dados
- Após 20 operações, você pode publicar na vitrine de estratégias
- Monitore o win rate e PNL da sua estratégia

BIBLIOTECAS PERMITIDAS:
- math: Operações matemáticas
- statistics: Cálculos estatísticos
- datetime: Manipulação de datas
- decimal: Precisão decimal
- numpy: Cálculos numéricos
- pandas: Análise de dados
- ta: Análise técnica
- talib: Indicators de trading

CAMPOS DISPONÍVEIS DE DADOS (data dict):
- close: float - Preço de fechamento
- open: float - Preço de abertura
- high: float - Preço máximo
- low: float - Preço mínimo
- volume: float - Volume
- closes: list[float] - Histórico de fechamentos
- highs: list[float] - Histórico de máximos
- lows: list[float] - Histórico de mínimos
"""
