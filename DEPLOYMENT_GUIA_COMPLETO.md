# 🚀 GUIA COMPLETO: DEPLOYMENT CRYPTO TRADE HUB EM VPS HOSTINGER

**Data:** Março 23, 2026  
**Objetivo:** Deploy em produção + Guia para atualizações futuras  
**Tempo estimado:** 4-6 horas (primeira vez)

---

## 📋 CHECKLIST PRÉ-DEPLOYMENT

- [ ] Domínio registrado e acessível
- [ ] VPS Hostinger contratada (mínimo: 4GB RAM, 2 vCPU, Ubuntu 22.04 LTS)
- [ ] Acesso SSH à VPS configurado
- [ ] Repositório Git pronto com todas as mudanças commitadas
- [ ] Arquivo `.env.production` preparado com suas chaves
- [ ] Certificado SSL Let's Encrypt pronto (gratuito)
- [ ] Backup do banco de dados local feito

---

## PARTE 1: PREPARAR A VPS HOSTINGER

### Passo 1.1: Conectar à VPS via SSH

```bash
# No seu computador local
ssh root@seu_ip_vps
# OU se tiver chave SSH
ssh -i /path/to/key.pem root@seu_ip_vps
```

**Senhas iniciais estão no painel Hostinger → Detalhes do Servidor**

### Passo 1.2: Atualizar Sistema

```bash
apt update && apt upgrade -y
apt install -y curl wget git vim htop
```

### Passo 1.3: Instalar Docker e Docker Compose

```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker root

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Validar
docker --version
docker-compose --version
```

### Passo 1.4: Instalar Python 3.11 (para backend)

```bash
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
python3.11 --version
```

### Passo 1.5: Instalar Node.js (para frontend)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
apt install -y nodejs npm

# Validar
node --version
npm --version
```

### Passo 1.6: Criar usuário não-root (segurança)

```bash
# Criar usuário
useradd -m -s /bin/bash appuser
usermod -aG docker appuser
usermod -aG sudo appuser

# Definir senha
passwd appuser

# Trocar para novo usuário
su - appuser
```

---

## PARTE 2: CONFIGURAR DOMÍNIO NA HOSTINGER

### Passo 2.1: Apontar Domínio para VPS

1. **Painel Hostinger → Domínios → Seu Domínio**
2. **Definir Apontamento DNS:**
   - Vá em **DNS Zone** ou **Gerenciar DNS**
   - Delete registros antigos (se houver)
   - Adicione novo registro A:
     ```
     Type: A
     Host: @ (ou deixe em branco)
     Value: seu_ip_da_vps
     TTL: 3600
     ```
   - Adicione também para www:
     ```
     Type: A
     Host: www
     Value: seu_ip_da_vps
     TTL: 3600
     ```

3. **Validar propagação** (pode levar 15-30 min):
   ```bash
   nslookup seu-dominio.com
   ping seu-dominio.com
   ```

### Passo 2.2: Criar Subdomínio para API (opcional)

Se quiser `api.seu-dominio.com`:

```
Type: A
Host: api
Value: seu_ip_da_vps
TTL: 3600
```

---

## PARTE 3: CLONAR E PREPARAR PROJETO NA VPS

### Passo 3.1: Clonar Repositório

```bash
# Na VPS, como appuser
cd /home/appuser

# Clonar projeto
git clone https://seu-github-url/crypto-trade-hub.git
cd crypto-trade-hub

# OU se já existe localmente, fazer push e depois clonar:
# git push origin main
```

### Passo 3.2: Preparar Arquivo .env

```bash
# Na VPS, copiar e editar template
cp .env.example .env.production

# Editar com vi/nano
nano .env.production
```

**Variáveis críticas a configurar:**

```bash
# ===== DOMÍNIO =====
DOMAIN=seu-dominio.com
FRONTEND_URL=https://seu-dominio.com
BACKEND_URL=https://seu-dominio.com/api

# ===== BANCO DE DADOS =====
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=SENHAFORTE_32CHARS_AQUI
MONGO_DBNAME=crypto_trade_hub

# ===== REDIS =====
REDIS_PASSWORD=SENHAFORTE_16CHARS_AQUI

# ===== JWT E SEGURANÇA =====
JWT_SECRET_KEY=CHAVE_HEX_64CHARS_AQUI
ENCRYPTION_KEY=FERNET_KEY_AQUI
CREDENTIAL_ENCRYPTION_KEY=FERNET_KEY_AQUI
STRATEGY_ENCRYPTION_KEY=FERNET_KEY_AQUI

# ===== SSL =====
SSL_CERT_PATH=/etc/letsencrypt/live/seu-dominio.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/seu-dominio.com/privkey.pem

# ===== APIS EXTERNAS (se tiver) =====
KUCOIN_API_KEY=seu_key
KUCOIN_API_SECRET=seu_secret

# ===== ENVIRONMENT =====
ENVIRONMENT=production
LOG_LEVEL=INFO
PAGE_SIZE=50
```

> **Gerar chaves fortes automaticamente:**
```bash
# JWT Secret (64 hex)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Fernet Keys
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# DB Password (32 hex)
python3 -c "import secrets; print(secrets.token_hex(16))"
```

### Passo 3.3: Fazer Build do Frontend

```bash
# Na VPS
npm install
npm run build

# Validar build
ls -la dist/  # Deve ter arquivos estáticos
```

---

## PARTE 4: CERTIFICADO SSL COM LET'S ENCRYPT

### Passo 4.1: Instalar Certbot

```bash
apt install -y certbot python3-certbot-nginx
```

### Passo 4.2: Gerar Certificado (Método Standalone)

```bash
# PARAR nginx/docker ANTES (se houver)
docker-compose -f docker-compose.prod.yml down

# Gerar certificado
certbot certonly --standalone \
  --email seu_email@dominio.com \
  --agree-tos \
  -d seu-dominio.com \
  -d www.seu-dominio.com

# Validar
ls -la /etc/letsencrypt/live/seu-dominio.com/
```

**Saída esperada:**
```
fullchain.pem  (Certificado)
privkey.pem    (Chave privada)
```

### Passo 4.3: Configurar Auto-Renovação

```bash
# Testar renovação
certbot renew --dry-run

# Setup cron automático (já vem pronto)
systemctl enable certbot.timer
systemctl start certbot.timer
```

---

## PARTE 5: SUBIR DOCKER COMPOSE EM PRODUÇÃO

### Passo 5.1: Revisar docker-compose.prod.yml

```bash
# Abrir arquivo para conferir
cat docker-compose.prod.yml | head -50
```

**Estrutura esperada:**
- MongoDB (porta 27017, apenas localhost)
- Redis (porta 6379, apenas localhost)
- Backend FastAPI (porta 8000)
- Nginx (portas 80/443)
- Frontend (servida via Nginx)

### Passo 5.2: Preparar Volumes e Permissões

```bash
# Criar diretórios para volumes
mkdir -p /home/appuser/docker-volumes/{mongo,redis,nginx}

# Permissões
chmod 755 /home/appuser/docker-volumes

# Copiar nginx.prod.conf para local correto
mkdir -p /home/appuser/nginx
cp nginx.prod.conf /home/appuser/nginx/nginx.conf
```

### Passo 5.3: Subir Containers

```bash
# Na pasta do projeto
cd /home/appuser/crypto-trade-hub

# Subir em background
docker-compose -f docker-compose.prod.yml up -d

# Acompanhar logs
docker-compose -f docker-compose.prod.yml logs -f

# Esperar 10-15 seg até serviços ficarem saudáveis
sleep 15

# Validar status
docker-compose -f docker-compose.prod.yml ps
```

**Esperado:**
```
NAME                    STATUS
crypto-trade-mongodb    Up (healthy)
crypto-trade-redis      Up (healthy)
crypto-trade-backend    Up (healthy)
crypto-trade-nginx      Up
```

### Passo 5.4: Validar Conectividade

```bash
# Teste local (dentro VPS)
curl http://localhost/api/health
curl http://seu-dominio.com/api/health  (será HTTPS em breve)

# Todos devem retornar 200 OK
```

---

## PARTE 6: CONFIGURAR NGINX PARA SSL

### Passo 6.1: Criar nginx.prod.conf com SSL

**Arquivo: `/home/appuser/nginx/nginx.conf`**

```nginx
# Nginx Production with SSL

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 4096;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 20M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss 
               application/rss+xml font/truetype font/opentype;

    # ===== REDIRECT HTTP → HTTPS =====
    server {
        listen 80;
        listen [::]:80;
        server_name seu-dominio.com www.seu-dominio.com;
        
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        location / {
            return 301 https://$server_name$request_uri;
        }
    }

    # ===== HTTPS - FRONTEND + BACKEND =====
    server {
        listen 443 ssl http2;
        listen [::]:443 ssl http2;
        server_name seu-dominio.com www.seu-dominio.com;

        # ===== SSL CERTIFICATES =====
        ssl_certificate /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com/privkey.pem;
        
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # ===== SECURITY HEADERS =====
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;

        # ===== FRONTEND (React SPA) =====
        location / {
            # Servir arquivos estáticos
            root /app/dist;
            try_files $uri $uri/ /index.html;
            
            # Cache busting
            location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
                expires 1y;
                add_header Cache-Control "public, immutable";
            }
        }

        # ===== BACKEND API (/api/*) =====
        location /api/ {
            proxy_pass http://backend:8000/;
            
            # Headers
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # ===== HEALTH CHECK =====
        location /health {
            access_log off;
            return 200 "OK\n";
            add_header Content-Type text/plain;
        }
    }
}
```

### Passo 6.2: Atualizar Docker Compose com Volumes Corretos

**docker-compose.prod.yml — seção nginx:**

```yaml
nginx:
  image: nginx:alpine
  container_name: crypto-trade-nginx
  
  ports:
    - "80:80"
    - "443:443"
  
  volumes:
    # Arquivo de configuração
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    
    # Frontend (arquivos estáticos)
    - ./dist:/app/dist:ro
    
    # Certificados SSL
    - /etc/letsencrypt:/etc/letsencrypt:ro
    
    # Logs
    - nginx_logs:/var/log/nginx
  
  depends_on:
    - backend
  
  networks:
    - backend_network
```

### Passo 6.3: Recarregar Docker Compose

```bash
# Reconstruir com novo nginx.conf
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# Validar
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs nginx
```

### Passo 6.4: Testar SSL

```bash
# Testar HTTPS
curl -I https://seu-dominio.com
curl -I https://seu-dominio.com/api/health

# Ambos devem retornar 200/301
```

---

## PARTE 7: TESTES E VALIDAÇÃO

### Passo 7.1: Validar Frontend

```bash
# Abrir navegador
https://seu-dominio.com

# Deve aparecer a aplicação React
# Verificar console (F12) sem erros de CORS
```

### Passo 7.2: Validar Backend

```bash
# A partir do navegador ou terminal
curl https://seu-dominio.com/api/health

# Resposta esperada:
# {"status":"ok","timestamp":"2026-03-23T10:00:00"}
```

### Passo 7.3: Monitorar Logs

```bash
# Logs em tempo real
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f nginx

# Buscar erros
docker-compose -f docker-compose.prod.yml logs backend | grep -i error
```

### Passo 7.4: Teste de SSL (A+ no SSLLabs)

```bash
# Ir para https://www.ssllabs.com/ssltest/
# E testar seu domínio

# Esperado: Grade A+ ou A
```

---

## PARTE 8: CONFIGURAR BACKUPS AUTOMÁTICOS

### Passo 8.1: Criar Script de Backup

**Arquivo: `/home/appuser/backup.sh`**

```bash
#!/bin/bash

# Backup automático MongoDB + Redis

BACKUP_DIR="/home/appuser/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_$DATE"

# Criar diretório
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Iniciando backup..."

# 1. Backup MongoDB
MONGO_CONTAINER=$(docker ps --filter "name=crypto-trade-mongodb" -q)
docker exec $MONGO_CONTAINER mongodump --username admin --password $MONGO_ROOT_PASSWORD \
  --authenticationDatabase admin \
  --out /tmp/mongo_backup

# 2. Compactar
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" /tmp/mongo_backup

# 3. Limpeza
rm -rf /tmp/mongo_backup

# 4. Keeper ultimos 7 dias
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

echo "[$(date)] Backup concluído: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
```

### Passo 8.2: Configurar Cron

```bash
# Abrir cron editor
crontab -e

# Adicionar (backup diário às 2AM)
0 2 * * * /home/appuser/backup.sh >> /home/appuser/backup.log 2>&1

# Validar
crontab -l
```

---

## PARTE 9: MONITORAMENTO

### Passo 9.1: Criar Script de Health Check

**Arquivo: `/home/appuser/health_check.sh`**

```bash
#!/bin/bash

# Verificar saúde dos serviços

DOMAIN="seu-dominio.com"

echo "=== Crypto Trade Hub - Health Check ==="
echo "Data: $(date)"
echo ""

# Frontend
echo -n "Frontend: "
curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN
echo ""

# Backend API
echo -n "Backend API: "
curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/api/health
echo ""

# Docker containers
echo "Containers:"
docker-compose -f /home/appuser/crypto-trade-hub/docker-compose.prod.yml ps

# Uso de recursos
echo ""
echo "Uso de Disco:"
df -h / | grep -v Filesystem

echo ""
echo "Uso de Memória:"
free -h | grep Mem

echo ""
echo "Uso de CPU:"
top -bn1 | grep "Cpu(s)" | awk '{print $2}'
```

### Passo 9.2: Executar Health Check Manual

```bash
chmod +x /home/appuser/health_check.sh
/home/appuser/health_check.sh
```

---

## 🔄 PARTE 10: PROCEDIMENTO PARA ATUALIZAÇÕES FUTURAS

**Após qualquer mudança APÓS deployment em produção, siga este procedure:**

### Modificação 1: Mudança Apenas no Frontend (React/HTML/CSS)

```bash
# Na VPS

cd /home/appuser/crypto-trade-hub

# 1. Fazer pull das mudanças
git pull origin main

# 2. Rebuild frontend
npm run build

# 3. Recarregar nginx (sem downtime)
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

# ✅ Pronto! Frontend atualizado, nenhum downtime.
```

**Tempo:** ~2-5 minutos

---

### Modificação 2: Mudança no Backend (Python/FastAPI)

```bash
# Na VPS

cd /home/appuser/crypto-trade-hub

# 1. Fazer pull das mudanças
git pull origin main

# 2. Rebuild imagem Docker do backend
docker-compose -f docker-compose.prod.yml build backend

# 3. Parar container antigo gracefully
docker-compose -f docker-compose.prod.yml stop -t 30 backend

# 4. Iniciar novo container
docker-compose -f docker-compose.prod.yml up -d backend

# 5. Validar logs
docker-compose -f docker-compose.prod.yml logs backend | tail -20

# ✅ Pronto! Backend atualizado.
```

**Tempo:** ~1-3 minutos (downtime mínimo: ~30 seg)

---

### Modificação 3: Mudança no Banco de Dados (Migrations)

```bash
# Na VPS

cd /home/appuser/crypto-trade-hub

# 1. Fazer pull
git pull origin main

# 2. Executar migrations dentro do container
docker-compose -f docker-compose.prod.yml exec backend python -m alembic upgrade head

# 3. Validar
docker-compose -f docker-compose.prod.yml logs backend | grep -i migration

# ✅ Pronto! Banco atualizado sem downtime.
```

**Tempo:** Depende das migrations (geralmente <5 min)

---

### Modificação 4: Mudança em Ambos Frontend + Backend

```bash
# Combinar tudo acima

cd /home/appuser/crypto-trade-hub

git pull origin main

npm run build

docker-compose -f docker-compose.prod.yml build backend

docker-compose -f docker-compose.prod.yml stop -t 30 backend

docker-compose -f docker-compose.prod.yml up -d backend

docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

sleep 5

docker-compose -f docker-compose.prod.yml logs -f backend
```

**Tempo:** ~3-5 minutos

---

### Modificação 5: Atualizar Dependências (npm/pip)

```bash
# Frontend
npm install  # No seu PC, fazer push ao git
git push

# OU Backend
pip install -r backend/requirements.txt  # No seu PC
docker-compose -f docker-compose.prod.yml build backend
docker-compose -f docker-compose.prod.yml up -d backend
```

---

## ⚠️ PROCEDIMENTOS DE EMERGÊNCIA

### Vendo Aplicação Quebrou (Rollback)

```bash
# 1. Parar containers
docker-compose -f docker-compose.prod.yml down

# 2. Git volta para versão anterior
cd /home/appuser/crypto-trade-hub
git reset --hard HEAD~1  # Volta 1 commit atrás

# 3. Rebuild e restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 4. Verificar logs
docker-compose -f docker-compose.prod.yml logs -f backend
```

---

### Disco Cheio

```bash
# Identificar arquivos grandes
du -sh /var/lib/docker/*
du -sh /home/appuser/backups/*

# Limpar Docker (dangling)
docker system prune -a

# Remover backups antigos
rm /home/appuser/backups/backup_*.tar.gz  # Exceto últimos X

# Limpar logs (rolar para .1, .2, etc)
journalctl --vacuum=500M
```

---

### Memória/CPU Alta

```bash
# Verificar qual container consome
docker stats

# Redimensionar limits no docker-compose.prod.yml
# Depois: docker-compose -f docker-compose.prod.yml up -d
```

---

## 📊 MONITORAMENTO CONTÍNUO

### Configurar Alertas via Email (Cron)

**Arquivo: `/home/appuser/alert_check.sh`**

```bash
#!/bin/bash

# Se algum serviço falhar, enviar email

SERVICES=("backend" "nginx" "mongodb" "redis")
EMAIL="seu_email@dominio.com"
HOSTNAME=$(hostname)

for service in "${SERVICES[@]}"; do
  if ! docker ps | grep -q "$service"; then
    echo "ALERTA: Serviço $service não está rodando!" | \
      mail -s "[ALERTA] $HOSTNAME - $service DOWN" $EMAIL
  fi
done

# Verificar espaço em disco
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 85 ]; then
  echo "ALERTA: Disco com ${DISK_USAGE}% de uso!" | \
    mail -s "[ALERTA] $HOSTNAME - Disco Cheio" $EMAIL
fi
```

### Executar a Cada 30 Minutos

```bash
crontab -e

# Adicionar:
*/30 * * * * /home/appuser/alert_check.sh
```

---

## 🔐 CHECKLIST DE SEGURANÇA

- [ ] SSH configurado com key-based auth (sem password)
- [ ] Firewall ativo (UFW)
  ```bash
  ufw enable
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw status
  ```
- [ ] Fail2Ban instalado
  ```bash
  apt install -y fail2ban
  systemctl enable fail2ban
  ```
- [ ] Senhas de banco de dados fortes (32+ chars)
- [ ] `.env` não em repositório público
- [ ] Backups testados (tentar restore)
- [ ] SSL válido e renovação automática testada
- [ ] MongoDB com auth obrigatória
- [ ] Redis com senha definida

---

## 🎓 REFERÊNCIA RÁPIDA - COMANDOS ESSENCIAIS

```bash
# Ver status dos containers
docker-compose -f docker-compose.prod.yml ps

# Ver logs em tempo real
docker-compose -f docker-compose.prod.yml logs -f [serviço]

# Parar tudo gracefully
docker-compose -f docker-compose.prod.yml stop

# Restart um serviço
docker-compose -f docker-compose.prod.yml restart [serviço]

# Executar comando dentro do container
docker-compose -f docker-compose.prod.yml exec backend python script.py

# Remover volumes (CUIDADO - perda de dados!)
docker-compose -f docker-compose.prod.yml down -v

# Aprovisionar update sem downtime
git pull && npm run build && docker-compose -f docker-compose.prod.yml build backend && docker-compose -f docker-compose.prod.yml up -d
```

---

## 📞 SUPORTE E TROUBLESHOOTING

### Conexão Recusada (Connection Refused)

```bash
# Pode ser:
# 1. Container não está rodando
docker-compose -f docker-compose.prod.yml ps

# 2. Porta bloqueada
netstat -tulpn | grep LISTEN

# 3. Firewall
ufw status
```

### 502 Bad Gateway

```bash
# Verifica se backend está saudável
docker-compose -f docker-compose.prod.yml logs backend

# Se tiver erro, ver logs detalhados
docker-compose -f docker-compose.prod.yml exec backend journalctl -u app
```

### Certificado Expirado

```bash
# Renovar manualmente
certbot renew --force-renewal

# Validar
ssl-cert-check -c /etc/letsencrypt/live/seu-dominio.com/fullchain.pem
```

---

## 📈 PRÓXIMOS PASSOS

1. **Hoje:** Deploy inicial (seguir Partes 1-7)
2. **Amanhã:** Configurar backups + monitoramento (Partes 8-9)
3. **Semana que vem:** Testar procedimento de update (Parte 10)
4. **Contínuo:** Monitorar logs, usar health checks

---

## 📝 NOTAS IMPORTANTES

> ⚠️ **Nunca faça commit de `.env` com dados reais**  
> Guardar .env localmente e usar variáveis secretas apenas na VPS

> ⚠️ **Sempre fazer backup antes de qualquer alteração grande**  
> Script estará rodando diariamente via cron

> ⚠️ **TLS/SSL é OBRIGATÓRIO em produção**  
> Let's Encrypt gratuito, renovação automática

> ⚠️ **Health checks salvam sua aplicação**  
> Configurar alertas para downtime

---

**Criado em:** Março 23, 2026  
**Versão:** 1.0  
**Status:** Pronto para deploy ✅
