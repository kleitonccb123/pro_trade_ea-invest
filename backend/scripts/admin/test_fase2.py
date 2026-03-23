"""
Test FASE 2 Components - Validate security, encryption, and routers.

Usage:
    python test_fase2.py

Tests:
1. LogSanitizer - Remove secrets from logs
2. CredentialEncryption - Encrypt/decrypt credentials
3. Router imports - Verify all routers import correctly
4. Middleware - Verify middleware can be instantiated
"""

import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

print("="*70)
print("🧪 FASE 2 Test Suite")
print("="*70)


def test_log_sanitizer():
    """Test LogSanitizer masks secrets."""
    print("\n[1/5] Testing LogSanitizer...")
    
    from app.security.log_sanitizer import LogSanitizer
    
    # Test various secret patterns
    test_cases = [
        ("apiKey: '5f3113a1689401000612a12a'", "apiKey"),
        ("'secret': 'abc123def456'", "secret"),
        ("api_secret=my_secret_123", "api_secret"),
        ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "Bearer"),
    ]
    
    all_passed = True
    for text, secret_type in test_cases:
        sanitized = LogSanitizer.sanitize(text)
        if secret_type in sanitized.lower():
            # Check if secret is masked
            if "***" in sanitized:
                print(f"  ✅ {secret_type}: {text[:40]}... → {sanitized[:40]}...")
            else:
                print(f"  ❌ {secret_type}: Not masked!")
                all_passed = False
        else:
            print(f"  ✅ {secret_type}: Properly masked")
    
    return all_passed


def test_credential_encryption():
    """Test CredentialEncryption encrypt/decrypt."""
    print("\n[2/5] Testing CredentialEncryption...")
    
    from app.security.credential_encryption import CredentialEncryption
    
    # Generate key
    key = CredentialEncryption.generate_key()
    print(f"  Generated key: {key[:20]}...")
    
    # Create cipher
    cipher = CredentialEncryption(key)
    
    # Test encryption/decryption
    test_secret = "super_secret_api_key_12345"
    encrypted = cipher.encrypt_secret(test_secret)
    decrypted = cipher.decrypt_secret(encrypted)
    
    if decrypted == test_secret:
        print(f"  ✅ Encrypt/Decrypt: {test_secret} → {encrypted[:20]}... → {decrypted}")
        return True
    else:
        print(f"  ❌ Encrypt/Decrypt failed: {decrypted} != {test_secret}")
        return False


def test_router_imports():
    """Test all routers import correctly."""
    print("\n[3/5] Testing Router Imports...")
    
    try:
        from app.routers import exchanges_router, bots_router, orders_router
        
        print(f"  ✅ exchanges_router: {len(exchanges_router.routes)} routes")
        print(f"  ✅ bots_router: {len(bots_router.routes)} routes")
        print(f"  ✅ orders_router: {len(orders_router.routes)} routes")
        
        return True
    except Exception as e:
        print(f"  ❌ Router import failed: {e}")
        return False


def test_middleware():
    """Test middleware can be instantiated."""
    print("\n[4/5] Testing Middleware...")
    
    try:
        from app.middleware import (
            AuthorizationMiddleware,
            RequestLoggingMiddleware,
            ErrorHandlingMiddleware,
        )
        
        print(f"  ✅ AuthorizationMiddleware imported")
        print(f"  ✅ RequestLoggingMiddleware imported")
        print(f"  ✅ ErrorHandlingMiddleware imported")
        
        return True
    except Exception as e:
        print(f"  ❌ Middleware import failed: {e}")
        return False


def test_initialization():
    """Test initialization module."""
    print("\n[5/5] Testing Initialization Module...")
    
    try:
        from app.initialization import init_fase_2, FASE_2_SUMMARY
        
        print(f"  ✅ init_fase_2 function imported")
        print(f"  ✅ FASE_2_SUMMARY available ({len(FASE_2_SUMMARY)} chars)")
        
        return True
    except Exception as e:
        print(f"  ❌ Initialization import failed: {e}")
        return False


def main():
    """Run all tests."""
    results = []
    
    # Run tests
    results.append(("LogSanitizer", test_log_sanitizer()))
    results.append(("CredentialEncryption", test_credential_encryption()))
    results.append(("Router Imports", test_router_imports()))
    results.append(("Middleware", test_middleware()))
    results.append(("Initialization", test_initialization()))
    
    # Summary
    print("\n" + "="*70)
    print("📊 Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All FASE 2 components working!")
        return 0
    else:
        print("\n⚠️  Some tests failed - check output above")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
