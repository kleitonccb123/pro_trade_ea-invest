# =============================================================================
# DEPLOYMENT GUIDE - Crypto Trade Hub
# =============================================================================
# Guia completo para deploy em produção com Docker
# =============================================================================

## 🚀 Quick Start (Desenvolvimento)

```bash
# 1. Clone o repositório
git clone <repository-url>
cd crypto-trade-hub

# 2. Copie e configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações

# 3. Inicie com Docker Compose
docker-compose up -d

# 4. Verifique os logs
docker-compose logs -f

# 5. Acesse a aplicação
# Frontend: http://localhost
# API Docs: http://localhost/docs
```

## 📋 Pré-requisitos

- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM mínimo
- 10GB espaço em disco

## 🔧 Configuração de Produção

### 1. Variáveis de Ambiente Obrigatórias

```bash
# Gerar chaves seguras
openssl rand -hex 32  # Para SECRET_KEY
openssl rand -hex 32  # Para JWT_SECRET_KEY
```

Edite `.env`:
```env
APP_ENV=production
DEBUG=false
SECRET_KEY=<chave-gerada>
JWT_SECRET_KEY=<chave-gerada>
```

### 2. Configurar MongoDB com Autenticação

No `docker-compose.yml`, adicione:
```yaml
mongodb:
  environment:
    MONGO_INITDB_ROOT_USERNAME: admin
    MONGO_INITDB_ROOT_PASSWORD: <senha-forte>
```

Atualize `MONGODB_URL`:
```env
MONGODB_URL=mongodb://admin:<senha>@mongodb:27017/crypto_trade_hub?authSource=admin
```

### 3. Configurar HTTPS (Obrigatório para Produção)

#### Opção A: Certificado Let's Encrypt (Recomendado)

```bash
# Instalar Certbot
apt-get install certbot

# Gerar certificado
certbot certonly --standalone -d seu-dominio.com

# Os certificados estarão em:
# /etc/letsencrypt/live/seu-dominio.com/fullchain.pem
# /etc/letsencrypt/live/seu-dominio.com/privkey.pem
```

Adicione no `docker-compose.yml`:
```yaml
nginx:
  volumes:
    - /etc/letsencrypt:/etc/letsencrypt:ro
```

#### Opção B: Cloudflare (SSL Flexível)

Configure o DNS para apontar para seu servidor e habilite SSL no Cloudflare.

### 4. Configurar Google OAuth (Opcional)

1. Acesse https://console.cloud.google.com/apis/credentials
2. Crie um novo OAuth 2.0 Client ID
3. Configure Authorized redirect URIs: `https://seu-dominio.com/api/auth/google/callback`
4. Adicione ao `.env`:
```env
GOOGLE_CLIENT_ID=<seu-client-id>
GOOGLE_CLIENT_SECRET=<seu-client-secret>
GOOGLE_REDIRECT_URI=https://seu-dominio.com/api/auth/google/callback
```

### 5. Configurar Webhooks (Opcional)

#### Telegram:
1. Crie um bot com @BotFather
2. Obtenha o token
3. Inicie uma conversa com o bot e obtenha seu chat_id

```env
TELEGRAM_BOT_TOKEN=<bot-token>
TELEGRAM_CHAT_ID=<seu-chat-id>
```

#### Discord:
1. No servidor Discord, vá em Configurações > Integrações > Webhooks
2. Crie um novo webhook e copie a URL

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

## 🛡️ Segurança

### Checklist de Produção

- [ ] SECRET_KEY e JWT_SECRET_KEY são valores aleatórios fortes
- [ ] DEBUG=false
- [ ] HTTPS configurado
- [ ] MongoDB com autenticação habilitada
- [ ] Redis com autenticação (se exposto)
- [ ] Firewall configurado (apenas portas 80, 443)
- [ ] Rate limiting ativo
- [ ] Backups automáticos configurados
- [ ] Monitoramento de logs ativo

### Portas a Expor

| Porta | Serviço | Acesso |
|-------|---------|--------|
| 80    | HTTP    | Público (redireciona para 443) |
| 443   | HTTPS   | Público |
| 27017 | MongoDB | Interno apenas |
| 6379  | Redis   | Interno apenas |
| 8000  | Backend | Interno apenas |

## 📊 Monitoramento

### Verificar Saúde dos Serviços

```bash
# Status dos containers
docker-compose ps

# Logs em tempo real
docker-compose logs -f

# Logs de um serviço específico
docker-compose logs -f backend

# Endpoint de health
curl http://localhost/health
```

### Métricas MongoDB

```bash
docker-compose exec mongodb mongosh --eval "db.serverStatus()"
```

### Uso de Recursos

```bash
docker stats
```

## 🔄 Atualizações

### Deploy de Nova Versão

```bash
# 1. Pull das mudanças
git pull origin main

# 2. Rebuild e reiniciar
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 3. Verificar logs
docker-compose logs -f
```

### Rollback

```bash
# Voltar para versão anterior
git checkout <commit-anterior>
docker-compose down
docker-compose build
docker-compose up -d
```

## 💾 Backups

### Backup MongoDB

```bash
# Backup manual
docker-compose exec mongodb mongodump --out /backup

# Copiar para host
docker cp $(docker-compose ps -q mongodb):/backup ./backup-$(date +%Y%m%d)
```

### Script de Backup Automático

```bash
#!/bin/bash
# backup.sh - Execute com cron

BACKUP_DIR="/backups/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)

docker-compose exec -T mongodb mongodump --archive > "$BACKUP_DIR/backup_$DATE.archive"

# Manter apenas últimos 7 dias
find $BACKUP_DIR -type f -mtime +7 -delete
```

Adicione ao crontab:
```bash
0 2 * * * /path/to/backup.sh
```

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs detalhados
docker-compose logs <service-name>

# Verificar configuração
docker-compose config
```

### Erro de conexão com MongoDB

```bash
# Verificar se MongoDB está rodando
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# Verificar variáveis de ambiente
docker-compose exec backend env | grep MONGO
```

### Frontend não conecta ao Backend

1. Verificar CORS_ORIGINS no `.env`
2. Verificar VITE_API_URL
3. Verificar se nginx está roteando corretamente

```bash
# Testar API diretamente
curl http://localhost/api/health
```

### Alto uso de memória

```bash
# Limitar memória dos containers no docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 512M
```

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique os logs: `docker-compose logs -f`
2. Consulte a documentação da API: `/docs`
3. Abra uma issue no repositório

---

**Versão:** 1.0.0  
**Última atualização:** 2024
