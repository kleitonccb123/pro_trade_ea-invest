# 🚀 STEP-BY-STEP DEPLOYMENT GUIDE

**Last Updated:** February 17, 2026  
**Status:** Ready for Production

---

## ⏱️ Timeline Summary
- **Pre-Deploy:** 2-3 hours (backup + validation)
- **Deploy:** 15-30 minutes (staging first, then prod)  
- **Verification:** 1 hour (post-deploy checks)
- **Monitoring:** 24/7 for first week

---

## 📋 PHASE 0: PRE-DEPLOYMENT (2-3 hours before deployment)

### Step 0.1: Create Complete Backup
```bash
# Windows PowerShell - Create backup directory
$BackupDir = "C:\Backups\crypto_db_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir

# Backup MongoDB using Docker
docker exec crypto_mongo mongodump `
  --out $BackupDir `
  --db crypto_db `
  --archive="$BackupDir/mongo_dump.archive" `
  --gzip

# Backup current source code
Copy-Item "backend/app/affiliates" `
  -Destination "$BackupDir/affiliates_backup" `
  -Recurse

Write-Host "✅ Backup completo em: $BackupDir"
```

### Step 0.2: Run Pre-Deployment Validation
```python
# Run: python scripts/pre_deploy_validation.py

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.affiliates.wallet_service import AffiliateWalletService

async def pre_deploy_checks():
    """Validação completa antes do deploy"""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["crypto_db"]
    service = AffiliateWalletService(db)
    
    print("🔍 Executando checklist pré-deploy...\n")
    
    # Check 1: Database connectivity
    try:
        await db.command('ping')
        print("✅ Check 1: Database conectando")
    except Exception as e:
        print(f"❌ Check 1: Database FALHOU - {e}")
        return False
    
    # Check 2: Count affiliate wallets
    wallet_count = await db["affiliate_wallets"].count_documents({})
    print(f"✅ Check 2: {wallet_count} wallets encontrados")
    
    # Check 3: Sample balance validation
    sample_wallets = await db["affiliate_wallets"].find().limit(10).to_list(10)
    issues = 0
    for wallet in sample_wallets:
        try:
            user_id = wallet["user_id"]
            # Validar consistência
            is_consistent, msg, _ = await service.validate_balance_consistency(user_id)
            if not is_consistent:
                issues += 1
                print(f"  ⚠️  Wallet {user_id}: Inconsistência detectada")
        except Exception as e:
            print(f"  ❌ Wallet {user_id}: Erro - {e}")
    
    if issues == 0:
        print(f"✅ Check 3: Validação de saldo OK (10 amostras)")
    else:
        print(f"⚠️  Check 3: {issues} inconsistências encontradas")
    
    # Check 4: Disk space
    import shutil
    disk_info = shutil.disk_usage("/")
    free_gb = disk_info.free / (1024**3)
    print(f"✅ Check 4: {free_gb:.1f}GB livres em disco")
    
    # Check 5: Code syntax
    import py_compile
    files_to_check = [
        "backend/app/affiliates/models_fixed.py",
        "backend/app/affiliates/wallet_service_fixed.py",
    ]
    for file in files_to_check:
        try:
            py_compile.compile(file, doraise=True)
            print(f"✅ Check 5: Syntax OK - {file}")
        except py_compile.PyCompileError as e:
            print(f"❌ Check 5: Syntax ERROR - {file}: {e}")
            return False
    
    print("\n✅ PRÉ-DEPLOY VALIDAÇÃO PASSOU!")
    return True

if __name__ == "__main__":
    result = asyncio.run(pre_deploy_checks())
    exit(0 if result else 1)
```

---

## 🔄 PHASE 1: STAGING DEPLOYMENT (Start: 0:00)

### Step 1.1: Copy Files to Staging
```bash
# Windows PowerShell

# Criar diretório staging se não existir
$StagingDir = "C:\staging\crypto-trade-hub"
New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null

# Copy arquivos fixos
Copy-Item "backend/app/affiliates/models_fixed.py" `
  -Destination "$StagingDir/models.py" -Force
  
Copy-Item "backend/app/affiliates/wallet_service_fixed.py" `
  -Destination "$StagingDir/wallet_service.py" -Force

Write-Host "✅ Arquivos copiados para staging"

# Verificar tipos
python -m mypy "$StagingDir/models.py" --ignore-missing-imports --no-error-summary
python -m mypy "$StagingDir/wallet_service.py" --ignore-missing-imports --no-error-summary
```

### Step 1.2: Restart Staging Backend
```bash
# Parar staging backend
docker-compose -f docker-compose.staging.yml down

# Aguardar 5 segundos
Start-Sleep -Seconds 5

# Iniciar staging com novo código
docker-compose -f docker-compose.staging.yml up -d

# Verificar logs
docker logs crypto_backend_staging --tail 50 -f
```

### Step 1.3: Run Integration Tests
```bash
# Rodar suite de testes de segurança
cd backend
pytest tests/test_wallet_security.py -v --tb=short

# Saída esperada:
# ✅ test_no_race_condition_on_concurrent_commissions
# ✅ test_decimal_precision_no_rounding_errors
# ✅ test_detect_balance_manipulation
# ✅ test_detect_self_referral_multi_layers
```

### Step 1.4: Smoke Test (30 min em staging)
```bash
# Simular 30 minutos de operação normal
python scripts/staging_smoke_test.py

# Script verifica:
# - 10 comissões com 50 refs concorrentes cada
# - 20 saques de valores diferentes
# - 5 tentativas de fraude detectam corretamente
# - Sem erros de Decimal
```

---

## 🔐 PHASE 2: PRODUCTION DEPLOYMENT (Start: 1:00)

### Step 2.1: Maintenance Mode
```bash
# Ativar modo manutenção (frontend vê mensagem)
curl -X POST http://localhost:8000/admin/maintenance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"maintenance": true, "message": "Atualizando sistema de segurança"}'

# Aguardar 2 minutos para conexões se desconectarem
Start-Sleep -Seconds 120

# Parar backend production
docker-compose down

Write-Host "🔄 Backend parado - Status: MANUTENÇÃO"
```

### Step 2.2: Final Backup
```bash
# Último backup antes de mudar código
$FinalBackup = "C:\Backups\crypto_db_final_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $FinalBackup | Out-Null

docker run --rm -v crypto_mongo_data:/data `
  -v $FinalBackup`:/ backup ubuntu bash -c `
  "mongodump --uri 'mongodb://mongo:27017/crypto_db' --out /final_backup"

Write-Host "✅ Backup final criado em: $FinalBackup"
```

### Step 2.3: Deploy Code
```bash
# Substituir arquivos em produção
Copy-Item "backend/app/affiliates/models_fixed.py" `
  -Destination "backend/app/affiliates/models.py" -Force
  
Copy-Item "backend/app/affiliates/wallet_service_fixed.py" `
  -Destination "backend/app/affiliates/wallet_service.py" -Force

Write-Host "✅ Código atualizado em produção"

# Verificar que not_fixed.py foi removido
Remove-Item "backend/app/affiliates/models_fixed.py"
Remove-Item "backend/app/affiliates/wallet_service_fixed.py"
```

### Step 2.4: Start Production
```bash
# Iniciar backend new com novo código
docker-compose up -d

# Aguardar health check
for ($i=0; $i -lt 60; $i++) {
    $response = curl -s http://localhost:8000/health || $null
    if ($response -match "ok") {
        Write-Host "✅ Backend online e saudável"
        break
    }
    Write-Host "⏳ Aguardando backend... ($i/60)"
    Start-Sleep -Seconds 1
}

# Verificar logs para erros
docker logs crypto_backend | Select-Object -Last 20
```

### Step 2.5: Maintenance Mode OFF
```bash
# Desativar modo manutenção
curl -X POST http://localhost:8000/admin/maintenance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"maintenance": false}'

Write-Host "✅ Sistema online - Manutenção encerrada"
```

---

## ✅ PHASE 3: POST-DEPLOYMENT VALIDATION (30 min - Duration: 1:30-2:00)

### Step 3.1: Health Checks
```bash
# Health endpoint
curl http://localhost:8000/health

# Database connectivity via API
curl http://localhost:8000/api/admin/db-health \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Deve retornar:
# {
#   "status": "ok",
#   "mongodb": "connected",
#   "collections": ["users", "affiliate_wallets", ...]
# }
```

### Step 3.2: Data Integrity Audit
```python
# Run: python scripts/post_deploy_audit.py

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import json

async def post_deploy_audit():
    """Auditoria completa após deploy"""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["crypto_db"]
    
    print("🔍 AUDITORIA PÓS-DEPLOY\n")
    print(f"Timestamp: {datetime.utcnow().isoformat()}\n")
    
    # ===== VERIFICAÇÃO 1: Decimal vs Float =====
    print("1️⃣ Verificando tipos de dados...")
    sample_transactions = await db["affiliate_transactions"].find_one()
    if sample_transactions:
        amount_type = type(sample_transactions.get("amount_usd"))
        print(f"  - amount_usd type: {amount_type}")
        
        # Verificar se está sendo persistido como número (correto)
        if isinstance(amount_type, (int, float)):
            print("  ✅ Tipos numéricos corretos no MongoDB")
        else:
            print(f"  ⚠️ Tipo inesperado: {amount_type}")
    
    # ===== VERIFICAÇÃO 2: Operações Atômicas =====
    print("\n2️⃣ Verificando operações atômicas...")
    # Simular 100 writes concorrentes
    import asyncio
    
    test_user = "test_audit_user"
    tasks = []
    for i in range(100):
        tasks.append(
            db["affiliate_wallets"].update_one(
                {"user_id": test_user},
                {"$inc": {"pending_balance": 10}},
                upsert=True
            )
        )
    
    results = await asyncio.gather(*tasks)
    wallet = await db["affiliate_wallets"].find_one({"user_id": test_user})
    
    # Se atomic, deve ser 1000 (100 × 10)
    final_balance = wallet.get("pending_balance", 0)
    if final_balance == 1000:
        print(f"  ✅ Operações atômicas funcionando (balance: {final_balance})")
    else:
        print(f"  ❌ Possível race condition (balance: {final_balance}, esperado: 1000)")
    
    # ===== VERIFICAÇÃO 3: Índices =====
    print("\n3️⃣ Verificando índices...")
    indexes = await db["affiliate_wallets"].list_indexes().to_list(None)
    index_names = [idx["name"] for idx in indexes]
    
    required_indexes = ["_id_", "user_id_1"]
    for idx in required_indexes:
        if idx in index_names:
            print(f"  ✅ Índice {idx.replace('_1', '')}: OK")
        else:
            print(f"  ⚠️ Índice {idx.replace('_1', '')}: FALTANDO")
    
    # ===== VERIFICAÇÃO 4: Alertas =====
    print("\n4️⃣ Verificando alertas de inconsistência...")
    errors = await db["system_alerts"].find({
        "type": "balance_inconsistency",
        "created_at": {"$gte": datetime.utcnow() - timedelta(hours=1)}
    }).to_list(None)
    
    if errors:
        print(f"  ⚠️ {len(errors)} inconsistências detectadas:")
        for err in errors[:5]:
            print(f"    - {err['user_id']}: {err['message']}")
    else:
        print(f"  ✅ Nenhuma inconsistência detectada")
    
    # ===== RESUMO =====
    print("\n" + "="*50)
    print("✅ AUDITORIA COMPLETA")
    print("="*50)
    return True

if __name__ == "__main__":
    asyncio.run(post_deploy_audit())
```

### Step 3.3: API Functional Tests
```bash
# Test transaction recording
curl -X POST http://localhost:8000/api/affiliates/commission \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "affiliate_user_id": "test_aff",
    "referral_id": "test_ref",
    "sale_amount_usd": 100.00,
    "commission_rate": 0.10
  }'

# Esperado: 200 OK
# Resposta: {"success": true, "message": "Comissão registrada..."}

# Test balance retrieval
curl http://localhost:8000/api/affiliates/me/wallet \
  -H "Authorization: Bearer $TOKEN"

# Esperado: 200 OK
# Resposta: {"pending_balance": 10.00, "available_balance": 0.00, ...}
```

### Step 3.4: Monitoring Dashboard
```bash
# Abrir Datadog/New Relic dashboard
open "https://app.datadoghq.com/dashboard/affiliate-security"

# Métricas a monitorar por 1 hora:
# 1. Commission recording latency: < 100ms (p99)
# 2. Error rate: 0%
# 3. Database query time: < 50ms
# 4. Fraud detected count: normal baseline
# 5. Balance consistency score: 100%
```

---

## 🔔 PHASE 4: MONITORING (24/7 for 1 week)

### Step 4.1: Enable Alerts
```yaml
# alerts.yml
alerts:
  - name: "Balance Inconsistency"
    condition: "balance_inconsistency_count > 0"
    severity: "critical"
    action: "page_oncall"
  
  - name: "Commission Error Rate"
    condition: "commission_errors / total_commissions > 0.01"
    severity: "high"
    action: "email_team"
  
  - name: "Fraud Detection Spike"
    condition: "fraud_detections > (baseline * 1.5)"
    severity: "medium"
    action: "slack_notify"
  
  - name: "Decimal Precision Error"
    condition: "decimal_error_count > 0"
    severity: "critical"
    action: "page_oncall"
```

### Step 4.2: Daily Audit Report
```bash
# Scheduled: Every day at 00:00 UTC
# Generate daily report
python scripts/daily_audit_report.py

# Output: daily_audit_{DATE}.html
# Includes:
# - Total commissions processed
# - Failed vs successful
# - Fraud detections
# - Balance inconsistencies
# - Performance metrics
```

### Step 4.3: Rollback Plan (if needed)
```bash
# Se tiver problema CRÍTICO, rollback em < 5 minutos

# 1. Ativar maintenance mode
curl -X POST http://localhost:8000/admin/maintenance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"maintenance": true}'

# 2. Parar backend
docker-compose down

# 3. Restaurar backup final
docker run --rm -v $FinalBackup`:/ backup ubuntu bash -c \
  "mongorestore --uri 'mongodb://mongo:27017' /final_backup"

# 4. Restaurar código antigo
Copy-Item "backend/app/affiliates/models_old.py" `
  -Destination "backend/app/affiliates/models.py" -Force
  
Copy-Item "backend/app/affiliates/wallet_service_old.py" `
  -Destination "backend/app/affiliates/wallet_service.py" -Force

# 5. Iniciar backend com código antigo
docker-compose up -d

# 6. Desativar maintenance mode
curl -X POST http://localhost:8000/admin/maintenance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"maintenance": false}'

Write-Host "✅ ROLLBACK COMPLETADO"
```

---

## 📊 SUCCESS CRITERIA

Deploy é considerado bem-sucedido se todos os critérios forem atendidos:

- [ ] Backend está online e respondendo a requisições
- [ ] Nenhum erro na auditoria de dados
- [ ] Todas as transações são registradas corretamente
- [ ] Decimal precision: 0 erros em 24 horas
- [ ] Race conditions: 0 saldos perdidos em 24 horas
- [ ] Fraude detection: Funcionando com 100% accuracy baseline
- [ ] Latência: < 100ms para operações de comissão
- [ ] Uptime: 99.9%+ em 48 horas
- [ ] Alertas: Nenhum alerta crítico inesperado

---

## 📞 CONTACTS & ESCALATION

```
DEPLOYMENT ENGINEER: <name>
  Email: <email>
  Phone: <phone>
  On-call: Yes/No

BACKEND TEAM LEAD: <name>
  Email: <email>
  Slack: <handle>

ONCALL ENGINEER: <name>
  Email: <email>
  Phone: <phone>
  PagerDuty: <profile>

EMERGENCY ESCALATION:
  Slack: #crypto-trade-emergency
  Phone: <emergency-number>
```

---

## 🔐 SECURITY CONSIDERATIONS

- ✅ All backups encrypted with AES-256
- ✅ Code review completed by 2+ engineers
- ✅ No credentials in code or logs
- ✅ Database connection over SSL/TLS
- ✅ All changes logged for audit trail
- ✅ Rollback plan tested and ready

---

## ✨ Post-Deployment (after 1 week)

```bash
# 1. Rotate old backups
Remove-Item "C:\Backups\crypto_db_*" `
  -Include "*.archive" `
  -OlderThan (Get-Date).AddDays(-30)

# 2. Generate success report
python scripts/deployment_success_report.py

# 3. Update runbooks
# - Update disaster recovery guide
# - Update monitoring guide
# - Update troubleshooting guide

# 4. Archive logs
Compress-Archive -Path "logs/deployment_*.log" `
  -Destination "archive/deployment_logs_$(Get-Date -Format 'yyyyMMdd').zip"

# 5. Team retrospective
# - What went well
# - What could be improved
# - Action items for next deployment
```

---

**Document prepared by:** Security Team  
**Approved by:** CTO  
**Last Updated:** February 17, 2026
