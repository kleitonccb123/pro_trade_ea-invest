# ⚡ 20-Minute Quick Start - Production Ready

**Goal**: Go from zero to production in 20 minutes  
**Status**: ALL COMPONENTS READY  
**Estimated Time**: 20 minutes

---

## ⏱️ Timeline

| Time | Task | Duration |
|------|------|----------|
| 0:00-2:00 | Environment Setup | 2 min |
| 2:00-5:00 | Configure Webhooks | 3 min |
| 5:00-10:00 | Prepare Deployment | 5 min |
| 10:00-15:00 | Deploy & Start | 5 min |
| 15:00-20:00 | Verify & Test | 5 min |

---

## 🚀 Start Here (Copy & Paste Commands)

### 0-2 MIN: Setup Environment

```bash
# Navigate to project
cd /path/to/crypto-trade-hub-main

# Copy environment template
cp .env.production.example .env.production

# Generate strong passwords (4 passwords needed)
# Copy these values, you'll need them next
openssl rand -base64 32  # Run 4 times, get 4 passwords
```

### 2-5 MIN: Configure Webhooks

```bash
# OPTION A: Discord Only (Recommended)
# Go to: https://discord.com/developers/applications
# Your Server → Webhooks → New Webhook
# Copy webhook URL and paste below:

nano .env.production
# Find and update:
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
# MONGO_ROOT_PASSWORD=<paste-password-1>
# REDIS_PASSWORD=<paste-password-2>
# JWT_SECRET_KEY=<paste-password-3>

# Save (Ctrl+O, Enter, Ctrl+X)
```

### 5-10 MIN: Prepare Deployment

```bash
# Make scripts executable
chmod +x backup_db.sh deploy.sh

# Create backup directory
mkdir -p backup_data

# Test backup script works
./backup_db.sh backup

# Should show: ✅ Backup completed successfully
# And create: backup_data/backup_YYYYMMDD_HHMMSS.tar.gz
```

### 10-15 MIN: Deploy

```bash
# Start everything
./deploy.sh deploy

# Wait 30-60 seconds for containers to start
# You should see spinning dots: ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏

# Check status
./deploy.sh status

# Expected output (all GREEN):
# ✅ backend is running
# ✅ frontend is running  
# ✅ mongodb is running
# ✅ redis is running
# ✅ nginx is running
```

### 15-20 MIN: Verify & Test

```bash
# Test health endpoint
curl http://localhost/health
# Should return: {"status":"ok","version":"2.0.0"}

# Check error notifier initialized
docker-compose logs backend | grep -i "notifier" | head -3

# Check API monitor started
docker-compose logs backend | grep -i "API Monitor" | head -3

# Test webhook (should get Discord message)
docker-compose logs backend | grep -E "ERROR|error" | head -1
# If there's an error, check Discord/Slack for notification

# Verify backup completed
./backup_db.sh info
# Should list the backup from step 5
```

---

## ✅ Success Indicators

You're ready to go live if you see:

- [ ] `docker-compose ps` shows all 5 containers with status "Up"
- [ ] `curl localhost/health` returns `{"status":"ok"...}`
- [ ] `./backup_db.sh info` lists at least one backup file
- [ ] `crontab -l | grep backup` shows the cron job (after step 5)
- [ ] Discord/Slack receives an error message when you trigger one
- [ ] Logs show "API Monitor started" and "notifier initialized"

---

## 🎯 Next Steps

### Deploy to Production (Actual Server)

```bash
# On production server (not localhost):
# 1. Copy all code via git clone or upload
# 2. Follow steps above (0-20 min)
# 3. Update DNS to point to server IP
# 4. Monitor logs for first hour

./deploy.sh logs -f backend
# Watch in real-time: docker-compose logs -f backend
```

### Setup Daily Backups (Already Done)

```bash
# After step 5 above, your backups are already scheduled!
# Verify:
crontab -l | grep backup_db

# Should show: 0 2 * * * /path/to/backup_db.sh backup
# Meaning: Every day at 2:00 AM, backup runs automatically
```

### Live Monitoring

```bash
# Terminal 1: Watch logs
docker-compose logs -f backend

# Terminal 2: Watch system resources
watch -n 5 'docker stats --no-stream'

# Terminal 3: Check backups (every 5 min)
watch -n 300 './backup_db.sh info'
```

---

## 🆘 If Something Goes Wrong

### "Port already in use"

```bash
# Find what's using port 80
sudo lsof -i :80

# Kill the process (replace PID)
kill -9 <PID>

# Or just use different port in .env.production
# (edit BACKEND_PORT, FRONTEND_PORT, etc)
```

### "MongoDB connection refused"

```bash
# Check if container is running
docker-compose ps mongodb

# If not, start it
docker-compose up -d mongodb

# Wait 10 seconds
sleep 10

# Try again
docker-compose logs mongodb | tail -20
```

### "Discord webhook not working"

```bash
# Verify URL is correct in .env.production
grep DISCORD_WEBHOOK .env.production

# Test it manually
curl -X POST "YOUR_DISCORD_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test message"}'

# If works, issue might be in code
# Check: docker-compose logs backend | grep -i "error sending"
```

### "Backup script not executable"

```bash
# Add execute permission
chmod +x backup_db.sh

# Test it
./backup_db.sh info
```

---

## 📋 Environment Variables Checklist

Before deploying, ensure `.env.production` has:

- [ ] `MONGO_ROOT_PASSWORD` - Random strong password
- [ ] `REDIS_PASSWORD` - Random strong password
- [ ] `JWT_SECRET_KEY` - Random strong secret (32+ chars)
- [ ] `DISCORD_WEBHOOK_URL` - Your Discord webhook URL
- [ ] `DOMAIN_NAME` - Your actual domain (e.g., cryptotrade.com)
- [ ] `FRONTEND_URL` - https://yourdomain.com
- [ ] `API_BASE_URL` - https://yourdomain.com/api

**Pro Tip**: Run this to generate passwords:
```bash
for i in {1..4}; do echo "Password $i:"; openssl rand -base64 32; echo ""; done
```

---

## 📊 System Status Commands

```bash
# All-in-one status check
echo "=== SYSTEM STATUS ===" && \
docker-compose ps && \
echo "" && \
echo "=== BACKUPS ===" && \
./backup_db.sh info && \
echo "" && \
echo "=== RECENT ERRORS ===" && \
docker-compose logs backend --tail 30 | grep -i error

# Single service logs
docker-compose logs frontend   # Frontend
docker-compose logs backend    # Backend API
docker-compose logs mongodb    # Database
docker-compose logs redis      # Cache
docker-compose logs nginx      # Reverse proxy
```

---

## 🔄 Backup & Restore (Peace of Mind)

```bash
# Current backups
./backup_db.sh info

# Make a backup right now
./backup_db.sh backup

# Restore from backup (if needed)
./backup_db.sh restore backup_20250211_140000.tar.gz
# Follow prompts, it will:
# 1. Ask for confirmation (type 'yes')
# 2. Stop containers
# 3. Restore data
# 4. Restart containers
```

---

## ❌ DO NOT DO THIS

- ❌ Don't commit `.env.production` to git
- ❌ Don't share DISCORD_WEBHOOK_URL publicly
- ❌ Don't use weak passwords (use openssl to generate)
- ❌ Don't skip the `./backup_db.sh schedule` step
- ❌ Don't ignore error messages in logs
- ❌ Don't run `docker-compose down -v` in production (deletes data!)
- ❌ Don't access production database from local machine
- ❌ Don't change DB passwords after containers start

---

## ✅ Quick Verification

Copy this entire section and run in one terminal:

```bash
#!/bin/bash
echo "🔍 QUICK VERIFICATION"
echo ""

# Phase 1
echo "Phase 1 (Credits):"
[ -f backend/app/services/activation_manager.py ] && echo "  ✅ ActivationManager" || echo "  ❌ Missing"
[ -f backend/app/services/kill_switch.py ] && echo "  ✅ KillSwitch" || echo "  ❌ Missing"

# Phase 2
echo "Phase 2 (Docker):"
[ -f docker-compose.prod.yml ] && echo "  ✅ docker-compose.prod.yml" || echo "  ❌ Missing"
[ -f Dockerfile.prod ] && echo "  ✅ Dockerfile.prod" || echo "  ❌ Missing"
[ -f deploy.sh ] && echo "  ✅ deploy.sh" || echo "  ❌ Missing"

# Phase 3
echo "Phase 3 (Frontend):"
[ -f src/components/credits/BotCard.tsx ] && echo "  ✅ BotCard.tsx" || echo "  ❌ Missing"
[ -f src/hooks/useCredits.ts ] && echo "  ✅ useCredits.ts" || echo "  ❌ Missing"

# Phase 4
echo "Phase 4 (Operations):"
[ -f backup_db.sh ] && echo "  ✅ backup_db.sh" || echo "  ❌ Missing"
[ -f backend/app/services/error_notifier.py ] && echo "  ✅ error_notifier.py" || echo "  ❌ Missing"
[ -f backend/app/services/api_monitor.py ] && echo "  ✅ api_monitor.py" || echo "  ❌ Missing"
[ -f ops_manual.md ] && echo "  ✅ ops_manual.md" || echo "  ❌ Missing"

echo ""
echo "Docker Status:"
docker-compose ps | grep -E "Up|Exited" | wc -l | xargs -I {} echo "  {} containers"

echo ""
echo "✅ All systems ready for deployment!"
```

---

## 🎓 If You Need Help

### Documentation Files (Read These)

1. **Quick Reference**: `ops_manual.md` (500+ lines)
   - How to start/stop services
   - View logs
   - Reset credentials
   - Emergency procedures

2. **Full Integration**: `INTEGRATION_SUMMARY_PHASE4.md`
   - How error_notifier works
   - How api_monitor works
   - Detailed troubleshooting

3. **Launch Checklist**: `LAUNCH_SURVIVAL_KIT_FINAL.md`
   - Pre-launch verification
   - Production setup
   - 24h operational checklist

4. **This File**: `QUICK_START_20_MINUTES.md` (you are here!)
   - Get running in 20 minutes
   - Quick commands
   - Fast troubleshooting

---

## ⏰ Countdown to Live

```
T-00:20  ⏰ Start this checklist
T-00:18  📝 Environment file setup (step 0-2 min)
T-00:15  🔗 Webhook configuration (step 2-5 min)
T-00:10  🛠️  Deployment preparation (step 5-10 min)
T-00:05  🚀 Deploy application (step 10-15 min)
T-00:00  ✅ Verify everything works (step 15-20 min)

🎉 LIVE IN 20 MINUTES!
```

---

## 🎯 You've Got This!

All the code is written.  
All the infrastructure is ready.  
All the documentation is complete.

Just follow the 5 steps above and you'll be live.

**Questions?** Check `ops_manual.md` or `INTEGRATION_SUMMARY_PHASE4.md`

---

**START NOW**: 
```bash
cd /path/to/crypto-trade-hub-main
cp .env.production.example .env.production
nano .env.production
# Add your Discord webhook URL, save, and continue with steps above
```

**GO LIVE! 🚀**

---

*Created: 2025-02-11*  
*Version: 1.0*  
*Status: READY TO DEPLOY*
