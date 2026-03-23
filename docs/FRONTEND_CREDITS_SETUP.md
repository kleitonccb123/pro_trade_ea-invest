# 🚀 Frontend Credit System - Setup & Integration

Guia rápido para integração do sistema de créditos no seu frontend React existente.

---

## 📦 Instalação de Dependências

```bash
# React Query (state management)
npm install @tanstack/react-query

# React Confetti (animações de celebração)
npm install react-confetti-explosion

# Recharts (gráficos)
npm install recharts

# Lucide React (ícones)
npm install lucide-react

# ShadcnUI já deve estar instalado
# Se não, instale com:
npx shadcn-ui@latest init
```

---

## 🔧 Setup Rápido

### 1. Copiar componentes

```bash
# Copiar todos os arquivos
cp -r src/components/credits/* /seu/projeto/src/components/credits/
cp -r src/hooks/useCredits.ts /seu/projeto/src/hooks/
```

### 2. Instalar componentes ShadcnUI necessários

```bash
npx shadcn-ui@latest add card
npx shadcn-ui@latest add badge
npx shadcn-ui@latest add progress
npx shadcn-ui@latest add tooltip
npx shadcn-ui@latest add tabs
npx shadcn-ui@latest add alert-dialog
npx shadcn-ui@latest add button
```

### 3. Configurar variáveis de ambiente

```bash
# .env.local (ou .env.development)
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_AUTH_STORAGE_KEY=authToken
```

### 4. Adicionar QueryClient ao root da aplicação

```tsx
// main.tsx ou App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60000,           // 1 minuto
      cacheTime: 300000,          // 5 minutos
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <YourApp />
    </QueryClientProvider>
  );
}

export default App;
```

---

## 📤 Exemplo de Integração

### Opção 1: Usar Dashboard Completo

```tsx
// pages/Dashboard.tsx
import { Dashboard } from '@/components/credits/Dashboard';

export default function DashboardPage() {
  return (
    <Dashboard
      userId={user.id}
      onNavigate={(path) => navigate(path)}
    />
  );
}
```

### Opção 2: Integrar Componentes Individuais

```tsx
// pages/MyBotsPage.tsx
import { useState } from 'react';
import { CreditMonitor } from '@/components/credits/CreditMonitor';
import { BotCard } from '@/components/credits/BotCard';
import { SingletonActivationModal } from '@/components/credits/SingletonActivationModal';
import { SwapConfirmationModal } from '@/components/credits/SwapConfirmationModal';
import useCredits from '@/hooks/useCredits';

export default function MyBotsPage() {
  const { 
    credits, 
    startBot, 
    stopBot, 
    updateConfig,
  } = useCredits();

  const [showSingletonModal, setShowSingletonModal] = useState(false);
  const [showSwapModal, setShowSwapModal] = useState(false);

  return (
    <div className="space-y-6 p-6">
      {/* Credit Monitor no topo */}
      {credits && (
        <CreditMonitor
          plan={credits.plan}
          activationCredits={credits.activationCredits}
          activationCreditsUsed={credits.activationCreditsUsed}
          activationCreditsRemaining={credits.activationCreditsRemaining}
          activeBotsCount={credits.activeBotsCount}
          onUpgradeClick={() => navigate('/upgrade')}
        />
      )}

      {/* Grid de Bots */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {bots.map(bot => (
          <BotCard
            key={bot.id}
            botId={bot.id}
            botName={bot.name}
            tradingPair={bot.pair}
            isRunning={bot.isRunning}
            isActiveSlot={bot.isActiveSlot}
            balance={bot.balance}
            profit={bot.profit}
            profitPercentage={bot.profitPercentage}
            swapCount={bot.swapCount}
            activationCreditsRemaining={
              credits?.activationCreditsRemaining || 0
            }
            onStart={startBot}
            onStop={stopBot}
            onConfigUpdate={updateConfig}
          />
        ))}
      </div>

      {/* Modals */}
      <SingletonActivationModal
        isOpen={showSingletonModal}
        onClose={() => setShowSingletonModal(false)}
        onConfirm={async () => {
          await startBot(selectedBotId);
          setShowSingletonModal(false);
        }}
        currentBotName={currentBot?.name}
        currentBotPair={currentBot?.pair}
        newBotName={selectedBot?.name}
        newBotPair={selectedBot?.pair}
        activationCreditsRemaining={
          credits?.activationCreditsRemaining
        }
      />
    </div>
  );
}
```

### Opção 3: Usar Hook isoladamente

```tsx
// components/MyCustomBotControl.tsx
import { useCredits } from '@/hooks/useCredits';

export function MyCustomBotControl({ botId }: { botId: string }) {
  const {
    credits,
    startBot,
    stopBot,
    isStartingBot,
    error,
    clearError,
  } = useCredits();

  return (
    <div>
      {error && (
        <div className="p-3 bg-red-100 text-red-800 rounded">
          {error}
          <button onClick={clearError}>✕</button>
        </div>
      )}

      <button
        onClick={() => startBot(botId)}
        disabled={isStartingBot || !credits?.activationCreditsRemaining}
      >
        {isStartingBot ? 'Iniciando...' : 'Iniciar Bot'}
      </button>

      <p>Créditos disponíveis: {credits?.activationCreditsRemaining}</p>
    </div>
  );
}
```

---

## 🎨 Customização

### Mudar Cores Primárias

Editar `tailwind.config.ts`:

```ts
export default {
  theme: {
    extend: {
      colors: {
        credit: {
          50: '#f0f9ff',
          500: '#0ea5e9',
          600: '#0284c7',
          900: '#0c2d6b',
        },
      },
    },
  },
};
```

Usar em componentes:
```tsx
<div className="bg-credit-100 text-credit-900">
  Seu Conteúdo
</div>
```

### Customizar Types do useCredits

```tsx
// types/credits.ts
export interface CustomCreditData {
  plan: 'starter' | 'pro' | 'premium' | 'enterprise';
  activationCredits: number;
  // ... suas props
}

// hooks/useCredits.ts (modificar)
const { data: credits, ...rest } = useQuery<CustomCreditData>([...])
```

### Temas Diferentes por Plano

```tsx
const PLAN_THEMES = {
  starter: 'bg-blue-50 border-blue-300',
  pro: 'bg-purple-50 border-purple-300',
  premium: 'bg-amber-50 border-amber-300',
};

<Card className={PLAN_THEMES[credits.plan]}>
  {/* ... */}
</Card>
```

---

## 🧪 Testando Localmente

### Mock Data para Dev

```tsx
// hooks/useCredits.ts (adicionar modo dev)
const USE_MOCK_DATA = process.env.REACT_APP_USE_MOCK_CREDITS === 'true';

if (USE_MOCK_DATA) {
  return {
    credits: {
      plan: 'pro',
      activationCredits: 5,
      activationCreditsUsed: 2,
      activationCreditsRemaining: 3,
      activeBotsCount: 1,
      lastUpdated: new Date().toISOString(),
    },
    // ... mock methods
  };
}
```

Usar com:
```bash
REACT_APP_USE_MOCK_CREDITS=true npm run dev
```

### Testar Componentes Isoladamente

```tsx
// stories/CreditMonitor.stories.tsx (Storybook)
import { CreditMonitor } from '@/components/credits/CreditMonitor';

export default {
  component: CreditMonitor,
  title: 'Components/Credits/CreditMonitor',
};

export const Pro = {
  args: {
    plan: 'pro',
    activationCredits: 5,
    activationCreditsUsed: 2,
    activationCreditsRemaining: 3,
    activeBotsCount: 1,
  },
};

export const SemCreditos = {
  args: {
    plan: 'starter',
    activationCredits: 1,
    activationCreditsUsed: 1,
    activationCreditsRemaining: 0,
    activeBotsCount: 0,
  },
};
```

Run Storybook:
```bash
npm run storybook
```

---

## 🔗 Conectar ao Backend Real

### Configurar Token Auth

```tsx
// hooks/useCredits.ts (modificar)
const getAuthHeader = () => {
  const token = localStorage.getItem('authToken') || 
                sessionStorage.getItem('authToken');
  
  if (!token) {
    throw new Error('No auth token found');
  }
  
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
};
```

### Usar Context para Token (Melhor Prática)

```tsx
// context/AuthContext.tsx
import { createContext, useContext } from 'react';

interface AuthContextType {
  token: string | null;
  user: any;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // ... implementação
  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
```

Usar no hook:
```tsx
// hooks/useCredits.ts
const { token } = useAuth();

const { data: credits } = useQuery(['credits'], async () => {
  const res = await fetch(
    `${API_BASE_URL}/auth/profile/activation-credits`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return res.json();
});
```

---

## 🚨 Troubleshooting

### Erro: "Cannot find module '@/components/credits/CreditMonitor'"

**Solução**: Verificar path alias no `vite.config.ts` ou `tsconfig.json`

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

### Erro: "useQuery is not a function"

**Solução**: Envolver app em QueryClientProvider

```tsx
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <YourApp />
    </QueryClientProvider>
  );
}
```

### Modais não aparecem

**Solução**: Verificar z-index do modal vs outras camadas

```css
/* Adicionar se necessário */
.modal-overlay {
  z-index: 999999;
}
```

### API retorna 401 Unauthorized

**Solução**: Token expirado ou invalid
```tsx
// Adicionar refresh token logic
const { refetch } = useQuery([...], {
  onError: (error: any) => {
    if (error.response?.status === 401) {
      // Refresh token aqui
      refreshToken().then(() => refetch());
    }
  },
});
```

---

## 📊 Performance Tips

### 1. Memoize componentes pesados
```tsx
export const BotCard = memo(({ botId, ...props }: Props) => {
  return <Card>{/* ... */}</Card>;
}, (prevProps, nextProps) => {
  return prevProps.botId === nextProps.botId;
});
```

### 2. Lazy load componentes
```tsx
const AffiliatePanel = lazy(() => import('./AffiliatePanel'));

<Suspense fallback={<Skeleton />}>
  <AffiliatePanel {...props} />
</Suspense>
```

### 3. Otimizar queries
```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,  // 5 minutos
      cacheTime: 1000 * 60 * 10, // 10 minutos
      retry: 2,
    },
  },
});
```

### 4. Virtualizar listas (se muitos bots)
```tsx
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={bots.length}
  itemSize={300}
>
  {({ index, style }) => (
    <div style={style}>
      <BotCard bot={bots[index]} />
    </div>
  )}
</FixedSizeList>
```

---

## 🎯 Checklist Final

- [ ] Todas as dependências instaladas
- [ ] ShadcnUI componentes adicionados
- [ ] QueryClientProvider configurado
- [ ] useCredits hook testado
- [ ] API_BASE_URL configurada
- [ ] Auth token obtido do localStorage/context
- [ ] Componentes aparecem sem erros
- [ ] Modais funcionam
- [ ] Animações suaves
- [ ] Responsive em mobile
- [ ] Dark mode suportado (se necessário)
- [ ] Erros tratados gracefully
- [ ] Performance aceitável (<100ms renders)
- [ ] Testes unitários criados
- [ ] Documentação atualizada

---

## 📞 Suporte

Se encontrar problemas:
1. Ver console do navegador (F12) para erros
2. Verificar Network tab para requisições falhadas
3. Ler README.md para documentação completa
4. Verificar tipos TypeScript (IDE deve mostrar erros)

---

**Pronto para usar!** 🚀  
**Última atualização**: 2026-02-11
