#!/usr/bin/env python3

import requests
import json

print("=" * 60)
print("🔍 Testando conectividade frontend/backend")
print("=" * 60)

# Test 1: Backend Health
print("\n1️⃣ Testando /health...")
try:
    resp = requests.get('http://localhost:8000/health', timeout=3)
    print(f"   ✅ Status: {resp.status_code}")
    print(f"   📋 Response: {resp.json()}")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# Test 2: Frontend
print("\n2️⃣ Testando frontend index...")
try:
    resp = requests.get('http://localhost:8081', timeout=3)
    print(f"   ✅ Status: {resp.status_code}")
    print(f"   📏 Tamanho resposta: {len(resp.text)} bytes")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# Test 3: Login endpoint (preflight)
print("\n3️⃣ Testando OPTIONS /api/auth/login...")
try:
    resp = requests.options('http://localhost:8000/api/auth/login', 
                           headers={'Origin': 'http://localhost:8081'},
                           timeout=3)
    print(f"   ✅ Status: {resp.status_code}")
    cors_headers = {k: v for k, v in resp.headers.items() if 'access' in k.lower() or 'cors' in k.lower()}
    if cors_headers:
        print(f"   📋 CORS Headers: {cors_headers}")
    else:
        print(f"   ⚠️  Nenhum header de CORS retornado")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# Test 4: POST Login
print("\n4️⃣ Testando POST /api/auth/login...")
try:
    resp = requests.post('http://localhost:8000/api/auth/login',
                        headers={'Content-Type': 'application/json'},
                        json={'email': 'test@test.com', 'password': 'test123'},
                        timeout=5)
    print(f"   ✅ Status: {resp.status_code}")
    print(f"   📋 Response: {resp.text[:200]}...")
except Exception as e:
    print(f"   ❌ Erro: {e}")

print("\n" + "=" * 60)
print("✅ Teste completo!")
print("=" * 60)
