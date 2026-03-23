#!/bin/bash

################################################################################
# Crypto Trade Hub - AUTO DEPLOYMENT SCRIPT
################################################################################
# 
# Este script automatiza o deployment completo da VPS
# 
# Uso:
#   chmod +x deploy_vps.sh
#   ./deploy_vps.sh seu-dominio.com seu_email@dominio.com
#
# PRÉ-REQUISITOS:
#   - VPS Ubuntu 22.04 LTS
#   - SSH root access
#   - Domínio apontando para VPS
#
################################################################################

set -euo pipefail

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Funções de logging
log_info()    { echo -e "${BLUE}[INFO]${NC}    $1"; }
log_success() { echo -e "${GREEN}[✓]${NC}     $1"; }
log_warn()    { echo -e "${YELLOW}[AVISO]${NC}   $1"; }
log_error()   { echo -e "${RED}[ERRO]${NC}    $1"; }
log_step()    { echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }

# Validar argumentos
if [ $# -lt 2 ]; then
  log_error "Uso: $0 <dominio.com> <email@dominio.com>"
  echo ""
  echo "Exemplo:"
  echo "  $0 protradeeainvest.com noreply@protradeeainvest.com"
  exit 1
fi

DOMAIN="$1"
EMAIL="$2"
APP_USER="appuser"
APP_HOME="/home/$APP_USER"
PROJECT_DIR="$APP_HOME/crypto-trade-hub"

################################################################################
# 1. VERIFICAR PERMISSÕES
################################################################################

log_step "PASSO 1/8: Verificando Permissões"

if [ "$EUID" -ne 0 ]; then
  log_error "Este script deve ser executado como root"
  exit 1
fi

log_success "Executando como root"

################################################################################
# 2. ATUALIZAR SISTEMA
################################################################################

log_step "PASSO 2/8: Atualizar Sistema"

log_info "apt update && apt upgrade..."
apt update > /dev/null 2>&1
apt upgrade -y > /dev/null 2>&1

log_info "Instalando dependências básicas..."
apt install -y curl wget git vim htop > /dev/null 2>&1

log_success "Sistema atualizado"

################################################################################
# 3. INSTALAR DOCKER
################################################################################

log_step "PASSO 3/8: Instalar Docker"

if command -v docker &> /dev/null; then
  log_warn "Docker já instalado"
  docker --version
else
  log_info "Baixando Docker..."
  curl -fsSL https://get.docker.com -o get-docker.sh > /dev/null 2>&1
  sh get-docker.sh > /dev/null 2>&1
  rm get-docker.sh
  
  log_success "Docker instalado"
fi

# Docker Compose
if command -v docker-compose &> /dev/null; then
  log_warn "Docker Compose já instalado"
else
  log_info "Instalando Docker Compose..."
  COMPOSE_VERSION="v2.24.0"
  DOWNLOAD_URL="https://github.com/docker/compose/releases/download/$COMPOSE_VERSION/docker-compose-$(uname -s)-$(uname -m)"
  curl -L "$DOWNLOAD_URL" -o /usr/local/bin/docker-compose > /dev/null 2>&1
  chmod +x /usr/local/bin/docker-compose
  
  log_success "Docker Compose v2.24.0 instalado"
fi

################################################################################
# 4. INSTALAR PYTHON + NODE
################################################################################

log_step "PASSO 4/8: Instalar Python 3.11 e Node.js"

log_info "Python 3.11..."
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip > /dev/null 2>&1
log_success "Python 3.11 instalado"

log_info "Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash > /dev/null 2>&1
apt install -y nodejs npm > /dev/null 2>&1
log_success "Node.js instalado"

################################################################################
# 5. CRIAR USUÁRIO NÃO-ROOT
################################################################################

log_step "PASSO 5/8: Criar Usuário '$APP_USER'"

if id "$APP_USER" &>/dev/null; then
  log_warn "Usuário '$APP_USER' já existe"
else
  log_info "Criando usuário..."
  useradd -m -s /bin/bash "$APP_USER"
  usermod -aG docker "$APP_USER"
  
  # Gerar senha aleatória
  USERPASS=$(openssl rand -base64 12)
  echo "$APP_USER:$USERPASS" | chpasswd
  
  log_success "Usuário '$APP_USER' criado"
  log_warn "Senha: $USERPASS (guardar em lugar seguro!)"
fi

################################################################################
# 6. INSTALAR CERTBOT (Le Encrypt)
################################################################################

log_step "PASSO 6/8: Instalar Certbot (Let's Encrypt)"

apt install -y certbot python3-certbot-nginx > /dev/null 2>&1

log_info "Aguardando DNS propagar para $DOMAIN..."
sleep 5

log_info "Gerando certificado SSL..."

# Tentar gerar certificado 3 vezes
attempt=1
max_attempts=3

while [ $attempt -le $max_attempts ]; do
  if certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" 2>&1; then
    log_success "Certificado SSL gerado com sucesso"
    break
  else
    if [ $attempt -eq $max_attempts ]; then
      log_error "Falha ao gerar certificado. Verificar DNS propagation."
      log_error "Comando manual: certbot certonly --standalone --email $EMAIL -d $DOMAIN -d www.$DOMAIN"
      exit 1
    fi
    
    log_warn "Tentativa $attempt/$max_attempts falhou, retentando em 30s..."
    sleep 30
    ((attempt++))
  fi
done

# Setup auto-renovação
systemctl enable certbot.timer > /dev/null 2>&1
systemctl start certbot.timer > /dev/null 2>&1
log_success "Auto-renovação SSL configurada"

################################################################################
# 7. CLONAR PROJETO E PREPARAR
################################################################################

log_step "PASSO 7/8: Clonar Projeto"

if [ -d "$PROJECT_DIR" ]; then
  log_warn "Diretório $PROJECT_DIR já existe"
else
  log_info "Clonando repositório..."
  
  # Criar diretório
  sudo -u "$APP_USER" mkdir -p "$APP_HOME"
  
  # Su para appuser e clonar
  sudo -u "$APP_USER" bash -c "cd $APP_HOME && git clone https://github.com/seu-usuario/crypto-trade-hub.git" 2>&1 || \
    log_warn "Falha ao clonar. Certificar repo URL e acesso git."
fi

log_info "Preparando arquivos..."

# Criar diretórios
sudo -u "$APP_USER" mkdir -p "$PROJECT_DIR/docker-volumes/{mongo,redis,nginx}"
sudo -u "$APP_USER" mkdir -p "$PROJECT_DIR/backups"

# Copiar nginx.conf
log_info "Preparando Nginx..."
sudo -u "$APP_USER" bash -c "mkdir -p $PROJECT_DIR/nginx && cp $PROJECT_DIR/nginx.prod.conf $PROJECT_DIR/nginx/nginx.conf"

# Build frontend
log_info "Build Frontend..."
sudo -u "$APP_USER" bash -c "cd $PROJECT_DIR && npm install > /dev/null 2>&1 && npm run build > /dev/null 2>&1"
log_success "Frontend buildado"

################################################################################
# 8. SUBIR DOCKER COMPOSE
################################################################################

log_step "PASSO 8/8: Subir Aplicação"

log_info "Subindo Docker Compose..."

# Gerar variáveis de ambiente aleatórias
MONGO_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))")
REDIS_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Criar .env.production
log_info "Gerando .env.production..."

cat > "$PROJECT_DIR/.env.production" << EOF
# ===== DOMÍNIO =====
DOMAIN=$DOMAIN
FRONTEND_URL=https://$DOMAIN
BACKEND_URL=https://$DOMAIN/api

# ===== BANCO DE DADOS =====
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=$MONGO_PASS
MONGO_DBNAME=crypto_trade_hub

# ===== REDIS =====
REDIS_PASSWORD=$REDIS_PASS

# ===== JWT E SEGURANÇA =====
JWT_SECRET_KEY=$JWT_SECRET

# ===== SSL =====
SSL_CERT_PATH=/etc/letsencrypt/live/$DOMAIN/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/$DOMAIN/privkey.pem

# ===== ENVIRONMENT =====
ENVIRONMENT=production
LOG_LEVEL=INFO
PAGE_SIZE=50
EOF

chmod 600 "$PROJECT_DIR/.env.production"

log_info "Iniciando containers..."
cd "$PROJECT_DIR"

# Subir
sudo -u "$APP_USER" docker-compose -f docker-compose.prod.yml up -d > /dev/null 2>&1

# Aguardar
sleep 15

# Verificar
MONGO_CHECK=$(docker ps | grep crypto-trade-mongodb || echo "")
REDIS_CHECK=$(docker ps | grep crypto-trade-redis || echo "")
BACKEND_CHECK=$(docker ps | grep crypto-trade-backend || echo "")

if [ -n "$MONGO_CHECK" ] && [ -n "$REDIS_CHECK" ] && [ -n "$BACKEND_CHECK" ]; then
  log_success "Todos os containers rodando ✓"
else
  log_error "Algum container não iniciou"
  log_info "Verificar logs: docker-compose -f docker-compose.prod.yml logs"
  exit 1
fi

################################################################################
# 9. CONFIGURAR BACKUPS
################################################################################

log_step "CONFIGURAR BACKUPS"

cat > "$PROJECT_DIR/backup.sh" << 'BACKUP_EOF'
#!/bin/bash

BACKUP_DIR="/home/appuser/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
MONGO_PASS=$(grep MONGO_ROOT_PASSWORD /home/appuser/crypto-trade-hub/.env.production | cut -d= -f2)

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Iniciando backup..."

# Backup MongoDB
MONGO_CONTAINER=$(docker ps --filter "name=crypto-trade-mongodb" -q)
docker exec $MONGO_CONTAINER mongodump \
  --username admin \
  --password "$MONGO_PASS" \
  --authenticationDatabase admin \
  --out /tmp/mongo_backup

# Compactar
tar -czf "$BACKUP_DIR/backup_$DATE.tar.gz" /tmp/mongo_backup

# Limpeza
rm -rf /tmp/mongo_backup

# Keeper ultimos 7 dias
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

echo "[$(date)] Backup concluído"
BACKUP_EOF

chmod +x "$PROJECT_DIR/backup.sh"
sudo -u "$APP_USER" bash -c "crontab -l 2>/dev/null | grep -v 'backup.sh' | crontab -; crontab -l 2>/dev/null > /tmp/cron && echo '0 2 * * * /home/appuser/crypto-trade-hub/backup.sh >> /home/appuser/backup.log 2>&1' >> /tmp/cron && crontab /tmp/cron"

log_success "Backups configurados (diariamente 2AM)"

################################################################################
# 10. CONFIGURAR FIREWALL
################################################################################

log_step "CONFIGURAR FIREWALL"

ufw --force enable > /dev/null 2>&1
ufw default deny incoming > /dev/null 2>&1
ufw default allow outgoing > /dev/null 2>&1
ufw allow 22/tcp > /dev/null 2>&1
ufw allow 80/tcp > /dev/null 2>&1
ufw allow 443/tcp > /dev/null 2>&1

log_success "Firewall habilitado"

################################################################################
# RESUMO FINAL
################################################################################

log_step "🎉 DEPLOYMENT COMPLETO!"

echo ""
echo -e "${GREEN}${BOLD}✓ Aplicação online em: ${CYAN}https://$DOMAIN${NC}"
echo ""
echo "Informações importantes:"
echo ""
echo -e "  ${YELLOW}MongoDB Root Password:${NC}  $MONGO_PASS"
echo -e "  ${YELLOW}Redis Password:${NC}           $REDIS_PASS"
echo -e "  ${YELLOW}JWT Secret:${NC}              $JWT_SECRET"
echo ""
echo "⚠️  GUARDAR ESTAS SENHAS EM LOCAL SEGURO!"
echo ""
echo "Arquivo .env salvo em:"
echo "  $PROJECT_DIR/.env.production"
echo ""
echo "Próximas ações:"
echo ""
echo "  1. Validar acesso:"
echo "     curl https://$DOMAIN/api/health"
echo ""
echo "  2. Acompanhar logs:"
echo "     docker-compose -f $PROJECT_DIR/docker-compose.prod.yml logs -f backend"
echo ""
echo "  3. Ver status:"
echo "     docker-compose -f $PROJECT_DIR/docker-compose.prod.yml ps"
echo ""
echo "  4. Faturamento de SSL:"
echo "     certbot renew --dry-run"
echo ""
echo "Documentação:"
echo "  - DEPLOYMENT_GUIA_COMPLETO.md"
echo "  - DEPLOYMENT_CHECKLIST_RAPIDO.md"
echo ""

################################################################################
# SALVAR LOG
################################################################################

LOG_FILE="/root/deployment_$(date +%Y%m%d_%H%M%S).log"
echo "deployment. Log salvo em: $LOG_FILE"

cat > "$LOG_FILE" << EOF
=== Crypto Trade Hub - Auto Deployment Log ===
Data: $(date)
Domínio: $DOMAIN
Email: $EMAIL

Senhas Geradas:
- MongoDB Root: $MONGO_PASS
- Redis: $REDIS_PASS
- JWT Secret: $JWT_SECRET

Localização do Projeto: $PROJECT_DIR
Arquivo .env: $PROJECT_DIR/.env.production

Certificado SSL: /etc/letsencrypt/live/$DOMAIN/

Comandos úteis:
  docker-compose -f $PROJECT_DIR/docker-compose.prod.yml ps
  docker-compose -f $PROJECT_DIR/docker-compose.prod.yml logs -f backend
  docker-compose -f $PROJECT_DIR/docker-compose.prod.yml restart backend

Backup cron:
  0 2 * * * $PROJECT_DIR/backup.sh

Acompanhamento:
  curl https://$DOMAIN/api/health
  curl https://$DOMAIN

EOF

log_success "Log salvo em: $LOG_FILE"

echo ""
echo -e "${CYAN}━━━ Deployment Finalizado em $(date +%H:%M:%S) ━━━${NC}"
echo ""
