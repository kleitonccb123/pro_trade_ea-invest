# ⚡ CHECKLIST RÁPIDO - DEPLOYMENT VPS HOSTINGER

**Data:** Março 23, 2026  
**Tempo Total:** ~4-6 horas (primeira vez)  
**Tempo Futuro:** 5-30 min (por atualização)

---

## 🚀 ANTES DE COMEÇAR

```bash
# Antes de tudo, tenha isto pronto:
☐ IP da VPS (em Painel Hostinger)
☐ Senha/Chave SSH
☐ Domínio apontando para VPS (ou pronto para apontar)
☐ Todas as mudanças no código fazendo commit
☐ Arquivo .env.production preparado locally
```

---

## FASE 1: PREPARAR VPS (30-45 min)

```bash
# 1. Conectar SSH
☐ ssh root@SEU_IP_VPS

# 2. Atualizar sistema
☐ apt update && apt upgrade -y

# 3. Instalar dependências
☐ apt install -y curl wget git vim htop
☐ curl -fsSL https://get.docker.com | sh
☐ curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose
☐ apt install -y python3.11 python3.11-venv python3-pip
☐ curl -fsSL https://deb.nodesource.com/setup_20.x | bash && apt install -y nodejs npm

# 4. Criar usuário não-root
☐ useradd -m -s /bin/bash appuser
☐ usermod -aG docker appuser
☐ usermod -aG sudo appuser
☐ passwd appuser
☐ su - appuser
```

**Validar:**
```bash
☐ docker --version
☐ docker-compose --version
☐ node --version
☐ python3.11 --version
```

---

## FASE 2: CONFIGURAR DOMÍNIO (5-15 min)

**Na Hostinger:**
```
☐ Painel → Domínios → Seu Domínio → DNS Zone
☐ Adicionar registro A:
   - Host: @ (ou vazio)
   - Value: SEU_IP_VPS
   - TTL: 3600
☐ Também para www (opcional)
☐ Salvar e aguardar propagação (15-30 min)
```

**Na VPS (depois de propagação):**
```bash
☐ nslookup seu-dominio.com  # Deve resolver pro seu IP
☐ ping seu-dominio.com      # Deve ter resposta
```

---

## FASE 3: CLONAR E PREPARAR PROJETO (10-20 min)

```bash
# Na VPS como appuser
☐ cd /home/appuser
☐ git clone https://seu-github-url/crypto-trade-hub.git
☐ cd crypto-trade-hub

# Copiar .env
☐ cp .env.example .env.production
☐ nano .env.production  # Editar com valores reais

# Build frontend
☐ npm install
☐ npm run build
☐ ls dist/  # Deve ter arquivos
```

**Variáveis .env críticas:**
```
DOMAIN=seu-dominio.com
MONGO_ROOT_PASSWORD=SENHA_FORTE_32CHARS
REDIS_PASSWORD=SENHA_FORTE_16CHARS
JWT_SECRET_KEY=HEX_64CHARS
```

---

## FASE 4: CERTIFICADO SSL (10-15 min)

```bash
# Na VPS como root
☐ apt install -y certbot python3-certbot-nginx
☐ certbot certonly --standalone \
    --email seu_email@dominio.com \
    --agree-tos \
    -d seu-dominio.com \
    -d www.seu-dominio.com

# Validar
☐ ls -la /etc/letsencrypt/live/seu-dominio.com/
☐ fullchain.pem e privkey.pem existem ✓
```

---

## FASE 5: PREPARAR DOCKER (5 min)

```bash
# Na VPS como appuser
☐ cd /home/appuser/crypto-trade-hub

# Criar pasta nginx
☐ mkdir -p nginx
☐ cp nginx.prod.conf nginx/nginx.conf  # Copiar arquivo com SSL configurado

# Criar volumes
☐ mkdir -p docker-volumes/{mongo,redis,nginx}
☐ chmod 755 docker-volumes
```

---

## FASE 6: SUBIR DOCKER COMPOSE (5-10 min)

```bash
# Na VPS como appuser
☐ cd /home/appuser/crypto-trade-hub

# Iniciar containers
☐ docker-compose -f docker-compose.prod.yml up -d

# Aguardar 15 seg
☐ sleep 15

# Validar
☐ docker-compose -f docker-compose.prod.yml ps
   - crypto-trade-mongodb   Up (healthy)
   - crypto-trade-redis     Up (healthy)
   - crypto-trade-backend   Up (healthy)
   - crypto-trade-nginx     Up

# Acompanhar logs
☐ docker-compose -f docker-compose.prod.yml logs -f backend
```

---

## FASE 7: VALIDAR ACESSO (5-10 min)

```bash
# Via terminal
☐ curl -I https://seu-dominio.com  # Status 200/301
☐ curl -I https://seu-dominio.com/api/health  # Status 200

# Via navegador
☐ Abrir https://seu-dominio.com no Chrome
☐ Aplicação React carrega sem erros ✓
☐ F12 Console - sem CORS errors ✓
```

---

## FASE 8: CONFIGURAR BACKUPS (5 min)

```bash
# Na VPS como appuser
☐ mkdir -p /home/appuser/backups
☐ cat > /home/appuser/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/appuser/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"
docker exec crypto-trade-mongodb mongodump --username admin --password $MONGO_ROOT_PASSWORD --authenticationDatabase admin --out /tmp/mongo_backup
tar -czf "$BACKUP_DIR/backup_$DATE.tar.gz" /tmp/mongo_backup
rm -rf /tmp/mongo_backup
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete
EOF

☐ chmod +x /home/appuser/backup.sh
☐ crontab -e  # Adicionar: 0 2 * * * /home/appuser/backup.sh >> /home/appuser/backup.log 2>&1
```

---

## ✅ DEPLOY COMPLETO!

```bash
# Testar tudo uma última vez
☐ curl https://seu-dominio.com/api/health
☐ https://seu-dominio.com carrega?
☐ docker-compose -f docker-compose.prod.yml ps mostra tudo Up
```

**STATUS: APLICAÇÃO EM PRODUÇÃO** 🎉

---

---

## 🔄 PARA ATUALIZAÇÕES FUTURAS

### Tipo 1: Só Frontend Mudou

```bash
☐ git pull
☐ npm run build
☐ docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
# Tempo: 2-5 min, sem downtime
```

### Tipo 2: Backend Mudou

```bash
☐ git pull
☐ docker-compose -f docker-compose.prod.yml build backend
☐ docker-compose -f docker-compose.prod.yml stop -t 30 backend
☐ docker-compose -f docker-compose.prod.yml up -d backend
# Tempo: 1-3 min
```

### Tipo 3: Frontend + Backend

```bash
☐ git pull
☐ npm run build
☐ docker-compose -f docker-compose.prod.yml build backend
☐ docker-compose -f docker-compose.prod.yml stop -t 30 backend
☐ docker-compose -f docker-compose.prod.yml up -d backend
☐ docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
# Tempo: 3-5 min
```

### Tipo 4: Database Migration

```bash
☐ git pull
☐ docker-compose -f docker-compose.prod.yml exec backend python -m alembic upgrade head
# Tempo: <5 min
```

---

## 🆘 SE ALGO QUEBRAR

### Opção 1: Ver o que tá ruim
```bash
docker-compose -f docker-compose.prod.yml logs backend | tail -50
docker-compose -f docker-compose.prod.yml logs nginx | tail -50
```

### Opção 2: Voltar atrás (Rollback)
```bash
cd /home/appuser/crypto-trade-hub
git reset --hard HEAD~1
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml restart
```

### Opção 3: Restart tudo
```bash
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📊 MONITORAR SAÚDE

```bash
# Criar script de health check
cat > /home/appuser/health.sh << 'EOF'
#!/bin/bash
echo "Frontend: $(curl -s -o /dev/null -w '%{http_code}' https://seu-dominio.com)"
echo "Backend:  $(curl -s -o /dev/null -w '%{http_code}' https://seu-dominio.com/api/health)"
docker-compose -f /home/appuser/crypto-trade-hub/docker-compose.prod.yml ps
df -h /
free -h
EOF

chmod +x /home/appuser/health.sh

# Executar quando necessário
/home/appuser/health.sh
```

---

## 🔐 SEGURANÇA BÁSICA

```bash
# Firewall
☐ ufw enable
☐ ufw allow 22/tcp
☐ ufw allow 80/tcp
☐ ufw allow 443/tcp
☐ ufw status

# Fail2Ban
☐ apt install -y fail2ban
☐ systemctl enable fail2ban

# SSH só com key (remover password login)
# Editar /etc/ssh/sshd_config
☐ PasswordAuthentication no
☐ systemctl restart sshd
```

---

## 📝 DOCUMENTAÇÃO COMPLETA

Para mais detalhes, ver: `DEPLOYMENT_GUIA_COMPLETO.md`

- Troubleshooting detalhado
- Procedimentos de emergência
- Monitoramento avançado
- Alertas por email

---

**Pronto? Comece pelo Passo 1!** 🚀
