# 🏗️ Architectural Changes Visualization

## ANTES: Problema Identificados

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (React + Zustand)                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ❌ URL hardcoded em múltiplos locais                  │
│     • src/context/AuthContext.tsx → http://...        │
│     • src/hooks/use-websocket.ts → http://...         │
│     • src/lib/api.ts → http://...                     │
│                                                         │
│  ❌ Tokens duplicados                                  │
│     • localStorage                                     │
│     • Zustand state                                    │
│     → Sincronização fraca = drift                      │
│                                                         │
│  ❌ WebSocket conecta ANTES de autenticado             │
│     • Não aguarda token disponível                    │
│     → 401 errors frequentes                            │
│                                                         │
│  ❌ Interceptor fetch token UMA VEZ na init           │
│     → Token pode expirar durante sessão               │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          ↓
           ❌ No logging de problemas


┌─────────────────────────────────────────────────────────┐
│ Backend (FastAPI + MongoDB)                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ❌ MongoDB SSL/TLS failure = silent fallback         │
│     → App switches to SQLite sem warning             │
│     → Produção impactada sem saber                    │
│                                                         │
│  ❌ Google OAuth não validado                          │
│     • GOOGLE_CLIENT_ID pode ser None                 │
│     • Endpoint retorna erro em runtime               │
│                                                         │
│  ❌ Email validation só no frontend                    │
│     → Backend aceita emails inválidos               │
│                                                         │
│  ❌ WebSocket sem autenticação                         │
│     → Qualquer um pode conectar                      │
│     → Dados sensíveis expostos                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## DEPOIS: Arquitetura Corrigida

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (React + TypeScript)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ src/config/constants.ts (CENTRAL HUB)                     │
│     ┌──────────────────────────────────────────────────┐       │
│     │ API_BASE_URL = "http://localhost:8000"          │       │
│     │ WS_BASE_URL = "ws://localhost:8000"             │       │
│     │ STORAGE_KEYS = { accessToken, refreshToken }    │       │
│     │ AUTH_CONFIG = { loginTimeoutMs, endpoints... }  │       │
│     │ httpToWsUrl() util function                     │       │
│     └──────────────────────────────────────────────────┘       │
│            ↑                                                     │
│            └─ Imports em:                                       │
│               • AuthContext.tsx                                 │
│               • use-websocket.ts                               │
│               • api.ts                                         │
│               • Todos components                              │
│                                                                 │
│  ✅ src/services/authService.ts (SINGLETON)                   │
│     ┌──────────────────────────────────────────────────┐       │
│     │ Single source of truth para tokens               │       │
│     │                                                  │       │
│     │ Methods:                                        │       │
│     │  • getAccessToken()                            │       │
│     │  • getRefreshToken()                           │       │
│     │  • setTokens(access, refresh)                  │       │
│     │  • clearTokens()                               │       │
│     │  • validateTokens()                            │       │
│     │  • isAuthenticated()                           │       │
│     │  • refreshAccessToken()                        │       │
│     │  • onTokensChange(callback)                    │       │
│     │                                                  │       │
│     │ Features:                                       │       │
│     │  • JWT parsing com validação exp               │       │
│     │  • Cross-tab sync via window events            │       │
│     │  • Custom localStorage keys                    │       │
│     └──────────────────────────────────────────────────┘       │
│                             ↑                                   │
│                    Utilizado por:                               │
│                    • AuthContext                               │
│                    • api.ts interceptors                       │
│                    • use-websocket.ts                          │
│                                                                 │
│  ✅ src/lib/api.ts (SMART INTERCEPTOR)                        │
│     ┌──────────────────────────────────────────────────┐       │
│     │ Request Interceptor:                             │       │
│     │   • Fetch token @ REQUEST TIME (não init)       │       │
│     │   • Always fresh token                           │       │
│     │   • Add "Bearer {token}" header                 │       │
│     │                                                  │       │
│     │ Response Interceptor:                            │       │
│     │   • On 401: Try refresh token                   │       │
│     │   • Use authService for storage                 │       │
│     │   • Emit error events                           │       │
│     │   • Redirect to login if needed                 │       │
│     └──────────────────────────────────────────────────┘       │
│                                                                 │
│  ✅ src/hooks/use-websocket.ts (LAZY + AUTH)                  │
│     ┌──────────────────────────────────────────────────┐       │
│     │ Lazy Connection Pattern:                         │       │
│     │   • shouldConnect() = requires auth             │       │
│     │   • No connection until authenticated           │       │
│     │                                                  │       │
│     │ Auth Monitoring:                                │       │
│     │   • useEffect watches isAuthenticated           │       │
│     │   • Connects on login                           │       │
│     │   • Disconnects on logout                       │       │
│     │                                                  │       │
│     │ Safe URL Building:                              │       │
│     │   • httpToWsUrl() util                          │       │
│     │   • buildWsUrl(baseUrl, token)                 │       │
│     │   • No string concatenation                     │       │
│     │                                                  │       │
│     │ Token Management:                               │       │
│     │   • Fetch token @ connect time                  │       │
│     │   • Use authService                             │       │
│     │   • Enhanced logging                            │       │
│     └──────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                             ↓↓↓
┌─────────────────────────────────────────────────────────────────┐
│ Backend (FastAPI + Python)                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ MongoDB Connection (database.py)                           │
│     ┌──────────────────────────────────────────────────┐       │
│     │ TLS + certifi configuration                      │       │
│     │ Connection options with timeouts                │       │
│     │                                                  │       │
│     │ ERROR HANDLING:                                 │       │
│     │   → MongoDB fails                              │       │
│     │   → CRITICAL log emitted                        │       │
│     │     "🚨 MONGODB CONNECTION FAILED"             │       │
│     │     + diagnostic info                           │       │
│     │   → Fallback to SQLite                         │       │
│     │   → SQLite fails                               │       │
│     │   → CRITICAL log emitted                        │       │
│     │     "🚨 CRITICAL ERROR - BOTH FAILED"          │       │
│     │   → Fallback to in-memory mock                 │       │
│     └──────────────────────────────────────────────────┘       │
│                                                                 │
│  ✅ Startup Validation (main.py)                              │
│     ┌──────────────────────────────────────────────────┐       │
│     │ @app.on_event("startup"):                        │       │
│     │   1. Check GOOGLE_CLIENT_ID                     │       │
│     │      If None → CRITICAL log                    │       │
│     │      + instructions to fix                      │       │
│     │   2. Connect to MongoDB                         │       │
│     │   3. Initialize databases                       │       │
│     │   4. Start background tasks                     │       │
│     └──────────────────────────────────────────────────┘       │
│                                                                 │
│  ✅ Email Validation (auth/router.py)                         │
│     ┌──────────────────────────────────────────────────┐       │
│     │ /register endpoint:                              │       │
│     │   1. Validate email format (RFC 5322)           │       │
│     │   2. If invalid → 400 "Email inválido"         │       │
│     │   3. Check if already exists                    │       │
│     │   4. Create user                                │       │
│     │                                                  │       │
│     │ /login endpoint:                                │       │
│     │   1. Validate email format                      │       │
│     │   2. Find user                                  │       │
│     │   3. Verify password                            │       │
│     │   4. Return tokens                              │       │
│     └──────────────────────────────────────────────────┘       │
│                                                                 │
│  ✅ WebSocket Authentication (bots/router.py)                 │
│     ┌──────────────────────────────────────────────────┐       │
│     │ @router.websocket("/ws/{client_type}")           │       │
│     │                                                  │       │
│     │ 1. Extract token from query param or header      │       │
│     │    ws://host/ws/dashboard?token=JWT             │       │
│     │                                                  │       │
│     │ 2. Validate token using decode_token()          │       │
│     │    → Get user_id from payload                   │       │
│     │                                                  │       │
│     │ 3. If invalid -> Close with code 4001/4002/4003 │       │
│     │                                                  │       │
│     │ 4. If valid -> Proceed to connect               │       │
│     │    → Enhanced logging with user_id              │       │
│     └──────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Comparison

### ANTES: Token Management (Broken)

```
Frontend:
┌──────────────────────────┐
│ User Login Happens       │
└──────────────┬───────────┘
               │
               ↓
         ┌─────────────────────────┐
         │ localStorage.setItem()  │ ← Direct write
         └──────┬──────────────────┘
                │
                ├─→ Zustand state update (🧵 Race condition)
                │
                ├─→ useAPI.ts cached token (❌ Stale)
                │
                └─⚠️ Desynchronization risk


WebSocket:
┌──────────────────────────┐
│ Hook Initialize          │
└──────────────┬───────────┘
               │
               ↓
        ┌──────────────────┐
        │ Get token @ INIT │ ← Cached once
        │ (from localStorage) │
        └──────┬───────────┘
               │
               ↓
     🚀 Immediately connect  ← No auth check
        (may fail if not ready)
```

### DEPOIS: Token Management (Fixed)

```
Frontend:
┌──────────────────────────┐
│ User Login Happens       │
└──────────────┬───────────┘
               │
               ↓
    ┌─────────────────────────────┐
    │ authService.setTokens()     │ ← Single entry point
    └──────┬──────────────────────┘
           │
           ├─→ localStorage write (verified)
           │
           ├─→ Dispatch 'tokensUpdated' event
           │
           └─→ All modules notified
                 (AuthContext, API, WebSocket)


WebSocket:
┌──────────────────────────────────┐
│ Hook Initialize                  │
└──────────────┬───────────────────┘
               │
               ↓
        ┌────────────────────────────┐
        │ useEffect watches          │
        │ isAuthenticated change      │
        └──────┬─────────────────────┘
               │
               ├─ Not authenticated      → Don't connect
               │
               └─ Authenticated          → Call connect()
                                              │
                                              ↓
                          ┌──────────────────────────────────┐
                          │ connect() function:              │
                          │  1. shouldConnect() check        │
                          │  2. Get fresh token from         │
                          │     authService                  │
                          │  3. Build safe URL with token    │
                          │  4. Connect with timeout         │
                          │  5. Reconnect with exponential   │
                          │     backoff (capped)             │
                          └──────────────────────────────────┘


API Requests:
┌──────────────────────────┐
│ HTTP Request Made        │
└──────────────┬───────────┘
               │
               ↓
        ┌──────────────────────────┐
        │ Request Interceptor      │
        │ (triggered for EVERY req)│
        └──────┬───────────────────┘
               │
               ├─ Fetch token @ REQUEST TIME (fresh)
               │   from authService
               │
               ├─ Add Authorization header
               │
               └─→ Send request
                      │
                      ├─ Success → Extract response data
                      │
                      └─ 401 Unauthorized
                            │
                            ↓
                    Response Interceptor:
                    1. Try refresh token
                    2. Get new access token
                    3. Retry original request
                    4. If refresh fails → Clear tokens
                       & redirect to login
```

---

## Error Handling Flow

### MongoDB Connection Failure

```
┌─────────────────────────────┐
│ Server Startup              │
│ connect_db() called         │
└──────────────┬──────────────┘
               │
               ↓
        ┌──────────────────────┐
        │ Try MongoDB Connect  │
        └──────┬───────────────┘
               │
        ┌──────┴───────┐
        │              │
      ✅ Success      ❌ Error
        │              │
        │              ↓
        │      ┌────────────────────────┐
        │      │ LOG CRITICAL:          │
        │      │ "🚨 MONGODB FAILED"   │
        │      │ + diagnostics          │
        │      └──────┬─────────────────┘
        │             │
        │             ↓
        │      ┌────────────────────────┐
        │      │ Try SQLite Fallback    │
        │      └──────┬─────────────────┘
        │             │
        │        ┌────┴─────┐
        │        │           │
        │      ✅ OK      ❌ Fail
        │        │           │
        │        │           ↓
        │        │    ┌────────────────────┐
        │        │    │ LOG CRITICAL:      │
        │        │    │ "BOTH FAILED"      │
        │        │    │ Use in-memory mock │
        │        │    └────────────────────┘
        │        │
        └────────┴──→ App continues (degraded)
                      Logs clearly indicate status
```

---

## Security Improvements

### Before vs After

```
BEFORE:
┌──────────────────────────────────────────────────┐
│ WebSocket Endpoint                               │
│ @router.websocket("/ws/{client_type}")           │
├──────────────────────────────────────────────────┤
│ ❌ No authentication check                       │
│ ❌ Anyone can connect                            │
│ ❌ Receives all real-time data                   │
│ ❌ Security vulnerability                        │
└──────────────────────────────────────────────────┘


AFTER:
┌──────────────────────────────────────────────────┐
│ WebSocket Endpoint                               │
│ @router.websocket("/ws/{client_type}")           │
├──────────────────────────────────────────────────┤
│ ✅ Requires Bearer token in query or header      │
│ ws://host/ws/dashboard?token=JWT_TOKEN          │
│                                                  │
│ ✅ Validates token using decode_token()         │
│                                                  │
│ ✅ Extracts user_id from payload                │
│                                                  │
│ ✅ Closes with 4001/4002/4003 if invalid       │
│                                                  │
│ ✅ Logs user_id for audit trail                 │
│                                                  │
│ ✅ Only authenticated users receive data        │
│                                                  │
│ ✅ Security: PASSED ✓                           │
└──────────────────────────────────────────────────┘
```

---

## Testing Strategy

```
┌────────────────────────────────────────────────────────────┐
│ Test MongoDB Connection                                    │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ Run Test Script:                                           │
│ $ python test_mongodb_tls.py                              │
│  OR                                                        │
│ $ node test_mongodb_tls.js                                │
│                                                            │
│ Checks:                                                    │
│  1. ✓ Driver installation                                 │
│  2. ✓ SSL certificates present                            │
│  3. ✓ DATABASE_URL configured                             │
│  4. ✓ MongoDB atlas reachable                             │
│  5. ✓ TLS handshake successful                            │
│  6. ✓ Ping command working                                │
│                                                            │
│ Output:                                                    │
│ ================================================================================│
│ ✅ ALL TESTS PASSED - MongoDB connection is healthy!      │
│ ================================================================================│
│                                                            │
└────────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────┐
│ Frontend Integration Tests                                 │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ 1. Login Flow:                                             │
│    • Form → Submit                                         │
│    • authService.setTokens() called                        │
│    • Token in authService singleton ✓                     │
│    • Token in localStorage ✓                              │
│    • Zustand state updated ✓                              │
│                                                            │
│ 2. WebSocket Connection:                                   │
│    • isAuthenticated = true                                │
│    • useEffect triggers connect()                          │
│    • shouldConnect() returns true                          │
│    • Token fetched from authService ✓                     │
│    • buildWsUrl() creates safe URL ✓                      │
│    • WebSocket connects successfully ✓                    │
│                                                            │
│ 3. Token Refresh:                                          │
│    • API request made                                      │
│    • Interceptor fetches token @ request time ✓           │
│    • If 401: Response interceptor calls refresh ✓         │
│    • New token obtained from authService ✓                │
│    • Request retried with new token ✓                    │
│                                                            │
│ 4. Logout Flow:                                            │
│    • logout() called                                       │
│    • authService.clearTokens() called                      │
│    • All tokens removed                                    │
│    • WebSocket disconnects automatically ✓                │
│    • Redirect to login ✓                                  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Summary of Improvements

| Aspect | Before | After | Impact |
|--------|--------|-------|--------|
| **URL Config** | Hardcoded in 5+ places | Single constants.ts | 🟢 Maintainability |
| **Token Storage** | localStorage + Zustand | authService singleton | 🟢 Reliability |
| **WebSocket Auth** | None | JWT validation | 🟢 Security |
| **Token Freshness** | Cached @ init | Fresh @ request time | 🟢 Reliability |
| **MongoDB Fallback** | Silent | CRITICAL logs | 🟢 Observability |
| **Startup Validation** | None | Google OAuth check | 🟢 Reliability |
| **Email Format** | Frontend only | Backend validated | 🟢 Security |
| **Error Messages** | Generic | Diagnostic detail | 🟢 Debuggability |

---

**Architecture Status**: ✅ MODERNIZED AND RESILIENT
