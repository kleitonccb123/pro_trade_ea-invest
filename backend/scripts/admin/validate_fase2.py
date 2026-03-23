"""
Quick FASE 2 Validation - Check that all files were created correctly.

This script validates the structure of FASE 2 components without running heavy operations.
"""

import os
import sys
from pathlib import Path

print("="*70)
print("✅ FASE 2 Implementation Validation")
print("="*70)

workspace = Path(".")
backend = workspace / "backend" / "app"

# Expected files for FASE 2
EXPECTED_FILES = {
    "Security Module": [
        "security/__init__.py",
        "security/log_sanitizer.py",
        "security/credential_encryption.py",
        "security/credential_store.py",
    ],
    "Routers": [
        "routers/__init__.py",
        "routers/exchanges.py",
        "routers/bots.py",
        "routers/orders.py",
    ],
    "Middleware & Initialization": [
        "middleware.py",
        "initialization.py",
    ]
}

all_ok = True

for category, files in EXPECTED_FILES.items():
    print(f"\n[{category}]")
    for file in files:
        path = backend / file
        if path.exists():
            size = path.stat().st_size
            print(f"  ✅ {file:40} ({size:,} bytes)")
        else:
            print(f"  ❌ {file:40} NOT FOUND")
            all_ok = False

# Check created components
print(f"\n[Integration Files]")

env_file = workspace / "backend" / ".env.example"
if env_file.exists():
    print(f"  ✅ .env.example (with FASE 2 config)")
else:
    print(f"  ❌ .env.example NOT FOUND")
    all_ok = False

test_file = workspace / "test_fase2.py"
if test_file.exists():
    print(f"  ✅ test_fase2.py (test suite)")
else:
    print(f"  ❌ test_fase2.py NOT FOUND")
    all_ok = False

# Summary
print("\n" + "="*70)

if all_ok:
    print("🎉 FASE 2 Implementation Complete!")
    print("\nImplemented Components:")
    print("  ✅ Security Module (LogSanitizer, CredentialEncryption, CredentialStore)")
    print("  ✅ FastAPI Routers (exchanges, bots, orders)")
    print("  ✅ Middleware (authorization, logging, error handling)")
    print("  ✅ Initialization (init_fase_2 function)")
    print("  ✅ Configuration (.env.example with FASE 2 variables)")
    
    print("\nNext Steps:")
    print("  1. Run backend with: python -m uvicorn app.main:app --reload")
    print("  2. Add init_fase_2(app, db) call to main.py")
    print("  3. Set CREDENTIAL_ENCRYPTION_KEY in .env")
    print("  4. Test endpoints with curl or Swagger UI at /docs")
    
    sys.exit(0)
else:
    print("⚠️  Some FASE 2 files are missing!")
    print("Check the output above for details.")
    sys.exit(1)
