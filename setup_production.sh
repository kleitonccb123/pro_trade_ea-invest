#!/bin/bash
################################################################################
# Crypto Trade Hub — Production Environment Setup
################################################################################
#
# Este script prepara o ambiente de produção:
#   1. Gera TODOS os secrets criptográficos
#   2. Cria .env a partir do template .env.production
#   3. Configura SSL (Let's Encrypt OU Cloudflare)
#   4. Builda o frontend
#   5. Configura backup cron
#   6. Valida tudo antes de subir
#
# Uso:
#   chmod +x setup_production.sh
#   ./setup_production.sh
#
# PRÉ-REQUISITOS:
#   - Docker + Docker Compose instalados
#   - Python 3.8+ instalado (para gerar Fernet keys)
#   - Domínio apontando para este servidor (DNS A record)
#
################################################################################

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error()   { echo -e "${RED}[ERRO]${NC}  $1"; }
log_step()    { echo -e "\n${CYAN}━━━ $1 ━━━${NC}\n"; }

ENV_FILE=".env"
TEMPLATE_FILE=".env.production"

################################################################################
# 1. GERAR SECRETS
################################################################################

generate_secrets() {
    log_step "PASSO 1/6: Gerando secrets criptograficos"

    # JWT Secret (64 hex chars = 32 bytes)
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || \
                 python -c "import secrets; print(secrets.token_hex(32))")
    log_success "JWT_SECRET_KEY gerado (64 chars)"

    # Fernet keys (para criptografia de credenciais)
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
                     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    log_success "ENCRYPTION_KEY gerado (Fernet)"

    CREDENTIAL_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
                                python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    log_success "CREDENTIAL_ENCRYPTION_KEY gerado (Fernet)"

    STRATEGY_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
                              python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    log_success "STRATEGY_ENCRYPTION_KEY gerado (Fernet)"

    # Database passwords (32 hex chars)
    MONGO_ROOT_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || \
                          python -c "import secrets; print(secrets.token_hex(16))")
    log_success "MONGO_ROOT_PASSWORD gerado"

    REDIS_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || \
                     python -c "import secrets; print(secrets.token_hex(16))")
    log_success "REDIS_PASSWORD gerado"

    # Grafana password
    GRAFANA_PASSWORD=$(python3 -c "import secrets; print(secrets.token_hex(12))" 2>/dev/null || \
                       python -c "import secrets; print(secrets.token_hex(12))")
    log_success "GRAFANA_PASSWORD gerado"
}

################################################################################
# 2. CRIAR .env COM VALORES REAIS
################################################################################

create_env_file() {
    log_step "PASSO 2/6: Criando .env com secrets reais"

    if [ -f "$ENV_FILE" ]; then
        BACKUP_NAME=".env.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$ENV_FILE" "$BACKUP_NAME"
        log_warn ".env existente salvo como $BACKUP_NAME"
    fi

    # Perguntar dominio
    echo ""
    read -p "Dominio principal (ex: protradeeainvest.com): " DOMAIN
    DOMAIN="${DOMAIN:-protradeeainvest.com}"

    read -p "Subdominio da API (ex: api.protradeeainvest.com): " API_DOMAIN
    API_DOMAIN="${API_DOMAIN:-api.$DOMAIN}"

    # Google OAuth
    echo ""
    log_warn "Google OAuth e OBRIGATORIO para login."
    log_info "Crie em: https://console.cloud.google.com/apis/credentials"
    echo ""
    read -p "GOOGLE_CLIENT_ID (cole aqui): " GOOGLE_CLIENT_ID
    read -p "GOOGLE_CLIENT_SECRET (cole aqui): " GOOGLE_CLIENT_SECRET

    # SMTP (opcional)
    echo ""
    read -p "SMTP_USER (email, ou Enter para pular): " SMTP_USER
    read -p "SMTP_PASS (app password, ou Enter para pular): " SMTP_PASS

    # Payments (opcional)
    echo ""
    read -p "PERFECT_PAY_API_KEY (ou Enter para pular): " PERFECT_PAY_API_KEY
    read -p "PERFECT_PAY_POSTBACK_SECRET (ou Enter para pular): " PERFECT_PAY_POSTBACK_SECRET

    cat > "$ENV_FILE" << ENVEOF
# ============================================================
# CRYPTO TRADE HUB — PRODUCTION .env
# Gerado automaticamente em $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# ============================================================

# ── Mode ─────────────────────────────────────────────────────
APP_MODE=prod
DEBUG=false
LOG_LEVEL=info

# ── Database ─────────────────────────────────────────────────
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=${MONGO_ROOT_PASSWORD}
MONGO_DBNAME=crypto_trade_hub
DATABASE_URL=mongodb://admin:${MONGO_ROOT_PASSWORD}@mongodb:27017/crypto_trade_hub?authSource=admin

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
REDIS_PASSWORD=${REDIS_PASSWORD}

# ── Security (CRITICOS) ─────────────────────────────────────
JWT_SECRET_KEY=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
CREDENTIAL_ENCRYPTION_KEY=${CREDENTIAL_ENCRYPTION_KEY}
STRATEGY_ENCRYPTION_KEY=${STRATEGY_ENCRYPTION_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_MINUTES=10080
ALGORITHM=HS256

# ── CORS ─────────────────────────────────────────────────────
CORS_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}
ALLOWED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},${API_DOMAIN}

# ── Google OAuth ─────────────────────────────────────────────
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
GOOGLE_REDIRECT_URI=https://${API_DOMAIN}/api/auth/google/callback
FRONTEND_REDIRECT_URI=https://${DOMAIN}

# ── Frontend ─────────────────────────────────────────────────
VITE_API_BASE_URL=https://${API_DOMAIN}
VITE_WS_URL=wss://${API_DOMAIN}
VITE_KUCOIN_WS_URL=wss://ws-api-spot.kucoin.com
VITE_GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}

# ── KuCoin ───────────────────────────────────────────────────
KUCOIN_SANDBOX=false

# ── Payments ─────────────────────────────────────────────────
PERFECT_PAY_API_KEY=${PERFECT_PAY_API_KEY:-}
PERFECT_PAY_POSTBACK_SECRET=${PERFECT_PAY_POSTBACK_SECRET:-}
PERFECT_PAY_PLAN_MAP={"plan_basic":"basic","plan_pro":"pro","plan_enterprise":"enterprise"}

# ── Email ────────────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=${SMTP_USER:-}
SMTP_PASS=${SMTP_PASS:-}
SMTP_FROM=noreply@${DOMAIN}

# ── Monitoring ───────────────────────────────────────────────
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
SENTRY_DSN=

# ── Rate Limiting ────────────────────────────────────────────
RATE_LIMIT_USER=100
RATE_LIMIT_IP=30
RATE_LIMIT_WINDOW_SEC=60

# ── Risk Management ─────────────────────────────────────────
MAX_POSITION_SIZE_USD=100000
MAX_LOSS_PER_TRADE_USD=1000
MAX_DAILY_LOSS_USD=5000
MAX_LEVERAGE=10.0
MAX_OPEN_POSITIONS=10
ENVEOF

    chmod 600 "$ENV_FILE"
    log_success ".env criado com permissoes 600 (somente owner)"
}

################################################################################
# 3. SSL SETUP
################################################################################

setup_ssl() {
    log_step "PASSO 3/6: Configurando SSL"

    echo ""
    echo "Opcoes de SSL:"
    echo "  1) Cloudflare (RECOMENDADO — SSL automatico, sem cert local)"
    echo "  2) Let's Encrypt (certbot — certificado local)"
    echo "  3) Pular (ja tenho certificados em ./certs/)"
    echo ""
    read -p "Escolha [1/2/3]: " SSL_CHOICE

    case "${SSL_CHOICE}" in
        1)
            setup_cloudflare
            ;;
        2)
            setup_letsencrypt
            ;;
        3)
            if [ -f "./certs/cert.pem" ] && [ -f "./certs/key.pem" ]; then
                log_success "Certificados encontrados em ./certs/"
            else
                log_error "Certificados NAO encontrados em ./certs/"
                log_info "Copie cert.pem e key.pem para ./certs/ e rode novamente"
                exit 1
            fi
            ;;
        *)
            log_error "Opcao invalida"
            exit 1
            ;;
    esac
}

setup_cloudflare() {
    log_info "Configurando para Cloudflare..."
    log_info ""
    log_info "PASSOS NO CLOUDFLARE:"
    log_info "  1. Adicione seu dominio no Cloudflare"
    log_info "  2. Aponte DNS A para o IP deste servidor"
    log_info "  3. SSL/TLS > modo 'Full' (nao 'Full Strict')"
    log_info "  4. Em 'Origin Server', crie um certificado de origem"
    log_info "  5. Salve cert.pem e key.pem em ./certs/"
    log_info ""

    mkdir -p ./certs

    read -p "Ja configurou no Cloudflare? Os certs estao em ./certs/? [s/N]: " CF_READY
    if [[ "${CF_READY,,}" == "s" ]]; then
        if [ -f "./certs/cert.pem" ] && [ -f "./certs/key.pem" ]; then
            log_success "Certificados Cloudflare Origin encontrados"
        else
            log_warn "Certs nao encontrados. Usando self-signed temporario..."
            generate_self_signed_cert
        fi
    else
        log_warn "Gerando certificado self-signed temporario (substitua depois)"
        generate_self_signed_cert
    fi
}

setup_letsencrypt() {
    log_info "Configurando Let's Encrypt..."

    if ! command -v certbot &> /dev/null; then
        log_info "Instalando certbot..."
        apt-get update && apt-get install -y certbot 2>/dev/null || {
            log_error "Nao foi possivel instalar certbot. Instale manualmente."
            exit 1
        }
    fi

    # Parar nginx se estiver rodando (certbot precisa da porta 80)
    docker-compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true

    certbot certonly --standalone \
        -d "${DOMAIN}" \
        -d "www.${DOMAIN}" \
        -d "${API_DOMAIN}" \
        --non-interactive \
        --agree-tos \
        -m "admin@${DOMAIN}"

    # Copiar certs
    mkdir -p ./certs
    cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ./certs/cert.pem
    cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" ./certs/key.pem
    chmod 600 ./certs/key.pem

    # Configurar auto-renewal via cron
    CRON_RENEWAL="0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem $(pwd)/certs/cert.pem && cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem $(pwd)/certs/key.pem && docker-compose -f $(pwd)/docker-compose.prod.yml exec -T nginx nginx -s reload"
    (crontab -l 2>/dev/null | grep -v 'certbot renew'; echo "$CRON_RENEWAL") | crontab -

    log_success "Let's Encrypt configurado com auto-renewal"
}

generate_self_signed_cert() {
    mkdir -p ./certs
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ./certs/key.pem \
        -out ./certs/cert.pem \
        -subj "/CN=${DOMAIN:-localhost}" 2>/dev/null
    chmod 600 ./certs/key.pem
    log_warn "Certificado self-signed criado (APENAS para teste inicial)"
}

################################################################################
# 4. BUILD FRONTEND
################################################################################

build_frontend() {
    log_step "PASSO 4/6: Build do Frontend"

    if command -v npm &> /dev/null; then
        log_info "Buildando frontend com npm..."
        npm install --legacy-peer-deps 2>/dev/null || npm install
        VITE_API_BASE_URL="https://${API_DOMAIN:-api.protradeeainvest.com}" \
        VITE_GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
            npm run build
        log_success "Frontend buildado em ./dist/"
    elif command -v docker &> /dev/null; then
        log_info "Buildando frontend via Docker..."
        docker build \
            --build-arg VITE_API_URL="https://${API_DOMAIN:-api.protradeeainvest.com}" \
            --build-arg VITE_API_BASE_URL="https://${API_DOMAIN:-api.protradeeainvest.com}" \
            --build-arg VITE_GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
            -f Dockerfile.frontend \
            -t crypto-trade-frontend:latest \
            .
        log_success "Frontend image buildada"
    else
        log_warn "Nem npm nem docker encontrados. Build do frontend pulado."
        log_warn "Instale Node.js ou Docker e rode: npm run build"
    fi
}

################################################################################
# 5. CONFIGURAR BACKUP CRON
################################################################################

setup_backup_cron() {
    log_step "PASSO 5/6: Configurando backup automatico"

    BACKUP_SCRIPT="$(pwd)/backup_db.sh"
    PROJECT_DIR="$(pwd)"

    if [ ! -f "$BACKUP_SCRIPT" ]; then
        log_warn "backup_db.sh nao encontrado. Criando backup simples..."
        cat > "$BACKUP_SCRIPT" << 'BACKUPEOF'
#!/bin/bash
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
docker exec crypto-trade-mongodb mongodump \
    --username "${MONGO_ROOT_USER:-admin}" \
    --password "${MONGO_ROOT_PASSWORD}" \
    --authenticationDatabase admin \
    --out "/tmp/backup" 2>/dev/null
docker cp crypto-trade-mongodb:/tmp/backup "$BACKUP_DIR"
docker exec crypto-trade-mongodb rm -rf /tmp/backup
# Manter ultimos 30 dias
find ./backups -type d -mtime +30 -exec rm -rf {} + 2>/dev/null
BACKUPEOF
        chmod +x "$BACKUP_SCRIPT"
    fi

    # Adicionar cron job (diario as 02:00)
    CRON_BACKUP="0 2 * * * cd ${PROJECT_DIR} && source .env && bash backup_db.sh >> ${PROJECT_DIR}/logs/backup.log 2>&1"
    (crontab -l 2>/dev/null | grep -v 'backup_db.sh'; echo "$CRON_BACKUP") | crontab -

    log_success "Backup diario agendado (02:00 UTC)"
}

################################################################################
# 6. VALIDACAO FINAL
################################################################################

validate_setup() {
    log_step "PASSO 6/6: Validacao final"

    ERRORS=0

    # Verificar .env
    if [ -f "$ENV_FILE" ]; then
        log_success ".env existe"
    else
        log_error ".env NAO encontrado"
        ERRORS=$((ERRORS+1))
    fi

    # Verificar secrets nao sao placeholder
    check_not_placeholder() {
        VALUE=$(grep "^$1=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2-)
        if [ -z "$VALUE" ] || echo "$VALUE" | grep -qE '<|changeme|your-secret'; then
            log_error "$1 esta vazio ou e placeholder"
            ERRORS=$((ERRORS+1))
        else
            log_success "$1 configurado"
        fi
    }

    check_not_placeholder "JWT_SECRET_KEY"
    check_not_placeholder "ENCRYPTION_KEY"
    check_not_placeholder "CREDENTIAL_ENCRYPTION_KEY"
    check_not_placeholder "MONGO_ROOT_PASSWORD"
    check_not_placeholder "REDIS_PASSWORD"
    check_not_placeholder "GRAFANA_PASSWORD"

    # Verificar Google OAuth
    GOOG_ID=$(grep "^GOOGLE_CLIENT_ID=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2-)
    if [ -z "$GOOG_ID" ] || echo "$GOOG_ID" | grep -qE '<|your_client'; then
        log_warn "GOOGLE_CLIENT_ID nao configurado (login Google nao funcionara)"
    else
        log_success "GOOGLE_CLIENT_ID configurado"
    fi

    # Verificar SSL certs
    if [ -f "./certs/cert.pem" ] && [ -f "./certs/key.pem" ]; then
        log_success "Certificados SSL encontrados"
    else
        log_error "Certificados SSL NAO encontrados em ./certs/"
        ERRORS=$((ERRORS+1))
    fi

    # Verificar frontend build
    if [ -d "./dist" ] || [ -d "./frontend/dist" ]; then
        log_success "Frontend buildado"
    else
        log_warn "Frontend nao buildado (npm run build)"
    fi

    # Verificar permissoes
    PERM=$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%Lp' "$ENV_FILE" 2>/dev/null)
    if [ "$PERM" = "600" ]; then
        log_success ".env com permissoes corretas (600)"
    else
        log_warn ".env com permissoes $PERM (recomendado: 600)"
    fi

    echo ""
    if [ $ERRORS -eq 0 ]; then
        log_success "=========================================="
        log_success "  SETUP COMPLETO! Pronto para deploy."
        log_success "=========================================="
        echo ""
        log_info "Proximo passo:"
        log_info "  ./deploy.sh"
        echo ""
    else
        log_error "=========================================="
        log_error "  $ERRORS ERROS encontrados. Corrija antes de deploy."
        log_error "=========================================="
        exit 1
    fi
}

################################################################################
# MAIN
################################################################################

main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   Crypto Trade Hub — Production Setup           ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    # Verificar pre-requisitos
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        log_error "Python nao encontrado. Instale Python 3.8+"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "Docker nao encontrado. Instale Docker primeiro."
        exit 1
    fi

    # Verificar se tem cryptography instalada
    python3 -c "from cryptography.fernet import Fernet" 2>/dev/null || \
    python -c "from cryptography.fernet import Fernet" 2>/dev/null || {
        log_warn "Pacote 'cryptography' nao encontrado. Instalando..."
        pip3 install cryptography 2>/dev/null || pip install cryptography
    }

    generate_secrets
    create_env_file
    setup_ssl
    build_frontend
    setup_backup_cron
    validate_setup
}

main "$@"
