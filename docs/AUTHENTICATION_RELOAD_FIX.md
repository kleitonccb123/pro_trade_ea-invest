# 🔐 AUTENTICAÇÃO - Análise de Problemas e Soluções
**Data**: 19 de Fevereiro, 2026  
**Status**: Problemas identificados + Soluções prontas  
**Prioridade**: CRÍTICA

---

## 📋 RESUMO EXECUTIVO

### Situação Atual
- ✅ Login funciona corretamente
- ❌ Ao recarregar a página (F5), volta para login
- ❌ Token não está sendo persistido entre recargas

### Causa Raiz Identificada
O `onRehydrateStorage` do Zustand **não está resetando `isLoading` para `false`** após restaurar tokens do localStorage, causando que:
1. ProtectedRoute fique preso em "Carregando..."
2. checkAuth() tente validar token
3. Se falhar, redireciona para login (perdendo tokens válidos)

---

## 🔍 PROBLEMAS ENCONTRADOS

### Problema #1: onRehydrateStorage não reseta isLoading
**Arquivo**: `src/context/AuthContext.tsx` (linhas 313-330)  
**Severidade**: 🔴 CRÍTICA

```typescript
// ❌ PROBLEMA: Não retorna novo estado atualizado
onRehydrateStorage: () => (state) => {
  if (state) {
    if (!state.accessToken && !state.refreshToken) {
      // Recupera tokens...
      state.accessToken = accessToken;
      // MAS: isLoading continua undefined/true!
    }
  }
  // ❌ Não retorna estado para Zustand aplicar
},
```

**Sintoma**:
```
[ProtectedRoute] Status: { isAuthenticated: true, isLoading: true }
// Fica preso em "Carregando..." mesmo com token válido
```

**Impacto**:
- Tela de carregamento não some
- checkAuth() tenta validar
- Validação pode falhar (timeout, conexão)
- Token é limpo desnecessariamente
- Redirect para login

---

### Problema #2: Estado inicial isLoading=true sem reset
**Arquivo**: `src/context/AuthContext.tsx` (linha 49)  
**Severidade**: 🟡 ALTA

```typescript
isLoading: true, // Start as true until initial checkAuth is complete
```

**Problema**:
- Zustand persist não restaura `isLoading` do localStorage
- Resultado: Sempre inicia com `isLoading: true`
- Mesmo com token válido, mostra tela de carregamento

---

### Problema #3: onRehydrateStorage não força set() do Zustand
**Arquivo**: `src/context/AuthContext.tsx` (linhas 313-330)  
**Severidade**: 🟡 ALTA

```typescript
// ❌ onRehydrateStorage não pode chamar set() diretamente
// Deve retornar novo estado ou usar a function signature corretamente
onRehydrateStorage: () => (state) => {
  // Modifica state in-place, mas Zustand pode não aplicar
  state.isLoading = false; // ❌ Não funciona!
  return state; // ❌ Zustand ignora
},
```

**Solução**: Usar `onRehydrateStorage` corretamente ou simplificar lógica

---

### Problema #4: Ausência de flag isHydrated
**Arquivo**: Todas  
**Severidade**: 🟡 ALTA

**Problema**:
- Não há como distinguir entre "rehydrating" vs "loaded from initial state"
- ProtectedRoute não pode esperar pela rehydratação corretamente
- checkAuth() pode ser chamado múltiplas vezes desnecessariamente

---

### Problema #5: Rotas WebSocket inválidas
**Arquivo**: `src/hooks/use-websocket.ts`  
**Severidade**: 🟠 MÉDIA

```
Erro: ws://localhost:8000//emergency/ws (note: duplo /)
Esperado: ws://localhost:8000/api/emergency/ws
```

Routes não existem no backend:
- `/emergency/ws` ❌
- `/system/health/ws` ❌
- `/validation/health/detailed` ❌

---

### Problema #6: API calls antes da autenticação estar completa
**Arquivo**: `src/hooks/use-license.tsx`  
**Severidade**: 🟠 MÉDIA

```
[API] Request without token: GET /license/my-plan
Failed to fetch license: AxiosError: Request failed with status code 404
```

O componente tenta buscar dados sem token, causando erro 404.

---

## ✅ SOLUÇÕES

### Solução #1: Corrigir onRehydrateStorage 
**Arquivo**: `src/context/AuthContext.tsx`  
**Impacto**: 🟢 Alto  
**Tempo**: 5 minutos

```typescript
// ANTES (Problema)
onRehydrateStorage: () => (state) => {
  if (state) {
    if (!state.accessToken && !state.refreshToken) {
      const { accessToken, refreshToken } = authService.getTokens();
      if (accessToken) {
        state.accessToken = accessToken;
        state.refreshToken = refreshToken;
        state.isAuthenticated = true;
        // ❌ isLoading não é resetado!
        saveTokensToStorage(accessToken, refreshToken);
      }
    }
  }
},

// DEPOIS (Solução)
onRehydrateStorage: () => (state) => {
  if (state) {
    // Se não tem token no Zustand, tenta recuperar do localStorage direto (authService)
    if (!state.accessToken && !state.refreshToken) {
      const { accessToken, refreshToken } = authService.getTokens();
      if (accessToken) {
        state.accessToken = accessToken;
        state.refreshToken = refreshToken;
        state.isAuthenticated = true;
        state.isLoading = false; // ✅ RESET isLoading
        saveTokensToStorage(accessToken, refreshToken);
      } else {
        state.isLoading = false; // ✅ Se não tem token, não precisa carregar
      }
    } else if (state.accessToken) {
      state.isLoading = false; // ✅ Já tem token, não precisa carregar
      saveTokensToStorage(state.accessToken, state.refreshToken);
    }
  }
},
```

**Resultado**:
- ✅ isLoading é resetado após rehydratação
- ✅ ProtectedRoute mostra conteúdo imediatamente
- ✅ checkAuth() só é chamado se necessário

---

### Solução #2: Adicionar flag isHydrated
**Arquivo**: `src/context/AuthContext.tsx`  
**Impacto**: 🟢 Alto  
**Tempo**: 10 minutos

```typescript
// Adicionar ao AuthStore interface
export interface AuthStore {
  // ... existing fields
  isHydrated: boolean; // ✅ Nova flag
  setHydrated: (value: boolean) => void; // ✅ Nova action
}

// No create()
const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // ... existing
      isHydrated: false, // ✅ Inicia como falso
      
      setHydrated: (value) => set({ isHydrated: value }),
      
      // ... rest of actions
    }),
    {
      // ... existing config
      onRehydrateStorage: () => (state) => {
        // ... existing logic
        if (state) {
          // ... token restoration logic
          // ✅ Marcar como hidratado após restauração
          state.isHydrated = true;
        }
      },
    }
  )
);
```

**Usar em ProtectedRoute**:
```typescript
const { isAuthenticated, isLoading, isHydrated } = useAuthStore();

// Esperar hidratação antes de redirecionar
if (!isHydrated) {
  return <LoadingScreen />;
}

// Agora é seguro verificar autenticação
if (!isAuthenticated) {
  return <Navigate to="/login" />;
}

return <>{children}</>;
```

---

### Solução #3: Corrigir rotas WebSocket
**Arquivo**: `src/hooks/use-websocket.ts`  
**Impacto**: 🟡 Médio (erros não bloqueantes)  
**Tempo**: 15 minutos

**Problema**: URLs com `//` duplos:
```
// ❌ ANTES
ws://localhost:8000//emergency/ws
ws://localhost:8000//system/health/ws

// ✅ DEPOIS
ws://localhost:8000/api/emergency/ws
ws://localhost:8000/api/system/health/ws
```

**Fix**: Revisar todas as conexões WebSocket e corrigir caminhos.

---

### Solução #4: Proteger API calls contra falta de token
**Arquivo**: `src/hooks/use-license.tsx`  
**Impacto**: 🟡 Médio  
**Tempo**: 10 minutos

```typescript
// ANTES
useEffect(() => {
  fetchLicense(); // Sem verificação
}, []);

// DEPOIS
useEffect(() => {
  const token = authService.getAccessToken();
  
  if (!token) {
    console.warn('[useLicense] Sem token, aguardando autenticação');
    return; // Não faz requisição
  }
  
  if (!isHydrated) {
    console.warn('[useLicense] Esperando rehydratação');
    return; // Aguarda Zustand hidratar
  }
  
  fetchLicense();
}, [isHydrated]);
```

---

## 📊 Plano de Implementação

| Ordem | Solução | Arquivo | Impacto | Tempo | Prioridade |
|-------|---------|---------|--------|-------|-----------|
| 1️⃣ | Corrigir onRehydra tStorage | AuthContext.tsx | 🔴 CRÍTICA | 5 min | 🔴 P0 |
| 2️⃣ | Adicionar isHydrated | AuthContext.tsx | 🟢 Alto | 10 min | 🔴 P0 |
| 3️⃣ | Atualizar ProtectedRoute | ProtectedRoute.tsx | 🟢 Alto | 5 min | 🔴 P0 |
| 4️⃣ | Corrigir rotas WebSocket | use-websocket.ts | 🟡 Médio | 15 min | 🟠 P1 |
| 5️⃣ | Proteger API calls | use-license.tsx | 🟡 Médio | 10 min | 🟠 P1 |

---

## 🚀 Checklist de Implementação

### FASE 1: Corrigir Autenticação (P0 - URGENTE)
- [ ] Atualizar `onRehydrateStorage` em AuthContext.tsx
- [ ] Adicionar `isHydrated` flag ao AuthStore
- [ ] Atualizar ProtectedRoute para usar `isHydrated`
- [ ] Testar: Fazer login → Recarregar página → Deve permanecer na dashboard
- [ ] Testar: Fazer logout → Recarregar página → Deve ir para login

### FASE 2: Corrigir Erros (P1 - IMPORTANTE)
- [ ] Corrigir rotas WebSocket (remover `/` duplicados)
- [ ] Proteger API calls contra falta de token
- [ ] Testar erros de WebSocket não aparecem
- [ ] Testar API calls só funcionam com token válido

### FASE 3: Validação
- [ ] Teste E2E: Login completo
- [ ] Teste E2E: Persistência de sessão
- [ ] Teste E2E: Logout e re-login
- [ ] Teste E2E: Timeout de sessão

---

## 🔧 Código Pronto para Implementar

### AuthContext.tsx - Seção onRehydrateStorage
```typescript
onRehydrateStorage: () => (state) => {
  if (state) {
    // Se Zustand não restaurou tokens, tente recuperar do authService
    if (!state.accessToken && !state.refreshToken) {
      const { accessToken, refreshToken } = authService.getTokens();
      if (accessToken) {
        state.accessToken = accessToken;
        state.refreshToken = refreshToken;
        state.isAuthenticated = true;
        state.isLoading = false; // ✅ ADICIONAR ESTA LINHA
        state.isHydrated = true; // ✅ ADICIONAR ESTA LINHA
        saveTokensToStorage(accessToken, refreshToken);
      } else {
        state.isLoading = false; // ✅ ADICIONAR ESTA LINHA
        state.isHydrated = true; // ✅ ADICIONAR ESTA LINHA
      }
    } else if (state.accessToken) {
      // Se Zustand restaurou tokens, sincronize com authService
      state.isLoading = false; // ✅ ADICIONAR ESTA LINHA
      state.isHydrated = true; // ✅ ADICIONAR ESTA LINHA
      saveTokensToStorage(state.accessToken, state.refreshToken);
    } else {
      // Sem tokens de forma alguma
      state.isLoading = false; // ✅ ADICIONAR ESTA LINHA
      state.isHydrated = true; // ✅ ADICIONAR ESTA LINHA
    }
  }
},
```

---

## 📈 Resultados Esperados

### Antes (Problema)
```
1. User faz login ✅
2. Tokens salvos em localStorage ✅
3. User recarrega página (F5)
4. Zustand restaura tokens ❌ (MAS isLoading fica true)
5. ProtectedRoute vê isLoading=true → mostra "Carregando..."
6. checkAuth() tenta validar
7. Se timeout/erro → tokens limpos
8. Redirect para login ❌ (token era válido!)
```

### Depois (Solução)
```
1. User faz login ✅
2. Tokens salvos em localStorage ✅
3. User recarrega página (F5)
4. Zustand restaura tokens + isLoading=false ✅
5. ProtectedRoute vê isLoading=false → mostra conteúdo ✅
6. checkAuth() valida silenciosamente
7. Token é válido → permanece autenticado ✅
8. Dashboard carrega normalmente ✅
```

---

## 📞 Suporte

Se após implementar as soluções ainda houver problemas:

1. **Abra DevTools** (F12) → Console
2. **Procure por logs**:
   - `[AuthContext]` - Logs de autenticação
   - `[ProtectedRoute]` - Status de proteção
   - `[AuthService]` - Logs de persistência
3. **Verifique localStorage**: `Application` → `Local Storage` → Procure por `access_token` e `auth-storage`
4. **Teste a validação manual**:
   ```javascript
   // No console do navegador
   localStorage.getItem('access_token');
   localStorage.getItem('auth-storage');
   ```

---

**Próximas Ações**: Implementar Solução #1 e #2 (CRÍTICAS) imediatamente, depois P1.
