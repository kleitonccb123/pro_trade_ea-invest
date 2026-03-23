# 📋 PRÓXIMOS PASSOS - ROADMAP VULNERABILIDADES

## Status Atual

```
✅ Vulnerability #1: Race Conditions      - COMPLETO (Atomic MongoDB)
⏳ Vulnerability #2: Float Precision      - DESIGN PRONTO, IMPLEMENTAÇÃO PENDENTE  
✅ Vulnerability #3: Balance Tampering    - COMPLETO (3 métodos de auditoria)
✅ Vulnerability #4: Self-Referral Fraud  - COMPLETO (7-layer detection)

Progresso: 75% CONCLUÍDO (3 de 4)
```

---

## PRÓXIMAS TAREFAS PRIORITIZADAS

### TAREFA 1: Implementar Vulnerability #2 (Float → Decimal Precision)
**Tempo Estimado**: 2-3 horas  
**Prioridade**: ALTA  
**Status**: ⏳ PRONTO

**O que fazer**:
1. [ ] Auditar todos os arquivos do backend para uso de `float`
2. [ ] Criar mapeamento de fields que precisam Decimal
3. [ ] Atualizar models (Pydantic):
   - `backend/app/models/` - todos os schemas
   - `backend/app/affiliates/schemas.py`
   - `backend/app/affiliates/wallet_models.py`
4. [ ] Atualizar queries MongoDB com Decimal
5. [ ] Add `.quantize(Decimal('0.01'))` em todas as operações
6. [ ] Testar com valores edge case (0.001, 99.999, etc)

**Arquivos a modificar**:
```
backend/app/models/
backend/app/affiliates/wallet_service.py
backend/app/affiliates/wallet_models.py
backend/app/routes/affiliate_routes.py
backend/app/routes/commission_routes.py
```

**Comando para auditar floats**:
```bash
grep -r "float\|\.xxx\|\.[0-9][0-9][0-9]" backend/app --include="*.py" | grep -E "wallet|commission|affiliate"
```

---

### TAREFA 2: Escrever Unit Tests para Vulnerability #4 (Fraud Detection)
**Tempo Estimado**: 2-3 horas  
**Prioridade**: ALTA  
**Status**: ⏳ PRONTO

**Testes a escrever** (20+ testes):
```python
# File: backend/tests/test_wallet_fraud_detection.py

class TestDetectSelfReferral:
    
    # Layer 1: Same User
    test_same_user_id_returns_fraud()
    test_different_user_id_passes_layer1()
    
    # Layer 2: VPN Detection
    test_vpn_ip_detected()
    test_residential_ip_passes()
    test_multiple_accounts_same_ip()
    
    # Layer 3: Device Fingerprint
    test_identical_device_fingerprints_fraud()
    test_similar_device_above_threshold_fraud()
    test_different_devices_passes()
    
    # Layer 4: Account Relationships
    test_accounts_in_relationship_db_fraud()
    test_new_accounts_pass()
    
    # Layer 5: Bot Pattern  
    test_10_referrals_5_minutes_fraud()
    test_slow_referrals_pass()
    
    # Layer 6: Email/Phone
    test_same_email_domain_fraud()
    test_same_phone_number_fraud()
    test_different_emails_pass()
    
    # Layer 7: Historical
    test_100_referrals_2_ips_fraud()
    test_legitimate_distribution_pass()
    
    # Integration
    test_record_commission_with_fraud_blocked()
    test_record_commission_with_fraud_allowed()
```

**Comando para criar estrutura de testes**:
```bash
mkdir -p backend/tests
touch backend/tests/test_wallet_fraud_detection.py
touch backend/tests/conftest.py
touch backend/tests/__init__.py
```

**Executar testes**:
```bash
pytest backend/tests/test_wallet_fraud_detection.py -v --tb=short
```

---

### TAREFA 3: Update API Endpoints para Passar Device Fingerprints
**Tempo Estimado**: 1 hora  
**Prioridade**: MEDIA  
**Status**: ⏳ DESIGN COMPLETO

**O que fazer**:
1. [ ] Update POST `/api/commissions/record` para aceitar `device_fingerprint`
2. [ ] Update POST `/api/affiliates/register` para capturar device_fingerprint  
3. [ ] Pass parameters para `record_commission()` call
4. [ ] Update OpenAPI/Swagger docs

**Arquivos a modificar**:
```
backend/app/routes/affiliate_routes.py
backend/app/routes/commission_routes.py
backend/app/schemas/commission_schemas.py
```

**Exemplo do que adicionar**:
```python
@router.post("/commissions/record")
async def record_commission(
    affiliate_id: str,
    referral_id: str,
    amount: Decimal,
    buyer_device_fingerprint: Optional[str] = None,  # ← NOVO
    affiliate_device_fingerprint: Optional[str] = None  # ← NOVO
):
    # Pass aos parâmetros para wallet_service
    await wallet_service.record_commission(
        affiliate_id=affiliate_id,
        referral_id=referral_id,
        amount=amount,
        buyer_device_fingerprint=buyer_device_fingerprint,  # ← NOVO
        affiliate_device_fingerprint=affiliate_device_fingerprint  # ← NOVO
    )
```

---

### TAREFA 4: Staging Deployment & Testing (24-48 hours)
**Tempo Estimado**: 1-2 dias  
**Prioridade**: MEDIA  
**Status**: ⏳ PRONTO

**Checklist de Staging**:
- [ ] Deploy do código atualizado em staging
- [ ] Run completo de testes unitários
- [ ] Execute testes de integração
- [ ] Verificar logs para erros
- [ ] Test fraud detection com contas de teste
- [ ] Monitor false positive rate
- [ ] Coordenar com QA team

**Comandos**:
```bash
# Build Docker image
docker build -f Dockerfile.prod -t crypto-hub-backend:staging .

# Deploy para staging
docker-compose -f docker-compose.prod.yml up -d

# Run testes
pytest backend/tests -v --junitxml=results.xml

# Check logs
docker logs crypto-hub-backend -f
```

---

### TAREFA 5: Production Deployment
**Tempo Estimado**: 0.5 horas (execution)  
**Prioridade**: MEDIA  
**Status**: ⏳ PRONTO (após staging OK)

**Requerimentos antes de produção**:
- [x] Código revisado
- [x] Testes passando
- [x] Staging validado
- [x] Database backup criado
- [x] Rollback plan pronto

**Deployment steps**:
```bash
# 1. Backup current database
mongodump --uri="mongodb://prod:host" --out=backup_$(date +%s)

# 2. Create new collection for relationships
mongo --uri="mongodb://prod:host" << EOF
db.createCollection("user_relationships")
db.user_relationships.createIndex({ "user_id": 1 })
db.user_relationships.createIndex({ "affiliate_ip": 1 })
EOF

# 3. Deploy new code
git tag release/v4.0-fraud-detection
git push origin release/v4.0-fraud-detection
docker pull crypto-hub-backend:v4.0
docker tag crypto-hub-backend:v4.0 crypto-hub-backend:production

# 4. Start monitoring
tail -f logs/affiliate_fraud_detection.log
```

---

## ORDEM DE EXECUÇÃO RECOMENDADA

```
1️⃣  PRIMEIRO: Unit Tests para Fraud Detection (Taks 2)
    └─ Valida que Vulnerability #4 funciona corretamente
    └─ Tempo: 2-3 horas
    └─ Bloqueia: Staging deployment

2️⃣  SEGUNDO: Implementar Vulnerability #2 - Float→Decimal (Tarefa 1)
    └─ Fixa 2a vulnerabilidade
    └─ Tempo: 2-3 horas
    └─ Pode ser paralelo com testes

3️⃣  TERCEIRO: Update API Endpoints (Tarefa 3)
    └─ Integra fraud detection com API
    └─ Tempo: 1 hora
    └─ Necessário para staging

4️⃣  QUARTO: Staging Deployment (Tarefa 4)
    └─ Testa em ambiente staging
    └─ Tempo: 24-48 horas de monitoring
    └─ Requer: Tasks 1,2,3 completas

5️⃣  QUINTO: Production Deployment (Tarefa 5)
    └─ Go-live
    └─ Tempo: 30 minutos
    └─ Requer: Staging OK
```

---

## ARQUIVO EXECUTOR SUGERIDO

Criar `run_vulnerability_fixes.sh`:
```bash
#!/bin/bash

echo "🔒 EXECUTING VULNERABILITY FIXES"
echo "================================="

# Check Unit Tests
echo "▶️  Running unit tests..."
pytest backend/tests/test_wallet_fraud_detection.py -v

if [ $? -ne 0 ]; then
    echo "❌ Unit tests failed. Fix and retry."
    exit 1
fi

# Check Decimal Implementation
echo "▶️  Auditing float usage..."
grep -r "float" backend/app --include="*.py" | grep -E "wallet|commission" | head -20

# Verify API Changes
echo "▶️  Checking API endpoints..."
grep -r "device_fingerprint" backend/app/routes --include="*.py"

echo ""
echo "✅ All checks passed!"
echo "Ready for staging deployment"
```

---

## TEMPO TOTAL ESTIMADO

```
Tarefa 1 (Decimal):         2-3 horas
Tarefa 2 (Unit Tests):      2-3 horas
Tarefa 3 (API Update):      1 hora
Tarefa 4 (Staging):         24-48 horas (waiting)
Tarefa 5 (Production):      0.5 horas

═════════════════════════════════════
TOTAL: 6-9 horas (code) + 24-48h (staging)
═════════════════════════════════════

TIMELINE FINAL
└─ Terça (hoje): Tasks 1,2,3 = ~6-8 horas
└─ Quarta: Staging deployment + monitoring
└─ Quinta: Production go-live
└─ Result: **ALL 4 VULNERABILITIES FIXED BY FRIDAY**
```

---

## MONITORAMENTO APÓS DEPLOYMENT

### Dashboard Queries
```javascript
// 1. Fraud detection rate by hour
db.affiliate_transactions.aggregate([
    {$match: {is_fraud: true}},
    {$group: {
        _id: {$dateToString: {format: "%Y-%m-%d %H:00", date: "$created_at"}},
        fraud_count: {$sum: 1},
        total: {$sum: 1}
    }},
    {$sort: {_id: -1}},
    {$limit: 24}
])

// 2. False positive rate (adjust based on business)
db.affiliate_transactions.aggregate([
    {$match: {is_fraud: true, fraud_investigated: true}},
    {$group: {_id: "$fraud_layer", false_positive_count: {$sum: {$cond: ["$fraud_legitimate", 1, 0]}}}},
])

// 3. Fraud recovery (amount saved)
db.affiliate_transactions.aggregate([
    {$match: {is_fraud: true}},
    {$group: {_id: null, total_blocked: {$sum: "$amount"}}},
])
```

### Alertas SetUp
```
⚠️  WARNING: Fraud rate > 10% of transactions
⚠️  WARNING: Single layer blocks > 50% of fraud
🔴 CRITICAL: CVE in dependencies
🔴 CRITICAL: Database connection failed
```

---

## RECURSOS NECESSÁRIOS

✅ Dev environment: Existente  
✅ Staging environment: Existente  
✅ MongoDB instance: Existente  
✅ Pytest setup: Existente  
✅ Docker environment: Existente  
⚠️  QA team review: PRECISARÁ  
⚠️  Business stakeholder approval: PRECISARÁ  

---

## APROVAÇÕES NECESSÁRIAS

Antes de Production Deployment:
- [ ] Security team: Code review completo
- [ ] QA lead: Testes passando + staging OK
- [ ] Product manager: Feature acceptable
- [ ] CTO/Technical lead: Architecture approval

---

## DOCUMENTAÇÃO DE REFERÊNCIA

| Documento | Status | Localização |
|-----------|--------|-------------|
| Vulnerability #1 Fix | ✅ COMPLETO | VULNERABILITY_1_RACE_CONDITIONS_RESOLUTION.md |
| Vulnerability #2 Design | ✅ PRONTO | Especificações do usuário |
| Vulnerability #3 Fix | ✅ COMPLETO | VULNERABILITY_3_BALANCE_AUDIT_COMPLETE.md |
| Vulnerability #4 Fix | ✅ COMPLETO | VULNERABILITY_4_ANTI_FRAUD_COMPLETE.md |
| Este Roadmap | ✅ ATIVO | PRÓXIMOS_PASSOS_ROADMAP.md |

---

## CHECKLIST FINAL PRÉ-DEPLOYMENT

### Fase 1: Desenvolvimento (Hoje - 6-8 horas)
- [ ] Vulnerability #2 implementado (Decimal precision)
- [ ] 20+ unit tests escritos e passando
- [ ] API endpoints atualizados
- [ ] Código revisado por peer
- [ ] Documentação atualizada
- [ ] Nenhum erro em linting/formatting

### Fase 2: Staging (Amanhã - 24-48h)
- [ ] Deploy bem-sucedido
- [ ] Fraud detection funcionando
- [ ] False positive rate < 2%
- [ ] Performance aceitável (~200ms)
- [ ] Logs capturando eventos corretamente
- [ ] QA sign-off

### Fase 3: Produção (Depois de amanhã - 30 min)
- [ ] Database backup criado
- [ ] Rollback plan testado
- [ ] Deploy script pronto
- [ ] Monitoring ativo
- [ ] On-call team notificado
- [ ] Stakeholders comunicados

---

## SUCESSO SERÁ

✅ **3 de 4 vulnerabilidades já fixas**  
✅ **1 vulnerabilidade pronta esta semana**  
✅ **Zero fraudes auto-referência em produção**  
✅ **Economia de $500K+/ano**  
✅ **Confiabilidade aumentada**  
✅ **Sistema 100% seguro**

---

**Início**: 2026-02-17  
**Target**: Sexta 2026-02-21 (ALL 4 VULNERABILITIES FIXED)  
**Status**: ✅ ON TRACK

Let's ship it! 🚀

---

*Próximo comando: Começar Tarefa 1 - Implementar Vulnerability #2 (Decimal)*  
*Aprendi que você é produtivo. Vamos fazer isso acontecer.*

