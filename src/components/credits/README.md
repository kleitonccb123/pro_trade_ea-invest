# 🎨 Frontend - Sistema de Créditos de Ativação

Componentes React + TypeScript + ShadcnUI para gerenciar visualmente o sistema de créditos de ativação.

---

## 📋 Componentes Criados

### 1. **CreditMonitor.tsx**
Card de monitoramento de créditos fixo no dashboard.

**Props:**
```typescript
interface CreditMonitorProps {
  plan: 'starter' | 'pro' | 'premium';
  activationCredits: number;
  activationCreditsUsed: number;
  activationCreditsRemaining: number;
  activeBotsCount: number;
  onUpgradeClick?: () => void;
}
```

**Funcionalidades:**
- Progress bar visual dos créditos usados
- Badge com plano atual
- Tooltip explicado cada conceito
- Alertas se créditos <= 2
- Detalhes expansíveis com benefits do plano
- Botão de upgrade sugerido

**Exemplo:**
```tsx
<CreditMonitor
  plan="pro"
  activationCredits={5}
  activationCreditsUsed={2}
  activationCreditsRemaining={3}
  activeBotsCount={1}
  onUpgradeClick={() => navigateTo('/upgrade')}
/>
```

---

### 2. **SwapConfirmationModal.tsx**
Modal de confirmação quando usuário altera configuração do bot.

**Props:**
```typescript
interface SwapConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  swapCount: number;
  activationCreditsRemaining: number;
  botName: string;
  changesSummary?: string;
}
```

**Funcionalidades:**
- Diferencia entre swap grátis (1-2) e pago (3+)
- Mostra histórico de swaps
- Aviso visual crítico se falta crédito
- Dicas quando no último swap grátis
- Loading state durante processamento
- Error handling com mensagem clara

**Exemplo:**
```tsx
<SwapConfirmationModal
  isOpen={showModal}
  onClose={() => setShowModal(false)}
  onConfirm={async () => {
    await api.updateBotConfig(botId, newConfig);
    setShowModal(false);
  }}
  swapCount={2}
  activationCreditsRemaining={3}
  botName="ETH Grid"
  changesSummary="Alterando pair para ETH/USDC"
/>
```

---

### 3. **SingletonActivationModal.tsx**
Modal de aviso ao ativar bot quando outro está rodando.

**Props:**
```typescript
interface SingletonActivationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  currentBotName: string;
  currentBotPair: string;
  newBotName: string;
  newBotPair: string;
  costCredit?: number;
  activationCreditsRemaining?: number;
}
```

**Funcionalidades:**
- Visual claro: Bot atual será desligado ↓ / Bot novo será ativado ↑
- Checkbox de confirmação (usuário precisa confirmar entendimento)
- Exibe custo do crédito
- Educacional (mostra que estado é preservado)
- Desabilita botão confirm se checkbox não marcado

**Exemplo:**
```tsx
<SingletonActivationModal
  isOpen={showModal}
  onClose={() => setShowModal(false)}
  onConfirm={async () => {
    await api.startBot(newBotId);
    setShowModal(false);
  }}
  currentBotName="BTC Long"
  currentBotPair="BTC/USDT"
  newBotName="ETH Grid"
  newBotPair="ETH/USDT"
  costCredit={1}
  activationCreditsRemaining={3}
/>
```

---

### 4. **BotStartButton.tsx**
Botão inteligente que mostra START ou STOP com validações de crédito.

**Props:**
```typescript
interface BotStartButtonProps {
  botId: string;
  botName: string;
  botPair: string;
  isRunning: boolean;
  isActiveSlot: boolean;
  swapCount: number;
  activationCreditsRemaining: number;
  otherRunningBot?: { id: string; name: string; pair: string };
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  onSingletonWarning?: (otherBot: any) => void;
  showSkeletonAnimation?: boolean;
}
```

**Funcionalidades:**
- Estados visuais: Lock (inativo), Play (pronto), Pause (rodando)
- Animação confetti quando bot inicia com sucesso
- Mostra status do bot com ícones
- Avisa sobre recursos de swap
- Tooltip contextualizado
- Loading state durante operação

**Estados do Botão:**
1. **Inativo**: Botão cinza com Lock, requer crédito para ativar slot
2. **Pronto**: Botão verde, clicável para iniciar
3. **Rodando**: Botão vermelho (stop), mostra status com checkmark animado

**Exemplo:**
```tsx
<BotStartButton
  botId="bot-1"
  botName="BTC Long"
  botPair="BTC/USDT"
  isRunning={true}
  isActiveSlot={true}
  swapCount={1}
  activationCreditsRemaining={3}
  onStart={async () => {
    await api.startBot('bot-1');
  }}
  onStop={async () => {
    await api.stopBot('bot-1');
  }}
/>
```

---

### 5. **AffiliatePanel.tsx**
Card gamificado do programa de afiliados com tiers e comissões.

**Props:**
```typescript
interface AffiliatePanelProps {
  referralCode: string;
  referralLink: string;
  referredUsersCount: number;
  commissionEarned: number;
  tier: 'bronze' | 'silver' | 'gold' | 'platinum';
  nextTierAt?: number;
  onShareClick?: () => void;
}
```

**Funcionalidades:**
- Badge visual do tier atual (🥉🥈🏆💎)
- Progress bar até próximo tier
- Copy-to-clipboard do link
- Botão share nativo do navegador
- Grid com referências e ganhos acumulados
- Taxa de comissão por tier
- Potencial de ganho calculado
- Dicas educacionais

**Tiers:**
- **Bronze** (0 ref): 10% comissão
- **Silver** (5+ ref): 15% comissão
- **Gold** (15+ ref): 20% comissão
- **Platinum** (50+ ref): 25% comissão

**Exemplo:**
```tsx
<AffiliatePanel
  referralCode="REF123ABC"
  referralLink="https://shop.com/ref/REF123ABC"
  referredUsersCount={8}
  commissionEarned={125.50}
  tier="silver"
  nextTierAt={15}
  onShareClick={() => {
    navigator.share({
      title: 'Join me!',
      url: referralLink
    })
  }}
/>
```

---

### 6. **BotCard.tsx**
Card integrado do bot mostrando métricas, status e ações com créditos.

**Props:** (Veja componente para lista completa)

**Funcionalidades:**
- Métricas: Saldo, PnL, Return %
- Status badges (Ativo, Pronto, Inativo)
- Integração com BotStartButton
- Gráfico em tempo real (LineChart Recharts)
- Alerta sobre consumo de crédito
- Botão editar configuração
- Integração com SwapConfirmationModal e SingletonActivationModal

**Exemplo:**
```tsx
<BotCard
  botId="bot-1"
  botName="BTC Long"
  tradingPair="BTC/USDT"
  isRunning={true}
  isActiveSlot={true}
  balance={2500.50}
  profit={520.25}
  profitPercentage={20.8}
  swapCount={1}
  activationCreditsRemaining={3}
  onStart={startBot}
  onStop={stopBot}
  onConfigUpdate={updateConfig}
/>
```

---

### 7. **Dashboard.tsx** (Example Integration)
Dashboard demonstrando integração completa de todos os componentes.

**Características:**
- CreditMonitor fixo no topo (sticky)
- Grid de BotCards
- Tabs: Bots | Referência | Histórico
- Tips educacionais no bottom
- Alerts contextualizados
- Responsivo (mobile, tablet, desktop)

---

## 🪝 Hook: useCredits

Hook customizado para gerenciar estado de créditos e comunicação com backend.

**Uso:**
```tsx
const {
  credits,           // CreditData | undefined
  error,             // string | null
  isLoadingCredits,  // boolean
  isStartingBot,     // boolean
  validateBotActivation,  // (botId) => Promise<ValidationResponse>
  validateSwap,           // (botId) => Promise<SwapValidationResponse>
  startBot,               // (botId) => Promise<void>
  stopBot,                // (botId) => Promise<void>
  updateConfig,           // ({ botId, config }) => Promise<void>
  upgradePlan,            // (plan) => Promise<void>
  canStartBot,            // (botId?) => boolean
  canSwapBot,             // (swapCount) => boolean
  clearError,             // () => void
} = useCredits();
```

**Exemplo Completo:**
```tsx
function MyComponent() {
  const { 
    credits, 
    startBot, 
    isStartingBot,
    error,
    clearError 
  } = useCredits();

  const handleStart = async () => {
    try {
      await startBot('bot-1');
      console.log('Bot iniciado!');
    } catch (err) {
      console.error('Erro:', err);
    }
  };

  if (error) {
    return (
      <div>
        <p>Erro: {error}</p>
        <button onClick={clearError}>Descartar</button>
      </div>
    );
  }

  return (
    <button onClick={handleStart} disabled={isStartingBot}>
      {isStartingBot ? 'Iniciando...' : 'Iniciar'}
    </button>
  );
}
```

---

## 🎨 Styling & Customization

### Dependências Required
```json
{
  "@shadcn/ui": "*",
  "lucide-react": "*",
  "recharts": "*",
  "react-confetti-explosion": "*",
  "@tanstack/react-query": "*",
  "tailwindcss": "*"
}
```

### Instalar Componentes ShadcnUI
```bash
npx shadcn-ui@latest add card
npx shadcn-ui@latest add badge
npx shadcn-ui@latest add progress
npx shadcn-ui@latest add tooltip
npx shadcn-ui@latest add tabs
npx shadcn-ui@latest add alert-dialog
npx shadcn-ui@latest add button
```

### Cores Utilizadas
- **Blue**: Informações, ações primárias
- **Green**: Sucesso, status ativo, lucros
- **Red**: Erro, perda, ações destrutivas
- **Amber/Yellow**: Avisos, transições
- **Purple/Pink**: Prima, afiliados, especial
- **Gray**: Neutro, background

---

## 🎬 Animações & Micro-interactions

### Confetti Explosion
Ativada quando:
- ✨ Bot iniciado com sucesso
- 💰 Novo tier de afiliado atingido
- 🎯 Objetivo alcançado

```tsx
import ConfettiExplosion from 'react-confetti-explosion';

{showConfetti && <ConfettiExplosion particleCount={30} />}
```

### Pulsing Status
- Bot ativo: checkmark animado / pulsing
- Carregamento: spinner circular
- Progresso: animação de largura

### Hover Effects
- Elevação de shadows em cards
- Transições de cor em botões
- Scale suave em ícones

---

## 📦 Integração com Backend

### API Endpoints Esperados

```typescript
// Get credits
GET /api/v1/auth/profile/activation-credits
Response: {
  plan: 'pro',
  activationCredits: 5,
  activationCreditsUsed: 2,
  activationCreditsRemaining: 3,
  activeBotsCount: 1
}

// Validate bot activation
POST /api/v1/bots/{botId}/validate-activation
Response: {
  isValid: true,
  runningBotId?: 'bot-x',
  data: {}
}

// Validate swap cost
POST /api/v1/bots/{botId}/validate-swap
Response: {
  isFree: true,
  cost: 0,
  swapCount: 1
}

// Start bot
POST /api/v1/bots/{botId}/start
Response: { success: true, botId, isRunning: true }

// Stop bot
POST /api/v1/bots/{botId}/stop
Response: { success: true, botId, isRunning: false }

// Update config
PUT /api/v1/bots/{botId}/config
Body: { setting: value }
Response: { success: true, updatedConfig }

// Upgrade plan
POST /api/v1/users/upgrade-plan
Body: { plan: 'premium' }
Response: { plan, activationCredits, ... }
```

---

## 🎯 Gamification Elements

### Visual Feedback
- ✅ **Green Check**: Ação bem-sucedida
- ⚠️ **Yellow Alert**: Aviso (últimos créditos, limite próximo)
- ❌ **Red X**: Erro ou ação negada
- 💫 **Confetti**: Celebração de milestone

### Escassez Visual
- Progress bars mostram créditos usados
- Badges de tier incentivam upgrade
- Contador regressivo de swaps grátis
- Campos "cambaleantes" quando sem créditos

### Dopamina Hits
- Animação de sucesso ao iniciar bot
- Confetti ao atingir novo tier
- Green badges em ações bem-sucedidas
- Sons (opcional): ding ao sucesso

---

## 🧪 Testing

### Unit Test Example
```tsx
import { render, screen } from '@testing-library/react';
import { CreditMonitor } from './CreditMonitor';

describe('CreditMonitor', () => {
  it('renders credit count', () => {
    render(
      <CreditMonitor
        plan="pro"
        activationCredits={5}
        activationCreditsUsed={2}
        activationCreditsRemaining={3}
        activeBotsCount={1}
      />
    );

    expect(screen.getByText(/2 \/ 5/)).toBeInTheDocument();
    expect(screen.getByText(/3 créditos disponíveis/i)).toBeInTheDocument();
  });
});
```

---

## 📱 Responsive Design

Todos os componentes são:
- ✅ Mobile-first
- ✅ Tablet-optimized
- ✅ Desktop-ready
- ✅ Touch-friendly buttons (min 44px)
- ✅ Grid responsivo (1col → 2col → 3col)

---

## 🚀 Deployment Checklist

- [ ] useCredits hook conectado ao backend real
- [ ] Auth token obtido de localStorage / context
- [ ] API_BASE_URL configurado em .env
- [ ] Componentes ShadcnUI instalados
- [ ] Tailwind CSS configurado
- [ ] Fonts customizadas carregados
- [ ] Dark mode (opcional) testado
- [ ] Mobile responsividade verificada
- [ ] Modais aparecem corretamente
- [ ] Animações suaves sem lag
- [ ] Error handling funciona
- [ ] Toast/notifications configurado

---

## 💡 Pro Tips

1. **Debounce de cliques**: Use `useCallback` + timeouts para prevenir múltiplos cliques
2. **Otimizar queries**: Use `staleTime` e `cacheTime` no React Query
3. **Error boundaries**: Wrap Dashboard em ErrorBoundary para crashes
4. **Suspense**: Use Suspense para loading states
5. **Locale**: I18n para suportar múltiplos idiomas
6. **Accessibility**: Use ARIA labels, teste com screen readers
7. **Analytics**: Track quando usuário vê warnings, clica em upgrade, etc

---

## 📝 Próximos Passos

1. [ ] Implementar notificações (Toast)
2. [ ] Adicionar Dark Mode
3. [ ] Integrar com Stripe/pagamentos
4. [ ] Adicionar histórico detalhado
5. [ ] WebSocket para updates em tempo real
6. [ ] Exportar relatórios (CSV, PDF)
7. [ ] Mobile app (React Native)
8. [ ] Análise de créditos usados ao longo do tempo

---

**Status**: ✅ Pronto para integração  
**Versão**: 1.0  
**Último Update**: 2026-02-11
