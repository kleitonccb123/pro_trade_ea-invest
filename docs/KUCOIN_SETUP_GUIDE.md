# 🚀 KuCoin Integration Setup Guide

## Table of Contents
1. [Environment Variables](#environment-variables)
2. [API Key Creation & IP Whitelisting](#api-key-creation--ip-whitelisting)
3. [Sandbox Testing](#sandbox-testing)
4. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
5. [Production Deployment](#production-deployment)

---

## Environment Variables

### Backend Configuration (`.env` or `.env.production`)

```bash
# ===== KuCoin API Credentials =====
# Get these from KuCoin API Management console
# https://www.kucoin.com/zh_CN/sub/security/

# Your KuCoin API Key
KUCOIN_API_KEY=your-api-key-here

# Your KuCoin API Secret
KUCOIN_API_SECRET=your-api-secret-here

# Your KuCoin API Passphrase (set in API Key settings)
KUCOIN_PASSPHRASE=your-passphrase-here

# ===== KuCoin Environment =====
# Set to 'true' for sandbox (testing), 'false' for production
KUCOIN_SANDBOX_MODE=false

# Master Account UID (your main trading account)
# Find this in Profile > UID on KuCoin
KUCOIN_MASTER_UID=your-master-account-uid

# ===== Rate Limiting =====
# Max withdrawals per user per hour (default: 1)
WITHDRAWAL_MAX_PER_HOUR=1

# Max withdrawals per user per day (default: 5)
WITHDRAWAL_MAX_PER_DAY=5

# Max withdrawals system-wide per day (default: 50)
WITHDRAWAL_MAX_TOTAL_PER_DAY=50

# ===== Currency & Precision =====
# Only USDT supported currently
WITHDRAWAL_CURRENCY=USDT

# Decimal precision for USDT (8 decimal places = 0.00000001)
WITHDRAWAL_DECIMAL_PLACES=8
```

### Frontend Configuration (`.env`)

```bash
# Backend API URL
REACT_APP_API_URL=http://localhost:8000
# or for production:
# REACT_APP_API_URL=https://api.yourdomain.com
```

---

## API Key Creation & IP Whitelisting

### Step 1: Create KuCoin API Key

1. **Login to KuCoin** → https://www.kucoin.com
2. **Navigate to Security:**
   - Click your avatar (top right)
   - Select "Security" or "API Management"
   
3. **Create New API Key:**
   - Click "Add API Key"
   - Name: `crypto-trade-hub-affiliate` (or similar)
   - Select "Private"
   
4. **Configure Permissions:**
   - ✅ **Enable** "General" (required for transfers)
   - ✅ **Enable** "Inner Transfer" (required for inter-account transfers)
   - ❌ **Disable** "Trading" (not needed)
   - ❌ **Disable** "Withdrawals" (we only do internal transfers)
   - ❌ **Disable** "Deposit" (not needed)

5. **Set IP Whitelist (CRITICAL):**
   ```
   Production Server IP: your.server.ip.address
   Development (Optional): 127.0.0.1
   ```
   
   > ⚠️ **IMPORTANT**: Leave IP whitelist as restrictive as possible. Only add:
   > - Your production server IP
   > - Your office/development IP (if needed)
   > - Never add 0.0.0.0 (allows everyone)

6. **Copy Your Credentials:**
   - **API Key**: Copy paste into `KUCOIN_API_KEY`
   - **API Secret**: Copy paste into `KUCOIN_API_SECRET`
   - **Passphrase**: Set a complex passphrase and copy into `KUCOIN_PASSPHRASE`

### Step 2: Verify KuCoin Master Account (Your Receiving Account)

Your "master account" is where affiliate payouts will be debited from. Ensure:

1. ✅ Account has sufficient USDT balance
2. ✅ Account is "Main Account" or "Trading Account" 
3. ✅ Account UID matches `KUCOIN_MASTER_UID` in `.env`
4. ✅ "Inner Transfer" is enabled in account settings

**Find Your UID:**
```
Profile > UID (appears as 8-10 digit number)
```

### Step 3: Test Permission Scope

Run this test to ensure API key has correct permissions:

```bash
# From your server
cd backend

# Test basic connectivity
python -m pytest tests/test_kucoin_api.py::test_check_balance -v

# Should output:
# ✓ Successfully retrieved master account USDT balance
# ✓ API Key has required permissions
```

---

## Sandbox Testing

### Enable Sandbox Mode

In `.env`:
```bash
KUCOIN_SANDBOX_MODE=true
KUCOIN_API_KEY=sandbox-api-key
KUCOIN_API_SECRET=sandbox-api-secret
KUCOIN_PASSPHRASE=sandbox-passphrase
```

### Create Sandbox Account

1. Go to **KuCoin Sandbox**: https://sandbox.kucoin.com
2. Register new account (separate from main account)
3. Generate API Key (same process as above)
4. Add test USDT to sandbox account:
   - Use sandbox faucet or
   - Transfer from main KuCoin account

### Test Flow

```bash
# 1. Start backend with sandbox mode enabled
cd backend
python -m uvicorn app.main:app --reload

# 2. Run integration tests
python -m pytest tests/test_kucoin_integration.py -v

# 3. Create test withdrawal request
curl -X POST http://localhost:8000/affiliates/withdraw \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <test-token>" \
  -d '{
    "amount_usd": 10.50,
    "withdrawal_method_id": "test-kucoin-uid"
  }'

# Expected response:
# {
#   "success": true,
#   "message": "Withdrawal processed successfully",
#   "transfer_id": "67123456789abcdef",
#   "status": "PROCESSING"
# }
```

---

## Monitoring & Troubleshooting

### Common Errors

#### 1. "Invalid API Key"
```
Error: 400 Bad Request - { "code": "400001", "msg": "Invalid API key" }
```
**Solution:**
- Verify API key in `.env` is correctly copied (no extra spaces)
- Check API key hasn't expired (regenerate if old)
- Ensure IP whitelist includes your server IP

#### 2. "Insufficient Permissions"
```
Error: 403 Forbidden - { "code": "403000", "msg": "Access denied" }
```
**Solution:**
- API Key must have "Inner Transfer" permission enabled
- Go to KuCoin > Security > API Key > Edit
- Enable "Inner Transfer" checkbox

#### 3. "Invalid Passphrase"
```
Error: 400 Bad Request - { "code": "400100", "msg": "Invalid Passphrase" }
```
**Solution:**
- Passphrase must match what you set in KuCoin
- Check for typos (case-sensitive)
- If forgotten, regenerate API Key in KuCoin

#### 4. "Destination Account Not Found"
```
Error: 400 Bad Request - { "code": "400100", "msg": "The inner transfer account is not found" }
```
**Solution:**
- Verify destination UID is correct (8-10 digits)
- User must enter their UID, not username
- Destination account must exist in KuCoin

#### 5. "Insufficient USDT Balance"
```
Error: 400 Bad Request - { "code": "200008", "msg": "Insufficient balance" }
```
**Solution:**
- Add more USDT to your master account
- Check if balance is in "Available" (not frozen)

#### 6. "Rate Limit Exceeded (429)"
```
Error: 429 Too Many Requests
```
**Solution:**
- KuCoin API has rate limits (1000 requests/10 seconds)
- Our code implements proper backoff + retry
- Check WithdrawalRateLimiter: max 1 transaction/hour per user

### Backend Logging

All KuCoin operations are logged with details:

```bash
# View logs
tail -f logs/app.log | grep "KuCoin\|withdrawal"

# Example log output:
2024-01-15 10:23:45 🟡 [KuCoin] Checking master account balance...
2024-01-15 10:23:46 ✓ Balance: 5000.12345678 USDT
2024-01-15 10:23:47 📤 [KuCoin] Executing internal transfer to UID 87654321...
2024-01-15 10:23:49 ✓ Transfer successful: transfer_id=aB12cD34eF56
```

### Database Monitoring

Check withdrawal attempts and transfers:

```bash
# Connect to MongoDB
mongosh

# View pending transfers
db.affiliate_withdraw_requests.find({ status: "PROCESSING" })

# View rate limit records
db.withdrawal_rate_limits.find({ created_at: { $gte: new Date(Date.now() - 3600000) } })

# View transaction audit
db.affiliate_transactions.find({ type: "withdrawal", method: "kucoin_uid" }).limit(10)
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] **API Keys Generated** with correct permissions
- [ ] **IP Whitelist Configured** (only production server IP)
- [ ] **Environment Variables Set** on production server
- [ ] **KUCOIN_SANDBOX_MODE=false** in production `.env`
- [ ] **Master Account UID Verified** and has sufficient USDT balance
- [ ] **Rate Limits Configured** (adjust `WITHDRAWAL_MAX_*` if needed)
- [ ] **Database Backups Enabled** (for transaction audit trail)
- [ ] **Monitoring Alerts Set Up** (for failed transfers)
- [ ] **Email Notifications Ready** (for successful withdrawals)
- [ ] **Test Withdrawals Completed** in sandbox first

### Deployment Steps

#### 1. Update Production `.env`

```bash
# SSH into production server
ssh user@your-server.com

# Edit environment file
nano /app/.env.production

# Add/Update KuCoin variables (see Environment Variables section)
```

#### 2. Restart Backend

```bash
# If using Docker
docker-compose -f docker-compose.prod.yml restart backend

# If using systemd
systemctl restart crypto-trade-hub-backend

# Verify
curl http://localhost:8000/health
```

#### 3. Test Live Withdrawals

```bash
# Create test affiliate with small balance
curl -X POST http://your-api.com/affiliates/test \
  -H "Authorization: Bearer admin-token"

# Process small test withdrawal (e.g., 1 USDT)
curl -X POST http://your-api.com/affiliates/withdraw \
  -H "Authorization: Bearer user-token" \
  -d '{ "amount_usd": 1.0 }'

# Verify in KuCoin
# Transaction should appear in "Internal Transfers" within 30 seconds
```

#### 4. Monitor First 24 Hours

Watch for:
- ✓ Successful transfers in KuCoin
- ✓ Rate limiting working correctly
- ✓ No database errors
- ✓ Proper logging in backend

```bash
# Real-time monitoring
tail -f /var/log/crypto-trade-hub.log | grep -E "KuCoin|withdrawal|ERROR"

# Daily summary report
curl http://your-api.com/admin/affiliate-payouts?date=today
```

---

## Disaster Recovery

### If Transfer Fails

**Scenario:** User receives "transfer failed" but USDT was debited

**Recovery Steps:**

1. **Check Transfer Status:**
   ```bash
   # Backend logs show transfer_id
   db.affiliate_transactions.findOne({ transfer_id: "aB12cD34eF56" })
   # If status="FAILED"
   ```

2. **Manual Reversal:**
   ```bash
   # Reverse the debit from affiliate wallet
   db.affiliate_wallets.updateOne(
     { user_id: "user123" },
     { $inc: { saldo_disponivel: 10.50 } }
   )
   
   # Record reversal transaction
   db.affiliate_transactions.insertOne({
     user_id: "user123",
     type: "reversal",
     amount: 10.50,
     reason: "failed_transfer_aB12cD34eF56",
     created_at: new Date()
   })
   ```

3. **Notify User:**
   - Send email explaining the issue
   - Option to retry or choose different withdrawal method

### If Master Account Runs Low

**Scenario:** Not enough USDT in master account for pending withdrawals

**Quick Fix:**
```bash
# Transfer USDT from cold storage or other account to master account
# Via KuCoin app (faster than API)
```

**Prevent Future:**
- Set up daily monitoring alert if balance < $1000
- Maintain buffer of at least 10% of total pending withdrawals

---

## Useful Resources

- **KuCoin API Docs:** https://docs.kucoin.com/

- **KuCoin Inner Transfer API:** https://docs.kucoin.com/#inner-transfer

- **KuCoin Security Best Practices:** https://support.kucoin.plus/hc/en-us/articles/8209476387097

- **Community Support:** https://www.kucoin.com/support

---

## Next Steps

1. ✅ Generate API Key with correct permissions
2. ✅ Configure IP whitelist to your server IP
3. ✅ Set environment variables in `.env`
4. ✅ Test in sandbox mode
5. ✅ Deploy to production
6. ✅ Monitor first 24 hours for issues
7. ✅ Enable monitoring alerts

Questions? Check the logs:
```bash
tail -f logs/app.log | grep KuCoin
```
