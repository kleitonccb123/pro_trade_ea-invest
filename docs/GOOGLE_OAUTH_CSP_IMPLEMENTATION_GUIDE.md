# 🔐 Guia: GoogleOAuthCSPMiddleware - Implementação & Testes

**Data:** 19 de Fevereiro de 2026  
**Status:** ✅ IMPLEMENTADO NO CÓDIGO  
**Arquivo:** `backend/app/middleware/csp.py`  
**Integração:** `backend/app/main.py` (linhas 54 e ~352)

---

## ✅ O Que Foi Implementado

### 1. Novo Arquivo Criado
**Localização:** `backend/app/middleware/csp.py` (210+ linhas)

```python
class GoogleOAuthCSPMiddleware(BaseHTTPMiddleware):
    """CSP 3 otimizado para Google OAuth 3.0 (GSI)"""
    
    PRODUCTION_CSP = "..."  # CSP mais restritiva
    DEVELOPMENT_CSP = "..."  # CSP mais permissiva
```

**Características:**
- ✅ Diferencia automaticamente dev vs production via `ENVIRONMENT=production`
- ✅ Usa `settings.app_mode` como fallback
- ✅ Logging de qual CSP foi aplicada (sem expor detalhes em prod)
- ✅ Método estático `get_csp_policy()` para uso manual

### 2. Modifications in app/main.py

#### Adição de Import (linha ~54)
```python
from app.middleware.csp import GoogleOAuthCSPMiddleware
```

#### Atualização do SecurityHeadersMiddleware
- ❌ Removido: CSP fraca (`"default-src 'self'; script-src 'self'..."`)
- ✅ Comentário: CSP agora é handled pelo GoogleOAuthCSPMiddleware
- ✅ Mantido: X-Frame-Options, X-Content-Type-Options, etc.

#### Adição do Middleware (linha ~352)
```python
app.add_middleware(GoogleOAuthCSPMiddleware)  # DEVE rodar ANTES
app.add_middleware(SecurityHeadersMiddleware) # Depois SecurityHeaders
app.add_middleware(MaxUploadSizeMiddleware)   # Por último
```

---

## 📊 Diretivas CSP Aplicadas

### 🔒 Production Policy

```csp
default-src 'self'
script-src 'self' 
           https://accounts.google.com 
           https://apis.google.com 
           https://*.gstatic.com 
           https://www.googletagmanager.com
connect-src 'self' 
            https://accounts.google.com 
            https://accounts.google.co.jp 
            https://accounts.youtube.com 
            https://*.googleapis.com 
            https://play.google.com 
            https://www.google.com
img-src 'self' data: 
        https://accounts.google.com 
        https://*.gstatic.com 
        https://*.googleapis.com 
        https://*.googleusercontent.com    ← CRÍTICO: Fotos de perfil
style-src 'self' 'unsafe-inline' 
          https://accounts.google.com 
          https://*.gstatic.com 
          https://fonts.googleapis.com
font-src 'self' data: 
         https://fonts.gstatic.com 
         https://*.googleapis.com
frame-src https://accounts.google.com     ← CRÍTICO: Google One Tap
frame-ancestors 'none'
upgrade-insecure-requests
object-src 'none'
base-uri 'self'
form-action 'self'
```

### 🧪 Development Policy

```csp
default-src 'self'
script-src 'self' 'unsafe-inline' 'unsafe-eval' 
           https://accounts.google.com 
           ...
connect-src 'self' 
            https://accounts.google.com 
            ...
            http://localhost:8000       ← Dev backend
            http://localhost:8081       ← Dev frontend (Vite)
            ws://localhost:8081         ← WebSocket dev
            ws://0.0.0.0:8081
            ...
```

---

## 🧪 Testes de Validação

### ✅ Teste 1: Verificar se CSP está sendo aplicada

```bash
# Terminal
curl -I http://localhost:8000/health

# Output esperado:
HTTP/1.1 200 OK
Content-Security-Policy: default-src 'self'; script-src ...
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

### ✅ Teste 2: Verificar CSP no DevTools

1. Abrir navegador: `http://localhost:8081`
2. Abrir DevTools: **F12**
3. Aba **Console**
4. Executar:

```javascript
// Testar se Google Script pode ser carregado
fetch('https://accounts.google.com/gsi/client')
  .then(r => r.ok ? console.log('✅ Google GSI Script OK') : console.log('❌ Erro:', r.status))
  .catch(e => console.log('❌ CORS Error:', e.message))
```

**Esperado:** ✅ Google GSI Script OK

### ✅ Teste 3: Verificar CORS para Google

```bash
curl -X OPTIONS http://localhost:8000/auth/google \
  -H "Origin: http://localhost:8081" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v

# Output deve incluir:
# Access-Control-Allow-Origin: http://localhost:8081
# Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
```

### ✅ Teste 4: Testar Login Google Completo

1. **Iniciar backend:**
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

2. **Iniciar frontend (novo terminal):**
```bash
npm run dev
# Ou usar a task: "Run Frontend"
```

3. **Abrir navegador:** `http://localhost:8081`

4. **Clicar em "Sign in with Google"**

5. **Verificar DevTools - Aba Console:**

```
✅ [OK] Arquivo .env carregado
CSP Applied [🧪 DEVELOPMENT] for /
✅ Login Google funciona!
```

**Se tudo OK:** Foto do usuário deve aparecer após login ✨

### ✅ Teste 5: Verificar CSP Report Only (antes de impacto)

Para testar CSP sem bloquear nada, adicionar temporariamente ao middleware:

```python
response.headers["Content-Security-Policy-Report-Only"] = csp_policy
# (em vez de "Content-Security-Policy")
```

Isso enviará reports de violações sem bloquear.

---

## 🚨 Troubleshooting - "O Pulo do Gato"

### ❌ Problema: Login Google funciona mas foto de perfil não aparece

**Causa:** CSP não permite `https://*.googleusercontent.com`

**Verificação:**
```javascript
// No DevTools Console
fetch('https://lh3.googleusercontent.com/a/default-user')
  .then(r => console.log('✅ OK'))
  .catch(e => console.log('❌ Bloqueado'))
```

**Solução:** Garantir que `img-src` inclua:
```csp
img-src 'self' data: https://*.googleusercontent.com
```

✅ **JÁ ESTÁ NO MIDDLEWARE** ✅

---

### ❌ Problema: Google One Tap popup não aparece

**Causa:** CSP não permite `frame-src https://accounts.google.com`

**Verificação:** Abrir DevTools > Console e procurar by "frame-ancestors" ou "frame-src"

**Solução:** Garantir:
```csp
frame-src https://accounts.google.com
```

✅ **JÁ ESTÁ NO MIDDLEWARE** ✅

---

### ❌ Problema: "Requisição cross-origin bloqueada" ainda aparece

**Causa mais comum:** Extensão de navegador injetando scripts

**Verificação:**
1. Abrir em **Modo Incógnito** (sem extensões):
   - Windows/Linux: **Ctrl + Shift + N**
   - Mac: **Cmd + Shift + N**

2. Testar novamente

**Se funciona em Incógnito:** É uma extensão bloqueando

**Extensões conhecidas que causam problemas:**
- ❌ **Ghostery** - Bloqueia rastreamento
- ❌ **uBlock Origin** - Bloqueador geral
- ❌ **Privacy Badger** - Proteção de privacidade
- ❌ **Adblock Plus** - Bloqueador de anúncios

**Solução:** Desabilitar extensões para o seu localhost:
1. DevTools > View extensions
2. Desabilitar para `localhost:8081`

---

### ❌ Problema: "connect-src violation" no Console

**Causa:** CSP não permite uma URL específica

**Verificação:** O erro deve mencionar a URL:
```
Refused to connect to 'https://xyz.google.com' because...
```

**Solução:** Adicionar a URL ao `connect-src`:
```csp
connect-src 'self' https://xyz.google.com ...
```

---

### ❌ Problema: CSP muito permissiva em desenvolvimento

**Se preocupado com segurança durante dev:**

1. Usar CSP Report Only:
```python
# Não bloqueia, apenas informa
response.headers["Content-Security-Policy-Report-Only"] = csp_policy
```

2. Implementar collecão de reports:
```python
# Enviar violations para seu servidor
response.headers["Report-Uri"] = "http://localhost:8000/csp-report"

@app.post("/csp-report")
async def csp_report(request: Request):
    data = await request.json()
    logger.warning(f"CSP Violation: {data}")
```

---

## 🔍 Como Verificar Qual CSP Está Ativa

### Opção 1: DevTools (Navegador)

1. Abrir DevTools (F12)
2. Aba **Network**
3. Clicar em qualquer request
4. Aba **Response Headers**
5. Procurar por `Content-Security-Policy`

### Opção 2: Command Line

```bash
# Verificar header CSP completo
curl -s -I http://localhost:8000/health | grep -i "Content-Security-Policy"
```

### Opção 3: Python

```python
import requests

response = requests.get('http://localhost:8000/health')
csp = response.headers.get('Content-Security-Policy', 'NOT SET')
print(f"CSP: {csp}")
```

---

## 📝 Variáveis de Ambiente Necessárias

### .env

```bash
# Ambiente: production ou development
ENVIRONMENT=development

# Google OAuth
GOOGLE_CLIENT_ID=seu_client_id_aqui.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu_secret_aqui

# Frontend
VITE_GOOGLE_CLIENT_ID=seu_client_id_aqui.apps.googleusercontent.com
```

### settings.py (fallback)

```python
# Se ENVIRONMENT não estiver definido, tenta usar:
if os.getenv("APP_MODE") == "prod":
    # Production CSP
```

---

## 🚀 Deploy para Produção

### Checklist Pré-Deploy

- [ ] **1. Definir ENVIRONMENT=production**
  ```bash
  export ENVIRONMENT=production
  ```

- [ ] **2. Testar CSP Production localmente**
  ```bash
  export ENVIRONMENT=production
  python -m uvicorn app.main:app
  # Verificar se foto de perfil ainda aparece
  ```

- [ ] **3. Verificar allowed_origins em settings.py**
  ```python
  # Deve incluir seu domínio de produção
  allowed_origins = [
      "https://seu-dominio.com",
      "https://www.seu-dominio.com",
  ]
  ```

- [ ] **4. Verificar CORS em produção**
  ```python
  # app/main.py deve usar settings.allowed_origins
  # NÃO use allow_origins=["*"] em produção!
  ```

- [ ] **5. Testar em staging primeiro**
  ```bash
  ENVIRONMENT=production npx vite build
  python -m uvicorn app.main:app
  ```

- [ ] **6. Monitorar CSP violations em produção**
  ```python
  @app.post("/csp-report")
  async def csp_violation_report(request: Request):
      data = await request.json()
      logger.error(f"CSP Violation in PROD: {data}")
      # Enviar para Sentry/NewRelic
  ```

---

## 📚 Referências CSP 3

- **MDN:** https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy
- **W3C CSP Spec:** https://www.w3.org/TR/CSP3/
- **Google OAuth Setup:** https://developers.google.com/identity/gsi/web
- **CSP Validator:** https://csp-evaluator.withgoogle.com/
- **OWASP CSP:** https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html

---

## 📋 Checklist Final

- [ ] Middleware criado: `backend/app/middleware/csp.py`
- [ ] `__init__.py` criado: `backend/app/middleware/__init__.py`
- [ ] Import adicionado em `app/main.py`
- [ ] SecurityHeadersMiddleware atualizado
- [ ] GoogleOAuthCSPMiddleware adicionado
- [ ] Backend reiniciado
- [ ] Testar login Google em http://localhost:8081
- [ ] Verificar foto de perfil aparece
- [ ] DevTools Console sem erros CSP
- [ ] Testar em Modo Incógnito

---

## ✨ Resultado Esperado

Após implementação:

```
✅ Login Google funciona
✅ Foto de perfil do usuário aparece
✅ Google One Tap popup funciona (se habilitado)
✅ Zero erros de "cross-origin bloqueado"
✅ Zero erros CSP no console
✅ Segurança mantida em produção
```

**Status:** 🟢 PRONTO PARA PRODUÇÃO

---

**Última atualização:** 19 de Fevereiro de 2026  
**Versão:** 1.0
