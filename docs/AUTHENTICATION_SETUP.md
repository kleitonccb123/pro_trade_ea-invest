# Sistema de Autenticação - Crypto Trade Hub

## Visão Geral

Sistema completo de autenticação com suporte para:
- ✅ Email + Senha (Registro e Login)
- ✅ Google OAuth
- ✅ Tokens JWT (Access + Refresh)
- ✅ Persistência em localStorage
- ✅ Proteção de rotas

## Arquitetura

### Backend (FastAPI)

**Endpoints de Autenticação:**

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/auth/register` | Registra novo usuário |
| POST | `/api/auth/login` | Login com email/senha |
| POST | `/api/auth/google` | Google OAuth |
| POST | `/api/auth/refresh` | Renova access token |
| GET | `/api/auth/me` | Retorna usuário autenticado |
| POST | `/api/auth/logout` | Logout |

**Requisições e Respostas:**

```bash
# Registrar usuário
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "senha123"
}

Response:
{
  "success": true,
  "message": "Usuário registrado com sucesso!",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

```bash
# Login com email/senha
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "senha123"
}
```

```bash
# Google OAuth
POST /api/auth/google
Content-Type: application/json

{
  "id_token": "eyJ...", // JWT do Google
  "email": "user@gmail.com",
  "name": "John Doe"
}
```

```bash
# Renovar token
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}

Response:
{
  "success": true,
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

```bash
# Obter usuário autenticado
GET /api/auth/me
Authorization: Bearer eyJ...

Response:
{
  "success": true,
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

### Frontend (React + TypeScript)

**Estrutura de Arquivos:**

```
src/
├── context/
│   └── AuthContext.tsx         # Zustand store de autenticação
├── components/
│   └── ProtectedRoute.tsx       # Wrapper para rotas protegidas
└── pages/
    ├── Login.tsx               # Tela de login
    └── Signup.tsx              # Tela de signup
```

**AuthContext - Zustand Store:**

```typescript
// Importar o hook
import { useAuthStore } from '@/context/AuthContext';

// Usar em componentes
export function MyComponent() {
  const { user, isAuthenticated, login, logout } = useAuthStore();

  return (
    <div>
      {isAuthenticated ? (
        <>
          <p>Bem-vindo, {user?.name}!</p>
          <button onClick={() => logout()}>Logout</button>
        </>
      ) : (
        <p>Faça login para continuar</p>
      )}
    </div>
  );
}
```

**Métodos do Store:**

- `login(email, password)` - Login com email/senha
- `signup(email, password)` - Registrar novo usuário
- `googleLogin(idToken, email, name)` - Google OAuth
- `logout()` - Fazer logout
- `checkAuth()` - Verificar se token é válido
- `setUser(user)` - Atualizar usuário
- `setTokens(access, refresh)` - Atualizar tokens

**ProtectedRoute - Wrapper para rotas autenticadas:**

```typescript
import ProtectedRoute from '@/components/ProtectedRoute';

<Route
  element={
    <ProtectedRoute>
      <AppLayout />
    </ProtectedRoute>
  }
>
  <Route path="/dashboard" element={<Dashboard />} />
</Route>
```

**Login Component:**

- Form com email e senha
- Integração com Google OAuth (@react-oauth/google)
- Decodificação de JWT do Google
- Tratamento de erros
- Loading states
- Link para signup

**Signup Component:**

- Form com nome, email, senha, confirmação
- Validação de formulário
- Criação de conta
- Tratamento de erros
- Link para login

## Configuração

### Backend

1. **Variáveis de Ambiente:**

```env
MONGODB_URL=mongodb+srv://...
JWT_SECRET=sua-chave-secreta-aqui
JWT_EXPIRY_MINUTES=15
JWT_REFRESH_EXPIRY_DAYS=7
```

2. **Dependências instaladas:**
- FastAPI
- PyJWT
- bcrypt
- Motor (async MongoDB)
- pydantic

3. **Iniciar:**

```bash
cd backend
python run_server.py
```

Backend rodará em `http://localhost:8000`

### Frontend

1. **Variáveis de Ambiente:**

```env
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=sua-client-id-google
```

2. **Dependências instaladas:**
- @react-oauth/google
- zustand
- react-router-dom
- lucide-react

3. **Configuração do Google OAuth:**

No `src/main.tsx`:
```typescript
<GoogleOAuthProvider clientId="YOUR_GOOGLE_CLIENT_ID">
  <App />
</GoogleOAuthProvider>
```

4. **Iniciar:**

```bash
npm run dev
```

Frontend rodará em `http://localhost:8080` (ou porta disponível)

## Fluxo de Autenticação

### Registro
1. Usuário acessa `/signup`
2. Preenche: nome, email, senha, confirmação
3. Frontend valida formulário
4. Envia para `POST /api/auth/register`
5. Backend:
   - Valida email único
   - Hash senha com bcrypt
   - Cria documento em MongoDB
   - Retorna tokens JWT
6. Frontend:
   - Armazena tokens em localStorage
   - Atualiza Zustand store
   - Redireciona para dashboard

### Login
1. Usuário acessa `/login`
2. Preenche: email e senha
3. Frontend envia para `POST /api/auth/login`
4. Backend:
   - Valida credenciais
   - Compara senha com bcrypt
   - Gera tokens JWT
   - Retorna tokens e dados do usuário
5. Frontend:
   - Armazena tokens
   - Atualiza store
   - Redireciona para dashboard

### Google OAuth
1. Usuário clica em "Entrar com Google"
2. Google abre dialog de login
3. Usuário autoriza
4. Recebe `credential` JWT
5. Frontend decodifica JWT (sem validar assinatura)
6. Extrai: `id_token`, `email`, `name`
7. Envia para `POST /api/auth/google`
8. Backend:
   - Valida email
   - Se existe: atualiza `google_id`
   - Se não: cria novo usuário
   - Retorna tokens
9. Frontend: mesmo que login normal

### Rotas Protegidas
1. ProtectedRoute verifica `isAuthenticated`
2. Se falso: redireciona para `/login`
3. Se verdadeiro: renderiza componente
4. No load: `checkAuth()` valida token com `/api/auth/me`

### Renovação de Token
- Access token expira em 15 minutos
- Frontend pode renovar com `refresh_token`
- Call: `POST /api/auth/refresh`
- Retorna novo `access_token`
- Recomendação: implementar interceptor para auto-refresh

## Segurança

### Backend
- ✅ Senhas com bcrypt (hash + salt)
- ✅ JWT tokens com assinatura
- ✅ Access token curto (15 min)
- ✅ Refresh token seguro (7 dias)
- ✅ MongoDB com validação
- ✅ Validação de email com Pydantic

### Frontend
- ✅ Tokens em localStorage (vulnerável a XSS)
- ⚠️ Recomendação: considerar httpOnly cookies
- ✅ Tokens inclusos em Authorization header
- ✅ ProtectedRoute previne acesso não autenticado
- ✅ Google OAuth usa credential JWT

## Melhorias Futuras

1. **Email Verification**
   - Enviar email de confirmação
   - Link com token único
   - Ativar conta após verificação

2. **Forgot Password**
   - Email com reset link
   - Token com expiração
   - Novo formulário de senha

3. **Two-Factor Authentication (2FA)**
   - TOTP (Google Authenticator)
   - SMS verification
   - Backup codes

4. **OAuth Providers**
   - GitHub
   - Apple
   - Discord

5. **Profile Management**
   - Editar nome
   - Trocar email
   - Foto de perfil
   - Histórico de login

6. **Security**
   - Auditoria de logins
   - Detecção de atividades suspeitas
   - Rate limiting em endpoints
   - CORS configuration
   - HTTPS enforcement

## Testes

### Endpoints do Backend

```bash
# Registrar
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Get current user
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer {ACCESS_TOKEN}"
```

### Frontend

1. Acessar `http://localhost:8081/login`
2. Criar conta em `/signup`
3. Acessar `/dashboard` (protegido)
4. Verificar localStorage em DevTools > Application > localStorage
5. Verificar token em DevTools > Network > Headers

## Troubleshooting

**Erro: "Port já em uso"**
- Matar processo: `taskkill /PID {PID} /F`
- Ou usar porta diferente

**Erro: "Google OAuth não funciona"**
- Verificar CLIENT_ID em `main.tsx`
- Configurar authorized origins no Google Cloud
- Verificar credentials em Dev Console

**Erro: "Token expirado"**
- Fazer logout e login novamente
- Ou implementar auto-refresh com refresh_token

**Erro: "Email já existe"**
- Usar email diferente
- Ou fazer login com aquele email

**Erro: "Senha incorreta"**
- Verificar se está digitando corretamente
- Considerar "Esqueceu senha?" no futuro

## Suporte

Para mais informações:
- Backend: [backend/README.md](./backend/README.md)
- Frontend: [src/](./src/)
- Documentação FastAPI: http://localhost:8000/docs
- Zustand Docs: https://github.com/pmndrs/zustand
- React OAuth Google: https://www.npmjs.com/package/@react-oauth/google
