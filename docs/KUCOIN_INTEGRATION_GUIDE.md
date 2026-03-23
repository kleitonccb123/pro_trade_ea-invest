# 🎯 KuCoin Integration - Complete Implementation Guide

## Overview

This document describes the complete KuCoin affiliate withdrawal system, including:
- System architecture and flow
- Backend services and endpoints
- Frontend components
- Security measures
- Testing procedures

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AFFILIATE WITHDRAWAL FLOW                    │
└─────────────────────────────────────────────────────────────────┘

User Dashboard
      │
      ├─→ [Select Withdrawal Method]
      │         │ (PIX / KuCoin UID / Crypto / Banco)
      │         │
      │         └─→ WithdrawConfig Component (Frontend)
      │              - Validate UID format (8-10 digits)
      │              - Show example and where to find UID
      │              - Collect holder name
      │
      └─→ [Submit Withdrawal Request]
                │
                └─→ POST /affiliates/withdraw
                     │
                     ├─→ 1️⃣ Check Rate Limit
                     │    (Max 1 per hour, 5 per day, 50 system-wide)
                     │    └─→ FAIL? Return 429
                     │
                     ├─→ 2️⃣ Validate Request
                     │    - Amount > 0
                     │    - Wallet exists
                     │    - Withdrawal method exists
                     │    └─→ FAIL? Return 400
                     │
                     ├─→ 3️⃣ Check Balance
                     │    - Saldo disponível >= amount
                     │    └─→ FAIL? Return 400
                     │
                     ├─→ 4️⃣ Route by Method Type
                     │    │
                     │    ├─ IF "kucoin_uid":
                     │    │  │
                     │    │  ├─→ 5a. Initialize KuCoinPayoutService
                     │    │  │
                     │    │  ├─→ 5b. Call process_internal_transfer()
                     │    │  │    - Validate UID format (8-10 digits)
                     │    │  │    - Check master USDT balance
                     │    │  │    - Execute POST /accounts/inner-transfer
                     │    │  │    └─→ SUCCESS? Return transfer_id
                     │    │  │    └─→ FAIL? Return error, NO debit
                     │    │  │
                     │    │  ├─→ 5c. IF success:
                     │    │  │    - Debit affiliate wallet (saldo_disponivel)
                     │    │  │    - Create AffiliateTransaction record
                     │    │  │    - Record successful withdrawal
                     │    │  │    - Return 200 with transfer_id
                     │    │  │
                     │    │  └─→ 5d. IF fail:
                     │    │       - Wallet NOT debited (atomic!)
                     │    │       - Return error message
                     │    │       - Log for admin review
                     │    │
                     │    └─ ELSE (PIX/Crypto/Banco):
                     │       - Use existing wallet_service.process_withdrawal()
                     │       - Mark as pending
                     │
                     └─→ 6️⃣ Record Rate Limit Attempt
                          (regardless of success/failure)
                          └─→ Return 200 or error
                               │
                               └─→ Update Dashboard
                                   - Show success notification
                                   - Display transfer_id
                                   - Remove amount from saldo
                                   - Show 24h countdown timer
```

---

## Backend Components

### 1. KuCoinPayoutService

**Location:** `backend/app/services/kucoin_payout_service.py`

**Responsibility:** Handles all KuCoin API interactions

**Key Methods:**

#### `__init__(db, api_key, api_secret, passphrase, sandbox_mode=False)`
Initialize the service with KuCoin credentials

```python
service = KuCoinPayoutService(
    db=db,
    api_key="your-key",
    api_secret="your-secret",
    passphrase="your-passphrase",
    sandbox_mode=False  # Set to True for testing
)
```

#### `check_master_account_balance() → Decimal`
Get USDT balance of master account

```python
balance = await service.check_master_account_balance()
# Returns: Decimal('5000.12345678')
```

#### `process_internal_transfer(destination_uid: str, amount_usd: float, user_id: str, withdrawal_id: str) → (bool, str, str)`
Main method - executes KuCoin internal transfer

```python
success, message, transfer_id = await service.process_internal_transfer(
    destination_uid="12345678",      # User's KuCoin UID
    amount_usd=10.50,                # Amount in USD
    user_id="user123",               # For audit trail
    withdrawal_id="withdraw456"      # For tracking
)

# Returns:
# (True, "Transfer successful", "67890abcdef") - on success
# (False, "Insufficient balance", None) - on failure
```

#### `get_transfer_status(transfer_id: str) → Optional[str]`
Check status of a transfer

```python
status = await service.get_transfer_status("67890abcdef")
# Returns: "PENDING" or "SUCCESS" or "FAILED"
```

### 2. WithdrawalRateLimiter

**Location:** `backend/app/services/withdrawal_rate_limiter.py`

**Responsibility:** Prevents withdrawal abuse

**Key Methods:**

#### `check_rate_limit(user_id: str) → (bool, str)`
Check if user has reached rate limits

```python
limiter = WithdrawalRateLimiter(db)
is_allowed, message = await limiter.check_rate_limit("user123")

if is_allowed:
    # Proceed with withdrawal
else:
    # Return error: "User has exceeded withdrawal limit (1 per hour)"
```

#### `record_withdrawal_attempt(user_id: str, withdrawal_id: str) → None`
Record withdrawal attempt in database

```python
await limiter.record_withdrawal_attempt("user123", "withdraw456")
# Stores in withdrawal_rate_limits collection
```

**Rate Limit Windows:**
- Per hour: 1 withdrawal max
- Per day (user): 5 withdrawals max
- Per day (system): 50 withdrawals max

### 3. Updated Router Endpoint

**Location:** `backend/app/affiliates/router.py`

**Endpoint:**
```
POST /affiliates/withdraw
```

**Request:**
```json
{
  "amount_usd": 10.50,
  "withdrawal_method_id": "method123"  // User's saved method (PIX/KuCoin/etc)
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Withdrawal processed successfully",
  "withdrawal_id": "withdraw456",
  "transfer_id": "67890abcdef",  // KuCoin transfer ID (if KuCoin UID)
  "status": "PROCESSING",  // or "COMPLETED" for instant methods
  "amount_usd": 10.50,
  "method_type": "kucoin_uid",
  "estimated_arrival": "2024-01-16T10:23:45Z"  // for display
}
```

**Response (Failure):**
```json
{
  "success": false,
  "error": "error_code",
  "message": "Human readable message",
  "details": "Additional context if available"
}
```

**Common Errors:**
- `429 Too Many Requests` - Rate limit exceeded
- `400 Invalid UID` - Destination UID format invalid
- `400 Insufficient Balance` - Master account USDT running low
- `400 User Limit Exceeded` - User reached max 5/day
- `503 KuCoin API Error` - KuCoin API temporarily unavailable

---

## Frontend Components

### 1. WithdrawConfig Component

**Location:** `src/components/affiliate/WithdrawConfig.tsx`

**Features:**
- Method selector (PIX / KuCoin UID / Crypto / Banco)
- Format validation by method type
- UID input mask (8-10 digits only)
- Example display with copy button
- Where-to-find instructions for KuCoin UID
- Holder name validation
- Error handling and success confirmation

**Usage:**
```jsx
<WithdrawConfig 
  onMethodSaved={(method) => {
    // Refresh dashboard or navigate
    console.log('Method saved:', method);
  }}
/>
```

**Data Submitted:**
```json
{
  "type": "kucoin_uid",
  "key": "12345678",      // The UID
  "holder_name": "João Silva"
}
```

### 2. Withdrawal History / Status Display

**Recommended Component:** Add to Dashboard

```jsx
// Show recent withdrawals with status
<WithdrawalHistory
  withdrawals={affiliateWithdrawals}
  onRetry={handleRetryWithdrawal}
/>
```

**Display Info:**
- Withdrawal amount
- Destination (last 4 digits of UID)
- Status: PENDING / PROCESSING / SUCCESS / FAILED
- Timestamp
- Transfer ID (for KuCoin transfers)
- Retry button (if failed)

---

## Security Measures

### 1. API Key Security

✅ **IP Whitelisting** (CRITICAL)
- Only your production server IP can access KuCoin API
- Set in KuCoin Security settings
- No access from other IPs even with correct key/secret

✅ **Minimal Permissions**
- API Key has ONLY "Inner Transfer" permission
- NO Trading, Deposits, or Withdrawals enabled
- NO Edit permission on key

✅ **Environment Variables**
- Keys stored in `.env` (not in code)
- Never commit to git
- Rotate regularly (quarterly recommended)

### 2. Rate Limiting

✅ **Per-User Limits**
- 1 withdrawal per hour (prevents rapid-fire requests)
- 5 withdrawals per day (prevents bulk abuse)

✅ **System-Wide Limit**
- 50 withdrawals per day maximum
- Circuit breaker if exceeded

✅ **Attempt Recording**
- All attempts logged (success or failure)
- Prevents duplicate detection
- Audit trail for compliance

### 3. Amount Validation

✅ **No Negative Amounts**
- Validate `amount > 0`

✅ **Balance Check**
- BEFORE KuCoin API call
- BEFORE wallet debit

✅ **Atomic Transactions**
- If KuCoin call fails: wallet NOT debited
- If wallet debit fails: funds revert (via reversal transaction)

### 4. UID Validation

✅ **Format Check**
- Must be 8-10 digits numeric only
- Checked on frontend AND backend

✅ **Account Verification**
- KuCoin confirms UID exists (returns error if not)

✅ **Precision Decimals**
- USDT precision: 8 decimal places (0.00000001)
- All amounts quantized before transmission

### 5. Logging & Audit Trail

✅ **Complete Logging**
- Every API call logged with timestamp
- Request/response logged (sanitized, no keys)
- Errors logged with full context
- File rotation to prevent disk overflow

✅ **Database Audit**
- affiliate_transactions table stores all T+0 data
- withdrawal_rate_limits tracks attempts
- affiliate_withdraw_requests has final status
- 90-day retention minimum

✅ **Admin Alerts**
- Failed transfers alert admin
- Rate limits alerts if approaching system limit
- Any KuCoin API errors trigger notification

---

## Testing Procedures

### Unit Testing

```bash
cd backend
pytest tests/test_kucoin_payout_service.py -v

# Tests:
# ✓ test_validate_uid_format
# ✓ test_signature_generation
# ✓ test_decimal_precision
# ✓ test_error_handling
```

### Integration Testing (Sandbox)

```bash
# Enable sandbox in .env
KUCOIN_SANDBOX_MODE=true

# Run integration tests
pytest tests/test_kucoin_integration.py -v -s

# Tests:
# ✓ test_check_master_balance
# ✓ test_process_internal_transfer_success
# ✓ test_process_internal_transfer_insufficient_balance
# ✓ test_rate_limiter_per_hour
# ✓ test_rate_limiter_per_day
# ✓ test_withdraw_endpoint_kucoin
```

### Manual Testing

1. **Add test funds to sandbox:**
   ```bash
   # Use sandbox faucet or transfer test USDT
   ```

2. **Create test user with affiliate wallet:**
   ```bash
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com", "password":"test123"}'
   ```

3. **Add balance to test user:**
   ```bash
   # Via admin endpoint or directly in DB
   db.affiliate_wallets.updateOne(
     { user_id: "test_user_id" },
     { $inc: { saldo_disponivel: 50 } }
   )
   ```

4. **Create withdrawal method:**
   ```bash
   curl -X POST http://localhost:8000/affiliates/withdrawal-method \
     -H "Authorization: Bearer test_token" \
     -d '{
       "type": "kucoin_uid",
       "key": "12345678",
       "holder_name": "Test User"
     }'
   ```

5. **Submit withdrawal:**
   ```bash
   curl -X POST http://localhost:8000/affiliates/withdraw \
     -H "Authorization: Bearer test_token" \
     -H "Content-Type: application/json" \
     -d '{"amount_usd": 5.00}'
   ```

6. **Verify in KuCoin Sandbox:**
   - Login to https://sandbox.kucoin.com
   - Check "Assets" → "Overview"
   - Should see transfer to destination UID

---

## Monitoring & Maintenance

### Daily Checklist

```bash
# 1. Check KuCoin API status
curl -s https://status.kucoin.com | grep -i "operational"

# 2. Monitor failed transfers
db.affiliate_transactions
  .find({ method: "kucoin_uid", status: "FAILED" })
  .limit(5)

# 3. Check rate limiter health
db.withdrawal_rate_limits.countDocuments()
# Should be < 100 records (cleaned up daily)

# 4. Verify master account balance
# Via backend logs:
tail -f logs/app.log | grep "master account balance"
```

### Weekly Checklist

```bash
# 1. Export withdrawal summary
./scripts/export_affiliate_payouts.sh $(date -d '-7 days' +%Y-%m-%d)

# 2. Reconcile with KuCoin statements
# Download https://www.kucoin.com/account/statement

# 3. Check for any orphaned transfers
db.affiliate_transactions
  .find({ method: "kucoin_uid", status: "PROCESSING", created_at: { $lt: new Date(Date.now() - 86400000) } })
  .pretty()
# Should be empty (older than 24h)

# 4. Verify API key permissions still active
# Check KuCoin dashboard for any security alerts
```

### Monthly Checklist

```bash
# 1. Rotate API credentials
# Old key → Disable → Create new → Update .env → Delete old

# 2. Review rate limit settings
# Adjust MAX_WITHDRAWALS_PER_* if needed based on usage

# 3. Backup database
./scripts/backup_mongodb.sh

# 4. Generate compliance report
./scripts/affiliate_payout_report.sh --month $(date +%Y-%m)
```

---

## Troubleshooting Reference

### Issue: Transfer Succeeds but Wallet Not Debited

**Likely Cause:** Race condition or error in wallet debit step

**Solution:**
```bash
# 1. Check if transfer actually succeeded in KuCoin
db.affiliate_transactions.findOne({ transfer_id: "abc123" })

# 2. If transfer_id exists and KuCoin confirmed:
db.affiliate_wallets.updateOne(
  { user_id: "user123" },
  { $inc: { saldo_disponivel: -10.50 } }  // Debit amount
)

# 3. Create reversal note
db.affiliate_transactions.insertOne({
  user_id: "user123",
  type: "adjustment",
  amount: -10.50,
  reason: "manual_debit_fix_for_transfer_abc123",
  created_at: new Date()
})
```

### Issue: User Gets "Rate Limit Exceeded" but Only Made 1 Request

**Likely Cause:** Previous failed request still recorded

**Solution:**
```bash
# Clean up old rate limit records (older than 1 hour)
db.withdrawal_rate_limits.deleteMany({
  created_at: { $lt: new Date(Date.now() - 3600000) }
})
```

### Issue: KuCoin API Keeps Returning 429 (Rate Limited by KuCoin)

**Likely Cause:** Too many requests in short time

**Solution:**
- Implemented in service: exponential backoff (wait 1s, 2s, 4s)
- Max 3 retries
- After 3 failures: return error to user
- Manual fix: wait 10 minutes before retrying

---

## Next Steps

1. **Review & Approve**
   - Review backend services implementation
   - Review frontend component design
   - Test on sandbox

2. **Deploy to Staging**
   - Deploy backend code
   - Deploy frontend code
   - Test complete flow
   - Monitor for 24 hours

3. **Deploy to Production**
   - Follow KUCOIN_SETUP_GUIDE.md
   - Enable KUCOIN_SANDBOX_MODE=false
   - Monitor transfers closely first week

4. **Communicate to Users**
   - Send email explaining new KuCoin withdrawal option
   - Guide on where to find their UID
   - FAQ about fees (if any) and processing time

---

## Support & Questions

For issues:
1. Check logs: `tail -f logs/app.log | grep -E "KuCoin|withdraw"`
2. Check database: `db.affiliate_transactions.find(...)`
3. Check KuCoin API status: https://status.kucoin.com
4. Check KuCoin docs: https://docs.kucoin.com/

For emergencies (stuck transfers, API key issues):
- Contact KuCoin support: https://www.kucoin.com/support
- Escalate with transfer_id or error message
- May take 24-48 hours for support response
