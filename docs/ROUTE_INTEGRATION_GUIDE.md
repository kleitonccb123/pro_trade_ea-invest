/**
 * ROUTE_INTEGRATION_GUIDE.md
 * 
 * Guia para integrar MyStrategies e PublicStrategies ao roteamento principal
 */

# Como Integrar as Estratégias ao App.tsx

## 1. Imports Necessários

Adicione estes imports no topo do seu `App.tsx`:

```typescript
import MyStrategies from './pages/MyStrategies';
import PublicStrategies from './pages/PublicStrategies';
import ProtectedRoute from './components/ProtectedRoute'; // Se usar ACL
```

## 2. Adicionar Rotas

No seu arquivo de roteamento (presumindo React Router v6), adicione:

```typescript
// Rotas públicas
<Route path="/strategies" element={<PublicStrategies />} />

// Rotas protegidas (autenticação obrigatória)
<Route
  path="/my-strategies"
  element={
    <ProtectedRoute>
      <MyStrategies />
    </ProtectedRoute>
  }
/>
```

## 3. Links de Navegação

Adicione no seu navbar/menu de navegação:

```typescript
<nav>
  <Link to="/strategies">Estratégias Públicas</Link>
  <Link to="/my-strategies">Minhas Estratégias</Link>
</nav>
```

## 4. Verificar Dependências

Certifique-se que você tem:

- ✅ React Router v6
- ✅ Zustand (para AuthContext - vérificar em src/context/AuthContext.tsx)
- ✅ Axios
- ✅ TailwindCSS
- ✅ Lucide React Icons

## 5. Testar Integração

```bash
# Terminal 1 - Backend
cd backend
python run_server.py

# Terminal 2 - Frontend
npm run dev
```

Depois navegue para:
- `http://localhost:5173/strategies` - Ver estratégias públicas
- `http://localhost:5173/my-strategies` - Ver suas estratégias (protegido)

## 6. Fluxo Completo

1. **Usuário não autenticado:**
   - Acessa `/strategies` → Vê estratégias públicas ✅
   - Tenta acessar `/my-strategies` → Redirecionado para login ❌

2. **Usuário autenticado:**
   - Acessa `/strategies` → Vê estratégias públicas ✅
   - Acessa `/my-strategies` → Vê suas estratégias ✅
   - Clica em "Criar Estratégia" → Modal aparece ✅
   - Preenche formulário → API POST envia com Bearer token ✅
   - Backend valida JWT → Cria estratégia com user_id ✅
   - Resposta volta → UI atualiza grid ✅
   - Pode editar/deletar apenas suas estratégias ✅

## 7. Arquivos Criados

```
src/
├── types/
│   └── strategy.ts (Interfaces TypeScript)
├── hooks/
│   └── useStrategies.ts (Custom hook CRUD)
├── pages/
│   ├── MyStrategies.tsx (Minhas estratégias - protegido)
│   └── PublicStrategies.tsx (Estratégias públicas - público)
└── lib/
    └── api.ts (Axios com interceptor)
```

## 8. Próximos Passos

- [ ] Integrar rotas ao App.tsx
- [ ] Testar fluxo end-to-end
- [ ] Implementar encriptação de chaves Binance (AES/Fernet)
- [ ] Criar página de Trading com gráficos
- [ ] Adicionar sistema de notificações

## 9. Troubleshooting

### Erro: "Cannot find module 'useStrategies'"
→ Certifique-se que `src/hooks/useStrategies.ts` foi criado

### Erro: "401 Unauthorized"
→ Verifique se o token JWT está sendo enviado no header `Authorization: Bearer <token>`
→ Verifique em Network → Request Headers

### Erro: "user_id is required"
→ Backend esperando `user_id` no JWT token
→ Verifique token em `https://jwt.io` (decode sem validar)

### Componente não renderiza
→ Verifique se React Router está configurado
→ Verifique se ProtectedRoute está retornando corretamente
→ Check console.log para erros

## 10. Estrutura de Dados (Backend ↔ Frontend)

**Backend Response (MongoDB):**
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "Estratégia Momentum",
  "description": "Segue momentum de 15 minutos",
  "user_id": "507f1f77bcf86cd799439010",
  "parameters": {
    "timeframe": "15m",
    "threshold": 0.02
  },
  "is_public": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Frontend TypeScript Interface:**
```typescript
interface StrategyResponse {
  id: string; // Aliased from _id
  name: string;
  description?: string;
  user_id: string;
  parameters: Record<string, any>;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}
```

**Hook Usage:**
```typescript
const MyComponent = () => {
  const { strategies, fetchStrategies, createStrategy, deleteStrategy } = useStrategies();

  useEffect(() => {
    fetchStrategies(); // GET /api/strategies/my
  }, [fetchStrategies]);

  const handleCreate = async (data) => {
    await createStrategy(data); // POST /api/strategies/submit
  };

  return (
    <div>
      {strategies.map(s => (
        <div key={s.id}>{s.name}</div>
      ))}
    </div>
  );
};
```

---

## Status da Integração

✅ TypeScript interfaces criadas
✅ Custom hook criado
✅ MyStrategies component criado
✅ PublicStrategies component criado
✅ API interceptor existe (src/lib/api.ts)
⏳ Aguardando integração ao App.tsx

**Próxima ação:** Localize seu arquivo App.tsx e adicione as rotas conforme guia acima.
