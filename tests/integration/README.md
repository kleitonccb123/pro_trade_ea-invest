# 🧪 Teste de Integração - Caminho Feliz

## Descrição

Script de teste automatizado que valida o fluxo completo do sistema Crypto Trade Hub:

1. ✅ **Health Check** - Validar que o servidor está respondendo
2. 👤 **Autenticação** - Registrar usuário e fazer login
3. 🤖 **Criação de Bot** - Criar novo bot de trading
4. ▶️ **Iniciar Bot** - Iniciar a execução do bot
5. 🔍 **Verificar Status** - Confirmar que bot está rodando
6. ⏹️ **Cleanup** - Parar o bot e limpar dados

## Requisitos

### Backend em execução
```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Dependências Python
```bash
pip install pytest pytest-asyncio httpx
```

## Como Executar

### Opção 1: Porta padrão (8000)
```bash
pytest tests/integration/test_happy_path.py -v -s
```

### Opção 2: Porta customizada (ex: 8001)
```bash
pytest tests/integration/test_happy_path.py -v -s --base-url http://localhost:8001
```

### Opção 3: Variável de ambiente
```bash
# Windows PowerShell
$env:BASE_URL="http://localhost:8001"; pytest tests/integration/test_happy_path.py -v -s

# Linux/Mac
BASE_URL=http://localhost:8001 pytest tests/integration/test_happy_path.py -v -s
```

### Opção 4: Executar direto como script
```bash
python tests/integration/test_happy_path.py
```

## Output Esperado

✅ **Se todos os testes passarem:**

```
🎉 TESTE INTEGRADO PASSOU! SISTEMA ESTÁ FUNCIONANDO!

test_happy_path_complete PASSED                     [100%]
=============================== 1 passed in 2.34s ========
```

## O Que Cada Teste Valida

| Teste | Validação |
|-------|-----------|
| `test_01_health_check` | Backend está respondendo |
| `test_02_user_registration_and_login` | Autenticação funciona |
| `test_03_create_bot` | Endpoint POST /bots retorna 201 |
| `test_04_get_bot_details` | Bot foi persistido no banco |
| `test_05_start_bot` | Endpoint POST /bots/{id}/start funciona |
| `test_06_verify_bot_running` | Campo `is_running=True` é retornado |
| `test_07_stop_bot` | Cleanup: bot pode ser parado |
| `test_happy_path_complete` | **Fluxo completo ponta-a-ponta** |

## Troubleshooting

### ❌ "Connection refused"
Backend não está rodando. Verifique:
```bash
# Confirmar que o servidor está rodando
curl http://localhost:8000/health
```

### ❌ "401 Unauthorized"
Token JWT inválido. Verifique logs de autenticação no backend.

### ❌ "404 Not Found"
Endpoint pode estar em desenvolvimento. Verifique implementação em `backend/app/bots/router.py`.

### ❌ Timeout
Aumentar timeout:
```bash
pytest tests/integration/test_happy_path.py --timeout 60
```

## Logs Detalhados

Os testes geram logs estruturados:
- Cada teste tem uma seção clara com `====`
- Payloads e responses são exibidas em JSON
- Status de cada operação é marcado com ✅ ⚠️ ❌

## Próximos Passos

- ✅ Se passar: Pode ir direto para **Passo 3 (Segurança)**
- ❌ Se falhar: Veja a mensagem de erro exata para diagnosticar
