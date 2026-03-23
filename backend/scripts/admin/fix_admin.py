#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para apagar e recriar o admin com uma nova senha"""

import requests
import json
import sys

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

print("Registrando novo admin...")

# Tentar registrar um novo admin
register_url = "http://localhost:8000/api/auth/register"
data = {
    "email": "root@admin.com",
    "password": "admin123",
    "name": "Root Admin"
}

print(f"[*] Registrando novo admin em {register_url}")
response = requests.post(register_url, json=data)
print(f"[*] Status: {response.status_code}")
print(f"[*] Response: {response.json()}")

# Agora fazer login para confirmar
login_url = "http://localhost:8000/api/auth/login"
login_data = {
    "email": "root@admin.com",
    "password": "admin123"
}

print(f"\n[*] Testando login...")
response = requests.post(login_url, json=login_data)
print(f"[*] Status: {response.status_code}")
if response.status_code == 200:
    print("[OK] Login bem-sucedido!")
    result = response.json()
    print(f"[OK] Email: {result.get('user', {}).get('email')}")
    print(f"[OK] Token: {result.get('access_token', '')[:50]}...")
else:
    print(f"[ERROR] Erro: {response.text}")
