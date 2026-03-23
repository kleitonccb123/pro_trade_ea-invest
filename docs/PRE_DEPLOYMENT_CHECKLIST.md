# ✅ Pre-Deployment Checklist

## Sistema de Créditos de Ativação

Este checklist garante que toda a infraestrutura de produção está pronta.

---

## 📋 Fase 1: Configuração Ambiente (15 min)

### Environment File
- [ ] `.env.production.example` existe na raiz
- [ ] Copiei para `.env.production`
- [ ] Geração de senhas:
  - [ ] `MONGO_ROOT_PASSWORD`: `openssl rand -base64 32`
  - [ ] `MONGO_INITDB_ROOT_PASSWORD`: Mesma da anterior
  - [ ] `REDIS_PASSWORD`: `openssl rand -base64 32`
  - [ ] `JWT_SECRET_KEY`: `openssl rand -base64 32`
- [ ] `.env.production` estã com permissão 600: `chmod 600 .env.production`
- [ ] Todos os "changeme-" foram substituídos
- [ ] DOMAIN_NAME está correto
- [ ] FRONTEND_URL e API_BASE_URL têm https://

### Variáveis Críticas
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `MONGO_DBNAME=crypto_trade_hub`
- [ ] `SMTP_HOST` está configurado (email)
- [ ] `JWT_SECRET_KEY` é uma string aleátoria forte

---

## 📋 Fase 2: SSL/TLS Certificates (5 min)

### Certificados
- [ ] Diretório `certs/` existe: `mkdir -p certs`
- [ ] `certs/cert.pem` existe (certificate)
- [ ] `certs/key.pem` existe (private key)
- [ ] Permissões corretas:
  ```bash
  chmod 644 certs/cert.pem
  chmod 600 certs/key.pem
  ```

### Opções de Certificado
- [ ] **Option A (Produção)**: Let's Encrypt via `certbot`
  ```bash
  sudo certbot certonly --standalone -d yourdomain.com
  sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem certs/cert.pem
  sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem certs/key.pem
  ```
  
- [ ] **Option B (Dev/Teste)**: Self-signed
  ```bash
  openssl req -x509 -newkey rsa:4096 -nodes \
    -out certs/cert.pem -keyout certs/key.pem -days 365 \
    -subj "/C=BR/ST=SP/L=SP/O=CryptoHub/CN=localhost"
  ```

- [ ] **Option C (Existentes)**: Copiar certificados já gerados
  ```bash
  cp /path/to/cert.pem certs/cert.pem
  cp /path/to/key.pem certs/key.pem
  ```

---

## 📋 Fase 3: Arquivos Docker (5 min)

### Verifying Docker Files
- [ ] `Dockerfile.prod` existe
  - [ ] Tem 2 stages (builder + runtime)
  - [ ] Define CMD com `gunicorn` 4 workers
  - [ ] Non-root user (appuser)

- [ ] `docker-compose.prod.yml` existe
  - [ ] 4 serviços: mongodb, redis, backend, nginx
  - [ ] Volumes para persistência: mongodb_data, redis_data
  - [ ] Network: backend_network (isolada)
  - [ ] Health checks em todos os serviços
  - [ ] Resource limits definidos

- [ ] `nginx.prod.conf` existe
  - [ ] SSL/TLS redirect HTTP → HTTPS
  - [ ] Proxy para backend em /api/v1
  - [ ] WebSocket support em /ws
  - [ ] Static frontend serving em /
  - [ ] Rate limiting zones

- [ ] `redis.prod.conf` existe
  - [ ] RDB snapshots habilitados
  - [ ] AOF (append-only file) habilitado
  - [ ] maxmemory 512mb com LRU eviction
  - [ ] Slow query logging

- [ ] `init-mongo.sh` existe
  - [ ] Cria collections: users, bots, audit_logs
  - [ ] JSON schema validation
  - [ ] Índices de performance
  - [ ] TTL para audit_logs (90 dias)

---

## 📋 Fase 4: Deploy Script (2 min)

### Deploy Automation
- [ ] `deploy.sh` existe na raiz
- [ ] `deploy.sh` é executável: `chmod +x deploy.sh`
- [ ] Contém functions: check_prerequisites, load_environment, run_migration, health_check
- [ ] Aceita comandos: deploy, clean, stop, logs, status

---

## 📋 Fase 5: Sistema Backend (5 min)

### Código Python
- [ ] `app/services/activation_manager.py` existe
  - [ ] Método `validate_activation()`
  - [ ] Método `activate_bot()` (singleton rule)
  - [ ] Método `validate_swap()` (2 free → 1 credit)
  - [ ] Método `record_swap()`

- [ ] `app/services/balance_guard.py` existe
  - [ ] Verifica balance na exchange
  - [ ] Previne "Minimum Order Amount"

- [ ] `app/services/kill_switch.py` existe
  - [ ] `activate_for_user()` para desligar todos
  - [ ] `get_history()` para auditoria
  - [ ] Registra em audit_logs com CRITICAL

- [ ] `app/bots/router.py` tem endpoints atualizados
  - [ ] `POST /bots/{id}/start` com 3 validadores
  - [ ] `PUT /bots/{id}/config` com swap validation
  - [ ] `GET /bots/{id}/swap-status`

- [ ] `app/users/model.py` tem campos:
  - [ ] `activation_credits` (int)
  - [ ] `plan` (Starter/Pro/Premium)
  - [ ] Property: `activation_credits_remaining`

- [ ] `app/bots/model.py` tem campos:
  - [ ] `is_active_slot` (bool)
  - [ ] `swap_count` (int)
  - [ ] `swap_history` (List[SwapHistory])

---

## 📋 Fase 6: Networking & Security (10 min)

### Firewall
- [ ] Porta 22 (SSH) aberta para seu IP apenas
  ```bash
  sudo ufw allow from YOUR_IP to any port 22
  ```

- [ ] Porta 80 (HTTP) aberta para todo mundo
  ```bash
  sudo ufw allow 80/tcp
  ```

- [ ] Porta 443 (HTTPS) aberta para todo mundo
  ```bash
  sudo ufw allow 443/tcp
  ```

- [ ] Portas internas FECHADAS:
  - [ ] 27017 (MongoDB) ❌ NÃO abrir
  - [ ] 6379 (Redis) ❌ NÃO abrir
  - [ ] 8000 (Backend) ❌ NÃO abrir

- [ ] Firewall ativado: `sudo ufw enable`

### Network Verificação
- [ ] Docker bridge network criada: `backend_network`
- [ ] MongoDB rodando apenas em 127.0.0.1:27017
- [ ] Redis rodando apenas em 127.0.0.1:6379
- [ ] Backend rodando apenas em 127.0.0.1:8000
- [ ] Nginx expondo apenas 80 e 443 para 0.0.0.0

### Permissões de Arquivo
- [ ] `.env.production`: `chmod 600 .env.production`
- [ ] `certs/key.pem`: `chmod 600 certs/key.pem`
- [ ] `deploy.sh`: `chmod +x deploy.sh`
- [ ] `init-mongo.sh`: `chmod +x init-mongo.sh` (inside Docker ok)

---

## 📋 Fase 7: Pré-Deploy Validação (5 min)

### Sistema Operacional
- [ ] Linux (Ubuntu 20.04+) ou macOS
- [ ] RAM disponível: Mínimo 4GB
  ```bash
  free -h | grep Mem
  ```

- [ ] Espaço em disco: Mínimo 20GB
  ```bash
  df -h /
  ```

- [ ] Sem processos usando portas críticas:
  ```bash
  sudo lsof -i :80 :443 :27017 :6379
  ```

### Docker
- [ ] Docker instalado: `docker --version` → 20.10+
  ```bash
  docker run hello-world  # Validar funcionamento
  ```

- [ ] Docker Compose instalado: `docker-compose --version` → 1.29+
  ```bash
  docker-compose version
  ```

- [ ] Docker daemon rodando
  ```bash
  docker ps -a  # Deve listar containers sem erro
  ```

- [ ] Espaço em disco para imagens:
  ```bash
  docker system df  # Mostrar uso
  ```

### Diretório Projeto
- [ ] Na raiz do projeto crypto-trade-hub/
- [ ] Arquivo checklist:
  ```bash
  ls -la Dockerfile.prod
  ls -la docker-compose.prod.yml
  ls -la deploy.sh
  ls -la .env.production
  ls -la certs/cert.pem certs/key.pem
  ```

---

## 📋 Fase 8: Executar Deploy (este é o grande momento!)

### Comando Deploy
```bash
# Tornar executável
chmod +x deploy.sh

# Executar
./deploy.sh

# Esperado output:
# ✅ Checking Docker installation...
# ✅ Checking Docker Compose...
# ✅ Building Docker images...
# ✅ Starting services...
# ✅ Initializing MongoDB replica set...
# ✅ Running migration...
# ✅ Health checks passed!
# ✅ Deployment complete!
```

- [ ] Deploy script executou sem erros
- [ ] Todos os 4 containers estão "Up"
- [ ] Todos os 4 containers estão "healthy"

### Validar Status
```bash
./deploy.sh status
```

- [ ] ✅ mongodb: Up (healthy)
- [ ] ✅ redis: Up (healthy)
- [ ] ✅ backend: Up (healthy)
- [ ] ✅ nginx: Up (healthy)

---

## 📋 Fase 9: Teste Funcional (10 min)

### Health Check
```bash
curl -k https://localhost/health
# Esperado: 200 OK
```

- [ ] Frontend respondendo (status 200)

### Backend API
```bash
curl -k https://localhost/api/v1/health
# Esperado: 200 OK
```

- [ ] Backend respondendo

### Testar Créditos de Ativação

1. **Get Access Token**
   ```bash
   TOKEN=$(curl -s -X POST https://localhost/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"user@example.com","password":"password"}' \
     -k | jq -r '.access_token')
   ```
   - [ ] Token obtido com sucesso

2. **Check Credits**
   ```bash
   curl -s https://localhost/api/v1/auth/profile/activation-credits \
     -H "Authorization: Bearer $TOKEN" \
     -k | jq
   ```
   - [ ] Retorna plan, activation_credits, activation_credits_remaining

3. **Start Bot com Créditos**
   ```bash
   curl -X POST https://localhost/api/v1/bots/BOT_ID/start \
     -H "Authorization: Bearer $TOKEN" \
     -k
   ```
   - [ ] Status 200 = sucesso (tem créditos)
   - [ ] Status 402 = erro (sem créditos)

4. **Test Swap Limit**
   ```bash
   curl -X PUT https://localhost/api/v1/bots/BOT_ID/config \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"trading_pair":"BTC/USDT"}' \
     -k
   ```
   - [ ] Primeiro swap: grátis
   - [ ] Segundo swap: grátis
   - [ ] Terceiro swap: 1 crédito consumido

### MongoDB Validação
```bash
docker-compose -f docker-compose.prod.yml exec mongodb mongosh \
  -u admin -p SENHA \
  --eval "db.users.findOne()"
```

- [ ] Users collection existe
- [ ] Dados foram migrados

### Redis Validação
```bash
docker-compose -f docker-compose.prod.yml exec redis redis-cli \
  -a SENHA PING
```

- [ ] Retorna "PONG"

### Nginx Logs
```bash
./deploy.sh logs nginx | tail -20
```

- [ ] Sem erros 502 Bad Gateway
- [ ] Sem erros SSL

---

## 📋 Fase 10: Post-Deployment (30 min)

### Configurar Monitoramento
- [ ] Alertas se backend cair
- [ ] Alertas se MongoDB usar >80% disco
- [ ] Alertas se Redis atingir maxmemory

### Backup Inicial
- [ ] Fazer backup do MongoDB:
  ```bash
  docker-compose -f docker-compose.prod.yml exec mongodb mongodump \
    -u admin -p SENHA --authenticationDatabase admin \
    --out /backup-$(date +%Y%m%d)
  ```

- [ ] Fazer backup do Redis:
  ```bash
  docker-compose -f docker-compose.prod.yml exec redis redis-cli \
    -a SENHA --rdb /backup-$(date +%Y%m%d).rdb
  ```

### Documentação
- [ ] Documentar senhas em local seguro (1Password, Vault, etc)
- [ ] Documentar IP do servidor
- [ ] Documentar domínio e certificado
- [ ] Documentar comando: `./deploy.sh logs` para troubleshooting

### Team Training
- [ ] Time ops sabe usar `./deploy.sh status`
- [ ] Team ops sabe ver logs: `./deploy.sh logs`
- [ ] Team ops sabe para parar: `./deploy.sh stop`
- [ ] Team ops sabe fazer rollback: `./deploy.sh clean` (CUIDADO!)

---

## 🎯 Final Status

### Antes de ir para Produção

**Todos os items desta checklist DEVEM estar marcados ✅**

Se algum item está ❌:
1. Voltar para a seção correspondente
2. Seguir as instruções
3. Marcar como ✅
4. Continuar

### Após Marcar Tudo ✅

Você está **100% pronto** para:
- [ ] Fazer deploy de produção
- [ ] Aceitar usuários reais
- [ ] Processar fundos reais
- [ ] Escalar a aplicação

---

## 📞 Suporte

Se algo der errado:

1. **Erros de Deploy**
   ```bash
   ./deploy.sh logs backend  # Ver logs do backend
   ./deploy.sh logs mongodb  # Ver logs do MongoDB
   ./deploy.sh logs nginx    # Ver logs do Nginx
   ```

2. **Erros de Conexão**
   - Ping backend: `curl -k https://localhost/health`
   - Ping MongoDB: `mongosh -u admin -p SENHA`
   - Ping Redis: `redis-cli PING`

3. **Docs**
   - Backend: Ver `app/services/activation_manager.py`
   - Config: Ver `.env.production.example`
   - Deploy: Ver `deploy.sh`

---

**Status**: 🚀 Pronto para deploy  
**Versão**: 1.0  
**Data**: 2026-02-11  
**Checklist**: PRODUCTION-READY quando todos ✅
