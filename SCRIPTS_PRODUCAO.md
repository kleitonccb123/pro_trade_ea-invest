# 🔧 SCRIPTS E UTILIDADES - DEPLOYMENT EM PRODUÇÃO

**Data:** Março 23, 2026  
**Objetivo:** Scripts prontos para manutenção e troubleshooting

---

## 📂 ORGANIZAÇÃO DE SCRIPTS

Após o deployment, você terá estes scripts na VPS:

```
/home/appuser/crypto-trade-hub/
├── backup.sh              (Backup automático diário)
├── health_check.sh        (Verificação de saúde)
├── update_frontend.sh     (Atualizar frontend)
├── update_backend.sh      (Atualizar backend)
├── update_all.sh          (Atualizar tudo)
├── rollback.sh            (Voltar versão anterior)
└── troubleshoot.sh        (Detectar problemas)
```

---

## 1️⃣ SCRIPT: health_check.sh

**Verifica saúde da aplicação em tempo real**

```bash
#!/bin/bash

# Health Check - Crypto Trade Hub

DOMAIN="seu-dominio.com"
PROJECT_DIR="/home/appuser/crypto-trade-hub"

echo "╔════════════════════════════════════════════════════════╗"
echo "║     Crypto Trade Hub - Health Check                    ║"
echo "║     $(date '+%Y-%m-%d %H:%M:%S')                                  ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# 1. Frontend
echo -n "🌐 Frontend (HTTP):  "
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://$DOMAIN 2>/dev/null || echo "000")
if [ "$FRONTEND_STATUS" = "301" ] || [ "$FRONTEND_STATUS" = "200" ]; then
  echo "✓ $FRONTEND_STATUS"
else
  echo "✗ $FRONTEND_STATUS"
fi

# 2. Frontend HTTPS
echo -n "🔒 Frontend (HTTPS): "
FRONTEND_HTTPS=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN 2>/dev/null || echo "000")
if [ "$FRONTEND_HTTPS" = "200" ]; then
  echo "✓ $FRONTEND_HTTPS"
else
  echo "✗ $FRONTEND_HTTPS"
fi

# 3. Backend API
echo -n "⚙️  Backend API:     "
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/api/health 2>/dev/null || echo "000")
if [ "$BACKEND_STATUS" = "200" ]; then
  echo "✓ $BACKEND_STATUS"
else
  echo "✗ $BACKEND_STATUS"
fi

echo ""
echo "📦 Containers:"

cd "$PROJECT_DIR"
MONGO=$(docker-compose -f docker-compose.prod.yml ps crypto-trade-mongodb | grep -i up | wc -l)
REDIS=$(docker-compose -f docker-compose.prod.yml ps crypto-trade-redis | grep -i up | wc -l)
BACKEND=$(docker-compose -f docker-compose.prod.yml ps crypto-trade-backend | grep -i up | wc -l)
NGINX=$(docker-compose -f docker-compose.prod.yml ps crypto-trade-nginx | grep -i up | wc -l)

[ "$MONGO" -eq 1 ] && echo "   ✓ MongoDB" || echo "   ✗ MongoDB DOWN"
[ "$REDIS" -eq 1 ] && echo "   ✓ Redis" || echo "   ✗ Redis DOWN"
[ "$BACKEND" -eq 1 ] && echo "   ✓ Backend" || echo "   ✗ Backend DOWN"
[ "$NGINX" -eq 1 ] && echo "   ✓ Nginx" || echo "   ✗ Nginx DOWN"

echo ""
echo "💾 Recursos:"

# Disco
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
DISK_COLOR="\033[0;32m"
[ $DISK_USAGE -gt 85 ] && DISK_COLOR="\033[0;31m"
echo -e "   Disco: ${DISK_COLOR}${DISK_USAGE}%\033[0m"

# Memória
MEM_USAGE=$(free | awk 'NR==2 {printf "%.0f", $3/$2 * 100}')
MEM_COLOR="\033[0;32m"
[ $MEM_USAGE -gt 85 ] && MEM_COLOR="\033[0;31m"
echo -e "   Memória: ${MEM_COLOR}${MEM_USAGE}%\033[0m"

# CPU
CPU=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{printf "%.0f", 100 - $1}')
echo "   CPU: ${CPU}%"

echo ""
echo "🔐 SSL:"

CERT_DATE=$(openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -enddate 2>/dev/null | cut -d= -f2)
echo "   Válido até: $CERT_DATE"

DAYS_LEFT=$(( ( $(date -d "$CERT_DATE" +%s) - $(date +%s) ) / 86400 ))
if [ $DAYS_LEFT -gt 30 ]; then
  echo "   Status: ✓ OK ($DAYS_LEFT dias)"
elif [ $DAYS_LEFT -gt 7 ]; then
  echo "   Status: ⚠️  AVISO ($DAYS_LEFT dias)"
else
  echo "   Status: ✗ CRÍTICO ($DAYS_LEFT dias)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Retorna 0 se tudo OK
if [ "$FRONTEND_HTTPS" = "200" ] && [ "$BACKEND_STATUS" = "200" ]; then
  echo "Status: ✅ TUDO OK"
  exit 0
else
  echo "Status: ⚠️  PROBLEMAS DETECTADOS"
  exit 1
fi
```

**Como usar:**
```bash
chmod +x health_check.sh
./health_check.sh

# Executar a cada 5 minutos
*/5 * * * * /home/appuser/crypto-trade-hub/health_check.sh >> /home/appuser/health_check.log 2>&1
```

---

## 2️⃣ SCRIPT: update_frontend.sh

**Atualizar apenas Frontend (React/HTML/CSS)**

```bash
#!/bin/bash

# Update Frontend - Zero Downtime

PROJECT_DIR="/home/appuser/crypto-trade-hub"
cd "$PROJECT_DIR"

echo "🚀 Atualizando Frontend..."
echo "[$(date)] Iniciando update frontend" >> update.log

# 1. Pull
echo "  1. Fazendo git pull..."
git pull origin main >> /dev/null 2>&1

# 2. Build
echo "  2. Buildando React..."
npm install >> /dev/null 2>&1
npm run build >> /dev/null 2>&1

# 3. Validar build
if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
  echo "  ✗ ERRO: Build falhou"
  echo "[$(date)] ERROR: Build failed" >> update.log
  exit 1
fi

echo "  ✓ Build sucesso"

# 4. Recarregar nginx
echo "  3. Recarregando Nginx..."
docker-compose -f docker-compose.prod.yml exec -T nginx nginx -s reload

# 5. Aguardar
sleep 2

# 6. Validar
STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://seu-dominio.com)
if [ "$STATUS" = "200" ]; then
  echo "✅ Frontend atualizado com sucesso!"
  echo "[$(date)] Frontend update SUCCESS" >> update.log
else
  echo "⚠️  Status: $STATUS"
  exit 1
fi
```

**Como usar:**
```bash
chmod +x update_frontend.sh
./update_frontend.sh
```

---

## 3️⃣ SCRIPT: update_backend.sh

**Atualizar apenas Backend (Python/FastAPI)**

```bash
#!/bin/bash

# Update Backend - Graceful Restart

PROJECT_DIR="/home/appuser/crypto-trade-hub"
cd "$PROJECT_DIR"

echo "🚀 Atualizando Backend..."
echo "[$(date)] Iniciando update backend" >> update.log

# 1. Pull
echo "  1. Fazendo git pull..."
git pull origin main >> /dev/null 2>&1

# 2. Build
echo "  2. Buildando Docker..."
docker-compose -f docker-compose.prod.yml build backend >> /dev/null 2>&1

if [ $? -ne 0 ]; then
  echo "  ✗ ERRO: Build Docker falhou"
  echo "[$(date)] ERROR: Docker build failed" >> update.log
  exit 1
fi

echo "  ✓ Build sucesso"

# 3. Stop graceful (30 seg pra finalizar requisições)
echo "  3. Parando container antigo..."
docker-compose -f docker-compose.prod.yml stop -t 30 backend

# 4. Start novo
echo "  4. Iniciando novo container..."
docker-compose -f docker-compose.prod.yml up -d backend

# 5. Aguardar inicializar
sleep 5

# 6. Validar
echo "  5. Validando..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://seu-dominio.com/api/health)

if [ "$STATUS" = "200" ]; then
  echo "✅ Backend atualizado com sucesso!"
  echo "[$(date)] Backend update SUCCESS" >> update.log
else
  echo "⚠️  Status: $STATUS"
  echo "[$(date)] ERROR: Health check failed ($STATUS)" >> update.log
  exit 1
fi
```

**Como usar:**
```bash
chmod +x update_backend.sh
./update_backend.sh
```

---

## 4️⃣ SCRIPT: update_all.sh

**Atualizar Frontend + Backend juntos**

```bash
#!/bin/bash

# Update All - Complete Deployment

PROJECT_DIR="/home/appuser/crypto-trade-hub"
cd "$PROJECT_DIR"

echo "🚀 Deployment Completo (Frontend + Backend)..."
echo "[$(date)] Iniciando deployment completo" >> update.log

# 1. Pull
echo "  1. Fazendo git pull..."
git pull origin main

# 2. Build frontend
echo "  2. Buildando Frontend..."
npm install
npm run build
if [ ! -d "dist" ]; then
  echo "  ✗ Erro no build frontend"
  exit 1
fi

# 3. Build backend
echo "  3. Buildando Backend..."
docker-compose -f docker-compose.prod.yml build backend
if [ $? -ne 0 ]; then
  echo "  ✗ Erro no build backend"
  exit 1
fi

# 4. Stop backend
echo "  4. Parando Backend..."
docker-compose -f docker-compose.prod.yml stop -t 30 backend

# 5. Start novo
echo "  5. Iniciando servicos..."
docker-compose -f docker-compose.prod.yml up -d backend

# 6. Reload nginx
echo "  6. Atualizando Frontend..."
sleep 3
docker-compose -f docker-compose.prod.yml exec -T nginx nginx -s reload

# 7. Aguardar
sleep 3

# 8. Validar
echo "  7. Validando..."
FRONTEND=$(curl -s -o /dev/null -w "%{http_code}" https://seu-dominio.com)
BACKEND=$(curl -s -o /dev/null -w "%{http_code}" https://seu-dominio.com/api/health)

if [ "$FRONTEND" = "200" ] && [ "$BACKEND" = "200" ]; then
  echo "✅ DEPLOYMENT SUCESSO!"
  echo "[$(date)] DEPLOYMENT SUCCESS" >> update.log
else
  echo "⚠️  Frontend: $FRONTEND, Backend: $BACKEND"
  exit 1
fi
```

---

## 5️⃣ SCRIPT: rollback.sh

**Voltar para versão anterior (Undo)**

```bash
#!/bin/bash

# Rollback - Volta versão anterior

PROJECT_DIR="/home/appuser/crypto-trade-hub"
cd "$PROJECT_DIR"

echo "⏮️  Fazendo Rollback..."
echo "[$(date)] Iniciando rollback" >> update.log

# 1. Voltar commit
git reset --hard HEAD~1

# 2. Rebuild frontend
npm run build

# 3. Rebuild backend
docker-compose -f docker-compose.prod.yml build backend

# 4. Restart
docker-compose -f docker-compose.prod.yml stop backend
docker-compose -f docker-compose.prod.yml up -d backend
docker-compose -f docker-compose.prod.yml exec -T nginx nginx -s reload

sleep 3

# 5. Validar
BACKEND=$(curl -s -o /dev/null -w "%{http_code}" https://seu-dominio.com/api/health)

if [ "$BACKEND" = "200" ]; then
  echo "✅ Rollback concluído com sucesso!"
  echo "[$(date)] Rollback SUCCESS" >> update.log
else
  echo "⚠️  Rollback pode ter falhado"
  exit 1
fi
```

---

## 6️⃣ SCRIPT: troubleshoot.sh

**Diagnosticar problemas**

```bash
#!/bin/bash

# Troubleshoot - Detectar problemas

PROJECT_DIR="/home/appuser/crypto-trade-hub"
cd "$PROJECT_DIR"

echo "🔍 Diagnóstico do Sistema..."
echo ""

# 1. Containers
echo "━━━ Containers ━━━"
docker-compose -f docker-compose.prod.yml ps
echo ""

# 2. Logs Backend (últimos 50 linhas)
echo "━━━ Logs Backend ━━━"
docker-compose -f docker-compose.prod.yml logs backend | tail -20
echo ""

# 3. Logs Nginx
echo "━━━ Logs Nginx ━━━"
docker-compose -f docker-compose.prod.yml logs nginx | tail -20
echo ""

# 4. Logs MongoDB
echo "━━━ Logs MongoDB ━━━"
docker-compose -f docker-compose.prod.yml logs mongodb | tail -20
echo ""

# 5. Erros críticos
echo "━━━ Erros Críticos ━━━"
ERRORS=$(docker-compose -f docker-compose.prod.yml logs backend 2>&1 | grep -i error)
if [ -z "$ERRORS" ]; then
  echo "✓ Nenhum erro crítico detectado"
else
  echo "$ERRORS"
fi
echo ""

# 6. Health check
echo "━━━ Health Check ━━━"
curl -s https://seu-dominio.com/api/health | python -m json.tool || echo "API não responde"
echo ""

# 7. Certificado SSL
echo "━━━ Certificado SSL ━━━"
openssl x509 -in /etc/letsencrypt/live/seu-dominio.com/fullchain.pem -noout -enddate
echo ""

# 8. Recursos
echo "━━━ Recursos ━━━"
echo "Disco:"
df -h / | tail -1
echo "Memória:"
free -h | grep Mem
echo "CPU:"
nproc
```

---

## 7️⃣ SCRIPT: auto_restart.sh

**Restartar container se cair**

```bash
#!/bin/bash

# Monitorar e auto-restart se necessário

PROJECT_DIR="/home/appuser/crypto-trade-hub"
cd "$PROJECT_DIR"

# Verifica a cada 30 segundos
while true; do
  # Verificar se backend está up
  BACKEND_RUNNING=$(docker-compose -f docker-compose.prod.yml ps crypto-trade-backend | grep -i up | wc -l)
  
  if [ $BACKEND_RUNNING -eq 0 ]; then
    echo "[$(date)] Backend DOWN! Iniciando restart..."
    docker-compose -f docker-compose.prod.yml restart backend
    
    # Notificar
    echo "Backend restart em $(date)" | mail -s "⚠️  Backend Restart" seu_email@dominio.com
  fi
  
  sleep 30
done
```

**Rodar como background daemon:**
```bash
nohup ./auto_restart.sh > auto_restart.log 2>&1 &
```

---

## 8️⃣ CRONTAB - TODOS OS JOBS AUTOMATIZADOS

```bash
# Abrir editor
crontab -e

# Adicionar estas linhas:

# ===== BACKUPS =====
# Backup diário às 2AM
0 2 * * * /home/appuser/crypto-trade-hub/backup.sh >> /home/appuser/backup.log 2>&1

# ===== HEALTH CHECKS =====
# Health check a cada 5 minutos
*/5 * * * * /home/appuser/crypto-trade-hub/health_check.sh >> /home/appuser/health_check.log 2>&1

# ===== ALERTAS =====
# Se falhar, enviar email (a cada 30 min)
*/30 * * * * /home/appuser/crypto-trade-hub/alert_check.sh >> /home/appuser/alert.log 2>&1

# ===== AUTO RESTART =====
# Monitorar backend cada minuto
* * * * * (docker-compose -f /home/appuser/crypto-trade-hub/docker-compose.prod.yml ps crypto-trade-backend | grep -q "Up" || docker-compose -f /home/appuser/crypto-trade-hub/docker-compose.prod.yml restart backend)
```

---

## 📝 ROTINA DE MANUTENÇÃO RECOMENDADA

### Diariamente
- [ ] Health check (automático via cron)
- [ ] Revisar logs: `tail -f /home/appuser/crypto-trade-hub/update.log`

### Semanalmente
- [ ] Testar backup: `tar -tzf /home/appuser/backups/latest.tar.gz | head`
- [ ] Verificar espaço em disco: `df -h`
- [ ] Revisar logs de erro: `docker-compose logs backend | grep ERROR`

### Mensalmente
- [ ] Revisar certificado SSL (dias até expiração)
- [ ] Testar procedimento de rollback
- [ ] Update de dependências (npm/pip)

### Quando fazer deploy
- [ ] Sempre em horários de baixa demanda
- [ ] Sempre fazer backup antes
- [ ] Sempre testar em staging primeiro
- [ ] Sempre ter rollback pronto

---

## 🚨 QUICK FIXES

### 502 Bad Gateway
```bash
docker-compose -f docker-compose.prod.yml logs backend
docker-compose -f docker-compose.prod.yml restart backend
```

### Aplicação Lenta
```bash
free -h          # Verificar memória
df -h            # Verificar disco
docker stats     # Ver qual container consome
```

### Certificado SSL Expirou
```bash
certbot renew --force-renewal
docker-compose -f docker-compose.prod.yml restart nginx
```

### Banco de Dados Cheio
```bash
# Limpar backups antigos
find /home/appuser/backups -mtime +30 -delete

# Limpeza Docker
docker system prune -a
```

---

**Status: Pronto para produção! ✅**
