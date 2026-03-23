#!/bin/bash
################################################################################
# Crypto Trade Hub - Production Deployment Script
################################################################################
#
# This script automates the production deployment:
# 1. Validates environment configuration
# 2. Runs database migration for Activation Credits System
# 3. Builds and starts Docker containers
# 4. Initializes MongoDB replica set
# 5. Performs health checks
# 6. Cleans up old logs
#
# Usage:
#   ./deploy.sh [clean|stop|logs|status]
#
# Examples:
#   ./deploy.sh                  # Full deployment
#   ./deploy.sh clean            # Stop and remove containers/volumes
#   ./deploy.sh stop             # Stop running containers
#   ./deploy.sh logs             # Show logs from all services
#   ./deploy.sh status           # Check service status
#
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
PROJECT_NAME="crypto-trade"
LOG_DIR="./logs"
BACKUP_DIR="./backups"

################################################################################
# Utility Functions
################################################################################

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        log_error ".env nao encontrado. Rode ./setup_production.sh primeiro"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

validate_secrets() {
    log_info "Validating production secrets..."
    
    MISSING=0
    REQUIRED_VARS="JWT_SECRET_KEY ENCRYPTION_KEY CREDENTIAL_ENCRYPTION_KEY MONGO_ROOT_PASSWORD REDIS_PASSWORD GRAFANA_PASSWORD"
    
    for VAR in $REQUIRED_VARS; do
        VALUE=$(grep "^${VAR}=" .env 2>/dev/null | cut -d'=' -f2-)
        if [ -z "$VALUE" ] || echo "$VALUE" | grep -qE '<|changeme|your-secret|placeholder'; then
            log_error "  $VAR esta vazio ou e placeholder"
            MISSING=$((MISSING+1))
        fi
    done
    
    if [ $MISSING -gt 0 ]; then
        log_error "$MISSING secrets faltando. Rode ./setup_production.sh"
        exit 1
    fi
    
    log_success "All secrets validated"
}

create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "./certs"
    log_success "Directories created"
}

load_environment() {
    log_info "Loading environment configuration..."
    
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
        log_success "Environment loaded from .env"
    else
        log_error ".env not found. Rode ./setup_production.sh"
        exit 1
    fi
}

backup_database() {
    log_info "Creating database backup..."
    
    BACKUP_NAME="mongo_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
    
    docker-compose -f "$COMPOSE_FILE" exec -T mongodb mongodump \
        --username "${MONGO_ROOT_USER:-admin}" \
        --password "${MONGO_ROOT_PASSWORD:-changeme}" \
        --authenticationDatabase admin \
        --out "/data/$BACKUP_NAME" 2>/dev/null || true
    
    log_success "Database backup created: $BACKUP_NAME"
}

run_migration() {
    log_info "Running Activation Credits System migration..."
    
    # Wait for MongoDB to be ready
    sleep 5
    
    docker-compose -f "$COMPOSE_FILE" exec -T backend python scripts/migrate_activation_system.py
    
    if [ $? -eq 0 ]; then
        log_success "Migration completed successfully"
    else
        log_warning "Migration encountered issues. Check logs."
    fi
}

initialize_mongodb() {
    log_info "Initializing MongoDB replica set..."
    
    # Give MongoDB time to start
    sleep 10
    
    docker-compose -f "$COMPOSE_FILE" exec -T mongodb mongosh \
        --username "${MONGO_ROOT_USER:-admin}" \
        --password "${MONGO_ROOT_PASSWORD:-changeme}" \
        --authenticationDatabase admin \
        --eval "rs.status()" 2>/dev/null | grep -q "rs0" && log_success "Replica set already initialized" || {
        docker-compose -f "$COMPOSE_FILE" exec -T mongodb mongosh \
            --username "${MONGO_ROOT_USER:-admin}" \
            --password "${MONGO_ROOT_PASSWORD:-changeme}" \
            --authenticationDatabase admin \
            --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"
        log_success "Replica set initialized"
    }
}

health_check() {
    log_info "Performing health checks..."
    
    # Check MongoDB
    log_info "  Checking MongoDB..."
    docker-compose -f "$COMPOSE_FILE" exec -T mongodb mongosh \
        --username "${MONGO_ROOT_USER:-admin}" \
        --password "${MONGO_ROOT_PASSWORD:-changeme}" \
        --authenticationDatabase admin \
        --eval "db.adminCommand('ping')" > /dev/null 2>&1 && log_success "    MongoDB healthy" || log_error "    MongoDB unhealthy"
    
    # Check Redis
    log_info "  Checking Redis..."
    docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1 && log_success "    Redis healthy" || log_error "    Redis unhealthy"
    
    # Check Backend
    log_info "  Checking Backend..."
    for i in {1..30}; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "    Backend healthy"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "    Backend unhealthy"
        fi
        sleep 2
    done
    
    # Check Nginx
    log_info "  Checking Nginx..."
    for i in {1..20}; do
        if curl -f http://localhost/health > /dev/null 2>&1; then
            log_success "    Nginx healthy"
            break
        fi
        if [ $i -eq 20 ]; then
            log_error "    Nginx unhealthy"
        fi
        sleep 2
    done
}

clean_logs() {
    log_info "Cleaning old logs..."
    
    # Keep only last 7 days of logs
    if [ -d "$LOG_DIR" ]; then
        find "$LOG_DIR" -type f -mtime +7 -delete
        log_success "Old logs cleaned"
    fi
}

setup_backup_cron() {
    log_info "Setting up daily backup cron..."
    
    PROJECT_DIR="$(pwd)"
    CRON_BACKUP="0 2 * * * cd ${PROJECT_DIR} && bash backup_db.sh >> ${PROJECT_DIR}/logs/backup.log 2>&1"
    
    # Remove old entry (if exists) and add new one
    (crontab -l 2>/dev/null | grep -v 'backup_db.sh'; echo "$CRON_BACKUP") | crontab -
    
    log_success "Daily backup scheduled at 02:00 UTC"
}

deploy() {
    log_info "Starting deployment..."
    
    # Check prerequisites
    check_prerequisites
    
    # Load environment
    load_environment
    
    # Validate secrets
    validate_secrets
    
    # Create directories
    create_directories
    
    # Build and start containers
    log_info "Building Docker images..."
    docker-compose -f "$COMPOSE_FILE" build --no-cache backend
    log_success "Docker images built"
    
    log_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    log_success "Services started"
    
    # Initialize MongoDB
    initialize_mongodb
    
    # Run migration (if containers are ready)
    sleep 15
    run_migration
    
    # Health checks
    health_check
    
    # Setup backup cron
    setup_backup_cron
    
    # Clean logs
    clean_logs
    
    log_success "🎉 Deployment completed successfully!"
    log_info "Services are running at:"
    log_info "  Frontend: https://yourdomain.com"
    log_info "  Backend API: https://yourdomain.com/api/v1"
    log_info "  MongoDB: localhost:27017 (local only)"
    log_info "  Redis: localhost:6379 (local only)"
}

stop_services() {
    log_info "Stopping services..."
    docker-compose -f "$COMPOSE_FILE" down
    log_success "Services stopped"
}

clean_all() {
    log_info "Cleaning up (removing containers and volumes)..."
    docker-compose -f "$COMPOSE_FILE" down -v
    log_success "Cleanup completed. All data removed!"
}

show_logs() {
    SERVICE=${1:-}
    if [ -n "$SERVICE" ]; then
        docker-compose -f "$COMPOSE_FILE" logs -f "$SERVICE"
    else
        docker-compose -f "$COMPOSE_FILE" logs -f
    fi
}

show_status() {
    log_info "Service status:"
    docker-compose -f "$COMPOSE_FILE" ps
    log_info ""
    log_info "System resource usage:"
    docker stats --no-stream
}

################################################################################
# Main Script
################################################################################

case "${1:-}" in
    "clean")
        clean_all
        ;;
    "stop")
        stop_services
        ;;
    "logs")
        show_logs "$2"
        ;;
    "status")
        show_status
        ;;
    "")
        deploy
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        echo "Usage: $0 [clean|stop|logs|status]"
        echo ""
        echo "Commands:"
        echo "  (no args)     Full deployment"
        echo "  clean         Stop and remove all containers/volumes"
        echo "  stop          Stop running containers"
        echo "  logs [svc]    Show logs (optional: service name)"
        echo "  status        Show service status"
        exit 1
        ;;
esac
