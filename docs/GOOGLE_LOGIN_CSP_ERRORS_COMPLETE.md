# Documento Completo: Erros de Login Google - Content-Security-Policy 3

**Data:** 19 de Fevereiro de 2026  
**Versão:** 1.0  
**Status:** Crítico - Bloqueia autenticação Google OAuth

---

## 📋 Sumário Executivo

Os erros de CSP (Content-Security-Policy) estão impedindo a autenticação via Google OAuth. O sistema está bloqueando:
- Requisições CORS para serviços Google
- Carregamento de scripts Google necessários
- APIs deprecadas causando warnings

**Impacto:** ❌ Login Google **NÃO FUNCIONA**

---

## 🔴 Erros Identificados

### 1. **Aviso Self-XSS no Console**
```
AVISO m=_b,_tp:426:253
O uso deste console pode permitir que invasores falsifiquem sua identidade 
para roubar informações por meio de um ataque chamado Self-XSS.
```

**O que é:** Aviso de segurança genérico do Google Chrome sobre uso do console
**Severidade:** ⚠️ Baixa (apenas informativo)
**Causa:** Não está bloqueando funcionalidade, apenas avisos de segurança

---

### 2. **Requisição CORS Bloqueada - CRÍTICA** ⛔

```
Requisição cross-origin bloqueada: A diretiva Same Origin (mesma origem) 
não permite a leitura do recurso remoto em 
https://play.google.com/log?format=json&hasfast=true&authuser=0

Motivo: falha na requisição CORS
Código de status: (null)
```

**O que é:** O navegador bloqueou uma solicitação CORS para Google Play Services
**Severidade:** 🔴 CRÍTICA
**Causa Raiz:** Content-Security-Policy está bloqueando:
- Domínios externos (*.google.com, *.googleapis.com)
- Requisições CORS não autorizadas
- Scripts e recursos do Google não permitidos

**Impacto Direto:**
- ❌ Google OAuth não consegue se comunicar com servidores Google
- ❌ Autenticação falha silenciosamente
- ❌ Usuário não consegue fazer login

---

### 3. **APIs Deprecadas - MouseEvent**

```
MouseEvent.mozPressure está obsoleto. 
Em vez disso, use PointerEvent.pressure.
```

```
MouseEvent.mozInputSource está obsoleto. 
Em vez disso, use PointerEvent.pointerType.
```

**Severidade:** ⚠️ Média (não bloqueia, mas será removido futuramente)
**Causa:** Scripts Google usando APIs antigas do Firefox
**Impacto:** Avisos no console, sem bloqueio direto

---

## 🔍 Análise Detalhada de CSP

### Como CSP 3 está bloqueando Google OAuth

Seu arquivo HTML ou resposta do servidor provavelmente contém:

```html
<!-- ❌ PROBLEMA: CSP muito restritiva -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self'; 
  script-src 'self'; 
  connect-src 'self';
  style-src 'self' 'unsafe-inline'
">
```

**O que está acontecendo:**

1. **`default-src 'self'`** - Bloqueia TUDO que não for do mesmo domínio
2. **`script-src 'self'`** - Bloqueia scripts do Google
3. **`connect-src 'self'`** - Bloqueia fetch/XMLHttpRequest para Google
4. **Resultado:** Google OAuth não funciona

---

## ✅ Solução Completa

### Opção 1: CSP Permissiva para Google OAuth (RECOMENDADA)

#### A. Frontend - Arquivo HTML principal

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- ✅ CSP 3 Permissiva para Google OAuth -->
    <meta http-equiv="Content-Security-Policy" content="
        default-src 'self';
        
        script-src 'self' 
                   'unsafe-inline'
                   https://accounts.google.com
                   https://apis.google.com
                   https://platform.linkedin.com
                   https://www.googletagmanager.com
                   https://*.gstatic.com
                   https://*.google.com;
        
        connect-src 'self'
                    https://accounts.google.com
                    https://accounts.google.co.jp
                    https://accounts.youtube.com
                    https://*.googleapis.com
                    https://*.google.com
                    https://play.google.com
                    http://localhost:8000
                    http://localhost:8081
                    ws://localhost:8081
                    http://0.0.0.0:8000
                    http://0.0.0.0:8081;
        
        img-src 'self' 
                data:
                https://accounts.google.com
                https://*.gstatic.com
                https://*.googleapis.com;
        
        style-src 'self' 
                  'unsafe-inline'
                  https://accounts.google.com
                  https://*.gstatic.com;
        
        font-src 'self'
                 https://*.gstatic.com
                 https://*.googleapis.com;
        
        frame-src https://accounts.google.com;
        
        object-src 'none';
        base-uri 'self';
        form-action 'self';
    ">
    
    <title>Crypto Trade Hub</title>
</head>
<body>
    <!-- Seu conteúdo aqui -->
</body>
</html>
```

#### B. Backend - Headers HTTP (MELHOR PRÁTICA)

No seu `app/main.py` (FastAPI):

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI()

# ✅ Adicionar CSP através de middleware
class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # CSP 3 para Google OAuth
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' "
                "https://accounts.google.com "
                "https://apis.google.com "
                "https://*.gstatic.com "
                "https://*.google.com; "
            "connect-src 'self' "
                "https://accounts.google.com "
                "https://accounts.google.co.jp "
                "https://accounts.youtube.com "
                "https://*.googleapis.com "
                "https://*.google.com "
                "https://play.google.com "
                "http://localhost:8000 "
                "http://localhost:8081 "
                "ws://localhost:8081 "
                "http://0.0.0.0:8000 "
                "http://0.0.0.0:8081; "
            "img-src 'self' data: "
                "https://accounts.google.com "
                "https://*.gstatic.com "
                "https://*.googleapis.com; "
            "style-src 'self' 'unsafe-inline' "
                "https://accounts.google.com "
                "https://*.gstatic.com; "
            "font-src 'self' "
                "https://*.gstatic.com "
                "https://*.googleapis.com; "
            "frame-src https://accounts.google.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        
        return response

app.add_middleware(CSPMiddleware)

# ✅ CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://0.0.0.0:8081",
        "https://accounts.google.com",
        "https://apis.google.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### C. Vite Config - Para desenvolvimento

No seu `vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8081,
    host: '0.0.0.0',
    
    // ✅ Proxy para backend
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    },
    
    // ✅ Headers para desenvolvimento
    middlewares: [
      {
        configResolved: (config) => { },
        apply: 'pre',
        async handle(req, res, next) {
          // CSP para desenvolvimento
          res.setHeader('Content-Security-Policy', 
            "default-src 'self'; " +
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' " +
              "https://accounts.google.com " +
              "https://*.gstatic.com " +
              "https://*.google.com; " +
            "connect-src 'self' " +
              "https://accounts.google.com " +
              "https://*.googleapis.com " +
              "https://*.google.com " +
              "http://localhost:8000 " +
              "ws://localhost:*; " +
            "img-src 'self' data: https:; " +
            "style-src 'self' 'unsafe-inline' https:; " +
            "font-src 'self' data: https:; " +
            "frame-src https://accounts.google.com; "
          );
          next();
        }
      }
    ]
  }
})
```

### Opção 2: CSP com Hash/Nonce (MAS SEGURO)

Se quiser CSP mais seguro com hashes:

```html
<meta http-equiv="Content-Security-Policy" content="
    default-src 'self';
    script-src 'self' 
               'nonce-{RANDOM_NONCE_HERE}'
               https://accounts.google.com;
    connect-src 'self'
               https://accounts.google.com
               https://*.googleapis.com;
    img-src 'self' data: https://accounts.google.com;
    style-src 'self' 'unsafe-inline' https://accounts.google.com;
    frame-src https://accounts.google.com;
">
```

**Aplicar nonce no backend:**

```python
import secrets
from base64 import b64encode

@app.get("/")
async def get_index():
    nonce = b64encode(secrets.token_bytes(16)).decode()
    # Renderizar HTML com nonce
    return f'''
    <meta http-equiv="Content-Security-Policy" 
          content="script-src 'nonce-{nonce}' ...">
    <script nonce="{nonce}">
        // Seu script seguro aqui
    </script>
    '''
```

---

## 🔧 Checklist de Implementação

### 1. Google OAuth Setup

- [ ] Verificar ID do cliente Google em `config.env`
- [ ] Confirmar origem autorizada em Google Cloud Console:
  ```
  http://localhost:8081
  https://seudominio.com
  ```
- [ ] Script Google presente no HTML:
  ```html
  <script src="https://accounts.google.com/gsi/client" async defer></script>
  ```

### 2. Frontend - Adicionar CSP

Arquivo: `index.html`
```html
<!-- ✅ Adicionar meta tag CSP -->
<meta http-equiv="Content-Security-Policy" content="...">
```

### 3. Backend - Adicionar Headers

Arquivo: `app/main.py`
```python
# ✅ Adicionar CSPMiddleware
app.add_middleware(CSPMiddleware)
app.add_middleware(CORSMiddleware, ...)
```

### 4. Testar Login

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Frontend
npm run dev
```

Abrir navegador: `http://localhost:8081`

---

## 🧪 Testes e Verificações

### Verificar CSP no DevTools

1. **Abrir DevTools** (F12)
2. **Console** - Verificar se há erros CSP
3. **Network** - Verificar requisições Google
4. **Application > Manifest** - Ver headers

```javascript
// Script para testar no console
fetch('https://accounts.google.com/gsi/client')
  .then(r => console.log('✅ Google Script OK'))
  .catch(e => console.log('❌ Erro:', e.message))
```

### Verificar CORS

```bash
curl -H "Origin: http://localhost:8081" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: X-Custom-Header" \
     -X OPTIONS \
     http://localhost:8000/auth/google \
     -v
```

### Testar com CSP Report Only (antes de aplicar)

```html
<!-- Testar sem bloquear -->
<meta http-equiv="Content-Security-Policy-Report-Only" 
      content="...">
```

---

## 🚨 Problemas Comuns e Soluções

### Problema 1: "Requisição cross-origin bloqueada"

**Causa:** CSP não permite domínio Google

**Solução:**
```html
<!-- ✅ Adicionar no connect-src -->
connect-src 'self' https://accounts.google.com https://*.googleapis.com;
```

### Problema 2: Script Google não carrega

**Causa:** `script-src` não permite accounts.google.com

**Solução:**
```html
<!-- ✅ Adicionar no script-src -->
script-src 'self' https://accounts.google.com https://apis.google.com;
```

### Problema 3: Autenticação falha silenciosamente

**Causa:** CSP permite script mas bloqueia comunicação de volta

**Solução:** Garantir que `connect-src` inclua todos endpoints Google:
```
https://accounts.google.com
https://accounts.google.co.jp
https://*.googleapis.com
https://play.google.com
https://www.google.com
```

### Problema 4: MouseEvent warnings

**Causa:** Scripts Google usando APIs Firefox antigas

**Solução:** Avisos do Firefox, não bloqueia. Ignorar ou atualizar Firefox.

---

## 📊 CSP 3 Diretivas Explicadas

| Diretiva | Função | Para Google OAuth |
|----------|--------|------------------|
| **script-src** | Controla scripts | Deve incluir google.com |
| **connect-src** | Controla fetch/XHR | CRÍTICA: deve incluir google.com |
| **img-src** | Imagens | Precisa para avatares |
| **style-src** | CSS/estilos | Para widgets Google |
| **font-src** | Fontes | Para UI Google |
| **frame-src** | iframes | Para login popup |
| **default-src** | Fallback padrão | Base para tudo |

---

## 🔐 Segurança vs Funcionalidade

### Nível 1: Máxima Segurança (RECOMENDADO para PRODUÇÃO)
```csp
script-src 'nonce-{random}' https://accounts.google.com;
connect-src 'self' https://accounts.google.com;
```
- ✅ Mais seguro
- ❌ Mais complexo para manter
- ⚠️ Precisa nonce em cada página

### Nível 2: Segurança Moderada (DESENVOLVIMENTO)
```csp
script-src 'self' 'unsafe-inline' https://accounts.google.com;
connect-src 'self' https://accounts.google.com https://*.googleapis.com;
```
- 😐 Balanço
- ✅ Funciona bem
- ⚠️ Evita `'unsafe-eval'`

### Nível 3: Permissivo (NÃO USE EM PRODUÇÃO!)
```csp
script-src *;
connect-src *;
```
- ❌ Inseguro
- ✅ Tudo funciona
- 🚫 Vulnerável a XSS

---

## 📝 Configuração Completa Recomendada

### Arquivo: `backend/app/middleware/csp.py`

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class GoogleOAuthCSPMiddleware(BaseHTTPMiddleware):
    """Middleware CSP 3 otimizado para Google OAuth"""
    
    PRODUCTION_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'nonce-{nonce}' "
            "https://accounts.google.com "
            "https://apis.google.com "
            "https://*.gstatic.com; "
        "connect-src 'self' "
            "https://accounts.google.com "
            "https://accounts.google.co.jp "
            "https://accounts.youtube.com "
            "https://*.googleapis.com "
            "https://play.google.com; "
        "img-src 'self' data: "
            "https://accounts.google.com "
            "https://*.gstatic.com "
            "https://*.googleusercontent.com; "
        "style-src 'self' 'unsafe-inline' "
            "https://accounts.google.com "
            "https://*.gstatic.com; "
        "font-src 'self' "
            "https://*.gstatic.com "
            "https://fonts.googleapis.com; "
        "frame-src https://accounts.google.com; "
        "frame-ancestors 'none'; "
        "upgrade-insecure-requests; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    
    DEVELOPMENT_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://accounts.google.com "
            "https://apis.google.com "
            "https://*.gstatic.com; "
        "connect-src 'self' "
            "https://accounts.google.com "
            "https://*.googleapis.com "
            "https://*.google.com "
            "http://localhost:8000 "
            "http://localhost:8081 "
            "ws://localhost:* "
            "http://0.0.0.0:8000 "
            "http://0.0.0.0:8081; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "font-src 'self' data: https:; "
        "frame-src https://accounts.google.com; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Selecionar CSP baseado em ambiente
        import os
        is_production = os.getenv("ENVIRONMENT") == "production"
        csp = self.PRODUCTION_CSP if is_production else self.DEVELOPMENT_CSP
        
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response
```

### Usar no main.py:

```python
from app.middleware.csp import GoogleOAuthCSPMiddleware

app.add_middleware(GoogleOAuthCSPMiddleware)
```

---

## 📚 Referências

- [MDN: Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy)
- [CSP 3 Specification](https://www.w3.org/TR/CSP3/)
- [Google OAuth Setup](https://developers.google.com/identity/gsi/web)
- [OWASP CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)

---

## ✔️ Próximos Passos

1. ✅ Implementar CSP no backend com middleware
2. ✅ Configurar CORS corretamente
3. ✅ Testar login Google no localhost
4. ✅ Verificar console do DevTools
5. ✅ Fazer deploy com CSP ajustado
6. ✅ Monitorar CSP violations em produção

---

**Status Atual:** 🔴 Bloqueado - Aguardando implementação de CSP
**Prioridade:** 🔴 CRÍTICA
**Tempo Estimado:** 30-45 minutos
**Dificuldade:** ⭐⭐ Médio
