# Configuração Google OAuth - Crypto Trade Hub

## 📋 Passo A: Criar Credenciais no Google Cloud

### 1.1 Acessar Google Cloud Console
1. Abrir https://console.cloud.google.com/
2. Fazer login com conta Google da sua empresa
3. Criar novo projeto ou selecionar existente

### 1.2 Habilitar Google+ API
1. No menu lateral, clicar em "APIs & Services" → "Library"
2. Buscar por "Google+ API"
3. Clicar em "Enable"

### 1.3 Criar OAuth 2.0 Client ID
1. Ir para "APIs & Services" → "Credentials"
2. Clicar em "Create Credentials" → "OAuth 2.0 Client ID"
3. Selecionar "Web application"
4. Preencher:
   - **Name:** "Crypto Trade Hub Frontend"
   - **Authorized JavaScript origins:**
     - `http://localhost:8080`
     - `http://localhost:5173`
     - `http://127.0.0.1:8080`
   - **Authorized redirect URIs:**
     - `http://localhost:8080/login`
     - `http://localhost:8080/callback`
5. Copiar o **Client ID** (formato: `xxxxx.apps.googleusercontent.com`)

---

## 📋 Passo B: Configurar Variáveis de Ambiente

### 2.1 Backend - `.env`
```env
# Google OAuth
GOOGLE_CLIENT_ID=seu_client_id_aqui.apps.googleusercontent.com
```

⚠️ **IMPORTANTE:** 
- Substituir `seu_client_id_aqui` pelo Client ID copiado
- Não commitar este arquivo com credenciais reais no Git
- Em produção, usar secrets seguros (AWS Secrets Manager, etc.)

### 2.2 Frontend - Adicionar ao `.env.local`
Se usando Google Sign-In Button no frontend:
```env
VITE_GOOGLE_CLIENT_ID=seu_client_id_aqui.apps.googleusercontent.com
```

---

## 📋 Passo C: Integração Frontend (Optional)

Se desejar usar Google Sign-In Button oficial do Google:

### 3.1 Instalar Google Auth Library
```bash
npm install @react-oauth/google
```

### 3.2 Exemplo de Componente Login
```typescript
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { authService } from '@/lib/api';

export function LoginPage() {
  const navigate = useNavigate();

  const handleGoogleSuccess = async (credentialResponse: any) => {
    try {
      // Enviar token para backend
      const response = await authService.loginWithGoogle({
        id_token: credentialResponse.credential
      });

      if (response.success) {
        // Salvar tokens
        localStorage.setItem('access_token', response.access_token);
        localStorage.setItem('refresh_token', response.refresh_token);
        
        // Redirecionar para dashboard
        navigate('/dashboard');
      }
    } catch (error) {
      console.error('Erro ao autenticar:', error);
    }
  };

  return (
    <GoogleLogin
      onSuccess={handleGoogleSuccess}
      onError={() => console.log('Login Falhou')}
    />
  );
}
```

### 3.3 Wrapper da Aplicação
```typescript
import { GoogleOAuthProvider } from '@react-oauth/google';

export function App() {
  return (
    <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
      <YourRoutes />
    </GoogleOAuthProvider>
  );
}
```

---

## 🔒 Segurança - O que Acontece no Backend

### 4.1 Fluxo de Validação (backend/app/auth/router.py)

```
Frontend envia:
  POST /api/auth/google
  { "id_token": "eyJhbGc..." }
        ↓
Backend valida:
  1. ✅ Assina JWT com chaves públicas do Google
  2. ✅ Verifica issuer (accounts.google.com)
  3. ✅ Verifica aud (GOOGLE_CLIENT_ID)
  4. ✅ Verifica expiração
        ↓
Extrai dados validados:
  - email
  - name
  - picture
  - sub (Google ID único)
        ↓
No MongoDB:
  - Procura usuário por google_id
  - Se não existe: cria novo usuário
  - Se existe: atualiza last_login
        ↓
Retorna JWT da aplicação:
  - access_token (15min)
  - refresh_token (30 dias)
```

### 4.2 Por que é Seguro?

✅ **Token validado com chaves públicas do Google** - impossível falsificar
✅ **Issuer verificado** - token deve vir do Google, não de terceiro
✅ **GOOGLE_CLIENT_ID validado** - token é para esta aplicação, não outra
✅ **Expiração verificada** - tokens antigos rejeitados
✅ **Logging detalhado** - todos os logins registrados no backend

---

## 🧪 Testando

### 5.1 Via cURL (Simular Teste)
```bash
curl -X POST http://localhost:8000/api/auth/google \
  -H "Content-Type: application/json" \
  -d '{
    "id_token": "seu_token_aqui_do_google",
    "email": "user@example.com",
    "name": "João Silva"
  }'
```

Resposta esperada (200 OK):
```json
{
  "success": true,
  "message": "Autenticação Google realizada com sucesso!",
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "name": "João Silva",
    "avatar": "https://..."
  }
}
```

Erros esperados:
- **400**: Token não contém email/ID
- **401**: Token inválido/expirado/forjado
- **500**: Google OAuth não configurado (GOOGLE_CLIENT_ID faltando)

### 5.2 Via MongoDB
Verificar se usuário foi criado:
```javascript
db.users.findOne({ email: "user@example.com" })
```

Resposta esperada:
```javascript
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "name": "João Silva",
  "avatar": "https://lh3.googleusercontent.com/...",
  "auth_provider": "google",
  "google_id": "123456789...",
  "is_active": true,
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "updated_at": ISODate("2024-01-15T10:30:00.000Z"),
  "last_login": ISODate("2024-01-15T10:30:00.000Z")
}
```

---

## 🚀 Implantação em Produção

### 6.1 Endpoints Authorized
No Google Cloud Console, adicionar:

**Authorized JavaScript origins:**
- `https://seu-dominio.com`
- `https://www.seu-dominio.com`

**Authorized redirect URIs:**
- `https://seu-dominio.com/login`
- `https://seu-dominio.com/callback`

### 6.2 Variáveis de Ambiente
```bash
# Backend (.env em produção)
GOOGLE_CLIENT_ID=seu_client_id_producao.apps.googleusercontent.com

# Frontend (.env.production)
VITE_GOOGLE_CLIENT_ID=seu_client_id_producao.apps.googleusercontent.com
```

### 6.3 Logs de Auditoria
O backend registra todos os logins:
```python
logger.info(f"Autenticação Google bem-sucedida: {email} (ID: {user_id})")
logger.warning(f"Token Google inválido: {erro}")
logger.error(f"Erro na autenticação Google: {erro}", exc_info=True)
```

---

## ⚠️ Troubleshooting

### Erro: "GOOGLE_CLIENT_ID não configurado"
- ✅ Verificar se `.env` tem `GOOGLE_CLIENT_ID=...`
- ✅ Reiniciar servidor backend: `python run_server.py`

### Erro: "Token Google inválido ou expirado"
- ✅ Token pode ter expirado (tomar novo do Google Sign-In)
- ✅ Verificar se Client ID no `.env` está correto
- ✅ Verificar relógio do servidor (clock skew tolerado: 10 segundos)

### Erro: "Token não foi emitido pelo Google"
- ⚠️ Possível ataque: token forjado detectado
- ✅ Checar logs do backend para detalhes
- ✅ Verificar frontend não está modificando o token

### Usuário aparece em MongoDB mas login falha
- ✅ Verificar se `google_id` está salvo correto
- ✅ Deletar e criar novo usuário
- ✅ Checar logs: `tail -f backend/app.log`

---

## 📚 Recursos

- Google OAuth 2.0: https://developers.google.com/identity/protocols/oauth2
- google-auth Python: https://github.com/googleapis/google-auth-library-python
- @react-oauth/google: https://github.com/react-oauth/react-oauth.google

---

## ✅ Checklist

- [ ] Google Cloud Project criado
- [ ] Google+ API habilitada
- [ ] OAuth 2.0 Client ID criado
- [ ] Client ID copiado para `.env`
- [ ] Backend reiniciado
- [ ] Testar login com cURL ou Google Sign-In Button
- [ ] Verificar usuário criado em MongoDB
- [ ] Testar login múltiplas vezes (deve atualizar last_login)
- [ ] Em produção: adicionar domínios ao Google Cloud Console
