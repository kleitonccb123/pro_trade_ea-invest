# 🚀 Nova Aba: Criador de Estratégias de Trading

## 📋 Resumo Executivo

Uma nova aba foi adicionada ao Crypto Trade Hub que permite aos usuários criarem suas próprias estratégias de trading automatizado em Python, sem necessidade de conhecimento avançado de programação.

### ✨ Principais Funcionalidades

1. **Editor de Código Python**
   - Interface intuitiva para escrever estratégias
   - Validação automática de código
   - Sugestões e avisos em tempo real

2. **Validação Inteligente**
   - Detecta erros de sintaxe
   - Verifica funções obrigatórias
   - Bloqueia código perigoso (eval, exec, import os, etc)

3. **Rastreamento de Operações**
   - Conta automaticamente quantas operações foram realizadas
   - Mostra estatísticas (PNL, taxa de acerto, etc)
   - Histórico completo de trades

4. **Publicação Automática**
   - Após 20 operações, estratégia fica elegível para publicação
   - Aparece na vitrine para outros usuários
   - Dados preservados por 6 meses

## 🎯 Como Usar

### Passo 1: Acessar a Aba
1. Na navegação lateral, clique em **"Estratégia"** (novo ícone de código)
2. Você verá sua lista de estratégias e um botão **"Nova Estratégia"**

### Passo 2: Criar Estratégia
1. Clique em **"Nova Estratégia"**
2. Preencha os campos:
   - **Nome**: "Minha Estratégia SMA"
   - **Descrição**: "Estratégia baseada em média móvel"
   - **Par de Trading**: BTCUSDT, ETHUSDT, etc
   - **Timeframe**: 1m, 5m, 15m, 1h, 4h, 1d

### Passo 3: Escrever Código
Cole seu código Python com as funções obrigatórias:

```python
def on_buy_signal(data):
    """Retorna True quando deve comprar"""
    if len(data['closes']) < 20:
        return False
    
    sma = sum(data['closes'][-20:]) / 20
    return data['close'] > sma

def on_sell_signal(data):
    """Retorna True quando deve vender"""
    if len(data['closes']) < 20:
        return False
    
    sma = sum(data['closes'][-20:]) / 20
    return data['close'] < sma
```

### Passo 4: Validar
1. Clique em **"Validar Código"**
2. O sistema checará:
   - ✅ Sintaxe Python válida
   - ✅ Funções obrigatórias presentes
   - ✅ Imports permitidos
   - ✅ Sem código perigoso

### Passo 5: Criar
1. Se validado com sucesso, clique em **"Criar Estratégia"**
2. Estratégia será salva como **"Rascunho"**

### Passo 6: Testar e Publicar
1. Estratégia começa a executar em simulação
2. Cada operação é rastreada
3. Quando atingir **20 operações**, aparece botão **"Publicar"**
4. Clique para publicar na vitrine

## 📊 Dashboard da Estratégia

Para cada estratégia você verá:

| Campo | Descrição |
|-------|-----------|
| **Nome** | Nome da sua estratégia |
| **Status** | Rascunho / Testando / Publicada |
| **Operações** | X/20 (quando chegar a 20, pode publicar) |
| **PNL** | Lucro/Prejuízo total em USD |
| **Taxa de Acerto** | Percentual de operações lucrativas |
| **Versão** | Número da versão do código |
| **Par** | BTC/USDT, ETH/USDT, etc |
| **Timeframe** | 1h, 4h, 1d, etc |

## 🔒 Restrições de Código

### ❌ Não Permitido
```python
eval()           # Avaliação dinâmica
exec()           # Execução dinâmica
compile()        # Compilação dinâmica
import os        # Sistema operacional
import sys       # Sistema
import subprocess # Subprocessos
__import__       # Import dinâmico
```

### ✅ Permitido
```python
import math
import statistics
import datetime
import numpy
import pandas
from ta import indicators  # Análise técnica
```

## 💾 Armazenamento

- **Duração**: 6 meses a partir da criação
- **Salvo em**: Banco de dados do Crypto Trade Hub
- **Acesso**: Apenas você pode ver seu código
- **Backup**: Dados preservados mesmo após expiração (30 dias extras)

## 📈 Critérios para Publicação

Sua estratégia é publicada quando:

- ✅ Você clica em "Publicar"
- ✅ Tem no mínimo **20 operações**
- ✅ Não expirou (menos de 6 meses)
- ✅ Está ativa

## 🔄 Ciclo de Vida

```
┌─────────────┐
│  Rascunho   │  ← Estratégia criada
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│ Testando             │  ← Executando operações
│ (contando trades)    │
└──────┬───────────────┘
       │ (20+ trades)
       ▼
┌─────────────┐
│ Publicada   │  ← Apareça na vitrine
└─────────────┘
       │
       ▼
┌─────────────┐
│ Expirada    │  ← Após 6 meses
└─────────────┘
```

## 🧪 Exemplos de Estratégias

### Exemplo 1: RSI Simples

```python
def calculate_rsi(closes, period=14):
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
    return 100 - (100 / (1 + rs))

def on_buy_signal(data):
    rsi = calculate_rsi(data['closes'])
    return rsi is not None and rsi < 30

def on_sell_signal(data):
    rsi = calculate_rsi(data['closes'])
    return rsi is not None and rsi > 70
```

### Exemplo 2: Cruzamento de Médias Móveis

```python
def on_buy_signal(data):
    if len(data['closes']) < 21:
        return False
    
    sma_fast = sum(data['closes'][-10:]) / 10
    sma_slow = sum(data['closes'][-20:]) / 20
    sma_fast_prev = sum(data['closes'][-11:-1]) / 10
    sma_slow_prev = sum(data['closes'][-21:-1]) / 20
    
    return sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow

def on_sell_signal(data):
    if len(data['closes']) < 21:
        return False
    
    sma_fast = sum(data['closes'][-10:]) / 10
    sma_slow = sum(data['closes'][-20:]) / 20
    sma_fast_prev = sum(data['closes'][-11:-1]) / 10
    sma_slow_prev = sum(data['closes'][-21:-1]) / 20
    
    return sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow
```

## 🔌 API Endpoints

```
POST   /api/strategies                    Criar estratégia
GET    /api/strategies                    Listar estratégias
GET    /api/strategies/{id}               Detalhe da estratégia
PUT    /api/strategies/{id}               Atualizar estratégia
DELETE /api/strategies/{id}               Deletar estratégia
POST   /api/strategies/{id}/publish       Publicar na vitrine
POST   /api/strategies/validate           Validar código
GET    /api/strategies/{id}/trades        Listar trades
POST   /api/strategies/{id}/bot-instances Criar bot instance
POST   /api/strategies/{id}/bot-instances/{iid}/trades  Registrar trade
```

## ⏰ Agendamento

- **Limpeza Automática**: Diariamente às 00:00 UTC
- **Validade**: 6 meses (180 dias)
- **Notificações**: Você recebe aviso 7 dias antes da expiração

## 🆘 Troubleshooting

### Erro: "Funções obrigatórias não encontradas"
- Certifique-se que tem `on_buy_signal()` e `on_sell_signal()`
- Verifique a indentação (use 4 espaços)

### Erro: "Módulo não permitido"
- Alguns imports não são permitidos (os, sys, subprocess)
- Use apenas: math, numpy, pandas, ta, talib, datetime, decimal, statistics

### Estratégia não conta operações
- Certifique-se que operações estão sendo criadas através da API
- Verifique se bot instance foi criada

## 📞 Suporte

Para reportar bugs ou sugestões, entre em contato com o suporte do Crypto Trade Hub.

---

**Versão**: 1.0  
**Data**: 2026-02-03  
**Status**: ✅ Ativo
