# 🚀 Guia de Instalação - Sistema de Estratégias

## ✅ Pré-requisitos

- Python 3.8+
- Node.js 16+
- PostgreSQL 12+
- Virtual environment ativado

## 📦 Instalação

### 1. Backend Setup

#### Passo 1: Instalar dependências
```bash
cd backend
pip install -r requirements.txt
```

Se `requirements.txt` não contiver os pacotes novos, adicione:
```bash
pip install sqlalchemy pydantic ast json
```

#### Passo 2: Criar migration (se usar Alembic)
```bash
# Não é necessário fazer manualmente
# Os modelos foram adicionados a app/strategies/model.py
# e serão criados automaticamente ao iniciar o app
```

#### Passo 3: Inicializar o banco (primeiro uso)
```bash
# O banco será criado automaticamente ao iniciar
python run_server.py
```

Se precisar resetar manualmente:
```bash
python create_db.py
python create_tables.py
```

### 2. Frontend Setup

#### Passo 1: Instalar dependências (já feito, mas verificar)
```bash
# Já estão inclusos:
# - lucide-react (ícones)
# - shadcn/ui (componentes)
```

#### Passo 2: Verificar importações
```bash
# No arquivo src/pages/Strategy.tsx
# Todos os imports já estão disponíveis
```

#### Passo 3: Build
```bash
npm run build
# ou
npm run dev  # Para desenvolvimento
```

## 🗄️ Database Schema

As tabelas serão criadas automaticamente:

```sql
-- user_strategies
CREATE TABLE user_strategies (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  strategy_code TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'draft',
  trade_count INTEGER DEFAULT 0,
  total_pnl FLOAT DEFAULT 0.0,
  win_rate FLOAT,
  symbol VARCHAR(50),
  timeframe VARCHAR(10),
  is_active BOOLEAN DEFAULT true,
  version INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_user_id_status ON user_strategies(user_id, status);
CREATE INDEX idx_user_id_created_at ON user_strategies(user_id, created_at);
CREATE INDEX idx_expires_at ON user_strategies(expires_at);

-- strategy_bot_instances
CREATE TABLE strategy_bot_instances (
  id SERIAL PRIMARY KEY,
  strategy_id INTEGER NOT NULL REFERENCES user_strategies(id) ON DELETE CASCADE,
  symbol VARCHAR(50) NOT NULL,
  timeframe VARCHAR(10) NOT NULL,
  is_running BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  started_at TIMESTAMP,
  stopped_at TIMESTAMP
);

-- strategy_trades
CREATE TABLE strategy_trades (
  id SERIAL PRIMARY KEY,
  strategy_id INTEGER NOT NULL REFERENCES user_strategies(id) ON DELETE CASCADE,
  instance_id INTEGER NOT NULL REFERENCES strategy_bot_instances(id) ON DELETE CASCADE,
  entry_price FLOAT NOT NULL,
  exit_price FLOAT,
  quantity FLOAT NOT NULL,
  side VARCHAR(10) NOT NULL,
  pnl FLOAT,
  pnl_percent FLOAT,
  entry_time TIMESTAMP DEFAULT NOW(),
  exit_time TIMESTAMP
);

CREATE INDEX idx_strategy_id_entry_time ON strategy_trades(strategy_id, entry_time);
```

## ⚙️ Configuração

### Variáveis de Ambiente

Nenhuma variável específica é necessária além das existentes:
- `DATABASE_URL`: Já configurado
- `API_BASE`: Já configurado

### Scheduler

O scheduler rodará automaticamente ao iniciar o app:

```python
# No app/main.py
@app.on_event("startup")
async def on_startup():
    await init_db()
    await core_scheduler.scheduler.start()
```

A task de limpeza rodará a cada 24 horas:
```python
# No app/core/scheduler.py
self.add_task("cleanup_expired_strategies", self._cleanup_expired_strategies, interval=86400)
```

## 🧪 Testes

### Backend Tests

#### Validar código
```bash
curl -X POST http://localhost:8000/api/strategies/validate \
  -H "Content-Type: application/json" \
  -d '{"strategy_code":"def on_buy_signal(data):\n    return True\n\ndef on_sell_signal(data):\n    return False"}'
```

Resposta esperada:
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": []
}
```

#### Criar estratégia
```bash
curl -X POST http://localhost:8000/api/strategies \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Strategy",
    "strategy_code": "def on_buy_signal(data):\n    return True\n\ndef on_sell_signal(data):\n    return False",
    "symbol": "BTCUSDT",
    "timeframe": "1h"
  }'
```

#### Listar estratégias
```bash
curl -X GET http://localhost:8000/api/strategies \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Frontend Tests

1. **Acessar página**
   - Navegue para `http://localhost:5173/strategy`
   - Deve abrir a página de estratégias

2. **Criar estratégia**
   - Clique em "Nova Estratégia"
   - Preencha formulário
   - Valide código
   - Crie estratégia

3. **Validar código**
   - Entrada válida: Código com on_buy_signal e on_sell_signal
   - Entrada inválida: Código sem funções obrigatórias
   - Código perigoso: import os (deve rejeitar)

## 🚀 Deployment

### Desenvolvimento
```bash
# Terminal 1 - Backend
cd backend
python run_server.py

# Terminal 2 - Frontend
npm run dev
```

### Staging/Produção
```bash
# Build
npm run build

# Deploy frontend
# (conforme seu setup)

# Deploy backend
# (conforme seu setup)

# Migrate database
# (conforme seu setup)
```

## 📋 Checklist de Verificação

Após instalação, verificar:

- [ ] Banco de dados criado
- [ ] Tabelas `user_strategies`, `strategy_bot_instances`, `strategy_trades` existem
- [ ] Backend rodando na porta 8000
- [ ] Frontend rodando na porta 5173
- [ ] API `/api/strategies` respondendo
- [ ] Aba "Estratégia" visível na navegação
- [ ] Modal de criação abrindo
- [ ] Validação de código funcionando
- [ ] Criar estratégia salva no banco
- [ ] Scheduler task registrada

## 🔍 Troubleshooting

### Erro: "Tabela user_strategies não existe"
**Solução**: 
- Certifique-se que `app/strategies/model.py` foi importado
- Verifique em `app/main.py`:
```python
import app.strategies.model  # noqa: F401
```

### Erro: "Módulo strategies não encontrado"
**Solução**:
- Crie arquivo `backend/app/strategies/__init__.py`
- Registre router em `app/main.py`:
```python
from app.strategies import router as strategies_router
app.include_router(strategies_router.router)
```

### Erro: "Rota /strategy não encontrada"
**Solução**:
- Verifique `src/App.tsx`:
```tsx
import Strategy from "./pages/Strategy";
// ...
<Route path="/strategy" element={<Strategy />} />
```

### Erro ao validar código
**Solução**:
- Certifique-se que funções estão indentadas corretamente
- Use 4 espaços para indentação
- Exemplo correto:
```python
def on_buy_signal(data):
    return True
```

## 📊 Monitoramento

### Logs a Monitorar

**Backend**:
```log
Scheduler: cleanup_expired_strategies enabled (interval=86400s / 24h)
Cleaned up N expired strategies
Strategy published successfully
Strategy created successfully
```

**Frontend**:
- Console do browser para erros de API
- Network tab para requests

## 🎯 Próximos Passos

Após instalação bem-sucedida:

1. Crie uma estratégia de teste
2. Valide o código
3. Monitore a execução
4. Verifique banco de dados
5. Leia documentação de uso

## 📞 Suporte

Para problemas:

1. Verifique [STRATEGY_TECHNICAL_SUMMARY.md](./STRATEGY_TECHNICAL_SUMMARY.md)
2. Verifique logs do backend
3. Verifique console do frontend
4. Verifique banco de dados

---

**Data**: 2026-02-03  
**Versão**: 1.0  
**Status**: ✅ Pronto
