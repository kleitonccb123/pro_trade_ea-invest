# 🔧 TESTE: Google OAuth 401 - Diagnóstico com Logs Detalhados

**Status**: Backend está rodando com LOGS DETALHADOS na porta 8001

---

##  ⚡ PASSO 1: Abrir Console do Backend

1. Procure pela janela/terminal do PowerShell onde o backend está rodando
2. Ou abra nova janela PowerShell e vá para a pasta do projeto:

```powershell
cd C:\Users\CLIENTE\Downloads\crypto-trade-hub-main\crypto-trade-hub-main
```

Este console MOSTRARÁ os logs [GOOGLE_AUTH] e [VALIDATE_GOOGLE_TOKEN] em tempo real.

---

##  ⚡ PASSO 2: Testar Google Login

1. Abra browser: **http://localhost:8081/login**
2. Clique no botão azul **"Fazer Login com o Google"**
3. Selecione sua conta Google e confirme
4. **OBSERVE O TERMINAL DO BACKEND**

---

##  ⚡ PASSO 3: Procure  por esses Logs

Se tudo funcionar, verá:

```
[GOOGLE_AUTH] Requisição POST /google recebida
[GOOGLE_AUTH] Email enviado: seu.email@gmail.com
[GOOGLE_AUTH] Name enviado: Seu Nome
[GOOGLE_AUTH] Token length: 2500
[GOOGLE_AUTH] Iniciando validação do token...

[VALIDATE_GOOGLE_TOKEN] Iniciando validação
[VALIDATE_GOOGLE_TOKEN] GOOGLE_CLIENT_ID: 477006347863-5p274av1ob2q7mhbgfmsbf2pgt4hpeli.apps.googleusercontent.com
[VALIDATE_GOOGLE_TOKEN] Chamando verify_oauth2_token...
[VALIDATE_GOOGLE_TOKEN] Token verificado com sucesso
[VALIDATE_GOOGLE_TOKEN] Email: seu.email@gmail.com

[GOOGLE_AUTH] Token validado com sucesso!
[GOOGLE_AUTH] Dados extraídos do token:
[GOOGLE_AUTH]   Email: seu.email@gmail.com
[GOOGLE_AUTH]   Name: Seu Nome
[GOOGLE_AUTH]   Google ID: 123456789...
...
✓ Autenticação Google bem-sucedida: seu.email@gmail.com (ID: abc123)
```

**Resultado**: Dashboard carrega, login funciona ✅

---

##  ⚠️ Se Receber ERRO 401

### Cenário 1: Token inválido/expirado

```
[GOOGLE_AUTH] Requisição POST /google recebida
[GOOGLE_AUTH] Iniciando validação do token...
[VALIDATE_GOOGLE_TOKEN] Iniciando validação
[VALIDATE_GOOGLE_TOKEN] GOOGLE_CLIENT_ID: 477006347863-...
[VALIDATE_GOOGLE_TOKEN] Chamando verify_oauth2_token...
[VALIDATE_GOOGLE_TOKEN] Exception ValueError: Token nao foi emitido pelo Google
```

**Motivo**: Token está vencido ou inválido\
**Solução**: Faça login de novo no Google (não use browser cache)

### Cenário 2: GOOGLE_CLIENT_ID faltando/errado

```
[GOOGLE_AUTH] Requisição POST /google recebida
[VALIDATE_GOOGLE_TOKEN] Missing GOOGLE_CLIENT_ID
```

**Motivo**: backend/.env não tem GOOGLE_CLIENT_ID ou é inválido\
**Solução**: 
1. Abra `backend/.env`
2. Procure por `GOOGLE_CLIENT_ID`
3. Deve ser: `477006347863-5p274av1ob2q7mhbgfmsbf2pgt4hpeli.apps.googleusercontent.com`
4. Se diferente, copie o correto
5. Reinicie backend

### Cenário 3: Frontend não está enviando token

```
[GOOGLE_AUTH] Email enviado: 
[GOOGLE_AUTH] Token length: 0
```

**Motivo**: Componente GoogleLogin não está funcionando\
**Solução**: Verificar se VITE_GOOGLE_CLIENT_ID está correto no `.env` frontend

---

##  🔍 O que foi adicionado

Adicionei logs em 2 lugares:

### 1. Função `validate_google_token()` (linha 41)
```python
print(f"[VALIDATE_GOOGLE_TOKEN] Iniciando validação")
print(f"[VALIDATE_GOOGLE_TOKEN] GOOGLE_CLIENT_ID: {GOOGLE_CLIENT_ID}")
print(f"[VALIDATE_GOOGLE_TOKEN] Chamando verify_oauth2_token...")
...
```

### 2. Endpoint `@router.post("/google")` (linha 538)
```python
print(f"[GOOGLE_AUTH] Requisição POST /google recebida")
print(f"[GOOGLE_AUTH] Email enviado: {req.email}")
print(f"[GOOGLE_AUTH] Token length: {len(req.id_token)}")
...
```

Esses logs mostram EXATAMENTE onde está falhando e qual é o erro específico.

---

##  📋 Checklist Antes de Testar

- [ ] Backend está rodando na porta 8001
- [ ] Frontend está rodando na porta 8081
- [ ] `backend/.env` tem GOOGLE_CLIENT_ID
- [ ] `backend/.env` tem GOOGLE_CLIENT_SECRET
- [ ] `backend/.env` tem GOOGLE_REDIRECT_URI=http://localhost:8001/api/auth/google/callback
- [ ] `.env` frontend tem VITE_GOOGLE_CLIENT_ID
- [ ] `.env` frontend tem VITE_API_BASE_URL=http://localhost:8001

---

##  📞 Próximas Ações

1. **Faça o teste** e observe os logs
2. **Copie os logs** que aparecerem (especialmente os com erro/exception)
3. **Mostre para mim** qual log exato está aparecendo
4. Vou analisar e corrigir o problema específico

---

**Importante**: Deixe o console do backend aberto enquanto testa. Os logs desaparecem rápido, então observe enquanto tenta fazer login!
