# MongoDB Atlas TLS Connection Test

> Comprehensive diagnostic scripts to validate MongoDB Atlas connectivity and SSL/TLS configuration

## Overview

Two test scripts are provided to diagnose MongoDB Atlas connection issues:

- **Python**: `test_mongodb_tls.py` - Requires Python 3.8+
- **Node.js**: `test_mongodb_tls.js` - Requires Node.js 14+

## Quick Start

### Python Testing

```bash
# Using Python 3
python3 test_mongodb_tls.py

# Or if python3 is in PATH
python test_mongodb_tls.py

# Make executable (on Linux/Mac)
chmod +x test_mongodb_tls.py
./test_mongodb_tls.py
```

**Requirements:**
```bash
pip install certifi motor pymongo aiosqlite
```

### Node.js Testing

```bash
# Using Node.js
node test_mongodb_tls.js

# Or if configured in package.json
npm run test:mongodb
```

**Requirements:**
```bash
npm install mongodb
```

## What Each Script Tests

### Common Tests (Both Scripts)

1. **✓ Driver Installation**
   - Checks if MongoDB client library is installed
   - Validates driver version

2. **✓ SSL Certificate Configuration**
   - Verifies system SSL certificates are present
   - Checks certificate paths and availability
   - For Python: Uses `certifi` package for certificate management
   - For Node.js: Checks system SSL store

3. **✓ Database URL Configuration**
   - Validates `DATABASE_URL` environment variable
   - Checks MongoDB Atlas format (mongodb+srv://)
   - Extracts and logs cluster information (safely)

4. **✓ MongoDB Connection**
   - Attempts actual connection to MongoDB Atlas
   - Sends ping command to verify responsiveness
   - Measures connection latency
   - Reports any SSL/TLS errors

5. **✓ Resilience Testing** (Python only)
   - Tests SQLite fallback capability
   - Verifies offline mode functionality

## Interpreting Results

### Successful Test Output

```
✓ mongodb driver module is installed
✓ Certificate bundle path: /path/to/certificates
✓ DATABASE_URL found
✓ Using MongoDB Atlas (mongodb+srv) connection
✓ MongoDB connection successful!
✓ Server responded to ping command

✅ ALL TESTS PASSED - MongoDB connection is healthy!
```

### Common Error Scenarios

#### 1. SSL/TLS Certificate Errors

**Error:**
```
✗ SSL/TLS certificate validation error
```

**Solutions:**
```bash
# Python - Reinstall certifi
pip install --upgrade certifi

# Node.js - Update system SSL certificates
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install ca-certificates

# CentOS/RHEL
sudo yum update ca-certificates

# macOS
# Usually handled automatically, try:
brew install openssl
```

#### 2. Connection Timeout

**Error:**
```
✗ Connection timeout - MongoDB Atlas unreachable
```

**Solutions:**
1. Verify MongoDB Atlas is running (check console)
2. Check IP whitelist in MongoDB Atlas:
   - Go to https://cloud.mongodb.com/
   - Security → Network Access
   - Add your current IP address (or 0.0.0.0/0 for testing only)

3. Test network connectivity:
   ```bash
   # Test DNS resolution
   nslookup cluster.mongodb.net
   
   # Test connectivity
   curl -v telnet://cluster.mongodb.net:27017
   ```

#### 3. Authentication Failure

**Error:**
```
✗ Authentication failed
```

**Solutions:**
1. Verify DATABASE_URL format - check username and password
2. Reset password in MongoDB Atlas if necessary
3. Ensure special characters in password are URL-encoded:
   ```
   mongodb+srv://user%40email.com:pass%40word@cluster...
   ```

#### 4. IP Not Whitelisted

**Error:**
```
✗ IP address not whitelisted
```

**Solutions:**
1. Find your public IP: `curl https://api.ipify.org`
2. Go to MongoDB Atlas console
3. Security → Network Access
4. Click "Add IP Address"
5. Enter your IP and click Confirm

## Environment Configuration

### Setting DATABASE_URL

```bash
# Linux/macOS exports
export DATABASE_URL="mongodb+srv://username:password@cluster0.abc123.mongodb.net/dbname?retryWrites=true&w=majority"

# Windows (Command Prompt)
set DATABASE_URL=mongodb+srv://username:password@cluster0.abc123.mongodb.net/dbname?retryWrites=true&w=majority

# Windows (PowerShell)
$env:DATABASE_URL = "mongodb+srv://username:password@cluster0.abc123.mongodb.net/dbname?retryWrites=true&w=majority"

# Docker/Kubernetes - Add to .env file
DATABASE_URL=mongodb+srv://...
```

### Getting Connection String from MongoDB Atlas

1. Log in to MongoDB Atlas console
2. Click "Connect" on your cluster
3. Select "Drivers"
4. Choose "Node.js" or "Python"
5. Copy the connection string
6. Replace `<username>`, `<password>`, and `<dbname>`

## Troubleshooting Guide

### Problem: "Connection refused"

- MongoDB Atlas cluster is paused
- Solution: Go to MongoDB Atlas and start your cluster

### Problem: "DNS resolution failed"

- Network/firewall blocking DNS
- Solution: Try with explicit IP or check firewall settings

### Problem: "Certificate validation failed"

- System doesn't have MongoDB CA certificates
- Python: `pip install certifi`
- Node.js: Update OS SSL certificates

### Problem: "Too many connections"

- Your application is creating new connections excessively
- Solution: Use connection pooling (handled by these drivers)

## Advanced Options

### Custom Certificate Path

**Python:**
```python
from motor.motor_asyncio import AsyncIOMotorClient
client = AsyncIOMotorClient(
    db_url,
    tlsCAFile="/path/to/custom/ca.pem"
)
```

**Node.js:**
```javascript
const { MongoClient } = require('mongodb');
const client = new MongoClient(db_url, {
    tlsCertificateKeyFile: "/path/to/client.pem",
    tlsCAFile: "/path/to/ca.pem"
});
```

### Disable Certificate Validation (Development Only)

**Python:**
```python
connection_options = {
    "tls": True,
    "tlsAllowInvalidCertificates": True,
    "tlsAllowInvalidHostnames": True,
}
```

**Node.js:**
```javascript
// Not recommended - Node.js validates by default
// Use only for development with self-signed certificates
```

## Logs and Debugging

### View Test Logs

Both scripts generate logs:

```bash
# Python logs
tail -f mongodb_tls_test.log

# Node.js output in console (no file by default)
```

### Enable Verbose MongoDB Logging

**Python:**
```python
import logging
logging.getLogger('motor.motor_asyncio').setLevel(logging.DEBUG)
```

**Node.js:**
```javascript
const client = new MongoClient(url, {
    loggerLevel: 'debug',
    logger: function(msg, ctx) {
        console.log(msg, ctx);
    }
});
```

## Integration with Application

These test scripts should be run:

1. **Before deployment** - Verify MongoDB is reachable
2. **In CI/CD pipelines** - Automated connectivity checks
3. **During troubleshooting** - Diagnose connection issues
4. **In health checks** - Monitor MongoDB availability

### Add to package.json (Node.js)

```json
{
  "scripts": {
    "test:mongodb": "node test_mongodb_tls.js",
    "prestart": "npm run test:mongodb"
  }
}
```

### Add to GitHub Actions

```yaml
- name: Test MongoDB Connection
  run: python test_mongodb_tls.py
  env:
    DATABASE_URL: ${{ secrets.MONGODB_URI }}
```

## Performance Metrics

The scripts measure and report:

- **Connection Time**: How long to establish connection
- **Response Time**: Server response to ping
- **Pool Status**: Active connections and limits
- **Timeout Values**: Connection timeout settings

Target metrics:

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Connection Time | < 100ms | 500-1000ms | > 1000ms |
| Ping Response | < 50ms | 100-200ms | > 200ms |
| Pool Availability | > 80% | 50-80% | < 50% |

## Support and Additional Resources

- **MongoDB Atlas Docs**: https://docs.mongodb.com/manual/
- **MongoDB Drivers**: https://docs.mongodb.com/drivers/
- **SSL/TLS Reference**: https://docs.mongodb.com/manual/reference/connection-string/#tls-ssl-options
- **Network Setup**: https://docs.atlas.mongodb.com/security-whitelist/

## License

These diagnostic scripts are provided as-is for troubleshooting MongoDB connectivity.

---

**Last Updated**: 2024
**Tested with**: Python 3.8+, Node.js 14+, MongoDB Atlas
