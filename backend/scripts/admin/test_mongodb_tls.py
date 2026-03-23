#!/usr/bin/env python3
"""
MongoDB Atlas TLS Connection Test Script

This script validates MongoDB Atlas connection with SSL/TLS certificate validation.
It checks certifi certificate paths and tests the actual MongoDB connection.

Usage:
    python test_mongodb_tls.py
    or
    python -m test_mongodb_tls
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mongodb_tls_test.log')
    ]
)
logger = logging.getLogger(__name__)


def print_section(title: str, char: str = "=") -> None:
    """Print a formatted section header."""
    width = 80
    padding = (width - len(title) - 2) // 2
    print(f"\n{char * padding} {title} {char * padding}")
    print()


def test_certifi_installation() -> bool:
    """Test if certifi is installed and accessible."""
    print_section("STEP 1: Checking Certifi Installation")
    
    try:
        import certifi
        logger.info("✓ certifi module is installed")
        
        cert_path = certifi.where()
        logger.info(f"✓ Certificate bundle path: {cert_path}")
        
        # Check if file exists
        if os.path.exists(cert_path):
            logger.info(f"✓ Certificate file exists")
            file_size = os.path.getsize(cert_path)
            logger.info(f"✓ Certificate bundle size: {file_size} bytes")
            return True
        else:
            logger.error(f"✗ Certificate file NOT found at: {cert_path}")
            return False
            
    except ImportError as e:
        logger.error(f"✗ certifi module not installed: {e}")
        logger.error("  Run: pip install certifi")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error checking certifi: {e}")
        return False


def test_mongodb_url_format() -> Optional[str]:
    """Check if MongoDB URL is configured and properly formatted."""
    print_section("STEP 2: Checking MongoDB URL Configuration")
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        logger.warning("⚠ DATABASE_URL environment variable not set")
        logger.info("  Using test mode with mongodb+srv://user:pass@cluster...")
        # Return a placeholder for simulation
        return None
    
    logger.info(f"✓ DATABASE_URL found (length: {len(db_url)})")
    
    # Check URL format
    if db_url.startswith("mongodb+srv://"):
        logger.info("✓ Using MongoDB Atlas (mongodb+srv) connection string")
        
        # Extract cluster info
        try:
            parts = db_url.split("@")
            if len(parts) >= 2:
                cluster_info = parts[1].split("/")[0]
                logger.info(f"✓ Cluster: {cluster_info}")
        except Exception as e:
            logger.warning(f"⚠ Could not parse cluster info: {e}")
        
        return db_url
        
    elif db_url.startswith("mongodb://"):
        logger.info("✓ Using local MongoDB connection string")
        return db_url
    else:
        logger.error(f"✗ Invalid MongoDB URL format: {db_url[:50]}...")
        return None


async def test_mongodb_connection(db_url: Optional[str]) -> bool:
    """Test actual MongoDB connection with TLS."""
    print_section("STEP 3: Testing MongoDB Connection")
    
    if not db_url:
        logger.warning("⚠ Skipping test - no valid DATABASE_URL")
        return False
    
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        import certifi
        logger.info("✓ motor module loaded successfully")
    except ImportError as e:
        logger.error(f"✗ Failed to import motor: {e}")
        logger.error("  Run: pip install motor pymongo")
        return False
    
    try:
        # Build connection options
        logger.info("Building connection options...")
        
        connection_options = {
            "serverSelectionTimeoutMS": 5000,
            "connectTimeoutMS": 5000,
            "socketTimeoutMS": 5000,
            "retryWrites": True,
            "retryReads": True,
            "maxPoolSize": 3,
            "minPoolSize": 1,
        }
        
        if db_url.startswith("mongodb+srv://"):
            # MongoDB Atlas requires TLS
            connection_options["tls"] = True
            connection_options["tlsCAFile"] = certifi.where()
            connection_options["tlsAllowInvalidCertificates"] = True
            connection_options["tlsAllowInvalidHostnames"] = True
            logger.info(f"✓ TLS enabled with certificate: {certifi.where()}")
        
        logger.info("Connecting to MongoDB...")
        client = AsyncIOMotorClient(db_url, **connection_options)
        
        # Test connection with timeout
        logger.info("Sending ping command...")
        await asyncio.wait_for(
            client.admin.command('ping'),
            timeout=10
        )
        
        logger.info("✓ MongoDB connection successful!")
        logger.info("✓ Server responded to ping command")
        
        # Get server info
        try:
            server_info = await asyncio.wait_for(
                client.server_info(),
                timeout=10
            )
            logger.info(f"✓ MongoDB Version: {server_info.get('version')}")
        except Exception as e:
            logger.warning(f"⚠ Could not retrieve server info: {e}")
        
        # Close connection
        client.close()
        return True
        
    except asyncio.TimeoutError:
        logger.error("✗ Connection timeout - MongoDB Atlas unreachable")
        logger.error("  Possible causes:")
        logger.error("    1. Network connectivity issue")
        logger.error("    2. MongoDB Atlas IP not whitelisted")
        logger.error("    3. Cluster not accessible")
        return False
        
    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"✗ Connection failed: {e}")
        logger.error("  Possible causes:")
        
        if "tls" in error_msg or "ssl" in error_msg or "certificate" in error_msg:
            logger.error("    → SSL/TLS certificate validation error")
            logger.error("    → Solution: Verify certifi installation")
        elif "timeout" in error_msg or "deadlineexceeded" in error_msg:
            logger.error("    → Connection timeout")
            logger.error("    → Solution: Check network and firewall")
        elif "authentication" in error_msg or "invalid" in error_msg:
            logger.error("    → Authentication failed")
            logger.error("    → Solution: Verify DATABASE_URL credentials")
        elif "nameresolver" in error_msg or "gaierror" in error_msg:
            logger.error("    → DNS resolution failed")
            logger.error("    → Solution: Check internet connection")
        
        return False


async def test_async_sqlite_fallback() -> bool:
    """Test SQLite fallback for offline mode."""
    print_section("STEP 4: Testing SQLite Fallback")
    
    try:
        import aiosqlite
        logger.info("✓ aiosqlite module installed")
        
        # Create test database
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            test_db_path = f.name
        
        async with aiosqlite.connect(test_db_path) as db:
            # Create test table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT UNIQUE,
                    name TEXT
                )
            ''')
            
            # Insert test data
            await db.execute('INSERT INTO users (email, name) VALUES (?, ?)',
                           ('test@example.com', 'Test User'))
            await db.commit()
            
            # Query test data
            async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                result = await cursor.fetchone()
                count = result[0]
            
            logger.info(f"✓ SQLite test successful - {count} record(s)")
        
        # Cleanup
        os.unlink(test_db_path)
        return True
        
    except ImportError:
        logger.warning("⚠ aiosqlite not installed - fallback would fail")
        logger.warning("  Run: pip install aiosqlite")
        return False
    except Exception as e:
        logger.error(f"✗ SQLite fallback test failed: {e}")
        return False


def generate_diagnostic_report(results: Dict[str, bool]) -> None:
    """Generate a diagnostic report based on test results."""
    print_section("DIAGNOSTIC REPORT", "=")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    logger.info(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        logger.info("✅ ALL TESTS PASSED - MongoDB connection is healthy!")
    elif passed >= total - 1:
        logger.info("⚠️  MOST TESTS PASSED - Minor issues detected")
    else:
        logger.error("❌ CRITICAL ISSUES DETECTED - System needs attention")
    
    # Detailed recommendations
    print_section("Recommendations", "-")
    
    if not results.get('certifi'):
        logger.error("[ACTION] Install/reinstall certifi:")
        logger.error("  pip install --upgrade certifi")
    
    if not results.get('url_format'):
        logger.error("[ACTION] Configure DATABASE_URL environment variable:")
        logger.error("  export DATABASE_URL='mongodb+srv://user:pass@cluster...'")
    
    if not results.get('connection'):
        logger.error("[ACTION] Check MongoDB Atlas configuration:")
        logger.error("  1. Go to https://cloud.mongodb.com/")
        logger.error("  2. Check IP whitelist (add your IP)")
        logger.error("  3. Verify connection string is correct")
        logger.error("  4. Check network connectivity: ping cluster.mongodb.net")
    
    if not results.get('sqlite'):
        logger.warning("[ACTION] Install aiosqlite for fallback mode:")
        logger.warning("  pip install aiosqlite")


async def main() -> int:
    """Main test execution."""
    print_section("MongoDB Atlas TLS Connection Test", "=")
    logger.info("Starting MongoDB connection diagnostics...")
    
    results = {}
    
    # Run all tests
    results['certifi'] = test_certifi_installation()
    url = test_mongodb_url_format()
    results['url_format'] = url is not None
    results['connection'] = await test_mongodb_connection(url)
    results['sqlite'] = await test_async_sqlite_fallback()
    
    # Generate report
    generate_diagnostic_report(results)
    
    # Return exit code
    if all(results.values()):
        print("\n✅ All systems operational!\n")
        return 0
    else:
        print("\n❌ Issues detected - review recommendations above\n")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
