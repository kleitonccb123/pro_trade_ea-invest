# 🚀 Integração Rápida - Sistema de Wallet de Afiliados

Guia passo-a-passo para ativar o sistema completo de carteira de afiliados com comissões, carência e saques.

---

## ⚡ 5 Passos de Integração

### ✅ Passo 1: Verificar Dependências

Certifique-se de que tem no `requirements.txt`:

```txt
apscheduler>=3.10.0
motor>=3.1.0
fastapi>=0.95.0
pymongo>=4.3.0
```

**Instalar**:
```bash
pip install -r requirements.txt
```

---

### ✅ Passo 2: Integrar com main.py

Abra `backend/app/main.py` e adicione ao início:

```python
from app.affiliates.wallet_service import AffiliateWalletService
from app.affiliates.scheduler import create_affiliate_scheduler
```

No evento `@app.on_event("startup")`, adicione:

```python
@app.on_event("startup")
async def startup():
    # ... seus startups existentes ...
    
    # 🆕 Inicia scheduler de afiliados
    from app.core.database import get_db_sync  # ou wherever you get db
    db = await get_db()  # Get database instance
    wallet_service = AffiliateWalletService(db)
    scheduler = create_affiliate_scheduler(wallet_service)
    
    try:
        scheduler.start()
        logger.info("✅ Affiliate wallet scheduler iniciado")
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar scheduler: {e}")
```

No evento `@app.on_event("shutdown")`, adicione:

```python
@app.on_event("shutdown")
async def shutdown():
    # ... seus shutdowns existentes ...
    
    # 🆕 Para scheduler
    try:
        scheduler.shutdown()
        logger.info("🛑 Affiliate wallet scheduler finalizado")
    except:
        pass
```

---

### ✅ Passo 3: Ativar Endpoints no Router

Abra `backend/app/affiliates/router.py` - **Já está pronto!** 

Os endpoints estão adicionados:
- `GET /affiliates/wallet` ✅
- `POST /affiliates/withdrawal-method` ✅
- `POST /affiliates/withdraw` ✅
- `GET /affiliates/transactions` ✅

Confirme que o router está registrado em `main.py`:

```python
from app.affiliates.router import router as affiliates_router

app.include_router(affiliates_router, prefix="/api")
```

---

### ✅ Passo 4: Integrar record_commission() na Venda

Quando um usuário compra um plano, registre a comissão:

**Em `backend/app/gamification/router.py`** (ou onde fica o endpoint de compra):

```python
from app.affiliates.wallet_service import AffiliateWalletService

@router.post("/store/purchase-plan")
async def purchase_plan(
    request: PurchasePlanRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    # ... lógica de compra ...
    
    # 🆕 Registra comissão do afiliado (se houver referrer)
    referrer_id = request.referrer_id  # Ou pega do cookie/session
    if referrer_id:
        wallet_service = AffiliateWalletService(db)
        
        buyer_ip = request.client.host  # IP do comprador
        affiliate_ip = get_affiliate_ip_from_session(referrer_id)
        
        success, msg = await wallet_service.record_commission(
            affiliate_user_id=referrer_id,
            referral_id=str(current_user["_id"]),
            sale_amount_usd=request.plan_price_usd,
            commission_rate=0.10,  # 10% padrão
            buyer_ip=buyer_ip,
            affiliate_ip=affiliate_ip
        )
        
        if success:
            logger.info(f"✅ Comissão: {msg}")
        else:
            logger.warning(f"❌ Comissão: {msg}")
    
    return {"success": True, "message": "Plano comprado!"}
```

---

### ✅ Passo 5: Adicionar ao Frontend

Abra `src/pages/Affiliate.tsx` (sua página de afiliados) e importe:

```typescript
import AffiliateDashboard from '../components/affiliate/AffiliateDashboard';

export default function AffiliatePage() {
  return (
    <div>
      {/* Seu layout existente */}
      
      {/* 🆕 Dashboard de carteira */}
      <AffiliateDashboard />
    </div>
  );
}
```

Ou crie uma rota nova:

```typescript
// src/pages/AffiliateWallet.tsx
export { default } from '../components/affiliate/AffiliateDashboard';
```

E em seu router (App.tsx):

```typescript
import AffiliateWallet from './pages/AffiliateWallet';

<Route path="/affiliate-wallet" element={<AffiliateWallet />} />
```

---

## 🎯 Checklist de Ativação

- [ ] Dependências instaladas (apscheduler, motor)
- [ ] Imports adicionados em main.py
- [ ] Scheduler iniciado em `@app.on_event("startup")`
- [ ] Router de afiliados registrado (`app.include_router`)
- [ ] `record_commission()` chamado em evento de compra
- [ ] Dashboard importado/roteado no frontend
- [ ] Backend rodando: `python -m uvicorn app.main:app --reload`
- [ ] Frontend rodando: `npm run dev`
- [ ] Testado: Acessar `http://localhost:8081/affiliate-wallet`

---

## 🧪 Teste Rápido

### 1. Backend Ready?

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/affiliates/wallet
```

Esperado: `{"pending_balance": 0, "available_balance": 0, ...}`

### 2. Frontend Ready?

Acesse no navegador:
```
http://localhost:8081/affiliate-wallet
```

Esperado: Dashboard com 3 cards de saldo

### 3. Comissão Registrada?

```bash
# Simular uma compra via curl
curl -X POST http://localhost:8000/api/store/purchase-plan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer AFFILIATE_TOKEN" \
  -d '{
    "plan_id": "start",
    "referrer_id": "afiliado_123"
  }'

# Depois checar wallet
curl -H "Authorization: Bearer AFFILIATE_TOKEN" \
  http://localhost:8000/api/affiliates/wallet
```

Esperado: `"pending_balance": 1.00` (para plano $9.99)

### 4. Scheduler Rodando?

Veja em `backend_log.txt` ou console:

```
⏰ AFFILIATE JOB: Iniciando verificação de liberação de saldos
✅ JOB COMPLETO: 0 saldos foram liberados
```

Deve aparecer a cada 1 hora! 🕐

---

## 🔗 Estrutura Arquivos Criados

```
backend/app/affiliates/
├── models.py              ✅ Criado - Schemas Pydantic
├── wallet_service.py      ✅ Criado - Lógica principal
├── scheduler.py           ✅ Criado - Jobs agendados
└── router.py              ✅ Modificado - 4 novos endpoints

src/components/affiliate/
└── AffiliateDashboard.tsx ✅ Criado - React Component

/ (root)
└── AFFILIATE_WALLET_IMPLEMENTATION.md ✅ Criado - Docs completas
```

---

## 🚨 Troubleshooting

**Problema**: "ModuleNotFoundError: No module named 'apscheduler'"

**Solução**:
```bash
pip install apscheduler
```

---

**Problema**: Scheduler não inicia

**Solução**: Verifique em `main.py` se `get_db()` funciona:
```python
from app.core.database import get_db

db = get_db()  # Deve retornar AsyncIOMotorDatabase
```

---

**Problema**: Comissão não aparece como pending

**Solução**: Verifique se `record_commission()` está sendo chamado:
```python
logger.info(f"record_commission chamado com: {affiliate_user_id}, {sale_amount}")
```

---

**Problema**: Frontend não carrega dados

**Solução**: Verifique headers de CORS em `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],  # Seu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📞 Suporte Rápido

| Problema | Comando de Debug |
|----------|-----------------|
| Verificar collection MongoDB | `db.affiliate_wallets.find()` |
| Listar jobs scheduler | `scheduler.get_jobs()` |
| Forçar release | `await wallet_service.release_pending_balances()` |
| Reset testes | `db.affiliate_wallets.deleteMany({})`; `db.affiliate_transactions.deleteMany({})` |

---

## ✨ Pronto!

Agora você tem:

✅ **Comissões automáticas** - 10% registradas como pending
✅ **Carência de 7 dias** - Liberadas automaticamente via scheduler
✅ **Saques USD** - Validação de $50 mínimo
✅ **3 Tipos de método** - PIX, Crypto, Banco
✅ **Dashboard completo** - React com Framer Motion
✅ **Auditoria completa** - Transações rastreáveis
✅ **Retry automático** - Saques falhados reprocessam

**Próximo passo**: Conectar com gateway de pagamento real (StarkBank, Stripe, etc)

