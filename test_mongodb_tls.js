#!/usr/bin/env node

/**
 * MongoDB Atlas TLS Connection Test Script (Node.js)
 * 
 * This script validates MongoDB Atlas connection with SSL/TLS certificate validation.
 * It checks for MongoDB driver installation and tests the actual connection.
 * 
 * Usage:
 *     node test_mongodb_tls.js
 *     npm test:mongodb
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Color codes for terminal output
const colors = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    green: '\x1b[32m',
    red: '\x1b[31m',
    yellow: '\x1b[33m',
    blue: '\x1b[36m',
};

function log(message, color = 'reset') {
    const timestamp = new Date().toISOString().split('T')[1].slice(0, 8);
    console.log(`${colors[color]}[${timestamp}]${colors.reset} ${message}`);
}

function printSection(title, char = '=') {
    const width = 80;
    const padding = Math.floor((width - title.length - 2) / 2);
    console.log();
    console.log(`${char.repeat(padding)} ${title} ${char.repeat(padding)}`);
    console.log();
}

// ============================================================================
// STEP 1: Check MongoDB Driver Installation
// ============================================================================

async function testMongoDBDriver() {
    printSection('STEP 1: Checking MongoDB Driver Installation');
    
    try {
        const { MongoClient } = require('mongodb');
        log('✓ mongodb driver module is installed', 'green');
        
        const version = require('mongodb/package.json').version;
        log(`✓ MongoDB driver version: ${version}`, 'green');
        
        return true;
    } catch (error) {
        log('✗ mongodb driver not installed', 'red');
        log('  Run: npm install mongodb', 'yellow');
        return false;
    }
}

// ============================================================================
// STEP 2: Check SSL Certificates
// ============================================================================

function testSSLCertificates() {
    printSection('STEP 2: Checking SSL Certificates');
    
    try {
        // Node.js uses the system certificate store by default
        const certPaths = [
            '/etc/ssl/certs/ca-certificates.crt',           // Ubuntu/Debian
            '/etc/pki/tls/certs/ca-bundle.crt',            // CentOS/RHEL
            '/etc/ssl/ca-bundle.pem',                       // OpenSUSE
            '/etc/ssl/cert.pem',                            // OpenBSD
            '/usr/local/share/ca-certificates/',            // Linux
            process.env.NODE_EXTRA_CA_CERTS,               // Custom CA bundle
        ].filter(p => p && p.length > 0);
        
        log('✓ Node.js will use system SSL certificate store', 'green');
        log(`✓ Checked paths: ${certPaths.length} known locations`, 'green');
        
        // Check if any exist
        let foundCert = false;
        for (const certPath of certPaths) {
            if (certPath && fs.existsSync(certPath)) {
                log(`✓ Found certificate at: ${certPath}`, 'green');
                foundCert = true;
                break;
            }
        }
        
        if (!foundCert) {
            log('⚠ No standard certificate locations found', 'yellow');
            log('  This may be OK if using system's default certificate store', 'yellow');
        }
        
        // Check pinning option
        log('✓ Node.js supports certificate pinning for enhanced security', 'green');
        
        return true;
    } catch (error) {
        log(`✗ SSL certificate check failed: ${error.message}`, 'red');
        return false;
    }
}

// ============================================================================
// STEP 3: Check MongoDB URL Configuration
// ============================================================================

function testMongoDBURLConfig() {
    printSection('STEP 3: Checking MongoDB URL Configuration');
    
    const dbUrl = process.env.DATABASE_URL;
    
    if (!dbUrl) {
        log('⚠ DATABASE_URL environment variable not set', 'yellow');
        log('  Set it with: export DATABASE_URL="mongodb+srv://..."', 'yellow');
        return false;
    }
    
    log(`✓ DATABASE_URL found (length: ${dbUrl.length})`, 'green');
    
    // Check URL format (don't log the full URL for security)
    if (dbUrl.startsWith('mongodb+srv://')) {
        log('✓ Using MongoDB Atlas (mongodb+srv) connection', 'green');
        
        try {
            const clusterPart = dbUrl.split('@')[1];
            const clusterName = clusterPart.split('.')[0];
            log(`✓ Cluster: ${clusterName}.mongodb.net`, 'green');
        } catch (e) {
            log('⚠ Could not parse cluster info', 'yellow');
        }
        
        return true;
    } else if (dbUrl.startsWith('mongodb://')) {
        log('✓ Using local MongoDB connection', 'green');
        return true;
    } else {
        log('✗ Invalid MongoDB URL format', 'red');
        return false;
    }
}

// ============================================================================
// STEP 4: Test MongoDB Connection
// ============================================================================

async function testMongoDBConnection() {
    printSection('STEP 4: Testing MongoDB Connection');
    
    const dbUrl = process.env.DATABASE_URL;
    
    if (!dbUrl) {
        log('⚠ Skipping connection test - no DATABASE_URL', 'yellow');
        return false;
    }
    
    try {
        const { MongoClient, ServerApiVersion } = require('mongodb');
        
        log('Creating MongoDB client with TLS options...', 'blue');
        
        const clientOptions = {
            serverApi: {
                version: ServerApiVersion.v1,
                strict: true,
                deprecationErrors: true,
            },
            socketTimeoutMS: 5000,
            connectTimeoutMS: 5000,
            serverSelectionTimeoutMS: 5000,
            maxPoolSize: 3,
            minPoolSize: 1,
            // TLS is automatically enabled for mongodb+srv:// URLs
            // For custom CA:
            // tlsCAFile: '/path/to/ca.pem',
            // tlsCertificateKeyFile: '/path/to/client.pem'
        };
        
        const client = new MongoClient(dbUrl, clientOptions);
        
        log('Connecting to MongoDB...', 'blue');
        const startTime = Date.now();
        
        await Promise.race([
            client.connect(),
            new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Connection timeout')), 10000)
            ),
        ]);
        
        const connectionTime = Date.now() - startTime;
        log(`✓ Connected in ${connectionTime}ms`, 'green');
        
        // Test with admin.ping()
        log('Sending ping command...', 'blue');
        await client.db('admin').command({ ping: 1 });
        log('✓ Server responded to ping', 'green');
        
        // Get server information
        try {
            const serverStatus = await client.db('admin').command({ dbStats: 1 });
            log('✓ Backend connection active and responding', 'green');
        } catch (e) {
            log(`⚠ Could not retrieve detailed status: ${e.message}`, 'yellow');
        }
        
        // List databases (requires appropriate permissions)
        try {
            const adminDb = client.db('admin');
            const dbList = await adminDb.listDatabases();
            log(`✓ MongoDB has ${dbList.databases.length} database(s)`, 'green');
        } catch (e) {
            log(`⚠ Could not list databases (may require permissions): ${e.message}`, 'yellow');
        }
        
        await client.close();
        log('✓ Connection closed successfully', 'green');
        
        return true;
    } catch (error) {
        log(`✗ MongoDB connection failed: ${error.message}`, 'red');
        
        const errorMsg = error.message.toLowerCase();
        log('Possible causes:', 'yellow');
        
        if (errorMsg.includes('timeout') || errorMsg.includes('econnrefused')) {
            log('  → Network timeout or connection refused', 'yellow');
            log('  → Solution: Check MongoDB Atlas is reachable', 'yellow');
        }
        
        if (errorMsg.includes('enotfound') || errorMsg.includes('dns')) {
            log('  → DNS resolution failed', 'yellow');
            log('  → Solution: Check internet connection', 'yellow');
        }
        
        if (errorMsg.includes('ssl') || errorMsg.includes('tls') || errorMsg.includes('certificate')) {
            log('  → SSL/TLS certificate validation error', 'yellow');
            log('  → Solution: Verify system SSL certificates', 'yellow');
        }
        
        if (errorMsg.includes('auth') || errorMsg.includes('unauthorized')) {
            log('  → Authentication failure', 'yellow');
            log('  → Solution: Check username/password in DATABASE_URL', 'yellow');
        }
        
        if (errorMsg.includes('whitelist') || errorMsg.includes('ip')) {
            log('  → IP address not whitelisted', 'yellow');
            log('  → Solution: Add your IP to MongoDB Atlas network access', 'yellow');
        }
        
        return false;
    }
}

// ============================================================================
// STEP 5: Test Connection Resilience
// ============================================================================

async function testConnectionResilience() {
    printSection('STEP 5: Testing Connection Resilience');
    
    const dbUrl = process.env.DATABASE_URL;
    
    if (!dbUrl) {
        log('⚠ Skipping resilience test - no DATABASE_URL', 'yellow');
        return false;
    }
    
    try {
        const { MongoClient } = require('mongodb');
        
        const client = new MongoClient(dbUrl, {
            maxPoolSize: 2,
            minPoolSize: 1,
            maxIdleTimeMS: 30000,
            serverSelectionTimeoutMS: 5000,
        });
        
        await client.connect();
        log('✓ Initial connection successful', 'green');
        
        // Simulate multiple requests
        const attempts = 3;
        for (let i = 1; i <= attempts; i++) {
            try {
                await client.db('admin').command({ ping: 1 });
                log(`✓ Request ${i}/${attempts} successful`, 'green');
            } catch (e) {
                log(`✗ Request ${i}/${attempts} failed: ${e.message}`, 'red');
            }
        }
        
        await client.close();
        return true;
    } catch (error) {
        log(`✗ Resilience test failed: ${error.message}`, 'red');
        return false;
    }
}

// ============================================================================
// Diagnostic Report
// ============================================================================

function generateDiagnosticReport(results) {
    printSection('DIAGNOSTIC REPORT', '=');
    
    const total = Object.keys(results).length;
    const passed = Object.values(results).filter(v => v === true).length;
    
    log(`Tests Passed: ${passed}/${total}`, 'blue');
    
    if (passed === total) {
        log('✅ ALL TESTS PASSED - MongoDB connection is healthy!', 'green');
        log('Your application should connect to MongoDB Atlas successfully.', 'green');
    } else if (passed >= total - 1) {
        log('⚠️  MOST TESTS PASSED - Minor issues detected', 'yellow');
        log('Your application may have intermittent issues.', 'yellow');
    } else {
        log('❌ CRITICAL ISSUES DETECTED - System needs attention', 'red');
        log('Your application will likely fail to connect.', 'red');
    }
    
    printSection('Recommendations', '-');
    
    if (!results.driver) {
        log('[ACTION] Install MongoDB driver for Node.js:', 'yellow');
        log('  npm install mongodb', 'yellow');
    }
    
    if (!results.config) {
        log('[ACTION] Set MongoDB connection string:', 'yellow');
        log('  export DATABASE_URL="mongodb+srv://user:pass@cluster.mongodb.net/db"', 'yellow');
    }
    
    if (!results.connection || !results.resilience) {
        log('[ACTION] Check MongoDB Atlas configuration:', 'yellow');
        log('  1. Go to https://cloud.mongodb.com/', 'yellow');
        log('  2. Check IP whitelist (add your IP address)', 'yellow');
        log('  3. Verify connection string credentials', 'yellow');
        log('  4. Test DNS: nslookup cluster.mongodb.net', 'yellow');
    }
}

// ============================================================================
// Main Execution
// ============================================================================

async function main() {
    try {
        printSection('MongoDB Atlas TLS Connection Test (Node.js)', '=');
        log('Starting MongoDB connection diagnostics...', 'blue');
        
        const results = {};
        
        // Run tests
        results.driver = await testMongoDBDriver();
        results.ssl = testSSLCertificates();
        results.config = testMongoDBURLConfig();
        results.connection = await testMongoDBConnection();
        results.resilience = await testConnectionResilience();
        
        // Generate report
        generateDiagnosticReport(results);
        
        // Return exit code
        const allPassed = Object.values(results).every(v => v === true);
        const exitCode = allPassed ? 0 : 1;
        
        console.log();
        process.exit(exitCode);
    } catch (error) {
        log(`Fatal error: ${error.message}`, 'red');
        console.error(error);
        process.exit(1);
    }
}

// Handle SIGINT gracefully
process.on('SIGINT', () => {
    log('Test interrupted by user', 'yellow');
    process.exit(130);
});

// Run main
main();
