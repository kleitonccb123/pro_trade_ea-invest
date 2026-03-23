# DOC 09 — Escalabilidade e Arquitetura SaaS

> **Nível:** Produção | **Escopo:** Horizontal Scaling, Multi-tenancy, Docker, Deploy, Isolamento  
> **Prioridade:** Média-Alta — necessário para crescer além de 100 usuários simultâneos

---

## 1. PROBLEMA ATUAL

A arquitetura atual executa tudo em um único processo Python. Com 100+ usuários ativos e 300+ bots rodando, isso causa:
- CPU/RAM saturados em um único container
- Um bug em um bot pode crashar a engine inteira
- Deploy de nova versão derruba todos os bots
- Impossível escalar horizontalmente

---

## 2. ARQUITETURA ESCALÁVEL TARGET

```
                        Load Balancer (nginx / Traefik)
                               │
                ┌──────────────┼──────────────┐
                │              │              │
           API Server 1   API Server 2   API Server N
           (FastAPI)       (FastAPI)       (FastAPI)
                │              │              │
                └──────────────┼──────────────┘
                               │
                         Redis Cluster
                    (bot:commands queue, cache)
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
    Bot Engine 1         Bot Engine 2         Bot Engine N
    (20 workers)         (20 workers)         (20 workers)
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                       MongoDB Replica Set
                    (Primary + 2 Secondaries)
```

---

## 3. ISOLAMENTO MULTI-TENANT

### 3.1 Isolamento de Recursos

```python
# Cada instância de bot é completamente isolada:
# - Credenciais KuCoin separadas por usuário (criptografadas)
# - Estado em memória isolado no BotWorker
# - Logs com user_id em cada entrada
# - Locks no MongoDB garantem sem interferência entre usuários

# Dados compartilhados (read-only por usuário):
# - Preços de mercado (público, compartilhado via Redis Pub/Sub)
# - KuCoin REST → CADA usuário usa suas próprias credenciais
# - Rankings (computação agregada sem expor dados individuais)
```

### 3.2 Quotas por Plano

```python
# backend/app/plan_limits.py

PLAN_LIMITS = {
    "free":     {"bots": 0,  "pairs_per_bot": 1,  "timeframes": ["1h"],         "api_calls_per_min": 10},
    "start":    {"bots": 1,  "pairs_per_bot": 1,  "timeframes": ["15m","1h"],   "api_calls_per_min": 30},
    "pro":      {"bots": 3,  "pairs_per_bot": 2,  "timeframes": ["5m","15m","1h","4h"], "api_calls_per_min": 60},
    "pro_plus": {"bots": 5,  "pairs_per_bot": 3,  "timeframes": ["1m","5m","15m","1h","4h"], "api_calls_per_min": 120},
    "quant":    {"bots": 10, "pairs_per_bot": 5,  "timeframes": ["1m","5m","15m","1h","4h","1d"], "api_calls_per_min": 300},
    "black":    {"bots": 20, "pairs_per_bot": 10, "timeframes": ["all"],         "api_calls_per_min": 1000},
}
```

---

## 4. DOCKER COMPOSE PRODUÇÃO

```yaml
# docker-compose.prod.yml

version: "3.9"

services:
  # ── API Servers (escalável) ────────────────────────────────────────────
  api:
    image: crypto-trade-hub-api:${IMAGE_TAG:-latest}
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 30s
        order: start-first   # Zero downtime deploy
      restart_policy:
        condition: on-failure
        max_attempts: 3
    environment:
      - MONGODB_URL=${MONGODB_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET=${JWT_SECRET}
      - FERNET_KEY=${FERNET_KEY}
      - KUCOIN_SANDBOX=${KUCOIN_SANDBOX:-false}
      - LOG_LEVEL=INFO
    ports:
      - "8000"
    depends_on:
      - redis
      - mongodb
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ── Bot Engine Workers ─────────────────────────────────────────────────
  engine:
    image: crypto-trade-hub-engine:${IMAGE_TAG:-latest}
    build:
      context: ./backend
      dockerfile: Dockerfile.engine
    deploy:
      replicas: 2           # Cada engine suporta ~50 bots simultâneos
      restart_policy:
        condition: on-failure
    environment:
      - MONGODB_URL=${MONGODB_URL}
      - REDIS_URL=${REDIS_URL}
      - FERNET_KEY=${FERNET_KEY}
      - MAX_BOTS_PER_ENGINE=50
      - LOG_LEVEL=INFO
    depends_on:
      - redis
      - mongodb

  # ── Frontend ────────────────────────────────────────────────────────────
  frontend:
    image: crypto-trade-hub-frontend:${IMAGE_TAG:-latest}
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api

  # ── Redis ────────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "6379"

  # ── MongoDB ──────────────────────────────────────────────────────────────
  mongodb:
    image: mongo:7
    command: mongod --replSet rs0 --keyFile /etc/mongo-keyfile
    environment:
      - MONGO_INITDB_ROOT_USERNAME=${MONGO_USER}
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_PASS}
    volumes:
      - mongo_data:/data/db
      - ./mongo-keyfile:/etc/mongo-keyfile:ro
    ports:
      - "27017"

  # ── Nginx (Load Balancer) ─────────────────────────────────────────────
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx/nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
      - frontend

  # ── Monitoramento ────────────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}

volumes:
  redis_data:
  mongo_data:
  prometheus_data:
  grafana_data:
```

---

## 5. DISTRIBUIÇÃO DE BOTS ENTRE ENGINES

```python
# backend/app/engine/orchestrator.py (extensão para multi-engine)

# Cada engine registra sua capacidade no Redis
ENGINE_REGISTRY_KEY = "engines:registry"
ENGINE_HEARTBEAT_TTL = 30  # segundos

class EngineCoordinator:
    """
    Distribuição de bots entre múltiplas engines (Round-robin ou least-loaded).
    """
    async def register_engine(self, engine_id: str, capacity: int, current_load: int):
        await self.redis.hset(ENGINE_REGISTRY_KEY, engine_id, json.dumps({
            "capacity": capacity,
            "current_load": current_load,
            "last_seen": datetime.utcnow().isoformat()
        }))
        await self.redis.expire(ENGINE_REGISTRY_KEY, ENGINE_HEARTBEAT_TTL)

    async def get_least_loaded_engine(self) -> Optional[str]:
        """Seleciona a engine com mais capacidade disponível."""
        engines = await self.redis.hgetall(ENGINE_REGISTRY_KEY)
        if not engines:
            return None

        best_engine = None
        best_free_slots = -1

        for engine_id, data_str in engines.items():
            data = json.loads(data_str)
            free_slots = data["capacity"] - data["current_load"]
            if free_slots > best_free_slots:
                best_free_slots = free_slots
                best_engine = engine_id

        return best_engine

    async def route_start_command(self, bot_instance_id: str, command: dict):
        """Roteia o comando de start para a engine menos carregada."""
        engine_id = await self.get_least_loaded_engine()
        queue_key = f"bot:commands:{engine_id}" if engine_id else "bot:commands:default"
        await self.redis.lpush(queue_key, json.dumps(command))
```

---

## 6. ZERO DOWNTIME DEPLOY

```bash
#!/bin/bash
# deploy_zero_downtime.sh

set -e
IMAGE_TAG=$(git rev-parse --short HEAD)

echo "🚀 Deploy da versão $IMAGE_TAG"

# 1. Build das imagens
docker build -t crypto-trade-hub-api:$IMAGE_TAG ./backend
docker build -t crypto-trade-hub-frontend:$IMAGE_TAG .

# 2. Rodar migrations antes
docker run --rm --env-file .env crypto-trade-hub-api:$IMAGE_TAG \
  python -m app.migrations.run

# 3. Deploy API com rolling update (sem downtime)
IMAGE_TAG=$IMAGE_TAG docker stack deploy \
  -c docker-compose.prod.yml \
  crypto-trade-hub \
  --with-registry-auth

# 4. Aguardar todos os serviços estarem healthy
docker service wait crypto-trade-hub_api

# 5. Deploy do engine com graceful shutdown
# (engine termina trades abertas antes de parar)
docker service update \
  --image crypto-trade-hub-engine:$IMAGE_TAG \
  --update-order=start-first \
  --update-delay=60s \
  crypto-trade-hub_engine

echo "✅ Deploy completo"
```

---

## 7. ESCALABILIDADE MONGODB

```javascript
// Configuração Replica Set para alta disponibilidade
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },  // Primary preferido
    { _id: 1, host: "mongo2:27017", priority: 1 },  // Secondary
    { _id: 2, host: "mongo3:27017", priority: 0, votes: 1, hidden: true }  // Analytics
  ]
})

// Read Preference para queries de ranking (lê do Secondary para não sobrecarregar Primary)
db.bot_trades.withReadPreference("secondaryPreferred")
```

---

## 8. VARIÁVEIS DE AMBIENTE

```bash
# .env.prod — NUNCA committar no git

# Core
SECRET_KEY=your-jwt-secret-minimum-32-chars
FERNET_KEY=base64-encoded-32-bytes
ENVIRONMENT=production

# Database
MONGODB_URL=mongodb://user:pass@mongo1:27017,mongo2:27017,mongo3:27017/crypto_hub?replicaSet=rs0
REDIS_URL=redis://:password@redis:6379

# KuCoin
KUCOIN_SANDBOX=false

# Email / Alertas
SMTP_HOST=smtp.sendgrid.net
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-key
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_ALERT_CHAT_ID=your-chat-id

# Monitoramento
GRAFANA_PASSWORD=secure-grafana-password
SENTRY_DSN=https://xxx@sentry.io/xxx
```

---

## 9. LIMITES DE CAPACIDADE

| Configuração | Bots Suportados | Usuários Ativos | RAM Total |
|---|---|---|---|
| 1 API + 1 Engine | ~50 | ~200 | 2 GB |
| 3 API + 2 Engine | ~100 | ~500 | 6 GB |
| 3 API + 5 Engine | ~250 | ~1000 | 12 GB |
| 5 API + 10 Engine | ~500 | ~2000 | 24 GB |

---

## 10. CHECKLIST

- [ ] Separação de containers: API vs Engine
- [ ] Redis como fila única entre API e Engines
- [ ] Engines registram capacidade no Redis (heartbeat)
- [ ] Roteamento least-loaded para novos bots
- [ ] Rolling deploy sem downtime para API
- [ ] Graceful shutdown da engine (60s para fechar trades)
- [ ] MongoDB Replica Set (mínimo 3 nós)
- [ ] Todas as secrets via variáveis de ambiente
- [ ] `.env.prod` no `.gitignore`
- [ ] Health check em todos os serviços
- [ ] Prometheus coletando métricas de todos os serviços
