# 🚀 Crypto Trade Hub - Production Deployment Guide

## Overview
This guide covers deploying the Crypto Trade Hub in production using Docker containers with optimized performance, security, and scalability.

## 🏗️ Architecture

```
Internet → Nginx (SSL/TLS) → Frontend (React)
                      ↓
                Backend (FastAPI + Gunicorn)
                      ↓
            MongoDB + Redis (Database & Cache)
```

## 📋 Prerequisites

- Docker & Docker Compose
- At least 4GB RAM, 2 CPU cores
- SSL certificate (Let's Encrypt recommended)
- Domain name

## 🔧 Production Setup

### 1. Environment Configuration

Create production environment file:

```bash
# .env.prod
# Database
MONGO_ROOT_USER=your_secure_mongo_user
MONGO_ROOT_PASSWORD=your_secure_mongo_password
MONGO_DB=crypto_trade_hub_prod
MONGO_PORT=27017

# Redis
REDIS_PASSWORD=your_secure_redis_password
REDIS_PORT=6379

# Application
SECRET_KEY=your_64_char_secret_key_here
ENCRYPTION_KEY=your_32_char_encryption_key_here
APP_MODE=production
DEBUG=false

# External APIs
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key

# CORS
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Ports
BACKEND_PORT=8000
FRONTEND_PORT=8080
```

### 2. Secrets Management

Create secrets directory and files:

```bash
mkdir secrets
echo "your_secure_mongo_user" > secrets/mongo_root_user.txt
echo "your_secure_mongo_password" > secrets/mongo_root_password.txt
echo "your_64_char_secret_key" > secrets/secret_key.txt
echo "your_32_char_encryption_key" > secrets/encryption_key.txt
echo "mongodb://user:pass@mongodb:27017/db" > secrets/mongodb_url.txt
echo "redis://:password@redis:6379/0" > secrets/redis_url.txt
echo "your_google_api_key" > secrets/google_api_key.txt
echo "your_groq_api_key" > secrets/groq_api_key.txt
```

Set proper permissions:
```bash
chmod 600 secrets/*
```

### 3. SSL/TLS Setup

#### Using Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Certificates will be in /etc/letsencrypt/live/yourdomain.com/
```

#### Docker with SSL

Update docker-compose.prod.yml to include SSL:

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-ssl.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl/certs:ro
      - /etc/letsencrypt/live/yourdomain.com:/etc/ssl/certs/yourdomain.com:ro
    depends_on:
      - frontend
      - backend
```

### 4. Deployment

#### Start Production Stack

```bash
# Build and start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Check health
curl https://yourdomain.com/health
```

#### Scaling

```bash
# Scale backend workers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale backend=3

# Scale database (if using replica set)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale mongodb=3
```

## 🔒 Security Features

### Container Security
- ✅ **Non-root user**: All containers run as non-privileged users
- ✅ **Minimal base images**: Uses slim Python images
- ✅ **No unnecessary packages**: Only essential runtime dependencies
- ✅ **Read-only filesystems**: Where possible

### Application Security
- ✅ **Gunicorn with Uvicorn workers**: Production-grade ASGI server
- ✅ **Environment-based secrets**: No hardcoded credentials
- ✅ **Encrypted sensitive data**: Database encryption for API keys
- ✅ **Rate limiting**: Nginx-level request throttling
- ✅ **Security headers**: XSS protection, CSRF prevention

### Network Security
- ✅ **Reverse proxy**: Nginx handles all external traffic
- ✅ **SSL/TLS**: End-to-end encryption
- ✅ **WebSocket security**: Proper upgrade handling
- ✅ **Health checks**: Automated service monitoring

## 📊 Monitoring & Observability

### Application Metrics
- **Prometheus endpoint**: `https://yourdomain.com/metrics`
- **Health checks**: `https://yourdomain.com/health`
- **Custom metrics**: Trades, API latency, circuit breaker status

### Container Monitoring
```bash
# View resource usage
docker stats

# Container logs
docker-compose logs -f backend

# Health status
docker ps
```

### Log Aggregation
```bash
# Application logs
docker-compose exec backend tail -f /app/logs/access.log
docker-compose exec backend tail -f /app/logs/error.log

# Nginx logs
docker-compose exec nginx tail -f /var/log/nginx/access.log
```

## 🔄 Maintenance

### Updates
```bash
# Pull latest images
docker-compose pull

# Update with zero downtime
docker-compose up -d --no-deps backend

# Clean up old images
docker image prune -f
```

### Backups
```bash
# Database backup
docker-compose exec mongodb mongodump --out /backup/$(date +%Y%m%d_%H%M%S)

# Copy backup to host
docker cp $(docker-compose ps -q mongodb):/backup ./backups/
```

### Database Migrations
```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Check migration status
docker-compose exec backend alembic current
```

## 🚨 Troubleshooting

### Common Issues

#### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Check database connectivity
docker-compose exec backend python -c "from app.core.database import connect_db; connect_db()"

# Check environment variables
docker-compose exec backend env | grep -E "(DATABASE|REDIS)"
```

#### High memory usage
```bash
# Check container resources
docker stats

# Adjust Gunicorn workers
echo "WORKERS=2" >> .env.prod
docker-compose up -d backend
```

#### WebSocket connections failing
```bash
# Check Nginx WebSocket configuration
docker-compose exec nginx nginx -t

# Verify backend WebSocket endpoint
curl -I http://localhost:8000/api/trading/circuit-breakers
```

### Performance Tuning

#### Gunicorn Workers
```bash
# Calculate optimal workers: (CPU cores * 2) + 1
# For 2 CPU cores: 5 workers
echo "WORKERS=5" >> .env.prod
```

#### Database Connection Pool
```bash
# Adjust MongoDB connection pool
# Set in environment: MAX_POOL_SIZE=10
```

#### Redis Connection Pool
```bash
# Adjust Redis max connections
# Set in environment: REDIS_MAX_CONNECTIONS=20
```

## 📈 Scaling

### Horizontal Scaling
```bash
# Add more backend instances
docker-compose up -d --scale backend=3

# Load balancer configuration needed
```

### Database Scaling
```bash
# MongoDB replica set
# Redis cluster for high availability
```

### CDN Integration
```bash
# Use CloudFlare or AWS CloudFront
# Configure for static assets
```

## 🔧 Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| Workers | 1 (uvicorn) | 4+ (gunicorn) |
| Reload | Enabled | Disabled |
| Debug | Enabled | Disabled |
| Secrets | .env file | Docker secrets |
| Logging | Console | JSON files |
| Health checks | Basic | Comprehensive |

## 📞 Support

For production deployment issues:
1. Check logs: `docker-compose logs`
2. Verify configuration: `docker-compose config`
3. Test endpoints: `curl https://yourdomain.com/health`
4. Monitor resources: `docker stats`

## 🎯 Success Metrics

- **Response time**: < 500ms for API calls
- **Uptime**: > 99.9%
- **Error rate**: < 0.1%
- **WebSocket connections**: Stable
- **Memory usage**: < 80% of allocated

---

**🚀 Happy deploying! Your Crypto Trade Hub is now production-ready.**