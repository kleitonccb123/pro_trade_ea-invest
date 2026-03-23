#!/bin/bash

####################################################################
# Test MongoDB Atlas Backup with TLS/SSL
# 
# This script validates that backup_db.sh can successfully connect
# to MongoDB Atlas with TLS and perform a backup.
# 
# Prerequisites:
# - mongodump command installed
# - MongoDB URI or connection parameters in .env or environment
# - Network access to MongoDB Atlas cluster
# 
# Usage:
# chmod +x test_atlas_backup.sh
# ./test_atlas_backup.sh
####################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Source environment variables
if [ -f "$PROJECT_ROOT/.env.production" ]; then
    export $(cat "$PROJECT_ROOT/.env.production" | grep -v '^#' | xargs)
fi

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${BLUE}[${timestamp}] [INFO]${NC} $message" ;;
        SUCCESS) echo -e "${GREEN}[${timestamp}] [✓]${NC} $message" ;;
        ERROR) echo -e "${RED}[${timestamp}] [✗]${NC} $message" ;;
        WARN) echo -e "${YELLOW}[${timestamp}] [!]${NC} $message" ;;
    esac
}

####################################################################
# TEST 1: Check mongodump installation
####################################################################
test_mongodump_installed() {
    log "INFO" "TEST 1: Checking mongodump installation..."
    
    if command -v mongodump &> /dev/null; then
        local version=$(mongodump --version | head -1)
        log "SUCCESS" "mongodump is installed: $version"
        return 0
    else
        log "ERROR" "mongodump not found. Install MongoDB Database Tools:"
        log "WARN" "  Ubuntu/Debian: apt-get install mongodb-database-tools"
        log "WARN" "  macOS: brew install mongodb-database-tools"
        log "WARN" "  See: https://docs.mongodb.com/database-tools/installation/installation/"
        return 1
    fi
}

####################################################################
# TEST 2: Check environment variables
####################################################################
test_environment_vars() {
    log "INFO" "TEST 2: Checking environment variables..."
    
    local errors=0
    
    # Check for MongoDB connection info
    if [ -z "${MONGO_URI:-}" ] && [ -z "${MONGO_HOST:-}" ]; then
        log "ERROR" "Neither MONGO_URI nor MONGO_HOST is set"
        errors=$((errors + 1))
    fi
    
    if [ -z "${MONGO_USER:-}" ]; then
        log "ERROR" "MONGO_USER not set"
        errors=$((errors + 1))
    fi
    
    if [ -z "${MONGO_PASSWORD:-}" ]; then
        log "ERROR" "MONGO_PASSWORD not set"
        errors=$((errors + 1))
    fi
    
    # Display what's configured
    if [ -n "${MONGO_URI:-}" ]; then
        log "INFO" "MONGO_URI is configured (for MongoDB Atlas)"
    else
        log "INFO" "Using MONGO_HOST=${MONGO_HOST:-localhost} MONGO_PORT=${MONGO_PORT:-27017}"
    fi
    
    if [ "${MONGO_USE_TLS:-false}" = "true" ]; then
        log "SUCCESS" "TLS is enabled"
        
        if [ -n "${MONGO_TLS_CA_FILE:-}" ]; then
            if [ -f "${MONGO_TLS_CA_FILE}" ]; then
                log "SUCCESS" "TLS CA file exists: ${MONGO_TLS_CA_FILE}"
            else
                log "ERROR" "TLS CA file not found: ${MONGO_TLS_CA_FILE}"
                errors=$((errors + 1))
            fi
        else
            log "WARN" "No TLS CA file specified, will use system CA bundle"
        fi
    else
        log "WARN" "TLS is disabled (MONGO_USE_TLS=${MONGO_USE_TLS:-false})"
    fi
    
    return $errors
}

####################################################################
# TEST 3: Test MongoDB connection
####################################################################
test_mongodb_connection() {
    log "INFO" "TEST 3: Testing MongoDB connection..."
    
    local mongosh_cmd="mongosh"
    local connect_string=""
    
    if [ -n "${MONGO_URI:-}" ]; then
        connect_string="${MONGO_URI}"
    else
        connect_string="mongodb://${MONGO_USER}:${MONGO_PASSWORD}@${MONGO_HOST}:${MONGO_PORT}/admin"
    fi
    
    # Add TLS if enabled
    if [ "${MONGO_USE_TLS:-false}" = "true" ]; then
        if [[ ! "$connect_string" == *"?"* ]]; then
            connect_string="${connect_string}?"
        else
            connect_string="${connect_string}&"
        fi
        connect_string="${connect_string}tls=true"
        
        if [ -n "${MONGO_TLS_CA_FILE:-}" ] && [ -f "${MONGO_TLS_CA_FILE}" ]; then
            connect_string="${connect_string}&tlsCAFile=${MONGO_TLS_CA_FILE}"
        fi
    fi
    
    # Simple connectivity test
    log "INFO" "Attempting connection to MongoDB..."
    
    if timeout 10 $mongosh_cmd "$connect_string" --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        log "SUCCESS" "MongoDB connection successful!"
        return 0
    else
        log "ERROR" "Failed to connect to MongoDB"
        log "WARN" "This could be due to:"
        log "WARN" "  1. Invalid credentials"
        log "WARN" "  2. Network connectivity issues"
        log "WARN" "  3. TLS configuration problems"
        log "WARN" "  4. IP whitelist restrictions (check MongoDB Atlas)"
        return 1
    fi
}

####################################################################
# TEST 4: Test actual backup
####################################################################
test_backup() {
    log "INFO" "TEST 4: Testing actual MongoDB backup..."
    
    local test_backup_dir="${PROJECT_ROOT}/.test_backup"
    mkdir -p "$test_backup_dir"
    
    local mongodump_cmd="mongodump"
    
    if [ -n "${MONGO_URI:-}" ]; then
        mongodump_cmd="${mongodump_cmd} --uri=\"${MONGO_URI}\""
    else
        mongodump_cmd="${mongodump_cmd} --host=\"${MONGO_HOST:-localhost}\" --port=\"${MONGO_PORT:-27017}\""
    fi
    
    mongodump_cmd="${mongodump_cmd} --username=\"${MONGO_USER}\" --password=\"${MONGO_PASSWORD}\" --authenticationDatabase=\"admin\""
    
    if [ "${MONGO_USE_TLS:-false}" = "true" ]; then
        mongodump_cmd="${mongodump_cmd} --tls"
        
        if [ -n "${MONGO_TLS_CA_FILE:-}" ] && [ -f "${MONGO_TLS_CA_FILE}" ]; then
            mongodump_cmd="${mongodump_cmd} --tlsCAFile=\"${MONGO_TLS_CA_FILE}\""
        fi
        
        if [ "${MONGO_TLS_ALLOW_INVALID_HOSTNAMES:-false}" = "true" ]; then
            mongodump_cmd="${mongodump_cmd} --tlsAllowInvalidHostnames"
        fi
    fi
    
    mongodump_cmd="${mongodump_cmd} --db=\"${MONGO_DB:-crypto_trade_hub}\" --out=\"${test_backup_dir}\""
    
    log "INFO" "Running: mongodump (with TLS=${MONGO_USE_TLS:-false})"
    
    if eval "$mongodump_cmd" > /dev/null 2>&1; then
        log "SUCCESS" "Backup completed successfully!"
        
        # Check if files were created
        local file_count=$(find "$test_backup_dir" -type f 2>/dev/null | wc -l)
        log "INFO" "Backup files created: $file_count"
        
        # Show backup size
        local backup_size=$(du -sh "$test_backup_dir" | awk '{print $1}')
        log "INFO" "Backup size: $backup_size"
        
        # Cleanup
        rm -rf "$test_backup_dir"
        
        return 0
    else
        log "ERROR" "Backup failed. Check credentials and network connectivity."
        rm -rf "$test_backup_dir"
        return 1
    fi
}

####################################################################
# TEST 5: Verify backup_db.sh script
####################################################################
test_backup_script() {
    log "INFO" "TEST 5: Verifying backup_db.sh script..."
    
    if [ -f "${PROJECT_ROOT}/backup_db.sh" ]; then
        log "SUCCESS" "backup_db.sh found"
        
        if grep -q "MONGO_USE_TLS" "${PROJECT_ROOT}/backup_db.sh"; then
            log "SUCCESS" "backup_db.sh has TLS support"
            return 0
        else
            log "WARN" "backup_db.sh does not appear to have TLS support"
            return 1
        fi
    else
        log "ERROR" "backup_db.sh not found"
        return 1
    fi
}

####################################################################
# MAIN TEST RUNNER
####################################################################
main() {
    log "INFO" "======================================"
    log "INFO" "MongoDB Atlas Backup Test Suite"
    log "INFO" "======================================"
    
    local total_tests=5
    local passed=0
    
    if test_mongodump_installed; then passed=$((passed + 1)); fi
    if test_environment_vars; then passed=$((passed + 1)); fi
    if test_mongodb_connection; then passed=$((passed + 1)); fi
    if test_backup; then passed=$((passed + 1)); fi
    if test_backup_script; then passed=$((passed + 1)); fi
    
    log "INFO" "======================================"
    log "INFO" "Test Results: $passed/$total_tests passed"
    log "INFO" "======================================"
    
    if [ $passed -eq $total_tests ]; then
        log "SUCCESS" "All tests passed! You're ready for production backup."
        exit 0
    else
        log "ERROR" "Some tests failed. Please fix issues above before deploying."
        exit 1
    fi
}

# Run tests
main
