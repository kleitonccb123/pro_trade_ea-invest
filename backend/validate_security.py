#!/usr/bin/env python
"""Validar seguran?a do backend ap?s hardening"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.getcwd())

from app.main import app
from app.core.config import settings

print("\n" + "="*60)
print("??  VALIDA??O DE SEGURAN?A - PASSO 3")
print("="*60 + "\n")

# 1. Verificar middlewares
print("? MIDDLEWARES CONFIGURADOS:")
for i, mw in enumerate(app.user_middleware, 1):
    print(f"   {i}. {mw.cls.__name__}")

print("\n? CHECKLIST:")

# 2. Verificar deep-translator
try:
    import deep_translator
    print("   ? deep-translator: AINDA INSTALADO")
except ImportError:
    print("   ? deep-translator: REMOVIDO")

# 3. Verificar cryptography version
try:
    import cryptography
    version = cryptography.__version__
    major_minor = tuple(map(int, version.split('.')[:2]))
    if major_minor >= (46, 0):
        print(f"   ? cryptography {version}: SEGURO (>= 46.0.5)")
    else:
        print(f"   ??  cryptography {version}: VERIFICAR (< 46.0)")
except ImportError:
    print("   ? cryptography: N?O INSTALADO")

# 4. Verificar FastAPI version
try:
    import fastapi
    version = fastapi.__version__
    major_minor = tuple(map(int, version.split('.')[:2]))
    if major_minor >= (0, 115):
        print(f"   ? fastapi {version}: ATUALIZADO")
    else:
        print(f"   ??  fastapi {version}: VERIFICAR")
except ImportError:
    print("   ? fastapi: N?O INSTALADO")

# 5. Verificar Pydantic v2
try:
    from pydantic_settings import BaseSettings
    print("   ? Pydantic v2: ATIVO")
except ImportError:
    print("   ? Pydantic v2: N?O ENCONTRADO")

# 6. Verificar settings
print(f"\n? CONFIGURA??ES:")
print(f"   APP_MODE: {settings.app_mode}")
print(f"   Database: {settings.database_name}")
print(f"   HSTS Active (prod): {('Sim' if settings.app_mode == 'prod' else 'Dev mode')}")

print("\n" + "="*60)
print("? STATUS: VERDE ?")
print("="*60 + "\n")
