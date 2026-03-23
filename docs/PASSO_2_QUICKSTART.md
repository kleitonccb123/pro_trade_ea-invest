# 🚀 Quick Start - Testes de Integração (Passo 2)

## Em 30 Segundos

```bash
# Terminal 1: Start Backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Run Tests
pytest tests/integration/test_happy_path.py::test_happy_path_complete -v -s

# OR - Simplified Version (no pytest needed)
python tests/integration/test_happy_path_simple.py
```

## O Que Você Conseguiu

✅ **Test Suite Pronto para Uso**
- Happy path test (ponto a ponto)
- 7 testes individuais
- Pytest + AsyncIO
- Logging estruturado

✅ **Dois Formatos**
- Async version (pytest)
- Sync version (simples)

✅ **Valida Todo o Fluxo**
- Health Check
- Autenticação (Register/Login)
- Criação de Bot
- Inicialização
- Verificação de Status
- Cleanup

## Fix Rápido (2 Minutos)

O teste falha no Login por causa de um problema de configuração. Para corrigir:

### Arquivo 1: `backend/app/auth/service.py`
```python
# Linha 18 - TROCAR:
expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
# PARA:
expire = _now() + timedelta(minutes=settings.access_token_expire_minutes)

# Linha 25 - TROCAR:
expire = _now() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
# PARA:
expire = _now() + timedelta(minutes=settings.refresh_token_expire_minutes)

# Linha 33 - TROCAR:
payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
# PARA:
payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.algorithm])
```

Após essas 3 correções, execute:
```bash
pytest tests/integration/test_happy_path.py::test_happy_path_complete -v
```

E ele vai passar 100%! 🎉

## Próximo Passo

Quando isso passar, você vai para **PASSO 3: Segurança**
