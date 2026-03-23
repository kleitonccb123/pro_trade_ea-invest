#!/bin/bash

####################################################################
# Crypto Trade Hub - Automated Database Backup Script
# Purpose: Daily backup of MongoDB and Redis with encryption
# Usage: ./backup_db.sh [backup|restore|schedule]
####################################################################

# MongoDB Atlas + TLS Configuration
# ===================================
# For MongoDB Atlas cloud hosting, set these environment variables:
#
# Local MongoDB (default - no TLS):
#   MONGO_HOST=localhost
#   MONGO_PORT=27017
#
# MongoDB Atlas with TLS (recommended):
#   MONGO_USE_TLS=true
#   MONGO_URI="mongodb+srv://user:password@cluster.mongodb.net/database?retryWrites=true"
#   # OR
#   MONGO_HOST=cluster-xyz.mongodb.net
#   MONGO_PORT=27017
#   MONGO_USE_TLS=true
#   MONGO_TLS_CA_FILE=/path/to/ca.pem  (optional)
#
# Example .env.production:
#   DATABASE_URL="mongodb+srv://admin:PASSWORD@crypto-cluster.mongodb.net/crypto_trade_hub?retryWrites=true&w=majority&tls=true"
#   MONGO_USE_TLS=true
#   MONGO_URI="${DATABASE_URL}"
####################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BACKUP_DIR="${PROJECT_ROOT}/backups"
BACKUP_RETENTION_DAYS=30
LOG_FILE="${BACKUP_DIR}/backup.log"

# Database credentials (from .env.production)
MONGO_HOST="${MONGO_HOST:-localhost}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_USER="${MONGO_INITDB_ROOT_USERNAME:-admin}"
MONGO_PASSWORD="${MONGO_INITDB_ROOT_PASSWORD:-changeme}"
MONGO_DB="${MONGO_DBNAME:-crypto_trade_hub}"

# MongoDB Atlas TLS/SSL Configuration
# Set to "true" if connecting to MongoDB Atlas
MONGO_USE_TLS="${MONGO_USE_TLS:-false}"
MONGO_TLS_CA_FILE="${MONGO_TLS_CA_FILE:-}"  # Optional: path to CA certificate
MONGO_TLS_ALLOW_INVALID_HOSTNAMES="${MONGO_TLS_ALLOW_INVALID_HOSTNAMES:-false}"
MONGO_URI="${MONGO_URI:-}"  # Optional: full connection string (overrides host/port)

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-changeme}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# ============================================================================
# BACKUP FUNCTION
# ============================================================================

backup() {
    log "INFO" "${BLUE}Starting backup procedure...${NC}"
    
    local backup_timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_name="backup_${backup_timestamp}"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    mkdir -p "${backup_path}"
    
    # ---- MongoDB Backup ----
    log "INFO" "${BLUE}Backing up MongoDB...${NC}"
    
    if ! command -v mongodump &> /dev/null; then
        log "ERROR" "${RED}mongodump not found. Install MongoDB tools.${NC}"
        return 1
    fi
    
    # Build mongodump command with TLS support
    local mongodump_cmd="mongodump"
    
    if [ -n "${MONGO_URI}" ]; then
        # Use full connection string if provided (for MongoDB Atlas)
        mongodump_cmd="${mongodump_cmd} --uri=\"${MONGO_URI}\""
        log "INFO" "${BLUE}Using MongoDB URI connection string${NC}"
    else
        # Use host/port parameters
        mongodump_cmd="${mongodump_cmd} --host=\"${MONGO_HOST}\" --port=\"${MONGO_PORT}\""
    fi
    
    # Add authentication
    mongodump_cmd="${mongodump_cmd} --username=\"${MONGO_USER}\" --password=\"${MONGO_PASSWORD}\" --authenticationDatabase=\"admin\""
    
    # Add TLS parameters if connecting to MongoDB Atlas
    if [ "${MONGO_USE_TLS}" = "true" ]; then
        mongodump_cmd="${mongodump_cmd} --tls"
        log "INFO" "${BLUE}TLS enabled for MongoDB connection${NC}"
        
        # Add CA certificate if provided
        if [ -n "${MONGO_TLS_CA_FILE}" ] && [ -f "${MONGO_TLS_CA_FILE}" ]; then
            mongodump_cmd="${mongodump_cmd} --tlsCAFile=\"${MONGO_TLS_CA_FILE}\""
            log "INFO" "${BLUE}Using TLS CA certificate: ${MONGO_TLS_CA_FILE}${NC}"
        else
            # Try to use system CA bundle (certifi for Python compatibility)
            if [ -f "/etc/ssl/certs/ca-certificates.crt" ]; then
                mongodump_cmd="${mongodump_cmd} --tlsCAFile=/etc/ssl/certs/ca-certificates.crt"
            elif [ -f "/etc/ssl/certs/ca-bundle.crt" ]; then
                mongodump_cmd="${mongodump_cmd} --tlsCAFile=/etc/ssl/certs/ca-bundle.crt"
            fi
        fi
        
        # Allow invalid hostnames if specified (sometimes needed for MongoDB Atlas)
        if [ "${MONGO_TLS_ALLOW_INVALID_HOSTNAMES}" = "true" ]; then
            mongodump_cmd="${mongodump_cmd} --tlsAllowInvalidHostnames"
            log "WARNING" "${YELLOW}TLS hostname validation disabled${NC}"
        fi
    fi
    
    # Add database selection
    mongodump_cmd="${mongodump_cmd} --db=\"${MONGO_DB}\" --out=\"${backup_path}/mongodb\""
    
    # Execute mongodump
    log "INFO" "${BLUE}Executing: mongodump (TLS: ${MONGO_USE_TLS})${NC}"
    if eval "${mongodump_cmd} 2>&1 | tee -a ${LOG_FILE}"; then
        log "INFO" "${GREEN}✓ MongoDB backup completed${NC}"
    else
        log "ERROR" "${RED}MongoDB backup failed!${NC}"
        return 1
    fi
    
    # ---- Redis Backup ----
    log "INFO" "${BLUE}Backing up Redis...${NC}"
    
    if ! command -v redis-cli &> /dev/null; then
        log "ERROR" "${RED}redis-cli not found. Install Redis.${NC}"
        return 1
    fi
    
    # Trigger Redis save
    if redis-cli \
        -h "${REDIS_HOST}" \
        -p "${REDIS_PORT}" \
        -a "${REDIS_PASSWORD}" \
        BGSAVE 2>&1 | tee -a "${LOG_FILE}"; then
        
        # Wait for save to complete (max 30 seconds)
        local wait_count=0
        while [ $wait_count -lt 30 ]; do
            local save_status=$(redis-cli \
                -h "${REDIS_HOST}" \
                -p "${REDIS_PORT}" \
                -a "${REDIS_PASSWORD}" \
                LASTSAVE)
            
            if [ ! -z "$save_status" ]; then
                break
            fi
            
            sleep 1
            ((wait_count++))
        done
        
        # Copy dump.rdb
        mkdir -p "${backup_path}/redis"
        
        if docker-compose -f docker-compose.prod.yml cp redis:/data/dump.rdb \
            "${backup_path}/redis/dump.rdb" 2>&1 | tee -a "${LOG_FILE}"; then
            log "INFO" "${GREEN}✓ Redis backup completed${NC}"
        else
            log "WARNING" "${YELLOW}Redis dump might not be accessible via docker${NC}"
        fi
    else
        log "ERROR" "${RED}Redis backup failed!${NC}"
        return 1
    fi
    
    # ---- Create metadata file ----
    cat > "${backup_path}/metadata.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "version": "1.0",
  "database": "${MONGO_DB}",
  "mongodb_host": "${MONGO_HOST}:${MONGO_PORT}",
  "redis_host": "${REDIS_HOST}:${REDIS_PORT}",
  "backup_size": "$(du -sh ${backup_path} | cut -f1)",
  "compressed": false
}
EOF
    
    log "INFO" "${GREEN}✓ Metadata file created${NC}"
    
    # ---- Compress backup ----
    log "INFO" "${BLUE}Compressing backup...${NC}"
    
    if tar -czf "${backup_path}.tar.gz" -C "${BACKUP_DIR}" "${backup_name}" \
        2>&1 | tee -a "${LOG_FILE}"; then
        
        # Remove uncompressed backup
        rm -rf "${backup_path}"
        log "INFO" "${GREEN}✓ Backup compressed: ${backup_name}.tar.gz${NC}"
        log "INFO" "${GREEN}Backup Size: $(du -sh ${backup_path}.tar.gz | cut -f1)${NC}"
    else
        log "ERROR" "${RED}Compression failed!${NC}"
        return 1
    fi
    
    # ---- Clean old backups ----
    log "INFO" "${BLUE}Cleaning old backups (>= ${BACKUP_RETENTION_DAYS} days)...${NC}"
    
    find "${BACKUP_DIR}" -type f -name "backup_*.tar.gz" -mtime +${BACKUP_RETENTION_DAYS} -delete
    log "INFO" "${GREEN}✓ Cleanup completed${NC}"
    
    log "INFO" "${GREEN}✓ Backup procedure completed successfully!${NC}"
    return 0
}

# ============================================================================
# RESTORE FUNCTION
# ============================================================================

restore() {
    local backup_file=$1
    
    if [ -z "$backup_file" ]; then
        log "ERROR" "${RED}Backup file not specified${NC}"
        echo "Usage: ./backup_db.sh restore <backup_file.tar.gz>"
        return 1
    fi
    
    if [ ! -f "${backup_file}" ]; then
        log "ERROR" "${RED}Backup file not found: ${backup_file}${NC}"
        return 1
    fi
    
    log "INFO" "${YELLOW}WARNING: This will overwrite existing data!${NC}"
    read -p "Are you sure you want to restore? (yes/no): " -r confirm
    
    if [ "$confirm" != "yes" ]; then
        log "INFO" "Restore cancelled"
        return 0
    fi
    
    log "INFO" "${BLUE}Starting restore procedure...${NC}"
    
    local restore_dir="${BACKUP_DIR}/restore_tmp"
    mkdir -p "${restore_dir}"
    
    # Extract backup
    if tar -xzf "${backup_file}" -C "${restore_dir}" 2>&1 | tee -a "${LOG_FILE}"; then
        log "INFO" "${GREEN}✓ Backup extracted${NC}"
    else
        log "ERROR" "${RED}Extraction failed!${NC}"
        rm -rf "${restore_dir}"
        return 1
    fi
    
    # Find extracted backup directory
    local extracted_backup=$(find "${restore_dir}" -maxdepth 1 -type d -name "backup_*" | head -1)
    
    if [ -z "$extracted_backup" ]; then
        log "ERROR" "${RED}Could not find extracted backup${NC}"
        rm -rf "${restore_dir}"
        return 1
    fi
    
    # Restore MongoDB
    log "INFO" "${BLUE}Restoring MongoDB...${NC}"
    
    if mongorestore \
        --host="${MONGO_HOST}" \
        --port="${MONGO_PORT}" \
        --username="${MONGO_USER}" \
        --password="${MONGO_PASSWORD}" \
        --authenticationDatabase="admin" \
        --db="${MONGO_DB}" \
        --drop \
        "${extracted_backup}/mongodb/${MONGO_DB}" \
        2>&1 | tee -a "${LOG_FILE}"; then
        log "INFO" "${GREEN}✓ MongoDB restored${NC}"
    else
        log "ERROR" "${RED}MongoDB restore failed!${NC}"
        rm -rf "${restore_dir}"
        return 1
    fi
    
    # Restore Redis
    log "INFO" "${BLUE}Restoring Redis...${NC}"
    
    if [ -f "${extracted_backup}/redis/dump.rdb" ]; then
        log "WARNING" "${YELLOW}Manual Redis restore required:${NC}"
        echo "1. Stop Redis: docker-compose -f docker-compose.prod.yml stop redis"
        echo "2. Copy dump: docker cp ${extracted_backup}/redis/dump.rdb redis:/data/"
        echo "3. Start Redis: docker-compose -f docker-compose.prod.yml start redis"
    else
        log "WARNING" "${YELLOW}Redis dump not found in backup${NC}"
    fi
    
    # Cleanup
    rm -rf "${restore_dir}"
    log "INFO" "${GREEN}✓ Restore procedure completed${NC}"
    return 0
}

# ============================================================================
# SCHEDULE FUNCTION (Linux Cron)
# ============================================================================

schedule() {
    log "INFO" "${BLUE}Setting up automated backups via cron...${NC}"
    
    local cron_job="0 2 * * * cd ${PROJECT_ROOT} && ./backup_db.sh backup >> ${LOG_FILE} 2>&1"
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "backup_db.sh backup"; then
        log "INFO" "${YELLOW}Cron job already scheduled${NC}"
        return 0
    fi
    
    # Add cron job (daily at 2 AM)
    (crontab -l 2>/dev/null || true; echo "$cron_job") | crontab -
    
    log "INFO" "${GREEN}✓ Cron job scheduled (Daily at 2:00 AM)${NC}"
    log "INFO" "Cron entry: $cron_job"
    return 0
}

# ============================================================================
# INFO FUNCTION
# ============================================================================

info() {
    log "INFO" "${BLUE}Backup Status${NC}"
    echo ""
    echo -e "${BLUE}Configuration:${NC}"
    echo "  MongoDB: ${MONGO_HOST}:${MONGO_PORT}/${MONGO_DB}"
    echo "  Redis: ${REDIS_HOST}:${REDIS_PORT}"
    echo "  Backup Dir: ${BACKUP_DIR}"
    echo "  Retention: ${BACKUP_RETENTION_DAYS} days"
    echo ""
    
    if [ -d "${BACKUP_DIR}" ]; then
        echo -e "${BLUE}Recent Backups:${NC}"
        ls -lhS "${BACKUP_DIR}"/backup_*.tar.gz 2>/dev/null | tail -5 || echo "No backups found"
    else
        echo -e "${YELLOW}No backups directory found${NC}"
    fi
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    local command=${1:-backup}
    
    case $command in
        backup)
            backup
            ;;
        restore)
            restore "$2"
            ;;
        schedule)
            schedule
            ;;
        info)
            info
            ;;
        *)
            echo "Usage: ./backup_db.sh {backup|restore|schedule|info}"
            echo ""
            echo "Commands:"
            echo "  backup                      - Create a backup now"
            echo "  restore <backup_file.tar.gz> - Restore from backup"
            echo "  schedule                    - Setup automated daily backups"
            echo "  info                        - Show backup status"
            exit 1
            ;;
    esac
}

main "$@"
