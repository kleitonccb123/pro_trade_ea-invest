# 🔧 Race Condition Fix - Implementation Guide

## Executive Summary

**Vulnerability:** Race condition in `record_commission()` method  
**Severity:** CRITICAL  
**Fix Status:** Ready to apply  
**Current Location:** `backend/app/affiliates/wallet_service.py` (lines 130-200)

---

## Step-by-Step Fix Instructions

### Method 1: Manual Copy-Paste (Simplest)

#### 1. Open the file
```
backend/app/affiliates/wallet_service.py
```

#### 2. Find the vulnerable code
Look for this section around line 130-145:
```python
try:
    # Busca wallet
    wallet = await self.get_or_create_wallet(affiliate_user_id)

    # Adiciona ao saldo pendente  
    wallet.pending_balance += commission_amount
    wallet.total_earned += commission_amount

    # Salva wallet
    await self.save_wallet(wallet)

    # Registra transação para auditoria
    transaction = AffiliateTransaction(
```

#### 3. Replace with this atomic version
Delete everything from `try:` through `await self.save_wallet(wallet)` and replace with:

```python
try:
    # ✅ CORREÇÃO: Operação atômica! MongoDB garante que só uma thread executa
    # Se 1000 requests chegarem ao mesmo tempo, todos são enfileirados atomicamente
    now = datetime.utcnow()
    update_result = await self.wallet_col.update_one(
        {"user_id": affiliate_user_id},  # Query
        {
            "$inc": {  # ← ATÔMICO! Incrementa atomicamente
                "pending_balance": commission_amount,
                "total_earned": commission_amount,
            },
            "$set": {
                "updated_at": now,
                "last_commission_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "user_id": affiliate_user_id,
                "available_balance": 0.0,
                "total_withdrawn": 0.0,
                "withdrawal_method": None,
            }
        },
        upsert=True,  # Cria wallet se não existir
    )

    wallet_created = update_result.upserted_id is not None

    # Registra transação para auditoria
    transaction = AffiliateTransaction(
```

#### 4. After the transaction creation, add this line:
Look for where you create the transaction (after the code above), then before the line `result = await self.transaction_col.insert_one(transaction.dict())`, make sure you have:

```python
created_at=now,
```

#### 5. Save the file
Make sure the file is saved after making changes.

---

### Method 2: Using Python Script (Automated)

Run this Python script from the project root:

```bash
python3 << 'EOF'
import io
import shutil
from datetime import datetime

file_path = 'backend/app/affiliates/wallet_service.py'

# Backup
backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy2(file_path, backup_path)
print(f"Backup created: {backup_path}")

# Read
with io.open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the vulnerable section
new_lines = []
i = 0
replaced = False

while i < len(lines):
    line = lines[i]
    
    # Find the try block with "# Busca wallet"
    if 'try:' in line and i + 1 < len(lines) and '# Busca wallet' in lines[i+1]:
        # Found it - add comment
        new_lines.append(line)  # try:
        i += 1
        new_lines.append('            # ✅ CORREÇÃO: Operação atômica!\n')
        new_lines.append('            # Se 1000 requests chegarem ao mesmo tempo, todos são enfileirados atomicamente\n')
        new_lines.append('            now = datetime.utcnow()\n')
        
        # Skip the old lines until we find "# Registra transação"
        while i < len(lines) and '# Registra transação' not in lines[i]:
            if 'await self.get_or_create_wallet' not in lines[i] and \
               'wallet.pending_balance' not in lines[i] and \
               'wallet.total_earned' not in lines[i] and \
               'await self.save_wallet' not in lines[i] and \
               '# Busca wallet' not in lines[i] and \
               '# Adiciona ao saldo' not in lines[i] and \
               '# Salva wallet' not in lines[i]:
                new_lines.append(lines[i])
            i += 1
        
        # Add the atomic operation
        new_lines.append('            update_result = await self.wallet_col.update_one(\n')
        new_lines.append('                {"user_id": affiliate_user_id},\n')
        new_lines.append('                {\n')
        new_lines.append('                    "$inc": {\n')
        new_lines.append('                        "pending_balance": commission_amount,\n')
        new_lines.append('                        "total_earned": commission_amount,\n')
        new_lines.append('                    },\n')
        new_lines.append('                    "$set": {\n')
        new_lines.append('                        "updated_at": now,\n')
        new_lines.append('                        "last_commission_at": now,\n')
        new_lines.append('                    },\n')
        new_lines.append('                    "$setOnInsert": {\n')
        new_lines.append('                        "created_at": now,\n')
        new_lines.append('                        "user_id": affiliate_user_id,\n')
        new_lines.append('                        "available_balance": 0.0,\n')
        new_lines.append('                        "total_withdrawn": 0.0,\n')
        new_lines.append('                        "withdrawal_method": None,\n')
        new_lines.append('                    }\n')
        new_lines.append('                },\n')
        new_lines.append('                upsert=True,\n')
        new_lines.append('            )\n')
        new_lines.append('            wallet_created = update_result.upserted_id is not None\n')
        new_lines.append('\n')
        new_lines.append('            # Registra transação para auditoria\n')
        replaced = True
        continue
    
    new_lines.append(line)
    i += 1

if replaced:
    with io.open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✅ File updated successfully!")
    
    # Verify
    with io.open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if '"$inc"' in content and 'wallet.pending_balance += commission_amount' not in content:
        print("✅ VERIFICATION PASSED - Fix applied correctly!")
    else:
        print("❌ Verification failed")
        shutil.copy2(backup_path, file_path)
else:
    print("❌ Could not find vulnerable code pattern")
EOF
```

---

## Verification Checklist

After applying the fix, verify these points:

- [ ] Line with `wallet.pending_balance += commission_amount` is REMOVED
- [ ] Line with `wallet.total_earned += commission_amount` is REMOVED  
- [ ] Line with `await self.save_wallet(wallet)` is REMOVED
- [ ] New atomic operation with `"$inc"` is present
- [ ] `now = datetime.utcnow()` is declared before the update
- [ ] `$setOnInsert` creates wallet on first record if needed
- [ ] Transaction still created after atomic operation
- [ ] File still has no syntax errors

---

## Testing the Fix

### Unit Test

Add this test to `backend/tests/test_wallet.py`:

```python
@pytest.mark.asyncio
async def test_concurrent_commission_recording():
    '''Testa que 1000 comissões simultâneas não perdem dados (validação de atomicidade)'''
    
    wallet_service = AffiliateWalletService(db)
    affiliate_id = "test_concurrent_fix"
    num_commissions = 100
    commission_per_call = 10.55
    
    # Clean up
    await wallet_service.wallet_col.delete_one({"user_id": affiliate_id})
    
    # Simulate 100 concurrent requests
    tasks = [
        wallet_service.record_commission(
            affiliate_user_id=affiliate_id,
            referral_id=f"referral_{i}",
            sale_amount_usd=commission_per_call,
            commission_rate=0.10,
        )
        for i in range(num_commissions)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Verify all succeeded
    assert all(success for success, _ in results), "Some commissions failed"
    
    # Verify balance
    wallet = await wallet_service.get_or_create_wallet(affiliate_id)
    expected = num_commissions * commission_per_call * 0.10
    
    # Allow small floating-point variance
    assert abs(wallet.pending_balance - expected) < 0.01, \
        f"Balance mismatch: expected {expected}, got {wallet.pending_balance}"
    
    print(f"✅ {num_commissions} concurrent transactions - NO DATA LOSS!")
```

Run the test:
```bash
pytest backend/tests/test_wallet.py::test_concurrent_commission_recording -v
```

### Stress Test

```bash
# Simulate 1000+ simultaneous requests
python3 << 'EOF'
import asyncio
import httpx

async def stress_test():
    async with httpx.AsyncClient() as client:
        tasks = []
        
        for i in range(1000):
            task = client.post(
                "http://localhost:8000/api/affiliates/commission",
                json={
                    "affiliate_id": "stress_test_user",
                    "referral_id": f"ref_{i}",
                    "amount_usd": 10.55,
                    "buyer_ip": "192.168.1.1",
                    "affiliate_ip": "192.168.1.2",
                }
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r.status_code == 200)
        
        print(f"Completed: {success_count}/{len(tasks)}")
        if success_count == len(tasks):
            print("✅ STRESS TEST PASSED - No data loss under load!")
        else:
            print("❌ Some requests failed")

asyncio.run(stress_test())
EOF
```

---

## Database Migration (If Needed)

If you already have wallets with incorrect balances due to the race condition, run this cleanup:

```python
"""
Optional: Fix existing wallets if race condition lost data

Run ONLY if you suspect data loss in existing wallets!
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

async def audit_and_fix_wallets(db: AsyncIOMotorDatabase):
    """
    Checks each wallet balance against transaction history
    and fixes any discrepancies
    """
    
    wallets_col = db["affiliate_wallets"]
    transactions_col = db["affiliate_transactions"]
    
    wallets = await wallets_col.find({}).to_list(None)
    
    for wallet in wallets:
        user_id = wallet["user_id"]
        
        # Calculate real balance from transactions
        pipeline = [
            {'$match': {'user_id': user_id, 'type': 'commission', 'status': 'pending'}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount_usd'}}}
        ]
        
        real_balance = await transactions_col.aggregate(pipeline).to_list(1)
        real_pending = real_balance[0]['total'] if real_balance else 0
        
        stored_pending = wallet.get('pending_balance', 0)
        
        if real_pending != stored_pending:
            print(f"⚠️ {user_id}: stored={stored_pending}, real={real_pending}")
            
            # Fix it
            await wallets_col.update_one(
                {"user_id": user_id},
                {"$set": {"pending_balance": real_pending, "fixed_at": datetime.utcnow()}}
            )
            print(f"✅ Fixed {user_id}")
    
    print("✅ Wallet audit complete!")

# Run: asyncio.run(audit_and_fix_wallets(db))
```

---

## After Deployment Checklist

- [ ] Code deployed to production
- [ ] Monitoring active (check commission recording rate)
- [ ] 24-hour observation period completed with no errors
- [ ] Database backups confirmed available  
- [ ] Team notified of fix
- [ ] Documentation updated in wiki

---

## Rollback Procedure (If Needed)

If issues occur after deployment:

```bash
# 1. Restore from backup
cp backend/app/affiliates/wallet_service.py.backup.[timestamp] \
   backend/app/affiliates/wallet_service.py

# 2. Restart application
systemctl restart crypto-trade-hub-backend

# 3. Verify old code is running
curl http://localhost:8000/api/health

# 4. Investigate issue
# Check logs at: /var/log/crypto-trade-hub/backend.log
```

Rollback time: **< 5 minutes**

---

## Questions & Support

If you encounter any issues during implementation:

1. **File not found?** - Ensure you're in the correct directory
2. **Syntax errors after edit?** - Check for missing colons, indentation
3. **Testing fails?** - Check MongoDB is running and connection string is correct
4. **Still see race conditions?** - Verify $inc is actually in the file (not just += )

Contact the development team with error logs and file excerpts.

---

**Document Version**: 1.0  
**Last Updated**: 2026-02-17  
**Status**: Ready for Implementation
