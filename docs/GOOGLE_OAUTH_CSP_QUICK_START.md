# ⚡ Quick Reference - Teste Rápido Google OAuth CSP

**Tempo:** 5 minutos para testar tudo

---

## 1️⃣ Verificar se Middleware Está Ativo

```bash
# Terminal - verificar headers
curl -I http://localhost:8000/health | grep "Content-Security-Policy"

# Esperado:
# Content-Security-Policy: default-src 'self'; script-src ...
```

---

## 2️⃣ Testar CORS

```bash
curl -X OPTIONS http://localhost:8000/auth/google \
  -H "Origin: http://localhost:8081" \
  -v 2>&1 | grep -i "access-control"

# Esperado:
# Access-Control-Allow-Origin: http://localhost:8081
```

---

## 3️⃣ Testar no Browser

### Abrir DevTools (F12 > Console)

```javascript
// Teste 1: Google GSI Client (script)
fetch('https://accounts.google.com/gsi/client')
  .then(r => console.log('✅ GSI Script:', r.ok))
  .catch(e => console.log('❌ Error:', e.message))

// Teste 2: Google OAuth endpoint
fetch('https://accounts.google.com/signin/oauth/token')
  .then(r => console.log('✅ OAuth:', r.ok))
  .catch(e => console.log('❌ Error:', e.message))

// Teste 3: Google APIs
fetch('https://www.googleapis.com/oauth2/v1/userinfo')
  .then(r => console.log('✅ APIs:', r.ok))
  .catch(e => console.log('❌ Error:', e.message))
```

**Esperado:** 3 "✅" ou erros autorizados (não CSP bloqueado)

---

## 4️⃣ Testar Login Completo

1. Abrir: `http://localhost:8081`
2. Clicar: **"Sign in with Google"**
3. Verificar:
   - ✅ Google popup abre
   - ✅ Pode fazer login
   - ✅ Token é gerado
   - ✅ **Foto de perfil carrega**

**Erros esperados:** NENHUM no console

---

## 5️⃣ Se Não Funcionar...

### Passo A: Testar em Incógnito
```
Chrome/Edge: Ctrl + Shift + N
Firefox: Ctrl + Shift + P  
Safari: Cmd + Shift + N
```
**Funciona em Incógnito?** → Extensão browser culpada

### Passo B: Desabilitar Extensões
1. chrome://extensions (ou about:addons no Firefox)
2. Desabilitar uma por uma
3. Testar cada vez
4. Se voltar a funcionar = encontrou a extensão

**Extensões suspeitas:**
- Ghostery ⚠️
- uBlock Origin ⚠️
- Privacy Badger ⚠️
- Adblock Plus ⚠️

### Passo C: Verificar CSP Exata

```javascript
// No DevTools Console:
fetch('/health').then(r => {
  const csp = r.headers.get('content-security-policy');
  console.log('CSP:', csp);
})
```

Copiar e colar a saída nos documentos de referência

### Passo D: Backend log
```bash
# Procurar por linha:
# CSP Applied [🧪 DEVELOPMENT] for /

# Se não aparecer = middleware não foi adicionado
```

---

## 📋 Resumo CSP Implementada

### Dev (padrão)
```
✅ Localhost 8000, 8081
✅ Google OAuth
✅ WebSocket
✅ Hot reload
```

### Production (quando ENVIRONMENT=production)
```
✅ Apenas HTTPS
✅ Google OAuth
✅ Sem localhost
✅ Mais restritiva
```

---

## 🎯 Sucesso = Todos Esses Sinais Verdes

- [ ] `curl` mostra `Content-Security-Policy` header
- [ ] `curl` mostra `Access-Control-Allow-Origin`
- [ ] DevTools console sem erros CSP
- [ ] Google popup abre e funciona
- [ ] Foto de perfil carrega após login
- [ ] Network tab mostra requests Google com status 200

---

## 🆘 Precisa de Ajuda?

**Se tiver dúvida, verificar estes documentos na ordem:**

1. **[GOOGLE_OAUTH_CSP_SUMMARY.md](GOOGLE_OAUTH_CSP_SUMMARY.md)** ← LEIA PRIMEIRO
2. **[GOOGLE_OAUTH_CSP_IMPLEMENTATION_GUIDE.md](GOOGLE_OAUTH_CSP_IMPLEMENTATION_GUIDE.md)** ← Testes detalhados
3. **[GOOGLE_OAUTH_CSP_TECHNICAL_DETAILS.md](GOOGLE_OAUTH_CSP_TECHNICAL_DETAILS.md)** ← Detalhes avançados
4. **[GOOGLE_LOGIN_CSP_ERRORS_COMPLETE.md](GOOGLE_LOGIN_CSP_ERRORS_COMPLETE.md)** ← Análise completa

---

**Tempo Total de Implementação:** ✅ COMPLETO (0 tempo necessário, já está feito!)

**Próximo:** Testar por 5 minutos e confirmar sucesso 🎉
