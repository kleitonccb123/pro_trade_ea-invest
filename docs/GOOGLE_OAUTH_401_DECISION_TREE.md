# 🔍 ÁRVORE DE DECISÃO - Erro 401: invalid_client

**Como encontrar EXATAMENTE qual é o problema**

---

## 🎯 Comece Aqui

### Pergunta 1: Você tem um `GOOGLE_CLIENT_ID`?

```
┌─ SIM → Pergunta 2
└─ NÃO → [PROBLEMA #1] Abrir: GOOGLE_OAUTH_401_INVALID_CLIENT_FIX.md, PASSO 2
```

---

## 🔍 Se tem Client ID

### Pergunta 2: Você sabe de cor qual é o seu Client ID?

```
┌─ SIM → Pergunta 3
└─ NÃO → Ir para VERIFICAÇÃO A (descobrir o valor)
```

**VERIFICAÇÃO A: Descobrir o Client ID**

```bash
# Terminal
cd backend
cat .env | grep GOOGLE_CLIENT_ID

# Resultado esperado:
# GOOGLE_CLIENT_ID=123456789-abcdef...apps.googleusercontent.com
         ↓
      Copie este valor e anote em um lugar

# Se vir vazio ou "GOOGLE_CLIENT_ID=" sem valor
→ [PROBLEMA #1] Vá para GOOGLE_OAUTH_401_INVALID_CLIENT_FIX.md, PASSO 3
```

---

## ✔️ Se sabe o Client ID

### Pergunta 3: O Client ID tem `.apps.googleusercontent.com` no final?

```
Formato correto:
123456789012-abcdefghijklmnopqrstuvwxyz1234567.apps.googleusercontent.com
                                              ↑
                            Deve terminar com isso

┌─ SIM → Pergunta 4
└─ NÃO → [PROBLEMA #2] Valor foi digitado errado
         Ação: Abrir Google Cloud, copiar a EXATA e colar novamente
```

---

## 🔐 Formato Correto?

### Pergunta 4: O formato é: números-letras.apps.googleusercontent.com?

```
Padrão:
[números]-[letras maiúsculas/minúsculas][números].apps.googleusercontent.com

Exemplos CORRETOS:
✅ 123456789012-abc123xyz.apps.googleusercontent.com
✅ 987654321098-XYZ123abc.apps.googleusercontent.com
✅ 111111111111-aaabbbccc123xyz.apps.googleusercontent.com

Exemplos ERRADOS:
❌ abc123xyz (falta .apps.googleusercontent.com)
❌ 123456789012-abc (falta .apps.googleusercontent.com)
❌ https://123456789012-abc...apps.googleusercontent.com (tem protocolo)
❌ 123456789012 abc123xyz (tem espaço no meio)

┌─ SIM, está correto → Pergunta 5
└─ NÃO → [PROBLEMA #2] Valor está digitado errado
         Ação: Copiar EXATAMENTE do Google Cloud Console
```

---

## 🌍 Em Qual Arquivo Você Colocou?

### Pergunta 5: Você colocou em `backend/.env`?

```
Localização correta:
crypto-trade-hub-main/
  └─ backend/
      └─ .env  ← Aqui

Content:
GOOGLE_CLIENT_ID=123456789012-abc...apps.googleusercontent.com

┌─ SIM → Pergunta 6
└─ NÃO → [PROBLEMA #3] Colocar em backend/.env
         Ação: Abrir ou criar backend/.env e adicionar
```

---

### Pergunta 6: Você colocou em `.env` (raiz do projeto) para frontend?

```
Localização para Vite:
crypto-trade-hub-main/
  ├─ .env  ← Aqui (opcional, mas recomendado)
  └─ backend/
      └─ .env

Content:
VITE_GOOGLE_CLIENT_ID=123456789012-abc...apps.googleusercontent.com

┌─ SIM → Pergunta 7
└─ NÃO/NÃO SEI → Tambem adicionar lá (mesmo valor)
               Ação: Ver PASSO 3B do GOOGLE_OAUTH_401_INVALID_CLIENT_FIX.md
```

---

## 🚀 Servidores Reiniciados?

### Pergunta 7: Você reiniciou TANTO o backend QUANTO o frontend?

```
Sequência correta de reinício:

1. Terminal 1 - BACKEND:
   Ctrl + C (se estava rodando)
   cd backend
   python -m uvicorn app.main:app --reload
   Aguarde aparecer: "Uvicorn running on..."

2. Terminal 2 - FRONTEND:
   Ctrl + C (se estava rodando)
   npm run dev
   Aguarde aparecer: "VITE v5.x.x ready in..."

3. Browser:
   F5 (refresh)
   DevTools (F12) → Console → procurar erros

┌─ SIM → Pergunta 8
└─ NÃO → [PROBLEMA #4] Reiniciar agora!
         Ação: Seguir sequência acima
```

---

## 🧪 Teste Rápido

### Pergunta 8: Você fez o teste do DevTools?

```javascript
// Abrir DevTools (F12)
// Console
// Copiar e colar:

console.log("Backend GOOGLE_CLIENT_ID:", "?");  // Não vemos aqui
console.log("Frontend GOOGLE_CLIENT_ID:", import.meta.env.VITE_GOOGLE_CLIENT_ID);

// Esperado no Console:
// Frontend GOOGLE_CLIENT_ID: 123456789012-abc...apps.googleusercontent.com

// Se vir:
// ❌ "undefined" → Frontend .env não está carregado (reiniciar)
// ❌ "" (string vazia) → Arquivo .env existe mas está vazio
// ✅ "123456789..." → OK, continuar

┌─ Viu o valor correto? → Pergunta 9
└─ Viu "undefined" ou vazio → [PROBLEMA #5] Frontend .env não carregado
                              Ação: Verificar PASSO 3 do GOOGLE_OAUTH_401_INVALID_CLIENT_FIX.md
```

---

## 🔐 Origem Autorizada?

### Pergunta 9: Seu localhost está autorizado no Google Cloud?

```
Verificar:
1. Abrir: https://console.cloud.google.com/
2. APIs & Services → Credentials
3. OAuth 2.0 Clients → [Seu Client]
4. Procurar seção "Authorized JavaScript origins"

Verificar se contém:
✅ http://localhost:8081
✅ http://0.0.0.0:8081
✅ http://localhost

Se de vir VAZIO ou sem localhost:
→ [PROBLEMA #6] Adicionar no Google Cloud
  Ação: Ver PASSO 2D do GOOGLE_OAUTH_401_INVALID_CLIENT_FIX.md
```

---

### Pergunta 10: As Redirect URIs estão configuradas?

```
Verificar:
1. Google Cloud Console
2. Seu OAuth Client
3. Procurar seção "Authorized redirect URIs"

Verificar se contém AMBAS:
✅ http://localhost:8081
✅ http://localhost:8081/auth/callback

Ou (se usar 0.0.0.0):
✅ http://0.0.0.0:8081
✅ http://0.0.0.0:8081/auth/callback

Se de vir VAZIO ou sem isso:
→ [PROBLEMA #7] Adicionar redirect URIs
  Ação: Ver PASSO 2D do GOOGLE_OAUTH_401_INVALID_CLIENT_FIX.md
```

---

## 🎯 Teste de Login

### Pergunta 11: Você clicou em "Sign in with Google"?

```
1. Abrir: http://localhost:8081
2. Clicar em botão "Sign in with Google"
3. Observar o que acontece

Se aparecer:
├─ ✅ Google popup/widget → SUCESSO! Vá para VERIFICAÇÃO FINAL
├─ ❌ Erro "invalid_client" → [PROBLEMA #8] Ver abaixo
├─ ❌ Erro diferente → [PROBLEMA ?] Documentar e enviar
└─ ❌ Nada acontece → [PROBLEMA #9] Verificar DevTools Console
```

---

## ✅ VERIFICAÇÃO FINAL

Se chegou aqui sem erro 401:

```
1. Google popup/button funciona? ✅
2. Consegue fazer login? ✅
3. Token foi gerado? ✅

Então está TUDO CORRETO!

Próximos passos:
→ Ler: GOOGLE_OAUTH_CSP_IMPLEMENTATION_GUIDE.md (testes de CSP)
→ Validar: Profile picture carrega após login
→ Confirmar: Zero erros no DevTools Console
```

---

## 🔴 Lista de Problemas (Quick Reference)

| #️⃣ | Problema | Solução | Tempo |
|----|----------|---------|-------|
| **#1** | Client ID vazio/faltando | Criar em Google Cloud | 5 min |
| **#2** | Client ID digitado errado | Copiar exatamente do Google Cloud | 2 min |
| **#3** | Client ID no lugar errado | Colocar em backend/.env | 2 min |
| **#4** | Servidor não reiniciado | Restart backend + frontend | 3 min |
| **#5** | Frontend .env não carregado | Restart Vite (npm run dev) | 2 min |
| **#6** | Localhost não autorizado | Adicionar em Google Cloud | 3 min |
| **#7** | Redirect URIs faltando | Adicionar em Google Cloud | 3 min |
| **#8** | Ainda com erro 401 | Debugar com log completo | 10 min |
| **#9** | Nada acontece | Verificar DevTools Console | 5 min |

---

## 🎯 Próximas Ações

### Se TUDO OK:
```
1. Ler: GOOGLE_OAUTH_CSP_QUICK_START.md
2. Testar: Login funciona?
3. Validar: Foto de perfil carrega?
4. Confirmar: Zero erros no console?
```

### Se AINDA TEM ERRO:
```
1. Copiar exato erro que vê no DevTools Console
2. Enviar seguir informações:
   - Erro exato (print do console)
   - Seu Client ID (primeiros 10 números)
   - Qual localhost você usa (8081 ou outro)
```

---

**Data:** 19 de Fevereiro de 2026  
**Versão:** 1.0 - Árvore de Decisão para Erro 401
