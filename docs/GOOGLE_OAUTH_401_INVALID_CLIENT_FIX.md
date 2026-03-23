# 🔴 ERRO 401: invalid_client - Guia Completo de Resolução

**Data:** 19 de Fevereiro de 2026  
**Erro Reportado:** `Acesso bloqueado: erro de autorização - The OAuth client was not found`  
**Código:** `401: invalid_client`  
**Status:** CRÍTICO - Login Google não funciona

---

## 📸 Erro Observado

```
Acesso bloqueado: erro de autorização

praksapizzariagandu@gmail.com

The OAuth client was not found.

Se você é um desenvolvedor dessa app, consulte os 
detalhes do erro.

Erro 401: invalid_client
```

---

## 🔍 O Que Este Erro Significa

### Causa Raiz
Google não encontrou/reconheceu seu **GOOGLE_CLIENT_ID**

### Possíveis Causas (em ordem de probabilidade)

| # | Causa | Probabilidade |
|---|-------|--------------|
| 1️⃣ | **Client ID não está correto no .env** | 🔴 90% |
| 2️⃣ | **Client ID não foi criado no Google Cloud** | 🔴 5% |
| 3️⃣ | **Redirect URIs não configuradas corretamente** | 🟠 3% |
| 4️⃣ | **Frontend não está passando o Client ID** | 🟠 2% |

---

## ✅ Solução Passo-a-Passo

### PASSO 1: Verificar se GOOGLE_CLIENT_ID Existe

#### A. Verificar arquivo `.env`

```bash
# Terminal - verificar if .env existe e tem valor
cat backend/.env | grep GOOGLE_CLIENT_ID

# Esperado:
# GOOGLE_CLIENT_ID=xyz123abc.apps.googleusercontent.com
```

**Não apareceu nada?** → Vá para PASSO 2 (criar Client ID)

**Apareceu algo vazio?** → Vá para PASSO 2 também

#### B. Verificar formato do Client ID

```bash
# Client ID deve ser assim:
123456789-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com
             ↑                                            ↑
        Começa com números    Termina com .apps.googleusercontent.com
```

**Seu Client ID está diferente?** → Está errado, vá para PASSO 2

---

### PASSO 2: Criar/Recriar OAuth Client ID

#### A. Acessar Google Cloud Console

1. Abrir: https://console.cloud.google.com/
2. Login com sua conta Google
3. Selecionar seu projeto (ou criar novo)

#### B. Habilitar Google+ API

```
Google Cloud Console
  → APIs & Services
  → Library
  → Buscar: "Google+ API"
  → Clicar e depois "Enable"
```

#### C. Criar OAuth 2.0 Credentials

```
Google Cloud Console
  → APIs & Services
  → Credentials
  → Create Credentials
  → OAuth client ID
```

**Se aparecer: "You need to create an OAuth consent screen first"**

```
1. Clique em "Create OAuth consent screen"
2. Escolha: "External" (se for teste/dev)
3. Preencha os dados obrigatórios:
   - App name: "Crypto Trade Hub"
   - User support email: seu.email@gmail.com
   - Developer contact info: seu.email@gmail.com
4. Continue e ignore as opções de scopes
5. Volte para criar Credentials
```

#### D. Configurar OAuth Client

```
1. Escolha tipo: "Web application"
2. Nome: "Crypto Trade Hub - Dev/Prod"
3. Authorized JavaScript origins:
   ├─ http://localhost:8081
   ├─ http://0.0.0.0:8081
   ├─ http://localhost
   ├─ https://seu-dominio.com (depois)
   └─ https://www.seu-dominio.com (depois)

4. Authorized redirect URIs:
   ├─ http://localhost:8081
   ├─ http://localhost:8081/auth/callback
   ├─ http://0.0.0.0:8081
   ├─ http://0.0.0.0:8081/auth/callback
   ├─ https://seu-dominio.com/auth/callback (depois)
   └─ https://www.seu-dominio.com/auth/callback (depois)

5. Clique "Create"
```

#### E. Copiar Client ID

```
Google Cloud Console
  → APIs & Services
  → Credentials
  → OAuth 2.0 Clients (procure "Web application")
  → Clique no seu client
  → Copie o "Client ID" (não o Secret!)
```

**Formato esperado:**
```
123456789012-abcdefghijklmnopqrstuvwxyz1234567.apps.googleusercontent.com
```

---

### PASSO 3: Adicionar Client ID ao Projeto

#### A. Backend - Arquivo `.env`

Localização: `backend/.env`

```bash
# ============================================
# 🔐 Google OAuth Configuration
# ============================================

# Cole aqui o Client ID que copiou
GOOGLE_CLIENT_ID=123456789012-abcdefghijklmnopqrstuvwxyz1234567.apps.googleusercontent.com

# (Optional) Se tiver Secret (raramente usado em frontend OAuth)
GOOGLE_CLIENT_SECRET=sua_secret_aqui_se_tiver

# ============================================
# Ambiente
# ============================================
ENVIRONMENT=development
```

#### B. Frontend - Arquivo `.env` (se usar Vite)

Localização: `.env` (raiz do projeto)

```bash
# ============================================
# 🔐 Google OAuth Configuration
# ============================================

# Mesmo Client ID que colocou no backend
VITE_GOOGLE_CLIENT_ID=123456789012-abcdefghijklmnopqrstuvwxyz1234567.apps.googleusercontent.com
```

---

### PASSO 4: Verificar Configuração no Frontend

#### A. Arquivo: `src/components/GoogleLogin.tsx` (ou similar)

```typescript
// ❌ ERRADO - Client ID hardcoded
<GoogleLogin clientId="123456789012-abc..." />

// ✅ CORRETO - Pega do .env
<GoogleLogin clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID} />
```

#### B. Arquivo: `index.html`

```html
<!-- ✅ Script Google deve estar presente -->
<head>
    <script src="https://accounts.google.com/gsi/client" async defer></script>
</head>
```

#### C. Arquivo: `src/main.tsx` (ou entry point)

```typescript
// ✅ Verificar se Google é inicializado
window.google.accounts.id.initialize({
    client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
    callback: handleCredentialResponse
});
```

---

### PASSO 5: Reiniciar Tudo e Testar

```bash
# Terminal 1: Para o backend (se estava rodando)
# Ctrl + C

# Terminal 1: Limpar variáveis de cache Python
Set-Location backend
Remove-Item -Recurse -Force __pycache__

# Terminal 1: Reiniciar backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Para o frontend (se estava rodando)
# Ctrl + C

# Terminal 2: Limpar cache Vite
Set-Location ..
Get-ChildItem -Path node_modules/.vite -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# Terminal 2: Reiniciar frontend
npm run dev
```

#### Teste no Navegador

1. Abrir: `http://localhost:8081`
2. Abrir DevTools: **F12**
3. Console: Procurar por erros
4. Clicar em "Sign in with Google"
5. **Esperado:** Google popup abre (não erro 401)

---

## 🧪 Verificações Rápidas

### Verificação 1: Client ID no Backend

```bash
# Terminal
cd backend
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GOOGLE_CLIENT_ID'))"

# Esperado: 
# 123456789012-abcdefghijklmnopqrstuvwxyz1234567.apps.googleusercontent.com

# Se vir: None ou vazio → Problema no .env
# Se vir diferente → Client ID incorreto
```

### Verificação 2: Client ID no Frontend

```javascript
// DevTools Console:
console.log("Client ID:", import.meta.env.VITE_GOOGLE_CLIENT_ID)

// Esperado: 123456789012-abc...
// Se vir: undefined → Problema no .env frontend ou Vite não foi reiniciado
```

### Verificação 3: Validar Formato

```javascript
// DevTools Console:
const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const isValid = clientId && 
                clientId.includes('.apps.googleusercontent.com') &&
                clientId.length > 30;
console.log("Client ID válido?", isValid);

// Esperado: true
// Se vir: false → Client ID está errado
```

### Verificação 4: Google Cloud Console

```
1. Abrir: https://console.cloud.google.com/
2. APIs & Services → Credentials
3. OAuth 2.0 Clients → Seu client
4. Verificar:
   ✅ Status está ativo?
   ✅ Authorized JavaScript origins inclui localhost?
   ✅ Authorized redirect URIs inclui seu app?
```

---

## 🚨 Problemas Comuns & Soluções

### Problema 1: "The OAuth client was not found"

**Causa mais comum:** Client ID não existe ou está digitado errado

**Solução:**
```bash
# 1. Vá para Google Cloud Console
# 2. Copie EXATAMENTE o Client ID (incluindo números)
# 3. Cole no .env (sem espaços extras)
# 4. Salve o arquivo
# 5. Reinicie o backend
```

### Problema 2: "invalid_client + Redirect URI mismatch"

Erro completo:
```
The redirect_uri parameter does not match 
one of the Authorized redirect URIs.
```

**Causa:** Seu app está em uma origem diferente da configurada

**Solução:**
```
Google Cloud Console
  → Credentials
  → Seu OAuth Client
  → Authorized redirect URIs
  → Adicione sua URL atual:

Se sua app está em: http://192.168.1.100:8081
Adicione: http://192.168.1.100:8081
          http://192.168.1.100:8081/auth/callback
```

### Problema 3: "invalid_client + formato estranho"

Erro:
```
Acesso bloqueado: erro de autorização
(erro genérico na página)
```

**Causa:** Client ID foi corrompido ou está vazio

**Solução:**
```bash
# 1. Delete arquivo backend/.env
# 2. Crie novo backend/.env novamente
# 3. Cole o Client ID corretamente
# 4. Salve e reinicie
```

### Problema 4: Funciona no Backend mas não no Frontend

**Causa:** Frontend está com outro Client ID diferente

**Solução:**
```bash
# Garantir que AMBOS têm o MESMO Client ID
echo $GOOGLE_CLIENT_ID                    # Backend
echo $VITE_GOOGLE_CLIENT_ID                # Frontend (deve ser igual)
```

---

## 📋 Checklist de Implementação

- [ ] **Google Cloud Setup**
  - [ ] Projeto criado em console.cloud.google.com
  - [ ] Google+ API habilitada
  - [ ] OAuth consent screen criado

- [ ] **OAuth Client Criado**
  - [ ] Tipo: Web application
  - [ ] JavaScript origins: http://localhost:8081
  - [ ] Redirect URIs: http://localhost:8081 (+ callback)
  - [ ] Client ID copiado (formato: ...googleusercontent.com)

- [ ] **Backend Configurado**
  - [ ] `backend/.env` contém GOOGLE_CLIENT_ID
  - [ ] Valor não está vazio
  - [ ] Sem espaços extras antes/depois

- [ ] **Frontend Configurado**
  - [ ] `.env` contém VITE_GOOGLE_CLIENT_ID
  - [ ] `index.html` tem script Google
  - [ ] Componente usa `import.meta.env.VITE_GOOGLE_CLIENT_ID`

- [ ] **Servidores Reiniciados**
  - [ ] Backend: python -m uvicorn ...
  - [ ] Frontend: npm run dev
  - [ ] Browser: F5 para refresh

- [ ] **Testado**
  - [ ] DevTools console sem erros
  - [ ] Google popup abre ao clicar
  - [ ] Login funciona

---

## 🔧 Debug Avançado

### Se ainda não funcionar, execute isto:

```bash
# 1. Verificar se backend está pegando Client ID
cd backend
python << 'EOF'
import os
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

# Imprimir tudo
print("=== BACKEND CONFIG ===")
print(f"GOOGLE_CLIENT_ID: {os.getenv('GOOGLE_CLIENT_ID')}")
print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
print(f"Path: {os.getcwd()}")

# Validar
client_id = os.getenv('GOOGLE_CLIENT_ID')
if client_id:
    print(f"✅ Client ID found ({len(client_id)} chars)")
    if '.apps.googleusercontent.com' in client_id:
        print("✅ Format looks correct")
    else:
        print("❌ Format looks wrong!")
else:
    print("❌ Client ID is empty or not found!")
EOF
```

### 2. Verificar arquivo .env

```bash
# Listar conteúdo de backend/.env
Get-Content backend/.env | Select-String -Pattern "GOOGLE"

# Esperado:
# GOOGLE_CLIENT_ID=123456...
```

### 3. Verificar se .env é reconhecido

```bash
# Verificar se arquivo existe
Test-Path backend/.env

# Esperado: True
```

### 4. Verificar logs do servidor

```bash
# Ao iniciar o backend, deve aparecer:
# [OK] Arquivo .env carregado de: .../.env
# [OK] Google OAuth configured: 123456...

# Se não aparece → .env não foi encontrado
# Se aparecer erro → Client ID está vazio
```

---

## 🌐 Para Produção

Quando for fazer deploy:

### 1. Criar novo OAuth Client em Production

```
Google Cloud Console
  → Credentials
  → Create New (não usa o dev)
  → Type: Web application
  → Name: "Crypto Trade Hub - Production"
  → Authorized JavaScript origins:
     ├─ https://seu-dominio.com
     ├─ https://www.seu-dominio.com
  → Authorized redirect URIs:
     ├─ https://seu-dominio.com/auth/callback
     ├─ https://www.seu-dominio.com/auth/callback
```

### 2. Configurar no Servidor

```bash
# Em seu servidor de produção, adicione ao .env:
GOOGLE_CLIENT_ID=seu_client_id_producao
ENVIRONMENT=production
```

### 3. Testar em Staging Primeiro

```bash
# Antes de fazer deploy final
ENVIRONMENT=production npm run build
npm run preview

# Testar login
```

---

## 📞 Suporte Rápido

| Erro | Solução | Tempo |
|------|---------|-------|
| **"OAuth client not found"** | Verificar Client ID em .env | 2 min |
| **"invalid_client"** | Copiar Client ID correto do Google Cloud | 3 min |
| **"Redirect URI mismatch"** | Adicionar seu localhost no Google Cloud | 2 min |
| **Funciona dev, falha prod** | Criar novo Client ID para produção | 5 min |
| **DevTools com erro estranho** | Limpar browser cache + restart servidor | 5 min |

---

## ✅ Após Resolver

Uma vez que login funcionar:

1. ✅ Salvar credentials em lugar seguro
2. ✅ Documentar Google Cloud setup para servidor
3. ✅ Criar client ID separado para produção
4. ✅ Testar em múltiplos browsers
5. ✅ Testar em mobile também

---

## 📚 Referências

- **Google OAuth Documentation:** https://developers.google.com/identity/gsi/web
- **Google Cloud Console:** https://console.cloud.google.com/
- **Client ID Format:** https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
- **Troubleshooting:** https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid#troubleshoot

---

**Status:** 🔴 Bloqueado por Client ID incorreto  
**Tempo de Resolução:** 5-10 minutos  
**Dificuldade:** ⭐ Fácil

---

**Criado:** 19 de Fevereiro de 2026  
**Versão:** 1.0 - Resolução de Erro 401 invalid_client
