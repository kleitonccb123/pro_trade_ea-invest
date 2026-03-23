import requests
import json

# Testar login regular
url = "http://localhost:8000/api/auth/login"
data = {
    "email": "demo@tradehub.com",
    "password": "demo123"
}

print("🔐 Testando login regular...")
try:
    response = requests.post(url, json=data, timeout=10)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("✅ Login bem-sucedido!")
        print(f"   Mensagem: {result.get('message')}")
        print(f"   Token type: {result.get('token_type')}")
        print(f"   User: {result.get('user', {}).get('email')}")
        print(f"   Access token length: {len(result.get('access_token', ''))}")
    else:
        error = response.json()
        print(f"❌ Erro: {error.get('message', 'Erro desconhecido')}")

except Exception as e:
    print(f"❌ Erro de conexão: {str(e)}")