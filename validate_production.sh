#!/bin/bash

# 🚀 Crypto Trade Hub - Production Validation Script
# This script validates the production deployment setup

set -e

echo "🔍 Validating Production Deployment Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "success" ]; then
        echo -e "${GREEN}✅ $message${NC}"
    elif [ "$status" = "warning" ]; then
        echo -e "${YELLOW}⚠️  $message${NC}"
    else
        echo -e "${RED}❌ $message${NC}"
    fi
}

# Check if Docker is running
echo "📋 Checking prerequisites..."
if ! docker info >/dev/null 2>&1; then
    print_status "error" "Docker is not running"
    exit 1
fi
print_status "success" "Docker is running"

# Check if Docker Compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    print_status "error" "Docker Compose is not installed"
    exit 1
fi
print_status "success" "Docker Compose is available"

# Check required files
echo ""
echo "📁 Checking configuration files..."
files=("docker-compose.yml" "docker-compose.prod.yml" "Dockerfile" "entrypoint.sh" "nginx.conf" ".dockerignore")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        print_status "success" "$file exists"
    else
        print_status "error" "$file missing"
    fi
done

# Check if secrets directory exists
if [ -d "secrets" ]; then
    print_status "success" "Secrets directory exists"
    secret_files=("mongo_root_user.txt" "mongo_root_password.txt" "secret_key.txt" "encryption_key.txt")
    for file in "${secret_files[@]}"; do
        if [ -f "secrets/$file" ]; then
            print_status "success" "Secret file $file exists"
        else
            print_status "warning" "Secret file $file missing"
        fi
    done
else
    print_status "warning" "Secrets directory missing - create with: mkdir secrets"
fi

# Validate Dockerfile
echo ""
echo "🏗️  Validating Dockerfile..."
if docker build --dry-run . >/dev/null 2>&1; then
    print_status "success" "Dockerfile syntax is valid"
else
    print_status "error" "Dockerfile has syntax errors"
fi

# Check entrypoint.sh
echo ""
echo "🔧 Validating entrypoint.sh..."
if [ -x "entrypoint.sh" ]; then
    print_status "success" "entrypoint.sh is executable"
else
    print_status "warning" "entrypoint.sh is not executable - run: chmod +x entrypoint.sh"
fi

# Validate shell script syntax
if bash -n entrypoint.sh >/dev/null 2>&1; then
    print_status "success" "entrypoint.sh syntax is valid"
else
    print_status "error" "entrypoint.sh has syntax errors"
fi

# Check Nginx configuration
echo ""
echo "🌐 Validating Nginx configuration..."
if docker run --rm -v "$(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:alpine nginx -t >/dev/null 2>&1; then
    print_status "success" "nginx.conf is valid"
else
    print_status "error" "nginx.conf has configuration errors"
fi

# Check environment file
echo ""
echo "🔐 Checking environment configuration..."
if [ -f ".env.prod" ]; then
    print_status "success" ".env.prod file exists"
    # Check for required variables
    required_vars=("MONGO_ROOT_USER" "MONGO_ROOT_PASSWORD" "SECRET_KEY" "ENCRYPTION_KEY")
    for var in "${required_vars[@]}"; do
        if grep -q "^$var=" .env.prod; then
            print_status "success" "Environment variable $var is set"
        else
            print_status "warning" "Environment variable $var is missing"
        fi
    done
else
    print_status "warning" ".env.prod file missing - copy from .env and modify for production"
fi

# Test Docker Compose configuration
echo ""
echo "🐳 Validating Docker Compose configuration..."
if docker-compose -f docker-compose.yml -f docker-compose.prod.yml config >/dev/null 2>&1; then
    print_status "success" "Docker Compose configuration is valid"
else
    print_status "error" "Docker Compose configuration has errors"
fi

# Check resource limits
echo ""
echo "📊 Checking resource limits..."
if grep -q "deploy:" docker-compose.prod.yml && grep -q "resources:" docker-compose.prod.yml; then
    print_status "success" "Resource limits are configured"
else
    print_status "warning" "Resource limits not found in docker-compose.prod.yml"
fi

# Security check
echo ""
echo "🔒 Security validation..."
# Check if running as non-root
if grep -q "USER app" Dockerfile; then
    print_status "success" "Container runs as non-root user"
else
    print_status "warning" "Container may run as root - check Dockerfile"
fi

# Check if secrets are used
if grep -q "_FILE" docker-compose.prod.yml; then
    print_status "success" "Docker secrets are configured"
else
    print_status "warning" "Docker secrets not configured"
fi

echo ""
echo "🎯 Validation complete!"
echo ""
echo "📝 Next steps:"
echo "1. Fix any errors shown above"
echo "2. Run: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
echo "3. Check logs: docker-compose logs -f"
echo "4. Test health endpoint: curl http://localhost/health"
echo ""
echo "📖 For detailed deployment guide, see: PRODUCTION_DEPLOYMENT.md"