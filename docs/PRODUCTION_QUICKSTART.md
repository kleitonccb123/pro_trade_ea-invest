# 🚀 Production Quickstart - Deploy com Docker

## Resumo Executivo

A aplicação está **100% pronta para produção** com:
- ✅ Sistema de Créditos de Ativação (Slots)
- ✅ Regra Singleton (1 bot rodando)
- ✅ Limite de Swaps (2 grátis, depois 1 crédito)
- ✅ Kill Switch (desligador de emergência)
- ✅ Docker multi-stage otimizado
- ✅ Redis com persistência (RDB + AOF)
- ✅ MongoDB com replica set
- ✅ Nginx com SSL/TLS + WebSocket
- ✅ Script de deploy automatizado

---

## ⏱️ Tempo Total: ~30 minutos

| Etapa | Tempo | Status |
|-------|-------|--------|
| Preparar ambiente | 5 min | 📝 Você |
| Gerar certificados SSL | 3 min | 📝 Você |
| Executar deploy.sh | 10 min | ⚙️ Automático |
| Validar saúde | 2 min | ✅ Health checks |
| Teste de créditos | 5 min | 🧪 Manual |

---

## 📋 Step-by-Step

### 1️⃣ Preparar Environment File (5 min)

```bash
# Na raiz do projeto
cp .env.production.example .env.production
```

**Abra `.env.production` com seu editor favorito e substitua:**

```env
# ================== MONGODB ==================
MONGO_ROOT_PASSWORD=changeme-123456789  →  SUA_SENHA_FORTE_AQUI_32_CHARS
MONGO_INITDB_ROOT_USERNAME=admin
MONGO_INITDB_ROOT_PASSWORD=changeme-123456789  →  MESMA_SENHA_ACIMA
MONGO_DB=crypto_trade_hub

# ================== REDIS ==================
REDIS_PASSWORD=changeme-redis-123456789  →  OUTRA_SENHA_FORTE_32_CHARS

# ================== FASTAPI ==================
ENVIRONMENT=production
DEBUG=false
JWT_SECRET_KEY=changeme-jwt-secret-key-32-chars  →  TERCEIRA_SENHA_FORTE

# ================== DOMÍNIO ==================
DOMAIN_NAME=yourdomain.com  →  SEU_DOMÍNIO.COM
FRONTEND_URL=https://yourdomain.com  →  https://SEU_DOMINIO.COM
API_BASE_URL=https://yourdomain.com/api/v1  →  https://SEU_DOMINIO.COM/api/v1

# ================== GOOGLE OAUTH (OPCIONAL) ==================
GOOGLE_CLIENT_ID=changeme-client-id  →  Deixar em branco se não usar
GOOGLE_CLIENT_SECRET=changeme-secret  →  Deixar em branco se não usar

# ================== EMAIL ==================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-app-específica-gerada-no-gmail
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

**🔐 Gerar senhas aleatórias:**

```bash
# Terminal
openssl rand -base64 32

# Copie o output 3 vezes (para MongoDB, Redis, JWT)
```

### 2️⃣ Criar Certificados SSL (3 min)

**Opção A: Let's Encrypt (Recomendado - Produção)**

```bash
# Instalar certbot
sudo apt-get install certbot

# Gerar certificado (certbot vai perguntar seu email)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Copiar para o projeto
mkdir -p certs
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem certs/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem certs/key.pem
sudo chown $USER:$USER certs/*
chmod 600 certs/*
```

**Opção B: Self-signed (Dev/Teste)**

```bash
mkdir -p certs

openssl req -x509 -newkey rsa:4096 -nodes \
  -out certs/cert.pem -keyout certs/key.pem -days 365 \
  -subj "/C=BR/ST=State/L=City/O=CryptoHub/CN=localhost"
```

**Opção C: Copiar certificados existentes**

```bash
cp /seu/caminho/cert.pem certs/cert.pem
cp /seu/caminho/key.pem certs/key.pem
chmod 600 certs/*
```

### 3️⃣ Executar Deploy Automático (10 min)

```bash
# Tornar script executável
chmod +x deploy.sh

# Executar deploy
./deploy.sh

# Você verá:
# ✅ Checking Docker installation...
# ✅ Building Docker images...
# ✅ Starting services...
# ✅ Initializing MongoDB replica set...
# ✅ Running migration...
# ✅ Running health checks...
# ✅ Cleaning old logs...
# ✅ Deployment complete!
```

**O que o `deploy.sh` faz automaticamente:**
1. Valida Docker/Docker Compose instalado
2. Build imagem Dockerfile.prod
3. Inicia 4 containers (MongoDB, Redis, Backend, Nginx)
4. Cria replica set MongoDB
5. Executa migration de Créditos
6. Verifica saúde de todos os serviços
7. Limpa logs com >7 dias

### 4️⃣ Validar Saúde dos Serviços (2 min)

```bash
# Ver status dos containers
./deploy.sh status

# Esperado:
# NAME          STATUS          PORTS
# mongodb       Up (healthy)    127.0.0.1:27017
# redis         Up (healthy)    127.0.0.1:6379
# backend       Up (healthy)    127.0.0.1:8000 → 8000/tcp
# nginx         Up (healthy)    0.0.0.0:80->80, 0.0.0.0:443->443

# Ver logs em tempo real
./deploy.sh logs nginx    # Últimas 100 linhas do Nginx
```

### 5️⃣ Testar Sistema de Créditos (5 min)

**Teste 1: Verificar perfil com créditos**

```bash
# Obter token (exemplo com user.id = "user123")
TOKEN=$(curl -s -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"senha"}' \
  -k | jq -r '.access_token')

# Ver créditos e plano
curl -s https://localhost/api/v1/auth/profile/activation-credits \
  -H "Authorization: Bearer $TOKEN" \
  -k | jq

# Esperado:
# {
#   "plan": "pro",  
#   "activation_credits": 5,
#   "activation_credits_used": 0,
#   "activation_credits_remaining": 5,
#   "active_bots_count": 0
# }
```

**Teste 2: Iniciar bot com validação de créditos**

```bash
# Sem créditos suficientes (erro 402)
curl -X POST https://localhost/api/v1/bots/bot-id-1/start \
  -H "Authorization: Bearer $TOKEN" \
  -k -i grep HTTP  # Deve retornar 402 Payment Required se sem créditos

# Com créditos (sucesso 200)
# Deve ativar bot e consumir 1 crédito
```

**Teste 3: Testar limite de swaps**

```bash
# Primeiros 2 swaps = grátis
# 3º swap em diante = 1 crédito cada

curl -X PUT https://localhost/api/v1/bots/bot-id-1/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"setting":"value"}' \
  -k
```

**Teste 4: Kill Switch (Admin)**

```bash
# Desligar todos os bots de um usuário
curl -X POST https://localhost/api/v1/admin/kill-switch/activate/user-id-123 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Suspicious activity detected"}' \
  -k

# Ver audit trail
curl -s https://localhost/api/v1/admin/kill-switch/status/user-id-123 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -k | jq
```

---

## 🛑 Troubleshooting Rápido

### ❌ "Permission denied" ao rodar deploy.sh

```bash
chmod +x deploy.sh
```

### ❌ Porta 80/443 já em uso

```bash
# Verificar o que está usando
sudo lsof -i :80
sudo lsof -i :443

# Parar conflito e retry
./deploy.sh
```

### ❌ "Dockerfile.prod not found"

```bash
# Confirmar que está na raiz do projeto
ls -la Dockerfile.prod
ls -la docker-compose.prod.yml
```

### ❌ MongoDB não inicializa

```bash
# Ver logs detalhados
./deploy.sh logs mongodb

# Se persistir, fazer clean e retry
./deploy.sh clean
./deploy.sh
```

### ❌ Backend retorna 502 Bad Gateway

```bash
# Verificar se backend está rodando
curl -i http://localhost:8000/health

# Se não responder, reiniciar
docker-compose -f docker-compose.prod.yml restart backend
```

### ❌ Nginx reclama sobre certificado

```bash
# Confirmar que certs existem
ls -la certs/cert.pem certs/key.pem

# Verificar permissões
chmod 644 certs/cert.pem
chmod 600 certs/key.pem

# Reiniciar Nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

---

## 📊 Monitoramento Pós-Deploy

### Ver logs em tempo real

```bash
# Todos os serviços
./deploy.sh logs

# Serviço específico
./deploy.sh logs backend      # FastAPI
./deploy.sh logs mongodb      # MongoDB
./deploy.sh logs redis        # Redis
./deploy.sh logs nginx        # Nginx

# Últimas 50 linhas e seguir
./deploy.sh logs backend | tail -50 -f
```

### Usar diferentes comandos

```bash
./deploy.sh                  # Deploy completo
./deploy.sh status           # Ver status dos containers
./deploy.sh logs backend     # Ver logs do backend
./deploy.sh stop             # Parar containers (mantém dados)
./deploy.sh clean            # Limpar tudo (DELETE volumes!)
```

---

## 🔐 Checklist de Segurança

- [ ] `.env.production` modificado com senhas reais (NÃO usar "changeme")
- [ ] `.env.production` tem permissão 600: `chmod 600 .env.production`
- [ ] SSL certificados importados em `./certs/`
- [ ] Firewall aberto para portas 80/443 apenas
- [ ] MongoDB/Redis acessíveis APENAS via localhost (verificar em docker-compose.prod.yml)
- [ ] Backend rodando em 4 workers (Gunicorn)
- [ ] Health checks passando em todos os 4 serviços
- [ ] Redis persistence ativa (RDB + AOF em redis.prod.conf)

---

## 🎯 Próximas Etapas

### Imediato (após confirmar health checks)
1. Acessar https://SEU_DOMINIO.COM
2. Testar login e visualizar créditos
3. Testar iniciar bot (com créditos)
4. Testar swap limit

### Curto prazo (primeira semana)
1. Configurar alertas (se bot cair)
2. Configurar backup automático (MongoDB + Redis)
3. Monitorar logs (erros críticos)
4. Testar failover (kill container, ver recovery)

### Médio prazo (próximas semanas)
1. Configurar log aggregation (ELK, Datadog)
2. Adicionar métricas (Prometheus + Grafana)
3. Configurar CI/CD (auto-deploy em push)
4. Treinar time operacional

---

## 📚 Documentação Completa

Para referência detalhada, ver:
- **Backend**: `/app/services/activation_manager.py` (Lógica de créditos)
- **Configuração**: `.env.production.example` (Todas as opções)
- **Deployment**: `deploy.sh` (Script completo)
- **Nginx**: `nginx.prod.conf` (Proxy + SSL)
- **Redis**: `redis.prod.conf` (Persistência)

---

## ✅ Status

- **Código Backend**: Completo ✅
- **Docker Infrastructure**: Completo ✅
- **Deployment Automation**: Completo ✅
- **Documentação**: Você está lendo ✅
- **Ready for Production**: 🚀 SIM

**Próximo passo**: Executar passo 1-5 acima!

---

**Última Atualização**: 2026-02-11  
**Versão**: 1.0  
**Status**: Production-Ready 🚀
