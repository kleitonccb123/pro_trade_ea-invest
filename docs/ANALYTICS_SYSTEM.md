# Sistema de Análise de Robôs - Implementação Completa

## Resumo das Mudanças

Foi implementado um sistema completo de análise de robôs no frontend e backend que permite visualizar:

1. **Robôs Mais Usados** - Estatísticas dos robôs com mais execuções nos últimos 10, 30 e 90 dias
2. **Robôs Mais Rentáveis** - Robôs com maior lucratividade (PnL e percentual) nos últimos 10, 30 e 90 dias

---

## Backend (Python/FastAPI)

### 1. **Repository Layer** (`backend/app/bots/repository.py`)

Adicionadas duas novas funções assíncronas:

```python
async def get_most_used_bots(db: AsyncSession, days: int) -> List[dict]
```
- Retorna robôs mais usados com contagem de execuções
- Filtra por período (10, 30, 90 dias)
- Ordena por número de execuções (descendente)

```python
async def get_most_profitable_bots(db: AsyncSession, days: int) -> List[dict]
```
- Retorna robôs mais rentáveis com:
  - PnL total (lucro total em USD)
  - Percentual médio de PnL
  - Contagem de operações fechadas
- Filtra por período e apenas operações fechadas
- Ordena por PnL total (descendente)

### 2. **Service Layer** (`backend/app/bots/service.py`)

Adicionadas duas novas funções que chamam o repository:

```python
async def get_most_used_bots(self, days: int)
async def get_most_profitable_bots(self, days: int)
```

### 3. **Router** (`backend/app/bots/router.py`)

Dois novos endpoints REST:

```
GET /bots/analytics/most-used?days=10
GET /bots/analytics/most-profitable?days=10
```

**Parâmetros:**
- `days`: 10, 30 ou 90

**Respostas:**
```json
{
  "days": 10,
  "bots": [
    {
      "id": 1,
      "name": "BTC Scalper",
      "symbol": "BTCUSDT",
      "usage_count": 25
    }
  ]
}
```

---

## Frontend (React/TypeScript)

### 1. **Novo Componente** (`src/components/robots/BotAnalytics.tsx`)

Componente completo com:

- **Abas**: "Mais Usados" e "Mais Rentáveis"
- **Seletor de Período**: Botões para 10, 30 e 90 dias
- **Carregamento de Dados**: Fetches automáticos para todos os períodos
- **Visualização de Dados**:
  - Ranking com badges numéricas (#1, #2, #3)
  - Cards com informações detalhadas por robô
  - Ícones de tendência (TrendingUp/TrendingDown)
  - Cores visuais (verde para lucro, vermelho para prejuízo)

- **Resumo Estatístico**: Cards com:
  - Total de robôs usados
  - Total de execuções
  - Lucro total consolidado

### 2. **Integração na Página** (`src/pages/Robots.tsx`)

O componente `BotAnalytics` foi integrado na página de robôs, logo após as estatísticas gerais.

---

## Fluxo de Dados

```
Frontend (BotAnalytics.tsx)
  ↓
  ├─ GET /bots/analytics/most-used?days=10,30,90
  ├─ GET /bots/analytics/most-profitable?days=10,30,90
  ↓
Backend Router
  ↓
Backend Service
  ↓
Repository (Queries SQL)
  ↓
Database (SimulatedTrade + BotInstance + Bot tables)
```

---

## Funcionalidades Principais

### Robôs Mais Usados
- Conta quantas vezes cada robô foi executado (instâncias iniciadas)
- Filtra por data de início da instância
- Agrupa por robô_id

### Robôs Mais Rentáveis
- Soma PnL de todas as operações fechadas do robô
- Calcula percentual médio de retorno
- Filtra por operações com exit_price definido
- Agrupa por robô_id

---

## Endpoints de Teste

```bash
# Robôs mais usados nos últimos 10 dias
curl http://localhost:8000/bots/analytics/most-used?days=10

# Robôs mais usados nos últimos 30 dias
curl http://localhost:8000/bots/analytics/most-used?days=30

# Robôs mais usados nos últimos 90 dias
curl http://localhost:8000/bots/analytics/most-used?days=90

# Robôs mais rentáveis nos últimos 10 dias
curl http://localhost:8000/bots/analytics/most-profitable?days=10

# E assim por diante com 30 e 90 dias
curl http://localhost:8000/bots/analytics/most-profitable?days=30
curl http://localhost:8000/bots/analytics/most-profitable?days=90
```

---

## Estrutura do Banco de Dados Esperada

O sistema usa as tabelas existentes:
- `bots` - Informações dos robôs
- `bot_instances` - Execuções dos robôs
- `sim_trades` - Operações realizadas

Queries SQL geradas pelo SQLAlchemy agrupam e somam esses dados conforme necessário.

---

## Notas Técnicas

- **Assincronismo**: Todas as funções são assíncronas para melhor performance
- **Validação**: Endpoints validam que `days` é 10, 30 ou 90
- **Tratamento de Erros**: Endpoints retornam 400 para valores inválidos, 500 para erros de banco
- **Flexibilidade**: Fácil adicionar mais períodos (7, 15, 60 dias, etc.)
- **Escalabilidade**: Queries usam índices de data e agrupamento eficiente

---

## Próximas Melhorias Possíveis

1. Adicionar filtro por símbolo específico
2. Incluir taxa de vitória (win rate)
3. Adicionar Sharpe Ratio e outras métricas
4. Cache de resultados com TTL
5. Exportar dados em CSV/PDF
6. Gráficos e dashboards mais avançados
