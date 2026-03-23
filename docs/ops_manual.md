# 🚀 Manual de Operações - Crypto Trade Hub

**Para: Equipe de DevOps/Suporte**  
**Versão**: 1.0  
**Última Atualização**: 2025-02-11

---

## 📋 Índice Rápido

1. [Iniciar/Parar Aplicação](#inicararparar)
2. [Visualizar Logs](#visualizar-logs)
3. [Gerenciar Backups](#gerenciar-backups)
4. [Reset Manual de Créditos](#reset-de-créditos)
5. [Reverter Kill Switch](#reverter-kill-switch)
6. [Troubleshooting](#troubleshooting)
7. [Procedimentos de Emergência](#emergência)

---

## 🔧 Iniciar/Parar Aplicação {#inicararparar}

### Iniciar Stack Completa (Produção)

```bash
# Navegar para diretório do projeto
cd /path/to/crypto-trade-hub

# Deploy completo (recomendado)
./deploy.sh deploy

# Ou com docker-compose diretamente
docker-compose -f docker-compose.prod.yml up -d

# Verificar status dos serviços
./deploy.sh status
# ou
docker-compose ps
```

### Parar Stack Completa

```bash
# Parar mantendo volumes (dados persistem)
./deploy.sh stop

# Parar e remover tudo (CUIDADO: deleta dados!)
./deploy.sh clean
docker-compose -f docker-compose.prod.yml down -v
```

### Reiniciar Serviço Específico

```bash
# Reiniciar apenas backend
docker-compose -f docker-compose.prod.yml restart backend

# Reiniciar apenas frontend
docker-compose -f docker-compose.prod.yml restart frontend

# Reiniciar apenas MongoDB
docker-compose -f docker-compose.prod.yml restart mongodb

# Reiniciar apenas Redis
docker-compose -f docker-compose.prod.yml restart redis
```

---

## 📊 Visualizar Logs {#visualizar-logs}

### Logs em Tempo Real

```bash
# Todos os serviços
./deploy.sh logs

# Apenas backend (com filtro)
./deploy.sh logs backend | grep ERROR

# Apenas frontend
docker-compose logs -f frontend

# Apenas MongoDB
docker-compose logs -f mongodb

# Apenas Nginx
docker-compose logs -f nginx
```

### Filtros Úteis

```bash
# Erros de API
docker-compose logs backend | grep "API_ERROR"

# Problemas de autenticação
docker-compose logs backend | grep "auth"

# WebSocket errors
docker-compose logs nginx | grep "websocket"

# Seguir novo erro específico
docker-compose logs -f backend | grep "NomeDaExcecao"
```

### Salvar Logs para Investigação

```bash
# Exportar últimas 1000 linhas
docker-compose logs backend > /tmp/backend_logs_$(date +%Y%m%d_%H%M%S).txt

# Comprimir para arquivo
docker-compose logs --timestamps >> backend_logs.txt
tar -czf backend_logs_$(date +%Y%m%d).tar.gz backend_logs.txt
```

---

## 💾 Gerenciar Backups {#gerenciar-backups}

### Fazer Backup Manual

```bash
# Backup imediato (MongoDB + Redis)
./backup_db.sh backup

# Verificar backups recentes
./backup_db.sh info
```

### Programar Backups Automáticos

```bash
# Configurar cron para backup diário às 2 AM
./backup_db.sh schedule

# Verificar que foi adicionado
crontab -l | grep backup_db

# Backup manual a qualquer hora
./backup_db.sh backup
```

### Restaurar de Backup

```bash
# Listar backups disponíveis
./backup_db.sh info

# Restaurar de arquivo específico
./backup_db.sh restore backup_20250211_143022.tar.gz

# O script vai:
# 1. Confirmar restauração (sim/não)
# 2. Parar serviços
# 3. Restaurar MongoDB e Redis
# 4. Reiniciar serviços
```

### Verificar Integridade do Backup

```bash
# Testar restauração sem aplicar
cd /tmp
tar -tzf /path/to/backup_20250211_143022.tar.gz | head -20

# Verificar metadata
cat /path/to/backup_20250211_143022.metadata.json
```

---

## 👤 Reset de Créditos {#reset-de-créditos}

### Cenário: Usuário reporta créditos incorretos

```bash
# 1. Conectar ao MongoDB
docker-compose exec mongodb mongosh -u admin -p $MONGO_PASSWORD

# 2. No prompt mongosh (substituir valores reais)
use trading_db

# Ver créditos atuais
db.users.findOne({email: "user@example.com"})

# Reset completo de créditos (volta ao plano inicial)
db.users.updateOne(
  {email: "user@example.com"},
  {$set: {
    activation_credits: 5,  # ou valor correto do plano
    activation_credits_used: 0,
    swap_count: 0
  }}
)

# Verificar atualização
db.users.findOne({email: "user@example.com"})

# Sair
exit
```

### Reset para Múltiplos Usuários

```bash
# Reset todos os usuários do plano PRO
docker-compose exec mongodb mongosh -u admin -p $MONGO_PASSWORD << 'EOF'
use trading_db
db.users.updateMany(
  {plan: "PRO"},
  {$set: {
    activation_credits_used: 0,
    swap_count: 0
  }}
)
EOF
```

---

## 🛑 Reverter Kill Switch {#reverter-kill-switch}

### Cenário: Kill Switch ativado por erro, precisa desativar

```bash
# 1. Conectar ao MongoDB
docker-compose exec mongodb mongosh -u admin -p $MONGO_PASSWORD

# 2. No prompt mongosh (substituir user_id real)
use trading_db

# Ver status Kill Switch
db.users.findOne({_id: ObjectId("507f1f77bcf86cd799439011")})

# Desativar Kill Switch
db.users.updateOne(
  {_id: ObjectId("507f1f77bcf86cd799439011")},
  {$set: {
    is_blocked_by_kill_switch: false,
    kill_switch_reason: null,
    kill_switch_timestamp: null
  }}
)

# Reativar slot do bot
db.bots.updateOne(
  {user_id: ObjectId("507f1f77bcf86cd799439011")},
  {$set: {is_active_slot: true}}
)

# Verificar
db.users.findOne({_id: ObjectId("507f1f77bcf86cd799439011")})

# Sair
exit
```

### Ver Histórico de Kill Switch

```bash
docker-compose exec mongodb mongosh -u admin -p $MONGO_PASSWORD << 'EOF'
use trading_db
db.kill_switch_events.find().sort({timestamp: -1}).limit(10).pretty()
EOF
```

---

## 🔍 Troubleshooting {#troubleshooting}

### Erro: "Porta já em uso"

```bash
# Ver o que está usando as portas
lsof -i :80    # Nginx
lsof -i :443   # Nginx SSL
lsof -i :8000  # Backend
lsof -i :27017 # MongoDB
lsof -i :6379  # Redis

# Matar processo específico
kill -9 <PID>

# Ou parar stack e reniciar
docker-compose down
docker-compose up -d
```

### Erro: "MongoDB connection refused"

```bash
# 1. Verificar status
docker-compose ps mongodb

# 2. Se parado, iniciar
docker-compose up -d mongodb

# 3. Verificar logs
docker-compose logs mongodb | tail -50

# 4. Se recusar conexão, pode ser auth
# Verificar variáveis de ambiente
echo $MONGO_ROOT_PASSWORD
echo $MONGO_USERNAME

# 5. Se estava correto antes, pode ter crash de volume
# Backup e limpar
docker-compose exec mongodb mongodump --out /backups/last_working
docker-compose down
rm -rf mongo_data/
docker-compose up -d mongodb
```

### Erro: "Redis out of memory"

```bash
# Ver consumo atual
docker-compose exec redis redis-cli info memory

# Limpar keys expiradas
docker-compose exec redis redis-cli FLUSHDB

# APENAS SE NECESSÁRIO - Limpar TUDO (cuidado!)
docker-compose exec redis redis-cli FLUSHALL

# Aumentar limite em redis.prod.conf
# maxmemory 512mb  →  maxmemory 1gb
# Depois: docker-compose up -d redis
```

### Erro: "Bot não consegue conectar API"

```bash
# 1. Verificar logs do bot
docker-compose logs backend | grep "exchange"

# 2. Testar credenciais (se for KuCoin)
curl -X POST https://api.kucoin.com/api/v1/account-list \
  -H "Content-Type: application/json" \
  -H "KC-API-KEY: seu_api_key" \
  -H "KC-API-SIGN: seu_signature" \
  -H "KC-API-TIMESTAMP: $(date +%s)000" \
  -H "KC-API-PASSPHRASE: sua_passphrase"

# 3. Se API inválido, resetar no banco
# Ver seção "Reset de Créditos"
```

### Erro: "WebSocket desconectando"

```bash
# Ver logs do Nginx
docker-compose logs nginx | grep -i upgrade

# Verificar configuração de timeout
docker-compose exec nginx cat /etc/nginx/nginx.conf | grep timeout

# Se necessário, aumentar timeout
# proxy_connect_timeout 60s;
# proxy_send_timeout 60s;
# proxy_read_timeout 60s;
```

---

## 🚨 Procedimentos de Emergência {#emergência}

### Stack Down Completo

```bash
# Status atual
./deploy.sh status

# Parar tudo
./deploy.sh stop

# Remover e recriar (CUIDADO - perde dados!)
./deploy.sh clean

# Redeploy completo
./deploy.sh deploy

# Verificar saúde
./deploy.sh logs
```

### Restaurar de Backup em Emergência

```bash
# 1. Stop seleto (manter apenas MongoDB off-backup)
docker-compose down

# 2. Restaurar
./backup_db.sh restore backup_20250210_020000.tar.gz

# 3. Redeploy
./deploy.sh deploy

# 4. Verificar saúde
docker-compose ps
./deploy.sh status
```

### Resetar Aplicação (Nuclear Option)

```bash
# ⚠️ CUIDADO: Deleta TUDO
docker-compose down -v
rm -rf mongo_data/ redis_data/ logs/

# Recriar volumes zerados
docker-compose up -d

# Reaplicar migrations (se houver)
docker-compose exec backend python -m scripts.migrate_activation_system

# Seed inicial (se necessário)
docker-compose exec backend python -m scripts.seed_data
```

### Contato de Suporte

Se problema não resolvido:

```bash
# Coletar informações de diagnóstico
SUPPORT_DIR=/tmp/crypto_support_$(date +%Y%m%d_%H%M%S)
mkdir -p $SUPPORT_DIR

# Logs
./deploy.sh logs > $SUPPORT_DIR/logs.txt

# Status docker
docker-compose ps > $SUPPORT_DIR/docker_ps.txt
docker stats --no-stream > $SUPPORT_DIR/docker_stats.txt

# Configuração
env | grep -E "MONGO|REDIS|API" > $SUPPORT_DIR/env_summary.txt

# Backup
./backup_db.sh info > $SUPPORT_DIR/backup_status.txt

# Comprimir para suporte
tar -czf $SUPPORT_DIR.tar.gz $SUPPORT_DIR/

echo "📦 Diagnóstico salvo em: $SUPPORT_DIR.tar.gz"
```

---

## ✅ Checklist de Saúde (Executar Diariamente)

```bash
#!/bin/bash
echo "🏥 Health Check - Crypto Trade Hub"

echo "Docker Containers:"
docker-compose ps

echo "\nMemory Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}"

echo "\nDisk Space (Backups):"
du -sh backup_data/

echo "\nRecent Backups:"
ls -lh backup_data/ | tail -5

echo "\nRedis Memory:"
docker-compose exec redis redis-cli info memory | grep used_memory_human

echo "\nMongoDB Replication:"
docker-compose exec mongodb mongosh -u admin -p $MONGO_PASSWORD --eval "rs.status().set"

echo "✅ Check complete!"
```

---

## 📞 Contatos de Emergência

- **Suporte Técnico**: [seu-email]@example.com
- **DevOps Lead**: [seu-nome]
- **Escalação**: [manager]@example.com
- **Status Page**: https://status.example.com

---

## 📝 Changelog Recent

| Data | Problema | Solução |
|------|----------|---------|
| 2025-02-11 | Backups iniciados | Cron agendado 2 AM |
| 2025-02-11 | Alerta de erros ativo | Discord webhook configurado |
| 2025-02-11 | Monitor API iniciado | Check a cada 30 minutos |

---

**Última atualização**: 2025-02-11 14:32 UTC
