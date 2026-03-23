# 🎯 TESTE RÁPIDO - Login Google

## Pré-Requisitos ✅

Todas as correções foram aplicadas:
- ✅ Backend porta: **8001**
- ✅ Frontend porta: **8081** 
- ✅ Google Client ID: Sincronizado
- ✅ Redirect URI: Correto (localhost:8001)
- ✅ Rate Limiting: Implementado em 3 endpoints

---

## Passo 1: Reiniciar Servidores

**Terminal 1 - Backend** (PowerShell):
```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 2 - Frontend** (PowerShell):
```powershell
npx vite --port 8081 --host 0.0.0.0
```

**ou use a tarefa VS Code**:
- Ctrl+Shift+B → Executar "Backend Server" (porta 8001)
- Ctrl+Shift+B → Executar "Frontend Server" (porta 8081)

---

## Passo 2: Teste Manual

### A. Botão GoogleLogin (Oficial)

1. Abra http://localhost:8081/login
2. Procure pelo **botão azul do Google** (component official)
3. Clique > Deve abrir popup de login Google
4. Selecione conta Google
5. Espere redirect para `http://localhost:8081/auth-callback`
6. Deve ver loading spinner e depois redirect para `/dashboard`

**Sucesso**: ✅ Login realizado, dashboard acessível

---

### B. Botão "Continuar com Google" (Customizado)

1. Abra http://localhost:8081/login
2. Procure pelo **botão branco com ícone Google** (abaixo do azul)
3. Clique > Deve fazer redirect direto para http://localhost:8001/api/auth/google/login
4. Servirá mesma lógica Google
5. Callback volta para frontend

**Sucesso**: ✅ Mesmo resultado do botão oficial

---

### C. Testar Cancelamento

1. Clique em "Continuar com Google" (customizado)
2. Na janela Google, clique **X** (fechar sem selecionar conta)
3. Browser volta com `?error=...` na URL
4. Frontend mostra mensagem de erro amigável

**Sucesso**: ✅ Erro tratado graciosamente

---

### D. Testar Rate Limiting (Avançado)

**GET /google/login** (3 req/min):
```bash
for i in {1..5}; do 
  curl -i "http://localhost:8001/api/auth/google/login"
  sleep 0.5
done
# Respostas 4 e 5 devem retornar 429 (Too Many Requests)
```

**POST /google** (5 req/min):
```bash
for i in {1..7}; do 
  curl -i -X POST "http://localhost:8001/api/auth/google" \
    -H "Content-Type: application/json" \
    -d '{"id_token":"fake_token"}' 
  sleep 0.5
done
# Respostas 6 e 7 devem retornar 429 (Too Many Requests)
```

---

## Erros Comuns & Soluções

### Erro: "invalid_client"
- **Causa**: VITE_GOOGLE_CLIENT_ID não carregado em main.tsx
- **Solução**: Reiniciar frontend (npm run dev)
- **Verificar**: Abrir DevTools > Console > procurar erros de GoogleOAuthProvider

### Erro: "Redirect URI does not match"
- **Causa**: GOOGLE_REDIRECT_URI no backend está errado
- **Solução**: Verificar `backend/.env` linha 96
- **Deve ser**: `http://localhost:8001/api/auth/google/callback`

### Erro: 404 no /api/auth/google/login
- **Causa**: Backend não está rodando ou porta errada
- **Solução**: Verificar se backend está em 8001
- **Teste**: `curl http://localhost:8001/api/auth/google/login`

### Erro: "Too many login attempts"
- **Causa**: Rate limiting ativado (3 tentativas/min)
- **Solução**: Aguardar 60 segundos ou resetar IP
- **Esperado**: Após 3 tentativas rápidas, retorna HTTP 429

---

## Checklist Final

- [ ] Backend rodando em `localhost:8001`
- [ ] Frontend rodando em `localhost:8081`
- [ ] Arquivo `backend/.env` tem `GOOGLE_REDIRECT_URI=http://localhost:8001/...`
- [ ] Arquivo `.env` tem `VITE_GOOGLE_CLIENT_ID` preenchido
- [ ] `src/pages/Login.tsx` linha 430 usa fallback `8001`
- [ ] GoogleLogin component renderiza sem erros
- [ ] Botão "Continuar com Google" redireciona para backend
- [ ] AuthCallback.tsx processa ?error= e ?success= na URL
- [ ] Dashboard acessível após login Google bem-sucedido

---

**Pronto para Testar!** ✅

Se encontrar problemas, verifique o Console do navegador (DevTools F12) para erros de JavaScript.
