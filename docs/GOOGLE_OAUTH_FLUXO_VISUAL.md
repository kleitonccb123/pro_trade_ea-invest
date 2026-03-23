# 🔐 Fluxo de Autenticação Google - Visualização

## 1️⃣ Fluxo Completo (Front → Google → Back → MongoDB)

```
┌─────────────┐          ┌──────────┐         ┌──────────────┐       ┌──────────┐
│   Frontend  │          │  Google  │         │   Backend    │       │ MongoDB  │
│   (React)   │          │  OAuth   │         │  (FastAPI)   │       │  Atlas   │
└──────┬──────┘          └────┬─────┘         └──────┬───────┘       └────┬─────┘
       │                      │                       │                     │
       │ 1. Usuário clica     │                       │                     │
       │    "Login com Google"│                       │                     │
       │                      │                       │                     │
       ├─────────────────────>│                       │                     │
       │   Abrir Google OAuth │                       │                     │
       │   Consent Screen     │                       │                     │
       │                      │                       │                     │
       │ 2. Usuário faz login │                       │                     │
       │    e autoriza        │                       │                     │
       │                      │                       │                     │
       │<─────────────────────┤                       │                     │
       │   Retorna id_token   │                       │                     │
       │   (JWT assinado)     │                       │                     │
       │                      │                       │                     │
       │ 3. Frontend envia    │                       │                     │
       │    token para backend│                       │                     │
       │    POST /api/auth/google                    │                     │
       ├──────────────────────────────────────────────>                     │
       │                      │                       │                     │
       │                      │    4. Validar         │                     │
       │                      │       token com       │                     │
       │                      │       chaves Google   │                     │
       │                      │       ✅ Assinatura  │                     │
       │                      │       ✅ Issuer      │                     │
       │                      │       ✅ Expiração   │                     │
       │                      │                       │                     │
       │                      │    5. Extrair dados:  │                     │
       │                      │       - email         │                     │
       │                      │       - name          │                     │
       │                      │       - picture       │                     │
       │                      │       - sub (ID)      │                     │
       │                      │                       │                     │
       │                      │    6. Procurar ou     │                     │
       │                      │       criar usuário   │                     │
       │                      ├────────────────────────>                    │
       │                      │                       │  Procurar por      │
       │                      │                       │  google_id ou email│
       │                      │                       │<────────────────────┤
       │                      │                       │  Encontrado/Novo   │
       │                      │                       │  Atualizar/Salvar  │
       │                      │                       ├────────────────────>│
       │                      │                       │  {_id, email, name,│
       │                      │                       │   avatar, google_id│
       │                      │                       │   auth_provider}   │
       │                      │                       │<────────────────────┤
       │                      │    7. Gerar tokens    │  OK                 │
       │                      │       - access_token  │                     │
       │                      │       - refresh_token │                     │
       │                      │                       │                     │
       │<──────────────────────────────────────────────┤                    │
       │ 200 OK                                        │                    │
       │ {access_token,                                │                    │
       │  refresh_token,                               │                    │
       │  user: {id, email, name, avatar}}             │                    │
       │                       │                       │                    │
       │ 8. Frontend salva     │                       │                    │
       │    tokens em          │                       │                    │
       │    localStorage        │                       │                    │
       │                       │                       │                    │
       │ 9. Frontend redireciona                       │                    │
       │    para /dashboard    │                       │                    │
       │                       │                       │                    │
```

---

## 2️⃣ Fluxo de Validação do Token (Detalhe)

```
Token JWT recebido do frontend:
┌────────────────────────────────────────┐
│ eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyMyJ9│
│ .eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2Cl...
│ .PqWGDHYzzRKTwJL2azKqRj...                  │
└────────────────────────────────────────┘
    ↓
    ├─ Header: { "alg": "RS256", "kid": "123" }
    ├─ Payload: { "iss": "accounts.google.com", "email": "...", ... }
    └─ Signature: PqWGDHYzzRKTwJL2azKqRj...


VALIDAÇÃO PASSO A PASSO:
═══════════════════════════════════════════════════

┌─────────────────────────────┐
│ 1. VERIFICAR ASSINATURA     │
└──────────────┬──────────────┘
               │
               ├─ Buscar chaves públicas do Google
               ├─ Usar chave com kid "123"
               ├─ Validar: RS256(header.payload) == assinatura
               │
               ✅ SIM: Continuar
               ❌ NÃO: Erro 401 (Token forjado)
               │
┌──────────────┴──────────────┐
│ 2. VERIFICAR ISSUER         │
└──────────────┬──────────────┘
               │
               ├─ Verificar se iss == "accounts.google.com"
               │ ou iss == "https://accounts.google.com"
               │
               ✅ SIM: Continuar
               ❌ NÃO: Erro 401 (Issuer inválido)
               │
┌──────────────┴──────────────┐
│ 3. VERIFICAR EXPIRAÇÃO      │
└──────────────┬──────────────┘
               │
               ├─ Verificar se exp > agora (com skew de 10s)
               │
               ✅ SIM: Continuar
               ❌ NÃO: Erro 401 (Token expirado)
               │
┌──────────────┴──────────────┐
│ 4. VERIFICAR CLIENTE (AUD)  │
└──────────────┬──────────────┘
               │
               ├─ Verificar se aud == GOOGLE_CLIENT_ID
               │
               ✅ SIM: Continuar
               ❌ NÃO: Erro 401 (Token para outra app)
               │
┌──────────────┴──────────────┐
│ 5. EXTRAIR DADOS            │
└──────────────┬──────────────┘
               │
               ├─ email: "usuario@gmail.com"
               ├─ name: "João Silva"
               ├─ picture: "https://lh3.googleusercontent.com/..."
               ├─ sub: "118765432100987654321" (ID único Google)
               │
┌──────────────┴──────────────┐
│ ✅ TOKEN VALIDADO!          │
└─────────────────────────────┘
               │
               ✓ Seguro usar os dados
               ✓ Salvar em MongoDB
               ✓ Gerar JWT da aplicação
```

---

## 3️⃣ Estados Possíveis e Respostas

```
CENÁRIO 1: Novo usuário (nunca fez login antes)
═══════════════════════════════════════════════════

Entrada: Token válido de usuario@gmail.com
         ↓
         MongoDB: "usuario@gmail.com" não existe
         ↓
         Ação: CREATE novo usuário
         ↓
Saída:   {
           "_id": "507f1f77bcf86cd799439011",
           "email": "usuario@gmail.com",
           "name": "João Silva",
           "avatar": "https://...",
           "google_id": "118...",
           "auth_provider": "google",
           "created_at": "2024-01-15T10:30:00Z",
           "last_login": "2024-01-15T10:30:00Z"
         }


CENÁRIO 2: Usuário existente (login repetido)
═══════════════════════════════════════════════════

Entrada: Token válido de usuario@gmail.com
         ↓
         MongoDB: "usuario@gmail.com" JÁ existe
         ↓
         Ação: UPDATE last_login
         ↓
Saída:   {
           "_id": "507f1f77bcf86cd799439011",
           "email": "usuario@gmail.com",
           "name": "João Silva",
           "avatar": "https://...",
           "google_id": "118...",
           "auth_provider": "google",
           "created_at": "2024-01-15T10:00:00Z",
           "last_login": "2024-01-15T15:45:00Z"  ← ATUALIZADO
         }


CENÁRIO 3: Token inválido (forjado, expirado, etc)
═══════════════════════════════════════════════════

Entrada: Token forjado ou expirado
         ↓
         Validação: FALHA em um dos passos
         ↓
Saída:   HTTP 401 Unauthorized
         {
           "detail": "Token Google inválido, expirado ou forjado"
         }
         Log: ERROR - Erro na validação do token Google: ...


CENÁRIO 4: GOOGLE_CLIENT_ID não configurado
═════════════════════════════════════════════════════

Entrada: Qualquer token
         ↓
         Backend: .env sem GOOGLE_CLIENT_ID
         ↓
Saída:   HTTP 500 Internal Server Error
         {
           "detail": "Google OAuth não configurado no servidor"
         }
         Log: ERROR - GOOGLE_CLIENT_ID não configurado no .env
```

---

## 4️⃣ Estrutura de Dados no MongoDB

```
USUÁRIO GOOGLE:
════════════════════════════════════════════════════════════

{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  
  "email": "joao.silva@gmail.com",
  "name": "João Silva",
  "avatar": "https://lh3.googleusercontent.com/a/AGNmyx...",
  
  "auth_provider": "google",              ← Identificador do provedor
  "google_id": "118765432100987654321",   ← ID único do Google
  "hashed_password": "",                  ← Não usa senha
  
  "is_active": true,
  "created_at": ISODate("2024-01-15T10:30:00.000Z"),
  "updated_at": ISODate("2024-01-15T10:30:00.000Z"),
  "last_login": ISODate("2024-01-15T15:45:00.000Z"),
}


USUÁRIO EMAIL/SENHA (comparação):
════════════════════════════════════════════════════════════

{
  "_id": ObjectId("507f1f77bcf86cd799439012"),
  
  "email": "maria.santos@email.com",
  "name": "Maria Santos",
  "avatar": null,                         ← Sem avatar automático
  
  "auth_provider": "email",               ← Provedor local
  "google_id": null,                      ← Sem ID do Google
  "hashed_password": "$2b$12$7Zqx9...",  ← Senha hasheada
  
  "is_active": true,
  "created_at": ISODate("2024-01-14T08:15:00.000Z"),
  "updated_at": ISODate("2024-01-14T08:15:00.000Z"),
  "last_login": ISODate("2024-01-15T09:20:00.000Z"),
}
```

---

## 5️⃣ Fluxo de Erro - Token Forjado

```
Ataque Tentado:
===============

Hacker tenta falsificar um token:
┌────────────────────────────────┐
│ eyJhbGc.forged.payload.fake...│
└────────────────────────────────┘

Backend recebe:
     ↓
     ├─ Busca chaves públicas do Google
     ├─ Tenta validar assinatura
     │  ├─ Calcula: RS256(header.payload)
     │  ├─ Compara com: "fake..."
     │  └─ RESULTADO: NÃO CORRESPONDE ❌
     │
     └─ Levanta HTTPException(401)

Resposta ao Hacker:
┌──────────────────────────────────┐
│ HTTP 401 Unauthorized            │
│                                  │
│ {                                │
│   "detail": "Token Google        │
│             inválido, expirado   │
│             ou forjado"          │
│ }                                │
└──────────────────────────────────┘

Log no Backend:
┌────────────────────────────────────────┐
│ 2024-01-15 15:44:21 ERROR             │
│ Erro na validação do token Google:    │
│ Invalid signature detected             │
│ Source: 192.168.1.100                 │
└────────────────────────────────────────┘

Resultado: ✅ ATAQUE BLOQUEADO
          ❌ Token NÃO é aceito
          📝 Tentativa registrada em logs
```

---

## 6️⃣ Segurança - Por Que Funciona

```
┌─────────────────────────────────────────────────────┐
│        POR QUE NÃO PODE SER FORJADO?                │
└────────────┬────────────────────────────────────────┘
             │
             ├─ Assinatura RS256 usa chave PRIVADA do Google
             │  └─ Apenas Google tem a chave privada
             │  └─ Hacker não consegue calcular assinatura válida
             │  └─ IMPOSSÍVEL falsificar: assinatura != válida
             │
             ├─ Issuer verificado
             │  └─ Token PRECISA dizer que vem de Google
             │  └─ Se disser outro issuer = rejeitado
             │  └─ Impostor não consegue ter issuer Google legítimo
             │
             ├─ Cliente (GOOGLE_CLIENT_ID) verificado
             │  └─ Token PRECISA ser para esta aplicação
             │  └─ Se for para outra app = rejeitado
             │  └─ Hacker não consegue token para outra client_id
             │
             ├─ Expiração verificada
             │  └─ Token antigo/expirado = rejeitado
             │  └─ Previne replay attacks (reusar token antigo)
             │
             └─ Tudo junto = Segurança máxima
                └─ Token é criptograficamente seguro
                └─ Assegurado por infraestrutura do Google
                └─ Padrão da indústria (RFC 7519)
```

---

## 7️⃣ Tokens da Aplicação (Gerados após validação)

```
Depois que Google OAuth é validado com sucesso,
o backend GERA seus próprios tokens para a sessão:


ACCESS TOKEN (Curta duração = 15 minutos)
═════════════════════════════════════════════

{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "507f1f77bcf86cd799439011",  ← ID do usuário em MongoDB
    "exp": 1705348800,                   ← Expira em 15 minutos
    "iat": 1705348500
  },
  "signature": "HMACSHA256(...)"          ← Assinado com SECRET_KEY
}

Uso: Autenticar requisições do frontend
     Authorization: Bearer <access_token>


REFRESH TOKEN (Longa duração = 30 dias)
═══════════════════════════════════════════

{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "507f1f77bcf86cd799439011",  ← ID do usuário em MongoDB
    "exp": 1708027200,                   ← Expira em 30 dias
    "iat": 1705348500,
    "type": "refresh"
  },
  "signature": "HMACSHA256(...)"          ← Assinado com SECRET_KEY
}

Uso: Renovar access_token sem login novamente
     POST /api/auth/refresh com refresh_token
```

---

## 📊 Resumo de Segurança

```
╔════════════════════════════════════════════════════╗
║        VALIDAÇÕES IMPLEMENTADAS                    ║
╠════════════════════════════════════════════════════╣
║ ✅ Assinatura JWT                                  ║
║ ✅ Issuer (Google)                                 ║
║ ✅ Client ID                                       ║
║ ✅ Expiração                                       ║
║ ✅ Clock Skew (10 segundos)                        ║
║ ✅ Erro 401 para inválidos                         ║
║ ✅ Logging detalhado                               ║
║ ✅ Impossível falsificar (criptografia)            ║
║ ✅ Impossível reusar antigo (expiração)            ║
║ ✅ Impossível impersonar (assinatura)              ║
╚════════════════════════════════════════════════════╝

Resultado: IMPLEMENTAÇÃO SEGURA ✅ PRONTA PARA PRODUÇÃO 🚀
```
