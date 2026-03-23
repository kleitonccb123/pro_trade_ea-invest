# Sistema de Estratégias de Trading - Crypto Trade Hub

## Visão Geral

O novo sistema de estratégias permite que usuários criem suas próprias estratégias de trading automatizado em Python. Após criadas, essas estratégias são testadas em simulação e podem ser publicadas na vitrine quando atingem critérios específicos.

## Fluxo Principais

### 1. Criação de Estratégia
- Usuário acessa a aba **"Estratégia"** na navegação
- Clica em **"Nova Estratégia"**
- Preenche os dados básicos:
  - Nome da estratégia
  - Descrição (opcional)
  - Par de trading (BTC/USDT, ETH/USDT, etc)
  - Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
  - Código Python da estratégia

### 2. Validação de Código
- O sistema valida automaticamente o código Python
- Verifica se contém as funções obrigatórias:
  - `on_buy_signal(data)`
  - `on_sell_signal(data)`
- Detecta imports proibidos (os, sys, subprocess, etc)
- Avisa sobre padrões de código inseguros

### 3. Execução e Rastreamento
- Estratégia começa em status **"Rascunho"**
- Pode ser testada em simulação
- Cada operação realizada é rastreada
- Sistema conta quantas operações foram executadas

### 4. Publicação na Vitrine
- Após **20 operações**, a estratégia fica elegível para publicação
- Estratégia é movida para status **"Publicada"**
- Aparece na vitrine para outros usuários descobrirem
- Mostra estatísticas (PNL, taxa de acerto, etc)

### 5. Expiração
- Estratégias expiram após **6 meses**
- Dados são mantidos no banco durante esse período
- Após expiração, pode ser renovada ou deletada

## Estrutura de Dados no Backend

### Tabelas do Banco de Dados

```
user_strategies
├── id (PK)
├── user_id (FK)
├── name
├── description
├── strategy_code
├── status (draft, testing, published, archived)
├── trade_count
├── total_pnl
├── win_rate
├── created_at
├── updated_at
├── expires_at (6 meses)
├── symbol
├── timeframe
├── is_active
└── version

strategy_bot_instances
├── id (PK)
├── strategy_id (FK)
├── symbol
├── timeframe
├── is_running
├── created_at
├── started_at
└── stopped_at

strategy_trades
├── id (PK)
├── strategy_id (FK)
├── instance_id (FK)
├── entry_price
├── exit_price
├── quantity
├── side (buy/sell)
├── pnl
├── pnl_percent
├── entry_time
└── exit_time
```

## API Endpoints

### Estratégias
- `POST /api/strategies` - Criar nova estratégia
- `GET /api/strategies` - Listar estratégias do usuário
- `GET /api/strategies/{id}` - Obter detalhes da estratégia
- `PUT /api/strategies/{id}` - Atualizar estratégia
- `DELETE /api/strategies/{id}` - Deletar estratégia
- `POST /api/strategies/{id}/publish` - Publicar na vitrine (requer 20+ trades)

### Validação
- `POST /api/strategies/validate` - Validar código Python

### Trades
- `GET /api/strategies/{id}/trades` - Listar trades da estratégia
- `POST /api/strategies/{id}/bot-instances` - Criar instância de bot
- `POST /api/strategies/{id}/bot-instances/{instance_id}/trades` - Registrar trade

## Exemplo de Estratégia

```python
def on_buy_signal(data):
    """
    Sinal de compra quando preço fecha acima da média móvel simples
    """
    if len(data['closes']) < 20:
        return False
    
    # Calcula média móvel dos últimos 20 fechamentos
    sma = sum(data['closes'][-20:]) / 20
    
    # Sinal de compra se preço atual > SMA
    return data['close'] > sma

def on_sell_signal(data):
    """
    Sinal de venda quando preço fecha abaixo da média móvel simples
    """
    if len(data['closes']) < 20:
        return False
    
    # Calcula média móvel dos últimos 20 fechamentos
    sma = sum(data['closes'][-20:]) / 20
    
    # Sinal de venda se preço atual < SMA
    return data['close'] < sma
```

## Como Usar a Interface

### Criando uma Estratégia

1. Clique em **"Nova Estratégia"**
2. Preencha o formulário:
   - Nome: "Minha Estratégia SMA"
   - Descrição: "Estratégia baseada em média móvel simples"
   - Par: BTCUSDT
   - Timeframe: 1h
   - Código: Cole seu código Python

3. Clique em **"Validar Código"**
4. Se validado, clique em **"Criar Estratégia"**

### Monitorando uma Estratégia

1. Acesse a aba **"Estratégia"**
2. Veja a lista de suas estratégias com:
   - Status (Rascunho, Testando, Publicada)
   - Número de operações (X/20)
   - PNL total
   - Taxa de acerto
   - Versão

### Publicando na Vitrine

1. Quando atingir 20 operações, aparecer botão **"Publicar"**
2. Clique para publicar na vitrine
3. Estratégia fica visível para outros usuários

### Deletando uma Estratégia

1. Clique no botão **"Deletar"** na estratégia
2. Confirme a exclusão
3. Estratégia e histórico serão removidos

## Limitações e Restrições

### Código Não Permitido
- `eval()`, `exec()`, `compile()`
- Imports de `os`, `sys`, `subprocess`, `socket`, `urllib`
- Mais de 500 linhas
- Indentação muito profunda (>6 níveis)

### Código Permitido
- Python padrão
- `numpy`, `pandas`, `ta`, `talib`
- Lógica de condicional e loops simples

## Limpeza Automática

- Um job agendado verifica diariamente por estratégias expiradas
- Estratégias com mais de 6 meses são marcadas como `ARCHIVED`
- Dados são preservados para auditoria
- Usuário recebe notificação antes da expiração

## Segurança

- Código é validado antes de salvar
- Funções perigosas (eval, exec) são bloqueadas
- Ambiente de execução isolado
- Apenas o proprietário pode visualizar código completo
- Rate limiting em endpoints sensíveis

## Próximas Features

- Integração com backtesting de histórico
- Live trading com estratégias publicadas
- Performance comparativa entre estratégias
- Marketplace de estratégias com remuneração
- Editor de código com syntax highlighting
- Templates pré-prontos de estratégias
